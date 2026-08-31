"""Eval 2 — is the response appropriate for the condition it was given?

The question the benchmark exists to answer. A model hears the same conversation three ways
and answers each; if those answers are interchangeable, the sounds did nothing.

Scoring is pairwise, per your plan. For each item and model, the response to condition X is
paired against the response to each of the other two conditions, and a judge that can see
condition X's transcript — tags included — ranks the pair. The matched response should win.

    condition happy:  (happy vs neutral) and (happy vs sad)
    condition sad:    (sad vs neutral)   and (sad vs happy)
    condition neutral:(neutral vs happy) and (neutral vs sad)

Order within a pair is randomized, the judge never learns which is which, and each pair is
judged three times: two of three agreeing decides it, otherwise the pair is flagged for a
human rather than counted.

The judge sees the tagged transcript, so it knows what the condition is. That is deliberate —
it is a gold-standard ranking, not a blind discrimination test. What is being measured is
whether the response fits the condition, not whether a judge can tell conditions apart.

Chance is 50%. A model whose three responses are interchangeable scores 50%.

Usage:
    python benchmark/eval2_appropriateness.py --limit 3
    python benchmark/eval2_appropriateness.py
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live
load_dotenv(REPO / ".env")

TRIALS = HERE / "out" / "trials.jsonl"
TRANSCRIPTS = HERE / "out" / "transcripts.json"
VOTES = HERE / "out" / "eval2_votes.jsonl"
OUT_JSON = HERE / "out" / "eval2_appropriateness.json"
OUT_MD = HERE / "out" / "eval2_appropriateness.md"

JUDGE = "gpt-5.6-terra"
CONDITIONS = ("neutral", "happy", "sad")
ROUNDS = 3
WORKERS = 6

SYSTEM = (
    "You judge which of two replies fits a conversation better.\n\n"
    "You will see a transcript of a conversation between two people, written out with the "
    "non-speech sounds marked in brackets exactly where they occurred. Then two replies, A "
    "and B, each written by someone who heard the conversation and was asked to speak next "
    "as a third person.\n\n"
    "Decide which reply better fits this conversation as it was actually said — the words and "
    "the sounds together. A reply that answers the mood in the room fits better than one that "
    "ignores it.\n\n"
    "Answer with exactly one line:\nBETTER: A or B"
)

_lock = threading.Lock()


def prompt_for(transcript: list[str], first: str, second: str, expectation: str) -> str:
    return "\n".join([
        "The conversation, as it was said:", "", *transcript, "",
        f"For reference, a good next turn would: {expectation}", "",
        "Two replies:", "", f"A. {first}", "", f"B. {second}", "",
        "Which fits better?",
    ])


def recorded() -> set[tuple]:
    if not VOTES.exists():
        return set()
    return {(r["provider"], r["item_id"], r["condition"], r["against"], r["round"])
            for r in map(json.loads, VOTES.read_text(encoding="utf-8").splitlines()) if r}


def record(row: dict) -> None:
    with _lock:
        with VOTES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def judge_once(client: OpenAI, key: tuple, transcript: list[str], matched: str,
               other: str, expectation: str, seed: int, model: str) -> dict:
    provider, item_id, condition, against, round_no = key
    # randomize which slot the matched response occupies, per round
    matched_is_a = random.Random(seed).random() < 0.5
    first, second = (matched, other) if matched_is_a else (other, matched)
    try:
        response = client.responses.create(
            model=model, instructions=SYSTEM,
            input=prompt_for(transcript, first, second, expectation),
            max_output_tokens=2000, reasoning={"effort": "low"})
        answer = (response.output_text or "").strip()
        pick = re.search(r"(?im)^\s*BETTER\s*:\s*([AB])", answer)
        chose = pick.group(1).upper() if pick else "?"
        correct = (chose == "A") == matched_is_a if chose in ("A", "B") else None
        row = {"provider": provider, "item_id": item_id, "condition": condition,
               "against": against, "round": round_no, "matched_is_a": matched_is_a,
               "chose": chose, "correct": correct}
    except Exception as exc:
        row = {"provider": provider, "item_id": item_id, "condition": condition,
               "against": against, "round": round_no,
               "error": f"{type(exc).__name__}: {str(exc)[:120]}", "correct": None}
    record(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="first N items only")
    parser.add_argument("--providers", default="openai,gemini,qwen",
                        help="whose replies to score; grok is out until it can hear audio")
    parser.add_argument("--model", default=JUDGE)
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = {i["item_id"]: i for i in
             json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))["items"] if "error" not in i}
    trials = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    trials = [t for t in trials if "error" not in t]
    latest = {(t["provider"], t["item_id"], t["condition"]): t for t in trials}

    providers = sorted({p for p, _, _ in latest})
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    item_ids = sorted({i for _, i, _ in latest})
    if args.limit:
        item_ids = item_ids[: args.limit]

    if args.fresh and VOTES.exists():
        VOTES.unlink()
    done = recorded()

    jobs = []
    for provider in providers:
        for item_id in item_ids:
            for condition in CONDITIONS:
                matched = latest.get((provider, item_id, condition))
                if matched is None or item_id not in items:
                    continue
                for against in CONDITIONS:
                    if against == condition:
                        continue
                    other = latest.get((provider, item_id, against))
                    if other is None:
                        continue
                    for round_no in range(1, args.rounds + 1):
                        key = (provider, item_id, condition, against, round_no)
                        if key in done:
                            continue
                        jobs.append((key, items[item_id], matched["response"],
                                     other["response"]))

    print(f"{len(providers)} model(s) × {len(item_ids)} items × 3 conditions × 2 pairs × "
          f"{args.rounds} rounds · {len(jobs)} judgements to run", flush=True)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {}
        for key, item, matched, other in jobs:
            condition = key[2]
            seed = hash(key) & 0xFFFF
            futures[pool.submit(judge_once, client, key,
                                item["rendered"][condition], matched, other,
                                item[condition]["expectation"], seed, args.model)] = key
        finished = 0
        for future in as_completed(futures):
            future.result()
            finished += 1
            if finished % 25 == 0:
                print(f"  {finished}/{len(jobs)}", flush=True)

    rows = [json.loads(l) for l in VOTES.read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs = defaultdict(list)
    for r in rows:
        if r.get("correct") is not None:
            pairs[(r["provider"], r["item_id"], r["condition"], r["against"])].append(
                r["correct"])

    scored, unstable = {}, []
    for key, votes in pairs.items():
        yes = sum(votes)
        if len(votes) < 2 or yes == len(votes) - yes:
            unstable.append(key)
            continue
        scored[key] = yes > len(votes) / 2

    by = defaultdict(list)
    for (provider, item_id, condition, against), ok in scored.items():
        by[(provider, "all")].append(ok)
        by[(provider, condition)].append(ok)

    lines = ["# Eval 2 — does the response fit the condition it was given", "",
             f"Judge `{args.model}`, {args.rounds} rounds per pair, order randomized, "
             "majority decides. Chance is 50%: a model whose three responses are "
             "interchangeable scores 50%.", "",
             "| model | overall | neutral | happy | sad | flagged |",
             "| --- | --- | --- | --- | --- | --- |"]
    summary = {}
    for provider in providers:
        cells = []
        for condition in ("all", "neutral", "happy", "sad"):
            votes = by[(provider, condition)]
            pct = 100 * sum(votes) / len(votes) if votes else 0.0
            summary[f"{provider}_{condition}"] = round(pct, 1)
            cells.append(f"{pct:.0f}% ({sum(votes)}/{len(votes)})" if votes else "—")
        flagged = sum(1 for k in unstable if k[0] == provider)
        lines.append(f"| {provider} | " + " | ".join(cells) + f" | {flagged} |")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "judge": args.model, "rounds": args.rounds, "summary": summary,
        "unstable_pairs": [list(k) for k in unstable],
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n{len(scored)} pairs decided · {len(unstable)} flagged for a human")


if __name__ == "__main__":
    main()

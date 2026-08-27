"""Q2 — tone alignment, rated 0-4 by a speech panel that listens to the reply.

Q1 asks whether a model said something apt; this asks whether it *sounded* right. The gold is
the one-sentence expected tone written in stage 5 from the transcript with the sounds in it, so
the target is a described delivery rather than a label from a fixed list. 1.0 scored tone by
exact match against one of six labels, which meant a reply described as "gently wry" scored
zero against a gold of "dryly sympathetic" — a disagreement about vocabulary counted as a
failure of delivery.

The panel is openai, gemini and qwen, **leave-one-out**: no model rates its own reply. Grok is
rated by all three; each panel member is rated by the other two. That asymmetry is recorded per
response rather than hidden, since a mean over two judges is noisier than over three.

Judges hear the reply audio alone, not the conversation. Giving them the conversation would
tell them which condition they were rating, and a judge that knows the answer is not rating
tone.

Neutral replies are not rated — there is no gold tone for a conversation with no sounds in it.

    python 2.0/eval_q2.py
    python 2.0/eval_q2.py --providers grok
"""

from __future__ import annotations

import argparse
import json
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TRIALS = OUT / "trials.jsonl"
RATINGS = OUT / "eval_q2_ratings.jsonl"
RESULT = OUT / "eval_q2.json"

PANEL = ("openai", "gemini", "qwen")
SCORED = ("happy", "sad")
CONCURRENCY = {"openai": 3, "gemini": 3, "qwen": 3}
RETRIES = 3

QUESTION = (
    "You will hear one short spoken reply. Judge only how it is delivered — its tone, warmth, "
    "energy, pacing — not whether you agree with what it says.\n\n"
    "The reply was supposed to sound like this: {tone}\n\n"
    "How well does the tone of what you heard match that description?\n"
    "0 = strongly mismatched\n1 = mostly mismatched\n2 = neither\n3 = mostly matched\n"
    "4 = strongly matched\n\n"
    "Answer with one digit, 0 to 4, and nothing else."
)

_sema = {name: threading.Semaphore(n) for name, n in CONCURRENCY.items()}
_lock = threading.Lock()


def score_of(answer: str) -> int | None:
    match = re.search(r"\b([0-4])\b", (answer or "").strip())
    return int(match.group(1)) if match else None


def record(row: dict) -> None:
    with _lock:
        with RATINGS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recorded() -> set[tuple]:
    if not RATINGS.exists():
        return set()
    done = set()
    for line in RATINGS.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("score") is not None:
                done.add((row["judge"], row["provider"], row["item_id"], row["condition"]))
    return done


def rate(judge: str, row: dict, tone: str) -> dict:
    audio = HERE / row["response_audio"]
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            with _sema[judge]:
                answer = P.ask(judge, audio, QUESTION.format(tone=tone))
            score = score_of(answer)
            if score is not None:
                out = {"judge": judge, "provider": row["provider"],
                       "item_id": row["item_id"], "condition": row["condition"],
                       "score": score, "raw": (answer or "").strip()[:80]}
                record(out)
                return out
            last = f"unparsed: {(answer or '')[:60]!r}"
        except Exception as exc:                    # noqa: BLE001 - recorded, then retried
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
    out = {"judge": judge, "provider": row["provider"], "item_id": row["item_id"],
           "condition": row["condition"], "score": None, "error": last}
    record(out)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers")
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold = {e["item_id"]: e for e in json.loads((OUT / "gold.json").read_text())["items"]}

    rows = [json.loads(line) for line in TRIALS.read_text().splitlines() if line.strip()]
    latest = {}
    for row in rows:
        if "error" not in row and row.get("response_audio") and row["condition"] in SCORED:
            latest[(row["provider"], row["item_id"], row["condition"])] = row
    if args.providers:
        keep = {p.strip() for p in args.providers.split(",")}
        latest = {k: v for k, v in latest.items() if k[0] in keep}

    missing_audio = [k for k, v in latest.items() if not (HERE / v["response_audio"]).exists()]
    if missing_audio:
        print(f"  {len(missing_audio)} replies have no audio on disk; skipping them")
        latest = {k: v for k, v in latest.items() if k not in missing_audio}

    done = recorded()
    jobs = []
    for (provider, item_id, condition), row in sorted(latest.items()):
        tone = gold[item_id][condition]["tone"]
        for judge in PANEL:
            if judge == provider:                  # never rates its own reply
                continue
            if (judge, provider, item_id, condition) in done:
                continue
            jobs.append((judge, row, tone))

    print(f"{len(latest)} replies · {len(jobs)} ratings to collect "
          f"({len(done)} already recorded)\n")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(rate, *job) for job in jobs]
        for n, future in enumerate(as_completed(futures), start=1):
            future.result()
            if n % 25 == 0:
                print(f"  [{n}/{len(jobs)}]", flush=True)

    ratings = [json.loads(l) for l in RATINGS.read_text().splitlines() if l.strip()]
    ratings = [r for r in ratings if r.get("score") is not None]
    by_response = defaultdict(list)
    for r in ratings:
        by_response[(r["provider"], r["item_id"], r["condition"])].append(r["score"])

    per_provider = defaultdict(list)
    per_cell = defaultdict(list)
    judges_used = defaultdict(list)
    for (provider, item_id, condition), scores in by_response.items():
        mean = sum(scores) / len(scores)
        per_provider[provider].append(mean)
        per_cell[(provider, condition)].append(mean)
        judges_used[provider].append(len(scores))

    print("\nQ2 tone alignment — mean of the panel's 0-4 ratings")
    print(f"  {'model':8} {'overall':>9} {'happy':>9} {'sad':>9} {'judges':>8}")
    for provider in sorted(per_provider):
        overall = sum(per_provider[provider]) / len(per_provider[provider])
        cells = []
        for condition in SCORED:
            values = per_cell[(provider, condition)]
            cells.append(f"{sum(values)/len(values):.2f}" if values else "  -")
        panel = sum(judges_used[provider]) / len(judges_used[provider])
        print(f"  {provider:8} {overall:9.2f} {cells[0]:>9} {cells[1]:>9} {panel:8.1f}")

    per_judge = defaultdict(list)
    for r in ratings:
        per_judge[r["judge"]].append(r["score"])
    print("\n  how each judge rates in general")
    for judge in sorted(per_judge):
        values = per_judge[judge]
        print(f"    {judge:8} mean {sum(values)/len(values):.2f} over {len(values)} ratings")

    RESULT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "panel": list(PANEL), "leave_one_out": True, "ratings": len(ratings),
        "scale": "0 strongly mismatched to 4 strongly matched, against the stage-5 gold tone",
        "per_provider": {p: round(sum(v)/len(v), 3) for p, v in per_provider.items()},
        "per_condition": {f"{p}|{c}": round(sum(v)/len(v), 3)
                          for (p, c), v in per_cell.items()},
        "per_judge_mean": {j: round(sum(v)/len(v), 3) for j, v in per_judge.items()}},
        indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {RESULT.name}")


if __name__ == "__main__":
    main()

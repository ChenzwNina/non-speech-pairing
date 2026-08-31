"""Evals 1 and 3 — listen to each response and report its sounds and its tone.

Both questions are about the same recording, so they are asked in one listening pass per
judge instead of two: the judge hears the reply, answers what non-speech sounds are in it,
then answers what tone it carries. That halves the sessions without changing either measure.

    eval 1   a reply to the happy condition should not contain sighing, and a reply to the
             sad condition should not contain laughter. The must-not-appear list was written
             per condition before any model was run. Scored 1 if the majority of judges hear
             nothing from that list, 0 otherwise.

    eval 3   the gold tone was also written before any model was run. Scored 1 if the
             majority label matches it.

Answers are constrained to a letter and a label from a fixed set, so the majority is counted
mechanically. Free text is collected alongside for audit but not scored — an LLM asked whether
two prose descriptions "mean the same thing" is a judgement call standing in for arithmetic.

Judges are the models that pass the audio preflight, and a model never judges its own reply.

Usage:
    python benchmark/eval13_response_audio.py --limit 2
    python benchmark/eval13_response_audio.py
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live
TRIALS = HERE / "out" / "trials.jsonl"
TRANSCRIPTS = HERE / "out" / "transcripts.json"
JUDGMENTS = HERE / "out" / "eval13_judgments.jsonl"
OUT_JSON = HERE / "out" / "eval13_response_audio.json"
OUT_MD = HERE / "out" / "eval13_response_audio.md"

TONES = ("amused", "teasing", "sympathetic", "consoling", "neutral", "curious")

# Six labels are finer than judges can reliably resolve. Sympathetic and consoling are one
# stance at two strengths, as are amused and teasing — and gold splits the sad items 13/7
# across the first pair and the happy items 12/8 across the second. A reply judged consoling
# against a gold of sympathetic then scores zero while being right about everything that
# matters. Family match is the headline; exact match is reported beside it.
FAMILY = {"amused": "light", "teasing": "light",
          "sympathetic": "warm", "consoling": "warm",
          "neutral": "flat", "curious": "flat"}

TASK = (
    "You will hear one short spoken reply, recorded by someone taking their turn in a "
    "conversation. Listen to how it is said, not only what it says.\n\n"
    "First question. Apart from the words, does the reply contain any non-speech sounds:\n"
    "A. laughter\nB. sighing\nC. neither\nD. both\n\n"
    "Answer in exactly two lines:\nANSWER: <letter>\nBECAUSE: a few words on what you hear"
)
FOLLOWUP = (
    "Second question, about the same reply. Which one word best describes the speaker's "
    "tone?\n" + "\n".join(f"- {t}" for t in TONES) + "\n\n"
    "Answer in exactly two lines:\nTONE: <one of the words above>\nBECAUSE: a few words"
)

SOUND_OF = {"A": "laughter", "B": "sighing", "C": "neither", "D": "both"}
FORBIDDEN = {"happy": "laughter", "sad": "sighing"}   # what a reply MAY contain per condition

_lock = threading.Lock()


def parse(answer: str, followup: str) -> dict:
    letter = re.search(r"(?im)^\s*ANSWER\s*:\s*([ABCD])", answer or "")
    tone = re.search(r"(?im)^\s*TONE\s*:\s*([a-z]+)", followup or "")
    label = tone.group(1).lower() if tone else ""
    if label not in TONES:
        label = next((t for t in TONES if t in (followup or "").lower()), "")
    return {"sound": SOUND_OF.get(letter.group(1).upper()) if letter else "",
            "tone": label, "sound_raw": (answer or "").strip()[:200],
            "tone_raw": (followup or "").strip()[:200]}


def recorded() -> set[tuple]:
    if not JUDGMENTS.exists():
        return set()
    # only successes count as done — a recorded failure is work still to do
    return {(r["judge"], r["provider"], r["item_id"], r["condition"])
            for r in map(json.loads, JUDGMENTS.read_text(encoding="utf-8").splitlines())
            if r and "error" not in r}


def record(row: dict) -> None:
    with _lock:
        with JUDGMENTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def judge(trial: dict, judge_name: str) -> dict:
    audio = FAMILY / trial["response_audio"]
    base = {"judge": judge_name, "provider": trial["provider"],
            "item_id": trial["item_id"], "condition": trial["condition"]}
    last = ""
    for attempt in range(3):          # DNS and handshake failures come in bursts
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                out = P.converse(judge_name, audio, TASK, [FOLLOWUP])
            row = {**base, **parse(out["response"], out["answers"][0])}
            record(row)
            return row
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
            time.sleep(2 ** attempt)
    row = {**base, "error": last}
    record(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judges", default="openai,gemini,qwen")
    parser.add_argument("--providers", default="openai,gemini,qwen",
                        help="whose replies to score; grok is out until it can hear audio")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--group-tones", action="store_true",
                        help="score tone by family (light/warm/flat) rather than exact "
                             "label — for data generated after this change, not for "
                             "rescoring a run measured on exact match")
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    group_tones = args.group_tones
    items = {i["item_id"]: i for i in
             json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))["items"] if "error" not in i}
    trials = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    scored_providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    trials = [t for t in trials if "error" not in t and t.get("response_audio")
              and t["provider"] in scored_providers]
    if args.limit:
        keep = sorted({t["item_id"] for t in trials})[: args.limit]
        trials = [t for t in trials if t["item_id"] in keep]

    if args.fresh and JUDGMENTS.exists():
        JUDGMENTS.unlink()
    done = recorded()
    jobs = [(t, j) for t in trials for j in judges
            if j != t["provider"]                      # never judge your own reply
            and (j, t["provider"], t["item_id"], t["condition"]) not in done]
    print(f"{len(trials)} replies × {len(judges)} judges (minus self) · {len(jobs)} to run",
          flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(judge, t, j): (t, j) for t, j in jobs}
        finished = 0
        for future in as_completed(futures):
            future.result()
            finished += 1
            if finished % 25 == 0:
                print(f"  {finished}/{len(jobs)}", flush=True)

    rows = [json.loads(l) for l in JUDGMENTS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    grouped = defaultdict(list)
    for r in rows:
        if "error" not in r:
            grouped[(r["provider"], r["item_id"], r["condition"])].append(r)

    eval1, eval3 = defaultdict(list), defaultdict(list)
    eval3_exact = defaultdict(list)
    detail = []
    for (provider, item_id, condition), votes in grouped.items():
        sounds = Counter(v["sound"] for v in votes if v["sound"])
        tones = Counter(v["tone"] for v in votes if v["tone"])
        if not sounds or not tones:
            continue
        heard, _ = sounds.most_common(1)[0]
        tone, _ = tones.most_common(1)[0]

        allowed = FORBIDDEN.get(condition)          # laughter ok in happy, sighing in sad
        contains = {"laughter"} if heard == "laughter" else \
                   {"sighing"} if heard == "sighing" else \
                   {"laughter", "sighing"} if heard == "both" else set()
        wrong = {s for s in contains if s != allowed}
        eval1[provider].append(0.0 if wrong else 1.0)

        gold = items[item_id][condition]["tone_label"]
        exact = tone == gold
        same_family = FAMILY.get(tone) == FAMILY.get(gold)
        # exact match is the score. Family grouping came later, and applying it to a run
        # already measured the other way would change results after the fact — it is
        # available with --group-tones for data generated from here on.
        eval3[provider].append(1.0 if (same_family if group_tones else exact) else 0.0)
        eval3_exact[provider].append(1.0 if exact else 0.0)
        detail.append({"provider": provider, "item_id": item_id, "condition": condition,
                       "heard": heard, "unwanted": sorted(wrong), "tone": tone,
                       "gold_tone": gold, "exact": exact, "same_family": same_family,
                       "votes": len(votes)})

    providers = sorted(eval1)
    lines = ["# Evals 1 and 3 — the response audio", "",
             f"Judges: {', '.join(judges)}, majority per reply, no model judging its own.", "",
             f"| model | eval 1 · no unwanted sound | eval 3 · tone "
             f"({'family' if group_tones else 'exact label'}) |",
             "| --- | --- | --- |"]
    for provider in providers:
        a, b = eval1[provider], eval3[provider]
        lines.append(f"| {provider} | {100*sum(a)/len(a):.0f}% ({sum(a):.0f}/{len(a)}) "
                     f"| {100*sum(b)/len(b):.0f}% ({sum(b):.0f}/{len(b)}) |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "judges": judges, "tones": list(TONES),
        "eval1": {p: round(sum(v)/len(v), 3) for p, v in eval1.items()},
        "scoring": "family" if group_tones else "exact",
        "eval3": {p: round(sum(v)/len(v), 3) for p, v in eval3.items()},
        "eval3_exact": {p: round(sum(v)/len(v), 3) for p, v in eval3_exact.items()},
        "detail": detail, "scored_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

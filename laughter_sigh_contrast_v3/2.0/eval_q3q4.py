"""Q3 and Q4 — pragmatic function and perception, scored by comparing letters.

Both are multiple choice with a known gold, so neither needs a judge. The only judgement
involved is reading a model's answer as a letter, which is why the parser is strict and
anything it cannot read is reported as unparsed rather than counted as wrong: a model that
replied "I heard laughter" has not failed the perception question, it has failed the format,
and folding the two together would flatter or punish models for the wrong reason.

Q3 asks how the two speakers treat the story. Gold is the answer written for the condition the
model actually heard, so getting it right means the sounds moved the reading.

Q4 asks which vocalization was heard. Gold is laughter for happy and a sigh for sad. Chance is
25%, and the wrong options include the *other* real vocalization, so confusing a sigh for
laughter costs the same as inventing a yawn.

Neutral is not scored: it was never asked.

    python 2.0/eval_q3q4.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TRIALS = OUT / "trials.jsonl"
RESULT = OUT / "eval_q3q4.json"


def letter(answer: str) -> str | None:
    """The letter a model chose, or None if it did not give one.

    Accepts "B", "B.", "(b)", "Answer: B", "B. they are ..." — a leading letter followed by a
    boundary. Rejects prose that merely contains a capital letter somewhere.
    """
    text = (answer or "").strip()
    if not text:
        return None
    match = re.match(r"^\W*(?:answer\s*[:\-]?\s*)?([A-D])\b", text, re.I)
    if match:
        return match.group(1).upper()
    match = re.fullmatch(r"\W*([A-D])\W*", text, re.I)
    return match.group(1).upper() if match else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers")
    args = parser.parse_args()

    rows = [json.loads(line) for line in TRIALS.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r.get("scored") and "error" not in r]
    if args.providers:
        keep = {p.strip() for p in args.providers.split(",")}
        rows = [r for r in rows if r["provider"] in keep]
    # A resumed run can hold more than one row per trial; the last one is the one that stuck.
    latest = {}
    for row in rows:
        latest[(row["provider"], row["item_id"], row["condition"])] = row
    rows = list(latest.values())

    options_by_item = {e["item_id"]: e
                       for e in json.loads((OUT / "q3_options.json").read_text())["items"]}
    tally = defaultdict(lambda: defaultdict(lambda: {"right": 0, "asked": 0, "unparsed": 0}))
    detail = []
    for row in rows:
        for q in ("q3", "q4"):
            chose = letter(row.get(f"{q}_answer"))
            gold = row[f"{q}_gold_letter"]
            bucket = tally[q][row["provider"]]
            bucket["asked"] += 1
            if chose is None:
                bucket["unparsed"] += 1
            elif chose == gold:
                bucket["right"] += 1
            detail.append({"provider": row["provider"], "item_id": row["item_id"],
                           "condition": row["condition"], "question": q,
                           "gold": gold, "chose": chose,
                           "correct": chose == gold,
                           "raw": (row.get(f"{q}_answer") or "")[:120]})
        # When Q3 is wrong, what did it pick instead? The other condition's reading means
        # the sounds did not move it; a distractor means it read the conversation wrongly
        # altogether. Those are different failures and worth separating.
        chose3 = letter(row.get("q3_answer"))
        if chose3 and chose3 != row["q3_gold_letter"]:
            index = ord(chose3) - 65
            options = row["q3_options"]
            if 0 <= index < len(options):
                picked = options[index]
                entry = options_by_item.get(row["item_id"], {})
                other = entry["sad"] if row["condition"] == "happy" else entry.get("happy")
                detail[-2]["picked_text"] = picked
                detail[-2]["picked_other_condition"] = picked == other

    print(f"{len(rows)} scored trials\n")
    for q, label, chance in (("q3", "Q3 pragmatic function", 0.25),
                             ("q4", "Q4 perception", 0.25)):
        print(f"{label}   (chance {chance:.0%})")
        for provider, bucket in sorted(tally[q].items()):
            asked, right, unparsed = bucket["asked"], bucket["right"], bucket["unparsed"]
            scored = asked - unparsed
            print(f"  {provider:8} {right}/{asked} = {right/max(1,asked):.0%}"
                  + (f"   ({right}/{scored} = {right/max(1,scored):.0%} of parsed, "
                     f"{unparsed} unparsed)" if unparsed else ""))
        print()

    # Q3 by condition: is one framing easier to read than the other?
    by_cond = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        for q in ("q3", "q4"):
            chose = letter(row.get(f"{q}_answer"))
            cell = by_cond[q][(row["provider"], row["condition"])]
            cell[0] += chose == row[f"{q}_gold_letter"]
            cell[1] += 1
    for q, label in (("q3", "Q3"), ("q4", "Q4")):
        print(f"{label} by condition")
        providers = sorted({p for p, _ in by_cond[q]})
        print(f"  {'model':8} {'happy':>12} {'sad':>12}")
        for provider in providers:
            cells = []
            for condition in ("happy", "sad"):
                right, total = by_cond[q][(provider, condition)]
                cells.append(f"{right}/{total} = {right/max(1,total):3.0%}".rjust(12))
            print(f"  {provider:8} " + " ".join(cells))
        print()

    wrong3 = [d for d in detail if d["question"] == "q3" and d["chose"] and not d["correct"]]
    if wrong3:
        swapped = sum(1 for d in wrong3 if d.get("picked_other_condition"))
        print("Q3 wrong answers")
        print(f"  picked the other condition's reading  {swapped}/{len(wrong3)} "
              f"({swapped/len(wrong3):.0%})  <- heard it, read it the other way")
        print(f"  picked a distractor                   {len(wrong3)-swapped}/{len(wrong3)} "
              f"({(len(wrong3)-swapped)/len(wrong3):.0%})")
        print()

    RESULT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trials": len(rows),
        "scoring": "exact letter match against the condition's gold; chance is 25%",
        "summary": {q: {p: dict(b) for p, b in tally[q].items()} for q in tally},
        "detail": detail}, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {RESULT.name}")


if __name__ == "__main__":
    main()

"""Eval 4 — score what each model said it heard against what is actually there.

No judge anywhere in this file. `transcripts.json` records every insertion as
(turn, position, token), so type, count and location are all checkable arithmetic. That makes
this the one eval with no adjudication step and no circularity: the models under test do not
get a say in what the right answer was.

Three sub-scores per trial, averaged:

    type      the reported family matches the condition — laughter for happy, sigh for sad,
              nothing at all for neutral. Half credit if the right family is reported
              alongside the wrong one.
    count     1 - |reported - actual| / actual, floored at 0
    location  F1 over the set of turn numbers

Neutral is a false-alarm test and is scored strictly: the audio contains no vocalizations, so
anything reported there is invented and scores zero across the board. It is reported on its
own as well as inside the average, because a model that hears laughter everywhere would
otherwise look strong on the happy items.

Usage:
    python benchmark/eval4_perception.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRIALS = HERE / "out" / "trials.jsonl"
TRANSCRIPTS = HERE / "out" / "transcripts.json"
OUT_JSON = HERE / "out" / "eval4_perception.json"
OUT_MD = HERE / "out" / "eval4_perception.md"

# Two families. "breath" sits with sigh deliberately: an exhale reported as breathing is the
# same perception under a different word, and penalising the wording would measure vocabulary
# rather than hearing.
FAMILY = {
    "laugh": ("laugh", "laughter", "laughing", "chuckle", "chuckling", "giggle", "giggling",
              "snicker", "snickering", "titter", "chortle"),
    "sigh": ("sigh", "sighing", "exhale", "exhalation", "breath", "breathing", "huff",
             "groan", "moan"),
}
EXPECTED = {"happy": "laugh", "sad": "sigh", "neutral": None}


def family_of(name: str) -> str | None:
    low = name.strip().lower()
    for family, words in FAMILY.items():
        if any(word in low for word in words):
            return family
    return None


def parse_heard(text: str) -> dict[str, dict]:
    """{family: {count, turns}} from the model's SOUND/COUNT/TURNS lines."""
    if not text:
        return {}
    if re.search(r"(?i)^\s*none\b", text.strip()) and "SOUND" not in text.upper():
        return {}
    found: dict[str, dict] = defaultdict(lambda: {"count": 0, "turns": set(), "names": []})
    for line in text.splitlines():
        if "SOUND" not in line.upper():
            continue
        name = re.search(r"(?i)SOUND\s*:\s*([^|]+)", line)
        count = re.search(r"(?i)COUNT\s*:\s*(\d+)", line)
        turns = re.search(r"(?i)TURNS?\s*:\s*([0-9,\s]+)", line)
        if not name:
            continue
        family = family_of(name.group(1))
        if family is None:
            continue
        entry = found[family]
        entry["count"] += int(count.group(1)) if count else 1
        entry["names"].append(name.group(1).strip())
        if turns:
            entry["turns"].update(int(n) for n in re.findall(r"\d+", turns.group(1)))
    return dict(found)


def f1(reported: set, gold: set) -> float:
    if not gold and not reported:
        return 1.0
    if not gold or not reported:
        return 0.0
    hit = len(reported & gold)
    if not hit:
        return 0.0
    precision, recall = hit / len(reported), hit / len(gold)
    return 2 * precision * recall / (precision + recall)


def score(trial: dict, item: dict) -> dict:
    condition = trial["condition"]
    expected = EXPECTED[condition]
    heard = parse_heard(trial.get("heard", ""))

    if expected is None:                       # neutral: silence is the only right answer
        clean = not heard
        return {"type": float(clean), "count": float(clean), "location": float(clean),
                "reported": {f: {"count": v["count"], "turns": sorted(v["turns"])}
                             for f, v in heard.items()},
                "false_alarm": not clean}

    insertions = item["happy_insertions" if condition == "happy" else "sad_insertions"]
    gold_turns = {i["turn"] for i in insertions}
    gold_count = len(insertions)

    other = "sigh" if expected == "laugh" else "laugh"
    if expected in heard:
        type_score = 0.5 if other in heard else 1.0
    else:
        type_score = 0.0

    entry = heard.get(expected, {"count": 0, "turns": set()})
    count_score = max(0.0, 1 - abs(entry["count"] - gold_count) / gold_count)
    location_score = f1(entry["turns"], gold_turns)
    return {"type": type_score, "count": count_score, "location": location_score,
            "gold_count": gold_count, "gold_turns": sorted(gold_turns),
            "reported": {f: {"count": v["count"], "turns": sorted(v["turns"])}
                         for f, v in heard.items()},
            "false_alarm": False}


def main() -> None:
    items = {i["item_id"]: i for i in
             json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))["items"] if "error" not in i}
    trials = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    trials = [t for t in trials if "error" not in t]
    # last recorded attempt wins
    latest = {(t["provider"], t["item_id"], t["condition"]): t for t in trials}

    scored = []
    for (provider, item_id, condition), trial in latest.items():
        if item_id not in items:
            continue
        result = score(trial, items[item_id])
        result["mean"] = (result["type"] + result["count"] + result["location"]) / 3
        scored.append({"provider": provider, "item_id": item_id, "condition": condition,
                       "heard_raw": trial.get("heard", ""), **result})

    by = defaultdict(list)
    for row in scored:
        by[(row["provider"], row["condition"])].append(row)
        by[(row["provider"], "all")].append(row)

    providers = sorted({r["provider"] for r in scored})
    lines = ["# Eval 4 — did the models hear the vocalizations", "",
             "Mechanical scoring against the insertion list. No judge involved.", "",
             "| model | overall | happy | sad | neutral (false alarms) |",
             "| --- | --- | --- | --- | --- |"]
    summary = {}
    for provider in providers:
        cells = []
        for condition in ("all", "happy", "sad", "neutral"):
            rows = by[(provider, condition)]
            mean = sum(r["mean"] for r in rows) / len(rows) if rows else 0.0
            summary[f"{provider}_{condition}"] = round(mean, 3)
            if condition == "neutral":
                alarms = sum(r["false_alarm"] for r in rows)
                cells.append(f"{mean:.2f}  ({alarms}/{len(rows)} invented)")
            else:
                cells.append(f"{mean:.2f}")
        lines.append(f"| {provider} | " + " | ".join(cells) + " |")

    lines += ["", "## Sub-scores on the conditions that have vocalizations", "",
              "| model | condition | type | count | location |", "| --- | --- | --- | --- | --- |"]
    for provider in providers:
        for condition in ("happy", "sad"):
            rows = by[(provider, condition)]
            if not rows:
                continue
            t = sum(r["type"] for r in rows) / len(rows)
            c = sum(r["count"] for r in rows) / len(rows)
            l = sum(r["location"] for r in rows) / len(rows)
            lines.append(f"| {provider} | {condition} | {t:.2f} | {c:.2f} | {l:.2f} |")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"summary": summary, "trials": scored},
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT_MD.name} and {OUT_JSON.name}")


if __name__ == "__main__":
    main()

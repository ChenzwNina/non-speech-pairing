"""Sample scenarios from EmpatheticDialogues to seed the contrastive pairs.

v3 drew only from `embarrassed`, because that label reads both ways on its own. v4 does not
need that from the seed: the contrast is carried by a vocalization the writer chooses, so the
scenario only has to be a situation two people could plausibly discuss. That opens the sampling
to the whole set of 32 labels.

Two are held out. A scenario about bereavement or terror cannot honestly support an `amusement`
or `pleasure` framing, and asking a model to hear one as funny is both incoherent and tasteless.

    python v4/seeds.py --n 40
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SOURCE = REPO / "archive" / "train.csv"
OUT = HERE / "out"

EXCLUDED = ("devastated", "terrified")
MIN_WORDS, MAX_WORDS = 6, 45


def clean(text: str) -> str:
    """EmpatheticDialogues escapes punctuation as _comma_ and friends."""
    text = text.replace("_comma_", ",").replace("_pipe_", "|").replace("_conj_", "and")
    return re.sub(r"\s+", " ", text).strip()


def usable(text: str) -> bool:
    return MIN_WORDS <= len(text.split()) <= MAX_WORDS and text[:1].isalpha()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--emotions", help="comma-separated; default is everything usable")
    args = parser.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} is missing; refetch from "
                         "github.com/facebookresearch/EmpatheticDialogues")

    seen: dict[str, dict] = {}
    with SOURCE.open(encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            emotion = row["context"].strip()
            if emotion in EXCLUDED:
                continue
            situation = clean(row["prompt"])
            if not usable(situation) or situation in seen:
                continue
            seen[situation] = {"emotion": emotion, "situation": situation,
                               "conv_id": row["conv_id"]}

    pool = list(seen.values())
    if args.emotions:
        wanted = {e.strip() for e in args.emotions.split(",")}
        pool = [r for r in pool if r["emotion"] in wanted]

    rng = random.Random(args.seed)
    by_emotion: dict[str, list[dict]] = {}
    for row in pool:
        by_emotion.setdefault(row["emotion"], []).append(row)
    for rows in by_emotion.values():
        rng.shuffle(rows)

    # Round-robin across labels rather than sampling the pool flat, so no emotion dominates.
    picked, order = [], sorted(by_emotion)
    while len(picked) < args.n and any(by_emotion.values()):
        rng.shuffle(order)
        for emotion in order:
            if by_emotion[emotion] and len(picked) < args.n:
                picked.append(by_emotion[emotion].pop())

    for index, row in enumerate(picked, start=1):
        row["item_id"] = f"v4_{index:03d}"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "seeds.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "EmpatheticDialogues train.csv",
        "excluded_emotions": list(EXCLUDED),
        "seed": args.seed, "n": len(picked), "items": picked},
        indent=2, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for row in picked:
        counts[row["emotion"]] = counts.get(row["emotion"], 0) + 1
    print(f"{len(seen):,} distinct usable scenarios · sampled {len(picked)} "
          f"across {len(counts)} emotions")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("\nwrote out/seeds.json")


if __name__ == "__main__":
    main()

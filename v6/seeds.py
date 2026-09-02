"""Sample scenarios from EmpatheticDialogues to seed the v6 dialogues.

v4 sampled round-robin across the 32 labels and held two of them out, because the pair it
assigned a seed could ask a bereavement scenario to read as `amusement`. v6 does not select on
the label at all: the contrast lives inside a single vocalization, and the scenario only has to
be a situation two people could plausibly talk about. So this is a flat random draw over the
whole file, with the label kept as metadata rather than used as a filter.

    python v6/seeds.py --n 60
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

MIN_WORDS, MAX_WORDS = 6, 45


def clean(text: str) -> str:
    """EmpatheticDialogues escapes punctuation as _comma_ and friends."""
    text = text.replace("_comma_", ",").replace("_pipe_", "|").replace("_conj_", "and")
    return re.sub(r"\s+", " ", text).strip()


def usable(text: str) -> bool:
    """Long enough to be a situation, short enough to be one situation."""
    return MIN_WORDS <= len(text.split()) <= MAX_WORDS and text[:1].isalpha()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} is missing; refetch from "
                         "github.com/facebookresearch/EmpatheticDialogues")

    # Keyed on the situation text: the file repeats each prompt once per utterance of the
    # conversation it seeded, so a flat read would sample popular conversations twice.
    seen: dict[str, dict] = {}
    with SOURCE.open(encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            situation = clean(row["prompt"])
            if not usable(situation) or situation in seen:
                continue
            seen[situation] = {"label": row["context"].strip(), "situation": situation,
                               "conv_id": row["conv_id"]}

    pool = list(seen.values())
    rng = random.Random(args.seed)
    picked = rng.sample(pool, min(args.n, len(pool)))
    for index, row in enumerate(picked, start=1):
        row["seed_id"] = f"s{index:03d}"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "seeds.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "EmpatheticDialogues train.csv",
        "selection": "flat random sample, no label restriction",
        "seed": args.seed, "n": len(picked), "items": picked},
        indent=2, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for row in picked:
        counts[row["label"]] = counts.get(row["label"], 0) + 1
    print(f"{len(pool):,} distinct usable scenarios · sampled {len(picked)} "
          f"touching {len(counts)} of the 32 labels")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("\nwrote v6/out/seeds.json")


if __name__ == "__main__":
    main()

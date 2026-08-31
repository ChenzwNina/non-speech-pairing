"""Sample persona candidates from the PersonaChat sentence pool.

PersonaChat profiles are four or five sentences describing one person. The copy available here
is a flat list of 6,732 sentences with the grouping lost, and sampling five at random from it
produces people who already have grandchildren while studying for their GCSEs.

Rather than reconstruct the profiles, this hands the writer five candidates per speaker and
asks it to keep only the ones that can describe the same person. Coherence is judged where the
story is written, by something that can read the sentences, and the selection is reported back
so it can be checked against what was offered.

    python v5/personas.py --n 40
"""

from __future__ import annotations

import argparse
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
POOL = Path("/Users/ninachen/Documents/github/audio-as-thinking/personas.txt")
OUT = HERE / "out"

CANDIDATES = 5      # offered per speaker; the writer keeps the compatible ones


def tidy(line: str) -> str:
    """PersonaChat writes " i m a doctor ." — space before punctuation, no capitals."""
    text = re.sub(r"\s+([.,!?'])", r"\1", line.strip())
    text = re.sub(r"\bi\b", "I", text)
    # the pool has apostrophes stripped: "I m", "don t", "it s"
    text = re.sub(r"\bI m\b", "I'm", text)
    text = re.sub(r"(\w)n t\b", r"\1n't", text)
    return text[:1].upper() + text[1:] if text else text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not POOL.exists():
        raise SystemExit(f"{POOL} is missing")
    lines = [tidy(l) for l in POOL.read_text(encoding="utf-8").splitlines() if l.strip()]
    # The pool holds near-duplicate spellings of the same sentence; collapse them so one
    # persona does not receive the same fact twice in two spellings.
    seen, pool = set(), []
    for line in lines:
        key = re.sub(r"[^a-z ]", "", line.lower())
        key = re.sub(r"\s+", " ", key).strip()
        if key and key not in seen:
            seen.add(key)
            pool.append(line)

    rng = random.Random(args.seed)
    items = []
    for index in range(1, args.n + 1):
        picked = rng.sample(pool, CANDIDATES * 2)
        items.append({"item_id": f"v5_{index:03d}",
                      "candidates_a": picked[:CANDIDATES],
                      "candidates_b": picked[CANDIDATES:]})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "personas.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(POOL), "pool_size": len(pool),
        "candidates_per_speaker": CANDIDATES, "seed": args.seed,
        "items": items}, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(lines):,} lines · {len(pool):,} after collapsing near-duplicates")
    print(f"{len(items)} items, {CANDIDATES} candidates per speaker")
    print("\nexample candidates for one speaker:")
    for line in items[0]["candidates_a"]:
        print(f"  {line}")
    print("\nwrote out/personas.json")


if __name__ == "__main__":
    main()

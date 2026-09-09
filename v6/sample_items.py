"""Stage one — draw the seeds and the vocalization pairs. No model is called.

Kept separate from the reasoning stages so the assignment is a reviewable artefact rather than
something that happens inside a loop. Every pair of vocalizations appears `--per-pair` times and
the order is shuffled, so the draw is random without leaving one combination with a single item
and another with seven.

Each item gets its own seed situation. The rest of the sampled seeds are recorded as `spare`,
because stage two can find that a situation cannot honestly carry its pair and needs another.

    python v6/sample_items.py --dry-run
    python v6/sample_items.py
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import evalkit as K

OUT = K.HERE / "out"
ITEMS = OUT / "items.json"
VOCS_FILE = K.HERE / "vocalization_emotions.json"


def build(vocs: list[dict], seeds: list[dict], per_pair: int, seed: int) -> tuple[list, list]:
    pairs = list(itertools.combinations(vocs, 2))
    plan = [(f"v6_{n + 1:02d}{chr(97 + k)}", pairs[n])
            for n in range(len(pairs)) for k in range(per_pair)]
    K.stable_rng(seed, "pair-order").shuffle(plan)

    queue = list(seeds)
    K.stable_rng(seed, "seed-order").shuffle(queue)
    items = []
    for item_id, (a, b) in plan:
        if not queue:
            break
        row = queue.pop()
        items.append({"item_id": item_id, "seed_id": row["seed_id"],
                      "seed_label": row["label"], "situation": row["situation"],
                      "voc_a": a["vocalization"], "tag_a": a["dia_tag"],
                      "voc_b": b["vocalization"], "tag_b": b["dia_tag"]})
    return items, queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-pair", type=int, default=4)
    parser.add_argument("--reseed", action="append",
                        help="give these item ids a fresh situation from the spare pool, "
                             "keeping their vocalization pair. For an item whose two "
                             "conditions turned out to call for the same reply: the situation "
                             "is what failed, so rewriting the same one would fail again.")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config()
        vocs = json.loads(VOCS_FILE.read_text())
        seeds = json.loads((OUT / "seeds.json").read_text())["items"]
    except (K.ConfigError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    seed = args.seed if args.seed is not None else config["seed"]

    if args.reseed:
        if not ITEMS.exists():
            print(f"error: no {ITEMS} to reseed from", file=sys.stderr)
            return 2
        current = json.loads(ITEMS.read_text())
        items, spare = current["items"], list(current["spare_seeds"])
        wanted = set(args.reseed)
        unknown = wanted - {i["item_id"] for i in items}
        if unknown:
            print(f"error: no such item(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        used = {i["situation"] for i in items}
        swapped = []
        for row in items:
            if row["item_id"] not in wanted:
                continue
            fresh = None
            while spare and fresh is None:
                candidate = spare.pop()
                if candidate["situation"] not in used:
                    fresh = candidate
            if fresh is None:
                print(f"error: no spare seeds left for {row['item_id']}", file=sys.stderr)
                return 2
            swapped.append((row["item_id"], row["seed_id"], fresh["seed_id"]))
            row.update({"seed_id": fresh["seed_id"], "seed_label": fresh["label"],
                        "situation": fresh["situation"]})
            used.add(fresh["situation"])
        K.report("reseed", planned=len(wanted), completed=len(swapped), skipped=0, failed=0,
                 invalid=0)
        for item_id, old, new in swapped:
            print(f"  {item_id} · {old} -> {new}")
        print(f"  {len(spare)} spare seed(s) left")
        if args.dry_run:
            print("dry run: nothing written")
            return 0
        K.write_json(ITEMS, {**current, "reseeded_at": K.now(), "items": items,
                             "spare_seeds": spare}, overwrite=True)
        print(f"wrote {ITEMS.relative_to(K.HERE.parent)}")
        return 0

    items, spare = build(vocs, seeds, args.per_pair, seed)
    counts: dict[str, int] = {}
    for row in items:
        key = f"{row['voc_a']}/{row['voc_b']}"
        counts[key] = counts.get(key, 0) + 1

    K.report("sample", planned=len(items), completed=len(items), skipped=0, failed=0,
             invalid=0)
    print(f"  {len(counts)} pairs · " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"  {len(items)} distinct seeds used, {len(spare)} spare")
    if args.dry_run:
        for row in items[:5]:
            print(f"    {row['item_id']} · {row['voc_a']}/{row['voc_b']} · "
                  f"{row['situation'][:60]}")
        print("dry run: nothing written")
        return 0

    K.write_json(ITEMS, {"sampled_at": K.now(), "seed": seed, "per_pair": args.per_pair,
                         "items": items, "spare_seeds": spare}, overwrite=True)
    print(f"wrote {ITEMS.relative_to(K.HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

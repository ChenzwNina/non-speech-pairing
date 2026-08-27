#!/usr/bin/env python3
"""Re-run the mechanical gates over everything in bench/items.

Free and offline. Run it after hand-editing an item, tightening a gate, or before shipping a
release — hand edits are exactly how lexical drift gets into a contrastive pair.

  python scripts/verify.py
  python scripts/verify.py --items bench/items --verbose
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import taxonomy, validate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_items(items_dir):
    for name in sorted(os.listdir(items_dir)):
        path = os.path.join(items_dir, name, "item.json")
        if os.path.exists(path):
            with open(path) as fh:
                yield name, json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", default=os.path.join(ROOT, "bench", "items"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.items):
        print("no items directory at %s" % args.items)
        return 1

    total = bad = 0
    for name, item in load_items(args.items):
        total += 1
        fails = validate.check(item)

        # Cross-check the taxonomy metadata against the pair recorded on the item.
        pair_meta = item.get("pair") or {}
        for slot, key in (("performance_a", pair_meta.get("a")), ("performance_b", pair_meta.get("b"))):
            if key and key not in taxonomy.FUNCTIONS:
                fails.append(validate.Failure("unknown_function", "%s -> %r" % (slot, key)))
            recorded = ((item.get(slot) or {}).get("function") or {}).get("key")
            if key and recorded and recorded != key:
                fails.append(
                    validate.Failure("function_mismatch", "%s says %r, pair says %r" % (slot, recorded, key))
                )

        if fails:
            bad += 1
            print("FAIL %s" % name)
            for f in fails:
                print("       %s: %s" % (f.code, f.detail))
        else:
            prior = ((item.get("curation") or {}).get("text_prior") or {})
            note = ""
            if prior.get("vote_share") is not None:
                note = "  text prior %.0f%% -> %s, conf %.2f" % (
                    100 * prior["vote_share"],
                    prior.get("favours"),
                    prior.get("mean_confidence") or 0.0,
                )
            print("ok   %s%s" % (name, note))
            if args.verbose:
                print("       %s" % item["transcript"][item["laugh_turn"]]["text"])

    print("\n%d items, %d clean, %d failing" % (total, total - bad, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

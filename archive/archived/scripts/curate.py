#!/usr/bin/env python3
"""Curate contrastive laughter items with the Claude CLI.

  python scripts/curate.py --list-pairs
  python scripts/curate.py --pair benevolence-induction:mocking --n 1
  python scripts/curate.py --auto --n 4 --judge-model opus
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import pipeline, render, taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "bench", "items")
DEFAULT_JSONL = os.path.join(ROOT, "bench", "dataset.jsonl")


def log(*parts):
    """Unbuffered, so `> run.log` stays useful while a long run is in flight."""
    print(*parts)
    sys.stdout.flush()


def list_pairs():
    print("Curated contrastive pairs (index, key):\n")
    for i, pair in enumerate(taxonomy.CONTRAST_PAIRS):
        fn_a, fn_b = pair.functions()
        print("[%d] %s" % (i, pair.key))
        print("    %s  (%s)" % (fn_a.name, taxonomy.BRANCHES[fn_a.branch].name))
        print("    %s  (%s)" % (fn_b.name, taxonomy.BRANCHES[fn_b.branch].name))
        print("    crosses branches: %s" % ("yes" if pair.crosses_branch() else "no"))
        print("    %s\n" % pair.note)


def list_functions():
    for branch in taxonomy.BRANCHES.values():
        print("== %s" % branch.name)
        print("   %s" % branch.gloss)
        for fn in taxonomy.FUNCTIONS.values():
            if fn.branch == branch.key:
                flag = "" if fn.cooperative else "  [non-cooperative]"
                print("   - %-24s %s%s" % (fn.key, fn.name, flag))
        print()


def existing_transcripts(out_dir):
    """Titles + closing lines already in the bench, so the writer doesn't repeat itself."""
    seen = []
    if not os.path.isdir(out_dir):
        return seen
    for name in sorted(os.listdir(out_dir)):
        path = os.path.join(out_dir, name, "item.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                item = json.load(fh)
        except ValueError:
            continue
        seen.append(
            "%s — closes on %r" % (item.get("title", name), item["transcript"][-1]["text"])
        )
    return seen


def next_item_id(out_dir, pair):
    n = 1
    if os.path.isdir(out_dir):
        n = len([d for d in os.listdir(out_dir) if os.path.isdir(os.path.join(out_dir, d))]) + 1
    return "%03d-%s" % (n, pair.key.replace("__vs__", "-vs-"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", help="`fn_a:fn_b`, a pair key, or an index from --list-pairs")
    ap.add_argument("--auto", action="store_true", help="cycle through the curated pairs")
    ap.add_argument("--n", type=int, default=1, help="how many items to accept")
    ap.add_argument("--topic", help="scenario seed handed to the writer")
    ap.add_argument("--writer-model", default="opus", help="Opus 5 by default")
    ap.add_argument(
        "--judge-model",
        default="opus",
        help="Opus 5 by default. Both judge gates are only as strong as this model: a weak judge "
        "failing to read a performance is not evidence the performance is subtle.",
    )
    ap.add_argument("--attempts", type=int, default=3, help="rewrite attempts per item")
    ap.add_argument("--blind-runs", type=int, default=pipeline.DEFAULT_THRESHOLDS.blind_runs)
    ap.add_argument("--listener-runs", type=int, default=pipeline.DEFAULT_THRESHOLDS.listener_runs)
    ap.add_argument(
        "--strict-split",
        action="store_true",
        help="also require the text-only vote to be split. Very few scenarios survive this; the "
        "pair-level metric already makes a text prior worthless.",
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--jsonl", default=DEFAULT_JSONL)
    ap.add_argument("--skip-judges", action="store_true", help="mechanical gates only (cheap dry run)")
    ap.add_argument("--list-pairs", action="store_true")
    ap.add_argument("--list-functions", action="store_true")
    args = ap.parse_args(argv)

    if args.list_pairs:
        list_pairs()
        return 0
    if args.list_functions:
        list_functions()
        return 0
    if not args.pair and not args.auto:
        ap.error("give --pair or --auto (see --list-pairs)")

    thresholds = pipeline.DEFAULT_THRESHOLDS._replace(
        blind_runs=args.blind_runs,
        listener_runs=args.listener_runs,
        strict_split=args.strict_split,
    )

    if args.auto:
        pairs = [taxonomy.CONTRAST_PAIRS[i % len(taxonomy.CONTRAST_PAIRS)] for i in range(args.n)]
    else:
        pairs = [taxonomy.get_pair(args.pair)] * args.n

    accepted, total_cost = 0, 0.0
    started = time.time()
    for i, pair in enumerate(pairs):
        fn_a, fn_b = pair.functions()
        log("\n[item %d/%d] %s vs %s" % (i + 1, len(pairs), fn_a.name, fn_b.name))
        if not pair.crosses_branch():
            log("  note: both functions sit in the same branch (%s)" % fn_a.branch)

        item, report = pipeline.curate_one(
            pair,
            topic=args.topic,
            avoid=existing_transcripts(args.out),
            writer_model=args.writer_model,
            judge_model=args.judge_model,
            thresholds=thresholds,
            seed=args.seed + i,
            max_attempts=args.attempts,
            skip_judges=args.skip_judges,
            log=log,
        )
        total_cost += report.cost_usd

        if not report.accepted:
            log("  REJECTED (last gate: %s) — nothing written" % report.rejected_by)
            continue

        item_id = next_item_id(args.out, pair)
        item["id"] = item_id
        paths = render.write_bundle(item, report, args.out, item_id)
        os.makedirs(os.path.dirname(args.jsonl), exist_ok=True)
        render.append_jsonl(item, args.jsonl)
        accepted += 1
        log("  ACCEPTED -> %s" % os.path.relpath(paths["item"], ROOT))
        log("             %s" % os.path.relpath(paths["tts"], ROOT))

    log(
        "\n%d/%d accepted · $%.2f · %.0fs"
        % (accepted, len(pairs), total_cost, time.time() - started)
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())

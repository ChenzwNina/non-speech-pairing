"""Build the ranking trials: one contrastive pair per item, judged in both directions.

Only `condition_a` against `condition_b`. The baseline is not an opponent — with no
vocalization almost any sensible reply fits it, so a win against it says little — and with it
gone the baseline needs no response elicited at all.

The same two replies are judged twice, once in each condition's context:

    under A's context   does R_A beat R_B?
    under B's context   does R_B beat R_A?

Both right scores 1, one right 0.5, neither 0. A model whose two replies are interchangeable
cannot get 0.5 by luck in the way a single direction would allow — it has to win the direction
it was given, twice.

**Eligibility is perception.** A trial only runs when the model identified the vocalization
correctly in *both* conditions, because asking whether it answered a laugh better than a sigh
is meaningless if it did not hear which was which. Ineligible items are recorded as N/A rather
than zero: the perception failure is already counted in the perception score, and counting it
again here would penalise it twice. What keeps that honest is reporting coverage — how many of
the planned pairs became eligible — beside the conditional accuracy, so a model that only heard
correctly on the easy items cannot hide a thin denominator behind a high score.

    python v6/build_pairs.py --responses out/eval/responses/responses.jsonl --dry-run
    python v6/build_pairs.py --responses out/eval/responses/responses.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import evalkit as K


VOC_CONDITIONS = ("condition_a", "condition_b")


def group(records: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    """(evaluated_model, item_id) -> condition -> the response record."""
    out: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for record in records:
        if record.get("task_type") != "response" or record.get("status") not in (None, "ok"):
            continue
        model = record.get("evaluated_model") or record.get("model_name", "?")
        out[(model, record["item_id"])][record["condition"]] = record
    return out


def perceived(records: list[dict]) -> set[tuple[str, str, str]]:
    """(model, item, condition) for every stimulus whose vocalization was identified."""
    heard = set()
    for record in records:
        if record.get("task_type") != "perception" or record.get("status") not in (None, "ok"):
            continue
        if record.get("correct") is True:
            heard.add((record.get("evaluated_model") or record.get("model_name", "?"),
                       record["item_id"], record["condition"]))
    return heard


def trials(responses: dict[tuple[str, str], dict[str, dict]], heard: set, seed: int, run: str,
           prompt_version: str, swap: bool) -> tuple[list[dict], list[dict]]:
    """The eligible trials, and one N/A record per ineligible pair so coverage is computable."""
    built: list[dict] = []
    ineligible: list[dict] = []
    for (model, item_id), by_condition in sorted(responses.items()):
        missing = [c for c in VOC_CONDITIONS if c not in by_condition]
        deaf = [c for c in VOC_CONDITIONS if (model, item_id, c) not in heard]
        if missing or deaf:
            ineligible.append({"evaluated_model": model, "item_id": item_id,
                               "eligible": False,
                               "reason": ("no response for " + ", ".join(missing)) if missing
                                         else "perception wrong for " + ", ".join(deaf)})
            continue
        for target in VOC_CONDITIONS:
            against = next(c for c in VOC_CONDITIONS if c != target)
            gold, other = by_condition[target], by_condition[against]
            pair = f"{K.RESPONSE_CODE[target]}-vs-{K.RESPONSE_CODE[against]}"
            for swapped in ([False, True] if swap else [False]):
                rng = K.stable_rng(seed, model, item_id, target, "slot")
                gold_slot = rng.choice(("A", "B"))
                if swapped:
                    gold_slot = "B" if gold_slot == "A" else "A"
                other_slot = "B" if gold_slot == "A" else "A"
                record = K.provenance(
                    run=run, item_id=item_id, condition=target, task_type="content_pair",
                    prompt_version=prompt_version, seed=seed,
                    stimulus_audio_path=gold.get("stimulus_audio_path", ""),
                    parsed=None, status="built")
                record["task_id"] = K.task_id(item_id, target, "content_pair", pair,
                                              *(["swap"] if swapped else []))
                record.update({
                    "evaluated_model": model, "eligible": True,
                    "target_condition": target, "against_condition": against,
                    "pair": pair, "direction": K.RESPONSE_CODE[target], "swapped": swapped,
                    "gold_slot": gold_slot,
                    "candidates": {
                        gold_slot: {"condition": target,
                                    "response_text": gold.get("response_text", ""),
                                    "response_audio_path":
                                        gold.get("response_audio_path", "")},
                        other_slot: {"condition": against,
                                     "response_text": other.get("response_text", ""),
                                     "response_audio_path":
                                         other.get("response_audio_path", "")}}})
                built.append(record)
    return built, ineligible


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--perception",
                        help="perception judgements, for eligibility; default is "
                             "out/eval/judgments/perception.jsonl")
    parser.add_argument("--output", help="paired-tasks JSONL; default is out/eval/tasks")
    parser.add_argument("--config")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--swap-duplicate", action="store_true",
                        help="also emit the mirrored trial, overriding the config")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    source = Path(args.responses)
    if not source.is_absolute():
        source = K.HERE / source
    if not source.exists():
        print(f"error: no responses at {source}", file=sys.stderr)
        return 2

    judgments = (Path(args.perception) if args.perception
                 else K.stage_dir("judgments") / "perception.jsonl")
    if not judgments.is_absolute():
        judgments = K.HERE / judgments
    records = K.read_jsonl(source)
    if args.item_id:
        keep = set(args.item_id)
        records = [r for r in records if r.get("item_id") in keep]
    seed = args.seed if args.seed is not None else config["seed"]
    swap = args.swap_duplicate or config.get("paired", {}).get("swap_duplicate", False)
    _, version = K.prompt("content_pairwise_judge")

    per_item = len(VOC_CONDITIONS) * (2 if swap else 1)
    responses = group(records)
    heard = perceived(K.read_jsonl(judgments) if judgments.exists() else [])
    if not heard:
        print(f"warning: no perception results at {judgments.name} — every pair will be "
              f"ineligible. Score perception first.", file=sys.stderr)
    built, ineligible = trials(responses, heard, seed, K.run_id(args.run_id), version, swap)

    per_model = Counter(t["evaluated_model"] for t in built)
    slots = Counter(t["gold_slot"] for t in built)
    planned = len(responses)
    eligible_items = len({(t["evaluated_model"], t["item_id"]) for t in built})
    K.report("build-pairs", planned=planned * per_item, completed=len(built),
             skipped=len(ineligible) * per_item, failed=0,
             invalid=sum(1 for t in built if not all(
                 c["response_text"] for c in t["candidates"].values())))
    print(f"  {eligible_items} of {planned} (model, item) pair(s) eligible — coverage "
          f"{eligible_items / planned:.1%}" if planned else "  nothing to build")
    print(f"  {per_item} direction(s) each · gold in slot "
          + ", ".join(f"{k} {v}" for k, v in sorted(slots.items())))
    for model, count in sorted(per_model.items()):
        print(f"    {model}: {count} trial(s)")
    why = Counter(r["reason"].split(" for ")[0] for r in ineligible)
    for reason, count in sorted(why.items()):
        print(f"    ineligible — {reason}: {count}")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    out = Path(args.output) if args.output else K.stage_dir("tasks") / "content_pairs.jsonl"
    if out.exists() and not args.overwrite:
        print(f"error: {out} exists; pass --overwrite", file=sys.stderr)
        return 2
    out.unlink(missing_ok=True)
    for record in built:
        K.append_jsonl(out, record)
    # The N/A pairs are written too: coverage cannot be computed from the eligible ones alone.
    coverage = out.with_name(out.stem + "_ineligible.jsonl")
    coverage.unlink(missing_ok=True)
    for record in ineligible:
        K.append_jsonl(coverage, record)
    print(f"wrote {out.relative_to(K.HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

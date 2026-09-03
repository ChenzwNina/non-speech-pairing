"""Build the directed paired-content trials from the collected responses.

For a target condition, the question is whether the response produced after hearing *that*
version fits it better than the response the same model produced after hearing a different
version. So each target condition faces the other two, giving two trials, and all three
conditions as targets give six directed trials per item and evaluated model.

`CA` comparing RA against RB and `CB` comparing RA against RB are different trials even though
the two candidates are the same pair of texts: the target context changes, and so does which
candidate is supposed to win. Both are kept.

Candidate order is drawn per trial from the run seed, so it is reproducible, and the slot the
matching response landed in is recorded — a judge with a first-slot habit would otherwise look
like signal. `paired.swap_duplicate` in the config emits the mirrored trial as well, which
measures that habit directly at twice the cost.

Both candidates come from the same evaluated model, so the comparison is insensitive to how
eloquent a model is in general and sensitive only to whether it answered this version
differently.

    python v6/build_pairs.py --responses out/eval/responses/responses.jsonl --dry-run
    python v6/build_pairs.py --responses out/eval/responses/responses.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import evalkit as K


def group(records: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    """(evaluated_model, item_id) -> condition -> the response record."""
    out: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for record in records:
        if record.get("task_type") != "response" or record.get("status") not in (None, "ok"):
            continue
        model = record.get("evaluated_model") or record.get("model_name", "?")
        out[(model, record["item_id"])][record["condition"]] = record
    return out


def trials(responses: dict[tuple[str, str], dict[str, dict]], seed: int, run: str,
           prompt_version: str, swap: bool) -> tuple[list[dict], list[str]]:
    built: list[dict] = []
    incomplete: list[str] = []
    for (model, item_id), by_condition in sorted(responses.items()):
        missing = [c for c in K.CONDITIONS if c not in by_condition]
        if missing:
            incomplete.append(f"{model}/{item_id} missing {missing}")
            continue
        for target in K.CONDITIONS:
            for against in K.CONDITIONS:
                if against == target:
                    continue
                gold, other = by_condition[target], by_condition[against]
                pair = f"{K.RESPONSE_CODE[target]}-vs-{K.RESPONSE_CODE[against]}"
                variants = [False, True] if swap else [False]
                for swapped in variants:
                    rng = K.stable_rng(seed, model, item_id, target, against, "slot")
                    gold_slot = rng.choice(("A", "B"))
                    if swapped:
                        gold_slot = "B" if gold_slot == "A" else "A"
                    other_slot = "B" if gold_slot == "A" else "A"
                    extra = ["swap"] if swapped else []
                    record = K.provenance(
                        run=run, item_id=item_id, condition=target,
                        task_type="content_pair", prompt_version=prompt_version, seed=seed,
                        stimulus_audio_path=gold.get("stimulus_audio_path", ""),
                        parsed=None, status="built")
                    record["task_id"] = K.task_id(item_id, target, "content_pair",
                                                  pair, *extra)
                    record.update({
                        "evaluated_model": model,
                        "target_condition": target, "against_condition": against,
                        "pair": pair, "swapped": swapped,
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
    return built, incomplete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", required=True)
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

    records = K.read_jsonl(source)
    if args.item_id:
        keep = set(args.item_id)
        records = [r for r in records if r.get("item_id") in keep]
    seed = args.seed if args.seed is not None else config["seed"]
    swap = args.swap_duplicate or config.get("paired", {}).get("swap_duplicate", False)
    _, version = K.prompt("content_pairwise_judge")

    responses = group(records)
    built, incomplete = trials(responses, seed, K.run_id(args.run_id), version, swap)

    per_model = Counter(t["evaluated_model"] for t in built)
    slots = Counter(t["gold_slot"] for t in built)
    K.report("build-pairs", planned=len(responses) * (6 * (2 if swap else 1)),
             completed=len(built), skipped=len(incomplete), failed=0,
             invalid=sum(1 for t in built if not all(
                 c["response_text"] for c in t["candidates"].values())))
    print(f"  {len(responses)} (model, item) group(s) · "
          f"{6 * (2 if swap else 1)} trial(s) each · gold in slot "
          + ", ".join(f"{k} {v}" for k, v in sorted(slots.items())))
    for model, count in sorted(per_model.items()):
        print(f"    {model}: {count}")
    for line in incomplete[:5]:
        print(f"    skipped {line}")

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
    print(f"wrote {out.relative_to(K.HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

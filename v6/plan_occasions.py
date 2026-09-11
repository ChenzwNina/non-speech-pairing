"""Stage two — decide when each sound would actually be produced, then build a moment for it.

The failure this stage exists to prevent: a conversation written first, with the vocalization
attached at the end and expected to fit. It never fits the same way twice, because sounds are
not interchangeable in when they can be produced. A gasp is the instant of contact with
something — a person cannot gasp at news they are themselves delivering, or at something they
learned last week and are now recounting. A sigh has no such requirement; it can be produced
about anything already known.

So the model is asked for the production condition of each sound *before* it looks at the
situation, then to satisfy the stricter of the two, then to outline five turns that arrive
there. The schema's field order is that reasoning order, which is why it is fixed.

Nothing here is specific to any one vocalization. The intersection tightens on its own when a
strict sound is drawn and stays loose when two permissive ones are.

    python v6/plan_occasions.py --dry-run
    python v6/plan_occasions.py --only v6_01a
    python v6/plan_occasions.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import evalkit as K
import text_models as T

OUT = K.HERE / "out"
ITEMS = OUT / "items.json"
OCCASIONS = OUT / "occasions.json"
MAX_TOKENS = 20000


class Infeasible(RuntimeError):
    """The situation cannot meet the stricter production condition. Try another seed."""


def payload(item: dict, situation: str) -> str:
    return json.dumps({"situation": situation,
                       "vocalization_a": item["voc_a"],
                       "vocalization_b": item["voc_b"]}, indent=2, ensure_ascii=False)


def plan_one(item: dict, situation: str, args, run: str) -> dict:
    template, version = K.prompt("occasion_planner")
    system = K.fill(template, INPUT=payload(item, situation))
    K.guard(f"openai {args.planner}")
    result = T.retry(T.json_call, args.planner, system, "Return the plan as JSON.",
                     K.strict(K.schema("occasion_plan")), "occasion_plan", args.effort,
                     MAX_TOKENS)
    if not result.get("feasible", True):
        raise Infeasible(f"{item['voc_a']}/{item['voc_b']} does not fit "
                         f"{situation[:60]!r}: {result.get('why_not', '')[:90]}")
    for key, voc in (("production_condition_a", item["voc_a"]),
                     ("production_condition_b", item["voc_b"])):
        result[key]["vocalization"] = voc
    for key, voc in (("framing_a", item["voc_a"]), ("framing_b", item["voc_b"])):
        result[key]["vocalization"] = voc
    record = K.provenance(
        run=run, item_id=item["item_id"], condition="all", task_type="occasion_plan",
        prompt_version=version, model_provider="openai", model_name=args.planner,
        settings={"effort": args.effort or "default"}, parsed=result, status="ok",
        seed_id=item["seed_id"], seed_label=item["seed_label"], situation=situation,
        voc_a=item["voc_a"], voc_b=item["voc_b"],
        tag_a=item["tag_a"], tag_b=item["tag_b"])
    record["errors"] = K.schema_errors("occasion_plan", result)
    if record["errors"]:
        record["status"] = "invalid"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--planner", default="gpt-5.6-terra")
    parser.add_argument("--effort", default=None,
                        help="reasoning effort; omitted by default")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    if not ITEMS.exists():
        print(f"error: no items at {ITEMS}; run sample_items.py first", file=sys.stderr)
        return 2
    source = json.loads(ITEMS.read_text())
    items, spare = source["items"], list(source["spare_seeds"])
    existing = json.loads(OCCASIONS.read_text())["items"] if OCCASIONS.exists() else []
    by_id = {r["item_id"]: r for r in existing}
    order = {row["item_id"]: n for n, row in enumerate(items)}
    if args.only:
        items = [i for i in items if i["item_id"] in set(args.only)]
    elif not args.redo:
        items = [i for i in items if i["item_id"] not in by_id]
    if not items:
        print("nothing to plan")
        return 0

    if args.dry_run:
        template, version = K.prompt("occasion_planner")
        row = items[0]
        print(f"{'=' * 78}\n{row['item_id']} · {version} · {args.planner}\n{'=' * 78}")
        print(K.fill(template, INPUT=payload(row, row["situation"])))
        K.report("plan", planned=len(items), completed=0, skipped=0, failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    run = K.run_id(args.run_id)
    swapped, failed = [], 0
    for row in items:
        situation, record = row["situation"], None
        while record is None:
            try:
                record = plan_one(row, situation, args, run)
            except Infeasible as exc:
                swapped.append(f"{row['item_id']} {exc}")
                if not spare:
                    print(f"  {row['item_id']} · infeasible and no spare seeds left")
                    break
                situation = spare.pop()["situation"]
                print(f"  {row['item_id']} · seed swapped", flush=True)
            except Exception as exc:                          # noqa: BLE001 - recorded
                failed += 1
                print(f"  {row['item_id']} · FAILED {type(exc).__name__}: {exc}"[:150])
                break
        if record is None:
            continue
        by_id[row["item_id"]] = record
        p = record["parsed"]
        print(f"  {row['item_id']} · {row['voc_a']}/{row['voc_b']} · "
              f"lands: {p['what_lands'][:64]}", flush=True)
        K.write_json(OCCASIONS, {"planned_at": K.now(), "run_id": run,
                                 "planner": args.planner,
                                 "effort": args.effort or "default",
                                 "prompt_version": record["prompt_version"],
                                 "items": sorted(by_id.values(),
                                                 key=lambda r: order.get(r["item_id"], 999))},
                     overwrite=True)

    K.report("plan", planned=len(items), completed=len(items) - failed, skipped=len(swapped),
             failed=failed, invalid=sum(1 for r in by_id.values() if r["status"] != "ok"))
    for line in swapped[:5]:
        print(f"    {line}"[:170])
    print(f"wrote {OCCASIONS.relative_to(K.HERE.parent)} · {len(by_id)} plan(s)")
    if T.usage_report():
        print(T.usage_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

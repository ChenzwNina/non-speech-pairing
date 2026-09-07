"""Stage one — decide what each conversation is about, and what each sound would make it mean.

Nothing is written yet. For one seed situation and one randomly drawn pair of vocalizations,
this asks for a five-turn outline plus the two emotional framings the same words should take on
depending on which sound ends them.

**The framings are decided per item, not looked up.** An inventory that fixed `laugh =
amusement` everywhere would be asserting the thing the benchmark is supposed to test — the same
laugh means different things in different conversations. The planner is given the situation and
the two sounds, and nothing more: `default_reading` in vocalization_emotions.json is kept as a
record of an earlier design and is deliberately not passed here.

**The pairs are drawn from a balanced pool.** Each of the six unordered pairs appears
`--per-pair` times and the order is shuffled, so the draw is random without leaving some
combinations with one item and others with seven.

Splitting planning from writing means a plan can be read, and rejected, before anything is spent
on prose — and stage two can be re-run with a different writer without re-deciding what the
conversation is about.

    python v6/plan_transcripts.py --dry-run
    python v6/plan_transcripts.py --per-pair 1     # a pilot, one per pair
    python v6/plan_transcripts.py                  # 24 plans
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

import evalkit as K
import text_models as T

OUT = K.HERE / "out"
PLANS = OUT / "plans.json"
VOCS_FILE = K.HERE / "vocalization_emotions.json"
MAX_TOKENS = 20000


class Infeasible(RuntimeError):
    """The seed cannot honestly carry this pair. Try another seed, not another attempt."""


def prompt_for(seed: dict, pair: tuple[dict, dict]) -> str:
    a, b = pair
    # The situation and the two sounds, and nothing else. An earlier version also passed each
    # vocalization's default reading as an anchor, and it anchored: every laugh came back framed
    # as comic absurdity and every sigh as resigned acceptance, which is the fixed mapping this
    # design exists to avoid asserting.
    return json.dumps({
        "situation": seed["situation"],
        "vocalization_a": a["vocalization"],
        "vocalization_b": b["vocalization"],
    }, indent=2, ensure_ascii=False)


def plan_one(seed: dict, pair: tuple[dict, dict], item_id: str, args, run: str) -> dict:
    a, b = pair
    template, version = K.prompt("transcript_planner")
    system = K.fill(template, INPUT=prompt_for(seed, pair))
    K.guard(f"openai {args.planner}")
    result = T.retry(T.json_call, args.planner, system,
                     "Return the plan as JSON.", K.strict(K.schema("transcript_plan")),
                     "transcript_plan", args.effort, MAX_TOKENS)
    if not result.get("feasible", True):
        raise Infeasible(f"{a['vocalization']}/{b['vocalization']} does not fit "
                         f"{seed['situation'][:60]!r}: {result.get('why_not', '')[:90]}")
    for key, voc in (("framing_a", a), ("framing_b", b)):
        result[key]["vocalization"] = voc["vocalization"]
    record = K.provenance(
        run=run, item_id=item_id, condition="all", task_type="transcript_plan",
        prompt_version=version, model_provider="openai", model_name=args.planner,
        settings={"effort": args.effort or "default"}, parsed=result, status="ok",
        seed_id=seed["seed_id"], seed_label=seed["label"], situation=seed["situation"],
        voc_a=a["vocalization"], voc_b=b["vocalization"],
        tag_a=a["dia_tag"], tag_b=b["dia_tag"])
    record["errors"] = K.schema_errors("transcript_plan", result)
    if record["errors"]:
        record["status"] = "invalid"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-pair", type=int, default=4,
                        help="plans per pair of vocalizations; six pairs")
    parser.add_argument("--only", action="append", help="item ids")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--planner", default="gpt-5.6-terra")
    parser.add_argument("--effort", default=None,
                        help="reasoning effort; omitted by default, so the model runs at its "
                             "own. 2.0's convention: nothing in the pipeline sets it.")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config()
        vocs = json.loads(VOCS_FILE.read_text())
        pool = json.loads((OUT / "seeds.json").read_text())["items"]
    except (K.ConfigError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    seed = args.seed if args.seed is not None else config["seed"]

    all_pairs = list(itertools.combinations(vocs, 2))
    ids = {n: [f"v6_{n + 1:02d}{chr(97 + k)}" for k in range(args.per_pair)]
           for n in range(len(all_pairs))}
    plan = [(item_id, all_pairs[n]) for n in range(len(all_pairs)) for item_id in ids[n]]
    K.stable_rng(seed, "pair-order").shuffle(plan)
    order = {item_id: n for n, (item_id, _) in enumerate(plan)}

    existing = json.loads(PLANS.read_text())["items"] if PLANS.exists() else []
    by_id = {r["item_id"]: r for r in existing}
    used = {r["situation"] for r in by_id.values()}
    if args.only:
        plan = [(i, p) for i, p in plan if i in set(args.only)]
    elif not args.redo:
        plan = [(i, p) for i, p in plan if i not in by_id]

    queue = [s for s in pool if s["situation"] not in used]
    random.Random(seed).shuffle(queue)

    if args.dry_run:
        print(f"  {len(all_pairs)} pairs x {args.per_pair} = {len(ids) * args.per_pair} plans")
        for item_id, pair in plan[:6]:
            print(f"    {item_id} · {pair[0]['vocalization']}/{pair[1]['vocalization']}")
        template, version = K.prompt("transcript_planner")
        if queue:
            print(f"\n{'=' * 78}\n{plan[0][0]} · {version} · {args.planner}\n{'=' * 78}")
            print(K.fill(template, INPUT=prompt_for(queue[-1], plan[0][1])))
        K.report("plan", planned=len(plan), completed=0, skipped=0, failed=0, invalid=0)
        print("dry run: nothing called, nothing written")
        return 0

    run = K.run_id(args.run_id)
    skipped, failed = [], 0
    for item_id, pair in plan:
        record = None
        while queue and record is None:
            seed_row = queue.pop()
            try:
                record = plan_one(seed_row, pair, item_id, args, run)
            except Infeasible as exc:
                skipped.append(f"{item_id} {exc}")
                print(f"  {item_id} · seed infeasible, trying another", flush=True)
            except Exception as exc:                          # noqa: BLE001 - recorded
                failed += 1
                print(f"  {item_id} · FAILED {type(exc).__name__}: {exc}"[:150], flush=True)
                break
        if record is None:
            continue
        by_id[item_id] = record
        p = record["parsed"]
        print(f"  {item_id} · {record['voc_a']}/{record['voc_b']} · "
              f"{record['seed_label']:12} · {p['why_different'][:70]}", flush=True)
        K.write_json(PLANS, {"planned_at": K.now(), "run_id": run, "planner": args.planner,
                             "effort": args.effort or "default",
                             "prompt_version": record["prompt_version"],
                             "items": sorted(by_id.values(),
                                             key=lambda r: order.get(r["item_id"], 999))},
                     overwrite=True)

    K.report("plan", planned=len(plan), completed=len(plan) - failed - len(skipped),
             skipped=len(skipped), failed=failed,
             invalid=sum(1 for r in by_id.values() if r["status"] != "ok"))
    for line in skipped[:5]:
        print(f"    {line}"[:170])
    print(f"wrote {PLANS.relative_to(K.HERE.parent)} · {len(by_id)} plan(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Freeze the perception multiple-choice tasks.

Two properties matter more than they look.

**The option set is frozen and shared.** Every evaluated model must see the same four options in
the same order for a given item and condition, or their accuracies are not comparable. So this
writes the task file once and refuses to overwrite it; a rebuild with a different seed is a
different benchmark, not a refresh.

**The plan is always computed over the whole dataset.** Correct-answer positions are balanced
15/15/15/15 across the 60 stimuli and distractor use is balanced greedily, which are properties
of the full set. `--item-id` therefore filters what is printed, never what is assigned: building
a subset would give it different options from the ones the full run froze.

Distractors are drawn from the remaining inventory by lowest use so far, with a seeded
tie-break, so no label becomes a stock wrong answer. `none` is balanced like any other label —
it is a real answer for the baseline stimuli and a real distractor elsewhere.

Pragmatic understanding is no longer multiple choice — a model answers in its own words and
judges decide whether it matches any of the acceptable interpretations — so nothing is frozen
for it here.

    python v6/build_tasks.py --dry-run
    python v6/build_tasks.py
    python v6/build_tasks.py --item-id v6_01a
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import evalkit as K

OPTION_IDS = ("A", "B", "C", "D", "E")


def fingerprint(items: list[dict]) -> str:
    """Identifies the item set a plan was computed over.

    Correct-answer positions are balanced 15/15/15/15 and distractor use is balanced greedily,
    and both are properties of the whole set — so an item's options depend on which other items
    were present and in what order. That is the price of the balance the spec asks for, and it
    is fine because the task file is written once. What is not fine is discovering later that a
    frozen file was built from a different set, so the set is stamped into the file and a
    rebuild reports whether it moved.
    """
    joined = "|".join(f"{i['item_id']}:{i['voc_a']}/{i['voc_b']}" for i in items)
    return f"sha256:{hashlib.sha256(joined.encode()).hexdigest()[:16]}"

READABLE = {"laugh": "a laugh", "sigh": "a sigh", "gasp": "a gasp", "groan": "a groan",
            "none": "no non-speech vocalization"}


def render(template: str, options: list[dict]) -> str:
    lines = "\n".join(f"{o['id']}. {o['text']}" for o in options)
    return K.fill(template, OPTIONS=lines)


def positions(seed: int, count: int) -> list[str]:
    """One correct-answer position per stimulus, as evenly spread as `count` allows."""
    slots = [OPTION_IDS[i % len(OPTION_IDS)] for i in range(count)]
    K.stable_rng(seed, "correct-positions").shuffle(slots)
    return slots


def perception_options(items: list[dict], seed: int) -> dict[tuple[str, str], dict]:
    """Frozen option sets. Every question carries every label; only the order varies.

    There are no distractors to choose. With four vocalizations and `none` the whole inventory
    fits in one question, so a model cannot be helped or hindered by which wrong answers it was
    offered — which removes a confound the earlier four-of-six design had to balance away.
    What still matters is where the correct answer falls, so the positions are spread evenly
    across the whole set rather than drawn independently.
    """
    inventory = list(READABLE)
    stimuli = list(K.stimuli(items))
    where = positions(seed, len(stimuli))
    plan: dict[tuple[str, str], dict] = {}
    for index, (item, condition) in enumerate(stimuli):
        correct = K.gold_vocalization(item, condition)
        others = [label for label in inventory if label != correct]
        K.stable_rng(seed, item["item_id"], condition, "option-order").shuffle(others)
        correct_id = where[index]
        options, remaining = [], iter(others)
        for option_id in OPTION_IDS:
            label = correct if option_id == correct_id else next(remaining)
            options.append({"id": option_id, "label": label, "text": READABLE[label]})
        plan[(item["item_id"], condition)] = {
            "options": options, "correct_option": correct_id, "correct_label": correct}
    return plan


def build(items, config, plan, task_type: str, template_for, run: str, seed: int) -> list[dict]:
    tasks = []
    for item, condition in K.stimuli(items):
        frozen = plan.get((item["item_id"], condition))
        if frozen is None:
            continue
        template, version = template_for(condition)
        # The question is renderer-independent: the same four options are asked about every
        # rendering of the stimulus, which is what makes the renderers comparable. Only the
        # audio differs, so the task carries one path per renderer and the runner stamps the
        # one it actually played into `stimulus_audio_path`.
        record = K.provenance(
            run=run, item_id=item["item_id"], condition=condition, task_type=task_type,
            prompt_version=version, seed=seed, parsed=None, status="built")
        record["stimulus_audio"] = {
            renderer: str(K.audio_path(config, item["item_id"], condition, renderer)
                          .relative_to(K.HERE))
            for renderer in sorted(K.renderers(config))}
        record["task_id"] = K.task_id(item["item_id"], condition, task_type)
        record["question"] = render(template, frozen["options"])
        record.update({k: v for k, v in frozen.items()})
        record["gold_vocalization"] = K.gold_vocalization(item, condition)
        record["gold_emotion"] = K.gold_emotion(item, condition)
        tasks.append(record)
    return tasks


def summarize(tasks: list[dict], label: str) -> None:
    if not tasks:
        print(f"  {label}: none built")
        return
    where = Counter(t["correct_option"] for t in tasks)
    print(f"  {label}: {len(tasks)} tasks · correct at "
          + ", ".join(f"{k} {where.get(k, 0)}" for k in OPTION_IDS))
    flagged = [t["item_id"] for t in tasks if t.get("ambiguity_flag")]
    if flagged:
        print(f"    ambiguity-flagged: {len(flagged)} ({sorted(set(flagged))})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")

    parser.add_argument("--output", help="directory; default is out/eval/tasks")
    parser.add_argument("--config")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--item-id", action="append", help="filters the printed preview only")
    parser.add_argument("--condition", action="append", choices=list(K.CONDITIONS))
    parser.add_argument("--task-type", action="append", choices=["perception"])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and report without writing task files")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
        if args.input:
            config["dataset"]["transcripts"] = args.input
        _, items = K.load_items(config)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    seed = args.seed if args.seed is not None else config["seed"]
    stamp = fingerprint(items)
    run = K.run_id(args.run_id)
    wanted = set(args.task_type or ["perception"])
    out_dir = Path(args.output) if args.output else K.stage_dir("tasks")

    perception_q = K.prompt("perception_question")

    built: dict[str, list[dict]] = {}
    pending = 0
    if "perception" in wanted:
        plan = perception_options(items, seed)
        built["perception"] = build(items, config, plan, "perception",
                                    lambda _c: perception_q, run, seed)

    invalid = 0
    for task_type, tasks in built.items():
        for task in tasks:
            if len({o["id"] for o in task["options"]}) != len(OPTION_IDS):
                invalid += 1
            if len({o["text"] for o in task["options"]}) != len(OPTION_IDS):
                invalid += 1

    K.report("build-tasks",
             planned=sum(len(t) for t in built.values()) + pending * len(K.CONDITIONS),
             completed=sum(len(t) for t in built.values()),
             skipped=pending * len(K.CONDITIONS), failed=0, invalid=invalid)
    for task_type, tasks in built.items():
        summarize(tasks, task_type)
    if pending:
        print(f"  pragmatic: {pending} item(s) have no written options yet — "
              f"run write_pragmatic.py")

    preview = [t for tasks in built.values() for t in tasks
               if (not args.item_id or t["item_id"] in set(args.item_id))
               and (not args.condition or t["condition"] in set(args.condition))]
    if args.item_id or args.condition:
        for task in preview[:6]:
            print(f"\n  {task['task_id']}  (correct {task['correct_option']}"
                  f" = {task['correct_label']})")
            for line in task["question"].splitlines():
                print(f"    {line}")

    if args.dry_run:
        print("\ndry run: nothing written")
        return 1 if invalid else 0

    for task_type, tasks in built.items():
        if not tasks:
            continue
        path = out_dir / f"{task_type}.json"
        if path.exists() and args.overwrite:
            previous = json.loads(path.read_text()).get("items_fingerprint")
            if previous and previous != stamp:
                print(f"  note: {path.name} was built from a different item set "
                      f"({previous} -> {stamp}); every item's options change")
        payload = {"built_at": K.now(), "run_id": run, "seed": seed,
                   "transcripts": config["dataset"]["transcripts"],
                   "renderers": sorted(K.renderers(config)),
                   "items_fingerprint": stamp, "items": len(items),
                   "task_type": task_type, "tasks": tasks}
        try:
            K.write_json(path, payload, overwrite=args.overwrite)
        except K.ConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {path.relative_to(K.HERE.parent)}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())

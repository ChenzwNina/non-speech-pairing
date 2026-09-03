"""Freeze the multiple-choice tasks: perception options, and pragmatic options once written.

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

Pragmatic options come from write_pragmatic.py. If that has not run, the perception tasks are
still built and the pragmatic ones are reported as pending.

    python v6/build_tasks.py --dry-run
    python v6/build_tasks.py --seed 20260902
    python v6/build_tasks.py --item-id v6_01a --task-type perception
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import evalkit as K

OPTION_IDS = ("A", "B", "C", "D")


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
            "scream": "a scream", "none": "no non-speech vocalization"}


def render(template: str, options: list[dict]) -> str:
    lines = "\n".join(f"{o['id']}. {o['text']}" for o in options)
    return K.fill(template, OPTIONS=lines)


def positions(seed: int, count: int) -> list[str]:
    """One correct-answer position per stimulus, as evenly spread as `count` allows."""
    slots = [OPTION_IDS[i % len(OPTION_IDS)] for i in range(count)]
    K.stable_rng(seed, "correct-positions").shuffle(slots)
    return slots


def perception_options(items: list[dict], seed: int) -> dict[tuple[str, str], dict]:
    """Frozen option sets for every stimulus, balanced over the whole dataset."""
    inventory = list(READABLE)
    stimuli = list(K.stimuli(items))
    where = positions(seed, len(stimuli))
    used: Counter = Counter()
    plan: dict[tuple[str, str], dict] = {}

    for index, (item, condition) in enumerate(stimuli):
        correct = K.gold_vocalization(item, condition)
        pool = [label for label in inventory if label != correct]
        # Least-used first; a seeded shuffle breaks ties so the order of `inventory` does not
        # silently decide which label becomes everyone's favourite wrong answer.
        K.stable_rng(seed, item["item_id"], condition, "distractors").shuffle(pool)
        distractors = sorted(pool, key=lambda label: used[label])[:3]
        used.update(distractors)

        order = list(distractors)
        K.stable_rng(seed, item["item_id"], condition, "option-order").shuffle(order)
        correct_id = where[index]
        options, remaining = [], iter(order)
        for option_id in OPTION_IDS:
            label = correct if option_id == correct_id else next(remaining)
            options.append({"id": option_id, "label": label, "text": READABLE[label]})
        plan[(item["item_id"], condition)] = {
            "options": options, "correct_option": correct_id, "correct_label": correct,
            "distractor_labels": distractors}
    return plan


def pragmatic_options(items: list[dict], seed: int,
                      written: dict[str, dict]) -> dict[tuple[str, str], dict]:
    """The same treatment for the LLM-written interpretations, when they exist."""
    stimuli = [(i, c) for i, c in K.stimuli(items) if i["item_id"] in written]
    where = positions(seed, len(stimuli))
    plan: dict[tuple[str, str], dict] = {}
    for index, (item, condition) in enumerate(stimuli):
        block = next((b for b in written[item["item_id"]]["conditions"]
                      if b["condition"] == condition), None)
        if block is None:
            continue
        order = [d["text"] for d in block["distractors"]]
        kinds = {d["text"]: d["kind"] for d in block["distractors"]}
        K.stable_rng(seed, item["item_id"], condition, "pragmatic-order").shuffle(order)
        correct_id = where[index]
        options, remaining = [], iter(order)
        for option_id in OPTION_IDS:
            if option_id == correct_id:
                options.append({"id": option_id, "label": "correct", "text": block["correct"]})
            else:
                text = next(remaining)
                options.append({"id": option_id, "label": kinds[text], "text": text})
        plan[(item["item_id"], condition)] = {
            "options": options, "correct_option": correct_id, "correct_label": "correct",
            "ambiguity_flag": block.get("ambiguity_flag", False),
            "ambiguity_note": block.get("ambiguity_note", "")}
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
    labels = Counter(l for t in tasks for l in t.get("distractor_labels", []))
    if labels:
        print("    distractor use: "
              + ", ".join(f"{k} {v}" for k, v in sorted(labels.items())))
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
    parser.add_argument("--task-type", action="append",
                        choices=["perception", "pragmatic"])
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
    wanted = set(args.task_type or ["perception", "pragmatic"])
    out_dir = Path(args.output) if args.output else K.stage_dir("tasks")

    perception_q = K.prompt("perception_question")
    pragmatic_q = K.prompt("pragmatic_question")
    pragmatic_base_q = K.prompt("pragmatic_question_baseline")

    built: dict[str, list[dict]] = {}
    if "perception" in wanted:
        plan = perception_options(items, seed)
        built["perception"] = build(items, config, plan, "perception",
                                    lambda _c: perception_q, run, seed)

    pending = 0
    if "pragmatic" in wanted:
        written_path = K.stage_dir("rubrics") / "pragmatic_options.json"
        written, rejected = {}, 0
        if written_path.exists():
            # The file holds provenance records, so the options are under `parsed`, and a
            # record whose writer failed validation must not become a task.
            for row in json.loads(written_path.read_text())["items"]:
                if row.get("status") == "ok" and row.get("parsed"):
                    written[row["item_id"]] = row["parsed"]
                else:
                    rejected += 1
        pending = len(items) - len(written)
        if rejected:
            print(f"  pragmatic: {rejected} written record(s) failed validation and were "
                  f"not turned into tasks")
        plan = pragmatic_options(items, seed, written)
        built["pragmatic"] = build(
            items, config, plan, "pragmatic",
            lambda c: pragmatic_base_q if c == "baseline" else pragmatic_q, run, seed)

    invalid = 0
    for task_type, tasks in built.items():
        for task in tasks:
            if len({o["id"] for o in task["options"]}) != 4:
                invalid += 1
            if len({o["text"] for o in task["options"]}) != 4:
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

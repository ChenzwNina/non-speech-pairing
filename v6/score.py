"""Score the collected judgements. Five metrics, kept apart, each with clustered intervals.

The five numbers diagnose different failures and are never collapsed into a headline: a model
can hear every vocalization and still answer as though it had heard none, which is exactly what
1.0 found, and an average would hide it.

Two statistical points the spec is firm about, both implemented here rather than noted.

**Resampling is by item, not by row.** The three conditions of one transcript are the same words
spoken three ways; treating them as independent observations would shrink every interval by
roughly the square root of three. `cluster_bootstrap` resamples `item_id`s with replacement and
carries all of an item's rows with it.

**Invalid and unjudgeable records leave the denominator and are reported.** A malformed judge
reply is not a wrong answer, and scoring it as one would reward a judge for failing to answer.
Every metric prints how many rows it dropped and why.

    python v6/score.py --dry-run
    python v6/score.py --judgments out/eval/judgments --output out/eval/scores
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import evalkit as K

CONTRACT = {"perception": "judge_outputs:mc_answer",
            "pragmatic": "judge_outputs:mc_answer",
            "content_absolute": "judge_outputs:content_absolute",
            "content_pair": "judge_outputs:content_pairwise",
            "tone_absolute": "judge_outputs:tone_absolute"}


# ---------------------------------------------------------------- loading and validation

def load_judgments(directory: Path) -> tuple[list[dict], list[dict]]:
    """Every judgement on disk, split into those that honour their contract and those that do not."""
    good, bad = [], []
    for path in sorted(directory.glob("*.jsonl")):
        for record in K.read_jsonl(path):
            record.setdefault("source_file", path.name)
            task_type = record.get("task_type")
            if task_type not in CONTRACT:
                record["errors"] = [f"unknown task_type {task_type!r}"]
                bad.append(record)
                continue
            if record.get("status") not in (None, "ok"):
                record.setdefault("errors", [f"status {record.get('status')!r}"])
                bad.append(record)
                continue
            errors = K.schema_errors(CONTRACT[task_type], record.get("parsed"))
            if errors:
                record["errors"] = errors
                bad.append(record)
                continue
            good.append(record)
    return good, bad


# ---------------------------------------------------------------- statistics

def cluster_bootstrap(rows: list[dict], statistic, resamples: int, confidence: float,
                      seed: int) -> dict:
    """Point estimate and a percentile interval, resampling whole items."""
    import numpy

    point = statistic(rows)
    if point is None or not rows:
        return {"value": point, "low": None, "high": None, "n": len(rows), "items": 0}
    by_item: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_item[row["item_id"]].append(row)
    items = sorted(by_item)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        sample: list[dict] = []
        for _ in items:
            sample.extend(by_item[items[rng.randrange(len(items))]])
        value = statistic(sample)
        if value is not None:
            draws.append(value)
    if not draws:
        return {"value": point, "low": None, "high": None, "n": len(rows),
                "items": len(items)}
    tail = (1 - confidence) / 2 * 100
    return {"value": point,
            "low": float(numpy.percentile(draws, tail)),
            "high": float(numpy.percentile(draws, 100 - tail)),
            "n": len(rows), "items": len(items)}


def mean(values) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def accuracy(rows: list[dict]) -> float | None:
    return mean(1.0 if row["_correct"] else 0.0 for row in rows)


def macro_f1(rows: list[dict], labels: list[str]) -> float | None:
    """Unweighted mean F1 over the labels that actually occur as gold."""
    if not rows:
        return None
    scores = []
    for label in labels:
        tp = sum(1 for r in rows if r["_gold"] == label and r["_predicted"] == label)
        fp = sum(1 for r in rows if r["_gold"] != label and r["_predicted"] == label)
        fn = sum(1 for r in rows if r["_gold"] == label and r["_predicted"] != label)
        if tp + fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn)
        scores.append(2 * precision * recall / (precision + recall)
                      if precision + recall else 0.0)
    return mean(scores)


def confusion(rows: list[dict]) -> dict:
    table: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        table[row["_gold"]][row["_predicted"]] += 1
    return {gold: dict(counts) for gold, counts in sorted(table.items())}


def ordinal_agreement(rows: list[dict]) -> dict:
    """How closely the judges track each other, apart from how high they score."""
    from scipy import stats

    by_task: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        by_task[row["task_id"]][row["judge"]] = row["_score"]
    judges = sorted({judge for scores in by_task.values() for judge in scores})
    exact, close, pairs, correlations = [], [], 0, []
    for first in range(len(judges)):
        for second in range(first + 1, len(judges)):
            a, b = judges[first], judges[second]
            shared = [(s[a], s[b]) for s in by_task.values() if a in s and b in s]
            if len(shared) < 3:
                continue
            pairs += 1
            exact += [1.0 if x == y else 0.0 for x, y in shared]
            close += [1.0 if abs(x - y) <= 1 else 0.0 for x, y in shared]
            if len({x for x, _ in shared}) > 1 and len({y for _, y in shared}) > 1:
                correlations.append(float(stats.spearmanr([x for x, _ in shared],
                                                          [y for _, y in shared]).statistic))
    return {"judges": judges, "judge_pairs_compared": pairs,
            "exact_agreement": mean(exact), "within_one": mean(close),
            "mean_pairwise_spearman": mean(correlations)}


def binary_agreement(rows: list[dict]) -> dict:
    """Pairwise agreement and Fleiss' kappa over trials every judge answered."""
    by_task: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        by_task[row["task_id"]][row["judge"]] = int(row["_correct"])
    judges = sorted({judge for votes in by_task.values() for judge in votes})
    agree = []
    for first in range(len(judges)):
        for second in range(first + 1, len(judges)):
            a, b = judges[first], judges[second]
            shared = [(v[a], v[b]) for v in by_task.values() if a in v and b in v]
            agree += [1.0 if x == y else 0.0 for x, y in shared]
    complete = [votes for votes in by_task.values() if len(votes) == len(judges)]
    kappa = None
    if complete and len(judges) > 1:
        raters = len(judges)
        chosen = [sum(votes.values()) for votes in complete]
        observed = mean(((c * (c - 1) + (raters - c) * (raters - c - 1))
                         / (raters * (raters - 1))) for c in chosen)
        share = mean(c / raters for c in chosen)
        expected = share ** 2 + (1 - share) ** 2
        kappa = (observed - expected) / (1 - expected) if expected < 1 else None
    return {"judges": judges, "pairwise_agreement": mean(agree),
            "fleiss_kappa": kappa, "trials_all_judges_answered": len(complete)}


# ---------------------------------------------------------------- per-task-type scoring

def by_group(rows: list[dict], key, statistic, resamples, confidence, seed) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return {name: cluster_bootstrap(subset, statistic, resamples, confidence, seed)
            for name, subset in sorted(groups.items())}


def score_multiple_choice(rows: list[dict], tasks: dict, labels: list[str], cfg) -> dict:
    prepared = []
    for row in rows:
        task = tasks.get(row["task_id"])
        if task is None:
            continue
        chosen = row["parsed"]["selected_option"]
        picked = next((o for o in task["options"] if o["id"] == chosen), None)
        prepared.append(dict(
            row, _correct=chosen == task["correct_option"],
            _gold=task["correct_label"],
            _predicted=picked["label"] if picked else "<no-such-option>",
            _confidence=row["parsed"].get("confidence"),
            _voc=task.get("gold_vocalization"), _flagged=task.get("ambiguity_flag", False)))
    scored = [r for r in prepared if not r["_flagged"]]
    flagged = [r for r in prepared if r["_flagged"]]
    resamples, confidence, seed = cfg
    baseline = [r for r in scored if r["condition"] == "baseline"]
    return {
        "n": len(scored), "flagged_excluded": len(flagged),
        "overall_accuracy": cluster_bootstrap(scored, accuracy, resamples, confidence, seed),
        "by_model": by_group(scored, lambda r: r.get("evaluated_model", "?"),
                             accuracy, resamples, confidence, seed),
        "by_renderer": by_group(scored, lambda r: r.get("renderer", "?"),
                                accuracy, resamples, confidence, seed),
        "by_vocalization": by_group(scored, lambda r: r["_voc"], accuracy,
                                    resamples, confidence, seed),
        "by_condition": by_group(scored, lambda r: r["condition"], accuracy,
                                 resamples, confidence, seed),
        "macro_f1": cluster_bootstrap(scored, lambda rs: macro_f1(rs, labels),
                                      resamples, confidence, seed),
        "confusion": confusion(scored),
        "baseline_false_positive_rate": cluster_bootstrap(
            baseline, lambda rs: mean(0.0 if r["_correct"] else 1.0 for r in rs),
            resamples, confidence, seed),
        "flagged_items": sorted({r["item_id"] for r in flagged}),
    }


def score_absolute(rows: list[dict], cfg, what: str) -> dict:
    resamples, confidence, seed = cfg
    valid, unjudgeable = [], []
    for row in rows:
        if row["parsed"].get("unjudgeable"):
            unjudgeable.append(row)
            continue
        valid.append(dict(row, _score=float(row["parsed"]["score"])))
    statistic = lambda rs: mean(r["_score"] for r in rs)
    return {
        "n": len(valid), "unjudgeable": len(unjudgeable),
        "unjudgeable_rate": (len(unjudgeable) / (len(valid) + len(unjudgeable))
                             if valid or unjudgeable else None),
        "unjudgeable_reasons": Counter(
            r["parsed"].get("unjudgeable_reason", "") for r in unjudgeable),
        f"{what}_absolute": cluster_bootstrap(valid, statistic, resamples, confidence, seed),
        "normalized": (mean((r["_score"] - 1) / 4 for r in valid) if valid else None),
        "by_model": by_group(valid, lambda r: r.get("evaluated_model", "?"),
                             statistic, resamples, confidence, seed),
        "by_renderer": by_group(valid, lambda r: r.get("renderer", "?"), statistic,
                                resamples, confidence, seed),
        "by_condition": by_group(valid, lambda r: r["condition"], statistic,
                                 resamples, confidence, seed),
        "by_vocalization": by_group(valid, lambda r: r.get("gold_vocalization", "?"),
                                    statistic, resamples, confidence, seed),
        "by_judge": by_group(valid, lambda r: r.get("judge", "?"), statistic,
                             resamples, confidence, seed),
        "distribution": dict(sorted(Counter(int(r["_score"]) for r in valid).items())),
        "agreement": ordinal_agreement(valid) if valid else {},
    }


def score_pairs(rows: list[dict], trials: dict, cfg, tie_policy: str) -> dict:
    resamples, confidence, seed = cfg
    prepared = []
    for row in rows:
        trial = trials.get(row["task_id"])
        if trial is None:
            continue
        prepared.append(dict(row, _correct=row["parsed"]["preferred_response"]
                             == trial["gold_slot"],
                             _confidence=row["parsed"].get("confidence"),
                             _target=trial["target_condition"],
                             _against=trial["against_condition"],
                             _gold_slot=trial["gold_slot"],
                             _swapped=trial.get("swapped", False)))
    # Aggregated per trial, to report the split rate the tie policy is about.
    votes: dict[str, list[dict]] = defaultdict(list)
    for row in prepared:
        votes[row["task_id"]].append(row)
    splits = sum(1 for rs in votes.values()
                 if len(rs) > 1 and sum(r["_correct"] for r in rs) * 2 == len(rs))
    aggregated = []
    for task, rs in votes.items():
        share = mean(1.0 if r["_correct"] else 0.0 for r in rs)
        if share == 0.5 and tie_policy == "unresolved":
            continue
        aggregated.append(dict(rs[0], _correct=share > 0.5,
                               _half=share == 0.5))
    statistic = accuracy
    return {
        "n": len(prepared), "trials": len(votes),
        "tie_policy": tie_policy,
        "split_decisions": splits,
        "split_rate": (splits / len(votes)) if votes else None,
        "content_pair_accuracy": cluster_bootstrap(prepared, statistic, resamples,
                                                   confidence, seed),
        "aggregated_accuracy": cluster_bootstrap(
            aggregated,
            (lambda rs: mean((0.5 if r.get("_half") else (1.0 if r["_correct"] else 0.0))
                             for r in rs)) if tie_policy == "half" else statistic,
            resamples, confidence, seed),
        "by_model": by_group(prepared, lambda r: r.get("evaluated_model", "?"), statistic,
                             resamples, confidence, seed),
        "by_renderer": by_group(prepared, lambda r: r.get("renderer", "?"), statistic,
                                resamples, confidence, seed),
        "by_target": by_group(prepared, lambda r: r["_target"], statistic,
                              resamples, confidence, seed),
        "by_judge": by_group(prepared, lambda r: r.get("judge", "?"), statistic,
                             resamples, confidence, seed),
        "gold_slot_balance": dict(sorted(Counter(r["_gold_slot"] for r in prepared).items())),
        "accuracy_by_gold_slot": by_group(prepared, lambda r: r["_gold_slot"], statistic,
                                          resamples, confidence, seed),
        "agreement": binary_agreement(prepared) if prepared else {},
        "chance": 0.5,
    }


# ---------------------------------------------------------------- reporting

def show(label: str, block: dict, key: str, scale: str = "") -> None:
    stat = block.get(key)
    if not stat or stat.get("value") is None:
        print(f"  {label:34} —")
        return
    interval = ("" if stat["low"] is None
                else f"  [{stat['low']:.3f}, {stat['high']:.3f}]")
    print(f"  {label:34} {stat['value']:.3f}{interval}"
          f"   n={stat['n']} items={stat['items']}{scale}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", help="directory; default is out/eval/tasks")
    parser.add_argument("--judgments", help="directory; default is out/eval/judgments")
    parser.add_argument("--output", help="directory; default is out/eval/scores")
    parser.add_argument("--config")
    parser.add_argument("--item-id", action="append")
    parser.add_argument("--task-type", action="append", choices=list(CONTRACT))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be scored without writing")
    args = parser.parse_args()
    K.set_dry_run(args.dry_run)

    try:
        config = K.load_config(Path(args.config) if args.config else None)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tasks_dir = Path(args.tasks) if args.tasks else K.stage_dir("tasks")
    judgments_dir = Path(args.judgments) if args.judgments else K.stage_dir("judgments")
    for directory in (tasks_dir, judgments_dir):
        if not directory.is_absolute():
            directory = K.HERE / directory
    seed = args.seed if args.seed is not None else config["seed"]
    scoring = config.get("scoring", {})
    cfg = (int(scoring.get("bootstrap_resamples", 2000)),
           float(scoring.get("confidence", 0.95)), seed)

    lookup: dict[str, dict] = {}
    for name in ("perception", "pragmatic"):
        path = tasks_dir / f"{name}.json"
        if path.exists():
            for task in json.loads(path.read_text())["tasks"]:
                lookup[task["task_id"]] = task
    trials = {t["task_id"]: t for t in K.read_jsonl(tasks_dir / "content_pairs.jsonl")}

    good, bad = load_judgments(judgments_dir)
    if args.item_id:
        keep = set(args.item_id)
        good = [r for r in good if r.get("item_id") in keep]
        bad = [r for r in bad if r.get("item_id") in keep]
    wanted = set(args.task_type or CONTRACT)
    buckets: dict[str, list[dict]] = defaultdict(list)
    for record in good:
        if record["task_type"] in wanted:
            buckets[record["task_type"]].append(record)

    labels = list(config["inventory"])
    scores: dict[str, dict] = {}
    if buckets["perception"]:
        scores["perception"] = score_multiple_choice(buckets["perception"], lookup, labels, cfg)
    if buckets["pragmatic"]:
        scores["pragmatic"] = score_multiple_choice(
            buckets["pragmatic"], lookup,
            ["correct", "paired_condition", "wrong_function", "scenario_plausible"], cfg)
    if buckets["content_absolute"]:
        scores["content_absolute"] = score_absolute(buckets["content_absolute"], cfg, "content")
    if buckets["content_pair"]:
        scores["content_pair"] = score_pairs(
            buckets["content_pair"], trials, cfg,
            config.get("paired", {}).get("tie_policy", "individual"))
    if buckets["tone_absolute"]:
        scores["tone_absolute"] = score_absolute(buckets["tone_absolute"], cfg, "tone")

    invalid_by_type = Counter(r.get("task_type", "?") for r in bad)
    K.report("score", planned=len(good) + len(bad), completed=len(good),
             skipped=sum(1 for r in good if r["task_type"] not in wanted),
             failed=0, invalid=len(bad))
    if bad:
        print("  invalid records retained, excluded from every denominator:")
        for task_type, count in sorted(invalid_by_type.items()):
            print(f"    {task_type}: {count}")
        for record in bad[:3]:
            print(f"    {record.get('task_id', '?')}: {record.get('errors', [])[:1]}"[:150])
    if not scores:
        print("  nothing to score yet")
        return 0

    for name, block in scores.items():
        print(f"\n{name}")
        if name in ("perception", "pragmatic"):
            show("overall accuracy", block, "overall_accuracy")
            show("macro-F1", block, "macro_f1")
            if name == "perception":
                show("baseline false-positive rate", block,
                     "baseline_false_positive_rate")
            for model, stat in block["by_model"].items():
                show(f"  {model}", {"x": stat}, "x")
            if block["flagged_excluded"]:
                print(f"  excluded as ambiguous: {block['flagged_excluded']} row(s) "
                      f"over {len(block['flagged_items'])} item(s)")
        elif name == "content_pair":
            show("paired accuracy (chance 0.500)", block, "content_pair_accuracy")
            show("aggregated", block, "aggregated_accuracy")
            print(f"  split decisions: {block['split_decisions']} of {block['trials']} "
                  f"trial(s) · policy {block['tie_policy']}")
            agreement = block["agreement"]
            print(f"  judge agreement: pairwise "
                  f"{agreement.get('pairwise_agreement')}, kappa "
                  f"{agreement.get('fleiss_kappa')}")
        else:
            key = "content_absolute" if name == "content_absolute" else "tone_absolute"
            show("mean score (1-5)", block, key)
            print(f"  normalized (0-1): {block['normalized']}")
            print(f"  distribution: {block['distribution']}")
            print(f"  unjudgeable: {block['unjudgeable']} "
                  f"({block['unjudgeable_rate']})")
            agreement = block["agreement"]
            print(f"  judge agreement: exact {agreement.get('exact_agreement')}, "
                  f"within one {agreement.get('within_one')}, spearman "
                  f"{agreement.get('mean_pairwise_spearman')}")

    if args.dry_run:
        print("\ndry run: nothing written")
        return 0
    out_dir = Path(args.output) if args.output else K.stage_dir("scores")
    payload = {"scored_at": K.now(), "seed": seed,
               "bootstrap_resamples": cfg[0], "confidence": cfg[1],
               "invalid_records": len(bad), "invalid_by_task_type": dict(invalid_by_type),
               "scores": scores}
    try:
        K.write_json(out_dir / "scores.json", payload, overwrite=args.overwrite)
    except K.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"\nwrote {(out_dir / 'scores.json').relative_to(K.HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

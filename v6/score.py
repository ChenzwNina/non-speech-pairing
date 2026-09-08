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
            "interpretation": "judge_outputs:interpretation_match",
            "content_match": "judge_outputs:content_match",
            "content_pair": "judge_outputs:content_pairwise",
            "tone": "judge_outputs:tone_judgement"}


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


def majority(votes: list) -> bool | None:
    """True, False, or None on a tie. A tie is reported, never rounded into a score."""
    if not votes:
        return None
    yes = sum(1 for v in votes if v)
    if yes * 2 == len(votes):
        return None
    return yes * 2 > len(votes)


def score_interpretation(rows: list[dict], cfg) -> dict:
    """Did the model's own account of the sound match any acceptable reading?

    Three judges; two agreeing carries it. A tie is not half a point — it is recorded, because
    a split panel means the answer sat on the boundary of the interpretation set, which is a
    fact about the item rather than about the model.
    """
    resamples, confidence, seed = cfg
    by_task: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    decided, ties = [], []
    for votes in by_task.values():
        verdict = majority([v["parsed"]["matched"] for v in votes])
        row = dict(votes[0])
        if verdict is None:
            ties.append(row)
            continue
        row["_correct"] = verdict
        picked = Counter(v["parsed"]["interpretation_index"]
                         for v in votes if v["parsed"]["matched"]).most_common(1)
        row["_which"] = picked[0][0] if picked else 0
        decided.append(row)
    return {
        "n": len(decided), "ties": len(ties),
        "tie_rate": len(ties) / len(by_task) if by_task else None,
        "judges": sorted({r.get("judge", "?") for r in rows}),
        "accuracy": cluster_bootstrap(decided, accuracy, resamples, confidence, seed),
        "by_model": by_group(decided, lambda r: r.get("evaluated_model", "?"), accuracy,
                             resamples, confidence, seed),
        "by_vocalization": by_group(decided, lambda r: r.get("gold_vocalization", "?"),
                                    accuracy, resamples, confidence, seed),
        "which_matched": dict(sorted(Counter(r["_which"] for r in decided).items())),
        "tie_items": sorted({r["item_id"] for r in ties}),
    }


def score_ranking(rows: list[dict], trials: dict, ineligible: list[dict], cfg) -> dict:
    """Conditional ranking accuracy over the A/B pair, and the coverage it is conditional on.

    The unit is the item, not the trial. An eligible item is judged in both directions — does
    R_A win under A's context, does R_B win under B's context — and scores 1, 0.5 or 0. A model
    whose two replies are interchangeable cannot collect 0.5 by luck the way one direction
    would let it; it has to win the direction it was given, twice.

    Ineligible items are N/A, not zero. Their perception failure is already counted in the
    perception score and charging it again here would penalise it twice. Coverage is what keeps
    that honest, reported beside the accuracy so a thin denominator cannot hide behind a high
    score.
    """
    resamples, confidence, seed = cfg
    by_direction: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        trial = trials.get(row["task_id"])
        if trial is None:
            continue
        won = row["parsed"]["preferred_response"] == trial["gold_slot"]
        by_direction[(trial["evaluated_model"], trial["item_id"],
                      trial["direction"])].append(won)

    per_item: dict[tuple, dict] = defaultdict(dict)
    ties = 0
    for (model, item_id, direction), votes in by_direction.items():
        verdict = majority(votes)
        ties += verdict is None
        per_item[(model, item_id)][direction] = verdict

    scored, widths = [], Counter()
    for (model, item_id), directions in sorted(per_item.items()):
        decided = [v for v in directions.values() if v is not None]
        if not decided:
            continue
        widths[len(decided)] += 1
        scored.append({"evaluated_model": model, "item_id": item_id,
                       "_score": sum(1.0 for v in decided if v) / len(decided)})

    eligible = len(per_item)
    planned = eligible + len({(r["evaluated_model"], r["item_id"]) for r in ineligible})
    statistic = lambda rs: mean(r["_score"] for r in rs)
    return {
        "eligible_items": eligible, "planned_items": planned,
        "coverage": eligible / planned if planned else None,
        "ineligible_reasons": dict(sorted(Counter(
            r["reason"].split(" for ")[0] for r in ineligible).items())),
        "judges": sorted({r.get("judge", "?") for r in rows}),
        "direction_ties": ties,
        "items_with_both_directions": widths.get(2, 0),
        "conditional_accuracy": cluster_bootstrap(scored, statistic, resamples, confidence,
                                                  seed),
        "by_model": by_group(scored, lambda r: r["evaluated_model"], statistic, resamples,
                             confidence, seed),
        "score_distribution": dict(sorted(Counter(r["_score"] for r in scored).items())),
        "chance": 0.5,
    }


def score_response_quality(rows: list[dict], heard: set, cfg) -> dict:
    """A 1-5 mean over the conditions whose sound was identified, and the same with the rest floored.

    Two questions from one set of judgements. The conditional score asks whether a model that
    heard the sound can respond to it; the end-to-end score asks whether it gets from hearing to
    responding at all, so its denominator is every condition rather than the surviving ones.
    Reporting only the first flatters a model that heard little and answered that little well;
    reporting only the second hides which half it failed at.
    """
    resamples, confidence, seed = cfg
    valid, unjudgeable = [], []
    for row in rows:
        if row["parsed"].get("unjudgeable"):
            unjudgeable.append(row)
            continue
        key = (row.get("evaluated_model", "?"), row["item_id"], row["condition"])
        valid.append(dict(row, _score=float(row["parsed"]["score"]), _heard=key in heard))
    conditional = [r for r in valid if r["_heard"]]
    # Normalised so a perception failure scores 0 rather than the 0.25 a floored 1-5 would give.
    end_to_end = [dict(r, _norm=(r["_score"] - 1) / 4 if r["_heard"] else 0.0) for r in valid]
    statistic = lambda rs: mean(r["_score"] for r in rs)
    normalized = lambda rs: mean(r["_norm"] for r in rs)
    return {
        "n": len(valid), "n_conditional": len(conditional),
        "unjudgeable": len(unjudgeable),
        "judges": sorted({r.get("judge", "?") for r in rows}),
        "conditional_quality": cluster_bootstrap(conditional, statistic, resamples,
                                                 confidence, seed),
        "end_to_end": cluster_bootstrap(end_to_end, normalized, resamples, confidence, seed),
        "by_model_conditional": by_group(conditional, lambda r: r.get("evaluated_model", "?"),
                                         statistic, resamples, confidence, seed),
        "by_model_end_to_end": by_group(end_to_end, lambda r: r.get("evaluated_model", "?"),
                                        normalized, resamples, confidence, seed),
        "distribution": dict(sorted(Counter(int(r["_score"]) for r in conditional).items())),
        "agreement": ordinal_agreement(conditional) if conditional else {},
    }


def score_tone(rows: list[dict], cfg) -> dict:
    """Two audio judges. Both hearing a wrong tone scores 0, neither scores 1, a split waits.

    A split is neither 0.5 nor dropped quietly — it goes to a human queue and stays out of the
    denominator until someone listens. The rubric is a list of things a judge should be
    confident about, so disagreement means neither verdict was.
    """
    resamples, confidence, seed = cfg
    by_task: dict[str, list[dict]] = defaultdict(list)
    unjudgeable = 0
    for row in rows:
        if row["parsed"].get("unjudgeable"):
            unjudgeable += 1
            continue
        by_task[row["task_id"]].append(row)
    scored, review = [], []
    for task, votes in by_task.items():
        heard = [v["parsed"]["inappropriate_present"] for v in votes]
        if len(set(heard)) > 1:
            review.append({"task_id": task, "item_id": votes[0]["item_id"],
                           "condition": votes[0]["condition"],
                           "evaluated_model": votes[0].get("evaluated_model", "?"),
                           "verdicts": {v.get("judge", "?"): v["parsed"] for v in votes}})
            continue
        scored.append(dict(votes[0], _score=0.0 if heard[0] else 1.0,
                           _tones=[t for v in votes for t in v["parsed"]["tones_heard"]]))
    statistic = lambda rs: mean(r["_score"] for r in rs)
    return {
        "n": len(scored), "awaiting_human_review": len(review),
        "split_rate": len(review) / len(by_task) if by_task else None,
        "unjudgeable": unjudgeable,
        "judges": sorted({r.get("judge", "?") for r in rows}),
        "tone_ok_rate": cluster_bootstrap(scored, statistic, resamples, confidence, seed),
        "by_model": by_group(scored, lambda r: r.get("evaluated_model", "?"), statistic,
                             resamples, confidence, seed),
        "tones_heard": dict(sorted(Counter(t for r in scored for t in r["_tones"]).items())),
        "review_queue": review,
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
    ineligible = K.read_jsonl(tasks_dir / "content_pairs_ineligible.jsonl")

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

    # Which (model, item, condition) had its vocalization identified. Everything downstream is
    # conditional on this, so it is derived once from the perception judgements rather than
    # trusted from a flag someone else set.
    heard = set()
    for row in buckets["perception"]:
        task = lookup.get(row["task_id"])
        if task and row["parsed"]["selected_option"] == task["correct_option"]:
            heard.add((row.get("evaluated_model", "?"), row["item_id"], row["condition"]))

    labels = list(config["inventory"])
    scores: dict[str, dict] = {}
    if buckets["perception"]:
        scores["perception"] = score_multiple_choice(buckets["perception"], lookup, labels, cfg)
    if buckets["interpretation"]:
        scores["interpretation"] = score_interpretation(buckets["interpretation"], cfg)
    if buckets["content_match"]:
        scores["response_quality"] = score_response_quality(buckets["content_match"], heard,
                                                            cfg)
    if buckets["content_pair"]:
        scores["ranking"] = score_ranking(buckets["content_pair"], trials, ineligible, cfg)
    if buckets["tone"]:
        scores["tone"] = score_tone(buckets["tone"], cfg)

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
        if name == "perception":
            show("accuracy", block, "overall_accuracy")
            show("macro-F1", block, "macro_f1")
            show("baseline false positives", block, "baseline_false_positive_rate")
        elif name == "interpretation":
            show("match rate (2 of 3 judges)", block, "accuracy")
            print(f"  panel ties: {block['ties']} ({block['tie_rate']})")
            print(f"  which reading matched: {block['which_matched']}")
        elif name == "response_quality":
            show("conditional quality (1-5)", block, "conditional_quality")
            show("end-to-end (0-1)", block, "end_to_end")
            print(f"  scored {block['n_conditional']} of {block['n']} on perception-correct "
                  f"conditions · distribution {block['distribution']}")
        elif name == "ranking":
            show("conditional accuracy (chance .500)", block, "conditional_accuracy")
            print(f"  coverage: {block['eligible_items']}/{block['planned_items']} items "
                  f"eligible ({block['coverage']})")
            print(f"  both directions judged: {block['items_with_both_directions']} · "
                  f"panel ties: {block['direction_ties']}")
            print(f"  per-item scores: {block['score_distribution']}")
            if block["ineligible_reasons"]:
                print(f"  ineligible: {block['ineligible_reasons']}")
        elif name == "tone":
            show("tone acceptable rate", block, "tone_ok_rate")
            print(f"  awaiting human review: {block['awaiting_human_review']} "
                  f"({block['split_rate']}) · unjudgeable {block['unjudgeable']}")
            if block["tones_heard"]:
                print(f"  tones heard: {block['tones_heard']}")
        for model, stat in block.get("by_model", {}).items():
            show(f"  {model}", {"x": stat}, "x")

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

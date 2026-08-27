"""The curation loop: write -> mechanical gates -> bivalence probe -> discriminability probe.

The two model-based gates test different things.

  bivalence (blind judge, tag-free transcript)
      Because the two performances are word-for-word identical, no text-only reader can tell them
      apart — that is guaranteed by construction, not something to measure. What this probe
      actually measures is:
        1. whether BOTH readings are coherent on those words (`both_plausible`) — if a strong
           reader calls one reading impossible, that performance is a stretch and the item is dead;
        2. how strong a PRIOR the prosody has to overcome. A reader with no acoustic evidence falls
           back on base rates: a laugh between equals in a low-stakes exchange is probably
           affiliative, a speaker recounting their own mishap is probably self-deprecating. That
           prior is recorded on the item, not gated away.
      A confident prior is disqualifying (prosody will not be believed); a unanimous but hedged
      prior is not — it just makes one performance the harder direction. The pair-level metric
      neutralises the prior anyway: an item counts as passed only if a model gets BOTH performances
      right, so answering from the prior alone scores zero, not 50%.

  discriminability (listener judge, one tagged performance)
      A reader given the performance directions MUST be able to recover the intended function. If
      it cannot, the performance is too weak to carry the contrast and the audio will be a coin
      flip for humans too.

Both judges see the same two options — the performances' own `expected_answer` strings — with the
order shuffled per run to cancel position bias.
"""

import collections
import random
from concurrent.futures import ThreadPoolExecutor

from . import claude_cli, prompts, taxonomy, validate

Thresholds = collections.namedtuple(
    "Thresholds",
    "blind_runs listener_runs max_blind_vote_share max_blind_confidence "
    "min_both_plausible min_listener_accuracy strict_split",
)

DEFAULT_THRESHOLDS = Thresholds(
    blind_runs=4,
    listener_runs=3,
    max_blind_vote_share=0.75,  # only enforced when strict_split is on
    max_blind_confidence=0.70,  # a *confident* text prior means prosody will not be believed
    min_both_plausible=0.50,  # both readings must be coherent on these words
    min_listener_accuracy=0.67,  # 3 runs: at least 2/3 correct, for each performance
    strict_split=False,  # demand a split text-only vote too (very few scenarios survive)
)


class Report(object):
    def __init__(self):
        self.cost_usd = 0.0
        self.stages = collections.OrderedDict()
        self.accepted = False
        self.rejected_by = None

    def add(self, name, payload):
        self.stages[name] = payload

    def as_dict(self):
        return {
            "accepted": self.accepted,
            "rejected_by": self.rejected_by,
            "cost_usd": round(self.cost_usd, 4),
            "stages": self.stages,
        }


def _options(item):
    return [item["performance_a"]["expected_answer"], item["performance_b"]["expected_answer"]]


def _run_votes(make_prompt, system, model, runs, options, rng, workers=4):
    """Run a judge `runs` times with the option order shuffled. Returns (votes, records, cost).

    A vote is 0 for performance_a's answer, 1 for performance_b's.
    """
    plans = []
    for _ in range(runs):
        flipped = rng.random() < 0.5
        shown = list(reversed(options)) if flipped else list(options)
        plans.append((flipped, shown))

    def one(plan):
        flipped, shown = plan
        obj, cost = claude_cli.ask_json(make_prompt(shown), system=system, model=model)
        raw_choice = obj.get("choice")
        try:
            idx = int(raw_choice) - 1
        except (TypeError, ValueError):
            idx = None
        if idx not in (0, 1):
            return None, {"error": "bad choice %r" % (raw_choice,), "raw": obj}, cost
        vote = (1 - idx) if flipped else idx
        record = {
            "shown_order": "b,a" if flipped else "a,b",
            "voted_for": "performance_a" if vote == 0 else "performance_b",
            "confidence": obj.get("confidence"),
            "both_plausible": obj.get("both_plausible"),
            "reason": obj.get("reason"),
        }
        return vote, record, cost

    votes, records, cost = [], [], 0.0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for vote, record, c in pool.map(one, plans):
            cost += c
            records.append(record)
            if vote is not None:
                votes.append(vote)
    return votes, records, cost


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bivalence_probe(item, model, thresholds, rng):
    """Are both readings coherent on these words, and how strong is the text-only prior?"""
    options = _options(item)

    def make(shown):
        return prompts.blind_prompt(item, shown, item["laugh_turn"], item["laugher"])

    votes, records, cost = _run_votes(
        make, prompts.BLIND_SYSTEM, model, thresholds.blind_runs, options, rng
    )
    if not votes:
        return {"ok": False, "reason": "no usable votes", "runs": records}, cost

    counts = collections.Counter(votes)
    vote_share = counts.most_common(1)[0][1] / float(len(votes))
    confs = [_as_float(r.get("confidence")) for r in records if r.get("confidence") is not None]
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    both = [bool(r.get("both_plausible")) for r in records if "both_plausible" in r]
    both_rate = (sum(both) / float(len(both))) if both else 0.0

    top_vote, top_count = counts.most_common(1)[0]
    favoured = "performance_a" if top_vote == 0 else "performance_b"
    problems = []
    if both_rate < thresholds.min_both_plausible:
        problems.append(
            "only %.0f%% of runs called both readings plausible — one performance is a stretch "
            "on these words" % (100 * both_rate)
        )
    if mean_conf > thresholds.max_blind_confidence:
        problems.append(
            "the text prior is held at mean confidence %.2f — too strong for prosody to overturn"
            % mean_conf
        )
    if thresholds.strict_split and vote_share > thresholds.max_blind_vote_share:
        problems.append("%d/%d text-only votes went to %s" % (top_count, len(votes), favoured))

    ok = not problems
    reason = None
    if not ok:
        reasons = [r.get("reason") for r in records if r.get("reason")][:2]
        reason = "%s. The blind reader said: %s" % ("; ".join(problems), " | ".join(reasons))
    return {
        "ok": ok,
        "reason": reason,
        "vote_share": round(vote_share, 3),
        "prior_favours": favoured,
        "prior_is_unanimous": vote_share == 1.0,
        "mean_confidence": round(mean_conf, 3),
        "both_plausible_rate": round(both_rate, 3),
        "votes": ["performance_a" if v == 0 else "performance_b" for v in votes],
        "runs": records,
    }, cost


def discriminability_probe(item, model, thresholds, rng):
    """Given the performance directions, can a reader recover each intended function? It must."""
    options = _options(item)
    out = {"ok": True, "reason": None, "per_performance": {}}
    cost = 0.0

    for idx, name in enumerate(("performance_a", "performance_b")):
        turns = item[name]["turns"]

        def make(shown, turns=turns):
            return prompts.listener_prompt(turns, shown, item["laugh_turn"], item["laugher"])

        votes, records, c = _run_votes(
            make, prompts.LISTENER_SYSTEM, model, thresholds.listener_runs, options, rng
        )
        cost += c
        correct = sum(1 for v in votes if v == idx)
        accuracy = correct / float(len(votes)) if votes else 0.0
        out["per_performance"][name] = {
            "accuracy": round(accuracy, 3),
            "correct": correct,
            "runs_used": len(votes),
            "detail": records,
        }
        if accuracy < thresholds.min_listener_accuracy:
            out["ok"] = False
            out["reason"] = (
                "%s is not recoverable from its own performance directions (%d/%d correct) — "
                "the tags do not carry the intended function" % (name, correct, len(votes))
            )
    return out, cost


def curate_one(
    pair,
    topic=None,
    avoid=None,
    writer_model="opus",
    judge_model="opus",
    thresholds=DEFAULT_THRESHOLDS,
    seed=0,
    max_attempts=3,
    skip_judges=False,
    log=print,
):
    """Produce one accepted item, or the last rejected attempt. Returns (item, Report)."""
    report = Report()
    rng = random.Random(seed)
    notes = None
    item = None

    for attempt in range(1, max_attempts + 1):
        log("  attempt %d/%d — writing (%s)" % (attempt, max_attempts, writer_model))
        item, cost = claude_cli.ask_json(
            prompts.writer_prompt(pair, topic=topic, avoid=avoid, notes=notes),
            system=prompts.WRITER_SYSTEM,
            model=writer_model,
        )
        report.cost_usd += cost

        fails = validate.check(item)
        report.add("mechanical", {"attempt": attempt, "failures": [f.as_dict() for f in fails]})
        if fails:
            log("  mechanical gates failed: %s" % "; ".join(f.code for f in fails))
            notes = "\n".join("  - %s: %s" % (f.code, f.detail) for f in fails)
            report.rejected_by = "mechanical"
            continue
        log("  mechanical gates passed")

        if skip_judges:
            report.accepted = True
            report.rejected_by = None
            break

        biv, cost = bivalence_probe(item, judge_model, thresholds, rng)
        report.cost_usd += cost
        report.add("bivalence", biv)
        if not biv["ok"]:
            log("  bivalence probe failed: %s" % biv["reason"])
            notes = (
                "A blind reader given only the tag-free transcript did not treat both readings as "
                "live options. %s\nRebuild so that both readings are genuinely available on these "
                "words: keep the wording neutral, and make sure neither speaker has a standing "
                "social incentive that decides the reading in advance." % biv["reason"]
            )
            report.rejected_by = "bivalence"
            continue
        log(
            "  bivalence probe passed (text prior %.0f%% -> %s, mean conf %.2f, both-plausible %.0f%%)"
            % (
                100 * biv["vote_share"],
                biv["prior_favours"],
                biv["mean_confidence"],
                100 * biv["both_plausible_rate"],
            )
        )

        disc, cost = discriminability_probe(item, judge_model, thresholds, rng)
        report.cost_usd += cost
        report.add("discriminability", disc)
        if not disc["ok"]:
            log("  discriminability probe failed: %s" % disc["reason"])
            notes = (
                "The performance directions did not carry the intended reading. %s\nKeep the "
                "words identical, but make the tags and punctuation of that performance "
                "unmistakable — set the framing on speaker A's turns too, not only on the "
                "laugh." % disc["reason"]
            )
            report.rejected_by = "discriminability"
            continue
        log(
            "  discriminability probe passed (a %.0f%%, b %.0f%%)"
            % (
                100 * disc["per_performance"]["performance_a"]["accuracy"],
                100 * disc["per_performance"]["performance_b"]["accuracy"],
            )
        )

        report.accepted = True
        report.rejected_by = None
        break

    if item is not None and report.accepted:
        item = finalise(item, pair, report)
    return item, report


def finalise(item, pair, report=None):
    """Attach taxonomy metadata, the evaluation probe, and the curation evidence."""
    fn_a, fn_b = pair.functions()
    laugher = item["laugher"]
    other = "B" if laugher == "A" else "A"

    item["performance_a"]["function"] = fn_a.as_dict()
    item["performance_b"]["function"] = fn_b.as_dict()
    item["pair"] = {
        "a": pair.a,
        "b": pair.b,
        "crosses_branch": pair.crosses_branch(),
        "note": pair.note,
    }
    item["probe"] = prompts.build_probe(
        item,
        laugher,
        other,
        item["performance_a"]["expected_answer"],
        item["performance_b"]["expected_answer"],
        gold_letter_a="a",
        gold_letter_b="b",
    )
    item["transcript_text"] = "\n".join(
        "%s: %s" % (t["speaker"], t["text"]) for t in item["transcript"]
    )

    if report is not None:
        biv = report.stages.get("bivalence") or {}
        disc = report.stages.get("discriminability") or {}
        prior = biv.get("prior_favours")
        harder = None
        if prior in ("performance_a", "performance_b"):
            harder = "performance_b" if prior == "performance_a" else "performance_a"
        item["curation"] = {
            "text_prior": {
                "note": "What a strong reader guesses from the tag-free transcript alone, with no "
                "acoustic evidence. It cannot discriminate the two performances (their words are "
                "identical) — it only shows which reading is the default and how firmly it is "
                "held. `prosody_must_overturn` is the harder direction of the pair.",
                "favours": prior,
                "vote_share": biv.get("vote_share"),
                "mean_confidence": biv.get("mean_confidence"),
                "both_plausible_rate": biv.get("both_plausible_rate"),
                "prosody_must_overturn": harder,
                "votes": biv.get("votes"),
            },
            "script_discriminability": {
                "note": "Whether a reader given the performance directions recovers the intended "
                "function. Text-level proxy for the audio — confirm on the rendered audio "
                "before shipping.",
                "performance_a": (disc.get("per_performance", {}).get("performance_a") or {}).get(
                    "accuracy"
                ),
                "performance_b": (disc.get("per_performance", {}).get("performance_b") or {}).get(
                    "accuracy"
                ),
            },
            "audio_verified": False,
        }
    return item

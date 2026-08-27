"""Verifier for laughter-ambiguity transcripts, judged by GPT-5.4.

Importable module + CLI. Two stages per candidate:

STAGE 0 - format gate (Python, free)
    Exactly 3 prior turns, speakers are A/B, no vocal annotation leaked into
    the text. The judge is never asked to count turns.

STAGE A - balance panel (the 50/50 test)
    The judge sees ONLY the words, plus both laughter functions in full (name,
    laughable type, definition, example, example explanation) presented as
    "Option 1" / "Option 2", and must pick which function the laughter would
    serve. Runs `--trials` independent calls with presentation order
    counterbalanced (half with function 1 in the first slot, half with
    function 2) so a preference for whichever option is listed first cannot
    masquerade as balance.

    Each trial also reports the judge's confidence that function 1 is the
    intended one, 0-100. A perfectly ambiguous transcript sits at 50. Two gates:
    the mean confidence must land near 50, and the picks must not be dominated
    by which option was listed second. The vote split is reported alongside for
    comparison but no longer decides anything.

Usage:
    python verifier.py                                # verify transcripts.json
    python verifier.py --dry-run --limit 1            # print prompts, no API calls
    python verifier.py --trials 10 --prob-tolerance 7   # stricter
    python verifier.py --workers 12                   # faster, more concurrency
    python verifier.py --in runs/v1.json --out runs/v1.verdicts.json
"""

import argparse
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads OPENAI_API_KEY from .env

# --- config ------------------------------------------------------------------

MODEL = "gpt-5.4"
EFFORT = "low"           # a first-read forced choice; deep reasoning defeats the point
MAX_OUTPUT_TOKENS = 4000
DEFAULT_IN = Path("transcripts.json")
DEFAULT_OUT = Path("verdicts.json")

# Independent trials per candidate. Must be even so the two presentation orders
# are equally represented. Measured on real data, the judge's mean probability
# settles within a few points by 4-6 trials, while the vote share needs ~16 - so
# gating on the probability buys the same confidence for a third of the calls.
TRIALS = 6

# Gate 1 - ambiguity. How far the mean of the judge's probability estimates may
# sit from 50. 10.0 -> a mean anywhere in 40-60 passes.
PROB_TOLERANCE = 10.0

# Gate 2 - reliability. Share of trials that picked whichever function was
# listed SECOND. The judge has a real second-slot preference (~75% on the first
# candidate measured), so counterbalancing cancels it in the mean; but when it
# runs this high the picks are being driven by position rather than by the
# dialogue, and the reading for that candidate is not trustworthy.
SLOT2_MAX = 0.70

# The vote split is still computed and reported so the two gates can be
# compared on the same run, but it no longer decides anything.

# Concurrency for the trials of one candidate. The calls are independent, so
# this is the difference between a 7-minute run and an hour-long one.
WORKERS = 6

# Network plumbing only - nothing to do with scoring. A failed call (rate limit,
# timeout, 5xx) is retried up to 3 times, waiting 2s, then 4s, then 8s.
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0

# --- prompts -----------------------------------------------------------------

PANEL_SYSTEM_PROMPT = """
You are an expert annotator of laughter pragmatics in spoken dialogue.

You will see a short dialogue transcript and two candidate pragmatic functions for
laughter placed at the marked current turn. Each function is given with its name, its
laughable type, its definition, and an example with an explanation - use those to fix
the distinction precisely before you decide.

You see the WORDS ONLY - no audio, and no information about how the laughter sounds.

Decide which of the two functions the laughter is more likely to be serving, judging
from the lexical content and the interactional context alone.

This is a forced choice. You must pick one option even when the two feel close - do
not refuse, hedge into a tie, or answer "both". Also report your probability that
Option 1 is the intended function, as an integer from 0 to 100; use 50 when the two
are genuinely indistinguishable from the words.

Report the single strongest cue in the wording that drove your choice, quoted verbatim
from the dialogue. If nothing in the wording pushed you either way and the choice was
effectively arbitrary, return an empty string for the cue.
"""

PANEL_SCHEMA = {
    "type": "object",
    "properties": {
        "pick": {
            "type": "string",
            "enum": ["option_1", "option_2"],
            "description": "Which option the laughter more likely serves.",
        },
        "p_option_1": {
            "type": "integer",
            "description": "Probability (0-100) that Option 1 is the intended function.",
        },
        "cue": {
            "type": "string",
            "description": "Verbatim span from the dialogue that drove the choice, or \"\" if arbitrary.",
        },
    },
    "required": ["pick", "p_option_1", "cue"],
    "additionalProperties": False,
}

PANEL_USER_TEMPLATE = """
[dialogue topic]: {topic}

[dialogue]
{dialogue}

Laughter occurs at the CURRENT TURN, marked above.

[Option 1]
{option_1}

[Option 2]
{option_2}

Which option is the laughter more likely serving, judging from the words alone?
"""


# --- helpers -----------------------------------------------------------------

def describe_function(fn):
    """The full CSV row for one function, as shown to the judge."""
    return (
        f"Function name - {fn['function']}\n"
        f"Laughable type - {fn['laughable_type']}\n"
        f"Definition - {fn['definition']}\n"
        f"Example - {fn['example']}\n"
        f"Example explanation - {fn['example_explanation']}"
    )


def render_dialogue(record):
    """Turn a result's transcript into plain text, marking the current turn."""
    parsed = record.get("transcript_json")
    if not isinstance(parsed, dict):
        # Fall back to the raw text so the candidate can still be judged.
        return (record.get("transcript") or "").strip()

    lines = [f"{t.get('speaker')}: {t.get('text')}" for t in parsed.get("prior_turns") or []]
    current = parsed.get("current_turn") or {}
    lines.append(f"{current.get('speaker')}: {current.get('text')}    <-- CURRENT TURN")
    return "\n".join(lines)


def check_format(record):
    """Stage 0. Returns a list of problems (empty means clean)."""
    parsed = record.get("transcript_json")
    if not isinstance(parsed, dict):
        return ["transcript did not parse as JSON"]

    problems = []
    prior = parsed.get("prior_turns")
    current = parsed.get("current_turn")

    if not isinstance(prior, list) or len(prior) != 3:
        problems.append(
            f"expected 3 prior_turns, got {len(prior) if isinstance(prior, list) else 'none'}"
        )
    if not isinstance(current, dict):
        problems.append("current_turn is not an object")

    turns = [*(prior if isinstance(prior, list) else []),
             *([current] if isinstance(current, dict) else [])]
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict):
            problems.append(f"turn {i} is not an object")
            continue
        if turn.get("speaker") not in ("A", "B"):
            problems.append(f"turn {i} speaker is {turn.get('speaker')!r}, expected 'A' or 'B'")
        text = turn.get("text") or ""
        if re.search(r"\[.*?\]|\blaugh\w*\b|<laughter", text, re.IGNORECASE):
            problems.append(f"turn {i} contains a vocal annotation: {text!r}")

    # Seen in practice: the writer repeats the last prior turn as the current one.
    if (isinstance(prior, list) and prior and isinstance(current, dict)
            and prior[-1].get("text") == current.get("text")):
        problems.append("current_turn duplicates the last prior turn")
    return problems


def build_panel_prompt(record, a_first):
    """One trial's user prompt. a_first=True puts function 1 in the Option 1 slot."""
    fn_a, fn_b = record["laughter_functions"]
    first, second = (fn_a, fn_b) if a_first else (fn_b, fn_a)
    return PANEL_USER_TEMPLATE.format(
        topic=record["topic"],
        dialogue=render_dialogue(record),
        option_1=describe_function(first),
        option_2=describe_function(second),
    )


def call_panel_trial(client, user_prompt, args):
    """One structured Responses API call. Returns (parsed dict, usage dict)."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.responses.create(
                model=args.model,
                instructions=PANEL_SYSTEM_PROMPT,
                input=user_prompt,
                reasoning={"effort": args.effort},
                text={"format": {"type": "json_schema", "name": "laughter_function_choice",
                                 "schema": PANEL_SCHEMA, "strict": True}},
                max_output_tokens=args.max_output_tokens,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"response status {response.status} "
                    f"({getattr(response, 'incomplete_details', None)}) "
                    "- raise --max-output-tokens"
                )
            usage = response.usage
            return json.loads(response.output_text), {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"      retry {attempt + 1}/{MAX_RETRIES - 1} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise last_error


def binomial_two_sided_p(successes, n):
    """Exact two-sided binomial test against p=0.5. 1.0 means a perfect tie."""
    if n == 0:
        return 1.0

    def cdf(k):
        return sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n

    lower = cdf(successes)
    upper = 1.0 - cdf(successes - 1) if successes > 0 else 1.0
    return min(1.0, 2 * min(lower, upper))


def run_balance_panel(client, record, args):
    """Counterbalanced forced-choice panel. Returns (balance dict, usage dict)."""
    totals = {"input_tokens": 0, "output_tokens": 0}

    # Alternate presentation order so each order gets exactly half the trials.
    orders = [i % 2 == 0 for i in range(args.trials)]

    def one_trial(a_first):
        result, usage = call_panel_trial(client, build_panel_prompt(record, a_first), args)
        # Map the option slot back to the actual function.
        picked_a = (result["pick"] == "option_1") == a_first
        p_a = result["p_option_1"] if a_first else 100 - result["p_option_1"]
        return {
            "a_first": a_first,
            "picked": "function_1" if picked_a else "function_2",
            "p_function_1": p_a,
            "cue": result["cue"],
        }, usage

    # The trials are independent, so run them concurrently. Results are collected
    # in submission order so the record is reproducible regardless of timing.
    workers = max(1, min(args.workers, len(orders)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(one_trial, orders))

    trials = []
    for trial, usage in outcomes:
        trials.append(trial)
        for k in totals:
            totals[k] += usage[k]

    n = len(trials)
    picks_a = sum(1 for t in trials if t["picked"] == "function_1")
    pick_share_a = picks_a / n
    mean_p_a = sum(t["p_function_1"] for t in trials) / n

    # Position effect. slot2_share is how often the second-listed option won;
    # order_gap is how far the two presentation orders disagree on the mean
    # probability. Both measure the same pull, coarsely and finely.
    slot2_share = sum(
        1 for t in trials if (t["picked"] == "function_1") != t["a_first"]
    ) / n
    by_order = {
        order: [t["p_function_1"] for t in trials if t["a_first"] == order]
        for order in (True, False)
    }
    order_gap = abs(
        sum(by_order[True]) / len(by_order[True])
        - sum(by_order[False]) / len(by_order[False])
    ) if by_order[True] and by_order[False] else 0.0
    position_bias = slot2_share > args.slot2_max or (1 - slot2_share) > args.slot2_max

    # Trials where the judge reported no lexical cue at all. A high share means
    # the choice was near-arbitrary - which is what a good candidate looks like,
    # but is also what an incoherent one looks like, so it is reported, not gated.
    arbitrary = sum(1 for t in trials if not t["cue"].strip())

    pick_imbalance = abs(pick_share_a - 0.5)
    prob_imbalance = abs(mean_p_a - 50.0)
    # Confidence gates the verdict; the vote split is reported for comparison.
    balanced = prob_imbalance <= args.prob_tolerance and not position_bias

    return {
        "trials": n,
        "picks_function_1": picks_a,
        "picks_function_2": n - picks_a,
        "pick_share_function_1": round(pick_share_a, 3),
        "pick_imbalance": round(pick_imbalance, 3),
        "mean_p_function_1": round(mean_p_a, 1),
        "prob_imbalance": round(prob_imbalance, 1),
        "binomial_p": round(binomial_two_sided_p(picks_a, n), 4),
        "slot2_share": round(slot2_share, 3),
        "order_gap": round(order_gap, 1),
        "position_bias_suspected": position_bias,
        "arbitrary_share": round(arbitrary / n, 3),
        "balanced": balanced,
        "cues": [t["cue"] for t in trials if t["cue"].strip()],
        "trial_detail": trials,
    }, totals


def verify_record(client, record, args):
    """Full verification of one candidate. Returns a verdict dict."""
    verdict = {
        "id": record["id"],
        "topic": record["topic"],
        "functions": [fn["function"] for fn in record["laughter_functions"]],
        "format_problems": check_format(record),
    }
    # A malformed candidate fails whatever the panel says, so don't pay for it.
    if verdict["format_problems"]:
        verdict["balance"] = None
        verdict["passed"] = False
        verdict["usage"] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        return verdict

    balance, usage = run_balance_panel(client, record, args)
    verdict["balance"] = balance
    verdict["passed"] = balance["balanced"]
    verdict["usage"] = {**usage, "total_tokens": sum(usage.values())}
    return verdict


def load_done(path):
    """Ids already verified, so an interrupted run can be resumed."""
    if not path.exists():
        return {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {v["id"]: v for v in previous.get("verdicts", []) if not v.get("error")}


def write_output(path, verdicts, args):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verifier_model": args.model,
        "effort": args.effort,
        "trials_per_candidate": args.trials,
        "prob_tolerance": args.prob_tolerance,
        "slot2_max": args.slot2_max,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.infile),
        "panel_system_prompt": PANEL_SYSTEM_PROMPT,
        "verdicts": verdicts,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT,
                        choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--max-output-tokens", type=int, default=MAX_OUTPUT_TOKENS)
    parser.add_argument("--trials", type=int, default=TRIALS,
                        help="forced-choice trials per candidate (must be even)")
    parser.add_argument("--prob-tolerance", type=float, default=PROB_TOLERANCE,
                        help="max |mean P(function 1) - 50| to count as balanced")
    parser.add_argument("--slot2-max", type=float, default=SLOT2_MAX,
                        help="max share of picks going to the second-listed option")
    parser.add_argument("--workers", type=int, default=WORKERS,
                        help="concurrent trials per candidate")
    parser.add_argument("--limit", type=int, help="only verify the first N candidates")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts instead of calling the API")
    parser.add_argument("--overwrite", action="store_true",
                        help="re-verify ids already present in --out")
    args = parser.parse_args()

    if args.trials < 2 or args.trials % 2 != 0:
        raise SystemExit("--trials must be an even number >= 2 "
                         "(the two presentation orders are counterbalanced)")

    if not args.infile.exists():
        raise SystemExit(f"{args.infile} not found - run generate_transcripts.py first")

    source = json.loads(args.infile.read_text(encoding="utf-8"))
    records = [r for r in source.get("results", []) if not r.get("error")]
    if args.limit:
        records = records[: args.limit]

    print(f"{len(records)} candidate(s) from {args.infile} "
          f"(written by {source.get('model', 'unknown')})")
    print(f"verifier {args.model}: {args.trials} forced-choice trials each "
          f"-> {len(records) * args.trials} API calls, {args.workers} at a time")

    if args.dry_run:
        for record in records:
            print("\n" + "=" * 70)
            print(record["id"])
            print("=" * 70)
            print("--- stage 0: format check ---")
            print(check_format(record) or "ok")
            print("--- panel system ---")
            print(PANEL_SYSTEM_PROMPT)
            print("--- panel user (function 1 in slot 1) ---")
            print(build_panel_prompt(record, a_first=True))
            print("--- panel user (function 2 in slot 1) ---")
            print(build_panel_prompt(record, a_first=False))
        return

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is empty - set it in .env (see .env.example)")

    client = OpenAI(api_key=api_key)
    done = {} if args.overwrite else load_done(args.out)
    if done:
        print(f"resuming: {len(done)} verdict(s) already in {args.out}")

    verdicts = []
    for i, record in enumerate(records, 1):
        if record["id"] in done:
            verdicts.append(done[record["id"]])
            print(f"[{i}/{len(records)}] skip {record['id']}")
            continue

        print(f"[{i}/{len(records)}] {record['id']}")
        try:
            verdict = verify_record(client, record, args)
            b = verdict["balance"]
            if b is None:
                print(f"    REVISE format (panel skipped)  {verdict['format_problems'][0]}")
            else:
                split = f"{b['picks_function_1']}/{b['picks_function_2']}"
                if verdict["passed"]:
                    flag = "PASS"
                elif b["position_bias_suspected"]:
                    flag = "REVISE position-bias"
                else:
                    flag = "REVISE unbalanced"
                print(f"    {flag}  meanP={b['mean_p_function_1']}"
                      f"  (off-50 {b['prob_imbalance']})  vote={split}"
                      f"  slot2={b['slot2_share']:.2f}  gap={b['order_gap']}")
        except Exception as exc:
            verdict = {
                "id": record["id"],
                "topic": record["topic"],
                "functions": [fn["function"] for fn in record["laughter_functions"]],
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"    failed: {verdict['error']}", file=sys.stderr)

        verdicts.append(verdict)
        write_output(args.out, verdicts, args)  # checkpoint after every candidate

    write_output(args.out, verdicts, args)

    graded = [v for v in verdicts if not v.get("error")]
    scored = [v for v in graded if v.get("balance")]
    passed = [v for v in graded if v["passed"]]
    skipped = len(graded) - len(scored)
    print(f"\nwrote {len(verdicts)} verdict(s) to {args.out}")
    if skipped:
        print(f"{skipped} skipped the panel on a format problem")
    if scored:
        n = len(scored)
        label = "score" if n == 1 else f"mean over {n}"
        mean_imbalance = sum(v["balance"]["pick_imbalance"] for v in scored) / n
        mean_prob = sum(v["balance"]["prob_imbalance"] for v in scored) / n
        mean_arb = sum(v["balance"]["arbitrary_share"] for v in scored) / n
        print(f"{len(passed)}/{n} balanced "
              f"(mean P within {args.prob_tolerance} of 50, "
              f"slot-2 share <= {args.slot2_max})")
        mean_slot2 = sum(v["balance"]["slot2_share"] for v in scored) / n
        mean_gap = sum(v["balance"]["order_gap"] for v in scored) / n
        print(f"  prob imbalance   {label} {mean_prob:.1f}  (0.0 = mean P exactly 50) GATE")
        print(f"  slot-2 share     {label} {mean_slot2:.2f}  (0.50 = no position pull) GATE")
        print(f"  order gap        {label} {mean_gap:.1f}  (points of P between orders)")
        print(f"  vote imbalance   {label} {mean_imbalance:.3f}  (reported, does not gate)")
        print(f"  arbitrary share  {label} {mean_arb:.2f}  (trials with no lexical cue)")
    failures = [v for v in verdicts if v.get("error")]
    if failures:
        print(f"{len(failures)} candidate(s) failed", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Counterfactual three-vocalization scenarios: A proposes, B reacts wordlessly, A replies.

The tested model plays Speaker A. Each scenario is one shared context plus one proposal,
held exactly identical across three counterfactual conditions that differ only in B's
non-speech reaction:

    context + proposal + [laughter]
    context + proposal + [sigh]
    context + proposal + [gasp]

For each, the scenario records what A should infer about B, the conversational function A's
next turn should perform, and a natural sentence realizing it. The benchmark then asks
whether a model's own next turn shifts the way the gold answers do.

The generation prompt lives in prompt_scenario.txt and is loaded verbatim at import — it is
not restated in this file, so editing the prompt never requires touching the code.

Generation is a writer call against that prompt followed by:
  1. mechanical validate() — shape, sound-naming leakage, distinctness, the generic-response
     blocklist the prompt itself calls out
  2. an LLM judge_scenario() — the prompt's own eight-point final quality check, run
     externally, including the permutation test that self-checking tends to wave through

Usage:
    python make_response/generate.py
    python make_response/generate.py --n 3 --verbose
    python make_response/generate.py --model gpt-4o
    python make_response/generate.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "scenarios.json"
PROMPT_PATH = HERE / "prompt_scenario.txt"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 6000
MAX_ATTEMPTS = 4

MAX_RESPONSE_WORDS = 34
MAX_INFERRED_STATE_WORDS = 45

VOC_ORDER = ["laughter", "sigh", "gasp"]

SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()


def supports_reasoning_effort(model: str) -> bool:
    """gpt-4o and other non-reasoning chat models reject the `reasoning` param outright."""
    return not re.match(r"^gpt-(4|3\.5)", model)


def output_schema() -> dict:
    """Mirrors the OUTPUT FORMAT block of the prompt exactly.

    `item_id` is deliberately absent — the script assigns ids itself so the prompt's
    declared structure stays untouched.
    """
    condition_schema = {
        "type": "object",
        "properties": {
            "inferred_state": {"type": "string"},
            "response_function": {"type": "string"},
            "response": {"type": "string"},
        },
        "required": ["inferred_state", "response_function", "response"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "relationship": {"type": "string"},
            "shared_context": {"type": "string"},
            "proposal": {"type": "string"},
            "reaction_affordances": {
                "type": "object",
                "properties": {voc: {"type": "string"} for voc in VOC_ORDER},
                "required": VOC_ORDER,
                "additionalProperties": False,
            },
            "laughter": condition_schema,
            "sigh": condition_schema,
            "gasp": condition_schema,
            "contrastive_rationale": {"type": "string"},
        },
        "required": [
            "domain", "relationship", "shared_context", "proposal",
            "reaction_affordances", "laughter", "sigh", "gasp", "contrastive_rationale",
        ],
        "additionalProperties": False,
    }


# ------------------------------------------------------------ mechanical validation

TAG_RE = re.compile(r"\[[^\[\]]*\]")

# the prompt's own BAD examples are "Why did you gasp?" and "I hear you sighing" — naming
# the reaction is banned in A's response, though it is expected in reaction_affordances
VOC_WORD_RE = re.compile(
    r"(?i)\b("
    r"gasp(?:s|ed|ing)?|laugh(?:s|ed|ing|ter)?|sigh(?:s|ed|ing)?|"
    r"chuckle(?:s|d)?|groan(?:s|ed|ing)?"
    r")\b"
)

# verbatim from the prompt's "avoid generic responses such as" list
GENERIC_RESPONSES = {
    "i know, it's a lot",
    "we can talk about it",
    "i understand",
    "let's think about it",
}

# the prompt's BAD CONTEXT example is a context that pre-announces B's stance
CONTEXT_GIVEAWAY_RE = re.compile(
    r"(?i)\bB (?:has always|would never|always|never|has repeatedly) (?:said|felt|insisted|"
    r"maintained|refused)\b|\bB (?:hates|loves|dreads|resents)\b"
)


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def canonical(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", normalize(text).lower()).strip()


def validate(payload: dict) -> list[str]:
    problems: list[str] = []

    for field, min_words in (
        ("domain", 1), ("relationship", 1), ("shared_context", 25), ("proposal", 4),
        ("contrastive_rationale", 15),
    ):
        text = normalize(payload.get(field) or "")
        if not text:
            problems.append(f"{field} is empty")
        elif len(text.split()) < min_words:
            problems.append(f"{field} is too thin")

    context = normalize(payload.get("shared_context") or "")
    if CONTEXT_GIVEAWAY_RE.search(context):
        problems.append(
            "shared_context states B's standing attitude, which makes B's reaction "
            "predictable (see the prompt's BAD CONTEXT example)"
        )
    if TAG_RE.search(context):
        problems.append("shared_context contains a bracketed tag")

    proposal = normalize(payload.get("proposal") or "")
    if TAG_RE.search(proposal):
        problems.append("proposal contains a bracketed tag")
    if VOC_WORD_RE.search(proposal):
        problems.append("proposal mentions a vocalization")

    affordances = payload.get("reaction_affordances") or {}
    for voc in VOC_ORDER:
        text = normalize(affordances.get(voc) or "")
        if len(text.split()) < 6:
            problems.append(f"reaction_affordances.{voc} is too thin to be a real affordance")

    responses: dict[str, str] = {}
    functions: dict[str, str] = {}

    for voc in VOC_ORDER:
        block = payload.get(voc) or {}
        state = normalize(block.get("inferred_state") or "")
        function = normalize(block.get("response_function") or "")
        response = normalize(block.get("response") or "")

        if not state:
            problems.append(f"{voc}.inferred_state is empty")
        else:
            if len(state.split()) > MAX_INFERRED_STATE_WORDS:
                problems.append(f"{voc}.inferred_state is too long")
            if not re.search(r"\bB\b", state):
                problems.append(f"{voc}.inferred_state should say what B appears to think")

        if not function:
            problems.append(f"{voc}.response_function is empty")
        else:
            functions[voc] = canonical(function)

        if not response:
            problems.append(f"{voc}.response is empty")
        else:
            responses[voc] = response
            if TAG_RE.search(response):
                problems.append(f"{voc}.response contains a bracketed tag")
            if VOC_WORD_RE.search(response):
                problems.append(
                    f"{voc}.response names B's vocalization, which the prompt forbids"
                )
            if len(response.split()) > MAX_RESPONSE_WORDS:
                problems.append(f"{voc}.response is longer than one short sentence")
            if canonical(response) in GENERIC_RESPONSES:
                problems.append(
                    f"{voc}.response is on the prompt's list of responses to avoid"
                )

    for label, values in (("response", responses), ("response_function", functions)):
        seen: dict[str, str] = {}
        for voc, value in values.items():
            key = canonical(value)
            if key in seen:
                problems.append(f"{voc}.{label} duplicates {seen[key]}.{label}")
            else:
                seen[key] = voc

    return problems


# --------------------------------------------------------------------- the verifier

# the prompt's FINAL QUALITY CHECK, as eight independently judged conditions
JUDGE_PROPERTIES = [
    ("supports_all_three",
     "the same context and proposal do not plausibly support all three of laughter, sigh "
     "and gasp"),
    ("context_does_not_reveal_reaction",
     "the context already reveals which reaction B will have"),
    ("inferred_states_distinct",
     "the three inferred states are not pragmatically distinct"),
    ("response_functions_distinct",
     "the three response functions are not meaningfully different"),
    ("responses_realize_functions",
     "at least one response does not clearly realize its intended response function"),
    ("intended_matching_clearly_best",
     "the intended three-way matching is not clearly more natural than some other "
     "permutation of the three responses"),
    ("no_response_too_generic",
     "at least one response is generic enough to fit all three reactions equally well"),
    ("sounds_natural",
     "the dialogue or responses do not sound like natural human conversation"),
]

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{key: {"type": "boolean"} for key, _ in JUDGE_PROPERTIES},
        "best_permutation": {
            "type": "string",
            "enum": ["intended", "laughter-gasp-swap", "laughter-sigh-swap",
                     "sigh-gasp-swap", "other"],
        },
        "weakest_condition": {"type": "string", "enum": VOC_ORDER + ["none"]},
        "overall": {"type": "string", "enum": ["PASS", "FAIL"]},
        "reason": {"type": "string"},
    },
    "required": [key for key, _ in JUDGE_PROPERTIES]
    + ["best_permutation", "weakest_condition", "overall", "reason"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """
You are a strict, independent verifier for a counterfactual vocalization benchmark.

You receive one scenario: a shared context, Speaker A's proposal, and three conditions
keyed laughter / sigh / gasp. The context and proposal are identical across all three; only
B's non-speech reaction differs. Each condition carries an `inferred_state` (what A should
infer about B), a `response_function` (the conversational action A should take), and a
`response` (what A actually says).

Judge these eight conditions, each independently.

1. supports_all_three
   Could a real person plausibly react to this proposal, in this context, with laughter, or
   with a sigh, or with a gasp? Check all three. FAIL if any one would be odd here.

2. context_does_not_reveal_reaction
   Does the context leave B's reaction genuinely open? FAIL if it states or strongly implies
   B's standing attitude, so that one reaction is already the obvious one.

3. inferred_states_distinct
   Are the three inferred states pragmatically distinct readings of B — not three wordings
   of the same state?

4. response_functions_distinct
   Are the three response functions meaningfully different conversational actions? FAIL if
   two amount to the same move.

5. responses_realize_functions
   Does each response actually perform the function claimed for it? FAIL if a response is
   labelled "acknowledge reluctance" but in fact defends the proposal, and so on.

6. intended_matching_clearly_best
   This is the central test. Consider reassigning the three responses to the three
   vocalizations. Is the intended assignment — laughter response to laughter, sigh to sigh,
   gasp to gasp — clearly the most natural overall assignment?

   Do NOT require a response to be impossible after the other reactions; natural dialogue
   overlaps. Ask only whether the intended one-to-one matching is substantially better than
   the alternatives. Report which assignment reads best in `best_permutation`: "intended" if
   the intended matching wins, otherwise the swap that beats it.

7. no_response_too_generic
   Is any response bland enough to sit equally well after all three reactions? Responses of
   the form "I know, it's a lot", "we can talk about it", "I understand", "let's think about
   it" fail this.

8. sounds_natural
   Do the context, proposal and all three responses read like real speech rather than
   written-up prose or a template?

Report the shakiest of the three conditions in `weakest_condition`, or "none".

Return PASS only if all eight conditions pass. Otherwise FAIL.

Be strict. The usual failure is condition 6: the three responses are individually fine but
two of them could trade places without loss. Give `reason` as one concise sentence naming
the single most important problem, or what carries the scenario if it passes.

Do not rewrite or repair the scenario. Only verify it.
""".strip()


def judge_scenario(client: OpenAI, payload: dict, model: str, effort: str) -> tuple[dict, dict]:
    item = {
        "shared_context": payload["shared_context"],
        "proposal": payload["proposal"],
        **{
            voc: {
                "inferred_state": payload[voc]["inferred_state"],
                "response_function": payload[voc]["response_function"],
                "response": payload[voc]["response"],
            }
            for voc in VOC_ORDER
        },
    }
    kwargs = dict(
        model=model,
        instructions=JUDGE_SYSTEM,
        input=json.dumps(item, ensure_ascii=False, indent=2),
        text={
            "format": {
                "type": "json_schema",
                "name": "make_response_scenario_judge",
                "schema": JUDGE_SCHEMA,
                "strict": True,
            }
        },
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    if supports_reasoning_effort(model):
        kwargs["reasoning"] = {"effort": effort}
    response = client.responses.create(**kwargs)
    if response.status != "completed":
        raise RuntimeError(f"judge status={response.status}")
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return json.loads(response.output_text), usage


def judge_problems(verdict: dict) -> list[str]:
    problems = [message for key, message in JUDGE_PROPERTIES if not verdict.get(key)]
    permutation = verdict.get("best_permutation")
    if permutation and permutation != "intended" and not any("permutation" in p for p in problems):
        problems.append(f"a different assignment reads better than the intended one: {permutation}")
    # weakest_condition is diagnostic; it only signals a failure when condition 1 failed
    if not verdict.get("supports_all_three"):
        weakest = verdict.get("weakest_condition")
        if weakest and weakest != "none":
            problems.append(f"[{weakest}] does not fit this context and proposal")
    if not problems and verdict.get("overall") == "FAIL":
        problems.append(verdict.get("reason") or "judge returned overall FAIL")
    return problems


# ------------------------------------------------------------------------- plumbing

def user_prompt(used: list[dict]) -> str:
    lines = ["Generate exactly one scenario."]
    if used:
        lines += [
            "",
            "Scenarios already generated — vary the domain, relationship, stakes and "
            "proposal type, and do not repeat these situations:",
        ]
        for record in used[-10:]:
            lines.append(
                f"- {record.get('domain')} / {record.get('relationship')}: "
                f"{record.get('proposal')}"
            )
    return "\n".join(lines)


def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "make_response_scenario",
                        "schema": output_schema(),
                        "strict": True,
                    }
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if supports_reasoning_effort(model):
                kwargs["reasoning"] = {"effort": effort}
            response = client.responses.create(**kwargs)
            if response.status != "completed":
                raise RuntimeError(
                    f"status={response.status} "
                    f"details={getattr(response, 'incomplete_details', None)}"
                )
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return json.loads(response.output_text), usage, response.model
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            wait = 2 ** attempt
            print(f"    retry in {wait}s: {exc}", flush=True)
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


class GenerationFailed(RuntimeError):
    def __init__(self, message: str, draft: dict | None, problems: list[str], judge: dict | None):
        super().__init__(message)
        self.draft = draft
        self.problems = problems
        self.judge = judge


def print_draft(payload: dict) -> None:
    print(f"      context: {payload.get('shared_context')}", flush=True)
    print(f"      A proposes: {payload.get('proposal')}", flush=True)
    for voc in VOC_ORDER:
        block = payload.get(voc) or {}
        print(f"      [{voc}] {block.get('inferred_state')}", flush=True)
        print(f"         fn: {block.get('response_function')}", flush=True)
        print(f"         A: {block.get('response')}", flush=True)


def generate_one(
    client: OpenAI, item_id: str, args: argparse.Namespace, used: list[dict]
) -> dict:
    verbose = getattr(args, "verbose", False)
    prompt = user_prompt(used)
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    last_draft: dict | None = None
    last_verdict: dict | None = None
    served_by = args.model

    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        last_draft = payload

        problems = validate(payload)
        verdict: dict | None = None
        if not problems and not args.no_judge:
            verdict, judge_usage = judge_scenario(client, payload, args.model, args.effort)
            totals["input_tokens"] += judge_usage["input_tokens"]
            totals["output_tokens"] += judge_usage["output_tokens"]
            problems = judge_problems(verdict)
        last_verdict = verdict

        if verbose:
            print(f"    -- attempt {attempt}/{MAX_ATTEMPTS} --", flush=True)
            print_draft(payload)

        if not problems:
            payload["item_id"] = item_id
            payload["vocalizations"] = VOC_ORDER
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            if verdict is not None:
                payload["judge"] = verdict
            if verbose:
                print("      accepted", flush=True)
            return payload

        last_problems = problems
        if verbose:
            print(f"      rejected: {problems}", flush=True)
            if verdict is not None:
                print(f"      judge: {verdict}", flush=True)
        else:
            print(
                f"    rejected ({problems[0][:74]}); attempt {attempt}/{MAX_ATTEMPTS}",
                flush=True,
            )
        prompt = user_prompt(used) + (
            "\n\nThe previous attempt failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nIf the problem is that two responses could trade places, push their "
            "conversational functions further apart. If the problem is that a reaction "
            "does not fit, rebuild the scenario so all three affordances are present."
            "\nReturn a corrected scenario."
        )

    raise GenerationFailed(
        "still invalid after retries: " + "; ".join(last_problems),
        draft=last_draft, problems=last_problems, judge=last_verdict,
    )


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# make_response — counterfactual laughter / sigh / gasp scenarios",
        "",
        f"writer: {model} · {len(records)} scenario(s) · "
        f"{len(records) * len(VOC_ORDER)} test conditions",
        "",
        "The tested model plays Speaker A. Context and proposal are identical across the",
        "three conditions of a scenario; only B's non-speech reaction changes. What is",
        "recorded per condition is what A should infer, the function A's next turn should",
        "perform, and a natural sentence realizing it.",
        "",
    ]
    for record in records:
        lines += [
            f"## {record['item_id']} — {record.get('domain')}",
            "",
            f"**Relationship:** {record.get('relationship')}",
            "",
            f"**Shared context:** {record.get('shared_context')}",
            "",
            f"**A proposes:** {record.get('proposal')}",
            "",
            "**Affordances**",
            "",
        ]
        affordances = record.get("reaction_affordances") or {}
        for voc in VOC_ORDER:
            lines.append(f"- *{voc}:* {affordances.get(voc)}")
        lines.append("")
        for voc in VOC_ORDER:
            block = record[voc]
            lines += [
                f"### B: [{voc}]",
                "",
                f"- **A infers:** {block['inferred_state']}",
                f"- **Response function:** {block['response_function']}",
                f"- **A says:** {block['response']}",
                "",
            ]
        lines += [f"*Contrastive rationale:* {record.get('contrastive_rationale')}", ""]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort", default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--n", type=int, default=3, help="scenarios to generate")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    print(
        f"{args.n} scenario(s) x {len(VOC_ORDER)} conditions = "
        f"{args.n * len(VOC_ORDER)} test items  ·  model {args.model}",
        flush=True,
    )

    if args.dry_run:
        print("\n" + "=" * 72)
        print(f"SYSTEM PROMPT (from {PROMPT_PATH.name}, {len(SYSTEM_PROMPT)} chars)")
        print("=" * 72)
        print(SYSTEM_PROMPT)
        print("\n" + "=" * 72)
        print("USER MESSAGE")
        print("=" * 72)
        print(user_prompt([]))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)
    print(
        f"prompt: {PROMPT_PATH.name}"
        + ("  (judge off)" if args.no_judge else "  (+ 8-point verifier)"),
        flush=True,
    )

    records: list[dict] = []
    accepted: list[dict] = []

    for index in range(1, args.n + 1):
        item_id = f"scenario_{index:03d}"
        print(f"\n[{index}/{args.n}] {item_id}", flush=True)
        try:
            record = generate_one(client, item_id, args, accepted)
            records.append(record)
            accepted.append(record)
            print(f"    domain: {record['domain']}  ({record['relationship']})", flush=True)
            print(f"    A proposes: {record['proposal']}", flush=True)
            for voc in VOC_ORDER:
                print(
                    f"      [{voc}]  {record[voc]['response_function']}\n"
                    f"        A: {record[voc]['response']}",
                    flush=True,
                )
        except GenerationFailed as exc:
            failed = {
                "item_id": item_id,
                "error": f"{type(exc).__name__}: {exc}",
                "last_problems": exc.problems,
            }
            if exc.draft is not None:
                failed["last_draft"] = exc.draft
            if exc.judge is not None:
                failed["last_judge"] = exc.judge
            records.append(failed)
            print(f"    failed: {exc}", flush=True)
            if exc.draft is not None:
                print("    last draft:", flush=True)
                print_draft(exc.draft)
        except Exception as exc:
            records.append({"item_id": item_id, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    failed: {exc}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "model": args.model,
                "effort": args.effort,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "prompt_file": PROMPT_PATH.name,
                "vocalizations": VOC_ORDER,
                "judged": not args.no_judge,
                "structure": (
                    "the tested model plays Speaker A; shared_context and proposal are "
                    "identical across the three conditions and only B's vocalization "
                    "changes; each condition carries inferred_state, response_function and "
                    "a gold response for A"
                ),
                "results": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    md_path = args.out.with_suffix(".md")
    ok = [r for r in records if "proposal" in r]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for r in records if r.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

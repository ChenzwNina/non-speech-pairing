"""Generate short lexical transcripts for laughter-function pairs.

Each transcript must create one natural conversational event in which a later
laugh from the final speaker can plausibly receive either of two target pragmatic
analyses. The generator is provider-agnostic; MODEL selects the backend.

USER_PROMPT_TEMPLATE is rendered with fields from `prompt_fields()`. Structural
profiles and pair-specific conditions are appended when they are not already
referenced explicitly in the template.

Usage:
    python generate_transcripts.py                       # all topics, all pairs
    python generate_transcripts.py --dry-run             # print prompts, no API calls
    python generate_transcripts.py --limit 3             # first 3 combinations
    python generate_transcripts.py --out runs/v1.json    # custom output path
"""

import argparse
import csv
import itertools
import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

# Single source of truth for what a well-formed transcript looks like: the
# verifier's Stage 0. Importing it means the writer and the checker can never
# drift apart.
from verifier import check_format

load_dotenv()  # reads OPENAI_API_KEY / ANTHROPIC_API_KEY from .env

# --- prompts -----------------------------------------------------------------

SYSTEM_PROMPT = """
You are an expert in natural spoken dialogue and the pragmatics of laughter.

TASK
Generate ONE four-turn spoken dialogue in which a laugh added to the FINAL turn
could plausibly perform either of the TWO laughter functions supplied by the user.
Generate only the lexical transcript: do not write laughter, prosody, tone labels,
stage directions, or acoustic descriptions.

The goal is NOT to make the dialogue vague. The goal is to build one concrete,
natural conversational event that supplies the prerequisites for BOTH functions.
The words may contain mild criticism, irony-capable wording, hesitation, a request,
an awkward admission, or another function-relevant cue when a target function
requires it.

PRIORITY ORDER
When instructions pull in different directions, use this order:
1. BOTH target-function preconditions must genuinely be satisfied.
2. The pair-specific condition, if supplied, must be satisfied.
3. The dialogue must sound like ordinary human conversation and make common sense.
4. The final turn must provide usable evidence for BOTH readings without making
   either reading overwhelmingly more natural.
5. Keep the dialogue concise and follow the required output format.

PAIR CONSTRUCTION
Before writing, reason internally about the pair. Do not output this reasoning.

A. Find the overlap.
Identify one conversational event that can simultaneously satisfy both functions'
preconditions. If no such event exists, choose the closest genuinely plausible
configuration allowed by the supplied pair condition; do not fake compatibility
by making the wording empty or generic.

B. Respect participant roles.
Use each structural profile's laugher role and laughable origin.
- If both functions require the final speaker to be the producer, make the final
  speaker's own contribution supply the relevant act.
- If one function is responsive to the partner while the other attaches to the
  final speaker's own contribution, design the final turn to do both: respond to
  the partner AND contribute the relevant material itself.

C. Preserve necessary lexical hooks.
If a target function needs a lexical hook, the transcript MUST make that hook
available. Do not remove a required cue merely to create ambiguity.
Examples of legitimate cues include:
- a mild criticism or disagreement for softening;
- a suggestion, opinion, or favor for benevolence induction;
- a socially awkward moment for smoothing;
- a partner's vulnerable or awkward display for sympathy;
- wording that can be read nonliterally for irony;
- one expression with a nonstandard/enriched sense for scare-quoting;
- hesitation, hedge, repair, or questionable word choice for lexical editing;
- a detectable clash with background expectations for incongruity functions.

D. Make the cues overlap when possible.
The best transcript uses the SAME piece of wording or the SAME event as evidence
for both functions. For example, a mildly critical remark may also formulate an
absurd reversal; an uncertain adjective may also soften a negative evaluation.
Avoid constructing two unrelated mini-events, one for each function.

FINAL-TURN DESIGN
The fourth turn is where laughter will later be inserted.

Prefer a final turn that is:
- short and spoken-like;
- specific rather than generic;
- responsive to the immediately preceding turn;
- rich enough to support both target readings;
- plausible with a small or medium laugh added naturally.

Do NOT impose blanket neutrality. A final turn may contain criticism, evaluation,
irony-capable wording, disagreement, hesitation, a request, or another delicate
act when the target functions require it.

However, avoid wording that lexicalizes ONLY ONE function so strongly that the
other becomes implausible. In particular, avoid:
- a fully explicit joke whose only reasonable uptake is amusement;
- a direct insult or harsh criticism when a pleasant reading is also required;
- an explicit statement such as "I'm joking", "I'm being sarcastic", "don't be
  offended", or "I feel sorry for you";
- explaining the pragmatic stance instead of letting laughter contribute it;
- contrived wordplay or theatrical punchlines that people would not normally say.

BALANCE PRINCIPLE
Lexical evidence for a function is GOOD when that function requires it.
Reject a cue only when it supports one target function at the expense of the
other.

The desired ambiguity is:
    "What is the laughter doing here?"
not:
    "What is this utterance doing at all?"

The lexical transcript may make the underlying social action visible. What should
remain open is which target function best describes the later laughter's
contribution to that action.

NATURALNESS
Use an everyday situation appropriate to the requested topic. The dialogue should
sound like something two people might actually say without knowing they are in an
experiment.

Avoid:
- exposition inserted only to satisfy a definition;
- unnatural vagueness such as "That's something" or "So that's that";
- overly polished one-liners;
- repeating the function definitions in conversational wording;
- obscure scenarios requiring special knowledge.

DIALOGUE STRUCTURE
- Exactly two speakers: A and B.
- Exactly four turns: A -> B -> A -> B.
- The first three turns are dialogue history.
- The fourth B turn is the current turn where laughter will later be inserted.
- One sentence per turn.
- Keep each turn concise and spoken-like.
- Lexical content only: no laughter tags, brackets, stage directions, tone labels,
  or prosodic descriptions.

USE OF DEFINITIONS, EXAMPLES, PROFILES, AND PAIR CONDITION
- Definitions specify what each function must mean in this task.
- Examples illustrate the mechanism; do NOT copy their scenario or wording.
- Structural-profile PRECONDITIONS are hard requirements whenever compatible.
- The pair-specific condition is a direct design requirement for this pair and
  takes precedence over generic stylistic preferences.
- "Likely next move" is diagnostic context, not a hard requirement: two different
  laughter functions may still permit the same next spoken response.

MANDATORY INTERNAL CHECKS
Before returning the transcript, check all of the following. Do not output the
checks.

1. DUAL-PRECONDITION TEST
Point to the exact event/wording that satisfies Function 1's precondition and the
exact event/wording that satisfies Function 2's precondition. If either is absent,
rewrite the dialogue.

2. PAIR-CONDITION TEST
If a pair-specific condition was supplied, does the transcript instantiate it
literally rather than merely approximately? If not, rewrite it.

3. DUAL-EVIDENCE TEST
Can you identify positive lexical/contextual evidence for BOTH target readings?
"Nothing rules it out" is not enough. Each function needs an affirmative reason.

4. DOMINANCE TEST
After imagining laughter in the final turn, would a reasonable analyst regard one
function as clearly natural and the other as strained? If yes, rewrite it. Mild
asymmetry is acceptable; one reading being merely technically possible is not.

5. SHARED-LOCUS TEST
Whenever possible, do both readings attach to the same phrase/event in the final
turn or its immediate context? If they depend on unrelated parts of the dialogue,
rewrite toward a tighter overlap.

6. NATURALNESS TEST
Would two people plausibly say these exact four sentences in ordinary speech? If
not, simplify or rewrite.

7. LAUGH-PLACEMENT TEST
Could a laugh occur naturally within or immediately after the final turn without
changing its words? If not, rewrite it.

Return only a candidate that passes all seven checks.

OUTPUT FORMAT
Return ONLY one valid JSON object:

{
  "prior_turns": [
    {"speaker": "A", "text": "..."},
    {"speaker": "B", "text": "..."},
    {"speaker": "A", "text": "..."}
  ],
  "current_turn": {
    "speaker": "B",
    "text": "..."
  }
}

The dialogue is exactly four turns in total.
- `prior_turns` contains exactly the first three turns: A, then B, then A.
- `current_turn` contains only the fourth turn: B.
- Do not duplicate the fourth turn in `prior_turns`.
- Do not return markdown or explanation.
"""

USER_PROMPT_TEMPLATE = """
[dialogue topic]: {topic}

[laughter function 1]
Function name: {function_a}
Definition: {definition_a}
Example: {example_a}
Example explanation: {example_explanation_a}

[laughter function 2]
Function name: {function_b}
Definition: {definition_b}
Example: {example_b}
Example explanation: {example_explanation_b}

Generate ONE short, natural spoken dialogue for this topic in which laughter added
to B's final turn can plausibly be analyzed as either function.

Do not make the transcript neutral merely for the sake of ambiguity. Build the
specific conversational conditions that both definitions require, and let the
same final-turn wording carry evidence for both readings.
"""

# --- config ------------------------------------------------------------------

# Either provider may write the transcripts; the prompt is identical, so runs
# are directly comparable. Anything starting "claude-" goes to Anthropic,
# anything starting "gpt-" or "o" to OpenAI.
MODEL = "gpt-5.6-sol"
EFFORT = "high"
MAX_TOKENS = 8000
CSV_PATH = Path("laughter_definitions.csv")
PROFILES_PATH = Path("function_profiles_compact.csv")

# Per-pair conditions are off by default: the explicit TARGET_PAIRS list below
# now does the pair selection, and the compact profiles carry the design
# guidance. Pass --conditions pair_conditions.csv to bring them back.
CONDITIONS_PATH = None

# Fields from function_profiles_compact.csv shown to the writer, in this order.
PROFILE_FIELDS = [
    "laugher_role", "event_initiator", "event_focus", "trigger_event",
    "laughter_action", "lexical_anchor",
]

# The contrastive pairs to generate. Every pair is one of the two incongruity
# functions crossed with a partner whose social action differs from it. Names
# must match the `function` column of laughter_definitions.csv exactly. Empty
# this list (or pass --all-combinations) to sweep every pair instead.
TARGET_PAIRS = [
    ("Show enjoyment of incongruity", "Marking irony"),
    ("Show enjoyment of incongruity", "Smoothing"),
    ("Show enjoyment of incongruity", "Benevolence induction"),
    ("Show enjoyment of incongruity", "Show sympathy"),
    ("Show enjoyment of incongruity", "Softening / trouble-telling"),
    ("Show enjoyment of incongruity", "Scare-quoting / invite enrichment"),
    ("Show enjoyment of incongruity", "Lexical uncertainty / editing phrase"),
    ("Marking irony", "Show sympathy"),
    ("Marking irony", "Benevolence induction"),
    ("Marking irony", "Smoothing"),
    ("Marking irony", "Softening / trouble-telling"),
    ("Marking irony", "Lexical uncertainty / editing phrase"),
    ("Marking irony", "Scare-quoting / invite enrichment"),
]

# Appended when the template has no {profile_a_block} of its own.
PROFILE_BLOCK = """

    [laughter function 1 - structural profile]
    {profile_a_block}

    [laughter function 2 - structural profile]
    {profile_b_block}
"""

# Appended to the user prompt when the template has no {pair_condition}
# placeholder of its own. Move it into USER_PROMPT_TEMPLATE if you want it
# somewhere else in the prompt.
PAIR_CONDITION_BLOCK = """

    [What this pair needs]
    {pair_condition}
"""
DEFAULT_OUT = Path("transcripts.json")

# Server-side refusal fallback: on a policy decline, Anthropic re-runs the
# request on a fallback model instead of returning the refusal.
BETAS = ["server-side-fallback-2026-07-01"]

# Matches the [Output format] block in SYSTEM_PROMPT. Enforced by the API, so
# transcript_json is always populated for a successful call.
TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "prior_turns": {
            "type": "array",
            "description": "Exactly 3 turns of dialogue history.",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["A", "B"]},
                    "text": {"type": "string"},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        },
        "current_turn": {
            "type": "object",
            "description": "The single turn where laughter will be inserted later.",
            "properties": {
                "speaker": {"type": "string", "enum": ["A", "B"]},
                "text": {"type": "string"},
            },
            "required": ["speaker", "text"],
            "additionalProperties": False,
        },
    },
    "required": ["prior_turns", "current_turn"],
    "additionalProperties": False,
}

TOPICS = [
    "domestic",
    "school",
]

# combinations         -> unordered pairs of two distinct functions (45 for 10 rows)
# permutations         -> ordered pairs of two distinct functions (90)
# combinations_with_replacement -> unordered, same function allowed twice (55)
PAIR_MODE = "combinations"

# How many times to re-generate a candidate whose reply violates the transcript
# format. The JSON schema pins the shape of each turn but cannot pin the NUMBER
# of prior turns (Anthropic structured outputs do not support minItems), so the
# writer can drift - this catches that before it reaches the verifier.
# Candidates generated concurrently. The calls are independent; this is the
# difference between a 20-minute run over 45 pairs and a 4-minute one.
WORKERS = 6

# Candidates per (pair, topic). One attempt each by default; raise it only when
# you have a filter to choose between the attempts.
SAMPLES = 1

MAX_FORMAT_ATTEMPTS = 3

# Appended to the user prompt on a retry, so the model is told what went wrong.
FORMAT_RETRY_NOTE = """

Your previous reply did not follow the required output format: {problem}
Return a corrected version: exactly 3 turns in "prior_turns", one distinct
"current_turn" that does not repeat the last prior turn, and nothing else.
"""

MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0


def load_functions(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [
            {k: (v or "").strip() for k, v in row.items() if k}
            for row in csv.DictReader(f)
        ]
    if not rows:
        raise SystemExit(f"{path} has no rows")
    return rows


def slug(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def make_pairs(functions, mode):
    pairer = {
        "combinations": itertools.combinations,
        "permutations": itertools.permutations,
        "combinations_with_replacement": itertools.combinations_with_replacement,
    }[mode]
    return list(pairer(functions, 2))


def describe(fn, label):
    return (
        f"[Laughter function {label}]\n"
        f"Name: {fn['function']}\n"
        f"Laughable type: {fn['laughable_type']}\n"
        f"Definition: {fn['definition']}\n"
        f"Example: {fn['example']}\n"
        f"Example explanation: {fn['example_explanation']}"
    )


def load_pair_conditions(path):
    """The reviewed conditions from pair_conditions.py, keyed by function pair."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            (row["function_1"], row["function_2"]): row
            for row in csv.DictReader(f)
            if row.get("function_1") and row.get("function_2")
        }


def load_function_profiles(path):
    """The reviewed structural profiles from function_profiles.py, keyed by function."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row["function"]: row for row in csv.DictReader(f) if row.get("function")}


def describe_profile(profile):
    """One function's profile as labelled lines, skipping fields left blank."""
    if not profile:
        return ""
    lines = []
    for field in PROFILE_FIELDS:
        value = (profile.get(field) or "").strip()
        if value:
            lines.append(f"{field.replace('_', ' ')}: {value}")
    # Indent continuation lines so the block sits flush inside the prompt.
    return "\n    ".join(lines)


def prompt_fields(topic, fn_a, fn_b, condition="", profiles=None):
    """Every field available to USER_PROMPT_TEMPLATE as a {placeholder}."""
    profiles = profiles or {}
    fields = {"topic": topic}
    for label, fn in (("a", fn_a), ("b", fn_b)):
        fields[f"function_{label}"] = fn["function"]
        fields[f"laughable_type_{label}"] = fn["laughable_type"]
        fields[f"definition_{label}"] = fn["definition"]
        fields[f"example_{label}"] = fn["example"]
        fields[f"example_explanation_{label}"] = fn["example_explanation"]
        profile = profiles.get(fn["function"], {})
        for field in PROFILE_FIELDS:
            fields[f"{field}_{label}"] = (profile.get(field) or "").strip()
        fields[f"profile_{label}_block"] = describe_profile(profile)
    fields["function_a_block"] = describe(fn_a, "A")
    fields["function_b_block"] = describe(fn_b, "B")
    fields["pair_condition"] = condition
    return fields


def build_user_prompt(topic, fn_a, fn_b, condition="", profiles=None):
    """Build the pair prompt without dropping pair-specific information.

    Structural profiles and pair conditions are independent sources of guidance.
    If both exist, both are supplied unless USER_PROMPT_TEMPLATE already references
    the corresponding placeholders explicitly.
    """
    fields = prompt_fields(topic, fn_a, fn_b, condition, profiles)
    has_profiles = bool(fields.get("profile_a_block") or fields.get("profile_b_block"))
    has_placeholder = any(f"{{{key}}}" in USER_PROMPT_TEMPLATE for key in fields)

    if has_placeholder:
        prompt = USER_PROMPT_TEMPLATE.format(**fields)
    else:
        context = "\n\n".join(
            [f"Topic: {topic}", fields["function_a_block"], fields["function_b_block"]]
        )
        prompt = f"{USER_PROMPT_TEMPLATE}\n\n{context}".strip()

    if has_profiles and "{profile_a_block}" not in USER_PROMPT_TEMPLATE:
        prompt += PROFILE_BLOCK.format(
            profile_a_block=fields["profile_a_block"],
            profile_b_block=fields["profile_b_block"],
        )

    if condition and "{pair_condition}" not in USER_PROMPT_TEMPLATE:
        prompt += PAIR_CONDITION_BLOCK.format(pair_condition=condition)

    return prompt


def match_pair(fn_a, fn_b, patterns):
    """True when a "left|right" pattern matches both function names, either order."""
    if not patterns:
        return True
    names = (fn_a["function"].lower(), fn_b["function"].lower())
    for pattern in patterns:
        left, _, right = pattern.lower().partition("|")
        left, right = left.strip(), right.strip()
        if not right:
            if any(left in n for n in names):
                return True
            continue
        if ((left in names[0] and right in names[1])
                or (left in names[1] and right in names[0])):
            return True
    return False


def build_jobs(functions, topics, pair_mode, conditions=None, all_pairs=False,
               profiles=None, pair_patterns=None, samples=1, target_pairs=None):
    conditions = conditions or {}
    profiles = profiles or {}
    # Order-insensitive lookup of the wanted pairs.
    wanted = {frozenset(p) for p in (target_pairs or [])}
    jobs, skipped = [], []
    for topic in topics:
        for fn_a, fn_b in make_pairs(functions, pair_mode):
            if wanted and frozenset((fn_a["function"], fn_b["function"])) not in wanted:
                continue
            if not match_pair(fn_a, fn_b, pair_patterns):
                continue
            row = conditions.get((fn_a["function"], fn_b["function"]), {})
            viability = (row.get("viability") or "").strip().lower()
            # An explicitly requested pair is never skipped for viability.
            if viability == "impossible" and not all_pairs and not wanted:
                skipped.append(f"{fn_a['function']} x {fn_b['function']}")
                continue
            condition = (row.get("condition") or "").strip()
            base_id = f"{slug(topic)}__{slug(fn_a['function'])}__{slug(fn_b['function'])}"
            prompt = build_user_prompt(topic, fn_a, fn_b, condition, profiles)
            # Best-of-N: the same prompt sampled `samples` times. Ids stay distinct
            # so resume and the verifier can tell the attempts apart.
            for n in range(1, samples + 1):
                jobs.append(
                    {
                        "id": base_id if samples == 1 else f"{base_id}__s{n}",
                        "pair_id": base_id,
                        "sample": n,
                        "topic": topic,
                        "laughter_functions": [fn_a, fn_b],
                        "pair_condition": condition,
                        "pair_viability": viability,
                        "user_prompt": prompt,
                    }
                )
    return jobs, skipped


def provider_for(model):
    return "anthropic" if model.startswith("claude") else "openai"


def make_client(model):
    """Client plus the key it needs, chosen by the model name."""
    if provider_for(model) == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is empty - set it in .env")
        return anthropic.Anthropic(api_key=key)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty - set it in .env")
    return OpenAI(api_key=key)


def call_openai(client, user_prompt, model, effort, max_tokens):
    """One transcript via the Responses API. Returns (text, usage, served_by)."""
    # The Responses API tops out at "high"; Anthropic's extra tiers map onto it.
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                reasoning={"effort": effort},
                text={"format": {"type": "json_schema", "name": "transcript",
                                 "schema": TRANSCRIPT_SCHEMA, "strict": True}},
                max_output_tokens=max_tokens,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"response status {response.status} "
                    f"({getattr(response, 'incomplete_details', None)}) "
                    "- raise --max-tokens"
                )
            usage = response.usage
            return response.output_text, {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }, response.model
        except Exception as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"    retry {attempt + 1}/{MAX_RETRIES - 1} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise last_error


def call_model(client, user_prompt, model, effort, max_tokens, use_fallbacks=True):
    """One transcript, from whichever provider owns this model."""
    if provider_for(model) == "openai":
        return call_openai(client, user_prompt, model, effort, max_tokens)
    return call_anthropic(client, user_prompt, model, effort, max_tokens, use_fallbacks)


def call_anthropic(client, user_prompt, model, effort, max_tokens, use_fallbacks=True):
    """One transcript. Returns (text, usage dict, model that served it)."""
    body = {
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": TRANSCRIPT_SCHEMA},
        }
    }
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_prompt}],
        # Thinking is on by default on Opus 5; stated explicitly so it is visible.
        # max_tokens caps thinking + response text together.
        "thinking": {"type": "adaptive"},
        "extra_body": body,
    }
    if SYSTEM_PROMPT.strip():
        kwargs["system"] = SYSTEM_PROMPT
    if use_fallbacks:
        kwargs["betas"] = BETAS
        body["fallbacks"] = "default"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.beta.messages.create(**kwargs)

            # Check stop_reason before touching content: a refusal returns HTTP 200
            # with empty or partial content, and max_tokens truncates the JSON.
            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                raise RuntimeError(f"model declined the request (category={category})")
            if response.stop_reason == "max_tokens":
                raise RuntimeError("hit max_tokens before finishing the JSON "
                                   "- raise --max-tokens")

            text = next((b.text for b in response.content if b.type == "text"), None)
            if text is None:
                raise RuntimeError(f"no text block (stop_reason={response.stop_reason})")

            usage = response.usage
            return text, {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }, response.model

        except anthropic.BadRequestError as exc:
            # If this org/SDK can't use server-side fallbacks, drop them and keep
            # going rather than failing the whole run.
            if use_fallbacks and "fallback" in str(exc).lower():
                print("    server-side fallbacks unavailable; retrying without them")
                use_fallbacks = False
                kwargs.pop("betas", None)
                body.pop("fallbacks", None)
                continue
            raise
        except (anthropic.RateLimitError, anthropic.APIConnectionError,
                anthropic.InternalServerError, RuntimeError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            delay = RETRY_BASE_DELAY * (2**attempt)
            print(f"    retry {attempt + 1}/{MAX_RETRIES - 1} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise last_error


def repair_transcript(parsed):
    """Fix the one malformation that has an unambiguous reading.

    The writer sometimes emits all four turns in `prior_turns` AND repeats the
    fourth as `current_turn`. That is the same turn written twice, so dropping
    the duplicate is safe. A `prior_turns` of four DISTINCT turns is a genuine
    five-turn dialogue and is left alone - discarding a turn there would orphan
    the content the current turn refers back to.
    """
    if not isinstance(parsed, dict):
        return parsed, False
    prior = parsed.get("prior_turns")
    current = parsed.get("current_turn")
    if (isinstance(prior, list) and len(prior) == 4 and isinstance(current, dict)
            and isinstance(prior[-1], dict)
            and prior[-1].get("text") == current.get("text")
            and prior[-1].get("speaker") == current.get("speaker")):
        return {**parsed, "prior_turns": prior[:3]}, True
    return parsed, False


def generate_transcript(client, user_prompt, args):
    """Generate a candidate, re-generating while the reply breaks the format.

    Returns (text, parsed, usage, served_by, problems, attempts). `problems` is
    empty when the transcript is well formed; if every attempt fails it holds the
    last set of problems so the caller can record the failure rather than hide it.
    """
    totals = {"input_tokens": 0, "output_tokens": 0}
    prompt = user_prompt
    result = None

    for attempt in range(1, MAX_FORMAT_ATTEMPTS + 1):
        text, usage, served_by = call_model(client, prompt, args.model,
                                            args.effort, args.max_tokens)
        for k in totals:
            totals[k] += usage[k]

        parsed, repaired = maybe_json(text), False
        parsed, repaired = repair_transcript(parsed)
        problems = check_format({"transcript_json": parsed})
        result = (text, parsed, dict(totals), served_by, problems, attempt, repaired)
        if not problems:
            return result

        if attempt < MAX_FORMAT_ATTEMPTS:
            print(f"    format problem ({problems[0]}) - regenerating "
                  f"({attempt}/{MAX_FORMAT_ATTEMPTS - 1})")
            prompt = user_prompt + FORMAT_RETRY_NOTE.format(problem=problems[0])

    return result


def maybe_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def load_done(path):
    """Ids already generated, so an interrupted run can be resumed."""
    if not path.exists():
        return {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    # A malformed result is not "done" - drop it so the next run regenerates it.
    return {
        r["id"]: r
        for r in previous.get("results", [])
        if not r.get("error") and not check_format(r)
    }


def write_output(path, results, args):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pair_mode": args.pair_mode,
        "topics": TOPICS,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt_template": USER_PROMPT_TEMPLATE,
        "results": [r for r in results if r is not None],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH,
                        help="reviewed structural profiles from function_profiles.py")
    parser.add_argument("--conditions", type=Path, default=CONDITIONS_PATH,
                        help="optional pair conditions from pair_conditions.py; "
                             "off by default")
    parser.add_argument("--all-combinations", action="store_true",
                        help="ignore TARGET_PAIRS and sweep every pair")
    parser.add_argument("--all-pairs", action="store_true",
                        help="include pairs marked impossible in the conditions file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default=EFFORT,
                        choices=["minimal", "low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--pair-mode", default=PAIR_MODE,
                        choices=["combinations", "permutations",
                                 "combinations_with_replacement"])
    parser.add_argument("--topics", nargs="+", default=TOPICS)
    parser.add_argument("--workers", type=int, default=WORKERS,
                        help="candidates generated concurrently")
    parser.add_argument("--pair", action="append", default=[],
                        help='restrict to pairs matching "left|right" on function '
                             'names, either order; repeatable')
    parser.add_argument("--samples", type=int, default=SAMPLES,
                        help="candidates per (pair, topic); best-of-N when > 1")
    parser.add_argument("--limit", type=int, help="only run the first N candidates")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts instead of calling the API")
    parser.add_argument("--overwrite", action="store_true",
                        help="regenerate ids already present in --out")
    args = parser.parse_args()

    functions = load_functions(args.csv)
    conditions = load_pair_conditions(args.conditions) if args.conditions else {}
    profiles = load_function_profiles(args.profiles)
    targets = [] if args.all_combinations else TARGET_PAIRS
    if targets:
        known = {fn["function"] for fn in functions}
        unknown = {n for pair in targets for n in pair} - known
        if unknown:
            raise SystemExit("TARGET_PAIRS names not in the definitions CSV: "
                             + ", ".join(sorted(unknown)))
    jobs, skipped = build_jobs(functions, args.topics, args.pair_mode,
                               conditions, args.all_pairs, profiles,
                               args.pair, args.samples, targets)
    if targets:
        print(f"target pairs: {len(targets)} requested")
    if profiles:
        print(f"function profiles: {len(profiles)} row(s) from {args.profiles}")
    if conditions:
        with_condition = sum(1 for j in jobs if j["pair_condition"])
        print(f"pair conditions: {len(conditions)} row(s) from {args.conditions}, "
              f"{with_condition} attached")
    if skipped:
        print(f"skipping {len(skipped)} pair(s) marked impossible "
              f"(use --all-pairs to include them)")
    if args.limit:
        jobs = jobs[: args.limit]

    pairs_used = len({j["pair_id"] for j in jobs})
    print(f"{pairs_used} pair(s) x {len(args.topics)} topic(s) x {args.samples} sample(s) "
          f"-> {len(jobs)} candidate(s)")

    if args.dry_run:
        for job in jobs:
            print("\n" + "=" * 70)
            print(job["id"])
            print("=" * 70)
            print("--- system ---")
            print(SYSTEM_PROMPT or "(empty)")
            print("--- user ---")
            print(job["user_prompt"])
        return

    done = {} if args.overwrite else load_done(args.out)
    if done:
        print(f"resuming: {len(done)} result(s) already in {args.out}")

    client = make_client(args.model)
    print(f"writer: {args.model} ({provider_for(args.model)}), effort {args.effort}")
    results = [None] * len(jobs)
    lock = threading.Lock()
    completed = 0

    def work(index):
        job = jobs[index]
        if job["id"] in done:
            return index, done[job["id"]], True

        record = dict(job)
        try:
            (text, parsed, usage, served_by,
             problems, attempts, repaired) = generate_transcript(
                client, job["user_prompt"], args)
            record["transcript"] = text
            record["transcript_json"] = parsed
            record["usage"] = usage
            record["served_by"] = served_by
            record["attempts"] = attempts
            record["repaired_duplicate_turn"] = repaired
            if problems:
                record["format_problems"] = problems
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        return index, record, False

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, i) for i in range(len(jobs))]
        for future in as_completed(futures):
            index, record, skipped = future.result()
            with lock:
                results[index] = record
                completed += 1
                note = "skip" if skipped else ""
                if record.get("error"):
                    note = f"failed: {record['error']}"
                elif record.get("format_problems"):
                    note = (f"still malformed after {record['attempts']} attempts: "
                            f"{record['format_problems'][0]}")
                elif not skipped and (record.get("attempts", 1) > 1
                                      or record.get("repaired_duplicate_turn")):
                    bits = []
                    if record.get("attempts", 1) > 1:
                        bits.append(f"{record['attempts']} attempts")
                    if record.get("repaired_duplicate_turn"):
                        bits.append("repaired duplicate turn")
                    note = "ok (" + ", ".join(bits) + ")"
                print(f"[{completed}/{len(jobs)}] {record['id']} {note}".rstrip())
                write_output(args.out, results, args)  # checkpoint

    write_output(args.out, results, args)
    failures = [r for r in results if r and r.get("error")]
    print(f"\nwrote {len(results)} result(s) to {args.out}"
          + (f" ({len(failures)} failed)" if failures else ""))


if __name__ == "__main__":
    main()

"""Generate paired laughter realizations plus gold QA annotations.

For each (topic x laughter-function-pair), the model generates:

A. One four-turn lexical transcript with NO audio/laughter markup.
B. The same transcript realized for laughter Function A, with TTS-friendly audio tags
   and an orthographic laugh vocalization inserted only into B's final turn.
C. The same transcript realized for laughter Function B.
D. Gold answers for each realized version:
   1) contains laughter (binary),
   2) laughter timing (before/after/within final utterance),
   3) laughter intention (one of the 10 functions),
   4) third-person interpretation MCQ (1 correct + 2 function-mapped distractors),
   5) open expected-response answer.

The two realized versions MUST preserve exactly the same lexical dialogue. Only the
laughter realization (tags, laugh vocalization, and placement) may differ.

Usage:
    python generate_transcripts_audio_gold.py
    python generate_transcripts_audio_gold.py --dry-run
    python generate_transcripts_audio_gold.py --limit 3
    python generate_transcripts_audio_gold.py --pair "softening|enjoyment"
    python generate_transcripts_audio_gold.py --samples 3
    python generate_transcripts_audio_gold.py --out runs/audio_gold.json
"""

import argparse
import csv
import itertools
import json
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# -----------------------------------------------------------------------------
# Prompt
# -----------------------------------------------------------------------------

SYSTEM_PROMPT = r"""
You are an expert in natural spoken dialogue, pragmatic functions of laughter,
and TTS-oriented performance annotation.

TASK
For ONE supplied pair of laughter functions, produce four linked artifacts:

A. BASE LEXICAL TRANSCRIPT
Create one natural four-turn spoken dialogue with exactly two speakers in the
sequence A -> B -> A -> B. The final B turn must lexically support BOTH target
laughter functions. It contains NO laughter words, audio tags, stage directions,
or prosodic annotation.

B. FUNCTION-A REALIZATION
Copy the exact same dialogue and exact same lexical wording. Insert laughter
material ONLY into B's final turn so the realized version strongly supports
Function A.

C. FUNCTION-B REALIZATION
Again copy the exact same dialogue and exact same lexical wording. Insert laughter
material ONLY into B's final turn so the realized version strongly supports
Function B.

D. GOLD QUESTIONS
For EACH realized version, provide the third-person interpretation MCQ and an open
answer describing what kind of response that interpretation would call for.
The script will deterministically fill the binary laughter-presence answer, the
laughter-timing answer, and the intention-category answer from the realization
metadata, so your interpretation and response must agree with that target.

CORE DESIGN PRINCIPLE
The BASE transcript should make BOTH pragmatic analyses genuinely available.
The REALIZATIONS are allowed to be highly diagnostic and label-leaking because
they are intended for TTS generation, not for text-only judgment.

The ambiguity belongs in A; the acoustic/performance distinction belongs in B/C.

PRIORITY ORDER
1. The base dialogue must satisfy the conversational/event pattern of BOTH target
   functions.
2. The pair-specific condition, if supplied, must be satisfied.
3. The dialogue must sound natural and make common sense.
4. The same base wording must be preserved exactly in both realizations.
5. Each realization must clearly support its own target function.
6. Gold interpretations must follow the realized function AND the actual context.

BASE-TRANSCRIPT CONSTRUCTION
Reason internally before writing; do not output your reasoning.

- Identify who supplies the relevant event for each function.
- Identify what the event is mainly about.
- Identify what happened that makes each function possible.
- Identify what the laughter does to that event.
- Build ONE event that supports both functions at once.
- Prefer overlap: the same phrase/event should support both analyses.
- Do not make the final turn empty, vague, or generic merely to preserve ambiguity.
- Function-relevant lexical material is allowed when required: mild criticism,
  evaluative wording, a request, uncertainty, irony-capable wording, awkwardness,
  or another needed cue.
- Avoid a base turn that lexicalizes only one target so strongly that the other
  becomes implausible.

BASE DIALOGUE FORMAT
- Exactly two speakers: A and B.
- Exactly four turns: A -> B -> A -> B.
- `prior_turns` has exactly three entries.
- `current_turn` is B only.
- One concise spoken-like sentence per turn.
- No laughter words such as haha/heh in the base transcript.
- No square-bracket audio tags in the base transcript.

AUDIO REALIZATION RULES
Each realization changes ONLY B's final turn by inserting audio/performance
material. Do not paraphrase, delete, reorder, or add lexical dialogue words.

Each realization contains ONE laughter episode. That episode may contain:
- one or more square-bracket audio tags; and
- exactly one orthographic laugh vocalization.

AUDIO TAG FORMAT
Every square-bracket tag must contain ONE performance expression only.
Good examples:
    [excited]
    [warm]
    [hesitant]
    [ironic]
    [reassuring]
    [soft laugh]
    [big laugh]
    [breathy]

Do NOT combine multiple expressions in one bracket:
    BAD: [warm, teasing]
    BAD: [soft laugh and hesitant]
Instead use separate tags:
    GOOD: [warm] [teasing] [soft laugh]

In the JSON, list each tag in `audio_tags` exactly as it appears in the transcript,
square brackets included: ["[warm]", "[soft laugh]"], not ["warm", "soft laugh"].

Multiple separate tags are allowed and encouraged when they help TTS express the
function. The tags may be semantically explicit or "leaky" (for example [ironic]
or [sympathetic]) because they are TTS instructions, not evaluation text.

LAUGH VOCALIZATION
Choose a natural written laugh form that supports the intended realization, such
as `haha`, `hah`, `heh`, `hehe`, or `ha`. Do not mechanically use the same form for
every function. Consider whether the target calls for a light, hesitant, warm,
awkward, restrained, amused, affiliative, or larger laugh. The vocalization must
appear outside square brackets.

Do not use only a tag like [laugh] with no vocalization: there must be an explicit
laugh word as well.

LAUGHTER PLACEMENT
Choose exactly ONE placement class for each realization:
- `Before the final utterance`: all inserted laughter material comes before the
  first lexical word of B's base final turn.
- `After the final utterance`: all inserted laughter material comes after the
  complete lexical wording of B's base final turn.
- `Within the final utterance`: the laughter episode interrupts the lexical turn
  between words/phrases, while preserving all lexical words in order.

Do not mix placement classes within one realization. Multiple tags may surround
the one laugh vocalization, but they belong to the same laughter episode.

The Function-A and Function-B realizations MAY use different tags, laugh words,
and placement classes if that better expresses their distinct pragmatic actions.

GOLD QUESTION 4: OBSERVER INTERPRETATION MCQ
For each realization, generate exactly THREE answer options.

- One option is the correct third-person interpretation of the laughter in this
  exact conversational context and must map to that realization's target function.
- Two options are plausible distractor interpretations and each must map to a
  DIFFERENT laughter function from the 10-category inventory.
- Neither distractor may map to the correct target function.
- When contextually plausible, ONE distractor should map to the OTHER member of
  the target pair. This is especially useful because the base transcript was
  designed to support both functions before audio realization.
- The other distractor should map to a different function from the remaining
  inventory.
- Write interpretations as contextualized pragmatic readings, not dictionary
  definitions and not merely the category name.
- Keep options comparable in specificity and length; do not make the correct one
  obviously longer or more detailed.
- `correct_option` must be exactly A, B, or C.

Example style only (do not copy):
    A. B is enjoying the absurd reversal in A's story and inviting shared amusement.
    B. B is using the laugh to make a mild criticism sound less intrusive.
    C. B is uncertain about the adjective they just chose and is repairing it.

GOLD QUESTION 5: EXPECTED RESPONSE
Give a short open-ended answer describing what KIND of response the interpretation
would normally make relevant from the interlocutor in this exact context.
Describe the interactional response, not a mandatory verbatim line.
Examples of form: acknowledge the joke and join the amusement; accept the softened
criticism lightly; reassure the speaker; show uptake of the ironic meaning; accept
the lexical repair; reciprocate warmth.

Do not assume one deterministic next turn. State the response type that the
interpretation makes socially relevant.

INTERNAL CHECKS
Before returning, verify silently:
1. Base transcript has no tags or laughter vocalizations.
2. Base transcript positively supports BOTH target functions.
3. Pair condition is satisfied if present.
4. Both realized transcripts preserve every base lexical word in the same order.
5. Only B's final turn contains inserted audio material.
6. Every bracket contains one expression only.
7. Each realization has exactly one laugh vocalization.
8. Each realization uses exactly one placement class and the declared placement
   matches the text.
9. Function A realization clearly supports Function A.
10. Function B realization clearly supports Function B.
11. Each observer MCQ has exactly three function-mapped options, exactly one target
    option, and two distinct non-target distractor functions.
12. Each expected-response answer follows from the target function AND context.

OUTPUT
Return only the JSON object required by the schema. No markdown or explanation.
"""

USER_PROMPT_TEMPLATE = r"""
[dialogue topic]: {topic}

[laughter function A]
Function name: {function_a}
Definition: {definition_a}
Example: {example_a}
Example explanation: {example_explanation_a}

[laughter function B]
Function name: {function_b}
Definition: {definition_b}
Example: {example_b}
Example explanation: {example_explanation_b}

Create one shared lexical transcript, then two TTS laughter realizations of the
same final turn: one supporting Function A and one supporting Function B. Then
create the observer-interpretation MCQ and expected-response gold answer for each
realization.
"""

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

MODEL = "gpt-5.6-sol"
EFFORT = "high"
MAX_TOKENS = 12000
CSV_PATH = Path("laughter_definitions.csv")
# Per-pair conditions off by default: TARGET_PAIRS does the selection and the
# compact profiles carry the guidance. Pass --conditions pair_conditions.csv to use.
CONDITIONS_PATH = None
PROFILES_PATH = Path("function_profiles_compact.csv")
DEFAULT_OUT = Path("transcripts_audio_gold.json")

PROFILE_FIELDS = [
    "laugher_role",
    "event_initiator",
    "event_focus",
    "trigger_event",
    "laughter_action",
    "lexical_anchor",
]

PROFILE_BLOCK = r"""

[Compact structural profile - Function A]
{profile_a_block}

[Compact structural profile - Function B]
{profile_b_block}
"""

PAIR_CONDITION_BLOCK = r"""

[What this pair needs]
{pair_condition}
"""

# Server-side refusal fallback.
BETAS = ["server-side-fallback-2026-07-01"]

TOPICS = ["domestic", "school"]
PAIR_MODE = "combinations"
WORKERS = 6
SAMPLES = 1

# The contrastive pairs to generate, matching generate_transcripts.py. Names must
# match the `function` column of laughter_definitions.csv exactly. Pass
# --all-combinations to sweep every pair instead.
TARGET_PAIRS = [
    ("Show enjoyment of incongruity", "Marking irony"),
    ("Show enjoyment of incongruity", "Softening / trouble-telling"),
    ("Show enjoyment of incongruity", "Benevolence induction"),
    ("Show enjoyment of incongruity", "Smoothing"),
    ("Show enjoyment of incongruity", "Show sympathy"),
    ("Marking irony", "Softening / trouble-telling"),
    ("Marking irony", "Benevolence induction"),
    ("Marking irony", "Smoothing"),
    ("Marking irony", "Show sympathy"),
]
MAX_FORMAT_ATTEMPTS = 3
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0

FORMAT_RETRY_NOTE = r"""

Your previous reply failed validation:
{problem}

Regenerate the complete JSON object. Preserve the task requirements, especially:
- exactly 3 prior turns and one B current turn in every transcript;
- no audio material in transcript_no_audio;
- realization A/B preserve the base lexical wording exactly;
- one laughter episode per realization;
- each bracket contains one performance expression;
- exactly 3 observer MCQ options with correct function mappings.
"""

LAUGHTER_TIMINGS = [
    "Before the final utterance",
    "After the final utterance",
    "Within the final utterance",
]

# Broad recognizer used only to ensure the base transcript does not accidentally
# contain an obvious laugh token. Realization validation uses the model's explicit
# `laughter_vocalization` field, so it does not depend on this list.
BASE_LAUGH_RE = re.compile(
    r"(?i)(?<![A-Za-z])(?:ha(?:ha)+|heh(?:heh)*|hehe+|hah(?:ah)*|lol)(?![A-Za-z])"
)
TAG_RE = re.compile(r"\[[^\[\]]+\]")


# -----------------------------------------------------------------------------
# Data loading / prompt construction
# -----------------------------------------------------------------------------

def load_functions(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [
            {k: (v or "").strip() for k, v in row.items() if k}
            for row in csv.DictReader(f)
        ]
    if not rows:
        raise SystemExit(f"{path} has no rows")
    return rows


def load_pair_conditions(path):
    if not path.exists():
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            a = (row.get("function_1") or "").strip()
            b = (row.get("function_2") or "").strip()
            if a and b:
                out[(a, b)] = row
                out[(b, a)] = row
    return out


def load_function_profiles(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            row["function"]: {k: (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(f)
            if row.get("function")
        }


def slug(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def make_pairs(functions, mode):
    pairer = {
        "combinations": itertools.combinations,
        "permutations": itertools.permutations,
        "combinations_with_replacement": itertools.combinations_with_replacement,
    }[mode]
    return list(pairer(functions, 2))


def describe_profile(profile):
    if not profile:
        return ""
    lines = []
    for field in PROFILE_FIELDS:
        value = (profile.get(field) or "").strip()
        if value:
            lines.append(f"{field.replace('_', ' ')}: {value}")
    return "\n".join(lines)


def prompt_fields(topic, fn_a, fn_b, condition="", profiles=None, function_names=None):
    profiles = profiles or {}
    fields = {
        "topic": topic,
        "pair_condition": condition,
        "function_inventory": ", ".join(function_names or []),
    }
    for label, fn in (("a", fn_a), ("b", fn_b)):
        fields[f"function_{label}"] = fn["function"]
        fields[f"laughable_type_{label}"] = fn.get("laughable_type", "")
        fields[f"definition_{label}"] = fn.get("definition", "")
        fields[f"example_{label}"] = fn.get("example", "")
        fields[f"example_explanation_{label}"] = fn.get("example_explanation", "")
        profile = profiles.get(fn["function"], {})
        fields[f"profile_{label}_block"] = describe_profile(profile)
        for field in PROFILE_FIELDS:
            fields[f"{field}_{label}"] = (profile.get(field) or "").strip()
    return fields


def build_user_prompt(topic, fn_a, fn_b, condition="", profiles=None, function_names=None):
    fields = prompt_fields(topic, fn_a, fn_b, condition, profiles, function_names)
    prompt = USER_PROMPT_TEMPLATE.format(**fields)

    if fields["profile_a_block"] or fields["profile_b_block"]:
        prompt += PROFILE_BLOCK.format(
            profile_a_block=fields["profile_a_block"],
            profile_b_block=fields["profile_b_block"],
        )

    if condition:
        prompt += PAIR_CONDITION_BLOCK.format(pair_condition=condition)

    prompt += "\n\n[10-category laughter inventory]\n" + "\n".join(
        f"- {name}" for name in (function_names or [])
    )
    return prompt


def match_pair(fn_a, fn_b, patterns):
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
    function_names = [fn["function"] for fn in functions]
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
            prompt = build_user_prompt(
                topic, fn_a, fn_b, condition, profiles, function_names
            )
            for n in range(1, samples + 1):
                jobs.append({
                    "id": base_id if samples == 1 else f"{base_id}__s{n}",
                    "pair_id": base_id,
                    "sample": n,
                    "topic": topic,
                    "laughter_functions": [fn_a, fn_b],
                    "pair_condition": condition,
                    "pair_viability": viability,
                    "user_prompt": prompt,
                    "function_names": function_names,
                })
    return jobs, skipped


# -----------------------------------------------------------------------------
# Structured output schema
# -----------------------------------------------------------------------------

def turn_schema(speaker_enum=None):
    speaker = {"type": "string", "enum": speaker_enum or ["A", "B"]}
    return {
        "type": "object",
        "properties": {
            "speaker": speaker,
            "text": {"type": "string"},
        },
        "required": ["speaker", "text"],
        "additionalProperties": False,
    }


def transcript_schema():
    return {
        "type": "object",
        "properties": {
            "prior_turns": {
                "type": "array",
                "items": turn_schema(),
            },
            "current_turn": turn_schema(["B"]),
        },
        "required": ["prior_turns", "current_turn"],
        "additionalProperties": False,
    }


def realization_schema(function_names):
    return {
        "type": "object",
        "properties": {
            "target_function": {"type": "string", "enum": function_names},
            "laughter_position": {"type": "string", "enum": LAUGHTER_TIMINGS},
            "laughter_vocalization": {"type": "string"},
            "audio_tags": {
                "type": "array",
                "description": ("Each tag exactly as it appears in the transcript, "
                                "including the square brackets, e.g. \"[warm]\". "
                                "One performance expression per tag."),
                "items": {"type": "string"},
            },
            "transcript": transcript_schema(),
        },
        "required": [
            "target_function", "laughter_position", "laughter_vocalization",
            "audio_tags", "transcript",
        ],
        "additionalProperties": False,
    }


def mcq_schema(function_names):
    option = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": ["A", "B", "C"]},
            "text": {"type": "string"},
            "maps_to_function": {"type": "string", "enum": function_names},
        },
        "required": ["label", "text", "maps_to_function"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "options": {"type": "array", "items": option},
            "correct_option": {"type": "string", "enum": ["A", "B", "C"]},
        },
        "required": ["options", "correct_option"],
        "additionalProperties": False,
    }


def model_gold_schema(function_names):
    # Q1-Q3 are added deterministically after generation. The model writes only
    # the context-sensitive parts Q4-Q5.
    return {
        "type": "object",
        "properties": {
            "observer_interpretation_mcq": mcq_schema(function_names),
            "expected_response": {"type": "string"},
        },
        "required": ["observer_interpretation_mcq", "expected_response"],
        "additionalProperties": False,
    }


def build_output_schema(function_names):
    return {
        "type": "object",
        "properties": {
            "transcript_no_audio": transcript_schema(),
            "realization_a": realization_schema(function_names),
            "realization_b": realization_schema(function_names),
            "gold_context_a": model_gold_schema(function_names),
            "gold_context_b": model_gold_schema(function_names),
        },
        "required": [
            "transcript_no_audio", "realization_a", "realization_b",
            "gold_context_a", "gold_context_b",
        ],
        "additionalProperties": False,
    }


# -----------------------------------------------------------------------------
# Provider calls
# -----------------------------------------------------------------------------

def provider_for(model):
    return "anthropic" if model.startswith("claude") else "openai"


def make_client(model):
    if provider_for(model) == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is empty - set it in .env")
        return anthropic.Anthropic(api_key=key)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty - set it in .env")
    return OpenAI(api_key=key)


def call_openai(client, user_prompt, model, effort, max_tokens, schema):
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                reasoning={"effort": effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "laughter_audio_gold",
                        "schema": schema,
                        "strict": True,
                    }
                },
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
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"    retry {attempt + 1}/{MAX_RETRIES - 1} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise last_error


def call_anthropic(client, user_prompt, model, effort, max_tokens, schema,
                   use_fallbacks=True):
    body = {
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        }
    }
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_prompt}],
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
            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                raise RuntimeError(f"model declined the request (category={category})")
            if response.stop_reason == "max_tokens":
                raise RuntimeError(
                    "hit max_tokens before finishing the JSON - raise --max-tokens"
                )
            text = next((b.text for b in response.content if b.type == "text"), None)
            if text is None:
                raise RuntimeError(
                    f"no text block (stop_reason={response.stop_reason})"
                )
            usage = response.usage
            return text, {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }, response.model
        except anthropic.BadRequestError as exc:
            if use_fallbacks and "fallback" in str(exc).lower():
                print("    server-side fallbacks unavailable; retrying without them")
                use_fallbacks = False
                kwargs.pop("betas", None)
                body.pop("fallbacks", None)
                continue
            raise
        except (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.InternalServerError,
            RuntimeError,
        ) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"    retry {attempt + 1}/{MAX_RETRIES - 1} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise last_error


def call_model(client, user_prompt, model, effort, max_tokens, schema):
    if provider_for(model) == "openai":
        return call_openai(client, user_prompt, model, effort, max_tokens, schema)
    return call_anthropic(client, user_prompt, model, effort, max_tokens, schema)


# -----------------------------------------------------------------------------
# Validation and deterministic gold completion
# -----------------------------------------------------------------------------

def maybe_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def normalize_spacing(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([\(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]])", r"\1", text)
    return text


def check_base_transcript(transcript, prefix="transcript_no_audio"):
    problems = []
    if not isinstance(transcript, dict):
        return [f"{prefix} is not an object"]
    prior = transcript.get("prior_turns")
    current = transcript.get("current_turn")
    if not isinstance(prior, list) or len(prior) != 3:
        problems.append(f"{prefix}.prior_turns must contain exactly 3 turns")
        return problems
    expected = ["A", "B", "A"]
    for i, (turn, speaker) in enumerate(zip(prior, expected)):
        if not isinstance(turn, dict) or turn.get("speaker") != speaker:
            problems.append(f"{prefix}.prior_turns[{i}] must be speaker {speaker}")
    if not isinstance(current, dict) or current.get("speaker") != "B":
        problems.append(f"{prefix}.current_turn must be speaker B")

    all_turns = prior + ([current] if isinstance(current, dict) else [])
    for i, turn in enumerate(all_turns):
        text = (turn.get("text") or "") if isinstance(turn, dict) else ""
        if TAG_RE.search(text):
            problems.append(f"{prefix} contains an audio tag in turn {i + 1}")
        if BASE_LAUGH_RE.search(text):
            problems.append(f"{prefix} contains an explicit laugh token in turn {i + 1}")
    return problems


def strip_realization_material(text, tags, vocalization):
    stripped = text
    # Remove declared tags exactly. Longest first avoids accidental partial overlap.
    for tag in sorted(tags, key=len, reverse=True):
        stripped = stripped.replace(tag, " ")
    # Remove exactly one declared vocalization occurrence. Case-insensitive fallback.
    idx = stripped.find(vocalization)
    if idx >= 0:
        stripped = stripped[:idx] + " " + stripped[idx + len(vocalization):]
    else:
        m = re.search(re.escape(vocalization), stripped, flags=re.IGNORECASE)
        if m:
            stripped = stripped[:m.start()] + " " + stripped[m.end():]
    return normalize_spacing(stripped)


def infer_placement(realized_text, base_text, tags, vocalization):
    """Infer whether the inserted episode is before, after, or within the base text.

    We locate the base lexical text after removing the declared audio material.
    For robust placement validation, compare where the first/last inserted material
    appears relative to the first/last lexical token in the realized string.
    """
    markers = list(tags) + [vocalization]
    spans = []
    for marker in markers:
        start = realized_text.find(marker)
        if start >= 0:
            spans.append((start, start + len(marker)))
    if not spans:
        return None

    # Remove markers while retaining a mapping from characters to original indices.
    occupied = [False] * len(realized_text)
    for start, end in spans:
        for i in range(start, min(end, len(occupied))):
            occupied[i] = True

    lexical_indices = [
        i for i, ch in enumerate(realized_text)
        if not occupied[i] and not ch.isspace()
    ]
    if not lexical_indices:
        return None
    first_lex = min(lexical_indices)
    last_lex = max(lexical_indices)
    first_mark = min(s for s, _ in spans)
    last_mark = max(e - 1 for _, e in spans)

    if last_mark < first_lex:
        return "Before the final utterance"
    if first_mark > last_lex:
        return "After the final utterance"
    return "Within the final utterance"


def check_audio_tag(tag):
    if not isinstance(tag, str) or not re.fullmatch(r"\[[^\[\]]+\]", tag.strip()):
        return False
    inner = tag.strip()[1:-1].strip()
    if not inner:
        return False
    # We cannot perfectly define "one expression" linguistically, but reject the
    # common multi-expression separators the prompt explicitly forbids.
    if "," in inner or ";" in inner or " / " in inner or re.search(r"\band\b", inner, re.I):
        return False
    return True


def check_realization(realization, base, target_function, function_names, prefix):
    problems = []
    if not isinstance(realization, dict):
        return [f"{prefix} is not an object"]
    if realization.get("target_function") != target_function:
        problems.append(
            f"{prefix}.target_function must be {target_function!r}"
        )
    if realization.get("laughter_position") not in LAUGHTER_TIMINGS:
        problems.append(f"{prefix}.laughter_position is invalid")

    vocal = (realization.get("laughter_vocalization") or "").strip()
    if not vocal:
        problems.append(f"{prefix}.laughter_vocalization is empty")
    if "[" in vocal or "]" in vocal:
        problems.append(f"{prefix}.laughter_vocalization must be outside brackets")

    tags = realization.get("audio_tags")
    if not isinstance(tags, list) or not tags:
        problems.append(f"{prefix}.audio_tags must contain at least one tag")
        tags = []
    else:
        for tag in tags:
            if not check_audio_tag(tag):
                problems.append(
                    f"{prefix} has invalid/multi-expression audio tag: {tag!r}"
                )

    transcript = realization.get("transcript")
    if not isinstance(transcript, dict):
        problems.append(f"{prefix}.transcript is missing")
        return problems

    prior = transcript.get("prior_turns")
    current = transcript.get("current_turn")
    base_prior = base.get("prior_turns") if isinstance(base, dict) else None
    base_current = base.get("current_turn") if isinstance(base, dict) else None

    if prior != base_prior:
        problems.append(f"{prefix}.prior_turns must exactly equal transcript_no_audio.prior_turns")
    if not isinstance(current, dict) or current.get("speaker") != "B":
        problems.append(f"{prefix}.current_turn must be speaker B")
        return problems

    realized_text = current.get("text") or ""
    base_text = (base_current or {}).get("text") or ""

    # Every declared tag and the declared laugh word must occur in the realized text.
    for tag in tags:
        if realized_text.count(tag) != 1:
            problems.append(f"{prefix} must contain declared tag {tag!r} exactly once")
    if vocal and len(re.findall(re.escape(vocal), realized_text, flags=re.IGNORECASE)) != 1:
        problems.append(f"{prefix} must contain the declared laugh vocalization exactly once")

    # No undeclared tags.
    actual_tags = TAG_RE.findall(realized_text)
    if sorted(actual_tags) != sorted(tags):
        problems.append(f"{prefix} contains undeclared or missing audio tags")

    stripped = strip_realization_material(realized_text, tags, vocal)
    if stripped != normalize_spacing(base_text):
        problems.append(
            f"{prefix} changes lexical wording; after removing audio material got "
            f"{stripped!r}, expected {normalize_spacing(base_text)!r}"
        )

    inferred = infer_placement(realized_text, base_text, tags, vocal)
    declared = realization.get("laughter_position")
    if inferred and declared != inferred:
        problems.append(
            f"{prefix}.laughter_position says {declared!r} but text looks {inferred!r}"
        )

    return problems


def check_mcq(gold_ctx, target_function, paired_function, function_names, prefix):
    problems = []
    if not isinstance(gold_ctx, dict):
        return [f"{prefix} is not an object"]
    mcq = gold_ctx.get("observer_interpretation_mcq")
    if not isinstance(mcq, dict):
        return [f"{prefix}.observer_interpretation_mcq is missing"]
    options = mcq.get("options")
    correct = mcq.get("correct_option")
    if not isinstance(options, list) or len(options) != 3:
        problems.append(f"{prefix} must have exactly 3 observer MCQ options")
        return problems

    labels = [o.get("label") for o in options if isinstance(o, dict)]
    if sorted(labels) != ["A", "B", "C"]:
        problems.append(f"{prefix} option labels must be exactly A, B, C")
    by_label = {o.get("label"): o for o in options if isinstance(o, dict)}
    if correct not in by_label:
        problems.append(f"{prefix}.correct_option must point to A, B, or C")
        return problems

    mappings = [o.get("maps_to_function") for o in options if isinstance(o, dict)]
    if any(m not in function_names for m in mappings):
        problems.append(f"{prefix} contains an unknown function mapping")
    if len(set(mappings)) != 3:
        problems.append(f"{prefix} options must map to 3 distinct laughter functions")
    if by_label[correct].get("maps_to_function") != target_function:
        problems.append(f"{prefix} correct option must map to target function {target_function!r}")
    if mappings.count(target_function) != 1:
        problems.append(f"{prefix} must contain target function exactly once")

    # The paired function is strongly preferred as a distractor, but not hard-failed:
    # some pair/context combinations make that distractor awkward after a strongly
    # diagnostic TTS realization. Store a warning-like problem only if desired; here
    # we keep validation permissive.

    if not (gold_ctx.get("expected_response") or "").strip():
        problems.append(f"{prefix}.expected_response is empty")
    return problems


def normalize_audio_tags(parsed):
    """Canonicalize `audio_tags` to the bracketed form used in the transcript.

    The model sometimes lists tags as bare expressions ("warm") while writing them
    bracketed in the text ("[warm]"). That is a formatting slip, not a content
    error, so bracket it here rather than spending a regeneration on it.
    """
    if not isinstance(parsed, dict):
        return
    for key in ("realization_a", "realization_b"):
        realization = parsed.get(key)
        if not isinstance(realization, dict):
            continue
        tags = realization.get("audio_tags")
        if not isinstance(tags, list):
            continue
        realization["audio_tags"] = [
            tag if not isinstance(tag, str) or tag.strip().startswith("[")
            else f"[{tag.strip()}]"
            for tag in tags
        ]


def check_generated(parsed, job):
    problems = []
    if not isinstance(parsed, dict):
        return ["response is not valid JSON object"]

    base = parsed.get("transcript_no_audio")
    problems.extend(check_base_transcript(base))

    fn_a = job["laughter_functions"][0]["function"]
    fn_b = job["laughter_functions"][1]["function"]
    names = job["function_names"]

    problems.extend(check_realization(
        parsed.get("realization_a"), base, fn_a, names, "realization_a"
    ))
    problems.extend(check_realization(
        parsed.get("realization_b"), base, fn_b, names, "realization_b"
    ))
    problems.extend(check_mcq(
        parsed.get("gold_context_a"), fn_a, fn_b, names, "gold_context_a"
    ))
    problems.extend(check_mcq(
        parsed.get("gold_context_b"), fn_b, fn_a, names, "gold_context_b"
    ))
    return problems


def complete_gold(parsed, job):
    """Add deterministic Q1-Q3 and present Q4-Q5 in final gold objects."""
    fn_a = job["laughter_functions"][0]["function"]
    fn_b = job["laughter_functions"][1]["function"]

    for suffix, fn in (("a", fn_a), ("b", fn_b)):
        realization = parsed[f"realization_{suffix}"]
        ctx = parsed.pop(f"gold_context_{suffix}")
        parsed[f"gold_{suffix}"] = {
            "contains_laughter": True,
            "laughter_timing": realization["laughter_position"],
            "intention": fn,
            "observer_interpretation_mcq": ctx["observer_interpretation_mcq"],
            "expected_response": ctx["expected_response"],
        }
    return parsed


def generate_candidate(client, job, args, schema):
    totals = {"input_tokens": 0, "output_tokens": 0}
    prompt = job["user_prompt"]
    result = None

    for attempt in range(1, MAX_FORMAT_ATTEMPTS + 1):
        text, usage, served_by = call_model(
            client, prompt, args.model, args.effort, args.max_tokens, schema
        )
        for key in totals:
            totals[key] += usage[key]

        parsed = maybe_json(text)
        normalize_audio_tags(parsed)
        problems = check_generated(parsed, job)
        result = (text, parsed, dict(totals), served_by, problems, attempt)
        if not problems:
            parsed = complete_gold(parsed, job)
            return text, parsed, dict(totals), served_by, [], attempt

        if attempt < MAX_FORMAT_ATTEMPTS:
            print(
                f"    validation problem ({problems[0]}) - regenerating "
                f"({attempt}/{MAX_FORMAT_ATTEMPTS - 1})"
            )
            prompt = job["user_prompt"] + FORMAT_RETRY_NOTE.format(
                problem=problems[0]
            )

    return result


# -----------------------------------------------------------------------------
# Persistence / CLI
# -----------------------------------------------------------------------------

def load_done(path, jobs_by_id):
    if not path.exists():
        return {}
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    done = {}
    for record in previous.get("results", []):
        rid = record.get("id")
        if not rid or record.get("error") or record.get("format_problems"):
            continue
        # Completed records already contain deterministic gold_a/gold_b and no
        # gold_context_* fields, so don't run pre-completion validation again.
        if all(k in record.get("generation", {}) for k in (
            "transcript_no_audio", "realization_a", "realization_b", "gold_a", "gold_b"
        )):
            done[rid] = record
    return done


def write_output(path, results, args):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pair_mode": args.pair_mode,
        "topics": args.topics,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt_template": USER_PROMPT_TEMPLATE,
        "results": [r for r in results if r is not None],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument(
        "--profiles", type=Path, default=PROFILES_PATH,
        help="compact structural profiles CSV"
    )
    parser.add_argument(
        "--conditions", type=Path, default=CONDITIONS_PATH,
        help="reviewed pair conditions CSV"
    )
    parser.add_argument("--all-pairs", action="store_true",
                        help="include pairs marked impossible in the conditions file")
    parser.add_argument("--all-combinations", action="store_true",
                        help="ignore TARGET_PAIRS and sweep every pair")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort", default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"]
    )
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument(
        "--pair-mode", default=PAIR_MODE,
        choices=["combinations", "permutations", "combinations_with_replacement"]
    )
    parser.add_argument("--topics", nargs="+", default=TOPICS)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument(
        "--pair", action="append", default=[],
        help='restrict to pairs matching "left|right" on function names'
    )
    parser.add_argument("--samples", type=int, default=SAMPLES,
                        help="candidates per (pair, topic)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    functions = load_functions(args.csv)
    function_names = [fn["function"] for fn in functions]
    if len(function_names) != 10:
        print(
            f"warning: expected 10 laughter categories, found {len(function_names)}"
        )

    profiles = load_function_profiles(args.profiles)
    conditions = load_pair_conditions(args.conditions) if args.conditions else {}
    targets = [] if args.all_combinations else TARGET_PAIRS
    if targets:
        known = {fn["function"] for fn in functions}
        unknown = {n for pair in targets for n in pair} - known
        if unknown:
            raise SystemExit("TARGET_PAIRS names not in the definitions CSV: "
                             + ", ".join(sorted(unknown)))
        print(f"target pairs: {len(targets)} requested")
    jobs, skipped = build_jobs(
        functions, args.topics, args.pair_mode, conditions, args.all_pairs,
        profiles, args.pair, args.samples, targets
    )

    if args.limit:
        jobs = jobs[:args.limit]

    if profiles:
        print(f"function profiles: {len(profiles)} row(s) from {args.profiles}")
    if conditions:
        attached = sum(1 for j in jobs if j["pair_condition"])
        print(
            f"pair conditions: {len(conditions) // 2 if conditions else 0} pair(s), "
            f"{attached} attached to current jobs"
        )
    if skipped:
        print(
            f"skipping {len(skipped)} pair(s) marked impossible "
            "(use --all-pairs to include them)"
        )

    pairs_used = len({j["pair_id"] for j in jobs})
    print(
        f"{pairs_used} pair(s) x {len(args.topics)} topic(s) x {args.samples} "
        f"sample(s) -> {len(jobs)} candidate(s)"
    )

    if args.dry_run:
        for job in jobs:
            print("\n" + "=" * 78)
            print(job["id"])
            print("=" * 78)
            print("--- system ---")
            print(SYSTEM_PROMPT)
            print("--- user ---")
            print(job["user_prompt"])
        return

    schema = build_output_schema(function_names)
    jobs_by_id = {j["id"]: j for j in jobs}
    done = {} if args.overwrite else load_done(args.out, jobs_by_id)
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

        record = {
            key: job[key]
            for key in (
                "id", "pair_id", "sample", "topic", "laughter_functions",
                "pair_condition", "pair_viability", "user_prompt"
            )
        }
        try:
            text, parsed, usage, served_by, problems, attempts = generate_candidate(
                client, job, args, schema
            )
            record["raw_generation"] = text
            record["generation"] = parsed
            record["usage"] = usage
            record["served_by"] = served_by
            record["attempts"] = attempts
            if problems:
                record["format_problems"] = problems
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        return index, record, False

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, i) for i in range(len(jobs))]
        for future in as_completed(futures):
            index, record, was_done = future.result()
            with lock:
                results[index] = record
                completed += 1
                note = "skip" if was_done else ""
                if record.get("error"):
                    note = f"failed: {record['error']}"
                elif record.get("format_problems"):
                    note = (
                        f"still invalid after {record.get('attempts', '?')} attempts: "
                        f"{record['format_problems'][0]}"
                    )
                elif not was_done and record.get("attempts", 1) > 1:
                    note = f"ok ({record['attempts']} attempts)"
                print(f"[{completed}/{len(jobs)}] {record['id']} {note}".rstrip())
                write_output(args.out, results, args)

    write_output(args.out, results, args)
    failures = [r for r in results if r and r.get("error")]
    malformed = [r for r in results if r and r.get("format_problems")]
    suffix = []
    if failures:
        suffix.append(f"{len(failures)} failed")
    if malformed:
        suffix.append(f"{len(malformed)} invalid")
    extra = f" ({', '.join(suffix)})" if suffix else ""
    print(f"\nwrote {len(results)} result(s) to {args.out}{extra}")


if __name__ == "__main__":
    main()

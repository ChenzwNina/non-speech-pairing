"""Generate three-person vocalization minimal pairs.

Four contrasts across six domains (school, work, family, health,
entertainment, travel). Default: 4 × 6 = 24 items.

Usage:
    python pairing_type/generate.py
    python pairing_type/generate.py --domain school --contrast C1
    python pairing_type/generate.py --dry-run
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

load_dotenv()

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "out" / "pairs.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000

CONTRASTS = [
    {
        "id": "C1",
        "contrast": "enjoyment laughter vs impatient groan",
        "vocalization_a": "[happy laugh] haha",
        "meaning_a": "enjoyment laughter",
        "vocalization_b": "[groan]...",
        "meaning_b": "impatient groan",
        "response_distinction": "celebrate or joke along ↔ hurry the group or move on",
        "vocalization_b_options": ["[groan]..."],
    },
    {
        "id": "C2",
        "contrast": "enjoyment laughter vs exhausted sigh",
        "vocalization_a": "[happy laugh] haha",
        "meaning_a": "enjoyment laughter",
        "vocalization_b": "[exhausted sigh]",
        "meaning_b": "exhausted sigh",
        "response_distinction": "celebrate or joke ↔ acknowledge fatigue",
        "vocalization_b_options": ["[exhausted sigh]"],
    },
    {
        "id": "C3",
        "contrast": "impatient groan vs relief sigh",
        "vocalization_a": "[groan]...",
        "meaning_a": "impatient groan",
        "vocalization_b": "[sigh] hoo",
        "meaning_b": "relief sigh",
        "response_distinction": "hurry or wrap up ↔ treat the task as done and ease off",
        "vocalization_b_options": ["[sigh] hoo"],
    },
    {
        "id": "C4",
        "contrast": "engagement mm-hm vs impatient groan",
        "vocalization_a": "mm-hm",
        "meaning_a": "engagement mm-hm",
        "vocalization_b": "[groan]...",
        "meaning_b": "impatient groan",
        "response_distinction": "continue ↔ wrap up, shorten, or change topic",
        "vocalization_b_options": ["[groan]..."],
    },
]

DOMAINS = ["school", "work", "family", "health", "entertainment", "travel"]

DOMAIN_HINTS = {
    "school": "Set it at school: classmates, a teacher, homework, a club, or campus life.",
    "work": "Set it at work: coworkers, a meeting, a manager, a client, or an office task.",
    "family": "Set it among family: parents, siblings, relatives, or something happening at home.",
    "health": "Set it around everyday health: sleep, stretching, a walk, a checkup. Not an emergency.",
    "entertainment": "Set it around entertainment: a show, concert, party, or night out.",
    "travel": "Set it around travel: a trip, airport, hotel, or packing to leave.",
}

TAG_RE = re.compile(r"\[[^\[\]]+\]")
NAMING_RE = re.compile(
    r"(?i)\b("
    r"that sounded like|i interpreted|your (?:laugh|sigh|gasp|yawn) suggests|"
    r"you seem to be expressing|you sound|that laugh means|you seem sarcastic|"
    r"benchmark|vocalization|realization"
    r")\b"
)

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string", "enum": ["A", "B", "C"]},
        "text": {"type": "string"},
    },
    "required": ["speaker", "text"],
    "additionalProperties": False,
}

REALIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "vocalization": {"type": "string"},
        "intended_meaning": {"type": "string"},
        "transcript": {"type": "array", "items": TURN_SCHEMA},
    },
    "required": ["vocalization", "intended_meaning", "transcript"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_id": {"type": "string"},
        "comparison_id": {"type": "string"},
        "contrast": {"type": "string"},
        "domain": {"type": "string"},
        "shared_context": {
            "type": "object",
            "properties": {
                "turn_1": TURN_SCHEMA,
                "turn_2_lexical_content": {"type": "string"},
            },
            "required": ["turn_1", "turn_2_lexical_content"],
            "additionalProperties": False,
        },
        "realization_a": REALIZATION_SCHEMA,
        "realization_b": REALIZATION_SCHEMA,
        "response_difference": {
            "type": "object",
            "properties": {
                "realization_a_action": {"type": "string"},
                "realization_b_action": {"type": "string"},
                "why_responses_diverge": {"type": "string"},
            },
            "required": [
                "realization_a_action",
                "realization_b_action",
                "why_responses_diverge",
            ],
            "additionalProperties": False,
        },
        "quality_check": {
            "type": "object",
            "properties": {
                "turn_1_identical": {"type": "boolean"},
                "turn_2_words_identical": {"type": "boolean"},
                "only_vocalization_changes": {"type": "boolean"},
                "both_meanings_plausible_from_same_words": {"type": "boolean"},
                "third_turn_actions_differ": {"type": "boolean"},
                "vocalization_meaning_not_explicitly_named": {"type": "boolean"},
            },
            "required": [
                "turn_1_identical",
                "turn_2_words_identical",
                "only_vocalization_changes",
                "both_meanings_plausible_from_same_words",
                "third_turn_actions_differ",
                "vocalization_meaning_not_explicitly_named",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "item_id",
        "comparison_id",
        "contrast",
        "domain",
        "shared_context",
        "realization_a",
        "realization_b",
        "response_difference",
        "quality_check",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
You are generating benchmark items for evaluating whether a conversational system
can use non-speech vocalizations to infer pragmatic meaning and produce an
appropriate next response.

TASK

Generate three-person conversational minimal pairs.

The conversation MUST be about the supplied domain (school, work, family, health,
entertainment, or travel). Invent a fresh situation inside that domain.

Each item contains Speakers A, B, and C.

- Speaker A speaks in Turn 1.
- Speaker B speaks in Turn 2.
- Speaker C is already present in the conversation but speaks for the first time in Turn 3.

The benchmark manipulates the NON-SPEECH VOCALIZATION in Speaker B's Turn 2.

For each item, create two realizations:

REALIZATION A:
Turn 2 contains Vocalization A, conveying Meaning A.
Speaker C then gives a Turn 3 response appropriate to Meaning A.

REALIZATION B:
Turn 2 contains Vocalization B, conveying Meaning B.
Speaker C then gives a Turn 3 response appropriate to Meaning B.

CRITICAL CONTROL:
The lexical words spoken by Speaker B in Turn 2 MUST be exactly identical
between Realization A and Realization B.

Only the audio/vocalization tag may change.

Speaker A's Turn 1 must also be exactly identical across both realizations.

Speaker C's Turn 3 SHOULD differ because the appropriate conversational response
depends on how B's vocalization is interpreted.

TARGET CONTRASTS

Use only the contrast supplied in the user message. Turn 2 MUST start with the
exact vocalization formula, then the shared spoken words. Do not invent other
tags or laugh spellings.

C1. enjoyment laughter vs impatient groan
- Vocalization A: [happy laugh] haha
- Vocalization B: [groan]...

C2. enjoyment laughter vs exhausted sigh
- Vocalization A: [happy laugh] haha
- Vocalization B: [exhausted sigh]

C3. impatient groan vs relief sigh
- Vocalization A: [groan]...
- Vocalization B: [sigh] hoo

C4. engagement mm-hm vs impatient groan
- Vocalization A: mm-hm
- Vocalization B: [groan]...

The tokens haha, ..., hoo, and mm-hm are part of the vocalization formula, not
the shared lexical utterance.

DIALOGUE STRUCTURE

Each item contains exactly three turns.

Turn 1 — Speaker A:
- Establish a short, natural situation.
- All three speakers should plausibly be present.
- Do not explicitly describe B's emotional state.
- 5–20 words.
- No audio tags.

Turn 2 — Speaker B:
- Starts with the exact vocalization formula for that realization, then a short
  lexical utterance.
- 3–15 spoken words after the formula.
- The lexical utterance must plausibly support BOTH meanings in the selected contrast.
- The exact lexical content after the formula must remain IDENTICAL in Realization A
  and Realization B.

Turn 3 — Speaker C:
- Speaker C interprets B's vocalization and responds accordingly.
- C's response must be natural in a three-person conversation.
- C should not explicitly say things such as:
  "You sound exhausted,"
  "That laugh means you're happy,"
  "You seem sarcastic,"
  or otherwise name the benchmark label.
- Instead, C's response should SHOW the interpretation through the conversational action.
- 4–20 words.
- No audio tags.

AUDIO TAG RULES

Turns 1 and 3 must contain no audio tags at all.

Turn 2 starts with the supplied formula, then the shared words. Examples:
    [happy laugh] haha We actually got it all done.
    [groan]... We actually got it all done.
    [exhausted sigh] We actually got it all done.
    [sigh] hoo We actually got it all done.
    mm-hm There are more pictures in the back.

Do not add extra tags. Do not write [laugh], [happy], or [sighs impatiently].
For engagement, write mm-hm with no square brackets.
Keep [groan]... glued as shown, with the three dots part of the formula.

MINIMAL-PAIR REQUIREMENTS

For every item:

1. Turn 1 must be identical across Realization A and Realization B.

2. Speaker B's spoken words AFTER the vocalization formula must be EXACTLY identical.

GOOD:
A: [happy laugh] haha We actually got it all done.
B: [groan]... We actually got it all done.

BAD: the shared words changed, or haha / hoo / mm-hm were treated as the shared words.

3. The vocalization must materially change the plausible pragmatic meaning.

4. Speaker C's appropriate response must change.

5. If essentially the same Turn 3 response works naturally for both realizations,
discard the example and generate a new one.

6. Do not make the lexical content itself strongly reveal the interpretation.

BAD:
[exhausted sigh] "I absolutely hate doing this."

GOOD:
[exhausted sigh] We actually got it all done.

7. Do not rely on narration to explain the intended interpretation.

8. Use everyday realistic scenarios:
- friends
- coworkers
- roommates
- family
- classmates
- collaborative tasks
- planning
- meals
- travel
- household situations
- casual social interaction

9. Avoid dangerous, traumatic, sexual, medical, or highly sensitive scenarios.

10. Vary scenarios and wording. Do not repeatedly use "Sure," "Okay," "Again?",
or the example utterances provided in the contrast definitions. Do not restage
the early-hike / "Again?" example.

THIRD-SPEAKER REQUIREMENT

Speaker C must behave as a genuine participant in the interaction, not as an evaluator.

C must NEVER say:
- "That sounded like..."
- "I interpreted that as..."
- "Your laugh suggests..."
- "You seem to be expressing..."

Instead, C should naturally act on the interpretation.

Generate exactly ONE item for the contrast specified by the user.
Return JSON only.
""".strip()


def strip_tags(text: str) -> str:
    return " ".join(TAG_RE.sub(" ", text or "").split())


def word_count(text: str) -> int:
    return len(strip_tags(text).split())


def tags_in(text: str) -> list[str]:
    return TAG_RE.findall(text or "")


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def glue_ellipsis(text: str) -> str:
    return re.sub(r"\]\s*\.\.\.", "]...", normalize(text))


def rest_after_prefix(text: str, prefix: str) -> str | None:
    t = glue_ellipsis(text)
    p = glue_ellipsis(prefix)
    if not t.lower().startswith(p.lower()):
        return None
    return t[len(p) :].lstrip(" ,")


def validate(payload: dict, spec: dict, item_id: str, domain: str) -> list[str]:
    problems: list[str] = []
    if payload.get("item_id") != item_id:
        problems.append(f"item_id should be {item_id}")
    if payload.get("comparison_id") != spec["id"]:
        problems.append(f"comparison_id should be {spec['id']}")
    if payload.get("contrast") != spec["contrast"]:
        problems.append(f"contrast should be {spec['contrast']!r}")
    if (payload.get("domain") or "").strip().lower() != domain:
        problems.append(f"domain should be {domain}")

    shared = payload.get("shared_context") or {}
    turn1 = shared.get("turn_1") or {}
    lexical = normalize(strip_tags(shared.get("turn_2_lexical_content") or ""))

    for key, _expected_speaker in (("realization_a", "A"), ("realization_b", "B")):
        real = payload.get(key) or {}
        turns = real.get("transcript") or []
        if not isinstance(turns, list) or len(turns) != 3:
            problems.append(f"{key} needs exactly three turns")
            continue
        speakers = [turn.get("speaker") for turn in turns]
        if speakers != ["A", "B", "C"]:
            problems.append(f"{key} speakers must be A, B, C")
        texts = [turn.get("text") or "" for turn in turns]
        if normalize(texts[0]) != normalize(turn1.get("text") or ""):
            problems.append(f"{key} Turn 1 must match shared_context.turn_1")
        if turn1.get("speaker") != "A":
            problems.append("shared turn_1 speaker must be A")
        if tags_in(texts[0]) or tags_in(texts[2]):
            problems.append(f"{key} Turns 1 and 3 must have no audio tags")
        prefix = spec["vocalization_a"] if key == "realization_a" else spec["vocalization_b"]
        rest = rest_after_prefix(texts[1], prefix)
        if rest is None:
            problems.append(f"{key} Turn 2 must start with {prefix}")
        else:
            if normalize(rest) != lexical:
                problems.append(f"{key} Turn 2 words after the formula must match turn_2_lexical_content")
            spoken = word_count(rest)
            if spoken < 3 or spoken > 15:
                problems.append(f"{key} Turn 2 must be 3–15 spoken words after the formula")
        if tags_in(texts[1]) != tags_in(prefix):
            problems.append(f"{key} Turn 2 tags must match the formula {prefix}")
        if word_count(texts[0]) < 5 or word_count(texts[0]) > 20:
            problems.append(f"{key} Turn 1 must be 5–20 words")
        if word_count(texts[2]) < 4 or word_count(texts[2]) > 20:
            problems.append(f"{key} Turn 3 must be 4–20 words")
        if NAMING_RE.search(texts[2]):
            problems.append(f"{key} Turn 3 names the vocalization or label")

    real_a = payload.get("realization_a") or {}
    real_b = payload.get("realization_b") or {}
    voc_a = (real_a.get("vocalization") or "").strip()
    voc_b = (real_b.get("vocalization") or "").strip()
    if glue_ellipsis(voc_a) != glue_ellipsis(spec["vocalization_a"]):
        problems.append(f"realization_a vocalization should be {spec['vocalization_a']}")
    if glue_ellipsis(voc_b) not in {glue_ellipsis(opt) for opt in spec["vocalization_b_options"]}:
        problems.append(
            "realization_b vocalization should be "
            + " or ".join(spec["vocalization_b_options"])
        )
    if (real_a.get("intended_meaning") or "").strip().casefold() != spec["meaning_a"].casefold():
        problems.append(f"realization_a intended_meaning should be {spec['meaning_a']}")
    if (real_b.get("intended_meaning") or "").strip().casefold() != spec["meaning_b"].casefold():
        problems.append(f"realization_b intended_meaning should be {spec['meaning_b']}")

    turns_a = real_a.get("transcript") or []
    turns_b = real_b.get("transcript") or []
    if len(turns_a) == 3 and len(turns_b) == 3:
        text_a = [turn.get("text") or "" for turn in turns_a]
        text_b = [turn.get("text") or "" for turn in turns_b]
        if normalize(text_a[0]) != normalize(text_b[0]):
            problems.append("Turn 1 must be identical across realizations")
        rest_a = rest_after_prefix(text_a[1], spec["vocalization_a"])
        rest_b = rest_after_prefix(text_b[1], spec["vocalization_b"])
        if rest_a is None or rest_b is None or normalize(rest_a) != normalize(rest_b):
            problems.append("Turn 2 spoken words after the formula must be identical")
        if normalize(text_a[2]) == normalize(text_b[2]):
            problems.append("Turn 3 must differ across realizations")
        if glue_ellipsis(voc_a) != glue_ellipsis(spec["vocalization_a"]):
            problems.append(f"realization_a vocalization should be {spec['vocalization_a']}")
        if glue_ellipsis(voc_b) not in {glue_ellipsis(opt) for opt in spec["vocalization_b_options"]}:
            problems.append(
                "realization_b vocalization should be "
                + " or ".join(spec["vocalization_b_options"])
            )
        if lexical and lexical.lower() in {"sure", "okay", "again?", "again"}:
            problems.append("Turn 2 lexical content is too close to the banned examples")

    checks = payload.get("quality_check") or {}
    for field in (
        "turn_1_identical",
        "turn_2_words_identical",
        "only_vocalization_changes",
        "both_meanings_plausible_from_same_words",
        "third_turn_actions_differ",
        "vocalization_meaning_not_explicitly_named",
    ):
        if checks.get(field) is not True:
            problems.append(f"quality_check.{field} must be true")
    return problems


def user_prompt(
    spec: dict,
    item_id: str,
    domain: str,
    used_turn1: list[str],
    used_turn2: list[str],
) -> str:
    lines = [
        "Generate exactly one item for this contrast and domain.",
        "",
        f"item_id: {item_id}",
        f"comparison_id: {spec['id']}",
        f"contrast: {spec['contrast']}",
        f"domain: {domain}",
        DOMAIN_HINTS[domain],
        "Every turn should clearly belong to this domain.",
        "",
        f"Vocalization A: {spec['vocalization_a']} → {spec['meaning_a']}",
        f"Vocalization B: {spec['vocalization_b']} → {spec['meaning_b']}",
        f"Response distinction: {spec['response_distinction']}",
        "",
        "Use EXACTLY these Turn 2 formulas, then the same shared words. Turns 1 and 3 have no tags.",
        f"Realization A Turn 2 must start with {spec['vocalization_a']}",
        f"Realization B Turn 2 must start with {spec['vocalization_b']}",
        "turn_2_lexical_content is ONLY the shared words after the formula, not haha / ... / hoo / mm-hm.",
        f'intended_meaning A must be exactly: "{spec["meaning_a"]}"',
        f'intended_meaning B must be exactly: "{spec["meaning_b"]}"',
    ]
    if used_turn1:
        lines += ["", "Do not reuse these Turn 1 setups:"]
        lines += [f"- {text}" for text in used_turn1[-12:]]
    if used_turn2:
        lines += ["", "Do not reuse these Turn 2 utterances:"]
        lines += [f"- {text}" for text in used_turn2[-12:]]
    return "\n".join(lines)


def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                reasoning={"effort": effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "pairing_type_item",
                        "schema": OUTPUT_SCHEMA,
                        "strict": True,
                    }
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"status={response.status} details={getattr(response, 'incomplete_details', None)}"
                )
            payload = json.loads(response.output_text)
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return payload, usage, response.model
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            wait = 2 ** attempt
            print(f"    retry in {wait}s: {exc}")
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


def generate_one(
    client: OpenAI,
    spec: dict,
    item_id: str,
    domain: str,
    args: argparse.Namespace,
    used_turn1: list[str],
    used_turn2: list[str],
) -> dict:
    prompt = user_prompt(spec, item_id, domain, used_turn1, used_turn2)
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    served_by = args.model

    for attempt in range(1, 4):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, spec, item_id, domain)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            return payload
        last_problems = problems
        prompt = (
            user_prompt(spec, item_id, domain, used_turn1, used_turn2)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Pairing-type minimal pairs",
        "",
        f"writer: {model} · {len(records)} item(s)",
        "",
        "Turn 1 and Turn 2 words are identical within each pair; only B's vocalization and C's response change.",
        "",
    ]
    current = None
    for record in records:
        if record["contrast"] != current:
            current = record["contrast"]
            lines += [f"## {record['comparison_id']}. {current}", ""]
        lexical = record["shared_context"]["turn_2_lexical_content"]
        turn1 = record["shared_context"]["turn_1"]["text"]
        a = record["realization_a"]
        b = record["realization_b"]
        lines += [
            f"### {record['item_id']} · {record.get('domain', '')}",
            "",
            f"A: {turn1}",
            f"B lexical: {lexical}",
            "",
            f"- A · {a['vocalization']} {a['intended_meaning']}",
            f"  - B: {a['transcript'][1]['text']}",
            f"  - C: {a['transcript'][2]['text']}",
            f"- B · {b['vocalization']} {b['intended_meaning']}",
            f"  - B: {b['transcript'][1]['text']}",
            f"  - C: {b['transcript'][2]['text']}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort",
        default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--n", type=int, default=1, help="items per contrast × domain")
    parser.add_argument("--contrast", action="append", default=[], help="restrict to ids, e.g. C3")
    parser.add_argument("--domain", action="append", default=[], help="restrict to these domains")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = CONTRASTS
    if args.contrast:
        needles = [item.lower() for item in args.contrast]
        specs = [
            spec
            for spec in CONTRASTS
            if any(n in spec["id"].lower() or n in spec["contrast"].lower() for n in needles)
        ]
        if not specs:
            raise SystemExit("no contrast matched --contrast")

    domains = DOMAINS
    if args.domain:
        needles = [item.lower() for item in args.domain]
        domains = [domain for domain in DOMAINS if any(n in domain for n in needles)]
        if not domains:
            raise SystemExit("no domain matched --domain")

    jobs = [
        (spec, domain, sample)
        for spec in specs
        for domain in domains
        for sample in range(1, args.n + 1)
    ]
    print(f"{len(specs)} contrast(s) × {len(domains)} domain(s) × {args.n} → {len(jobs)} item(s)")

    if args.dry_run:
        used_turn1: list[str] = []
        used_turn2: list[str] = []
        for spec, domain, sample in jobs:
            item_id = f"{spec['id']}_{domain}_{sample:03d}"
            print("\n" + "=" * 72)
            print(f"{item_id} · {spec['contrast']} · {domain}")
            print("=" * 72)
            print(user_prompt(spec, item_id, domain, used_turn1, used_turn2))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}")
    records: list[dict] = []
    used_turn1 = []
    used_turn2 = []

    for index, (spec, domain, sample) in enumerate(jobs, start=1):
        item_id = f"{spec['id']}_{domain}_{sample:03d}"
        print(f"[{index}/{len(jobs)}] {item_id} · {spec['contrast']}")
        try:
            record = generate_one(client, spec, item_id, domain, args, used_turn1, used_turn2)
            records.append(record)
            used_turn1.append(record["shared_context"]["turn_1"]["text"])
            used_turn2.append(record["shared_context"]["turn_2_lexical_content"])
            a_c = record["realization_a"]["transcript"][2]["text"]
            b_c = record["realization_b"]["transcript"][2]["text"]
            print(f"    A C: {a_c}")
            print(f"    B C: {b_c}")
        except Exception as exc:
            records.append(
                {
                    "item_id": item_id,
                    "comparison_id": spec["id"],
                    "contrast": spec["contrast"],
                    "domain": domain,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"    failed: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contrasts": [spec["id"] for spec in specs],
        "domains": domains,
        "n_per_contrast_domain": args.n,
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "realization_a" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

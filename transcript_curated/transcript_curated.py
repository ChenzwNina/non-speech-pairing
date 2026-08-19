"""Generate four-turn same-content vocalization pairs.

Turns 1 and 2 are identical. Turn 3 keeps the same spoken words and changes
only the audio tags. Turn 4 is Speaker C's response to that vibe.

Three contrasts × five domains (school, work, family, health, entertainment).
Default: 3 × 5 = 15 items.

Usage:
    python transcript_curated/transcript_curated.py
    python transcript_curated/transcript_curated.py --domain school --pair P1
    python transcript_curated/transcript_curated.py --dry-run
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
load_dotenv(HERE.parent / ".env")
DEFAULT_OUT = HERE / "out" / "pairs.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000

PAIRS = [
    {
        "id": "P1",
        "contrast": "enjoyment big laugh vs sympathetic laugh",
        "vocalization_a": "[happy laugh] hahahaha",
        "meaning_a": "enjoyment big laugh",
        "placement_a": "prefix",
        "vocalization_b": "[sympathetic]",
        "meaning_b": "sympathetic laugh",
        "placement_b": "in_speech",
        "response_distinction": (
            "join the fun, treat it as a shared joke "
            "↔ soften, comfort, or help with the mishap"
        ),
        "setup_hint": (
            "Turns 1–2 set up a mild mishap or awkward moment that can be "
            "told as funny or as something still a bit sore. Do not already "
            "mark it as a joke or as a problem. Turn 3 comments on that event "
            "in words that work as either a punchline or a kind remark."
        ),
    },
    {
        "id": "P2",
        "contrast": "sarcastic laugh vs enjoyment big laugh",
        "vocalization_a": "[sarcastic] ha... ha... ha...",
        "meaning_a": "sarcastic laugh",
        "placement_a": "prefix",
        "vocalization_b": "[happy laugh] hahahaha",
        "meaning_b": "enjoyment big laugh",
        "placement_b": "prefix",
        "response_distinction": (
            "treat the line as criticism and course-correct "
            "↔ celebrate or joke along"
        ),
        "setup_hint": (
            "Turns 1–2 set up a plan, result, or remark that could be "
            "genuinely pleasing or dryly mocked. Turn 3 is an evaluation "
            "that works as real delight or as sarcasm. Avoid words that "
            "lock the reading (love that, unfortunately, obviously terrible)."
        ),
    },
    {
        "id": "P3",
        "contrast": "exhausted sigh vs relief sigh",
        "vocalization_a": "[heavy sigh]...",
        "meaning_a": "exhausted sigh",
        "placement_a": "prefix",
        "vocalization_b": "[happy]hooo[exhale]",
        "meaning_b": "relief sigh",
        "placement_b": "prefix",
        "response_distinction": (
            "acknowledge fatigue, take over, or stop "
            "↔ treat the task as done and ease off with them"
        ),
        "setup_hint": (
            "Turns 1–2 reach a wrap-up or last step that could feel draining "
            "or resolving. Turn 3 notes that the thing is finished or nearly "
            "finished, in words that work as worn-out or as a happy release."
        ),
    },
]

DOMAINS = ["school", "work", "family", "health", "entertainment"]

DOMAIN_HINTS = {
    "school": "Set it at school: classmates, a teacher, homework, a club, or campus life.",
    "work": "Set it at work: coworkers, a meeting, a manager, a client, or an office task.",
    "family": "Set it among family: parents, siblings, relatives, or something happening at home.",
    "health": "Set it around everyday health: sleep, stretching, a walk, a checkup. Not an emergency.",
    "entertainment": "Set it around entertainment: a show, concert, party, or night out.",
}

TAG_RE = re.compile(r"\[[^\[\]]+\]")
LAUGH_TOKEN_RE = re.compile(
    r"(?i)(?<![a-z])(?:ha(?:ha)+|ha(?:\.\.\.\s*ha){1,}|heh(?:e|eh)*|hehe+)(?![a-z])"
)
NAMING_RE = re.compile(
    r"(?i)\b("
    r"that sounded like|i interpreted|your (?:laugh|sigh|gasp|yawn) suggests|"
    r"you seem to be expressing|you sound|that laugh means|you seem sarcastic|"
    r"you sound exhausted|you sound relieved|sympathetic laugh|"
    r"benchmark|vocalization|realization"
    r")\b"
)
NARRATION_RE = re.compile(
    r"(?i)^(?:c |speaker c )|\bC (?:takes|fetches|grabs|asks|brings|goes)\b"
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

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_id": {"type": "string"},
        "pair_id": {"type": "string"},
        "contrast": {"type": "string"},
        "domain": {"type": "string"},
        "turn_1": TURN_SCHEMA,
        "turn_2": TURN_SCHEMA,
        "turn_3_lexical": {"type": "string"},
        "turn_3_a": TURN_SCHEMA,
        "turn_3_b": TURN_SCHEMA,
        "turn_4_a": TURN_SCHEMA,
        "turn_4_b": TURN_SCHEMA,
        "response_difference": {
            "type": "object",
            "properties": {
                "version_a_action": {"type": "string"},
                "version_b_action": {"type": "string"},
                "why_responses_diverge": {"type": "string"},
            },
            "required": [
                "version_a_action",
                "version_b_action",
                "why_responses_diverge",
            ],
            "additionalProperties": False,
        },
        "quality_check": {
            "type": "object",
            "properties": {
                "turn_1_identical": {"type": "boolean"},
                "turn_2_identical": {"type": "boolean"},
                "turn_3_words_identical": {"type": "boolean"},
                "only_vocalization_changes": {"type": "boolean"},
                "both_meanings_plausible_from_same_words": {"type": "boolean"},
                "turn_4_actions_differ": {"type": "boolean"},
                "vocalization_meaning_not_explicitly_named": {"type": "boolean"},
            },
            "required": [
                "turn_1_identical",
                "turn_2_identical",
                "turn_3_words_identical",
                "only_vocalization_changes",
                "both_meanings_plausible_from_same_words",
                "turn_4_actions_differ",
                "vocalization_meaning_not_explicitly_named",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "item_id",
        "pair_id",
        "contrast",
        "domain",
        "turn_1",
        "turn_2",
        "turn_3_lexical",
        "turn_3_a",
        "turn_3_b",
        "turn_4_a",
        "turn_4_b",
        "response_difference",
        "quality_check",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
You are generating benchmark items for evaluating whether a conversational
system can use non-speech vocalizations to infer pragmatic meaning and
produce an appropriate next response.

TASK

Generate four-turn conversational minimal pairs.

The conversation MUST be about the supplied domain. Invent a fresh situation
inside that domain.

Speakers A and B talk in Turns 1–3. Speaker C is already present but speaks
for the first time in Turn 4.

DIALOGUE STRUCTURE

Turn 1 — Speaker A:
- Establish a short, natural situation. All three people are present.
- Do not describe anyone's emotional state.
- 6–22 words. No audio tags.

Turn 2 — Speaker B:
- Continue the same situation. Keep the event readable as either vibe.
- 5–20 words. No audio tags.

Turn 3 — Speaker A:
- Same spoken words in version A and version B.
- Only the audio / vocalization tags change.
- 5–16 spoken words after tags and laugh/sigh tokens are removed.
- The words must support BOTH meanings in the pair.

Turn 4 — Speaker C:
- Spoken dialogue in C's own voice. Never narrate ("C takes a photo...").
- C hears Turn 3 and responds to that vibe.
- Show the interpretation through the action. Do not name the laugh, sigh,
  sarcasm, sympathy, exhaustion, or relief.
- Version A and version B MUST be different actions.
- 4–22 words. No audio tags.

If essentially the same Turn 4 works for both versions, discard and rewrite.

VOCALIZATION FORMULAS

Use only the pair supplied in the user message. Do not invent other tags or
laugh spellings.

P1. enjoyment big laugh vs sympathetic laugh
- Version A, prefix burst: [happy laugh] hahahaha then the shared words.
  Example: [happy laugh] hahahaha At least the title is still readable.
- Version B, in-speech: insert [sympathetic] once inside the shared words.
  No haha / hehe token. Example: At least the title is [sympathetic] still readable.

P2. sarcastic laugh vs enjoyment big laugh
- Version A, prefix: [sarcastic] ha... ha... ha... then the shared words.
  Example: [sarcastic] ha... ha... ha... That's one way to handle the client.
- Version B, prefix: [happy laugh] hahahaha then the same shared words.
  Example: [happy laugh] hahahaha That's one way to handle the client.

P3. exhausted sigh vs relief sigh
- Version A, prefix: [heavy sigh]... then the shared words.
  Example: [heavy sigh]... That's the last box.
- Version B, prefix: [happy]hooo[exhale] then the same shared words.
  Example: [happy]hooo[exhale] That's the last box.

The tokens hahahaha, ha... ha... ha..., ..., and hooo belong to the formula,
not to turn_3_lexical.

turn_3_lexical is ONLY the shared spoken words, with no tags and no formula
tokens.

MINIMAL-PAIR REQUIREMENTS

1. Turns 1 and 2 are identical across versions and have no tags.
2. Turn 3 spoken words are exactly identical. Only tags / formula tokens change.
3. The vocalization must change the plausible vibe.
4. Speaker C's Turn 4 must change.
5. Do not let the lexical content itself lock one reading.
6. Do not narrate the interpretation.
7. Everyday realistic scenarios. No dangerous, traumatic, sexual, medical, or
   highly sensitive situations.
8. Vary scenarios. Do not reuse Sure / Okay / Again? or the examples above.
9. C never says "that sounded like", "you sound", "I interpreted", or names
   the benchmark label.

Generate exactly ONE item. Return JSON only.
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


def strip_formula_tokens(text: str) -> str:
    cleaned = glue_ellipsis(strip_tags(text))
    cleaned = re.sub(r"(?i)\bha(?:\.\.\.\s*ha){1,}\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bha(?:ha)+\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bhooo+\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bheh(?:e|eh)*\b", " ", cleaned)
    cleaned = re.sub(r"\.\.\.", " ", cleaned)
    return normalize(cleaned)


def rest_after_prefix(text: str, prefix: str) -> str | None:
    t = glue_ellipsis(text)
    p = glue_ellipsis(prefix)
    if not t.lower().startswith(p.lower()):
        return None
    return t[len(p) :].lstrip(" ,")


def lexical_from_turn(text: str, spec: dict, which: str) -> str | None:
    placement = spec[f"placement_{which}"]
    prefix = spec[f"vocalization_{which}"]
    if placement == "prefix":
        rest = rest_after_prefix(text, prefix)
        if rest is None:
            return None
        return strip_formula_tokens(rest)
    lexical = strip_formula_tokens(text)
    return lexical or None


def validate(payload: dict, spec: dict, item_id: str, domain: str) -> list[str]:
    problems: list[str] = []
    if payload.get("item_id") != item_id:
        problems.append(f"item_id should be {item_id}")
    if payload.get("pair_id") != spec["id"]:
        problems.append(f"pair_id should be {spec['id']}")
    if payload.get("contrast") != spec["contrast"]:
        problems.append(f"contrast should be {spec['contrast']!r}")
    if (payload.get("domain") or "").strip().lower() != domain:
        problems.append(f"domain should be {domain}")

    turn1 = payload.get("turn_1") or {}
    turn2 = payload.get("turn_2") or {}
    lexical = normalize(strip_formula_tokens(payload.get("turn_3_lexical") or ""))

    if turn1.get("speaker") != "A":
        problems.append("turn_1 speaker must be A")
    if turn2.get("speaker") != "B":
        problems.append("turn_2 speaker must be B")
    if tags_in(turn1.get("text") or "") or tags_in(turn2.get("text") or ""):
        problems.append("Turns 1 and 2 must have no audio tags")
    if word_count(turn1.get("text") or "") < 6 or word_count(turn1.get("text") or "") > 22:
        problems.append("Turn 1 must be 6–22 words")
    if word_count(turn2.get("text") or "") < 5 or word_count(turn2.get("text") or "") > 20:
        problems.append("Turn 2 must be 5–20 words")
    if not lexical or len(lexical.split()) < 5 or len(lexical.split()) > 16:
        problems.append("turn_3_lexical must be 5–16 spoken words")
    if TAG_RE.search(payload.get("turn_3_lexical") or ""):
        problems.append("turn_3_lexical must contain no audio tags")
    if LAUGH_TOKEN_RE.search(payload.get("turn_3_lexical") or ""):
        problems.append("turn_3_lexical must not include laugh tokens")

    for which, key3, key4 in (("a", "turn_3_a", "turn_4_a"), ("b", "turn_3_b", "turn_4_b")):
        t3 = payload.get(key3) or {}
        t4 = payload.get(key4) or {}
        if t3.get("speaker") != "A":
            problems.append(f"{key3} speaker must be A")
        if t4.get("speaker") != "C":
            problems.append(f"{key4} speaker must be C")
        text3 = t3.get("text") or ""
        text4 = t4.get("text") or ""
        if tags_in(text4):
            problems.append(f"{key4} must have no audio tags")
        if word_count(text4) < 4 or word_count(text4) > 22:
            problems.append(f"{key4} must be 4–22 words")
        if NAMING_RE.search(text4):
            problems.append(f"{key4} names the vocalization or label")
        if NARRATION_RE.search(text4):
            problems.append(f"{key4} must be spoken dialogue, not third-person narration")

        placement = spec[f"placement_{which}"]
        prefix = spec[f"vocalization_{which}"]
        got_lexical = lexical_from_turn(text3, spec, which)
        if got_lexical is None:
            if placement == "prefix":
                problems.append(f"{key3} must start with {prefix}")
            else:
                problems.append(f"{key3} must keep the shared words around {prefix}")
        elif got_lexical != lexical:
            problems.append(f"{key3} spoken words must match turn_3_lexical")

        if placement == "prefix":
            if tags_in(glue_ellipsis(text3)) != tags_in(glue_ellipsis(prefix)):
                problems.append(f"{key3} tags must match the formula {prefix}")
        else:
            if tags_in(text3) != [prefix]:
                problems.append(f"{key3} must contain exactly one {prefix} tag")
            if LAUGH_TOKEN_RE.search(strip_tags(text3)):
                problems.append(f"{key3} in-speech version must not add haha/hehe")
            if not re.search(r"\w.+\[[^\]]+\].+\w", text3):
                problems.append(f"{key3} must place {prefix} inside the sentence, not as a prefix burst")

    t4a = normalize((payload.get("turn_4_a") or {}).get("text") or "")
    t4b = normalize((payload.get("turn_4_b") or {}).get("text") or "")
    if t4a and t4b and t4a == t4b:
        problems.append("Turn 4 must differ across versions")

    checks = payload.get("quality_check") or {}
    for field in (
        "turn_1_identical",
        "turn_2_identical",
        "turn_3_words_identical",
        "only_vocalization_changes",
        "both_meanings_plausible_from_same_words",
        "turn_4_actions_differ",
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
    used_turn3: list[str],
) -> str:
    lines = [
        "Generate exactly one item for this pair and domain.",
        "",
        f"item_id: {item_id}",
        f"pair_id: {spec['id']}",
        f"contrast: {spec['contrast']}",
        f"domain: {domain}",
        DOMAIN_HINTS[domain],
        "Every turn should clearly belong to this domain.",
        "",
        spec["setup_hint"],
        "",
        f"Version A vocalization: {spec['vocalization_a']} → {spec['meaning_a']} ({spec['placement_a']})",
        f"Version B vocalization: {spec['vocalization_b']} → {spec['meaning_b']} ({spec['placement_b']})",
        f"Response distinction: {spec['response_distinction']}",
        "",
        "Turn 1 speaker A, Turn 2 speaker B, Turn 3 speaker A, Turn 4 speaker C.",
        "Turns 1, 2, and 4 have no tags.",
        "turn_3_lexical is ONLY the shared words, no tags and no hahahaha / ha... / hooo.",
    ]
    if spec["placement_a"] == "prefix":
        lines.append(f"turn_3_a.text must start with {spec['vocalization_a']} then the shared words.")
    else:
        lines.append(f"turn_3_a.text inserts {spec['vocalization_a']} once inside the shared words.")
    if spec["placement_b"] == "prefix":
        lines.append(f"turn_3_b.text must start with {spec['vocalization_b']} then the shared words.")
    else:
        lines.append(
            f"turn_3_b.text inserts {spec['vocalization_b']} once inside the shared words, "
            "not as a leading burst and with no haha token."
        )
    if used_turn1:
        lines += ["", "Do not reuse these Turn 1 setups:"]
        lines += [f"- {text}" for text in used_turn1[-12:]]
    if used_turn3:
        lines += ["", "Do not reuse these Turn 3 utterances:"]
        lines += [f"- {text}" for text in used_turn3[-12:]]
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
                        "name": "transcript_curated_item",
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
    used_turn3: list[str],
) -> dict:
    prompt = user_prompt(spec, item_id, domain, used_turn1, used_turn3)
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
            user_prompt(spec, item_id, domain, used_turn1, used_turn3)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Transcript-curated minimal pairs",
        "",
        f"writer: {model} · {len(records)} item(s)",
        "",
        "Turns 1 and 2 are identical. Turn 3 words are identical; only the tags change. Turn 4 is Speaker C.",
        "",
    ]
    current = None
    for record in records:
        if record["contrast"] != current:
            current = record["contrast"]
            lines += [f"## {record['pair_id']}. {current}", ""]
        spec = next(item for item in PAIRS if item["id"] == record["pair_id"])
        lines += [
            f"### {record['item_id']} · {record.get('domain', '')}",
            "",
            f"Turn 1 A: {record['turn_1']['text']}",
            f"Turn 2 B: {record['turn_2']['text']}",
            f"Turn 3 lexical: {record['turn_3_lexical']}",
            "",
            f"Turn 3 A · {spec['meaning_a']}: {record['turn_3_a']['text']}",
            f"Turn 3 B · {spec['meaning_b']}: {record['turn_3_b']['text']}",
            f"Turn 4 A · {spec['meaning_a']}: {record['turn_4_a']['text']}",
            f"Turn 4 B · {spec['meaning_b']}: {record['turn_4_b']['text']}",
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
    parser.add_argument("--n", type=int, default=1, help="items per pair × domain")
    parser.add_argument("--pair", action="append", default=[], help="restrict to ids, e.g. P1")
    parser.add_argument("--domain", action="append", default=[], help="restrict to these domains")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = PAIRS
    if args.pair:
        needles = [item.lower() for item in args.pair]
        specs = [
            spec
            for spec in PAIRS
            if any(n in spec["id"].lower() or n in spec["contrast"].lower() for n in needles)
        ]
        if not specs:
            raise SystemExit("no pair matched --pair")

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
    print(f"{len(specs)} pair(s) × {len(domains)} domain(s) × {args.n} → {len(jobs)} item(s)")

    if args.dry_run:
        used_turn1: list[str] = []
        used_turn3: list[str] = []
        for spec, domain, sample in jobs:
            item_id = f"{spec['id']}_{domain}_{sample:03d}"
            print("\n" + "=" * 72)
            print(f"{item_id} · {spec['contrast']} · {domain}")
            print("=" * 72)
            print(user_prompt(spec, item_id, domain, used_turn1, used_turn3))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}")
    records: list[dict] = []
    used_turn1 = []
    used_turn3 = []
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def write_outputs() -> None:
        payload = {
            "model": args.model,
            "effort": args.effort,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pairs": [spec["id"] for spec in specs],
            "domains": domains,
            "n_per_pair_domain": args.n,
            "results": records,
        }
        args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path = args.out.with_suffix(".md")
        ok = [record for record in records if "turn_3_a" in record]
        md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")

    for index, (spec, domain, sample) in enumerate(jobs, start=1):
        item_id = f"{spec['id']}_{domain}_{sample:03d}"
        print(f"[{index}/{len(jobs)}] {item_id} · {spec['contrast']}")
        try:
            record = generate_one(client, spec, item_id, domain, args, used_turn1, used_turn3)
            records.append(record)
            used_turn1.append(record["turn_1"]["text"])
            used_turn3.append(record["turn_3_lexical"])
            print(f"    T3: {record['turn_3_lexical']}")
            print(f"    C A: {record['turn_4_a']['text']}")
            print(f"    C B: {record['turn_4_b']['text']}")
        except Exception as exc:
            records.append(
                {
                    "item_id": item_id,
                    "pair_id": spec["id"],
                    "contrast": spec["contrast"],
                    "domain": domain,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"    failed: {exc}")
        write_outputs()

    failures = sum(1 for record in records if record.get("error"))
    print(f"\nwrote {args.out} and {args.out.with_suffix('.md')}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

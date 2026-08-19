"""Generate three-turn scripts where a vocalization foreshadows Turn 3 content.

The last utterance starts with a fixed non-speech formula. The gold
completion matches that vocalization's typical next-content type. One
alternative takes the opposite stance (reluctant → willing, protest → eager).

Usage:
    python predicting_content/generate.py
    python predicting_content/generate.py --vocalization groan --domain school
    python predicting_content/generate.py --dry-run
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
DEFAULT_OUT = HERE / "out" / "items.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000

VOCALIZATIONS = [
    {
        "id": "sigh",
        "label": "Sigh",
        "formula": "[sigh]",
        "foreshadow": "resignation, complaint, reluctant acceptance",
        "content_type": "fine…, complaint, closure",
        "example": "[sigh] I guess we can do it tomorrow.",
        "opposite_type": "willing, upbeat acceptance",
        "opposite_hint": "Same task as gold, but A is glad to do it. No complaint, no 'fine'.",
    },
    {
        "id": "groan",
        "label": "Groan",
        "formula": "[groan]",
        "foreshadow": "objection, annoyance, reluctance",
        "content_type": "rejection, protest, not again",
        "example": "[groan] Do we really have to redo this?",
        "opposite_type": "eager acceptance",
        "opposite_hint": "A wants the thing gold refused. Enthusiastic yes, not protest.",
    },
    {
        "id": "laugh",
        "label": "Laugh / chuckle",
        "formula": "[laugh]",
        "foreshadow": "joking, teasing, positive framing",
        "content_type": "joke, playful evaluation",
        "example": "[laugh] That might be the worst plan we've had.",
        "opposite_type": "earnest, unironic take",
        "opposite_hint": "Treat the situation seriously. No tease, no joke. Sincere concern or sincere praise.",
    },
    {
        "id": "hmm",
        "label": "Hmm",
        "formula": "Hmm...",
        "foreshadow": "consideration, uncertainty",
        "content_type": "tentative proposal, evaluation",
        "example": "Hmm... Maybe we should try the other route.",
        "opposite_type": "confident decision",
        "opposite_hint": "No hedging. A already knows what to do and states it firmly.",
    },
    {
        "id": "mmhm",
        "label": "Mm-hm / uh-huh",
        "formula": "Mm-hm...",
        "foreshadow": "engagement / acknowledgment",
        "content_type": "continuation, agreement",
        "example": "Mm-hm... Tell me what happened after that.",
        "opposite_type": "disengagement, shut down",
        "opposite_hint": "A does not want more of this talk. Cut it off; do not ask a follow-up.",
    },
    {
        "id": "scoff",
        "label": "Scoff / snort",
        "formula": "[scoff]",
        "foreshadow": "disbelief, rejection",
        "content_type": "disagreement, criticism",
        "example": "[scoff] You really think that's going to work?",
        "opposite_type": "enthusiastic endorsement",
        "opposite_hint": "A sincerely likes the plan gold criticized. Warm yes, not disbelief.",
    },
    {
        "id": "throat_clear",
        "label": "Throat clear",
        "formula": "[clears throat]",
        "foreshadow": "delicacy, awkwardness, preparation for difficult speech",
        "content_type": "correction, disagreement, sensitive topic",
        "example": "[clears throat] There's something we should discuss.",
        "opposite_type": "easy, nothing-is-wrong",
        "opposite_hint": "No sensitive correction. A is fine with the current plan and says so lightly.",
    },
    {
        "id": "exhale",
        "label": "Exhale",
        "formula": "[exhale]",
        "foreshadow": "relief / release",
        "content_type": "closure, positive resolution",
        "example": "[exhale] Okay, we're finally done.",
        "opposite_type": "still unresolved, not done",
        "opposite_hint": "The problem is not over. A is still stuck or anxious, not relieved.",
    },
    {
        "id": "yawn",
        "label": "Yawn",
        "formula": "[yawn]",
        "foreshadow": "fatigue / disengagement",
        "content_type": "ending interaction, postponement",
        "example": "[yawn] Maybe we should finish this tomorrow.",
        "opposite_type": "energized, keep going",
        "opposite_hint": "A wants to continue now. No postponement, no wrapping up.",
    },
    {
        "id": "shaky_breath",
        "label": "Whimper / shaky breath",
        "formula": "[shaky breath]",
        "foreshadow": "distress / vulnerability",
        "content_type": "disclosure, request for reassurance",
        "example": "[shaky breath] I don't think I can do this alone.",
        "opposite_type": "confident, I have this",
        "opposite_hint": "A is steady and capable. No fear, no bid for comfort.",
    },
]

DOMAINS = ["school", "work", "family"]

DOMAIN_HINTS = {
    "school": "Set it at school: classmates, a teacher, homework, a club, or campus life.",
    "work": "Set it at work: coworkers, a meeting, a manager, a client, or an office task.",
    "family": "Set it among family: parents, siblings, relatives, or something happening at home.",
}

TAG_RE = re.compile(r"\[[^\[\]]+\]")
NAMING_RE = re.compile(
    r"(?i)\b("
    r"that sounded like|i (?:sighed|groaned|laughed|yawned)|"
    r"your (?:sigh|groan|laugh|yawn)|"
    r"vocalization|benchmark|foreshadow"
    r")\b"
)

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string", "enum": ["A", "B"]},
        "text": {"type": "string"},
    },
    "required": ["speaker", "text"],
    "additionalProperties": False,
}

ALT_SCHEMA = {
    "type": "object",
    "properties": {
        "content_type": {"type": "string"},
        "text": {"type": "string"},
        "why_mismatch": {"type": "string"},
    },
    "required": ["content_type", "text", "why_mismatch"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_id": {"type": "string"},
        "vocalization_id": {"type": "string"},
        "vocalization": {"type": "string"},
        "formula": {"type": "string"},
        "domain": {"type": "string"},
        "foreshadow": {"type": "string"},
        "content_type": {"type": "string"},
        "transcript": {"type": "array", "items": TURN_SCHEMA},
        "gold": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "lexical": {"type": "string"},
            },
            "required": ["text", "lexical"],
            "additionalProperties": False,
        },
        "alternatives": {
            "type": "array",
            "items": ALT_SCHEMA,
        },
        "quality_check": {
            "type": "object",
            "properties": {
                "turn_3_starts_with_formula": {"type": "boolean"},
                "gold_matches_content_type": {"type": "boolean"},
                "alternatives_are_distinct": {"type": "boolean"},
                "setup_allows_multiple_continuations": {"type": "boolean"},
                "vocalization_not_named_in_speech": {"type": "boolean"},
            },
            "required": [
                "turn_3_starts_with_formula",
                "gold_matches_content_type",
                "alternatives_are_distinct",
                "setup_allows_multiple_continuations",
                "vocalization_not_named_in_speech",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "item_id",
        "vocalization_id",
        "vocalization",
        "formula",
        "domain",
        "foreshadow",
        "content_type",
        "transcript",
        "gold",
        "alternatives",
        "quality_check",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
You are generating benchmark items for whether a conversational system can use
a non-speech vocalization at the start of an utterance to predict the speaker's
upcoming lexical content.

TASK

Write one three-turn script in the supplied domain.

SPEAKERS

Two speakers, A and B.

- Turn 1: Speaker A. Spoken words only. No audio tags.
- Turn 2: Speaker B. Spoken words only. No audio tags.
- Turn 3: Speaker A. MUST begin with the supplied formula, then the gold sentence.

Turns 1 and 2 set a situation in which several next-content types could be
plausible if you ignore how Turn 3 starts. The vocalization is what makes the
gold completion the right one.

TURN 3

Turn 3 is one utterance: formula + gold lexical content.

- The formula must be copied EXACTLY, including brackets, dots, and spacing.
- Put a single space after a bracketed formula. Formulas that already end in
  "..." (Hmm..., Mm-hm...) are followed by a single space, then the sentence.
- Gold lexical content must match the supplied typical next-content type.
- Gold should sound like the table example's speech act, not a copy of it.
- Do not put any other audio tags in any turn.
- Do not name the vocalization in the spoken words (no "I sighed", "that laugh").

ALTERNATIVE

Also generate exactly one alternative Turn 3 completion.

It must be the OPPOSITE stance of gold, using the supplied opposite_type.

- Same formula prefix as gold.
- Same situation, flipped attitude or reasoning.
  Reluctant / unwilling accept → glad, willing accept.
  Protest / rejection → eager yes.
  Joke / tease → earnest, unironic.
  Tentative / uncertain → firm decision.
  Engaged follow-up → shut the topic down.
  Criticism / disbelief → sincere endorsement.
  Sensitive correction → nothing is wrong.
  Relieved closure → still unresolved.
  Postpone / stop → keep going now.
  Distressed bid for comfort → confident, I have this.
- Do not write a joke, a follow-up question, or a near-paraphrase of gold.
- The alternative must still make sense after Turns 1–2.

Do not reuse the table's example sentences. Invent a fresh situation.

OUTPUT

JSON only, matching the schema.

- transcript has exactly 3 turns, speakers A, B, A.
- gold.text is the full Turn 3 string (formula + lexical).
- gold.lexical is ONLY the words after the formula.
- transcript[2].text MUST equal gold.text.
- alternatives has exactly 1 object. alternatives[0].text is a full Turn 3
  string starting with the same formula.
- quality_check fields must all be true.
""".strip()


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "for", "at",
    "with", "we", "i", "you", "it", "this", "that", "is", "are", "be", "can",
    "will", "just", "so", "if", "do", "not", "no", "yes", "my", "our", "your",
    "me", "us", "i'll", "i'm", "we're", "that's", "there's",
}


def content_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z']+", text.lower())
        if tok not in STOPWORDS and len(tok) > 2
    }


def token_overlap(a: str, b: str) -> float:
    left, right = content_tokens(a), content_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def formula_ok(text: str, formula: str) -> bool:
    return text.startswith(formula)


def lexical_of(text: str, formula: str) -> str:
    if not text.startswith(formula):
        return text.strip()
    rest = text[len(formula) :].lstrip()
    return rest.strip()


def spoken_parts(record: dict, spec: dict) -> list[str]:
    formula = spec["formula"]
    parts = [record["transcript"][0]["text"], record["transcript"][1]["text"]]
    parts.append(lexical_of(record["gold"]["text"], formula))
    for alt in record.get("alternatives") or []:
        parts.append(lexical_of(alt.get("text", ""), formula))
    return parts


def validate(payload: dict, spec: dict, item_id: str, domain: str) -> list[str]:
    problems = []
    if payload.get("item_id") != item_id:
        problems.append(f"item_id {payload.get('item_id')!r} != {item_id!r}")
    if payload.get("vocalization_id") != spec["id"]:
        problems.append("vocalization_id mismatch")
    if payload.get("formula") != spec["formula"]:
        problems.append(f"formula {payload.get('formula')!r} != {spec['formula']!r}")
    if payload.get("domain") != domain:
        problems.append("domain mismatch")
    if payload.get("content_type") != spec["content_type"]:
        problems.append("content_type must be copied exactly")

    turns = payload.get("transcript") or []
    if len(turns) != 3:
        problems.append(f"need 3 turns, got {len(turns)}")
        return problems
    if [t.get("speaker") for t in turns] != ["A", "B", "A"]:
        problems.append("speakers must be A, B, A")

    formula = spec["formula"]
    gold = payload.get("gold") or {}
    gold_text = (gold.get("text") or "").strip()
    gold_lex = (gold.get("lexical") or "").strip()
    if turns[2].get("text", "").strip() != gold_text:
        problems.append("transcript turn 3 must equal gold.text")
    if not formula_ok(gold_text, formula):
        problems.append(f"gold.text must start with {formula!r}")
    if TAG_RE.search(turns[0]["text"]) or TAG_RE.search(turns[1]["text"]):
        problems.append("turns 1 and 2 must not contain audio tags")
    gold_tags = TAG_RE.findall(gold_text)
    if formula.startswith("[") and formula.endswith("]"):
        if gold_tags != [formula]:
            problems.append(f"turn 3 tags {gold_tags} != [{formula}]")
    elif gold_tags:
        problems.append(f"turn 3 has unexpected audio tags {gold_tags}")
    if not gold_lex:
        problems.append("gold.lexical is empty")
    elif gold_lex.lower() not in gold_text.lower():
        problems.append("gold.lexical must appear in gold.text")
    if lexical_of(gold_text, formula).lower() != gold_lex.lower():
        problems.append("gold.lexical must be the words after the formula")
    example_lex = lexical_of(spec["example"], formula).lower()
    if gold_lex.lower() == example_lex:
        problems.append("do not copy the table example")

    alts = payload.get("alternatives") or []
    if len(alts) != 1:
        problems.append(f"need 1 alternative, got {len(alts)}")
        return problems

    gold_norm = gold_lex.lower()
    gold_type = spec["content_type"].strip().lower()
    required = (spec.get("opposite_type") or "").strip().lower()
    alt = alts[0]
    text = (alt.get("text") or "").strip()
    lex = lexical_of(text, formula)
    ctype = (alt.get("content_type") or "").strip().lower()
    if not formula_ok(text, formula):
        problems.append(f"alternative must start with {formula!r}")
    if not lex:
        problems.append("alternative has empty lexical content")
    if lex.lower() == gold_norm:
        problems.append("alternative duplicates gold")
    if ctype == gold_type:
        problems.append("alternative content_type must differ from gold")
    if required and ctype != required:
        problems.append(f"alternative content_type must be {spec.get('opposite_type')!r}")

    for part in spoken_parts(payload, spec):
        # Allow the formula itself; flag naming in lexical speech.
        if NAMING_RE.search(part):
            problems.append(f"spoken words name a vocalization: {part[:80]!r}")
            break

    qc = payload.get("quality_check") or {}
    for key, value in qc.items():
        if value is not True:
            problems.append(f"quality_check.{key} is not true")
    return problems


def user_prompt(spec: dict, item_id: str, domain: str, used: list[str]) -> str:
    lines = [
        "Generate exactly one item.",
        "",
        f"item_id: {item_id}",
        f"vocalization_id: {spec['id']}",
        f"vocalization: {spec['label']}",
        f"formula: {spec['formula']}",
        f"domain: {domain}",
        DOMAIN_HINTS[domain],
        "Every turn should clearly belong to this domain.",
        "",
        f"Foreshadow: {spec['foreshadow']}",
        f"Gold content_type (copy exactly): {spec['content_type']}",
        f"Table example (do not copy): {spec['example']}",
        "",
        "Turn 3 MUST start with this exact formula:",
        spec["formula"],
        "",
        f"Opposite content_type (copy exactly): {spec['opposite_type']}",
        spec["opposite_hint"],
    ]
    if used:
        lines += ["", "Do not reuse these Turn 1 setups:"]
        lines += [f"- {text}" for text in used[-12:]]
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
                        "name": "predicting_content_item",
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
    used: list[str],
) -> dict:
    prompt = user_prompt(spec, item_id, domain, used)
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
            user_prompt(spec, item_id, domain, used)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Predicting next content from a vocalization",
        "",
        f"writer: {model} · {len(records)} item(s)",
        "",
        "Turn 3 starts with a non-speech formula. Gold matches that vocalization's",
        "typical next-content type. The alternative is the opposite stance.",
        "",
    ]
    current = None
    for record in records:
        voc = record["vocalization"]
        if voc != current:
            current = voc
            lines += [f"## {record['vocalization_id']} · {voc}", ""]
        t1, t2, t3 = record["transcript"]
        lines += [
            f"### {record['item_id']} · {record['domain']}",
            "",
            f"Gold type: {record['content_type']}",
            "",
            f"- A: {t1['text']}",
            f"- B: {t2['text']}",
            f"- A (gold): {t3['text']}",
            "",
            "Alternatives:",
            "",
        ]
        for alt in record["alternatives"]:
            lines.append(f"- {alt['text']}  — {alt['content_type']}")
        lines.append("")
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
    parser.add_argument("--n", type=int, default=1, help="items per vocalization × domain")
    parser.add_argument("--vocalization", action="append", default=[], help="restrict to ids, e.g. groan")
    parser.add_argument("--domain", action="append", default=[], help="restrict to these domains")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = VOCALIZATIONS
    if args.vocalization:
        needles = [item.lower() for item in args.vocalization]
        specs = [
            spec
            for spec in VOCALIZATIONS
            if any(n in spec["id"].lower() or n in spec["label"].lower() for n in needles)
        ]
        if not specs:
            raise SystemExit("no vocalization matched --vocalization")

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
    print(f"{len(specs)} vocalization(s) × {len(domains)} domain(s) × {args.n} → {len(jobs)} item(s)")

    if args.dry_run:
        used: list[str] = []
        for spec, domain, sample in jobs:
            item_id = f"{spec['id']}_{domain}_{sample:03d}"
            print("\n" + "=" * 72)
            print(f"{item_id} · {spec['label']} · {domain}")
            print("=" * 72)
            print(user_prompt(spec, item_id, domain, used))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}")
    records: list[dict] = []
    used = []

    for index, (spec, domain, sample) in enumerate(jobs, start=1):
        item_id = f"{spec['id']}_{domain}_{sample:03d}"
        print(f"[{index}/{len(jobs)}] {item_id} · {spec['label']}")
        try:
            record = generate_one(client, spec, item_id, domain, args, used)
            records.append(record)
            used.append(record["transcript"][0]["text"])
            print(f"    gold: {record['gold']['text']}")
            for alt in record["alternatives"]:
                print(f"    alt:  {alt['text']}")
        except Exception as exc:
            records.append(
                {
                    "item_id": item_id,
                    "vocalization_id": spec["id"],
                    "vocalization": spec["label"],
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
        "vocalizations": [spec["id"] for spec in specs],
        "domains": domains,
        "n_per_vocalization_domain": args.n,
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "gold" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

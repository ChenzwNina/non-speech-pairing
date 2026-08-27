"""Generate four-turn spoken dialogues with one embedded laughter function.

For each selected row in laughter_definitions.csv, the matching row in
function_profiles_compact.csv is attached so the writer knows who laughs, what
event the laugh attaches to, and what the laugh is doing. The model then writes
a two-speaker, four-turn conversation in which exactly one turn carries that
laughter, plus ElevenLabs v3 audio tags so the script can be sent to TTS.

Usage:
    python generate_transcript.py
    python generate_transcript.py --function "Marking irony"
    python generate_transcript.py --n 2 --out out/transcripts.json
    python generate_transcript.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
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
DEFINITIONS_CSV = HERE / "laughter_definitions.csv"
PROFILES_CSV = HERE / "function_profiles_compact.csv"
DEFAULT_OUT = HERE / "out" / "transcripts.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000

LAUGH_TAG_RE = re.compile(
    r"\[(?=[^\]]*(?:laugh|chuckl|giggl|wheez|belly laugh|cracking up))[^\]]+\]",
    re.IGNORECASE,
)
ANY_TAG_RE = re.compile(r"\[[^\[\]]+\]")


SYSTEM_PROMPT = """
You write short spoken dialogues for ElevenLabs v3 text-to-speech.

Write one four-turn conversation between two people, labeled A and B, in the
order A, B, A, B. Everyday English. One spoken sentence per turn. Invent a
fresh situation; do not reuse the taxonomy example.

Exactly one turn contains the target laughter function. Choose that turn from
the structural profile:
- laugher role "producer": the laughing speaker is performing the relevant act
  in that same turn.
- laugher role "recipient": the laugh responds to the partner's previous turn,
  so it cannot be turn 1.
- laugher role "either": pick whichever placement sounds more natural.

Satisfy the profile's trigger event, event focus, laughter action, and lexical
anchor. If a lexical anchor is required, put that wording in the laughing turn
or in the immediately preceding turn.

ElevenLabs v3 audio tags are square-bracket cues the model performs, not words
it speaks. Put them inline with the dialogue.

Rules for tags:
- One expression per pair of brackets. Write [warm] [laughs], never [warm, laughs].
- Tags describe voice only: emotion, delivery, or a human reaction.
- Place a tag just before the stretch of speech it colors, or just after a
  reaction that happens on its own.
- Every turn should have at least one delivery tag so TTS has a performance cue.
- Only the laughing turn may use a laugh reaction, such as [laughs], [chuckles],
  [giggles], [laughs harder], [starts laughing], [wheezing], or [stifling laughter].
- Match laugh color to the function: delighted or amused for enjoyment; dry or
  pointed for marking incongruity; gentle or hesitant for softening; warm or
  coaxing for benevolence; awkward or sheepish for smoothing; sympathetic for
  sympathy; sarcastic or ironic for irony; knowing for scare-quoting; uncertain
  for lexical editing; warm or fond for affiliation.
- Allowed extras: [sighs], [exhales], [whispers], [pause], ellipses for a beat,
  and CAPS for emphasis.
- Do not use visual tags ([grinning], [nodding]) or scene sound effects
  ([applause], [gunshot], [door slam]).
- Do not write haha / heh / hehe. The laugh tag is the laugh.

Return JSON only, matching the schema.
""".strip()


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "situation": {"type": "string"},
        "laughing_turn": {"type": "integer", "enum": [1, 2, 3, 4]},
        "turns": {
            "type": "array",
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
    },
    "required": ["situation", "laughing_turn", "turns"],
    "additionalProperties": False,
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing file: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]
    if not rows:
        raise SystemExit(f"{path} has no rows")
    return rows


def load_catalog(definitions_path: Path, profiles_path: Path) -> list[dict]:
    definitions = load_csv(definitions_path)
    profiles = {row["function"]: row for row in load_csv(profiles_path) if row.get("function")}
    catalog = []
    missing = []
    for row in definitions:
        name = row.get("function")
        if not name:
            continue
        profile = profiles.get(name)
        if not profile:
            missing.append(name)
            continue
        catalog.append({"definition": row, "profile": profile})
    if missing:
        raise SystemExit("no profile row for: " + ", ".join(missing))
    return catalog


def user_prompt(entry: dict, topic: str | None) -> str:
    definition = entry["definition"]
    profile = entry["profile"]
    lines = [
        "Write one four-turn dialogue for this laughter function.",
        "",
        f"Function: {definition['function']}",
        f"Laughable type: {definition['laughable_type']}",
        f"Definition: {definition['definition']}",
        f"Taxonomy example (do not copy): {definition['example']}",
        f"Why that example works: {definition['example_explanation']}",
        "",
        "How to realize this function:",
        f"- laugher role: {profile['laugher_role']}",
        f"- event initiator: {profile['event_initiator']}",
        f"- event focus: {profile['event_focus']}",
        f"- trigger event: {profile['trigger_event']}",
        f"- laughter action: {profile['laughter_action']}",
        f"- lexical anchor: {profile['lexical_anchor']}",
    ]
    if topic:
        lines.extend(["", f"Keep the situation in this setting: {topic}."])
    return "\n".join(lines)


def laugh_tags(text: str) -> list[str]:
    return LAUGH_TAG_RE.findall(text)


def validate(payload: dict) -> list[str]:
    problems = []
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) != 4:
        return ["need exactly four turns"]

    expected = ["A", "B", "A", "B"]
    laugh_turns = []
    for index, (turn, speaker) in enumerate(zip(turns, expected), start=1):
        if not isinstance(turn, dict):
            problems.append(f"turn {index} is not an object")
            continue
        if turn.get("speaker") != speaker:
            problems.append(f"turn {index} must be speaker {speaker}")
        text = turn.get("text") or ""
        if not text.strip():
            problems.append(f"turn {index} is empty")
        if not ANY_TAG_RE.search(text):
            problems.append(f"turn {index} has no audio tag")
        for tag in ANY_TAG_RE.findall(text):
            inner = tag[1:-1].strip()
            if "," in inner or ";" in inner or re.search(r"\band\b", inner, re.I):
                problems.append(f"turn {index} combines expressions in {tag}")
        if laugh_tags(text):
            laugh_turns.append(index)
        if re.search(r"(?i)(?<![a-z])(?:ha(?:ha)+|heh+|hehe+|lol)(?![a-z])", text):
            problems.append(f"turn {index} uses a written laugh instead of a laugh tag")

    if len(laugh_turns) != 1:
        problems.append(f"need laughter in exactly one turn, found {laugh_turns}")
    else:
        declared = payload.get("laughing_turn")
        if declared != laugh_turns[0]:
            problems.append(
                f"laughing_turn is {declared} but laugh tags are on turn {laugh_turns[0]}"
            )
        role = payload.get("_laugher_role", "")
        if role == "recipient" and laugh_turns[0] == 1:
            problems.append("recipient laughter cannot occur on turn 1")

    return problems


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
                        "name": "dialogue",
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


def generate_one(client: OpenAI, entry: dict, args: argparse.Namespace, topic: str | None) -> dict:
    prompt = user_prompt(entry, topic)
    last_problems: list[str] = []
    totals = {"input_tokens": 0, "output_tokens": 0}
    served_by = args.model

    for attempt in range(1, 4):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        payload["_laugher_role"] = entry["profile"]["laugher_role"].strip().lower()
        problems = validate(payload)
        if not problems:
            payload.pop("_laugher_role", None)
            laughing = payload["turns"][payload["laughing_turn"] - 1]
            return {
                "situation": payload["situation"],
                "laughing_turn": payload["laughing_turn"],
                "laughing_speaker": laughing["speaker"],
                "laugh_tags": laugh_tags(laughing["text"]),
                "turns": payload["turns"],
                "usage": totals,
                "served_by": served_by,
                "attempts": attempt,
            }
        last_problems = problems
        prompt = (
            user_prompt(entry, topic)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        f"# Laughter transcripts",
        "",
        f"writer: {model} · {len(records)} dialogue(s)",
        "",
    ]
    current_function = None
    for record in records:
        if record["function"] != current_function:
            current_function = record["function"]
            lines += [f"## {current_function}", ""]
        heading = record.get("topic") or record["situation"]
        lines.append(f"### {heading}")
        lines.append("")
        lines.append(f"_{record['situation']}_")
        lines.append("")
        lines.append(
            f"Laughter: turn {record['laughing_turn']} "
            f"({record['laughing_speaker']}) "
            + " ".join(record["laugh_tags"])
        )
        lines.append("")
        for turn in record["turns"]:
            lines.append(f"- {turn['speaker']}: {turn['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definitions", type=Path, default=DEFINITIONS_CSV)
    parser.add_argument("--profiles", type=Path, default=PROFILES_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort",
        default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument(
        "--function",
        action="append",
        default=[],
        help="substring match on function name; repeatable",
    )
    parser.add_argument("--topic", help="optional setting constraint, e.g. kitchen")
    parser.add_argument("--n", type=int, default=1, help="dialogues per function")
    parser.add_argument("--limit", type=int, help="stop after N dialogues")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = load_catalog(args.definitions, args.profiles)

    if args.function:
        needles = [item.lower() for item in args.function]
        catalog = [
            entry
            for entry in catalog
            if any(needle in entry["definition"]["function"].lower() for needle in needles)
        ]
        if not catalog:
            raise SystemExit("no function matched --function")

    jobs = []
    for entry in catalog:
        for sample in range(1, args.n + 1):
            jobs.append((entry, sample))
    if args.limit:
        jobs = jobs[: args.limit]

    print(f"{len(catalog)} function(s) × {args.n} → {len(jobs)} dialogue(s)")

    if args.dry_run:
        for entry, sample in jobs:
            print("\n" + "=" * 72)
            print(f"{entry['definition']['function']}  sample {sample}")
            print("=" * 72)
            print(user_prompt(entry, args.topic))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}")

    records: list[dict] = []
    for index, (entry, sample) in enumerate(jobs, start=1):
        name = entry["definition"]["function"]
        print(f"[{index}/{len(jobs)}] {name}" + (f" #{sample}" if args.n > 1 else ""))
        try:
            generated = generate_one(client, entry, args, args.topic)
            record = {
                "id": f"{index:03d}",
                "function": name,
                "laughable_type": entry["definition"]["laughable_type"],
                "profile": {
                    key: entry["profile"][key]
                    for key in (
                        "laugher_role",
                        "event_initiator",
                        "event_focus",
                        "trigger_event",
                        "laughter_action",
                        "lexical_anchor",
                    )
                },
                "topic": args.topic,
                "sample": sample,
                **generated,
            }
            records.append(record)
            laugh_turn = record["turns"][record["laughing_turn"] - 1]
            print(f"    turn {record['laughing_turn']} {laugh_turn['speaker']}: {laugh_turn['text']}")
        except Exception as exc:
            records.append(
                {
                    "id": f"{index:03d}",
                    "function": name,
                    "topic": args.topic,
                    "sample": sample,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"    failed: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "turns" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")

    failures = sum(1 for record in records if record.get("error"))
    print(f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

"""Generate four-turn dialogues for identifying a laughter function.

Each dialogue targets one of six functions in one of four themes
(school, work, family, health). Default run: 4 themes × 6 functions.

Usage:
    python laughter_identify/generate.py
    python laughter_identify/generate.py --theme school --function irony
    python laughter_identify/generate.py --dry-run
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
REPO = HERE.parent.parent
DEFINITIONS_CSV = REPO / "laughter_definitions.csv"
PROFILES_CSV = REPO / "function_profiles_compact.csv"
DEFAULT_OUT = HERE / "out" / "dialogues.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000

TARGET_FUNCTIONS = [
    "Show enjoyment of incongruity",
    "Softening / trouble-telling",
    "Benevolence induction",
    "Smoothing",
    "Show sympathy",
    "Marking irony",
]

THEMES = ["school", "work", "family", "health"]

THEME_HINTS = {
    "school": "Set it at school: classmates, a teacher, homework, a club, or campus life.",
    "work": "Set it at work: coworkers, a meeting, a manager, a client, or an office task.",
    "family": "Set it among family: parents, siblings, relatives, or something happening at home.",
    "health": "Set it around health: a clinic visit, recovery, sleep, a checkup, or how someone is feeling. Keep it everyday, not a medical emergency.",
}

FUNCTION_CONSTRAINTS = {
    "Show enjoyment of incongruity": """
Hard requirement for this function:
The laugh DISPLAYS ENJOYMENT of a pleasant clash (joke, pun, goofy wording,
witty mismatch with what people normally expect). A listener should hear
appreciation, not a dry flag, not sympathy, not a request.
The clash must be recoverable as funny from the line itself.
Do not put the laugh on an ironic proposition whose point is "do not take
this literally" — that is Marking irony. Do not use sarcastic, dry, or wry
as the laugh adjective. Do not restage a lecturer/audience joke.
""".strip(),
    "Softening / trouble-telling": """
Hard requirement for this function:
The laughing speaker's turn must itself BE the delicate act aimed at the
partner, or painful talk about the self. Prefer criticism / dissent / refusal
aimed at B, in the spirit of "you didn't put anything in the bathroom".
The laugh cushions that act. Do not use "I forgot / it's missing / I didn't
finish" unless the point is painful self-disclosure, not a project update.
Do not criticize a third party through B ("tell Dad that Grandpa shouldn't
drive") unless B is the person being faulted. Do not put a request or favor
in the laughing turn.
""".strip(),
    "Benevolence induction": """
Hard requirement for this function:
Follow the DEFINITION, not the taxonomy example. The CSV example is John
admitting "other things occupying me" with no ask; that is Softening-like
self-disclosure. Do not restage an interview admission.
The laughing turn must contain a request, favor, suggestion, or opinion that
B could refuse (could you / would you / can we / would it be okay if).
The laugh asks B not to judge the ask harshly. A small supporting confession
is allowed only if the REQUEST is still the main act.
Do not criticize the partner. Do not merely admit a mistake. Do not hide the
ask as smoothing ("I can do pasta, but could Dad take dessert?").
""".strip(),
    "Smoothing": """
Hard requirement for this function:
Awkwardness lives in the INTERACTION, not in a face-threat or a favor.
Nobody criticizes, nobody asks for help, nobody tells a joke to be enjoyed.
The laugh lets talk continue after embarrassment, a boast-trap, an unexpected
reply, or a socially sticky pause.
Do NOT default to compliment-deflection (the taxonomy example). Invent a
different awkward shape at least as often as praise. Deflecting praise is
allowed at most as one pattern among others, never the only move.
Forbidden in the laughing turn: a favor ("could you / could Dad / can you
spare"), partner criticism, a status-update confession, or treating a mishap
as comedy.
""".strip(),
    "Show sympathy": """
Hard requirement for this function:
Recipient laugh only: it ANSWERS the partner's previous turn (never turn 1).
That previous turn must show social discomfort — embarrassment, a
face-sensitive admission, awkward weakness — not a joke and not mere warmth.
The laugh reassures: I understand, I am not judging you.
Do not treat the mishap as entertaining ([amused] / [delighted] is wrong).
Do not use the skeleton "A confesses a goof → B [warm] hehe, that could
happen to anyone" as the only shape. Vary who is uncomfortable and what the
discomfort is (awkward request, compliment they cannot take, reluctant
admission). There must be social incongruity in the partner's turn; a
supportive pat with no discomfort is Affiliation, not sympathy.
""".strip(),
    "Marking irony": """
Hard requirement for this function:
The LAUGHER produces (or is about to produce) a proposition whose LITERAL
reading is not the intended stance. The laugh flags "do not take this
literally." Canonical shape: dry/sarcastic laugh on "history ended with
Ronald Reagan."
Producer only: do not be the audience enjoying someone else's sarcasm
(that is Show enjoyment, taxonomy Ex. 10). Do not use amused/delighted/
playful as the laugh adjective.
A listener who took the line literally should get the opposite evaluation
from what the speaker means. Do not tell a joke whose point is shared
enjoyment of a clash; do not cushion criticism; do not ask a favor.
""".strip(),
}

LAUGH_ADJECTIVES = {
    "Show enjoyment of incongruity": "delighted, amused, playful",
    "Softening / trouble-telling": "awkward, apologetic, uneasy",
    "Benevolence induction": "sheepish, hopeful, coaxing",
    "Smoothing": "embarrassed, awkward, light",
    "Show sympathy": "warm, kind, understanding",
    "Marking irony": "sarcastic, dry, wry",
}

WRITTEN_LAUGH_RE = re.compile(
    r"(?i)(?<![a-z])(?:ha(?:ha)+|heh(?:e|eh)*|hehe+)(?![a-z])"
)
LAUGH_TAG_RE = re.compile(
    r"\[(?=[^\]]*(?:laugh|chuckl|giggl|wheez))[^\]]+\]",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"\[[^\[\]]+\]")
REQUEST_RE = re.compile(
    r"(?i)\b(?:could (?:you|we|he|she|dad|mom|mum)|would you|can you|"
    r"spare \w+ minutes|would it be okay|do you (?:mind|think you could))\b"
)

SYSTEM_PROMPT = """
You write short spoken dialogues for ElevenLabs v3. The dialogue will later be
used to test whether a listener can tell what a laugh is doing.

Write ONE four-turn conversation between A and B (A, B, A, B). Everyday
speech. The conversation MUST be about the supplied theme (school, work,
family, or health). Invent a fresh situation inside that theme; do not copy
the taxonomy example.

Exactly one laugh belongs in the dialogue. That laugh must perform the target
function supplied by the user. Blend it into the talk so it sounds like
something people would actually do, not a caption. Place it on the speaker
and turn that the structural profile calls for:
- producer: the person producing the delicate / ironic / requesting act laughs
  in that same turn
- recipient: the laugh answers the partner's previous turn (never turn 1)
- either: pick whichever placement is more natural

Satisfy the profile: trigger event, event focus, laughter action, and lexical
anchor. If a lexical anchor is required, put that wording in the laughing turn
or the turn just before it.

SEPARATE FUNCTIONS BY WHAT THE LAUGHING SPEAKER IS DOING
Do not restage the taxonomy example. Invent a fresh situation in the theme.

Pleasant vs pragmatic clash:
- Show enjoyment of incongruity: laugh APPRECIATES a witty/pleasant clash
  (joke, pun, goofy behaviour). Adjective: delighted / amused / playful.
  NOT a dry flag that a line is non-literal.
- Marking irony: the laugher PRODUCES a non-literal proposition and flags
  "do not take this literally." Adjective: sarcastic / dry / wry.
  NOT the audience enjoying someone else's sarcasm.

Three social functions that can all sound like a small awkward hehe:
- Softening / trouble-telling: the laugher does something TO the partner
  that has face cost, or discloses something painful about themselves.
  Criticism, disagreement, refusal, inconvenient answer, or painful
  self-disclosure. Canonical: "you left the bathroom empty [uneasy] hehe".
  NOT a project status update. NOT a request. NOT deflecting a compliment.
- Benevolence induction: the laugher ASKS for something B could refuse
  (favor, suggestion, opinion, permission). The laugh asks for leniency on
  the ask. Canonical: "could you cover my shift, [sheepish] hehe".
  Ignore the taxonomy interview-admission example; that has no request.
  NOT criticism. NOT compliment-deflection. NOT admit-without-asking.
- Smoothing: nobody criticizes and nobody asks a favor. Mild awkwardness in
  the interaction (embarrassment, unexpected reply, sticky pause) and the
  laugh lets talk continue. Do not always deflect a compliment.
  NOT "could you help me". NOT "you did this wrong". NOT laughing at a joke.

Recipient vs producer:
- Show sympathy: recipient laugh at the partner's social discomfort,
  reassuring them they are not being judged. Adjective: warm / kind /
  understanding. The previous turn must contain that discomfort.
  NOT enjoying the mishap as comedy. NOT affiliation with no awkwardness.

HOW TO WRITE THE LAUGH
Do not use laugh tags such as [laughs], [chuckles], [nervous laugh], or
[big laugh]. TTS performs those poorly.

Break the laugh into an adjective tag plus a laugh word:
    [delighted] haha
    [awkward] hehe
    [sheepish] heh
    [warm] hehe
    [sarcastic] haha

The adjective should describe how the laugh itself sounds, matching the
function. You may stack a second delivery tag around the same line:
    [uneasy] hehe, [softly] you didn't put anything in the bathroom
    [sarcastic] haha... history ended right there
    [delighted] haha, [excited] it told me I had reached my emotional destination

Use ... for a beat or hesitation when it helps.

AUDIO TAGS ON EVERY TURN
Use tags freely so the whole conversation has a natural atmosphere, not only
the laugh line: [curious], [tired], [worried], [happy], [annoyed], [whispering],
[sighs], [surprised], [warmly], [playful], [hesitant]. A line may have more
than one tag. Tags describe voice, not faces or blocking.

Do not add extra haha/hehe on other turns. One written laugh only.

Keep each turn to one spoken sentence. No narrator.

Return JSON only.
""".strip()


TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string", "enum": ["A", "B"]},
        "text": {"type": "string"},
    },
    "required": ["speaker", "text"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "situation": {"type": "string"},
        "laughing_turn": {"type": "integer", "enum": [1, 2, 3, 4]},
        "laugh_adjective": {
            "type": "string",
            "description": "The adjective used in the laugh tag, without brackets.",
        },
        "laugh_word": {
            "type": "string",
            "description": "The written laugh, e.g. haha or hehe.",
        },
        "turns": {"type": "array", "items": TURN_SCHEMA},
    },
    "required": ["situation", "laughing_turn", "laugh_adjective", "laugh_word", "turns"],
    "additionalProperties": False,
}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def load_catalog() -> dict[str, dict]:
    definitions = {row["function"]: row for row in load_csv(DEFINITIONS_CSV)}
    profiles = {row["function"]: row for row in load_csv(PROFILES_CSV)}
    catalog = {}
    missing = []
    for name in TARGET_FUNCTIONS:
        if name not in definitions or name not in profiles:
            missing.append(name)
            continue
        catalog[name] = {"definition": definitions[name], "profile": profiles[name]}
    if missing:
        raise SystemExit("missing CSV rows for: " + ", ".join(missing))
    return catalog


def user_prompt(name: str, entry: dict, theme: str) -> str:
    definition = entry["definition"]
    profile = entry["profile"]
    adjectives = LAUGH_ADJECTIVES[name]
    lines = [
            "Write one four-turn dialogue whose laugh performs this function.",
            "",
            f"Theme: {theme}",
            THEME_HINTS[theme],
            "Every turn should clearly belong to this theme.",
            "",
            f"Function: {definition['function']}",
            f"Laughable type: {definition['laughable_type']}",
            f"Definition: {definition['definition']}",
            f"Taxonomy example (meaning only; do not restage): {definition['example']}",
            f"Why that example works: {definition['example_explanation']}",
            "Invent a new social shape in the theme. If the example is vivid "
            "(lecturer joke, bathroom criticism, interview admission, compliment "
            "deflection, Reagan irony), do not reuse that scene.",
            "",
            "How to realize this function:",
            f"- laugher role: {profile['laugher_role']}",
            f"- event initiator: {profile['event_initiator']}",
            f"- event focus: {profile['event_focus']}",
            f"- trigger event: {profile['trigger_event']}",
            f"- laughter action: {profile['laughter_action']}",
            f"- lexical anchor: {profile['lexical_anchor']}",
            "",
            f"Laugh adjective ideas: {adjectives}",
            "Write the laugh as [adjective] plus haha/hehe/heh, not as a laugh tag.",
        ]
    extra = FUNCTION_CONSTRAINTS.get(name)
    if extra:
        lines.extend(["", extra])
    return "\n".join(lines)


def validate(payload: dict, entry: dict) -> list[str]:
    problems = []
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) != 4:
        return ["need exactly four turns"]
    expected = ["A", "B", "A", "B"]
    laugh_turns = []
    for index, (turn, speaker) in enumerate(zip(turns, expected), start=1):
        if turn.get("speaker") != speaker:
            problems.append(f"turn {index} must be speaker {speaker}")
        text = turn.get("text") or ""
        if not TAG_RE.search(text):
            problems.append(f"turn {index} has no audio tag")
        if LAUGH_TAG_RE.search(text):
            problems.append(
                f"turn {index} uses a laugh tag; write [adjective] haha/hehe instead"
            )
        laughs = WRITTEN_LAUGH_RE.findall(text)
        if laughs:
            laugh_turns.append(index)
    if laugh_turns != [payload.get("laughing_turn")]:
        problems.append(
            f"laughing_turn is {payload.get('laughing_turn')} but written laughs "
            f"are on turns {laugh_turns}"
        )
    if len(laugh_turns) != 1:
        problems.append(f"need exactly one written laugh, found on {laugh_turns}")
    else:
        laugh_text = turns[laugh_turns[0] - 1].get("text") or ""
        adjective = (payload.get("laugh_adjective") or "").strip().lower()
        word = (payload.get("laugh_word") or "").strip().lower()
        if adjective and f"[{adjective}]" not in laugh_text.lower():
            problems.append(
                f"laugh_adjective [{adjective}] is missing from the laughing turn"
            )
        if word and word.lower() not in laugh_text.lower():
            problems.append(f"laugh_word {word!r} is missing from the laughing turn")
        allowed = {
            item.strip().lower()
            for item in LAUGH_ADJECTIVES[entry["definition"]["function"]].split(",")
        }
        if adjective and adjective not in allowed:
            problems.append(
                f"laugh_adjective {adjective!r} is not in {sorted(allowed)} "
                f"for {entry['definition']['function']}"
            )
        role = (entry["profile"].get("laugher_role") or "").strip().lower()
        if role == "recipient" and laugh_turns[0] == 1:
            problems.append("recipient laughter cannot occur on turn 1")
        function = entry["definition"]["function"]
        has_request = bool(REQUEST_RE.search(laugh_text))
        if function == "Benevolence induction" and not has_request:
            problems.append(
                "benevolence laughing turn must contain a request or favor "
                "(could you / would you / can you / can we)"
            )
        if function in {"Softening / trouble-telling", "Smoothing"} and has_request:
            problems.append(
                f"{function} laughing turn must not contain a request or favor"
            )
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
                        "name": "identify_dialogue",
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
    client: OpenAI, name: str, entry: dict, theme: str, args: argparse.Namespace
) -> dict:
    prompt = user_prompt(name, entry, theme)
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    served_by = args.model

    for attempt in range(1, 4):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, entry)
        if not problems:
            laugh_turn = payload["turns"][payload["laughing_turn"] - 1]
            return {
                "situation": payload["situation"],
                "laughing_turn": payload["laughing_turn"],
                "laughing_speaker": laugh_turn["speaker"],
                "laugh_adjective": payload["laugh_adjective"],
                "laugh_word": payload["laugh_word"],
                "turns": payload["turns"],
                "usage": totals,
                "served_by": served_by,
                "attempts": attempt,
            }
        last_problems = problems
        prompt = (
            user_prompt(name, entry, theme)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Laughter identify dialogues",
        "",
        f"writer: {model} · {len(records)} dialogue(s) · themes: {', '.join(THEMES)}",
        "",
        "Each four-turn dialogue has one laugh written as [adjective] plus a laugh word.",
        "",
    ]
    current = None
    for record in records:
        if record["function"] != current:
            current = record["function"]
            lines += [f"## {current}", ""]
        lines += [
            f"### {record['theme']} — {record['situation']}",
            "",
            f"Laugh: turn {record['laughing_turn']} ({record['laughing_speaker']}) "
            f"[{record['laugh_adjective']}] {record['laugh_word']}",
            "",
        ]
        for turn in record["turns"]:
            lines.append(f"- {turn['speaker']}: {turn['text']}")
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
    parser.add_argument("--n", type=int, default=1, help="dialogues per theme × function")
    parser.add_argument("--theme", action="append", default=[], help="restrict to these themes")
    parser.add_argument("--function", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = load_catalog()
    names = TARGET_FUNCTIONS
    if args.function:
        needles = [item.lower() for item in args.function]
        names = [name for name in names if any(n in name.lower() for n in needles)]
        if not names:
            raise SystemExit("no function matched --function")

    themes = THEMES
    if args.theme:
        needles = [item.lower() for item in args.theme]
        themes = [theme for theme in THEMES if any(n in theme for n in needles)]
        if not themes:
            raise SystemExit("no theme matched --theme")

    jobs = [
        (theme, name, sample)
        for theme in themes
        for name in names
        for sample in range(1, args.n + 1)
    ]
    print(f"{len(themes)} theme(s) × {len(names)} function(s) × {args.n} → {len(jobs)} dialogue(s)")

    if args.dry_run:
        for theme, name, sample in jobs:
            print("\n" + "=" * 72)
            print(f"{theme} · {name}  sample {sample}")
            print("=" * 72)
            print(user_prompt(name, catalog[name], theme))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}")
    records: list[dict] = []

    for index, (theme, name, sample) in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {theme} · {name}" + (f" #{sample}" if args.n > 1 else ""))
        try:
            generated = generate_one(client, name, catalog[name], theme, args)
            record = {
                "id": f"{index:03d}",
                "theme": theme,
                "function": name,
                "laughable_type": catalog[name]["definition"]["laughable_type"],
                "profile": {
                    key: catalog[name]["profile"][key]
                    for key in (
                        "laugher_role",
                        "event_initiator",
                        "event_focus",
                        "trigger_event",
                        "laughter_action",
                        "lexical_anchor",
                    )
                },
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
                    "theme": theme,
                    "function": name,
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
        "functions": names,
        "themes": themes,
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

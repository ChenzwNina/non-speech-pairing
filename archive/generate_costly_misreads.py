"""Ask gpt-5.6-terra for dialogues where misreading a laugh is socially costly.

v4: turns 1-3 keep identical spoken words; only tags (and ...) may change.
Laughs are written out (hehe / haha) next to emotion tags, not [nervous laugh].

Usage:
    python generate_costly_misreads.py
    python generate_costly_misreads.py --out out/costly_misreads_v4.json
    python generate_costly_misreads.py --dry-run
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
DEFAULT_OUT = HERE / "out" / "costly_misreads_v4.json"
MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 12000
N_ITEMS = 10
VERSION_LABEL = "v4"

PATTERNS = [
    "laughing with someone vs laughing at them",
    "irony or sarcasm vs sincere meaning",
    "nonliteral scare-quoted wording vs literal",
    "a real request vs treated as a gag",
    "genuine celebration vs hollow or unwanted news",
    "playful flirt vs a boundary was crossed",
    "dark coping humor vs please stop I am not okay",
    "warm affiliation vs brushing off something still raw",
    "affectionate teasing vs the target is actually hurt",
    "in-joke or conspiracy vs a serious accusation",
    "relief after a scare vs still frightened",
    "self-softening a criticism vs a real attack",
    "shared amusement vs distress that needs care",
]

LAUGH_TAG_RE = re.compile(
    r"\[(?=[^\]]*(?:laugh|chuckl|giggl|wheez))[^\]]+\]",
    re.IGNORECASE,
)
WRITTEN_LAUGH_RE = re.compile(
    r"(?i)(?<![a-z])(?:ha(?:ha)+|heh(?:e|eh)*|hehe+)(?![a-z])"
)
WEAK_TAG_RE = re.compile(
    r"\[(?:strained|flat|gentle|wincing|knowing|matter-of-fact|deadpan|nervous laugh)\]",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"\[[^\[\]]+\]")


def tags_in(text: str) -> list[str]:
    return [tag.lower() for tag in TAG_RE.findall(text or "")]


def spoken_words(text: str) -> str:
    """Words outside audio tags, ignoring ellipses used as hesitation."""
    text = TAG_RE.sub(" ", text or "")
    text = text.replace("...", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip().lower()


SYSTEM_PROMPT = """
You write short spoken dialogues for studying laughter, meant to be read by
ElevenLabs v3 TTS.

The point is not "there was a laugh." The point is that the laugh, plus the
atmosphere around it, decides what kind of moment this is. Speaker C answers
from that atmosphere. If C takes the wrong reading, the reply should be a
clearly inappropriate social move. Make the two vibes OBVIOUS: stack tags,
use ..., and write the laugh in letters so TTS can perform it.

SHAPE OF EVERY TRANSCRIPT
Exactly four turns:
    Turn 1: speaker A
    Turn 2: speaker B
    Turn 3: speaker A or B  <- the laughter utterance, second from last
    Turn 4: speaker C       <- responds to the laugh and the overall vibe

IDENTICAL WORDS ON TURNS 1-3
For each pair, turns 1, 2, and 3 must use the EXACT same spoken words in both
versions. Only square-bracket audio tags, and optional ..., may differ.
Do not add, drop, or swap any word outside the tags.
Turn 4 (C) MUST change.

HOW TO WRITE LAUGHS
Do NOT use laugh tags such as [nervous laugh], [big laugh], [chuckles],
[laughs], or [sympathetic laugh]. TTS does not perform those well.

Write the laugh as letters, then color it with emotion tags. A sentence may
have more than one tag. Two working recipes:

1. Emotion tag + written laugh:
       [delighted] haha
       [very nervous] hehe
       [sarcastic] heh
2. Written laugh, then another tag on the next words:
       [very nervous] hehe, [hesitant] it has a window
       [excited] haha... [happy] I was this close

Use ... for hesitation, trailing off, or delayed punch. The dramatic version
can add ... even if the other version does not; do not change the words.

SEED PATTERN (do not copy the train story)
Same letters on turns 1-3, including the laugh spelling:
    A: [excited] I ran all the way and still missed it.
    B: [amused] The doors closed right in front of you?
    A: [delighted] haha, [happy] I was this close.
    C: [excited] That is so you.
versus
    A: [worried] I ran all the way and still missed it.
    B: [worried] The doors closed right in front of you?
    A: [very nervous] haha... [hesitant] I was this close.
    C: [sad] I'm sorry. Want me to wait with you?

Use "shared amusement vs distress that needs care" at most ONCE.

PATTERN DIVERSITY IS THE MAIN REQUIREMENT
Each of the 10 pairs must use a DIFFERENT `pattern`. Do not write ten
funny-anecdote-vs-crisis stories. Change what the laugh is doing. C's wrong
move is not always "don't joke about pain." Sometimes C should not
congratulate, join the roast, take it literally, treat a request as a bit,
keep flirting, or keep a secret.

TASK
Write 10 contrastive pairs, one per chosen pattern.
- Turns 1-3: identical spoken words; different tags / ... to paint atmosphere.
- Turn 3 in BOTH versions contains a written laugh (haha / hehe / heh).
- The laugh letters must match across versions (both haha, or both hehe).
- Stack tags when it helps. Make the two atmospheres loud and distinct.
- Turn 4 MUST change.

AUDIO TAGS
Concrete emotion and delivery only:
    [very nervous] [hesitant] [worried] [sad] [scared] [disappointed]
    [excited] [delighted] [happy] [amused] [sarcastic] [annoyed]
    [surprised] [curious] [tired] [angry] [whispering] [sighs]
    [warmly] [softly] [exhales] [crying] [playful]

Do NOT use: [strained] [flat] [gentle] [wincing] [knowing]
[matter-of-fact] [deadpan] or any tag containing laugh / chuckle / giggle.

Every turn needs at least one tag. Keep lines short and spoken. No narrator.

Return JSON only.
""".strip()


USER_PROMPT = f"""
Write {N_ITEMS} contrastive transcript pairs. Each pair must use a different
pattern from this list (pick 10, all distinct):
{chr(10).join(f"- {p}" for p in PATTERNS)}

Four turns: A, B, written laugh on turn 3 (haha/hehe plus emotion tags), then C.
Turns 1-3 must have identical words outside audio tags. Tags and ... may differ
and should make the two vibes obvious. Do not use [nervous laugh] or [chuckles].
Use shared amusement vs distress at most once.
""".strip()


TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string", "enum": ["A", "B", "C"]},
        "text": {"type": "string"},
    },
    "required": ["speaker", "text"],
    "additionalProperties": False,
}

VERSION_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {
            "type": "string",
            "description": "Short name for this reading, e.g. funny story among friends.",
        },
        "what_the_laugh_is_doing": {"type": "string"},
        "correct_next_move": {
            "type": "string",
            "description": "What speaker C should do in the last turn.",
        },
        "turns": {"type": "array", "items": TURN_SCHEMA},
    },
    "required": ["label", "what_the_laugh_is_doing", "correct_next_move", "turns"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "pattern": {
                        "type": "string",
                        "enum": PATTERNS,
                        "description": "Contrast family. Each item must use a different one.",
                    },
                    "setting": {"type": "string"},
                    "relationship": {"type": "string"},
                    "contrast": {
                        "type": "string",
                        "description": "The two social acts being distinguished.",
                    },
                    "cost_of_misread": {
                        "type": "string",
                        "description": "What goes badly wrong if C answers as if it were the other version.",
                    },
                    "version_1": VERSION_SCHEMA,
                    "version_2": VERSION_SCHEMA,
                },
                "required": [
                    "title",
                    "pattern",
                    "setting",
                    "relationship",
                    "contrast",
                    "cost_of_misread",
                    "version_1",
                    "version_2",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def validate(payload: dict) -> list[str]:
    problems = []
    items = payload.get("items")
    if not isinstance(items, list):
        return ["items must be a list"]
    if len(items) != N_ITEMS:
        problems.append(f"need {N_ITEMS} items, got {len(items)}")

    patterns_used = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"item {i} is not an object")
            continue
        pattern = item.get("pattern") or ""
        patterns_used.append(pattern)
        c_lines = []
        v1_turns = (item.get("version_1") or {}).get("turns") or []
        v2_turns = (item.get("version_2") or {}).get("turns") or []
        if isinstance(v1_turns, list) and isinstance(v2_turns, list) and len(v1_turns) == 4 and len(v2_turns) == 4:
            same_tags = 0
            for t in range(3):
                t1 = v1_turns[t].get("text") if isinstance(v1_turns[t], dict) else ""
                t2 = v2_turns[t].get("text") if isinstance(v2_turns[t], dict) else ""
                if spoken_words(t1) != spoken_words(t2):
                    problems.append(
                        f"item {i} turn {t + 1} spoken words differ: "
                        f"{spoken_words(t1)!r} vs {spoken_words(t2)!r}"
                    )
                if tags_in(t1) == tags_in(t2):
                    same_tags += 1
            if same_tags >= 2:
                problems.append(
                    f"item {i} needs different atmosphere tags on turns 1-3; "
                    f"{same_tags} of those turns reuse the same tags"
                )
            laughs_1 = WRITTEN_LAUGH_RE.findall(
                v1_turns[2].get("text") if isinstance(v1_turns[2], dict) else ""
            )
            laughs_2 = WRITTEN_LAUGH_RE.findall(
                v2_turns[2].get("text") if isinstance(v2_turns[2], dict) else ""
            )
            if laughs_1 and laughs_2 and [x.lower() for x in laughs_1] != [x.lower() for x in laughs_2]:
                problems.append(
                    f"item {i} turn 3 laugh letters must match across versions "
                    f"({laughs_1} vs {laughs_2})"
                )
        for key in ("version_1", "version_2"):
            version = item.get(key) or {}
            turns = version.get("turns")
            if not isinstance(turns, list) or len(turns) != 4:
                problems.append(f"item {i} {key} needs exactly 4 turns")
                continue
            speakers = [turn.get("speaker") for turn in turns]
            if speakers[:2] != ["A", "B"]:
                problems.append(f"item {i} {key} must start A then B")
            if speakers[2] not in ("A", "B"):
                problems.append(f"item {i} {key} turn 3 must be A or B")
            if speakers[3] != "C":
                problems.append(f"item {i} {key} last turn must be C")
            if speakers[2] == "C":
                problems.append(f"item {i} {key} diagnostic laugh cannot be on C")

            turn3 = turns[2].get("text") or ""
            if not WRITTEN_LAUGH_RE.search(turn3):
                problems.append(
                    f"item {i} {key} turn 3 must contain a written laugh such as haha or hehe"
                )

            for t, turn in enumerate(turns, start=1):
                text = turn.get("text") or ""
                if not TAG_RE.search(text):
                    problems.append(f"item {i} {key} turn {t} has no audio tag")
                laugh_tags = LAUGH_TAG_RE.findall(text)
                if laugh_tags:
                    problems.append(
                        f"item {i} {key} turn {t} uses laugh tag {laugh_tags[0]}; "
                        "write haha/hehe next to an emotion tag instead"
                    )
                weak = WEAK_TAG_RE.findall(text)
                if weak:
                    problems.append(
                        f"item {i} {key} turn {t} uses weak TTS tag {weak[0]}; "
                        "prefer [worried], [very nervous], [hesitant], [delighted]"
                    )
                if "train" in text.lower() and "miss" in text.lower():
                    problems.append(f"item {i} {key} copies the missed-train seed")

            c_lines.append((turns[3].get("text") or "").strip())

        if len(c_lines) == 2 and c_lines[0] and c_lines[0] == c_lines[1]:
            problems.append(f"item {i} C's last line is identical in both versions")

        v1 = " ".join((t.get("text") or "") for t in (item.get("version_1") or {}).get("turns") or [])
        v2 = " ".join((t.get("text") or "") for t in (item.get("version_2") or {}).get("turns") or [])
        if v1 and v1 == v2:
            problems.append(f"item {i} versions are identical, including tags")

    nonempty = [p for p in patterns_used if p]
    if len(nonempty) != len(set(nonempty)):
        problems.append("each item must use a different pattern")
    if patterns_used.count("shared amusement vs distress that needs care") > 1:
        problems.append("use shared amusement vs distress at most once")

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
                        "name": "costly_misreads",
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


def generate(client: OpenAI, model: str, effort: str) -> dict:
    prompt = USER_PROMPT
    totals = {"input_tokens": 0, "output_tokens": 0}
    served_by = model
    last_problems: list[str] = []

    for attempt in range(1, 4):
        payload, usage, served_by = call_model(client, prompt, model, effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            return payload
        last_problems = problems
        prompt = (
            USER_PROMPT
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object with 10 diverse four-turn pairs."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2")

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(payload: dict, model: str) -> str:
    lines = [
        f"# Costly laughter misreads {VERSION_LABEL}",
        "",
        f"writer: {model} · {len(payload.get('items', []))} pairs",
        "",
        "Turns 1-3 keep the same spoken words. Tags and ... paint the vibe.",
        "Laughs are written as haha/hehe next to emotion tags, not [nervous laugh].",
        "Turn 4: C answers from that atmosphere.",
        "",
    ]
    for i, item in enumerate(payload.get("items", []), start=1):
        lines += [
            f"## {i}. {item['title']}",
            "",
            f"{item['setting']} · {item['relationship']}",
            "",
            f"**Pattern:** {item.get('pattern', '')}",
            "",
            f"**Contrast:** {item['contrast']}",
            "",
            f"**If C misreads it:** {item['cost_of_misread']}",
            "",
        ]
        for key, heading in (("version_1", "Version 1"), ("version_2", "Version 2")):
            version = item[key]
            lines += [
                f"### {heading} — {version['label']}",
                "",
                f"Laugh is doing: {version['what_the_laugh_is_doing']}",
                "",
                f"C should: {version['correct_next_move']}",
                "",
            ]
            for turn in version["turns"]:
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
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        print("--- system ---")
        print(SYSTEM_PROMPT)
        print("\n--- user ---")
        print(USER_PROMPT)
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}  ({VERSION_LABEL})")
    payload = generate(client, args.model, args.effort)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "version": VERSION_LABEL,
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "served_by": payload.pop("served_by", args.model),
        "usage": payload.pop("usage", {}),
        "attempts": payload.pop("attempts", 1),
        "items": payload["items"],
    }
    args.out.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    md_path.write_text(render_markdown(document, args.model), encoding="utf-8")

    print(f"wrote {len(document['items'])} pairs to {args.out} and {md_path}")
    for i, item in enumerate(document["items"], start=1):
        print(f"  {i}. [{item.get('pattern', '?')}] {item['title']}")


if __name__ == "__main__":
    main()

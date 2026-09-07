"""Loading and validating v6 transcript items.

An item is valid input to the audio pipeline only if all of the checks in `validate_item`
pass. Items that fail are reported, never rewritten — the transcript JSON is read-only from
this pipeline's point of view.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .tags import validate_tag

TURN_COUNT = 4
EXPECTED_SPEAKERS = ["A", "B", "A", "B"]

TagPosition = Literal["prefix", "inline", "suffix"]

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


@dataclass(frozen=True)
class Turn:
    turn: int
    speaker: str
    text: str


@dataclass(frozen=True)
class Item:
    item_id: str
    scenario: str
    voc_a: str
    emotion_a: str
    tag_a: str
    voc_b: str
    emotion_b: str
    tag_b: str
    vocalization_turn: int
    vocalization_speaker: str
    baseline_turns: tuple[Turn, ...]
    condition_a_turns: tuple[Turn, ...]
    condition_b_turns: tuple[Turn, ...]
    raw: dict


REQUIRED_ITEM_FIELDS = (
    "item_id", "scenario", "voc_a", "emotion_a", "tag_a", "voc_b", "emotion_b", "tag_b",
    "vocalization_turn", "vocalization_speaker", "condition_a", "condition_b", "baseline",
)


def load_transcript(path: str | Path) -> dict:
    """The raw JSON. Callers that only need `items` should use `load_items`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError(f"{path}: no top-level 'items' array")
    return data


def _turns(raw_condition: dict) -> tuple[Turn, ...]:
    return tuple(Turn(turn=t["turn"], speaker=t["speaker"], text=t["text"])
                 for t in raw_condition["turns"])


def parse_item(raw: dict) -> Item:
    missing = [f for f in REQUIRED_ITEM_FIELDS if f not in raw]
    if missing:
        raise ValueError(f"item {raw.get('item_id', '?')}: missing fields {missing}")
    return Item(
        item_id=raw["item_id"], scenario=raw["scenario"],
        voc_a=raw["voc_a"], emotion_a=raw["emotion_a"], tag_a=raw["tag_a"],
        voc_b=raw["voc_b"], emotion_b=raw["emotion_b"], tag_b=raw["tag_b"],
        vocalization_turn=raw["vocalization_turn"],
        vocalization_speaker=raw["vocalization_speaker"],
        baseline_turns=_turns(raw["baseline"]),
        condition_a_turns=_turns(raw["condition_a"]),
        condition_b_turns=_turns(raw["condition_b"]),
        raw=raw,
    )


def load_items(path: str | Path) -> list[Item]:
    return [parse_item(raw) for raw in load_transcript(path)["items"]]


def strip_tag(text: str, tag: str) -> str:
    """`text` with one occurrence of the literal tag string removed, whitespace normalized."""
    return _norm(text.replace(tag, "", 1))


def tag_position(text: str, tag: str) -> TagPosition | None:
    """Where `tag` sits inside `text`: prefix, suffix, or inline. None if `tag` is not in `text`
    or occupies the whole turn (no lexical words at all)."""
    idx = text.find(tag)
    if idx < 0:
        return None
    before = _norm(text[:idx])
    after = _norm(text[idx + len(tag):])
    if not before and not after:
        return None
    if not before:
        return "prefix"
    if not after:
        return "suffix"
    return "inline"


def _turns_by_number(turns: tuple[Turn, ...]) -> dict[int, Turn]:
    return {t.turn: t for t in turns}


def validate_item(item: Item) -> list[str]:
    """Every problem found; empty means the item is safe to synthesize.

    Checks, in the order the research spec lists them:
    1. each condition has four turns
    2. speaker order is A-B-A-B
    3. baseline contains no vocalization tag
    4. condition_a / condition_b each contain exactly one tag (the declared one)
    5. the tag occurs in the declared speaker and turn
    6. removing the tags makes all three lexical transcripts identical
    plus: tag_a/tag_b are on the Dia allowlist, and the tag sits at a determinable
    (non-degenerate) position within its turn.
    """
    problems: list[str] = []
    conditions = {
        "baseline": (item.baseline_turns, None),
        "condition_a": (item.condition_a_turns, item.tag_a),
        "condition_b": (item.condition_b_turns, item.tag_b),
    }

    # 1. turn count + numbering
    for name, (turns, _tag) in conditions.items():
        if len(turns) != TURN_COUNT:
            problems.append(f"{name}: has {len(turns)} turns, expected {TURN_COUNT}")
            continue
        if [t.turn for t in turns] != list(range(1, TURN_COUNT + 1)):
            problems.append(f"{name}: turns are not numbered 1..{TURN_COUNT} in order")

    # 2. speaker order
    for name, (turns, _tag) in conditions.items():
        speakers = [t.speaker for t in turns]
        if speakers != EXPECTED_SPEAKERS:
            problems.append(f"{name}: speaker order is {speakers}, expected {EXPECTED_SPEAKERS}")

    if problems:
        # Turn-shape problems make every later positional check meaningless.
        return problems

    # tags on the allowlist
    for voc, tag, label in ((item.voc_a, item.tag_a, "tag_a"), (item.voc_b, item.tag_b, "tag_b")):
        issue = validate_tag(voc, tag)
        if issue:
            problems.append(f"{label}: {issue}")

    # 3. baseline has no tag
    baseline_text = " ".join(t.text for t in item.baseline_turns)
    for tag, label in ((item.tag_a, "tag_a"), (item.tag_b, "tag_b")):
        if tag in baseline_text:
            problems.append(f"baseline contains {label} ({tag!r}); baseline must have no "
                             "vocalization")

    # 4. exactly one tag in each vocalized condition
    for name, (turns, tag) in conditions.items():
        if tag is None:
            continue
        text = " ".join(t.text for t in turns)
        count = text.count(tag)
        if count != 1:
            problems.append(f"{name}: tag {tag!r} occurs {count} times, expected exactly 1")

    # 5. the tag occurs in the declared speaker and turn
    for name, (turns, tag) in conditions.items():
        if tag is None:
            continue
        by_number = _turns_by_number(turns)
        target = by_number.get(item.vocalization_turn)
        if target is None:
            problems.append(f"{name}: vocalization_turn {item.vocalization_turn} does not exist")
            continue
        if target.speaker != item.vocalization_speaker:
            problems.append(f"{name}: vocalization_speaker is {item.vocalization_speaker!r} but "
                             f"turn {item.vocalization_turn} is spoken by {target.speaker!r}")
        if tag not in target.text:
            problems.append(f"{name}: tag {tag!r} is not in turn {item.vocalization_turn} "
                             f"({target.text!r})")
        elif tag_position(target.text, tag) is None:
            problems.append(f"{name}: tag {tag!r} in turn {item.vocalization_turn} has no "
                             "lexical words around it (degenerate position)")

    # 6. lexical identity once tags are removed
    base_norm = [(t.speaker, _norm(t.text)) for t in item.baseline_turns]
    for name, (turns, tag) in conditions.items():
        if tag is None:
            continue
        stripped = [(t.speaker, strip_tag(t.text, tag) if t.turn == item.vocalization_turn
                     else _norm(t.text)) for t in turns]
        if stripped != base_norm:
            diffs = [n + 1 for n, (x, y) in enumerate(zip(stripped, base_norm)) if x != y]
            problems.append(f"{name}: lexical words differ from baseline once the tag is "
                             f"removed (turn(s) {diffs})")

    return problems

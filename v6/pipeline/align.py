"""Aligning Whisper's word timestamps to the known lexical transcript, and turning that
alignment into the bounded search interval for a vocalization.

Whisper is not asked to find the vocalization — it cannot recognize non-speech sound as a
word. It is only asked to time the words we already know are there. The vocalization then
lives in the silence its own alignment brackets: the gap between two known words.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .schema import Turn

_APOSTROPHES = re.compile(r"[‘’`´]")
_NON_WORD = re.compile(r"[^\w\s']")
# Hyphens and slashes separate tokens rather than vanishing inside them. Whisper splits
# "warm-ups." into two word tokens (" warm", "-ups."), so collapsing the expected side to a
# single "warmups" left the last word permanently unmatched and rejected a take whose audio
# was in fact correct. Splitting on both sides makes the two tokenizations agree regardless of
# which one Whisper happens to produce.
_TOKEN_SPLIT = re.compile(r"[\s\-–—/]+")


def normalize_word(word: str) -> str:
    """lowercase, unify apostrophe variants, drop punctuation, strip whitespace.

    faster-whisper's `word.word` carries a leading space by convention (e.g. `" The"`, not
    `"The"`) since words are segment-boundary tokens; `_NON_WORD` deliberately preserves `\\s`
    (so it doesn't merge multi-word ASR artifacts into one token) which means that leading
    space survives the regex and has to be stripped explicitly, or every ASR token fails to
    match its (whitespace-free, `str.split()`-derived) expected counterpart.
    """
    word = word.strip()
    word = _APOSTROPHES.sub("'", word)
    word = word.lower()
    word = _NON_WORD.sub("", word)
    word = word.strip("'")
    # Drop a possessive marker. ASR is inconsistent about it — Whisper rendered
    # "Grandma's standing" as "Grandma standing" — and dropping it on both sides makes the two
    # agree whichever way it went. It costs only the its/it's distinction, which carries no
    # information for aligning a script we already know.
    if word.endswith("'s"):
        word = word[:-2]
    return word


def normalize_tokens(text: str) -> list[str]:
    """Normalized tokens, splitting on whitespace and on hyphens/slashes."""
    return [tok for tok in (normalize_word(w) for w in _TOKEN_SPLIT.split(text)) if tok]


@dataclass(frozen=True)
class ExpectedWord:
    turn: int
    speaker: str
    index_in_turn: int
    text: str


@dataclass(frozen=True)
class AsrWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class AlignedWord:
    expected: ExpectedWord
    asr_index: int | None
    start: float | None
    end: float | None
    matched: bool


def expected_words(turns: tuple[Turn, ...], tag: str | None = None) -> list[ExpectedWord]:
    """The turns' words, in order, with `tag` (if given) removed from wherever it sits."""
    out: list[ExpectedWord] = []
    for turn in turns:
        text = turn.text.replace(tag, "", 1) if tag and tag in turn.text else turn.text
        for index, token in enumerate(normalize_tokens(text)):
            out.append(ExpectedWord(turn=turn.turn, speaker=turn.speaker,
                                     index_in_turn=index, text=token))
    return out


def align(expected: list[ExpectedWord], asr_words: list[AsrWord]) -> list[AlignedWord]:
    """Sequence-align normalized ASR tokens to the normalized expected tokens.

    Uses difflib's longest-matching-blocks alignment (Ratcliff/Obershelp) over the two token
    sequences. Only tokens inside an "equal" block are treated as aligned; tokens Whisper
    dropped, added, or mis-heard are left unmatched rather than guessed at, so a caller can
    tell a real timestamp from a filled-in gap.
    """
    expected_tokens = [w.text for w in expected]

    # One Whisper word can normalize to more than one token ("warm-ups." -> warm, ups), so the
    # ASR side is expanded to a flat token list where each token remembers which AsrWord it
    # came from. Sub-tokens share that word's timestamps: the split is inside a single spoken
    # word, so its outer boundaries are still the right anchors.
    asr_tokens: list[str] = []
    token_source: list[int] = []
    for word_index, word in enumerate(asr_words):
        for token in normalize_tokens(word.text):
            asr_tokens.append(token)
            token_source.append(word_index)

    matcher = difflib.SequenceMatcher(None, expected_tokens, asr_tokens, autojunk=False)

    result: list[AlignedWord | None] = [None] * len(expected)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "equal":
            continue
        for offset in range(i2 - i1):
            ei, aj = i1 + offset, j1 + offset
            source_index = token_source[aj]
            asr = asr_words[source_index]
            result[ei] = AlignedWord(expected=expected[ei], asr_index=source_index,
                                      start=asr.start, end=asr.end, matched=True)
    return [w or AlignedWord(expected=expected[i], asr_index=None, start=None, end=None,
                              matched=False)
            for i, w in enumerate(result)]


def alignment_quality(aligned: list[AlignedWord]) -> dict:
    matched = sum(1 for w in aligned if w.matched)
    total = len(aligned)
    return {
        "total_expected_words": total,
        "matched_words": matched,
        "match_rate": (matched / total) if total else 0.0,
    }


def words_before_tag(turn_text: str, tag: str) -> int:
    """How many lexical words precede `tag` inside `turn_text`."""
    index = turn_text.find(tag)
    if index < 0:
        raise ValueError(f"tag {tag!r} not found in {turn_text!r}")
    return len(normalize_tokens(turn_text[:index]))


class BoundaryError(ValueError):
    """The vocalization interval could not be determined; caller should reject/flag the item."""


@dataclass(frozen=True)
class Interval:
    left: float
    right: float

    @property
    def duration(self) -> float:
        return self.right - self.left


def _turn_words(aligned: list[AlignedWord], turn: int) -> list[AlignedWord]:
    return [w for w in aligned if w.expected.turn == turn]


def compute_boundary(aligned: list[AlignedWord], tag_turn: int, position: str,
                      total_turns: int, words_before: int = 0,
                      audio_duration: float | None = None,
                      carry_words: int = 0) -> Interval:
    """The bounded [left, right] search interval (seconds) for the vocalization.

    `position` is "prefix" | "inline" | "suffix" (schema.tag_position). `words_before` is only
    used for "inline": how many lexical words in the tagged turn precede the tag.

    `carry_words` extends the right edge past the vocalization to the END of that many lexical
    words following it, instead of stopping at the START of the next word. A laugh usually
    bleeds into the word after it, so cutting exactly at the word onset clips the blend; taking
    "(laughs) I" whole keeps it. The cost is that those carried words then come from the
    vocalized take rather than the baseline, so the caller must splice them as a REPLACEMENT of
    the matching baseline span (see audio_ops.splice_replace) and must accept that those words
    are no longer physically identical across conditions.
    """
    def carried_end(words: list[AlignedWord], first_index: int, label: str) -> float:
        """End of the `carry_words`-th word starting at `first_index`."""
        last_index = first_index + carry_words - 1
        if last_index >= len(words):
            raise BoundaryError(f"{label}: cannot carry {carry_words} word(s) past the tag; "
                                 f"only {len(words) - first_index} follow it")
        carried = words[first_index:last_index + 1]
        unmatched = [w.expected.text for w in carried if not w.matched]
        if unmatched:
            raise BoundaryError(f"{label}: carried word(s) {unmatched} did not align")
        return carried[-1].end
    if position == "prefix":
        if tag_turn == 1:
            left = 0.0
        else:
            prev_words = _turn_words(aligned, tag_turn - 1)
            if not prev_words:
                raise BoundaryError(f"turn {tag_turn - 1}: no aligned words to anchor the "
                                     "left boundary")
            if not prev_words[-1].matched:
                raise BoundaryError(f"turn {tag_turn - 1}: final word did not align")
            left = prev_words[-1].end
        cur_words = _turn_words(aligned, tag_turn)
        if not cur_words or not cur_words[0].matched:
            raise BoundaryError(f"turn {tag_turn}: first word did not align")
        right = (carried_end(cur_words, 0, f"turn {tag_turn}") if carry_words
                 else cur_words[0].start)

    elif position == "suffix":
        cur_words = _turn_words(aligned, tag_turn)
        if not cur_words or not cur_words[-1].matched:
            raise BoundaryError(f"turn {tag_turn}: final word did not align")
        left = cur_words[-1].end
        if tag_turn >= total_turns:
            if audio_duration is None:
                raise BoundaryError("final turn's tag has no following turn and no "
                                     "audio_duration was given for the endpoint")
            right = audio_duration
        else:
            next_words = _turn_words(aligned, tag_turn + 1)
            if not next_words or not next_words[0].matched:
                raise BoundaryError(f"turn {tag_turn + 1}: first word did not align")
            right = (carried_end(next_words, 0, f"turn {tag_turn + 1}") if carry_words
                     else next_words[0].start)

    elif position == "inline":
        cur_words = _turn_words(aligned, tag_turn)
        if words_before <= 0 or words_before >= len(cur_words):
            raise BoundaryError(f"turn {tag_turn}: inline tag has no lexical word on one "
                                 f"side (words_before={words_before}, turn has "
                                 f"{len(cur_words)} words)")
        before, after = cur_words[words_before - 1], cur_words[words_before]
        if not before.matched or not after.matched:
            raise BoundaryError(f"turn {tag_turn}: word adjacent to the inline tag did not "
                                 "align")
        left = before.end
        right = (carried_end(cur_words, words_before, f"turn {tag_turn}") if carry_words
                 else after.start)
    else:
        raise BoundaryError(f"unknown tag position {position!r}")

    if right <= left:
        raise BoundaryError(f"candidate interval is empty or negative: [{left}, {right}]")
    return Interval(left=left, right=right)

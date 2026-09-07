"""Locating a vocalization inside a raw Dia generation, and cutting it out.

This sits between align.py (word timestamps) and audio_ops.py (waveform manipulation): it
turns "the tag is a prefix on turn 2" plus an aligned word list into an actual sample range,
then trims and fades that range into a clean standalone clip.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .align import AlignedWord, BoundaryError, Interval, compute_boundary, words_before_tag
from .audio_ops import apply_fade, rms_dbfs, trim_silence
from .schema import Item, tag_position

TOTAL_TURNS = 4


@dataclass(frozen=True)
class TagLocation:
    turn: int
    speaker: str
    position: str  # "prefix" | "inline" | "suffix"
    words_before: int  # only meaningful for "inline"


def locate_tag(item: Item, condition: str, renumber_to: int | None = None) -> TagLocation:
    """Where condition_a's or condition_b's tag sits, derived from the transcript alone (no
    audio needed) — the same information `schema.validate_item` already checked exists.

    `renumber_to` sets the turn number reported in the result. A single-turn take (see
    runner.vocalized_take_turns) contains only the tagged turn, renumbered to turn 1, so its
    alignment has no turn 2/3 to anchor against; pass 1 to match.
    """
    if condition not in ("condition_a", "condition_b"):
        raise ValueError("locate_tag is only meaningful for condition_a / condition_b")
    turns = item.condition_a_turns if condition == "condition_a" else item.condition_b_turns
    tag = item.tag_a if condition == "condition_a" else item.tag_b
    turn = next(t for t in turns if t.turn == item.vocalization_turn)
    position = tag_position(turn.text, tag)
    if position is None:
        raise BoundaryError(f"{condition}: tag {tag!r} has no determinable position in turn "
                             f"{turn.turn}")
    words_before = words_before_tag(turn.text, tag) if position == "inline" else 0
    return TagLocation(turn=renumber_to if renumber_to is not None else turn.turn,
                        speaker=turn.speaker, position=position, words_before=words_before)


def find_candidate_interval(aligned: list[AlignedWord], location: TagLocation,
                             audio_duration: float | None = None,
                             total_turns: int = TOTAL_TURNS,
                             carry_words: int = 0) -> Interval:
    return compute_boundary(aligned, tag_turn=location.turn, position=location.position,
                             total_turns=total_turns, words_before=location.words_before,
                             audio_duration=audio_duration, carry_words=carry_words)


def carried_word_texts(aligned: list[AlignedWord], location: TagLocation,
                        carry_words: int) -> list[str]:
    """The lexical words the clip carries past the vocalization — recorded in the manifest,
    since these are the words that stop being physically identical across conditions."""
    if carry_words <= 0:
        return []
    turn_words = [w for w in aligned if w.expected.turn == location.turn]
    first = location.words_before if location.position == "inline" else 0
    if location.position == "suffix":
        turn_words = [w for w in aligned if w.expected.turn == location.turn + 1]
        first = 0
    return [w.expected.text for w in turn_words[first:first + carry_words]]


REALIZED_FLOOR_DB = -45.0
MIN_PLAUSIBLE_S = 0.05
MAX_PLAUSIBLE_S = 4.0


@dataclass(frozen=True)
class ExtractionResult:
    raw: np.ndarray            # the untrimmed candidate interval, sample-exact
    trimmed: np.ndarray        # energy-trimmed + faded, ready to splice
    raw_interval: Interval
    trimmed_start_in_raw: int  # sample offset of `trimmed` within `raw`
    trimmed_end_in_raw: int
    issues: list[str]


def extract_vocalization(samples: np.ndarray, sample_rate: int, interval: Interval,
                          fade_ms: float = 5.0, pad_ms: float = 75.0,
                          threshold_db: float = -40.0,
                          keep_tail: bool = False,
                          anchor: str = "largest") -> ExtractionResult:
    """Cuts, trims, and fades the candidate interval. Always returns both `raw` and `trimmed`
    so a rejected extraction can still be inspected; `issues` says why it was rejected, if it
    was.

    `keep_tail` is for carry-word mode, and it matters more than it looks. When the window
    deliberately ends at the END of a carried word, the clip holds separate energy regions —
    the vocalization, a gap, then the word — so the right edge must be left exactly where the
    caller put it (it is a Whisper word-end, not a guess) and only the leading silence trimmed.
    Trimming both ends here would drop either the vocalization or the carried word, whichever
    the `anchor` rule happened not to pick.

    `anchor` is passed through to `audio_ops.trim_silence`: use "first" when the vocalization
    is known to lead the window (prefix tag, single-turn take) and "largest" when the window is
    bounded by real words on both sides.
    """
    issues: list[str] = []
    duration = interval.duration
    if duration <= 0:
        issues.append(f"candidate interval is empty ({duration:.3f}s)")
        empty = np.zeros(0, dtype=np.float64)
        return ExtractionResult(raw=empty, trimmed=empty, raw_interval=interval,
                                 trimmed_start_in_raw=0, trimmed_end_in_raw=0, issues=issues)
    if duration > MAX_PLAUSIBLE_S:
        issues.append(f"candidate interval is implausibly long ({duration:.3f}s > "
                       f"{MAX_PLAUSIBLE_S}s) — likely includes lexical speech")

    start = max(0, int(round(interval.left * sample_rate)))
    end = min(len(samples), int(round(interval.right * sample_rate)))
    raw = samples[start:end].astype(np.float64).copy()

    if raw.size == 0:
        issues.append("candidate interval maps to zero audio samples")
        return ExtractionResult(raw=raw, trimmed=raw, raw_interval=interval,
                                 trimmed_start_in_raw=0, trimmed_end_in_raw=0, issues=issues)

    if keep_tail:
        # The right edge is a Whisper word-end the caller chose deliberately; only the leading
        # silence is ours to remove.
        trim_start, _ = trim_silence(raw, sample_rate, threshold_db=threshold_db,
                                      pad_ms=pad_ms, anchor=anchor)
        trim_end = len(raw)
    else:
        trim_start, trim_end = trim_silence(raw, sample_rate, threshold_db=threshold_db,
                                             pad_ms=pad_ms, anchor=anchor)
    if trim_end <= trim_start:
        issues.append("no acoustic activity found above threshold inside the candidate "
                       "interval — the vocalization does not appear to have been realized")
        trimmed = np.zeros(0, dtype=np.float64)
    else:
        trimmed = apply_fade(raw[trim_start:trim_end], sample_rate, fade_ms=fade_ms)
        trimmed_duration = len(trimmed) / sample_rate
        if trimmed_duration < MIN_PLAUSIBLE_S:
            issues.append(f"trimmed vocalization is implausibly short "
                           f"({trimmed_duration:.3f}s < {MIN_PLAUSIBLE_S}s)")
        if rms_dbfs(trimmed) < REALIZED_FLOOR_DB:
            issues.append(f"trimmed vocalization is at or below the silence floor "
                           f"({REALIZED_FLOOR_DB} dBFS) — acoustic activity does not support "
                           "the requested vocalization")

    return ExtractionResult(raw=raw, trimmed=trimmed, raw_interval=interval,
                             trimmed_start_in_raw=trim_start, trimmed_end_in_raw=trim_end,
                             issues=issues)

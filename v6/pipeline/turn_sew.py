"""Sewing a vocalization out of one ElevenLabs turn take and into the clean take of that turn.

The ElevenLabs renderer writes one file per turn (see make_audio.py). A turn that carries a
vocalization is rendered three times: once clean, once with tag A, once with tag B. That
layout is what makes this path better controlled than the Dia one:

    Dia          one whole-conversation baseline + independent takes, each an independent
                 sample, so the *speaking voice* drifts between conditions and has to be
                 selected for (see voice.py).
    ElevenLabs   a pinned voice_id per speaker, and the clean take of the tagged turn is a
                 sibling of the two vocalized takes — same voice, same settings, same words.

So the cut is the only thing that has to be got right here. The rule is the same one
show_cuts.py prints for the Dia path:

    cut  = [take start .. onset of the first lexical word]      (prefix tag)
           [end of the word before .. onset of the word after]  (inline tag)
    into = the CLEAN take's own onset of that same anchor word

Nothing is removed from the clean take, so every lexical word in every output is bit-identical
across neutral / A / B — the inserted clip is the only difference. `verify_waveform_preserved`
is asserted on every splice rather than trusted.

Whisper is never asked to find the vocalization: it cannot hear non-speech as a word. It is
asked only to time the words we already know are there, and the vocalization is then whatever
lives in the silence those words bracket.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .align import (AlignedWord, BoundaryError, Interval, align, compute_boundary,
                     expected_words)
from .audio_ops import (AudioClip, apply_fade, match_loudness, read_wav, rms_dbfs,
                         splice_insert, trim_silence, verify_waveform_preserved)
from .extraction import extract_vocalization, locate_tag
from .schema import Item, Turn

# A single-turn take holds exactly one turn, renumbered to 1, so prefix logic anchors its left
# edge at 0.0 and there is no turn 2 to look for. Both are what compute_boundary needs told.
TAKE_TURN = 1
TAKE_TOTAL_TURNS = 1

CONDITIONS = ("condition_a", "condition_b")
VARIANT_OF = {"condition_a": "a", "condition_b": "b"}


# --------------------------------------------------------------------------- manifest reading

@dataclass(frozen=True)
class TurnTake:
    turn: int
    speaker: str
    variant: str          # "" for the clean take, "a" / "b" for a vocalized one
    text: str             # as sent to ElevenLabs, so a variant still carries its bracketed tag
    path: Path
    seconds: float
    # The renderer records both spellings per tagged take, because `text` uses the bracketed
    # one while the transcripts use the parenthesised one. Both are needed to strip the tag.
    dia_tag: str | None = None
    elevenlabs_tag: str | None = None


@dataclass(frozen=True)
class ItemTakes:
    """Every take belonging to one item, indexed the way the sewing needs it."""
    item_id: str
    vocalization_turn: int
    vocalization_speaker: str
    gap_seconds: float
    turn_order: tuple[int, ...]
    clean: dict[int, TurnTake]           # turn number -> the untagged take of that turn
    variants: dict[str, TurnTake]        # "a" / "b" -> the tagged take of the tagged turn

    def clean_paths(self) -> list[Path]:
        return [self.clean[turn].path for turn in self.turn_order]


def _resolve(root: Path, raw: str) -> Path:
    """Manifest paths are written relative to the v6 directory the renderer ran in."""
    direct = Path(raw)
    if direct.exists():
        return direct
    joined = root / raw
    return joined if joined.exists() else direct


def load_turn_takes(manifest_path: str | Path, root: str | Path = ".") -> dict[str, ItemTakes]:
    """Parse the renderer's manifest into one ItemTakes per item, checking the layout the
    sewing assumes actually holds — a missing variant here would otherwise surface much later
    as a confusing alignment failure."""
    manifest_path, root = Path(manifest_path), Path(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: dict[str, ItemTakes] = {}

    for entry in manifest.get("items", []):
        item_id = entry["item_id"]
        assembly = entry.get("assembly", {})
        turn_order = tuple(assembly.get("turn_order") or ())
        voc_turn = entry["vocalization_turn"]

        clean: dict[int, TurnTake] = {}
        variants: dict[str, TurnTake] = {}
        for take in entry.get("takes", []):
            record = TurnTake(turn=take["turn"], speaker=take["speaker"],
                               variant=take.get("variant", ""), text=take["text"],
                               path=_resolve(root, take["path"]),
                               seconds=float(take.get("seconds", 0.0)),
                               dia_tag=take.get("dia_tag"),
                               elevenlabs_tag=take.get("elevenlabs_tag"))
            if record.variant:
                variants[record.variant] = record
            else:
                clean[record.turn] = record

        if not turn_order:
            turn_order = tuple(sorted(clean))
        missing = [t for t in turn_order if t not in clean]
        if missing:
            raise ValueError(f"{item_id}: no clean take for turn(s) {missing}")
        if set(variants) != {"a", "b"}:
            raise ValueError(f"{item_id}: expected variants a and b on turn {voc_turn}, "
                              f"found {sorted(variants) or 'none'}")
        off_turn = [v.turn for v in variants.values() if v.turn != voc_turn]
        if off_turn:
            raise ValueError(f"{item_id}: variant take(s) sit on turn {off_turn}, but the "
                              f"vocalization turn is {voc_turn}")
        for variant, take in sorted(variants.items()):
            # The tag the manifest says is in this take's text has to actually be in it, or the
            # stripping below silently leaves it there for the aligner to treat as a word.
            if take.elevenlabs_tag and take.elevenlabs_tag not in take.text:
                raise ValueError(f"{item_id} variant {variant}: manifest says the take carries "
                                  f"{take.elevenlabs_tag!r}, but its text is {take.text!r}")

        out[item_id] = ItemTakes(
            item_id=item_id, vocalization_turn=voc_turn,
            vocalization_speaker=entry["vocalization_speaker"],
            gap_seconds=float(assembly.get("gap_seconds", entry.get("gap_seconds", 0.0))),
            turn_order=turn_order, clean=clean, variants=variants)
    return out


# ------------------------------------------------------------------------------ the cut itself

# Any `(word)` or `[word]` left after stripping is an un-recognised tag spelling.
_RESIDUAL_TAG = re.compile(r"[\[(][A-Za-z]+[\])]")


def spoken_text(text: str, tags: tuple[str, ...]) -> str:
    """`text` with every tag spelling removed — what the aligner is given, since the aligner
    must be asked to place lexical words only.

    Raises if a tag-shaped token survives. That is worth failing on rather than passing
    through: a tag left in the text gets force-aligned as if it were a word, which silently
    moves the prefix anchor onto the vocalization itself and collapses the cut window to
    nothing. It is a wrong cut, not a crash, so nothing downstream would notice.
    """
    for tag in tags:
        if tag:
            text = text.replace(tag, " ")
    out = " ".join(text.split())
    residual = _RESIDUAL_TAG.search(out)
    if residual:
        known = sorted({tag for tag in tags if tag})
        raise ValueError(
            f"{residual.group(0)!r} survived tag stripping in {out!r}. The tags it was given "
            f"were {known}. The transcripts spell tags Dia's way, '(laughs)', and the "
            "ElevenLabs takes spell them '[laughs]' — both spellings have to be stripped; see "
            "tag_spellings().")
    return out


def take_expected_words(text: str, speaker: str, tags: tuple[str, ...]) -> list:
    """Expected words for a single-turn take, renumbered to turn 1 (see TAKE_TURN).

    The tags are stripped from the text up front rather than handed to `expected_words`, which
    only knows how to remove one spelling.
    """
    turn = Turn(turn=TAKE_TURN, speaker=speaker, text=spoken_text(text, tags))
    return expected_words((turn,), tag=None)


def tag_spellings(item: Item, takes: ItemTakes) -> tuple[str, ...]:
    """Every spelling of this item's two tags that could appear in a take's text.

    The transcripts carry Dia's parenthesised tags; make_audio.py maps them to ElevenLabs'
    bracketed ones and records both per take. So the transcript says `(laughs)` while the take
    that was actually rendered says `[laughs]`, and stripping only one of them is not enough.
    """
    spellings = {item.tag_a, item.tag_b}
    for take in takes.variants.values():
        spellings.update(tag for tag in (take.dia_tag, take.elevenlabs_tag) if tag)
    return tuple(sorted(tag for tag in spellings if tag))


@dataclass(frozen=True)
class CutPlan:
    condition: str
    vocalization: str
    position: str              # "prefix" | "inline"
    words_before: int
    anchor_word: str           # the lexical word the cut ends at, and inserts before
    cut: Interval              # where the vocalization sits in the VOCALIZED take
    insert_at: float           # where it goes in the CLEAN take, seconds


def plan_cut(item: Item, condition: str, variant_aligned: list[AlignedWord],
              clean_aligned: list[AlignedWord], variant_duration: float) -> CutPlan:
    """Turn two alignments of the same turn — one vocalized, one clean — into a cut window and
    the point in the clean take it belongs at.

    Raises BoundaryError if an anchor word did not align, in either take. A guessed timestamp
    here would put a laugh in the middle of a word, so an unplaced anchor has to fail loudly.
    """
    location = locate_tag(item, condition, renumber_to=TAKE_TURN)
    if location.position == "suffix":
        # No item in the current set has one, and a suffix tag in a single-turn take has no
        # following word to bound it — it would run to the end of the file.
        raise BoundaryError(f"{item.item_id} {condition}: suffix tags are not supported on "
                             "single-turn takes")

    cut = compute_boundary(variant_aligned, tag_turn=TAKE_TURN, position=location.position,
                            total_turns=TAKE_TOTAL_TURNS, words_before=location.words_before,
                            audio_duration=variant_duration)

    anchor_index = location.words_before if location.position == "inline" else 0
    clean_words = [w for w in clean_aligned if w.expected.turn == TAKE_TURN]
    if anchor_index >= len(clean_words):
        raise BoundaryError(f"{item.item_id} {condition}: clean take has "
                             f"{len(clean_words)} word(s), no anchor at index {anchor_index}")
    anchor = clean_words[anchor_index]
    if not anchor.matched or anchor.start is None:
        raise BoundaryError(f"{item.item_id} {condition}: the clean take's anchor word "
                             f"{anchor.expected.text!r} did not align, so there is nowhere "
                             "to put the clip")

    return CutPlan(condition=condition,
                    vocalization=item.voc_a if condition == "condition_a" else item.voc_b,
                    position=location.position, words_before=location.words_before,
                    anchor_word=anchor.expected.text, cut=cut, insert_at=float(anchor.start))


# -------------------------------------------------------------------------------- the assembly

@dataclass(frozen=True)
class SewnTurn:
    samples: np.ndarray
    insert_sample: int
    inserted_length: int
    preserved: bool            # everything outside the inserted span is the clean take, exactly
    clip_seconds: float
    loudness_delta_db: float
    issues: list[str]


def sew_tagged_turn(clean: np.ndarray, sample_rate: int, clip: np.ndarray, insert_at: float,
                     gap_ms: float = 75.0) -> tuple[np.ndarray, int, int, bool]:
    """Insert `clip` into `clean` at `insert_at` seconds. Nothing is removed."""
    insert_sample = int(np.clip(round(insert_at * sample_rate), 0, len(clean)))
    spliced, inserted_length = splice_insert(clean, insert_sample, clip, sample_rate,
                                              gap_ms=gap_ms)
    preserved = verify_waveform_preserved(clean, spliced, insert_sample, inserted_length,
                                           replaced_length=0)
    return spliced, insert_sample, inserted_length, preserved


def assemble(turns: list[np.ndarray], gap_seconds: float, sample_rate: int) -> np.ndarray:
    """Concatenate per-turn waveforms with `gap_seconds` of silence between them.

    Deliberately numpy rather than sew.py: that helper shells out to ffmpeg and re-encodes to
    mp3, which would both require ffmpeg and lose the sample-exactness the whole design rests
    on. The takes are already decoded here, so concatenation is just an array join.
    """
    if not turns:
        raise ValueError("nothing to assemble")
    gap = np.zeros(max(0, int(round(gap_seconds * sample_rate))), dtype=np.float64)
    pieces: list[np.ndarray] = []
    for index, samples in enumerate(turns):
        if index:
            pieces.append(gap)
        pieces.append(np.asarray(samples, dtype=np.float64))
    return np.concatenate(pieces)


def _mono(clip: AudioClip) -> np.ndarray:
    samples = np.asarray(clip.samples, dtype=np.float64)
    return samples.mean(axis=1) if samples.ndim > 1 else samples


def read_take(path: Path) -> AudioClip:
    """Decode a take. `read_wav` is soundfile-backed, so it reads the renderer's mp3 too; the
    sewn output is written as WAV so nothing is re-encoded after the splice."""
    clip = read_wav(str(path))
    return AudioClip(samples=_mono(clip), sample_rate=clip.sample_rate)


def speech_dbfs(samples: np.ndarray, sample_rate: int) -> float:
    """RMS of the take's speech region, ignoring its leading and trailing silence."""
    start, end = trim_silence(samples, sample_rate)
    region = samples[start:end] if end > start else samples
    return rms_dbfs(region)


# ------------------------------------------------------------------------------- orchestration

@dataclass
class SewOptions:
    gap_ms: float = 75.0             # silence between the inserted clip and the resumed words
    fade_ms: float = 5.0
    pad_ms: float = 75.0
    threshold_db: float = -40.0
    match_loudness: bool = False     # measure always, apply only when asked (see README)
    max_adjust_db: float = 6.0


@dataclass
class ItemResult:
    item_id: str
    sample_rate: int
    gap_seconds: float
    neutral: np.ndarray
    sewn: dict[str, np.ndarray] = field(default_factory=dict)      # "a" / "b" -> dialogue
    plans: dict[str, CutPlan] = field(default_factory=dict)
    turns: dict[str, SewnTurn] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)           # variant -> why, if rejected
    issues: list[str] = field(default_factory=list)


def build_neutral(takes: ItemTakes) -> ItemResult:
    """The no-vocalization dialogue: the clean takes, in order, with the renderer's own gap.

    Needs no alignment and no model — it is pure concatenation, which is why it can be built
    anywhere while the sewn versions wait on WhisperX.
    """
    clips = [read_take(takes.clean[turn].path) for turn in takes.turn_order]
    rates = {clip.sample_rate for clip in clips}
    if len(rates) != 1:
        raise ValueError(f"{takes.item_id}: takes disagree on sample rate: {sorted(rates)}")
    sample_rate = rates.pop()
    neutral = assemble([clip.samples for clip in clips], takes.gap_seconds, sample_rate)
    return ItemResult(item_id=takes.item_id, sample_rate=sample_rate,
                       gap_seconds=takes.gap_seconds, neutral=neutral)


def sew_item(item: Item, takes: ItemTakes, aligner, options: SewOptions | None = None,
              conditions: tuple[str, ...] = CONDITIONS) -> ItemResult:
    """Build all three dialogues for one item.

    `aligner` is anything with WhisperXAligner's `.align(path, text, duration) -> {"words": …}`
    shape, so the sewing is testable without a model and the backend stays swappable.

    A condition whose cut cannot be trusted is *refused*, not approximated: it gets an entry in
    `failed` and no entry in `sewn`, so no file is written for it. Falling back to the clean
    turn would produce a `_sewn_laugh` that is identical to neutral and would still be scored
    as a laugh. The neutral dialogue and the other condition are unaffected.
    """
    options = options or SewOptions()
    tags = tag_spellings(item, takes)
    result = build_neutral(takes)

    voc_turn = takes.vocalization_turn
    clean_take = takes.clean[voc_turn]
    clean_clip = read_take(clean_take.path)
    clean_text = spoken_text(clean_take.text, tags)
    clean_aligned = align(
        take_expected_words(clean_take.text, clean_take.speaker, tags),
        aligner.align(str(clean_take.path), clean_text, clean_clip.duration)["words"])
    clean_target_db = speech_dbfs(clean_clip.samples, clean_clip.sample_rate)

    order = list(takes.turn_order)
    # The untagged turns are shared by all three dialogues, so they are decoded once — this is
    # also what makes neutral and both sewn files sample-identical outside the tagged turn.
    shared = {turn: read_take(takes.clean[turn].path).samples
               for turn in order if turn != voc_turn}

    for condition in conditions:
        variant = VARIANT_OF[condition]
        take = takes.variants[variant]
        clip = read_take(take.path)
        if clip.sample_rate != result.sample_rate:
            raise ValueError(f"{item.item_id} {condition}: variant take is "
                              f"{clip.sample_rate} Hz, clean takes are {result.sample_rate} Hz")

        text = spoken_text(take.text, tags)
        variant_aligned = align(
            take_expected_words(take.text, take.speaker, tags),
            aligner.align(str(take.path), text, clip.duration)["words"])

        # One condition that cannot be cut must not cost the item its other two files.
        try:
            plan = plan_cut(item, condition, variant_aligned, clean_aligned, clip.duration)
        except BoundaryError as exc:
            result.failed[variant] = str(exc)
            result.issues.append(f"{condition}: not spliced: {exc}")
            continue
        result.plans[variant] = plan

        extraction = extract_vocalization(
            clip.samples, clip.sample_rate, plan.cut, fade_ms=options.fade_ms,
            pad_ms=options.pad_ms, threshold_db=options.threshold_db,
            # The vocalization leads the window for a prefix tag; for an inline one the window
            # is bounded by real words on both sides, so take the largest energy region.
            anchor="first" if plan.position == "prefix" else "largest")

        vocalization = extraction.trimmed
        # extract_vocalization returns `trimmed` even when it rejects the cut, so that a bad
        # extraction can still be inspected — `issues` is the verdict, not emptiness. Splicing
        # a rejected clip would put silence, or a fragment of a word, where a laugh should be.
        rejected = list(extraction.issues) or ([] if vocalization.size
                                                else ["the extracted clip was empty"])
        if rejected:
            reason = "; ".join(rejected)
            result.failed[variant] = reason
            result.issues.append(f"{condition}: not spliced: {reason}")
            result.turns[variant] = SewnTurn(
                samples=clean_clip.samples, insert_sample=0, inserted_length=0, preserved=True,
                clip_seconds=0.0, loudness_delta_db=0.0, issues=rejected)
            continue

        # Measured either way and recorded in the manifest; applied only on request, since the
        # clip and the clean take come from one pinned voice and forcing the gain would change
        # how loud the vocalization actually was relative to the words.
        delta_db = float(clean_target_db - rms_dbfs(vocalization))
        if options.match_loudness:
            vocalization, delta_db = match_loudness(
                vocalization, clean_target_db, max_adjust_db=options.max_adjust_db)
            vocalization = apply_fade(vocalization, clip.sample_rate, fade_ms=options.fade_ms)

        sewn_turn, insert_sample, inserted_length, preserved = sew_tagged_turn(
            clean_clip.samples, clean_clip.sample_rate, vocalization, plan.insert_at,
            gap_ms=options.gap_ms)
        issues: list[str] = []
        if not preserved:
            # Should be unreachable — splice_insert removes nothing — so treat it as a bug
            # rather than a warning, and refuse to emit the file.
            issues.append("splice did not preserve the clean waveform outside the clip")
            result.failed[variant] = issues[-1]
            result.issues.append(f"{condition}: not spliced: {issues[-1]}")
            result.turns[variant] = SewnTurn(
                samples=clean_clip.samples, insert_sample=0, inserted_length=0, preserved=False,
                clip_seconds=0.0, loudness_delta_db=delta_db, issues=issues)
            continue

        pieces = [shared[turn] if turn != voc_turn else sewn_turn for turn in order]
        result.sewn[variant] = assemble(pieces, takes.gap_seconds, result.sample_rate)
        result.turns[variant] = SewnTurn(
            samples=sewn_turn, insert_sample=insert_sample, inserted_length=inserted_length,
            preserved=preserved, clip_seconds=len(vocalization) / clip.sample_rate,
            loudness_delta_db=delta_db, issues=issues)

    return result

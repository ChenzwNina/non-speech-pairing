"""Sewing a vocalization from one ElevenLabs turn take into the clean take of that turn.

Every test here runs on synthetic tones and a stub aligner, so the whole cut-and-sew path is
exercised without torch, WhisperX or a GPU — the same way audio_ops and extraction are tested.
The stub returns word timings we choose, which is what makes it possible to assert *exactly*
where the cut landed rather than merely that it ran.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from pipeline.align import AsrWord, BoundaryError, align
from pipeline.schema import parse_item
from pipeline.turn_sew import (SewOptions, assemble, build_neutral, load_turn_takes, plan_cut,
                                sew_item, sew_tagged_turn, spoken_text, tag_spellings,
                                take_expected_words)

from .conftest import SAMPLE_RATE, make_raw_item, silence, sine_wave

TURN_TEXTS = {
    1: "The kids are crawling around the living room like lions.",
    2: "Looks like the safari gave them a new game.",
    3: "They've been playing it since we got home.",
    4: "I'll move the coffee table out of their way.",
}
SPEAKERS = {1: "A", 2: "B", 3: "A", 4: "B"}
GAP_SECONDS = 0.35


# --------------------------------------------------------------------------------- the harness

class StubAligner:
    """WhisperXAligner's `.align` shape, with timings we dictate, keyed by file name."""

    def __init__(self, timings: dict[str, list[tuple[str, float, float]]]):
        self.timings = timings
        self.calls: list[str] = []

    def align(self, path: str, text: str, duration: float) -> dict:
        name = Path(path).name
        self.calls.append(name)
        if name not in self.timings:
            raise AssertionError(f"stub aligner asked for unexpected file {name}")
        return {"words": [AsrWord(text=w, start=s, end=e)
                          for w, s, e in self.timings[name]]}

    def unload(self) -> None:
        pass


def even_timings(text: str, start: float, word_s: float = 0.1) -> list[tuple[str, float, float]]:
    """One evenly spaced timing per whitespace token, from `start`."""
    out, cursor = [], start
    for token in text.split():
        out.append((token, cursor, cursor + word_s))
        cursor += word_s
    return out


def write_take(path: Path, samples: np.ndarray) -> Path:
    """soundfile picks the container from the extension, so the subtype has to follow it —
    PCM_16 is not a legal mp3 subtype and MPEG_LAYER_III is not a legal wav one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subtype = "MPEG_LAYER_III" if path.suffix == ".mp3" else "PCM_16"
    sf.write(str(path), samples, SAMPLE_RATE, subtype=subtype)
    return path


def build_take_tree(root: Path, *, voc_turn: int = 2, item_id: str = "t_01a",
                     lead_a: float = 0.30, lead_b: float = 0.20,
                     ext: str = ".wav") -> tuple[Path, dict]:
    """A miniature version of what make_audio.py leaves behind: four clean turn takes plus two
    vocalized takes of the tagged turn, and a manifest describing them.

    Each vocalized take opens with a tone standing in for the vocalization, then a silence,
    then the same 'speech' tone the clean take holds. The stub aligner is told the lexical
    words start after that lead, so the cut window is exactly the lead plus its trailing gap.

    `ext` defaults to .wav so the sample assertions are exact; the renderer's real output is
    mp3, which one test writes for real to check nothing in the path assumes WAV.
    """
    audio = root / "out" / "audio_turns" / "elevenlabs"
    speech = {turn: sine_wave(1.0, freq=300.0) for turn in TURN_TEXTS}
    clean_lead = 0.10

    takes, timings = [], {}
    for turn, text in TURN_TEXTS.items():
        name = f"{item_id}__t{turn}{ext}"
        samples = np.concatenate([silence(clean_lead), speech[turn]])
        write_take(audio / name, samples)
        takes.append({"turn": turn, "speaker": SPEAKERS[turn], "variant": "", "text": text,
                       "path": f"out/audio_turns/elevenlabs/{name}",
                       "seconds": len(samples) / SAMPLE_RATE})
        timings[name] = even_timings(text, clean_lead)

    # The take text spells its tag ElevenLabs' way while the transcript spells it Dia's way,
    # exactly as make_audio.py leaves it. A fixture that used one spelling for both would hide
    # the whole class of bug where only one of them gets stripped.
    for variant, dia_tag, el_tag, lead in (("a", "(laughs)", "[laughs]", lead_a),
                                            ("b", "(sighs)", "[sighs]", lead_b)):
        name = f"{item_id}__t{voc_turn}__{variant}{ext}"
        # tone (the "vocalization"), a gap, then the same speech tone the clean take has
        samples = np.concatenate([sine_wave(lead, freq=500.0), silence(0.15),
                                   speech[voc_turn]])
        write_take(audio / name, samples)
        takes.append({"turn": voc_turn, "speaker": SPEAKERS[voc_turn], "variant": variant,
                       "text": f"{el_tag} {TURN_TEXTS[voc_turn]}",
                       "dia_tag": dia_tag, "elevenlabs_tag": el_tag,
                       "path": f"out/audio_turns/elevenlabs/{name}",
                       "seconds": len(samples) / SAMPLE_RATE})
        timings[name] = even_timings(TURN_TEXTS[voc_turn], lead + 0.15)

    manifest = {"renderer": "elevenlabs", "items": [{
        "item_id": item_id, "vocalization_turn": voc_turn,
        "vocalization_speaker": SPEAKERS[voc_turn], "takes": takes,
        "assembly": {"gap_seconds": GAP_SECONDS, "turn_order": [1, 2, 3, 4]},
    }]}
    path = audio / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, timings


@pytest.fixture
def take_tree(tmp_path):
    manifest_path, timings = build_take_tree(tmp_path)
    takes = load_turn_takes(manifest_path, root=tmp_path)["t_01a"]
    return takes, StubAligner(timings)


# ------------------------------------------------------------------------- reading the manifest

def test_load_turn_takes_separates_clean_takes_from_variants(take_tree):
    takes, _ = take_tree
    assert takes.turn_order == (1, 2, 3, 4)
    assert sorted(takes.clean) == [1, 2, 3, 4]
    assert sorted(takes.variants) == ["a", "b"]
    assert takes.vocalization_turn == 2
    assert takes.gap_seconds == GAP_SECONDS
    # the clean take of the tagged turn is a sibling of the variants, not a separate turn
    assert takes.clean[2].variant == ""
    assert takes.variants["a"].turn == 2


def test_load_turn_takes_rejects_a_missing_variant(tmp_path):
    manifest_path, _ = build_take_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["items"][0]["takes"] = [t for t in manifest["items"][0]["takes"]
                                      if t.get("variant") != "b"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="expected variants a and b"):
        load_turn_takes(manifest_path, root=tmp_path)


def test_load_turn_takes_rejects_a_variant_on_the_wrong_turn(tmp_path):
    manifest_path, _ = build_take_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    for take in manifest["items"][0]["takes"]:
        if take.get("variant") == "a":
            take["turn"] = 3
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="but the vocalization turn is 2"):
        load_turn_takes(manifest_path, root=tmp_path)


def test_load_turn_takes_rejects_a_missing_clean_take(tmp_path):
    manifest_path, _ = build_take_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["items"][0]["takes"] = [t for t in manifest["items"][0]["takes"]
                                      if not (t["turn"] == 3 and not t.get("variant"))]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=r"no clean take for turn\(s\) \[3\]"):
        load_turn_takes(manifest_path, root=tmp_path)


# ------------------------------------------------------------------------------- the primitives

def test_spoken_text_strips_either_tag_spelling():
    assert spoken_text("[laughs] Looks like it.", ("[laughs]", "[sighs]")) == "Looks like it."
    assert spoken_text("Looks (sighs) like it.", ("(laughs)", "(sighs)")) == "Looks like it."


def test_spoken_text_refuses_to_leave_an_unstripped_tag_for_the_aligner():
    """The bug this guard exists for: the take says [laughs], the transcript says (laughs), and
    stripping only the transcript's spelling hands '[laughs]' to the aligner as a word."""
    with pytest.raises(ValueError, match=r"survived tag stripping"):
        spoken_text("[laughs] Looks like it.", ("(laughs)", "(sighs)"))


def test_tag_spellings_covers_both_the_transcript_and_the_take(take_tree, valid_item):
    takes, _ = take_tree
    spellings = tag_spellings(valid_item, takes)
    assert set(spellings) == {"(laughs)", "(sighs)", "[laughs]", "[sighs]"}


def test_load_turn_takes_rejects_a_tag_the_take_text_does_not_contain(tmp_path):
    manifest_path, _ = build_take_tree(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    for take in manifest["items"][0]["takes"]:
        if take.get("variant") == "a":
            take["elevenlabs_tag"] = "[groans]"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=r"manifest says the take carries '\[groans\]'"):
        load_turn_takes(manifest_path, root=tmp_path)


def test_assemble_puts_the_gap_between_turns_and_nowhere_else():
    turns = [sine_wave(0.2), sine_wave(0.3), sine_wave(0.1)]
    out = assemble(turns, GAP_SECONDS, SAMPLE_RATE)
    gap_samples = int(round(GAP_SECONDS * SAMPLE_RATE))
    assert len(out) == sum(len(t) for t in turns) + 2 * gap_samples
    assert np.array_equal(out[:len(turns[0])], turns[0])          # no leading gap
    assert np.array_equal(out[-len(turns[-1]):], turns[-1])       # no trailing gap
    seam = len(turns[0])
    assert not out[seam:seam + gap_samples].any()


def test_assemble_of_one_turn_adds_no_gap():
    only = sine_wave(0.2)
    assert np.array_equal(assemble([only], GAP_SECONDS, SAMPLE_RATE), only)


def test_assemble_refuses_an_empty_dialogue():
    with pytest.raises(ValueError, match="nothing to assemble"):
        assemble([], GAP_SECONDS, SAMPLE_RATE)


def test_sew_tagged_turn_inserts_without_removing_anything():
    clean = sine_wave(1.0, freq=300.0)
    clip = sine_wave(0.25, freq=500.0)
    spliced, insert_sample, inserted, preserved = sew_tagged_turn(
        clean, SAMPLE_RATE, clip, insert_at=0.4, gap_ms=75.0)

    assert preserved
    assert insert_sample == int(round(0.4 * SAMPLE_RATE))
    assert inserted == len(clip) + int(SAMPLE_RATE * 0.075)
    assert len(spliced) == len(clean) + inserted
    assert np.array_equal(spliced[:insert_sample], clean[:insert_sample])
    assert np.array_equal(spliced[insert_sample + inserted:], clean[insert_sample:])


def test_sew_tagged_turn_clamps_an_insert_point_past_the_end():
    clean = sine_wave(0.5)
    spliced, insert_sample, _, preserved = sew_tagged_turn(
        clean, SAMPLE_RATE, sine_wave(0.1), insert_at=99.0)
    assert insert_sample == len(clean)
    assert preserved
    assert np.array_equal(spliced[:len(clean)], clean)


# ------------------------------------------------------------------------------------- the plan

def _aligned(text: str, timings, tags: tuple[str, ...] = (), speaker: str = "B"):
    return align(take_expected_words(text, speaker, tags),
                  [AsrWord(text=w, start=s, end=e) for w, s, e in timings])


def test_plan_cut_for_a_prefix_tag_runs_from_the_take_start_to_the_first_word(valid_item):
    text = TURN_TEXTS[2]
    variant = _aligned(f"(laughs) {text}", even_timings(text, 0.45), tags=("(laughs)",))
    clean = _aligned(text, even_timings(text, 0.10))

    plan = plan_cut(valid_item, "condition_a", variant, clean, variant_duration=1.6)

    assert plan.position == "prefix"
    assert plan.words_before == 0
    assert plan.anchor_word == "looks"
    assert plan.cut.left == pytest.approx(0.0)          # a prefix tag opens the take
    assert plan.cut.right == pytest.approx(0.45)        # ...and ends at the first word
    assert plan.insert_at == pytest.approx(0.10)        # the CLEAN take's own onset
    assert plan.vocalization == "laugh"


def test_plan_cut_for_an_inline_tag_is_bounded_by_the_words_on_either_side():
    raw = make_raw_item()
    raw["condition_a"]["turns"][1]["text"] = "Looks (laughs) like the safari gave them a new game."
    item = parse_item(raw)
    text = TURN_TEXTS[2]

    # "Looks" ends at 0.2; "like" starts at 0.7 — the tag lives in that half second.
    variant_timings = [("Looks", 0.1, 0.2)] + even_timings(
        "like the safari gave them a new game.", 0.7)
    variant = _aligned("Looks (laughs) like the safari gave them a new game.",
                        variant_timings, tags=("(laughs)",))
    clean = _aligned(text, even_timings(text, 0.10))

    plan = plan_cut(item, "condition_a", variant, clean, variant_duration=1.8)

    assert plan.position == "inline"
    assert plan.words_before == 1
    assert plan.anchor_word == "like"
    assert plan.cut.left == pytest.approx(0.2)
    assert plan.cut.right == pytest.approx(0.7)
    # inserted before "like" as the clean take itself times that word, not as the variant did
    assert plan.insert_at == pytest.approx(0.20)


def test_plan_cut_fails_loudly_when_the_clean_anchor_did_not_align(valid_item):
    text = TURN_TEXTS[2]
    variant = _aligned(f"(laughs) {text}", even_timings(text, 0.45), tags=("(laughs)",))
    # the clean take's alignment is missing the very first word
    clean = _aligned(text, even_timings("like the safari gave them a new game.", 0.10))

    with pytest.raises(BoundaryError, match="did not align"):
        plan_cut(valid_item, "condition_a", variant, clean, variant_duration=1.6)


def test_plan_cut_rejects_a_suffix_tag_on_a_single_turn_take():
    raw = make_raw_item()
    raw["condition_a"]["turns"][1]["text"] = f"{TURN_TEXTS[2]} (laughs)"
    item = parse_item(raw)
    text = TURN_TEXTS[2]
    aligned = _aligned(text, even_timings(text, 0.10))
    with pytest.raises(BoundaryError, match="suffix tags are not supported"):
        plan_cut(item, "condition_a", aligned, aligned, variant_duration=1.6)


# -------------------------------------------------------------------------------- end to end

def test_build_neutral_is_the_clean_takes_in_order(take_tree):
    takes, _ = take_tree
    result = build_neutral(takes)
    gap = int(round(GAP_SECONDS * SAMPLE_RATE))
    expected = sum(len(sf.read(str(takes.clean[t].path))[0]) for t in takes.turn_order)
    assert result.sample_rate == SAMPLE_RATE
    assert len(result.neutral) == expected + 3 * gap
    assert result.sewn == {}          # no model was involved, so nothing was sewn


def test_sew_item_builds_three_dialogues_that_differ_only_by_the_clip(take_tree, valid_item):
    takes, aligner = take_tree
    result = sew_item(valid_item, takes, aligner, SewOptions())

    assert sorted(result.sewn) == ["a", "b"]
    assert not result.issues

    gap = int(round(GAP_SECONDS * SAMPLE_RATE))
    turn_one = len(sf.read(str(takes.clean[1].path))[0])
    for variant in ("a", "b"):
        turn, dialogue = result.turns[variant], result.sewn[variant]
        assert turn.preserved
        assert turn.clip_seconds > 0
        assert len(dialogue) == len(result.neutral) + turn.inserted_length

        # the inserted span sits inside turn 2, which starts after turn 1 and one gap
        at = turn_one + gap + turn.insert_sample
        assert np.array_equal(dialogue[:at], result.neutral[:at])
        assert np.array_equal(dialogue[at + turn.inserted_length:], result.neutral[at:])


def test_the_two_sewn_versions_share_everything_before_the_vocalization(take_tree, valid_item):
    takes, aligner = take_tree
    result = sew_item(valid_item, takes, aligner, SewOptions())
    a, b = result.sewn["a"], result.sewn["b"]
    at = (len(sf.read(str(takes.clean[1].path))[0]) + int(round(GAP_SECONDS * SAMPLE_RATE))
          + result.turns["a"].insert_sample)

    assert result.turns["a"].insert_sample == result.turns["b"].insert_sample
    assert np.array_equal(a[:at], b[:at])
    # ...and the clips themselves are different lengths, so the pair is not accidentally equal
    assert result.turns["a"].inserted_length != result.turns["b"].inserted_length


def test_the_takes_bracketed_tag_never_becomes_a_lexical_word(take_tree, valid_item):
    """Regression. The take text says '[laughs]' and the transcript says '(laughs)'. Stripping
    only the transcript's spelling left '[laughs]' in the text handed to the aligner, which
    then aligned it as word 0 — so the prefix anchor became the laugh itself and the cut window
    collapsed to [0.0, 0.0]. On the real data that refused 18 of 40 conditions and made the
    rest far too short."""
    takes, aligner = take_tree
    assert "[laughs]" in takes.variants["a"].text          # the fixture is the real shape

    result = sew_item(valid_item, takes, aligner, SewOptions())

    for variant in ("a", "b"):
        plan = result.plans[variant]
        assert plan.anchor_word == "looks"                 # the first real word, not "laughs"
        assert plan.cut.right > plan.cut.left              # a window that actually contains it
        assert plan.cut.duration > 0.1
        assert variant in result.sewn
    takes, aligner = take_tree
    result = sew_item(valid_item, takes, aligner, SewOptions())

    plan_a = result.plans["a"]
    assert plan_a.position == "prefix"
    assert plan_a.cut.left == pytest.approx(0.0)
    assert plan_a.cut.right == pytest.approx(0.45)      # 0.30 lead + 0.15 gap
    # the 0.30s tone, plus the trim's padding, and well short of the 0.45s window
    assert 0.30 <= result.turns["a"].clip_seconds <= 0.45
    assert plan_a.insert_at == pytest.approx(0.10)      # the clean take's own first onset


def test_sew_item_aligns_the_clean_take_once_not_once_per_condition(take_tree, valid_item):
    takes, aligner = take_tree
    sew_item(valid_item, takes, aligner, SewOptions())

    assert aligner.calls.count(takes.clean[2].path.name) == 1
    assert aligner.calls.count(takes.variants["a"].path.name) == 1
    assert aligner.calls.count(takes.variants["b"].path.name) == 1
    # the untagged turns are never aligned: nothing is cut from them
    untagged = {takes.clean[t].path.name for t in (1, 3, 4)}
    assert not untagged & set(aligner.calls)


def test_match_loudness_changes_the_clip_but_still_preserves_the_words(take_tree, valid_item):
    takes, aligner = take_tree
    plain = sew_item(valid_item, takes, aligner, SewOptions(match_loudness=False))
    matched = sew_item(valid_item, takes, StubAligner(aligner.timings),
                        SewOptions(match_loudness=True))

    assert plain.turns["a"].loudness_delta_db != 0.0    # measured either way
    assert matched.turns["a"].preserved
    at_plain = plain.turns["a"].insert_sample
    assert np.array_equal(matched.turns["a"].samples[:at_plain],
                           plain.turns["a"].samples[:at_plain])


def test_the_whole_path_works_on_mp3_takes(tmp_path, valid_item):
    """The renderer writes mp3, and read_take leans on soundfile to decode it. The takes are
    decoded exactly once and spliced as arrays, so the preservation guarantee is unaffected by
    the source being lossy — only the trim boundaries move, since the codec smears the edges.
    """
    manifest_path, timings = build_take_tree(tmp_path, ext=".mp3")
    takes = load_turn_takes(manifest_path, root=tmp_path)["t_01a"]
    assert takes.clean[2].path.suffix == ".mp3"

    result = sew_item(valid_item, takes, StubAligner(timings), SewOptions())

    gap = int(round(GAP_SECONDS * SAMPLE_RATE))
    turn_one = len(sf.read(str(takes.clean[1].path))[0])
    for variant in ("a", "b"):
        turn, dialogue = result.turns[variant], result.sewn[variant]
        assert turn.preserved
        assert turn.clip_seconds > 0
        at = turn_one + gap + turn.insert_sample
        assert np.array_equal(dialogue[:at], result.neutral[:at])
        assert np.array_equal(dialogue[at + turn.inserted_length:], result.neutral[at:])


def test_a_silent_vocalized_take_is_refused_rather_than_spliced(tmp_path, valid_item):
    """If the take has no energy where the tag was asked for, there is nothing to splice. The
    condition must be refused outright — emitting a `_sewn_laugh` file that is silently
    identical to neutral would be worse than emitting none, because it would still get scored
    as a laugh."""
    manifest_path, timings = build_take_tree(tmp_path)
    takes = load_turn_takes(manifest_path, root=tmp_path)["t_01a"]
    # overwrite variant a with a take whose lead is silent
    write_take(takes.variants["a"].path,
                np.concatenate([silence(0.45), sine_wave(1.0, freq=300.0)]))

    result = sew_item(valid_item, takes, StubAligner(timings), SewOptions())

    assert "a" not in result.sewn                              # no misleading file
    assert "silence floor" in result.failed["a"]
    assert any("not spliced" in issue for issue in result.issues)
    assert result.turns["a"].inserted_length == 0
    assert "b" in result.sewn                                  # b is unaffected
    assert result.turns["b"].inserted_length > 0


def test_a_condition_whose_anchor_will_not_align_does_not_cost_the_other_one(tmp_path,
                                                                              valid_item):
    manifest_path, timings = build_take_tree(tmp_path)
    takes = load_turn_takes(manifest_path, root=tmp_path)["t_01a"]
    # variant a's alignment loses the anchor word, so the cut has no right-hand boundary
    timings[takes.variants["a"].path.name] = even_timings(
        "like the safari gave them a new game.", 0.45)

    result = sew_item(valid_item, takes, StubAligner(timings), SewOptions())

    assert "a" not in result.sewn
    assert "did not align" in result.failed["a"]
    assert "b" in result.sewn                                  # and b still came out
    assert result.turns["b"].preserved
    assert len(result.neutral) > 0                             # as did the neutral dialogue

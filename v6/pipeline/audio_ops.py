"""WAV I/O, energy-based trimming, fades, splicing, and waveform-preservation checks.

Everything here works on plain float64 numpy arrays in [-1, 1] and never depends on Dia or
Whisper being installed, so it is fully unit-testable on synthetic tones.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class AudioClip:
    samples: np.ndarray  # (n,) mono or (n, channels), float64
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate


def read_wav(path: str) -> AudioClip:
    samples, sample_rate = sf.read(path, always_2d=False, dtype="float64")
    return AudioClip(samples=samples, sample_rate=sample_rate)


def write_wav(path: str, clip: AudioClip, subtype: str = "PCM_16") -> None:
    peak = np.max(np.abs(clip.samples)) if clip.samples.size else 0.0
    if peak > 1.0:
        raise ValueError(f"refusing to write clipped audio: peak={peak:.4f} > 1.0")
    sf.write(path, clip.samples, clip.sample_rate, subtype=subtype)


def slice_seconds(clip: AudioClip, start_s: float, end_s: float) -> np.ndarray:
    start = max(0, int(round(start_s * clip.sample_rate)))
    end = min(len(clip.samples), int(round(end_s * clip.sample_rate)))
    return clip.samples[start:end]


def rms_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
    return 20.0 * np.log10(rms) if rms > 0 else float("-inf")


def trim_silence(samples: np.ndarray, sample_rate: int, frame_ms: float = 10.0,
                  threshold_db: float = -40.0, pad_ms: float = 75.0,
                  merge_gap_ms: float = 150.0,
                  anchor: str = "largest") -> tuple[int, int]:
    """Energy-based trim: the (start, end) sample indices of the region containing acoustic
    activity, padded by ~pad_ms of surrounding context on each side.

    `anchor` picks which activity is "the" vocalization:

    - "first"   — span the first activity through the last. Correct when the caller knows the
                  vocalization leads the window (a prefix tag in a single-turn take), and the
                  only thing that can follow it inside the window is the vocalization's own
                  later bursts or the breath before the next word.
    - "largest" — the largest merged region wins. For a window bounded by real words on both
                  sides (full-conversation takes, inline tags), where the edges may hold
                  neighbour speech that must lose.

    `threshold_db` is relative to this clip's own peak, so it adapts to the clip's own level
    rather than assuming an absolute loudness. Returns (0, len(samples)) — i.e. no trim — if
    no frame ever crosses the threshold, since that signals "nothing acoustically present"
    rather than "trim everything," and callers should treat that as a validation failure.
    """
    n = len(samples)
    if n == 0:
        return 0, 0
    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    peak = float(np.max(np.abs(samples))) or 1e-12
    active_frames = []
    for start in range(0, n, frame_len):
        frame = samples[start:start + frame_len]
        rms = float(np.sqrt(np.mean(np.square(frame))))
        db = 20.0 * np.log10(rms / peak) if rms > 0 else float("-inf")
        active_frames.append(db >= threshold_db)
    if not any(active_frames):
        return 0, n

    # The largest *contiguous* active region, not first-active..last-active. The window handed
    # to us is bounded by neighbouring words' timestamps, and Whisper's boundaries leak: a word
    # keeps decaying past its recorded end, and the breath before the next word starts before
    # its recorded onset. Spanning first..last therefore unions the vocalization with whatever
    # neighbour energy sits at the window edges, which is exactly how a 0.6s laugh came back as
    # a 1.18s clip whose first 0.47s was the tail of "...like lions."
    #
    # Regions separated by less than `merge_gap_ms` are merged first, because a laugh is
    # rhythmic — several bursts with short gaps — and must not be split into its own pieces.
    # A neighbour word sits much further off than one burst-gap, so it stays a separate region
    # and loses the size comparison.
    merge_gap_frames = max(1, int(merge_gap_ms / frame_ms))
    regions: list[list[int]] = []
    for index, active in enumerate(active_frames):
        if not active:
            continue
        if regions and index - regions[-1][1] <= merge_gap_frames:
            regions[-1][1] = index
        else:
            regions.append([index, index])

    if anchor == "first":
        # We know from the transcript that the vocalization comes first: a prefix tag in a
        # take that contains only the tagged turn has nothing before it. So span from the
        # first activity to the last, instead of guessing which region is "the" vocalization.
        # Size is a bad proxy — a real laugh here was three bursts spanning 1.0s, and the
        # single loudest region in the window was the following word.
        first, last = regions[0][0], regions[-1][1]
    else:
        first, last = max(regions, key=lambda r: r[1] - r[0])

    pad = int(sample_rate * pad_ms / 1000)
    start_sample = max(0, first * frame_len - pad)
    end_sample = min(n, (last + 1) * frame_len + pad)
    return start_sample, end_sample


def speech_bounds(samples: np.ndarray, sample_rate: int, approx_start: float,
                   approx_end: float, search_ms: float = 300.0, threshold_db: float = -35.0,
                   frame_ms: float = 10.0, max_gap_ms: float = 120.0) -> tuple[float, float]:
    """Snap a Whisper word interval to where the speech actually is, in seconds.

    Whisper's word timestamps are approximate and here run consistently *early* — it reported
    "Looks" at 2.70-3.10s in a baseline whose audio is silent until 3.00s. Taking those numbers
    literally meant cutting a carried word that wasn't inside the cut, and replacing a span of
    baseline that was mostly silence plus the word's first 100 ms. 14 of 40 conditions carried
    near-silence because of it.

    So the timestamps are treated as a *hint*: search +/- `search_ms` around them for the real
    onset and offset, thresholding against the loudest frame in that neighbourhood. Gaps
    shorter than `max_gap_ms` are bridged, so a stop consonant inside a word doesn't end it.
    Falls back to the supplied bounds when the region holds no speech at all.
    """
    n = len(samples)
    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    lo = max(0, int((approx_start - search_ms / 1000) * sample_rate))
    hi = min(n, int((approx_end + search_ms / 1000) * sample_rate))
    if hi <= lo:
        return approx_start, approx_end

    region = samples[lo:hi]
    peak = float(np.max(np.abs(region))) or 1e-12
    active = []
    for start in range(0, len(region), frame_len):
        frame = region[start:start + frame_len]
        rms = float(np.sqrt(np.mean(np.square(frame))))
        db = 20.0 * np.log10(rms / peak) if rms > 0 else float("-inf")
        active.append(db >= threshold_db)
    if not any(active):
        return approx_start, approx_end

    gap_frames = max(1, int(max_gap_ms / frame_ms))
    regions: list[list[int]] = []
    for index, is_active in enumerate(active):
        if not is_active:
            continue
        if regions and index - regions[-1][1] <= gap_frames:
            regions[-1][1] = index
        else:
            regions.append([index, index])

    # The run nearest the hinted centre, so a neighbouring word inside the search window
    # doesn't win just by being louder.
    centre = ((approx_start + approx_end) / 2 * sample_rate - lo) / frame_len
    first, last = min(regions, key=lambda r: abs((r[0] + r[1]) / 2 - centre))
    return (lo + first * frame_len) / sample_rate, (lo + (last + 1) * frame_len) / sample_rate


def apply_fade(samples: np.ndarray, sample_rate: int, fade_ms: float = 5.0) -> np.ndarray:
    """Short linear fade in/out on `samples`, to prevent clicks at clip boundaries."""
    samples = samples.astype(np.float64).copy()
    n = len(samples)
    fade_len = min(n // 2, int(sample_rate * fade_ms / 1000))
    if fade_len > 0:
        ramp = np.linspace(0.0, 1.0, fade_len)
        samples[:fade_len] *= ramp
        samples[-fade_len:] *= ramp[::-1]
    return samples


def match_loudness(samples: np.ndarray, target_dbfs: float,
                    max_adjust_db: float = 6.0) -> tuple[np.ndarray, float]:
    """Scale `samples` toward `target_dbfs`, clamped to +/- max_adjust_db, never clipping.
    Returns (adjusted_samples, applied_delta_db)."""
    current = rms_dbfs(samples)
    if not np.isfinite(current):
        return samples.astype(np.float64).copy(), 0.0
    delta_db = float(np.clip(target_dbfs - current, -max_adjust_db, max_adjust_db))
    gain = 10.0 ** (delta_db / 20.0)
    adjusted = samples.astype(np.float64) * gain
    peak = float(np.max(np.abs(adjusted))) if adjusted.size else 0.0
    if peak > 0.999:
        adjusted *= 0.999 / peak
    return adjusted, delta_db



def splice_replace(baseline: np.ndarray, start_sample: int, end_sample: int,
                    replacement: np.ndarray, sample_rate: int,
                    gap_ms: float = 0.0) -> tuple[np.ndarray, int]:
    """`baseline` with the span [start_sample, end_sample) replaced by `replacement`, plus an
    optional short gap of silence before the baseline resumes.

    A pure insertion is the degenerate case where the replaced span is empty
    (`end_sample == start_sample`) — see `splice_insert`. A non-empty span is what carrying
    words requires: the clip already contains the baseline's own next word(s) as rendered in
    the vocalized take, so the baseline copy of those words has to come out or they would be
    spoken twice.

    Returns (spliced, inserted_length), where `inserted_length` is how many samples now sit
    where the replaced span used to be — what `verify_waveform_preserved` needs.
    """
    if end_sample < start_sample:
        raise ValueError(f"replaced span is negative: [{start_sample}, {end_sample})")
    gap = np.zeros(int(sample_rate * gap_ms / 1000), dtype=np.float64)
    inserted = np.concatenate([replacement, gap])
    spliced = np.concatenate([baseline[:start_sample], inserted, baseline[end_sample:]])
    return spliced, len(inserted)


def splice_insert(baseline: np.ndarray, insert_at_sample: int, vocalization: np.ndarray,
                   sample_rate: int, gap_ms: float = 75.0) -> tuple[np.ndarray, int]:
    """`baseline` with `vocalization` inserted at `insert_at_sample`, followed by a short
    natural gap of silence before the baseline resumes. Nothing is removed."""
    return splice_replace(baseline, insert_at_sample, insert_at_sample, vocalization,
                           sample_rate, gap_ms)


def verify_waveform_preserved(baseline: np.ndarray, spliced: np.ndarray,
                               start_sample: int, inserted_length: int,
                               replaced_length: int = 0) -> bool:
    """True iff everything outside the spliced segment is bit-identical to `baseline`.

    `replaced_length` is how many baseline samples the splice removed (0 for a pure
    insertion). The check deliberately says nothing about the spliced segment itself — that
    span is *meant* to differ — only that the audio on either side of it is the untouched
    baseline.
    """
    before_ok = np.array_equal(spliced[:start_sample], baseline[:start_sample])
    tail_start = start_sample + inserted_length
    after_ok = np.array_equal(spliced[tail_start:], baseline[start_sample + replaced_length:])
    return before_ok and after_ok

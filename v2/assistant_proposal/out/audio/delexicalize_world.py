# delexicalize_world.py

import argparse
from pathlib import Path

import librosa
import numpy as np
import pyworld as pw
import soundfile as sf


EPS = 1e-12


def get_template(sp, mask):
    """
    Compute a time-invariant spectral template in log domain.
    We separately estimate voiced/unvoiced templates.
    """
    if np.sum(mask) < 3:
        # fallback: use all frames
        mask = np.ones(sp.shape[0], dtype=bool)

    log_sp = np.log(np.maximum(sp[mask], EPS))

    # Median is more robust than mean
    template = np.exp(np.median(log_sp, axis=0))

    return template


def scale_template_to_frame_energy(template, original_sp):
    """
    Replicate the same spectral shape for every frame,
    but preserve the original frame-by-frame spectral energy.
    """
    template_energy = np.sum(template) + EPS
    original_energy = np.sum(original_sp, axis=1) + EPS

    scale = original_energy / template_energy

    return template[None, :] * scale[:, None]


def delexicalize_sp(sp, f0, strength=0.9):
    """
    Remove phonetic/spectral-envelope dynamics while preserving
    gross prosody.

    strength:
        0.0 = original spectral envelope
        1.0 = completely time-invariant spectral shape
    """

    voiced = f0 > 0
    unvoiced = ~voiced

    voiced_template = get_template(sp, voiced)
    unvoiced_template = get_template(sp, unvoiced)

    neutral_sp = np.zeros_like(sp)

    if np.any(voiced):
        neutral_sp[voiced] = scale_template_to_frame_energy(
            voiced_template,
            sp[voiced]
        )

    if np.any(unvoiced):
        neutral_sp[unvoiced] = scale_template_to_frame_energy(
            unvoiced_template,
            sp[unvoiced]
        )

    # Blend in log-spectral space.
    # This tends to sound better than linear interpolation.
    log_original = np.log(np.maximum(sp, EPS))
    log_neutral = np.log(np.maximum(neutral_sp, EPS))

    new_sp = np.exp(
        (1.0 - strength) * log_original
        + strength * log_neutral
    )

    # Re-normalize every frame so its energy matches the original.
    original_energy = np.sum(sp, axis=1) + EPS
    new_energy = np.sum(new_sp, axis=1) + EPS

    new_sp *= (original_energy / new_energy)[:, None]

    return new_sp


def process(input_file, output_file, strength=0.9, sr=24000):
    print(f"Loading: {input_file}")

    # WORLD expects double precision.
    # librosa also converts stereo -> mono here.
    x, fs = librosa.load(
        input_file,
        sr=sr,
        mono=True,
        dtype=np.float64
    )

    # Avoid clipping / weird amplitudes
    peak = np.max(np.abs(x))
    if peak > 0:
        x = x / peak * 0.95

    print(f"Sample rate: {fs}")
    print(f"Duration: {len(x) / fs:.2f}s")

    # WORLD analysis
    print("Running WORLD analysis...")

    # harvest tends to be a little more robust for expressive/noisy speech.
    f0, timeaxis = pw.harvest(
        x,
        fs,
        f0_floor=50.0,
        f0_ceil=800.0
    )

    # Refine F0
    f0 = pw.stonemask(
        x,
        f0,
        timeaxis,
        fs
    )

    # Spectral envelope
    sp = pw.cheaptrick(
        x,
        f0,
        timeaxis,
        fs
    )

    # Aperiodicity
    ap = pw.d4c(
        x,
        f0,
        timeaxis,
        fs
    )

    print("Delexicalizing spectral envelope...")
    new_sp = delexicalize_sp(
        sp,
        f0,
        strength=strength
    )

    print("Synthesizing...")
    y = pw.synthesize(
        f0.astype(np.float64),
        new_sp.astype(np.float64),
        ap.astype(np.float64),
        fs
    )

    # Normalize output safely
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak * 0.95

    sf.write(
        output_file,
        y.astype(np.float32),
        fs
    )

    print(f"Saved: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input",
        help="Input audio file, e.g. test_sample.mp3"
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output WAV file"
    )

    parser.add_argument(
        "--strength",
        type=float,
        default=0.9,
        help="Delexicalization strength: 0=original, 1=maximum (default 0.9)"
    )

    parser.add_argument(
        "--sr",
        type=int,
        default=24000,
        help="Working sample rate (default 24000)"
    )

    args = parser.parse_args()

    if not 0.0 <= args.strength <= 1.0:
        raise ValueError("--strength must be between 0 and 1")

    input_path = Path(args.input)

    if args.output is None:
        output_path = input_path.with_name(
            f"{input_path.stem}_delex_{args.strength:.2f}.wav"
        )
    else:
        output_path = Path(args.output)

    process(
        str(input_path),
        str(output_path),
        strength=args.strength,
        sr=args.sr
    )
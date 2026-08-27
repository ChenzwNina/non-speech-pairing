"""Concatenate audio files and generated silences into one track.

Lifted out of prior_test/logo_sketch so the benchmark does not import across folders — and
because both files were called make_audio.py, which meant importing this one made it import
itself instead of the helper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def build(pieces: list[tuple[str, object]], dest: Path) -> None:
    """`pieces` entries are ("file", Path) or ("silence", seconds)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[Path] = [value for kind, value in pieces if kind == "file"]  # type: ignore
    parts: list[str] = []
    labels: list[str] = []
    index = 0

    for order, (kind, value) in enumerate(pieces):
        label = f"s{order}"
        if kind == "silence":
            parts.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{value},"
                         f"aformat=sample_fmts=fltp[{label}]")
        else:
            parts.append(f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
                         f"channel_layouts=stereo[{label}]")
            index += 1
        labels.append(f"[{label}]")

    # the trailing aresample avoids a libmp3lame "inadequate AVFrame plane padding" bug
    filt = (";".join(parts) + ";" + "".join(labels)
            + f"concat=n={len(labels)}:v=0:a=1[cat];[cat]aresample=44100[out]")
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path in inputs:
        command += ["-i", str(path)]
    command += ["-filter_complex", filt, "-map", "[out]", "-c:a", "libmp3lame",
                "-q:a", "2", str(dest)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-900:] if result.stderr else "ffmpeg failed")

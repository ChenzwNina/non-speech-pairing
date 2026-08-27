"""Render the logo-nudging sketch as a two-voice audio file.

MAN and AGENT get different ElevenLabs voices. Stage directions and the bare "…" turns are
not spoken — they become measured silence, because in a sketch like this the pauses are the
joke. The dead air after "Would you like me to add it back?" is doing more comedic work than
any line in the script.

The defeated laugh is synthesized in MAN's own voice rather than spliced in from a real
recording. Elsewhere in this repo real recordings are correct, since only the sound matters
there; here the laugh has to come from the same character, so a stranger's laughter would
break it.

Usage:
    python logo_sketch/make_audio.py
    python logo_sketch/make_audio.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

OUT_DIR = HERE / "out"
LINE_DIR = OUT_DIR / "lines"
FINAL = OUT_DIR / "logo_sketch.mp3"
TRANSCRIPT = OUT_DIR / "logo_sketch_transcript.md"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICES = {
    "MAN": "s3TPKV1kjDlVtZbl4Ksh",
    "AGENT": "aKw9UnnjRq5scbeeGI7Z",
}

# how expressive each voice is allowed to be. Lower stability = more variation, which suits
# a man slowly losing his grip; the agent stays flatly, cheerfully consistent throughout.
STABILITY = {"MAN": 0.35, "AGENT": 0.6}

DEFAULT_GAP = 0.34          # ordinary turn-to-turn beat
BEAT = "beat"               # marker for an explicit silence entry

# (speaker, text) for spoken turns, or (BEAT, seconds) for silence.
# Leading "…" in the source becomes a pause entry rather than punctuation the voice reads.
SCRIPT: list[tuple[str, object]] = [
    ("MAN", "Okay, just move the logo a little to the left."),
    ("AGENT", "Done."),
    ("MAN", "No, that's way too far left. Move it back a little."),
    ("AGENT", "Got it."),
    ("MAN", "Now it's on the right."),
    ("AGENT", "Ah. Let me fix that."),
    ("MAN", "Please do."),
    ("AGENT", "How about now?"),
    ("MAN", "You made it bigger."),
    ("AGENT", "Right. I'll make it smaller."),
    ("MAN", "No, keep the size. Just move it slightly left."),
    ("AGENT", "Understood."),
    (BEAT, 0.9),
    ("MAN", "Why is it at the bottom now?"),
    ("AGENT", "I thought it would look cleaner there."),
    ("MAN", "I didn't ask you to redesign it. Put it back at the top and move it just a "
            "tiny bit left."),
    ("AGENT", "Absolutely."),
    (BEAT, 1.6),                                    # MAN: … (says nothing)
    ("AGENT", "Better?"),
    ("MAN", "You changed the font."),
    ("AGENT", "I can change it back."),
    ("MAN", "Yes. Please. Change the font back, keep everything else exactly the same, "
            "and move the logo — just a little — to the left."),
    ("AGENT", "Done!"),
    (BEAT, 0.9),
    ("MAN", "Now the logo is gone."),
    ("AGENT", "Would you like me to add it back?"),
    (BEAT, 2.2),                                    # *stares at the screen*
    ("MAN", "Heh… heh… hahaha. Yeah. Sure. You know what? This is fine."),
    ("AGENT", "Great! Glad we got it right."),
    ("MAN", "Yep. Perfect."),
]


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(
        client.text_to_speech.convert(
            voice_id=VOICES[speaker],
            text=text,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=STABILITY[speaker]),
        )
    )
    dest.write_bytes(audio)


def duration_of(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def build(pieces: list[tuple[str, object]], dest: Path) -> None:
    """Concatenate speech files and generated silences into one track.

    `pieces` entries are ("file", Path) or ("silence", seconds).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[Path] = [value for kind, value in pieces if kind == "file"]  # type: ignore[misc]
    parts: list[str] = []
    labels: list[str] = []
    input_index = 0

    for order, (kind, value) in enumerate(pieces):
        label = f"s{order}"
        if kind == "silence":
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=0:{value},"
                f"aformat=sample_fmts=fltp[{label}]"
            )
        else:
            parts.append(
                f"[{input_index}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
                f"channel_layouts=stereo[{label}]"
            )
            input_index += 1
        labels.append(f"[{label}]")

    # trailing aresample avoids a known libmp3lame "inadequate AVFrame plane padding" bug
    filt = (
        ";".join(parts) + ";" + "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1[cat];[cat]aresample=44100[out]"
    )
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path in inputs:
        command += ["-i", str(path)]
    command += [
        "-filter_complex", filt, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(dest)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-900:] if result.stderr else "ffmpeg failed")


def timestamp(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="re-synthesize every line")
    parser.add_argument("--out", type=Path, default=FINAL)
    args = parser.parse_args()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    spoken = [entry for entry in SCRIPT if entry[0] != BEAT]
    print(f"{len(spoken)} spoken line(s), {len(SCRIPT) - len(spoken)} silent beat(s)", flush=True)

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []
    line_number = 0

    for order, (speaker, value) in enumerate(SCRIPT):
        if speaker == BEAT:
            pieces.append(("silence", float(value)))
            rows.append({"kind": "beat", "seconds": float(value)})
            continue

        line_number += 1
        text = str(value)
        path = LINE_DIR / f"{line_number:02d}_{speaker.lower()}.mp3"
        if not path.exists() or args.overwrite:
            synthesize(client, text, speaker, path)
            time.sleep(0.25)
            print(f"  [{line_number:02d}] {speaker:5} {text[:58]}", flush=True)

        if pieces and pieces[-1][0] != "silence":
            pieces.append(("silence", DEFAULT_GAP))
            rows.append({"kind": "gap", "seconds": DEFAULT_GAP})
        pieces.append(("file", path))
        rows.append({
            "kind": "line", "speaker": speaker, "text": text,
            "seconds": round(duration_of(path), 3),
        })

    build(pieces, args.out)
    total = duration_of(args.out)

    # transcript with running timestamps, so the beats are auditable
    lines = [
        "# The logo sketch",
        "",
        f"Total runtime **{timestamp(total)}** · MAN and AGENT are different voices · "
        "stage directions and the silent turns are rendered as pauses, not spoken.",
        "",
        "| time | speaker | line |",
        "| --- | --- | --- |",
    ]
    clock = 0.0
    for row in rows:
        if row["kind"] == "line":
            lines.append(
                f"| {timestamp(clock)} | {row['speaker']} | {row['text'].replace('|', '-')} |"
            )
        elif row["kind"] == "beat":
            lines.append(f"| {timestamp(clock)} | *(beat)* | *{row['seconds']:.1f}s of silence* |")
        clock += row["seconds"]
    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / "timing.json").write_text(
        json.dumps({"total_seconds": round(total, 3), "default_gap": DEFAULT_GAP,
                    "voices": VOICES, "stability": STABILITY, "segments": rows},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nwrote {args.out}  ({timestamp(total)})", flush=True)
    print(f"transcript: {TRANSCRIPT}", flush=True)


if __name__ == "__main__":
    main()

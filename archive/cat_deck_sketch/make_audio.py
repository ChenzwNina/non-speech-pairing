"""Render the cat-slide sketch: five laughs, one category, five different meanings.

    1. MAYA  warm, genuine amusement at Dan's joke
    2. DAN   nervous chuckle as he realises what he sent
    3. DAN   dry, sarcastic laugh at "Interesting use of Comic Sans"
    4. DAN   suppressed laughter that breaks into helpless real laughter
    5. DAN   laughing while apologising

All five are laughter. Only acoustics and position in the conversation separate them, which
is what makes this a harder probe than the logo sketch's single defeated laugh.

Getting five distinguishable laughs out of TTS is the hard part. eleven_v3 audio tags do the
work — spliced recordings would break character continuity, and Dan laughs four times in
four different ways, so his laughs have to be recognisably the same person.

Turn 18 is laughter with no words at all, which TTS handles badly on its own; it is written
with vocal onomatopoeia so there is something to render.

Usage:
    python cat_deck_sketch/make_audio.py
    python cat_deck_sketch/make_audio.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

# voice-agnostic ffmpeg glue, shared with the logo sketch
from make_audio import build, duration_of, timestamp  # noqa: E402

OUT_DIR = HERE / "out"
LINE_DIR = OUT_DIR / "lines"
FINAL = OUT_DIR / "cat_deck_sketch.mp3"
TRANSCRIPT = OUT_DIR / "cat_deck_transcript.md"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICES = {
    "MAYA": "aKw9UnnjRq5scbeeGI7Z",
    "DAN": "s3TPKV1kjDlVtZbl4Ksh",
}

# low stability on both: five distinct laughs need room to vary. Robust settings flatten
# laughter into something that reads as speech.
STABILITY = {"MAYA": 0.3, "DAN": 0.25}

DEFAULT_GAP = 0.32
BEAT = "beat"

# Each laugh carries an audio tag naming its quality, plus written vocalisation so there is
# phonetic material even where the tag is ignored. `laugh` marks the turns under test.
SCRIPT: list[tuple[str, object]] = [
    ("MAYA", "Did you really put a picture of a cat on the final slide?"),
    ("DAN", "It improves shareholder confidence."),
    ("MAYA", "[laughs warmly] Hah! Okay, that was actually funny.", "laugh_1_genuine"),
    ("DAN", "Anyway, I sent the deck to the client."),
    ("MAYA", "You sent it already?"),
    ("DAN", "Yeah."),
    ("MAYA", "Which version?"),
    ("DAN", "The one on the desktop."),
    ("MAYA", "That was the unfinished version."),
    (BEAT, 0.7),
    ("DAN", "[nervous chuckle] Heh. Oh. Uh… was it?", "laugh_2_nervous"),
    ("MAYA", "Dan."),
    ("DAN", "I can fix it. They probably haven't opened it yet."),
    ("MAYA", "They replied two minutes ago."),
    ("DAN", "What did they say?"),
    ("MAYA", "\"Interesting use of Comic Sans.\""),
    (BEAT, 0.5),
    ("DAN", "[dry sarcastic laugh] Ha. Great. Fantastic.", "laugh_3_sarcastic"),
    ("MAYA", "Wait, there's more. They said, \"And please tell us the cat will be "
             "attending tomorrow's meeting.\""),
    (BEAT, 0.6),
    ("DAN", "[stifling laughter] Pff— hah— [bursts into helpless laughter] "
            "hahahaha!", "laugh_4_helpless"),
    ("MAYA", "Don't laugh!"),
    ("DAN", "I'm sorry— [still laughing] —I know this is terrible.", "laugh_5_apologetic"),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--out", type=Path, default=FINAL)
    args = parser.parse_args()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    spoken = [e for e in SCRIPT if e[0] != BEAT]
    laughs = [e for e in spoken if len(e) > 2]
    print(
        f"{len(spoken)} spoken line(s), {len(SCRIPT) - len(spoken)} beat(s), "
        f"{len(laughs)} laugh(s) under test",
        flush=True,
    )

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []
    line_number = 0

    for entry in SCRIPT:
        speaker, value = entry[0], entry[1]
        if speaker == BEAT:
            pieces.append(("silence", float(value)))
            rows.append({"kind": "beat", "seconds": float(value)})
            continue

        line_number += 1
        text = str(value)
        laugh_id = entry[2] if len(entry) > 2 else None
        path = LINE_DIR / f"{line_number:02d}_{speaker.lower()}.mp3"
        if not path.exists() or args.overwrite:
            synthesize(client, text, speaker, path)
            time.sleep(0.25)
        tag = f"  <- {laugh_id}" if laugh_id else ""
        print(f"  [{line_number:02d}] {speaker:5} {text[:56]}{tag}", flush=True)

        if pieces and pieces[-1][0] != "silence":
            pieces.append(("silence", DEFAULT_GAP))
            rows.append({"kind": "gap", "seconds": DEFAULT_GAP})
        pieces.append(("file", path))
        rows.append({
            "kind": "line", "speaker": speaker, "text": text, "laugh_id": laugh_id,
            "seconds": round(duration_of(path), 3),
        })

    build(pieces, args.out)
    total = duration_of(args.out)

    lines = [
        "# The cat-slide sketch",
        "",
        f"Total runtime **{timestamp(total)}** · MAYA and DAN are different voices · "
        f"{len(laughs)} laughs, all the same category, five different meanings.",
        "",
        "| time | speaker | line | laugh |",
        "| --- | --- | --- | --- |",
    ]
    clock = 0.0
    laugh_times: list[dict] = []
    for row in rows:
        if row["kind"] == "line":
            lines.append(
                f"| {timestamp(clock)} | {row['speaker']} | "
                f"{row['text'].replace('|', '-')} | {row['laugh_id'] or ''} |"
            )
            if row["laugh_id"]:
                laugh_times.append({
                    "laugh_id": row["laugh_id"], "speaker": row["speaker"],
                    "at": timestamp(clock), "at_seconds": round(clock, 2),
                })
        elif row["kind"] == "beat":
            lines.append(f"| {timestamp(clock)} | *(beat)* | *{row['seconds']:.1f}s* | |")
        clock += row["seconds"]
    lines += ["", "## Laughs", ""]
    for item in laugh_times:
        lines.append(f"- **{item['at']}** {item['speaker']} — `{item['laugh_id']}`")
    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / "timing.json").write_text(
        json.dumps({"total_seconds": round(total, 3), "voices": VOICES,
                    "stability": STABILITY, "laughs": laugh_times, "segments": rows},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}  ({timestamp(total)})", flush=True)
    for item in laugh_times:
        print(f"  {item['at']}  {item['speaker']:5} {item['laugh_id']}", flush=True)
    print(f"transcript: {TRANSCRIPT}", flush=True)


if __name__ == "__main__":
    main()

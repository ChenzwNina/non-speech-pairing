"""Build a clip that keeps the scene through B's haha, then stops.

Turns 1–8 are unchanged. B's laugh turn is only the sarcastic haha
(no "Perfect timing"). C's last line is omitted.

Usage:
    python printer_jam/clip_through_haha.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DIALOGUE = HERE / "dialogue.json"
OUT_DIR = HERE / "out"
CLIPPED = OUT_DIR / "dialogue_through_haha.mp3"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICES = {
    "A": "r1KmysJdVYZjJCm4mL3b",
    "B": "IKne3meq5aSn9XLyUdCD",
    "C": "C3x1TEM7scV4p2AXJyrp",
}
HAHA_TTS = "[sarcastic] ha... ha..."


def collect_bytes(chunks) -> bytes:
    return b"".join(chunks)


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(DIALOGUE.read_text(encoding="utf-8"))
    turns = payload["turns"]
    laugh_idx = int(payload.get("laugh_turn") or 9) - 1
    inputs = []
    for i, turn in enumerate(turns):
        if i < laugh_idx:
            text = turn["tts"]
        elif i == laugh_idx:
            text = HAHA_TTS
        else:
            break
        inputs.append({"text": text, "voice_id": VOICES[turn["speaker"]]})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)
    print(f"model: {MODEL}  turns: {len(inputs)}  last: {inputs[-1]['text']}")
    audio = collect_bytes(
        client.text_to_dialogue.convert(
            inputs=inputs,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            settings=ModelSettingsResponseModel(stability=0.4),
        )
    )
    if not audio:
        raise SystemExit("empty audio response")
    CLIPPED.write_bytes(audio)
    print(f"wrote {CLIPPED} ({len(audio)} bytes)")


if __name__ == "__main__":
    main()

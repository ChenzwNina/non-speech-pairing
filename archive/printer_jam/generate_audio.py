"""Synthesize the printer-jam dialogue as one ElevenLabs v3 clip.

Usage:
    python printer_jam/generate_audio.py
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
AUDIO = OUT_DIR / "dialogue.mp3"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICES = {
    "A": "r1KmysJdVYZjJCm4mL3b",
    "B": "IKne3meq5aSn9XLyUdCD",
    "C": "C3x1TEM7scV4p2AXJyrp",
}


def collect_bytes(chunks) -> bytes:
    return b"".join(chunks)


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(DIALOGUE.read_text(encoding="utf-8"))
    inputs = [
        {"text": turn["tts"], "voice_id": VOICES[turn["speaker"]]}
        for turn in payload["turns"]
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)
    print(f"model: {MODEL}  turns: {len(inputs)}")
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
    AUDIO.write_bytes(audio)
    print(f"wrote {AUDIO} ({len(audio)} bytes)")


if __name__ == "__main__":
    main()

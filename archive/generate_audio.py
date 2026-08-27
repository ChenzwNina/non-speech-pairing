"""Render tagged transcripts as ElevenLabs v3 multi-speaker audio.

Reads out/transcripts.json (or --in) and writes one mp3 per dialogue via the
Text to Dialogue API, keeping the inline [audio tags] so v3 can perform laughs
and delivery.

Usage:
    python generate_audio.py
    python generate_audio.py --in out/transcripts.json --out-dir out/audio
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

load_dotenv()

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE / "out" / "transcripts.json"
DEFAULT_OUT_DIR = HERE / "out" / "audio"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_A = "r1KmysJdVYZjJCm4mL3b"  # female
VOICE_B = "IKne3meq5aSn9XLyUdCD"  # Charlie

VOICES = {"A": VOICE_A, "B": VOICE_B}


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def collect_bytes(chunks) -> bytes:
    return b"".join(chunks)


def generate_dialogue(client: ElevenLabs, turns: list[dict], voices: dict[str, str]) -> bytes:
    inputs = [
        {"text": turn["text"], "voice_id": voices[turn["speaker"]]}
        for turn in turns
    ]
    return collect_bytes(
        client.text_to_dialogue.convert(
            inputs=inputs,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            settings=ModelSettingsResponseModel(stability=0.4),
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--voice-a", default=os.getenv("ELEVENLABS_VOICE_A", VOICE_A))
    parser.add_argument("--voice-b", default=os.getenv("ELEVENLABS_VOICE_B", VOICE_B))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    results = [row for row in payload.get("results", []) if row.get("turns") and not row.get("error")]
    if args.limit:
        results = results[: args.limit]
    if not results:
        raise SystemExit(f"no usable dialogues in {args.infile}")

    voices = {"A": args.voice_a, "B": args.voice_b}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    print(f"model: {MODEL}  dialogues: {len(results)}")
    manifest = []

    for index, row in enumerate(results, start=1):
        name = f"{row['id']}-{slug(row['function'])}.mp3"
        path = args.out_dir / name
        record = {
            "id": row["id"],
            "function": row["function"],
            "audio": str(path.relative_to(HERE)),
            "laughing_turn": row.get("laughing_turn"),
            "laughing_speaker": row.get("laughing_speaker"),
        }

        if path.exists() and not args.overwrite:
            print(f"[{index}/{len(results)}] skip {name}")
            record["skipped"] = True
            manifest.append(record)
            continue

        print(f"[{index}/{len(results)}] {row['function']}")
        try:
            audio = generate_dialogue(client, row["turns"], voices)
            if not audio:
                raise RuntimeError("empty audio response")
            path.write_bytes(audio)
            record["bytes"] = len(audio)
            print(f"    wrote {path} ({len(audio)} bytes)")
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"    failed: {exc}")
            if index < len(results):
                time.sleep(2)
            manifest.append(record)
            continue

        if index < len(results):
            time.sleep(0.4)
        manifest.append(record)

    index_path = args.out_dir / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = sum(1 for item in manifest if item.get("error"))
    print(f"\nwrote {index_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

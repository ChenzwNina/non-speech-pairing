"""Render costly-misread v3 pairs as ElevenLabs v3 dialogue audio.

Three speakers. C uses gPPH6SLdL8XSX6GNJ40G. Writes mp3s under
out/costly_misreads_v3/audio/.

Usage:
    python generate_costly_misreads_audio.py
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
DEFAULT_IN = HERE / "out" / "costly_misreads_v3.json"
DEFAULT_OUT_DIR = HERE / "out" / "costly_misreads_v3" / "audio"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_A = "r1KmysJdVYZjJCm4mL3b"
VOICE_B = "IKne3meq5aSn9XLyUdCD"
VOICE_C = "C3x1TEM7scV4p2AXJyrp"


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:50]


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
    parser.add_argument("--voice-c", default=os.getenv("ELEVENLABS_VOICE_C", VOICE_C))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, help="max pairs (each pair is two clips)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"no items in {args.infile}")

    args.out_dir = args.out_dir.resolve()
    args.infile = args.infile.resolve()
    voices = {"A": VOICE_A, "B": VOICE_B, "C": args.voice_c}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    jobs = []
    for index, item in enumerate(items, start=1):
        base = f"{index:02d}-{slug(item.get('title') or item.get('pattern') or 'pair')}"
        for version_key, suffix in (("version_1", "v1"), ("version_2", "v2")):
            version = item.get(version_key) or {}
            turns = version.get("turns")
            if not turns:
                continue
            jobs.append(
                {
                    "path": args.out_dir / f"{base}-{suffix}.mp3",
                    "turns": turns,
                    "id": f"{base}-{suffix}",
                    "title": item.get("title"),
                    "pattern": item.get("pattern"),
                    "label": version.get("label"),
                }
            )

    print(f"model: {MODEL}  clips: {len(jobs)}  dir: {args.out_dir}")
    manifest = []

    for i, job in enumerate(jobs, start=1):
        path = job["path"]
        record = {
            "id": job["id"],
            "title": job["title"],
            "pattern": job["pattern"],
            "label": job["label"],
            "audio": str(path.relative_to(HERE)),
        }
        if path.exists() and not args.overwrite:
            print(f"[{i}/{len(jobs)}] skip {path.name}")
            record["skipped"] = True
            manifest.append(record)
            continue

        print(f"[{i}/{len(jobs)}] {path.name}")
        try:
            audio = generate_dialogue(client, job["turns"], voices)
            if not audio:
                raise RuntimeError("empty audio response")
            path.write_bytes(audio)
            record["bytes"] = len(audio)
            print(f"    wrote {path} ({len(audio)} bytes)")
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"    failed: {exc}")
            if i < len(jobs):
                time.sleep(2)
            manifest.append(record)
            continue

        if i < len(jobs):
            time.sleep(0.4)
        manifest.append(record)

    index_path = args.out_dir / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = sum(1 for item in manifest if item.get("error"))
    print(f"\nwrote {index_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

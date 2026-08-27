"""Render pairing-type items as ElevenLabs v3 audio.

Uses Turn 1 (A) and Turn 2 (B) only. Turn 3 is omitted so C's response
is not in the clip.

Usage:
    python pairing_type/generate_audio.py
    python pairing_type/generate_audio.py --in pairing_type/out/pairs.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

load_dotenv()

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT_DIR = HERE / "out" / "audio"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_A = "r1KmysJdVYZjJCm4mL3b"  # female
VOICE_B = "IKne3meq5aSn9XLyUdCD"  # Charlie


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
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, help="max items (each item is two clips)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    items = [item for item in payload.get("results") or [] if "realization_a" in item]
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"no items in {args.infile}")

    args.out_dir = args.out_dir.resolve()
    args.infile = args.infile.resolve()
    voices = {"A": VOICE_A, "B": VOICE_B}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    jobs = []
    for item in items:
        item_id = item["item_id"]
        for key, suffix in (("realization_a", "a"), ("realization_b", "b")):
            version = item.get(key) or {}
            turns = (version.get("transcript") or [])[:2]
            if len(turns) != 2:
                continue
            jobs.append(
                {
                    "path": args.out_dir / f"{item_id}-{suffix}.mp3",
                    "turns": turns,
                    "id": f"{item_id}-{suffix}",
                    "item_id": item_id,
                    "contrast": item.get("contrast"),
                    "vocalization": version.get("vocalization"),
                    "intended_meaning": version.get("intended_meaning"),
                }
            )

    print(f"model: {MODEL}  clips: {len(jobs)}  dir: {args.out_dir}")
    manifest = []

    for i, job in enumerate(jobs, start=1):
        path = job["path"]
        try:
            audio_rel = str(path.relative_to(REPO))
        except ValueError:
            audio_rel = str(path)
        record = {
            "id": job["id"],
            "item_id": job["item_id"],
            "contrast": job["contrast"],
            "vocalization": job["vocalization"],
            "intended_meaning": job["intended_meaning"],
            "turns": job["turns"],
            "audio": audio_rel,
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
            print(f"    wrote {path.name} ({len(audio)} bytes)")
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

"""Render pairing_type_upgraded context turns and response options.

Shared A/C turns are synthesized one clip each (no Speaker B, no voc).
Each pair's two final responses are synthesized separately as answer options.

Usage:
    python pairing_type_upgraded/generate_audio.py
    python pairing_type_upgraded/generate_audio.py --limit 1
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")

DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT_DIR = HERE / "out" / "audio_turns"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_A = "r1KmysJdVYZjJCm4mL3b"
VOICE_C = "C3x1TEM7scV4p2AXJyrp"
VOICES = {"A": VOICE_A, "C": VOICE_C}


def collect_bytes(chunks) -> bytes:
    return b"".join(chunks)


def generate_turn(client: ElevenLabs, text: str, voice_id: str) -> bytes:
    return collect_bytes(
        client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=0.4),
        )
    )


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="max pairs")
    return parser.parse_args()


def jobs_for_pair(item: dict, out_dir: Path) -> list[dict]:
    pair_id = item["pair_id"]
    jobs = []
    for index, turn in enumerate(item.get("shared_context") or [], start=1):
        speaker = turn["speaker"]
        if speaker == "B":
            raise SystemExit(f"{pair_id} shared_context includes Speaker B")
        if speaker not in VOICES:
            raise SystemExit(f"{pair_id} unknown speaker {speaker}")
        jobs.append(
            {
                "path": out_dir / f"{pair_id}-turn{index:02d}.mp3",
                "id": f"{pair_id}-turn{index:02d}",
                "pair_id": pair_id,
                "contrast": item.get("contrast"),
                "role": "context",
                "turn": index,
                "speaker": speaker,
                "text": turn["text"],
                "voice_id": VOICES[speaker],
                "version": None,
                "vocalization": None,
            }
        )
    for version_key, suffix in (("version_1", "v1"), ("version_2", "v2")):
        version = item.get(version_key) or {}
        responder = version.get("responder")
        text = (version.get("response") or "").strip()
        if responder not in VOICES:
            raise SystemExit(f"{pair_id} {version_key} responder must be A or C")
        if not text:
            raise SystemExit(f"{pair_id} {version_key} is missing a response")
        jobs.append(
            {
                "path": out_dir / f"{pair_id}-response-{suffix}.mp3",
                "id": f"{pair_id}-response-{suffix}",
                "pair_id": pair_id,
                "contrast": item.get("contrast"),
                "role": "response",
                "turn": None,
                "speaker": responder,
                "text": text,
                "voice_id": VOICES[responder],
                "version": suffix,
                "vocalization": version.get("vocalization"),
                "intended_interpretation": version.get("intended_interpretation"),
            }
        )
    return jobs


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    items = [item for item in payload.get("results") or [] if item.get("shared_context")]
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"no pairs in {args.infile}")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    jobs = []
    for item in items:
        jobs.extend(jobs_for_pair(item, out_dir))

    print(f"model: {MODEL}  pairs: {len(items)}  clips: {len(jobs)}  dir: {out_dir}", flush=True)
    manifest = []

    for i, job in enumerate(jobs, start=1):
        path = job["path"]
        record = {
            "id": job["id"],
            "pair_id": job["pair_id"],
            "contrast": job["contrast"],
            "role": job["role"],
            "turn": job["turn"],
            "speaker": job["speaker"],
            "text": job["text"],
            "version": job["version"],
            "vocalization": job["vocalization"],
            "audio": rel(path),
        }
        if job.get("intended_interpretation"):
            record["intended_interpretation"] = job["intended_interpretation"]
        if path.exists() and not args.overwrite:
            print(f"[{i}/{len(jobs)}] skip {path.name}", flush=True)
            record["skipped"] = True
            manifest.append(record)
            continue

        print(f"[{i}/{len(jobs)}] {path.name}  {job['speaker']}: {job['text'][:80]}", flush=True)
        try:
            audio = generate_turn(client, job["text"], job["voice_id"])
            if not audio:
                raise RuntimeError("empty audio response")
            path.write_bytes(audio)
            record["bytes"] = len(audio)
            print(f"    wrote {path.name} ({len(audio)} bytes)", flush=True)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"    failed: {exc}", flush=True)
            if i < len(jobs):
                time.sleep(2)
            manifest.append(record)
            continue

        if i < len(jobs):
            time.sleep(0.4)
        manifest.append(record)

    index_path = out_dir / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = sum(1 for item in manifest if item.get("error"))
    print(
        f"\nwrote {index_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

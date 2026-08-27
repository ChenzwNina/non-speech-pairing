"""Render Turn 1, Turn 2, and both tagged Turn 3 versions.

Turns 1 and 2 are shared. Turn 3 is synthesized twice with the audio
tags left in (version A vs version B). A tag-free Turn 3 is also kept
as a lexical reference clip.

Usage:
    python transcript_curated/generate_audio.py
    python transcript_curated/generate_audio.py --limit 1
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT_DIR = HERE / "out" / "audio_turns"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_A = "r1KmysJdVYZjJCm4mL3b"
VOICE_B = "IKne3meq5aSn9XLyUdCD"
VOICES = {"A": VOICE_A, "B": VOICE_B}
TAG_RE = re.compile(r"\[[^\[\]]+\]")


def strip_formula_tokens(text: str) -> str:
    cleaned = re.sub(r"\]\s*\.\.\.", "]...", " ".join((text or "").split()))
    cleaned = " ".join(TAG_RE.sub(" ", cleaned).split())
    cleaned = re.sub(r"(?i)\bha(?:\.\.\.\s*ha){1,}\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bha(?:ha)+\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bhooo+\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bheh(?:e|eh)*\b", " ", cleaned)
    cleaned = re.sub(r"\.\.\.", " ", cleaned)
    return " ".join(cleaned.split())


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


def neutral_turn3(item: dict) -> str:
    stored = (item.get("turn_3_lexical") or "").strip()
    from_a = strip_formula_tokens((item.get("turn_3_a") or {}).get("text") or "")
    from_b = strip_formula_tokens((item.get("turn_3_b") or {}).get("text") or "")
    if stored:
        return stored
    return from_a or from_b


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    items = [item for item in payload.get("results") or [] if item.get("turn_1")]
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"no items in {args.infile}")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    jobs = []
    for item in items:
        item_id = item["item_id"]
        t3 = neutral_turn3(item)
        t3a = (item.get("turn_3_a") or {}).get("text") or ""
        t3b = (item.get("turn_3_b") or {}).get("text") or ""
        if not t3:
            raise SystemExit(f"{item_id} has no neutral Turn 3 line")
        if not t3a or not t3b:
            raise SystemExit(f"{item_id} is missing turn_3_a or turn_3_b")
        base = {
            "item_id": item_id,
            "pair_id": item.get("pair_id"),
            "contrast": item.get("contrast"),
            "domain": item.get("domain"),
        }
        jobs.extend(
            [
                {
                    **base,
                    "path": out_dir / f"{item_id}-turn1.mp3",
                    "id": f"{item_id}-turn1",
                    "turn": 1,
                    "speaker": "A",
                    "text": item["turn_1"]["text"],
                    "voice_id": VOICE_A,
                    "neutral": False,
                    "version": None,
                },
                {
                    **base,
                    "path": out_dir / f"{item_id}-turn2.mp3",
                    "id": f"{item_id}-turn2",
                    "turn": 2,
                    "speaker": "B",
                    "text": item["turn_2"]["text"],
                    "voice_id": VOICE_B,
                    "neutral": False,
                    "version": None,
                },
                {
                    **base,
                    "path": out_dir / f"{item_id}-turn3.mp3",
                    "id": f"{item_id}-turn3",
                    "turn": 3,
                    "speaker": "A",
                    "text": t3,
                    "voice_id": VOICE_A,
                    "neutral": True,
                    "version": "neutral",
                },
                {
                    **base,
                    "path": out_dir / f"{item_id}-turn3-a.mp3",
                    "id": f"{item_id}-turn3-a",
                    "turn": 3,
                    "speaker": "A",
                    "text": t3a,
                    "voice_id": VOICE_A,
                    "neutral": False,
                    "version": "a",
                },
                {
                    **base,
                    "path": out_dir / f"{item_id}-turn3-b.mp3",
                    "id": f"{item_id}-turn3-b",
                    "turn": 3,
                    "speaker": "A",
                    "text": t3b,
                    "voice_id": VOICE_A,
                    "neutral": False,
                    "version": "b",
                },
            ]
        )

    print(f"model: {MODEL}  clips: {len(jobs)}  dir: {out_dir}")
    manifest = []

    for i, job in enumerate(jobs, start=1):
        path = job["path"]
        record = {
            "id": job["id"],
            "item_id": job["item_id"],
            "pair_id": job["pair_id"],
            "contrast": job["contrast"],
            "domain": job["domain"],
            "turn": job["turn"],
            "speaker": job["speaker"],
            "text": job["text"],
            "neutral": job["neutral"],
            "version": job.get("version"),
            "audio": rel(path),
        }
        if path.exists() and not args.overwrite:
            print(f"[{i}/{len(jobs)}] skip {path.name}")
            record["skipped"] = True
            manifest.append(record)
            continue

        print(f"[{i}/{len(jobs)}] {path.name}")
        if job.get("version") in {"a", "b", "neutral"}:
            print(f"    {job['version']}: {job['text']}")
        try:
            audio = generate_turn(client, job["text"], job["voice_id"])
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

    index_path = out_dir / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = sum(1 for item in manifest if item.get("error"))
    print(f"\nwrote {index_path}" + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

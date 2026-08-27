"""Clip Turn 2 vocalizations using ElevenLabs character timestamps.

Generates B's full Turn 2 (formula + words) for both realizations, then
cuts everything before the shared lexical words. Those clips can be
inserted in front of the neutral Turn 2 speech.

Usage:
    python pairing_type/generate_vocalization_audio.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

load_dotenv()

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_OUT_DIR = HERE / "out" / "audio_voc"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_B = "IKne3meq5aSn9XLyUdCD"
MIN_CLIP_SEC = 0.08


def glue_ellipsis(text: str) -> str:
    return re.sub(r"\]\s*\.\.\.", "]...", " ".join((text or "").split()))


def rest_after_prefix(text: str, prefix: str) -> str:
    t = glue_ellipsis(text)
    p = glue_ellipsis(prefix)
    if t.lower().startswith(p.lower()):
        return t[len(p) :].lstrip(" ,")
    return " ".join(re.sub(r"\[[^\[\]]+\]", " ", text).split())


def alignment_text(alignment) -> str:
    return "".join(alignment.characters or [])


def lexical_start_time(alignment, lexical: str) -> float | None:
    if alignment is None or not lexical:
        return None
    chars = alignment_text(alignment)
    starts = list(alignment.character_start_times_seconds or [])
    if not chars or not starts:
        return None
    idx = chars.find(lexical)
    if idx < 0:
        stripped = []
        index_map = []
        i = 0
        while i < len(chars):
            if chars[i] == "[":
                close = chars.find("]", i)
                i = close + 1 if close >= 0 else i + 1
                continue
            stripped.append(chars[i])
            index_map.append(i)
            i += 1
        idx2 = "".join(stripped).find(lexical)
        if idx2 >= 0:
            idx = index_map[idx2]
    if idx < 0 or idx >= len(starts):
        return None
    return float(starts[idx])


def clip_mp3(src: Path, dest: Path, end_sec: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-t",
            f"{end_sec:.3f}",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def generate_turn(client: ElevenLabs, text: str):
    return client.text_to_dialogue.convert_with_timestamps(
        inputs=[{"text": text, "voice_id": VOICE_B}],
        model_id=MODEL,
        output_format=OUTPUT_FORMAT,
        settings=ModelSettingsResponseModel(stability=0.4),
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
    args.out_dir.mkdir(parents=True, exist_ok=True)
    full_dir = args.out_dir / "full_turn2"
    full_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    jobs = []
    for item in items:
        lexical = (item.get("shared_context") or {}).get("turn_2_lexical_content") or ""
        for key, suffix in (("realization_a", "a"), ("realization_b", "b")):
            version = item.get(key) or {}
            turns = version.get("transcript") or []
            if len(turns) < 2:
                continue
            jobs.append(
                {
                    "item_id": item["item_id"],
                    "suffix": suffix,
                    "contrast": item.get("contrast"),
                    "domain": item.get("domain"),
                    "vocalization": version.get("vocalization"),
                    "intended_meaning": version.get("intended_meaning"),
                    "turn2_text": turns[1]["text"],
                    "lexical": lexical or rest_after_prefix(
                        turns[1]["text"], version.get("vocalization") or ""
                    ),
                    "voc_path": args.out_dir / f"{item['item_id']}-{suffix}-voc.mp3",
                    "full_path": full_dir / f"{item['item_id']}-{suffix}-turn2.mp3",
                }
            )

    print(f"model: {MODEL}  clips: {len(jobs)}  dir: {args.out_dir}")
    manifest = []

    for i, job in enumerate(jobs, start=1):
        voc_path = job["voc_path"]
        record = {
            "id": f"{job['item_id']}-{job['suffix']}-voc",
            "item_id": job["item_id"],
            "contrast": job["contrast"],
            "domain": job["domain"],
            "vocalization": job["vocalization"],
            "intended_meaning": job["intended_meaning"],
            "turn2_text": job["turn2_text"],
            "lexical": job["lexical"],
            "audio": str(voc_path.relative_to(REPO)),
            "full_turn2": str(job["full_path"].relative_to(REPO)),
        }
        if voc_path.exists() and not args.overwrite:
            print(f"[{i}/{len(jobs)}] skip {voc_path.name}")
            record["skipped"] = True
            manifest.append(record)
            continue

        print(f"[{i}/{len(jobs)}] {voc_path.name}")
        try:
            response = generate_turn(client, job["turn2_text"])
            audio = base64.b64decode(response.audio_base_64)
            if not audio:
                raise RuntimeError("empty audio response")
            job["full_path"].write_bytes(audio)
            start = lexical_start_time(response.alignment, job["lexical"])
            if start is None:
                start = lexical_start_time(response.normalized_alignment, job["lexical"])
            if start is None or start < MIN_CLIP_SEC:
                print("    timestamps too short; generating formula-only fallback")
                fallback = generate_turn(client, job["vocalization"])
                voc_path.write_bytes(base64.b64decode(fallback.audio_base_64))
                record["method"] = "formula_only"
                record["clip_end_sec"] = None
            else:
                clip_mp3(job["full_path"], voc_path, start)
                record["method"] = "timestamp_clip"
                record["clip_end_sec"] = round(start, 3)
            record["bytes"] = voc_path.stat().st_size
            print(f"    wrote {voc_path.name} ({record['method']}, {record.get('clip_end_sec')}s)")
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

"""Generate Turn 1, Turn 2, and gold Turn 3 audio, then clip the Turn 3 voc.

Turn 1 and Turn 3 use speaker A. Turn 2 uses speaker B.
Turn 3 is synthesized as formula + words; the vocalization is cut out
with character timestamps so it can be sewn back with Turns 1 and 2.

Usage:
    python predicting_content/generate_audio.py
    python predicting_content/generate_audio.py --limit 1
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")

DEFAULT_IN = HERE / "out" / "items.json"
DEFAULT_TURNS = HERE / "out" / "audio_turns"
DEFAULT_VOC = HERE / "out" / "audio_voc"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_A = "r1KmysJdVYZjJCm4mL3b"
VOICE_B = "IKne3meq5aSn9XLyUdCD"
MIN_CLIP_SEC = 0.08


def collect_bytes(chunks) -> bytes:
    return b"".join(chunks)


def generate_plain(client: ElevenLabs, text: str, voice_id: str) -> bytes:
    return collect_bytes(
        client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=0.4),
        )
    )


def generate_timed(client: ElevenLabs, text: str, voice_id: str):
    return client.text_to_dialogue.convert_with_timestamps(
        inputs=[{"text": text, "voice_id": voice_id}],
        model_id=MODEL,
        output_format=OUTPUT_FORMAT,
        settings=ModelSettingsResponseModel(stability=0.4),
    )


def glue_ellipsis(text: str) -> str:
    return re.sub(r"\]\s*\.\.\.", "]...", " ".join((text or "").split()))


def alignment_text(alignment) -> str:
    return "".join(alignment.characters or [])


def lexical_start_time(alignment, lexical: str) -> float | None:
    if alignment is None or not lexical:
        return None
    chars = alignment_text(alignment)
    starts = list(alignment.character_start_times_seconds or [])
    if not chars or not starts:
        return None
    needle = glue_ellipsis(lexical)
    idx = chars.find(needle)
    if idx < 0:
        idx = chars.lower().find(needle.lower())
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
        idx2 = "".join(stripped).find(needle)
        if idx2 < 0:
            idx2 = "".join(stripped).lower().find(needle.lower())
        if idx2 >= 0:
            idx = index_map[idx2]
    if idx < 0 or idx >= len(starts):
        return None
    return float(starts[idx])


def clip_prefix(src: Path, dest: Path, end_sec: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-t", f"{end_sec:.3f}",
            "-acodec", "libmp3lame", "-q:a", "2", str(dest),
        ],
        check=True,
        capture_output=True,
    )


def clip_suffix(src: Path, dest: Path, start_sec: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", f"{start_sec:.3f}", "-i", str(src),
            "-acodec", "libmp3lame", "-q:a", "2", str(dest),
        ],
        check=True,
        capture_output=True,
    )


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--turns-dir", type=Path, default=DEFAULT_TURNS)
    parser.add_argument("--voc-dir", type=Path, default=DEFAULT_VOC)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")

    payload = json.loads(args.infile.read_text(encoding="utf-8"))
    items = [item for item in payload.get("results") or [] if item.get("gold")]
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"no items in {args.infile}")

    turns_dir = args.turns_dir.resolve()
    voc_dir = args.voc_dir.resolve()
    full_dir = voc_dir / "full_turn3"
    turns_dir.mkdir(parents=True, exist_ok=True)
    voc_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=key)

    print(f"model: {MODEL}  items: {len(items)}")
    turn_manifest = []
    voc_manifest = []

    for i, item in enumerate(items, start=1):
        item_id = item["item_id"]
        t1, t2, t3 = item["transcript"]
        lexical = item["gold"]["lexical"]
        formula = item["formula"]
        turn1_path = turns_dir / f"{item_id}-turn1.mp3"
        turn2_path = turns_dir / f"{item_id}-turn2.mp3"
        speech_path = turns_dir / f"{item_id}-turn3-speech.mp3"
        full_path = full_dir / f"{item_id}-turn3.mp3"
        voc_path = voc_dir / f"{item_id}-voc.mp3"

        print(f"[{i}/{len(items)}] {item_id}")
        try:
            if args.overwrite or not turn1_path.exists():
                turn1_path.write_bytes(generate_plain(client, t1["text"], VOICE_A))
                print(f"    turn1 {turn1_path.name} ({turn1_path.stat().st_size} bytes)")
                time.sleep(0.35)
            else:
                print(f"    skip {turn1_path.name}")

            if args.overwrite or not turn2_path.exists():
                turn2_path.write_bytes(generate_plain(client, t2["text"], VOICE_B))
                print(f"    turn2 {turn2_path.name} ({turn2_path.stat().st_size} bytes)")
                time.sleep(0.35)
            else:
                print(f"    skip {turn2_path.name}")

            turn_manifest.append(
                {
                    "item_id": item_id,
                    "domain": item.get("domain"),
                    "turn1": rel(turn1_path),
                    "turn2": rel(turn2_path),
                    "turn3_speech": rel(speech_path),
                    "turn1_text": t1["text"],
                    "turn2_text": t2["text"],
                    "turn3_lexical": lexical,
                    "voice_a": VOICE_A,
                    "voice_b": VOICE_B,
                }
            )

            voc_record = {
                "item_id": item_id,
                "domain": item.get("domain"),
                "formula": formula,
                "gold_text": item["gold"]["text"],
                "lexical": lexical,
                "audio": rel(voc_path),
                "full_turn3": rel(full_path),
                "turn3_speech": rel(speech_path),
            }

            if voc_path.exists() and speech_path.exists() and not args.overwrite:
                print(f"    skip {voc_path.name}")
                voc_record["skipped"] = True
                voc_manifest.append(voc_record)
                continue

            response = generate_timed(client, item["gold"]["text"], VOICE_A)
            audio = base64.b64decode(response.audio_base_64)
            if not audio:
                raise RuntimeError("empty Turn 3 audio")
            full_path.write_bytes(audio)
            start = lexical_start_time(response.alignment, lexical)
            if start is None:
                start = lexical_start_time(response.normalized_alignment, lexical)
            if start is None or start < MIN_CLIP_SEC:
                print("    timestamps too short; formula-only voc + plain speech")
                fallback = generate_timed(client, formula, VOICE_A)
                voc_path.write_bytes(base64.b64decode(fallback.audio_base_64))
                speech_path.write_bytes(generate_plain(client, lexical, VOICE_A))
                voc_record["method"] = "formula_only"
                voc_record["clip_end_sec"] = None
            else:
                clip_prefix(full_path, voc_path, start)
                clip_suffix(full_path, speech_path, start)
                voc_record["method"] = "timestamp_clip"
                voc_record["clip_end_sec"] = round(start, 3)
            voc_record["bytes"] = voc_path.stat().st_size
            print(f"    voc {voc_path.name} ({voc_record['method']}, {voc_record.get('clip_end_sec')}s)")
            voc_manifest.append(voc_record)
            time.sleep(0.4)
        except Exception as exc:
            print(f"    failed: {exc}")
            voc_manifest.append(
                {
                    "item_id": item_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            time.sleep(2)

    (turns_dir / "index.json").write_text(
        json.dumps(turn_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (voc_dir / "index.json").write_text(
        json.dumps(voc_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    failures = sum(1 for row in voc_manifest if row.get("error"))
    print(f"\nwrote {turns_dir / 'index.json'} and {voc_dir / 'index.json'}"
          + (f" ({failures} failed)" if failures else ""))


if __name__ == "__main__":
    main()

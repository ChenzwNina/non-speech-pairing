"""Synthesize Turn 1 once per pair, splice each vocalization into its own clip.

Two separate audio files per pair — never mixed into one clip:

    out/audio_prompt/{pair_id}_v1.mp3  =  turn1 (TTS)  +gap+  vocalization_1 (real clip)
    out/audio_prompt/{pair_id}_v2.mp3  =  turn1 (TTS)  +gap+  vocalization_2 (real clip)

Both clips share the same Turn 1 recording (synthesized once, reused). The eval plays
them as two separate dialogues, not as one continuous clip — see eval_realtime.py, which
also decides at eval time (randomized per pair) which one is presented as "Dialogue 1".

Turn 1 is synthesized with one of two ElevenLabs voices, assigned per pair so the 15
pairs split as evenly as possible between the two.

Usage:
    python predicting_response_upgraded/generate_audio.py
    python predicting_response_upgraded/generate_audio.py --in out/pairs_v2.json
    python predicting_response_upgraded/generate_audio.py --limit 2
    python predicting_response_upgraded/generate_audio.py --sew-only
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DEFAULT_IN = HERE / "out" / "pairs_v2.json"
DEFAULT_TURN_DIR = HERE / "out" / "audio_turns"
DEFAULT_PROMPT_DIR = HERE / "out" / "audio_prompt"
DEFAULT_MANIFEST = HERE / "out" / "audio_manifest.json"
VOC_ROOT = REPO / "audio_non-speech"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_POOL = {
    "male": "s3TPKV1kjDlVtZbl4Ksh",
    "female": "aKw9UnnjRq5scbeeGI7Z",
}

VOC_DIRS = {
    "gasp": "gasp", "grunt": "grunt", "laughter": "laughter",
    "sigh": "sigh", "sob": "sobbing", "yawn": "yawn",
}

GAP_AFTER_TURN1 = 0.40
MIN_CLIP_SECONDS = 0.3
MAX_CLIP_SECONDS = 10.0

_duration_cache: dict[str, float] = {}
_excluded: dict[str, float] = {}


def all_clips(voc_id: str) -> list[Path]:
    folder = VOC_ROOT / VOC_DIRS[voc_id]
    if not folder.is_dir():
        raise SystemExit(f"missing clip folder: {folder}")
    clips = sorted(
        p for p in folder.iterdir() if p.suffix.lower() == ".mp3" and not p.name.startswith(".")
    )
    if not clips:
        raise SystemExit(f"no mp3 clips in {folder}")
    return clips


def clips_for(voc_id: str, lo: float = MIN_CLIP_SECONDS, hi: float = MAX_CLIP_SECONDS) -> list[Path]:
    keep: list[Path] = []
    for clip in all_clips(voc_id):
        seconds = duration_of(clip)
        if lo <= seconds <= hi:
            keep.append(clip)
        else:
            _excluded[str(clip.relative_to(REPO))] = round(seconds, 3)
    if not keep:
        raise SystemExit(f"every clip for {voc_id} is outside {lo}-{hi}s")
    return keep


def pick_clip(voc_id: str, used: Counter, rng: random.Random) -> Path:
    clips = clips_for(voc_id)
    fewest = min(used[str(clip)] for clip in clips)
    candidates = [clip for clip in clips if used[str(clip)] == fewest]
    choice = rng.choice(candidates)
    used[str(choice)] += 1
    return choice


def duration_of(path: Path) -> float:
    key = str(path)
    if key in _duration_cache:
        return _duration_cache[key]
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    seconds = float(result.stdout.strip())
    _duration_cache[key] = seconds
    return seconds


def synthesize(client: ElevenLabs, text: str, voice_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(
        client.text_to_speech.convert(
            voice_id=voice_id, text=text, model_id=MODEL, output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=0.4),
        )
    )
    dest.write_bytes(audio)


def sew(pieces: list[tuple[Path, float]], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    labels: list[str] = []
    for index, (path, gap) in enumerate(pieces):
        if gap > 0:
            parts.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{gap},aformat=sample_fmts=fltp[g{index}]")
            labels.append(f"[g{index}]")
        parts.append(f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{index}]")
        labels.append(f"[a{index}]")
    # trailing aresample avoids a known libmp3lame "inadequate AVFrame plane padding" bug
    filt = (
        ";".join(parts) + ";" + "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1[cat];[cat]aresample=44100[out]"
    )
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path, _ in pieces:
        command += ["-i", str(path)]
    command += ["-filter_complex", filt, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(dest)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] if result.stderr else "ffmpeg failed")


def assign_voices(pair_ids: list[str], rng: random.Random) -> dict[str, str]:
    labels = list(VOICE_POOL)
    n = len(pair_ids)
    half = n // 2
    counts = {labels[0]: half, labels[1]: n - half}
    if n % 2 == 1:
        bonus = rng.choice(labels)
        other = labels[1] if bonus == labels[0] else labels[0]
        counts = {bonus: half + 1, other: half}
    pool = [label for label in labels for _ in range(counts[label])]
    rng.shuffle(pool)
    order = list(pair_ids)
    rng.shuffle(order)
    return dict(zip(order, pool))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--turn-dir", type=Path, default=DEFAULT_TURN_DIR)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--sew-only", action="store_true")
    parser.add_argument("--reset-usage", action="store_true")
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    args.turn_dir = args.turn_dir.resolve()
    args.prompt_dir = args.prompt_dir.resolve()
    args.manifest = args.manifest.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    records = [r for r in data["results"] if "shared_turn1" in r]
    if args.limit:
        records = records[: args.limit]
    if not records:
        raise SystemExit(f"no usable records in {args.infile}")

    used: Counter = Counter()
    if args.manifest.exists() and not args.reset_usage:
        previous = json.loads(args.manifest.read_text(encoding="utf-8"))
        used.update(previous.get("clip_usage", {}))
        print(f"carrying clip counts from {args.manifest}", flush=True)

    client: ElevenLabs | None = None
    if not args.sew_only:
        key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not key:
            raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
        client = ElevenLabs(api_key=key)

    rng = random.Random(args.seed)
    voice_by_pair = assign_voices([r["pair_id"] for r in records], rng)
    print(
        f"{len(records)} pair(s) -> 2 clips each  ·  voices: "
        + ", ".join(f"{lbl}={sum(1 for v in voice_by_pair.values() if v == lbl)}" for lbl in VOICE_POOL),
        flush=True,
    )

    entries: list[dict] = []
    for index, record in enumerate(records, start=1):
        pair_id = record["pair_id"]
        turn_dir = args.turn_dir / pair_id
        voice_label = voice_by_pair[pair_id]
        voice_id = VOICE_POOL[voice_label]
        print(f"[{index}/{len(records)}] {pair_id}  voice {voice_label}", flush=True)

        turn1_path = turn_dir / "turn1.mp3"
        if turn1_path.exists() and not args.overwrite:
            pass
        elif args.sew_only:
            raise SystemExit(f"--sew-only but {turn1_path} is missing")
        else:
            assert client is not None
            synthesize(client, record["shared_turn1"], voice_id, turn1_path)
            time.sleep(0.3)

        for version_key, label in (("version_1", "v1"), ("version_2", "v2")):
            version = record[version_key]
            voc_id = version["vocalization"].strip("[]")
            clip = pick_clip(voc_id, used, rng)
            prompt_path = args.prompt_dir / f"{pair_id}_{label}.mp3"
            sew([(turn1_path, 0.0), (clip, GAP_AFTER_TURN1)], prompt_path)

            entries.append({
                "pair_id": pair_id,
                "version": label,
                "contrast": record.get("contrast"),
                "turn1_voice_label": voice_label,
                "shared_turn1": record["shared_turn1"],
                "vocalization": version["vocalization"],
                "interpretation": version["interpretation"],
                "response": version["response"],
                "clip": str(clip.relative_to(REPO)),
                "clip_seconds": round(duration_of(clip), 3),
                "prompt": str(prompt_path.relative_to(REPO)),
                "prompt_seconds": round(duration_of(prompt_path), 3),
            })
            print(f"    {label} {voc_id:9} {clip.name:16} -> {round(duration_of(prompt_path), 2)}s", flush=True)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    coverage = {}
    for voc_id in VOC_DIRS:
        clips = clips_for(voc_id)
        coverage[voc_id] = {
            "clips_in_folder": len(all_clips(voc_id)),
            "clips_eligible": len(clips),
            "clips_used": sum(1 for clip in clips if used[str(clip)] > 0),
        }
    args.manifest.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": str(args.infile.relative_to(REPO)),
            "tts_model": MODEL,
            "voice_pool": VOICE_POOL,
            "seed": args.seed,
            "gap_after_turn1": GAP_AFTER_TURN1,
            "clip_seconds_allowed": [MIN_CLIP_SECONDS, MAX_CLIP_SECONDS],
            "excluded_clips": dict(sorted(_excluded.items())),
            "coverage": coverage,
            "clip_usage": {p: c for p, c in sorted(used.items())},
            "clips": entries,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {len(entries)} clips to {args.prompt_dir}")
    print(f"manifest: {args.manifest}")
    for voc_id, info in coverage.items():
        print(f"  {voc_id:9} {info['clips_used']}/{info['clips_eligible']} used")
    if _excluded:
        print("\nexcluded as too long or too short:")
        for path, seconds in sorted(_excluded.items()):
            print(f"  {path}  {seconds}s")


if __name__ == "__main__":
    main()

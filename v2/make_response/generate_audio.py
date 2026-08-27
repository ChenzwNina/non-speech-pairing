"""Synthesize A's proposal once per scenario, splice each vocalization onto that same take.

    out/audio_prompt/{item_id}_laughter.mp3 = proposal (TTS) +gap+ laughter (real clip)
    out/audio_prompt/{item_id}_sigh.mp3     = the SAME proposal take +gap+ sigh
    out/audio_prompt/{item_id}_gasp.mp3     = the SAME proposal take +gap+ gasp

The proposal is synthesized exactly once per scenario and reused, so the three clips are
byte-identical up to the vocalization. That is the whole point: any difference in how a
model responds has to come from B's reaction and cannot come from a different TTS take of
A's line.

B never speaks words, so B needs no voice — B's turn is a real non-speech recording drawn
from audio_non-speech/.

Usage:
    python make_response/generate_audio.py
    python make_response/generate_audio.py --limit 1
    python make_response/generate_audio.py --sew-only
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

DEFAULT_IN = HERE / "out" / "scenarios.json"
DEFAULT_PROPOSAL_DIR = HERE / "out" / "audio_proposal"
DEFAULT_PROMPT_DIR = HERE / "out" / "audio_prompt"
DEFAULT_MANIFEST = HERE / "out" / "audio_manifest.json"
VOC_ROOT = REPO / "audio_non-speech"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_POOL = {
    "male": "s3TPKV1kjDlVtZbl4Ksh",
    "female": "aKw9UnnjRq5scbeeGI7Z",
}

VOC_ORDER = ["laughter", "sigh", "gasp"]
VOC_DIRS = {"laughter": "laughter", "sigh": "sigh", "gasp": "gasp"}

GAP_AFTER_PROPOSAL = 0.40
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


def clips_for(voc_id: str) -> list[Path]:
    keep: list[Path] = []
    for clip in all_clips(voc_id):
        seconds = duration_of(clip)
        if MIN_CLIP_SECONDS <= seconds <= MAX_CLIP_SECONDS:
            keep.append(clip)
        else:
            _excluded[str(clip.relative_to(REPO))] = round(seconds, 3)
    if not keep:
        raise SystemExit(f"every clip for {voc_id} is outside the allowed length")
    return keep


def pick_clip(voc_id: str, used: Counter, rng: random.Random) -> Path:
    clips = clips_for(voc_id)
    fewest = min(used[str(clip)] for clip in clips)
    candidates = [clip for clip in clips if used[str(clip)] == fewest]
    choice = rng.choice(candidates)
    used[str(choice)] += 1
    return choice


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
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=0:{gap},aformat=sample_fmts=fltp[g{index}]"
            )
            labels.append(f"[g{index}]")
        parts.append(
            f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
            f"channel_layouts=stereo[a{index}]"
        )
        labels.append(f"[a{index}]")
    # trailing aresample avoids a known libmp3lame "inadequate AVFrame plane padding" bug
    filt = (
        ";".join(parts) + ";" + "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1[cat];[cat]aresample=44100[out]"
    )
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path, _ in pieces:
        command += ["-i", str(path)]
    command += [
        "-filter_complex", filt, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(dest)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] if result.stderr else "ffmpeg failed")


def assign_voices(item_ids: list[str], rng: random.Random) -> dict[str, str]:
    labels = list(VOICE_POOL)
    n = len(item_ids)
    half = n // 2
    counts = {labels[0]: half, labels[1]: n - half}
    if n % 2 == 1:
        bonus = rng.choice(labels)
        other = labels[1] if bonus == labels[0] else labels[0]
        counts = {bonus: half + 1, other: half}
    pool = [label for label in labels for _ in range(counts[label])]
    rng.shuffle(pool)
    order = list(item_ids)
    rng.shuffle(order)
    return dict(zip(order, pool))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSAL_DIR)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--sew-only", action="store_true")
    args = parser.parse_args()
    for attr in ("infile", "proposal_dir", "prompt_dir", "manifest"):
        setattr(args, attr, getattr(args, attr).resolve())
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    records = [r for r in data["results"] if "proposal" in r]
    if args.limit:
        records = records[: args.limit]
    if not records:
        raise SystemExit(f"no usable scenarios in {args.infile}")

    used: Counter = Counter()
    client: ElevenLabs | None = None
    if not args.sew_only:
        key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not key:
            raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
        client = ElevenLabs(api_key=key)

    rng = random.Random(args.seed)
    voice_by_item = assign_voices([r["item_id"] for r in records], rng)
    print(
        f"{len(records)} scenario(s) -> {len(records) * len(VOC_ORDER)} clips  ·  voices: "
        + ", ".join(
            f"{lbl}={sum(1 for v in voice_by_item.values() if v == lbl)}" for lbl in VOICE_POOL
        ),
        flush=True,
    )

    entries: list[dict] = []
    for index, record in enumerate(records, start=1):
        item_id = record["item_id"]
        voice_label = voice_by_item[item_id]
        voice_id = VOICE_POOL[voice_label]
        print(f"[{index}/{len(records)}] {item_id}  voice {voice_label}", flush=True)

        # one take of A's proposal, reused for all three conditions
        proposal_path = args.proposal_dir / item_id / "proposal.mp3"
        if proposal_path.exists() and not args.overwrite:
            pass
        elif args.sew_only:
            raise SystemExit(f"--sew-only but {proposal_path} is missing")
        else:
            assert client is not None
            synthesize(client, record["proposal"], voice_id, proposal_path)
            time.sleep(0.3)

        for voc in VOC_ORDER:
            clip = pick_clip(voc, used, rng)
            prompt_path = args.prompt_dir / f"{item_id}_{voc}.mp3"
            sew([(proposal_path, 0.0), (clip, GAP_AFTER_PROPOSAL)], prompt_path)
            entries.append({
                "item_id": item_id,
                "vocalization": voc,
                "domain": record.get("domain"),
                "relationship": record.get("relationship"),
                "shared_context": record["shared_context"],
                "proposal": record["proposal"],
                "gold_inferred_state": record[voc]["inferred_state"],
                "gold_response_function": record[voc]["response_function"],
                "gold_response": record[voc]["response"],
                "proposal_voice_label": voice_label,
                "clip": str(clip.relative_to(REPO)),
                "clip_seconds": round(duration_of(clip), 3),
                "proposal_audio": str(proposal_path.relative_to(REPO)),
                "prompt": str(prompt_path.relative_to(REPO)),
                "prompt_seconds": round(duration_of(prompt_path), 3),
            })
            print(
                f"    {voc:9} {clip.name:16} -> {round(duration_of(prompt_path), 2)}s",
                flush=True,
            )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": str(args.infile.relative_to(REPO)),
            "tts_model": MODEL,
            "voice_pool": VOICE_POOL,
            "seed": args.seed,
            "gap_after_proposal": GAP_AFTER_PROPOSAL,
            "note": (
                "A's proposal is synthesized once per scenario and reused across its three "
                "conditions, so the clips differ only in B's vocalization"
            ),
            "excluded_clips": dict(sorted(_excluded.items())),
            "clip_usage": {p: c for p, c in sorted(used.items())},
            "clips": entries,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {len(entries)} clips to {args.prompt_dir}")
    print(f"manifest: {args.manifest}")


if __name__ == "__main__":
    main()

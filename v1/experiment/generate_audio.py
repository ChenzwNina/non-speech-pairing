"""Synthesize the spoken turns, splice in a real vocalization clip, sew each version.

Two sewn variants per version:

    out/audio_prompt/  turns 1..N + the vocalization clip        <- ends after turn N+1
    out/audio_full/    the same, plus turn N+2 (the reply)

The prompt variant is the eval input: it stops at B's vocalization, so the reply the model
is asked to choose is not audible. The full variant is for reading the dataset back.
Both are cut from the same turn files and the same clip choice, so they always agree.

Turns 1..N are shared by both versions of a pair, so they are synthesized once. Clip
choices are recorded in out/audio_manifest.json, and clips are drawn least-used-first so
the dataset spreads across each folder instead of leaning on a few recordings.

One of three ElevenLabs voices is picked at random per pair (same voice for both versions
of that pair, since turns 1..N are shared text); the pool spreads voice usage across a
generated set the same way clip choice spreads across the recordings.

Usage:
    python predicting_response/generate_audio.py
    python predicting_response/generate_audio.py --in out/pairs_a.json out/pairs_b.json
    python predicting_response/generate_audio.py --no-full
    python predicting_response/generate_audio.py --limit 2
    python predicting_response/generate_audio.py --sew-only
    python predicting_response/generate_audio.py --overwrite
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

DEFAULT_IN = HERE / "out" / "pairs.json"
DEFAULT_TURN_DIR = HERE / "out" / "audio_turns"
DEFAULT_PROMPT_DIR = HERE / "out" / "audio_prompt"
DEFAULT_FULL_DIR = HERE / "out" / "audio_full"
DEFAULT_MANIFEST = HERE / "out" / "audio_manifest.json"
VOC_ROOT = REPO / "audio_non-speech"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_A = "r1KmysJdVYZjJCm4mL3b"  # female, same voice used in pairing_type

# the three ElevenLabs voice ids used elsewhere in this repo (pairing_type, printer_jam,
# generate_costly_misreads_audio); one is picked per pair so turns 1..N and the reply
# stay in a single consistent voice within a conversation, varied across conversations
VOICE_POOL = [
    "r1KmysJdVYZjJCm4mL3b",  # female
    "IKne3meq5aSn9XLyUdCD",  # Charlie
    "C3x1TEM7scV4p2AXJyrp",
]

# folder names in audio_non-speech/ do not all match the vocalization ids
VOC_DIRS = {
    "gasp": "gasp",
    "grunt": "grunt",
    "laughter": "laughter",
    "sigh": "sigh",
    "sob": "sobbing",
    "yawn": "yawn",
}

GAP_BETWEEN_TURNS = 0.40  # beat between A's consecutive utterances
GAP_BEFORE_VOC = 0.35  # beat before B reacts
GAP_AFTER_VOC = 0.35  # beat before the reply


MIN_CLIP_SECONDS = 0.3
MAX_CLIP_SECONDS = 10.0

_duration_cache: dict[str, float] = {}
_excluded: dict[str, float] = {}


def all_clips(voc_id: str) -> list[Path]:
    folder = VOC_ROOT / VOC_DIRS[voc_id]
    if not folder.is_dir():
        raise SystemExit(f"missing clip folder: {folder}")
    clips = sorted(
        path
        for path in folder.iterdir()
        if path.suffix.lower() == ".mp3" and not path.name.startswith(".")
    )
    if not clips:
        raise SystemExit(f"no mp3 clips in {folder}")
    return clips


def clips_for(voc_id: str, lo: float = MIN_CLIP_SECONDS, hi: float = MAX_CLIP_SECONDS) -> list[Path]:
    """Clips of a plausible length for a single vocalization.

    The folders contain a few long recordings — a 69s gasp, a 39s sob — that are
    compilations rather than one reaction. Splicing those in would dwarf the dialogue,
    so they are excluded and reported.
    """
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
    """Random choice among the least-used clips for this vocalization."""
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
            voice_id=voice_id,
            text=text,
            model_id=MODEL,
            output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=0.4),
        )
    )
    dest.write_bytes(audio)


def duration_of(path: Path) -> float:
    key = str(path)
    if key in _duration_cache:
        return _duration_cache[key]
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    seconds = float(result.stdout.strip())
    _duration_cache[key] = seconds
    return seconds


def sew(pieces: list[tuple[Path, float]], dest: Path) -> None:
    """Concat each piece, inserting the given gap of silence before it."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    labels: list[str] = []
    for index, (path, gap) in enumerate(pieces):
        if gap > 0:
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=0:{gap},"
                f"aformat=sample_fmts=fltp[g{index}]"
            )
            labels.append(f"[g{index}]")
        parts.append(
            f"[{index}:a]aformat=sample_fmts=fltp:sample_rates=44100:"
            f"channel_layouts=stereo[a{index}]"
        )
        labels.append(f"[a{index}]")
    filt = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"

    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path, _ in pieces:
        command += ["-i", str(path)]
    command += ["-filter_complex", filt, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(dest)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:] if result.stderr else "ffmpeg failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in", dest="infiles", type=Path, nargs="+", default=[DEFAULT_IN],
        help="one or more pairs.json files; pair ids across them must not collide",
    )
    parser.add_argument("--turn-dir", type=Path, default=DEFAULT_TURN_DIR)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPT_DIR)
    parser.add_argument("--full-dir", type=Path, default=DEFAULT_FULL_DIR)
    parser.add_argument(
        "--no-full",
        action="store_true",
        help="write only the prompt variant that ends at the vocalization",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int, help="first N pairs only")
    parser.add_argument("--seed", type=int, default=0, help="clip-choice seed")
    parser.add_argument(
        "--overwrite", action="store_true", help="re-synthesize turns that already exist"
    )
    parser.add_argument(
        "--sew-only",
        action="store_true",
        help="skip TTS entirely and re-sew from existing turn files",
    )
    parser.add_argument(
        "--reset-usage",
        action="store_true",
        help="ignore clip counts from a previous manifest",
    )
    args = parser.parse_args()
    # relative_to(REPO) below requires absolute paths regardless of cwd
    args.infiles = [p.resolve() for p in args.infiles]
    args.turn_dir = args.turn_dir.resolve()
    args.prompt_dir = args.prompt_dir.resolve()
    args.full_dir = args.full_dir.resolve()
    args.manifest = args.manifest.resolve()
    return args


def main() -> None:
    args = parse_args()
    records: list[dict] = []
    seen_ids: set[str] = set()
    for infile in args.infiles:
        data = json.loads(infile.read_text(encoding="utf-8"))
        for record in data["results"]:
            if "shared_context" not in record:
                continue
            if record["pair_id"] in seen_ids:
                raise SystemExit(f"duplicate pair_id across --in files: {record['pair_id']}")
            seen_ids.add(record["pair_id"])
            records.append(record)
    if args.limit:
        records = records[: args.limit]
    if not records:
        raise SystemExit(f"no usable records in {args.infiles}")

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
    entries: list[dict] = []
    print(f"{len(records)} pair(s) → {len(records) * 2} clips", flush=True)

    for index, record in enumerate(records, start=1):
        pair_id = record["pair_id"]
        context = record["shared_context"]
        turn_dir = args.turn_dir / pair_id
        voice_id = rng.choice(VOICE_POOL)
        print(f"[{index}/{len(records)}] {pair_id}  voice {voice_id}", flush=True)

        # turns 1..N are shared by both versions
        shared_paths: list[Path] = []
        for position, turn in enumerate(context, start=1):
            dest = turn_dir / f"t{position}_{turn['speaker']}.mp3"
            if dest.exists() and not args.overwrite:
                pass
            elif args.sew_only:
                raise SystemExit(f"--sew-only but {dest} is missing")
            else:
                assert client is not None
                synthesize(client, turn["text"], voice_id, dest)
                time.sleep(0.3)
            shared_paths.append(dest)

        for version_key, label in (("version_1", "v1"), ("version_2", "v2")):
            version = record[version_key]
            voc_id = version["vocalization"].strip("[]")

            reply_path: Path | None = None
            if not args.no_full:
                reply_path = turn_dir / f"t{len(context) + 2}_{label}_{version['responder']}.mp3"
                if reply_path.exists() and not args.overwrite:
                    pass
                elif args.sew_only:
                    raise SystemExit(f"--sew-only but {reply_path} is missing")
                else:
                    assert client is not None
                    synthesize(client, version["response"], voice_id, reply_path)
                    time.sleep(0.3)

            clip = pick_clip(voc_id, used, rng)

            # turns 1..N then the vocalization; this is where the eval clip stops
            prompt_pieces: list[tuple[Path, float]] = []
            for position, path in enumerate(shared_paths):
                prompt_pieces.append((path, 0.0 if position == 0 else GAP_BETWEEN_TURNS))
            prompt_pieces.append((clip, GAP_BEFORE_VOC))

            prompt_path = args.prompt_dir / f"{pair_id}_{label}.mp3"
            sew(prompt_pieces, prompt_path)

            entry = {
                "pair_id": pair_id,
                "version": label,
                "contrast": record.get("contrast"),
                "theme": record.get("theme"),
                "voice_id": voice_id,
                "vocalization": version["vocalization"],
                "intended_interpretation": version["intended_interpretation"],
                "responder": version["responder"],
                "clip": str(clip.relative_to(REPO)),
                "clip_seconds": round(duration_of(clip), 3),
                "prompt": str(prompt_path.relative_to(REPO)),
                "prompt_seconds": round(duration_of(prompt_path), 3),
                "context_turns": [str(path.relative_to(REPO)) for path in shared_paths],
                "reply_text": version["response"],
            }

            if reply_path is not None:
                entry["reply_turn"] = str(reply_path.relative_to(REPO))
                full_path = args.full_dir / f"{pair_id}_{label}.mp3"
                sew(prompt_pieces + [(reply_path, GAP_AFTER_VOC)], full_path)
                entry["full"] = str(full_path.relative_to(REPO))
                entry["full_seconds"] = round(duration_of(full_path), 3)

            entries.append(entry)
            tail = (
                f"  full {entry['full_seconds']}s" if "full_seconds" in entry else ""
            )
            print(
                f"    {label} {version['vocalization']:11} {clip.name:16} "
                f"→ prompt {entry['prompt_seconds']}s{tail}",
                flush=True,
            )

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
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": [str(p.relative_to(REPO)) for p in args.infiles],
                "tts_model": MODEL,
                "voice_pool": VOICE_POOL,
                "seed": args.seed,
                "variants": {
                    "prompt": "turns 1..N + vocalization, ends at turn N+1",
                    "full": None if args.no_full else "prompt + turn N+2 reply",
                },
                "gaps": {
                    "between_turns": GAP_BETWEEN_TURNS,
                    "before_voc": GAP_BEFORE_VOC,
                    "after_voc": GAP_AFTER_VOC,
                },
                "clip_seconds_allowed": [MIN_CLIP_SECONDS, MAX_CLIP_SECONDS],
                "excluded_clips": dict(sorted(_excluded.items())),
                "coverage": coverage,
                "clip_usage": {path: count for path, count in sorted(used.items())},
                "clips": entries,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {len(entries)} prompt clips to {args.prompt_dir}")
    if not args.no_full:
        print(f"       {len(entries)} full clips to {args.full_dir}")
    print(f"manifest: {args.manifest}")
    for voc_id, info in coverage.items():
        print(
            f"  {voc_id:9} {info['clips_used']}/{info['clips_eligible']} used"
            + (
                f"  ({info['clips_in_folder'] - info['clips_eligible']} excluded by length)"
                if info["clips_in_folder"] != info["clips_eligible"]
                else ""
            )
        )
    if _excluded:
        print("\nexcluded as too long or too short for one vocalization:")
        for path, seconds in sorted(_excluded.items()):
            print(f"  {path}  {seconds}s")


if __name__ == "__main__":
    main()

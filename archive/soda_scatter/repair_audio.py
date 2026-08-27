"""Rebuild vocalization turns with real recordings instead of asking TTS for the sound.

eleven_v3 will not reliably produce these sounds. Verified against a 10-vocalization item,
only 3 labels survived: laughter and sigh sometimes land, sob and yawn essentially never, and
a scripted sob or yawn often comes out as a generic breathy exhale that a listener hears as a
sigh. A label the audio does not support is worse than no label.

So the turn is rebuilt from three pieces instead of one take:

    speech before the tag   (TTS)
    the vocalization        (a real human recording from audio_non-speech/)
    speech after the tag    (TTS)

The cost is that the sound comes from a different person than the speaking voice. For a
sketch that would be fatal; for a benchmark asking whether a model can identify and interpret
a vocalization, an unmistakable yawn in a different voice beats an inaudible one in the right
voice. The earlier folders in this repo took the same trade.

The clip is loudness-matched to the surrounding speech, because an unnormalized recording
either vanishes under the line or blares over it, and both make the item harder to hear than
it should be.

Usage:
    python soda_scatter/repair_audio.py --turns 4 6 9 11 12
    python soda_scatter/repair_audio.py --all-vocalization-turns
    python soda_scatter/repair_audio.py --types sob yawn
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from make_audio import build, duration_of, timestamp  # noqa: E402

DEFAULT_ITEMS = HERE / "out" / "items.json"
OUT_DIR = HERE / "out"

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
STABILITY = 0.4

VOICE_FEMALE = "aKw9UnnjRq5scbeeGI7Z"
VOICE_MALE = "s3TPKV1kjDlVtZbl4Ksh"

VOC_ROOT = REPO / "audio_non-speech"
VOC_DIRS = {"laughter": "laughter", "sigh": "sigh", "sob": "sobbing", "yawn": "yawn"}

CLIP_GAP = 0.12          # breath either side of the spliced sound
MIN_CLIP_SECONDS = 0.4
MAX_CLIP_SECONDS = 3.0   # a long compilation clip would dominate the turn

TAG_RE = re.compile(r"\[([^\[\]]+)\]")


def all_clips(voc: str) -> list[Path]:
    folder = VOC_ROOT / VOC_DIRS[voc]
    clips = sorted(p for p in folder.iterdir()
                   if p.suffix.lower() == ".mp3" and not p.name.startswith("."))
    if not clips:
        raise SystemExit(f"no clips in {folder}")
    return clips


def eligible_clips(voc: str) -> list[Path]:
    keep = [c for c in all_clips(voc) if MIN_CLIP_SECONDS <= duration_of(c) <= MAX_CLIP_SECONDS]
    if not keep:
        raise SystemExit(f"every {voc} clip is outside {MIN_CLIP_SECONDS}-{MAX_CLIP_SECONDS}s")
    return keep


def pick_clip(voc: str, used: Counter, rng: random.Random) -> Path:
    clips = eligible_clips(voc)
    fewest = min(used[str(c)] for c in clips)
    choice = rng.choice([c for c in clips if used[str(c)] == fewest])
    used[str(choice)] += 1
    return choice


def mean_volume(path: Path) -> float | None:
    """Mean dBFS via ffmpeg volumedetect, for loudness matching."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", result.stderr or "")
    return float(match.group(1)) if match else None


def gain_to_match(clip: Path, reference: Path, dest: Path) -> Path:
    """Copy the clip with a gain applied so its mean level matches the speech."""
    clip_level, speech_level = mean_volume(clip), mean_volume(reference)
    if clip_level is None or speech_level is None:
        return clip
    delta = speech_level - clip_level
    if abs(delta) < 1.0:
        return clip
    delta = max(-12.0, min(12.0, delta))  # avoid pumping a very quiet recording into noise
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip),
         "-af", f"volume={delta:.2f}dB", "-c:a", "libmp3lame", "-q:a", "2", str(dest)],
        check=True, capture_output=True,
    )
    return dest


def synthesize(client: ElevenLabs, text: str, voice_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(client.text_to_speech.convert(
        voice_id=voice_id, text=text, model_id=TTS_MODEL, output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=STABILITY)))
    dest.write_bytes(audio)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--turns", type=int, nargs="+", help="turn numbers to rebuild")
    parser.add_argument("--types", nargs="+", choices=sorted(VOC_DIRS),
                        help="rebuild every turn carrying these sounds")
    parser.add_argument("--all-vocalization-turns", action="store_true")
    parser.add_argument("--swap-voices", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    args.items = args.items.resolve()
    if not (args.turns or args.types or args.all_vocalization_turns):
        raise SystemExit("choose --turns, --types, or --all-vocalization-turns")
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.items.read_text(encoding="utf-8"))
    record = data["results"][args.index]
    seed, item_id = record["seed"], record["item_id"]

    voice_a = VOICE_MALE if args.swap_voices else VOICE_FEMALE
    voice_b = VOICE_FEMALE if args.swap_voices else VOICE_MALE
    voices = {seed["speaker_a"]: voice_a, seed["speaker_b"]: voice_b}

    voc_by_turn = {v["turn"]: v for v in record["vocalizations"]}
    wanted = set(args.turns or [])
    if args.types:
        wanted |= {t for t, v in voc_by_turn.items() if v["vocalization"] in args.types}
    if args.all_vocalization_turns:
        wanted |= set(voc_by_turn)
    targets = sorted(t for t in wanted if t in voc_by_turn)
    skipped = sorted(wanted - set(targets))
    if skipped:
        print(f"no vocalization on turn(s) {skipped}; skipping", flush=True)
    if not targets:
        raise SystemExit("nothing to rebuild")

    turn_text = {t["turn"]: t["text"] for t in record["turns"]}
    turn_speaker = {t["turn"]: t["speaker"] for t in record["turns"]}

    print(f"{item_id}: rebuilding {len(targets)} turn(s) with real recordings", flush=True)

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    rng = random.Random(args.seed)
    used: Counter = Counter()
    line_dir = OUT_DIR / "lines" / item_id          # replaces the single-take file
    part_dir = OUT_DIR / "parts" / item_id
    repairs: list[dict] = []

    for turn in targets:
        voc = voc_by_turn[turn]
        text, speaker = turn_text[turn], turn_speaker[turn]
        tag = voc["audio_tag"]
        before, _, after = text.partition(tag)
        before, after = before.strip(" —-–"), after.strip(" —-–")

        pieces: list[tuple[str, object]] = []
        reference: Path | None = None

        if before:
            path = part_dir / f"{turn:02d}_a.mp3"
            synthesize(client, before, voices[speaker], path)
            time.sleep(0.2)
            pieces.append(("file", path))
            reference = path
        if after:
            path_b = part_dir / f"{turn:02d}_b.mp3"
            synthesize(client, after, voices[speaker], path_b)
            time.sleep(0.2)
            reference = reference or path_b

        clip = pick_clip(voc["vocalization"], used, rng)
        matched = clip
        if reference is not None:
            matched = gain_to_match(clip, reference, part_dir / f"{turn:02d}_sound.mp3")

        if pieces:
            pieces.append(("silence", CLIP_GAP))
        pieces.append(("file", matched))
        if after:
            pieces.append(("silence", CLIP_GAP))
            pieces.append(("file", part_dir / f"{turn:02d}_b.mp3"))

        dest = line_dir / f"{turn:02d}_{speaker.lower().replace(' ', '_')}.mp3"
        old_seconds = duration_of(dest) if dest.exists() else None
        build(pieces, dest)
        new_seconds = duration_of(dest)

        repairs.append({
            "turn": turn, "vocalization": voc["vocalization"], "audio_tag": tag,
            "clip": str(clip.relative_to(REPO)),
            "clip_seconds": round(duration_of(clip), 3),
            "gain_matched": matched != clip,
            "position": "start" if not before else ("end" if not after else "middle"),
            "was_seconds": old_seconds and round(old_seconds, 3),
            "now_seconds": round(new_seconds, 3),
            "path": str(dest.relative_to(REPO)),
        })
        print(f"  t{turn:>2} {voc['vocalization']:9} {clip.name:16} "
              f"{repairs[-1]['position']:6} "
              f"{old_seconds or 0:5.2f}s -> {new_seconds:5.2f}s", flush=True)

    # re-sew the whole conversation from the current per-turn files
    timing_path = OUT_DIR / f"{item_id}_timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    pieces = []
    rows = []
    for row in timing["segments"]:
        if row.get("kind") != "line":
            continue
        path = REPO / row["path"]
        if pieces:
            pieces.append(("silence", timing.get("turn_gap", 0.36)))
            rows.append({"kind": "gap", "seconds": timing.get("turn_gap", 0.36)})
        pieces.append(("file", path))
        rows.append({**row, "seconds": round(duration_of(path), 3)})

    final = REPO / timing["audio"]
    build(pieces, final)
    total = duration_of(final)

    clock = 0.0
    for row in rows:
        if row["kind"] == "line":
            row["starts_at_seconds"] = round(clock, 2)
        clock += row["seconds"]
    timing["segments"] = rows
    timing["total_seconds"] = round(total, 3)
    timing["repairs"] = repairs
    timing["vocalizations"] = [
        {**mark,
         "turn_starts_at_seconds": next(
             r["starts_at_seconds"] for r in rows
             if r["kind"] == "line" and r["turn"] == mark["turn"]),
         "turn_starts_at": timestamp(next(
             r["starts_at_seconds"] for r in rows
             if r["kind"] == "line" and r["turn"] == mark["turn"]))}
        for mark in timing["vocalizations"]
    ]
    timing_path.write_text(json.dumps(timing, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nre-sewed {final.name}  ({timestamp(total)})", flush=True)
    print(f"updated {timing_path.name}", flush=True)
    print("next: verify_audio.py to re-check the rebuilt turns", flush=True)


if __name__ == "__main__":
    main()

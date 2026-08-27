"""Stages 6-7 — the conversation audio, and one clip per vocalization slot.

**Stage 6 is reused, not re-run.** The per-turn takes and their word alignments were rendered
for 1.0 from exactly these words, and dialogues.py refuses to import unless every turn still
matches the take recorded for it. So this reads 1.0's takes in place rather than paying
ElevenLabs to say the same sentences again and adding 8MB of identical audio to the repo. The
dependency is deliberate and recorded in the manifest.

**Stage 7 is per slot, not per form.** Each of the 205 slots gets its own laughter clip and its
own sigh clip, so a form that occurs eight times is eight different takes. Reusing one take
across slots would put audibly identical laughter in eight places, which is a cue about the
construction rather than about the conversation.

Every clip is levelled against the speech it will sit inside and re-rolled if it comes back
silent or runaway. Whether it actually *is* a laugh or a sigh is not decided here — that is
stage 8, verify_clips.py.

    python 2.0/make_audio.py                  # every slot, skipping clips already made
    python 2.0/make_audio.py --only emb_003   # one item, merged into the manifest
    python 2.0/make_audio.py --overwrite      # ignore what is on disk
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")

OUT = HERE / "out"
VOC_DIR = OUT / "audio_voc"
MANIFEST = OUT / "clip_manifest.json"

# Stage 6, reused in place. dialogues.py has already checked that every turn's words match the
# take here, and that every take has a word alignment.
PRIOR = REPO / "1.0" / "out"
TURN_DIR = PRIOR / "audio_turns"
ALIGNMENT = PRIOR / "turn_alignment.json"

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
VOICES = {"A": "s3TPKV1kjDlVtZbl4Ksh", "B": "aKw9UnnjRq5scbeeGI7Z"}
VOC_STABILITY = 0.30          # loose, so a laugh is allowed to be a laugh

MIN_CLIP, MAX_CLIP = 0.35, 3.5
MIN_DB = -40.0
MAX_BELOW_SPEECH_DB = 10.0    # a clip much quieter than the speech reads as absent
CLIP_ATTEMPTS = 4


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def mean_db(path: Path) -> float | None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect",
                           "-f", "null", "-"], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    return None


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"".join(client.text_to_speech.convert(
        voice_id=VOICES[speaker], text=text, model_id=TTS_MODEL,
        output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=VOC_STABILITY))))


def normalize(path: Path, speech_db: float) -> float | None:
    """Lift a clip that sits too far under the speech it will be spliced into."""
    db = mean_db(path)
    if db is None or db >= speech_db - MAX_BELOW_SPEECH_DB:
        return db
    gain = (speech_db - MAX_BELOW_SPEECH_DB) - db
    temp = path.with_suffix(".gain.mp3")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                    "-af", f"volume={gain:.2f}dB", "-c:a", "libmp3lame", "-q:a", "2",
                    str(temp)], check=True, capture_output=True)
    temp.replace(path)
    return mean_db(path)


def make_clip(eleven: ElevenLabs, token: str, speaker: str, dest: Path,
              speech_db: float, overwrite: bool) -> dict:
    """One vocalization take: re-roll on silence or runaway length, then level it."""
    problems: list[str] = []
    for attempt in range(1, CLIP_ATTEMPTS + 1):
        fresh = not (dest.exists() and not overwrite and attempt == 1)
        if fresh:
            synthesize(eleven, token, speaker, dest)
        seconds, db = duration_of(dest), mean_db(dest)
        problems = []
        if not MIN_CLIP <= seconds <= MAX_CLIP:
            problems.append(f"{seconds:.2f}s outside {MIN_CLIP}-{MAX_CLIP}s")
        if db is None or db < MIN_DB:
            problems.append(f"{db} dB is silence")
        if not problems:
            lifted = normalize(dest, speech_db) if fresh else db
            return {"seconds": round(seconds, 3), "db": db, "db_after": lifted,
                    "attempts": attempt, "ok": True}
        print(f"      reroll ({'; '.join(problems)})", flush=True)
    return {"seconds": round(duration_of(dest), 3), "db": mean_db(dest),
            "attempts": CLIP_ATTEMPTS, "ok": False, "problems": problems}


def clip_path(item_id: str, condition: str, order: int, slot: dict) -> Path:
    return (VOC_DIR / f"{item_id}_{condition}_{order:02d}"
                      f"_t{slot['turn']:02d}_w{slot['after_word']:03d}.mp3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = json.loads((OUT / "items.json").read_text())["items"]
    plan = {e["item_id"]: e for e in json.loads((OUT / "plan.json").read_text())["items"]}
    alignment = json.loads(ALIGNMENT.read_text())

    wanted = [i for i in items if not args.only or i["item_id"] in args.only]
    if args.limit:
        wanted = wanted[: args.limit]

    eleven = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"].strip())
    records, bad = [], 0

    for item in wanted:
        entry = plan[item["item_id"]]
        takes = [TURN_DIR / turn["take"].split("/")[-1] for turn in item["turns"]]
        missing = [p.name for p in takes if not p.exists()]
        if missing:
            raise SystemExit(f"{item['item_id']}: turn audio missing: {missing}")
        levels = [d for d in (mean_db(p) for p in takes) if d is not None]
        speech_db = sum(levels) / max(1, len(levels))
        print(f"\n{'=' * 78}\n{item['item_id']}  {len(item['turns'])} turns · "
              f"{len(entry['slots'])} slots · speech {speech_db:.1f} dB\n{'=' * 78}",
              flush=True)

        clips = []
        for order, slot in enumerate(entry["slots"]):
            speaker = item["turns"][slot["turn"] - 1]["speaker"]
            words = alignment[item["turns"][slot["turn"] - 1]["take"]]
            for condition, kind in (("happy", "laugh"), ("sad", "sigh")):
                path = clip_path(item["item_id"], condition, order, slot)
                info = make_clip(eleven, slot[kind], speaker, path, speech_db, args.overwrite)
                bad += not info["ok"]
                clips.append({"item_id": item["item_id"], "condition": condition,
                              "order": order, "turn": slot["turn"],
                              "after_word": slot["after_word"],
                              "position": slot["position"], "speaker": speaker,
                              "token": slot[kind], "kind": kind,
                              "word": words[slot["after_word"] - 1]["word"]
                                      if 0 < slot["after_word"] <= len(words) else None,
                              "path": str(path.relative_to(HERE)), **info})
                flag = "" if info["ok"] else "  <- FAILED QC"
                after = info.get("db_after")
                lifted = (after is not None and info["db"] is not None
                          and round(after - info["db"], 1) > 0.5)
                print(f"  {condition:5} t{slot['turn']} w{slot['after_word']:<3} "
                      f"{slot[kind]:20} {info['seconds']:4.2f}s "
                      f"{info['db']:6.1f}dB"
                      + (f" -> {after:6.1f}dB" if lifted else "")
                      + flag, flush=True)
        records.append({"item_id": item["item_id"], "slots": len(entry["slots"]),
                        "clips": clips})

    if (args.only or args.limit) and MANIFEST.exists():
        previous = json.loads(MANIFEST.read_text()).get("items", [])
        rebuilt = {r["item_id"]: r for r in records}
        records = [rebuilt.pop(r["item_id"], r) for r in previous] + list(rebuilt.values())

    total = sum(len(r["clips"]) for r in records)
    MANIFEST.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tts_model": TTS_MODEL, "voices": VOICES, "voc_stability": VOC_STABILITY,
        "turn_audio": "1.0/out/audio_turns (stage 6 reused; words verified by dialogues.py)",
        "clip_gate": {"seconds": [MIN_CLIP, MAX_CLIP], "min_db": MIN_DB,
                      "max_below_speech_db": MAX_BELOW_SPEECH_DB},
        "items": records}, indent=2, ensure_ascii=False))
    print(f"\n{len(records)} item(s) · {total} clips · {bad} failed QC · "
          f"wrote {MANIFEST.name}")


if __name__ == "__main__":
    main()

"""Render a soda_scatter item as audio, letting eleven_v3 perform the inline tags.

Unlike the sketches elsewhere in this repo, the vocalizations here are not separate segments
spliced between speech — they are bracketed tags sitting inside the turn text, often
mid-sentence ("and—[quiet sob]—I cannot let old pride..."). So each turn is synthesized as
one take and eleven_v3 performs the tag in place. That is the only way to get a sound that
genuinely interrupts a sentence rather than bracketing it.

The consequence is that these vocalizations cannot be excised afterwards to build a
no-laughter control, the way missed_train_sketch does. If you need that control for an item,
it has to be planned as separate segments from the start.

Timestamps for every vocalization are written out, so a later eval can be scored on whether
the model locates each sound as well as on how it reads it.

Usage:
    python soda_scatter/make_audio.py
    python soda_scatter/make_audio.py --swap-voices --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from make_audio import build, duration_of, timestamp  # noqa: E402

DEFAULT_IN = HERE / "out" / "items.json"
OUT_DIR = HERE / "out"

MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICE_FEMALE = "aKw9UnnjRq5scbeeGI7Z"
VOICE_MALE = "s3TPKV1kjDlVtZbl4Ksh"

# these turns carry emotional vocalizations, so the voice needs latitude; too low and the
# long informative business lines start to wander
STABILITY = 0.4

TURN_GAP = 0.36

TAG_RE = re.compile(r"\[([^\[\]]+)\]")


def synthesize(client: ElevenLabs, text: str, voice_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(
        client.text_to_speech.convert(
            voice_id=voice_id, text=text, model_id=MODEL, output_format=OUTPUT_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=STABILITY),
        )
    )
    dest.write_bytes(audio)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--index", type=int, default=0, help="which item in the file")
    parser.add_argument("--swap-voices", action="store_true",
                        help="give speaker A the male voice instead")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    record = data["results"][args.index]
    seed = record["seed"]
    item_id = record["item_id"]

    voice_a = VOICE_MALE if args.swap_voices else VOICE_FEMALE
    voice_b = VOICE_FEMALE if args.swap_voices else VOICE_MALE
    voices = {seed["speaker_a"]: voice_a, seed["speaker_b"]: voice_b}

    line_dir = OUT_DIR / "lines" / item_id
    final = OUT_DIR / "audio" / f"{item_id}.mp3"
    transcript = OUT_DIR / f"{item_id}_audio_transcript.md"

    voc_by_turn = {v["turn"]: v for v in record["vocalizations"]}
    print(f"{item_id}: {len(record['turns'])} turns, {len(voc_by_turn)} vocalizations", flush=True)
    print(f"  {seed['speaker_a']} -> {voice_a}", flush=True)
    print(f"  {seed['speaker_b']} -> {voice_b}", flush=True)

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    client = ElevenLabs(api_key=key)

    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []

    for turn in record["turns"]:
        number, speaker, text = turn["turn"], turn["speaker"], turn["text"]
        path = line_dir / f"{number:02d}_{speaker.lower().replace(' ', '_')}.mp3"
        if not path.exists() or args.overwrite:
            synthesize(client, text, voices[speaker], path)
            time.sleep(0.25)
        seconds = duration_of(path)
        voc = voc_by_turn.get(number)
        mark = f"  <- {voc['vocalization']} {voc['audio_tag']}" if voc else ""
        print(f"  [{number:02d}] {speaker:8} {seconds:5.2f}s{mark}", flush=True)

        if pieces:
            pieces.append(("silence", TURN_GAP))
            rows.append({"kind": "gap", "seconds": TURN_GAP})
        pieces.append(("file", path))
        rows.append({
            "kind": "line", "turn": number, "speaker": speaker, "text": text,
            "seconds": round(seconds, 3),
            # the verifier listens to these per-turn files rather than the sewn mix, so a
            # single sound is judged in isolation instead of competing with eleven others
            "path": str(path.relative_to(REPO)),
            "vocalization": voc["vocalization"] if voc else None,
            "audio_tag": voc["audio_tag"] if voc else None,
        })

    build(pieces, final)
    total = duration_of(final)

    # running clock, so every vocalization gets a timestamp in the finished mix
    clock = 0.0
    marks: list[dict] = []
    for row in rows:
        if row["kind"] == "line":
            if row["vocalization"]:
                voc = voc_by_turn[row["turn"]]
                marks.append({
                    "turn": row["turn"], "speaker": row["speaker"],
                    "vocalization": row["vocalization"], "audio_tag": row["audio_tag"],
                    "turn_starts_at": timestamp(clock),
                    "turn_starts_at_seconds": round(clock, 2),
                    "target": voc["target"], "intention_after": voc["intention_after"],
                })
            row["starts_at_seconds"] = round(clock, 2)
        clock += row["seconds"]

    lines = [
        f"# {item_id} — audio",
        "",
        f"Runtime **{timestamp(total)}** · {seed['speaker_a']} and {seed['speaker_b']} are "
        "different voices · vocalizations are performed in place from inline tags.",
        "",
        f"**Scenario (SODA #{seed.get('original_index')})** — {seed['narrative']}",
        "",
        "| time | turn | speaker | line |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["kind"] != "line":
            continue
        lines.append(
            f"| {timestamp(row['starts_at_seconds'])} | {row['turn']} | {row['speaker']} | "
            f"{row['text'].replace('|', '-')} |"
        )
    lines += ["", "## Vocalizations, with timestamps", "",
              "| turn starts | turn | speaker | sound | tag | target | intention after |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for mark in marks:
        lines.append(
            f"| {mark['turn_starts_at']} | {mark['turn']} | {mark['speaker']} | "
            f"{mark['vocalization']} | `{mark['audio_tag']}` | {mark['target']} | "
            f"{mark['intention_after']} |"
        )
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / f"{item_id}_timing.json").write_text(
        json.dumps({
            "item_id": item_id,
            "audio": str(final.relative_to(REPO)),
            "total_seconds": round(total, 3),
            "turn_gap": TURN_GAP,
            "stability": STABILITY,
            "voices": {seed["speaker_a"]: voice_a, seed["speaker_b"]: voice_b},
            "vocalizations": marks,
            "segments": rows,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nwrote {final}  ({timestamp(total)})", flush=True)
    for mark in marks:
        print(f"  {mark['turn_starts_at']}  t{mark['turn']:>2} {mark['speaker']:8} "
              f"{mark['vocalization']:9} {mark['audio_tag']}", flush=True)
    print(f"transcript: {transcript}", flush=True)


if __name__ == "__main__":
    main()

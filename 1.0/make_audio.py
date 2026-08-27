"""Synthesize the content once, the vocalizations separately, and sew the three conditions.

The whole benchmark rests on one property: the spoken words must be the same audio in all
three conditions. So each turn is synthesized exactly once, into its own file, and every
condition is built from those same files. Nothing is re-synthesized per condition — a second
take would differ in prosody and length, and then a model's behaviour could be responding to
delivery rather than to the vocalization.

Turn audio is deliberately flat: high stability, no delivery tags, nothing in the words that
leans amused or glum. The clips are the opposite — low stability, so the voice is free to
actually laugh rather than produce a polite "heh".

Each clip is checked before it is used, because eleven_v3 fails in two directions that are
both invisible in the waveform: it sometimes *speaks* the tag ("Sigh.") and it sometimes
ignores it and returns near-silence. Neither is caught by listening to a spectrogram, and a
laughed take that is secretly silent would quietly turn a happy item into a neutral one.

    duration   0.4-3.5s          rejects empty generations and rambling ones
    energy     above -40 dB      rejects silence
    tag leak   ASR must not say the manner word aloud

These are generation QC, not perception: they ask whether ElevenLabs produced what the
manifest claims, never whether a model can hear it. The four-model perception vote runs
afterwards, separately, and marks items suspicious rather than deleting them.

Usage:
    python benchmark/make_audio.py --limit 2
    python benchmark/make_audio.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
load_dotenv(REPO / ".env")

from sew import build

TRANSCRIPTS = HERE / "out" / "transcripts.json"
TURN_DIR = HERE / "out" / "audio_turns"
VOC_DIR = HERE / "out" / "audio_voc"
CONV_DIR = HERE / "out" / "audio"
MANIFEST = HERE / "out" / "audio_manifest.json"
TURN_TEXTS = HERE / "out" / "turn_texts.json"   # what each take actually says
ALIGNMENT = HERE / "out" / "turn_alignment.json"   # where each word sits inside each take

TTS_MODEL = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

VOICES = {"A": "s3TPKV1kjDlVtZbl4Ksh", "B": "aKw9UnnjRq5scbeeGI7Z"}
SPEECH_STABILITY = 0.55   # flat, so the same take is honest in all three conditions
VOC_STABILITY = 0.30      # loose, so a laugh is a laugh

TURN_GAP = 0.32           # between turns
SPLICE_GAP = 0.18         # between a clip and the words it sits against, inside one turn

MIN_CLIP, MAX_CLIP = 0.4, 3.5
MIN_DB = -40.0
CLIP_ATTEMPTS = 4

# A sigh 15 dB under the speech is a defect in the stimulus, not a hard item: if a model
# misses it we learn nothing. Clips are lifted to sit within this much of the item's own
# speech level. Not matched exactly — a real sigh is quieter than a sentence.
MAX_BELOW_SPEECH_DB = 10.0


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True,
                         check=True).stdout
    return float(out.strip())


def mean_db(path: Path) -> float | None:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", err)
    return float(m.group(1)) if m else None


def synthesize_aligned(client: ElevenLabs, text: str, speaker: str, dest: Path,
                       stability: float) -> list[dict]:
    """Synthesize a turn and keep the word timings that come back with it.

    The alignment is character-level, which is what makes mid-turn splicing possible: the
    space between two words has its own start and end, so the silence between them is a
    returned value rather than something to infer. Punctuation pauses do not appear as
    inter-word gaps — they sit inside the punctuation character's own duration — so the score
    below adds that in, and the widest-scoring boundaries are where the speaker was already
    pausing.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = client.text_to_speech.convert_with_timestamps(
        voice_id=VOICES[speaker], text=text, model_id=TTS_MODEL,
        output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=stability),
    )
    dest.write_bytes(base64.b64decode(result.audio_base_64))

    a = result.alignment
    words: list[dict] = []
    current, start, prev_end, tail = "", None, 0.0, 0.0
    for ch, cs, ce in zip(a.characters, a.character_start_times_seconds,
                          a.character_end_times_seconds):
        if ch == " ":
            if current:
                words.append({"word": current, "start": start, "end": prev_end,
                              "gap_start": cs, "gap_end": ce,
                              "gap": round(ce - cs, 4), "punct_pause": round(tail, 4)})
                current, start, tail = "", None, 0.0
            continue
        if start is None:
            start = cs
        if ch in ".,;:!?-":
            tail += ce - cs
        current += ch
        prev_end = ce
    if current:
        words.append({"word": current, "start": start, "end": prev_end,
                      "gap_start": None, "gap_end": None, "gap": 0.0,
                      "punct_pause": round(tail, 4)})
    for index, word in enumerate(words, 1):
        word["after_word"] = index
        word["score"] = round(word["gap"] + word["punct_pause"], 4)
    return words


def synthesize(client: ElevenLabs, text: str, speaker: str, dest: Path,
               stability: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"".join(client.text_to_speech.convert(
        voice_id=VOICES[speaker], text=text, model_id=TTS_MODEL,
        output_format=OUTPUT_FORMAT,
        voice_settings=ModelSettingsResponseModel(stability=stability),
    )))


def normalize(path: Path, speech_db: float) -> float | None:
    """Lift a clip that sits too far under the speech, in place."""
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
    """Generate one vocalization; re-roll on empty or runaway takes, then level it.

    Whether the clip actually *is* a laugh or a sigh — and whether the voice said the tag
    out loud instead of performing it — is not decided here. That is the four-model vote,
    which runs afterwards and marks disagreements for a human rather than deleting them.
    """
    problems: list[str] = []
    for attempt in range(1, CLIP_ATTEMPTS + 1):
        if not (dest.exists() and not overwrite and attempt == 1):
            synthesize(eleven, token, speaker, dest, VOC_STABILITY)
        seconds, db = duration_of(dest), mean_db(dest)
        problems = []
        if not MIN_CLIP <= seconds <= MAX_CLIP:
            problems.append(f"{seconds:.2f}s outside {MIN_CLIP}-{MAX_CLIP}s")
        if db is None or db < MIN_DB:
            problems.append(f"{db} dB is silence")
        if not problems:
            lifted = normalize(dest, speech_db)
            return {"seconds": round(seconds, 3), "db": db, "db_after": lifted,
                    "gain_applied": lifted is not None and db is not None
                    and round(lifted - db, 1) > 0.5,
                    "attempts": attempt, "ok": True}
        print(f"      reroll ({'; '.join(problems)})", flush=True)
    return {"seconds": round(duration_of(dest), 3), "db": mean_db(dest),
            "attempts": CLIP_ATTEMPTS, "ok": False, "problems": problems}


def cut(source: Path, start: float, end: float | None, dest: Path) -> Path:
    """A slice of a turn take, so a vocalization can sit inside the sentence.

    Both halves come out of the same file, so the spoken samples are still identical across
    the three conditions — the only thing a splice adds is silence and the clip.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-ss", f"{start:.3f}"]
    if end is not None:
        command += ["-to", f"{end:.3f}"]
    command += ["-c:a", "libmp3lame", "-q:a", "2", str(dest)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-500:] or "ffmpeg cut failed")
    return dest


def split_point(words: list[dict], after_word: int) -> float | None:
    """Where to cut, in seconds — the middle of the silence the speaker actually left."""
    if not words or after_word <= 0 or after_word >= len(words):
        return None
    word = words[after_word - 1]
    if word.get("gap_start") is None:
        return word["end"]
    return (word["gap_start"] + word["gap_end"]) / 2


def assemble(item: dict, condition: str, insertions: list[dict], turn_paths: list[Path],
             voc_paths: dict[tuple, Path], dest: Path,
             alignment: dict[str, list[dict]] | None = None) -> dict:
    """One condition, from the shared turn audio plus this condition's clips."""
    alignment = alignment or {}
    by_turn: dict[int, tuple[int, dict]] = {}
    for index, ins in enumerate(insertions):
        by_turn[ins["turn"]] = (index, ins)

    pieces: list[tuple[str, object]] = []
    timeline: list[dict] = []
    clock = 0.0

    def add_file(path: Path, kind: str, turn: int, detail: dict | None = None) -> None:
        nonlocal clock
        seconds = duration_of(path)
        timeline.append({"kind": kind, "turn": turn, "start": round(clock, 3),
                         "end": round(clock + seconds, 3), **(detail or {})})
        pieces.append(("file", path))
        clock += seconds

    def add_gap(seconds: float) -> None:
        nonlocal clock
        if pieces:
            pieces.append(("silence", seconds))
            clock += seconds

    for turn_index, (turn, path) in enumerate(zip(item["turns"], turn_paths), 1):
        add_gap(TURN_GAP)
        entry = by_turn.get(turn_index)
        if entry is None:
            add_file(path, "speech", turn_index,
                     {"speaker": turn["speaker"], "text": turn["text"]})
            continue

        order, ins = entry
        clip = voc_paths[(condition, order)]
        words = alignment.get(str(path.relative_to(HERE)), [])
        after = ins.get("after_word")
        if after is None:                     # older plans only knew start and end
            after = 0 if ins.get("position") == "start" else len(words)
        at = split_point(words, after)
        detail = {"token": ins["token"], "speaker": turn["speaker"], "after_word": after}

        if at is None and after <= 0:                       # in front of the whole turn
            add_file(clip, "vocalization", turn_index, {**detail, "where": "start"})
            add_gap(SPLICE_GAP)
            add_file(path, "speech", turn_index,
                     {"speaker": turn["speaker"], "text": turn["text"]})
        elif at is None:                                    # after the whole turn
            add_file(path, "speech", turn_index,
                     {"speaker": turn["speaker"], "text": turn["text"]})
            add_gap(SPLICE_GAP)
            add_file(clip, "vocalization", turn_index, {**detail, "where": "end"})
        else:                                               # inside the turn
            stem = f"{item['item_id']}_{condition}_t{turn_index:02d}"
            first = cut(path, 0.0, at, TURN_DIR / f"{stem}_a.mp3")
            second = cut(path, at, None, TURN_DIR / f"{stem}_b.mp3")
            said = turn["text"].split()
            add_file(first, "speech", turn_index,
                     {"speaker": turn["speaker"], "text": " ".join(said[:after])})
            add_gap(SPLICE_GAP)
            add_file(clip, "vocalization", turn_index,
                     {**detail, "where": f"after word {after}", "cut_at": round(at, 3)})
            add_gap(SPLICE_GAP)
            add_file(second, "speech", turn_index,
                     {"speaker": turn["speaker"], "text": " ".join(said[after:])})

    build(pieces, dest)
    return {"path": str(dest.relative_to(REPO)), "seconds": round(duration_of(dest), 3),
            "timeline": timeline}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", action="append")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
    items = [i for i in data["items"] if "error" not in i]
    if args.only:
        items = [i for i in items if i["item_id"] in args.only]
    if args.limit:
        items = items[: args.limit]

    eleven = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"].strip())
    spoken_texts = (json.loads(TURN_TEXTS.read_text(encoding="utf-8"))
                    if TURN_TEXTS.exists() else {})
    alignment = (json.loads(ALIGNMENT.read_text(encoding="utf-8"))
                 if ALIGNMENT.exists() else {})

    records, bad_clips = [], 0
    for item in items:
        print(f"\n{'=' * 78}\n{item['item_id']}  {len(item['turns'])} turns\n{'=' * 78}",
              flush=True)

        turn_paths = []
        for index, turn in enumerate(item["turns"], 1):
            path = TURN_DIR / f"{item['item_id']}_t{index:02d}_{turn['speaker']}.mp3"
            key = str(path.relative_to(HERE))
            # A take is reused only if it was made from the words we are asking for now.
            # Without this, regenerating one item's transcript left its old audio in place:
            # emb_002 said "I was midway through a yoga class when I heard a seam give way"
            # while its transcript had been rewritten to something else entirely, and nothing
            # in the pipeline noticed.
            stale = spoken_texts.get(key) != turn["text"]
            unaligned = key not in alignment
            if not path.exists() or args.overwrite or stale or unaligned:
                if stale and path.exists():
                    print(f"  t{index:02d}: words changed, re-synthesizing", flush=True)
                elif unaligned and path.exists():
                    print(f"  t{index:02d}: no alignment on file, re-synthesizing", flush=True)
                alignment[key] = synthesize_aligned(eleven, turn["text"], turn["speaker"],
                                                    path, SPEECH_STABILITY)
                spoken_texts[key] = turn["text"]
            turn_paths.append(path)
        speech_levels = [mean_db(p) for p in turn_paths]
        speech_db = sum(d for d in speech_levels if d is not None) / max(
            1, len([d for d in speech_levels if d is not None]))
        print(f"  {len(turn_paths)} turn takes "
              f"({sum(duration_of(p) for p in turn_paths):.1f}s of speech, "
              f"{speech_db:.1f} dB)", flush=True)

        voc_paths, voc_records = {}, []
        for condition, key in (("happy", "happy_insertions"), ("sad", "sad_insertions")):
            for order, ins in enumerate(item.get(key, [])):
                speaker = item["turns"][ins["turn"] - 1]["speaker"]
                path = (VOC_DIR /
                        f"{item['item_id']}_{condition}_{order}_t{ins['turn']:02d}"
                        f"_{ins['position']}.mp3")
                info = make_clip(eleven, ins["token"], speaker, path, speech_db,
                                 args.overwrite)
                voc_paths[(condition, order)] = path
                bad_clips += not info["ok"]
                voc_records.append({"condition": condition, "order": order,
                                    "turn": ins["turn"], "position": ins["position"],
                                    "token": ins["token"], "speaker": speaker,
                                    "path": str(path.relative_to(REPO)), **info})
                flag = "" if info["ok"] else "  <- FAILED QC"
                after = info.get("db_after")
                print(f"  {condition:5} t{ins['turn']} {ins['position']:5} "
                      f"{ins['token']:18} {info['seconds']:4.2f}s {info['db']:6.1f}dB"
                      + (f" -> {after:6.1f}dB" if info.get("gain_applied") else "")
                      + flag, flush=True)

        conditions = {
            "neutral": assemble(item, "neutral", [], turn_paths, voc_paths,
                                CONV_DIR / f"{item['item_id']}_neutral.mp3", alignment),
            "happy": assemble(item, "happy", item.get("happy_insertions", []), turn_paths,
                              voc_paths, CONV_DIR / f"{item['item_id']}_happy.mp3",
                              alignment),
            "sad": assemble(item, "sad", item.get("sad_insertions", []), turn_paths, voc_paths,
                            CONV_DIR / f"{item['item_id']}_sad.mp3", alignment),
        }
        for name, info in conditions.items():
            print(f"  {name:8} {info['seconds']:6.2f}s  {Path(info['path']).name}",
                  flush=True)

        records.append({"item_id": item["item_id"], "situation": item["situation"],
                        "turns": item["turns"], "clips": voc_records,
                        "conditions": conditions})

    TURN_TEXTS.write_text(json.dumps(spoken_texts, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    ALIGNMENT.write_text(json.dumps(alignment, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    dest = args.out or MANIFEST
    # --only/--limit must patch the manifest, not replace it with the one item just built
    if (args.only or args.limit) and dest.exists():
        previous = json.loads(dest.read_text(encoding="utf-8")).get("items", [])
        rebuilt = {r["item_id"]: r for r in records}
        merged = [rebuilt.pop(r["item_id"], r) for r in previous]
        records = merged + list(rebuilt.values())
    dest.write_text(json.dumps({
        "tts_model": TTS_MODEL, "voices": VOICES,
        "speech_stability": SPEECH_STABILITY, "voc_stability": VOC_STABILITY,
        "turn_gap": TURN_GAP, "splice_gap": SPLICE_GAP,
        "clip_gate": {"seconds": [MIN_CLIP, MAX_CLIP], "min_db": MIN_DB,
                      "max_below_speech_db": MAX_BELOW_SPEECH_DB},
        "items": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(records)} item(s) · {bad_clips} clip(s) failed QC · wrote {dest.name}")


if __name__ == "__main__":
    main()

"""Voice a soda_scatter item with gpt-4o-mini-tts, using `instructions` for the sounds.

The speech endpoint takes three things that matter here: `input` (the words, read verbatim),
`voice`, and `instructions` (how to deliver it). That split is the attraction — because
`input` is spoken literally, this model cannot paraphrase the script the way a conversational
model can, so the words are guaranteed correct and only the sound is uncertain.

The sounds therefore have to come from `instructions`, phrased as a direction rather than a
markup tag: bracketed tags are either ignored or read aloud.

Two modes, because it is not obvious a TTS model will produce a sound that has no
corresponding text in `input`:

    instructions  — input is the words only; the sound is requested purely in instructions
    onomatopoeia  — input carries a vocal cue ("hhhh", "ha ha ha") where the sound belongs,
                    and instructions say to perform that cue as a real sound, not read it

Mid-sentence placement is the weak spot for both. The direction names the word to pause
after, but nothing guarantees compliance, so listen before trusting a batch.

Usage:
    python soda_scatter/make_audio_tts.py
    python soda_scatter/make_audio_tts.py --mode onomatopoeia
    python soda_scatter/make_audio_tts.py --probe          # 3 lines only, both modes
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
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

from make_audio import build, duration_of, timestamp  # noqa: E402

DEFAULT_IN = HERE / "out" / "items.json"
OUT_DIR = HERE / "out"

MODEL = "gpt-4o-mini-tts"
RESPONSE_FORMAT = "mp3"
TURN_GAP = 0.36

TAG_RE = re.compile(r"\[([^\[\]]+)\]")

SOUND_WORD = {"laughter": "laughter", "sigh": "sigh", "sob": "sob",
              "yawn": "yawn", "gasp": "gasp"}

# a vocal cue for the onomatopoeia mode — something in `input` for the model to land on
CUE = {
    "sigh": "hhhhh",
    "sob": "hh— hh—",
    "gasp": "hah",
    "yawn": "haaaah",
    "laughter": "ha ha ha",
}

# intensity words fight audibility; the emotional qualifier is what carries the meaning
INTENSITY_RE = re.compile(
    r"(?i)\b(small|stifled|quiet|slight|faint|soft|brief|subtle|tiny|little|half)\b")


def descriptor(audio_tag: str, vocalization: str) -> str:
    inner = " ".join(INTENSITY_RE.sub(" ", audio_tag.strip().strip("[]")).split())
    if SOUND_WORD[vocalization] not in inner.lower():
        inner = f"{inner} {SOUND_WORD[vocalization]}".strip()
    return inner or SOUND_WORD[vocalization]


def split_on_tag(text: str, audio_tag: str) -> tuple[str, str]:
    before, _, after = text.partition(audio_tag)
    return before.strip(" —-–"), after.strip(" —-–")


def build_line(text: str, voc: dict | None, mode: str) -> tuple[str, str]:
    """Return (input_text, instructions) for one turn."""
    if not voc:
        return (
            " ".join(TAG_RE.sub(" ", text).split()),
            "Read this line naturally, as one side of a calm business conversation "
            "between two people who used to be rivals. Even pace, no added emotion.",
        )

    tag, kind = voc["audio_tag"], voc["vocalization"]
    before, after = split_on_tag(text, tag)
    desc, word = descriptor(tag, kind), SOUND_WORD[kind]

    if mode == "onomatopoeia":
        cue = CUE[kind]
        joined = " ".join(x for x in (before, cue, after) if x)
        instructions = (
            f'This line contains "{cue}", which is not a word. Perform it as one brief, '
            f"clearly audible {desc} — a real {word}, made with the voice — and never "
            f'pronounce it as letters or say the word "{word}". Deliver the rest of the '
            "line naturally, in character, as part of a business conversation."
        )
        return " ".join(joined.split()), instructions

    words_only = " ".join(x for x in (before, after) if x)
    if not before:
        where = f"Begin with one brief, clearly audible {desc}, then speak the line."
    elif not after:
        where = f"Speak the line, then end with one brief, clearly audible {desc}."
    else:
        last = before.rstrip(".,;:").split()[-1] if before.split() else ""
        where = (
            f'Partway through, immediately after the word "{last}", break off and make one '
            f"brief, clearly audible {desc}, then continue the rest of the line."
        )
    instructions = (
        f"{where} Make the sound for real with your voice, audibly. Do not say the word "
        f'"{word}" and do not describe the {word}. Deliver the words naturally, in '
        "character, as part of a business conversation."
    )
    return " ".join(words_only.split()), instructions


def synthesize(client: OpenAI, text: str, instructions: str, voice: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.audio.speech.with_streaming_response.create(
        model=MODEL, voice=voice, input=text, instructions=instructions,
        response_format=RESPONSE_FORMAT,
    ) as response:
        response.stream_to_file(dest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--mode", default="instructions",
                        choices=["instructions", "onomatopoeia"])
    parser.add_argument("--voice-a", default="marin")
    parser.add_argument("--voice-b", default="cedar")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--probe", action="store_true",
                        help="render 3 vocalization lines in BOTH modes and stop")
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    record = data["results"][args.index]
    seed, item_id = record["seed"], record["item_id"]
    voices = {seed["speaker_a"]: args.voice_a, seed["speaker_b"]: args.voice_b}
    voc_by_turn = {v["turn"]: v for v in record["vocalizations"]}

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    if args.probe:
        # one turn-initial, one mid-sentence, one at a different position
        picks = [t for t in record["turns"] if t["turn"] in (2, 3, 5)]
        probe_dir = OUT_DIR / "tts_probe"
        print(f"probe: {len(picks)} line(s) x 2 modes -> {probe_dir}", flush=True)
        for mode in ("instructions", "onomatopoeia"):
            for turn in picks:
                voc = voc_by_turn.get(turn["turn"])
                text, instructions = build_line(turn["text"], voc, mode)
                dest = probe_dir / f"t{turn['turn']:02d}_{mode}.mp3"
                synthesize(client, text, instructions, voices[turn["speaker"]], dest)
                print(f"\n  [{mode}] turn {turn['turn']} ({voc['vocalization']}) "
                      f"-> {duration_of(dest):.2f}s  {dest.name}", flush=True)
                print(f"    input       : {text}", flush=True)
                print(f"    instructions: {instructions}", flush=True)
                time.sleep(0.2)
        print("\nlisten and pick a mode, then run without --probe", flush=True)
        return

    line_dir = OUT_DIR / f"lines_tts_{args.mode}" / item_id
    final = OUT_DIR / "audio" / f"{item_id}_tts_{args.mode}.mp3"
    transcript = OUT_DIR / f"{item_id}_tts_{args.mode}_transcript.md"

    print(f"{item_id} · {MODEL} · mode={args.mode}", flush=True)
    print(f"  {seed['speaker_a']} -> {args.voice_a}", flush=True)
    print(f"  {seed['speaker_b']} -> {args.voice_b}", flush=True)

    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []
    for turn in record["turns"]:
        voc = voc_by_turn.get(turn["turn"])
        text, instructions = build_line(turn["text"], voc, args.mode)
        dest = line_dir / f"{turn['turn']:02d}_{turn['speaker'].lower()}.mp3"
        if not dest.exists() or args.overwrite:
            synthesize(client, text, instructions, voices[turn["speaker"]], dest)
            time.sleep(0.2)
        seconds = duration_of(dest)
        mark = f"  <- {voc['vocalization']}" if voc else ""
        print(f"  [{turn['turn']:02d}] {turn['speaker']:8} {seconds:5.2f}s{mark}", flush=True)

        if pieces:
            pieces.append(("silence", TURN_GAP))
            rows.append({"kind": "gap", "seconds": TURN_GAP})
        pieces.append(("file", dest))
        rows.append({
            "kind": "line", "turn": turn["turn"], "speaker": turn["speaker"],
            "scripted": turn["text"], "tts_input": text, "instructions": instructions,
            "seconds": round(seconds, 3),
            "vocalization": voc["vocalization"] if voc else None,
            "audio_tag": voc["audio_tag"] if voc else None,
        })

    build(pieces, final)
    total = duration_of(final)

    clock = 0.0
    marks: list[dict] = []
    for row in rows:
        if row["kind"] == "line":
            row["starts_at_seconds"] = round(clock, 2)
            if row["vocalization"]:
                voc = voc_by_turn[row["turn"]]
                marks.append({
                    "turn": row["turn"], "speaker": row["speaker"],
                    "vocalization": row["vocalization"], "audio_tag": row["audio_tag"],
                    "turn_starts_at": timestamp(clock),
                    "turn_starts_at_seconds": round(clock, 2),
                    "target": voc["target"], "intention_after": voc["intention_after"],
                })
        clock += row["seconds"]

    lines = [
        f"# {item_id} — voiced by {MODEL} (mode: {args.mode})",
        "",
        f"Runtime **{timestamp(total)}** · {seed['speaker_a']} ({args.voice_a}) and "
        f"{seed['speaker_b']} ({args.voice_b}).",
        "",
        "`input` is read verbatim by this model, so the words cannot drift; the "
        "vocalizations are requested through `instructions`.",
        "",
        f"**Scenario (SODA #{seed.get('original_index')})** — {seed['narrative']}",
        "",
        "| time | turn | speaker | tts input | sound requested |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["kind"] != "line":
            continue
        lines.append(
            f"| {timestamp(row['starts_at_seconds'])} | {row['turn']} | {row['speaker']} | "
            f"{row['tts_input'].replace('|', '-')} | {row['audio_tag'] or ''} |"
        )
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / f"{item_id}_tts_{args.mode}_timing.json").write_text(
        json.dumps({
            "item_id": item_id, "voiced_by": MODEL, "mode": args.mode,
            "voices": {seed["speaker_a"]: args.voice_a, seed["speaker_b"]: args.voice_b},
            "audio": str(final.relative_to(REPO)),
            "total_seconds": round(total, 3), "turn_gap": TURN_GAP,
            "vocalizations": marks,
            "segments": [{k: v for k, v in r.items() if k != "path"} for r in rows],
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

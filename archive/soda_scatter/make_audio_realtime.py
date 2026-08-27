"""Voice a soda_scatter item with gpt-realtime instead of TTS, one session per speaker.

eleven_v3 renders bracketed tags inconsistently — the sound is often too slight to read as a
sigh or a sob at all. gpt-realtime produces vocalizations natively, so here it acts rather
than synthesizes.

Two sessions, one per speaker, each with its own voice. Each session is given the whole
transcript up front for context, then fed only its own lines, one at a time, in order. Two
reasons for a session per speaker rather than a call per line: the voice stays consistent,
and the model knows what it is reacting to, which is most of what makes a mid-sentence sob
land.

The bracketed tags are performance directions, never words. Every line is checked after the
fact against what the model actually said — a conversational model handed a script will
sometimes paraphrase it, or read the direction aloud, and both have to be caught rather than
assumed away.

Usage:
    python soda_scatter/make_audio_realtime.py
    python soda_scatter/make_audio_realtime.py --voice-a coral --voice-b ash
    python soda_scatter/make_audio_realtime.py --overwrite
"""

from __future__ import annotations

import argparse
import base64
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

# low-level realtime helpers and the ffmpeg splicer
from eval_realtime import (  # noqa: E402
    PCM_RATE, event_error_message, pcm16_to_mp3, recv_event, wait_for,
    AUDIO_DELTA, AUDIO_TRANSCRIPT_DELTA, AUDIO_TRANSCRIPT_DONE,
)
from make_audio import build, duration_of, timestamp  # noqa: E402

DEFAULT_IN = HERE / "out" / "items.json"
OUT_DIR = HERE / "out"

MODEL = "gpt-realtime-2.1"
SESSION_TIMEOUT = 600.0
MAX_OUTPUT_TOKENS = 800
TURN_GAP = 0.36

TAG_RE = re.compile(r"\[([^\[\]]+)\]")

VOICE_ACTOR_INSTRUCTIONS = (
    "You are a voice actor recording lines for a radio drama. You will be given the script "
    "for context, then a series of directions, one at a time.\n\n"
    "Each direction tells you what sound to make and exactly what words to say. Follow it "
    "precisely:\n"
    "- Make the sound for real, out loud, and clearly audible. A sigh must be a real "
    "breathy sigh, a sob a real catch of the breath, a gasp a real sharp intake, a yawn a "
    "real wide yawn, laughter real laughter.\n"
    "- Say the quoted words exactly as written, with nothing added, removed, or reworded.\n"
    "- Never say the name of the sound, and never describe the sound in words.\n"
    "- Act it in character, given what has just happened in the script.\n\n"
    "Produce only the sound and the quoted words. Say nothing else."
)

# Bracketed tags do not work with a conversational model: it either ignores them or reads
# them. What works is a plain-language direction naming the sound, demanding audibility, and
# quoting the exact words — with an explicit ban on saying the sound's name.
SOUND_WORD = {"laughter": "laughter", "sigh": "sigh", "sob": "sob",
              "yawn": "yawn", "gasp": "gasp"}

# intensity modifiers are dropped: a measured pass found "small gasp of delight" and
# "stifled yawn" were inaudible, while the emotional qualifier is what carries meaning
INTENSITY_RE = re.compile(
    r"(?i)\b(small|stifled|quiet|slight|faint|soft|brief|subtle|tiny|little|half)\b")


def descriptor(audio_tag: str, vocalization: str) -> str:
    """Turn "[small gasp of delight]" into "gasp of delight"."""
    inner = audio_tag.strip().strip("[]")
    inner = " ".join(INTENSITY_RE.sub(" ", inner).split())
    if SOUND_WORD[vocalization] not in inner.lower():
        inner = f"{inner} {SOUND_WORD[vocalization]}".strip()
    return inner or SOUND_WORD[vocalization]


def build_directive(text: str, audio_tag: str | None, vocalization: str | None) -> str:
    """One plain-language direction for a line, positioning the sound where the tag was."""
    if not audio_tag or not vocalization:
        return f'Say exactly: "{text.strip()}"  Say nothing else.'

    before, _, after = text.partition(audio_tag)
    before, after = before.strip(" —-–"), after.strip(" —-–")
    desc = descriptor(audio_tag, vocalization)
    word = SOUND_WORD[vocalization]

    if not before:
        core = f'Begin with one brief, clearly audible {desc}, then say: "{after}"'
    elif not after:
        core = f'Say: "{before}"  Then end with one brief, clearly audible {desc}.'
    else:
        core = (f'Say: "{before}"  Then make one brief, clearly audible {desc}. '
                f'Then continue: "{after}"')
    return (f'{core}  Do not say the word "{word}" and do not describe the {word} '
            f'verbally. Say nothing else.')


def context_message(record: dict, speaker: str) -> str:
    lines = [
        "Here is the full script, for context only. Do not read it back.",
        "",
    ]
    for turn in record["turns"]:
        clean = " ".join(TAG_RE.sub(" ", turn["text"]).split())
        lines.append(f"{turn['turn']}. {turn['speaker']}: {clean}")
    lines += [
        "",
        f"You are playing {speaker}. I will now give you your lines one at a time, in order.",
        "Read only the line I give you, performed as directed. Reply with nothing else.",
    ]
    return "\n".join(lines)


def wait_for_take(conn, deadline: float) -> tuple[str, bytes]:
    texts: list[str] = []
    audio = bytearray()
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for response.done")
        event = recv_event(conn, remaining)
        etype = getattr(event, "type", None)
        if etype == "error":
            raise RuntimeError(event_error_message(event))
        if etype in AUDIO_DELTA:
            chunk = getattr(event, "delta", None)
            if chunk:
                audio.extend(base64.b64decode(chunk))
        elif etype in AUDIO_TRANSCRIPT_DELTA:
            texts.append(getattr(event, "delta", "") or "")
        elif etype in AUDIO_TRANSCRIPT_DONE:
            final = getattr(event, "transcript", None)
            if final:
                texts = [final]
        elif etype == "response.done":
            return "".join(texts).strip(), bytes(audio)


def record_speaker(
    client: OpenAI, record: dict, speaker: str, voice: str, model: str,
    line_dir: Path, overwrite: bool,
) -> dict[int, dict]:
    """One session: context first, then this speaker's directions in order."""
    turns = [t for t in record["turns"] if t["speaker"] == speaker]
    voc_by_turn = {v["turn"]: v for v in record["vocalizations"]}
    deadline = time.time() + SESSION_TIMEOUT
    takes: dict[int, dict] = {}

    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": VOICE_ACTOR_INSTRUCTIONS,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": PCM_RATE},
                              "turn_detection": None},
                    "output": {"format": {"type": "audio/pcm", "rate": PCM_RATE},
                               "voice": voice},
                },
            }
        )
        wait_for(conn, deadline, "session.updated")

        # context goes in as a conversation item without asking for a response
        conn.conversation.item.create(item={
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": context_message(record, speaker)}],
        })

        for turn in turns:
            dest = line_dir / f"{turn['turn']:02d}_{speaker.lower().replace(' ', '_')}.mp3"
            meta_path = dest.with_suffix(".json")
            if dest.exists() and meta_path.exists() and not overwrite:
                takes[turn["turn"]] = json.loads(meta_path.read_text(encoding="utf-8"))
                takes[turn["turn"]]["path"] = dest
                print(f"  [{turn['turn']:02d}] {speaker:8} cached", flush=True)
                continue

            voc = voc_by_turn.get(turn["turn"])
            directive = build_directive(
                turn["text"],
                voc["audio_tag"] if voc else None,
                voc["vocalization"] if voc else None,
            )
            conn.conversation.item.create(item={
                "type": "message", "role": "user",
                "content": [{"type": "input_text",
                             "text": f"Direction for line {turn['turn']}:\n{directive}"}],
            })
            conn.response.create(response={
                "output_modalities": ["audio"], "max_output_tokens": MAX_OUTPUT_TOKENS,
            })
            spoken_text, spoken_audio = wait_for_take(conn, deadline)
            if not spoken_audio:
                raise RuntimeError(f"no audio returned for turn {turn['turn']}")
            pcm16_to_mp3(spoken_audio, dest)
            meta = {"turn": turn["turn"], "speaker": speaker, "intended": turn["text"],
                    "directive": directive, "spoken_transcript": spoken_text,
                    "seconds": round(duration_of(dest), 3)}
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
            meta["path"] = dest
            takes[turn["turn"]] = meta
            print(f"  [{turn['turn']:02d}] {speaker:8} {meta['seconds']:5.2f}s  "
                  f"{spoken_text[:58]}", flush=True)
            time.sleep(0.2)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return takes


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", TAG_RE.sub(" ", text or "").lower())


def check_take(meta: dict) -> list[str]:
    """Did it say the line, and only the line?

    A sound word inside square brackets in the returned transcript means the model PERFORMED
    the sound and the transcriber annotated it — that is success, not leakage. Only an
    unbracketed sound word is evidence the direction was read aloud. An earlier version of
    this check flagged the bracketed form and produced three false alarms on a take that a
    separate listening pass confirmed was clean.
    """
    problems: list[str] = []
    intended, spoken = meta["intended"], meta["spoken_transcript"]
    outside_brackets = TAG_RE.sub(" ", spoken)

    for tag in TAG_RE.findall(intended):
        head = tag.split()[-1]  # "sigh" from "resigned sigh"
        if re.search(rf"\b{re.escape(head)}\w*\b", outside_brackets, re.I):
            problems.append(f"said {head!r} aloud instead of making the sound")

    want, got = words(intended), words(spoken)
    if not want:
        return problems
    kept = sum(1 for w in set(want) if w in set(got)) / len(set(want))
    if kept < 0.75:
        problems.append(f"only {kept:.0%} of the scripted words survived — likely paraphrased")
    extra = [w for w in set(got) - set(want) if len(w) > 3]
    if len(extra) > 4:
        problems.append(f"added words not in the script: {sorted(extra)[:6]}")
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--voice-a", default="marin", help="voice for the odd-turn speaker")
    parser.add_argument("--voice-b", default="cedar", help="voice for the even-turn speaker")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    args.infile = args.infile.resolve()
    return args


def main() -> None:
    args = parse_args()
    data = json.loads(args.infile.read_text(encoding="utf-8"))
    record = data["results"][args.index]
    seed, item_id = record["seed"], record["item_id"]
    speaker_a, speaker_b = seed["speaker_a"], seed["speaker_b"]

    line_dir = OUT_DIR / "lines_realtime" / item_id
    final = OUT_DIR / "audio" / f"{item_id}_realtime.mp3"
    transcript = OUT_DIR / f"{item_id}_realtime_transcript.md"

    voc_by_turn = {v["turn"]: v for v in record["vocalizations"]}
    print(f"{item_id} · {args.model} · one session per speaker", flush=True)
    print(f"  {speaker_a} -> {args.voice_a}", flush=True)
    print(f"  {speaker_b} -> {args.voice_b}", flush=True)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    takes: dict[int, dict] = {}
    for speaker, voice in ((speaker_a, args.voice_a), (speaker_b, args.voice_b)):
        print(f"\nsession: {speaker} ({voice})", flush=True)
        takes.update(record_speaker(client, record, speaker, voice, args.model,
                                    line_dir, args.overwrite))

    missing = [t["turn"] for t in record["turns"] if t["turn"] not in takes]
    if missing:
        raise SystemExit(f"no take for turn(s) {missing}")

    print("\nfidelity check", flush=True)
    issues: dict[int, list[str]] = {}
    for turn in record["turns"]:
        problems = check_take(takes[turn["turn"]])
        if problems:
            issues[turn["turn"]] = problems
            print(f"  t{turn['turn']:>2} {problems}", flush=True)
    if not issues:
        print("  all lines clean: nothing paraphrased, no direction read aloud", flush=True)

    pieces: list[tuple[str, object]] = []
    rows: list[dict] = []
    for turn in record["turns"]:
        meta = takes[turn["turn"]]
        if pieces:
            pieces.append(("silence", TURN_GAP))
            rows.append({"kind": "gap", "seconds": TURN_GAP})
        pieces.append(("file", meta["path"]))
        voc = voc_by_turn.get(turn["turn"])
        rows.append({
            "kind": "line", "turn": turn["turn"], "speaker": turn["speaker"],
            "text": turn["text"], "spoken_transcript": meta["spoken_transcript"],
            "seconds": meta["seconds"],
            "vocalization": voc["vocalization"] if voc else None,
            "audio_tag": voc["audio_tag"] if voc else None,
            "issues": issues.get(turn["turn"], []),
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
        f"# {item_id} — voiced by {args.model}",
        "",
        f"Runtime **{timestamp(total)}** · {speaker_a} ({args.voice_a}) and "
        f"{speaker_b} ({args.voice_b}) recorded in separate sessions, each reading only "
        "its own lines.",
        "",
        f"**Scenario (SODA #{seed.get('original_index')})** — {seed['narrative']}",
        "",
        "Vocalizations were performed, not synthesized from a text tag. The `spoken` column "
        "is what the model actually said, for fidelity.",
        "",
        "| time | turn | speaker | scripted | spoken |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["kind"] != "line":
            continue
        lines.append(
            f"| {timestamp(row['starts_at_seconds'])} | {row['turn']} | {row['speaker']} | "
            f"{row['text'].replace('|', '-')} | {row['spoken_transcript'].replace('|', '-')} |"
        )
    lines += ["", "## Vocalizations", "",
              "| turn starts | turn | speaker | sound | tag | target |",
              "| --- | --- | --- | --- | --- | --- |"]
    for mark in marks:
        lines.append(
            f"| {mark['turn_starts_at']} | {mark['turn']} | {mark['speaker']} | "
            f"{mark['vocalization']} | `{mark['audio_tag']}` | {mark['target']} |"
        )
    if issues:
        lines += ["", "## Fidelity issues", ""]
        for turn, problems in sorted(issues.items()):
            lines.append(f"- turn {turn}: {'; '.join(problems)}")
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / f"{item_id}_realtime_timing.json").write_text(
        json.dumps({
            "item_id": item_id, "voiced_by": args.model,
            "voices": {speaker_a: args.voice_a, speaker_b: args.voice_b},
            "audio": str(final.relative_to(REPO)),
            "total_seconds": round(total, 3), "turn_gap": TURN_GAP,
            "fidelity_issues": {str(k): v for k, v in issues.items()},
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

"""Free-form continuation: hand the model ONE dialogue and let it answer as Speaker B.

The MCQ version of this benchmark (../eval_realtime.py) gives the model both gold answers
and asks it to pick. That lets it work backward from the options. Here it gets no options
at all: it hears turn 1 plus B's non-speech reaction, and has to produce B's next line
itself, in role, out loud.

One trial per audio file, so both versions of a pair are run independently — 15 pairs x 2
vocalizations = 30 trials. The pair's two versions share an identical turn 1 and differ
only in B's sound, so if a model's two replies come out pragmatically identical, the sound
did nothing for it. That comparison is the point of running both.

The model is never told the six vocalization categories, never told which sound played,
and never shown either gold answer. Scoring happens afterwards in judge.py.

Optionally `--control` adds a third condition per pair: turn 1 alone, no vocalization at
all. It bounds how much of a reply is actually driven by the sound rather than by the words.

Usage:
    python predicting_response_upgraded/freeform/run.py --limit 2
    python predicting_response_upgraded/freeform/run.py
    python predicting_response_upgraded/freeform/run.py --control --resume
    python predicting_response_upgraded/freeform/run.py --modality text
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
REPO = PARENT.parent
load_dotenv(REPO / ".env")

DEFAULT_MANIFEST = PARENT / "out" / "audio_manifest.json"
DEFAULT_OUT = HERE / "out" / "responses.json"
DEFAULT_REPLY_DIR = HERE / "out" / "audio_reply"

MODEL = "gpt-realtime-2.1"
VOICE = "marin"
PCM_RATE = 24000
ITEM_TIMEOUT = 120.0
MAX_OUTPUT_TOKENS = 300
MAX_ATTEMPTS = 3

# In role as B, with no options and no mention of the six categories. "Non-speech sound"
# is the most the model is told — naming the inventory here would prime the answer.
INSTRUCTIONS = (
    "You are Speaker B in a short conversation between two people. You will hear the "
    "conversation so far: Speaker A says one line, and then you — Speaker B — react with "
    "a non-speech sound, using no words. Continue the conversation in character as B: say "
    "the next thing you would naturally say, right after that reaction of yours. Speak "
    "only B's next line, one or two sentences, the way a person would actually say it. Do "
    "not describe, name, or comment on the sound you made. Do not narrate, do not explain "
    "your reasoning, and do not ask what the sound meant. Just say B's line."
)

CONTROL_INSTRUCTIONS = (
    "You are Speaker B in a short conversation between two people. You will hear Speaker A "
    "say one line. Continue the conversation in character as B: say the next thing you "
    "would naturally say in response. Speak only B's next line, one or two sentences, the "
    "way a person would actually say it. Do not narrate and do not explain your reasoning. "
    "Just say B's line."
)

PROMPT_TEXT = "Say B's next line now."


def mp3_to_pcm16_24k(path: Path) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
         "-ac", "1", "-ar", str(PCM_RATE), "-f", "s16le", "pipe:1"],
        capture_output=True, check=True,
    )
    if not result.stdout:
        raise RuntimeError(f"ffmpeg produced no PCM for {path}")
    return result.stdout


def pcm16_to_mp3(pcm: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "s16le", "-ar", str(PCM_RATE), "-ac", "1", "-i", "pipe:0",
         "-c:a", "libmp3lame", "-q:a", "3", str(dest)],
        input=pcm, capture_output=True, check=True,
    )


def event_error_message(event) -> str:
    err = getattr(event, "error", None)
    if err is None:
        return str(event)
    message = getattr(err, "message", None) or str(err)
    code = getattr(err, "code", None)
    return f"{code}: {message}" if code else str(message)


def recv_event(conn, timeout: float):
    raw = conn._connection.recv(timeout=timeout, decode=False)
    return conn.parse_event(raw)


def wait_for(conn, deadline: float, etype_wanted: str) -> None:
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timed out waiting for {etype_wanted}")
        event = recv_event(conn, remaining)
        etype = getattr(event, "type", None)
        if etype == "error":
            raise RuntimeError(event_error_message(event))
        if etype == etype_wanted:
            return


# event names differ across realtime API revisions, so accept either spelling
AUDIO_DELTA = {"response.output_audio.delta", "response.audio.delta"}
AUDIO_TRANSCRIPT_DELTA = {
    "response.output_audio_transcript.delta", "response.audio_transcript.delta",
}
AUDIO_TRANSCRIPT_DONE = {
    "response.output_audio_transcript.done", "response.audio_transcript.done",
}
TEXT_DELTA = {"response.output_text.delta", "response.text.delta"}
TEXT_DONE = {"response.output_text.done", "response.text.done"}


def wait_for_response(conn, deadline: float) -> tuple[object, str, bytes]:
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
        elif etype in AUDIO_TRANSCRIPT_DELTA or etype in TEXT_DELTA:
            texts.append(getattr(event, "delta", "") or "")
        elif etype in AUDIO_TRANSCRIPT_DONE:
            final = getattr(event, "transcript", None)
            if final:
                texts = [final]
        elif etype in TEXT_DONE:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        elif etype == "response.done":
            return event, "".join(texts).strip(), bytes(audio)


def extract_response_text(response) -> str:
    parts = []
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            for attr in ("transcript", "text"):
                value = getattr(content, attr, None)
                if value:
                    parts.append(value)
                    break
    return "".join(parts).strip()


def ask_once(
    client: OpenAI, pcm: bytes | None, instructions: str, model: str, voice: str, modality: str
) -> dict:
    """One fresh session per trial — no cross-contamination between items."""
    deadline = time.time() + ITEM_TIMEOUT
    audio_config: dict = {
        "input": {"format": {"type": "audio/pcm", "rate": PCM_RATE}, "turn_detection": None}
    }
    if modality == "audio":
        audio_config["output"] = {"format": {"type": "audio/pcm", "rate": PCM_RATE}, "voice": voice}

    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": instructions,
                "output_modalities": ["audio"] if modality == "audio" else ["text"],
                "audio": audio_config,
            }
        )
        wait_for(conn, deadline, "session.updated")

        content: list[dict] = []
        if pcm is not None:
            content.append(
                {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")}
            )
        content.append({"type": "input_text", "text": PROMPT_TEXT})
        conn.conversation.item.create(item={"type": "message", "role": "user", "content": content})
        conn.response.create(
            response={
                "output_modalities": ["audio"] if modality == "audio" else ["text"],
                "max_output_tokens": MAX_OUTPUT_TOKENS,
            }
        )
        done, streamed, audio = wait_for_response(conn, deadline)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    response = done.response
    text = extract_response_text(response) or streamed
    usage = getattr(response, "usage", None)
    return {
        "text": text,
        "audio": audio,
        "status": getattr(response, "status", None),
        "usage": usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else None,
    }


def with_retries(fn, label: str):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            wait = 2 ** attempt
            print(f"    {label} retry in {wait}s: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def build_trials(manifest: dict, control: bool) -> list[dict]:
    trials: list[dict] = []
    for clip in manifest["clips"]:
        trials.append(
            {
                "trial_id": f"{clip['pair_id']}_{clip['version']}",
                "pair_id": clip["pair_id"],
                "version": clip["version"],
                "condition": "vocalization",
                "contrast": clip.get("contrast"),
                "turn1": clip["shared_turn1"],
                "vocalization": clip["vocalization"].strip("[]"),
                "gold_interpretation": clip["interpretation"],
                "gold_response": clip["response"],
                "audio": clip["prompt"],
            }
        )
    if control:
        # Turn 1 with no reaction spliced on, once per pair — the floor for "how much of
        # the reply is the words rather than the sound". This must still send turn 1's
        # audio; sending nothing just makes the model say it did not hear anything.
        seen: set[str] = set()
        for clip in manifest["clips"]:
            if clip["pair_id"] in seen:
                continue
            seen.add(clip["pair_id"])
            turn1_audio = (
                PARENT / "out" / "audio_turns" / clip["pair_id"] / "turn1.mp3"
            )
            if not turn1_audio.exists():
                print(f"skipping control for {clip['pair_id']}: {turn1_audio} missing", flush=True)
                continue
            trials.append(
                {
                    "trial_id": f"{clip['pair_id']}_control",
                    "pair_id": clip["pair_id"],
                    "version": "control",
                    "condition": "turn1_only",
                    "contrast": clip.get("contrast"),
                    "turn1": clip["shared_turn1"],
                    "vocalization": None,
                    "gold_interpretation": None,
                    "gold_response": None,
                    "audio": str(turn1_audio.relative_to(REPO)),
                }
            )
    return trials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reply-dir", type=Path, default=DEFAULT_REPLY_DIR)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--modality", default="audio", choices=["audio", "text"])
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--control", action="store_true",
        help="also run turn 1 with no vocalization, once per pair",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--no-shuffle", action="store_true",
        help="run in manifest order, which puts a pair's two versions back to back; the "
             "default shuffles so nothing order-dependent lands on the v1/v2 contrast",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.manifest = args.manifest.resolve()
    args.out = args.out.resolve()
    args.reply_dir = args.reply_dir.resolve()
    return args


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    trials = build_trials(manifest, args.control)

    # Manifest order puts a pair's two versions adjacent, so anything order-dependent
    # (cache warming, server-side state, drift over the run) would land squarely on the
    # v1/v2 contrast this eval measures. Shuffling separates them.
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(trials)

    if args.limit:
        trials = trials[: args.limit]

    done: dict[str, dict] = {}
    if args.resume and args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
        for row in previous.get("rows", []):
            if row.get("reply_text") and not row.get("error"):
                done[row["trial_id"]] = row
        print(f"resuming, {len(done)} trial(s) already collected", flush=True)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    print(
        f"{len(trials)} trial(s) · model {args.model} · {args.modality} out"
        + (f" · voice {args.voice}" if args.modality == "audio" else ""),
        flush=True,
    )

    rows: list[dict] = []
    for index, trial in enumerate(trials, start=1):
        if trial["trial_id"] in done:
            rows.append(done[trial["trial_id"]])
            continue
        row = dict(trial)
        try:
            pcm = mp3_to_pcm16_24k(REPO / trial["audio"]) if trial["audio"] else None
            instructions = INSTRUCTIONS if trial["audio"] else CONTROL_INSTRUCTIONS
            result = with_retries(
                lambda: ask_once(
                    client, pcm, instructions, args.model, args.voice, args.modality
                ),
                trial["trial_id"],
            )
            row["reply_text"] = result["text"]
            row["status"] = result["status"]
            row["usage"] = result["usage"]
            if result["audio"]:
                reply_path = args.reply_dir / f"{trial['trial_id']}.mp3"
                pcm16_to_mp3(result["audio"], reply_path)
                row["reply_audio"] = str(reply_path.relative_to(REPO))
            heard = trial["vocalization"] or "no reaction"
            print(
                f"[{index}/{len(trials)}] {trial['trial_id']:26} ({heard})\n"
                f"    B: {result['text']}",
                flush=True,
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(trials)}] {trial['trial_id']:26} failed: {exc}", flush=True)
        rows.append(row)

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "model": args.model,
                    "voice": args.voice if args.modality == "audio" else None,
                    "modality": args.modality,
                    "manifest": str(args.manifest.relative_to(REPO)),
                    "instructions": INSTRUCTIONS,
                    "control_instructions": CONTROL_INSTRUCTIONS if args.control else None,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "n_trials": len(trials),
                    "n_collected": sum(1 for r in rows if r.get("reply_text")),
                    "n_failed": sum(1 for r in rows if r.get("error")),
                    "rows": rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    collected = sum(1 for r in rows if r.get("reply_text"))
    failed = sum(1 for r in rows if r.get("error"))
    print(f"\ncollected {collected}/{len(trials)} free-form replies", flush=True)
    if failed:
        print(f"{failed} trial(s) failed", flush=True)
    print(f"wrote {args.out}", flush=True)
    print("next: python predicting_response_upgraded/freeform/judge.py", flush=True)


if __name__ == "__main__":
    main()

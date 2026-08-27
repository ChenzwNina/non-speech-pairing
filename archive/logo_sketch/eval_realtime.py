"""Play the sketch to gpt-realtime-2.1 and ask it what happened.

Three questions per session, escalating, all in one session so the audio stays in context:

    Q1  open — "describe what happens." Nothing is primed. If the model only reports a
        series of logo edits and misses the escalation, it has heard the words and not
        the scene.
    Q2  the laugh, without naming it. Asking "what does the laughter mean" would hand over
        the identification, so the question says only that a non-speech sound occurs.
        The reading that matters is defeat or resignation, not amusement — nothing about
        the sound itself carries that; only the preceding eight rounds of failure do.
    Q3  the sarcasm. "This is fine" and "Perfect" are the opposite of what they say. A model
        that takes them at face value has missed the entire point of the sketch.

Q1 comes before Q2 and Q3 deliberately: once you ask about a sound near the end, you have
told the model there is something notable there.

Runs several independent sessions so a single lucky or unlucky read is visible as such.

Usage:
    python logo_sketch/eval_realtime.py
    python logo_sketch/eval_realtime.py --runs 3
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DEFAULT_AUDIO = HERE / "out" / "logo_sketch.mp3"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
SESSION_TIMEOUT = 300.0
MAX_OUTPUT_TOKENS = 900

INSTRUCTIONS = (
    "You are listening to a short audio recording of a conversation between two people. "
    "Answer the questions you are asked about it. Be specific and concrete, and base what "
    "you say on what you actually hear in the recording."
)

QUESTIONS = [
    (
        "describe",
        "Describe what happens in this conversation.",
    ),
    (
        "the_sound",
        "Near the end of the recording, one of the speakers makes a non-speech sound "
        "before saying anything else. What is that sound, and what does it communicate at "
        "that point in the conversation?",
    ),
    (
        "sincerity",
        "At the very end, that same speaker says \"This is fine\" and \"Perfect.\" Does he "
        "mean those literally? Explain what he actually means.",
    ),
]


def mp3_to_pcm16_24k(path: Path) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
         "-ac", "1", "-ar", str(PCM_RATE), "-f", "s16le", "pipe:1"],
        capture_output=True, check=True,
    )
    if not result.stdout:
        raise RuntimeError(f"ffmpeg produced no PCM for {path}")
    return result.stdout


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


TEXT_DELTA = {"response.output_text.delta", "response.text.delta"}
TEXT_DONE = {"response.output_text.done", "response.text.done"}

# event names differ across realtime API revisions, so accept either spelling
AUDIO_DELTA = {"response.output_audio.delta", "response.audio.delta"}
AUDIO_TRANSCRIPT_DELTA = {
    "response.output_audio_transcript.delta", "response.audio_transcript.delta",
}
AUDIO_TRANSCRIPT_DONE = {
    "response.output_audio_transcript.done", "response.audio_transcript.done",
}


def pcm16_to_mp3(pcm: bytes, dest: Path) -> None:
    """Save raw pcm16 from the realtime stream as an mp3."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "s16le", "-ar", str(PCM_RATE), "-ac", "1", "-i", "pipe:0",
         "-c:a", "libmp3lame", "-q:a", "3", str(dest)],
        input=pcm, capture_output=True, check=True,
    )


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
        elif etype in TEXT_DELTA or etype in AUDIO_TRANSCRIPT_DELTA:
            texts.append(getattr(event, "delta", "") or "")
        elif etype in TEXT_DONE:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        elif etype in AUDIO_TRANSCRIPT_DONE:
            final = getattr(event, "transcript", None)
            if final:
                texts = [final]
        elif etype == "response.done":
            return event, "".join(texts).strip(), bytes(audio)


def extract_response_text(response) -> str:
    parts = []
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            for attr in ("text", "transcript"):
                value = getattr(content, attr, None)
                if value:
                    parts.append(value)
                    break
    return "".join(parts).strip()


def run_session(
    client: OpenAI, pcm: bytes, model: str,
    capture_audio: bool = False, voice: str = "marin",
) -> list[dict]:
    """Ask the module-level QUESTIONS in one session.

    With capture_audio the model speaks its answers; each answer then carries the raw pcm16
    under "audio" and its transcript under "answer". Note that a spoken answer is not
    necessarily worded the same as a written one, so audio and text runs should not be
    pooled with each other.
    """
    deadline = time.time() + SESSION_TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    answers: list[dict] = []
    audio_config: dict = {
        "input": {"format": {"type": "audio/pcm", "rate": PCM_RATE}, "turn_detection": None}
    }
    if capture_audio:
        audio_config["output"] = {"format": {"type": "audio/pcm", "rate": PCM_RATE},
                                  "voice": voice}
    modalities = ["audio"] if capture_audio else ["text"]
    try:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": INSTRUCTIONS,
                "output_modalities": modalities,
                "audio": audio_config,
            }
        )
        wait_for(conn, deadline, "session.updated")

        for index, (key, question) in enumerate(QUESTIONS):
            content: list[dict] = []
            if index == 0:
                content.append(
                    {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")}
                )
            content.append({"type": "input_text", "text": question})
            conn.conversation.item.create(
                item={"type": "message", "role": "user", "content": content}
            )
            conn.response.create(
                response={"output_modalities": modalities,
                          "max_output_tokens": MAX_OUTPUT_TOKENS}
            )
            done, streamed, spoken = wait_for_response(conn, deadline)
            text = extract_response_text(done.response) or streamed
            entry = {"key": key, "question": question, "answer": text}
            if capture_audio:
                entry["audio"] = spoken
            answers.append(entry)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return answers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    args.audio = args.audio.resolve()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    if not args.audio.exists():
        raise SystemExit(f"missing audio: {args.audio}")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    pcm = mp3_to_pcm16_24k(args.audio)
    seconds = len(pcm) / (PCM_RATE * 2)
    print(f"{args.audio.name} · {seconds:.1f}s · {args.model} · {args.runs} run(s)", flush=True)

    runs: list[dict] = []
    for run_index in range(1, args.runs + 1):
        print(f"\n{'=' * 78}\nRUN {run_index}\n{'=' * 78}", flush=True)
        try:
            answers = run_session(client, pcm, args.model)
        except Exception as exc:
            print(f"  failed: {exc}", flush=True)
            runs.append({"run": run_index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for item in answers:
            print(f"\n[{item['key']}]\n{item['answer']}", flush=True)
        runs.append({"run": run_index, "answers": answers})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "model": args.model,
            "audio": str(args.audio.relative_to(REPO)),
            "audio_seconds": round(seconds, 2),
            "instructions": INSTRUCTIONS,
            "questions": [{"key": k, "question": q} for k, q in QUESTIONS],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "runs": runs,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}", flush=True)


if __name__ == "__main__":
    main()

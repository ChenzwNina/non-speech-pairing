#!/usr/bin/env python3
"""Play one audio file to gpt-realtime and ask free-text questions about it.

A minimal probe, not an eval: the clip is pushed once per session and every
question is answered from that single listen. Answers are free text, so this is
for sanity-checking whether a stimulus survives the wire at all.

    python probe_realtime.py assistant_proposal/out/audio/sigh_voice_delex_0.90.wav
    python probe_realtime.py CLIP.wav --runs 5 --model gpt-realtime-2.1
    python probe_realtime.py CLIP.wav -q "Is there speech in this?" -q "How long is it?"
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
MAX_OUTPUT_TOKENS = 4000
TIMEOUT = 120.0

SESSION_INSTRUCTIONS = (
    "You are listening to a short audio clip. Answer each question directly and "
    "concretely about what you actually hear. If you cannot hear anything, say so "
    "plainly. Do not speculate about context you were not given. Two sentences max."
)

DEFAULT_QUESTIONS = [
    "Is the audio audible? Answer yes or no first, then describe in one sentence what you hear.",
    "What emotion is in the audio? Name it, and say how confident you are.",
]


def load_pcm16_24k(path: Path) -> bytes:
    """Return raw PCM16 mono 24k. Reads the wav directly when it already matches."""
    try:
        with wave.open(str(path), "rb") as w:
            if (w.getnchannels(), w.getframerate(), w.getsampwidth()) == (1, PCM_RATE, 2):
                return w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        pass
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
         "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(PCM_RATE), "-"],
        capture_output=True, check=True,
    )
    return out.stdout


def extract_response_text(response) -> str:
    parts = []
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            text = getattr(content, "text", None) or getattr(content, "transcript", None)
            if text:
                parts.append(text)
    return "".join(parts).strip()


def event_error_message(event) -> str:
    err = getattr(event, "error", None)
    if err is None:
        return str(event)
    message = getattr(err, "message", None) or str(err)
    code = getattr(err, "code", None)
    return f"{code}: {message}" if code else str(message)


def recv_event(conn, timeout: float):
    return conn.parse_event(conn._connection.recv(timeout=timeout, decode=False))


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


def wait_for_response(conn, deadline: float):
    texts: list[str] = []
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for response.done")
        event = recv_event(conn, remaining)
        etype = getattr(event, "type", None)
        if etype == "error":
            raise RuntimeError(event_error_message(event))
        if etype in {"response.output_text.delta", "response.text.delta"}:
            texts.append(getattr(event, "delta", "") or "")
        if etype in {"response.output_text.done", "response.text.done"}:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        if etype == "response.done":
            return event, "".join(texts).strip()


def open_session(client: OpenAI, model: str, deadline: float):
    conn = client.realtime.connect(model=model).enter()
    conn.session.update(session={
        "type": "realtime",
        "instructions": SESSION_INSTRUCTIONS,
        "output_modalities": ["text"],
        "audio": {"input": {"format": {"type": "audio/pcm", "rate": PCM_RATE},
                            "turn_detection": None}},
    })
    wait_for(conn, deadline, "session.updated")
    return conn


def ask(conn, deadline: float, content: list[dict]) -> str:
    conn.conversation.item.create(
        item={"type": "message", "role": "user", "content": content})
    # Without this the server sometimes answers before the audio item is
    # registered and the model reports hearing nothing at all. Note the event is
    # conversation.item.done on gpt-realtime-2.1 — *.created is never emitted.
    wait_for(conn, deadline, "conversation.item.done")
    conn.response.create(
        response={"output_modalities": ["text"], "max_output_tokens": MAX_OUTPUT_TOKENS})
    done, streamed = wait_for_response(conn, deadline)
    return extract_response_text(done.response) or streamed


def run_once(client: OpenAI, pcm: bytes, questions: list[str], model: str) -> list[dict]:
    deadline = time.time() + TIMEOUT
    conn = open_session(client, model, deadline)
    try:
        audio = {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")}
        answers = []
        for i, q in enumerate(questions):
            # clip rides along with the first question only; later questions
            # answer from the same listen
            content = [audio, {"type": "input_text", "text": q}] if i == 0 \
                else [{"type": "input_text", "text": q}]
            answers.append({"question": q, "answer": ask(conn, deadline, content)})
        return answers
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("-q", "--question", action="append", dest="questions")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    questions = args.questions or DEFAULT_QUESTIONS
    pcm = load_pcm16_24k(args.clip)
    dur = len(pcm) / 2 / PCM_RATE
    print(f"{args.clip.name}: {dur:.2f}s, {len(pcm)} bytes PCM16@{PCM_RATE} mono")
    print(f"model {args.model}, {args.runs} run(s), {len(questions)} question(s)\n")

    client = OpenAI()
    runs = []
    for r in range(args.runs):
        try:
            answers = run_once(client, pcm, questions, args.model)
        except Exception as exc:
            print(f"run {r + 1}: FAILED {type(exc).__name__}: {exc}\n")
            runs.append({"run": r + 1, "error": f"{type(exc).__name__}: {exc}"})
            continue
        runs.append({"run": r + 1, "answers": answers})
        print(f"--- run {r + 1} ---")
        for a in answers:
            print(f"Q: {a['question']}")
            print(f"A: {a['answer'] or '(empty)'}\n")

    if args.out:
        args.out.write_text(json.dumps(
            {"clip": str(args.clip), "duration_s": round(dur, 3), "model": args.model,
             "questions": questions, "runs": runs}, indent=2), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

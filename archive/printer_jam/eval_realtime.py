"""Ask gpt-realtime-2.1 why Speaker B laughs in the printer-jam clip.

Usage:
    python printer_jam/eval_realtime.py
    python printer_jam/eval_realtime.py --audio printer_jam/out/dialogue_through_haha.mp3
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

DEFAULT_AUDIO = HERE / "out" / "dialogue.mp3"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
ITEM_TIMEOUT = 90.0

SESSION_INSTRUCTIONS = (
    "You are taking a listening test. You will hear a short conversation "
    "among speakers A, B, and C. Speaker B laughs. Explain why Speaker B "
    "laughs. Answer in one or two sentences."
)

USER_TEXT = (
    "You heard a short conversation among speakers A, B, and C. "
    "Why does Speaker B laugh? Answer in one or two sentences."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def mp3_to_pcm16_24k(path: Path) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(PCM_RATE),
            "-f",
            "s16le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    if not result.stdout:
        raise RuntimeError(f"ffmpeg produced no PCM for {path}")
    return result.stdout


def extract_response_text(response) -> str:
    parts = []
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
            else:
                transcript = getattr(content, "transcript", None)
                if transcript:
                    parts.append(transcript)
    return "".join(parts).strip()


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


def wait_for_response(conn, deadline: float) -> tuple[object, str]:
    texts: list[str] = []
    seen: list[str] = []
    done = None
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timed out after events {seen}")
        event = recv_event(conn, remaining)
        etype = getattr(event, "type", None)
        seen.append(str(etype))
        if etype == "error":
            raise RuntimeError(event_error_message(event))
        if etype in {"response.output_text.delta", "response.text.delta"}:
            texts.append(getattr(event, "delta", "") or "")
        if etype in {"response.output_text.done", "response.text.done"}:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        if etype == "response.done":
            done = event
            break
    return done, "".join(texts).strip()


def main() -> None:
    args = parse_args()
    audio = args.audio.resolve()
    out = args.out.resolve()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    if not audio.exists():
        raise SystemExit(f"missing {audio}")

    pcm = mp3_to_pcm16_24k(audio)
    audio_b64 = base64.b64encode(pcm).decode("ascii")
    client = OpenAI(api_key=key)
    print(f"model: {MODEL}  audio: {audio.name}  pcm: {len(pcm)} bytes")

    deadline = time.time() + ITEM_TIMEOUT
    with client.realtime.connect(model=MODEL) as conn:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": SESSION_INSTRUCTIONS,
                "output_modalities": ["text"],
                "max_output_tokens": 512,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": PCM_RATE},
                        "turn_detection": None,
                    }
                },
            }
        )
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for session.updated")
            event = recv_event(conn, remaining)
            etype = getattr(event, "type", None)
            if etype == "error":
                raise RuntimeError(event_error_message(event))
            if etype == "session.updated":
                break

        conn.response.create(
            response={
                "conversation": "none",
                "output_modalities": ["text"],
                "max_output_tokens": 512,
                "instructions": SESSION_INSTRUCTIONS,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_audio", "audio": audio_b64},
                            {"type": "input_text", "text": USER_TEXT},
                        ],
                    }
                ],
            }
        )
        done, streamed = wait_for_response(conn, deadline)

    raw_text = extract_response_text(done.response) or streamed
    print(raw_text or "(empty)")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        audio_rel = str(audio.relative_to(REPO))
    except ValueError:
        audio_rel = str(audio)
    out.write_text(
        json.dumps(
            {
                "model": MODEL,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "audio": audio_rel,
                "question": USER_TEXT,
                "answer": raw_text,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

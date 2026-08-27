"""Ask grok-voice-think-fast-2.0 why Speaker B laughs.

Usage:
    python printer_jam/eval_grok_voice.py
    python printer_jam/eval_grok_voice.py --audio printer_jam/out/dialogue_through_haha.mp3
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
for extra in (
    REPO.parent / "non-speech-vocalization" / ".env",
    REPO.parent / "non-speech-vocalization2" / ".env",
    REPO.parent / "multi-people-voice-agent" / ".env",
):
    if not os.environ.get("XAI_API_KEY") and extra.exists():
        load_dotenv(extra)

DEFAULT_AUDIO = HERE / "out" / "dialogue_through_haha.mp3"
DEFAULT_OUT = HERE / "out" / "eval_grok_voice_think_fast_high.json"

MODEL = "grok-voice-think-fast-2.0"
XAI_BASE_URL = "https://api.x.ai/v1"
PCM_RATE = 24000
ITEM_TIMEOUT = 180.0
APPEND_CHUNK = 24_000  # 0.5s of 16-bit PCM at 24 kHz
SILENCE_SECONDS = 2.0

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


def is_benign_cancel(message: str) -> bool:
    return "no active response" in message.lower()


def recv_event(conn, timeout: float):
    raw = conn._connection.recv(timeout=timeout, decode=False)
    return conn.parse_event(raw)


def event_response_id(event) -> str | None:
    rid = getattr(event, "response_id", None)
    if rid:
        return str(rid)
    response = getattr(event, "response", None)
    if response is None:
        return None
    if isinstance(response, dict):
        value = response.get("id")
        return str(value) if value else None
    value = getattr(response, "id", None)
    return str(value) if value else None


def wait_until(conn, wanted: set[str], deadline: float, seen: list[str]) -> object:
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timed out waiting for {wanted} after events {seen}")
        try:
            event = recv_event(conn, min(remaining, 5.0))
        except TimeoutError:
            continue
        etype = getattr(event, "type", None)
        seen.append(str(etype))
        print("event:", etype)
        if etype == "error":
            message = event_error_message(event)
            if is_benign_cancel(message):
                print("ignore:", message)
                continue
            raise RuntimeError(message)
        if etype in wanted:
            return event


def wait_for_response(
    conn, deadline: float, seen: list[str], response_id: str | None = None
) -> tuple[object, str]:
    texts: list[str] = []
    transcripts: list[str] = []
    done = None
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timed out after events {seen}")
        try:
            event = recv_event(conn, min(remaining, 5.0))
        except TimeoutError:
            continue
        etype = getattr(event, "type", None)
        seen.append(str(etype))
        print("event:", etype)
        if etype == "error":
            message = event_error_message(event)
            if is_benign_cancel(message):
                print("ignore:", message)
                continue
            raise RuntimeError(message)
        rid = event_response_id(event)
        if etype in {"response.output_text.delta", "response.text.delta"}:
            texts.append(getattr(event, "delta", "") or "")
        if etype in {"response.output_text.done", "response.text.done"}:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        if etype in {
            "response.output_audio_transcript.delta",
            "response.audio_transcript.delta",
        }:
            transcripts.append(getattr(event, "delta", "") or "")
        if etype in {
            "response.output_audio_transcript.done",
            "response.audio_transcript.done",
        }:
            final = getattr(event, "transcript", None) or getattr(event, "text", None)
            if final:
                transcripts = [final]
        if etype == "response.done":
            if response_id and rid and rid != response_id:
                print("skip stale response.done", rid)
                continue
            done = event
            break
    streamed = "".join(texts).strip() or "".join(transcripts).strip()
    return done, streamed


def drain_events(
    conn, seen: list[str], asr_transcripts: list[str], timeout: float = 0.0
) -> list[object]:
    events = []
    while True:
        try:
            event = recv_event(conn, timeout)
        except TimeoutError:
            return events
        etype = getattr(event, "type", None)
        seen.append(str(etype))
        print("event:", etype)
        if etype == "error":
            message = event_error_message(event)
            if is_benign_cancel(message):
                print("ignore:", message)
                continue
            raise RuntimeError(message)
        transcript = getattr(event, "transcript", None)
        if transcript and "transcription" in str(etype):
            print("asr:", transcript)
            asr_transcripts.append(transcript)
        events.append(event)
        timeout = 0.0


def append_pcm(
    conn, pcm: bytes, seen: list[str], asr_transcripts: list[str], realtime: bool = True
) -> None:
    started = time.time()
    bytes_per_sec = PCM_RATE * 2
    for i in range(0, len(pcm), APPEND_CHUNK):
        chunk = pcm[i : i + APPEND_CHUNK]
        conn.input_audio_buffer.append(audio=base64.b64encode(chunk).decode("ascii"))
        drain_events(conn, seen, asr_transcripts, timeout=0.0)
        if realtime:
            target = started + (i + len(chunk)) / bytes_per_sec
            delay = target - time.time()
            if delay > 0:
                time.sleep(delay)


def main() -> None:
    args = parse_args()
    audio = args.audio.resolve()
    out = args.out.resolve()
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("XAI_API_KEY is empty; set it in .env")
    if not audio.exists():
        raise SystemExit(f"missing {audio}")

    pcm = mp3_to_pcm16_24k(audio)
    client = OpenAI(api_key=key, base_url=XAI_BASE_URL)
    print(f"model: {MODEL}  audio: {audio.name}  pcm: {len(pcm)} bytes")

    deadline = time.time() + ITEM_TIMEOUT
    seen: list[str] = []
    asr_transcripts: list[str] = []
    with client.realtime.connect(model=MODEL) as conn:
        conn.session.update(
            session={
                "voice": "eve",
                "instructions": SESSION_INSTRUCTIONS,
                "reasoning": {"effort": "high"},
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": False,
                    "interrupt_response": False,
                    "silence_duration_ms": 800,
                },
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": PCM_RATE},
                    }
                },
            }
        )
        updated = wait_until(conn, {"session.updated"}, deadline, seen)
        session = getattr(updated, "session", None)
        print("session.turn_detection:", getattr(session, "turn_detection", None))
        print("session.reasoning:", getattr(session, "reasoning", None))

        append_pcm(conn, pcm, seen, asr_transcripts, realtime=True)
        silence = b"\x00\x00" * int(PCM_RATE * SILENCE_SECONDS)
        append_pcm(conn, silence, seen, asr_transcripts, realtime=True)
        idle_until = time.time() + 1.5
        while time.time() < idle_until:
            remaining = min(0.2, idle_until - time.time())
            if remaining <= 0:
                break
            events = drain_events(conn, seen, asr_transcripts, timeout=remaining)
            if any(getattr(event, "type", None) == "input_audio_buffer.speech_started" for event in events):
                idle_until = time.time() + 1.5
        print("ingest done; events so far:", " ".join(seen))

        conn.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": USER_TEXT}],
            }
        )
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for text item after {seen}")
            try:
                event = recv_event(conn, min(remaining, 5.0))
            except TimeoutError:
                continue
            etype = getattr(event, "type", None)
            seen.append(str(etype))
            print("event:", etype)
            if etype == "error":
                message = event_error_message(event)
                if is_benign_cancel(message):
                    print("ignore:", message)
                    continue
                raise RuntimeError(message)
            if etype == "response.created":
                conn.response.cancel()
                print("cancelled premature response")
                continue
            if etype in {"conversation.item.added", "conversation.item.created"}:
                item = getattr(event, "item", None)
                content = getattr(item, "content", None) if item is not None else None
                types = []
                for part in content or []:
                    types.append(
                        getattr(part, "type", None)
                        or (part.get("type") if isinstance(part, dict) else None)
                    )
                print("item.added types:", types)
                if "input_text" in types:
                    break
        conn.response.create()
        created = wait_until(conn, {"response.created"}, deadline, seen)
        rid = event_response_id(created)
        print("asking with response_id:", rid)
        done, streamed = wait_for_response(conn, deadline, seen, response_id=rid)

    raw_text = ""
    if done is not None:
        raw_text = extract_response_text(getattr(done, "response", None))
    raw_text = raw_text or streamed
    print(raw_text or "(empty)")
    print("events:", " ".join(seen))
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        audio_rel = str(audio.relative_to(REPO))
    except ValueError:
        audio_rel = str(audio)
    out.write_text(
        json.dumps(
            {
                "model": MODEL,
                "reasoning_effort": "high",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "audio": audio_rel,
                "question": USER_TEXT,
                "answer": raw_text,
                "asr": asr_transcripts[-1] if asr_transcripts else None,
                "events": seen,
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

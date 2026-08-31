"""One way to ask four different realtime models what they heard.

Every provider takes audio and returns text, and every one of them wants it differently.
The differences are not cosmetic — three of the four will happily return a confident,
well-formatted answer while never having received the audio at all, so each adapter here was
checked against a control clip of real speech and only kept once the model read the words
back correctly.

    openai    conversation item carrying input_audio + input_text, then response.create
    grok      audio streamed into the buffer, server VAD, then response.create
    qwen      OpenAI-shaped realtime over a raw websocket; buffer append + commit
    gemini    the odd one out, see below

Gemini Live cost the most to get right. Its realtime audio channel and its text channel are
separate, and a text turn sent after the audio is treated as the content to be judged: asked
"what do you hear?", it answered "SOUND: word / WORDS: What do you hear?" — echoing the
question. Sending audio inline inside a content turn is rejected outright (1008). What works
is putting the task in the system instruction, streaming the audio as the only user input,
and taking the turn boundary away from VAD with explicit activity_start / activity_end.
Before that fix it returned "Goodbye" for every clip, which is what it says when it has heard
nothing — a perfectly plausible-looking answer that would have quietly poisoned every vote.

Rates differ too: Gemini wants 16 kHz, the rest take 24 kHz.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live
load_dotenv(REPO / ".env")

# The xAI key lives in a sibling project for historical reasons; look there if this repo's
# .env does not carry it, rather than failing at the last moment mid-run.
for extra in (REPO.parent / "non-speech-vocalization" / ".env",
              REPO.parent / "non-speech-vocalization2" / ".env",
              REPO.parent / "multi-people-voice-agent" / ".env"):
    if not os.environ.get("XAI_API_KEY") and extra.exists():
        load_dotenv(extra)

# Effort is raised only in the test phase, where the benchmark is measuring the model. Clip
# verification and the judging passes run at each model's default: "is this a laugh?" on a
# two-second clip needs no deliberation, and high effort made grok five times slower with no
# gain in agreement.
#
# Each provider exposes this differently, and one of them does not expose it at all:
#
#   openai   reasoning.effort = high
#   grok     reasoning.effort = high
#   gemini   thinking_level = high, which needs google-genai 2.x and therefore python >= 3.10.
#            On the 3.9 interpreter pip silently caps the SDK at 1.47.0, where the field does
#            not exist — an upgrade there looks like it worked and quietly gives you the old
#            parameter set. Run this from the `gemini-live` env (python 3.11).
#   qwen     no support — runs at its default while the other three are raised
TEST_EFFORT = "high"
GEMINI_THINKING_LEVEL = "high"

MODELS = {
    "openai": "gpt-realtime-2.1",
    "grok": "grok-voice-think-fast-2.0",
    "gemini": "gemini-3.1-flash-live-preview",
    "qwen": "qwen-audio-3.0-realtime-plus",
}
PROVIDERS = tuple(MODELS)

XAI_BASE = "https://api.x.ai/v1"
QWEN_WS = ("wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime?model={model}")
RATE_24K, RATE_16K = 24000, 16000
TIMEOUT = 180.0

# grok's realtime endpoint answers in about five seconds or not at all: roughly one session in
# three connects, accepts the audio, commits the buffer, then pings forever without ever
# emitting response.created. Waiting three minutes for those is pure waste — a short deadline
# makes a retry cheap, and a retry is all a hung session needs.
GROK_TIMEOUT = 25.0

# Grok's VAD decides whether the clip counts as speech at all. The default threshold treats a
# breathy exhale as silence, so nothing is committed and the session waits for a response that
# will never come. 0.1 is deliberately trigger-happy: for a file containing exactly one sound
# and nothing else, a false positive costs nothing and a false negative costs the trial.
GROK_VAD_THRESHOLD = 0.1

# Every call appends {provider, input_tokens, output_tokens}. Grok is far more expensive per
# call than the others, so the cost of a run is worth seeing rather than inferring.
USAGE: list[dict] = []


def note_usage(provider: str, response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    USAGE.append({
        "provider": provider,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    })


def usage_summary() -> dict:
    totals: dict[str, dict] = {}
    for row in USAGE:
        t = totals.setdefault(row["provider"], {"calls": 0, "input": 0, "output": 0})
        t["calls"] += 1
        t["input"] += row["input_tokens"]
        t["output"] += row["output_tokens"]
    return totals

# VAD decides whether a clip counts as speech at all, and these clips are quiet — a sigh at
# -25 dB may never trip it. Lifting the level for delivery does not change which sound it is,
# only whether the gate opens. 0 disables the boost.
GROK_GAIN_DB = 0.0


def pcm(path: Path, rate: int, gain_db: float = 0.0) -> bytes:
    filters = ["-af", f"volume={gain_db}dB"] if gain_db else []
    out = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-ac", "1", "-ar", str(rate), *filters, "-f", "s16le", "pipe:1"],
                         capture_output=True, check=True).stdout
    if not out:
        raise RuntimeError(f"ffmpeg produced no audio for {path}")
    return out


def key_for(provider: str) -> str:
    name = {"openai": "OPENAI_API_KEY", "grok": "XAI_API_KEY",
            "gemini": "GEMINI_API_KEY", "qwen": "DASHSCOPE_API_KEY"}[provider]
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is empty; set it in .env")
    return value


# --------------------------------------------------------------------------------------
# openai
# --------------------------------------------------------------------------------------

def ask_openai(audio: Path, task: str, question: str, model: str) -> str:
    import sys
    sys.path.insert(0, str(REPO / "archive" / "logo_sketch"))
    import eval_realtime as ev

    client = OpenAI(api_key=key_for("openai"))
    import time
    deadline = time.time() + TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(session={
            "type": "realtime", "instructions": task,
            "output_modalities": ["text"],
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE_24K},
                                "turn_detection": None}},
        })
        ev.wait_for(conn, deadline, "session.updated")
        content = [{"type": "input_audio",
                    "audio": base64.b64encode(pcm(audio, RATE_24K)).decode("ascii")}]
        if question:
            content.append({"type": "input_text", "text": question})
        conn.conversation.item.create(item={"type": "message", "role": "user",
                                            "content": content})
        conn.response.create(response={"output_modalities": ["text"],
                                       "max_output_tokens": 700})
        done, streamed, _ = ev.wait_for_response(conn, deadline)
        note_usage("openai", done.response)
        return ev.extract_response_text(done.response) or streamed
    finally:
        try:
            conn.close()
        except Exception:
            pass


# --------------------------------------------------------------------------------------
# grok
# --------------------------------------------------------------------------------------

def ask_grok(audio: Path, task: str, question: str, model: str) -> str:
    import sys, time
    sys.path.insert(0, str(REPO / "archive" / "printer_jam"))
    import eval_grok_voice as gv

    client = OpenAI(api_key=key_for("grok"), base_url=XAI_BASE)
    deadline = time.time() + GROK_TIMEOUT
    seen: list[str] = []
    asr: list[str] = []
    with client.realtime.connect(model=model) as conn:
        conn.session.update(session={
            # Server VAD stays ON. Grok only ingests audio through the VAD path: with
            # turn_detection None the audio is silently discarded and the model answers
            # "no audio clip is provided" — which reads exactly like a confident NO unless
            # you ask it for a reason. Sending audio as a conversation item drops it too.
            "voice": "eve", "instructions": task,
            "turn_detection": {"type": "server_vad", "create_response": False,
                               "interrupt_response": False, "silence_duration_ms": 800,
                               "threshold": GROK_VAD_THRESHOLD},
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE_24K}}},
        })
        gv.wait_until(conn, {"session.updated"}, deadline, seen)
        gv.append_pcm(conn, pcm(audio, RATE_24K, gain_db=GROK_GAIN_DB), seen, asr,
                      realtime=False)
        gv.append_pcm(conn, b"\x00\x00" * int(RATE_24K * 1.0), seen, asr, realtime=False)
        gv.drain_events(conn, seen, asr, timeout=2.0)
        if question:
            conn.conversation.item.create(item={
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": question}]})
        conn.response.create(response={"output_modalities": ["text"]})
        created = gv.wait_until(conn, {"response.created"}, deadline, seen)
        done, streamed = gv.wait_for_response(conn, deadline, seen,
                                              response_id=gv.event_response_id(created))
        note_usage("grok", getattr(done, "response", None))
        return streamed


# --------------------------------------------------------------------------------------
# qwen
# --------------------------------------------------------------------------------------

async def _ask_qwen(audio: Path, task: str, question: str, model: str) -> str:
    import websockets
    url = QWEN_WS.format(model=model)
    async with websockets.connect(url, additional_headers={
            "Authorization": f"bearer {key_for('qwen')}"},
            open_timeout=30, max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "session.update", "session": {
            "modalities": ["text"], "instructions": task,
            "input_audio_format": "pcm16", "turn_detection": None}}))
        data = pcm(audio, RATE_16K)
        for i in range(0, len(data), 8000):
            await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                      "audio": base64.b64encode(data[i:i + 8000]).decode()}))
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        if question:
            await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": question}]}}))
        await ws.send(json.dumps({"type": "response.create",
                                  "response": {"modalities": ["text"]}}))
        parts: list[str] = []
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=TIMEOUT))
            etype = event.get("type", "")
            if etype.endswith("text.delta"):
                parts.append(event.get("delta", ""))
            elif etype == "response.done":
                return "".join(parts).strip()
            elif etype == "error":
                raise RuntimeError(json.dumps(event)[:200])


def ask_qwen(audio: Path, task: str, question: str, model: str) -> str:
    return asyncio.run(_ask_qwen(audio, task, question, model))


# --------------------------------------------------------------------------------------
# gemini
# --------------------------------------------------------------------------------------

async def _ask_gemini(audio: Path, task: str, question: str, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key_for("gemini"))
    # the question has to ride in the system instruction; a text turn sent alongside the
    # audio gets treated as the thing to describe
    instruction = f"{task}\n\n{question}".strip()
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=instruction,
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)),
    )
    said: list[str] = []
    async with client.aio.live.connect(model=model, config=config) as session:
        data = pcm(audio, RATE_16K)
        await session.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(data), 3200):
            await session.send_realtime_input(
                audio=types.Blob(data=data[i:i + 3200], mime_type="audio/pcm;rate=16000"))
        await session.send_realtime_input(activity_end=types.ActivityEnd())
        async for message in session.receive():
            content = getattr(message, "server_content", None)
            if content is None:
                continue
            transcription = getattr(content, "output_transcription", None)
            if transcription is not None and transcription.text:
                said.append(transcription.text)
            if getattr(content, "turn_complete", False):
                break
    return "".join(said).strip()


def ask_gemini(audio: Path, task: str, question: str, model: str) -> str:
    return asyncio.run(_ask_gemini(audio, task, question, model))


ASK = {"openai": ask_openai, "grok": ask_grok, "qwen": ask_qwen, "gemini": ask_gemini}

# --------------------------------------------------------------------------------------
# two-turn: hear the conversation, take a turn, then answer a question about the audio
# --------------------------------------------------------------------------------------

def converse_openai(audio: Path, task: str, followups: list[str], model: str) -> dict:
    import sys, time
    sys.path.insert(0, str(REPO / "archive" / "logo_sketch"))
    import eval_realtime as ev

    client = OpenAI(api_key=key_for("openai"))
    deadline = time.time() + TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(session={
            "type": "realtime", "instructions": task,
            "output_modalities": ["audio"],
            "reasoning": {"effort": TEST_EFFORT},
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE_24K},
                                "turn_detection": None},
                      "output": {"format": {"type": "audio/pcm", "rate": RATE_24K},
                                 "voice": "marin"}},
        })
        ev.wait_for(conn, deadline, "session.updated")
        conn.conversation.item.create(item={"type": "message", "role": "user", "content": [
            {"type": "input_audio",
             "audio": base64.b64encode(pcm(audio, RATE_24K)).decode("ascii")}]})
        conn.response.create(response={"output_modalities": ["audio"],
                                       "max_output_tokens": 700})
        done, streamed, spoken = ev.wait_for_response(conn, deadline)
        reply = ev.extract_response_text(done.response) or streamed

        answers = []
        for question in followups:
            conn.conversation.item.create(item={
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": question}]})
            conn.response.create(response={"output_modalities": ["text"],
                                           "max_output_tokens": 700})
            done2, streamed2, _ = ev.wait_for_response(conn, deadline)
            answers.append(ev.extract_response_text(done2.response) or streamed2)
        return {"response": reply, "response_pcm": spoken, "answers": answers,
                "pcm_rate": RATE_24K}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def converse_grok(audio: Path, task: str, followups: list[str], model: str) -> dict:
    import sys, time
    sys.path.insert(0, str(REPO / "archive" / "printer_jam"))
    import eval_grok_voice as gv

    client = OpenAI(api_key=key_for("grok"), base_url=XAI_BASE)
    deadline = time.time() + TIMEOUT
    seen: list[str] = []
    asr: list[str] = []
    with client.realtime.connect(model=model) as conn:
        conn.session.update(session={
            "voice": "eve", "instructions": task, "reasoning": {"effort": TEST_EFFORT},
            "turn_detection": {"type": "server_vad", "create_response": False,
                               "interrupt_response": False, "silence_duration_ms": 800},
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE_24K}},
                      "output": {"format": {"type": "audio/pcm", "rate": RATE_24K}}},
        })
        gv.wait_until(conn, {"session.updated"}, deadline, seen)
        gv.append_pcm(conn, pcm(audio, RATE_24K), seen, asr, realtime=False)
        gv.append_pcm(conn, b"\x00\x00" * int(RATE_24K * 1.0), seen, asr, realtime=False)
        gv.drain_events(conn, seen, asr, timeout=1.5)

        reply, spoken = _grok_turn(conn, gv, deadline, seen, ["audio"])
        answers = []
        for question in followups:
            conn.conversation.item.create(item={
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": question}]})
            answer, _ = _grok_turn(conn, gv, deadline, seen, ["text"])
            answers.append(answer)
        return {"response": reply, "response_pcm": spoken, "answers": answers,
                "pcm_rate": RATE_24K}


def _grok_turn(conn, gv, deadline: float, seen: list, modalities: list) -> tuple[str, bytes]:
    conn.response.create(response={"output_modalities": modalities})
    created = gv.wait_until(conn, {"response.created"}, deadline, seen)
    rid = gv.event_response_id(created)
    parts: list[str] = []
    audio = bytearray()
    import time
    while True:
        if time.time() > deadline:
            raise TimeoutError("grok turn timed out")
        try:
            event = gv.recv_event(conn, 5.0)
        except TimeoutError:
            continue
        etype = getattr(event, "type", None)
        seen.append(str(etype))
        if etype == "error":
            message = gv.event_error_message(event)
            if gv.is_benign_cancel(message):
                continue
            raise RuntimeError(message)
        if etype in {"response.output_audio.delta", "response.audio.delta"}:
            chunk = getattr(event, "delta", None)
            if chunk:
                audio.extend(base64.b64decode(chunk))
        if etype in {"response.output_text.delta", "response.text.delta",
                     "response.output_audio_transcript.delta",
                     "response.audio_transcript.delta"}:
            parts.append(getattr(event, "delta", "") or "")
        if etype in {"response.output_audio_transcript.done",
                     "response.audio_transcript.done", "response.output_text.done",
                     "response.text.done"}:
            final = getattr(event, "transcript", None) or getattr(event, "text", None)
            if final:
                parts = [final]
        if etype == "response.done":
            if rid and gv.event_response_id(event) not in (None, rid):
                continue
            return "".join(parts).strip(), bytes(audio)


QWEN_MAX_BUFFER = 25.0    # the server rejects a buffer over 30s; leave headroom


def chunk_bounds(total: float, boundaries: list[float]) -> list[tuple[float, float]]:
    """Cut a long recording into buffer-sized pieces, preferring turn boundaries.

    DashScope caps one input buffer at 30 seconds, and 19 of our 60 files are longer than
    that. Committing a buffer closes it, so the fix is several consecutive input items rather
    than one — but a naive cut every 25s lands mid-word. The manifest records where each turn
    starts, so the split can be placed in the gap between turns instead.
    """
    if total <= QWEN_MAX_BUFFER:
        return [(0.0, total)]
    cuts, start = [], 0.0
    while total - start > QWEN_MAX_BUFFER:
        usable = [b for b in boundaries if start + 1.0 < b <= start + QWEN_MAX_BUFFER]
        cut = max(usable) if usable else start + QWEN_MAX_BUFFER
        cuts.append((start, cut))
        start = cut
    cuts.append((start, total))
    return cuts


def slice_pcm(data: bytes, rate: int, start: float, end: float) -> bytes:
    frame = 2
    return data[int(start * rate) * frame:int(end * rate) * frame]


async def _converse_qwen(audio: Path, task: str, followups: list[str], model: str,
                         boundaries: list[float] | None = None) -> dict:
    import websockets
    async with websockets.connect(QWEN_WS.format(model=model), additional_headers={
            "Authorization": f"bearer {key_for('qwen')}"},
            open_timeout=30, max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "session.update", "session": {
            "modalities": ["text", "audio"], "instructions": task,
            "input_audio_format": "pcm16", "turn_detection": None}}))
        data = pcm(audio, RATE_16K)
        total = len(data) / (RATE_16K * 2)
        for start, end in chunk_bounds(total, boundaries or []):
            piece = slice_pcm(data, RATE_16K, start, end)
            for i in range(0, len(piece), 8000):
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(piece[i:i + 8000]).decode()}))
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

        async def turn(modalities: list) -> tuple[str, bytes]:
            await ws.send(json.dumps({"type": "response.create",
                                      "response": {"modalities": modalities}}))
            parts: list[str] = []
            out = bytearray()
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=TIMEOUT))
                etype = event.get("type", "")
                if etype.endswith("audio.delta"):
                    out.extend(base64.b64decode(event.get("delta", "")))
                elif etype.endswith("text.delta") or etype.endswith("transcript.delta"):
                    parts.append(event.get("delta", ""))
                elif etype == "response.done":
                    return "".join(parts).strip(), bytes(out)
                elif etype == "error":
                    raise RuntimeError(json.dumps(event)[:200])

        # DashScope rejects an audio-only response: "Invalid modalities: [audio]. Must
        # include 'text'." — the transcript comes back alongside the speech either way.
        reply, spoken = await turn(["text", "audio"])
        answers = []
        for question in followups:
            await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": question}]}}))
            answer, _ = await turn(["text"])
            answers.append(answer)
        return {"response": reply, "response_pcm": spoken, "answers": answers,
                "pcm_rate": RATE_24K}


def converse_qwen(audio: Path, task: str, followups: list[str], model: str,
                  boundaries: list[float] | None = None) -> dict:
    return asyncio.run(_converse_qwen(audio, task, followups, model, boundaries))


async def _converse_gemini(audio: Path, task: str, followups: list[str], model: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key_for("gemini"))
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=task,
        thinking_config=types.ThinkingConfig(thinking_level=GEMINI_THINKING_LEVEL),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)))

    async with client.aio.live.connect(model=model, config=config) as session:
        data = pcm(audio, RATE_16K)
        await session.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(data), 3200):
            await session.send_realtime_input(
                audio=types.Blob(data=data[i:i + 3200], mime_type="audio/pcm;rate=16000"))
        await session.send_realtime_input(activity_end=types.ActivityEnd())

        async def collect() -> tuple[str, bytes]:
            said: list[str] = []
            out = bytearray()
            async for message in session.receive():
                if getattr(message, "data", None):
                    out.extend(message.data)
                content = getattr(message, "server_content", None)
                if content is None:
                    continue
                transcription = getattr(content, "output_transcription", None)
                if transcription is not None and transcription.text:
                    said.append(transcription.text)
                if getattr(content, "turn_complete", False):
                    break
            return "".join(said).strip(), bytes(out)

        reply, spoken = await collect()
        # a text turn is read as a question now that the audio arrived through the
        # activity boundaries; before that fix it was mistaken for the content
        answers = []
        for question in followups:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=question)]),
                turn_complete=True)
            answer, _ = await collect()
            answers.append(answer)
        return {"response": reply, "response_pcm": spoken, "answers": answers,
                "pcm_rate": RATE_24K}


def converse_gemini(audio: Path, task: str, followups: list[str], model: str) -> dict:
    return asyncio.run(_converse_gemini(audio, task, followups, model))


CONVERSE = {"openai": converse_openai, "grok": converse_grok, "qwen": converse_qwen,
            "gemini": converse_gemini}


def converse(provider: str, audio: Path, task: str, followups: list[str],
             model: str | None = None, boundaries: list[float] | None = None) -> dict:
    """Play the conversation, take a turn, then answer a question about what was heard.

    `boundaries` are turn start times in seconds; only qwen uses them, to place its buffer
    splits between turns rather than through a word.
    """
    if provider == "qwen":
        return converse_qwen(audio, task, followups, model or MODELS[provider], boundaries)
    return CONVERSE[provider](audio, task, followups, model or MODELS[provider])



def ask(provider: str, audio: Path, task: str, question: str = "",
        model: str | None = None) -> str:
    """Play `audio` to one model and return what it says back, as text."""
    return ASK[provider](audio, task, question, model or MODELS[provider])


if __name__ == "__main__":
    # the control that every adapter had to pass: play real speech, ask for the words back
    speech = HERE / "out" / "audio_turns" / "emb_002_t01_A.mp3"
    task = "Write down exactly the words you hear in the audio. Nothing else."
    for provider in PROVIDERS:
        try:
            print(f"  {provider:8} {ask(provider, speech, task)[:100]}", flush=True)
        except Exception as exc:
            print(f"  {provider:8} {type(exc).__name__}: {str(exc)[:110]}", flush=True)

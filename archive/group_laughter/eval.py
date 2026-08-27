"""Play the scene to a model, as the third person in the room, and let it take its turn.

Two conditions from one recording — the group laughing, or the same words with the laughs
removed — and the model is C, who now has to say something. No question is asked about the
audio, nothing is labelled, and the model is never told a sound is at issue: it just gets a
turn. What is measured is what it does with it.

    joins in   — laughs, teases, matches the register the room has set
    sympathy   — "that's awful", "are you okay" — kind, and marked when two people are
                 laughing at the story

Both providers get identical instructions and identical audio. gpt-realtime takes a
conversation item; Grok wants the audio streamed with server VAD, so the plumbing differs
even though the stimulus does not.

Usage:
    python group_laughter/eval.py --provider grok --runs 3
    python group_laughter/eval.py --provider openai --runs 3
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "printer_jam"))
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

import eval_grok_voice as gv  # noqa: E402  — Grok realtime plumbing, and the XAI key
import eval_realtime as ev  # noqa: E402  — OpenAI realtime plumbing

OUT_DIR = HERE / "out"
REPLY_DIR = OUT_DIR / "replies"
CONDITIONS = {"laughter": OUT_DIR / "wrong_airport_laughter.mp3",
              "plain": OUT_DIR / "wrong_airport_plain.mp3"}

OPENAI_MODEL = "gpt-realtime-2.1"
GROK_MODEL = "grok-voice-think-fast-2.0"
ITEM_TIMEOUT = 300.0
MAX_OUTPUT_TOKENS = 700

INSTRUCTIONS = (
    "You are one of three people in a conversation. The other two are A and B, and you are "
    "standing there with them as part of the group.\n\n"
    "You will hear A say something and then B respond. After that it is your turn to speak, "
    "as yourself, the third person in the group.\n\n"
    "When you take your turn, say only what you would actually say out loud — one or two "
    "sentences, the way a person talks. Do not describe the recording, do not narrate, do "
    "not explain yourself, and do not mention that you are an AI. Just say your line."
)

# Read off the model's own transcript of what it said. Crude, and reported next to the raw
# text rather than instead of it — the transcript is the evidence, these are a first pass.
LAUGHS = re.compile(r"(?i)\b(a?ha([\s,]*ha)+|he+h+|hee+)\b|😂|😄")
TEASE = re.compile(
    r"(?i)\b(classic|of course|typical|only you|every time|somehow|talent|"
    r"impressive|record|legend|three hours early)\b"
)
SYMPATHY = re.compile(
    r"(?i)\b(sorry|that sucks|that's rough|awful|terrible|oh no|unlucky|shame|"
    r"are you okay|hope you|frustrating|gutted|devastating)\b"
)


def run_openai(client: OpenAI, pcm: bytes, model: str, voice: str) -> tuple[str, bytes]:
    deadline = time.time() + ITEM_TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(session={
            "type": "realtime", "instructions": INSTRUCTIONS,
            "output_modalities": ["audio"],
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": ev.PCM_RATE},
                          "turn_detection": None},
                "output": {"format": {"type": "audio/pcm", "rate": ev.PCM_RATE},
                           "voice": voice},
            },
        })
        ev.wait_for(conn, deadline, "session.updated")
        conn.conversation.item.create(item={
            "type": "message", "role": "user",
            "content": [{"type": "input_audio",
                         "audio": base64.b64encode(pcm).decode("ascii")}],
        })
        conn.response.create(response={"output_modalities": ["audio"],
                                       "max_output_tokens": MAX_OUTPUT_TOKENS})
        done, streamed, spoken = ev.wait_for_response(conn, deadline)
        return (ev.extract_response_text(done.response) or streamed), spoken
    finally:
        try:
            conn.close()
        except Exception:
            pass


AUDIO_DELTAS = {"response.output_audio.delta", "response.audio.delta"}


def run_grok(client: OpenAI, pcm: bytes, model: str, effort: str) -> tuple[str, bytes]:
    deadline = time.time() + ITEM_TIMEOUT
    seen: list[str] = []
    asr: list[str] = []
    with client.realtime.connect(model=model) as conn:
        conn.session.update(session={
            "voice": "eve", "instructions": INSTRUCTIONS,
            "reasoning": {"effort": effort},
            "turn_detection": {"type": "server_vad", "create_response": False,
                               "interrupt_response": False, "silence_duration_ms": 800},
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": gv.PCM_RATE}},
                      "output": {"format": {"type": "audio/pcm", "rate": gv.PCM_RATE}}},
        })
        gv.wait_until(conn, {"session.updated"}, deadline, seen)
        gv.append_pcm(conn, pcm, seen, asr, realtime=False)
        gv.append_pcm(conn, b"\x00\x00" * int(gv.PCM_RATE * gv.SILENCE_SECONDS), seen, asr,
                      realtime=False)
        gv.drain_events(conn, seen, asr, timeout=2.0)
        conn.response.create()
        created = gv.wait_until(conn, {"response.created"}, deadline, seen)
        rid = gv.event_response_id(created)

        parts: list[str] = []
        audio = bytearray()
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("timed out")
            try:
                event = gv.recv_event(conn, min(remaining, 5.0))
            except TimeoutError:
                continue
            etype = getattr(event, "type", None)
            seen.append(str(etype))
            if etype == "error":
                message = gv.event_error_message(event)
                if gv.is_benign_cancel(message):
                    continue
                raise RuntimeError(message)
            if etype in AUDIO_DELTAS:
                chunk = getattr(event, "delta", None)
                if chunk:
                    audio.extend(base64.b64decode(chunk))
            if etype in {"response.output_text.delta", "response.text.delta",
                         "response.output_audio_transcript.delta",
                         "response.audio_transcript.delta"}:
                parts.append(getattr(event, "delta", "") or "")
            if etype in {"response.output_text.done", "response.text.done"}:
                parts = [getattr(event, "text", "") or "".join(parts)]
            if etype in {"response.output_audio_transcript.done",
                         "response.audio_transcript.done"}:
                final = getattr(event, "transcript", None)
                if final:
                    parts = [final]
            if etype == "response.done":
                if rid and gv.event_response_id(event) not in (None, rid):
                    continue
                return "".join(parts).strip(), bytes(audio)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "grok"), default="grok")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model")
    parser.add_argument("--voice", default="marin", help="openai only")
    parser.add_argument("--effort", default="high", help="grok only")
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.provider == "openai":
        model = args.model or OPENAI_MODEL
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        client = OpenAI(api_key=key)
    else:
        model = args.model or GROK_MODEL
        key = os.environ.get("XAI_API_KEY", "").strip()
        client = OpenAI(api_key=key, base_url=gv.XAI_BASE_URL)
    if not key:
        raise SystemExit(f"no API key for {args.provider}")

    results: list[dict] = []
    for condition, path in CONDITIONS.items():
        if not path.exists():
            raise SystemExit(f"missing audio: {path} — run make_audio.py first")
        pcm = ev.mp3_to_pcm16_24k(path)
        for run in range(1, args.runs + 1):
            print(f"\n{'=' * 78}\n{args.provider}  {condition}  run {run}\n{'=' * 78}",
                  flush=True)
            try:
                if args.provider == "openai":
                    text, spoken = run_openai(client, pcm, model, args.voice)
                else:
                    text, spoken = run_grok(client, pcm, model, args.effort)
            except Exception as exc:
                print(f"  failed: {type(exc).__name__}: {exc}", flush=True)
                results.append({"condition": condition, "run": run,
                                "error": f"{type(exc).__name__}: {exc}"})
                continue
            reply_mp3 = REPLY_DIR / f"{args.provider}_{condition}_{run}.mp3"
            if spoken:
                ev.pcm16_to_mp3(spoken, reply_mp3)
            markers = {"laughs": bool(LAUGHS.search(text)),
                       "teases": bool(TEASE.search(text)),
                       "sympathy": bool(SYMPATHY.search(text))}
            print(f"  {text}", flush=True)
            print(f"  markers: {markers}", flush=True)
            results.append({"condition": condition, "run": run, "turn": text,
                            "audio": str(reply_mp3.relative_to(REPO)) if spoken else None,
                            **markers})

    dest = args.out or OUT_DIR / f"eval_{args.provider}.json"
    dest.write_text(json.dumps({
        "model": model, "provider": args.provider,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "instructions": INSTRUCTIONS,
        "conditions": {k: str(v.relative_to(REPO)) for k, v in CONDITIONS.items()},
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 78)
    for condition in CONDITIONS:
        rows = [r for r in results if r["condition"] == condition and "error" not in r]
        if rows:
            print(f"{condition:9} laughs {sum(r['laughs'] for r in rows)}/{len(rows)}  "
                  f"teases {sum(r['teases'] for r in rows)}/{len(rows)}  "
                  f"sympathy {sum(r['sympathy'] for r in rows)}/{len(rows)}", flush=True)
    print(f"wrote {dest}", flush=True)


if __name__ == "__main__":
    main()

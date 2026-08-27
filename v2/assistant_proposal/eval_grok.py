"""Replay the mock-reproach pairs to grok-voice-think-fast-2.0 and have it take the turn.

Same audio, same role, different model. Each item is played up to the end of the user's turn
— the assistant's own proposal, then the laugh and the reproach — and Grok has to say what
comes next. What is being compared is not eloquence but a behavioural fork: does it play
along with the tease and keep the indulgence alive, or does it read the words as a complaint
and apologize or back off.

The two conditions differ only in whether the reproach is laughed through, so any difference
in Grok's turn is the laugh. If both conditions get the same treatment, Grok is doing what
gpt-realtime did everywhere except this one design: reading the words and ignoring the sound.

The session plumbing is printer_jam/eval_grok_voice.py — Grok wants audio streamed in real
time with server VAD rather than dropped in as a conversation item, and it needs a text nudge
to actually take its turn. That nudge is identical in both conditions, so it cannot separate
them.

Usage:
    python assistant_proposal/eval_grok.py --tag tempt2
    python assistant_proposal/eval_grok.py --tag tempt2 --only splurge
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "printer_jam"))
sys.path.insert(0, str(HERE.parent / "logo_sketch"))

import eval_grok_voice as gv  # noqa: E402  — Grok realtime plumbing, and the XAI key
import eval_realtime as ev  # noqa: E402  — pcm16 -> mp3
from make_audio import build  # noqa: E402

OUT_DIR = HERE / "out"
TURN_DIR = OUT_DIR / "audio_turns"
PROMPT_DIR = OUT_DIR / "audio_prompt"
GROK_DIR = OUT_DIR / "audio_grok"        # Grok's own conversations, when run live

GAP_BEFORE_TURN = 0.45                   # matches the gap in the sewn conversations
ITEM_TIMEOUT = 300.0

# Replay mode only. In --live mode Grok gets exactly what gpt-realtime got, below.
REPLAY_INSTRUCTIONS = (
    "You are a voice assistant in a live spoken conversation with the user.\n\n"
    "{context}\n\n"
    "You are about to hear the conversation so far. The first voice is your own — your last "
    "turn — and then the user replies.\n\n"
    "Talk the way people talk out loud: one or two sentences a turn, no lists, no headings, "
    "no stage directions. Say only your next line."
)

NUDGE = "Your turn. Say your next line."

# --live runs the real protocol instead of replaying: byte-identical instructions and opener
# to the original run, Grok invents its own proposal, and the only thing it is given is the
# same take of the user's turn. No borrowed proposal, no extra sentence about whose voice is
# whose, no text nudge. The tease line was written from the task and never from the proposal,
# so it fits whatever Grok comes up with.
LIVE_INSTRUCTIONS = (
    "You are a voice assistant in a live spoken conversation with the user.\n\n"
    "{context}\n\n"
    "Talk the way people talk out loud: one or two sentences a turn, no lists, no headings, "
    "no stage directions. Say only your next line."
)
OPENER = "Okay — what do you think we should do?"

AUDIO_DELTAS = {"response.output_audio.delta", "response.audio.delta"}


def capture(conn, deadline: float, seen: list[str], rid: str | None) -> tuple[str, bytes]:
    """Like gv.wait_for_response, but keeps the spoken audio as well as the transcript."""
    import base64
    parts: list[str] = []
    audio = bytearray()
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(f"timed out after {seen}")
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
        harvest([event], parts)
        if etype == "response.done":
            if rid and gv.event_response_id(event) not in (None, rid):
                continue
            return "".join(parts).strip(), bytes(audio)


def run_live(client: OpenAI, item: dict, turn_audio: Path, model: str,
             effort: str) -> dict:
    """Grok plays the assistant for real: it proposes, hears the tease, and replies."""
    deadline = time.time() + ITEM_TIMEOUT
    seen: list[str] = []
    asr: list[str] = []
    with client.realtime.connect(model=model) as conn:
        conn.session.update(
            session={
                "voice": "eve",
                "instructions": LIVE_INSTRUCTIONS.format(context=item["context"]),
                "reasoning": {"effort": effort},
                "turn_detection": {"type": "server_vad", "create_response": False,
                                   "interrupt_response": False,
                                   "silence_duration_ms": 800},
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": gv.PCM_RATE}},
                    "output": {"format": {"type": "audio/pcm", "rate": gv.PCM_RATE}},
                },
            }
        )
        gv.wait_until(conn, {"session.updated"}, deadline, seen)

        conn.conversation.item.create(
            item={"type": "message", "role": "user",
                  "content": [{"type": "input_text", "text": OPENER}]}
        )
        conn.response.create()
        created = gv.wait_until(conn, {"response.created"}, deadline, seen)
        proposal, proposal_pcm = capture(conn, deadline, seen,
                                         gv.event_response_id(created))

        gv.append_pcm(conn, gv.mp3_to_pcm16_24k(turn_audio), seen, asr, realtime=False)
        silence = b"\x00\x00" * int(gv.PCM_RATE * gv.SILENCE_SECONDS)
        gv.append_pcm(conn, silence, seen, asr, realtime=False)
        stray: list[str] = []
        harvest(gv.drain_events(conn, seen, asr, timeout=2.0), stray)

        conn.response.create()
        created = gv.wait_until(conn, {"response.created"}, deadline, seen)
        reply, reply_pcm = capture(conn, deadline, seen, gv.event_response_id(created))

    return {"proposal": proposal, "proposal_pcm": proposal_pcm,
            "reply": reply, "reply_pcm": reply_pcm, "asr": asr[-1] if asr else None}

# Three things this file gets wrong if you copy printer_jam verbatim.
#
# Streaming at realtime=True paces a 25s clip over 25 wall-clock seconds. That is right when
# you are testing an interactive agent; for a fixed recording it just costs 25s an item.
#
# With create_response True, Grok answers the *proposal* mid-clip — it treats every incoming
# voice as the user, so VAD closes on the assistant's own turn and it replies to itself. It
# has to stay False.
#
# And it starts a response of its own anyway. Cancelling that and re-asking loses the first
# half of the sentence, because the replacement response continues the cancelled one from the
# middle: "spend your money wisely..." was the tail of a sentence whose head we threw away.
# So every response's text is collected, cancelled ones included, and joined back together.
TEXT_DELTAS = {"response.output_audio_transcript.delta", "response.audio_transcript.delta",
               "response.output_text.delta", "response.text.delta"}
TEXT_DONE = {"response.output_audio_transcript.done", "response.audio_transcript.done",
             "response.output_text.done", "response.text.done"}


def harvest(events, parts: list[str]) -> None:
    """Keep whatever any response said, including one we are about to cancel."""
    for event in events:
        etype = getattr(event, "type", None)
        if etype in TEXT_DELTAS:
            parts.append(getattr(event, "delta", "") or "")
        elif etype in TEXT_DONE:
            final = getattr(event, "transcript", None) or getattr(event, "text", None)
            if final:
                parts[:] = [final]


def prompt_clip(item: dict) -> Path:
    """Proposal + the user's turn, stopping before the reply we are trying to replace."""
    item_id = item["item_id"]
    proposal = TURN_DIR / f"{item_id}_proposal.mp3"
    turn = TURN_DIR / f"{item_id}_user_turn.mp3"
    for path in (proposal, turn):
        if not path.exists():
            raise SystemExit(f"missing turn audio: {path}")
    dest = PROMPT_DIR / f"{item_id}.mp3"
    if not dest.exists():
        build([("file", proposal), ("silence", GAP_BEFORE_TURN), ("file", turn)], dest)
    return dest


def take_turn(client: OpenAI, item: dict, model: str, effort: str) -> dict:
    pcm = gv.mp3_to_pcm16_24k(prompt_clip(item))
    deadline = time.time() + ITEM_TIMEOUT
    seen: list[str] = []
    asr: list[str] = []
    with client.realtime.connect(model=model) as conn:
        conn.session.update(
            session={
                "voice": "eve",
                "instructions": REPLAY_INSTRUCTIONS.format(context=item["context"]),
                "reasoning": {"effort": effort},
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": False,
                    "interrupt_response": False,
                    "silence_duration_ms": 800,
                },
                "audio": {"input": {"format": {"type": "audio/pcm", "rate": gv.PCM_RATE}}},
            }
        )
        gv.wait_until(conn, {"session.updated"}, deadline, seen)

        gv.append_pcm(conn, pcm, seen, asr, realtime=False)
        silence = b"\x00\x00" * int(gv.PCM_RATE * gv.SILENCE_SECONDS)
        gv.append_pcm(conn, silence, seen, asr, realtime=False)
        early: list[str] = []
        harvest(gv.drain_events(conn, seen, asr, timeout=2.0), early)

        conn.conversation.item.create(
            item={"type": "message", "role": "user",
                  "content": [{"type": "input_text", "text": NUDGE}]}
        )
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for the nudge after {seen}")
            try:
                event = gv.recv_event(conn, min(remaining, 5.0))
            except TimeoutError:
                continue
            etype = getattr(event, "type", None)
            seen.append(str(etype))
            harvest([event], early)
            if etype == "error":
                message = gv.event_error_message(event)
                if gv.is_benign_cancel(message):
                    continue
                raise RuntimeError(message)
            if etype == "response.created":
                conn.response.cancel()
                continue
            if etype in {"conversation.item.added", "conversation.item.created"}:
                item_obj = getattr(event, "item", None)
                content = getattr(item_obj, "content", None) if item_obj else None
                types = [getattr(p, "type", None) or (p.get("type") if isinstance(p, dict)
                                                      else None) for p in content or []]
                if "input_text" in types:
                    break

        conn.response.create()
        created = gv.wait_until(conn, {"response.created"}, deadline, seen)
        done, streamed = gv.wait_for_response(
            conn, deadline, seen, response_id=gv.event_response_id(created)
        )

    answer = ""
    if done is not None:
        answer = gv.extract_response_text(getattr(done, "response", None))
    answer = answer or streamed
    head = "".join(early).strip()
    if head and head not in answer:            # the cancelled response's half of the sentence
        answer = f"{head} {answer}".strip()
    return {"answer": answer, "asr": asr[-1] if asr else None}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="tempt2", help="which pair of runs to replay")
    parser.add_argument("--only", action="append", help="task id (repeatable)")
    parser.add_argument("--model", default=gv.MODEL)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--live", action="store_true",
                        help="run the real protocol: Grok proposes, then hears the tease")
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conditions = [("laughed", f"session_tease_{args.tag}.json"),
                  ("flat", f"session_teaseplain_{args.tag}.json")]
    client = OpenAI(api_key=gv.os.environ["XAI_API_KEY"].strip(), base_url=gv.XAI_BASE_URL)

    results: list[dict] = []
    for condition, name in conditions:
        session = json.loads((OUT_DIR / name).read_text(encoding="utf-8"))
        for item in session["items"]:
            if "error" in item or (args.only and item["task"] not in args.only):
                continue
            print(f"\n{'=' * 78}\n{condition:8} {item['item_id']}\n{'=' * 78}", flush=True)
            try:
                if args.live:
                    turn_audio = TURN_DIR / f"{item['item_id']}_user_turn.mp3"
                    live = run_live(client, item, turn_audio, args.model, args.effort)
                    stem = f"{item['item_id']}_grok"
                    proposal_mp3 = GROK_DIR / f"{stem}_proposal.mp3"
                    reply_mp3 = GROK_DIR / f"{stem}_reply.mp3"
                    ev.pcm16_to_mp3(live["proposal_pcm"], proposal_mp3)
                    ev.pcm16_to_mp3(live["reply_pcm"], reply_mp3)
                    conversation = GROK_DIR / f"{stem}.mp3"
                    build([("file", proposal_mp3), ("silence", GAP_BEFORE_TURN),
                           ("file", turn_audio), ("silence", GAP_BEFORE_TURN),
                           ("file", reply_mp3)], conversation)
                    print(f"  grok proposed: {live['proposal']}", flush=True)
                    print(f"  said:  {item['line']}", flush=True)
                    print(f"  grok:  {live['reply']}", flush=True)
                    results.append({
                        "condition": condition, "task": item["task"],
                        "item_id": stem, "context": item["context"],
                        "grok_proposal": live["proposal"], "line": item["line"],
                        "grok": live["reply"], "grok_asr": live["asr"],
                        "audio": str(conversation.relative_to(REPO)),
                        "gpt_realtime_proposal": item["proposal"],
                        "gpt_realtime": item["reply"],
                    })
                    continue
                turn = take_turn(client, item, args.model, args.effort)
            except Exception as exc:
                print(f"  failed: {type(exc).__name__}: {exc}", flush=True)
                results.append({"condition": condition, "task": item["task"],
                                "error": f"{type(exc).__name__}: {exc}"})
                continue
            print(f"  said:  {item['line']}", flush=True)
            print(f"  grok:  {turn['answer']}", flush=True)
            results.append({
                "condition": condition, "task": item["task"], "item_id": item["item_id"],
                "context": item["context"], "line": item["line"],
                "prompt_audio": str(prompt_clip(item).relative_to(REPO)),
                "grok": turn["answer"], "grok_asr": turn["asr"],
                "gpt_realtime": item["reply"],
            })

    dest = args.out or OUT_DIR / f"eval_grok_{args.tag}.json"
    dest.write_text(json.dumps({
        "model": args.model, "reasoning_effort": args.effort,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "instructions": LIVE_INSTRUCTIONS if args.live else REPLAY_INSTRUCTIONS,
        "protocol": "live" if args.live else "replay",
        "nudge": None if args.live else NUDGE,
        "compared_with": "gpt-realtime-2.1, from the original runs",
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {dest}", flush=True)


if __name__ == "__main__":
    main()

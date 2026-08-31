"""Measure exactly what we send to and receive from grok, in bytes, and price it.

Written because the xAI console reported ~66,000 seconds of audio, which is far more than
this project could plausibly have sent. The only way to settle that is to count the bytes
actually put on the wire and convert them with the format we configured — never to infer
duration from how long a websocket stayed open, which is precisely the quantity under
suspicion.

Per request it records:
    audio sent      total bytes of input_audio_buffer.append payloads, base64-decoded
    audio received  total bytes of response.output_audio.delta payloads
    protocol        conversation.item.create / response.create sent,
                    response.created received
    attempts        including retries and timeouts, each of which sends the audio again

Seconds are bytes / (rate * channels * width). At 24 kHz mono 16-bit that is 48,000 B/s.

Wall-clock session time is logged too, but clearly separated: it is what a connection-time
billing model would charge, and comparing the two columns is the point of the audit.

Usage:
    python v3/audit_grok.py --clips 6
    python v3/audit_grok.py --history        # reconstruct what past runs sent
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import providers as P

sys.path.insert(0, str(P.REPO / "archive" / "printer_jam"))
import eval_grok_voice as gv
from openai import OpenAI

RATE, CHANNELS, WIDTH = 24000, 1, 2
BYTES_PER_SECOND = RATE * CHANNELS * WIDTH      # 48,000
CHUNK = 24_000


@dataclass
class Meter:
    sent_bytes: int = 0
    recv_bytes: int = 0
    item_create: int = 0
    response_create: int = 0
    response_created: int = 0
    attempts: int = 0
    timeouts: int = 0
    wall: float = 0.0
    rows: list = field(default_factory=list)

    @property
    def sent_seconds(self) -> float:
        return self.sent_bytes / BYTES_PER_SECOND

    @property
    def recv_seconds(self) -> float:
        return self.recv_bytes / BYTES_PER_SECOND


def one_request(meter: Meter, audio: Path, question: str, timeout: float) -> str:
    """One session, counting every byte and every protocol message."""
    meter.attempts += 1
    started = time.time()
    client = OpenAI(api_key=P.key_for("grok"), base_url=P.XAI_BASE)
    deadline = time.time() + timeout
    seen, asr = [], []
    sent_here = recv_here = 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            with client.realtime.connect(model=P.MODELS["grok"]) as conn:
                conn.session.update(session={
                    "voice": "eve", "instructions": question,
                    "turn_detection": {"type": "server_vad", "create_response": False,
                                       "interrupt_response": False,
                                       "silence_duration_ms": 800,
                                       "threshold": P.GROK_VAD_THRESHOLD},
                    "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE}}}})
                gv.wait_until(conn, {"session.updated"}, deadline, seen)

                pcm = P.pcm(audio, RATE)
                silence = b"\x00\x00" * RATE          # the 1s tail we always append
                for blob in (pcm, silence):
                    for i in range(0, len(blob), CHUNK):
                        piece = blob[i:i + CHUNK]
                        conn.input_audio_buffer.append(
                            audio=base64.b64encode(piece).decode("ascii"))
                        sent_here += len(piece)
                gv.drain_events(conn, seen, asr, timeout=2.0)

                conn.response.create(response={"output_modalities": ["text"]})
                meter.response_create += 1
                created = gv.wait_until(conn, {"response.created"}, deadline, seen)
                meter.response_created += 1
                rid = gv.event_response_id(created)

                text_parts = []
                while True:
                    if time.time() > deadline:
                        raise TimeoutError("response.done")
                    event = gv.recv_event(conn, 5.0)
                    etype = getattr(event, "type", None)
                    if etype in {"response.output_audio.delta", "response.audio.delta"}:
                        delta = getattr(event, "delta", None)
                        if delta:
                            recv_here += len(base64.b64decode(delta))
                    if etype in {"response.output_text.delta", "response.text.delta",
                                 "response.output_audio_transcript.delta"}:
                        text_parts.append(getattr(event, "delta", "") or "")
                    if etype == "response.done":
                        answer = "".join(text_parts).strip()
                        break
        return answer
    except Exception as exc:
        meter.timeouts += 1
        return f"({type(exc).__name__})"
    finally:
        meter.sent_bytes += sent_here
        meter.recv_bytes += recv_here
        meter.wall += time.time() - started
        meter.rows.append({"audio": audio.name, "sent_bytes": sent_here,
                           "sent_seconds": round(sent_here / BYTES_PER_SECOND, 3),
                           "recv_bytes": recv_here,
                           "recv_seconds": round(recv_here / BYTES_PER_SECOND, 3),
                           "wall_seconds": round(time.time() - started, 1)})


def history() -> None:
    """What past runs could possibly have sent, from the recorded call counts."""
    out = Path(__file__).resolve().parent / "out"
    man = json.loads((out / "audio_manifest.json").read_text())
    clip_seconds = {c["path"]: c["seconds"] for i in man["items"] for c in i["clips"]}
    cond_seconds = {i["conditions"][c]["path"]: i["conditions"][c]["seconds"]
                    for i in man["items"] for c in ("neutral", "happy", "sad")}

    total = calls = 0.0, 0
    audio = 0.0
    rows = 0
    verdicts = out / "clip_verdicts.jsonl"
    if verdicts.exists():
        for line in verdicts.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("provider") != "grok":
                continue
            rows += 1
            audio += clip_seconds.get(r["path"], 1.5) + 1.0     # clip + the silence tail
    trials = out / "trials.jsonl"
    tr_rows = 0
    tr_audio = 0.0
    if trials.exists():
        for line in trials.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("provider") != "grok":
                continue
            tr_rows += 1
            tr_audio += cond_seconds.get(r.get("audio", ""), 30.0) + 1.0

    print("RECONSTRUCTED FROM RECORDED CALLS (one send per recorded row)")
    print(f"  clip verdicts   {rows:5} rows · {audio:9,.0f}s of audio sent")
    print(f"  test trials     {tr_rows:5} rows · {tr_audio:9,.0f}s")
    print(f"  total                   {audio + tr_audio:9,.0f}s "
          f"= {(audio + tr_audio)/3600:.2f} hours")
    print()
    print("  Retries are not in these counts: only the final row per attempt is recorded.")
    print("  Even at 6x for every call the total stays under "
          f"{6*(audio + tr_audio)/3600:.1f} hours.")


def _connect():
    client = OpenAI(api_key=P.key_for("grok"), base_url=P.XAI_BASE)
    return client.realtime.connect(model=P.MODELS["grok"])


def _configure(conn) -> None:
    conn.session.update(session={
        "voice": "eve", "instructions": "ignore",
        "turn_detection": {"type": "server_vad", "create_response": False,
                           "interrupt_response": False, "silence_duration_ms": 800,
                           "threshold": P.GROK_VAD_THRESHOLD},
        "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE}}}})


def discriminate(clip: Path, bulk_seconds: float, idle_seconds: float, reps: int) -> None:
    """Two blocks that pull audio-sent and connection-time as far apart as possible.

    Sending a short clip and closing at once -- the obvious probe -- puts roughly a second
    of audio through a roughly one-second session, so the two candidate meters land on the
    same number and a console delta cannot tell them apart. These blocks break the tie:

        bulk   lots of audio through a session held open as briefly as possible
        idle   a session held open a long time with no audio at all

    Whichever block moves the console names the quantity being metered.
    """
    unit = P.pcm(clip, RATE)
    reps_needed = max(1, int(bulk_seconds * BYTES_PER_SECOND / len(unit)))
    payload = unit * reps_needed + b"\x00\x00" * RATE      # 1s silence so VAD closes the turn
    bulk_each = len(payload) / BYTES_PER_SECOND

    print(f"format: {RATE} Hz · {CHANNELS} ch · {WIDTH*8}-bit = {BYTES_PER_SECOND:,} bytes/s")
    print(f"clip:   {clip.name} · {len(unit)/BYTES_PER_SECOND:.2f}s, repeated "
          f"{reps_needed}x -> {bulk_each:.1f}s per bulk session\n")

    def stamp(label: str) -> None:
        print(f"  --- {label} at {time.strftime('%H:%M:%S')} ---", flush=True)

    bulk_audio = bulk_wall = 0.0
    stamp("BULK BLOCK starts")
    for n in range(1, reps + 1):
        started = time.time()
        note = "ok"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with _connect() as conn:
                    _configure(conn)
                    for i in range(0, len(payload), CHUNK):
                        conn.input_audio_buffer.append(
                            audio=base64.b64encode(payload[i:i + CHUNK]).decode("ascii"))
                    bulk_audio += bulk_each
                    # Wait for the server to commit the turn before closing. Without the
                    # silence tail VAD never closes it, and an uncommitted buffer might not
                    # be metered at all -- which would make this block prove nothing.
                    note, end = "no commit", time.time() + 8
                    while time.time() < end:
                        try:
                            ev = gv.recv_event(conn, min(3.0, max(0.1, end - time.time())))
                        except Exception:
                            continue
                        etype = getattr(ev, "type", "") if ev is not None else ""
                        if etype == "input_audio_buffer.committed":
                            note = "committed"
                            break
                        if "error" in etype:
                            note = "ERROR"
                            break
        except Exception as exc:
            note = f"{type(exc).__name__}"
        wall = time.time() - started
        bulk_wall += wall
        print(f"  bulk {n}/{reps}: sent {bulk_each:5.1f}s · session {wall:5.2f}s · {note}",
              flush=True)

    idle_wall = 0.0
    stamp("IDLE BLOCK starts")
    for n in range(1, reps + 1):
        started = time.time()
        note = "ok"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with _connect() as conn:
                    _configure(conn)
                    end = time.time() + idle_seconds
                    while time.time() < end:
                        try:
                            gv.recv_event(conn, min(5.0, max(0.1, end - time.time())))
                        except Exception:
                            pass
        except Exception as exc:
            note = f"{type(exc).__name__}"
        wall = time.time() - started
        idle_wall += wall
        print(f"  idle {n}/{reps}: sent   0.0s · session {wall:5.2f}s · {note}", flush=True)
    stamp("BOTH BLOCKS done")

    print()
    print(f"  BULK   audio sent {bulk_audio:7.1f}s · connection {bulk_wall:7.1f}s")
    print(f"  IDLE   audio sent {0.0:7.1f}s · connection {idle_wall:7.1f}s")
    print(f"  TOTAL  audio sent {bulk_audio:7.1f}s · connection "
          f"{bulk_wall + idle_wall:7.1f}s")
    print()
    print("  Console delta over this window:")
    print(f"    ~{bulk_audio:5.0f}s and nothing from the idle block -> metered on audio sent")
    print(f"    ~{bulk_wall + idle_wall:5.0f}s, mostly from the idle block "
          "-> metered on connection time")


def manual_turn(clips: list[Path], grace: float, cap: float) -> None:
    """Manual turn control: no VAD, explicit commit, and close the moment it goes quiet.

    Two reasons to prefer this shape. It removes server VAD from the ingestion path, which
    is the component we have never been able to make reliable. And it bounds the session to
    what the exchange actually needs -- if nothing comes back within the grace window, the
    connection closes instead of sitting open until a timeout, so connection time stops
    dwarfing the audio whether or not that is what gets billed.
    """
    print(f"format: {RATE} Hz · {CHANNELS} ch · {WIDTH*8}-bit = {BYTES_PER_SECOND:,} bytes/s")
    print("turn control: manual (turn_detection off, explicit commit)")
    print(f"grace: {grace:.1f}s for the first byte back · cap: {cap:.1f}s once it starts\n")

    question = "Answer YES or NO: is this a person laughing?"
    sent_total = recv_total = wall_total = 0.0
    answered = 0
    rows = []

    for clip in clips:
        started = time.time()
        sent = recv = 0
        answer, why = "", ""
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with _connect() as conn:
                    conn.session.update(session={
                        "voice": "eve", "instructions": question,
                        "turn_detection": None,
                        "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE}}}})
                    payload = P.pcm(clip, RATE)
                    for i in range(0, len(payload), CHUNK):
                        piece = payload[i:i + CHUNK]
                        conn.input_audio_buffer.append(
                            audio=base64.b64encode(piece).decode("ascii"))
                        sent += len(piece)
                    conn.input_audio_buffer.commit()
                    conn.response.create(response={"output_modalities": ["audio"]})

                    parts = []
                    hard = time.time() + grace + cap
                    deadline = time.time() + grace     # extended once the first byte lands
                    while time.time() < min(deadline, hard):
                        try:
                            ev = gv.recv_event(conn, max(0.1, min(1.0, deadline - time.time())))
                        except Exception:
                            continue
                        etype = getattr(ev, "type", "") if ev is not None else ""
                        if etype in {"response.output_audio.delta", "response.audio.delta"}:
                            delta = getattr(ev, "delta", None)
                            if delta:
                                recv += len(base64.b64decode(delta))
                                deadline = min(hard, time.time() + grace)
                        elif etype in {"response.output_audio_transcript.delta",
                                       "response.output_text.delta", "response.text.delta"}:
                            parts.append(getattr(ev, "delta", "") or "")
                            deadline = min(hard, time.time() + grace)
                        elif etype == "response.done":
                            break
                        elif "error" in etype:
                            why = str(getattr(ev, "error", "error"))[:60]
                            break
                    answer = "".join(parts).strip()
                    # falling out of the loop closes the session at once: no idle waiting
        except Exception as exc:
            why = type(exc).__name__

        wall = time.time() - started
        sent_total += sent / BYTES_PER_SECOND
        recv_total += recv / BYTES_PER_SECOND
        wall_total += wall
        got = recv > 0
        answered += got
        rows.append({"clip": clip.name, "sent_seconds": round(sent / BYTES_PER_SECOND, 2),
                     "recv_seconds": round(recv / BYTES_PER_SECOND, 2),
                     "wall_seconds": round(wall, 2), "answer": answer, "note": why})
        mark = "audio back" if got else (why or "silent")
        print(f"  {clip.name:32} sent {sent / BYTES_PER_SECOND:5.2f}s · "
              f"recv {recv / BYTES_PER_SECOND:5.2f}s · session {wall:5.2f}s · "
              f"{mark:14} {answer[:26]!r}", flush=True)

    n = len(clips)
    print()
    print(f"  responded         {answered}/{n}")
    print(f"  AUDIO SENT     {sent_total:8.2f}s")
    print(f"  AUDIO RECEIVED {recv_total:8.2f}s")
    print(f"  connection     {wall_total:8.2f}s")
    ratio = wall_total / sent_total if sent_total else 0
    print(f"  ratio          {ratio:8.1f}x  connection / audio-sent")
    out = Path(__file__).resolve().parent / "out" / "grok_manual_turn.json"
    out.write_text(json.dumps({"grace": grace, "cap": cap, "rows": rows}, indent=2))
    print(f"\n  rows -> {out.name}")


def probe_close(count: int, empties: int, clip: Path) -> None:
    """Send one short clip, then close at once. Never ask for a response.

    The decisive test for what xAI meters. Each session puts a known, small amount of audio
    on the wire and holds the connection for as little as the protocol allows, so the two
    candidate quantities land far apart. A block of empty sessions -- connect, configure,
    close, no audio at all -- runs alongside as the control: if those also move the console,
    the meter is counting sessions, not sound.
    """
    pcm_bytes = P.pcm(clip, RATE)
    seconds = len(pcm_bytes) / BYTES_PER_SECOND
    print(f"format: {RATE} Hz · {CHANNELS} ch · {WIDTH*8}-bit = {BYTES_PER_SECOND:,} bytes/s")
    print(f"clip:   {clip.name} · {seconds:.3f}s · {len(pcm_bytes):,} bytes")
    print(f"plan:   {count} sessions sending that clip once, then closing immediately")
    print(f"        {empties} control sessions that connect and close, sending nothing\n")

    def session(payload: bytes | None, label: str) -> float:
        started = time.time()
        try:
            client = OpenAI(api_key=P.key_for("grok"), base_url=P.XAI_BASE)
            with contextlib.redirect_stdout(io.StringIO()):
                with client.realtime.connect(model=P.MODELS["grok"]) as conn:
                    conn.session.update(session={
                        "voice": "eve", "instructions": "ignore",
                        "turn_detection": {"type": "server_vad", "create_response": False,
                                           "interrupt_response": False,
                                           "silence_duration_ms": 800,
                                           "threshold": P.GROK_VAD_THRESHOLD},
                        "audio": {"input": {"format": {"type": "audio/pcm", "rate": RATE}}}})
                    if payload:
                        for i in range(0, len(payload), CHUNK):
                            conn.input_audio_buffer.append(
                                audio=base64.b64encode(payload[i:i + CHUNK]).decode("ascii"))
                    # no response.create, no waiting -- close
            wall = time.time() - started
            print(f"  {label}: closed after {wall:5.2f}s", flush=True)
        except Exception as exc:
            wall = time.time() - started
            print(f"  {label}: {type(exc).__name__} after {wall:5.2f}s", flush=True)
        return wall

    started_all = time.time()
    audio_walls = [session(pcm_bytes, f"audio {n:2}/{count}") for n in range(1, count + 1)]
    print()
    empty_walls = [session(None, f"empty {n:2}/{empties}") for n in range(1, empties + 1)]

    sent = len(pcm_bytes) * count
    total_wall = time.time() - started_all
    print()
    print(f"  AUDIO SENT          {sent / BYTES_PER_SECOND:8.2f}s  ({sent:,} bytes, "
          f"{count} sessions)")
    print(f"  connection time     {sum(audio_walls):8.2f}s  (audio sessions)")
    print(f"  connection time     {sum(empty_walls):8.2f}s  (empty sessions, 0s audio)")
    print(f"  connection total    {sum(audio_walls) + sum(empty_walls):8.2f}s")
    print(f"  run wall-clock      {total_wall:8.2f}s")
    print()
    print("  Read the console delta for this window and compare:")
    print(f"    ~{sent / BYTES_PER_SECOND:6.0f}s  -> metered on audio actually sent")
    print(f"    ~{sum(audio_walls) + sum(empty_walls):6.0f}s  -> metered on connection time")
    print(f"    ~{(count + empties) * 60:6.0f}s  -> metered per session at some fixed minimum")
    print("    anything larger -> metered on something else again")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clips", type=int, default=6)
    p.add_argument("--timeout", type=float, default=25.0)
    p.add_argument("--history", action="store_true")
    p.add_argument("--probe-close", type=int, metavar="N",
                   help="open N sessions, send one short clip each, close immediately")
    p.add_argument("--manual", type=int, metavar="N",
                   help="N clips through manual turn control, closing as soon as it goes quiet")
    p.add_argument("--grace", type=float, default=4.0)
    p.add_argument("--cap", type=float, default=12.0)
    p.add_argument("--discriminate", action="store_true",
                   help="bulk-audio vs idle-connection blocks, to tell the meters apart")
    p.add_argument("--bulk-seconds", type=float, default=30.0)
    p.add_argument("--idle-seconds", type=float, default=60.0)
    p.add_argument("--reps", type=int, default=4)
    p.add_argument("--empties", type=int, default=5,
                   help="control sessions that connect and close without sending audio")
    p.add_argument("--price-audio-in", type=float, default=None,
                   help="USD per minute of audio input, from xAI's current pricing")
    p.add_argument("--price-audio-out", type=float, default=None,
                   help="USD per minute of audio output")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.history:
        history()
        return
    voc = Path(__file__).resolve().parent / "out" / "audio_voc"
    if args.manual:
        manual_turn(sorted(voc.glob("*.mp3"))[: args.manual], args.grace, args.cap)
        return
    if args.discriminate:
        clip = min(sorted(voc.glob("*.mp3")), key=lambda c: c.stat().st_size)
        discriminate(clip, args.bulk_seconds, args.idle_seconds, args.reps)
        return
    if args.probe_close:
        clip = min(sorted(voc.glob("*.mp3")), key=lambda c: c.stat().st_size)
        probe_close(args.probe_close, args.empties, clip)
        return

    out = Path(__file__).resolve().parent / "out"
    clips = sorted(out.glob("audio_voc/*.mp3"))[: args.clips]
    meter = Meter()
    print(f"format: {RATE} Hz · {CHANNELS} ch · {WIDTH*8}-bit = {BYTES_PER_SECOND:,} bytes/s\n")
    for clip in clips:
        answer = one_request(meter, clip, "Answer YES or NO: is this a person laughing?",
                             args.timeout)
        row = meter.rows[-1]
        print(f"  {clip.name:36} sent {row['sent_seconds']:5.2f}s "
              f"({row['sent_bytes']:7,}B) · recv {row['recv_seconds']:5.2f}s · "
              f"wall {row['wall_seconds']:5.1f}s · {answer[:14]!r}")

    print(f"\n  attempts {meter.attempts} · timeouts {meter.timeouts} · "
          f"response.create {meter.response_create} · "
          f"response.created {meter.response_created}")
    print(f"  AUDIO SENT     {meter.sent_seconds:8.2f}s  ({meter.sent_bytes:,} bytes)")
    print(f"  AUDIO RECEIVED {meter.recv_seconds:8.2f}s  ({meter.recv_bytes:,} bytes)")
    print(f"  wall-clock     {meter.wall:8.2f}s  <- what connection-time billing would charge")
    ratio = meter.wall / meter.sent_seconds if meter.sent_seconds else 0
    print(f"  ratio          {ratio:8.1f}x  wall / audio-sent")

    if args.price_audio_in is not None:
        cost_in = meter.sent_seconds / 60 * args.price_audio_in
        cost_out = meter.recv_seconds / 60 * (args.price_audio_out or 0)
        print(f"\n  estimated: ${cost_in:.4f} in + ${cost_out:.4f} out = "
              f"${cost_in + cost_out:.4f} for {meter.attempts} request(s)")
    else:
        print("\n  pass --price-audio-in / --price-audio-out to price it; "
              "no rates are assumed here")


if __name__ == "__main__":
    main()

"""Test gpt-realtime-2.1 as Speaker A: hear B's reaction, then reason and reply.

Per condition the model gets the shared context as text and the conversation as audio (A's
own proposal, then B's wordless reaction), is told plainly that it is playing Speaker A, and
must return three things:

    INFERRED STATE    — what it takes B's reaction to mean here
    RESPONSE FUNCTION — the conversational action it is about to perform
    RESPONSE          — what A actually says, one sentence

Asking for all three makes the model's reasoning legible: if it names B's state correctly
but its response does not act on it, that is a different failure from misreading the sound
in the first place.

Every condition runs in its own fresh session, and the 9 trials are shuffled. A model that
saw the three counterfactual siblings together would know it was being contrast-tested; here
each trial is the model's honest read of one situation, with no view of the others.

Nothing about the gold answers, the three-way design, or the vocalization inventory is ever
shown to the model.

Usage:
    python make_response/eval_realtime.py --limit 2
    python make_response/eval_realtime.py
    python make_response/eval_realtime.py --resume
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
load_dotenv(REPO / ".env")

DEFAULT_MANIFEST = HERE / "out" / "audio_manifest.json"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
ITEM_TIMEOUT = 150.0
MAX_OUTPUT_TOKENS = 500
MAX_ATTEMPTS = 3

INSTRUCTIONS = (
    "You are playing Speaker A in a conversation with Speaker B. This is a role-play: "
    "everything you say is said as Speaker A, in the first person.\n\n"
    "You will be given the situation in writing, and then you will hear the conversation "
    "so far. The audio contains your own line — Speaker A's proposal to Speaker B — "
    "followed by Speaker B's reaction. Speaker B does not reply in words. B answers only "
    "with a non-speech sound.\n\n"
    "Work out what B's reaction tells you about how B is taking your proposal, then say the "
    "next thing you would say.\n\n"
    "Reply in exactly this format, three lines, nothing else:\n\n"
    "INFERRED STATE: <one sentence on what B's reaction tells you about B's state>\n"
    "RESPONSE FUNCTION: <a short phrase naming the conversational action you are about to "
    "perform>\n"
    "RESPONSE: <exactly one sentence, spoken in character as Speaker A, to Speaker B>\n\n"
    "In the RESPONSE line, do not name or describe the sound B made and do not ask B what "
    "it meant. Respond to what it meant. Stay in character as Speaker A."
)


def prompt_text(entry: dict) -> str:
    return "\n".join(
        [
            "The situation:",
            f"  {entry['shared_context']}",
            "",
            f"Who you are: {entry['relationship']}  You are Speaker A.",
            "",
            "Now listen to the conversation so far — your proposal, then B's reaction.",
            "Then give your three lines.",
        ]
    )


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


def wait_for_response(conn, deadline: float) -> tuple[object, str]:
    texts: list[str] = []
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for response.done")
        event = recv_event(conn, remaining)
        etype = getattr(event, "type", None)
        if etype == "error":
            raise RuntimeError(event_error_message(event))
        if etype in TEXT_DELTA:
            texts.append(getattr(event, "delta", "") or "")
        elif etype in TEXT_DONE:
            final = getattr(event, "text", None)
            if final:
                texts = [final]
        elif etype == "response.done":
            return event, "".join(texts).strip()


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


FIELD_RES = {
    "inferred_state": re.compile(r"INFERRED\s*STATE\s*:\s*(.+)", re.I),
    "response_function": re.compile(r"RESPONSE\s*FUNCTION\s*:\s*(.+)", re.I),
    "response": re.compile(r"RESPONSE\s*:\s*(.+)", re.I),
}


def parse_three_fields(text: str) -> dict:
    """RESPONSE: is a suffix of RESPONSE FUNCTION:, so match the function line first."""
    out: dict[str, str | None] = {}
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for key in ("inferred_state", "response_function"):
        out[key] = None
        for line in lines:
            match = FIELD_RES[key].match(line)
            if match:
                out[key] = match.group(1).strip()
                break
    out["response"] = None
    for line in lines:
        if FIELD_RES["response_function"].match(line):
            continue
        match = FIELD_RES["response"].match(line)
        if match:
            out["response"] = match.group(1).strip()
            break
    return out


def ask_once(client: OpenAI, entry: dict, pcm: bytes, model: str) -> dict:
    """A fresh session per condition: no sibling condition is ever in context."""
    deadline = time.time() + ITEM_TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": INSTRUCTIONS,
                "output_modalities": ["text"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": PCM_RATE},
                        "turn_detection": None,
                    }
                },
            }
        )
        wait_for(conn, deadline, "session.updated")
        conn.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt_text(entry)},
                    {"type": "input_audio", "audio": base64.b64encode(pcm).decode("ascii")},
                ],
            }
        )
        conn.response.create(
            response={"output_modalities": ["text"], "max_output_tokens": MAX_OUTPUT_TOKENS}
        )
        done, streamed = wait_for_response(conn, deadline)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    response = done.response
    raw = extract_response_text(response) or streamed
    usage = getattr(response, "usage", None)
    return {
        "raw_text": raw,
        **parse_three_fields(raw),
        "status": getattr(response, "status", None),
        "usage": usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.manifest = args.manifest.resolve()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    trials = list(manifest["clips"])
    # shuffle so nothing order-dependent lines up with the three-way contrast
    random.Random(args.seed).shuffle(trials)
    if args.limit:
        trials = trials[: args.limit]

    done: dict[str, dict] = {}
    if args.resume and args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
        for row in previous.get("rows", []):
            if row.get("response") and not row.get("error"):
                done[f"{row['item_id']}_{row['vocalization']}"] = row
        print(f"resuming, {len(done)} trial(s) already collected", flush=True)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    print(f"{len(trials)} trial(s) · model {args.model} · one fresh session each", flush=True)

    rows: list[dict] = []
    for index, entry in enumerate(trials, start=1):
        trial_id = f"{entry['item_id']}_{entry['vocalization']}"
        if trial_id in done:
            rows.append(done[trial_id])
            continue
        row = {
            "item_id": entry["item_id"],
            "vocalization": entry["vocalization"],
            "domain": entry.get("domain"),
            "relationship": entry.get("relationship"),
            "shared_context": entry["shared_context"],
            "proposal": entry["proposal"],
            "gold_inferred_state": entry["gold_inferred_state"],
            "gold_response_function": entry["gold_response_function"],
            "gold_response": entry["gold_response"],
            "audio": entry["prompt"],
        }
        try:
            pcm = mp3_to_pcm16_24k(REPO / entry["prompt"])
            result: dict | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    result = ask_once(client, entry, pcm, args.model)
                    if result.get("response"):
                        break
                    if attempt == MAX_ATTEMPTS:
                        break
                    print(f"    unparseable, retrying: {result['raw_text'][:90]!r}", flush=True)
                except Exception as exc:
                    if attempt == MAX_ATTEMPTS:
                        raise
                    wait = 2 ** attempt
                    print(f"    retry in {wait}s: {type(exc).__name__}: {exc}", flush=True)
                    time.sleep(wait)
            assert result is not None
            row.update({
                "raw_text": result["raw_text"],
                "inferred_state": result["inferred_state"],
                "response_function": result["response_function"],
                "response": result["response"],
                "usage": result["usage"],
            })
            print(f"[{index}/{len(trials)}] {trial_id}", flush=True)
            print(f"    B reacted with: {entry['vocalization']}", flush=True)
            print(f"    inferred : {result['inferred_state']}", flush=True)
            print(f"    function : {result['response_function']}", flush=True)
            print(f"    A says   : {result['response']}", flush=True)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(trials)}] {trial_id} failed: {exc}", flush=True)
        rows.append(row)

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({
                "model": args.model,
                "seed": args.seed,
                "manifest": str(args.manifest.relative_to(REPO)),
                "instructions": INSTRUCTIONS,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "n_trials": len(trials),
                "n_collected": sum(1 for r in rows if r.get("response")),
                "n_failed": sum(1 for r in rows if r.get("error")),
                "rows": rows,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    collected = sum(1 for r in rows if r.get("response"))
    print(f"\ncollected {collected}/{len(trials)}", flush=True)

    # side-by-side per scenario, which is where the contrast is visible
    by_item: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row.get("response"):
            by_item[row["item_id"]][row["vocalization"]] = row
    for item_id in sorted(by_item):
        print("\n" + "=" * 76)
        conditions = by_item[item_id]
        any_row = next(iter(conditions.values()))
        print(f"{item_id} — {any_row['domain']}")
        print(f"A proposed: {any_row['proposal']}")
        for voc in ("laughter", "sigh", "gasp"):
            row = conditions.get(voc)
            if not row:
                continue
            print(f"\n  B: [{voc}]")
            print(f"    model function: {row['response_function']}")
            print(f"    model says    : {row['response']}")
            print(f"    gold function : {row['gold_response_function']}")
            print(f"    gold says     : {row['gold_response']}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

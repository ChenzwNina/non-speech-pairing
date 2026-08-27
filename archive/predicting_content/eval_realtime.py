"""Two-choice eval of gpt-realtime-2.1 on sewn predicting_content clips.

The model hears Turn 1 + Turn 2 + the clipped Turn 3 vocalization, then
must choose Speaker A's next line: gold or the opposite alternative.

Usage:
    python predicting_content/eval_realtime.py
    python predicting_content/eval_realtime.py --limit 1
    python predicting_content/eval_realtime.py --seed 0 --resume
"""

from __future__ import annotations

import argparse
import base64
import hashlib
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

DEFAULT_IN = HERE / "out" / "items.json"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"
DEFAULT_AUDIO = HERE / "out" / "audio_sewn"

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
ITEM_TIMEOUT = 90.0
MAX_ATTEMPTS = 3

SESSION_INSTRUCTIONS = (
    "You are taking a listening test. You will hear a short conversation. "
    "Speaker A speaks first. Speaker B speaks second. Then Speaker A makes "
    "a brief non-speech sound. Choose which line Speaker A is about to say. "
    "Reply with exactly one letter: A or B. No other text."
)

LETTER_RE = re.compile(r"\b([AB])\b", re.I)
TAG_RE = re.compile(r"\[[^\[\]]+\]\s*")


def strip_formula(text: str, formula: str) -> str:
    text = (text or "").strip()
    if formula and text.startswith(formula):
        return text[len(formula) :].lstrip()
    return TAG_RE.sub("", text).strip()


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


def option_block(question: dict) -> str:
    lines = [
        "You heard a short conversation. Speaker A spoke first, Speaker B second,",
        "then Speaker A made a brief non-speech sound.",
        "",
        "Which line is Speaker A about to say?",
        "",
    ]
    for opt in question["options"]:
        lines.append(f"{opt['key']}. {opt['text']}")
    lines.extend(["", "Reply with only one letter: A or B."])
    return "\n".join(lines)


def parse_letter(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.upper() in {"A", "B"}:
        return text.upper()
    m = re.match(r"^\s*([AB])(?:\s*[.):,\-]|\s*$)", text, re.I)
    if m:
        return m.group(1).upper()
    found = LETTER_RE.findall(text)
    if found:
        return found[0].upper()
    return None


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


def wait_for_response(conn, deadline: float) -> tuple[object, str, list[str]]:
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
    return done, "".join(texts).strip(), seen


def query_one(client: OpenAI, question: dict, pcm: bytes) -> dict:
    user_text = option_block(question)
    audio_b64 = base64.b64encode(pcm).decode("ascii")
    deadline = time.time() + ITEM_TIMEOUT
    with client.realtime.connect(model=MODEL) as conn:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": SESSION_INSTRUCTIONS,
                "output_modalities": ["text"],
                "max_output_tokens": 256,
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
                "max_output_tokens": 256,
                "instructions": SESSION_INSTRUCTIONS,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_audio", "audio": audio_b64},
                            {"type": "input_text", "text": user_text},
                        ],
                    }
                ],
            }
        )
        done, streamed, _seen = wait_for_response(conn, deadline)

    response = done.response
    raw_text = extract_response_text(response) or streamed
    predicted = parse_letter(raw_text)
    status = getattr(response, "status", None)
    usage = getattr(response, "usage", None)
    usage_dict = usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else None
    if status and status != "completed" and not predicted:
        details = getattr(response, "status_details", None)
        raise RuntimeError(f"response status={status} details={details}")
    return {
        "raw_text": raw_text,
        "predicted_key": predicted,
        "status": status,
        "usage": usage_dict,
    }


def make_question(item: dict, audio_dir: Path) -> dict:
    formula = item["formula"]
    gold_text = item["gold"]["lexical"] or strip_formula(item["gold"]["text"], formula)
    alt = item["alternatives"][0]
    alt_text = strip_formula(alt["text"], formula)
    digest = hashlib.md5(item["item_id"].encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    options = [
        {"key": "A", "id": "gold", "text": gold_text},
        {"key": "B", "id": "alternative", "text": alt_text},
    ]
    rng.shuffle(options)
    for key, opt in zip(["A", "B"], options):
        opt["key"] = key
    correct_key = next(opt["key"] for opt in options if opt["id"] == "gold")
    return {
        "question_id": item["item_id"],
        "item_id": item["item_id"],
        "vocalization_id": item["vocalization_id"],
        "vocalization": item["vocalization"],
        "domain": item["domain"],
        "formula": formula,
        "content_type": item["content_type"],
        "audio": str((audio_dir / f"{item['item_id']}.mp3").relative_to(REPO)),
        "options": options,
        "correct_key": correct_key,
        "gold_text": gold_text,
        "alt_text": alt_text,
        "alt_type": alt.get("content_type"),
    }


def accuracy_block(rows: list[dict], key: str | None = None) -> dict:
    if key is None:
        groups = {"": rows}
    else:
        groups = defaultdict(list)
        for row in rows:
            groups[row.get(key)].append(row)
    out = {}
    for name, subset in groups.items():
        n = len(subset)
        correct = sum(1 for row in subset if row.get("correct"))
        parsed = sum(1 for row in subset if row.get("predicted_key"))
        out[name or "all"] = {
            "n": n,
            "correct": correct,
            "parsed": parsed,
            "accuracy": (correct / n) if n else None,
        }
    return out


def summarize(rows: list[dict]) -> dict:
    return {
        "overall": accuracy_block(rows)["all"],
        "by_vocalization": accuracy_block(rows, "vocalization_id"),
        "by_domain": accuracy_block(rows, "domain"),
    }


def fmt_acc(block: dict) -> str:
    acc = block["accuracy"]
    pct = "n/a" if acc is None else f"{100 * acc:.1f}%"
    return f"{block['correct']}/{block['n']} = {pct}"


def print_summary(summary: dict) -> None:
    print(f"\n=== {MODEL} accuracy ===")
    print(f"overall          {fmt_acc(summary['overall'])}")
    print("by vocalization")
    for name, block in sorted(summary["by_vocalization"].items()):
        print(f"  {name:<16} {fmt_acc(block)}")
    print("by domain")
    for name, block in sorted(summary["by_domain"].items()):
        print(f"  {name:<16} {fmt_acc(block)}")


def load_done(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {row["question_id"]: row for row in data.get("results", [])}


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    payload = json.loads(args.infile.read_text())
    items = [item for item in payload.get("results") or [] if item.get("gold") and item.get("alternatives")]
    questions = [make_question(item, args.audio_dir.resolve()) for item in items]
    rng = random.Random(args.seed)
    rng.shuffle(questions)
    if args.limit:
        questions = questions[: args.limit]

    done = load_done(args.out) if args.resume else {}
    client = OpenAI()
    results = []
    order = []

    print(f"model={MODEL}  n={len(questions)}  seed={args.seed}", flush=True)
    for i, question in enumerate(questions, start=1):
        qid = question["question_id"]
        order.append(qid)
        gold = question["correct_key"]
        if qid in done and done[qid].get("predicted_key"):
            row = done[qid]
            results.append(row)
            mark = "OK" if row.get("correct") else "NO"
            print(
                f"[{i}/{len(questions)}] {qid}  skip  gold={gold} pred={row.get('predicted_key')} {mark}",
                flush=True,
            )
            continue

        audio_path = REPO / question["audio"]
        if not audio_path.exists():
            raise SystemExit(f"missing audio: {audio_path}")

        print(f"[{i}/{len(questions)}] {qid}  querying...", flush=True)
        last_error = None
        row = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                pcm = mp3_to_pcm16_24k(audio_path)
                answer = query_one(client, question, pcm)
                predicted = answer["predicted_key"]
                row = {
                    "question_id": qid,
                    "item_id": question["item_id"],
                    "vocalization_id": question["vocalization_id"],
                    "domain": question["domain"],
                    "audio": question["audio"],
                    "options": question["options"],
                    "correct_key": gold,
                    "gold_text": question["gold_text"],
                    "alt_text": question["alt_text"],
                    "predicted_key": predicted,
                    "raw_text": answer["raw_text"],
                    "status": answer["status"],
                    "usage": answer["usage"],
                    "correct": predicted == gold if predicted else False,
                    "attempt": attempt,
                    "error": None,
                }
                break
            except Exception as exc:
                last_error = str(exc)
                print(
                    f"[{i}/{len(questions)}] {qid}  attempt {attempt} failed: {last_error}",
                    flush=True,
                )
                time.sleep(min(2 * attempt, 8))

        if row is None:
            row = {
                "question_id": qid,
                "item_id": question["item_id"],
                "vocalization_id": question["vocalization_id"],
                "domain": question["domain"],
                "audio": question["audio"],
                "options": question["options"],
                "correct_key": gold,
                "gold_text": question["gold_text"],
                "alt_text": question["alt_text"],
                "predicted_key": None,
                "raw_text": "",
                "status": "error",
                "usage": None,
                "correct": False,
                "attempt": MAX_ATTEMPTS,
                "error": last_error,
            }

        results.append(row)
        mark = "OK" if row["correct"] else "NO"
        pred = row["predicted_key"] or "?"
        extra = f"  err={row['error']}" if row["error"] else ""
        print(
            f"[{i}/{len(questions)}] {qid}  gold={gold} pred={pred} {mark}  "
            f"{(row.get('raw_text') or '')[:40]!r}{extra}",
            flush=True,
        )

        save(
            args.out,
            {
                "model": MODEL,
                "seed": args.seed,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "items": str(args.infile),
                "n": len(questions),
                "order": order,
                "results": results,
                "summary": summarize(results),
            },
        )

    summary = summarize(results)
    print_summary(summary)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

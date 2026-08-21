"""Two-question realtime eval on the audio_prompt clips.

Each clip is played once, then two questions are asked in the same session, so the model
answers both from one listen:

    Q1  which of six non-speech vocalizations was at the end          (6-way)
    Q2  which of two replies would the first speaker say next         (2-way)

Q2's distractor is the sibling version's reply — same words up to the vocalization, so the
transcript alone cannot decide it.

Usage:
    python predicting_response/eval_realtime.py
    python predicting_response/eval_realtime.py --limit 2
    python predicting_response/eval_realtime.py --seed 0 --resume
    python predicting_response/eval_realtime.py --separate-sessions
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
REPO = HERE.parent
load_dotenv(REPO / ".env")

DEFAULT_MANIFEST = HERE / "out" / "audio_manifest.json"
DEFAULT_OUT = HERE / "out" / "eval_realtime.json"

MODEL = "gpt-realtime-2.1"
PCM_RATE = 24000
ITEM_TIMEOUT = 120.0
MAX_OUTPUT_TOKENS = 512
MAX_ATTEMPTS = 3

VOC_LABELS = {
    "gasp": "Gasp",
    "grunt": "Grunt",
    "laughter": "Laughter",
    "sigh": "Sigh",
    "sob": "Sob",
    "yawn": "Yawn",
}
VOC_IDS = list(VOC_LABELS)

SESSION_INSTRUCTIONS = (
    "You are taking a listening test. You will hear a short conversation between two "
    "people. One person does all of the speaking. The other person is present but says "
    "nothing, and reacts at the end with a non-speech sound. Answer each question with "
    "exactly one letter and no other text."
)

Q1_LETTERS = "ABCDEF"
Q2_LETTERS = "AB"


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


def build_q1(rng: random.Random) -> tuple[str, dict[str, str]]:
    order = VOC_IDS[:]
    rng.shuffle(order)
    mapping = {Q1_LETTERS[i]: voc for i, voc in enumerate(order)}
    lines = [
        "You just heard the conversation.",
        "",
        "At the very end, the second person made a non-speech sound.",
        "Which sound was it?",
        "",
    ]
    for letter, voc in mapping.items():
        lines.append(f"{letter}. {VOC_LABELS[voc]}")
    lines += ["", "Reply with only one letter: A, B, C, D, E, or F."]
    return "\n".join(lines), mapping


def build_q2(gold: str, distractor: str, rng: random.Random) -> tuple[str, dict[str, str], str]:
    options = [gold, distractor]
    rng.shuffle(options)
    mapping = {Q2_LETTERS[i]: text for i, text in enumerate(options)}
    gold_letter = next(letter for letter, text in mapping.items() if text == gold)
    lines = [
        "Now think about what happens next in that conversation.",
        "",
        "Given how the second person reacted, what would the speaker say next?",
        "",
    ]
    for letter, text in mapping.items():
        lines.append(f"{letter}. {text}")
    lines += ["", "Reply with only one letter: A or B."]
    return "\n".join(lines), mapping, gold_letter


def parse_letter(text: str, allowed: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.upper() in set(allowed):
        return text.upper()
    match = re.match(rf"^\s*([{allowed}])(?:\s*[.):,\-]|\s*$)", text, re.I)
    if match:
        return match.group(1).upper()
    found = re.findall(rf"\b([{allowed}])\b", text, re.I)
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
    conn.session.update(
        session={
            "type": "realtime",
            "instructions": SESSION_INSTRUCTIONS,
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
    return conn


def ask(conn, deadline: float, content: list[dict], allowed: str) -> dict:
    conn.conversation.item.create(
        item={"type": "message", "role": "user", "content": content}
    )
    # gpt-realtime-2.1 reasons before answering; a tight cap is spent on reasoning
    # tokens and the response comes back empty, so leave real headroom here.
    conn.response.create(
        response={"output_modalities": ["text"], "max_output_tokens": MAX_OUTPUT_TOKENS}
    )
    done, streamed = wait_for_response(conn, deadline)
    response = done.response
    raw_text = extract_response_text(response) or streamed
    usage = getattr(response, "usage", None)
    return {
        "raw_text": raw_text,
        "letter": parse_letter(raw_text, allowed),
        "status": getattr(response, "status", None),
        "usage": usage.model_dump() if usage is not None and hasattr(usage, "model_dump") else None,
    }


def query_one(client: OpenAI, item: dict, pcm: bytes, model: str, separate: bool) -> dict:
    audio_b64 = base64.b64encode(pcm).decode("ascii")
    deadline = time.time() + ITEM_TIMEOUT
    audio_content = {"type": "input_audio", "audio": audio_b64}

    conn = open_session(client, model, deadline)
    try:
        q1 = ask(
            conn,
            deadline,
            [audio_content, {"type": "input_text", "text": item["q1_text"]}],
            Q1_LETTERS,
        )
        if separate:
            conn.close()
            conn = open_session(client, model, deadline)
            content = [audio_content, {"type": "input_text", "text": item["q2_text"]}]
        else:
            content = [{"type": "input_text", "text": item["q2_text"]}]
        q2 = ask(conn, deadline, content, Q2_LETTERS)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"q1": q1, "q2": q2}


def build_items(manifest: dict, rng: random.Random) -> list[dict]:
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for entry in manifest["clips"]:
        by_pair[entry["pair_id"]].append(entry)

    items: list[dict] = []
    for entry in manifest["clips"]:
        siblings = [e for e in by_pair[entry["pair_id"]] if e["version"] != entry["version"]]
        if len(siblings) != 1:
            raise SystemExit(
                f"{entry['pair_id']} {entry['version']} has {len(siblings)} sibling(s); "
                "the 2-way question needs exactly one"
            )
        gold_voc = entry["vocalization"].strip("[]")
        if gold_voc not in VOC_LABELS:
            raise SystemExit(f"unknown vocalization {entry['vocalization']}")
        q1_text, q1_map = build_q1(rng)
        q2_text, q2_map, q2_gold = build_q2(entry["reply_text"], siblings[0]["reply_text"], rng)
        gold_letter = next(letter for letter, voc in q1_map.items() if voc == gold_voc)
        items.append(
            {
                "item_id": f"{entry['pair_id']}_{entry['version']}",
                "pair_id": entry["pair_id"],
                "version": entry["version"],
                "theme": entry.get("theme"),
                "contrast": entry.get("contrast"),
                "audio": entry["prompt"],
                "gold_vocalization": gold_voc,
                "intended_interpretation": entry.get("intended_interpretation"),
                "q1_text": q1_text,
                "q1_options": q1_map,
                "q1_gold": gold_letter,
                "q2_text": q2_text,
                "q2_options": q2_map,
                "q2_gold": q2_gold,
            }
        )
    rng.shuffle(items)
    return items


def rate(rows: list[dict], field: str) -> str:
    if not rows:
        return "0/0"
    correct = sum(1 for row in rows if row.get(field))
    return f"{correct}/{len(rows)} = {100 * correct / len(rows):.1f}%"


def summarize(rows: list[dict]) -> dict:
    done = [row for row in rows if not row.get("error")]
    by_voc: dict[str, list[dict]] = defaultdict(list)
    by_contrast: dict[str, list[dict]] = defaultdict(list)
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for row in done:
        by_voc[row["gold_vocalization"]].append(row)
        by_contrast[row["contrast"]].append(row)
        by_theme[row.get("theme") or "unknown"].append(row)
    q1_right = [row for row in done if row.get("q1_correct")]
    q1_wrong = [row for row in done if not row.get("q1_correct")]
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in done:
        heard = row.get("q1_predicted_vocalization") or "unparsed"
        confusion[row["gold_vocalization"]][heard] += 1
    return {
        "n": len(done),
        "errors": len(rows) - len(done),
        "q1_vocalization": rate(done, "q1_correct"),
        "q2_response": rate(done, "q2_correct"),
        "both": rate(done, "both_correct"),
        "q2_when_q1_correct": rate(q1_right, "q2_correct"),
        "q2_when_q1_wrong": rate(q1_wrong, "q2_correct"),
        "q1_by_vocalization": {v: rate(rs, "q1_correct") for v, rs in sorted(by_voc.items())},
        "q2_by_vocalization": {v: rate(rs, "q2_correct") for v, rs in sorted(by_voc.items())},
        "q2_by_contrast": {c: rate(rs, "q2_correct") for c, rs in sorted(by_contrast.items())},
        "q1_by_theme": {t: rate(rs, "q1_correct") for t, rs in sorted(by_theme.items())},
        "q2_by_theme": {t: rate(rs, "q2_correct") for t, rs in sorted(by_theme.items())},
        "q1_confusion": {g: dict(h) for g, h in sorted(confusion.items())},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--seed", type=int, default=0, help="shuffle + option-order seed")
    parser.add_argument("--limit", type=int, help="first N items after shuffling")
    parser.add_argument("--resume", action="store_true", help="keep results already in --out")
    parser.add_argument(
        "--separate-sessions",
        action="store_true",
        help="ask Q2 in a fresh session so Q1's answer cannot scaffold it",
    )
    args = parser.parse_args()
    # relative_to(REPO) below requires absolute paths regardless of cwd
    args.manifest = args.manifest.resolve()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)
    items = build_items(manifest, rng)
    if args.limit:
        items = items[: args.limit]

    done: dict[str, dict] = {}
    if args.resume and args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
        for row in previous.get("rows", []):
            if not row.get("error"):
                done[row["item_id"]] = row
        print(f"resuming, {len(done)} item(s) already answered", flush=True)

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    print(
        f"{len(items)} item(s) · model {args.model} · seed {args.seed} · "
        + ("separate sessions" if args.separate_sessions else "one session, two questions"),
        flush=True,
    )

    rows: list[dict] = []
    for index, item in enumerate(items, start=1):
        if item["item_id"] in done:
            rows.append(done[item["item_id"]])
            continue
        audio_path = REPO / item["audio"]
        row = {k: v for k, v in item.items() if k not in {"q1_text", "q2_text"}}
        try:
            pcm = mp3_to_pcm16_24k(audio_path)
            result: dict | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    result = query_one(client, item, pcm, args.model, args.separate_sessions)
                    break
                except Exception as exc:
                    if attempt == MAX_ATTEMPTS:
                        raise
                    wait = 2 ** attempt
                    print(f"    retry in {wait}s: {type(exc).__name__}: {exc}", flush=True)
                    time.sleep(wait)
            assert result is not None
            q1, q2 = result["q1"], result["q2"]
            heard = item["q1_options"].get(q1["letter"]) if q1["letter"] else None
            row.update(
                {
                    "q1_raw": q1["raw_text"],
                    "q1_predicted": q1["letter"],
                    "q1_predicted_vocalization": heard,
                    "q1_correct": q1["letter"] == item["q1_gold"],
                    "q2_raw": q2["raw_text"],
                    "q2_predicted": q2["letter"],
                    "q2_predicted_text": item["q2_options"].get(q2["letter"]) if q2["letter"] else None,
                    "q2_correct": q2["letter"] == item["q2_gold"],
                    "usage": {"q1": q1["usage"], "q2": q2["usage"]},
                }
            )
            row["both_correct"] = bool(row["q1_correct"] and row["q2_correct"])
            print(
                f"[{index}/{len(items)}] {item['item_id']:24} "
                f"Q1 {item['gold_vocalization']:9}→{heard or '?':9} "
                f"{'ok ' if row['q1_correct'] else 'X  '}"
                f"Q2 {q1['letter'] or '?'}/{q2['letter'] or '?'} "
                f"{'ok' if row['q2_correct'] else 'X'}",
                flush=True,
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(items)}] {item['item_id']:24} failed: {exc}", flush=True)
        rows.append(row)

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "model": args.model,
                    "seed": args.seed,
                    "separate_sessions": args.separate_sessions,
                    "manifest": str(args.manifest.relative_to(REPO)),
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "summary": summarize(rows),
                    "rows": rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    summary = summarize(rows)
    print("\n" + "=" * 62)
    print(f"Q1 vocalization (6-way, chance 16.7%): {summary['q1_vocalization']}")
    print(f"Q2 next reply   (2-way, chance 50.0%): {summary['q2_response']}")
    print(f"both correct:                          {summary['both']}")
    print(f"  Q2 when Q1 right: {summary['q2_when_q1_correct']}")
    print(f"  Q2 when Q1 wrong: {summary['q2_when_q1_wrong']}")
    print("\nQ1 by vocalization:")
    for voc, value in summary["q1_by_vocalization"].items():
        print(f"  {voc:9} {value}")
    print("\nQ2 by vocalization:")
    for voc, value in summary["q2_by_vocalization"].items():
        print(f"  {voc:9} {value}")
    if len(summary["q1_by_theme"]) > 1:
        print("\nQ1 by theme:")
        for theme, value in summary["q1_by_theme"].items():
            print(f"  {theme:9} {value}")
        print("\nQ2 by theme:")
        for theme, value in summary["q2_by_theme"].items():
            print(f"  {theme:9} {value}")
    if summary["errors"]:
        print(f"\n{summary['errors']} item(s) errored")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

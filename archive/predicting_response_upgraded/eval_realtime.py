"""Two-dialogue eval on gpt-realtime: separate audios, then matching questions.

Each pair has two SEPARATE audio clips (from generate_audio.py): {pair_id}_v1.mp3 and
{pair_id}_v2.mp3, each turn1 + one vocalization, never mixed. Per item, which one plays
as "Dialogue 1" vs "Dialogue 2" is randomized independently of v1/v2 — otherwise position
is confounded with vocalization identity (v1 is always the alphabetically-earlier sound
in this dataset's contrasts).

Flow, all in one realtime session:
    play Dialogue 1 audio -> Q1: which sound was that?              (6-way)
    play Dialogue 2 audio -> Q1 again, same format, for Dialogue 2  (6-way)
    Q2: match the two gold interpretations to the two dialogues      (2-way)
    Q3: match the two gold responses to the two dialogues            (2-way)

Usage:
    python predicting_response_upgraded/eval_realtime.py
    python predicting_response_upgraded/eval_realtime.py --limit 2
    python predicting_response_upgraded/eval_realtime.py --resume --seed 0
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
MAX_OUTPUT_TOKENS = 512
MAX_ATTEMPTS = 3

VOC_LABELS = {
    "gasp": "Gasp", "grunt": "Grunt", "laughter": "Laughter",
    "sigh": "Sigh", "sob": "Sob", "yawn": "Yawn",
}
VOC_IDS = list(VOC_LABELS)
Q_LETTERS_6 = "ABCDEF"
Q_LETTERS_2 = "AB"

SESSION_INSTRUCTIONS = (
    "You are taking a listening test. You will hear two separate short dialogues, one at "
    "a time. In both dialogues, Speaker A says the exact same line. Right after that, "
    "Speaker B reacts using only a non-speech sound — no words either time. The two "
    "dialogues have different reactions from Speaker B. Listen to each dialogue fully "
    "before answering anything. Answer every question with exactly one letter and no "
    "other text."
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


def build_q_voc(rng: random.Random, dialogue_label: str) -> tuple[str, dict[str, str]]:
    order = VOC_IDS[:]
    rng.shuffle(order)
    mapping = {Q_LETTERS_6[i]: voc for i, voc in enumerate(order)}
    lines = [f"You just heard {dialogue_label}. Which non-speech sound did Speaker B produce?", ""]
    for letter, voc in mapping.items():
        lines.append(f"{letter}. {VOC_LABELS[voc]}")
    lines += ["", "Reply with only one letter: A, B, C, D, E, or F."]
    return "\n".join(lines), mapping


def build_q_interp_match(interp_d1: str, interp_d2: str, rng: random.Random) -> tuple[str, dict[str, str], str]:
    true_pairing = (
        f"\"{interp_d1}\" describes Dialogue 1, and \"{interp_d2}\" describes Dialogue 2."
    )
    swapped_pairing = (
        f"\"{interp_d2}\" describes Dialogue 1, and \"{interp_d1}\" describes Dialogue 2."
    )
    options = [true_pairing, swapped_pairing]
    rng.shuffle(options)
    mapping = {Q_LETTERS_2[i]: text for i, text in enumerate(options)}
    gold_letter = next(letter for letter, text in mapping.items() if text == true_pairing)
    lines = [
        "Here are two interpretations of what Speaker B's reaction means. Match each "
        "interpretation to the dialogue it actually applies to.",
        "",
    ]
    for letter, text in mapping.items():
        lines.append(f"{letter}. {text}")
    lines += ["", "Reply with only one letter: A or B."]
    return "\n".join(lines), mapping, gold_letter


def build_q_response_match(response_d1: str, response_d2: str, rng: random.Random) -> tuple[str, dict[str, str], str]:
    true_pairing = (
        f"\"{response_d1}\" follows Dialogue 1, and \"{response_d2}\" follows Dialogue 2."
    )
    swapped_pairing = (
        f"\"{response_d2}\" follows Dialogue 1, and \"{response_d1}\" follows Dialogue 2."
    )
    options = [true_pairing, swapped_pairing]
    rng.shuffle(options)
    mapping = {Q_LETTERS_2[i]: text for i, text in enumerate(options)}
    gold_letter = next(letter for letter, text in mapping.items() if text == true_pairing)
    lines = [
        "Here are two things Speaker B might say right after their reaction. Match each "
        "one to the dialogue it actually follows.",
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
                "input": {"format": {"type": "audio/pcm", "rate": PCM_RATE}, "turn_detection": None}
            },
        }
    )
    wait_for(conn, deadline, "session.updated")
    return conn


def ask(conn, deadline: float, content: list[dict], allowed: str) -> dict:
    conn.conversation.item.create(item={"type": "message", "role": "user", "content": content})
    conn.response.create(response={"output_modalities": ["text"], "max_output_tokens": MAX_OUTPUT_TOKENS})
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


def query_one(client: OpenAI, item: dict, pcm_d1: bytes, pcm_d2: bytes, model: str) -> dict:
    deadline = time.time() + ITEM_TIMEOUT
    audio_d1 = {"type": "input_audio", "audio": base64.b64encode(pcm_d1).decode("ascii")}
    audio_d2 = {"type": "input_audio", "audio": base64.b64encode(pcm_d2).decode("ascii")}

    conn = open_session(client, model, deadline)
    try:
        q1a = ask(conn, deadline, [audio_d1, {"type": "input_text", "text": item["q1a_text"]}], Q_LETTERS_6)
        q1b = ask(conn, deadline, [audio_d2, {"type": "input_text", "text": item["q1b_text"]}], Q_LETTERS_6)
        q2 = ask(conn, deadline, [{"type": "input_text", "text": item["q2_text"]}], Q_LETTERS_2)
        q3 = ask(conn, deadline, [{"type": "input_text", "text": item["q3_text"]}], Q_LETTERS_2)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"q1a": q1a, "q1b": q1b, "q2": q2, "q3": q3}


def build_items(manifest: dict, rng: random.Random) -> list[dict]:
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for entry in manifest["clips"]:
        by_pair[entry["pair_id"]].append(entry)

    items: list[dict] = []
    for pair_id, versions in sorted(by_pair.items()):
        if len(versions) != 2:
            raise SystemExit(f"{pair_id} has {len(versions)} version(s), expected 2")
        pair = {v["version"]: v for v in versions}
        v1, v2 = pair["v1"], pair["v2"]

        # which of v1/v2 is "Dialogue 1" is randomized per item, independent of v1/v2 —
        # otherwise position is confounded with vocalization identity across the dataset
        order = [v1, v2]
        rng.shuffle(order)
        d1, d2 = order

        voc_d1 = d1["vocalization"].strip("[]")
        voc_d2 = d2["vocalization"].strip("[]")
        if voc_d1 not in VOC_LABELS or voc_d2 not in VOC_LABELS:
            raise SystemExit(f"unknown vocalization in {pair_id}")

        q1a_text, q1a_map = build_q_voc(rng, "Dialogue 1")
        q1a_gold = next(letter for letter, voc in q1a_map.items() if voc == voc_d1)
        q1b_text, q1b_map = build_q_voc(rng, "Dialogue 2")
        q1b_gold = next(letter for letter, voc in q1b_map.items() if voc == voc_d2)

        q2_text, q2_map, q2_gold = build_q_interp_match(d1["interpretation"], d2["interpretation"], rng)
        q3_text, q3_map, q3_gold = build_q_response_match(d1["response"], d2["response"], rng)

        items.append({
            "item_id": pair_id,
            "pair_id": pair_id,
            "contrast": d1.get("contrast"),
            "audio_d1": d1["prompt"],
            "audio_d2": d2["prompt"],
            "d1_is_version": [k for k, v in pair.items() if v is d1][0],
            "d2_is_version": [k for k, v in pair.items() if v is d2][0],
            "gold_vocalization_d1": voc_d1,
            "gold_vocalization_d2": voc_d2,
            "q1a_text": q1a_text, "q1a_options": q1a_map, "q1a_gold": q1a_gold,
            "q1b_text": q1b_text, "q1b_options": q1b_map, "q1b_gold": q1b_gold,
            "q2_text": q2_text, "q2_options": q2_map, "q2_gold": q2_gold,
            "q3_text": q3_text, "q3_options": q3_map, "q3_gold": q3_gold,
        })
    rng.shuffle(items)
    return items


def rate(rows: list[dict], field: str) -> str:
    if not rows:
        return "0/0"
    correct = sum(1 for row in rows if row.get(field))
    return f"{correct}/{len(rows)} = {100 * correct / len(rows):.1f}%"


def summarize(rows: list[dict]) -> dict:
    done = [row for row in rows if not row.get("error")]
    by_voc_d1: dict[str, list[dict]] = defaultdict(list)
    by_voc_d2: dict[str, list[dict]] = defaultdict(list)
    for row in done:
        by_voc_d1[row["gold_vocalization_d1"]].append(row)
        by_voc_d2[row["gold_vocalization_d2"]].append(row)
    all_correct = [
        r for r in done
        if r.get("q1a_correct") and r.get("q1b_correct") and r.get("q2_correct") and r.get("q3_correct")
    ]
    both_ids_correct = [r for r in done if r.get("q1a_correct") and r.get("q1b_correct")]
    either_id_wrong = [r for r in done if r not in both_ids_correct]
    return {
        "n": len(done),
        "errors": len(rows) - len(done),
        "q1a_dialogue1_id": rate(done, "q1a_correct"),
        "q1b_dialogue2_id": rate(done, "q1b_correct"),
        "q2_interpretation_matching": rate(done, "q2_correct"),
        "q3_response_matching": rate(done, "q3_correct"),
        "all_four_correct": (
            f"{len(all_correct)}/{len(done)} = {100 * len(all_correct) / len(done):.1f}%" if done else "0/0"
        ),
        "matching_when_both_ids_correct": rate(both_ids_correct, "q2_correct"),
        "matching_when_an_id_missed": rate(either_id_wrong, "q2_correct"),
        "q1_by_vocalization": {
            v: rate(by_voc_d1.get(v, []) + [], "q1a_correct")
            for v in sorted(set(by_voc_d1) | set(by_voc_d2))
        },
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

    print(f"{len(items)} item(s) · model {args.model} · seed {args.seed}", flush=True)

    rows: list[dict] = []
    for index, item in enumerate(items, start=1):
        if item["item_id"] in done:
            rows.append(done[item["item_id"]])
            continue
        row = {k: v for k, v in item.items() if not k.endswith("_text")}
        try:
            pcm_d1 = mp3_to_pcm16_24k(REPO / item["audio_d1"])
            pcm_d2 = mp3_to_pcm16_24k(REPO / item["audio_d2"])
            result: dict | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    result = query_one(client, item, pcm_d1, pcm_d2, args.model)
                    break
                except Exception as exc:
                    if attempt == MAX_ATTEMPTS:
                        raise
                    wait = 2 ** attempt
                    print(f"    retry in {wait}s: {type(exc).__name__}: {exc}", flush=True)
                    time.sleep(wait)
            assert result is not None
            for qkey in ("q1a", "q1b", "q2", "q3"):
                q = result[qkey]
                letter = q["letter"]
                row[f"{qkey}_raw"] = q["raw_text"]
                row[f"{qkey}_predicted"] = letter
                row[f"{qkey}_predicted_text"] = item[f"{qkey}_options"].get(letter) if letter else None
                row[f"{qkey}_correct"] = letter == item[f"{qkey}_gold"]
            row["usage"] = {qk: result[qk]["usage"] for qk in ("q1a", "q1b", "q2", "q3")}
            print(
                f"[{index}/{len(items)}] {item['item_id']:24} "
                f"Q1a {'ok' if row['q1a_correct'] else 'X '} "
                f"Q1b {'ok' if row['q1b_correct'] else 'X '} "
                f"Q2 {'ok' if row['q2_correct'] else 'X '} "
                f"Q3 {'ok' if row['q3_correct'] else 'X '}",
                flush=True,
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(items)}] {item['item_id']:24} failed: {exc}", flush=True)
        rows.append(row)

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({
                "model": args.model, "seed": args.seed,
                "manifest": str(args.manifest.relative_to(REPO)),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "summary": summarize(rows), "rows": rows,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    summary = summarize(rows)
    print("\n" + "=" * 66)
    print(f"Q1a Dialogue-1 sound ID (6-way, chance 16.7%): {summary['q1a_dialogue1_id']}")
    print(f"Q1b Dialogue-2 sound ID (6-way, chance 16.7%): {summary['q1b_dialogue2_id']}")
    print(f"Q2  interpretation matching (2-way, chance 50%): {summary['q2_interpretation_matching']}")
    print(f"Q3  response matching (2-way, chance 50%):       {summary['q3_response_matching']}")
    print(f"all four correct:                                {summary['all_four_correct']}")
    print(f"  matching (Q2) when both sounds ID'd: {summary['matching_when_both_ids_correct']}")
    print(f"  matching (Q2) when a sound was missed: {summary['matching_when_an_id_missed']}")
    if summary["errors"]:
        print(f"\n{summary['errors']} item(s) errored")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

"""The test itself: each model joins the conversation as a third friend, then says what it heard.

Every trial is a fresh session with one condition of one item, so nothing a model learns from
the happy version can inform its answer to the sad one. Within the session it does two things,
in this order:

    1. takes its turn — spoken, captured as audio and text
    2. answers what non-speech sounds it heard, how many, and in which turns

The order matters. Asking about the sounds first would tell the model that sounds are the point
and turn the conversational turn into a demonstration; asking afterwards leaves turn 1 an
honest reaction. Nothing in the instruction mentions vocalizations, tone, or that there are
three versions of anything.

4 models × 20 items × 3 conditions = 240 sessions. Resumable: each trial is written as it
completes and a rerun skips what is already recorded, retrying only failures.

Usage:
    python benchmark/test_models.py --limit 1
    python benchmark/test_models.py --providers qwen,gemini
    python benchmark/test_models.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = HERE / "out" / "audio_manifest.json"
TRIALS = HERE / "out" / "trials.jsonl"
RESPONSE_DIR = HERE / "out" / "responses"

CONDITIONS = ("neutral", "happy", "sad")
CONCURRENCY = {"openai": 3, "grok": 3, "gemini": 3, "qwen": 3}
RETRIES = 3

# Nothing here hints that vocalizations are the subject, or that the same conversation exists
# in other versions. "Two of your friends" is the whole framing.
#
# The situation is the EmpatheticDialogues seed, shifted out of first person: it tells the
# model what happened without telling it how anyone feels about it, which is the only thing
# the audio decides. It is the same text in all three conditions.
TASK = (
    "You are having a conversation with two people. You will hear them talking to each "
    "other.\n\n"
    "Here is what the conversation is about: {situation}\n\n"
    "When they finish, it is your turn to speak. Respond naturally as the third speaker in "
    "the conversation."
)

# Asked only after the reply exists, so none of it can shape the reply. The order runs from
# least leading to most: the turn itself, then whether anything non-speech was there at all,
# then the atmosphere. Asking about atmosphere first would tell the model that mood is the
# subject.
FOLLOWUPS = [
    (
        "heard",
        "Now a separate question about the recording itself. Apart from the words, did you "
        "hear any non-speech sounds in the conversation:\n"
        "A. laughter\n"
        "B. sigh\n"
        "C. neither\n"
        "D. both\n\n"
        "Answer with the letter, then — unless you answered C — list each one. Answer in "
        "exactly this format, one line per kind of vocalization, and nothing else:\n"
        "ANSWER: <letter>\n"
        "VOCALIZATION: <name> | COUNT: <how many times>"
    ),
    (
        "atmosphere",
        "How would you characterize the overall conversational atmosphere?"
    ),
]

_lock = threading.Lock()


def pcm16_to_mp3(data: bytes, rate: int, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                    "-c:a", "libmp3lame", "-q:a", "3", str(dest)],
                   input=data, capture_output=True, check=True)


def done_trials() -> set[tuple[str, str, str]]:
    if not TRIALS.exists():
        return set()
    done = set()
    for line in TRIALS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if "error" not in row:
                done.add((row["provider"], row["item_id"], row["condition"]))
    return done


def record(row: dict) -> None:
    with _lock:
        with TRIALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_trial(provider: str, item: dict, condition: str) -> dict:
    """One session: hear the conversation, take a turn, then report what was heard."""
    audio = REPO / item["conditions"][condition]["path"]
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            starts = [t["start"] for t in item["conditions"][condition]["timeline"]
                      if t["kind"] == "speech"]
            situation = item.get("situation_third_person") or item["situation"]
            out = P.converse(provider, audio, TASK.format(situation=situation),
                             [q for _, q in FOLLOWUPS], boundaries=starts)
            stem = f"{provider}_{item['item_id']}_{condition}"
            reply_mp3 = RESPONSE_DIR / f"{stem}.mp3"
            if out.get("response_pcm"):
                pcm16_to_mp3(out["response_pcm"], out.get("pcm_rate", 24000), reply_mp3)
            row = {"provider": provider, "model": P.MODELS[provider],
                   "item_id": item["item_id"], "condition": condition,
                   "audio": item["conditions"][condition]["path"],
                   "situation": situation,
                   "response": out["response"],
                   **{key: answer for (key, _), answer
                      in zip(FOLLOWUPS, out["answers"])},
                   "response_audio": (str(reply_mp3.relative_to(REPO))
                                      if out.get("response_pcm") else None),
                   "attempts": attempt}
            record(row)
            return row
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:200]}"
            time.sleep(2 ** attempt)
    row = {"provider": provider, "model": P.MODELS[provider], "item_id": item["item_id"],
           "condition": condition, "error": last}
    record(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default=",".join(P.PROVIDERS))
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--limit", type=int, help="first N items only")
    parser.add_argument("--only", action="append", help="item id (repeatable)")
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chosen = [p.strip() for p in args.providers.split(",") if p.strip()]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    if args.only:
        items = [i for i in items if i["item_id"] in args.only]
    if args.limit:
        items = items[: args.limit]

    if args.fresh and TRIALS.exists():
        TRIALS.unlink()
    done = done_trials()
    todo = [(p, item, c) for item in items for c in conditions for p in chosen
            if (p, item["item_id"], c) not in done]
    total = len(items) * len(conditions) * len(chosen)
    print(f"{len(items)} items × {len(conditions)} conditions × {len(chosen)} models "
          f"= {total} trials · {total - len(todo)} recorded · {len(todo)} to run", flush=True)

    pools = {p: ThreadPoolExecutor(max_workers=CONCURRENCY.get(p, 3),
                                   thread_name_prefix=p) for p in chosen}
    futures = {pools[p].submit(run_trial, p, item, c): (p, item, c)
               for p, item, c in todo}
    finished = 0
    try:
        for future in as_completed(futures):
            provider, item, condition = futures[future]
            row = future.result()
            finished += 1
            if "error" in row:
                print(f"  [{finished:3}/{len(todo)}] {provider:7} {item['item_id']} "
                      f"{condition:8} FAILED {row['error'][:70]}", flush=True)
            else:
                print(f"  [{finished:3}/{len(todo)}] {provider:7} {item['item_id']} "
                      f"{condition:8} {row['response'][:64]}", flush=True)
    finally:
        for pool in pools.values():
            pool.shutdown(wait=True)

    rows = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines() if l.strip()]
    good = [r for r in rows if "error" not in r]
    print(f"\n{len(good)} trial(s) recorded")
    by = Counter(r["provider"] for r in good)
    for provider in chosen:
        print(f"  {provider:8} {by[provider]:3}/{len(items) * len(conditions)}")
    (HERE / "out" / "trials_meta.json").write_text(json.dumps({
        "models": {p: P.MODELS[p] for p in chosen}, "task": TASK, "followups": {k: q for k, q in FOLLOWUPS},
        "conditions": conditions, "run_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

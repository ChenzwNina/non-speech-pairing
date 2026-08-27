"""Stage 11 — play each condition to each model and collect its turn, then two questions.

Every tested model hears all three conditions and takes a turn in each. Only happy and sad are
scored: the neutral response exists so Q1's ranking has a third response to rank against.
Neutral is therefore asked nothing further — no follow-ups, no perception question.

Order matters and runs least-leading first. The turn comes before any question, so nothing in
the questions can shape the reply. Then Q3 asks how the speakers treat the story, which never
mentions sound; only then does Q4 name vocalizations. Reversing them would tell the model that
non-speech sound is the subject before it had to commit to a reading.

The four Q3 options are shuffled per trial and the four Q4 options with them, seeded from the
trial so a rerun asks the same question. The letter the gold landed on is recorded, because a
fixed gold letter is the easiest thing in a benchmark to score well on for the wrong reason.

    python 2.0/test_models.py                       # four models, three conditions
    python 2.0/test_models.py --providers grok      # one model
    python 2.0/test_models.py --only emb_003
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import providers as P

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MANIFEST = OUT / "audio_manifest.json"
TRIALS = OUT / "trials.jsonl"
RESPONSE_DIR = OUT / "responses"

CONDITIONS = ("neutral", "happy", "sad")
SCORED = ("happy", "sad")
CONCURRENCY = {"openai": 3, "grok": 1, "gemini": 3, "qwen": 3}
RETRIES = 3

# Nothing here hints that vocalizations are the subject, or that the same conversation exists
# in other versions. The situation is the EmpatheticDialogues seed shifted out of first person:
# it says what happened without saying how anyone feels about it, which is the only thing the
# audio decides. Identical text in all three conditions.
TASK = (
    "You are going to listen to a conversation between two speakers.\n\n"
    "Here is what the conversation is about: {situation}\n\n"
    "After listening, respond as a third speaker in the conversation."
)

Q3 = ("Now a separate question about the conversation you just heard. How do the two speakers "
      "treat the story?\n{options}\n\nAnswer with one letter and nothing else.")

Q4 = ("One more question about the recording itself. Apart from the words, what non-speech "
      "vocalization did you hear in the conversation?\n{options}\n\nAnswer with one letter and "
      "nothing else.")

# Q4's wrong options. Other vocalizations a model might plausibly report, none of which is ever
# present: the clips only ever contain laughter or a sigh.
Q4_DISTRACTORS = ("a gasp", "a yawn", "sobbing", "a grunt", "a throat clear")
Q4_REAL = {"happy": "laughter", "sad": "a sigh"}

_lock = threading.Lock()


def lettered(options: list[str]) -> str:
    return "\n".join(f"{chr(65 + n)}. {text}" for n, text in enumerate(options))


def question_set(item_id: str, provider: str, condition: str, q3: dict) -> dict:
    """Both multiple-choice questions, shuffled reproducibly from the trial identity."""
    seed = int(hashlib.sha256(f"{provider}:{item_id}:{condition}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    gold3 = q3["happy"] if condition == "happy" else q3["sad"]
    choices3 = [q3["happy"], q3["sad"], *q3["wrong"]]
    rng.shuffle(choices3)

    other = "a sigh" if condition == "happy" else "laughter"
    gold4 = Q4_REAL[condition]
    choices4 = [gold4, other, *rng.sample(Q4_DISTRACTORS, 2)]
    rng.shuffle(choices4)

    return {"q3_options": choices3, "q3_gold_letter": chr(65 + choices3.index(gold3)),
            "q3_gold": gold3,
            "q4_options": choices4, "q4_gold_letter": chr(65 + choices4.index(gold4)),
            "q4_gold": gold4}


def pcm16_to_mp3(data: bytes, rate: int, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                    "-c:a", "libmp3lame", "-q:a", "3", str(dest)],
                   input=data, capture_output=True, check=True)


def done_trials() -> set[tuple[str, str, str]]:
    """Only completed trials resume. An error is not a trial."""
    if not TRIALS.exists():
        return set()
    done = set()
    for line in TRIALS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if "error" not in row and row.get("response"):
                done.add((row["provider"], row["item_id"], row["condition"]))
    return done


def record(row: dict) -> None:
    with _lock:
        with TRIALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_trial(provider: str, item: dict, condition: str, q3: dict) -> dict:
    """One session: hear the conversation, take a turn, then answer what is asked."""
    entry = item["conditions"][condition]
    audio = HERE / entry["path"]
    situation = item.get("situation_third_person") or item["situation"]
    asked = question_set(item["item_id"], provider, condition, q3) if condition in SCORED else {}
    followups = ([Q3.format(options=lettered(asked["q3_options"])),
                  Q4.format(options=lettered(asked["q4_options"]))]
                 if asked else [])

    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            starts = [t["start"] for t in entry["timeline"] if t["kind"] == "speech"]
            out = P.converse(provider, audio, TASK.format(situation=situation),
                             followups, boundaries=starts)
            stem = f"{provider}_{item['item_id']}_{condition}"
            reply_mp3 = RESPONSE_DIR / f"{stem}.mp3"
            if out.get("response_pcm"):
                pcm16_to_mp3(out["response_pcm"], out.get("pcm_rate", 24000), reply_mp3)
            row = {"provider": provider, "model": P.MODELS[provider],
                   "item_id": item["item_id"], "condition": condition,
                   "scored": condition in SCORED,
                   "audio": entry["path"], "situation": situation,
                   "response": out["response"],
                   "response_audio": (str(reply_mp3.relative_to(HERE))
                                      if out.get("response_pcm") else None),
                   "attempts": attempt, **asked}
            if followups:
                row["q3_answer"] = out["answers"][0]
                row["q4_answer"] = out["answers"][1]
            record(row)
            return row
        except Exception as exc:                    # noqa: BLE001 - recorded, then retried
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
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chosen = [p.strip() for p in args.providers.split(",") if p.strip()]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    items = json.loads(MANIFEST.read_text())["items"]
    options = {e["item_id"]: e for e in json.loads((OUT / "q3_options.json").read_text())["items"]}
    if args.only:
        items = [i for i in items if i["item_id"] in args.only]
    if args.limit:
        items = items[: args.limit]
    missing = [i["item_id"] for i in items if i["item_id"] not in options]
    if missing:
        raise SystemExit(f"no Q3 options for {missing}; run make_options.py first")

    if args.fresh and TRIALS.exists():
        TRIALS.unlink()
    done = done_trials()
    todo = [(p, item, c) for item in items for c in conditions for p in chosen
            if (p, item["item_id"], c) not in done]
    print(f"{len(items)} items x {len(conditions)} conditions x {len(chosen)} models = "
          f"{len(items) * len(conditions) * len(chosen)} trials · {len(done)} already done · "
          f"{len(todo)} to run\n")

    results = []
    pools = {p: ThreadPoolExecutor(max_workers=CONCURRENCY.get(p, 3),
                                  thread_name_prefix=p) for p in chosen}
    try:
        futures = {pools[p].submit(run_trial, p, item, c, options[item["item_id"]]):
                   (p, item["item_id"], c) for p, item, c in todo}
        for n, future in enumerate(as_completed(futures), start=1):
            provider, item_id, condition = futures[future]
            row = future.result()
            results.append(row)
            mark = "ERROR" if "error" in row else (row["response"] or "")[:52].replace("\n", " ")
            print(f"  [{n}/{len(todo)}] {provider:7} {item_id} {condition:8} {mark!r}",
                  flush=True)
    finally:
        for pool in pools.values():
            pool.shutdown(wait=True)

    errors = [r for r in results if "error" in r]
    print(f"\n{len(results)} trials · {len(errors)} errors")
    for row in errors[:10]:
        print(f"  {row['provider']:7} {row['item_id']} {row['condition']:8} {row['error']}"[:160])
    print(f"wrote {TRIALS.name}")
    usage = P.usage_summary()
    if usage:
        print("token usage:", json.dumps(usage))


if __name__ == "__main__":
    main()

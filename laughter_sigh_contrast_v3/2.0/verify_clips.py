"""Stage 8 — does each clip actually contain the sound it was written to be?

The rule is the spec's: draw **two** of the four S2S models at random, ask each "Does the clip
contain {vocalization}? A. yes B. no" at its default effort, and keep the clip only if **both**
say yes. Both no, or a one-yes-one-no split, sends the clip back to ElevenLabs for another take
which the **same two** judges then re-hear. Three attempts, then it is reported as unresolved
rather than quietly kept.

Two judges with unanimity is a stricter gate than 1.0's four-model majority, where a 3-1 pass
let a clip through on one dissent. It is also cheaper, which is what makes a per-clip retry
loop affordable at 410 clips.

If a judge does not respond at all, it is asked once more with the same audio. Still nothing,
and the clip goes to regeneration — a silent judge is not a verdict, and 1.0's void grok
verdicts came precisely from treating one as if it were.

The judge pair is drawn from the clip's own path, so a rerun asks the same two models and the
verdicts stay comparable across rounds.

    python 2.0/verify_clips.py
    python 2.0/verify_clips.py --only emb_003
    python 2.0/verify_clips.py --workers 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P
from make_audio import MIN_CLIP, MAX_CLIP, MIN_DB, duration_of, mean_db, normalize, synthesize

HERE = Path(__file__).resolve().parent
FAMILY = HERE.parent          # laughter_sigh_contrast/, holding both versions
REPO = FAMILY.parent         # the repository root, where .env and archive/ live
OUT = HERE / "out"
MANIFEST = OUT / "clip_manifest.json"
ANSWERS = OUT / "clip_verdicts.jsonl"
VERDICTS = OUT / "clip_verdicts.json"

QUESTION = {
    "happy": "You will hear one short audio clip. Does the clip contain laughter? "
             "A. yes  B. no. Answer with one letter and nothing else.",
    "sad": "You will hear one short audio clip. Does the clip contain a sigh? "
           "A. yes  B. no. Answer with one letter and nothing else.",
}
# grok is not a judge. It answered yes to 25% of sigh clips where these three answered
# 98-100%, went silent on sigh audio 39 times against 2 for laughter, and denied real human
# sigh recordings 3 times out of 5. Every one of the 53 clips that failed the first pass had
# grok as a drawn judge; no clip judged by a grok-free pair failed at all. It remains a tested
# model in stage 11 — being deaf to sighs is a result worth reporting, not a reason to let it
# screen the stimuli. See out/grok_sigh_control.json.
JUDGES = ("openai", "gemini", "qwen")
NEEDED = 2              # judges per clip
MAX_ROUNDS = 3          # regenerations of the same token
NO_RESPONSE_TRIES = 2   # the spec's "try it one more time with the same audio"

# grok is one session at a time. Concurrent realtime sessions are not refused — they connect,
# take the audio, and then never produce response.created — so parallelism there buys nothing
# and costs the wall-clock of every timeout.
LIMITS = {"openai": 3, "grok": 1, "gemini": 3, "qwen": 3}

_sema = {name: threading.Semaphore(n) for name, n in LIMITS.items()}
_lock = threading.Lock()


def verdict_of(answer: str) -> str:
    """A / yes -> yes, B / no -> no. Anything else is not a verdict."""
    text = (answer or "").strip().lower()
    if re.match(r"^\W*a\b", text) or re.search(r"\byes\b", text):
        return "yes"
    if re.match(r"^\W*b\b", text) or re.search(r"\bno\b|\bnot\b", text):
        return "no"
    return "unclear"


def judges_for(path: str) -> list[str]:
    """Two judges, drawn from the clip's path so the draw survives a rerun."""
    seed = int(hashlib.sha256(path.encode()).hexdigest()[:8], 16)
    return sorted(random.Random(seed).sample(JUDGES, NEEDED))


def record(row: dict) -> None:
    with _lock:
        with ANSWERS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recorded() -> dict[tuple[str, str, int], dict]:
    """Only real verdicts resume. An error is not an answer, and counting it as one is how
    1.0's first verification pass came to think it was finished."""
    if not ANSWERS.exists():
        return {}
    out = {}
    for line in ANSWERS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("verdict") in {"yes", "no"}:
            out[(row["path"], row["provider"], row["round"])] = row
    return out


def ask_one(clip: dict, provider: str, round_no: int, done: dict) -> dict:
    key = (clip["path"], provider, round_no)
    if key in done:
        return done[key]
    last = ""
    for attempt in range(1, NO_RESPONSE_TRIES + 1):
        try:
            with _sema[provider]:
                answer = P.ask(provider, HERE / clip["path"], QUESTION[clip["condition"]])
            verdict = verdict_of(answer)
            row = {"path": clip["path"], "provider": provider, "round": round_no,
                   "answer": (answer or "").strip()[:200], "verdict": verdict,
                   "attempt": attempt}
            if verdict in {"yes", "no"}:
                record(row)
                return row
            last = f"unclear: {(answer or '')[:80]!r}"
        except Exception as exc:                        # noqa: BLE001 - recorded, then retried
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
            time.sleep(2 * attempt)
    row = {"path": clip["path"], "provider": provider, "round": round_no,
           "error": last, "verdict": "no_response"}
    record(row)
    return row


def remake(clip: dict, speech_db: float) -> bool:
    """Another take of the same written sound, re-levelled. Mechanical gates only."""
    from elevenlabs import ElevenLabs
    eleven = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"].strip())
    dest = HERE / clip["path"]
    for _ in range(3):
        synthesize(eleven, clip["token"], clip["speaker"], dest)
        seconds, db = duration_of(dest), mean_db(dest)
        if MIN_CLIP <= seconds <= MAX_CLIP and db is not None and db >= MIN_DB:
            normalize(dest, speech_db)
            return True
    return False


def resolve(clip: dict, speech_db: float, done: dict) -> dict:
    """One clip through up to MAX_ROUNDS takes, judged by the same two models each time."""
    pair = judges_for(clip["path"])
    rounds = []
    for round_no in range(1, MAX_ROUNDS + 1):
        answers = {p: ask_one(clip, p, round_no, done) for p in pair}
        verdicts = {p: row["verdict"] for p, row in answers.items()}
        yes = sum(v == "yes" for v in verdicts.values())
        silent = [p for p, v in verdicts.items() if v == "no_response"]
        rounds.append({"round": round_no, "verdicts": verdicts})
        if yes == NEEDED:
            return {**clip_key(clip), "judges": pair, "status": "kept",
                    "round": round_no, "rounds": rounds}
        reason = ("no response from " + ", ".join(silent)) if silent else \
                 ("both no" if yes == 0 else "split")
        if round_no < MAX_ROUNDS:
            print(f"    {Path(clip['path']).name}: {reason} -> new take "
                  f"({round_no + 1}/{MAX_ROUNDS})", flush=True)
            if not remake(clip, speech_db):
                return {**clip_key(clip), "judges": pair, "status": "unmakeable",
                        "round": round_no, "rounds": rounds}
    return {**clip_key(clip), "judges": pair, "status": "unresolved",
            "round": MAX_ROUNDS, "rounds": rounds}


def clip_key(clip: dict) -> dict:
    return {k: clip[k] for k in ("path", "item_id", "condition", "order", "turn",
                                 "after_word", "token", "kind", "speaker")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(MANIFEST.read_text())
    items = json.loads((OUT / "items.json").read_text())["items"]
    turn_dir = FAMILY / "1.0" / "out" / "audio_turns"
    by_item = {i["item_id"]: i for i in items}

    entries = [e for e in manifest["items"]
               if not args.only or e["item_id"] in args.only]
    if args.limit:
        entries = entries[: args.limit]
    clips = [c for e in entries for c in e["clips"]]
    if not clips:
        raise SystemExit("no clips to verify; run make_audio.py first")

    # Speech level per item, so a remade clip is levelled against the same speech as the first.
    speech_db = {}
    for entry in entries:
        takes = [turn_dir / t["take"].split("/")[-1]
                 for t in by_item[entry["item_id"]]["turns"]]
        levels = [d for d in (mean_db(p) for p in takes) if d is not None]
        speech_db[entry["item_id"]] = sum(levels) / max(1, len(levels))

    done = recorded()
    print(f"{len(clips)} clips · {len(done)} verdicts already recorded · "
          f"{NEEDED} judges each, unanimous yes to keep\n")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(resolve, clip, speech_db[clip["item_id"]], done): clip
                   for clip in clips}
        for n, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            if n % 25 == 0 or result["status"] != "kept":
                kept = sum(r["status"] == "kept" for r in results)
                print(f"  [{n}/{len(clips)}] {kept} kept · "
                      f"{Path(result['path']).name} {result['status']}", flush=True)

    order = {c["path"]: n for n, c in enumerate(clips)}
    results.sort(key=lambda r: order[r["path"]])
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    VERDICTS.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judges": list(JUDGES), "judges_per_clip": NEEDED,
        "rule": "both judges must answer yes; otherwise regenerate and re-ask the same two",
        "max_rounds": MAX_ROUNDS, "counts": counts, "clips": results},
        indent=2, ensure_ascii=False) + "\n")

    print(f"\n{len(results)} clips")
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:12} {n:4}  ({n/len(results):.0%})")
    first = sum(1 for r in results if r["status"] == "kept" and r["round"] == 1)
    print(f"  kept on the first take: {first}/{len(results)} ({first/len(results):.0%})")
    print(f"\nwrote {VERDICTS.name}")


if __name__ == "__main__":
    main()

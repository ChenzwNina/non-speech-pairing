"""Ask four models a yes-or-no question about each clip, and remake the ones that fail.

The earlier version asked an open question — "what do you hear, one of laugh / sigh / breath /
word / other / nothing" — and the answers turned into a vocabulary argument. Gemini called
seven sighs "breath", openai called fourteen of them "word" because `[sigh] ugh` contains a
written syllable, and each disagreement needed a human to decide whether the clip was wrong
or the label was. None of that is what we wanted to know.

So the question is now the one that actually matters:

    is this the sound of a person laughing?   YES / NO
    is this the sound of a person sighing?    YES / NO

Three of four models saying yes is a pass. Anything less and the clip goes back to ElevenLabs
for another take, up to three attempts, because a clip that three listeners cannot recognise
is a bad clip — not a hard item. What survives three failed attempts is left in place and
listed for a person to listen to.

Verdicts are appended as they arrive and a rerun re-votes only what has no verdict yet, so an
interrupted run costs nothing.

Usage:
    python benchmark/verify_clips.py --limit 8
    python benchmark/verify_clips.py
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import providers as P
from make_audio import MIN_CLIP, MAX_CLIP, MIN_DB, duration_of, mean_db, normalize, synthesize

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = HERE / "out" / "audio_manifest.json"
ANSWERS = HERE / "out" / "clip_verdicts.jsonl"
VOTES = HERE / "out" / "clip_verdicts.json"
REVIEW = HERE / "out" / "clip_review.md"

QUESTION = {
    "happy": "You will hear one short audio clip. Answer with one word, YES or NO: "
             "is this the sound of a person laughing?",
    "sad": "You will hear one short audio clip. Answer with one word, YES or NO: "
           "is this the sound of a person sighing?",
}
SOUND = {"happy": "laughing", "sad": "sighing"}

# grok is one-at-a-time. Extra concurrent realtime sessions are not refused — they connect,
# accept the audio, commit the buffer, and then ping forever without ever producing
# response.created, so they die on the 180s timeout and retry into the same wall. One clip
# took ten minutes that way; serially each takes about five seconds.
CONCURRENCY = {"openai": 3, "grok": 1, "gemini": 3, "qwen": 3}
MIN_AGREE = 3          # of four; two-two is a tie, not a majority
MAX_ROUNDS = 3
RETRIES = 3

_lock = threading.Lock()


def verdict_of(answer: str) -> str:
    text = (answer or "").strip().lower()
    if re.search(r"\byes\b", text):
        return "yes"
    if re.search(r"\bno\b|\bnot\b", text):
        return "no"
    return "unclear"


def record(row: dict) -> None:
    with _lock:
        with ANSWERS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recorded() -> dict[tuple[str, str, int], dict]:
    if not ANSWERS.exists():
        return {}
    out = {}
    for line in ANSWERS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if "error" not in row:
                out[(row["path"], row["provider"], row["round"])] = row
    return out


def ask_one(clip: dict, provider: str, round_no: int) -> dict:
    path = REPO / clip["path"]
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            answer = P.ask(provider, path, QUESTION[clip["condition"]])
            row = {"path": clip["path"], "provider": provider, "round": round_no,
                   "answer": answer.strip()[:200], "verdict": verdict_of(answer)}
            record(row)
            return row
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:150]}"
            time.sleep(2 ** attempt)
    row = {"path": clip["path"], "provider": provider, "round": round_no, "error": last,
           "verdict": "error"}
    record(row)
    return row


def remake(clip: dict, speech_db: float) -> bool:
    """Another take of the same token, re-levelled. Mechanical gates only."""
    import os
    from elevenlabs import ElevenLabs
    eleven = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"].strip())
    dest = REPO / clip["path"]
    for _ in range(3):
        synthesize(eleven, clip["token"], clip["speaker"], dest, 0.30)
        seconds, db = duration_of(dest), mean_db(dest)
        if MIN_CLIP <= seconds <= MAX_CLIP and db is not None and db >= MIN_DB:
            normalize(dest, speech_db)
            return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default=",".join(P.PROVIDERS))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chosen = [p.strip() for p in args.providers.split(",") if p.strip()]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    speech_db = {}
    clips = []
    for item in manifest["items"]:
        levels = [c.get("db_after") or c["db"] for c in item["clips"]]
        speech_db[item["item_id"]] = (sum(levels) / len(levels)) if levels else -20.0
        for clip in item["clips"]:
            clips.append({**clip, "item_id": item["item_id"]})
    if args.limit:
        clips = clips[: args.limit]

    if args.fresh and ANSWERS.exists():
        ANSWERS.unlink()

    pending = {c["path"]: c for c in clips}
    passed: dict[str, dict] = {}
    history: dict[str, list] = {c["path"]: [] for c in clips}

    for round_no in range(1, args.rounds + 1):
        if not pending:
            break
        done = recorded()
        todo = [(clip, provider) for clip in pending.values() for provider in chosen
                if (clip["path"], provider, round_no) not in done]
        print(f"\n=== round {round_no} · {len(pending)} clip(s) · {len(todo)} session(s) ===",
              flush=True)

        # grok runs inline. Inside a worker thread its realtime sessions connect, take the
        # audio, commit the buffer and then ping forever without ever emitting
        # response.created — every one dies on the 180s timeout. The same call in the main
        # thread answers in about five seconds, every time, even while other providers are
        # in flight. So it is not concurrency between providers, it is the thread.
        inline = [(c, p) for c, p in todo if CONCURRENCY.get(p, 3) == 1]
        pooled = [(c, p) for c, p in todo if CONCURRENCY.get(p, 3) > 1]

        finished = 0
        pools = {p: ThreadPoolExecutor(max_workers=CONCURRENCY.get(p, 3),
                                       thread_name_prefix=p)
                 for p in {p for _, p in pooled}}
        futures = {pools[p].submit(ask_one, clip, p, round_no): (clip, p)
                   for clip, p in pooled}
        try:
            for future in as_completed(futures):
                future.result()
                finished += 1
                if finished % 25 == 0:
                    print(f"  pooled {finished}/{len(pooled)}", flush=True)
        finally:
            for pool in pools.values():
                pool.shutdown(wait=True)

        for index, (clip, provider) in enumerate(inline, 1):
            row = ask_one(clip, provider, round_no)
            if index % 10 == 0 or "error" in row:
                print(f"  {provider} {index}/{len(inline)} "
                      f"{row.get('verdict')}", flush=True)

        done = recorded()
        still: dict[str, dict] = {}
        for path, clip in pending.items():
            verdicts = {p: done[(path, p, round_no)]["verdict"]
                        for p in chosen if (path, p, round_no) in done}
            yes = sum(1 for v in verdicts.values() if v == "yes")
            history[path].append({"round": round_no, "yes": yes, "verdicts": verdicts})
            if yes >= MIN_AGREE:
                passed[path] = {**clip, "yes": yes, "round": round_no,
                                "verdicts": verdicts}
            else:
                still[path] = clip
                print(f"  fail {Path(path).name:44} {yes}/{len(verdicts)} yes  {verdicts}",
                      flush=True)

        pending = still
        if pending and round_no < args.rounds:
            print(f"  remaking {len(pending)} clip(s)", flush=True)
            for clip in pending.values():
                remake(clip, speech_db.get(clip["item_id"], -20.0))

    results = []
    for clip in clips:
        path = clip["path"]
        results.append({**{k: clip[k] for k in ("item_id", "condition", "turn", "position",
                                                "token", "speaker", "path")},
                        "asked": SOUND[clip["condition"]],
                        "passed": path in passed,
                        "rounds": history[path]})
    VOTES.write_text(json.dumps({
        "models": {p: P.MODELS[p] for p in chosen}, "questions": QUESTION,
        "min_agree": MIN_AGREE, "max_rounds": args.rounds,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": len(passed), "failed": len(clips) - len(passed), "clips": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    failed = [r for r in results if not r["passed"]]
    lines = ["# Clips still unrecognised after three takes", "",
             f"{len(failed)} of {len(results)} clips never got {MIN_AGREE} of "
             f"{len(chosen)} models to say yes. The audio is in place — listen and decide "
             "whether to keep, hand-fix, or drop.", "",
             "| clip | asked | token | best round |", "| --- | --- | --- | --- |"]
    for row in failed:
        best = max((r["yes"] for r in row["rounds"]), default=0)
        lines.append(f"| `{Path(row['path']).name}` | {row['asked']} | "
                     f"`{row['token']}` | {best}/4 yes |")
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n{len(passed)}/{len(clips)} passed · {len(failed)} for your ear")
    by_round = Counter(passed[p]["round"] for p in passed)
    for r in sorted(by_round):
        print(f"  passed on round {r}: {by_round[r]}")
    agree = Counter()
    for path, rounds in history.items():
        if rounds:
            for provider, verdict in rounds[-1]["verdicts"].items():
                agree[(provider, verdict)] += 1
    print("\nlast-round verdicts per model:")
    for provider in chosen:
        yes, no, unclear = (agree[(provider, "yes")], agree[(provider, "no")],
                            agree[(provider, "unclear")])
        total = yes + no + unclear
        if total:
            print(f"  {provider:8} yes {yes:3}  no {no:3}  unclear {unclear:3}")


if __name__ == "__main__":
    main()

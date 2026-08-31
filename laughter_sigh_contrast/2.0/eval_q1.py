"""Q1 — answer appropriateness, by pairwise ranking against the other conditions' replies.

There is no gold reply. Instead: take the reply a model gave after hearing one condition, and
ask a judge which of two replies suits that conversation better — this one, or the reply the
same model gave after hearing a different condition. If the sounds changed how the model
answered, its own reply for this condition should win. If the sounds changed nothing, the three
replies are interchangeable and the judge is choosing at random.

Each scored reply faces two comparisons: against the neutral reply and against the other
scored condition's reply. Both sides come from the same model, so the comparison is insensitive
to how eloquent a model is in general — only to whether it answered *this* condition
differently and better.

Judges are text-only and see the transcript with the vocalizations tagged, since that is what
makes one reply more apt than the other. Three vendors, one judgement each, averaged: Claude
Opus 5, GPT-5.6-Terra and Grok-4.6. Presentation order is randomized per comparison, and the
position the correct reply landed in is recorded — a judge with a first-slot habit would
otherwise look like a signal.

Reported as the proportion of comparisons won, so 50% is chance and the number is comparable
with 1.0's 60-63%.

    python 2.0/eval_q1.py
    python 2.0/eval_q1.py --judges opus,terra
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TRIALS = OUT / "trials.jsonl"
VOTES = OUT / "eval_q1_votes.jsonl"
RESULT = OUT / "eval_q1.json"

SCORED = ("happy", "sad")
JUDGES = ("opus", "terra", "grok")

SYSTEM = """You judge which of two replies better suits a conversation you are shown.

You are given a short conversation between two friends, written out with its non-speech sounds
marked in place — laughter or sighs, exactly where they occurred. Then two replies, each from
someone joining as a third speaker.

Decide which reply is more appropriate as a third speaker's response to *this* conversation,
attending to the non-speech sounds as much as to the words. The sounds are not decoration:
they carry how the two speakers are treating what happened, and a reply that misreads them is
less appropriate however well written it is.

The two replies may be similar. Choose anyway, on the balance of fit.

Reply with a JSON object and nothing else:
{"choice": 1 or 2, "why": "one short sentence"}"""

_lock = threading.Lock()


def render(item: dict, condition: str, slots: list[dict]) -> str:
    """The transcript as the model heard it, sounds marked where they fell."""
    if condition == "neutral":
        return "\n".join(f"{t['speaker']}: {t['text']}" for t in item["turns"])
    key = "laugh" if condition == "happy" else "sigh"
    by_turn: dict[int, list[dict]] = {}
    for slot in slots:
        by_turn.setdefault(slot["turn"], []).append(slot)
    lines = []
    for index, turn in enumerate(item["turns"], start=1):
        words = turn["text"].split()
        for slot in sorted(by_turn.get(index, []), key=lambda s: -s["after_word"]):
            words.insert(slot["after_word"], slot[key])
        lines.append(f"{turn['speaker']}: {' '.join(words)}")
    return "\n".join(lines)


def prompt_for(transcript: str, first: str, second: str) -> str:
    return (f"Conversation:\n{transcript}\n\n"
            f"Reply 1: {first}\n\nReply 2: {second}\n\n"
            "Which reply is more appropriate as a third speaker's response?")


def record(row: dict) -> None:
    with _lock:
        with VOTES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recorded() -> set[tuple]:
    if not VOTES.exists():
        return set()
    done = set()
    for line in VOTES.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("choice") in (1, 2):
                done.add((row["judge"], row["provider"], row["item_id"],
                          row["condition"], row["against"]))
    return done


def compare(judge: str, provider: str, item: dict, condition: str, against: str,
            own: str, other: str, transcript: str) -> dict:
    """One judgement. Which slot the correct reply sits in is decided by the trial identity."""
    seed = int(hashlib.sha256(
        f"{judge}:{provider}:{item['item_id']}:{condition}:{against}".encode()
    ).hexdigest()[:8], 16)
    own_first = random.Random(seed).random() < 0.5
    first, second = (own, other) if own_first else (other, own)
    try:
        answer = T.retry(T.ask_json, judge, SYSTEM,
                         prompt_for(transcript, first, second), ("choice", "why"))
        choice = int(answer["choice"])
        won = (choice == 1) == own_first
        row = {"judge": judge, "provider": provider, "item_id": item["item_id"],
               "condition": condition, "against": against, "choice": choice,
               "own_position": 1 if own_first else 2, "won": won,
               "why": str(answer.get("why", ""))[:200]}
    except Exception as exc:                        # noqa: BLE001 - recorded, not swallowed
        row = {"judge": judge, "provider": provider, "item_id": item["item_id"],
               "condition": condition, "against": against,
               "error": f"{type(exc).__name__}: {str(exc)[:150]}"}
    record(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judges", default=",".join(JUDGES))
    parser.add_argument("--providers")
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    manifest = json.loads((OUT / "audio_manifest.json").read_text())["items"]
    items = {i["item_id"]: i for i in manifest}
    plan = {e["item_id"]: e for e in json.loads((OUT / "plan.json").read_text())["items"]}

    rows = [json.loads(line) for line in TRIALS.read_text().splitlines() if line.strip()]
    latest = {}
    for row in rows:
        if "error" not in row and row.get("response"):
            latest[(row["provider"], row["item_id"], row["condition"])] = row
    if args.providers:
        keep = {p.strip() for p in args.providers.split(",")}
        latest = {k: v for k, v in latest.items() if k[0] in keep}

    done = recorded()
    jobs = []
    for (provider, item_id, condition), row in sorted(latest.items()):
        if condition not in SCORED:
            continue
        item = items[item_id]
        transcript = render(item, condition, plan[item_id]["slots"])
        for against in ("neutral", "sad" if condition == "happy" else "happy"):
            other = latest.get((provider, item_id, against))
            if other is None:
                continue
            for judge in judges:
                if (judge, provider, item_id, condition, against) in done:
                    continue
                jobs.append((judge, provider, item, condition, against,
                             row["response"], other["response"], transcript))

    print(f"{len(latest)} replies · {len(jobs)} comparisons to judge "
          f"({len(done)} already recorded)\n")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(compare, *job) for job in jobs]
        for n, future in enumerate(as_completed(futures), start=1):
            future.result()
            if n % 25 == 0:
                print(f"  [{n}/{len(jobs)}]", flush=True)

    # Score from every recorded vote, including ones from earlier runs.
    votes = [json.loads(l) for l in VOTES.read_text().splitlines() if l.strip()]
    votes = [v for v in votes if v.get("choice") in (1, 2)]
    per_provider = defaultdict(lambda: [0, 0])
    per_judge = defaultdict(lambda: [0, 0])
    per_cell = defaultdict(lambda: [0, 0])
    position = defaultdict(lambda: [0, 0])
    for v in votes:
        for bucket in (per_provider[v["provider"]], per_judge[v["judge"]],
                       per_cell[(v["provider"], v["condition"], v["against"])]):
            bucket[0] += v["won"]
            bucket[1] += 1
        position[v["judge"]][0] += v["choice"] == 1
        position[v["judge"]][1] += 1

    print(f"\nQ1 answer appropriateness — proportion of comparisons won (chance 50%)")
    for provider, (won, total) in sorted(per_provider.items()):
        print(f"  {provider:8} {won}/{total} = {won/max(1,total):.0%}")
    print("\n  by comparison")
    providers = sorted({p for p, _, _ in per_cell})
    print(f"    {'model':8} {'happy vs neutral':>18} {'happy vs sad':>14} "
          f"{'sad vs neutral':>16} {'sad vs happy':>14}")
    for provider in providers:
        cells = []
        for condition, against in (("happy", "neutral"), ("happy", "sad"),
                                   ("sad", "neutral"), ("sad", "happy")):
            won, total = per_cell[(provider, condition, against)]
            cells.append(f"{won}/{total}={won/max(1,total):3.0%}")
        print(f"    {provider:8} {cells[0]:>18} {cells[1]:>14} {cells[2]:>16} {cells[3]:>14}")
    # The happy-vs-sad and sad-vs-happy cells are the direct contrast: the same two replies,
    # each judged against its own transcript. Scoring them alone is a cleaner test of
    # condition-sensitivity than the pooled figure, which also averages in the comparisons
    # against the neutral reply where several models have no signal at all.
    #
    # A judge that simply prefers one of the two replies scores 50% here, because it wins one
    # cell and loses the other; so does a judge coin-flipping between replies it cannot tell
    # apart. Above 50% means its choice tracks the transcript. Chance 50%, ceiling 100%.
    print("\n  direct contrast only — happy reply vs sad reply, each against its own transcript")
    print(f"    {'model':8} {'won':>10} {'accuracy':>9}   {'happy side':>11} {'sad side':>9}")
    for provider in providers:
        h_won, h_of = per_cell[(provider, "happy", "sad")]
        s_won, s_of = per_cell[(provider, "sad", "happy")]
        if not (h_of and s_of):
            continue
        won, total = h_won + s_won, h_of + s_of
        print(f"    {provider:8} {won:4}/{total:<5} {won/total:8.1%}   "
              f"{h_won/h_of:10.0%} {s_won/s_of:8.0%}")
    print("    the two sides are worth reading separately: equal accuracy can be a symmetric")
    print("    flip or a one-sided preference, and only the components tell them apart")

    print("\n  judge agreement with the model's own condition")
    for judge, (won, total) in sorted(per_judge.items()):
        first, n = position[judge]
        print(f"    {judge:8} {won}/{total} = {won/max(1,total):.0%}"
              f"   (chose slot 1 in {first/max(1,n):.0%} of its votes)")

    RESULT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judges": judges, "votes": len(votes),
        "scoring": ("each scored reply is compared against the same model's replies to the "
                    "other two conditions; a win means the judge preferred the reply actually "
                    "produced for the condition it is judging. chance is 50%"),
        "per_provider": {p: {"won": w, "of": t} for p, (w, t) in per_provider.items()},
        "per_judge": {j: {"won": w, "of": t} for j, (w, t) in per_judge.items()},
        "per_comparison": {f"{p}|{c}|vs {a}": {"won": w, "of": t}
                           for (p, c, a), (w, t) in per_cell.items()},
        "direct_contrast": {
            p: {"won": per_cell[(p, "happy", "sad")][0] + per_cell[(p, "sad", "happy")][0],
                "of": per_cell[(p, "happy", "sad")][1] + per_cell[(p, "sad", "happy")][1],
                "accuracy": round((per_cell[(p, "happy", "sad")][0]
                                   + per_cell[(p, "sad", "happy")][0])
                                  / (per_cell[(p, "happy", "sad")][1]
                                     + per_cell[(p, "sad", "happy")][1]), 4),
                "happy_side": round(per_cell[(p, "happy", "sad")][0]
                                    / per_cell[(p, "happy", "sad")][1], 4),
                "sad_side": round(per_cell[(p, "sad", "happy")][0]
                                  / per_cell[(p, "sad", "happy")][1], 4)}
            for p in providers
            if per_cell[(p, "happy", "sad")][1] and per_cell[(p, "sad", "happy")][1]},
        "direct_contrast_note": ("only the two cells that pit the happy reply against the sad "
                                 "reply, each against its own transcript. chance 50%, ceiling "
                                 "100%: a judge that simply prefers one reply wins one cell "
                                 "and loses the other. read the two sides separately, since "
                                 "equal accuracy can be a symmetric flip or a one-sided "
                                 "preference")},
        indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {RESULT.name} · CLI spend ${T.cli_spend():.2f}")


if __name__ == "__main__":
    main()

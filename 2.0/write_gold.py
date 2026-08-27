"""Stage 5 — the gold answers, written from the transcript that was actually rendered.

1.0 wrote its gold *before* placement, as a prediction of how the sounds would land, which is
the main reason its ground truth was not well defined: the writer was guessing at a
conversation that did not exist yet. Here the laughter and the sighs are already in the
transcript, so the writer is describing something rather than forecasting it.

Two sentences per condition:

    function   "How do the two speakers treat the story, based on the non-speech vocalization
               you observed?" — the answer Q3 scores against.
    tone       the tone a third speaker joining should adopt — what Q2's 0-4 panel rates.

GPT-5.6-Terra writes; Claude Opus 5 verifies. The load-bearing check is the **swap test**:
exchange the happy and sad gold and both must read as wrong. If they survive the exchange, the
gold is not distinguishing the conditions, and no score computed from it can either — the same
test v1 used on its gold response pairs.

    python 2.0/write_gold.py                  # every item
    python 2.0/write_gold.py --only emb_003
    python 2.0/write_gold.py --no-verify      # write only, leave verification for later
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
GOLD = OUT / "gold.json"

ATTEMPTS = 3

WRITER_SYSTEM = """You describe how a conversation is being told, for a speech benchmark.

You are given a conversation between two friends with non-speech sounds written into it — a
version told through laughter, or a version told through sighs. The spoken words are identical
across both versions. Only the sounds differ, so the sounds are the only thing that can
account for a difference in how the story is being treated.

Write two things.

1. function — how the two speakers are treating the story, given the sounds you can see. One
   short sentence. Describe their stance toward what happened: are they making light of it,
   commiserating over it, bracing against it, waving it off. Do not list or name the sounds,
   and do not quote the words. A reader who has not seen the transcript should still learn
   something specific about this conversation from the sentence.

2. tone — the tone a third person joining this conversation should adopt for their reply to
   land well. One short sentence, about delivery rather than content: warmth, briskness,
   dryness, gentleness, energy. Do not say what the third speaker should say.

Both sentences must be specific to this conversation. A sentence that would fit any laughter
version of any story is useless here. Be concrete about the stance, not the emotion label."""

VERIFIER_SYSTEM = """You verify gold answers for a speech benchmark, strictly.

You are given one conversation, in two versions with identical words: one told through
laughter, one told through sighs. For each version you get a proposed `function` sentence and
a proposed `tone` sentence.

Check all four things and answer honestly. A benchmark built on gold you waved through
measures nothing.

1. supported — is each function sentence actually supported by the sounds in that version,
   rather than by the words alone? If the same sentence would be written from the plain
   transcript with no sounds at all, it fails.
2. tone_follows — does each tone sentence describe a delivery a third speaker could actually
   adopt, and does it follow from that version's function?
3. swap — this is the important one. Exchange the two versions' answers: give the laughter
   version the sigh answers and vice versa. Do both exchanged pairs now read as wrong? If
   either exchange still reads as plausible, the answers are not distinguishing the versions.
4. specific — is each sentence specific to this conversation, rather than a sentence that
   would fit any laughter story or any sigh story?

Reply with a JSON object and nothing else:

{"supported": true/false, "tone_follows": true/false, "swap": true/false,
 "specific": true/false, "verdict": "pass" or "fail", "reasons": ["..."]}

`verdict` is "pass" only if all four checks are true. Put one short reason in `reasons` for
every check that failed, naming which version and which sentence."""


def schema() -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["function", "tone"],
            "properties": {"function": {"type": "string"}, "tone": {"type": "string"}}}


def render(item: dict, slots: list[dict], kind: str) -> str:
    """The transcript as it will be heard: the same words, with this condition's sounds in."""
    by_turn: dict[int, list[dict]] = {}
    for slot in slots:
        by_turn.setdefault(slot["turn"], []).append(slot)
    lines = []
    for index, turn in enumerate(item["turns"], start=1):
        words = turn["text"].split()
        for slot in sorted(by_turn.get(index, []), key=lambda s: -s["after_word"]):
            words.insert(slot["after_word"], slot[kind])
        lines.append(f"{turn['speaker']}: {' '.join(words)}")
    return "\n".join(lines)


def writer_prompt(item: dict, transcript: str, condition: str) -> str:
    return (f"Situation: {item['situation_third_person']}\n\n"
            f"This is the version told through {'laughter' if condition == 'happy' else 'sighs'}"
            f".\n\n{transcript}")


def verifier_prompt(item: dict, happy: str, sad: str, gold: dict) -> str:
    return (f"Situation: {item['situation_third_person']}\n\n"
            f"=== version told through laughter ===\n{happy}\n\n"
            f"proposed function: {gold['happy']['function']}\n"
            f"proposed tone: {gold['happy']['tone']}\n\n"
            f"=== version told through sighs ===\n{sad}\n\n"
            f"proposed function: {gold['sad']['function']}\n"
            f"proposed tone: {gold['sad']['tone']}")


def write_item(item: dict, slots: list[dict], verify: bool) -> dict:
    happy_text = render(item, slots, "laugh")
    sad_text = render(item, slots, "sigh")
    history = []

    for attempt in range(1, ATTEMPTS + 1):
        gold = {}
        for condition, transcript in (("happy", happy_text), ("sad", sad_text)):
            note = ""
            if history:
                note = ("\n\nA previous attempt was rejected by the verifier:\n"
                        + "\n".join(f"- {r}" for r in history[-1])
                        + "\nWrite different sentences that answer those objections.")
            gold[condition] = T.retry(
                T.json_call, T.WRITER, WRITER_SYSTEM,
                writer_prompt(item, transcript, condition) + note, schema(), "gold")
        if not verify:
            return {"item_id": item["item_id"], "attempts": attempt, "verified": False,
                    "happy": gold["happy"], "sad": gold["sad"],
                    "transcripts": {"happy": happy_text, "sad": sad_text}}
        check = T.retry(T.ask_json, "opus", VERIFIER_SYSTEM,
                        verifier_prompt(item, happy_text, sad_text, gold),
                        ("supported", "tone_follows", "swap", "specific", "verdict"))
        if check.get("verdict") == "pass":
            return {"item_id": item["item_id"], "attempts": attempt, "verified": True,
                    "checks": check, "happy": gold["happy"], "sad": gold["sad"],
                    "transcripts": {"happy": happy_text, "sad": sad_text}}
        history.append(check.get("reasons") or ["rejected without a reason"])
        print(f"    rejected: {'; '.join(history[-1])[:150]}", flush=True)

    return {"item_id": item["item_id"], "attempts": ATTEMPTS, "verified": False,
            "checks": check, "happy": gold["happy"], "sad": gold["sad"],
            "transcripts": {"happy": happy_text, "sad": sad_text},
            "note": "failed verification; not usable as gold"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-verify", action="store_true",
                        help="write without the Opus 5 pass; leaves verified=false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = json.loads((OUT / "items.json").read_text())["items"]
    plan = {e["item_id"]: e for e in json.loads((OUT / "plan.json").read_text())["items"]}
    wanted = [i for i in items if not args.only or i["item_id"] in args.only]
    if args.limit:
        wanted = wanted[: args.limit]

    existing = json.loads(GOLD.read_text())["items"] if GOLD.exists() else []
    by_id = {e["item_id"]: e for e in existing}

    for item in wanted:
        print(f"  {item['item_id']}", flush=True)
        record = write_item(item, plan[item["item_id"]]["slots"], not args.no_verify)
        by_id[item["item_id"]] = record
        ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
        GOLD.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "writer": T.WRITER, "verifier": T.VERIFIER,
             "verified": not args.no_verify, "items": ordered}, indent=2,
            ensure_ascii=False) + "\n")
        mark = "verified" if record["verified"] else "UNVERIFIED"
        print(f"    happy: {record['happy']['function']}", flush=True)
        print(f"    sad:   {record['sad']['function']}  [{mark}, "
              f"attempt {record['attempts']}]", flush=True)

    ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
    good = sum(1 for e in ordered if e["verified"])
    print(f"\nout/gold.json · {len(ordered)} items · {good} verified")


if __name__ == "__main__":
    main()

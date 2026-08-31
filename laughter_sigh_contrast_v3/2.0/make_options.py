"""Stage 10 — the four-option sets Q3 is scored against.

Q3 asks the tested model "How do the two speakers treat the story?" and offers four answers:
the one written for the happy condition, the one written for the sad condition, and two that
are wrong for both. The gold is whichever of the first two matches the condition the model
actually heard, so the question is not "describe this conversation" but "which of these two
readings did the sounds you heard support" — with two plausible wrong readings present so a
model cannot score by recognizing the format.

The two real options come from stage 5, written by GPT-5.6-Terra. The distractors are written
by a **second** model, Claude Opus 5, from the plain transcript with no sounds in it. That
separation matters: a distractor written by the model that wrote the real answers tends to
differ from them in style rather than in substance, and style is exactly what a tested model
would learn to key on.

    python 2.0/make_options.py
    python 2.0/make_options.py --only emb_003
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OPTIONS = OUT / "q3_options.json"

ATTEMPTS = 3

SYSTEM = """You write wrong-but-plausible answer options for a listening benchmark.

You are given a conversation between two friends, and two real answers to the question "How do
the two speakers treat the story?" — one written for a version of the conversation told through
laughter, one for a version told through sighs. The words are identical in both versions; only
non-speech sounds differ.

Write two more options that are **wrong for both versions**, and hard to dismiss without having
heard the audio.

What makes a good wrong option here:
- It is a coherent reading of these particular speakers and this particular story. Someone who
  read the transcript and never heard it could believe it.
- It is wrong about their *stance*: it attributes a treatment the sounds rule out. Alarm,
  scolding, indifference, competitiveness, formality, bafflement — stances that are neither
  making light of it nor commiserating over it.
- It matches the two real options in length, register and specificity. A shorter, vaguer or
  more generic option is a giveaway.
- It does not name or refer to any non-speech sound.

What makes a bad wrong option:
- A negation or hedge of a real option ("they do not find it funny").
- Something no reader could believe of this conversation.
- A description of the events rather than of how the speakers treat them.

Reply with a JSON object and nothing else:
{"wrong": ["...", "..."], "why": ["...", "..."]}

`why` gives, for each, the one-line reason it is wrong for both versions."""


def plain(item: dict) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in item["turns"])


def prompt_for(item: dict, happy: str, sad: str) -> str:
    return (f"Situation: {item['situation_third_person']}\n\n{plain(item)}\n\n"
            f"Real option (laughter version): {happy}\n"
            f"Real option (sigh version): {sad}")


def problems(wrong: list[str], happy: str, sad: str) -> list[str]:
    found = []
    if len(wrong) != 2:
        found.append(f"{len(wrong)} options, wanted 2")
    real = [happy, sad]
    for text in wrong:
        if len(text.split()) < 8:
            found.append(f"{text!r} is too short to sit beside the real options")
        if re.search(r"\b(laugh|laughter|chuckle|giggle|sigh|sighs|exhale|groan)\b", text, re.I):
            found.append(f"{text!r} names a non-speech sound")
        for other in real:
            shared = overlap(text, other)
            if shared > 0.6:
                found.append(f"{text!r} restates a real option (overlap {shared:.2f})")
    if len(wrong) == 2 and overlap(wrong[0], wrong[1]) > 0.6:
        found.append("the two wrong options are near-duplicates")
    return found


def overlap(a: str, b: str) -> float:
    def words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 3}
    x, y = words(a), words(b)
    return len(x & y) / max(1, len(x | y))


def write_item(item: dict, happy: str, sad: str) -> dict:
    prompt = prompt_for(item, happy, sad)
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        result = T.retry(T.ask_json, "opus", SYSTEM, prompt, ("wrong", "why"))
        wrong = [str(w).strip() for w in result["wrong"]]
        found = problems(wrong, happy, sad)
        if not found:
            return {"item_id": item["item_id"], "attempts": attempt,
                    "happy": happy, "sad": sad, "wrong": wrong,
                    "why": [str(w) for w in result.get("why", [])]}
        last = found
        prompt = (prompt_for(item, happy, sad)
                  + "\n\nYour previous options were rejected:\n"
                  + "\n".join(f"- {line}" for line in found))
    raise RuntimeError(f"{item['item_id']}: distractors failed after {ATTEMPTS}: {last}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = json.loads((OUT / "items.json").read_text())["items"]
    gold = {e["item_id"]: e for e in json.loads((OUT / "gold.json").read_text())["items"]}
    wanted = [i for i in items if not args.only or i["item_id"] in args.only]
    if args.limit:
        wanted = wanted[: args.limit]

    existing = json.loads(OPTIONS.read_text())["items"] if OPTIONS.exists() else []
    by_id = {e["item_id"]: e for e in existing}

    failed = []
    for item in wanted:
        entry = gold[item["item_id"]]
        try:
            record = write_item(item, entry["happy"]["function"], entry["sad"]["function"])
        except RuntimeError as exc:
            failed.append(str(exc))
            print(f"  {item['item_id']} · FAILED, continuing", flush=True)
            continue
        by_id[item["item_id"]] = record
        ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
        OPTIONS.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "real_options_from": T.WRITER, "distractors_from": T.VERIFIER,
             "items": ordered}, indent=2, ensure_ascii=False) + "\n")
        print(f"  {item['item_id']} · attempt {record['attempts']}", flush=True)
        for text in record["wrong"]:
            print(f"      {text}", flush=True)

    ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
    print(f"\nout/q3_options.json · {len(ordered)} items · "
          f"CLI spend ${T.cli_spend():.2f}")
    if failed:
        print(f"  {len(failed)} failed:")
        for line in failed:
            print(f"    {line}"[:200])


if __name__ == "__main__":
    main()

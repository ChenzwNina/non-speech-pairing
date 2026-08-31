"""Stages 3-4 — how many vocalizations, and where each one goes.

Stage 3 draws the count: between 1x and 2x the number of turns, so every turn carries at least
one on average and a long conversation carries proportionally more. 1.0 drew between 0.5x and
1x, which left most turns bare.

Stage 4 hands the script and that count to GPT-4o and asks it to choose the slots -- which turn,
after which word -- and to write each sound in the "[tag] written sound" form ElevenLabs needs.
1.0 drew slots by script instead, because an earlier LLM pass favoured turn starts and ends so
predictably that a model could have scored well by guessing. At 1-2x density that regularity
matters much less, but the position distribution is logged either way so a collapse back to a
pattern is visible rather than assumed.

**One set of slots serves both conditions.** Each slot gets a laughter form and a sigh form, so
happy and sad differ only in which sound is spliced in -- same words, same timing, same take.
That physical control is the point of the design; letting each condition choose its own
positions would give up the ability to attribute a difference to the sound.

    python 2.0/place.py                 # all items
    python 2.0/place.py --only emb_003  # one item, merged into the existing plan
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# A bracketed manner tag plus a short written sound. ElevenLabs rejects a bare "[sigh]" —
# every input must carry text after the speaker tags are stripped — and a tag with no written
# sound is often ignored outright, giving a take that is simply short.
LAUGH_TAGS = ("[laugh]", "[laughs]", "[chuckle]", "[chuckles]", "[giggle]", "[giggles]")
SIGH_TAGS = ("[sigh]", "[sighs]", "[heavy sigh]", "[exhales]")
LAUGH_SOUND = re.compile(r"^(h[aeiou]{1,3})+h*$", re.I)         # haha, hehe, hah, hoho
SIGH_SOUND = re.compile(r"^(ugh+|u+h+|h+|h[aou]+h*|a+h+|oof|phew|hoo+)$", re.I)

ATTEMPTS = 3

SYSTEM = """You place non-speech sounds into a written conversation for a speech benchmark.

The same conversation will be heard three ways: told through laughter, told through sighs, and
told plainly. You choose the positions once, and they serve both the laughter version and the
sigh version, so the two differ only in which sound is heard. Each position therefore needs
both a laughter form and a sigh form, and both must be plausible at that spot.

Rules:
- Use exactly the number of positions you are told.
- A position is a turn number plus a word index: after_word 0 means before the first word of
  that turn, after_word N means after the Nth word. Never exceed the turn's word count.
- Spread them across turns and across positions within a turn. Do not put everything at turn
  openings or turn endings, and do not stack more than three in one turn.
- Prefer a spot where a speaker would actually break: after a clause, before a reversal, at a
  hesitation. Mid-phrase is fine when that is where a real person would break.
- Write each sound as a bracketed manner tag followed by a short written sound, e.g.
  "[chuckle] hah" or "[sigh] ugh". The written sound is required: the voice needs syllables to
  perform, and a bare tag produces nothing.
- The laughter tag must be exactly one of: [laugh] [laughs] [chuckle] [chuckles] [giggle]
  [giggles]. The laughter sound is h plus vowels: ha, haha, hah, hehe, hoho.
- The sigh tag must be exactly one of: [sigh] [sighs] [heavy sigh] [exhales]. The sigh sound
  must be exactly one of: ugh, uh, hh, hoo, ah, oof, phew.
- Nothing outside those lists. [snort], [snicker], [nervous laughter] and the like are
  different vocalizations, and this benchmark asks models to tell laughter from sighs — a
  third kind of sound in the audio makes that question unanswerable. Convey nervousness or
  restraint by choosing [chuckle] over [laughs] and a shorter sound, not a new tag.
- Do not change, add or remove any of the spoken words. You are only choosing positions."""


def schema(count: int) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["slots"],
        "properties": {"slots": {
            "type": "array", "minItems": count, "maxItems": count,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["turn", "after_word", "laugh", "sigh", "why"],
                      "properties": {
                          "turn": {"type": "integer"},
                          "after_word": {"type": "integer"},
                          "laugh": {"type": "string"},
                          "sigh": {"type": "string"},
                          "why": {"type": "string"}}}}},
    }


def prompt_for(item: dict, count: int) -> str:
    lines = [f"Situation: {item['situation_third_person']}", "",
             f"Choose exactly {count} positions.", "", "Conversation:"]
    for index, turn in enumerate(item["turns"], start=1):
        lines.append(f"  turn {index} ({turn['speaker']}, {turn['words']} words): "
                     f"{turn['text']}")
    return "\n".join(lines)


def draw_count(turns: int, rng: random.Random) -> int:
    """Stage 3: between 1x and 2x the turn count."""
    return rng.randint(turns, 2 * turns)


def clean_form(value: str) -> str:
    """"[sigh] ugh." -> "[sigh] ugh". Trailing punctuation is how the model writes prose, and
    it says nothing about the sound; the written form is what gets sent to TTS, so canonicalize
    it here rather than rejecting an otherwise correct answer."""
    match = re.match(r"^\s*(\[[^\]]+\])\s*(.+?)\s*$", value)
    if not match:
        return value.strip()
    sound = match.group(2).strip().strip(".,!?;:\u2026")
    return f"{match.group(1).lower()} {sound}"


def form_problems(value: str, kind: str) -> str | None:
    tags = LAUGH_TAGS if kind == "laugh" else SIGH_TAGS
    pattern = LAUGH_SOUND if kind == "laugh" else SIGH_SOUND
    match = re.match(r"^\s*(\[[^\]]+\])\s*(.+?)\s*$", clean_form(value))
    if not match:
        return f"{kind} {value!r} is not '[tag] sound'"
    tag, sound = match.group(1).lower(), match.group(2)
    if tag not in tags:
        return f"{kind} tag {tag!r} is not one of {tags}"
    if not pattern.match(sound):
        return f"{kind} sound {sound!r} does not read as a {kind}"
    return None


def problems(item: dict, count: int, slots: list[dict]) -> list[str]:
    found = []
    if len(slots) != count:
        found.append(f"{len(slots)} slots, wanted {count}")
    per_turn = Counter()
    for slot in slots:
        turn = slot["turn"]
        if not 1 <= turn <= len(item["turns"]):
            found.append(f"turn {turn} out of range")
            continue
        per_turn[turn] += 1
        words = item["turns"][turn - 1]["words"]
        if not 0 <= slot["after_word"] <= words:
            found.append(f"turn {turn}: after_word {slot['after_word']} exceeds {words} words")
        for kind in ("laugh", "sigh"):
            issue = form_problems(slot[kind], kind)
            if issue:
                found.append(f"turn {turn}: {issue}")
    crowded = [f"turn {t} has {n}" for t, n in per_turn.items() if n > 3]
    if crowded:
        found.append("more than three in a turn: " + ", ".join(crowded))
    return found


def position_kind(slot: dict, item: dict) -> str:
    words = item["turns"][slot["turn"] - 1]["words"]
    if slot["after_word"] == 0:
        return "start"
    if slot["after_word"] >= words:
        return "end"
    return "middle"


def plan_item(item: dict, count: int, model: str) -> dict:
    prompt = prompt_for(item, count)
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        result = T.retry(T.json_call, model, SYSTEM, prompt, schema(count), "placement")
        slots = sorted(result["slots"], key=lambda s: (s["turn"], s["after_word"]))
        found = problems(item, count, slots)
        if not found:
            return {"item_id": item["item_id"], "turns": len(item["turns"]),
                    "count": count, "attempts": attempt,
                    "slots": [dict(slot, laugh=clean_form(slot["laugh"]),
                                   sigh=clean_form(slot["sigh"]),
                                   position=position_kind(slot, item))
                              for slot in slots]}
        last = found
        prompt = (prompt_for(item, count) + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in found))
    raise RuntimeError(f"{item['item_id']}: placement failed after {ATTEMPTS} attempts: {last}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="item ids; merged into the plan")
    parser.add_argument("--model", default=T.PLACER)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = json.loads((OUT / "items.json").read_text())["items"]
    wanted = [i for i in items if not args.only or i["item_id"] in args.only]
    if not wanted:
        raise SystemExit(f"no items match {args.only}")

    path = OUT / "plan.json"
    existing = json.loads(path.read_text())["items"] if path.exists() else []
    by_id = {entry["item_id"]: entry for entry in existing}

    rng = random.Random(args.seed)
    # Draw for every item in order so an item's count does not depend on which subset ran.
    counts = {item["item_id"]: draw_count(len(item["turns"]), rng) for item in items}

    def save() -> list[dict]:
        ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
        path.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "model": args.model, "seed": args.seed,
             "count_rule": "randint(turns, 2*turns)",
             "slots_shared": True, "items": ordered}, indent=2) + "\n")
        return ordered

    failed = []
    for item in wanted:
        try:
            planned = plan_item(item, counts[item["item_id"]], args.model)
        except RuntimeError as exc:
            failed.append(str(exc))
            print(f"  {item['item_id']} · FAILED, continuing", flush=True)
            continue
        by_id[item["item_id"]] = planned
        save()
        spread = Counter(slot["position"] for slot in planned["slots"])
        print(f"  {item['item_id']} · {planned['turns']} turns · {planned['count']} slots · "
              f"{dict(spread)} · attempt {planned['attempts']}", flush=True)

    ordered = [by_id[i["item_id"]] for i in items if i["item_id"] in by_id]
    total = sum(len(e["slots"]) for e in ordered)
    spread = Counter(slot["position"] for e in ordered for slot in e["slots"])
    ordered = save()
    print(f"\nout/plan.json · {len(ordered)} items · {total} slots per condition")
    print("  positions:", ", ".join(f"{k} {v} ({v/total:.0%})"
                                    for k, v in sorted(spread.items())))
    if failed:
        print(f"\n  {len(failed)} item(s) failed placement:")
        for line in failed:
            print(f"    {line}"[:200])


if __name__ == "__main__":
    main()

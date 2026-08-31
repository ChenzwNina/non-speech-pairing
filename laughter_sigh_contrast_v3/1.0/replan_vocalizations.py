"""Redraw where the vocalizations go, leaving the conversations untouched.

Three things move out of the writer model's hands and into a seeded draw:

    how many   Asked to pick a number between 2 and 4, it picked 3 on 18 of 20 items and
               never picked 2 — an anchor, not a decision. Worse, it did not scale the count
               with the length of the conversation, so density ranged from 0.38 to 0.75
               vocalizations per turn and items were not equally hard. Now: a random count
               between half the turns and all of them.

    where      It put one on turn 1 of every single item and clustered the rest at the middle
               and the end. That made the placement guessable: a strategy of naming turn 1,
               the middle and the last turn, without listening to anything, scored 0.61 on
               the location metric — higher than any model actually managed. Now: turns
               sampled at random, and turn 1 has no special status.

    which tag  `[laughs] hehe` renders as a thin, odd little titter. The inventory below keeps
               the tags that sound like a person and drops that one.

Happy and sad share the same slots by construction, so the two conditions differ in the kind
of sound and in nothing else — not in how many, not in where.

The words, the turn counts, the speakers and the neutral audio are all left exactly as they
are. Only the insertion plans change.

Usage:
    python benchmark/replan_vocalizations.py --dry-run
    python benchmark/replan_vocalizations.py
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = HERE / "out" / "transcripts.json"
OUT_MD = HERE / "out" / "transcripts.md"

POSITIONS = ("start", "end")

# A bare tag is not synthesizable: eleven_v3 rejects it with "All inputs must include
# non-empty text after removing speaker tags and emojis." The tag sets the manner, but
# something has to be voiced. So every token is tag plus a written sound — with "hehe" left
# out, since it renders as a thin titter rather than a laugh.
LAUGH_TOKENS = ("[laughs] haha", "[laughs] hahaha", "[chuckle] haha", "[chuckles] hah",
                "[happy laugh] haha", "[laughs] ha", "[giggle] haha", "[chuckle] hah")
SIGH_TOKENS = ("[sigh] ugh", "[sigh] uhh", "[sigh] ahh", "[heavy sigh] hhh",
               "[heavy sigh] uhh", "[exhale] hhh", "[sigh] hoo", "[heavy sigh] ahh")


def draw_count(turns: int, rng: random.Random) -> int:
    """Between half the turns and all of them, so density no longer drifts with length."""
    return rng.randint(math.ceil(turns / 2), turns)


# Three places a vocalization can go, not an open choice of word boundary:
#
#   start    before the first word
#   middle   at an interior punctuation mark, if the utterance has one
#   end      after the last word
#
# The middle option exists only when the speaker actually breaks mid-utterance — a comma, a
# full stop between two sentences, a dash. Those are the points where a laugh or a sigh can
# sit without cutting across connected speech; ordinary word gaps here run 27-67ms, far too
# tight. Where several interior breaks exist, the one nearest the middle of the utterance is
# used, so the label means what it says.


def middle_point(words: list[dict]) -> int | None:
    """`after_word` at the most central interior punctuation break, or None if there is none."""
    breaks = [w for w in words[:-1] if w["punct_pause"] > 0]
    if not breaks:
        return None
    midpoint = words[-1]["end"] / 2
    return min(breaks, key=lambda w: abs(w["end"] - midpoint))["after_word"]


def draw_point(turn: int, rng: random.Random,
               alignment: dict[int, list[dict]]) -> tuple[str, int]:
    """(label, after_word) — uniform over the positions this utterance actually offers."""
    words = alignment.get(turn) or []
    middle = middle_point(words)
    options = ["start", "end"] if middle is None else ["start", "middle", "end"]
    label = rng.choice(options)
    return label, {"start": 0, "middle": middle, "end": len(words)}[label]


def draw_slots(turns: int, count: int, rng: random.Random,
               alignment: dict[int, list[dict]]) -> list[tuple[int, int]]:
    """`count` distinct turns, each with one insertion point.

    Interior points are chosen from the widest boundaries the alignment reports — where the
    speaker was already pausing — so a laugh lands in real silence instead of splitting "my /
    phone". Turns with no usable pause fall back to an edge.
    """
    chosen = rng.sample(range(1, turns + 1), count)
    slots = []
    for turn in chosen:
        words = alignment.get(turn) or []
        pauses = [w["after_word"] for w in words[:-1] if w["score"] >= MIN_PAUSE]
        if pauses and rng.random() < INTERIOR_SHARE:
            slots.append((turn, rng.choice(pauses)))
        else:
            slots.append((turn, 0 if rng.random() < 0.5 else len(words)))
    return sorted(slots)


def render(turns: list[dict], insertions: list[dict]) -> list[str]:
    """The transcript as it reads, with each token sitting where it will be spliced."""
    by_turn = {ins["turn"]: ins for ins in insertions}
    lines = []
    for index, turn in enumerate(turns, 1):
        ins = by_turn.get(index)
        if ins is None:
            lines.append(f"{turn['speaker']}: {turn['text']}")
            continue
        words = turn["text"].split()
        at = max(0, min(ins["after_word"], len(words)))
        parts = words[:at] + [ins["token"]] + words[at:]
        lines.append(f"{turn['speaker']}: {' '.join(parts)}")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--placement-only", action="store_true",
                        help="move the insertion points inside their turns and change "
                             "nothing else — counts, turns, tokens and clips all survive")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))
    aligned = json.loads((HERE / "out" / "turn_alignment.json").read_text(encoding="utf-8"))
    rng = random.Random(args.seed)

    print(f"{'item':10} {'turns':>6} {'voc':>4}  {'mid':>5}   placements")
    counts = Counter()
    for item in data["items"]:
        if "error" in item:
            continue
        turns = item["turns"]
        n_turns = len(turns)
        before = len(item.get("happy_insertions", []))
        per_turn = {n: aligned.get(
            f"out/audio_turns/{item['item_id']}_t{n:02d}_{turns[n - 1]['speaker']}.mp3", [])
            for n in range(1, n_turns + 1)}

        if args.placement_only:
            # Keep the counts, the turns and the tokens exactly as they are — 190 clips are
            # already synthesized and verified against them, and redrawing any of that would
            # throw away 760 sessions of voting. Only the point inside the turn moves, and
            # `position` is left in place because the clip filenames are built from it.
            happy = [dict(ins) for ins in item["happy_insertions"]]
            sad = [dict(ins) for ins in item["sad_insertions"]]
            for h, sd in zip(happy, sad):
                label, point = draw_point(h["turn"], rng, per_turn)
                h["after_word"] = sd["after_word"] = point
                h["place"] = sd["place"] = label
            count = len(happy)
            slots = [(h["turn"], h["after_word"]) for h in happy]
        else:
            count = draw_count(n_turns, rng)
            slots = draw_slots(n_turns, count, rng, per_turn)
            happy = [{"turn": t, "after_word": w, "position": "start" if w == 0 else "end",
                      "token": rng.choice(LAUGH_TOKENS)} for t, w in slots]
            sad = [{"turn": t, "after_word": w, "position": "start" if w == 0 else "end",
                    "token": rng.choice(SIGH_TOKENS)} for t, w in slots]
        counts[count] += 1

        if not args.dry_run:
            item["happy_insertions"] = happy
            item["sad_insertions"] = sad
            item["rendered"] = {"neutral": render(turns, []),
                                "happy": render(turns, happy),
                                "sad": render(turns, sad)}
        labels = [ins.get("place", "?") for ins in happy]
        offered = sum(1 for n in range(1, n_turns + 1)
                      if middle_point(per_turn.get(n) or []) is not None)
        print(f"{item['item_id']:10} {n_turns:6} {count:4}  {offered:2}/{n_turns}   "
              + ", ".join(f"t{t}:{l}" for (t, _), l in zip(slots, labels)))

    total = sum(len(i.get('happy_insertions', [])) for i in data['items'] if 'error' not in i)
    print(f"\ncount distribution: {dict(sorted(counts.items()))}")
    print(f"density: every item now sits between 0.50 and 1.00 vocalizations per turn")
    if args.dry_run:
        print("\n(dry run — nothing written)")
        return

    backup = TRANSCRIPTS.with_suffix(".pre-replan.json")
    if not backup.exists():
        shutil.copy(TRANSCRIPTS, backup)
        print(f"\nkept the previous plans at {backup.name}")
    data["voc_plan"] = {
        "drawn_by": "script", "seed": args.seed,
        "count_rule": "randint(ceil(turns/2), turns)",
        "slots": "count distinct turns; position uniform over start/middle/end where the "
                 "utterance has an interior punctuation break, start/end where it does not; "
                 "shared between happy and sad",
        "laugh_tokens": list(LAUGH_TOKENS), "sigh_tokens": list(SIGH_TOKENS),
        "excluded": ["[laughs] hehe — thin titter, does not read as a laugh"],
        "replanned_at": datetime.now(timezone.utc).isoformat(),
    }
    TRANSCRIPTS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    good = [i for i in data["items"] if "error" not in i]
    md = ["# Benchmark transcripts", "",
          f"{len(good)} items · words unchanged · vocalization plans drawn in the script "
          f"(seed {args.seed}), count between half the turns and all of them, happy and sad "
          "sharing the same slots.", ""]
    for item in good:
        md += [f"## {item['item_id']} — {len(item['turns'])} turns, "
               f"{len(item['happy_insertions'])} vocalizations", "",
               f"*{item['situation']}*", ""]
        for condition in ("neutral", "happy", "sad"):
            md += [f"**{condition}** — third friend should: "
                   f"{item[condition]['expectation']} ({item[condition]['tone_label']})", ""]
            md += [f"> {line}" for line in item["rendered"][condition]] + [""]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote transcripts.json and transcripts.md · {total} clips per condition to make")


if __name__ == "__main__":
    main()

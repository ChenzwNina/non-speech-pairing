"""Rewrite the transcripts to sound spoken, with GPT-4o, without changing what they say.

`gpt-5.6-sol` writes correct stimuli in stiff English — "I knew one visit would not be enough"
where a person says "knew one look wasn't going to do it". This pass sends each transcript to
GPT-4o and asks only for the register: contractions, shorter clauses, the way people actually
talk. Same speakers, same turn order, same information, same situation.

**The vocalization is a marker, not a tag, while the rewrite happens.** The tagged turn goes out
as `«VOC»` sitting where the tag sat, and the three versions are rebuilt afterwards by replacing
the marker with tag A, tag B, or nothing. So the minimal pair survives the rewrite by
construction: one text in, three versions out, identical apart from the tag.

The specific risk of a colloquialization pass is that it settles the emotion — "oh no", "ugh",
"wow", "haha" are all natural spoken English and all fatal here, because the words are supposed
to leave both readings open. The prompt forbids them and `problems()` checks for them.

    python v6/spoken.py                  # every item in out/pairs.json
    python v6/spoken.py --only v6_01a
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

MARKER = "«VOC»"
TURNS = 4
ATTEMPTS = 3

PAREN = re.compile(r"\([^)]*\)")

# Interjections that carry a stance. Natural in speech, and each one decides for the listener
# what the sound in the same conversation is doing, which is the thing the design removes.
EMOTIVE = re.compile(
    r"\b(oh no|oh god|oh my god|omg|ugh|ew|yikes|whoa|wow|aw|aww|haha|hah|heh|hehe|lol|"
    r"jeez|geez|gosh|damn|great|terrible|awful|hilarious|scary|sad|funny|sorry)\b", re.I)

SYSTEM = """You rewrite dialogue so that it sounds like people actually talking.

You are given four turns of a two-speaker conversation. Rewrite each turn in natural spoken
English. That means contractions, shorter clauses, ordinary word choice, the odd fragment —
the way someone talks out loud rather than the way a sentence is written down.

WHAT MUST NOT CHANGE

- The meaning. Every piece of information in a turn stays in that turn. Nothing is added,
  nothing is dropped, nothing moves between turns.
- The speakers and their order: four turns, A, B, A, B.
- The situation, the relationship, and who knows what.

THE MARKER

One turn contains «VOC» exactly once. A non-speech sound goes there later. Keep the marker,
keep it in the same turn, and keep it at a natural boundary — if it starts the turn, it still
starts the turn. Write the rewritten line so the marker still sits comfortably where it is.

DO NOT DECIDE THE EMOTION

This conversation is used twice, with two different sounds at the marker, and it has to work
both times. So the words must not tell the listener how to feel about it.

- No emotive interjections: no "oh no", "ugh", "wow", "aw", "haha", "yikes", "jeez", "geez".
- No emotion words: not funny, sad, scary, awful, great, hilarious, sorry.
- No exclamation marks, no capitalised words, no repeated punctuation, no stage directions,
  and no parentheses other than the marker.

If the line you were given is already plainly spoken, leave it close to what it is. A rewrite
that adds colour is worse than one that changes little.

Return JSON only."""


def schema() -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["turns"],
        "properties": {"turns": {
            "type": "array", "minItems": TURNS, "maxItems": TURNS,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["turn", "speaker", "text"],
                      "properties": {"turn": {"type": "integer",
                                              "enum": list(range(1, TURNS + 1))},
                                     "speaker": {"type": "string", "enum": ["A", "B"]},
                                     "text": {"type": "string"}}}}},
    }


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def to_marker(item: dict) -> list[dict]:
    """condition_a, with the tag swapped for the marker: the one text to be rewritten."""
    out = []
    for turn in item["condition_a"]["turns"]:
        text = turn["text"].replace(item["tag_a"], MARKER)
        out.append({"turn": turn["turn"], "speaker": turn["speaker"], "text": tidy(text)})
    return out


def from_marker(turns: list[dict], tag: str | None) -> dict:
    """One version, built by filling the marker. `tag=None` is the baseline."""
    return {"turns": [{"turn": t["turn"], "speaker": t["speaker"],
                       "text": tidy(t["text"].replace(MARKER, tag or ""))}
                      for t in turns]}


def problems(before: list[dict], after: list[dict]) -> list[str]:
    found = []
    if [t["turn"] for t in after] != list(range(1, TURNS + 1)):
        found.append(f"turns are not numbered 1..{TURNS}")
    if [t["speaker"] for t in after] != [t["speaker"] for t in before]:
        found.append("the speakers changed")
    markers = sum(t["text"].count(MARKER) for t in after)
    if markers != 1:
        found.append(f"{markers} markers; there must be exactly one {MARKER}")
    else:
        was = next(t["turn"] for t in before if MARKER in t["text"])
        now = next(t["turn"] for t in after if MARKER in t["text"])
        if was != now:
            found.append(f"the marker moved from turn {was} to turn {now}")
        started = next(t["text"].startswith(MARKER) for t in before if MARKER in t["text"])
        starts = next(t["text"].startswith(MARKER) for t in after if MARKER in t["text"])
        if started != starts:
            found.append("the marker moved to the other side of the words in its turn")
    for turn in after:
        stray = [p for p in PAREN.findall(turn["text"])]
        if stray:
            found.append(f"turn {turn['turn']} adds {stray}")
        leaks = sorted({m.group(0).lower() for m in EMOTIVE.finditer(turn["text"])})
        if leaks:
            found.append(f"turn {turn['turn']} decides the emotion with {leaks}")
        if "!" in turn["text"] or re.search(r"[.?]{2,}", turn["text"]):
            found.append(f"turn {turn['turn']} uses exclamation or repeated punctuation")
    return found


def rewrite(item: dict, model: str) -> tuple[dict, int]:
    before = to_marker(item)
    prompt = json.dumps({"turns": before}, ensure_ascii=False, indent=2)
    for attempt in range(1, ATTEMPTS + 1):
        after = T.retry(T.json_call, model, SYSTEM, prompt, schema(), "spoken_turns")["turns"]
        found = problems(before, after)
        if not found:
            return after, attempt
        prompt = (json.dumps({"turns": before}, ensure_ascii=False, indent=2)
                  + "\n\nYour previous rewrite was rejected:\n"
                  + "\n".join(f"- {line}" for line in found)
                  + "\nRewrite so that none of those apply.")
    raise RuntimeError(f"{item['item_id']}: rejected after {ATTEMPTS} attempts: {found}")


def render(item: dict) -> str:
    voc_turn = item["vocalization_turn"]
    lines = [f"## {item['item_id']} · {item['voc_a']} vs {item['voc_b']} · "
             f"{item['emotion_a']} vs {item['emotion_b']}", ""]
    if item.get("situation"):
        lines += [f"**Seed** (`{item['seed_label']}`): {item['situation']}", ""]
    lines += [f"**Scenario:** {item['scenario']}", "",
              f"The tag sits in turn {voc_turn}, spoken by {item['vocalization_speaker']}.", ""]
    for turn in item["baseline"]["turns"]:
        was = next(t["text"] for t in item["sol_baseline"]["turns"]
                   if t["turn"] == turn["turn"])
        if turn["turn"] != voc_turn:
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}")
        else:
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}  ← baseline")
            for key in ("condition_a", "condition_b"):
                tagged = next(t for t in item[key]["turns"] if t["turn"] == voc_turn)
                lines.append(f"{turn['turn']}. **{turn['speaker']}:** {tagged['text']}")
        if tidy(was) != tidy(turn["text"]):
            lines.append(f"   <sub>was: {was}</sub>")
    lines += ["", "---", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="pairs.json")
    parser.add_argument("--out-tag", default="spoken")
    parser.add_argument("--model", default=T.PLACER)
    parser.add_argument("--only", action="append", help="item ids")
    args = parser.parse_args()

    source = json.loads((OUT / args.source).read_text())
    out_json = OUT / f"pairs_{args.out_tag}.json"
    out_md = OUT / f"pairs_{args.out_tag}.md"

    done, failed = [], []
    for item in source["items"]:
        if args.only and item["item_id"] not in args.only:
            continue
        try:
            after, attempts = rewrite(item, args.model)
        except RuntimeError as exc:
            failed.append(str(exc))
            print(f"  {item['item_id']} · FAILED")
            continue
        fresh = dict(item)
        fresh["sol_baseline"] = item["baseline"]
        fresh["rewrite_attempts"] = attempts
        fresh["baseline"] = from_marker(after, None)
        fresh["baseline"]["vocalization"] = "none"
        fresh["baseline"]["target_emotion"] = "ambiguous"
        for key, tag, voc, emotion in (("condition_a", item["tag_a"], item["voc_a"],
                                        item["emotion_a"]),
                                       ("condition_b", item["tag_b"], item["voc_b"],
                                        item["emotion_b"])):
            fresh[key] = from_marker(after, tag)
            fresh[key]["vocalization"] = voc
            fresh[key]["target_emotion"] = emotion
        done.append(fresh)
        old = " ".join(t["text"] for t in item["baseline"]["turns"])
        new = " ".join(t["text"] for t in fresh["baseline"]["turns"])
        print(f"  {item['item_id']} · attempt {attempts} · "
              f"{len(old.split())}→{len(new.split())} words", flush=True)

    out_json.write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "source": args.source, "writer": source.get("writer"),
         "rewriter": args.model,
         "rewrite": "register only: spoken English, same meaning, same speakers, same "
                    "information, tag position preserved",
         "vocalizations": source.get("vocalizations"), "items": done},
        indent=2, ensure_ascii=False) + "\n")
    out_md.write_text("# v6 · minimal-pair contrast sets, spoken register\n\n"
                      + "".join(render(e) for e in done))
    print(f"\n{out_json.relative_to(HERE.parent)} · {len(done)} items")
    for line in failed:
        print(f"  {line}"[:170])


if __name__ == "__main__":
    main()

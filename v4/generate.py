"""Write one contrastive pair per seed: the same dialogue, two vocalizations, two framings.

The design point is that the two conditions differ in exactly one thing — which non-speech
vocalization a silent third speaker produces — so any difference in how a model answers is
attributable to that sound and nothing else.

**The shared transcript is written once and both conditions are built from it.** The model
returns the spoken turns plus one insertion point, never two versions, which makes five of the
design's constraints true by construction rather than things to check afterwards: identical
transcript, identical speakers, identical turn order, exactly one vocalization, identical
placement. What is left to validate is what construction cannot guarantee — that the silent
speaker really is silent, that the two labels differ and cross valence, and that the words do
not settle the emotion by themselves.

That last one is the whole experiment. If the transcript says "I'm so relieved", the sound has
nothing left to do, and a model can score well without hearing it at all.

    python v4/generate.py --limit 5      # a pilot
    python v4/generate.py                # every seed
    python v4/generate.py --only v4_003
"""

from __future__ import annotations

import argparse
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import text_models as T

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
PAIRS = OUT / "pairs.json"
READABLE = OUT / "pairs.md"

POSITIVE = ("achievement", "amusement", "pleasure", "relief")
NEGATIVE = ("anger", "disgust", "fear", "sadness")
LABELS = POSITIVE + NEGATIVE

MIN_TURNS, MAX_TURNS = 3, 6
ATTEMPTS = 4

# Words that decide the emotion before the sound gets a chance to. The prompt asks for
# "emotionally interpretable but under-specified" lines; this is that requirement made
# checkable. Matched on word boundaries against the shared transcript only.
# The speaker labels are scaffolding, not names. A line like "this one has C's name on it"
# reads fine on the page and then becomes a spoken letter in the audio, on top of telling the
# listener there is a third participant the design would rather they simply hear.
# "A" is left out of the standalone check because it is also an article.
SPEAKER_LEAK = re.compile(r"\b[BC]\b|\b[ABC][\u2019']s\b")

EXPLICIT = re.compile(
    r"\b(sad|sadder|saddest|happy|happier|glad|thrilled|delighted|miserable|heartbroken|"
    r"relieved|relief|terrified|terrifying|scared|afraid|frightened|petrified|"
    r"disgusting|disgusted|revolting|gross|sickening|"
    r"hilarious|funny|hysterical|laughing|amusing|"
    r"furious|angry|livid|enraged|pissed|"
    r"devastated|awful|horrible|terrible|wonderful|amazing|fantastic|"
    r"excited|proud|ashamed|humiliated|mortified|grateful|thankful|"
    r"upset|distraught|ecstatic|overjoyed|depressed|anxious|worried)\b", re.I)

SYSTEM = """You generate contrastive dialogue pairs for studying how non-speech vocalizations
change the emotional framing of the same spoken interaction.

You are given one scenario from EmpatheticDialogues as a seed. Use it only as the semantic and
interpersonal seed. Do not copy the original dialogue, and never name the seed emotion in the
dialogue you write.

WHAT YOU WRITE

One spoken transcript, and one point in it where a silent speaker produces a single non-speech
vocalization. Two conditions are then built from what you return: identical in every respect
except which vocalization is heard. You therefore write the words ONCE.

THE TWO LABELS ARE GIVEN TO YOU

You do not choose them. Each request names one positive and one negative label, and your job is
to write a scenario and dialogue that both of them could plausibly reinterpret. They mean:

  achievement  triumph at having accomplished or won something; the sound of succeeding
  amusement    finding something funny
  pleasure     SENSORY pleasure — taste, warmth, touch, smell, physical comfort. Not
               sentimental warmth, not satisfaction at good news, not pride. A gift with
               personal meaning is NOT this. Something eaten, felt, smelled or heard is.
  relief       a burden lifted, a feared outcome avoided, tension released

  anger        indignation, being wronged
  disgust      revulsion, often physical
  fear         alarm, dread, being frightened
  sadness      grief, loss, being downcast

If you are given `pleasure`, the dialogue must contain a concrete sensory thing the sound could
be reacting to — a meal, warmth, a smell, a texture. Without one the label is wrong for the
scenario and you should say so rather than write it anyway.

THE SILENT SPEAKER

Speakers A and B do all the talking. Speaker C produces the vocalization and NOTHING else:
no line before it, no line after it, no words anywhere in the dialogue. C exists only to make
that one sound. Do not give C a spoken turn under any circumstances.

THE WORDS MUST NOT SETTLE THE EMOTION

This is the requirement everything else rests on. Write the spoken lines so that BOTH framings
remain genuinely plausible when you read the transcript alone. A reader who cannot hear the
sound should not be able to tell which of the two emotions is in play.

That rules out lines like "I'm so sad", "this is disgusting", "I'm terrified", "I'm so
relieved", "that's hilarious". It rules out emotion adjectives generally. Prefer
under-specified statements that report events and leave the appraisal open:
  "So that's really it."
  "Apparently everyone saw it."
  "They called me this morning."
  "We don't have to go back."
  "That's what they decided."

Place the vocalization so that at least one spoken turn follows it, and write that following
line to be the most emotionally ambiguous of all — it is the line the sound reinterprets.

BEFORE YOU ANSWER, CHECK

1. Reading the spoken words alone, could this conversation honestly support BOTH framings? If
   one is already obvious from the words, rewrite.
2. Would hearing vocalization A make one framing clearly more salient, and vocalization B the
   competing one? If the two sounds would leave the conversation meaning the same thing,
   choose a different pair or a different scenario angle.
3. Is the silent speaker completely silent?

If the seed scenario genuinely cannot support the two labels you were given — not merely that
it is hard, but that one of them would be incoherent — set `feasible` to false and explain in
`why`. A forced pair is worse than a missing one. Otherwise set it to true.

Return JSON only."""


def schema() -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["feasible", "turns", "voc_after_turn", "emotion_a", "emotion_b",
                     "framing_a", "framing_b", "why"],
        "properties": {
            "turns": {
                "type": "array", "minItems": MIN_TURNS, "maxItems": MAX_TURNS,
                "items": {"type": "object", "additionalProperties": False,
                          "required": ["speaker", "text"],
                          "properties": {"speaker": {"type": "string", "enum": ["A", "B"]},
                                         "text": {"type": "string"}}}},
            "feasible": {"type": "boolean",
                         "description": "false if this seed cannot honestly carry both labels"},
            "voc_after_turn": {"type": "integer",
                               "description": "the vocalization follows this many spoken turns"},
            "emotion_a": {"type": "string", "enum": list(LABELS)},
            "emotion_b": {"type": "string", "enum": list(LABELS)},
            "framing_a": {"type": "string"},
            "framing_b": {"type": "string"},
            "why": {"type": "string"}},
    }


def prompt_for(seed: dict, pair: tuple[str, str]) -> str:
    return (f"Seed emotion: {seed['emotion']}\n"
            f"Seed scenario: {seed['situation']}\n\n"
            f"Positive label to use: {pair[0]}\n"
            f"Negative label to use: {pair[1]}")


# Every positive label against every negative one: sixteen cells, filled evenly. Letting the
# writer choose produced a lopsided set — pleasure in the positive slot 16 times of 40, two
# combinations never used at all — and the skew was partly semantic, since the writer did not
# know what `pleasure` meant and reached for it as a generic positive.
ALL_PAIRS = [(p, n) for p in POSITIVE for n in NEGATIVE]


def problems(seed: dict, result: dict, pair: tuple[str, str]) -> list[str]:
    found = []
    turns = result["turns"]
    after = result["voc_after_turn"]

    if not 1 <= after <= len(turns) - 1:
        found.append(f"voc_after_turn {after} leaves no spoken turn after the vocalization "
                     f"({len(turns)} turns)")

    speakers = {t["speaker"] for t in turns}
    if "C" in speakers:
        found.append("speaker C has a spoken line; C must never speak")
    if len(speakers) < 2:
        found.append("only one speaker talks; the dialogue needs two")

    a, b = result["emotion_a"], result["emotion_b"]
    if (a, b) != pair:
        found.append(f"you were given {pair[0]}/{pair[1]} but returned {a}/{b}; "
                     "the labels are assigned, not chosen")

    spoken = " ".join(t["text"] for t in turns)
    leaks = sorted({m.group(0).lower() for m in EXPLICIT.finditer(spoken)})
    if leaks:
        found.append(f"the words settle the emotion by themselves: {leaks}")
    if re.search(rf"\b{re.escape(seed['emotion'])}\b", spoken, re.I):
        found.append(f"the transcript names the seed emotion {seed['emotion']!r}")
    labels = sorted({m.group(0) for m in SPEAKER_LEAK.finditer(spoken)})
    if labels:
        found.append(f"the words refer to a speaker by label ({labels}); speakers are never "
                     "named in the dialogue")
    return found


def as_positive_first(result: dict) -> dict:
    """Store the positive label as condition A, always.

    The writer is free to return the pair either way round and sometimes does. Nothing in the
    design depends on the order — presentation is randomized at test time — but a dataset where
    slot A is sometimes positive and sometimes negative makes every later grouping a special
    case. Swapping here keeps the labels, the framings and the built conditions together.
    """
    if result["emotion_a"] in POSITIVE:
        return result
    swapped = dict(result)
    swapped["emotion_a"], swapped["emotion_b"] = result["emotion_b"], result["emotion_a"]
    swapped["framing_a"], swapped["framing_b"] = result["framing_b"], result["framing_a"]
    return swapped


def condition(turns: list[dict], after: int, label: str) -> list[dict]:
    """The full turn sequence for one condition, silent speaker included."""
    out = [dict(t, kind="speech") for t in turns]
    out.insert(after, {"speaker": "C", "kind": "vocalization", "label": label})
    return out


class Infeasible(RuntimeError):
    """The seed cannot honestly carry the assigned pair. Try a different seed, not a retry."""


def write_item(seed: dict, pair: tuple[str, str], item_id: str) -> dict:
    prompt = prompt_for(seed, pair)
    last: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        result = T.retry(T.json_call, T.WRITER, SYSTEM, prompt, schema(), "contrastive_pair")
        if not result.get("feasible", True):
            raise Infeasible(f"{pair[0]}/{pair[1]} does not fit "
                             f"{seed['situation'][:60]!r}: {result.get('why','')[:90]}")
        found = problems(seed, result, pair)
        if not found:
            result = as_positive_first(result)
            turns, after = result["turns"], result["voc_after_turn"]
            return {"item_id": item_id, "seed_emotion": seed["emotion"],
                    "situation": seed["situation"], "attempts": attempt,
                    "assigned_pair": list(pair),
                    "turns": turns, "voc_after_turn": after,
                    "voc_speaker": "C",
                    "emotion_a": result["emotion_a"], "emotion_b": result["emotion_b"],
                    "framing_a": result["framing_a"], "framing_b": result["framing_b"],
                    "why": result["why"],
                    "condition_a": condition(turns, after, result["emotion_a"]),
                    "condition_b": condition(turns, after, result["emotion_b"])}
        last = found
        prompt = (prompt_for(seed, pair) + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in found)
                  + "\nRewrite so that none of those apply.")
    raise RuntimeError(f"{item_id}: rejected after {ATTEMPTS} attempts: {last}")


def render(item: dict) -> str:
    lines = [f"## {item['item_id']}", "",
             f"**Seed emotion:** {item['seed_emotion']}  ",
             f"**Seed scenario:** {item['situation']}", "",
             "**Shared transcript:**", ""]
    lines += [f"- Speaker {t['speaker']}: {t['text']}" for t in item["turns"]]
    lines += ["", f"**Contrast:** {item['emotion_a']} (A) vs {item['emotion_b']} (B)", ""]
    for name, key in (("Condition A", "condition_a"), ("Condition B", "condition_b")):
        lines.append(f"*{name}*")
        lines.append("")
        for turn in item[key]:
            lines.append(f"- Speaker {turn['speaker']}: "
                         + (f"`<{turn['label']}>`" if turn["kind"] == "vocalization"
                            else turn["text"]))
        lines.append("")
    lines += [f"**Framing A:** {item['framing_a']}", "",
              f"**Framing B:** {item['framing_b']}", "",
              f"**Why this pair works:** {item['why']}", "", "---", ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-pair", type=int, default=3,
                        help="items per positive/negative combination; 16 combinations")
    parser.add_argument("--only", action="append", help="item ids")
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pool = json.loads((OUT / "seeds.json").read_text())["items"]

    # One item per (combination, repeat), each drawing the next unused seed. A seed that cannot
    # carry its assigned pair is set aside and the next one tried, so an awkward combination
    # costs a seed rather than a cell.
    plan = [(f"v4_{n:03d}", pair)
            for n, pair in enumerate(
                [p for _ in range(args.per_pair) for p in ALL_PAIRS], start=1)]
    if args.only:
        plan = [(item_id, pair) for item_id, pair in plan if item_id in args.only]

    existing = json.loads(PAIRS.read_text())["items"] if PAIRS.exists() else []
    by_id = {e["item_id"]: e for e in existing}
    used = {e["situation"] for e in by_id.values()}
    queue = [s for s in pool if s["situation"] not in used]
    rng = random.Random(args.seed)
    rng.shuffle(queue)

    skipped, failed = [], []
    for item_id, pair in plan:
        item = None
        while queue and item is None:
            seed = queue.pop()
            try:
                item = write_item(seed, pair, item_id)
            except Infeasible as exc:
                skipped.append(f"{item_id} {exc}")
                print(f"  {item_id} · {pair[0]}/{pair[1]} · seed rejected as infeasible, "
                      f"trying another", flush=True)
            except RuntimeError as exc:
                failed.append(str(exc))
                print(f"  {item_id} · FAILED, continuing", flush=True)
                break
        if item is None:
            continue
        by_id[item_id] = item
        order = {p: n for n, (p, _) in enumerate(plan)}
        ordered = sorted(by_id.values(), key=lambda e: order.get(e["item_id"], 999))
        PAIRS.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "writer": T.WRITER, "labels": list(LABELS),
             "assignment": "every positive label against every negative one, "
                           f"{args.per_pair} item(s) each",
             "items": ordered}, indent=2, ensure_ascii=False) + "\n")
        READABLE.write_text("# v4 contrastive pairs\n\n"
                            + "".join(render(e) for e in ordered))
        print(f"  {item_id} · {item['seed_emotion']:12} · "
              f"{item['emotion_a']}/{item['emotion_b']:11} · "
              f"{len(item['turns'])} turns, voc after {item['voc_after_turn']} · "
              f"attempt {item['attempts']}", flush=True)

    ordered = list(by_id.values())
    counts: dict[str, int] = {}
    for item in ordered:
        key = f"{item['emotion_a']}/{item['emotion_b']}"
        counts[key] = counts.get(key, 0) + 1
    print(f"\nout/pairs.json · {len(ordered)} items · "
          f"{len(counts)}/{len(ALL_PAIRS)} combinations filled")
    thin = [f"{p}/{n}" for p, n in ALL_PAIRS if counts.get(f"{p}/{n}", 0) < args.per_pair]
    if thin:
        print(f"  short of {args.per_pair}: {thin}")
    if skipped:
        print(f"  {len(skipped)} seed(s) set aside as infeasible")
        for line in skipped[:5]:
            print(f"    {line}"[:170])
    if failed:
        print(f"  {len(failed)} failed:")
        for line in failed:
            print(f"    {line}"[:170])


if __name__ == "__main__":
    main()

"""Write contrastive pairs from personas: one speaker talks, the other only makes a sound.

v4 seeds each item with an EmpatheticDialogues scenario and has two people talking while a
silent third produces the vocalization. v5 changes both ends. The scenario is invented from two
PersonaChat personas rather than given, and there is no third party — the conversation has
exactly two people, one of whom never says a word.

That makes the silent speaker a participant rather than a bystander. Their one sound is their
entire contribution, and it is the only thing that differs between the two conditions.

Persona coherence is handled where it can be judged. The flat PersonaChat pool has lost its
groupings, so five candidate sentences are offered per speaker and the writer keeps only those
that could describe the same person, reporting which — checked here against what was offered.

    python v5/generate.py --per-pair 1     # one item per emotion combination, 16 in all
    python v5/generate.py --per-pair 3
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
ALL_PAIRS = [(p, n) for p in POSITIVE for n in NEGATIVE]

MIN_TURNS, MAX_TURNS = 3, 6
ATTEMPTS = 4

EXPLICIT = re.compile(
    r"\b(sad|sadder|saddest|happy|happier|glad|thrilled|delighted|miserable|heartbroken|"
    r"relieved|relief|terrified|terrifying|scared|afraid|frightened|petrified|"
    r"disgusting|disgusted|revolting|gross|sickening|"
    r"hilarious|funny|hysterical|laughing|amusing|"
    r"furious|angry|livid|enraged|pissed|"
    r"devastated|awful|horrible|terrible|wonderful|amazing|fantastic|"
    r"excited|proud|ashamed|humiliated|mortified|grateful|thankful|"
    r"upset|distraught|ecstatic|overjoyed|depressed|anxious|worried)\b", re.I)

SPEAKER_LEAK = re.compile(r"\b[AB]\b(?!\s+(?:lot|bit|few|while|little))|\b[AB][’']s\b")

SYSTEM = """You write two-person scenes in which only one person speaks.

You are given two personas and two emotion labels. Invent a situation from the personas and
write a short scene between exactly two people:

  Speaker A  talks. Every spoken line in the scene is A's.
  Speaker B  never speaks. B's entire contribution is ONE non-speech vocalization, at one
             point in the scene. No words from B, before or after, anywhere.

Two conditions are then built from what you return, identical except for which vocalization B
makes. You therefore write the words ONCE, and they must work for both.

THE TWO LABELS ARE GIVEN TO YOU

You do not choose them. They mean:

  achievement  triumph at having accomplished or won something; the sound of succeeding
  amusement    finding something funny
  pleasure     SENSORY pleasure — taste, warmth, touch, smell, physical comfort. Not
               sentimental warmth, not satisfaction at good news, not pride. A gift with
               personal meaning is NOT this; something eaten, felt or smelled is.
  relief       a burden lifted, a feared outcome avoided, tension released

  anger        indignation, being wronged
  disgust      revulsion, often physical
  fear         alarm, dread, being frightened
  sadness      grief, loss, being downcast

If you are given `pleasure`, the scene needs a concrete sensory thing already present in it for
the sound to be reacting to — and it must belong there naturally. Do not insert food or a smell
into an unrelated scene just to satisfy the label; if the personas and situation cannot carry a
sensory moment honestly, say the pair is infeasible instead.

THE PERSONAS

Five candidate sentences are offered for each speaker. They come from a pool whose groupings
were lost, so some will contradict each other. Keep only the ones that could describe the same
person — three or four each — and report exactly which you kept, copied verbatim.

**The persona decides who these people are, where they are, and what they are to each other.
It is not a checklist to read out.** Most of it should never be said aloud. Its job is to make
the situation specific: a nurse and a student give you a skills lab, a grill cook and an art
teacher give you a diner. Pick the one or two facts the scene actually needs — the ones that,
if removed, would make the scene stop working — and let the rest show in the choice of setting
and in how A talks. Naming three persona facts in one line is the failure mode; a reader should
feel these are particular people without being told their hobbies.

B's persona matters even though B is silent: it should be believable that this particular
person would react with this particular sound, and A may refer to B in ways that fit.

BOTH SOUNDS REACT TO THE SAME THING

Name it in `shared_referent`. It can be either:

  - the situation as a whole — everything A has just described, taken together; or
  - one specific object or event in the scene

Either is fine. What is not fine is the two sounds pointing at different things. Both
vocalizations react to the SAME referent, and the conditions differ in how B appraises it.

This is the difference between a real contrast and a fake one. A scene where the positive sound
is about the election result while the negative sound is about the stew on the stove tests
nothing: the two conditions have different subjects, and a listener only has to work out which
object the sound is pointing at — no reading of emotion required. Written properly, a listener
who has identified the referent still has to hear the sound to know whether B takes it as good
or bad.

Both `framing_a` and `framing_b` must therefore describe reactions to the shared referent, and
each must name it.

THE WORDS MUST NOT SETTLE THE EMOTION

This is what everything rests on. Write A's lines so that BOTH framings stay genuinely
plausible when read without the sound. Someone reading the transcript should not be able to
tell which of the two emotions B is feeling.

No emotion adjectives, no "I'm so relieved", no "that's disgusting". Prefer lines that report
and leave the appraisal open. Place the vocalization so at least one of A's lines follows it,
and make that following line the most ambiguous of all — it is the line the sound reinterprets.

Never write a speaker's letter into the dialogue as if it were a name.

If the personas genuinely cannot carry both labels, set `feasible` to false and say why in
`why`. A forced pair is worse than a missing one.

Return JSON only."""


def schema() -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["feasible", "persona_a", "persona_b", "setting", "turns",
                     "voc_after_turn", "shared_referent", "emotion_a", "emotion_b",
                     "framing_a", "framing_b", "why"],
        "properties": {
            "feasible": {"type": "boolean"},
            "persona_a": {"type": "array", "items": {"type": "string"},
                          "description": "the candidate sentences kept for A, verbatim"},
            "persona_b": {"type": "array", "items": {"type": "string"}},
            "setting": {"type": "string",
                        "description": "one sentence: who these two are to each other, and where"},
            "turns": {"type": "array", "minItems": MIN_TURNS, "maxItems": MAX_TURNS,
                      "items": {"type": "object", "additionalProperties": False,
                                "required": ["speaker", "text"],
                                "properties": {"speaker": {"type": "string", "enum": ["A"]},
                                               "text": {"type": "string"}}}},
            "voc_after_turn": {"type": "integer"},
            "shared_referent": {"type": "string",
                                "description": "the one thing both vocalizations react to: "
                                               "the whole situation, or one object in it"},
            "emotion_a": {"type": "string", "enum": list(LABELS)},
            "emotion_b": {"type": "string", "enum": list(LABELS)},
            "framing_a": {"type": "string"}, "framing_b": {"type": "string"},
            "why": {"type": "string"}},
    }


def prompt_for(item: dict, pair: tuple[str, str]) -> str:
    lines = ["Candidate persona sentences for Speaker A (the one who talks):"]
    lines += [f"  - {s}" for s in item["candidates_a"]]
    lines += ["", "Candidate persona sentences for Speaker B (the one who only makes a sound):"]
    lines += [f"  - {s}" for s in item["candidates_b"]]
    lines += ["", f"Positive label to use: {pair[0]}", f"Negative label to use: {pair[1]}"]
    return "\n".join(lines)


class Infeasible(RuntimeError):
    """These personas cannot carry the assigned pair. Try other personas, not a retry."""


STOPWORDS = {"like", "love", "have", "really", "very", "also", "want", "would", "with",
             "that", "this", "they", "them", "from", "into", "been", "some", "when",
             "time", "back", "good", "much", "more", "than", "then", "know", "just"}


def surfaced(persona: list[str], spoken: str) -> list[str]:
    """Which persona sentences show up in the words themselves.

    A sentence counts as surfaced when half its distinctive words appear, at least one. The
    ratio matters because persona sentences are short and uneven: "I like to water ski" carries
    a single distinctive word, so a fixed two-word threshold could never catch it however
    plainly it was recited. Matching is by prefix, since the writer paraphrases — "water-skiing"
    for "water ski".

    This is a proxy for recitation, not a judgement about whether a fact belonged in the scene.
    One or two surfacing is a scene using its personas; four is a scene reading them out.
    """
    words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", spoken)}
    out = []
    for sentence in persona:
        distinctive = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", sentence)
                       if w.lower() not in STOPWORDS]
        hits = sum(1 for d in distinctive
                   if any(w.startswith(d[:4]) or d.startswith(w[:4]) for w in words))
        if distinctive and hits >= max(1, len(distinctive) // 2):
            out.append(sentence)
    return out


def problems(item: dict, result: dict, pair: tuple[str, str]) -> list[str]:
    found = []
    turns = result["turns"]
    after = result["voc_after_turn"]

    if not 1 <= after <= len(turns) - 1:
        found.append(f"voc_after_turn {after} leaves no spoken line after the sound "
                     f"({len(turns)} turns)")
    if any(t["speaker"] != "A" for t in turns):
        found.append("only speaker A may have spoken lines; B never speaks")

    if (result["emotion_a"], result["emotion_b"]) != pair:
        found.append(f"you were given {pair[0]}/{pair[1]} but returned "
                     f"{result['emotion_a']}/{result['emotion_b']}")

    for who, key in (("A", "persona_a"), ("B", "persona_b")):
        kept = [s.strip() for s in result[key]]
        offered = {s.strip() for s in item[f"candidates_{who.lower()}"]}
        if not 2 <= len(kept) <= 5:
            found.append(f"persona {who} keeps {len(kept)} sentences; keep three or four")
        invented = [s for s in kept if s not in offered]
        if invented:
            found.append(f"persona {who} includes sentences that were not offered: {invented}")

    spoken = " ".join(t["text"] for t in turns)
    leaks = sorted({m.group(0).lower() for m in EXPLICIT.finditer(spoken)})
    if leaks:
        found.append(f"the words settle the emotion by themselves: {leaks}")
    labels = sorted({m.group(0) for m in SPEAKER_LEAK.finditer(spoken)})
    if labels:
        found.append(f"the words refer to a speaker by letter ({labels})")

    # Both framings must be about the shared referent. Checking that each names some of it is
    # crude, but it catches the failure that matters: framings that have drifted onto different
    # objects, where the contrast stops being about appraisal at all.
    referent = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", result["shared_referent"])
                if w.lower() not in STOPWORDS]
    if referent:
        for side in ("framing_a", "framing_b"):
            words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", result[side])}
            if not any(any(w.startswith(r[:4]) for w in words) for r in referent):
                found.append(f"{side} does not mention the shared referent "
                             f"({result['shared_referent']!r}); both sounds must react to the "
                             "same thing")

    for who, key in (("A", "persona_a"), ("B", "persona_b")):
        recited = surfaced(result[key], spoken)
        if len(recited) > 2:
            found.append(f"persona {who} is being recited: {len(recited)} of its facts are "
                         f"said aloud ({recited}). Let the persona choose the situation and "
                         "the manner of speaking; say only what the scene needs.")
    return found


def condition(turns: list[dict], after: int, label: str) -> list[dict]:
    out = [dict(t, kind="speech") for t in turns]
    out.insert(after, {"speaker": "B", "kind": "vocalization", "label": label})
    return out


def write_item(item: dict, pair: tuple[str, str], item_id: str,
               writer: str = T.WRITER) -> dict:
    prompt = prompt_for(item, pair)
    last: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        result = T.retry(T.json_call, writer, SYSTEM, prompt, schema(), "persona_pair")
        if not result.get("feasible", True):
            raise Infeasible(f"{pair[0]}/{pair[1]}: {result.get('why','')[:100]}")
        found = problems(item, result, pair)
        if not found:
            turns, after = result["turns"], result["voc_after_turn"]
            return {"item_id": item_id, "attempts": attempt,
                    "assigned_pair": list(pair),
                    "persona_a": result["persona_a"], "persona_b": result["persona_b"],
                    "setting": result["setting"],
                    "turns": turns, "voc_after_turn": after, "voc_speaker": "B",
                    "shared_referent": result["shared_referent"],
                    "emotion_a": result["emotion_a"], "emotion_b": result["emotion_b"],
                    "framing_a": result["framing_a"], "framing_b": result["framing_b"],
                    "why": result["why"],
                    "condition_a": condition(turns, after, result["emotion_a"]),
                    "condition_b": condition(turns, after, result["emotion_b"])}
        last = found
        prompt = (prompt_for(item, pair) + "\n\nYour previous answer was rejected:\n"
                  + "\n".join(f"- {line}" for line in found)
                  + "\nRewrite so that none of those apply.")
    raise RuntimeError(f"{item_id}: rejected after {ATTEMPTS} attempts: {last}")


def render(item: dict) -> str:
    lines = [f"## {item['item_id']}", "",
             f"**Setting:** {item['setting']}", "",
             f"**Both sounds react to:** {item.get('shared_referent','—')}", "",
             "**Speaker A** (talks): " + " ".join(item["persona_a"]), "",
             "**Speaker B** (only makes one sound): " + " ".join(item["persona_b"]), "",
             f"**Contrast:** {item['emotion_a']} (A) vs {item['emotion_b']} (B)", "",
             "**Scene:**", ""]
    for turn in item["condition_a"]:
        lines.append(f"- Speaker {turn['speaker']}: "
                     + (f"`<{item['emotion_a']}>` / `<{item['emotion_b']}>`"
                        if turn["kind"] == "vocalization" else turn["text"]))
    lines += ["", f"**Framing A:** {item['framing_a']}", "",
              f"**Framing B:** {item['framing_b']}", "",
              f"**Why this pair works:** {item['why']}", "", "---", ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-pair", type=int, default=1)
    parser.add_argument("--writer", default=T.WRITER, help="model that writes the scenes")
    parser.add_argument("--only", action="append")
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pool = json.loads((OUT / "personas.json").read_text())["items"]

    plan = [(f"v5_{n:03d}", pair)
            for n, pair in enumerate(
                [p for _ in range(args.per_pair) for p in ALL_PAIRS], start=1)]
    if args.only:
        plan = [(i, p) for i, p in plan if i in args.only]

    existing = json.loads(PAIRS.read_text())["items"] if PAIRS.exists() else []
    by_id = {e["item_id"]: e for e in existing}
    queue = [p for p in pool if p["item_id"] not in by_id]
    random.Random(args.seed).shuffle(queue)

    skipped, failed = [], []
    for item_id, pair in plan:
        built = None
        while queue and built is None:
            personas = queue.pop()
            try:
                built = write_item(personas, pair, item_id, args.writer)
            except Infeasible as exc:
                skipped.append(f"{item_id} {exc}")
                print(f"  {item_id} · {pair[0]}/{pair[1]} · personas infeasible, "
                      "trying others", flush=True)
            except RuntimeError as exc:
                failed.append(str(exc))
                print(f"  {item_id} · FAILED", flush=True)
                break
        if built is None:
            continue
        by_id[item_id] = built
        order = {i: n for n, (i, _) in enumerate(plan)}
        ordered = sorted(by_id.values(), key=lambda e: order.get(e["item_id"], 999))
        PAIRS.write_text(json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "writer": args.writer, "labels": list(LABELS),
             "design": "two speakers; A talks, B only produces one vocalization",
             "items": ordered}, indent=2, ensure_ascii=False) + "\n")
        READABLE.write_text("# v5 persona pairs\n\n" + "".join(render(e) for e in ordered))
        print(f"  {item_id} · {built['emotion_a']}/{built['emotion_b']:11} · "
              f"{len(built['turns'])} A-turns, sound after {built['voc_after_turn']} · "
              f"attempt {built['attempts']}", flush=True)

    print(f"\nout/pairs.json · {len(by_id)} items")
    if skipped:
        print(f"  {len(skipped)} persona set(s) skipped as infeasible")
        for line in skipped[:4]:
            print(f"    {line}"[:160])
    if failed:
        for line in failed:
            print(f"    {line}"[:160])


if __name__ == "__main__":
    main()

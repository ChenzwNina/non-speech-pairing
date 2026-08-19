"""Generate contrastive pairs: same setup, two vocalizations, two next responses.

Each version is exactly CONTEXT_TURNS + 2 turns:

    turns 1..N     the speaking side, identical across the two versions
    turn  N+1      B: [voc]        <- B's first contribution, vocalization only
    turn  N+2      the reply that the vocalization selects

Turn N is the trigger: the reveal, admission, or number that B reacts to. Nothing
may sit between the trigger and the vocalization.

Two speaker layouts:

    --speakers 2  (default)  A tells it, B reacts, A replies
    --speakers 3             A and C converse, B reacts, A or C replies

Usage:
    python predicting_response/generate.py
    python predicting_response/generate.py --speakers 3 --context-turns 8
    python predicting_response/generate.py --contrast laughter-sigh --n 2
    python predicting_response/generate.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")
DEFAULT_OUT = HERE / "out" / "pairs.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000
CONTEXT_TURNS = 4
SPEAKERS = 2
MAX_ATTEMPTS = 4

VOCALIZATIONS = {
    "gasp": {
        "formula": "[gasp]",
        "meanings": [
            "surprise",
            "pleasant surprise",
            "shock",
            "fear",
            "admiration",
            "disbelief",
            "sudden realization",
        ],
    },
    "grunt": {
        "formula": "[grunt]",
        "meanings": [
            "reluctant agreement",
            "annoyance",
            "acknowledgment",
            "dissatisfaction",
            "dismissal",
            "impatience",
            "skepticism",
        ],
    },
    "laughter": {
        "formula": "[laughter]",
        "meanings": [
            "genuine amusement",
            "teasing",
            "mockery",
            "awkward amusement",
            "nervousness",
            "disbelief",
            "shared amusement",
            "irony",
        ],
    },
    "sigh": {
        "formula": "[sigh]",
        "meanings": [
            "frustration",
            "disappointment",
            "relief",
            "resignation",
            "impatience",
            "exhaustion",
        ],
    },
    "sob": {
        "formula": "[sob]",
        "meanings": [
            "sadness",
            "hurt",
            "emotional overwhelm",
            "relief after distress",
            "being deeply moved",
        ],
    },
    "yawn": {
        "formula": "[yawn]",
        "meanings": [
            "boredom",
            "tiredness",
            "lack of interest",
            "exhaustion",
            "disengagement",
            "difficulty maintaining attention",
        ],
    },
}

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]


def context_speakers(speakers: int) -> list[str]:
    return ["A"] if speakers == 2 else ["A", "C"]


def output_schema(context_turns: int, speakers: int) -> dict:
    allowed = context_speakers(speakers)
    turn_schema = {
        "type": "object",
        "properties": {
            "speaker": {"type": "string", "enum": allowed},
            "text": {"type": "string"},
        },
        "required": ["speaker", "text"],
        "additionalProperties": False,
    }
    version_schema = {
        "type": "object",
        "properties": {
            "vocalization": {"type": "string"},
            "intended_interpretation": {"type": "string"},
            "responder": {"type": "string", "enum": allowed},
            "response": {"type": "string"},
        },
        "required": ["vocalization", "intended_interpretation", "responder", "response"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "pair_id": {"type": "string"},
            "scenario": {"type": "string"},
            "trigger_note": {"type": "string"},
            "shared_context": {
                "type": "array",
                "items": turn_schema,
                "minItems": context_turns,
                "maxItems": context_turns,
            },
            "version_1": version_schema,
            "version_2": version_schema,
            "why_the_vocalization_changes_the_response": {"type": "string"},
        },
        "required": [
            "pair_id",
            "scenario",
            "trigger_note",
            "shared_context",
            "version_1",
            "version_2",
            "why_the_vocalization_changes_the_response",
        ],
        "additionalProperties": False,
    }


TAG_RE = re.compile(r"\[[^\[\]]+\]")
NAME_VOC_RE = re.compile(
    r"(?i)\b("
    r"you (?:just )?(?:laughed|yawned|sighed|gasped|sobbed|grunted)|"
    r"are you (?:laughing|yawning|sighing|gasping|sobbing|crying|tired|sad)|"
    r"you're (?:laughing|yawning|crying)|"
    r"i hear that you are|"
    r"why are you (?:laughing|yawning|sighing|gasping|sobbing|grunting|screaming)|"
    r"stop (?:laughing|yawning|sighing)|"
    r"you sound|"
    r"that (?:laugh|yawn|sigh|gasp|sob|grunt)|"
    r"your (?:laugh|yawn|sigh|gasp|sob|grunt)"
    r")\b"
)
PREDICT_B_RE = re.compile(
    r"(?i)\b("
    r"b always|"
    r"speaker b|"
    r"has been listening|"
    r"b is about to|"
    r"b will (?:laugh|yawn|sigh|gasp|sob|grunt)|"
    r"b can barely|"
    r"keep(?:ing)? (?:his|her|their) eyes open"
    r")\b"
)


def system_prompt(context_turns: int, speakers: int) -> str:
    total = context_turns + 2
    voc_turn = context_turns + 1
    reply_turn = context_turns + 2

    if speakers == 2:
        cast = """Two people are present: **Speaker A** and **Speaker B**.

Speaker A speaks turns 1–{n}. Speaker B says nothing until the vocalization at turn {v}.
Speaker A replies at turn {t}.

A's turns are separate utterances with a beat between them, the way someone tells
something in pieces while the other person listens — not one paragraph split up.""".format(
            n=context_turns, v=voc_turn, t=reply_turn
        )
        context_rule = f"turns 1–{context_turns} are all Speaker A"
        responder_rule = f"Speaker A replies at turn {reply_turn} in both versions."
    else:
        cast = """Three people are present: **Speaker A**, **Speaker B**, and **Speaker C**.

A and C converse across turns 1–{n}, alternating. Speaker B says nothing until the
vocalization at turn {v}. Either A or C replies at turn {t} — the same one in both versions.""".format(
            n=context_turns, v=voc_turn, t=reply_turn
        )
        context_rule = f"turns 1–{context_turns} alternate between Speaker A and Speaker C"
        responder_rule = (
            f"The same speaker (A or C) replies at turn {reply_turn} in both versions."
        )

    return f"""
You are generating dialogue data for a benchmark that tests whether an audio-language
model can use a **non-speech vocalization** to choose the appropriate next spoken response.

The target vocalizations are: gasp, grunt, laughter, sigh, sob, yawn.

---

# Cast

{cast}

Speaker B has **no lexical speech anywhere** in the item. B's vocalization at turn {voc_turn}
is B's first contribution. The benchmark splices in **external audio** for it, so B's voice
must never be established by earlier speech.

Do not write lines like "B has been listening quietly." B's presence should be natural
without narrating it.

---

# Turn structure (hard requirement)

Exactly **{total} turns** per version: {context_rule}, turn {voc_turn} is B's vocalization
alone, turn {total} is the reply. {responder_rule}

Turns 1–{context_turns} are **word-for-word identical** across the two versions. The only
difference at turn {voc_turn} is which vocalization B produces, and that difference must make
a different turn {reply_turn} reply appropriate.

---

# Turn {context_turns} is the trigger — this matters most

Turn {context_turns} is the thing B reacts to. B's vocalization comes **immediately** after it,
so turn {context_turns} must be the beat that invites a reaction: the reveal, the number, the
admission, the punchline, the thing that just went wrong, the decision just announced.

Turns 1 through {context_turns - 1} are setup. Build toward the trigger; do not deliver the
interesting information early and then fill the remaining turns.

Turn {context_turns} must **not** be:

* logistics or scheduling that follows the reveal —
  "It'll be waiting at the front desk whenever we want it."
  If the reveal is at turn {context_turns - 1} and turn {context_turns} is housekeeping,
  the vocalization lands on the wrong beat. Restructure it.
* a question that the turn {reply_turn} speaker then answers —
  "So do I put that bit before or after the case study?"
  That makes turn {reply_turn} an answer to the question instead of a reaction to B.
* a neutral summary, an aside, or a restatement.

Ask yourself: **would a listener naturally react right here?** If B's reaction would make
more sense two turns earlier, the context is built wrong.

`trigger_note` states in one short phrase what turn {context_turns} puts on the table for B
to react to.

---

# The swap test

Write the two replies so that **swapping them is clearly wrong**.

If reply 2 would also work after vocalization 1, the item is invalid.

The most common way this fails: building the pair around a choice the context already
offers — before or after, this venue or that one, today or tomorrow — where either
vocalization could plausibly motivate either option. A gasp does not inherently mean
"put it first" and laughter does not inherently mean "put it last". Avoid arbitrary
two-option choices unless one option is genuinely tied to what B conveyed.

The replies must also commit to **different actions, decisions, or directions** — not the
same decision in two different tones.

Bad, same action in two tones:

    [laughter] -> "That's funny. I'll fix the headline and resend it."
    [sigh]     -> "I know, one more fix. I'll fix the headline and resend it."

Good, the decision itself changes:

    [laughter] -> "Fine, we'll lean into it. Hand me the skewers."
    [sigh]     -> "Okay, I won't gamble on it. I'll go to the bakery."

---

# Both vocalizations must be natural at that point

Ask of each version: **given turns 1–{context_turns}, would this reaction make sense from
someone listening?**

A gasp needs something genuinely surprising or alarming on the table. A sob needs real
emotional weight. A yawn needs length, repetition, or tedium. If the scene does not support
a reaction, do not assign it — invent a different scene, or pick a different meaning for
that vocalization from the list you were given.

Never force an interpretation the situation does not earn. If "sadness" does not fit the
scene, either build a scene where it does, or use a meaning of that vocalization that fits.

Both interpretations must be plausible **for the same context**. That is the point of the
item: the words leave both open, and only the sound decides.

---

# Turn {voc_turn} constraint

B's turn is **only** the plain tag.

Correct: `[laughter]` · `[sigh]`
Incorrect: `[laughter] That's hilarious.` · `Wow. [gasp]` · `[annoyed grunt]` · `[sarcastic laughter]`

The meaning must come from context and acoustics, never from an adjective in the tag.

---

# Turn {reply_turn} constraint

Do not merely identify the sound.

Bad: "You're laughing." · "You yawned." · "Are you crying?"

Good: "Fine, I admit it looked ridiculous." · "Okay, we'll skip the long explanation."
· "I know. We're going in circles again."

The reply should show the **social or pragmatic** reading of B's reaction, and should follow
from it — a listener should be able to work backwards from the reply to what B conveyed.

---

# Undecidable from text alone

Reading turns 1–{context_turns} with B's vocalization hidden, both replies must be genuinely
plausible. If the setup already points at one of them, the audio is carrying no load.

So: no lines that predict B's reaction ("B always laughs at this"), no describing B's state,
and no context that makes one reply the obvious continuation.

---

# Context requirements

Turns 1–{context_turns} should sound like ordinary talk, not exposition; carry no bracketed
tags; avoid specialized knowledge; and give just enough situation to read B's reaction.

Vary relationships (friends, coworkers, classmates, roommates, siblings, partners, teammates)
and situations (telling a story, admitting a mistake, unexpected news, explaining something,
revealing an outcome, waiting, joking, disagreeing, solving a problem). Avoid heavily medical,
violent, sexual, or otherwise sensitive scenes, and avoid constant high drama.

---

# Self-check before output

1. Does B have zero spoken turns before turn {voc_turn}?
2. Is turn {voc_turn} the plain tag and nothing else?
3. Is turn {context_turns} the actual trigger — not logistics, not a question, not a summary?
4. Would a listener naturally react right after turn {context_turns}?
5. Is each vocalization plausible from someone hearing turns 1–{context_turns}?
6. Does each intended interpretation genuinely fit the scene?
7. Are both replies plausible with the vocalization hidden?
8. Does each vocalization clearly favor its own reply?
9. Would swapping the two replies be clearly worse for both?
10. Do the replies commit to different actions, not the same action in two tones?

Rewrite the item if any check fails.

---

# Output rules

Generate exactly ONE contrastive pair matching the user message. Return JSON only.

* `shared_context` holds exactly {context_turns} turns and never includes Speaker B.
* `version_1.vocalization` / `version_2.vocalization` are the exact tags from the user message.
* `intended_interpretation` is the meaning you chose from that vocalization's list — pick the
  one that fits your scene, and make the two differ.
* `response` is the responder's single final line, with no tags.
* `scenario` is a short neutral label, e.g. "roommates deciding how to handle a repair bill".
* `trigger_note` says what turn {context_turns} puts on the table.
* Never mention the intended interpretation inside the dialogue.
""".strip()


JUDGE_PROPERTIES = [
    (
        "trigger_is_last_shared_turn",
        "the final shared turn is not the trigger; B is reacting to logistics, a question, "
        "or a summary instead of to the reveal — restructure so the trigger lands last",
    ),
    (
        "both_vocalizations_natural_here",
        "at least one vocalization is not a natural reaction to that context",
    ),
    (
        "interpretations_fit_the_context",
        "at least one intended interpretation is not earned by the scene",
    ),
    (
        "undecidable_from_text_alone",
        "the context already points at one reply; make both plausible without the voc",
    ),
    (
        "replies_commit_to_different_actions",
        "the two replies commit to the same action and differ only in tone",
    ),
    (
        "voc1_favors_reply1",
        "vocalization 1 does not clearly favor reply 1",
    ),
    (
        "voc2_favors_reply2",
        "vocalization 2 does not clearly favor reply 2",
    ),
    (
        "swapping_replies_is_clearly_worse",
        "the replies can be swapped without the dialogue getting worse",
    ),
]

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{key: {"type": "boolean"} for key, _ in JUDGE_PROPERTIES},
        "notes": {"type": "string"},
    },
    "required": [key for key, _ in JUDGE_PROPERTIES] + ["notes"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """
You are auditing one item from a benchmark that tests whether a model can use a non-speech
vocalization to choose the next spoken response.

Speaker B has not spoken. B's only contribution is a vocalization, produced immediately after
the final turn of the spoken context. One of the earlier speakers then replies.

Judge these properties independently and return JSON only. Judge what is written, not what was
intended; do not be charitable.

1. `trigger_is_last_shared_turn` — is the FINAL turn of the spoken context the thing B is
   reacting to? False if the notable information landed earlier and the final turn is
   logistics, scheduling, a summary, an aside, or a question that the reply then answers.
   A listener should want to react right after the final turn.

2. `both_vocalizations_natural_here` — given only the spoken context, would a listener
   plausibly produce each of the two vocalizations? False if the scene gives a gasp nothing
   surprising, a sob no emotional weight, a yawn no tedium, and so on.

3. `interpretations_fit_the_context` — does each stated interpretation genuinely fit the
   scene? False if a meaning appears forced onto a situation that does not earn it.

4. `undecidable_from_text_alone` — with the vocalization hidden, are both replies genuinely
   plausible? False if the context already points at one.

5. `replies_commit_to_different_actions` — do the replies commit to materially different
   actions, decisions, or directions? False if both settle on the same course and differ only
   in tone, politeness, or an attitude preface.

6. `voc1_favors_reply1` — knowing B produced vocalization 1, is reply 1 clearly the better of
   the two? Be strict: the link must be specific to what that vocalization conveys, not merely
   compatible with it.

7. `voc2_favors_reply2` — the same for vocalization 2 and reply 2.

8. `swapping_replies_is_clearly_worse` — if reply 2 followed vocalization 1 and reply 1
   followed vocalization 2, would both dialogues be clearly worse? False if the swap reads
   about as well. Watch for items built on an arbitrary two-option choice (before or after,
   this or that) where either vocalization could motivate either option.

`notes` is one sentence naming the weakest property.
""".strip()


def judge_pair(client: OpenAI, payload: dict, model: str, effort: str) -> tuple[dict, dict]:
    v1 = payload["version_1"]
    v2 = payload["version_2"]
    lines = ["Spoken context:", ""]
    for index, turn in enumerate(payload["shared_context"], start=1):
        lines.append(f"{index}. {turn['speaker']}: {turn['text']}")
    voc_turn = len(payload["shared_context"]) + 1
    lines += [
        "",
        f"Turn {voc_turn} is Speaker B's vocalization.",
        "",
        f"Vocalization 1: {v1['vocalization']}  (stated interpretation: {v1['intended_interpretation']})",
        f"Reply 1 — {v1['responder']}: {v1['response']}",
        "",
        f"Vocalization 2: {v2['vocalization']}  (stated interpretation: {v2['intended_interpretation']})",
        f"Reply 2 — {v2['responder']}: {v2['response']}",
    ]
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    response = client.responses.create(
        model=model,
        instructions=JUDGE_SYSTEM,
        input="\n".join(lines),
        reasoning={"effort": effort},
        text={
            "format": {
                "type": "json_schema",
                "name": "predicting_response_judge",
                "schema": JUDGE_SCHEMA,
                "strict": True,
            }
        },
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    if response.status != "completed":
        raise RuntimeError(f"judge status={response.status}")
    verdict = json.loads(response.output_text)
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return verdict, usage


def judge_problems(verdict: dict) -> list[str]:
    return [message for key, message in JUDGE_PROPERTIES if not verdict.get(key)]


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def formula_of(voc_id: str) -> str:
    return VOCALIZATIONS[voc_id]["formula"]


def contrast_list() -> list[tuple[str, str]]:
    return list(combinations(VOC_ORDER, 2))


def validate(
    payload: dict, voc1: str, voc2: str, pair_id: str, context_turns: int, speakers: int
) -> list[str]:
    problems: list[str] = []
    allowed = set(context_speakers(speakers))
    if payload.get("pair_id") != pair_id:
        problems.append(f"pair_id should be {pair_id}")

    context = payload.get("shared_context") or []
    if not isinstance(context, list) or len(context) != context_turns:
        problems.append(f"shared_context must have exactly {context_turns} turns")
        return problems

    names = [turn.get("speaker") for turn in context]
    if any(name == "B" for name in names):
        problems.append("Speaker B must have zero spoken turns in shared_context")
    if any(name not in allowed for name in names):
        problems.append(f"shared_context speakers must be in {sorted(allowed)}")
    if speakers == 3:
        if "A" not in names or "C" not in names:
            problems.append("shared_context must include both A and C")
        if any(a == b for a, b in zip(names, names[1:])):
            problems.append("A and C must alternate in shared_context")

    for index, turn in enumerate(context, start=1):
        text = turn.get("text") or ""
        if TAG_RE.search(text):
            problems.append(f"shared_context turn {index} has a tag")
        if not normalize(text):
            problems.append(f"shared_context turn {index} is empty")
        if PREDICT_B_RE.search(text):
            problems.append(f"shared_context turn {index} predicts B's reaction")

    trigger = normalize(context[-1].get("text") or "")
    if trigger.endswith("?"):
        problems.append(
            f"turn {context_turns} is a question, so the reply answers it instead of reacting "
            "to B; make the trigger a statement"
        )
    if not normalize(payload.get("trigger_note") or ""):
        problems.append("trigger_note is empty")

    v1 = payload.get("version_1") or {}
    v2 = payload.get("version_2") or {}
    f1 = formula_of(voc1)
    f2 = formula_of(voc2)
    if normalize(v1.get("vocalization") or "") != f1:
        problems.append(f"version_1.vocalization must be exactly {f1}")
    if normalize(v2.get("vocalization") or "") != f2:
        problems.append(f"version_2.vocalization must be exactly {f2}")

    r1_speaker = v1.get("responder")
    r2_speaker = v2.get("responder")
    if r1_speaker not in allowed or r2_speaker not in allowed:
        problems.append(f"responders must be in {sorted(allowed)}")
    elif r1_speaker != r2_speaker:
        problems.append("both versions must use the same responder")

    r1 = normalize(v1.get("response") or "")
    r2 = normalize(v2.get("response") or "")
    if not r1 or not r2:
        problems.append("both versions need a response")
    if r1 and r1 == r2:
        problems.append("the two responses must differ")
    if TAG_RE.search(r1) or TAG_RE.search(r2):
        problems.append("responses must have no audio tags")
    if NAME_VOC_RE.search(r1) or NAME_VOC_RE.search(r2):
        problems.append("response names the vocalization instead of interpreting it")
    if len(r1.split()) > 28 or len(r2.split()) > 28:
        problems.append("response is too long")

    i1 = normalize(v1.get("intended_interpretation") or "")
    i2 = normalize(v2.get("intended_interpretation") or "")
    if not i1 or not i2:
        problems.append("both versions need an intended_interpretation")
    if i1 and i1.lower() == i2.lower():
        problems.append("intended interpretations must differ")

    if not normalize(payload.get("scenario") or ""):
        problems.append("scenario is empty")

    why = normalize(payload.get("why_the_vocalization_changes_the_response") or "")
    if len(why.split()) < 8:
        problems.append("why_the_vocalization_changes_the_response is too short")

    return problems


def user_prompt(
    voc1: str,
    voc2: str,
    pair_id: str,
    responder: str,
    context_turns: int,
    speakers: int,
    used_scenarios: list[str],
    used_meanings: list[str],
) -> str:
    cast = "Speakers A and B only" if speakers == 2 else "Speakers A, B and C"
    lines = [
        "Generate exactly one contrastive pair.",
        "",
        f"Pair ID: {pair_id}",
        f"Cast: {cast}",
        f"Shared context: exactly {context_turns} turns, "
        + ("all Speaker A" if speakers == 2 else "Speaker A and Speaker C alternating"),
        f"Turn {context_turns}: the trigger B reacts to (a statement, not a question)",
        f"Turn {context_turns + 1}: Speaker B, vocalization only",
        f"Turn {context_turns + 2}: Speaker {responder} in BOTH versions",
        "",
        f"Version 1 vocalization: {formula_of(voc1)}",
        f"  choose one meaning that fits your scene: {', '.join(VOCALIZATIONS[voc1]['meanings'])}",
        f"Version 2 vocalization: {formula_of(voc2)}",
        f"  choose one meaning that fits your scene: {', '.join(VOCALIZATIONS[voc2]['meanings'])}",
        "",
        "Build the scene so BOTH of those vocalizations are natural reactions to the same",
        "context, then let each one select a different reply. Do not force a meaning the",
        "scene does not earn — invent a scene that earns both.",
        "Swapping the two replies must be clearly worse; avoid arbitrary two-option choices.",
    ]
    if used_scenarios:
        lines += ["", "Do not reuse these scenarios:"]
        lines += [f"- {text}" for text in used_scenarios[-16:]]
    if used_meanings:
        lines += ["", "Already used for this contrast; prefer different meanings:"]
        lines += [f"- {text}" for text in used_meanings]
    return "\n".join(lines)


def call_model(
    client: OpenAI,
    prompt: str,
    model: str,
    effort: str,
    context_turns: int,
    speakers: int,
) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.responses.create(
                model=model,
                instructions=system_prompt(context_turns, speakers),
                input=prompt,
                reasoning={"effort": effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "predicting_response_pair",
                        "schema": output_schema(context_turns, speakers),
                        "strict": True,
                    }
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"status={response.status} details={getattr(response, 'incomplete_details', None)}"
                )
            payload = json.loads(response.output_text)
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return payload, usage, response.model
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            wait = 2 ** attempt
            print(f"    retry in {wait}s: {exc}", flush=True)
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


def generate_one(
    client: OpenAI,
    voc1: str,
    voc2: str,
    pair_id: str,
    responder: str,
    args: argparse.Namespace,
    used_scenarios: list[str],
    used_meanings: list[str],
) -> dict:
    turns = args.context_turns
    speakers = args.speakers

    def build(extra: str = "") -> str:
        base = user_prompt(
            voc1, voc2, pair_id, responder, turns, speakers, used_scenarios, used_meanings
        )
        return base + extra

    prompt = build()
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    served_by = args.model

    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload, usage, served_by = call_model(
            client, prompt, args.model, args.effort, turns, speakers
        )
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, voc1, voc2, pair_id, turns, speakers)
        verdict: dict | None = None
        if not problems and not args.no_judge:
            verdict, judge_usage = judge_pair(client, payload, args.model, args.effort)
            totals["input_tokens"] += judge_usage["input_tokens"]
            totals["output_tokens"] += judge_usage["output_tokens"]
            problems = judge_problems(verdict)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            payload["contrast"] = f"{voc1}-{voc2}"
            payload["context_turns"] = turns
            payload["total_turns"] = turns + 2
            payload["speakers"] = speakers
            if verdict is not None:
                payload["judge"] = verdict
            return payload
        last_problems = problems
        prompt = build(
            "\n\nThe previous attempt failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nRebuild the item from scratch if the trigger or the scene is the problem."
            "\nReturn a corrected JSON object."
        )
        print(
            f"    rejected ({problems[0][:70]}); attempt {attempt}/{MAX_ATTEMPTS}",
            flush=True,
        )

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str, context_turns: int, speakers: int) -> str:
    total = context_turns + 2
    cast = "A and B" if speakers == 2 else "A, B and C"
    lines = [
        "# Predicting response",
        "",
        f"writer: {model} · {len(records)} pair(s) · {total} turns per version · cast {cast}",
        "",
        f"Turns 1–{context_turns} are identical across both versions, and turn {context_turns} "
        f"is the trigger. Turn {context_turns + 1} is B's first contribution, a vocalization "
        f"only. Turn {total} is the reply the vocalization should select.",
        "",
    ]
    for record in records:
        lines += [
            f"### Pair {record['pair_id']}",
            "",
            f"Contrast: {record.get('contrast', '')} · Scenario: {record.get('scenario', '')}",
            f"Trigger: {record.get('trigger_note', '')}",
            "",
            "**Shared context**",
            "",
        ]
        for index, turn in enumerate(record["shared_context"], start=1):
            marker = "  ← trigger" if index == context_turns else ""
            lines.append(f"{index}. {turn['speaker']}: {turn['text']}{marker}")
        for label, version in (("Version 1", record["version_1"]), ("Version 2", record["version_2"])):
            lines += [
                "",
                f"**{label}** — {version['vocalization']} as {version['intended_interpretation']}",
                "",
                f"{context_turns + 1}. B: {version['vocalization']}",
                f"{total}. {version['responder']}: {version['response']}",
            ]
        lines += [
            "",
            "**Why the vocalization changes the response:**",
            record["why_the_vocalization_changes_the_response"],
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort",
        default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument(
        "--speakers",
        type=int,
        default=SPEAKERS,
        choices=[2, 3],
        help="2 = A tells it and B reacts (default); 3 = A and C converse",
    )
    parser.add_argument(
        "--context-turns",
        type=int,
        default=CONTEXT_TURNS,
        help="spoken turns before B's vocalization (default: 4 → 6 turns per version)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="pairs per vocalization contrast (default: 1 → 15 pairs)",
    )
    parser.add_argument(
        "--contrast",
        action="append",
        default=[],
        help="restrict to ids like laughter-sigh",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="skip the model audit (schema checks only)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.context_turns < 2:
        parser.error("--context-turns must be at least 2")
    if args.speakers == 3 and args.context_turns < 2:
        parser.error("--speakers 3 needs at least 2 context turns")
    return args


def main() -> None:
    args = parse_args()
    turns = args.context_turns
    jobs = []
    for voc1, voc2 in contrast_list():
        contrast_id = f"{voc1}-{voc2}"
        if args.contrast:
            needles = [item.lower() for item in args.contrast]
            if not any(n in contrast_id for n in needles):
                continue
        for sample in range(1, args.n + 1):
            jobs.append((voc1, voc2, sample))
    if not jobs:
        raise SystemExit("no contrasts matched")

    cast = "A+B" if args.speakers == 2 else "A+B+C"
    print(
        f"{len(jobs)} pair(s)  "
        f"({len({(a, b) for a, b, _ in jobs})} contrast type(s) × {args.n}) · "
        f"{turns + 2} turns per version · cast {cast}",
        flush=True,
    )

    if args.dry_run:
        for index, (voc1, voc2, sample) in enumerate(jobs):
            pair_id = f"{voc1}_{voc2}_{sample:03d}"
            responder = "A" if args.speakers == 2 else ("A" if index % 2 == 0 else "C")
            print("\n" + "=" * 72)
            print(f"{pair_id} · {formula_of(voc1)} vs {formula_of(voc2)} · responder {responder}")
            print("=" * 72)
            print(user_prompt(voc1, voc2, pair_id, responder, turns, args.speakers, [], []))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(
        f"model: {args.model}"
        + ("  (audit off)" if args.no_judge else "  (+ contrast audit)"),
        flush=True,
    )
    records: list[dict] = []
    used_scenarios: list[str] = []
    meanings_by_contrast: dict[str, list[str]] = {}

    for index, (voc1, voc2, sample) in enumerate(jobs, start=1):
        pair_id = f"{voc1}_{voc2}_{sample:03d}"
        contrast_id = f"{voc1}-{voc2}"
        responder = "A" if args.speakers == 2 else ("A" if index % 2 == 1 else "C")
        print(f"[{index}/{len(jobs)}] {pair_id} · {responder} replies", flush=True)
        try:
            record = generate_one(
                client,
                voc1,
                voc2,
                pair_id,
                responder,
                args,
                used_scenarios,
                meanings_by_contrast.get(contrast_id, []),
            )
            records.append(record)
            used_scenarios.append(record.get("scenario", ""))
            meanings_by_contrast.setdefault(contrast_id, []).append(
                f"{record['version_1']['intended_interpretation']} vs "
                f"{record['version_2']['intended_interpretation']}"
            )
            print(f"    scenario: {record.get('scenario', '')}", flush=True)
            print(f"    trigger:  {record.get('trigger_note', '')}", flush=True)
            print(
                f"    v1 {record['version_1']['vocalization']} "
                f"({record['version_1']['intended_interpretation']}) → "
                f"{record['version_1']['response']}",
                flush=True,
            )
            print(
                f"    v2 {record['version_2']['vocalization']} "
                f"({record['version_2']['intended_interpretation']}) → "
                f"{record['version_2']['response']}",
                flush=True,
            )
        except Exception as exc:
            records.append(
                {
                    "pair_id": pair_id,
                    "contrast": contrast_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"    failed: {exc}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vocalizations": VOC_ORDER,
        "speakers": args.speakers,
        "context_turns": turns,
        "total_turns": turns + 2,
        "n_per_contrast": args.n,
        "judged": not args.no_judge,
        "constraint": (
            f"turns 1-{turns} identical across versions with turn {turns} as the trigger; "
            f"turn {turns + 1} is B's voc-only first contribution; "
            f"turn {turns + 2} is the selected reply"
        ),
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "shared_context" in record]
    md_path.write_text(
        render_markdown(ok, args.model, turns, args.speakers), encoding="utf-8"
    )
    failures = sum(1 for record in records if record.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

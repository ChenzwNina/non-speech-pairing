"""Build 8-turn vocalization items backward: plan the ground truth, then realize it.

The causal direction is fixed and enforced by the pipeline itself:

    intended pragmatic meaning -> required contextual evidence
        -> generated conversation -> vocalization appears naturally

never "generate a conversation, insert a sound, invent an explanation afterward."

Stage 1 writes a latent plan only: a domain plus two vocalization events, each with a
target turn, a speaker, a vocalization type, the intended pragmatic interpretation, and
an evidence plan saying what the later transcript must establish. No dialogue is written
at this stage, and no exact evidence sentences or evidence-turn numbers are assigned.

Stage 2 receives that plan and writes exactly eight turns that realize it, then reports
which turns actually carry the supporting evidence.

Stage 3 is an independent verifier. If the transcript fails to realize the plan, the
transcript is rebuilt against the SAME plan — the ground truth is never edited to match
whatever the writer happened to produce. Only when a plan proves unrealizable after
repeated attempts is a new plan drawn, which discards the item rather than mutating it.

The plan is also the evaluation rubric: each accepted item carries a `rubric` block whose
four entries are exactly the four questions the benchmark will ask (which turn, which
sound, what it means here, which earlier turns are the evidence).

Usage:
    python hard_task/generate.py
    python hard_task/generate.py --n 1 --verbose
    python hard_task/generate.py --pair laughter-sigh
    python hard_task/generate.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "items.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 6000

MAX_PLAN_ATTEMPTS = 3
MAX_TRANSCRIPT_ATTEMPTS = 3

N_TURNS = 8
TARGET_TURN_MIN = 2
TARGET_TURN_MAX = 8
MIN_TURN_GAP = 2
MAX_INTERPRETATION_WORDS = 45
MAX_TURN_WORDS = 42
MIN_TURN_WORDS = 3

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]

DOMAINS = [
    "workplace interactions",
    "school and student life",
    "friendship",
    "family life",
    "travel",
    "household problems",
    "technology and devices",
    "planning an event",
    "shopping and money",
    "hobbies and side projects",
    "neighbours and shared spaces",
    "health and appointments",
    "moving house",
    "pets and animals",
    "food and cooking",
]

# Every legal (earlier, later) target-turn pair: both in range, at least MIN_TURN_GAP
# apart. Assigned per item rather than chosen by the planner, which otherwise converges
# on turns 4 and 7 almost every time and makes the positions guessable without listening.
TURN_PAIRS = [
    (early, late)
    for early in range(TARGET_TURN_MIN, TARGET_TURN_MAX + 1)
    for late in range(early + MIN_TURN_GAP, TARGET_TURN_MAX + 1)
]

# distinct conversational reactions, offered so the two events in one item land on
# meaningfully different pragmatic meanings rather than two shades of the same one
PRAGMATIC_MENU = [
    "playful teasing", "resignation", "alarm", "relief", "reluctant agreement",
    "disappointment", "concern", "boredom", "admiration", "skepticism",
    "vindication", "grief", "being deeply moved", "impatience", "dismissal",
    "awkward deflection", "disbelief", "quiet dread", "affectionate exasperation",
]


def supports_reasoning_effort(model: str) -> bool:
    """gpt-4o and other non-reasoning chat models reject the `reasoning` param outright."""
    return not re.match(r"^gpt-(4|3\.5)", model)


def parity_speaker(turn: int) -> str:
    """Turn 1 is Speaker A and the conversation strictly alternates from there."""
    return "A" if turn % 2 == 1 else "B"


# ---------------------------------------------------------------- stage 1: the plan

EVENT_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "target_turn": {"type": "integer"},
        "speaker": {"type": "string", "enum": ["A", "B"]},
        "vocalization": {"type": "string", "enum": VOC_ORDER},
        "interpretation": {"type": "string"},
        "evidence_plan": {"type": "string"},
    },
    "required": ["target_turn", "speaker", "vocalization", "interpretation", "evidence_plan"],
    "additionalProperties": False,
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "event_1": EVENT_PLAN_SCHEMA,
        "event_2": EVENT_PLAN_SCHEMA,
    },
    "required": ["domain", "event_1", "event_2"],
    "additionalProperties": False,
}

STAGE1_SYSTEM = f"""
You are planning the latent ground truth for one item in a benchmark that tests whether
an audio-language model can use a multi-turn conversation to work out WHY a speaker
produced a non-speech vocalization and WHAT that vocalization communicates in that
specific context.

The six target vocalizations are: gasp, grunt, laughter, sigh, sob, yawn.

Recognising that a sound is laughter or a sigh is only the first step. The benchmark's
real question is what the sound means given everything said before it. Your plan fixes
that meaning in advance.

DO NOT WRITE ANY DIALOGUE AT THIS STAGE. No turns, no lines, no quoted sentences.

Produce:

1. A conversational domain or situation — a natural everyday setting.

2. Exactly two target vocalization events. For each event, decide:
   - target_turn: which turn carries the vocalization. The two turns are GIVEN to you in
     the request — use exactly those. They lie between {TARGET_TURN_MIN} and
     {TARGET_TURN_MAX}, because context has to accumulate first.
   - speaker: who produces it. The conversation strictly alternates with Speaker A on
     turn 1, so odd turns are A and even turns are B. The assigned target turn therefore
     determines the speaker — work out which one it is and report it.
   - vocalization: one of the six.
   - interpretation: what the vocalization communicates in this specific situation.
   - evidence_plan: what contextual information the later transcript must contain in
     order to support that interpretation.

The two events use different vocalizations so the benchmark covers diverse acoustic and
pragmatic phenomena. Design the situation so that both assigned turns are natural moments
for a reaction — an earlier target turn has less context behind it, so give it something
worth reacting to straight away.

INTERPRETATION QUALITY

An interpretation must describe what the vocalization communicates here. It must not
merely name an emotion.

  Avoid:  "B is frustrated."
  Prefer: "B reacts with resignation because A has repeated the same mistake despite
           being warned earlier."

  Avoid:  "B is amused."
  Prefer: "B finds A's failed attempt ridiculous and is playfully teasing A for making
           the problem worse."

Name the speaker (A or B) in the interpretation, and ground it in what happened in this
situation. Do not use the words gasp, grunt, laugh, laughter, sigh, sob, cry, or yawn
inside the interpretation — interpret the reaction, do not label the sound.

The substance of an interpretation is its causal and relational content: what the speaker
is reacting to, what they are doing to the other person, and why this situation makes
that reaction meaningful. The emotion word carrying it is the least important part.

Critically, the interpretation must be inferable from context that can appear BEFORE the
target turn. Do not build it around a consequence that could only become visible later —
"B accepts that they will now have to redo the work" cannot be supported in advance,
because B's acceptance has not happened yet when B produces the sound. Anchor the
interpretation in what is already established at that moment: what was promised, warned,
claimed, revealed, or repeated earlier.

THE TWO EVENTS MUST BE PRAGMATICALLY DIFFERENT

One might be playful teasing while the other is resignation, alarm, relief, reluctant
agreement, disappointment, concern, boredom, admiration, or another distinct
conversational reaction. Two events expressing essentially the same pragmatic meaning
make a weak item.

AVOID TRIVIAL CAUSE AND EFFECT

Do not plan something the text alone already answers. "A says B has not slept for two
days, then B yawns" tests almost nothing beyond a stereotypical association. The
preceding context should make the vocalization meaningful without announcing it. Aim for
a plan where several reactions would be plausible from the words alone, and hearing this
particular vocalization is what makes the intended reading clearly preferable.

EVIDENCE PLAN

The evidence plan says what the transcript must establish before the vocalization
occurs. Describe the required information only.

  Target vocalization: laughter
  Intended interpretation: B is playfully teasing A because A confidently attempted to
    fix a simple problem and made it substantially worse.
  Evidence plan: Earlier turns should establish that A confidently claims they can fix
    the problem without help, and later reveal that the attempted fix caused an
    additional problem.

Do not write the exact evidence sentences. Do not assign evidence-turn numbers — you are
specifying what the transcript must contain, not where it goes.

Prefer plans whose evidence naturally spreads across more than one earlier turn, so that
reading the single turn before the vocalization is not enough.

OUTPUT

Return exactly one JSON object matching the schema: `domain`, `event_1`, `event_2`.
Nothing else. No transcript.
""".strip()


def stage1_prompt(
    voc_a: str,
    voc_b: str,
    item_id: str,
    domain: str,
    turn_pair: tuple[int, int],
    used_domains: list[str],
    used_interpretations: list[str],
) -> str:
    early, late = turn_pair
    lines = [
        "Plan the latent ground truth for exactly one benchmark item.",
        "",
        f"Item ID: {item_id}",
        f"Domain to use: {domain}",
        "",
        f"event_1 must sit on turn {early}, spoken by {parity_speaker(early)}.",
        f"event_2 must sit on turn {late}, spoken by {parity_speaker(late)}.",
        "",
        "Use these two vocalizations, one per event:",
        f"  - {voc_a}",
        f"  - {voc_b}",
        "You decide which of the two lands on which of the assigned turns, and what each",
        "one means in the situation you invent.",
        "",
        "The two interpretations must be meaningfully different conversational reactions.",
        f"Distinct reactions to draw from: {', '.join(PRAGMATIC_MENU[:10])}, etc.",
    ]
    if used_domains:
        lines += ["", "Situations already used — invent a clearly different scenario:"]
        lines += [f"- {text}" for text in used_domains[-12:]]
    if used_interpretations:
        lines += ["", "Pragmatic readings already used recently — prefer different ones:"]
        lines += [f"- {text}" for text in used_interpretations[-10:]]
    lines += ["", "Return the plan only. Do not write any dialogue."]
    return "\n".join(lines)


# ------------------------------------------------------- stage 2: the transcript

TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "turns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn": {"type": "integer"},
                    "speaker": {"type": "string", "enum": ["A", "B"]},
                    "text": {"type": "string"},
                },
                "required": ["turn", "speaker", "text"],
                "additionalProperties": False,
            },
        },
        "event_1": {
            "type": "object",
            "properties": {
                "evidence_turns": {"type": "array", "items": {"type": "integer"}},
                "evidence_summary": {"type": "string"},
            },
            "required": ["evidence_turns", "evidence_summary"],
            "additionalProperties": False,
        },
        "event_2": {
            "type": "object",
            "properties": {
                "evidence_turns": {"type": "array", "items": {"type": "integer"}},
                "evidence_summary": {"type": "string"},
            },
            "required": ["evidence_turns", "evidence_summary"],
            "additionalProperties": False,
        },
    },
    "required": ["turns", "event_1", "event_2"],
    "additionalProperties": False,
}

STAGE2_SYSTEM = f"""
You are realizing a pre-fixed ground-truth plan as a conversation, for a benchmark on
non-speech vocalizations in multi-turn dialogue.

You will be given a latent plan: a domain, and two vocalization events, each with a
target turn, a speaker, a vocalization type, an intended pragmatic interpretation, and an
evidence plan.

YOUR JOB IS TO SERVE THAT PLAN, NOT TO REPLACE IT.

Preserve the specified target turns, speakers, vocalization types, and intended
interpretations exactly. Do not shift a vocalization to a different turn, swap the sound,
or drift to a different meaning because some other conversation would be easier to write.

Write exactly {N_TURNS} turns between Speaker A and Speaker B. Turn 1 is Speaker A and
the speakers strictly alternate, so odd turns are A and even turns are B.

The conversation must be natural, coherent, and self-contained. It should read like an
ordinary exchange between two people, not like an example written for an annotation task.
No narration, no stage directions, no scene-setting — only what the two people say.

EVIDENCE

The information that supports each interpretation must appear BEFORE that vocalization
occurs. It may be spread across several earlier turns and does not have to sit
immediately before the target turn. A vocalization on turn 7 may rest on something
introduced on turn 2 and reinforced on turn 6 — this is desirable, because the benchmark
should sometimes require multi-turn reasoning rather than a local reaction to the
previous sentence alone.

THE TARGET TURNS

At each target turn, the speaker produces the vocalization and nothing else. The entire
text of that turn is the tag alone, for example:

    turn 3, B: [laughter]
    turn 7, A: [sigh]

No words in that turn, before or after the tag.

DO NOT EXPLAIN THE VOCALIZATION IN THE DIALOGUE

Avoid anything like:

    A: You seem really disappointed.
    B: [sigh]

That hands over the interpretation. The surrounding dialogue must supply the
circumstances from which the meaning can be inferred, never the label. Do not use the
words gasp, grunt, laugh, laughter, sigh, sob, cry, or yawn anywhere in the spoken turns,
and do not have anyone name or comment on the sound itself.

THE VOCALIZATION MUST CARRY INFORMATION

From the words alone, more than one reaction should be plausible at that point. Once the
actual vocalization is heard, the intended interpretation should become clearly
preferable. If A admits a mistake, laughter would point to playful teasing while a sigh
would point to frustrated resignation — write the context so that it is rich enough to
decide between such readings, but does not settle the question on its own.

AFTER WRITING THE TURNS

For each event, report the earlier turns that actually support the intended
interpretation, as `evidence_turns`, plus a short `evidence_summary`.

    "evidence_turns": [1, 2]
    "evidence_summary": "A first claims the repair will be easy and then admits the
      attempted repair caused an additional failure."

The summary must describe what is genuinely present in those turns of the transcript you
just wrote. It must not introduce facts those turns do not state. Cite only spoken turns
as evidence — never a target turn, which contains no words. Every cited turn must come
before its target turn.

Above all: do not invent a new interpretation after writing the dialogue. The transcript
must realize the interpretation you were given.

OUTPUT

Return exactly one JSON object matching the schema: `turns` (all {N_TURNS}, each with
`turn`, `speaker`, `text`), and `event_1` / `event_2`, each with `evidence_turns` and
`evidence_summary`.
""".strip()


def stage2_prompt(plan: dict) -> str:
    lines = [
        "Realize this plan as an eight-turn conversation.",
        "",
        f"Domain: {plan['domain']}",
        "",
    ]
    for key in ("event_1", "event_2"):
        event = plan[key]
        lines += [
            f"{key}:",
            f"  target_turn: {event['target_turn']}  (speaker {event['speaker']})",
            f"  vocalization: [{event['vocalization']}]",
            f"  intended interpretation: {event['interpretation']}",
            f"  evidence plan: {event['evidence_plan']}",
            "",
        ]
    lines += [
        "Both target turns contain only the vocalization tag. Every other turn is spoken",
        "words with no tags. The evidence for each interpretation must already be on the",
        "page before its target turn.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------- stage 3: the verifier

VERIFY_PROPERTIES = [
    (
        "vocalization_natural_at_that_point",
        "the specified vocalization is not a natural thing for that speaker to produce at "
        "that point in the conversation",
    ),
    (
        "evidence_supports_interpretation",
        "the cited evidence turns do not genuinely support the intended interpretation, or "
        "the evidence summary claims something those turns do not state",
    ),
    (
        "interpretation_requires_context",
        "the interpretation follows from the sound category alone, without needing the "
        "conversation, or the dialogue announces the reaction outright",
    ),
    (
        "intended_interpretation_clearly_best",
        "a competing interpretation of the same vocalization at that point is about as well "
        "supported as the intended one",
    ),
]

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        **{
            key: {
                "type": "object",
                "properties": {
                    "event_1": {"type": "boolean"},
                    "event_2": {"type": "boolean"},
                },
                "required": ["event_1", "event_2"],
                "additionalProperties": False,
            }
            for key, _ in VERIFY_PROPERTIES
        },
        "overall": {"type": "string", "enum": ["PASS", "FAIL"]},
        "reason": {"type": "string"},
    },
    "required": [key for key, _ in VERIFY_PROPERTIES] + ["overall", "reason"],
    "additionalProperties": False,
}

VERIFY_SYSTEM = """
You are a strict, independent verifier for a benchmark on non-speech vocalizations in
multi-turn conversation.

You receive an eight-turn transcript in which exactly two turns contain a vocalization
tag, together with the ground truth for each of those two events: the target turn, the
speaker, the vocalization type, the intended pragmatic interpretation, the cited evidence
turns, and an evidence summary.

The ground truth was fixed BEFORE the transcript was written. Your job is to judge
whether the transcript actually realizes it. You do not rewrite anything, you do not
propose a better interpretation, and you do not repair the item. You only verify.

Judge each of the four criteria separately for event_1 and for event_2.

1. vocalization_natural_at_that_point
   Is this vocalization a natural thing for that speaker to produce at that moment, given
   everything said before it? PASS if a real person could plausibly react that way there.
   FAIL if the sound is out of place, or would require a mental state the conversation
   never sets up.

2. evidence_supports_interpretation
   Do the cited evidence turns genuinely support the intended interpretation? Read those
   turns. PASS only if they actually establish what the interpretation depends on, and the
   evidence summary describes what those turns really say. FAIL if the summary adds facts
   the turns do not state, if the real support lives in turns that were not cited, or if
   the evidence is too thin to license the interpretation.

   Judge the contextual core of the interpretation — what the speaker is reacting to and
   why. An interpretation may also gesture at what the speaker is resigned to doing or
   about to do next; that forward-looking part cannot be evidenced in advance and its
   absence from the earlier turns is not a failure. Ask whether the cited turns establish
   the situation the reaction is a reaction to.

3. interpretation_requires_context
   Does the interpretation depend on this conversation, rather than on the sound category
   alone? A reading that amounts to a generic gloss of the sound — laughter means amused,
   a sigh means tired — is a FAIL. So is a transcript that announces the reaction in
   words, for example one speaker saying the other seems disappointed just before a sigh.
   PASS only if the specific conversation is doing the work.

4. intended_interpretation_clearly_best
   Among reasonable alternative readings of that same vocalization at that same point, is
   the intended interpretation clearly the best supported?

   Be precise about what counts as a competing interpretation. A competitor is a reading
   that would change what the listener understands the speaker to be DOING: teasing versus
   reproaching, relief versus alarm, boredom versus concern, sympathy versus dismissal,
   or a reading that points at a different cause or a different target.

   A rewording of the same conversational move in a different affect register is NOT a
   competitor. "Resignation" versus "frustration" versus "exasperation" over the same
   situation, aimed at the same person, for the same reason, are paraphrases of one
   interpretation. Do not fail an event because a near-synonymous emotion label could also
   be applied — the emotion word is the least important part of the interpretation, and
   the benchmark grades the causal and relational content around it.

   PASS if the intended reading is clearly preferable to the genuinely competing moves.
   FAIL only if a reading with different pragmatic content is about as well supported,
   which would make the item ambiguous.

Also weigh, in your reason, whether the words alone would already give the interpretation
away. The vocalization is supposed to contribute information: from the text alone several
reactions should have been possible.

OVERALL

Return PASS only if all four criteria pass for both events. Otherwise return FAIL.

Be strict. An item that only just holds together should fail — the transcript will be
rejected rather than the ground truth being adjusted afterward.

Output format: for each of `vocalization_natural_at_that_point`,
`evidence_supports_interpretation`, `interpretation_requires_context`, and
`intended_interpretation_clearly_best`, return an object with a boolean for `event_1` and
a boolean for `event_2`. Return `overall` as exactly "PASS" or "FAIL", and `reason` as one
concise sentence naming the single most important reason for the decision — if the item
fails, say which criterion and which event failed and why.
""".strip()


def verify_payload(plan: dict, draft: dict) -> str:
    events = {}
    for key in ("event_1", "event_2"):
        events[key] = {
            "target_turn": plan[key]["target_turn"],
            "speaker": plan[key]["speaker"],
            "vocalization": plan[key]["vocalization"],
            "intended_interpretation": plan[key]["interpretation"],
            "evidence_turns": draft[key]["evidence_turns"],
            "evidence_summary": draft[key]["evidence_summary"],
        }
    return json.dumps(
        {
            "domain": plan["domain"],
            "transcript": [
                {"turn": t["turn"], "speaker": t["speaker"], "text": t["text"]}
                for t in draft["turns"]
            ],
            **events,
        },
        ensure_ascii=False,
        indent=2,
    )


def verdict_problems(verdict: dict) -> list[str]:
    problems: list[str] = []
    for key, message in VERIFY_PROPERTIES:
        result = verdict.get(key) or {}
        failed = [name for name in ("event_1", "event_2") if not result.get(name)]
        if failed:
            problems.append(f"{', '.join(failed)}: {message}")
    if not problems and verdict.get("overall") == "FAIL":
        # every boolean was true yet the verifier still failed it — an inconsistent
        # verdict, so surface the stated reason instead of silently accepting
        problems.append(verdict.get("reason") or "verifier returned overall FAIL")
    return problems


# ------------------------------------------------------------ mechanical validation

TAG_RE = re.compile(r"\[[^\[\]]*\]")

VOC_WORD_RE = re.compile(
    r"(?i)\b("
    r"gasp(?:s|ed|ing)?|"
    r"grunt(?:s|ed|ing)?|"
    r"laugh(?:s|ed|ing|ter)?|"
    r"sigh(?:s|ed|ing)?|"
    r"sob(?:s|bed|bing)?|"
    r"yawn(?:s|ed|ing)?|"
    r"cr(?:y|ies|ied|ying)|"
    r"chuckle(?:s|d)?|whimper(?:s|ed|ing)?|groan(?:s|ed|ing)?"
    r")\b"
)

# a bare emotion label is not a pragmatic interpretation
BARE_INTERPRETATION_RE = re.compile(
    r"^[AB] (?:is|was|seems|sounds|feels) (?:so |quite |really |very )?"
    r"(?:amused|frustrated|sad|bored|tired|shocked|surprised|annoyed|relieved|"
    r"upset|happy|angry|disappointed|worried|confused|impressed)\.?$",
    re.I,
)

# the turn just before a target turn must not announce the reaction in words
ANNOUNCE_RE = re.compile(
    r"(?i)\byou (?:seem|sound|look|must be|are being|'re being|really are)\b|"
    r"\bwhy are you so\b|\bdon't be so\b"
)

# the evidence plan describes required information, not turn locations
TURN_REF_RE = re.compile(r"(?i)\bturns?\s*(?:\d|one|two|three|four|five|six|seven|eight)\b")


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def validate_plan(
    plan: dict, voc_a: str, voc_b: str, domain: str, turn_pair: tuple[int, int]
) -> list[str]:
    problems: list[str] = []

    if not normalize(plan.get("domain") or ""):
        problems.append("domain is empty")

    turns: list[int] = []
    vocs: list[str] = []
    interpretations: list[str] = []

    for key, assigned in zip(("event_1", "event_2"), turn_pair):
        event = plan.get(key) or {}
        turn = event.get("target_turn")
        if turn != assigned:
            problems.append(f"{key}.target_turn must be the assigned turn {assigned}")
        voc = event.get("vocalization")
        speaker = event.get("speaker")
        interpretation = normalize(event.get("interpretation") or "")
        evidence_plan = normalize(event.get("evidence_plan") or "")

        if not isinstance(turn, int) or not (TARGET_TURN_MIN <= turn <= TARGET_TURN_MAX):
            problems.append(
                f"{key}.target_turn must be an integer in {TARGET_TURN_MIN}..{TARGET_TURN_MAX}"
            )
        else:
            turns.append(turn)
            if speaker != parity_speaker(turn):
                problems.append(
                    f"{key}.speaker is {speaker} but turn {turn} belongs to "
                    f"{parity_speaker(turn)} (turn 1 is A, speakers alternate)"
                )

        if voc not in VOC_ORDER:
            problems.append(f"{key}.vocalization must be one of {VOC_ORDER}")
        else:
            vocs.append(voc)

        if not interpretation:
            problems.append(f"{key}.interpretation is empty")
        else:
            interpretations.append(interpretation.lower())
            if BARE_INTERPRETATION_RE.match(interpretation):
                problems.append(
                    f"{key}.interpretation is a bare emotion label, not a pragmatic reading "
                    "grounded in this situation"
                )
            if len(interpretation.split()) > MAX_INTERPRETATION_WORDS:
                problems.append(f"{key}.interpretation is too long")
            if VOC_WORD_RE.search(interpretation):
                problems.append(
                    f"{key}.interpretation names the sound instead of interpreting the reaction"
                )
            if speaker in {"A", "B"} and not re.search(rf"\b{speaker}\b", interpretation):
                problems.append(
                    f"{key}.interpretation should say what speaker {speaker} is communicating"
                )

        if len(evidence_plan.split()) < 8:
            problems.append(f"{key}.evidence_plan is too thin to constrain the transcript")
        if TURN_REF_RE.search(evidence_plan):
            problems.append(
                f"{key}.evidence_plan assigns turn numbers; describe the required "
                "information only"
            )
        if '"' in evidence_plan or "”" in evidence_plan:
            problems.append(f"{key}.evidence_plan writes exact dialogue; describe it instead")

    if len(turns) == 2 and turns[0] == turns[1]:
        problems.append("the two events must sit on different turns")

    if len(vocs) == 2:
        if vocs[0] == vocs[1]:
            problems.append("the two events must use different vocalizations")
        elif sorted(vocs) != sorted([voc_a, voc_b]):
            problems.append(f"the two vocalizations must be exactly {voc_a} and {voc_b}")

    if len(interpretations) == 2 and interpretations[0] == interpretations[1]:
        problems.append("the two interpretations are identical")

    return problems


def validate_transcript(plan: dict, draft: dict) -> list[str]:
    problems: list[str] = []
    turns = draft.get("turns") or []

    if len(turns) != N_TURNS:
        problems.append(f"expected exactly {N_TURNS} turns, got {len(turns)}")
        return problems

    target_turns = {plan[key]["target_turn"]: plan[key]["vocalization"] for key in ("event_1", "event_2")}
    by_turn: dict[int, dict] = {}

    for index, turn in enumerate(turns, start=1):
        number = turn.get("turn")
        speaker = turn.get("speaker")
        text = normalize(turn.get("text") or "")
        if number != index:
            problems.append(f"turn {index} is numbered {number}")
            continue
        by_turn[index] = {"speaker": speaker, "text": text}
        if speaker != parity_speaker(index):
            problems.append(
                f"turn {index} is spoken by {speaker}; turn 1 is A and speakers alternate"
            )
        if index in target_turns:
            expected = f"[{target_turns[index]}]"
            if text != expected:
                problems.append(
                    f"turn {index} must be exactly {expected} with no other words, got {text!r}"
                )
        else:
            if not text:
                problems.append(f"turn {index} is empty")
                continue
            if TAG_RE.search(text):
                problems.append(f"turn {index} contains a bracketed tag but is not a target turn")
            if VOC_WORD_RE.search(text):
                problems.append(
                    f"turn {index} names a vocalization in the spoken words; rewrite it so the "
                    "sound is never labelled"
                )
            words = len(text.split())
            if words < MIN_TURN_WORDS:
                problems.append(f"turn {index} is too short to carry any content")
            elif words > MAX_TURN_WORDS:
                problems.append(f"turn {index} is too long for natural speech")

    for target_turn in target_turns:
        before = by_turn.get(target_turn - 1)
        if before and ANNOUNCE_RE.search(before["text"]):
            problems.append(
                f"turn {target_turn - 1} announces the reaction just before the vocalization "
                f"on turn {target_turn}; let the situation imply it instead"
            )

    non_adjacent_seen = False
    for key in ("event_1", "event_2"):
        target_turn = plan[key]["target_turn"]
        event = draft.get(key) or {}
        evidence = event.get("evidence_turns") or []
        summary = normalize(event.get("evidence_summary") or "")

        if not evidence:
            problems.append(f"{key}.evidence_turns is empty")
        for cited in evidence:
            if not isinstance(cited, int) or not (1 <= cited <= N_TURNS):
                problems.append(f"{key}.evidence_turns has an out-of-range turn {cited}")
            elif cited >= target_turn:
                problems.append(
                    f"{key}.evidence_turns cites turn {cited}, which is not before the "
                    f"vocalization on turn {target_turn}"
                )
            elif cited in target_turns:
                problems.append(
                    f"{key}.evidence_turns cites turn {cited}, which contains only a "
                    "vocalization and no words"
                )
            elif cited <= target_turn - 2:
                non_adjacent_seen = True

        if len(summary.split()) < 8:
            problems.append(f"{key}.evidence_summary is too thin")
        if VOC_WORD_RE.search(summary):
            problems.append(f"{key}.evidence_summary names the sound instead of the evidence")

    if not non_adjacent_seen:
        problems.append(
            "both events rest only on the turn immediately before them; at least one should "
            "depend on evidence introduced earlier than that"
        )

    return problems


# ------------------------------------------------------------------- model plumbing


def call_json(
    client: OpenAI,
    system: str,
    prompt: str,
    schema: dict,
    schema_name: str,
    model: str,
    effort: str,
) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model,
                instructions=system,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            if supports_reasoning_effort(model):
                kwargs["reasoning"] = {"effort": effort}
            response = client.responses.create(**kwargs)
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
            print(f"      retry in {wait}s: {exc}", flush=True)
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


class GenerationFailed(RuntimeError):
    """Raised when no plan could be realized; carries the last attempt for inspection."""

    def __init__(self, message: str, plan: dict | None, draft: dict | None,
                 problems: list[str], verdict: dict | None):
        super().__init__(message)
        self.plan = plan
        self.draft = draft
        self.problems = problems
        self.verdict = verdict


def print_plan(plan: dict) -> None:
    print(f"      domain: {plan.get('domain')}", flush=True)
    for key in ("event_1", "event_2"):
        event = plan.get(key) or {}
        print(
            f"      {key}: turn {event.get('target_turn')} {event.get('speaker')} "
            f"[{event.get('vocalization')}]",
            flush=True,
        )
        print(f"        means: {event.get('interpretation')}", flush=True)
        print(f"        evidence plan: {event.get('evidence_plan')}", flush=True)


def print_transcript(draft: dict) -> None:
    for turn in draft.get("turns") or []:
        print(f"      {turn.get('turn')}. {turn.get('speaker')}: {turn.get('text')}", flush=True)
    for key in ("event_1", "event_2"):
        event = draft.get(key) or {}
        print(
            f"      {key} evidence {event.get('evidence_turns')}: {event.get('evidence_summary')}",
            flush=True,
        )


def build_rubric(plan: dict, draft: dict) -> dict:
    """The fixed ground truth, laid out as the four questions the benchmark will ask.

    This is deliberately the same object the plan fixed up front — the rubric used to
    grade a model later is the ground truth that generated the item, not a post-hoc
    reading of the transcript.
    """
    rubric = {}
    for key in ("event_1", "event_2"):
        rubric[key] = {
            "q_which_turn": plan[key]["target_turn"],
            "q_which_vocalization": plan[key]["vocalization"],
            "q_what_it_means": plan[key]["interpretation"],
            "q_which_evidence": {
                "turns": draft[key]["evidence_turns"],
                "summary": draft[key]["evidence_summary"],
            },
            "speaker": plan[key]["speaker"],
        }
    return rubric


def generate_one(
    client: OpenAI,
    voc_a: str,
    voc_b: str,
    item_id: str,
    domain: str,
    turn_pair: tuple[int, int],
    args: argparse.Namespace,
    used_domains: list[str],
    used_interpretations: list[str],
) -> dict:
    verbose = getattr(args, "verbose", False)
    totals = {"input_tokens": 0, "output_tokens": 0}
    served_by = args.model

    last_plan: dict | None = None
    last_draft: dict | None = None
    last_problems: list[str] = []
    last_verdict: dict | None = None

    plan_feedback = ""
    for plan_attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
        base_plan_prompt = stage1_prompt(
            voc_a, voc_b, item_id, domain, turn_pair, used_domains, used_interpretations
        )
        plan, usage, served_by = call_json(
            client,
            STAGE1_SYSTEM,
            base_plan_prompt + plan_feedback,
            PLAN_SCHEMA,
            "hard_task_plan",
            args.model,
            args.effort,
        )
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        last_plan = plan

        problems = validate_plan(plan, voc_a, voc_b, domain, turn_pair)
        if verbose:
            print(f"    -- plan attempt {plan_attempt}/{MAX_PLAN_ATTEMPTS} --", flush=True)
            print_plan(plan)
        if problems:
            last_problems = problems
            if verbose:
                print(f"      plan rejected: {problems}", flush=True)
            else:
                print(f"    plan rejected ({problems[0][:70]})", flush=True)
            plan_feedback = (
                "\n\nA previous plan failed these checks:\n- "
                + "\n- ".join(problems)
                + "\nReturn a corrected plan."
            )
            continue

        # the plan is now the fixed ground truth: the transcript is retried against it,
        # and the plan is never edited to match whatever the writer produced
        transcript_feedback = ""
        for transcript_attempt in range(1, MAX_TRANSCRIPT_ATTEMPTS + 1):
            draft, usage, served_by = call_json(
                client,
                STAGE2_SYSTEM,
                stage2_prompt(plan) + transcript_feedback,
                TRANSCRIPT_SCHEMA,
                "hard_task_transcript",
                args.model,
                args.effort,
            )
            totals["input_tokens"] += usage["input_tokens"]
            totals["output_tokens"] += usage["output_tokens"]
            last_draft = draft

            problems = validate_transcript(plan, draft)
            verdict: dict | None = None
            if not problems and not args.no_verify:
                verdict, verify_usage, _ = call_json(
                    client,
                    VERIFY_SYSTEM,
                    verify_payload(plan, draft),
                    VERIFY_SCHEMA,
                    "hard_task_verdict",
                    args.model,
                    args.effort,
                )
                totals["input_tokens"] += verify_usage["input_tokens"]
                totals["output_tokens"] += verify_usage["output_tokens"]
                problems = verdict_problems(verdict)
            last_verdict = verdict

            if verbose:
                print(
                    f"    -- transcript attempt {transcript_attempt}/{MAX_TRANSCRIPT_ATTEMPTS} --",
                    flush=True,
                )
                print_transcript(draft)

            if not problems:
                record = {
                    "item_id": item_id,
                    "contrast": f"{voc_a}-{voc_b}",
                    "domain": plan["domain"],
                    "assigned_domain": domain,
                    "assigned_turns": list(turn_pair),
                    "plan": plan,
                    "transcript": draft["turns"],
                    "events": [
                        {
                            "event": key,
                            "target_turn": plan[key]["target_turn"],
                            "speaker": plan[key]["speaker"],
                            "vocalization": plan[key]["vocalization"],
                            "interpretation": plan[key]["interpretation"],
                            "evidence_plan": plan[key]["evidence_plan"],
                            "evidence_turns": draft[key]["evidence_turns"],
                            "evidence_summary": draft[key]["evidence_summary"],
                        }
                        for key in ("event_1", "event_2")
                    ],
                    "rubric": build_rubric(plan, draft),
                    "attempts": {"plan": plan_attempt, "transcript": transcript_attempt},
                    "usage": totals,
                    "served_by": served_by,
                }
                if verdict is not None:
                    record["verdict"] = verdict
                if verbose:
                    print("      accepted", flush=True)
                return record

            last_problems = problems
            if verbose:
                print(f"      transcript rejected: {problems}", flush=True)
                if verdict is not None:
                    print(f"      verdict: {verdict}", flush=True)
            else:
                print(
                    f"    transcript rejected ({problems[0][:70]}); "
                    f"attempt {transcript_attempt}/{MAX_TRANSCRIPT_ATTEMPTS}",
                    flush=True,
                )
            transcript_feedback = (
                "\n\nA previous attempt at this same plan failed these checks:\n- "
                + "\n- ".join(problems)
                + "\nThe plan above is fixed ground truth and must not change. Rewrite the "
                "transcript so it realizes that plan."
            )

        # the plan survived validation but could not be realized in MAX_TRANSCRIPT_ATTEMPTS;
        # draw a fresh plan rather than bending this one to fit a transcript
        print(
            f"    plan {plan_attempt} could not be realized; replanning",
            flush=True,
        )
        plan_feedback = (
            "\n\nA previous plan passed its own checks but no transcript could realize it. "
            "The last failures were:\n- "
            + "\n- ".join(last_problems)
            + "\nPlan a different situation that is easier to realize naturally while still "
            "requiring multi-turn context."
        )

    raise GenerationFailed(
        "no plan could be realized: " + "; ".join(last_problems),
        plan=last_plan,
        draft=last_draft,
        problems=last_problems,
        verdict=last_verdict,
    )


# ---------------------------------------------------------------------- rendering


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Hard task — 8-turn conversations, two vocalization events each",
        "",
        f"writer/verifier: {model} · {len(records)} item(s)",
        "",
        "Each item was built backward: the ground truth below (target turn, sound, meaning,",
        "evidence) was fixed before any dialogue existed, and the transcript was written to",
        "realize it. The ground truth doubles as the evaluation rubric.",
        "",
    ]
    for record in records:
        lines += [
            f"### {record['item_id']}",
            "",
            f"Domain: {record['domain']}  ·  contrast: {record.get('contrast', '')}",
            "",
        ]
        target_turns = {event["target_turn"] for event in record["events"]}
        for turn in record["transcript"]:
            marker = "  ← target" if turn["turn"] in target_turns else ""
            lines.append(f"{turn['turn']}. **{turn['speaker']}:** {turn['text']}{marker}")
        lines.append("")
        for event in record["events"]:
            lines += [
                f"**{event['event']} — turn {event['target_turn']}, "
                f"{event['speaker']}, [{event['vocalization']}]**",
                "",
                f"- Meaning: {event['interpretation']}",
                f"- Evidence turns: {event['evidence_turns']}",
                f"- Evidence: {event['evidence_summary']}",
                f"- Planned before writing: {event['evidence_plan']}",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort", default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument(
        "--n", type=int, default=1,
        help="items per vocalization pair (default: 1 -> 15 items)",
    )
    parser.add_argument(
        "--pair", action="append", default=[],
        help="restrict to pairs like laughter-sigh",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--no-verify", action="store_true",
        help="skip stage 3 (mechanical checks only)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="keep items already accepted in --out and only generate the missing ones "
             "(the job list is seed-deterministic, so item ids line up)",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    jobs: list[tuple[str, str, int]] = []
    for voc_a, voc_b in combinations(VOC_ORDER, 2):
        pair_id = f"{voc_a}-{voc_b}"
        if args.pair:
            needles = [item.lower() for item in args.pair]
            if not any(needle in pair_id for needle in needles):
                continue
        for sample in range(1, args.n + 1):
            jobs.append((voc_a, voc_b, sample))
    if not jobs:
        raise SystemExit("no vocalization pairs matched")

    # shuffle each pair's order so neither sound is systematically the earlier event, and
    # spread domains and target-turn positions across items instead of letting the model
    # reach for one setting or park both vocalizations on the same two turns every time
    domains = DOMAINS[:]
    rng.shuffle(domains)
    turn_pairs = TURN_PAIRS[:]
    rng.shuffle(turn_pairs)
    prepared = []
    for index, (voc_a, voc_b, sample) in enumerate(jobs):
        pair = [voc_a, voc_b]
        rng.shuffle(pair)
        prepared.append(
            (
                pair[0],
                pair[1],
                sample,
                domains[index % len(domains)],
                turn_pairs[index % len(turn_pairs)],
            )
        )

    print(f"{len(prepared)} item(s) · 8 turns each · two vocalization events", flush=True)

    already: dict[str, dict] = {}
    if args.resume and args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
        for record in previous.get("results", []):
            if "transcript" in record:
                already[record["item_id"]] = record
        print(f"resuming: {len(already)} item(s) already accepted in {args.out}", flush=True)

    if args.dry_run:
        for voc_a, voc_b, sample, domain, turn_pair in prepared:
            item_id = f"{voc_a}_{voc_b}_{sample:03d}"
            print("\n" + "=" * 72)
            print(f"{item_id} · {domain} · turns {turn_pair}")
            print("=" * 72)
            print(stage1_prompt(voc_a, voc_b, item_id, domain, turn_pair, [], []))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)
    print(
        f"model: {args.model}" + ("  (verifier off)" if args.no_verify else "  (+ verifier)"),
        flush=True,
    )

    records: list[dict] = []
    used_domains: list[str] = []
    used_interpretations: list[str] = []

    for index, (voc_a, voc_b, sample, domain, turn_pair) in enumerate(prepared, start=1):
        item_id = f"{voc_a}_{voc_b}_{sample:03d}"
        if item_id in already:
            record = already[item_id]
            records.append(record)
            used_domains.append(record["domain"])
            for event in record["events"]:
                used_interpretations.append(event["interpretation"])
            print(f"[{index}/{len(prepared)}] {item_id}  (kept from previous run)", flush=True)
            continue
        print(
            f"[{index}/{len(prepared)}] {item_id}  ({domain}, turns {turn_pair[0]}/{turn_pair[1]})",
            flush=True,
        )
        try:
            record = generate_one(
                client, voc_a, voc_b, item_id, domain, turn_pair, args,
                used_domains, used_interpretations,
            )
            records.append(record)
            used_domains.append(record["domain"])
            for event in record["events"]:
                used_interpretations.append(event["interpretation"])
            for event in record["events"]:
                print(
                    f"    turn {event['target_turn']} {event['speaker']} "
                    f"[{event['vocalization']}] <- evidence {event['evidence_turns']}",
                    flush=True,
                )
                print(f"      {event['interpretation']}", flush=True)
        except GenerationFailed as exc:
            failed = {
                "item_id": item_id,
                "contrast": f"{voc_a}-{voc_b}",
                "assigned_domain": domain,
                "assigned_turns": list(turn_pair),
                "error": f"{type(exc).__name__}: {exc}",
                "last_problems": exc.problems,
            }
            if exc.plan is not None:
                failed["last_plan"] = exc.plan
            if exc.draft is not None:
                failed["last_draft"] = exc.draft
            if exc.verdict is not None:
                failed["last_verdict"] = exc.verdict
            records.append(failed)
            print(f"    failed: {exc}", flush=True)
        except Exception as exc:
            records.append(
                {
                    "item_id": item_id,
                    "contrast": f"{voc_a}-{voc_b}",
                    "assigned_domain": domain,
                    "assigned_turns": list(turn_pair),
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
        "turns_per_item": N_TURNS,
        "events_per_item": 2,
        "seed": args.seed,
        "verified": not args.no_verify,
        "pipeline": (
            "stage 1 plans the latent ground truth (no dialogue); stage 2 realizes it as 8 "
            "turns and reports the actual evidence turns; stage 3 verifies independently. A "
            "failing transcript is rebuilt against the same fixed plan — the ground truth is "
            "never edited to fit the transcript."
        ),
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "transcript" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

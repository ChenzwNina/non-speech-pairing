"""Generate contrastive 2-turn vocalization-benchmark pairs, then audit them.

Each pair is: Speaker A says one line, Speaker B replies with only a non-speech
vocalization. Two versions share the identical Turn 1; only B's vocalization differs.
Each version also carries a gold interpretation (Q2) and a gold verbal continuation B
could say next (Q3, text only — never synthesized). Q2 and Q3 are both a forced choice
between the two versions' own gold answers — no random distractors.

Generation is a writer call against SYSTEM_PROMPT (the full benchmark spec) followed by:
  1. mechanical validate() — shape, leakage, literal-naming, gold-pair distinctness
  2. an LLM judge_pair() — the swap test and pragmatic distinctness that make the
     forced choice between the two golds actually have a defensible answer

Usage:
    python predicting_response_upgraded/generate.py
    python predicting_response_upgraded/generate.py --contrast gasp-grunt --n 2
    python predicting_response_upgraded/generate.py --no-judge --verbose
    python predicting_response_upgraded/generate.py --dry-run
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
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "pairs.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 4000
MAX_ATTEMPTS = 4
MAX_RESPONSE_WORDS = 22
MAX_INTERPRETATION_WORDS = 40

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]

VOCALIZATIONS = {
    "gasp": {
        "formula": "[gasp]",
        "meanings": [
            "shock",
            "pleasant surprise",
            "fear",
            "admiration",
            "disbelief",
            "sudden realization",
            "concern",
        ],
    },
    "grunt": {
        "formula": "[grunt]",
        "meanings": [
            "reluctant agreement",
            "disagreement",
            "annoyance",
            "skepticism",
            "acknowledgment",
            "dissatisfaction",
            "dismissal",
            "impatience",
        ],
    },
    "laughter": {
        "formula": "[laughter]",
        "meanings": [
            "genuine amusement",
            "teasing",
            "mockery",
            "disbelief",
            "nervous amusement",
            "awkwardness",
            "shared humor",
            "irony",
        ],
    },
    "sigh": {
        "formula": "[sigh]",
        "meanings": [
            "frustration",
            "disappointment",
            "resignation",
            "relief",
            "impatience",
            "exhaustion",
            "reluctant acceptance",
        ],
    },
    "sob": {
        "formula": "[sob]",
        "meanings": [
            "sadness",
            "hurt",
            "emotional overwhelm",
            "relief",
            "being deeply moved",
            "grief",
        ],
    },
    "yawn": {
        "formula": "[yawn]",
        "meanings": [
            "boredom",
            "tiredness",
            "disengagement",
            "impatience",
            "exhaustion",
            "loss of attention",
        ],
    },
}

FUNCTION_MENU = [
    "tease", "criticize", "sympathize", "comfort", "reassure", "express disbelief",
    "celebrate", "congratulate", "warn", "question", "express concern",
    "express resignation", "reluctantly agree", "disagree", "challenge", "mock",
    "encourage", "ask for clarification", "express admiration", "express disappointment",
    "signal boredom", "request that A stop or shorten something", "acknowledge relief",
    "express shock",
]

# not part of the original spec; added so scenes can be scoped to a domain on request,
# same definitions as predicting_response/generate.py for consistency across folders
THEMES = {
    "domestic": (
        "home and household life: chores, repairs, bills, family logistics, roommates, "
        "meals, pets, shared spaces, errands, scheduling around the house"
    ),
    "family": (
        "family relationships and life beyond household chores: parents, children, "
        "siblings, and extended family; visits, celebrations, family traditions, "
        "caregiving, sibling dynamics, keeping in touch, family news and decisions"
    ),
    "school": (
        "school and student life: classes, homework, group projects, teachers, "
        "classmates, exams, clubs, school trips, campus logistics"
    ),
    "work": (
        "workplace life: coworkers, meetings, deadlines, managers, office logistics, "
        "projects, clients, workplace events"
    ),
}


def supports_reasoning_effort(model: str) -> bool:
    """gpt-4o and other non-reasoning chat models reject the `reasoning` param outright."""
    return not re.match(r"^gpt-(4|3\.5)", model)


def output_schema() -> dict:
    version_schema = {
        "type": "object",
        "properties": {
            "vocalization": {"type": "string"},
            "interpretation": {"type": "string"},
            "response": {"type": "string"},
        },
        "required": ["vocalization", "interpretation", "response"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "pair_id": {"type": "string"},
            "shared_turn1": {"type": "string"},
            "version_1": version_schema,
            "version_2": version_schema,
            "contrastive_rationale": {"type": "string"},
        },
        "required": [
            "pair_id",
            "shared_turn1",
            "version_1",
            "version_2",
            "contrastive_rationale",
        ],
        "additionalProperties": False,
    }


SYSTEM_PROMPT = r"""
You are generating data for a benchmark that tests whether an audio-language model can use a non-speech vocalization to understand a speaker's reaction and predict what they would say next.
Target vocalizations
Use only:

* `[gasp]`
* `[grunt]`
* `[laughter]`
* `[sigh]`
* `[sob]`
* `[yawn]`

Generate exactly ONE contrastive pair per call.
1. Benchmark format
Each test example contains only two audible turns:
Turn 1: Speaker A says one natural utterance.
Turn 2: Speaker B responds only with a non-speech vocalization.
Example:
A: I still have forty more slides if you want the full explanation.
B: [yawn]
The audio ends after B's vocalization. B says no lexical words in the audio.
The benchmark then asks:
Q1 — Vocalization recognition
Which vocalization did B produce?
Choices are always:

* gasp
* grunt
* laughter
* sigh
* sob
* yawn

Q2 — Interpretation
What does B's reaction most likely communicate in this context?
The two answer choices are the two gold interpretations generated for the contrastive pair.
Q3 — Verbal continuation
What would B most naturally say immediately after the vocalization?
The two answer choices are the two gold verbal continuations generated for the pair.
2. Generate a contrastive pair
Every pair must contain:

* one shared Turn 1 from Speaker A;
* two different vocalizations from Speaker B;
* one interpretation for each vocalization;
* one predicted verbal continuation for each vocalization.

The shared Turn 1 must be exactly identical in both versions.
Example structure:
Shared Turn 1
A: [same utterance]
Version 1
B: [VOCALIZATION 1]
Interpretation: [Interpretation 1]
B's continuation: [Response 1]
Version 2
B: [VOCALIZATION 2]
Interpretation: [Interpretation 2]
B's continuation: [Response 2]
The only difference in the test audio is B's vocalization.
3. Core validity requirement
A pair is valid only if:

1. Both vocalizations are plausible reactions to the same Turn 1.
2. The two vocalizations imply clearly different pragmatic interpretations.
3. The two verbal continuations perform clearly different conversational functions.
4. Swapping the interpretations or responses makes the pair clearly worse.

In other words:
`Turn 1 + Vocalization 1 → Interpretation 1 → Response 1`
and
`Turn 1 + Vocalization 2 → Interpretation 2 → Response 2`
must both sound natural.
But:
`Turn 1 + Vocalization 1 → Response 2`
and
`Turn 1 + Vocalization 2 → Response 1`
should sound clearly unnatural, pragmatically mismatched, or strongly dispreferred.
If both responses still work reasonably well after swapping, reject the pair and generate a new one.
This is the most important rule.
4. Turn 1 requirements
Speaker A's utterance should create a situation where multiple reactions are possible.
Turn 1 should:

* sound like natural conversation;
* contain enough context to interpret B's reaction;
* not state B's emotional state;
* not make one target vocalization obviously inevitable;
* allow both selected vocalizations to be plausible.

Useful situations include:

* admitting a mistake;
* revealing an unexpected result;
* making a questionable suggestion;
* sharing surprising news;
* describing an embarrassing situation;
* reporting a problem;
* showing someone something;
* making a decision;
* explaining something at length;
* revealing something personally meaningful.

Avoid contexts where the text alone already determines B's reaction.
Bad:
A: You've been awake for thirty hours and can barely keep your eyes open.
This practically gives away `[yawn]`.
Better:
A: I can go through the remaining forty slides if you want the full explanation.
Several reactions remain possible.
5. Interpretation requirements
For each vocalization, write one sentence describing what B is communicating in this specific context.
The interpretation should capture the pragmatic meaning, not simply label the sound or emotion.
Bad:
B is amused.
Better:
B finds A's mistake ridiculous and is playfully teasing them for making the situation worse.
Bad:
B is frustrated.
Better:
B sees the outcome as a predictable consequence of A's decision and responds with resigned disapproval.
Do not mention the vocalization name itself inside the interpretation.
The two interpretations must be meaningfully different, not paraphrases or slight emotional variations.
6. Verbal continuation requirements
For each version, generate one short sentence that B could naturally say immediately after the vocalization.
The continuation is not part of the audio. It is the gold answer for Q3.
Each continuation must:

* sound natural in spoken conversation;
* match its interpretation;
* be concise;
* not mention the vocalization itself;
* perform a different conversational function from the paired response.

Useful conversational functions include:

* teasing
* reproaching
* comforting
* celebrating
* expressing concern
* questioning
* objecting
* reluctantly agreeing
* challenging
* reassuring
* expressing disbelief
* expressing relief
* asking A to stop or shorten something
* expressing admiration
* expressing disappointment

Do not treat two differently worded sentences as contrastive if they perform essentially the same function.
7. Vocalization meanings are context-dependent
Do not assign each sound one fixed meaning.
Possible interpretations include:

* gasp: surprise, shock, concern, admiration, disbelief
* grunt: reluctant agreement, annoyance, skepticism, dismissal, acknowledgment
* laughter: amusement, teasing, mockery, disbelief, awkward humor, irony
* sigh: frustration, relief, resignation, disappointment, impatience
* sob: sadness, hurt, emotional overwhelm, relief, being deeply moved
* yawn: boredom, fatigue, disengagement, impatience, loss of attention

Use different meanings across items.
8. Strong example 1
Shared Turn 1
A: I moved the project deadline up to tomorrow morning.
Version 1
Vocalization: `[grunt]`
Interpretation:
B reluctantly accepts the new deadline despite clearly disliking the extra pressure it creates.
B's continuation:
Fine, I'll stay late and finish my part.
Version 2
Vocalization: `[gasp]`
Interpretation:
B is alarmed by how unexpectedly soon the deadline is and questions whether the team can realistically meet it.
B's continuation:
Tomorrow? We haven't even started testing yet.
Why this works
The same announcement can reasonably trigger reluctant acceptance or alarm.
The responses have different functions:

* Version 1: reluctant compliance
* Version 2: challenge / alarm

Swapping them substantially changes the intended interaction.
9. Strong example 2
Shared Turn 1
A: I still have another forty slides explaining the implementation details.
Version 1
Vocalization: `[yawn]`
Interpretation:
B is losing interest or attention and implicitly signals that the explanation has gone on long enough.
B's continuation:
Maybe just give me the short version.
Version 2
Vocalization: `[gasp]`
Interpretation:
B is startled by the unexpectedly large amount of material still remaining.
B's continuation:
Forty more? How long is this presentation?
Why this works
Both reactions are plausible, but they motivate different actions:

* Version 1: request to shorten the explanation
* Version 2: surprised questioning

The vocalization changes how B's reaction should be interpreted.
10. Strong example 3
Shared Turn 1
A: I told the whole office I could fix the printer myself, and now it won't even turn on.
Version 1
Vocalization: `[laughter]`
Interpretation:
B treats A's failed repair attempt as comically incompetent and responds with playful ridicule.
B's continuation:
Only you could turn a broken printer into an even more broken printer.
Version 2
Vocalization: `[sigh]`
Interpretation:
B sees the outcome as an avoidable mistake and responds with frustrated resignation.
B's continuation:
This is exactly why I told you not to touch it.
Why this works
The first response teases A, while the second reproaches A.
They are not merely two different ways of saying that A made a mistake.
11. Bad example: responses too similar
Shared Turn 1
A: I found one of the drawings we made in elementary school.
Version 1
`[gasp]`
Wow, I completely forgot how creative we were.
Version 2
`[laughter]`
We really were imaginative kids.
REJECT.
Both responses express essentially the same function:
positive nostalgic appreciation
Either sentence could easily follow either vocalization.
The wording is different, but the pragmatic response is not.
12. Bad example: Turn 1 determines the reaction
A: I know you're completely exhausted and struggling to stay awake.
Version 1:
`[yawn]`
I really need some sleep.
REJECT as a contrastive context.
The linguistic context already makes the reaction predictable, so the vocalization contributes little new information.
13. Final self-check
Before returning the pair, verify only these three things:
Plausibility
Both vocalizations are natural reactions to the shared Turn 1, and Turn 1 does not strongly favor one.
Interpretation contrast
The interpretations express clearly different pragmatic meanings and are correctly matched to their vocalizations.
If they can be swapped without making the pair clearly worse, regenerate.
Response contrast
The responses perform clearly different conversational functions and are correctly matched to their vocalizations.
If either swapped response remains about as natural as the intended one, regenerate.
14. Output contract
Return exactly one JSON object matching the provided schema.
Use:

* `shared_turn1`: Speaker A's utterance only, with no speaker label.
* `version_1.vocalization`: exact vocalization tag, e.g. `[laughter]`.
* `version_1.interpretation`: one-sentence gold interpretation.
* `version_1.response`: B's predicted verbal continuation.
* `version_2`: same fields for the second vocalization.
* `contrastive_rationale`: one or two sentences explaining the pragmatic contrast and why swapping the responses would make the pair worse.

Do not generate random distractors.
Q2 and Q3 are forced choices between the two versions' own gold answers.
Do not mention the vocalization word itself inside an interpretation or response.
Generate exactly ONE pair.
Most importantly:
Both vocalizations must be plausible after the same Turn 1, but they must lead to clearly different pragmatic interpretations and verbal continuations. If the two gold answers remain reasonably interchangeable, reject the pair and generate a new one.

One schema field beyond what section 14 lists: `pair_id` — copy it exactly from the "Pair ID" given in the user message.
""".strip()


def formula_of(voc_id: str) -> str:
    return VOCALIZATIONS[voc_id]["formula"]


def contrast_list() -> list[tuple[str, str]]:
    return list(combinations(VOC_ORDER, 2))


def normalize(text: str) -> str:
    return " ".join((text or "").split())


TAG_RE = re.compile(r"\[[^\[\]]+\]")

# literal vocalization words / close synonyms that must not leak into Turn 1, an
# interpretation, or a response — either would let the text alone solve the question
# the literal sound-name words — banned everywhere (Turn 1, interpretation, response),
# since naming the vocalization is never the same as interpreting it
VOC_WORD_RE = re.compile(
    r"(?i)\b("
    r"gasp(?:s|ed|ing)?|"
    r"grunt(?:s|ed|ing)?|"
    r"laugh(?:s|ed|ing|ter)?|"
    r"sigh(?:s|ed|ing)?|"
    r"sob(?:s|bed|bing)?|"
    r"yawn(?:s|ed|ing)?|"
    r"cr(?:y|ies|ied|ying)"
    r")\b"
)

# broader state-description giveaways ("exhausted", "burst into tears") are fine — even
# good — inside an interpretation, since describing the state IS the job there. They only
# leak information when they appear in shared_turn1, predicting B's reaction before it
# happens, so they are checked separately and only against that field.
TURN1_GIVEAWAY_RE = re.compile(
    r"(?i)\b("
    r"exhausted|"
    r"can(?:'|no)?t keep (?:her|his|their|your) eyes open|"
    r"burst(?:s|ing)? into tears"
    r")\b"
)

# a bare, context-free naming of the emotion/sound is not a real interpretation
BARE_INTERPRETATION_RE = re.compile(
    r"^b (?:is|was|seems|sounds) (?:so |quite |really |very )?"
    r"(?:laughing|amused|sighing|frustrated|crying|sad|yawning|bored|tired|gasping|"
    r"shocked|surprised|annoyed|grunting)\.?$",
    re.I,
)


def validate(payload: dict, voc1: str, voc2: str, pair_id: str) -> list[str]:
    problems: list[str] = []
    if payload.get("pair_id") != pair_id:
        problems.append(f"pair_id should be {pair_id}")

    turn1 = normalize(payload.get("shared_turn1") or "")
    if not turn1:
        problems.append("shared_turn1 is empty")
    if TAG_RE.search(turn1):
        problems.append("shared_turn1 has a bracketed tag")
    if VOC_WORD_RE.search(turn1) or TURN1_GIVEAWAY_RE.search(turn1):
        problems.append(
            "shared_turn1 names or strongly implies a vocalization; rewrite it neutrally"
        )
    if turn1.strip().endswith("?") and len(turn1.split()) < 6:
        problems.append("shared_turn1 is a bare question with little content to react to")

    v1 = payload.get("version_1") or {}
    v2 = payload.get("version_2") or {}
    f1, f2 = formula_of(voc1), formula_of(voc2)
    if normalize(v1.get("vocalization") or "") != f1:
        problems.append(f"version_1.vocalization must be exactly {f1}")
    if normalize(v2.get("vocalization") or "") != f2:
        problems.append(f"version_2.vocalization must be exactly {f2}")

    i1 = normalize(v1.get("interpretation") or "")
    i2 = normalize(v2.get("interpretation") or "")
    r1 = normalize(v1.get("response") or "")
    r2 = normalize(v2.get("response") or "")

    for label, text in (("version_1.interpretation", i1), ("version_2.interpretation", i2)):
        if not text:
            problems.append(f"{label} is empty")
        elif BARE_INTERPRETATION_RE.match(text):
            problems.append(f"{label} is a bare emotion label, not a pragmatic reading")
        elif len(text.split()) > MAX_INTERPRETATION_WORDS:
            problems.append(f"{label} is too long")
        if VOC_WORD_RE.search(text):
            problems.append(f"{label} names the vocalization instead of interpreting it")

    for label, text in (("version_1.response", r1), ("version_2.response", r2)):
        if not text:
            problems.append(f"{label} is empty")
        elif len(text.split()) > MAX_RESPONSE_WORDS:
            problems.append(f"{label} is too long")
        if TAG_RE.search(text):
            problems.append(f"{label} has an audio tag")
        if VOC_WORD_RE.search(text):
            problems.append(f"{label} names the vocalization instead of reacting to it")

    if i1 and i2 and i1.lower() == i2.lower():
        problems.append("the two interpretations must differ")
    if r1 and r2 and r1.lower() == r2.lower():
        problems.append("the two responses must differ")


    rationale = normalize(payload.get("contrastive_rationale") or "")
    if len(rationale.split()) < 8:
        problems.append("contrastive_rationale is too short")

    return problems


JUDGE_PROPERTIES = [
    (
        "vocalizations_both_plausible",
        "at least one vocalization is not a plausible reaction to turn1, or turn1 reveals "
        "B's expected emotional state or reaction",
    ),
    (
        "interpretations_clearly_contrastive",
        "the two interpretations are paraphrases, express the same attitude/function, or "
        "either is generic enough to fit both vocalizations (swapping them would not "
        "clearly make the pair worse)",
    ),
    (
        "responses_clearly_contrastive",
        "the two responses perform the same conversational function, or a swapped response "
        "would sound about as natural as the intended one",
    ),
    (
        "negative_vocalization_semantics_preserved",
        "a negative/marked vocalization (grunt/sigh/sob/yawn) is treated as plain "
        "enthusiastic agreement, cheerful compliance, or emotionally unaffected "
        "continuation, with no evidence the vocalization mattered",
    ),
]

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{key: {"type": "boolean"} for key, _ in JUDGE_PROPERTIES},
        "overall": {"type": "string", "enum": ["PASS", "FAIL"]},
        "reason": {"type": "string"},
    },
    "required": [key for key, _ in JUDGE_PROPERTIES] + ["overall", "reason"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """
You are a strict verifier for contrastive non-speech vocalization benchmark items.
Each item contains:

* one shared `turn1` from Speaker A
* `vocalization_1`
* `interpretation_1`
* `response_1`
* `vocalization_2`
* `interpretation_2`
* `response_2`

Your job is to determine whether the pair is suitable for the benchmark.
Evaluate the following four criteria.
1. Vocalizations both plausible
Both vocalizations should be reasonable reactions to `turn1`.
`turn1` should not strongly predict one vocalization or make the other implausible.
PASS only if:

* both vocalizations could naturally occur after `turn1`; and
* `turn1` does not explicitly reveal B's emotional state or expected reaction.

2. Interpretations clearly contrastive
The two interpretations must express meaningfully different pragmatic meanings.
Each interpretation must fit its intended vocalization better than the other interpretation.
FAIL if:

* the interpretations are paraphrases;
* they express essentially the same attitude or conversational function;
* either interpretation is generic enough to fit both vocalizations.

Ask yourself:
If I swapped the two interpretations, would the pair become clearly worse?
If not, FAIL.
3. Responses clearly contrastive
The two responses must perform different conversational functions and naturally follow their intended vocalizations.
Examples of different functions include:

* teasing vs. reproaching
* comforting vs. celebrating
* expressing concern vs. expressing disbelief
* agreeing reluctantly vs. objecting
* asking for clarification vs. signaling boredom

Ask yourself:
Would `response_1` sound clearly worse after `vocalization_2` than `response_2` does?
and
Would `response_2` sound clearly worse after `vocalization_1` than `response_1` does?
If either swapped response remains about as natural as the intended response, FAIL.
Do not treat minor differences in wording, sentiment intensity, or tone as different pragmatic functions.
4. Negative vocalization semantics preserved
For:

* grunt
* sigh
* sob
* yawn

the interpretation and response should preserve the relevant reluctance, annoyance, fatigue, distress, resignation, boredom, or other marked reaction when appropriate.
FAIL if a negative or marked vocalization is treated as:

* plain enthusiastic agreement;
* cheerful compliance;
* emotionally unaffected continuation;
* neutral acknowledgment with no evidence that the vocalization matters.

This criterion is not automatically triggered just because one of these vocalizations appears. Judge whether the generated interpretation and response are compatible with the vocalization in context.
Overall decision
Return `PASS` only if all four criteria pass.
Otherwise return `FAIL`.
Be strict. The benchmark depends on the two vocalizations producing clearly distinguishable pragmatic interpretations and continuations.
A pair should fail if the distinction relies mainly on subtle wording rather than on a meaningful conversational difference.

Output format: return `vocalizations_both_plausible`, `interpretations_clearly_contrastive`,
`responses_clearly_contrastive`, and `negative_vocalization_semantics_preserved` as booleans,
`overall` as exactly "PASS" or "FAIL", and `reason` as one concise sentence explaining the
most important reason for the decision — identify the main failure in `reason` if the item
fails.
Do not rewrite or repair the item. Only verify it.
""".strip()


def judge_pair(client: OpenAI, payload: dict, model: str, effort: str) -> tuple[dict, dict]:
    v1 = payload["version_1"]
    v2 = payload["version_2"]
    item = {
        "turn1": payload["shared_turn1"],
        "vocalization_1": v1["vocalization"],
        "interpretation_1": v1["interpretation"],
        "response_1": v1["response"],
        "vocalization_2": v2["vocalization"],
        "interpretation_2": v2["interpretation"],
        "response_2": v2["response"],
    }
    kwargs = dict(
        model=model,
        instructions=JUDGE_SYSTEM,
        input=json.dumps(item, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "predicting_response_upgraded_judge",
                "schema": JUDGE_SCHEMA,
                "strict": True,
            }
        },
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    if supports_reasoning_effort(model):
        kwargs["reasoning"] = {"effort": effort}
    response = client.responses.create(**kwargs)
    if response.status != "completed":
        raise RuntimeError(f"judge status={response.status}")
    verdict = json.loads(response.output_text)
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return verdict, usage


def judge_problems(verdict: dict) -> list[str]:
    problems = [message for key, message in JUDGE_PROPERTIES if not verdict.get(key)]
    if not problems and verdict.get("overall") == "FAIL":
        # the four booleans were all true but the model still failed it overall —
        # an inconsistent verdict; surface the stated reason rather than silently pass
        problems.append(verdict.get("reason") or "judge returned overall FAIL")
    return problems


def user_prompt(
    voc1: str,
    voc2: str,
    pair_id: str,
    used_turn1s: list[str],
    used_functions: dict[str, list[str]],
    theme: str | None = None,
) -> str:
    lines = [
        "Generate exactly one contrastive pair.",
        "",
        f"Pair ID: {pair_id}",
        f"Vocalization 1: {formula_of(voc1)}",
        f"  choose a function that fits your scene from: {', '.join(VOCALIZATIONS[voc1]['meanings'])}",
        f"Vocalization 2: {formula_of(voc2)}",
        f"  choose a function that fits your scene from: {', '.join(VOCALIZATIONS[voc2]['meanings'])}",
        "",
        "Aim for the two gold responses to land on different conversational functions",
        f"(see the function list in section 8), e.g.: {', '.join(FUNCTION_MENU[:8])}, etc.",
        "Both vocalizations must be natural reactions to the SAME shared_turn1, and swapping",
        "either the interpretations or the responses must clearly make them worse.",
    ]
    if theme:
        lines += [
            "",
            f"Theme: {theme} — {THEMES[theme]}",
            "Set shared_turn1 recognizably within this theme; do not drift into an",
            "unrelated setting unless it naturally follows from it.",
        ]
    if used_turn1s:
        lines += ["", "Do not reuse these Turn 1 situations:"]
        lines += [f"- {text}" for text in used_turn1s[-16:]]
    pair_functions = used_functions.get(voc1, [])[-6:] + used_functions.get(voc2, [])[-6:]
    if pair_functions:
        lines += ["", "Already used recently for these vocalizations; prefer a different function:"]
        lines += [f"- {text}" for text in pair_functions]
    return "\n".join(lines)


def call_model(
    client: OpenAI, prompt: str, model: str, effort: str
) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "predicting_response_upgraded_pair",
                        "schema": output_schema(),
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
            print(f"    retry in {wait}s: {exc}", flush=True)
            time.sleep(wait)
    raise last_error  # type: ignore[misc]


class GenerationFailed(RuntimeError):
    """Raised when every attempt is rejected; carries the last draft for inspection."""

    def __init__(self, message: str, draft: dict | None, problems: list[str], judge: dict | None):
        super().__init__(message)
        self.draft = draft
        self.problems = problems
        self.judge = judge


def print_draft(payload: dict) -> None:
    print(f"      A: {payload.get('shared_turn1')}", flush=True)
    for label, key in (("v1", "version_1"), ("v2", "version_2")):
        v = payload.get(key) or {}
        print(
            f"      {label} B: {v.get('vocalization')}  ({v.get('interpretation')})",
            flush=True,
        )
        print(f"         B continues: {v.get('response')}", flush=True)


def print_verdict(problems: list[str], verdict: dict | None) -> None:
    print(f"      failed checks: {problems}", flush=True)
    if verdict is not None:
        print(f"      judge verdict: {verdict}", flush=True)


def generate_one(
    client: OpenAI,
    voc1: str,
    voc2: str,
    pair_id: str,
    args: argparse.Namespace,
    used_turn1s: list[str],
    used_functions: dict[str, list[str]],
) -> dict:
    verbose = getattr(args, "verbose", False)
    theme = getattr(args, "theme", None)

    def build(extra: str = "") -> str:
        base = user_prompt(voc1, voc2, pair_id, used_turn1s, used_functions, theme)
        return base + extra

    prompt = build()
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    last_draft: dict | None = None
    last_verdict: dict | None = None
    served_by = args.model

    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        last_draft = payload
        problems = validate(payload, voc1, voc2, pair_id)
        verdict: dict | None = None
        if not problems and not args.no_judge:
            verdict, judge_usage = judge_pair(client, payload, args.model, args.effort)
            totals["input_tokens"] += judge_usage["input_tokens"]
            totals["output_tokens"] += judge_usage["output_tokens"]
            problems = judge_problems(verdict)
        last_verdict = verdict
        if verbose:
            print(f"    -- attempt {attempt}/{MAX_ATTEMPTS} draft --", flush=True)
            print_draft(payload)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            payload["contrast"] = f"{voc1}-{voc2}"
            payload["theme"] = theme
            if verdict is not None:
                payload["judge"] = verdict
            if verbose:
                print("      accepted", flush=True)
            return payload
        last_problems = problems
        prompt = build(
            "\n\nThe previous attempt failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nRebuild the item from scratch if the scene or the swap test is the problem."
            "\nReturn a corrected JSON object."
        )
        if verbose:
            print_verdict(problems, verdict)
        else:
            print(
                f"    rejected ({problems[0][:70]}); attempt {attempt}/{MAX_ATTEMPTS}",
                flush=True,
            )

    raise GenerationFailed(
        "still invalid after retries: " + "; ".join(last_problems),
        draft=last_draft,
        problems=last_problems,
        judge=last_verdict,
    )


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Predicting response — upgraded (2-turn, 3-question benchmark)",
        "",
        f"writer: {model} · {len(records)} pair(s)",
        "",
        "Turn 1 (A) is identical across both versions. Turn 2 is B's vocalization only —",
        "that is all the benchmark audio contains. The verbal continuation is a text-only",
        "gold answer for Q3, never synthesized. Q2 and Q3 are a forced choice between the",
        "two versions' own gold answers — no distractors. Option lettering below is for",
        "reading only; the real eval shuffles each question's options independently.",
        "",
    ]
    for record in records:
        v1, v2 = record["version_1"], record["version_2"]
        lines += [
            f"### Pair {record['pair_id']}",
            "",
            f"Contrast: {record.get('contrast', '')}",
            "",
            f"**Shared Turn 1** — A: {record['shared_turn1']}",
            "",
            f"**Version 1** — {v1['vocalization']} ({v1['interpretation']})",
            f"  B continues: {v1['response']}",
            "",
            f"**Version 2** — {v2['vocalization']} ({v2['interpretation']})",
            f"  B continues: {v2['response']}",
            "",
            "**Q1 options:** Gasp / Grunt / Laughter / Sigh / Sob / Yawn",
            "",
            "**Q2 interpretation options (for reading; real eval shuffles):**",
            f"  A. {v1['interpretation']}",
            f"  B. {v2['interpretation']}",
            "",
            "**Q3 continuation options (for reading; real eval shuffles):**",
            f"  A. {v1['response']}",
            f"  B. {v2['response']}",
            "",
            "**Contrastive rationale:**",
            record["contrastive_rationale"],
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
        "--n",
        type=int,
        default=1,
        help="pairs per vocalization contrast (default: 1 -> 15 pairs)",
    )
    parser.add_argument(
        "--contrast",
        action="append",
        default=[],
        help="restrict to ids like laughter-sigh",
    )
    parser.add_argument(
        "--theme",
        default=None,
        choices=list(THEMES),
        help="optional scene theme; not in the original spec, defaults to unrestricted",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="skip the model audit of the swap test (mechanical checks only)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print every draft transcript and full judge verdict, accepted or rejected",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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

    print(
        f"{len(jobs)} pair(s)  "
        f"({len({(a, b) for a, b, _ in jobs})} contrast type(s) x {args.n})",
        flush=True,
    )

    prefix = f"{args.theme}_" if args.theme else ""

    if args.dry_run:
        for voc1, voc2, sample in jobs:
            pair_id = f"{prefix}{voc1}_{voc2}_{sample:03d}"
            print("\n" + "=" * 72)
            print(f"{pair_id} · {formula_of(voc1)} vs {formula_of(voc2)}")
            print("=" * 72)
            print(user_prompt(voc1, voc2, pair_id, [], {}, args.theme))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(
        f"model: {args.model}"
        + ("  (audit off)" if args.no_judge else "  (+ swap-test audit)"),
        flush=True,
    )
    records: list[dict] = []
    used_turn1s: list[str] = []
    used_functions: dict[str, list[str]] = {}

    for index, (voc1, voc2, sample) in enumerate(jobs, start=1):
        pair_id = f"{prefix}{voc1}_{voc2}_{sample:03d}"
        contrast_id = f"{voc1}-{voc2}"
        print(f"[{index}/{len(jobs)}] {pair_id}", flush=True)
        try:
            record = generate_one(client, voc1, voc2, pair_id, args, used_turn1s, used_functions)
            records.append(record)
            used_turn1s.append(record.get("shared_turn1", ""))
            used_functions.setdefault(voc1, []).append(record["version_1"]["interpretation"])
            used_functions.setdefault(voc2, []).append(record["version_2"]["interpretation"])
            print(f"    A: {record.get('shared_turn1', '')}", flush=True)
            print(
                f"    v1 {record['version_1']['vocalization']} -> {record['version_1']['response']}",
                flush=True,
            )
            print(
                f"    v2 {record['version_2']['vocalization']} -> {record['version_2']['response']}",
                flush=True,
            )
        except GenerationFailed as exc:
            rec = {
                "pair_id": pair_id,
                "contrast": contrast_id,
                "error": f"{type(exc).__name__}: {exc}",
                "last_problems": exc.problems,
            }
            if exc.draft is not None:
                rec["last_draft"] = exc.draft
            if exc.judge is not None:
                rec["last_judge"] = exc.judge
            records.append(rec)
            print(f"    failed: {exc}", flush=True)
            if exc.draft is not None:
                print("    last draft:", flush=True)
                print_draft(exc.draft)
        except Exception as exc:
            records.append(
                {"pair_id": pair_id, "contrast": contrast_id, "error": f"{type(exc).__name__}: {exc}"}
            )
            print(f"    failed: {exc}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "effort": args.effort,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vocalizations": VOC_ORDER,
        "theme": args.theme,
        "n_per_contrast": args.n,
        "judged": not args.no_judge,
        "structure": (
            "turn 1 (A) shared across versions; turn 2 (B) is the voc-only benchmark audio; "
            "response is a text-only gold continuation for Q3, never synthesized"
        ),
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "shared_turn1" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

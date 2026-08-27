"""Three-turn domestic conversations: Jane proposes, Alex reacts wordlessly, Jane replies.

    Turn 1  Jane:  proposes an idea or plan            (identical across all six versions)
    Turn 2  Alex:  one non-speech vocalization only    (the only thing that varies)
    Turn 3  Jane:  responds

Each item pairs ONE Jane turn 1 with ALL SIX vocalizations, so an item is six versions of
the same conversation that diverge only at turn 2. Jane's turn 3 is the dependent variable:
whatever changes in it is attributable to the sound Alex made and nothing else.

That six-way requirement is the hard constraint here. A turn 1 that supports a gasp and a
sigh is easy; one that also supports a sob and a yawn is not. The proposal has to be
surprising, effortful, tedious-sounding, emotionally loaded and faintly absurd all at once,
or some of the six reactions will be dead on arrival.

Generation is a writer call against SYSTEM_PROMPT followed by:
  1. mechanical validate() — shape, all six present, leakage, six distinct responses
  2. an LLM judge_item() — are all six plausible, and is each Jane reply really tied to its
     own vocalization rather than swappable with another version's

Usage:
    python make_response/generate.py
    python make_response/generate.py --n 3 --verbose
    python make_response/generate.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "items.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
MAX_OUTPUT_TOKENS = 6000
MAX_ATTEMPTS = 4

# Kept loose on purpose. Tight caps here backfire: squeezing Jane's turn 3 into a dozen
# words strips out what anchors it to its own vocalization, and the judge then — correctly —
# fails it as generic. Natural domestic speech runs longer than it feels like it should.
MAX_TURN1_WORDS = 52
MAX_RESPONSE_WORDS = 42
MAX_INTERPRETATION_WORDS = 42

SPEAKER_PROPOSER = "Jane"
SPEAKER_REACTOR = "Alex"

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]

# One seed per item. Without these the writer lands on "sell the house and restore a dead
# parent's cottage" every single time — the guidance about proposals with history in the
# home points straight at it. Each seed still has to carry all six reactions.
TOPIC_SEEDS = [
    "taking someone or something into the home — a relative who needs care, a lodger, "
    "a foster child, a second animal",
    "a large purchase or renovation the household would feel for years — a car, a "
    "structural change, knocking a room through, a loan",
    "moving, or refusing to move — a new city, downsizing, a job that relocates them, "
    "giving up a tenancy",
    "undoing something one of them built, planted, made, or has kept for years",
    "committing the household to a long obligation — hosting a big family gathering, a "
    "wedding, a rescue project, a course of study",
    "changing how the household runs day to day — money, schedules, who does what, "
    "separate rooms, screens, a strict new rule",
    "an animal's care — a serious vet decision, rehoming, a demanding new routine",
    "clearing out, giving away, or selling belongings that someone in the house is "
    "attached to",
]

# what each sound has to be able to mean, given a single shared proposal
VOC_ROLE = {
    "gasp": "shock, alarm, disbelief, or delighted surprise at the proposal",
    "grunt": "reluctance, annoyance, skepticism, or grudging acknowledgement",
    "laughter": "finding the proposal absurd, teasing Jane, or deflecting with humour",
    "sigh": "weariness, resignation, reluctant acceptance, or relief",
    "sob": "being emotionally overwhelmed — grief, hurt, or being deeply moved",
    "yawn": "boredom, disengagement, or being far too tired to take this on",
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
            "jane_response": {"type": "string"},
        },
        "required": ["vocalization", "interpretation", "jane_response"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "jane_turn1": {"type": "string"},
            "versions": {
                "type": "object",
                "properties": {voc: version_schema for voc in VOC_ORDER},
                "required": VOC_ORDER,
                "additionalProperties": False,
            },
            "why_all_six_work": {"type": "string"},
        },
        "required": ["item_id", "jane_turn1", "versions", "why_all_six_work"],
        "additionalProperties": False,
    }


SYSTEM_PROMPT = f"""
You are generating data for a benchmark that tests whether an audio-language model can hear
a non-speech vocalization and understand what it communicates in a specific conversation.

THE FORMAT

Every item is a three-turn domestic conversation between two people, {SPEAKER_PROPOSER} and
{SPEAKER_REACTOR}. They share a home — partners, housemates, or family living together.

    Turn 1  {SPEAKER_PROPOSER}:  proposes an idea or a plan
    Turn 2  {SPEAKER_REACTOR}:   reacts with ONE non-speech vocalization and no words at all
    Turn 3  {SPEAKER_PROPOSER}:  responds to that reaction

ONE ITEM = SIX VERSIONS

You write ONE turn 1 from {SPEAKER_PROPOSER}, and then six versions of the conversation. The
turn 1 is identical in all six. In each version {SPEAKER_REACTOR} produces a different
vocalization, and {SPEAKER_PROPOSER}'s turn 3 responds to that particular reaction.

The six vocalizations, one per version:

    [gasp]      {VOC_ROLE['gasp']}
    [grunt]     {VOC_ROLE['grunt']}
    [laughter]  {VOC_ROLE['laughter']}
    [sigh]      {VOC_ROLE['sigh']}
    [sob]       {VOC_ROLE['sob']}
    [yawn]      {VOC_ROLE['yawn']}

Those are the ranges available to each sound, not fixed meanings. Choose whichever reading
fits your scene.

THE HARD PART: ONE TURN 1 THAT SUPPORTS ALL SIX

This is the constraint that makes or breaks the item. A proposal that invites a gasp and a
sigh is easy to write. The same proposal must ALSO leave room for {SPEAKER_REACTOR} to be
moved to tears, to find it funny, to be too tired to face it, and to grunt at it.

So build a proposal that is several things at once:

  * consequential enough to be startling
  * effortful enough to be wearying
  * long or procedural enough to be boring
  * emotionally loaded enough that tears are possible
  * faintly ridiculous, or overreaching, so amusement is possible
  * unwelcome enough that reluctance is possible

Domestic proposals that carry this much weight usually touch something with history in the
home. Clearing out a room that belonged to someone. A large purchase or renovation. Moving.
Taking in a relative or an animal. Undoing something one of them built. Committing the
household to a long project, a big gathering, or a change in how they live.

A thin proposal — reorganising a shelf, trying a new recipe — cannot carry six reactions.
Neither can a proposal with no emotional stake, where a sob would be baffling.

TURN 1 REQUIREMENTS

  * natural spoken language, one to three sentences
  * enough context that {SPEAKER_REACTOR}'s reaction is interpretable
  * must NOT state or predict {SPEAKER_REACTOR}'s feelings, mood, or likely reaction
  * must NOT make any one of the six reactions obviously inevitable
  * no stage directions, no narration, no bracketed tags

INTERPRETATION REQUIREMENTS

For each version, write one sentence saying what {SPEAKER_REACTOR} is communicating with
that reaction, in this specific situation.

Capture the pragmatic meaning, not the emotion label.

  Weak:   {SPEAKER_REACTOR} is upset.
  Better: {SPEAKER_REACTOR} is grieving the room being changed and is not ready to have it
          emptied.

  Weak:   {SPEAKER_REACTOR} is amused.
  Better: {SPEAKER_REACTOR} thinks {SPEAKER_PROPOSER} is wildly underestimating the job and
          is teasing them for it.

Never use the words gasp, grunt, laugh, laughter, sigh, sob, cry, or yawn inside an
interpretation. Interpret the reaction; do not name the sound.

{SPEAKER_PROPOSER}'S TURN 3 REQUIREMENTS

Each turn 3 must:

  * read as natural spoken conversation, one or two sentences
  * respond to THAT reaction specifically — a listener should be able to infer roughly what
    {SPEAKER_REACTOR} did from how {SPEAKER_PROPOSER} answers
  * perform a different conversational move from the other five versions
  * never name or describe the sound. {SPEAKER_PROPOSER} does not say "why are you sighing"
    or "don't laugh at me". She responds to what it MEANT.

Six different conversational moves, one per version. Useful moves include: reassuring,
defending the plan, backing down, softening or comforting, teasing back, pressing on,
negotiating, conceding, explaining the reasoning, dropping it for now, asking what is
wrong, offering to do it alone, promising to take the weight off {SPEAKER_REACTOR}.

THE SWAP TEST — THE MOST IMPORTANT RULE

Take {SPEAKER_PROPOSER}'s turn 3 from any version and put it after a different version's
vocalization. It should sound clearly wrong or clearly worse.

If a turn 3 would work about equally well after three of the six sounds, it is too generic.
Rewrite it so it is anchored to its own reaction. Generic warmth — "okay, we can talk about
it later", "I hear you", "that's fair" — fails this test and must not appear.

The reaction to a sob and the reaction to a yawn should not both be gentle concern. The
reaction to a grunt and the reaction to a sigh should not both be mild concession. Push each
one somewhere distinct.

WORKED EXAMPLE OF THE SHAPE

    Turn 1  {SPEAKER_PROPOSER}: I think it is time we cleared out your dad's workshop and
            turned it into the spare room we keep saying we need.

    [gasp]      {SPEAKER_REACTOR} is blindsided that she would raise this now.
                {SPEAKER_PROPOSER}: I know, I should have led up to it instead of just saying it.

    [sob]       {SPEAKER_REACTOR} is not ready to lose the last room that is still his.
                {SPEAKER_PROPOSER}: Then we leave it exactly as it is. It was only an idea.

    [yawn]      {SPEAKER_REACTOR} cannot face a project of that size right now.
                {SPEAKER_PROPOSER}: You would not have to lift a thing, I would do it over my week off.

Notice each turn 3 does different work — apologising for the delivery, withdrawing the
proposal, removing the labour — and none of them would sit right after either of the others.

OUTPUT

Return exactly one JSON object matching the schema.

  * `item_id` — copy it exactly from the Item ID given in the user message.
  * `jane_turn1` — {SPEAKER_PROPOSER}'s proposal only, no speaker label.
  * `versions` — an object with all six keys: gasp, grunt, laughter, sigh, sob, yawn. Each
    holds `vocalization` (the exact tag, e.g. `[sigh]`), `interpretation`, and
    `jane_response`.
  * `why_all_six_work` — two or three sentences on why this one proposal genuinely leaves
    room for all six reactions, and why the six turn 3s are not interchangeable.

Write exactly ONE item.
""".strip()


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
    r"chuckle(?:s|d)?|groan(?:s|ed|ing)?|whimper(?:s|ed|ing)?|snicker(?:s|ed|ing)?"
    r")\b"
)

# Jane must not forecast Alex's reaction inside the proposal itself
TURN1_GIVEAWAY_RE = re.compile(
    r"(?i)\b("
    r"exhausted|too tired|worn out|"
    r"you(?:'| a)?re going to hate|you will hate|don't be upset|do not be upset|"
    r"i know you'?re tired|before you (?:react|say anything)"
    r")\b"
)

# generic filler that passes for a response but survives any vocalization
GENERIC_RESPONSE_RE = re.compile(
    r"(?i)^(?:okay|ok|alright|all right|fine|well)?[\s,.]*"
    r"(?:i hear you|that'?s fair|fair enough|we can talk about it later|"
    r"let'?s talk later|we'?ll figure it out|whatever you think|up to you)\.?$"
)


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def validate(payload: dict, item_id: str) -> list[str]:
    problems: list[str] = []

    if payload.get("item_id") != item_id:
        problems.append(f"item_id should be {item_id}")

    turn1 = normalize(payload.get("jane_turn1") or "")
    if not turn1:
        problems.append("jane_turn1 is empty")
    else:
        if TAG_RE.search(turn1):
            problems.append("jane_turn1 contains a bracketed tag")
        if VOC_WORD_RE.search(turn1) or TURN1_GIVEAWAY_RE.search(turn1):
            problems.append(
                "jane_turn1 names a sound or predicts Alex's reaction; keep it neutral"
            )
        if len(turn1.split()) > MAX_TURN1_WORDS:
            problems.append("jane_turn1 is too long")
        if len(turn1.split()) < 8:
            problems.append("jane_turn1 is too thin to support six different reactions")

    versions = payload.get("versions") or {}
    missing = [voc for voc in VOC_ORDER if voc not in versions]
    if missing:
        problems.append(f"missing versions: {', '.join(missing)}")

    responses: dict[str, str] = {}
    interpretations: dict[str, str] = {}

    for voc in VOC_ORDER:
        version = versions.get(voc) or {}
        tag = normalize(version.get("vocalization") or "")
        interpretation = normalize(version.get("interpretation") or "")
        response = normalize(version.get("jane_response") or "")

        if tag != f"[{voc}]":
            problems.append(f"versions.{voc}.vocalization must be exactly [{voc}]")

        if not interpretation:
            problems.append(f"versions.{voc}.interpretation is empty")
        else:
            interpretations[voc] = interpretation
            if VOC_WORD_RE.search(interpretation):
                problems.append(f"versions.{voc}.interpretation names the sound")
            if len(interpretation.split()) > MAX_INTERPRETATION_WORDS:
                problems.append(f"versions.{voc}.interpretation is too long")
            if not re.search(rf"\b{SPEAKER_REACTOR}\b", interpretation):
                problems.append(
                    f"versions.{voc}.interpretation should say what {SPEAKER_REACTOR} "
                    "is communicating"
                )

        if not response:
            problems.append(f"versions.{voc}.jane_response is empty")
        else:
            responses[voc] = response
            if TAG_RE.search(response):
                problems.append(f"versions.{voc}.jane_response contains a tag")
            if VOC_WORD_RE.search(response):
                problems.append(
                    f"versions.{voc}.jane_response names the sound instead of "
                    "responding to what it meant"
                )
            if len(response.split()) > MAX_RESPONSE_WORDS:
                problems.append(f"versions.{voc}.jane_response is too long")
            if GENERIC_RESPONSE_RE.match(response):
                problems.append(
                    f"versions.{voc}.jane_response is generic filler that would follow "
                    "any of the six reactions"
                )

    seen: dict[str, str] = {}
    for voc, response in responses.items():
        key = response.lower().rstrip(".!?")
        if key in seen:
            problems.append(
                f"versions.{voc}.jane_response duplicates versions.{seen[key]}.jane_response"
            )
        else:
            seen[key] = voc

    seen_interp: dict[str, str] = {}
    for voc, interpretation in interpretations.items():
        key = interpretation.lower().rstrip(".")
        if key in seen_interp:
            problems.append(
                f"versions.{voc}.interpretation duplicates versions.{seen_interp[key]}"
            )
        else:
            seen_interp[key] = voc

    if len(normalize(payload.get("why_all_six_work") or "").split()) < 12:
        problems.append("why_all_six_work is too short")

    return problems


JUDGE_PROPERTIES = [
    (
        "all_six_plausible",
        "at least one of the six vocalizations would be odd or baffling after this turn 1, "
        "or turn 1 makes one of them obviously inevitable",
    ),
    (
        "responses_each_tied_to_own_vocalization",
        "at least one of Jane's responses is generic enough to follow several of the six "
        "reactions, so it is not anchored to its own",
    ),
    (
        "responses_mutually_distinct",
        "two or more of Jane's responses perform the same conversational move, differing "
        "only in wording, intensity, or politeness",
    ),
    (
        "interpretations_context_specific",
        "an interpretation is a bare emotion label or a generic gloss of the sound rather "
        "than a reading grounded in this particular proposal",
    ),
    (
        "marked_vocalizations_respected",
        "a grunt, sigh, sob, or yawn is treated as plain agreement or cheerful enthusiasm, "
        "with no sign the reluctance, weariness, or distress registered",
    ),
]

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{key: {"type": "boolean"} for key, _ in JUDGE_PROPERTIES},
        "weakest_vocalization": {"type": "string", "enum": VOC_ORDER + ["none"]},
        "swappable_pairs": {"type": "array", "items": {"type": "string"}},
        "overall": {"type": "string", "enum": ["PASS", "FAIL"]},
        "reason": {"type": "string"},
    },
    "required": [key for key, _ in JUDGE_PROPERTIES]
    + ["weakest_vocalization", "swappable_pairs", "overall", "reason"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = f"""
You are a strict verifier for a three-turn vocalization benchmark.

Each item gives you:

  * `jane_turn1` — {SPEAKER_PROPOSER} proposes an idea or plan. Identical across all six
    versions.
  * six versions, keyed by vocalization. In each, {SPEAKER_REACTOR} reacts with only that
    non-speech sound and no words, and then {SPEAKER_PROPOSER} responds. Each version has an
    `interpretation` of what {SPEAKER_REACTOR} communicated and {SPEAKER_PROPOSER}'s
    `jane_response`.

Judge five criteria.

1. all_six_plausible
   Could a real person plausibly react to this proposal with EACH of the six sounds — gasp,
   grunt, laughter, sigh, sob, yawn? Check every one individually. The usual failure is a
   proposal with no emotional stake, where being moved to tears makes no sense, or one too
   trivial for weariness or boredom. FAIL if any of the six would be baffling here, or if
   turn 1 makes one of them the obvious reaction.
   Report the shakiest one in `weakest_vocalization`, or "none" if all six are solid.

2. responses_each_tied_to_own_vocalization
   For each version, ask: would {SPEAKER_PROPOSER}'s response sound clearly wrong after a
   different one of the six sounds? A response anchored to its own reaction survives this;
   a vague or all-purpose response does not. FAIL if any response would sit comfortably
   after several different reactions.

3. responses_mutually_distinct
   Do the six responses perform six different conversational moves — reassuring, defending
   the plan, backing down, comforting, teasing back, pressing on, negotiating, conceding,
   dropping it, offering to do it alone? FAIL if two or more do the same work with different
   words. Differences in politeness, warmth, or sentence length are not different moves.
   List every offending pair in `swappable_pairs` as strings like "sigh/grunt". Empty list
   if there are none.

4. interpretations_context_specific
   Does each interpretation say what {SPEAKER_REACTOR} communicates about THIS proposal?
   FAIL on bare emotion labels, or on generic glosses of the sound that would read the same
   in any conversation.

5. marked_vocalizations_respected
   For grunt, sigh, sob and yawn, do the interpretation and response register the reluctance,
   weariness, or distress? FAIL if one of them is treated as plain agreement or cheerful
   enthusiasm with no sign the reaction mattered. Do not fail this merely because one of
   those sounds appears — judge whether the handling fits.

OVERALL

Return PASS only if all five criteria pass. Otherwise FAIL.

Be strict. Six-way contrast is demanding and most drafts fail on criterion 2 or 3 — the
middle sounds drift toward the same accommodating reply. Give `reason` as one concise
sentence naming the single most important problem, or what carries the item if it passes.

Do not rewrite or repair the item. Only verify it.
""".strip()


def judge_item(client: OpenAI, payload: dict, model: str, effort: str) -> tuple[dict, dict]:
    item = {
        "jane_turn1": payload["jane_turn1"],
        "versions": {
            voc: {
                "vocalization": payload["versions"][voc]["vocalization"],
                "interpretation": payload["versions"][voc]["interpretation"],
                "jane_response": payload["versions"][voc]["jane_response"],
            }
            for voc in VOC_ORDER
        },
    }
    kwargs = dict(
        model=model,
        instructions=JUDGE_SYSTEM,
        input=json.dumps(item, ensure_ascii=False, indent=2),
        text={
            "format": {
                "type": "json_schema",
                "name": "make_response_judge",
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
    swappable = verdict.get("swappable_pairs") or []
    if swappable and not any("same conversational move" in p for p in problems):
        problems.append(f"responses too close to each other: {', '.join(swappable)}")
    # `weakest_vocalization` is diagnostic, not a verdict — the judge names the shakiest of
    # the six even when all six pass, so it only matters when criterion 1 actually failed
    if not verdict.get("all_six_plausible"):
        weakest = verdict.get("weakest_vocalization")
        if weakest and weakest != "none":
            problems.append(f"[{weakest}] does not fit this turn 1; strengthen the proposal")
    if not problems and verdict.get("overall") == "FAIL":
        problems.append(verdict.get("reason") or "judge returned overall FAIL")
    return problems


def user_prompt(item_id: str, used_turn1s: list[str], topic: str | None = None) -> str:
    lines = [
        "Write exactly one item.",
        "",
        f"Item ID: {item_id}",
        f"Setting: domestic — {SPEAKER_PROPOSER} and {SPEAKER_REACTOR} share a home.",
        "",
    ]
    if topic:
        lines += [
            f"Build the proposal around this kind of situation: {topic}.",
            "Invent the specifics yourself. It still has to carry all six reactions.",
            "",
        ]
    lines += [
        f"{SPEAKER_PROPOSER} proposes something in turn 1. Then give six versions, one per",
        "vocalization, each with what Alex communicated and how Jane responds to it.",
        "",
        "Before you settle on the proposal, test it against all six reactions in your head.",
        "If you cannot picture Alex being moved to tears by it, or too tired to face it, the",
        "proposal is not carrying enough weight — pick a different one.",
    ]
    if used_turn1s:
        lines += ["", "Proposals already used — write about something clearly different:"]
        lines += [f"- {text}" for text in used_turn1s[-12:]]
    return "\n".join(lines)


def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict, str]:
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
                        "name": "make_response_item",
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
                    f"status={response.status} "
                    f"details={getattr(response, 'incomplete_details', None)}"
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
    def __init__(self, message: str, draft: dict | None, problems: list[str], judge: dict | None):
        super().__init__(message)
        self.draft = draft
        self.problems = problems
        self.judge = judge


def print_draft(payload: dict) -> None:
    print(f"      {SPEAKER_PROPOSER}: {payload.get('jane_turn1')}", flush=True)
    versions = payload.get("versions") or {}
    for voc in VOC_ORDER:
        version = versions.get(voc) or {}
        print(f"      [{voc}] {version.get('interpretation')}", flush=True)
        print(f"         {SPEAKER_PROPOSER}: {version.get('jane_response')}", flush=True)


def generate_one(
    client: OpenAI, item_id: str, args: argparse.Namespace, used_turn1s: list[str],
    topic: str | None = None,
) -> dict:
    verbose = getattr(args, "verbose", False)
    prompt = user_prompt(item_id, used_turn1s, topic)
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

        problems = validate(payload, item_id)
        verdict: dict | None = None
        if not problems and not args.no_judge:
            verdict, judge_usage = judge_item(client, payload, args.model, args.effort)
            totals["input_tokens"] += judge_usage["input_tokens"]
            totals["output_tokens"] += judge_usage["output_tokens"]
            problems = judge_problems(verdict)
        last_verdict = verdict

        if verbose:
            print(f"    -- attempt {attempt}/{MAX_ATTEMPTS} --", flush=True)
            print_draft(payload)

        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            payload["speakers"] = {"proposer": SPEAKER_PROPOSER, "reactor": SPEAKER_REACTOR}
            payload["setting"] = "domestic"
            payload["topic_seed"] = topic
            if verdict is not None:
                payload["judge"] = verdict
            if verbose:
                print("      accepted", flush=True)
            return payload

        last_problems = problems
        if verbose:
            print(f"      rejected: {problems}", flush=True)
            if verdict is not None:
                print(f"      judge: {verdict}", flush=True)
        else:
            print(
                f"    rejected ({problems[0][:74]}); attempt {attempt}/{MAX_ATTEMPTS}",
                flush=True,
            )
        prompt = user_prompt(item_id, used_turn1s, topic) + (
            "\n\nThe previous attempt failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nIf the problem is that Jane's responses blur together, push them onto "
            "clearly different conversational moves. If the problem is that a sound does "
            "not fit the proposal, change the proposal so it carries more weight."
            "\nReturn a corrected JSON object."
        )

    raise GenerationFailed(
        "still invalid after retries: " + "; ".join(last_problems),
        draft=last_draft,
        problems=last_problems,
        judge=last_verdict,
    )


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# make_response — Jane proposes, Alex reacts wordlessly, Jane responds",
        "",
        f"writer: {model} · {len(records)} item(s) · {len(records) * len(VOC_ORDER)} versions",
        "",
        "Turn 1 is identical across all six versions of an item. Turn 2 is Alex's",
        "vocalization and nothing else. Turn 3 is Jane responding to that reaction —",
        "the only thing that differs between versions is the sound that caused it.",
        "",
    ]
    for record in records:
        lines += [
            f"## {record['item_id']}",
            "",
            f"**Turn 1 — {SPEAKER_PROPOSER}:** {record['jane_turn1']}",
            "",
        ]
        for voc in VOC_ORDER:
            version = record["versions"][voc]
            lines += [
                f"### {version['vocalization']}",
                "",
                f"**Turn 2 — {SPEAKER_REACTOR}:** {version['vocalization']}",
                "",
                f"*What it means:* {version['interpretation']}",
                "",
                f"**Turn 3 — {SPEAKER_PROPOSER}:** {version['jane_response']}",
                "",
            ]
        lines += [f"*Why all six work:* {record['why_all_six_work']}", ""]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort", default=EFFORT,
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--n", type=int, default=3, help="items to generate (default: 3)")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.out = args.out.resolve()
    return args


def main() -> None:
    args = parse_args()
    print(
        f"{args.n} item(s) x {len(VOC_ORDER)} vocalizations = "
        f"{args.n * len(VOC_ORDER)} three-turn versions",
        flush=True,
    )

    if args.dry_run:
        print("\n" + "=" * 72)
        print(user_prompt("domestic_001", [], TOPIC_SEEDS[0]))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)
    print(
        f"model: {args.model}" + ("  (judge off)" if args.no_judge else "  (+ six-way judge)"),
        flush=True,
    )

    records: list[dict] = []
    used_turn1s: list[str] = []

    for index in range(1, args.n + 1):
        item_id = f"domestic_{index:03d}"
        topic = TOPIC_SEEDS[(index - 1) % len(TOPIC_SEEDS)]
        print(f"[{index}/{args.n}] {item_id}  ({topic[:58]}...)", flush=True)
        try:
            record = generate_one(client, item_id, args, used_turn1s, topic)
            records.append(record)
            used_turn1s.append(record["jane_turn1"])
            print(f"    {SPEAKER_PROPOSER}: {record['jane_turn1']}", flush=True)
            for voc in VOC_ORDER:
                print(
                    f"      [{voc}]  -> {record['versions'][voc]['jane_response']}",
                    flush=True,
                )
        except GenerationFailed as exc:
            failed = {
                "item_id": item_id,
                "error": f"{type(exc).__name__}: {exc}",
                "last_problems": exc.problems,
            }
            if exc.draft is not None:
                failed["last_draft"] = exc.draft
            if exc.judge is not None:
                failed["last_judge"] = exc.judge
            records.append(failed)
            print(f"    failed: {exc}", flush=True)
            if exc.draft is not None:
                print("    last draft:", flush=True)
                print_draft(exc.draft)
        except Exception as exc:
            records.append({"item_id": item_id, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    failed: {exc}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "model": args.model,
                "effort": args.effort,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "setting": "domestic",
                "speakers": {"proposer": SPEAKER_PROPOSER, "reactor": SPEAKER_REACTOR},
                "vocalizations": VOC_ORDER,
                "judged": not args.no_judge,
                "structure": (
                    "turn 1 Jane proposes (shared across all six versions); turn 2 Alex "
                    "produces one vocalization and no words; turn 3 Jane responds to it"
                ),
                "results": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "versions" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

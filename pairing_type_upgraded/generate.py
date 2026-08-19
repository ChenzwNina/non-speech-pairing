"""Generate A/C contrastive pairs; B's first turn is a voc-only reaction.

Usage:
    python pairing_type_upgraded/generate.py
    python pairing_type_upgraded/generate.py --contrast laughter-sigh
    python pairing_type_upgraded/generate.py --dry-run
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

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string", "enum": ["A", "C"]},
        "text": {"type": "string"},
    },
    "required": ["speaker", "text"],
    "additionalProperties": False,
}

VERSION_SCHEMA = {
    "type": "object",
    "properties": {
        "vocalization": {"type": "string"},
        "intended_interpretation": {"type": "string"},
        "responder": {"type": "string", "enum": ["A", "C"]},
        "response": {"type": "string"},
    },
    "required": ["vocalization", "intended_interpretation", "responder", "response"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "pair_id": {"type": "string"},
        "shared_context": {
            "type": "array",
            "items": TURN_SCHEMA,
            "minItems": 3,
            "maxItems": 6,
        },
        "version_1": VERSION_SCHEMA,
        "version_2": VERSION_SCHEMA,
        "why_the_vocalization_changes_the_response": {"type": "string"},
    },
    "required": [
        "pair_id",
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

SYSTEM_PROMPT = """
You are generating dialogue data for a benchmark that tests whether an audio-language model can use a **non-speech vocalization** to predict the appropriate next conversational response.

The target non-speech vocalizations are:

* gasp
* grunt
* laughter
* sigh
* sob
* yawn

## Core benchmark design

Generate **contrastive dialogue pairs**.

Each pair contains:

1. A shared spoken dialogue context.
2. A third speaker, Speaker B, who has **not spoken anywhere in the preceding transcript**.
3. Speaker B's **first contribution to the conversation is a non-speech vocalization** supplied as external audio.
4. Two versions of that same context use two different vocalizations from Speaker B.
5. The appropriate next spoken response changes depending on B's vocalization.

The benchmark tests whether the model uses B's non-speech audio to determine what should happen next.

---

# Critical speaker constraint

The person who produces the target non-speech vocalization must **not have any previous spoken turn in the transcript**.

Use three speakers:

* Speaker A
* Speaker B
* Speaker C

**Speaker B is always the target vocalization speaker.**

Before the target vocalization:

* Speaker A may speak.
* Speaker C may speak.
* A and C may have several turns of conversation.
* **Speaker B must not have any dialogue turn.**
* B's first observable contribution must be the target non-speech vocalization.

Therefore, this is allowed:

A: I told him that was exactly what would happen.
C: You did warn him about it.
A: And now he's asking me to fix the whole thing.

B: [laughter]

A: Oh, you think this is funny?

This is NOT allowed:

A: I told you this would happen.
B: I know.
C: He definitely warned you.

B: [laughter]

This is invalid because Speaker B already spoke before producing the vocalization.

---

# Why this constraint exists

The benchmark will use **external audio recordings** for the target non-speech vocalization.

Therefore, Speaker B's vocalization must be their **first contribution** to the dialogue.

Do not establish B's voice through previous spoken dialogue.

Do not give B any lexical speech before the vocalization.

---

# Required contrastive-pair structure

Every item must contain **two versions of exactly the same spoken context**.

The only difference between the two versions before the final response is **Speaker B's non-speech vocalization**.

Use two different vocalizations selected from:

`[gasp]`
`[grunt]`
`[laughter]`
`[sigh]`
`[sob]`
`[yawn]`

For example:

## Shared context

A: I told everyone I didn't need the instructions.
C: That's usually how these stories start.
A: Well, I just realized I assembled the entire shelf backwards.

Speaker B has not spoken yet.

## Version 1

B: [laughter]
A: Yeah, yeah, get it out of your system.

## Version 2

B: [sigh]
A: I know. I should've listened to you.

The spoken context before B's vocalization must be **identical** across the two versions.

Both versions must use the same responder (A or C) after B's vocalization. Only the wording of that response may change.

---

# Most important requirement

The dialogue must be constructed so that the text alone does **not determine the correct final response**.

Before hearing Speaker B's vocalization:

* both candidate responses should be reasonably plausible;
* the model should not be able to confidently choose between them from the transcript alone.

After hearing B's vocalization:

* Vocalization 1 should make Response 1 clearly more appropriate;
* Vocalization 2 should make Response 2 clearly more appropriate.

The intended relationship is:

**same spoken context + Vocalization 1 → Response 1 preferred**

**same spoken context + Vocalization 2 → Response 2 preferred**

Changing only the non-speech audio should change the preferred continuation.

---

# Speaker B's role

Speaker B may be understood to be present during the conversation between A and C, but B must remain silent until the target vocalization.

A and C may speak about:

* something that just happened;
* something one of them did;
* a shared situation;
* a mistake;
* surprising information;
* an embarrassing event;
* plans;
* work or school;
* another person's behavior;
* something visible in their environment.

B can then react naturally through the vocalization.

Do not explicitly state:

"Speaker B has been listening silently."

The situation should make B's presence natural without explaining the benchmark mechanics.

---

# Target turn constraint

Speaker B's target turn must contain **only the non-speech vocalization**.

Correct:

B: [laughter]

Correct:

B: [sigh]

Incorrect:

B: [laughter] That's hilarious.

Incorrect:

B: Wow. [gasp]

Incorrect:

B: [annoyed grunt]

Incorrect:

B: [sarcastic laughter]

Use only the basic vocalization label.

The intended meaning must come from the preceding context and the acoustic realization, not from a descriptive label.

---

# Final response

Immediately after Speaker B's vocalization, either **Speaker A or Speaker C** should produce the next spoken response.

Preferably, that response should naturally react to what B communicated.

Example:

A: I told the whole office I could fix it myself.
C: And did you?
A: I somehow made it worse.

B: [laughter]
A: You're enjoying this way too much.

Alternative version:

B: [sigh]
A: I know. You warned me not to touch it.

The final response should demonstrate that the responding speaker interpreted B's reaction.

---

# Do not make the response trivial

Avoid final responses that merely identify the sound.

Bad:

B: [laughter]
A: You're laughing.

Bad:

B: [yawn]
A: You yawned.

Bad:

B: [sob]
A: Are you crying?

Prefer responses that reveal the **social or pragmatic interpretation**.

Good:

B: [laughter]
A: Fine, I admit it looked ridiculous.

Good:

B: [yawn]
C: Okay, we'll skip the long explanation.

Good:

B: [sigh]
A: I know. We're going in circles again.

---

# Pragmatic diversity

A vocalization must not always have the same meaning.

Use varied pragmatic interpretations.

## Gasp

Possible meanings include:

* surprise
* pleasant surprise
* shock
* fear
* admiration
* disbelief
* sudden realization

## Grunt

Possible meanings include:

* reluctant agreement
* annoyance
* acknowledgment
* dissatisfaction
* dismissal
* impatience
* skepticism

## Laughter

Possible meanings include:

* genuine amusement
* teasing
* mockery
* awkward amusement
* nervousness
* disbelief
* shared amusement
* irony

## Sigh

Possible meanings include:

* frustration
* disappointment
* relief
* resignation
* impatience
* exhaustion

## Sob

Possible meanings include:

* sadness
* hurt
* emotional overwhelm
* relief after distress
* being deeply moved

## Yawn

Possible meanings include:

* boredom
* tiredness
* lack of interest
* exhaustion
* disengagement
* difficulty maintaining attention

Do not always choose the most stereotypical interpretation.

---

# Good contrastive example

### Pair 001

**Shared context**

A: I've been explaining the new filing system for almost an hour.
C: You still have three sections left.
A: Right, and the next one is probably the most complicated.

**Version 1**

Vocalization: [yawn]
Intended interpretation: boredom / fatigue

B: [yawn]
A: Okay, I'll skip the details and give you the short version.

**Version 2**

Vocalization: [gasp]
Intended interpretation: surprise or concern

B: [gasp]
A: What? Did you notice something wrong with it?

**Why the vocalization changes the response:**
The preceding conversation does not determine B's reaction. A yawn suggests that B is losing attention, while a gasp suggests that B noticed something surprising or concerning.

---

# Another good contrastive example

### Pair 002

**Shared context**

A: Remember how I said the client would never approve my first draft?
C: Yeah, you were ready to rewrite the entire thing.
A: They just emailed me. They approved it without a single change.

**Version 1**

Vocalization: [gasp]
Intended interpretation: surprised excitement

B: [gasp]
A: I know! I had to read the email twice.

**Version 2**

Vocalization: [sigh]
Intended interpretation: relief

B: [sigh]
A: Exactly. We can finally stop worrying about it.

**Why the vocalization changes the response:**
Both surprise and relief are reasonable reactions to the news, but they motivate different conversational responses.

---

# Bad example: B appears earlier

A: Did you finish the report?
B: Almost.
C: We need it by noon.
A: That's going to be close.

B: [sigh]

INVALID.

Speaker B already produced lexical speech. B's vocalization is therefore not their first contribution.

---

# Bad example: context determines the answer

A: B has been awake for thirty hours.
C: Yeah, B can barely keep their eyes open.

B: [yawn]
A: You really need some sleep.

INVALID.

The preceding transcript already strongly predicts the meaning of the yawn and the response. The audio adds almost no new information.

---

# Bad example: same response works for both

Shared context:

A: I didn't get the job.
C: I'm sorry.

Version 1:

B: [sob]
A: It'll be okay.

Version 2:

B: [sigh]
A: It'll be okay.

INVALID.

Changing the vocalization does not meaningfully change the appropriate response.

---

# Bad example: vocalization label alone solves the task

Version 1:

B: [yawn]
A: Are you tired?

Version 2:

B: [sob]
A: Are you sad?

INVALID.

This primarily tests recognition of stereotypical vocalization meanings rather than contextual conversational reasoning.

---

# Pairing requirements

Every pair must use two different vocalizations.

The user message names the exact two vocalizations. Use those tags. You may refine the interpretation wording if a nearby meaning from the lists fits the scene better, but keep the contrast.

---

# Dialogue requirements

The shared spoken context should:

* contain approximately 3–6 spoken turns;
* involve Speaker A and Speaker C;
* never contain a spoken turn from Speaker B;
* sound like natural everyday conversation;
* provide enough context to interpret B's eventual reaction;
* remain ambiguous enough that the correct continuation cannot be determined without B's vocalization;
* avoid explicitly describing B's emotional state;
* avoid announcing what B is about to do;
* avoid specialized knowledge whenever possible.

Speaker B may be mentioned by A or C only when natural, but avoid descriptions that reveal how B is likely to react.

For example, avoid:

A: B always laughs whenever I make a mistake.

because this makes `[laughter]` predictable.

---

# Scenario diversity

Use varied relationships and situations, including:

* friends
* coworkers
* classmates
* roommates
* siblings
* family members
* partners
* teammates
* casual acquaintances

Use varied conversational situations, including:

* telling a story
* admitting a mistake
* sharing unexpected news
* explaining something
* revealing an outcome
* making plans
* discussing work
* discussing school
* reacting to an embarrassing situation
* disagreement
* waiting
* joking
* solving a problem
* discussing something that just happened

Avoid overusing highly emotional or dramatic situations.

Avoid relying heavily on medical, violent, sexual, dangerous, or highly sensitive scenarios.

---

# Quality-control test

Before outputting each pair, internally verify all of the following:

1. Does Speaker B have **zero spoken turns** before the target vocalization?
2. Is B's non-speech vocalization B's **first contribution to the conversation**?
3. Is the shared spoken transcript exactly identical across the two versions?
4. Are the two vocalizations different?
5. Is the vocalization the only thing that changes before the final response?
6. Could both final responses reasonably follow the shared transcript if B's vocalization were hidden?
7. Does Vocalization 1 strongly favor Response 1?
8. Does Vocalization 2 strongly favor Response 2?
9. Would swapping Response 1 and Response 2 make the dialogue noticeably less appropriate?
10. Does the example require contextual interpretation rather than merely identifying the sound category?
11. Does neither A nor C explicitly predict B's reaction before it occurs?
12. Are the final responses natural utterances a real person could plausibly say?

If any condition fails, rewrite the example before outputting it.

---

# Output rules

Generate exactly ONE contrastive pair matching the user message.
Return JSON only.
Do not copy the shelf, filing-system, or client-email examples.
Invent a fresh situation.
shared_context is only A and C turns BEFORE B's vocalization. Never include Speaker B there.
version_1.vocalization and version_2.vocalization must be the exact tags, e.g. "[laughter]".
version_1.responder and version_2.responder must be the same speaker, A or C.
version_1.response and version_2.response are that speaker's final lines only, with no tags.
Do not mention the intended interpretation inside the dialogue.
""".strip()


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def formula_of(voc_id: str) -> str:
    return VOCALIZATIONS[voc_id]["formula"]


def contrast_list() -> list[tuple[str, str]]:
    return list(combinations(VOC_ORDER, 2))


def validate(payload: dict, voc1: str, voc2: str, pair_id: str) -> list[str]:
    problems: list[str] = []
    if payload.get("pair_id") != pair_id:
        problems.append(f"pair_id should be {pair_id}")

    context = payload.get("shared_context") or []
    if not isinstance(context, list) or not (3 <= len(context) <= 6):
        problems.append("shared_context must have 3–6 turns")
        return problems

    speakers = [turn.get("speaker") for turn in context]
    if any(speaker == "B" for speaker in speakers):
        problems.append("Speaker B must have zero spoken turns in shared_context")
    if any(speaker not in {"A", "C"} for speaker in speakers):
        problems.append("shared_context speakers must be A or C")
    if "A" not in speakers or "C" not in speakers:
        problems.append("shared_context must include both A and C")
    for index, turn in enumerate(context, start=1):
        text = turn.get("text") or ""
        if TAG_RE.search(text):
            problems.append(f"shared_context turn {index} has a tag")
        if not normalize(text):
            problems.append(f"shared_context turn {index} is empty")
        if PREDICT_B_RE.search(text):
            problems.append(f"shared_context turn {index} predicts B's reaction or names the setup")

    v1 = payload.get("version_1") or {}
    v2 = payload.get("version_2") or {}
    f1 = formula_of(voc1)
    f2 = formula_of(voc2)
    if normalize(v1.get("vocalization") or "") != f1:
        problems.append(f"version_1.vocalization must be {f1}")
    if normalize(v2.get("vocalization") or "") != f2:
        problems.append(f"version_2.vocalization must be {f2}")

    r1_speaker = v1.get("responder")
    r2_speaker = v2.get("responder")
    if r1_speaker not in {"A", "C"} or r2_speaker not in {"A", "C"}:
        problems.append("responders must be A or C")
    elif r1_speaker != r2_speaker:
        problems.append("both versions must use the same responder")

    r1 = normalize(v1.get("response") or "")
    r2 = normalize(v2.get("response") or "")
    if not r1 or not r2:
        problems.append("both versions need a response")
    if r1 == r2:
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
    if i1.lower() == i2.lower():
        problems.append("intended interpretations must differ")

    why = normalize(payload.get("why_the_vocalization_changes_the_response") or "")
    if len(why.split()) < 8:
        problems.append("why_the_vocalization_changes_the_response is too short")

    return problems


def user_prompt(
    voc1: str,
    voc2: str,
    pair_id: str,
    meaning1: str,
    meaning2: str,
    responder: str,
    used: list[str],
) -> str:
    lines = [
        "Generate exactly one contrastive pair.",
        "",
        f"Pair ID: {pair_id}",
        f"Version 1 vocalization: {formula_of(voc1)}",
        f"Version 1 suggested interpretation: {meaning1}",
        f"Version 2 vocalization: {formula_of(voc2)}",
        f"Version 2 suggested interpretation: {meaning2}",
        f"Final responder in BOTH versions: Speaker {responder}",
        "",
        "Speaker B must not appear in shared_context at all.",
        "Use those two vocalization tags exactly.",
        "Do not use any other vocalization in this pair.",
        "Shared context must work for BOTH interpretations.",
        "Both responses must be plausible from the text alone; the voc should pick between them.",
        "Do not restage the backwards-shelf, filing-system, or client-email examples.",
    ]
    if used:
        lines += ["", "Do not reuse these opening setups:"]
        lines += [f"- {text}" for text in used[-16:]]
    return "\n".join(lines)


def suggested_meanings(voc1: str, voc2: str, sample: int) -> tuple[str, str]:
    m1 = VOCALIZATIONS[voc1]["meanings"]
    m2 = VOCALIZATIONS[voc2]["meanings"]
    return m1[(sample - 1) % len(m1)], m2[(sample - 1) % len(m2)]


def call_model(client: OpenAI, prompt: str, model: str, effort: str) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.responses.create(
                model=model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                reasoning={"effort": effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "pairing_type_upgraded_pair",
                        "schema": OUTPUT_SCHEMA,
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
    meaning1: str,
    meaning2: str,
    responder: str,
    args: argparse.Namespace,
    used: list[str],
) -> dict:
    prompt = user_prompt(voc1, voc2, pair_id, meaning1, meaning2, responder, used)
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    served_by = args.model

    for attempt in range(1, 4):
        payload, usage, served_by = call_model(client, prompt, args.model, args.effort)
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        problems = validate(payload, voc1, voc2, pair_id)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            payload["contrast"] = f"{voc1}-{voc2}"
            return payload
        last_problems = problems
        prompt = (
            user_prompt(voc1, voc2, pair_id, meaning1, meaning2, responder, used)
            + "\n\nThe previous JSON failed these checks:\n- "
            + "\n- ".join(problems)
            + "\nReturn a corrected JSON object."
        )
        print(f"    check failed ({problems[0]}); regenerating {attempt}/2", flush=True)

    raise RuntimeError("still invalid after retries: " + "; ".join(last_problems))


def render_markdown(records: list[dict], model: str) -> str:
    lines = [
        "# Pairing type upgraded",
        "",
        f"writer: {model} · {len(records)} pair(s)",
        "",
        "A and C speak first. B's first turn is a voc-only reaction. Two vocs, two replies.",
        "",
    ]
    for record in records:
        v1 = record["version_1"]
        v2 = record["version_2"]
        lines += [
            f"### Pair {record['pair_id']}",
            "",
            f"Contrast: {record.get('contrast', '')}",
            "",
            "**Shared context**",
            "",
        ]
        for turn in record["shared_context"]:
            lines.append(f"{turn['speaker']}: {turn['text']}")
        lines += [
            "",
            "**Version 1**",
            "",
            f"Vocalization: {v1['vocalization']}",
            f"Intended interpretation: {v1['intended_interpretation']}",
            "",
            f"B: {v1['vocalization']}",
            f"{v1['responder']}: {v1['response']}",
            "",
            "**Version 2**",
            "",
            f"Vocalization: {v2['vocalization']}",
            f"Intended interpretation: {v2['intended_interpretation']}",
            "",
            f"B: {v2['vocalization']}",
            f"{v2['responder']}: {v2['response']}",
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
        f"{len(jobs)} pair(s)  ({len({(a, b) for a, b, _ in jobs})} contrast type(s) × {args.n})",
        flush=True,
    )

    if args.dry_run:
        used: list[str] = []
        for index, (voc1, voc2, sample) in enumerate(jobs):
            pair_id = f"{voc1}_{voc2}_{sample:03d}"
            m1, m2 = suggested_meanings(voc1, voc2, sample)
            responder = "A" if index % 2 == 0 else "C"
            print("\n" + "=" * 72)
            print(f"{pair_id} · {formula_of(voc1)} vs {formula_of(voc2)} · responder {responder}")
            print("=" * 72)
            print(user_prompt(voc1, voc2, pair_id, m1, m2, responder, used))
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")

    client = OpenAI(api_key=key)
    print(f"model: {args.model}", flush=True)
    records: list[dict] = []
    used: list[str] = []

    for index, (voc1, voc2, sample) in enumerate(jobs, start=1):
        pair_id = f"{voc1}_{voc2}_{sample:03d}"
        m1, m2 = suggested_meanings(voc1, voc2, sample)
        responder = "A" if index % 2 == 1 else "C"
        print(f"[{index}/{len(jobs)}] {pair_id} · {m1} vs {m2} · {responder}", flush=True)
        try:
            record = generate_one(
                client, voc1, voc2, pair_id, m1, m2, responder, args, used
            )
            records.append(record)
            opening = next(
                (turn["text"] for turn in record["shared_context"] if turn["speaker"] == "A"),
                "",
            )
            used.append(opening)
            print(
                f"    v1 {record['version_1']['responder']}: {record['version_1']['response']}",
                flush=True,
            )
            print(
                f"    v2 {record['version_2']['responder']}: {record['version_2']['response']}",
                flush=True,
            )
        except Exception as exc:
            records.append(
                {
                    "pair_id": pair_id,
                    "contrast": f"{voc1}-{voc2}",
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
        "n_per_contrast": args.n,
        "constraint": "B has zero spoken turns before the voc-only first contribution",
        "results": records,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    ok = [record for record in records if "shared_context" in record]
    md_path.write_text(render_markdown(ok, args.model), encoding="utf-8")
    failures = sum(1 for record in records if record.get("error"))
    print(
        f"\nwrote {args.out} and {md_path}" + (f" ({failures} failed)" if failures else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()

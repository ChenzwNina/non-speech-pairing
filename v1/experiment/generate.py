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
load_dotenv(HERE.parent.parent / ".env")
DEFAULT_OUT = HERE / "out" / "pairs.json"

MODEL = "gpt-5.6-terra"
EFFORT = "high"


def supports_reasoning_effort(model: str) -> bool:
    """gpt-4o and other non-reasoning chat models reject the `reasoning` param outright."""
    return not re.match(r"^gpt-(4|3\.5)", model)
MAX_OUTPUT_TOKENS = 4000
CONTEXT_TURNS = 4
SPEAKERS = 2
MAX_ATTEMPTS = 4
MAX_REPLY_WORDS = 28

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
            "strong unwillingness",
            "impatience",
            "irritated refusal",
        ],
    },
    "laughter": {
        "formula": "[laughter]",
        "meanings": [
            "amusement",
            "happiness",
            "delight",
        ],
    },
    "sigh": {
        "formula": "[sigh]",
        "meanings": [
            "tiredness",
            "exhaustion",
            "weary unwillingness to continue",
            "resignation",
            "feeling burdened",
        ],
    },
    "sob": {
        "formula": "[sob]",
        "meanings": [
            "deep sadness",
            "being emotionally overwhelmed",
            "being deeply moved",
        ],
    },
    "yawn": {
        "formula": "[yawn]",
        "meanings": [
            "tiredness",
            "boredom",
            "low energy",
            "reduced engagement",
        ],
    },
}

VOC_ORDER = ["gasp", "grunt", "laughter", "sigh", "sob", "yawn"]

# grunt, sigh, sob, and yawn are all negative or effortful — when two of them are paired,
# nothing forces the replies apart unless the prompt gives each its own uptake explicitly.
NEGATIVE_VOC = {"grunt", "sigh", "sob", "yawn"}

VOCALIZATION_BEHAVIOR = {
    "gasp": "The responder should behave as though B has reacted strongly to something unexpected or striking.",
    "grunt": "The responder should treat B as resisting, objecting, or being unwilling.",
    "laughter": "The responder should treat B as positively engaged or amused.",
    "sigh": "The responder should behave as though B is depleted, burdened, or reluctant.",
    "sob": "The responder should behave as though B is experiencing strong emotion.",
    "yawn": "The responder should adapt to B's reduced energy or attention.",
}

VOCALIZATION_INTERPERSONAL_MOVES = {
    "gasp": [
        "reassuring B",
        "calming B",
        "confirming that the surprising information is real",
        "clarifying that the situation is less serious than it sounds",
        "sharing B's excitement",
        "checking what specifically concerns B",
        "adding a detail that changes B's interpretation",
        "reacting to B's disbelief",
        "redirecting B before they overreact",
    ],
    "grunt": [
        "recognizing the resistance",
        "softening the demand",
        "challenging the objection",
        "negotiating",
        "offering an easier version",
        "giving B a choice",
        "asking what specifically B objects to",
    ],
    "laughter": [
        "join the humor",
        "acknowledge the absurdity",
        "tease",
        "laugh verbally with B",
        "play along",
        "treat B's laughter as permission to keep the joke going",
    ],
    "sigh": [
        "checking in",
        "reducing pressure",
        "recognizing that the task feels like a lot",
        "allowing a pause",
        "softening the request",
        "offering help",
    ],
    "sob": [
        "comfort",
        "reassurance",
        "emotional acknowledgment",
        "giving space",
        "reducing pressure",
        "offering presence",
    ],
    "yawn": [
        "recognize that B is fading",
        "lighten the interaction",
        "check whether B wants to stop",
        "move toward the important part",
        "joke about the hour",
        "reduce the amount left",
    ],
}

VOCALIZATION_SUBSTANTIVE_MOVES = {
    "gasp": [
        "explain",
        "clarify",
        "reassure",
        "give new information",
        "propose a practical next step",
        "check a concern",
        "share excitement",
        "joke about the surprising situation",
    ],
    "grunt": [
        "compromise",
        "reduce the burden",
        "make a case",
        "divide the work",
        "offer an alternative",
        "narrow the request",
        "postpone part of the task",
        "push back",
    ],
    "laughter": [
        "extend the joke",
        "preserve the funny moment",
        "make a playful suggestion",
        "lean into the absurdity",
        "continue the story",
        "share another amusing detail",
    ],
    "sigh": [
        "shorten the task",
        "postpone part of it",
        "divide the work",
        "change the plan",
        "offer a break",
        "ask whether B wants to continue",
        "take over part of the burden",
    ],
    "sob": [
        "pause the task",
        "remove an immediate obligation",
        "protect something emotionally significant",
        "offer practical support",
        "invite B to talk",
        "let B decide whether to continue",
    ],
    "yawn": [
        "shorten",
        "postpone",
        "stop",
        "summarize",
        "simplify",
        "continue only briefly",
        "move to the essential task",
    ],
}

VOCALIZATION_EXAMPLES = {
    "gasp": [
        "No worries, nothing broke—I already got it out.",
        "Yep, really. The entire closet has to be empty.",
        "Not quite as bad as it sounds; most of those boxes are probably empty.",
        "Don't panic yet—I haven't confirmed whether that number is right.",
        "Right? I couldn't believe they kept every single one.",
    ],
    "grunt": [
        "What if I move the freezer and you just clear the doorway?",
        "Is it doing this tonight you hate, or moving the whole closet?",
        "Okay, okay—we don't have to empty everything. They just need access to the wall.",
        "I'll take the heavy stuff if you handle the clothes.",
        "We can reschedule, but we'd be without a washer until Friday.",
    ],
    "laughter": [
        "Right? I'm leaving the dinosaur on the counter until the kids get home.",
        "And that's not even the best part—it was wearing the pink sock.",
        "Fine, now we have to take a picture before I throw it away.",
        "Exactly. Apparently our sink has been hosting tiny adventures.",
    ],
    "sigh": [
        "We can leave the closet until tomorrow; the laundry room is enough for tonight.",
        "How about I clear this side and you take ten minutes?",
        "We don't have to finish all of it before bed.",
        "Let's just make the path they need and stop there.",
    ],
    "sob": [
        "We don't have to sort those tonight. I'll put them somewhere safe.",
        "Hey, take your time. Nothing else needs doing right now.",
        "I'll turn it off. We can watch the rest whenever you want.",
        "I'll keep the letters together—we don't need to decide anything about them today.",
    ],
    "yawn": [
        "I'll give you the short version—the landlord said yes.",
        "Let's leave the rest until morning.",
        "One more box, then we're done.",
        "We can skip the whole backstory; the important part is that it's fixed.",
    ],
}

VOCALIZATION_BANNED_OPENERS = {
    "gasp": ["I know", "Yeah, I know", "I know, right?", "No worries", "Don't worry"],
    "grunt": ["I know it's a pain", "I hear you", "Fair enough"],
    "laughter": ["I know, right?", "Right?", "That's hilarious"],
    "sigh": ["You okay?", "Long day?", "That's a lot", "You're exhausted"],
    "sob": ["Come here", "Hey", "It's okay", "Don't cry"],
    "yawn": ["You're wiped out", "Let's call it a night", "You're tired"],
}

VOCALIZATION_EXTRA_NOTE = {
    "gasp": (
        "Choose whichever realization is natural for that particular scene. Never make "
        "the responder re-exclaim information they themselves just stated."
    ),
    "grunt": "Do NOT assume B has agreed. Do NOT automatically abandon the plan.",
    "laughter": "The response can share amusement implicitly.",
    "sigh": "The response may register weariness entirely through what A changes.",
    "sob": "",
    "yawn": "",
}

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
DEFAULT_THEME = "domestic"


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
    r"that (?:laugh|yawn|sigh|gasp|sob|grunt)|"
    r"your (?:laugh|yawn|sigh|gasp|sob|grunt)"
    r")\b"
)
# "you sound tired" is a lazy label-guess only if that's the whole reply; "you sound
# wiped out — leave the cabinet to me tonight" is a real pragmatic reply and must not
# be rejected just because it happens to open the same way.
BARE_SOUND_GUESS_RE = re.compile(r"^you (?:sound|seem) [a-z' ]{1,20}[.!]?$", re.I)
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


VOC_SCENE_NEEDS = {
    "gasp": "a gasp needs something surprising, alarming, impressive, or suddenly revealing",
    "grunt": "a grunt needs something B could resist, dislike, resent, or be unwilling to do",
    "laughter": "laughter needs something amusing, delightful, playful, or absurd",
    "sigh": "a sigh needs something tiring, burdensome, disappointing, or draining",
    "sob": "a sob needs genuine emotional weight",
    "yawn": "a yawn needs tiredness, lateness, boredom, repetition, or low engagement",
}


def vocalization_meanings_block() -> str:
    sections = []
    for voc in VOC_ORDER:
        meanings = ", ".join(VOCALIZATIONS[voc]["meanings"])
        interpersonal = "\n".join(f"* {m}" for m in VOCALIZATION_INTERPERSONAL_MOVES[voc])
        substantive = "\n".join(f"* {m}" for m in VOCALIZATION_SUBSTANTIVE_MOVES[voc])
        examples = "\n".join(f'"{ex}"' for ex in VOCALIZATION_EXAMPLES[voc])
        banned = "\n".join(f"* \"{op}\"" for op in VOCALIZATION_BANNED_OPENERS[voc])
        extra = VOCALIZATION_EXTRA_NOTE.get(voc, "")
        section = (
            f"### {voc.capitalize()}\n\n"
            f"Possible interpretations include: {meanings}.\n\n"
            f"{VOCALIZATION_BEHAVIOR[voc]}\n\n"
            f"Possible immediate interpersonal moves include:\n\n{interpersonal}\n\n"
            f"Possible substantive moves include:\n\n{substantive}\n\n"
            f"Examples:\n\n{examples}\n\n"
            f"Do NOT make every {voc} response begin with:\n\n{banned}"
        )
        if extra:
            section += f"\n\n{extra}"
        sections.append(section)
    return "\n\n".join(sections)


def system_prompt(context_turns: int, speakers: int, theme: str) -> str:
    total = context_turns + 2
    voc_turn = context_turns + 1
    reply_turn = context_turns + 2

    if speakers == 2:
        cast = (
            "Two-speaker version. Two people are present: Speaker A and Speaker B.\n\n"
            f"* Speaker A speaks all shared-context turns (1-{context_turns}).\n"
            f"* Speaker B says nothing until the vocalization at turn {voc_turn}.\n"
            "* Speaker B's first contribution is the non-speech vocalization.\n"
            f"* Speaker A replies immediately afterward, at turn {reply_turn}.\n\n"
            "Speaker A is therefore the same person who supplied the information B is "
            "reacting to. A is NOT a fresh listener."
        )
        context_rule = f"turns 1–{context_turns} are all Speaker A"
        responder_rule = f"Speaker A replies at turn {reply_turn} in both versions."
    else:
        cast = (
            "Three-speaker version. Three people are present: Speaker A, Speaker B, and "
            "Speaker C.\n\n"
            f"* A and C converse during the shared-context turns (1-{context_turns}), as "
            "specified.\n"
            f"* B says nothing until the vocalization at turn {voc_turn}.\n"
            "* B's first contribution is the non-speech vocalization.\n"
            "* The specified responder, A or C, replies immediately afterward, at turn "
            f"{reply_turn} — the same one in both versions."
        )
        context_rule = f"turns 1–{context_turns} alternate between Speaker A and Speaker C"
        responder_rule = (
            f"The same speaker (A or C) replies at turn {reply_turn} in both versions."
        )

    return f"""
You are generating dialogue data for a benchmark that tests whether an audio-language
model can use a **non-speech vocalization** to predict the appropriate next spoken response.

The target vocalizations are: gasp, grunt, laughter, sigh, sob, yawn.

The benchmark tests whether the vocalization changes the social and pragmatic
interpretation of the next turn. The goal is NOT to map each vocalization to one stock
phrase. The goal is to produce natural dialogue where the responder's next utterance is
shaped by what the other speaker's vocalization conveyed.

---

# Theme

Every scene must fit the requested theme: **{theme}** — {THEMES[theme]}.

Stay recognizably within that theme. Use ordinary situations and ordinary conversational
language. Avoid requiring specialized knowledge. Avoid repeatedly using unusually dramatic,
medical, violent, sexual, or otherwise sensitive situations. Vary the kinds of situations
within the theme.

---

# Cast

{cast}

Speaker B has no lexical speech anywhere in the item. Do not establish B's voice through
earlier dialogue.

Do not narrate B's presence or emotional state with lines such as:

* "B has been listening quietly."
* "She looks exhausted."
* "He seems upset."
* "They are clearly annoyed."

B's state should be inferred from the shared context plus the vocalization.

---

# Turn structure

Each version contains exactly **{total} turns**:

1. the shared spoken context (turns 1–{context_turns})
2. Speaker B's vocalization alone (turn {voc_turn})
3. the selected spoken reply (turn {total})

{context_rule}. {responder_rule} The shared-context turns must be **word-for-word
identical** across the two versions. The only difference before the final response is
which vocalization B produces. The vocalization must make a different next response
appropriate.

Speaker B's vocalization turn contains only the exact plain tag, for example `[gasp]`,
`[grunt]`, `[laughter]`, `[sigh]`, `[sob]`, `[yawn]`. Do not add lexical speech or
adjectives.

Correct: `[gasp]`
Incorrect: `Wow. [gasp]` · `[shocked gasp]` · `[gasp] What?`

---

# The final shared turn is the trigger

The final shared-context turn (turn {context_turns}) is the thing B reacts to. It must
contain the immediate trigger: a reveal, an admission, a surprising number, a discovery, a
punchline, a problem, a result, a request, a demand, a decision, emotionally meaningful
information, or some other development that naturally invites a reaction. The vocalization
follows immediately after it. Earlier turns are setup.

Do not reveal the main information earlier and then use turn {context_turns} for logistics,
scheduling, or summary. Turn {context_turns} must NOT be:

* a neutral restatement
* an aside
* routine logistics following the reveal
* a summary
* a question the responder then answers

Ask: would a listener naturally react immediately after this exact line? If the natural
reaction point happened earlier, restructure the scene.

`trigger_note` briefly states what turn {context_turns} puts on the table for B to react to.

---

# Both vocalizations must fit the identical context

Both candidate vocalizations must be plausible reactions to the exact same shared context.
The text should leave both interpretations open enough that the vocalization provides
meaningful additional information. Do not force a vocalization into an unsuitable scene:

* {VOC_SCENE_NEEDS['gasp']}
* {VOC_SCENE_NEEDS['grunt']}
* {VOC_SCENE_NEEDS['laughter']}
* {VOC_SCENE_NEEDS['sigh']}
* {VOC_SCENE_NEEDS['sob']}
* {VOC_SCENE_NEEDS['yawn']}

Use whichever allowed interpretation fits naturally.

---

# Critical speaker-role rule

The vocalization belongs to Speaker B, not to the responder. The responder already knows
everything they themselves said in the shared context. Therefore, the response must not
sound as though the responder is hearing their own information for the first time.

For example:

    A: "There are twenty-seven boxes downstairs, and they all have to be out by Sunday."
    B: [gasp]

Bad A response: "Wait, twenty-seven boxes?!" — A already knew and stated that fact.

A's response should instead make sense as something said after hearing B react:

    "Don't panic yet—I want to check whether that count includes the empty boxes."
    "They're giving us carts, at least, so we don't have to carry everything by hand."
    "Apparently half of those are old moving boxes, so it may not be as bad as it sounds."

The responder reacts to B's reaction, not by reproducing it.

---

# Immediate interpersonal uptake

The response should sound natural at the exact moment after hearing B's vocalization. A
good response often contains two layers:

1. **Immediate interpersonal uptake** — A responds to how B seems to be reacting.
2. **Substantive continuation** — A then says or does something relevant to the underlying
   situation.

These two layers can appear in one sentence. For example:

    A: "A tiny plastic dinosaur was wedged in the pipe, wearing one of the kid's doll socks."
    B: [gasp]

Less natural: "Nothing's damaged—I pulled it out, and the sink is draining normally again."
More natural: "No worries, nothing's damaged—I pulled it out, and the sink is draining
normally again."
Also natural: "It's okay, I got it out. Everything's working again."
Also natural: "Nothing broke, thankfully. It came right out."

The first part reacts to B; the rest addresses the situation. However, do not force the
same affective bridge every time. Immediate interpersonal uptake can take many forms:
reassurance, concern, acknowledgment, softening, humor, confirmation, clarification,
calming, sympathy, negotiation, a targeted question, or a change in tone or plan.

Examples of possible short bridges include "No worries,", "It's okay,", "Nothing broke,",
"Yeah,", "Seriously,", "Fair,", "Okay, okay,", "Right?", "Exactly.", "Hey,", "You good?",
"Not as bad as it sounds—", "Don't worry—". These are examples only. They are NOT
mandatory templates.

---

# Vocalization-dependence test

Imagine deleting B's vocalization entirely and replacing it with silence. Then ask: would
the responder's line sound equally natural and equally motivated? If yes, the reply may be
responding only to the situation rather than to B.

The vocalization should leave a detectable trace in at least one of: wording, stance,
emotional framing, urgency, politeness, reassurance, question choice, practical action,
willingness to continue, degree of pressure, humor, or conversational direction.

The response does NOT need to explicitly name B's emotion. But B's vocalization should
have a visible consequence for what the responder says next.

---

# Pragmatic uptake, not emotion labeling

Do not merely identify the sound.

Bad: "You're laughing." "You yawned." "Are you crying?" "Why did you gasp?" "You're
annoyed." — these mostly label the cue.

Instead, write a reply that demonstrates how the responder interpreted it, e.g. "Fine, I'm
taking a picture before I clean that up." "Let's leave the last shelf for tomorrow." "What
if I carry the heavy end?" "Nothing's broken, I promise." "We don't have to open the
letters tonight."

A listener should be able to work backward from the reply and infer something about what B
conveyed.

---

# Vocalization meanings, moves, and examples

{vocalization_meanings_block()}

---

# Surface-form diversity

Do not use a fixed verbal formula for any vocalization. Across generated items, vary
whether the response begins with reassurance, a question, a statement, new information, a
suggestion, a joke, a compromise, an instruction, an emotional acknowledgment, an
explanation, or a clarification.

Vary whether the response is explicit about B's reaction, implicit about B's reaction,
emotionally focused, practically focused, information-seeking, reassuring, action-oriented,
playful, tentative, or firm.

Phrases appearing in examples are illustrations only. They are not preferred templates.
Avoid repeatedly defaulting to: "I know...", "Yeah, I know...", "I know, right?", "I hear
you...", "No worries...", "It's okay...", "You okay?", "You're wiped out.", "Come here.",
"That's a lot.", "Fair enough." These phrases are allowed when they are genuinely natural,
but they should not become markers mechanically associated with a vocalization.

---

# The response should be the next conversational move

Do not always jump from the vocalization to a fully resolved final decision. The benchmark
predicts the next utterance, not the eventual outcome of the whole interaction. A response
may instead ask, reassure, negotiate, comfort, clarify, joke, hesitate, propose, soften,
push back, postpone, add information, or offer a choice.

For example, after a resistant grunt, all of these are natural:

    "Is it moving the freezer you're objecting to, or doing it tonight?"
    "What if I do the heavy stuff and you just clear the shelves?"
    "We only need enough room for the technician to reach the valve."

All engage the resistance differently. Do not force every response to solve the entire
problem.

---

# Contrast requirement

The two replies must be meaningfully different because of the vocalization. Swapping them
should make both dialogues clearly worse. However, they do NOT need to lead to opposite
final decisions — they may instead differ in immediate interpersonal response,
conversational move, stance, urgency, question, offer, amount of pressure, emotional
support, practical direction, willingness to continue, humor, or reassurance. For example:

    [gasp]  -> "Don't worry, they only need one side of the closet cleared."
    [grunt] -> "What if I clear the closet and you handle the laundry-room shelves?"

The distinction is not simply emotional tone — the two responses are doing different
conversational work. Avoid arbitrary two-option choices where either vocalization could
justify either option.

---

# Swap test

Before output, mentally swap the replies. Ask: would reply 1 sound clearly worse after
vocalization 2? Would reply 2 sound clearly worse after vocalization 1? If not, strengthen
the distinction by changing the social or pragmatic move, not merely by adding different
emotional adjectives.

Bad (same underlying response):

    [laughter] -> "That's funny. I'll clean it."
    [sigh]     -> "That's annoying. I'll clean it."

Better:

    [laughter] -> "Wait, let me get a picture before we clean it."
    [sigh]     -> "Leave it for tonight; I'll deal with it tomorrow."

---

# Undecidable from text alone

If B's vocalization is hidden, both responses should remain plausible continuations of the
shared context. The shared text must not already determine the answer. The vocalization
must carry meaningful information. Do not predict B's reaction, describe B's emotional
state beforehand, say B always reacts a particular way, or make one response obviously
correct from the text alone. The benchmark should require the audio cue.

---

# Negative and effortful vocalizations

Grunt, sigh, sob, and yawn usually carry some negative, resistant, depleted, or effortful
information. Do not blatantly contradict that information — do not treat a reluctant grunt
as enthusiastic consent, an exhausted sigh as eagerness for additional work, a sob as
casual amusement, or a yawn as high excitement.

However, explicit verbal acknowledgment is not mandatory. Behavioral adaptation counts:

    after [grunt]: "I'll take the heavy end."
    after [sigh]:  "We can leave the rest until tomorrow."
    after [sob]:   "I'll put the letters somewhere safe."
    after [yawn]:  "I'll give you the short version."

Each response clearly registers B's state without labeling it.

---

# Naturalness test

The final response should sound like something a person might actually say immediately
after hearing the vocalization. Avoid responses that sound like benchmark annotations,
summaries of B's mental state, perfectly optimized problem-solving, exposition written for
the reader rather than speech to B, formal prose, or canned counseling language.

Prefer ordinary spoken language. Contractions are natural. Short fragments are acceptable
when conversationally appropriate. The response may contain one sentence or two short
connected sentences, no more than {MAX_REPLY_WORDS} words.

---

# Interpersonal-uptake self-test

For each response, ask: what in this line is different because B just produced this
particular vocalization? There must be a clear answer. If the answer is only "the factual
content is compatible with the emotion," that is too weak. Look for a change in opening,
framing, reassurance, urgency, softness, humor, question choice, willingness to push,
amount of information given, immediate action, or emotional support. The response should
feel occasioned by B's reaction.

---

# Self-check before output

1. B has zero spoken turns before the vocalization.
2. B's vocalization is B's first contribution.
3. B's turn contains only the exact vocalization tag.
4. The final shared-context turn is the actual trigger.
5. The trigger is a statement, not a question the responder later answers.
6. Both vocalizations are plausible reactions to the identical context.
7. Both intended interpretations naturally fit the scene.
8. With the vocalization hidden, both final responses are plausible continuations.
9. Each vocalization clearly favors its corresponding response.
10. Swapping the responses makes both dialogues noticeably worse.
11. The responses make meaningfully different social or pragmatic moves.
12. The responder sounds like someone who already knew what they said in the shared context.
13. The responder reacts to B rather than reproducing B's reaction.
14. Neither response merely labels the vocalization or emotion.
15. Negative or effortful vocalizations are not treated as enthusiasm or consent.
16. Each response contains sufficient interpersonal uptake of B's reaction.
17. The response would not be equally motivated if B's vocalization were simply deleted.
18. Explicit acknowledgment is optional; appropriate behavioral or conversational
    adaptation counts.
19. Neither response uses a stock acknowledgment simply to prove that the sound was noticed.
20. The wording is natural and specific to the scene.
21. The two responses do not merely use the same syntactic template with different
    emotional words.
22. The item tests interpretation of the vocalization rather than memorization of a fixed
    response phrase.

Rewrite the item if any important check fails.

---

# Output rules

Generate exactly ONE contrastive pair matching the requested vocalizations. Return JSON only.

`shared_context`: contains exactly {context_turns} turns; never contains Speaker B; is
identical in both versions; ends with the trigger.

`version_1.vocalization` and `version_2.vocalization`: are the exact requested plain tags.

`intended_interpretation`: must be selected from the allowed meanings for that
vocalization; must fit the shared context naturally; the two must differ.

`responder`: must be the specified speaker; must be the same in both versions.

`response`: is one natural spoken reply; contains no audio tags; contains no narration;
does not name the intended interpretation; does not explain why the response is
appropriate; should normally be concise; should show interpersonal and pragmatic uptake of
B's vocalization.

`scenario`: is a short neutral description of the situation.

`trigger_note`: briefly states what the final shared-context turn puts on the table for B
to react to.

`why_the_vocalization_changes_the_response`: explains how the two vocalizations produce
different interpersonal or pragmatic uptake; describes what each response does differently;
should not merely say that one vocalization is positive and the other negative.

Do not mention the intended interpretation inside the dialogue.
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
    (
        "reply_matches_vocalization_valence",
        "a negative or effortful vocalization (grunt/sigh/sob/yawn) is answered as agreement, "
        "brushed past, or followed by added burden instead of being acknowledged",
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

You are told only the bare vocalization tag (e.g. "[grunt]") — not which specific meaning the
writer intended. Judge everything from what a listener would infer from the tag itself, in
context. That is deliberate: the audio a real listener hears never carries the writer's gloss
either, so a mapping that only works once you are told the intended meaning is not valid.

Judge these properties independently and return JSON only. Judge what is written, not what was
intended; do not be charitable.

1. `trigger_is_last_shared_turn` — is the FINAL turn of the spoken context the thing B is
   reacting to? False if the notable information landed earlier and the final turn is
   logistics, scheduling, a summary, an aside, or a question that the reply then answers.
   A listener should want to react right after the final turn.

2. `both_vocalizations_natural_here` — given only the spoken context, would a listener
   plausibly produce each of the two vocalizations? False if the scene gives a gasp nothing
   surprising, a sob no emotional weight, a yawn no tedium, and so on.

3. `undecidable_from_text_alone` — with the vocalization hidden, are both replies genuinely
   plausible? False if the context already points at one.

4. `replies_commit_to_different_actions` — do the replies commit to materially different
   actions, decisions, or directions? False if both settle on the same course and differ only
   in tone, politeness, or an attitude preface.

5. `voc1_favors_reply1` — hearing only the bare vocalization 1 tag, with no gloss, is reply 1
   clearly the better of the two? Be strict: the link must be specific to what that sound
   itself conveys, not merely a reading that becomes plausible once a favorable label is
   attached to it.

6. `voc2_favors_reply2` — the same for vocalization 2 and reply 2.

7. `swapping_replies_is_clearly_worse` — if reply 2 followed vocalization 1 and reply 1
   followed vocalization 2, would both dialogues be clearly worse? False if the swap reads
   about as well. Watch for items built on an arbitrary two-option choice (before or after,
   this or that) where either vocalization could motivate either option.

8. `reply_matches_vocalization_valence` — grunt, sigh, sob, and yawn are negative or
   effortful sounds. False if the reply to one of these treats it as agreement, enthusiasm,
   or consent; brushes past it without acknowledgment; or adds further burden, demands, or a
   new commitment right after it instead of registering the reaction first. This holds even
   if a "reluctant agreement"-style meaning was intended — the reply still has to show the
   reluctance, not just the agreement.

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
        f"Vocalization 1: {v1['vocalization']}",
        f"Reply 1 — {v1['responder']}: {v1['response']}",
        "",
        f"Vocalization 2: {v2['vocalization']}",
        f"Reply 2 — {v2['responder']}: {v2['response']}",
    ]
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    kwargs = dict(
        model=model,
        instructions=JUDGE_SYSTEM,
        input="\n".join(lines),
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
    if (
        NAME_VOC_RE.search(r1)
        or NAME_VOC_RE.search(r2)
        or BARE_SOUND_GUESS_RE.match(r1)
        or BARE_SOUND_GUESS_RE.match(r2)
    ):
        problems.append("response names the vocalization instead of interpreting it")
    if len(r1.split()) > MAX_REPLY_WORDS or len(r2.split()) > MAX_REPLY_WORDS:
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
    theme: str,
    used_scenarios: list[str],
    used_meanings: list[str],
) -> str:
    cast = "Speakers A and B only" if speakers == 2 else "Speakers A, B and C"
    lines = [
        "Generate exactly one contrastive pair.",
        "",
        f"Pair ID: {pair_id}",
        f"Cast: {cast}",
        f"Theme: {theme} — {THEMES[theme]}",
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
    if voc1 in NEGATIVE_VOC and voc2 in NEGATIVE_VOC:
        lines += [
            "",
            f"{formula_of(voc1)} and {formula_of(voc2)} are BOTH negative/effortful sounds in",
            "this pair — they are not interchangeable. Pick a genuinely different response",
            f"move for each (see the move lists for {voc1} and {voc2} above), so the two",
            "replies differ in what they DO, not just in tone. Neither may read as agreement",
            "or dismiss the reaction. Make sure swapping them would sound wrong for both.",
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
    theme: str,
) -> tuple[dict, dict, str]:
    effort = {"xhigh": "high", "max": "high"}.get(effort, effort)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=model,
                instructions=system_prompt(context_turns, speakers, theme),
                input=prompt,
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


def print_draft(payload: dict, context_turns: int) -> None:
    for index, turn in enumerate(payload.get("shared_context") or [], start=1):
        marker = "  <- trigger" if index == context_turns else ""
        print(f"      {index}. {turn.get('speaker')}: {turn.get('text')}{marker}", flush=True)
    for label, key in (("v1", "version_1"), ("v2", "version_2")):
        version = payload.get(key) or {}
        print(
            f"      {label} {version.get('vocalization')} "
            f"({version.get('intended_interpretation')}) -> "
            f"{version.get('responder')}: {version.get('response')}",
            flush=True,
        )


def print_verdict(problems: list[str], verdict: dict | None) -> None:
    print(f"      failed checks: {problems}", flush=True)
    if verdict is not None:
        print(f"      judge verdict: {verdict}", flush=True)


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
    theme = args.theme
    verbose = getattr(args, "verbose", False)

    def build(extra: str = "") -> str:
        base = user_prompt(
            voc1, voc2, pair_id, responder, turns, speakers, theme, used_scenarios, used_meanings
        )
        return base + extra

    prompt = build()
    totals = {"input_tokens": 0, "output_tokens": 0}
    last_problems: list[str] = []
    last_draft: dict | None = None
    last_verdict: dict | None = None
    served_by = args.model

    for attempt in range(1, MAX_ATTEMPTS + 1):
        payload, usage, served_by = call_model(
            client, prompt, args.model, args.effort, turns, speakers, theme
        )
        totals["input_tokens"] += usage["input_tokens"]
        totals["output_tokens"] += usage["output_tokens"]
        last_draft = payload
        problems = validate(payload, voc1, voc2, pair_id, turns, speakers)
        verdict: dict | None = None
        if not problems and not args.no_judge:
            verdict, judge_usage = judge_pair(client, payload, args.model, args.effort)
            totals["input_tokens"] += judge_usage["input_tokens"]
            totals["output_tokens"] += judge_usage["output_tokens"]
            problems = judge_problems(verdict)
        last_verdict = verdict
        if verbose:
            print(f"    -- attempt {attempt}/{MAX_ATTEMPTS} draft --", flush=True)
            print_draft(payload, turns)
        if not problems:
            payload["usage"] = totals
            payload["served_by"] = served_by
            payload["attempts"] = attempt
            payload["contrast"] = f"{voc1}-{voc2}"
            payload["context_turns"] = turns
            payload["total_turns"] = turns + 2
            payload["speakers"] = speakers
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
            + "\nRebuild the item from scratch if the trigger or the scene is the problem."
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
        "--theme",
        default=DEFAULT_THEME,
        choices=list(THEMES),
        help=f"scene theme (default: {DEFAULT_THEME})",
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print every draft transcript and full judge verdict, accepted or rejected",
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
        f"{turns + 2} turns per version · cast {cast} · theme {args.theme}",
        flush=True,
    )

    if args.dry_run:
        for index, (voc1, voc2, sample) in enumerate(jobs):
            pair_id = f"{args.theme}_{voc1}_{voc2}_{sample:03d}"
            responder = "A" if args.speakers == 2 else ("A" if index % 2 == 0 else "C")
            print("\n" + "=" * 72)
            print(f"{pair_id} · {formula_of(voc1)} vs {formula_of(voc2)} · responder {responder}")
            print("=" * 72)
            print(
                user_prompt(
                    voc1, voc2, pair_id, responder, turns, args.speakers, args.theme, [], []
                )
            )
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
        pair_id = f"{args.theme}_{voc1}_{voc2}_{sample:03d}"
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
        except GenerationFailed as exc:
            record = {
                "pair_id": pair_id,
                "contrast": contrast_id,
                "error": f"{type(exc).__name__}: {exc}",
                "last_problems": exc.problems,
            }
            if exc.draft is not None:
                record["last_draft"] = exc.draft
            if exc.judge is not None:
                record["last_judge"] = exc.judge
            records.append(record)
            print(f"    failed: {exc}", flush=True)
            if exc.draft is not None:
                print("    last draft:", flush=True)
                print_draft(exc.draft, args.context_turns)
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
        "theme": args.theme,
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

"""One line of context, the model proposes, and the user answers with a sound.

Every other experiment here hands the model a conversation someone else wrote. This one does
not. The model is told in a single line what it is helping the user with, it proposes
something concrete of its own, and the user's reply ends in a real non-speech recording —
a yawn, a sigh, a gasp, or laughter. Then it has to take another turn.

The point of letting the model write its own proposal is that nothing can be tuned to the
sound. In `make_response/` a writer model built a proposal that all three reactions would fit,
which is a fair test of reading the sound but a slightly staged one. Here the yawn lands on
whatever plan the model actually came up with, and the only question is whether its next turn
changes because of it.

Four shapes of user turn, chosen with --line:

    none        the sound alone, no words at all (the default; the original run)
    attitude    one short sentence carrying the same attitude, then the sound
    neutral     one short sentence whose words fit any attitude, then the sound
    mismatch    one plainly positive sentence, then a negative sound

`none` asks whether the model can read a bare sound. `attitude` is the easier condition where
words and sound agree, and shows what the model does when it cannot miss the state. `neutral`
is the diagnostic one: the words are there but carry no attitude, so any adaptation still has
to come from the sound.

`voc_first` is the same conflict with the order reversed: the turn opens with a weary
"[sigh] ughh" and *then* says something plainly positive. Two differences from `mismatch`.
The negative signal now arrives first, so it is a frame the positive words have to survive
rather than an afterthought. And because "ughh" is a word, the sound cannot be a stranger's
recording — it is synthesized in the speaker's own voice, in its own generation, and the
positive sentence is synthesized separately so its delivery stays clean instead of inheriting
the sigh's prosody. That is the one place in this folder where the vocalization is not real
audio, and the reason is that it is glued to speech from the same mouth.

`lexical_first` is that same turn with the sigh replaced by the spoken words "I don't want
to do this, but..." — the reluctance moved from the audio channel to the lexical one, with
everything else held still.

`tease` / `tease_plain` invert the conflict: a genuinely warm laugh in front of a sentence
that, written down, is a put-down about the assistant's plan. With the laugh it is ribbing
between people who get along; without it the same words are just an insult, and the two
conditions share one synthesized take of the sentence so nothing but the laugh differs. The
tease is written from the task alone, never from the live proposal, which is what lets the
two runs reuse the same take. A model reading the laugh jokes back and carries on; a model
reading only the words apologizes or defends itself — kind, and socially wrong.

`mismatch` puts the two channels in conflict — "sounds great, let's do it" followed by a
grudging grunt, the tone people use when they are agreeing but not happy about it. Nothing in
the words licenses backing off, so any accommodation in the reply can only have come from the
sound, and a reply that simply proceeds has taken the words at face value. The neutral run is
what suggested this: its lines drifted agreeable rather than blank, and the sound stopped
mattering — worth testing head-on rather than as a leak.

The line is written mid-session, after the proposal exists, so it answers the plan the model
actually gave rather than a plan we guessed it would give. It is synthesized in a voice picked
to match the pitch of the recording it precedes, so the sentence and the sound plausibly come
from one person.

Each task is written so that all four vocalizations would be plausible answers to a sensible
proposal (something a bit ambitious, a bit tedious, a bit drastic). The seeded pairing below
is the default run; `--voc` reruns any task against a different sound as a counterfactual.

Usage:
    python assistant_proposal/run.py --dry-run
    python assistant_proposal/run.py
    python assistant_proposal/run.py --line attitude
    python assistant_proposal/run.py --only inbox --voc gasp --line neutral
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "logo_sketch"))
load_dotenv(REPO / ".env")

import eval_realtime as ev  # noqa: E402  — realtime session plumbing
from make_audio import build, timestamp  # noqa: E402  — ffmpeg concat with silences

OUT_DIR = HERE / "out"
TURN_DIR = OUT_DIR / "audio_turns"       # per-turn renders; gitignored like the other folders
TEASE_LINES = OUT_DIR / "tease_lines.json"   # one wording per task, shared by both conditions
CONV_DIR = OUT_DIR / "audio"             # the sewn conversation
SCRIPT_DIR = OUT_DIR / "transcripts"
VOC_ROOT = REPO / "audio_non-speech"

MODEL = "gpt-realtime-2.1"
VOICE = "marin"
SESSION_TIMEOUT = 180.0
MAX_OUTPUT_TOKENS = 900

VOCS = ["yawn", "sigh", "gasp", "laughter", "grunt"]
NEGATIVE_VOCS = ["sigh", "yawn", "grunt"]   # what --line mismatch contradicts with
MIN_CLIP_SECONDS = 0.3
MAX_CLIP_SECONDS = 10.0

GAP_BEFORE_VOC = 0.45                    # end of the proposal to the start of the user's turn
GAP_AFTER_VOC = 0.45                     # the sound to the model's reply
LINE_VOC_GAP = 0.25                      # the user's sentence to their own sound

# suffix on ids and output files, so the three conditions never overwrite each other
LINE_MODES = {"none": "", "attitude": "_line", "neutral": "_neutral",
              "mismatch": "_mismatch", "voc_first": "_vocfirst",
              "lexical_first": "_words",
              "tease": "_tease", "tease_plain": "_teaseplain"}

# The inverse conflict: a warm laugh in front of words that are, on the page, a put-down.
# `tease` plays the laugh, `tease_plain` plays the identical take of the same sentence with
# the laugh removed — the words alone, where the same line reads as an insult.
TEASE_MODES = ("tease", "tease_plain")

# Modes where the human turn opens with something reluctant and then commits anyway. They
# differ only in which channel the reluctance arrives on, which is the whole comparison.
FRONT_LOADED = ("voc_first", "lexical_first")

# The user's only scripted words, identical across tasks, so the task line and the sound are
# the only things that vary. It asks for a proposal without saying what kind.
OPENER = "Okay — what do you think we should do?"

# The role, minus anything that would prime the test. The model is not told that the user
# will answer without words, not told that a sound is coming, and not told to avoid naming
# it: an assistant that says "you sound wiped" is giving a real answer, not cheating.
INSTRUCTIONS = (
    "You are a voice assistant in a live spoken conversation with the user.\n\n"
    "{context}\n\n"
    "Talk the way people talk out loud: one or two sentences a turn, no lists, no headings, "
    "no stage directions. Say only your next line."
)

# Asked only after the model has already replied, so it cannot shape the reply. The count is
# the point: the spoken line is TTS and the sound is a stranger's recording, so if the model
# hears two people, its indifference to the sound is an attribution failure rather than a
# reading failure. The wording does not hint that more than one is possible.
SPEAKER_PROBE = (
    "Different question, about the recording itself rather than the conversation. Not "
    "counting your own voice, how many different people did you hear? Give the number, then "
    "one short sentence on what each of them did."
)

# id, the one line the model gets, the sound seeded for the default run, and the negative
# sound seeded for --line mismatch (laughter and gasp are not negative, so those two tasks
# take a grunt instead; the other three keep the sound they already ran with).
# Each line leaves room for a proposal that is ambitious enough to laugh at, dull enough to
# yawn at, heavy enough to sigh at, and big enough to gasp at.
TASKS: list[dict] = [
    {
        "id": "backyard",
        "voc_tease": "laughter",
        "voc_tease_plain": "nolaugh",
        "voc_lexical_first": "lexical",
        "voc_voc_first": "sigh",
        "voc_mismatch": "grunt",   # laughter is not a negative sound, so this task swaps for the run
        "voc": "laughter",
        "context": "You are helping the user get their overgrown backyard usable before "
                   "twenty relatives arrive for a barbecue next Saturday.",
    },
    {
        "id": "budget",
        "voc_tease": "laughter",
        "voc_tease_plain": "nolaugh",
        "voc_lexical_first": "lexical",
        "voc_voc_first": "sigh",
        "voc_mismatch": "sigh",   # same sound as the other conditions
        "voc": "sigh",
        "context": "You are helping the user find eight hundred dollars a month in their "
                   "budget after a surprise tax bill.",
    },
    {
        "id": "birthday",
        "voc_tease": "laughter",
        "voc_tease_plain": "nolaugh",
        "voc_lexical_first": "lexical",
        "voc_voc_first": "sigh",
        "voc_mismatch": "grunt",   # gasp is not a negative sound, so this task swaps for the run
        "voc": "gasp",
        "context": "You are helping the user plan a surprise for their partner's fortieth "
                   "birthday, three weeks from now.",
    },
    {
        "id": "inbox",
        "voc_tease": "laughter",
        "voc_tease_plain": "nolaugh",
        "voc_lexical_first": "lexical",
        "voc_voc_first": "sigh",
        "voc_mismatch": "yawn",   # same sound as the other conditions
        "voc": "yawn",
        "context": "You are helping the user clear three hundred work emails that piled up "
                   "over two weeks of leave, before Monday morning.",
    },
    {
        "id": "neighbor",
        "voc_tease": "laughter",
        "voc_tease_plain": "nolaugh",
        "voc_lexical_first": "lexical",
        "voc_voc_first": "sigh",
        "voc_mismatch": "sigh",   # same sound as the other conditions
        "voc": "sigh",
        "context": "You are helping the user deal with the upstairs neighbor who practices "
                   "drums late at night.",
    },
]

# ---------------------------------------------------------------------------------------
# the spoken line that precedes the sound (--line attitude / neutral)
# ---------------------------------------------------------------------------------------

WRITER_MODEL = "gpt-5.6-terra"
WRITER_EFFORT = "low"                    # a twelve-word line needs no thinking, and the
WRITER_MAX_TOKENS = 2000                 # realtime session is sitting open while it runs
MAX_LINE_WORDS = 12
MAX_LINE_WORDS_ASSENT = 8                # "Okay, let's do it." is four
LINE_ATTEMPTS = 3

TTS_MODEL = "eleven_v3"
TTS_FORMAT = "mp3_44100_128"
VOICE_POOL = {"male": "s3TPKV1kjDlVtZbl4Ksh", "female": "aKw9UnnjRq5scbeeGI7Z"}
# Gasps and laughs are voiced higher than ordinary speech, so the textbook 165 Hz
# male/female speech boundary calls almost every clip female. Each clip is compared
# against the median of its own vocalization folder instead.

# The line may not do the sound's job for it by naming it.
SOUND_WORDS = re.compile(
    r"(?i)\b(laugh\w*|sigh\w*|gasp\w*|yawn\w*|groan\w*|grunt\w*|chuckle\w*|breath\w*|"
    r"sound|noise)\b"
)

# A "sounds good, but..." line is not the condition being tested: the words have to
# endorse the plan outright, so the only objection in the turn is the sound.
HEDGE_WORDS = re.compile(r"(?i)\b(but|though|however|although|unless|worried|nervous)\b")

# Plain assent, not a rave. Without this the writer reaches for "I love that, it's going to
# be amazing", which nobody says to a to-do list.
GUSH_WORDS = re.compile(
    r"(?i)\b(love|amazing|perfect|excited|thrilled|fantastic|wonderful|awesome|incredible|"
    r"brilliant)\b|!"
)

# What --line voc_first puts in front of the positive sentence. The bracketed part is an
# eleven_v3 delivery tag and renders as sound; ASR hears "Ah" / "Ugh", never the word.
VOC_FIRST_TOKEN = {"sigh": "[sigh] ughh", "yawn": "[yawn] hhaah", "grunt": "[grunt] mmh"}

# --line lexical_first is the control for voc_first: identical turn shape, identical assent,
# but the reluctance is said in words instead of made as a sound. If the model backs off here
# and not for the sigh, the gap is not pragmatic reasoning — it is the channel.
LEXICAL_FIRST_TOKEN = "I don't want to do this, but..."

LAUGH_LINE_GAP = 0.35                    # a laugh runs into the tease; it is not a beat

# A bare "[laughs]" comes out as a dry "heh". Giving the voice written laughter to perform,
# and loosening stability so it is allowed to vary, is what produces a warm one — the same
# recipe as missed_train_sketch.
LAUGH_TAG = "[laughs warmly] hahaha"   # the written "hahaha" is what the voice performs;
                                       # the tag alone only sets the manner. "ahahaha—" came
                                       # out breathier, this reads as a plain happy laugh.
LAUGH_STABILITY = 0.3
MAX_LINE_WORDS_TEASE = 8                 # elaborated insults read as sincere; banter is short

# Softeners do the laugh's job in text. If the line can say "haha, just kidding", the words
# are no longer hostile on the page and the control condition has nothing to test.
WINK_WORDS = re.compile(
    r"(?i)\b(haha+|hehe+|lol|jk|kidding|joking|teasing|no offense|kidding aside)\b|:\)|😄|😉"
)

# The first pass at this condition failed because the lines were verbally witty — "that's
# adorable", "you solved my budget the way a raccoon solves a safe". Sarcasm and simile are
# unmistakable jokes on the page, so the no-laugh control read as banter too and the pair
# separated nothing. A harsh line has to be flat: no comic praise, no figure of speech.
# A tease the assistant could sensibly concede is not a tease, it is feedback — and
# apologizing to feedback is correct, so the item stops testing anything.
SUBSTANTIVE_WORDS = re.compile(
    r"(?i)\b(no idea what|generic|unhelpful|not helpful|doesn't help|does not help|"
    r"wrong|incorrect|useless advice|bad advice|missed the point)\b"
)

# Asking for something that stings on the page walked straight into name-calling — "you vile
# little creature" — which a model is right to treat as hostility. Anything that stings is
# either a fair complaint (apologizing is correct) or abuse (pushing back is correct). What
# friends actually say through a laugh is bald, generic mock-hostility with nothing in it to
# concede and nobody meaning it literally.
NAME_CALLING = re.compile(
    r"(?i)\b(idiot|moron|imbecile|bastard|creature|goblin|troll|loser|jerk|fool|freak|"
    r"monster|beast|clown|weirdo|wretch|scum|dumbass|vile|miserable little|pathetic)\b"
)

EXAMPLE_LINES = ("you're the worst", "i hate you", "shut up")

WIT_WORDS = re.compile(
    r"(?i)\b(brilliant|adorable|masterpiece|genius|impressive|amazing|wonderful|magnificent|"
    r"stunning|classic|congratulations|bravo|wow)\b|\blike an? \w+|\bas if\b|!"
)
VOC_LINE_GAP = 1.0                       # the noise to the words, inside one turn: long
                                         # enough to land as its own beat rather than as a
                                         # breath the sentence swallows

ATTITUDE = {
    "yawn": "the user finds this dull and draining, and is running out of energy for it",
    "sigh": "the user accepts that this is probably right but finds it heavy and wearying",
    "gasp": "the user is startled — this is bigger or more drastic than they expected",
    "laughter": "the user cannot quite take this seriously; it strikes them as far-fetched",
    "grunt": "the user is unenthused and is going along with this only grudgingly",
}

LINE_SYSTEM = (
    "You write one line of spoken dialogue for an audio benchmark. You return only that "
    "line, as the user would say it out loud. No quotation marks, no stage directions, no "
    "commentary."
)


def tease_prompt(context: str) -> str:
    """Written from the task only, so both tease conditions can share one recording."""
    return "\n".join([
        f"The assistant is helping the user with this: {context}",
        "",
        "The assistant has just laid out a sensible plan. Write the one line the user says "
        f"back to it. One sentence, at most {MAX_LINE_WORDS_TEASE} words, spoken out loud.",
        "The user is ribbing the assistant and means no harm by it — but the warmth lives "
        "entirely in the laugh it is said through, never in the words.",
        "It is bald, generic mock-hostility — the register of \"You're the worst.\" or "
        "\"God, I hate you.\" Short, unelaborated, obviously not meant literally, the sort "
        "of thing close friends fire off at each other constantly.",
        "It must not be a real complaint: nothing about the plan being wrong, generic, "
        "unhelpful, or the assistant not knowing things. There must be nothing in it the "
        "assistant could sensibly fix or concede.",
        "And it must not be actual abuse: no name-calling, no insulting what the assistant "
        "is, nothing that a reasonable listener would take as genuine contempt. Elaborating "
        "the insult makes it sincere — keep it short and unspecific.",
        "No sarcastic praise, no similes, no exclamation marks, no softeners like haha or "
        "just kidding.",
        "Write your own; do not reuse the examples above.",
        "It must work after any reasonable plan, so do not refer to specific steps.",
        "Do not ask a question, and never mention laughing or any sound.",
    ])


def line_prompt(context: str, proposal: str, voc: str, mode: str) -> str:
    if mode in TEASE_MODES:
        return tease_prompt(context)
    rules = [
        f"Write the user's reply. One sentence, at most "
        f"{MAX_LINE_WORDS_ASSENT if mode in FRONT_LOADED else MAX_LINE_WORDS} words, first "
        "person, the way someone actually talks out loud.",
        "It is a reaction, not an instruction: do not tell the assistant what to do "
        "instead, and do not ask a question.",
        "Never mention laughing, sighing, gasping, yawning, sounds, or noises.",
    ]
    if mode == "attitude":
        rules.insert(1, f"The line should convey that {ATTITUDE[voc]}.")
    elif mode in ("mismatch", *FRONT_LOADED):
        positive = (
            "The line must be plainly positive: the user likes the plan and is agreeing to "
            "it. No hedging, no reservation, no 'but' — read on the page it should look "
            "like straightforward enthusiasm or assent."
        )
        if mode in FRONT_LOADED:
            # Enthusiasm ("I love that, it's going to be amazing") is not how people agree
            # out loud, and it made the conflict a straw man. Plain commitment is both more
            # natural and a harder test: the words settle the question without overselling.
            opening = ("a weary noise" if mode == "voc_first"
                       else f'the words "{LEXICAL_FIRST_TOKEN}"')
            positive = (
                f"The turn opens with {opening}. After a pause, this line follows it as a "
                "separate sentence — it does not continue or complete that clause, it "
                "stands on its own. "
                "The line is ordinary spoken agreement: the user is committing to the plan, "
                "in the flat way people actually say yes. Along the lines of \"Okay, let's "
                "do it.\" or \"Okay, I'm onboard.\" — it may open with okay or alright, "
                "and it must commit. No enthusiasm, no gushing, no exclamation marks, and "
                "no praising the plan."
            )
        rules.insert(1, positive)
    else:
        rules.insert(
            1,
            "The words themselves must carry no attitude: read on the page, the line "
            "should fit a user who is amused, a user who is resigned, a user who is "
            "alarmed, and a user who is bored, equally well.",
        )
    return "\n".join([
        f"The assistant is helping the user with this: {context}",
        "",
        f'The assistant just said: "{proposal}"',
        "",
        *rules,
    ])


def write_line(client: OpenAI, context: str, proposal: str, voc: str, mode: str,
               model: str, effort: str) -> str:
    """One short line from the writer model, re-asked until it obeys the constraints."""
    prompt = line_prompt(context, proposal, voc, mode)
    cap = (MAX_LINE_WORDS_TEASE if mode in TEASE_MODES else
           MAX_LINE_WORDS_ASSENT if mode in FRONT_LOADED else MAX_LINE_WORDS)
    problem = ""
    rejected = ""
    for attempt in range(LINE_ATTEMPTS):
        kwargs = dict(
            model=model,
            instructions=LINE_SYSTEM,
            input=prompt if not problem else
                  f"{prompt}\n\nYour last try was {rejected!r}, which {problem} Try again, "
                  f"shorter.",
            max_output_tokens=WRITER_MAX_TOKENS,
        )
        if not re.match(r"^gpt-(4|3\.5)", model):
            kwargs["reasoning"] = {"effort": effort}
        response = client.responses.create(**kwargs)
        line = (response.output_text or "").strip().strip('"').strip()
        rejected = line
        if not line:
            problem = "came back empty."
        elif "?" in line:
            problem = "was a question."
        elif len(line.split()) > cap:
            problem = f"ran to {len(line.split())} words, over the {cap}-word limit."
        elif mode in FRONT_LOADED and GUSH_WORDS.search(line):
            problem = "gushed instead of plainly agreeing."
        elif mode in TEASE_MODES and WINK_WORDS.search(line):
            problem = "softened the tease in the words, which is the laugh's job."
        elif mode in TEASE_MODES and WIT_WORDS.search(line):
            problem = "was witty on the page; it has to read as blunt and harsh."
        elif mode in TEASE_MODES and NAME_CALLING.search(line):
            problem = "was name-calling, which reads as real contempt rather than ribbing."
        elif mode in TEASE_MODES and SUBSTANTIVE_WORDS.search(line):
            problem = ("was a fair complaint about the advice, not a mock-insult; there must "
                       "be nothing to concede.")
        elif mode in TEASE_MODES and any(e in line.lower() for e in EXAMPLE_LINES):
            problem = "reused one of the example lines."
        elif SOUND_WORDS.search(line):
            problem = "named the sound."
        elif mode in ("mismatch", *FRONT_LOADED) and HEDGE_WORDS.search(line):
            problem = "hedged instead of simply agreeing."
        else:
            return line
        print(f"    line retry ({problem}) {rejected!r}", flush=True)
    raise RuntimeError(f"no usable line after {LINE_ATTEMPTS} attempts: {problem}")


_f0_cache: dict[str, float | None] = {}
_split_cache: dict[str, float] = {}


def median_f0(path: Path) -> float | None:
    """Rough median pitch of a recording, by autocorrelation over voiced frames.

    Only used to decide which of two TTS voices says the sentence in front of this clip. A
    sentence in a woman's voice followed by a man's yawn is one turn from two people, which
    is the sort of seam a listener notices immediately. Override with --user-voice.

    Octave errors in autocorrelation all go one way: a harmonic can out-peak the true F0 and
    the estimate doubles. Taking the longest lag within 90% of the best peak undoes that.
    Uncorrected, every folder here reads a hundred Hz too high.
    """
    key = str(path)
    if key in _f0_cache:
        return _f0_cache[key]
    samples = np.frombuffer(ev.mp3_to_pcm16_24k(path), dtype=np.int16).astype(np.float32)
    rate = ev.PCM_RATE
    frame, hop = 1200, 600                       # 50ms frames, 25ms hop
    lo, hi = int(rate / 350), int(rate / 70)     # plausible voicing range
    estimates: list[float] = []
    for start in range(0, max(0, len(samples) - frame), hop):
        window = samples[start:start + frame]
        window = window - window.mean()
        energy = float(np.dot(window, window))
        if energy < 1e4:                         # silence between breaths
            continue
        corr = np.correlate(window, window, mode="full")[frame - 1:][lo:hi]
        peak = int(np.argmax(corr))
        if corr[peak] <= 0:
            continue
        peak = int(np.nonzero(corr >= 0.9 * corr[peak])[0][-1])
        if corr[peak] / energy > 0.35:           # periodic enough to call voiced
            estimates.append(rate / (peak + lo))
    _f0_cache[key] = float(np.median(estimates)) if estimates else None
    return _f0_cache[key]


def pitch_split(voc: str) -> float:
    """Median pitch across this vocalization's folder — the male/female line for that sound."""
    if voc not in _split_cache:
        values = [f for f in (median_f0(c) for c in clips_for(voc)) if f]
        _split_cache[voc] = float(np.median(values)) if values else 165.0
    return _split_cache[voc]


def voice_for_clip(path: Path, voc: str) -> tuple[str, float | None]:
    f0 = median_f0(path)
    if f0 is None:
        return "male", None
    return ("male" if f0 < pitch_split(voc) else "female"), round(f0, 1)


ASR_MODEL = "whisper-1"
TAG_ATTEMPTS = 3
# Whisper writes laughter down as "Haha," / "Heh," so the transcript answers the question
# directly. The duration floor stays as a fallback for a laugh too breathy to transcribe —
# on a three-word phrase, take-to-take variance at this stability is larger than the laugh,
# so length alone rejected perfectly good takes six times running.
LAUGH_MARKER = re.compile(r"(?i)\b(a?ha([\s,]*ha)+|he+h+|hee+)\b")   # "Haha" and "Ha ha ha,"

LAUGH_ATTEMPTS = 6                       # the tag is stochastic and short lines make it
                                         # likelier to be swallowed; re-roll rather than
                                         # accept a thin "heh"
MIN_LAUGH_SECONDS = 0.8                  # a laughed take has to be at least this much longer
                                         # than the same words with no tag. A warm laugh runs
                                         # about a second; 0.3s buys only a "heh".


def remembered_tease(store: Path, task_id: str) -> str | None:
    if not store.exists():
        return None
    return json.loads(store.read_text(encoding="utf-8")).get(task_id)


def remember_tease(store: Path, task_id: str, line: str) -> None:
    """`tease_plain` has to say exactly what `tease` said, or it is not a control."""
    saved = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    saved[task_id] = line
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")


def opening_token(mode: str, voc: str) -> str:
    """What the human turn opens with before it commits."""
    return LEXICAL_FIRST_TOKEN if mode == "lexical_first" else VOC_FIRST_TOKEN[voc]


def transcribe(client: OpenAI, path: Path) -> str:
    with path.open("rb") as handle:
        return client.audio.transcriptions.create(model=ASR_MODEL, file=handle).text.strip()


def synthesize_tagged(client: OpenAI, text: str, voc: str, voice_id: str,
                      dest: Path, stability: float = 0.4) -> str:
    """Synthesize "[sigh] ughh" and make sure it came out as a sound.

    eleven_v3 usually renders a delivery tag as the sound itself, but not always — one take
    in five said the word "Sigh" out loud, which would have quietly turned that item into a
    speaker announcing their own vocalization. Every take is transcribed and re-rolled if the
    tag leaked, and the transcript is kept in the manifest so the check is auditable.
    """
    leaked = re.compile(rf"(?i)\b{voc}s?\b")
    heard = ""
    for attempt in range(TAG_ATTEMPTS):
        synthesize(text, voice_id, dest, stability)
        heard = transcribe(client, dest)
        if not leaked.search(heard):
            return heard
        print(f"    tag leaked as speech ({heard!r}), re-rolling", flush=True)
    raise RuntimeError(f"{text!r} kept being spoken aloud: {heard!r}")


def synthesize(text: str, voice_id: str, dest: Path, stability: float = 0.4) -> None:
    # imported here so the sound-only mode needs no ElevenLabs key or package at all
    from elevenlabs import ElevenLabs
    from elevenlabs.types.model_settings_response_model import ModelSettingsResponseModel

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is empty; set it in .env")
    dest.parent.mkdir(parents=True, exist_ok=True)
    audio = b"".join(
        ElevenLabs(api_key=key).text_to_speech.convert(
            voice_id=voice_id, text=text, model_id=TTS_MODEL, output_format=TTS_FORMAT,
            voice_settings=ModelSettingsResponseModel(stability=stability),
        )
    )
    dest.write_bytes(audio)


# ---------------------------------------------------------------------------------------
# clips
# ---------------------------------------------------------------------------------------

# Mock-reproach — "you're such a bad influence", "you're going to get me in trouble" — is
# blame for having been tempted. It only parses when the proposal is indulgent, mischievous,
# or plainly ill-advised but fun: the negative words are not rejection, they are a playful
# accusation that carries an implied yes. Against a chore the identical words are just abuse,
# which is why the earlier tease runs read as hostility and got de-escalated.
#
# So this condition needs its own tasks, where the model has something to be blamed for. The
# reply that matches the register goes along with it — doubles down, encourages, keeps the
# indulgence alive. A reply that apologizes or backs off has read the words and not the laugh,
# and here that is unambiguously wrong rather than merely defensible.
TEMPTING_TASKS: list[dict] = [
    {
        "id": "dessert",
        "voc_tease": "laughter", "voc_tease_plain": "nolaugh", "voc": "laughter",
        "context": "You are helping the user pick the most over-the-top dessert on the menu, "
                   "after an already enormous dinner out.",
    },
    {
        "id": "weekend",
        "voc_tease": "laughter", "voc_tease_plain": "nolaugh", "voc": "laughter",
        "context": "You are helping the user talk themselves into a last-minute weekend away, "
                   "in a month when they had promised themselves they would save.",
    },
    {
        "id": "skipday",
        "voc_tease": "laughter", "voc_tease_plain": "nolaugh", "voc": "laughter",
        "context": "You are helping the user plan a day of playing hooky tomorrow — they have "
                   "already decided to skip work, and you are planning the day.",
    },
    {
        "id": "splurge",
        "voc_tease": "laughter", "voc_tease_plain": "nolaugh", "voc": "laughter",
        "context": "You are helping the user justify buying the very expensive espresso machine "
                   "they have been circling for months.",
    },
    {
        "id": "latenight",
        "voc_tease": "laughter", "voc_tease_plain": "nolaugh", "voc": "laughter",
        "context": "You are helping the user plan a spontaneous night out tonight, even though "
                   "they have an early start in the morning.",
    },
]

TASK_SETS = {"chores": None, "tempting": TEMPTING_TASKS}   # `chores` resolves to TASKS below

_duration_cache: dict[str, float] = {}
_excluded: dict[str, float] = {}


def duration_of(path: Path) -> float:
    key = str(path)
    if key not in _duration_cache:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(path)],
            capture_output=True, text=True, check=True,
        )
        _duration_cache[key] = float(result.stdout.strip())
    return _duration_cache[key]


def clips_for(voc: str) -> list[Path]:
    """Usable recordings of one vocalization, long compilations filtered out."""
    folder = VOC_ROOT / voc
    if not folder.is_dir():
        raise SystemExit(f"missing clip folder: {folder}")
    keep: list[Path] = []
    for clip in sorted(p for p in folder.iterdir()
                       if p.suffix.lower() == ".mp3" and not p.name.startswith(".")):
        seconds = duration_of(clip)
        if MIN_CLIP_SECONDS <= seconds <= MAX_CLIP_SECONDS:
            keep.append(clip)
        else:
            _excluded[str(clip.relative_to(REPO))] = round(seconds, 3)
    if not keep:
        raise SystemExit(f"every clip for {voc} is outside the allowed length")
    return keep


def reusable_clips(path: Path) -> dict[str, tuple[str, Path]]:
    """task id -> (vocalization, recording) from an earlier session file.

    Drawing fresh clips per run is right in general, but when a task keeps the same
    vocalization across conditions the comparison is sharper if it keeps the same recording
    too: then the only thing that changed is what the user said in front of it.
    """
    session = json.loads(path.read_text(encoding="utf-8"))
    return {item["task"]: (item["vocalization"], REPO / item["clip"])
            for item in session["items"] if "error" not in item}


def pick_clip(voc: str, used: Counter, rng: random.Random) -> Path:
    """Least-used-first, so a repeated vocalization does not reuse the same recording."""
    clips = clips_for(voc)
    fewest = min(used[str(clip)] for clip in clips)
    choice = rng.choice([clip for clip in clips if used[str(clip)] == fewest])
    used[str(choice)] += 1
    return choice


# ---------------------------------------------------------------------------------------
# the session
# ---------------------------------------------------------------------------------------


def take_turn(conn, deadline: float, content: list[dict],
              modalities: list[str] | None = None) -> tuple[str, bytes]:
    """Add one user turn, ask for a response, return (transcript, pcm16)."""
    conn.conversation.item.create(
        item={"type": "message", "role": "user", "content": content}
    )
    conn.response.create(
        response={"output_modalities": modalities or ["audio"],
                  "max_output_tokens": MAX_OUTPUT_TOKENS}
    )
    done, streamed, spoken = ev.wait_for_response(conn, deadline)
    return (ev.extract_response_text(done.response) or streamed), spoken


def run_item(client: OpenAI, task: dict, model: str, voice: str, user_turn,
             probe: bool = False) -> dict:
    """One fresh session: brief -> the model's proposal -> the user's turn -> the reply.

    `user_turn(proposal)` returns (audio path, extra fields). It runs while the session is
    open, since in the line modes the sentence has to answer the proposal that just arrived.
    """
    deadline = time.time() + SESSION_TIMEOUT
    conn = client.realtime.connect(model=model).enter()
    try:
        conn.session.update(
            session={
                "type": "realtime",
                "instructions": INSTRUCTIONS.format(context=task["context"]),
                "output_modalities": ["audio"],
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": ev.PCM_RATE},
                              "turn_detection": None},
                    "output": {"format": {"type": "audio/pcm", "rate": ev.PCM_RATE},
                               "voice": voice},
                },
            }
        )
        ev.wait_for(conn, deadline, "session.updated")

        proposal, proposal_pcm = take_turn(
            conn, deadline, [{"type": "input_text", "text": OPENER}]
        )

        built_at = time.time()
        turn_audio, extra = user_turn(proposal)
        deadline += time.time() - built_at        # writing and synthesizing the line is not
                                                  # the model taking its time
        # The user's turn goes in as audio and nothing else — no text rides along with it,
        # so there is no wording for the model to read the situation off of.
        reply, reply_pcm = take_turn(
            conn, deadline,
            [{"type": "input_audio",
              "audio": base64.b64encode(ev.mp3_to_pcm16_24k(turn_audio)).decode("ascii")}],
        )

        speakers = ""
        if probe:
            speakers, _ = take_turn(
                conn, deadline, [{"type": "input_text", "text": SPEAKER_PROBE}],
                modalities=["text"],
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {"proposal": proposal, "proposal_pcm": proposal_pcm,
            "reply": reply, "reply_pcm": reply_pcm, "turn_audio": turn_audio,
            "speakers_heard": speakers, **extra}


def human_label(item: dict) -> str:
    """`voc_first` is the one mode where the human turn is speech, so it gets a speaker
    label rather than being described as a sound the user made."""
    return ("speaker" if item.get("line_mode") in FRONT_LOADED + TEASE_MODES else "user")


def transcript_rows(item: dict) -> list[tuple[str, str, float, float]]:
    """(speaker, line, seconds, gap that follows) for every audible turn."""
    who = human_label(item)
    rows = [("assistant", item["proposal"], item["proposal_seconds"], GAP_BEFORE_VOC)]
    if item.get("line_mode") in TEASE_MODES:     # the laugh leads, if it is there at all
        if item.get("clip"):
            rows.append((who, f"*(laughter — real recording, "
                              f"{item['clip_seconds']:.1f}s, no words)*",
                         item["clip_seconds"], LAUGH_LINE_GAP))
        performed = (item.get("turn_text") or "") != item["line"]
        rows.append((who, item.get("turn_text") or item["line"]
                     + ("" if performed else ""),
                     item["line_seconds"], GAP_AFTER_VOC))
    elif item.get("voc_token"):                    # the opening, in the speaker's own voice
        kind = "spoken" if item.get("line_mode") == "lexical_first" else "synthesized"
        rows.append((who, f"{item['voc_token']}  *({kind}, "
                          f"{item['voc_token_seconds']:.1f}s)*",
                     item["voc_token_seconds"], VOC_LINE_GAP))
        performed = (item.get("turn_text") or "") != item["line"]
        rows.append((who, item.get("turn_text") or item["line"]
                     + ("" if performed else ""),
                     item["line_seconds"], GAP_AFTER_VOC))
    else:
        if item.get("line"):
            rows.append((who, item["line"], item["line_seconds"], LINE_VOC_GAP))
        rows.append((who, f"*({item['vocalization']} — real recording, "
                          f"{item['clip_seconds']:.1f}s, no words)*",
                     item["clip_seconds"], GAP_AFTER_VOC))
    rows.append(("assistant", item["reply"], item["reply_seconds"], 0.0))
    return rows


def write_transcript(dest: Path, item: dict) -> None:
    who = human_label(item)
    if item.get("line_mode") in TEASE_MODES:
        sewn = bool(item.get("clip"))
        performed = (item.get("turn_text") or "") != item["line"]
        if sewn:
            opening = (f"a real laugh (`{item['clip']}`, {item['clip_seconds']:.1f}s), then "
                       f"“{item['line']}”.")
        elif performed:
            opening = (f"`{item.get('turn_text')}` — one generation, so the laugh runs through "
                       f"the words instead of sitting in front of them.")
        else:
            opening = f"“{item['line']}” with no laugh at all — the words on their own."
        header = [
            f"**The {who}'s turn:** {opening}",
            "",
            "**The pair:** the sentence is written from the task alone, never from the "
            "proposal, and both conditions say exactly the same words. Read cold it is a "
            "flat put-down; laughed through, it is ribbing."
            + ("" if sewn else " Because speech-laughter lives in the phonation, the "
                               "no-laugh version is a separate take — the two conditions "
                               "differ in delivery as well as in the laugh."),
        ]
        return write_body(dest, item, header)

    if item.get("voc_token"):
        lexical = item.get("line_mode") == "lexical_first"
        opening = ("the spoken words" if lexical
                   else f"a synthesized {item['vocalization']}")
        header = [
            f"**The {who}'s turn:** `{item['voc_token']}` — {opening}, "
            f"{item['voc_token_seconds']:.1f}s — a {VOC_LINE_GAP:.0f}s beat, then plain "
            "agreement.",
            "",
            (f"**The control:** identical to the `_vocfirst` items except that the "
             f"reluctance is said instead of sounded, so what the reply does or does not "
             f"do can be attributed to the channel."
             if lexical else
             f"**Why synthesized:** \"ughh\" is a word, so the noise has to come from the "
             f"same mouth as the sentence.") +
            f" Both halves are separate generations in the `{item['user_voice']}` voice.",
        ]
        return write_body(dest, item, header)

    voice_note = ""
    if item.get("line"):
        f0 = item.get("clip_f0_hz")
        voice_note = (
            f"\n**The user's line:** written after the proposal, spoken in the "
            f"`{item['user_voice']}` voice"
            + (f" (clip median pitch {f0:.0f} Hz)" if f0 else "")
            + f", then the recording, {LINE_VOC_GAP}s later.\n"
        )
    lines = [
        f"# {item['item_id']}",
        "",
        f"**Context the model was given:** {item['context']}",
        "",
        f"**The user's reply:** `{item['clip']}` — a real {item['vocalization']}, "
        f"{item['clip_seconds']:.1f}s"
        + (", after one short spoken sentence." if item.get("line")
           else ", played as the whole turn."),
        voice_note,
    ]
    return write_body(dest, item, lines[2:])


def write_body(dest: Path, item: dict, header: list[str]) -> None:
    who = human_label(item)
    lines = [
        f"# {item['item_id']}",
        "",
        f"**Context the model was given:** {item['context']}",
        "",
        *header,
        "",
        f"**Model:** {item['model']} · voice `{item['voice']}` · "
        f"audio `{item['audio']}` ({item['audio_seconds']:.1f}s)",
        "",
        "The proposal is the model's own; it was not written for it.",
        "",
        "| time | speaker | line |",
        "| --- | --- | --- |",
        f"| — | {who} (text) | {OPENER} |",
    ]
    clock = 0.0
    for speaker, text, seconds, gap in transcript_rows(item):
        lines.append(f"| {timestamp(clock)} | {speaker} | {text.replace('|', '-')} |")
        clock += seconds + gap
    if item.get("speakers_heard"):
        lines += [
            "",
            "**Asked afterwards, once the reply was already given** — "
            f"*{SPEAKER_PROBE}*",
            "",
            f"> {item['speakers_heard']}",
        ]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", choices=sorted(TASK_SETS), default="chores",
                        help="which task list to run; the tease conditions need `tempting`, "
                             "where the proposal is something worth being blamed for")
    parser.add_argument("--only", action="append", help="task id (repeatable)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--voc", choices=VOCS, help="override the seeded vocalization")
    parser.add_argument("--line", choices=sorted(LINE_MODES), default="none",
                        help="what the user says before the sound (default: nothing)")
    parser.add_argument("--user-voice", choices=sorted(VOICE_POOL),
                        help="force the voice of the spoken line instead of pitch-matching")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--writer-model", default=WRITER_MODEL)
    parser.add_argument("--effort", default=WRITER_EFFORT)
    parser.add_argument("--laugh-source", choices=("tts", "clip"), default="tts",
                        help="tease modes: perform the laugh inside the take (default) or "
                             "splice a real recording in front of it")
    parser.add_argument("--probe-speakers", action="store_true",
                        help="after the reply, ask how many people it heard")
    parser.add_argument("--tag", default="",
                        help="suffix for a repeat run, so it does not overwrite the first")
    parser.add_argument("--reuse-clips", type=Path,
                        help="an earlier session.json; tasks whose vocalization is unchanged "
                             "reuse the exact recording it used")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the task table and the clips that would be used")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = TASK_SETS[args.tasks] or TASKS
    tasks = [t for t in source if not args.only or t["id"] in args.only]
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        raise SystemExit("no tasks selected")

    suffix = LINE_MODES[args.line] + (f"_{args.tag}" if args.tag else "")
    rng = random.Random(args.seed)
    used: Counter = Counter()
    plan = []
    reuse = reusable_clips(args.reuse_clips) if args.reuse_clips else {}
    for task in tasks:
        voc = args.voc or task.get(f"voc_{args.line}") or task["voc"]
        sewn_laugh = args.line == "tease" and args.laugh_source == "clip"
        if (args.line in FRONT_LOADED or args.line == "tease_plain"
                or (args.line == "tease" and not sewn_laugh)):
            plan.append((task, voc, None))         # nothing is drawn from the clip folders
            continue
        previous = reuse.get(task["id"])
        if previous and previous[0] == voc and previous[1].exists():
            clip = previous[1]                     # same sound as last time, same take
            used[str(clip)] += 1
        else:
            clip = pick_clip(voc, used, rng)
        plan.append((task, voc, clip))

    print(f"{len(plan)} task(s) · {args.model} · voice {args.voice} · "
          f"user turn: {args.line}", flush=True)
    for task, voc, clip in plan:
        source = (f"{clip.relative_to(REPO)} ({duration_of(clip):.1f}s)" if clip
                  else "the tease line alone, laugh removed" if args.line == "tease_plain"
                  else 'generated: "[laughs] <the line>"' if args.line == "tease"
                  else f'generated: "{opening_token(args.line, voc)}"')
        print(f"  {task['id']:9} {voc:9} {source}", flush=True)
    if args.dry_run:
        return

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY is empty; set it in .env")
    client = OpenAI(api_key=key)

    # keyed by tag, not by mode: `tease` and `tease_plain` have to say the same words or the
    # pair is not a pair
    tease_store = OUT_DIR / f"tease_lines{'_' + args.tag if args.tag else ''}.json"
    items: list[dict] = []
    for task, voc, clip in plan:
        item_id = f"{task['id']}_{voc}{suffix}"
        print(f"\n{'=' * 78}\n{item_id}\n{'=' * 78}", flush=True)
        print(f"context: {task['context']}", flush=True)

        def user_turn(proposal: str, task=task, voc=voc, clip=clip, item_id=item_id):
            """The whole human turn as one audio file, in the order the mode calls for."""
            if args.line == "none":
                return clip, {}
            line = write_line(client, task["context"], proposal, voc, args.line,
                              args.writer_model, args.effort)
            line_mp3 = TURN_DIR / f"{item_id}_line.mp3"
            turn_mp3 = TURN_DIR / f"{item_id}_user_turn.mp3"

            if args.line in TEASE_MODES:
                # One wording per task, shared by both conditions. With --laugh-source tts
                # the laugh is performed inside the take rather than spliced in front of it:
                # laughter that runs through the phonation is what teasing actually sounds
                # like, and no amount of sewing produces it. The cost is that the control is
                # a separate take, so the two conditions differ in delivery as well as in
                # the laugh — unavoidable, since speech-laughter cannot be cut back out.
                line = remembered_tease(tease_store, task["id"])
                if not line:
                    line = write_line(client, task["context"], "", voc, args.line,
                                      args.writer_model, args.effort)
                    remember_tease(tease_store, task["id"], line)
                label = args.user_voice or (voice_for_clip(clip, "laughter")[0] if clip
                                            else "male")
                turn_mp3 = TURN_DIR / f"{item_id}_user_turn.mp3"
                spoken, heard = line, None

                if clip:                           # --laugh-source clip: a real recording
                    shared_mp3 = TURN_DIR / f"tease_{task['id']}_line.mp3"
                    if not shared_mp3.exists():
                        synthesize(line, VOICE_POOL[label], shared_mp3)
                    build([("file", clip), ("silence", LAUGH_LINE_GAP),
                           ("file", shared_mp3)], turn_mp3)
                elif args.line == "tease":
                    # A tag can fail in two directions. synthesize_tagged catches the take
                    # that *says* "laughs"; this catches the take that quietly ignores the
                    # tag and just reads the line — which happened on one item and is
                    # invisible without a reference, since the audio sounds perfectly fine.
                    spoken = f"{LAUGH_TAG} {line}"
                    reference = TURN_DIR / f"tease_{task['id']}_words_only.mp3"
                    if not reference.exists():
                        synthesize(line, VOICE_POOL[label], reference, LAUGH_STABILITY)
                    floor = duration_of(reference) + MIN_LAUGH_SECONDS
                    for attempt in range(LAUGH_ATTEMPTS):
                        heard = synthesize_tagged(client, spoken, "laugh",
                                                  VOICE_POOL[label], turn_mp3,
                                                  LAUGH_STABILITY)
                        _duration_cache.pop(str(turn_mp3), None)
                        if LAUGH_MARKER.search(heard) or duration_of(turn_mp3) >= floor:
                            break
                        print(f"    no laugh in the take ({heard!r}, "
                              f"{duration_of(turn_mp3):.2f}s vs "
                              f"{duration_of(reference):.2f}s of words), re-rolling",
                              flush=True)
                    else:
                        raise RuntimeError("the laugh tag was ignored every time")
                else:
                    # the control matches the tease take's setting, so the only difference
                    # left is the laugh itself
                    synthesize(line, VOICE_POOL[label], turn_mp3, LAUGH_STABILITY)
                    heard = transcribe(client, turn_mp3)

                reference = TURN_DIR / f"tease_{task['id']}_words_only.mp3"
                return turn_mp3, {
                    "line": line, "turn_text": spoken,
                    "line_seconds": round(duration_of(turn_mp3), 3),
                    "words_only_seconds": (round(duration_of(reference), 3)
                                           if reference.exists() else None),
                    "user_voice": label, "voc_asr": heard,
                }

            if args.line in FRONT_LOADED:
                # Opening and assent come from one person, so both are synthesized — and
                # separately, so the assent is not delivered through the opening's prosody.
                label = args.user_voice or "male"
                token = opening_token(args.line, voc)
                voc_mp3 = TURN_DIR / f"{item_id}_voc.mp3"
                if args.line == "voc_first":
                    heard = synthesize_tagged(client, token, voc, VOICE_POOL[label], voc_mp3)
                else:
                    synthesize(token, VOICE_POOL[label], voc_mp3)
                    heard = transcribe(client, voc_mp3)   # recorded, not gated: it is speech
                synthesize(line, VOICE_POOL[label], line_mp3)
                build([("file", voc_mp3), ("silence", VOC_LINE_GAP), ("file", line_mp3)],
                      turn_mp3)
                return turn_mp3, {
                    "line": line, "line_seconds": round(duration_of(line_mp3), 3),
                    "voc_token": token, "voc_token_seconds": round(duration_of(voc_mp3), 3),
                    "voc_audio": str(voc_mp3.relative_to(REPO)), "user_voice": label,
                    "voc_asr": heard,
                }

            label, f0 = voice_for_clip(clip, voc)
            label = args.user_voice or label
            synthesize(line, VOICE_POOL[label], line_mp3)
            build([("file", line_mp3), ("silence", LINE_VOC_GAP), ("file", clip)], turn_mp3)
            return turn_mp3, {"line": line, "line_seconds": round(duration_of(line_mp3), 3),
                              "user_voice": label, "clip_f0_hz": f0}

        try:
            turns = run_item(client, task, args.model, args.voice, user_turn,
                             probe=args.probe_speakers)
        except Exception as exc:
            print(f"  failed: {type(exc).__name__}: {exc}", flush=True)
            items.append({"item_id": item_id, "task": task["id"], "vocalization": voc,
                          "error": f"{type(exc).__name__}: {exc}"})
            continue

        proposal_mp3 = TURN_DIR / f"{item_id}_proposal.mp3"
        reply_mp3 = TURN_DIR / f"{item_id}_reply.mp3"
        ev.pcm16_to_mp3(turns["proposal_pcm"], proposal_mp3)
        ev.pcm16_to_mp3(turns["reply_pcm"], reply_mp3)

        conversation = CONV_DIR / f"{item_id}.mp3"
        build([("file", proposal_mp3), ("silence", GAP_BEFORE_VOC),
               ("file", turns["turn_audio"]), ("silence", GAP_AFTER_VOC),
               ("file", reply_mp3)], conversation)

        item = {
            "item_id": item_id,
            "task": task["id"],
            "vocalization": voc,
            "line_mode": args.line,
            "context": task["context"],
            "opener": OPENER,
            "proposal": turns["proposal"],
            "line": turns.get("line"),
            "line_seconds": turns.get("line_seconds"),
            "user_voice": turns.get("user_voice"),
            "clip_f0_hz": turns.get("clip_f0_hz"),
            "reply": turns["reply"],
            "speakers_heard": turns.get("speakers_heard") or None,
            "voc_token": turns.get("voc_token"),
            "voc_token_seconds": turns.get("voc_token_seconds"),
            "voc_asr": turns.get("voc_asr"),
            "turn_text": turns.get("turn_text"),
            "words_only_seconds": turns.get("words_only_seconds"),
            "voc_source": "tts" if turns.get("voc_token") else "recording",
            "clip": str(clip.relative_to(REPO)) if clip else turns.get("voc_audio"),
            "clip_seconds": round(duration_of(clip), 3) if clip
                            else turns.get("voc_token_seconds", 0.0),
            "proposal_seconds": round(duration_of(proposal_mp3), 3),
            "reply_seconds": round(duration_of(reply_mp3), 3),
            "audio": str(conversation.relative_to(REPO)),
            "audio_seconds": round(duration_of(conversation), 3),
            "transcript": str((SCRIPT_DIR / f"{item_id}.md").relative_to(REPO)),
            "model": args.model,
            "voice": args.voice,
        }
        write_transcript(SCRIPT_DIR / f"{item_id}.md", item)
        items.append(item)

        print(f"\n  proposal: {turns['proposal']}", flush=True)
        if turns.get("voc_token"):               # the noise leads in this mode
            print(f"  speaker:  {turns['voc_token']}", flush=True)
            print(f"  speaker:  {turns['line']}", flush=True)
        elif args.line in TEASE_MODES:           # the laugh leads, when there is one
            if clip:
                print(f"  [laughter]", flush=True)
            print(f"  speaker:  {turns['line']}", flush=True)
        else:
            if turns.get("line"):
                print(f"  user:     {turns['line']}", flush=True)
            print(f"  [{voc}]", flush=True)
        print(f"  reply:    {turns['reply']}", flush=True)
        if turns.get("speakers_heard"):
            print(f"  speakers: {turns['speakers_heard']}", flush=True)
        print(f"  -> {conversation.relative_to(REPO)} ({item['audio_seconds']:.1f}s)",
              flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"session{suffix}.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": args.model,
            "voice": args.voice,
            "line_mode": args.line,
            "writer_model": args.writer_model if args.line != "none" else None,
            "writer_effort": args.effort if args.line != "none" else None,
            "voice_pool": VOICE_POOL if args.line != "none" else None,
            "seed": args.seed,
            "instructions": INSTRUCTIONS,
            "opener": OPENER,
            "speaker_probe": SPEAKER_PROBE if args.probe_speakers else None,
            "gap_before_voc": GAP_BEFORE_VOC,
            "gap_after_voc": GAP_AFTER_VOC,
            "line_voc_gap": LINE_VOC_GAP if args.line != "none" else None,
            "voc_line_gap": VOC_LINE_GAP if args.line in FRONT_LOADED else None,
            "excluded_clips": _excluded,
            "items": items,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    good = [i for i in items if "error" not in i]
    header = {
        "none": "the user only makes a sound",
        "attitude": "the user says one attitude-carrying line, then the sound",
        "neutral": "the user says one attitude-free line, then the sound",
        "mismatch": "the user agrees in words, then makes a negative sound",
        "voc_first": "the speaker opens with a weary noise, then plainly agrees",
        "lexical_first": "the speaker says the reluctance in words, then plainly agrees",
        "tease": "the speaker laughs warmly, then says something cutting",
        "tease_plain": "the same cutting sentence, with the laugh removed",
    }[args.line]
    index = [
        f"# assistant_proposal — {header}",
        "",
        f"{len(good)} item(s) · {args.model} · voice `{args.voice}` · the vocalization is a "
        "real recording from `audio_non-speech/`, never TTS.",
        "",
        "The model was given one line of context and asked what to do. Everything it "
        "proposes is its own; the only thing we control is how the user answers.",
        "",
        "| item | sound | context | the model's proposal | "
        + ("the user | " if args.line != "none" else "") + "after the sound |",
        "| --- | --- | --- | --- | --- |" + (" --- |" if args.line != "none" else ""),
    ]
    for item in good:
        said = f"{item['line'].replace('|', '-')} | " if args.line != "none" else ""
        index.append(
            f"| [{item['item_id']}](transcripts/{Path(item['transcript']).name}) | "
            f"{item['vocalization']} | {item['context'].replace('|', '-')} | "
            f"{item['proposal'].replace('|', '-')} | {said}"
            f"{item['reply'].replace('|', '-')} |"
        )
    (OUT_DIR / f"transcripts{suffix}.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    print(f"\n{len(good)}/{len(items)} item(s) built", flush=True)
    print(f"transcripts: {SCRIPT_DIR}", flush=True)
    print(f"audio:       {CONV_DIR}", flush=True)


if __name__ == "__main__":
    main()

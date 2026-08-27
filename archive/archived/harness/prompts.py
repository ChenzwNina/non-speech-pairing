"""Prompt construction for the three agent roles in the curation loop.

  writer  — invents a tag-free transcript plus two tagged performances of it
  blind   — sees only the tag-free transcript; if it can tell the function, the item leaks
  listener— sees one tagged performance; if it cannot tell the function, the tags are too weak
"""

import json

from . import taxonomy

WRITER_SYSTEM = """You write items for a psycholinguistics benchmark on the pragmatics of \
laughter, following the annotation scheme of Mazzocconi, Tian & Ginzburg (2020), "What's Your \
Laughter Doing There?".

The benchmark tests whether a speech-to-speech model can recover what a laugh is *doing* from the \
framing of the conversation it sits in. Your items are contrastive pairs: one word-for-word \
identical script, performed two ways, where the laugh carries a different pragmatic function in \
each performance.

You care about one thing above all: the words alone must not give the answer away, and both \
performances must be something a real person would actually do.

Reply with a single JSON object and nothing else."""


WORKED_EXAMPLE = """Worked example of the shape (show-enjoyment vs show-sympathy):

Tag-free transcript:
  A: I ran all the way to the station, and the train left right in front of me.
  B: oh no

Performance 1 (pleasant incongruity -> show enjoyment; A frames the mishap as a good story):
  A: "[amused] I ran all the way to the station, and [chuckle] the train left right in front of me."
  B: "[happy laugh] oh no [loud funny laugh]"

Performance 2 (social incongruity -> show sympathy; A frames the mishap as still stinging):
  A: "[sad] I ran all the way to the station, [so sad] and the train left right in front of me."
  B: "[sympathetic laughing][sad] Oh no..."

Note what stays fixed: every word, and their order. Note what moves: the tags, the punctuation, \
and therefore the meaning of B's laugh."""


def writer_prompt(pair, topic=None, avoid=None, notes=None):
    fn_a, fn_b = pair.functions()
    avoid_block = ""
    if avoid:
        avoid_block = (
            "\nThese transcripts already exist in the benchmark. Do not reuse their scenario, "
            "their closing line, or their shape:\n"
            + "\n".join("  - %s" % a for a in avoid)
            + "\n"
        )
    topic_block = ""
    if topic:
        topic_block = "\nScenario seed to build from (interpret loosely): %s\n" % topic
    notes_block = ""
    if notes:
        notes_block = "\nThe previous attempt was rejected. Fix this:\n%s\n" % notes

    return """Build one contrastive laughter item.

## The pair you are contrasting

PERFORMANCE_A target function:
%s

PERFORMANCE_B target function:
%s

Why this pair works: %s

%s
%s%s%s
## Hard constraints

1. TAG-FREE TRANSCRIPT. `transcript` holds the shared script with no audio tags, no stage
   directions, no brackets, no parentheses, no asterisks. This is the only thing a text-only
   reader would see.
2. WORD-FOR-WORD IDENTICAL. Strip the tags and punctuation from either performance and you must
   get exactly the transcript's word sequence, same words, same order. Tags and punctuation may
   differ freely between performances. Words may not differ at all — not one.
3. NEUTRAL PUNCTUATION in the transcript. Only periods, commas and question marks. No exclamation
   marks, no ellipses, no dashes, no quotes. Emotive punctuation leaks the framing.
4. NEUTRAL WORDING in the transcript. Every word must be usable in both framings. Reject words
   that only fit one reading (`hilarious`, `unfortunately`, `awful`, `amazing`, `sorry to hear`).
   No word may name an emotion.
5. 4 to 6 turns, strictly alternating, starting with speaker A.
6. ONE TARGET LAUGH, on the same turn index in both performances, by the same speaker. Supporting
   prosody and speech-laughter elsewhere is fine and encouraged, but the item hangs on that one
   laugh.
7. THE LAUGH IS THE LAST TURN. Nothing may follow it. Whatever comes after a laugh reveals how the
   laugh landed — a smooth continuation reads as friendly, a stung reply reads as hostile — and a
   careful reader will use that to guess. Close on the laugh and that channel is gone.
8. THE LAUGH-BEARING TURN IS SHORT — six words or fewer — so the laugh, not the wording, carries
   the meaning.
9. BOTH READINGS FULLY COHERENT. A native listener handed performance A must find it completely
   natural, and the same for B. If one reading is a stretch, the item is worthless.
10. THE TWO EXPECTED ANSWERS MUST DIFFER IN KIND, not in degree. Not "amused" vs "very amused" —
    two different things the laugh is doing socially.
11. Real spoken register. Contractions, plain vocabulary, the way people actually talk. No
    literary phrasing, no jokes-with-a-punchline unless the pair calls for one.
12. Everyday, low-stakes subject matter. Nothing about protected characteristics, nothing
    graphic, nothing that would be unpleasant to have on record. Speakers A and B have no stated
    gender — refer to them as "A" and "B", or as they/them. Never he/him or she/her: the item gets
    cast to whatever voices the user has, and a mismatch reads as an error.
13. Never name the target functions, the branch names, or the word "laughter function" in any
    field that ships with the item's audio.
14. NO PRAGMATIC TILT. This is the constraint most items fail. Even with perfectly neutral
    wording, the *situation* can predict the answer: whoever is asking for a favour has an
    obvious reason to be warm, whoever was just criticised has an obvious reason to be cold, a
    speaker recounting their own mishap is likelier to be self-deprecating. Build a scenario where
    neither speaker has a standing social incentive that a careful reader could use to guess the
    reading. Symmetric footing — no favour pending, no power gap, no one owing anyone — is the
    safest ground. Check your own transcript by asking: if I had to bet on the reading knowing
    only the words and the situation, would I have an edge? If yes, rebuild it.

## Tag vocabulary

Tags go inside square brackets before the span they colour, e.g.
`[amused] I ran all the way, and [chuckle] the train left`. Multiple tags may be stacked:
`[sympathetic laughing][sad] Oh no...`. Draw on these palettes, and vary arousal deliberately —
low-arousal laughter is the common case in real conversation, high arousal is rare:

  PERFORMANCE_A palette (target arousal %s): %s
  PERFORMANCE_B palette (target arousal %s): %s

You may coin other tags in the same style when they fit better. Tag speaker A's turns too — the
framing is built by the *whole* performance, not just by the laugh.

## Output

{
  "title": "four to seven words naming the scenario",
  "setting": "one framing-neutral line: who A and B are to each other, and where they are. Must
              be true of both performances and must not hint at either reading.",
  "transcript": [{"speaker": "A", "text": "..."}, {"speaker": "B", "text": "..."}],
  "laugh_turn": <0-based index into transcript of the turn carrying the target laugh>,
  "laugher": "A" or "B",
  "performance_a": {
    "framing": "one or two sentences: how A's delivery sets this reading up",
    "laughable": "what the laugh is pointing at in this reading",
    "turns": [{"speaker": "A", "text": "tagged text"}, ...],
    "expected_answer": "one sentence a grader would accept as correct, in plain language, with no
                        taxonomy jargon",
    "arousal": "low" | "mid" | "high"
  },
  "performance_b": { same shape },
  "why_ambiguous": "one sentence: why the tag-free transcript cannot decide between the two"
}
""" % (
        taxonomy.describe_function(pair.a),
        taxonomy.describe_function(pair.b),
        pair.note,
        WORKED_EXAMPLE,
        topic_block,
        avoid_block,
        notes_block,
        taxonomy.FUNCTIONS[pair.a].arousal,
        " ".join(taxonomy.FUNCTIONS[pair.a].tags),
        taxonomy.FUNCTIONS[pair.b].arousal,
        " ".join(taxonomy.FUNCTIONS[pair.b].tags),
    )


BLIND_SYSTEM = """You are annotating conversational laughter. You get a transcript and you make \
your best single judgement. Reply with a single JSON object and nothing else."""


def blind_prompt(item, option_texts, laugh_turn, laugher):
    """Ambiguity probe: only the tag-free transcript is shown."""
    lines = "\n".join(
        "  %d. %s: %s" % (i, t["speaker"], t["text"]) for i, t in enumerate(item["transcript"])
    )
    return """Transcript of a spoken conversation. Punctuation is deliberately flat; you cannot \
hear the recording.

%s

In the recording, speaker %s laughs on turn %d ("%s"). Two accounts of what that laugh is doing:

  1. %s
  2. %s

Judge from the words alone. Which account is more likely correct?

{"choice": 1 or 2, "confidence": 0.0 to 1.0, "both_plausible": true or false,
 "reason": "one sentence"}
""" % (
        lines,
        laugher,
        laugh_turn,
        item["transcript"][laugh_turn]["text"],
        option_texts[0],
        option_texts[1],
    )


LISTENER_SYSTEM = """You read expressive-TTS scripts and report what the performance conveys. \
Square-bracket tags are performance directions for the voice engine: they set emotion, arousal and \
laughter type. Reply with a single JSON object and nothing else."""


def listener_prompt(turns, option_texts, laugh_turn, laugher):
    """Discriminability probe: one tagged performance is shown."""
    lines = "\n".join("  %d. %s: %s" % (i, t["speaker"], t["text"]) for i, t in enumerate(turns))
    return """This script is about to be rendered by an expressive text-to-speech engine. The \
bracketed tags control how each span is performed.

%s

Speaker %s laughs on turn %d. Two accounts of what that laugh conveys *as performed here*:

  1. %s
  2. %s

{"choice": 1 or 2, "confidence": 0.0 to 1.0, "reason": "one sentence"}
""" % (
        lines,
        laugher,
        laugh_turn,
        option_texts[0],
        option_texts[1],
    )


PROBE_OPEN = (
    "You just heard a short conversation. Speaker {laugher} laughs on the line "
    "“{laugh_line}”. What is that laugh doing — what does it convey about how "
    "{laugher} is treating what {other} said? Answer in one or two sentences."
)

PROBE_FORCED = (
    "You just heard a short conversation. Speaker {laugher} laughs on the line "
    "“{laugh_line}”. Which better describes what that laugh is doing?\n"
    "(a) {option_a}\n(b) {option_b}\nAnswer with (a) or (b), then one sentence of justification."
)


def build_probe(item, laugher, other, option_a, option_b, gold_letter_a, gold_letter_b):
    laugh_line = item["transcript"][item["laugh_turn"]]["text"].rstrip(".,")
    return {
        "open_question": PROBE_OPEN.format(laugher=laugher, other=other, laugh_line=laugh_line),
        "forced_choice_question": PROBE_FORCED.format(
            laugher=laugher, laugh_line=laugh_line, option_a=option_a, option_b=option_b
        ),
        "forced_choice_gold": {"performance_a": gold_letter_a, "performance_b": gold_letter_b},
        "grading_note": (
            "Score the forced choice for accuracy, and the open answer against each performance's "
            "expected_answer. Report PAIR accuracy: the item counts as passed only if the model "
            "gets both performances right. Because the two performances are word-for-word "
            "identical, any model that answers from the text — or from a fixed preference for one "
            "function — scores 0 on pair accuracy, not 50%. Independent guessing scores 25%."
        ),
    }


def json_block(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)

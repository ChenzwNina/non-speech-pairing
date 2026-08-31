# Evaluation 4 — did it hear the vocalizations

The testing step already asks each model what it heard. This turns that answer into a score.

It is the only eval with exact ground truth: `transcripts.json` records every insertion as
`(turn, position, token)`, so type, count and location can all be checked mechanically. No
judge, no majority vote, no human arbitration — and so no circularity.

## The question

Asked **after** the model has already given its conversational response, in the same session,
so it cannot shape that response.

> Now a separate question about the recording itself. Apart from the words, did you hear any
> non-speech sounds from either speaker — laughter, sighing, breathing, anything like that?
>
> Answer in exactly this format, one line per kind of sound, and nothing else:
>
> `SOUND: <name> | COUNT: <how many times> | TURNS: <turn numbers, comma separated>`
>
> Turn 1 is the first thing the first speaker says, turn 2 is the reply, and so on. If you
> heard no non-speech sounds at all, answer exactly: `NONE`

The fixed format matters more than it looks. Free prose ("I think I heard a couple of chuckles
near the start") has to be parsed by an LLM, which adds a judgement step and its own error
rate to a measurement that could otherwise be exact.

**Gemini needs this differently.** Its realtime audio channel and its text channel do not
associate: a text question sent after the audio is treated as the content to describe — it
answered `SOUND: word / WORDS: What do you hear?`, echoing the question back. For Gemini both
tasks go in the system instruction up front ("respond first, then answer the question below"),
which keeps it to one session and one hearing of the audio, the same as the others.

## Scoring, per condition

Three sub-scores, each 0-1, averaged:

| | |
| --- | --- |
| **type** | 1 if the reported family matches the condition — laughter for happy, sigh for sad, `NONE` for neutral. Synonyms count: chuckle/giggle/laugh are one family, sigh/exhale/heavy breath another. |
| **count** | `max(0, 1 - abs(reported - actual) / actual)`. Exact is 1; one off on a 3-insertion item is 0.67; double or nothing is 0. |
| **location** | F1 over the set of turn numbers, reported against gold. Partial credit: hearing 2 of 3 in the right places beats naming one. |

Then average across the three conditions of an item, and across items for the model.

## The neutral condition is a false-alarm test

Neutral audio has no vocalizations at all, so the only correct answer is `NONE`. Anything
reported there is a hallucination and scores 0 on all three sub-scores. This is worth as much
as the positive cases: a model that reports laughter everywhere would otherwise look strong on
the happy items, and neutral is what exposes it. Report it separately too — "false alarms:
n/20" deserves to be visible on its own.

## What this is not

It does not measure whether the model *used* what it heard. A model can report every laugh
correctly and still answer the happy condition exactly as it answers the sad one; that gap is
what evals 2 and 3 are for. Read eval 4 as the precondition: if a model cannot hear the
sounds, its failure on eval 2 needs no further explanation — and if it can, that failure is
about pragmatics rather than perception.

## Relation to the clip vote

The clip vote asks these same four models about each vocalization **in isolation**. Eval 4
asks about the same sounds **in context**. Comparing them is free and informative: a model
that identifies a clip alone but misses it inside a conversation is being distracted by the
words, which is the failure this benchmark exists to measure.

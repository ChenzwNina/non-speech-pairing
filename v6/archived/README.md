# Superseded work

Nothing here is used. It is kept because the current design is only legible against what it
replaced, and because two of these were retired for reasons worth not rediscovering.

| | |
| --- | --- |
| [transcript_v1/](transcript_v1/) | `prompt.txt` + `generate.py`, then `spoken.py` for register |
| [transcript_v2/](transcript_v2/) | `plan_transcripts.py` + `transcript_planner.txt` |
| [eval_v1/](eval_v1/) | the rubric and pragmatic-MCQ evaluation stages |
| [audio/](audio/) | takes for the retired 20-item dataset |
| [data/](data/) | the datasets and intermediate outputs all of the above produced |

## transcript_v1 — four turns, tag inside a line, register fixed afterwards

The writer prompt was used verbatim as supplied. `spoken.py` then rewrote each transcript into
speech with GPT-4o: 807 words to 808, contractions 15 to 31, 65 of 80 turns reworded. Its
instruction was hardcoded in the script rather than kept as a versioned file, which is why
`data/pairs_spoken.json` records no hash for it and reading the script is the only way to know
what it was told. The current pipeline folds register into the writing prompt instead.

## transcript_v2 — planned the conversation, then attached the sound

Two faults, found in that order.

It was passed each vocalization's default reading as an anchor, and the anchor took: every laugh
came back framed as comic absurdity and every sigh as resigned acceptance, 12 out of 12 each.
That makes the pragmatic question answerable by naming the sound and applying a rule.
`data/plans_with_default_reading.json` is that run, kept as the only measurement of what the
input did.

And it planned the conversation first, attaching the sound afterwards, which produced turns like:

```
5  A: Yeah, I kept her number. I paid twelve dollars for it. (gasps)
```

The speaker is gasping at information he is himself delivering. Sounds are not interchangeable
in *when* they can be produced — a gasp is the instant of contact with something and cannot be
made about what you already know, while a sigh has no such requirement — so attaching the sound
last lets the strict cases fail silently. `data/transcripts_tag_at_end.json` and
`data/transcripts_v2_placement.json` are the two attempts to patch it before the ordering itself
was changed.

## eval_v1 — rubrics written three-at-once, pragmatic as multiple choice

The rubric writer saw all three versions in one call and returned three rubrics with a
`contrastive_requirement` field. That guaranteed the contrast and destroyed it as evidence: a
writer that knows it is looking at a laugh *and* a sigh can always phrase two requirements that
differ, whether or not the conversation supports the difference. `data/rubrics/` holds what it
produced — nine of twenty items drew an ambiguity flag or a review note, `scream` accounting for
most of them.

Pragmatic understanding was a four-option multiple choice with written distractors. It is now
free response judged against three acceptable interpretations, so a model that holds a
defensible minority reading is not marked wrong for it.

The two judge prompts went with them: the absolute content judge scored against a rubric shape
that no longer exists, and the tone judge scored 1-5 against a prescribed profile where the
current design asks only whether a clearly-wrong tone is present.

## audio — 120 takes for the retired dataset

Rendered from `data/pairs_spoken.json`. **They share item ids with the current dataset and are
not its audio**: `v6_01a` here is a different conversation from `v6_01a` in
`out/transcripts.json`. That is why they had to be moved rather than left in place —
`make_audio.py` skips takes already on disk and would have spliced these into the new items
without a word.

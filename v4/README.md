# v4 · One sound, two framings

**The same spoken dialogue, heard twice, differing only in which non-speech vocalization a
silent third speaker produces.** Does a model hear the difference, and does its answer change?

Where [v3](../laughter_sigh_contrast_v3/) spliced laughter and sighs *inside* utterances and
asked whether models use them, v4 makes the vocalization a turn of its own, produced by a
speaker who never says a word, and widens the inventory from two sounds to eight emotions.

## The design in one example

```
Speaker A: My receipt was higher than the price on the board.
Speaker B: Did you point it out before you left?
Speaker A: The manager looked at it and said they would take care of it.
Speaker C: <relief>   |   <anger>
Speaker B: Then I guess that's what goes through.
```

Every word is identical across the two conditions. Only the sound in speaker C's turn differs.
That last line — *"Then I guess that's what goes through"* — reads as acceptance after a
favourable resolution, or as resignation after being brushed off, and nothing in the transcript
decides which.

Speaker C never speaks: no line before the sound, none after, none anywhere. A speaker who also
talks would give the listener lexical evidence about the same person's state, which is the
evidence this design is trying to remove.

## What is here

| | |
| --- | --- |
| [seeds.py](seeds.py) | samples scenarios from all 32 EmpatheticDialogues labels |
| [generate.py](generate.py) | writes one shared transcript plus an insertion point; builds both conditions from it |
| [check_corpus.py](check_corpus.py) | plays each recording to a model and asks which emotion it is |
| `VocalizationsCorpus/` | 121 recordings, 8 labels, 4 speakers, about a second each |
| [out/pairs.md](out/pairs.md) | the pairs, readable |

The vocalization inventory is four positive labels — achievement, amusement, pleasure, relief —
and four negative — anger, disgust, fear, sadness. Each pair takes one from each side, so the
two conditions differ in emotional category rather than in intensity.

## Why the transcript is written once

The writer never sees two conditions. It returns the spoken turns and one insertion point, and
the code builds both versions. Five of the design's constraints are then true by construction
rather than being things a validator might miss: identical transcript, identical speakers,
identical turn order, exactly one vocalization, identical placement.

What remains to check is what construction cannot guarantee:

- **the silent speaker is silent** — no spoken line anywhere
- **the labels cross valence** — one positive, one negative
- **the words do not settle the emotion** — a lexicon rejects "I'm so relieved", "that's
  hilarious", and emotion adjectives generally
- **no speaker is named in the dialogue** — a pilot line read *"this one has C's name on it"*,
  which becomes a spoken letter in the audio and announces a third participant the listener
  should simply hear

The third of those is the experiment. If the words already decide the framing, a model can
score well without hearing anything.

## Seeds

v3 drew only from `embarrassed`, the label that reads both ways on its own. v4 does not need
that: the contrast is carried by the sound, so the scenario only has to be something two people
could plausibly discuss, and sampling opens to all 32 labels. `devastated` and `terrified` are
held out — those scenarios cannot honestly carry an `amusement` or `pleasure` framing.

## State

40 pairs, every one accepted on the first attempt, spanning 14 of the 16 possible cross-valence
contrasts. The distribution is uneven — `pleasure` takes the positive slot in 16 and `fear` the
negative in 17 — because the writer chooses the pair it finds most natural, as specified. A
balanced design would mean assigning each item a target pair in advance.

**Corpus screening is the open question.** Eight-way identification runs at 68%, but that is the
wrong measure here: every pair is positive against negative, so only a slip *across* valence can
flip a framing, and those are 9%. `anger` scores 17% eight-way while landing on the correct side
12 times out of 12, its confusion being entirely with `disgust`. `fear` is the real risk at 67%,
with three of twelve heard as `amusement` — and `fear` is the most-used negative label.

Not yet built: audio assembly, testing, evaluation.

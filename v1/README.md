# v1 · A vocalization as an entire turn

**Can S2S models detect standalone non-speech vocalizations that occupy an entire
conversational turn, and predict the response that should follow them?**

Two people talk for four turns. The fifth turn is one person's **sound alone** — a gasp, a
grunt, laughter, a sigh, a sob, a yawn — with no words at all. The sixth turn is the reply
that sound calls for.

Each item exists as a **pair**: identical setup, identical wording up to turn 5, and two
different vocalizations there. Because the words are frozen, only the sound can decide which
reply comes next.

```
1-3  A   setup, word-for-word identical across the pair
4    A   the trigger — the reveal B reacts to. Never a question
5    B   the vocalization alone, spliced in as a real recording
6    A   the reply that sound selects. Differs between the two versions
```

## The two questions

Both are asked in one session, after playing the audio once, which stops at turn 5:

1. **Which vocalization was that?** Six options, shuffled. Chance 17%.
2. **Which reply comes next?** The pair's two turn-6 lines, shuffled. The distractor is the
   sibling version's reply, so everything up to the sound is identical audio. Chance 50%.

Question 1 is the *interpretation*, question 2 the *response* — the pairing between them is
the point. A model that names the sound correctly and then picks the wrong reply has heard
it without understanding what it meant.

## Result

`gpt-realtime-2.1`, 28 items: **Q1 24/28 = 86%. Q2 21/28 = 75%.** Both correct on 19/28.

Q2 was 79% when Q1 was right and 50% — chance — when it was wrong, though only four items had
Q1 wrong, so treat that split as suggestive.

By vocalization, `sigh` is the outlier: recognized 4/5 but **1/5** on the reply, consistent
with its meanings spanning relief through frustration, which point at opposite next moves.
Confusions stay within family — grunt → sigh or laughter, laughter ↔ sigh — while gasp, sob
and yawn were never missed.

## What is here

```
experiment/          generation, audio, and the listening eval
  out/pairs.json     the pairs, with each version's interpretation and reply
  out/audio_prompt/  the eval input — ends at the vocalization, 14.9-25.0s
  out/audio_full/    the same plus turn 6
  out/themes/        family / school / work variants
web/viewer_base/     analysis site for the base set
web/viewer_themes/   analysis site for the theme sets — open index.html
```

Turn 5 is always a **real recording** drawn from `audio_non-speech/`, least-used-first, never
synthesized. Turns 1–4 and the reply are ElevenLabs `eleven_v3`.

## How the pairs were kept honest

A second model pass audits eight properties and rebuilds an item up to four times: the trigger
must be the last shared turn, both vocalizations must be natural there, the text alone must
not give the answer away, the two replies must commit to different actions, and — the test
that does most of the work — **swapping the replies must clearly make the dialogue worse**.

That last one catches items built on an arbitrary two-option choice, where a gasp is no more
"put it first" than laughter is.

14 of 15 contrasts survived. `gasp`–`sob` failed after four attempts: both are high-arousal
reactions to significant news, so they kept motivating the same next move.

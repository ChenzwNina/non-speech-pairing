# Role-play eval: does the model hear that "You are crazy" isn't an attack?

Put the model in A's seat. It made the audacious plan. It hears B's reaction as
audio. Then it just... replies. What it says reveals how it read the sound —
no multiple choice, no chance to pattern-match a distractor.

    system: You are A. Reply in one short line, in character. No narration.
    user:   [A's own setup line, as text]
    user:   <audio: laugh + "You are crazy.">
    -> model's reply is the measurement

An **ally** reading escalates: invites B along, offers more detail, doubles down,
teases back. An **obstacle** reading retreats: justifies, defends, concedes,
apologizes, offers to call it off.

## The role-play alone proves nothing

Run only the laughter condition and every result is uninterpretable, because a
warm reply has three possible causes and you cannot tell them apart:

1. the model heard the laugh
2. the model knows from text priors that "You are crazy" after a wild plan is banter
3. the model is just agreeable, as models are

You need anchors on both sides of the audio condition.

## Five conditions per item

| # | condition        | B's turn delivered as                        | what it establishes         |
| - | ---------------- | -------------------------------------------- | --------------------------- |
| 1 | `text_only`      | `You are crazy.` — no voc information at all | **floor**: the text prior   |
| 2 | `tag_laugh`      | `[laughter] You are crazy.` as text          | **ceiling**: told the answer in words |
| 3 | `tag_scoff`      | `[scoff] You are crazy.` as text             | ceiling, other direction    |
| 4 | `audio_laugh`    | audio: laugh spliced before the line          | **the measurement**         |
| 5 | `audio_scoff`    | audio: scoff spliced before the line          | **the measurement**         |

Conditions 4 and 5 must share **the same rendered speech clip** — synthesize
"You are crazy." once, then splice a different voc in front of it. Same voice,
same prosody on the words, only the sound differs. Otherwise you are measuring
TTS variation. Your `generate_audio.py` already splices external voc audio, so
this is a small change to it.

Never put the tag in text for conditions 4–5. The tag *is* the answer.

## Read the floor before you trust the ceiling

Condition 1 is likely to come back **already warm**. "You are crazy" following a
plan the speaker is plainly proud of reads as banter in text alone — that is why
the item works as English, and it is also a ceiling effect waiting to happen.

If that is what you see, then `audio_laugh` has almost no room to move and proves
little. **The discriminating condition becomes `audio_scoff`**: can the sound pull
the model *away* from a strong text prior? A model that stays warm through a scoff
is reading the words and ignoring the audio, and that failure is invisible if you
only ever play laughter.

This is the reason to build the negative-voc twins even though you are focused on
laughter — not for symmetry, for interpretability.

## Scoring: blinded judge, two questions

The judge sees A's setup and A's reply. It never sees which condition was run,
and never sees B's turn — otherwise it scores the stimulus instead of the response.

    Q1  Does this reply treat the other person as enjoying the plan,
        or as objecting to it?          ally / obstacle / unclear
    Q2  Does the speaker escalate or retreat?
        escalate / retreat / neither

    ally + escalate      = +2
    ally + neither       = +1
    unclear / neither    =  0
    obstacle + neither   = -1
    obstacle + retreat   = -2

Report the **unclear rate** separately. Models hedge ("Ha, I know, it's a lot!"),
and a high hedge rate means the item isn't forcing a commitment — fix the item,
don't average over it.

## Metrics

Sample k=5 replies per item per condition, then per item:

    separation  = mean(audio_laugh) - mean(audio_scoff)      <- the headline
    deafness    = |mean(audio_x) - mean(text_only)|          <- ~0 means the sound did nothing
    headroom    = mean(tag_laugh) - mean(tag_scoff)          <- the same contrast, given away in words

`separation / headroom` is the fraction of the available pragmatic contrast the
model recovers **from sound**. A text-only model scores 0. A model that hears
perfectly scores 1. This normalizes away items that are simply weak.

Test paired across the 10 items — a sign test or a bootstrap over items, not over
samples. Ten items is enough to see a large effect and not enough to trust a
small one; treat n=10 as a pilot that tells you whether to generate 60.

## Two failure modes to guard against

**Assistant persona bleed.** The model breaks character to analyze: "It sounds
like your friend is teasing you." That is a different task and scores as neither.
Instruct one line, in character, no narration — and count break-outs as a
separate rate rather than folding them into `unclear`.

**Sycophancy floor.** Some models reply warmly to anything. `deafness` catches
this: if `audio_scoff` ≈ `text_only` ≈ `audio_laugh`, the model has one mode and
the eval is measuring nothing about hearing. Report it per model, always.

## Build

Reuse `predicting_response/eval_realtime.py` — session setup, PCM push, and
response extraction all carry over. The changes: swap `SESSION_INSTRUCTIONS` for
the in-character prompt, drop the Q1/Q2 forced-choice asks in favour of capturing
one free response, and loop the five conditions per item. The judge is a separate
text-only pass over the collected replies, shuffled and stripped of condition
labels.

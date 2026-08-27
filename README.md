# Non-speech vocalization benchmark

Can a speech-to-speech model use laughter, sighs and other non-speech sounds as meaning — or
does it only hear the words?

Three versions of that question, each a folder. `v1` and `v2` are the exploratory
probes that shaped it; **1.0** is the benchmark they led to.

| | question | state |
| --- | --- | --- |
| **[v1](v1/)** | Can a model identify a vocalization that occupies an **entire turn**, and predict the reply it calls for? | 28 items, evaluated · **86% / 75%** |
| **[v2](v2/)** | Given a scenario, the model proposes something and the user answers with **only a sound**. Does its next turn change? | ~40 conditions, read by eye |
| **[1.0](1.0/)** | The same conversation heard three ways — plain, through laughter, through sighs — with the words held **physically identical**. | 20 items × 3 × 4 models, four evals |

`audio_non-speech/` holds the real recordings — gasp, grunt, laughter, sigh, sobbing, yawn —
used as source material throughout. `archive/` holds earlier experiments and probes.

## What the three found

**v1 — models can do this when the answer is a menu.** Given a vocalization alone and two
candidate replies, `gpt-realtime-2.1` identified the sound 86% of the time and picked the
right continuation 75%. Perception is not the bottleneck.

**v2 — a sound alone moves the model; words override it completely.** With no words competing,
the model changed course in 5 of 5 trials. In 20 trials where words and sound conflicted, it
went with the sound **zero** times — while the identical message stated in text was acted on
5 of 5. One exception: playful mock-reproach after a tempting proposal, where laughter is the
conventional carrier, moved it 5/5 against 2/5 without.

**1.0 — they hear the sounds and answer as though they had not.** Models identify the
vocalizations 97% of the time, then produce replies that a judge can barely tell apart
(60–63% against a 50% chance line) in a tone that does not shift at all (18–32% against a 27%
constant-register baseline). One model was heard as "sympathetic" on 14 of 20 items told
through laughter.

## Reading order

Start with [1.0/PIPELINE.md](1.0/PIPELINE.md) — it describes how the current dataset is built,
stage by stage, for someone who has not seen this project. Each folder's README covers its own
design, results and caveats.

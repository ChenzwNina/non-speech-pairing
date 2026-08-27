# 2.0 · Non-speech vocalization benchmark

**Can a speech-to-speech model use laughter and sighs embedded inside spoken utterances to
decide how to respond?**

The same conversation, heard three ways — through laughter, through sighs, and plainly — with
the words held physically identical. 1.0 established that models *hear* the sounds (97%) and
then reply as though they had not. 2.0 rebuilds the parts of 1.0 that could not support that
conclusion firmly: the ground truth, and the density of the signal being tested.

[SPEC.md](SPEC.md) is the authority for what this version does, transcribed from the design
document. Where the code and the spec disagree, the code is wrong.

## What changed from 1.0

The two changes that matter are about measurement, not scale.

**Gold is written from the transcript that was actually rendered.** 1.0 wrote its gold before
placement, as a prediction of how sounds would land in a conversation that did not exist yet,
then scored tone by exact match against one of six labels. 2.0 writes the gold after the
sounds are in the transcript, as two free sentences — how the speakers are treating the story,
and the tone a third speaker should adopt — with GPT-5.6-Terra writing and Claude Opus 5
verifying. The load-bearing check is a **swap test**: exchange the happy and sad gold, and both
must read as wrong. Gold that survives the exchange is not distinguishing the conditions, and
no score computed from it can either.

**Density went up.** 1.0 drew 0.5–1× the turn count, leaving most turns bare. 2.0 draws 1–2×,
so every turn carries at least one on average: **205 slots per condition** across 20 items,
against 1.0's 95.

Also: placement moved from a script to GPT-4o (which chose mid-utterance 83% of the time, where
1.0's concern had been collapse to turn boundaries); clip verification went from a four-model
majority to **two random judges who must agree**; and the four evals were rewritten — pairwise
appropriateness by three text judges, tone as a 0–4 rating by a leave-one-out speech panel, and
two new multiple-choice questions for pragmatic function and perception.

## Pipeline

| stage | script | what it does |
| --- | --- | --- |
| 1–2 | [dialogues.py](dialogues.py) | 20 `embarrassed` situations and their 4–8 turn dialogues, **reused from 1.0** — both stages are identical between versions, and every turn is verified to still match the take rendered for it |
| 3–4 | [place.py](place.py) | draws the count (1–2× turns), then GPT-4o chooses each slot — which turn, after which word — and writes the laughter and sigh forms |
| 5 | [write_gold.py](write_gold.py) | GPT-5.6-Terra writes function and tone from the spliced transcript; Opus 5 verifies, swap test included |
| 6–7 | [make_audio.py](make_audio.py) | turn audio reused in place from 1.0; one clip per slot per condition, levelled against the speech it will sit inside |
| 8 | [verify_clips.py](verify_clips.py) | two S2S judges drawn per clip must both hear the intended sound, else a new take, three rounds |
| — | [preflight.py](preflight.py) | plays every provider a real sentence and requires the words back, before any verdict is trusted |

**One set of slots serves both conditions.** Each slot gets a laughter form and a sigh form, so
happy and sad differ only in which sound is spliced in — same words, same timing, same take.
Letting each condition choose its own positions would give up the ability to attribute a
difference to the sound.

## Grok

Grok is in 2.0. It was excluded from 1.0's results because its audio never arrived: it answered
190 clip questions confidently while hearing nothing, and "I heard no laughter" is
indistinguishable from "I heard nothing" unless you ask it to repeat words it should have
heard. Under **manual turn control** — `turn_detection` off, explicit `input_audio_buffer.commit`,
session closed as soon as the reply goes quiet — it answered 11 of 12 clips correctly where
server VAD managed 5 of 10 and no sigh ever answered, and it now passes the preflight speech
check at 100%.

One deterministic failure survives: on some inputs the audio commits and then `response.create`
is dropped in silence — no `response.created`, no error, no `response.done`. Louder audio does
not fix it. `providers.py` bounds the wait and retries in a fresh session.

## State

Built and run: stages 1–8. Gold is written but **unverified** — the Anthropic key has no
credit, so the Opus 5 pass has not run.

Not yet built: stage 9 (splicing the three conditions), stage 10 (the Q3 option sets), stage 11
(testing), and the four evals.

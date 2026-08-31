# Non-speech vocalization benchmark — pipeline

**The question.** A speech-to-speech model hears two people talking about something that went
wrong. The words never change. Only the non-speech sounds around them do — laughter in one
version, sighs in another, nothing in a third. Does its reply change too?

Every stage below exists to make that the *only* thing that changes.

**Sample** → **Write** → **Place** → **Mark** → **Synthesize** → **Verify** → **Test** → **Score**

### Words used throughout

| term | meaning |
| --- | --- |
| **item** | one situation and the conversation written about it. There are 20 |
| **condition** | one of the three versions of an item: neutral, happy, sad |
| **turn** | one person's contribution to the conversation. Items have 4–8 |
| **clip** | a short recording of a single laugh or sigh, roughly half a second to two seconds |
| **trial** | one model hearing one condition of one item, once |

---

### 1 · Sample

Pick situations that could honestly be told either way — as a funny story or as a
humiliating one. If a situation only works one way, no amount of laughter or sighing will
change how a listener should respond to it, and the item measures nothing.

| | |
| --- | --- |
| **in** | a public dataset of everyday situations people described, each tagged with an emotion |
| **task** | keep only the ones tagged *embarrassed* — split trousers, a forgotten wallet, calling a teacher "Mum" — and drop entries too short to build a conversation from. Sample 20 |
| **out** | 20 situations |

*Deliberately excluded: labels like devastated or terrified. A laughter version of "my mother
died" is incoherent, and in a published benchmark, tasteless.*

### 2 · Write

Turn each situation into a conversation between two friends whose **words give nothing away**.
Read on the page, the conversation should not tell you whether this is funny or bleak. That
ambiguity is what leaves room for the sounds to decide.

| | |
| --- | --- |
| **in** | one situation |
| **task** | a language model writes the conversation once — 4–8 turns, two speakers, no laughter or sighs written into the words. Automatic checks throw out drafts that leak the mood into the wording |
| **out** | one conversation per item. Nothing else: placement comes next, and the gold answers after that |

*The conversation is written once, not three times. The versions are built by adding sounds to
it, so the words are identical across conditions by construction rather than by inspection.*

### 3 · Place

Decide how many sounds go into each conversation and where. Done by a script rather than by
the model, because the model was bad at it: asked to choose freely, it picked three
vocalizations for almost every item and put one in the very first turn every time — regular
enough that a guesser who never listened could score well.

| | |
| --- | --- |
| **in** | the conversation, and a map of where every word and pause falls in the recording |
| **task** | randomly choose a number of sounds between half the turns and all of them, then randomly choose which turns get one and whereabouts in the turn: **beginning, middle, or end**. Middle is only offered where the speaker actually breaks mid-sentence — at a comma or between two sentences — because that is the only place a sound can go without cutting across connected speech |
| **out** | a plan: which turn, which position, which sound. The happy and sad versions use the *same* plan, differing only in laughter versus sighs |

### 3.5 · Mark

Write down what a good reply looks like — **after** the sounds have been placed, reading the
conversation exactly as it will be heard.

| | |
| --- | --- |
| **in** | the conversation with every laugh and sigh written in at the point it will occur |
| **task** | a separate model call reads one version and says what a third person should say next, in what tone, and which sounds would be wrong in a reply. The three versions are written in separate calls, so each is judged on how it actually sounds rather than by contrast with the other two |
| **out** | the "right answer" notes used to score evals 2 and 3 |

*This used to happen back in stage 2, before anything was placed — which made it a prediction
about how the sounds would land rather than a reading of where they actually did. The writer
also had them all in view at once, which produces gold defined by contrast: "unlike the happy
version, here…"*

### 4 · Synthesize

Build the audio so that the speech is **physically the same recording** in all three versions.

| | |
| --- | --- |
| **in** | the conversation and the placement plan |
| **task** | synthesize each turn once, in a deliberately flat delivery, and keep the timing information that comes back with it. Synthesize each laugh and sigh separately, checking that each one is long enough, loud enough, and not much quieter than the speech around it. Then assemble the three versions from those same recordings, cutting a turn at a natural pause where a sound belongs mid-sentence |
| **out** | 60 finished recordings (20 items × 3 versions), plus the individual pieces and a record of exactly what is where, to the millisecond |

*Neither the speech nor a sound is ever synthesized twice for different versions. A second
take would differ in pace and pitch, and then a model's behaviour could be responding to
delivery rather than to the sound.*

### 5 · Verify

Confirm every laugh really sounds like a laugh and every sigh like a sigh — **before** any of
it is used to test anything.

| | |
| --- | --- |
| **in** | each short clip on its own, with no surrounding conversation |
| **task** | ask four different speech models a single yes-or-no question: *is this the sound of a person laughing?* (or sighing). Three of four must agree. If they do not, the clip is regenerated and re-asked, up to three attempts. Anything still unresolved is set aside for a person to listen to, never silently dropped |
| **out** | a verdict for every clip, and replacements for the ones that failed |

*This is quality control on the material, not a measurement of the models. Text-to-speech
fails in ways that are invisible in a waveform — it sometimes reads the instruction aloud
("Sigh.") instead of performing it.*

### 6 · Test

The actual experiment. A model is dropped into the conversation as a third person and has to
speak.

| | |
| --- | --- |
| **in** | one recording, plus one sentence saying what the conversation is about. No transcript, no labels, no hint that other versions exist |
| **task** | in a fresh session each time, the model hears the conversation and takes its turn out loud. Only afterwards is it asked two further questions: whether it heard any laughter or sighing, and how it would describe the atmosphere |
| **out** | for every trial: what the model said, as text and audio, plus its two answers |

*The order is the design. Asking about sounds first would announce that sounds are the point
and turn the reply into a demonstration.*

### 7 · Score

Four separate questions about what the models did.

| | |
| --- | --- |
| **in** | every reply, as text and as audio, and the "right answer" notes from stage 2 |
| **task** | **1** — does the reply contain a sound that would be wrong here, like laughing in response to a sad telling? Three models listen and vote. **2** — does the reply fit *this* version better than the replies given to the other two versions? A judge that can see which version it is ranks them, three times, with the order shuffled. **3** — does the reply carry the intended tone? Same listening pass as eval 1. **4** — did the model hear the sounds at all? Compared straight against the placement plan |
| **out** | a score per model per eval, with the disagreements recorded |

*Eval 4 is the precondition for the others. If a model cannot hear the sounds, its failure on
eval 2 needs no further explanation. If it can hear them and still ignores them, that is the
finding.*

---

## The three conditions

One item is one conversation in three versions:

| condition | audio | vocalizations |
| --- | --- | --- |
| **neutral** | the turn takes, concatenated | none |
| **happy** | the same takes, with laughter spliced in | 2–8 |
| **sad** | the same takes, with sighs spliced in | the same 2–8, same slots |

The speech is **the same recording** in all three. Happy and sad share identical slots — same
turns, same insertion points — so they differ in the *kind* of sound and in nothing else.
Neutral has zero in those slots, which makes it a false-alarm test rather than a third variant.

---

## Stage 1 — seeds

`out/seeds.json` · no script (one-off sample)

20 situations from **EmpatheticDialogues** `train.csv` (not in this repo; refetch from
[facebookresearch/EmpatheticDialogues](https://github.com/facebookresearch/EmpatheticDialogues)),
all labelled `embarrassed` — the
emotion whose situations read both ways. 563 unique candidates, 520 after dropping fragments,
20 sampled at seed 0.

Labels like *devastated* and *terrified* are excluded by design: a laughter condition over
"my mother died" is incoherent, and in a published benchmark, tasteless.

Source is CC BY-NC 4.0.

---

## Stage 2 — transcripts

`generate.py` → `out/transcripts.json`, `out/transcripts.md`

`gpt-5.6-terra`, high effort. **The writer never writes three versions.** It writes the
conversation once, and the conditions are insertion plans over it — so identical wording is
true by construction rather than something to check and rebuild when it drifts.

Per item it returns:

- `turns` — 4–8 turns, alternating A/B, A being the person it happened to
- `neutral` / `happy` / `sad` — what the third speaker should say next, a tone label from a
  fixed six, and a `must_not_appear` list
- `situation_third_person` — the seed shifted out of first person ("**a speaker** was
  exercising in a yoga class and **their** pants split open")

Mechanical checks reject: brackets or written laughter in the neutral words, wrong turn count,
speakers out of alternation, and a laugh token in the sad plan. Turn count is drawn in the
script — `randint(4, 8)`, seed 0 — not chosen by the model.

---

## Stage 3 — placement

`replan_vocalizations.py` → rewrites the insertion plans in `out/transcripts.json`

Counts and positions are drawn in the script, seed 7. This stage exists because the writer
was bad at both:

| | asked the model | drawn in the script |
| --- | --- | --- |
| how many | 3 on 18 of 20 items, never 2 | `randint(ceil(turns/2), turns)` → 2–8 |
| density | 0.38–0.75 per turn, drifting with length | 0.50–1.00, scaling with length |
| where | turn 1 of **every** item | sampled turns, turn 1 not guaranteed |

The count anchoring mattered more than it looks: with placement that predictable, a strategy
of naming turn 1, the middle and the last turn — without listening to anything — scored 0.61
on the old location metric, higher than any model managed. That metric has since been dropped.

**Position within a turn** is start, middle, or end:

- **middle** exists only where the utterance has an interior punctuation break. Ordinary word
  gaps here run 27–67 ms; a comma or sentence break runs 160–320 ms, which is where a
  vocalization can sit without cutting across connected speech.
- Where several breaks exist, the one nearest the utterance midpoint is used.
- 58 of 128 turns (45%) offer a middle. Drawn: **start 42, end 42, middle 11**.

Token inventory is fixed and excludes `hehe` (a thin titter rather than a laugh). A bare
`[sigh]` is not synthesizable — ElevenLabs rejects it with *"All inputs must include non-empty
text after removing speaker tags"* — so every token is a tag plus a written sound.

`--placement-only` moves insertion points and changes nothing else, so clips and their
verification survive.

---

## Stage 4 — audio

`make_audio.py` → `out/audio/`, `out/audio_turns/`, `out/audio_voc/`, `out/audio_manifest.json`

**128 turn takes**, ElevenLabs `eleven_v3`, stability 0.55 — deliberately flat, since the same
take has to be honest in all three conditions. Synthesized with `convert_with_timestamps`, so
each take arrives with **character-level alignment**; the space between two words has its own
start and end, which is what makes mid-utterance splicing possible at all.

**190 vocalization clips**, stability 0.30 so the voice actually laughs. Gates before use:

| check | rejects |
| --- | --- |
| duration 0.4–3.5 s | empty generations and rambling ones |
| level above −40 dB | silence |
| within 10 dB of the item's speech | a −35 dB sigh under −20 dB speech is a defect in the stimulus, not a hard item |

**Sewing.** Turn gap 0.32 s, splice gap 0.18 s. For a middle placement the take is cut at the
midpoint of the reported silence and rebuilt as `[0→t] + gap + clip + gap + [t→end]` — both
halves from the same file, so the spoken samples stay identical across conditions.

Two guards worth keeping:

- **Turn takes are keyed to their text.** Regenerating one item's transcript once left its
  old audio in place: `emb_002` said "I was midway through a yoga class when I heard a seam
  give way" while its transcript had been rewritten to something else. Nothing noticed.
- **`--only` merges** into the manifest instead of replacing it.

Output: 60 condition files, neutral 22.9 s mean, happy 31.3 s, sad 32.5 s.

---

## Stage 5 — clip verification

`verify_clips.py` → `out/clip_verdicts.json`, `out/clip_review.md`

Four models, one yes/no question each, at each model's **default** effort:

> *is this the sound of a person laughing?* / *…sighing?* — **YES / NO**

Three of four yes is a pass. Below that the clip goes back to ElevenLabs for another take and
is re-voted, up to **three rounds** (the original plus two remakes). Anything surviving three
failures is listed for a human, never deleted.

**Result: 190/190 passed** — 187 on round 1, 2 on round 2, 1 on round 3.

An earlier open-question version ("what do you hear: laugh / sigh / breath / word / other")
turned into a vocabulary argument: gemini called sighs "breath", openai called `ugh` a "word"
because the token contains a written syllable. The yes/no form has no room for that.

---

## Stage 6 — testing

`test_models.py` → `out/trials.jsonl`, `out/responses/`

**4 models × 20 items × 3 conditions = 240 trials**, each a fresh session so nothing learned
from the happy version can inform the sad one. Three things happen in order, and the order is
the design — asking about sounds first would tell the model that sounds are the point.

**1. Session instructions**

> You are having a conversation with two people. You will hear them talking to each other.
>
> Here is what the conversation is about: {situation}
>
> When they finish, it is your turn to speak. Respond naturally as the third speaker in the
> conversation.

Then the audio, and nothing else. No transcript, no tags, no mention of other versions. The
situation is identical across conditions: it says what happened, never how anyone feels about
it.

**2. What did you hear** — asked only after the turn exists

> Apart from the words, did you hear any non-speech sounds in the conversation:
> A. laughter · B. sigh · C. neither · D. both
>
> `ANSWER: <letter>` then `VOCALIZATION: <name> | COUNT: <how many times>`

**3. Atmosphere**

> How would you characterize the overall conversational atmosphere?

Captured per trial: the reply as **text and audio**, the A/B/C/D answer with counts, and the
atmosphere text.

---

## Stage 7 — evaluation

| eval | script | question | scoring |
| --- | --- | --- | --- |
| **1** | `eval13_response_audio.py` | does the reply contain a sound that should not be there? | 3 audio judges, majority, against the per-condition must-not list |
| **2** | `eval2_appropriateness.py` | does the reply fit *this* condition? | pairwise against the other two conditions, order randomized, 3 rounds, majority. **Chance 50%** |
| **3** | `eval13_response_audio.py` | does the reply carry the intended tone? | same listening pass, majority label against the gold label |
| **4** | `eval4_perception.py` | did it hear the sounds at all? | type and count against the insertion list — **no judge, no adjudication** |

Eval 2's judge sees the tagged transcript, so it knows the condition: a gold-standard ranking,
not a blind discrimination test. Evals 1 and 3 share one listening pass per judge, and no model
judges its own reply.

Answers are constrained to a letter or a label from a fixed set so majorities are counted
mechanically. Two LLM adjudication passes were removed this way — an LLM asked whether three
prose descriptions "mean the same thing" is a judgement call standing in for arithmetic, and it
brings its own error rate into the measurement.

Eval 4 is the precondition for the rest: if a model cannot hear the sounds, its failure on
eval 2 needs no further explanation — and if it can, that failure is about pragmatics.

---

## Effort settings

Raised only where the benchmark measures the model.

| model | testing | verification | evaluation |
| --- | --- | --- | --- |
| `gpt-realtime-2.1` | `reasoning.effort = high` | default | default |
| `grok-voice-think-fast-2.0` | `reasoning.effort = high` | default | default |
| `gemini-3.1-flash-live-preview` | `thinking_level = high` | default | default |
| `qwen-audio-3.0-realtime-plus` | default — unsupported | default | default |

`thinking_level` needs `google-genai` 2.x and therefore python ≥ 3.10. On python 3.9 pip
silently caps the SDK at 1.47.0, where the field does not exist — an upgrade there *looks*
like it worked and quietly hands back the old parameter set. **Run everything from the
`gemini-live` conda env (python 3.11).**

---

## Known problems

**Grok's 190 clip verdicts are void.** They were collected while the audio was never
arriving — asked for reasons, it answered *"No audio clip is provided in the query"* on 10 of
10 sampled clips. Every verdict meant "I heard nothing", and the 31% agreement rate computed
from them measures nothing. **Those verdicts are not used anywhere in the results above.**

**Manual turn control fixes the transport** (2026-08-26). With `turn_detection: None`, an
explicit `input_audio_buffer.commit`, and the session closed as soon as the reply goes quiet,
grok answered **11 of 12** clips across two passes — and every answer was correct, laughter
YES and sighs NO. Under server VAD the same clips scored 5 of 10 and no sigh ever answered.
The remaining failure (`emb_001_sad_0_t01_start.mp3`, `[sigh] uhh`) is deterministic and
narrow: the audio is received and committed, then `response.create` is silently dropped — no
`response.created`, no error, no `response.done`. Louder audio does not fix it, so it is not
an energy threshold; +12 dB got 670 ms of speech detected and still no response while +18 dB
got 58 ms. Grok is usable for 2.0 given a retry on drop; the 1.0 numbers stay as collected,
without it.

**Billing is metered on something other than the audio we send.** The console reported ~66,000
seconds against this project. Counting decoded payload bytes at 24 kHz mono 16-bit — 48,000
B/s — the recorded calls could only have sent **2,473 s (0.69 h)**, and under 4.1 h even
assuming every call was retried six times. Measured directly, session wall-clock ran **5.2x**
audio-sent under a 25 s timeout, and for most of the project the timeout was 180 s, which
makes connection time the leading explanation. `audit_grok.py` measures both quantities and
keeps them in separate columns; it never infers duration from how long a socket stayed open.
Manual turn control drops the ratio to **2.0x**. Grok also reports no usage at all —
`input_tokens`, `output_tokens` and `total_tokens` all null — so per-call cost cannot come
from the API.

The general lesson is in `preflight.py`: before collecting anything from a provider, play it a
real sentence and require the words back. A model that cannot repeat a sentence it was just
played is not in a position to say whether it heard a sigh, and everything it says afterwards
looks exactly like data.

**Qwen has a 30-second input buffer** and most happy/sad files now exceed it, so qwen hears
long items as several consecutive input turns where the others hear one. Splits are placed at
turn boundaries from the manifest timeline, so no cut lands mid-word — but it is an asymmetry
that belongs in any writeup.

**Splicing is not amused delivery.** Perfect word control comes at the price of prosody:
speech-laughter lives in the phonation and cannot be inserted. This benchmark tests whether a
model can use a discrete vocalization, not whether it can hear an amused voice.

---

## Current state

| stage | state |
| --- | --- |
| seeds | 20 |
| transcripts | 20/20 valid |
| placement | drawn, seed 7 — start 42 / end 42 / middle 11 |
| audio | 128 takes + aligned, 190 clips, 60 condition files |
| clip verification | **190/190 passed**, nothing awaiting a human |
| testing | running — 203/240 at last check |
| evals 1–3 | written, waiting on the trials |
| eval 4 | script exists; last run was against the *previous* placement and prompt, so its numbers are stale |

## File map

```
out/seeds.json                 20 situations
out/transcripts.json           turns, insertion plans, gold answers, voc_plan
out/transcripts.md             the same, readable
out/turn_alignment.json        word timings per take — makes placement redraws free
out/turn_texts.json            what each take says, so stale audio cannot be reused
out/audio_manifest.json        every clip's level and gain; per-condition timeline with
                               each turn and vocalization's start/end and any cut point
out/audio/                     60 condition files — the stimuli
out/audio_turns/               128 takes + cut halves for middle placements
out/audio_voc/                 190 vocalization clips
out/clip_verdicts.{json,jsonl} the four-model vote, per round
out/trials.jsonl               one row per trial: reply, heard, atmosphere
out/responses/                 the models' spoken replies
```

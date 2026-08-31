# 2.0 — specification

Transcribed from `Experiment_Design_and_Evaluation_Documentation.pages` (source deck *Exp
Design and Results (1).pptx*, slides last updated 08/25/2026), sections 5 and 6. This file is
the authority for what 2.0 should do; where the code and this file disagree, the code is
wrong. Open questions are marked **[Q]** and listed again at the bottom.

**Research question.** Can S2S models detect and interpret non-speech vocalizations embedded
*within* a spoken utterance, and appropriately adjust their responses based on them?

Why embedded rather than standalone: v1 and v2 established that a vocalization presented as an
isolated turn is too easy — the model can work from the sound alone without using the
conversational context.

## Dataset and audio construction

| # | stage | model / tool | in → out |
| --- | --- | --- | --- |
| 1 | Seed scenarios | — | EmpatheticDialogues, label `embarrassed` → situation descriptions (20 sampled for initial testing) |
| 2 | Write dialogue | GPT-5.6-Terra | situation → 4–8 turn conversation between two friends, written **once**, content not revealing whether the situation is funny or bleak |
| 3 | Draw frequency | — | turn count → number of laughter/sigh occurrences, **randomly between 1× and 2× the number of turns** |
| 4 | Place and form | **GPT-4o** | frequency + script → where each vocalization goes (**after which word**) and its written form, as `[vocalization type] sound description`, e.g. `[laugh]haha` — ElevenLabs needs words alongside the tag |
| 5 | Gold answer | GPT-5.6-Terra writes · **Claude Opus 5 verifies** | transcript with laughter inserted; transcript with sigh inserted → (1) **function**: "How do the two speakers treat the story, based on the non-speech vocalization you observed?", one short sentence; (2) **expected tone** for a third speaker joining, one short sentence |
| 6 | Dialogue audio | ElevenLabs | script → conversation audio with two voice IDs (one male, one female) + character-level alignment |
| 7 | Vocalization audio | ElevenLabs | frequency, location, form → the laughter and sigh clips |
| 8 | Verify clips | 2 S2S models, drawn at random | clip → "Does the clip contain {vocalization}? A. yes B. no" |
| 9 | Splice | — | clips + locations + conversation audio → three conditions |
| 10 | Form gold answers for the transcript | — | **[Q1] this stage is blank in the document** |
| 11 | Test | 4 S2S models | three conditions → responses + three follow-up answers |

**Stage 5 gold and verification.** The gold is written by a separate model from the one that
wrote the dialogue, and only after the vocalizations are in the transcript, so it describes
what was actually rendered rather than predicting it. GPT-5.6-Terra writes one function
sentence and one expected-tone sentence per condition; **Claude Opus 5 then verifies** them
against the same spliced transcript. Proposed checks, since the document does not spell them
out **[Q8]**:

- the function is supported by the vocalizations actually present, not by the words alone
- the tone is one a third speaker could adopt, and follows from the function
- the happy and sad golds differ, and survive a **swap test**: exchanged between conditions,
  both must read as wrong (the same test v1 used on its gold pairs)
- neither sentence quotes wording that would make the Q3 option set guessable

Failing any check sends it back to the writer, up to 3 attempts, matching stage 8's convention.

**Stage 8 retry rule.** Both yes → keep the clip. Both no, or one yes and one no → regenerate
and re-judge with the same two models, up to **3 attempts**. If a judge does not respond, retry
once with the same audio; if it still does not respond, fall through to the regeneration step.

**Stage 9 conditions.** `happy` = with laughter · `neutral` = neither · `sad` = with sigh. All
three share the same transcript and the same conversation audio; the only difference is the
inserted laughter or sigh.

**Neutral is heard but not evaluated.** The tested model listens to the neutral audio and
responds, because that response is needed as a comparison in the Q1 ranking. Nothing else is
asked of it: no follow-up questions, no tone rating, no scoring. Every score in 2.0 is over the
happy and sad conditions only.

**Stage 11 models.** GPT-realtime-2.1, Grok voice think fast 2.0, Gemini 3.1 flash live, Qwen
Audio 3.0 Realtime Plus — all at **default** effort and thinking level. Grok requires manual
turn control with VAD off: under VAD it reports hearing no audio and the session hangs.

## Evaluation

### Q1 — answer appropriateness

Prompt to the tested model: *"You are going to listen to a conversation of two speakers. After
listening, respond as a third speaker in the conversation."* **The situation is given as
well**, as in 1.0 — the EmpatheticDialogues seed shifted out of first person, so the model
knows what the conversation is about without being told how to feel about it.

Each response is compared **pairwise, twice**: the response from the current condition (A)
against the response from the second condition (B), and A against the response from the third
condition (C). Judges see the transcript with the vocalization tagged and are asked "Which
response is more appropriate as a third speaker response in the conversation?" Response order
is randomized.

- **Judges:** text-based — Claude Opus 5, GPT-5.6-Terra, Grok-4.6. One judgement each; the
  response's score is the average of the three.
- **Scoring:** no predefined gold. +1 if the top-ranked response is the one the model actually
  produced for that condition, else +0.
- **Conditions scored:** happy and sad only. Neutral is excluded because both the happy and
  the sad response can plausibly follow it. Neutral responses still serve as comparisons.

### Q2 — tone alignment

A **leave-one-out S2S panel** listens to the response audio and rates whether its tone aligns
with the gold expected tone, **0–4** (0 = strongly mismatched, 4 = strongly matched). A model
never judges its own response, so each response is rated by the other three; the score is
their average. Gold is the one-sentence expected tone from stage 5, given to the judge as text.
Happy and sad responses only. The judge hears the response audio alone, not the conversation,
so the condition is not leaked to it **[Q3]**.

### Q3 — pragmatic function understanding

Asked of the happy and sad conditions only. After responding, the model is asked "How do the
two speakers treat the story?" with four
options: **A.** the answer written for the happy condition · **B.** the answer written for the
sad condition · **C.** wrong option 1 · **D.** wrong option 2. Scored against the gold by exact
comparison, +1 / +0.

Gold construction: when the transcript is written, an LLM answers "How do the two speakers
treat the story?"; a second LLM writes two additional wrong options. The condition-specific
option is the gold answer. **[Q4]**

### Q4 — perception

Asked of the happy and sad conditions only. After responding, the model is asked "What
non-speech vocalization did you hear in the conversation?" with four options: **A.** laughter ·
**B.** sigh · **C.** wrong option 1 · **D.** wrong option 2. Gold is set by condition:
happy → laughter, sad → sigh. Distractors are drawn from gasp / yawn / sob / grunt /
throat-clear, randomized per trial **[Q4]**.

## What changes from 1.0

| | 1.0 as built | 2.0 as specified |
| --- | --- | --- |
| frequency | `randint(ceil(turns/2), turns)` — 0.5–1× turns | **1–2× turns**, so every turn carries at least one |
| placement | drawn by script at punctuation breaks, to avoid a gameable pattern | **decided by GPT-4o**, after a named word |
| gold | written *before* placement, as a prediction; content + tone label from a fixed set + must-not-appear | written *from the spliced transcript* by a separate model, **verified by Opus 5**; **function sentence + expected tone sentence**, free text |
| clip verification | four-model majority vote | **two random models, unanimous yes**, ≤3 regenerations |
| test prompt | included the situation: "Here is what the conversation is about: …" | unchanged — situation still given, plus "respond as a third speaker" |
| conditions scored | all three | **happy and sad only**; neutral is heard and answered, then used only as a Q1 comparison |
| appropriateness | pairwise with majority voting | **two comparisons per response**, three named text judges, averaged |
| tone | exact match against one of six labels | **0–4 alignment** rated by a leave-one-out S2S panel that hears the audio |
| pragmatic function | not tested | **new 4-option MCQ** |
| perception | free-form `VOCALIZATION / COUNT` | **4-option MCQ**, gold by condition |

The two changes that address "the ground truth is not well defined": gold is now written from
the transcript that was actually rendered, and tone is a graded judgement against a written
expectation instead of a match against a label nobody committed to in advance.

## Decisions

Settled by the document plus your corrections of 2026-08-26:

1. **Test prompt keeps the situation.** As in 1.0.
2. **Gold is written by GPT-5.6-Terra and verified by Claude Opus 5**, both working from the
   transcript that already has the laughter and the sighs in it.
3. **Neutral is heard, never scored.** The model listens and responds; that response exists
   only to be a comparison in Q1.
4. **Stage 10 is the Q3 option set** — the gold function statement plus two distractors — not a
   separate step.
5. **Q4 distractors** drawn from gasp / yawn / sob / grunt / throat-clear, randomized per trial.
6. **Q1 is reported as the proportion of comparisons won**, keeping it on the same 0–1 scale as
   1.0's 60–63% so the two are comparable.
7. **Stage 4 uses GPT-4o**, per the document, even though the other writing stages use
   GPT-5.6-Terra.
8. **20 items**, matching initial testing.

Still open:

- **[Q8] The Opus 5 verification criteria** above are proposed, not specified. The swap test is
  the load-bearing one: if the happy and sad golds can be exchanged without either reading
  wrong, the gold is not distinguishing the conditions and nothing downstream can.
- **Qwen's 30-second input buffer** against 1–2× density. Longer audio means nearly every item
  splits into several input turns for qwen where the other three hear one. Either it stays in
  with that asymmetry recorded, or it drops to a footnote.
- **Placement regularity.** Stage 4 returns placement to an LLM, which in 1.0 favoured turn
  starts and ends. The generator logs the distribution of chosen positions so a collapse back
  to a pattern is visible rather than assumed.

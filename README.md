# Experiment summary

These experiments are all pieces of a **non-speech vocalization benchmark**: can a speech model use laughs, groans, sighs, and similar sounds as pragmatic signal, or does it only hear the words?

Each folder is one experiment type. Scripts are LLM-written (`gpt-5.6-terra` unless noted), then mechanically checked. Two folders also have a realtime listening eval.

Two different “checks” show up below:

- **Generation check** — Python schema on the writer (identical words, legal tags, C does not name the voc). This is not the benchmark.
- **Verifier / eval** — what a *model under test* is asked. Usually audio + multiple choice.

Published viewers: [https://chenzwnina.github.io/non-speech-pairing/](https://chenzwnina.github.io/non-speech-pairing/)  
Task 1 = `pairing_type`. Task 2 = `predicting_content`.

---

## 1. `predicting_response/` — same setup, different vocalization → different next response

**Purpose.** Hold the spoken words fixed, change only Speaker B’s vocalization, and see whether the next appropriate reply changes with it. Where `pairing_type` asks what B *feels*, this asks what should *happen next*. A text-only model is guessing; the sound has to pick the continuation.

### Dataset

Default run: **two speakers**, exactly **six turns** (`--speakers 2`, `--context-turns 4`). Speaker A talks; Speaker B has no lexical speech anywhere. B’s first contribution is a voc-only tag, meant to be spliced in later as **external audio**.


| Turn | Speaker | Control                                                                                          |
| ---- | ------- | ------------------------------------------------------------------------------------------------ |
| 1–3  | A       | Setup. Word-for-word identical across the pair. No tags. Separate utterances, not one paragraph. |
| 4    | A       | **The trigger** — the reveal B reacts to. Identical across the pair. Never a question.           |
| 5    | B       | The vocalization alone (`[gasp]`, `[grunt]`, `[laughter]`, `[sigh]`, `[sob]`, `[yawn]`).         |
| 6    | A       | The reply the vocalization selects. Differs between versions. Must not name the sound.           |


Turn 4 is the beat that invites a reaction. Nothing may sit between it and B’s voc. Early drafts let the news land at turn 3 and filled turn 4 with housekeeping (`It'll be waiting at the front desk`), so B reacted to the wrong line. A question on turn 4 is also banned: that makes turn 6 an answer to A instead of a reading of B.

`--speakers 3` is an optional A/C context with either of them replying; `--context-turns 8` is a 10-turn variant. The generated set is the two-speaker default.

Six vocalizations paired every unordered way = **15 contrasts**. `--n` sets pairs per contrast (default 1). The writer picks each version’s interpretation from that voc’s meaning list to fit the scene it invented, rather than having a meaning assigned up front.

**Current run.** `gpt-5.6-terra`, high effort, judged. **14/15** valid pairs in `predicting_response/out/pairs.json`. `gasp`–`sob` failed after 4 attempts (replies swapped freely). All 14 survivors pass every audit property.

Example (`gasp_grunt_001`):

```
1. A: The festival coordinator called right after rehearsal.
2. A: Our little afternoon slot disappeared because another act canceled.
3. A: She offered us the main stage, but she needed an answer tonight.
4. A: I told her we'd play Saturday in front of ten thousand people.

[gasp]  (fear)                 -> A: You're right, I got carried away. I'll call her
                                      back and withdraw before she locks us in.
[grunt] (reluctant agreement)  -> A: Okay, I'll confirm the slot and book us extra
                                      rehearsals every night this week.
```

**Audio.** None yet. Intended splice: turns 1–4 speech + curated B voc. Response options stay separate as the two answer choices. One synthesized voice for A; B is never TTS’d.

**Generation check.** Mechanical: exactly 4 A-only context turns, no tags, turn 4 not a question, no line predicting B’s reaction, exact plain tags, same responder, replies differ and do not name the sound.

**Contrast audit** (a second model pass, `--no-judge` to skip). Eight properties; items rebuild up to 4 times:


| Property                           | Rejects                                                              |
| ---------------------------------- | -------------------------------------------------------------------- |
| `trigger_is_last_shared_turn`      | B reacting to logistics, a summary, or an aside                      |
| `both_vocalizations_natural_here`  | a gasp with nothing surprising, a yawn with no tedium                |
| `interpretations_fit_the_context`  | a meaning forced onto a scene that doesn’t earn it                   |
| `undecidable_from_text_alone`      | context that already points at one reply                             |
| `replies_commit_to_different_actions` | same decision in two tones                                        |
| `voc1_favors_reply1` / `voc2_favors_reply2` | a link that is merely compatible, not specific               |
| `swapping_replies_is_clearly_worse` | replies that swap without the dialogue degrading                    |


The swap test does most of the work. It catches items built on an arbitrary two-option choice, where a gasp is no more “put it first” than laughter is:

```
4. C: So do I put that bit before or after the case study?
[gasp]     -> "Before. That reveal is too good to bury."
[laughter] -> "After. We'll use the mascot bit as the closing joke."
```

`verify.py` re-runs the mechanical checks and tallies the audit flags with no API calls.

### Verifier

**None yet.** Intended probe: sew turns 1–4 with a curated voc, then 2-way forced choice between the two turn-6 replies (the pair’s other reply as the distractor).

### Comments

- `gasp`–`sob` is the hard contrast: both are high-arousal reactions to significant news, so they tend to motivate the same next move (slow down and verify, or move immediately).
- Two speakers keeps the audio simple — one synthesized voice, one spliced recording.

---

## 2. `pairing_type/` — same words, different vocalization → attitude

**Purpose.** Generate an audio dataset where the spoken words stay fixed and only Speaker B’s vocalization changes, then test whether a model can identify B’s attitude from that sound.

### Dataset

Three-person, three-turn dialogues: **A → B → C**.


| Turn | Speaker | Control                                                                                 |
| ---- | ------- | --------------------------------------------------------------------------------------- |
| 1    | A       | Identical across the pair. No tags. 5–20 words.                                         |
| 2    | B       | Same spoken words; only the vocalization formula changes. 3–15 words after the formula. |
| 3    | C       | Different next action per vibe. Not used in the eval. No tags. Must not name the voc.   |


Manipulation is **Turn 2 only**. The lexical line after the formula must support *both* readings (not “I hate this” locked to exhaustion).

Four contrasts × six domains (school, work, family, health, entertainment, travel) = **24 pairs / 48 clips**.


| Contrast | Vocalization A                 | Vocalization B                | C should…                         |
| -------- | ------------------------------ | ----------------------------- | --------------------------------- |
| C1       | `[happy laugh] haha` enjoyment | `[groan]...` impatience       | joke along ↔ hurry / wrap up      |
| C2       | `[happy laugh] haha` enjoyment | `[exhausted sigh]` exhaustion | celebrate ↔ acknowledge fatigue   |
| C3       | `[groan]...` impatience        | `[sigh] hoo` relief           | hurry ↔ treat the task as done    |
| C4       | `mm-hm` engagement             | `[groan]...` impatience       | continue ↔ wrap up / change topic |


Example (`C1_school_001`):

```
A: Our debate club finally got the auditorium for Friday's showcase.
B lexical: That should make the practice much more interesting.

A version: [happy laugh] haha That should make the practice much more interesting.
           C: Great—our dramatic objections will finally have proper echoes.

B version: [groan]... That should make the practice much more interesting.
           C: Let's assign the opening speakers before the meeting ends.
```

**Audio.** Neutral T1 and T2 speech are synthesized separately. The voc is clipped from a full tagged Turn 2 via timestamps, then sewn as **Turn 1 + clipped voc + Turn 2 speech**. C is dropped. Voices: A `r1KmysJdVYZjJCm4mL3b` (female), B Charlie `IKne3meq5aSn9XLyUdCD`. TTS `eleven_v3`.

**Generation check.** Reject unless T1 matches, T2 words match after the formula, only the formula changes, both meanings are plausible from those words, C’s replies differ, and C does not say things like “you sound exhausted.”

### Verifier

**Four-way multiple choice**, one question per clip (48). The model hears the sewn audio (not the transcript) and must answer with a letter.

Prompt:

> You heard a short conversation. Speaker A speaks first, Speaker B second.
>
> What is Speaker B's current status?
>
> A. Impatience
> B. Enjoyment / amusement
> C. Exhaustion
> D. Engagement / attention
>
> Reply with only one letter: A, B, C, or D.

Options are **attitude labels only** — no “laugh,” “groan,” or contrast names. Inventory:


| id                 | Label shown to the model |
| ------------------ | ------------------------ |
| enjoyment laughter | Enjoyment / amusement    |
| impatient groan    | Impatience               |
| exhausted sigh     | Exhaustion               |
| relief sigh        | Relief                   |
| engagement mm-hm   | Engagement / attention   |


Each item always includes the gold attitude, the **paired contrast** attitude, and two other attitudes, shuffled.

Same pair, other clip (`C1_school_001-b`, groan): gold is Impatience; Enjoyment is still among the four options.

Run: `gpt-realtime`, seed 0. **25/48 = 52.1%** (chance 25%). Impatience 2/18. C2 enjoyment vs exhaustion 9/12 = 75%.

---

## 3. `predicting_content/` — hear the vocalization → predict the next line

**Purpose.** Generate clips where the last turn *starts* with a non-speech sound that foreshadows upcoming words, then test whether a model can pick the matching next line **without hearing those words**.

### Dataset

Two speakers, three turns: **A → B → A**. Turn 3 is Speaker A again.

- Turns 1–2: ordinary context. No voc on these turns in the sewn clip.
- Gold Turn 3 = formula + lexical content matching that voc’s typical stance.
- One alternative = the **opposite stance** on the same situation (not a nearby speech act). Gold is frozen; alts were rewritten once (`regenerate_alts.py`).

Ten vocalizations × three domains (school, work, family) = **30 items**.


| id           | Formula           | Gold content                 | Opposite alternative     |
| ------------ | ----------------- | ---------------------------- | ------------------------ |
| sigh         | `[sigh]`          | reluctant accept / complaint | willing, upbeat accept   |
| groan        | `[groan]`         | rejection / protest          | eager yes                |
| laugh        | `[laugh]`         | joke / tease                 | earnest, unironic        |
| hmm          | `Hmm...`          | tentative proposal           | confident decision       |
| mmhm         | `Mm-hm...`        | continuation / agreement     | disengagement, shut down |
| scoff        | `[scoff]`         | disagreement / criticism     | enthusiastic endorsement |
| throat_clear | `[clears throat]` | sensitive correction         | easy, nothing-is-wrong   |
| exhale       | `[exhale]`        | relieved closure             | still unresolved         |
| yawn         | `[yawn]`          | postpone / stop              | energized, keep going    |
| shaky_breath | `[shaky breath]`  | distress / reassurance       | confident, I have this   |


Example (`sigh_school_001`):

```
A: The history club display has to be finished before tomorrow's open house,
   and Jordan just texted that he cannot stay after school.
B: We could ask Ms. Patel for more time, find another club member,
   or have you cover Jordan's part.

Gold: [sigh] Fine, I'll stay after school to finish the display,
      but this is the third time I've had to cover for someone.
Alt:  I'd be happy to stay after school and finish the display—
      we'll have it ready for the open house.
```

**Audio.** T1 (voice A), T2 (voice B), full T3 with timestamps (voice A). Voc is clipped off the front of T3. Sewn file is **Turn 1 + Turn 2 + clipped T3 voc only** — gold words never reach the model.

### Verifier

**Two-choice multiple choice.** Options are the two lexical lines with the formula stripped, shuffled A/B.

Prompt:

> You heard a short conversation. Speaker A spoke first, Speaker B second,
> then Speaker A made a brief non-speech sound.
>
> Which line is Speaker A about to say?
>
> A. Fine, I'll stay after school to finish the display, but this is the third time I've had to cover for someone.
> B. I'd be happy to stay after school and finish the display—we'll have it ready for the open house.
>
> Reply with only one letter: A or B.

The model does **not** see tags, formulas, or gold/alt labels. Chance 50%.

Run: `gpt-realtime-2.1`, seed 0. **24/30 = 80%**. Exhale 0/3, throat-clear 1/3, laugh 2/3; the other seven vocs 3/3. School 9/10, work 8/10, family 7/10.

---

## 4. `transcript_curated/` — same Turn 3 words, different delivery → different C response

**Purpose.** Generate four-turn pairs where Turns 1–2 and Turn 3’s *words* are the same, only how Turn 3 is voiced changes, and Speaker C’s next line should flip with that vibe. Intended as a “does the model pick the matching response / reading?” benchmark. **No listening eval yet.**

### Dataset

Four turns. A and B speak 1–3; C speaks 4 (already present, first time talking).


| Turn | Speaker | Control                                                                                    |
| ---- | ------- | ------------------------------------------------------------------------------------------ |
| 1    | A       | Identical. No tags. 6–22 words.                                                            |
| 2    | B       | Identical. No tags. 5–20 words.                                                            |
| 3    | A       | Same 5–16 spoken words. Tags / laugh–sigh tokens differ.                                   |
| 4    | C       | Different action per vibe. No tags. Must not name the voc or narrate (“C takes a photo…”). |


Three pairs × five domains (school, work, family, health, entertainment) = **15 items**.


| Pair | Version A                             | Version B                          | C should…                                    |
| ---- | ------------------------------------- | ---------------------------------- | -------------------------------------------- |
| P1   | `[happy laugh] hahahaha` prefix burst | `[sympathetic]` inserted in-speech | join the joke ↔ comfort / help               |
| P2   | `[sarcastic] ha... ha... ha...`       | `[happy laugh] hahahaha`           | treat as criticism ↔ celebrate               |
| P3   | `[heavy sigh]...` exhausted           | `[happy]hooo[exhale]` relief       | let them rest / take over ↔ ease off as done |


Example (`P1_school_001`):

```
T1 A: We're all outside the library when my poster board slides into the fountain.
T2 B: The ink spread across the whole timeline before we could grab it.
T3 lexical: At least the fish got to study ancient Rome.

T3 A: [happy laugh] hahahaha At least the fish got to study ancient Rome.
T4 A: I'm taking a picture for the history club group chat.

T3 B: At least the fish got to [sympathetic] study ancient Rome.
T4 B: I have spare paper in my bag; let's remake the timeline.
```

**Audio so far.** T1, T2, and a **neutral T3** (tags and `hahahaha` / `ha... ha... ha...` / `hooo` stripped). 15 × 3 = 45 clips. Tagged T3 vocs have not been synthesized or sewn yet.

**Generation check.** T1/T2 identical and tag-free; T3 words match after stripping formulas; P1’s `[sympathetic]` must sit inside the sentence; T4 differs and is spoken dialogue.

### Verifier

**None yet.** A natural next probe, matching the other evals, would be audio of T1–T3 (with the tagged T3) and a two-choice on C’s line, or a two-choice on the T3 vibe (enjoyment vs sympathy, sarcastic vs enjoyment, exhausted vs relief).

### Comments

- It is hard to distinguish different laughter types from audios, which makes  two versions of responses very similar.

---

## 5. `laughter_identify/` — identify which laughter function is in the dialogue

**Purpose.** Generate four-turn dialogues each targeting one taxonomy laughter function, as items for a “what is this laugh doing?” identification set. **No audio or listening eval in this folder.**

### Dataset

Two speakers, four turns, **A-B-A-B**. Exactly one written laugh (`haha` / `hehe`), plus an adjective tag (`[delighted]`, `[apologetic]`, `[sheepish]`, `[sarcastic]`, …). Do not write `[laugh]`. Every turn has some delivery tag.

Six functions × four themes (school, work, family, health) = **24 dialogues**.


| Function                      | Laugh should…                                      | Typical adjective           |
| ----------------------------- | -------------------------------------------------- | --------------------------- |
| Show enjoyment of incongruity | Display enjoyment of a pleasant clash              | delighted, amused, playful  |
| Softening / trouble-telling   | Cushion criticism, dissent, or painful self-talk   | awkward, apologetic, uneasy |
| Benevolence induction         | Soften a request / favor the partner could refuse  | sheepish, hopeful, coaxing  |
| Smoothing                     | Keep talk going after interactional awkwardness    | embarrassed, awkward, light |
| Show sympathy                 | Recipient laugh answering the partner’s discomfort | warm, kind, understanding   |
| Marking irony                 | Flag “do not take this literally”                  | sarcastic, dry, wry         |


Example (enjoyment, school):

```
A: [excited] At robotics club, our robot rolled into the principal's office during its presentation.
B: [delighted] haha, it finally found a real-world internship.
A: [relieved] The principal laughed too and asked it to stop emailing him meeting requests.
B: [playful] For a first-year student, it is already terrifyingly proactive.
```

Laugh: turn 2 (B).

**Generation check.** Exactly four turns, speakers A-B-A-B, exactly one written laugh on `laughing_turn`, no `[laugh]` tags, plus per-function constraints (e.g. benevolence must contain a real request; irony must not be sincere enjoyment).

### Verifier

**None yet.** A natural probe would be: play the clip (or show the tagged transcript) and force-choice among the six functions, or 2-way among a target vs a foil function.

### Comments

- The transcripts are not clear enough to tell which function the laughter maps to.

---

## Status at a glance


| Folder                | Turns          | Manipulation                | What the model is asked          | Format            | Result      |
| --------------------- | -------------- | --------------------------- | -------------------------------- | ----------------- | ----------- |
| `predicting_response` | 6 (A×4, B, A)  | T5 voc; context fixed       | which reply follows              | none yet          | —           |
| `pairing_type`        | 3 (A B C)      | T2 voc; words fixed         | B’s attitude                     | 4-way MCQ, audio  | 25/48 = 52% |
| `predicting_content`  | 3 (A B A)      | T3 voc; gold words held out | A’s next line                    | 2-way MCQ, audio  | 24/30 = 80% |
| `transcript_curated`  | 4 (A B A C)    | T3 tags; words fixed        | *(planned: C’s line or T3 vibe)* | none yet          | —           |
| `laughter_identify`   | 4 (A B A B)    | one targeted laugh function | *(planned: which function)*      | none yet          | —           |
| `archived`            | ~4, 2 performances | tags / delivery          | what the laugh is doing          | 2-way + open      | —           |
| `v2`                  | 4 lexical      | none (ambiguity filter)     | which function from text         | 2-way, 50/50 gate | filter only |

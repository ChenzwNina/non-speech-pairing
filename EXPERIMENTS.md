# Experiment summary

These experiments are all pieces of a **non-speech vocalization benchmark**: can a speech model use laughs, groans, sighs, and similar sounds as pragmatic signal, or does it only hear the words?

Each folder is one experiment type. Scripts are LLM-written (`gpt-5.6-terra` unless noted), then mechanically checked. Two folders also have a realtime listening eval.

Two different “checks” show up below:

- **Generation check** — Python schema on the writer (identical words, legal tags, C does not name the voc). This is not the benchmark.
- **Verifier / eval** — what a *model under test* is asked. Usually audio + multiple choice.

Published viewers: [https://chenzwnina.github.io/non-speech-pairing/](https://chenzwnina.github.io/non-speech-pairing/)  
Task 1 = `pairing_type`. Task 2 = `predicting_content`.

---

## 1. `pairing_type/` — same words, different vocalization → attitude

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

## 2. `predicting_content/` — hear the vocalization → predict the next line

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

## 3. `transcript_curated/` — same Turn 3 words, different delivery → different C response

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

## 4. `laughter_identify/` — identify which laughter function is in the dialogue

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

## 5. `predicting_response/` — same setup, different vocalization → different next response

**Purpose.** Hold the spoken words fixed, change only B's vocalization, and see whether the
next appropriate reply changes with it. Where `pairing_type` asks what B *feels*, this asks
what should *happen next*.

### Dataset

Six turns, two speakers (`--speakers 2`, default):


| Turn | Speaker | Control                                                                       |
| ---- | ------- | ----------------------------------------------------------------------------- |
| 1–3  | A       | Setup. Identical across the pair. No tags.                                    |
| 4    | A       | **The trigger** — the reveal B reacts to. Identical across the pair. Never a question. |
| 5    | B       | The vocalization alone. B's first contribution; B has no lexical speech anywhere. |
| 6    | A       | The reply the vocalization selects. Differs between versions.                 |


B stays silent through the context so the eval can splice in **external audio** for turn 5
without B's voice being established first.

`--speakers 3` restores an A/C context with either replying; `--context-turns 8` gives a
10-turn variant. Six vocalizations paired every way = **15 contrasts**; `--n` sets pairs per
contrast.

The writer chooses each version's interpretation from that vocalization's meaning list to fit
the scene it invented. Assigning the meaning up front produced reactions the scene had not
earned.

Example (`laughter_sob_001`):

```
1. A: I've been sorting through the old camcorder files for Mom's birthday slideshow.
2. A: Most of them are blurry holidays, with everybody talking over each other.
3. A: I thought the recording from the year Dad died had been lost for good.
4. A: But I found one where he's singing "Happy Birthday" hopelessly off-key,
      then he looks at Mom and says, "I love you, June."

laughter (shared amusement) -> A: Then I'm putting that clip at the end of the
                                 slideshow—his terrible singing will make everyone smile.
sob (being deeply moved)    -> A: I'll keep that one out of the slideshow and save it
                                 for just us after the party.
```

**Generation check.** Mechanical: turn count and speakers, no B in the context, no tags, turn 4
not a question, no line predicting B's reaction, exact plain tags, shared responder, replies
differ and don't name the sound.

**Contrast audit** (a second model pass, `--no-judge` to skip). Eight properties: the trigger is
the last shared turn; both vocalizations are natural there; both interpretations are earned; the
reply is undecidable from text alone; the replies commit to different actions; each vocalization
favors its own reply; and **swapping the replies is clearly worse**. Items are rebuilt up to 4
times.

The swap test does most of the work — 8 of 14 rebuilds in the 15-pair run. It catches items
built on an arbitrary two-option choice, where a gasp is no more "put it first" than laughter is:

```
4. C: So do I put that bit before or after the case study?
[gasp]     -> "Before. That reveal is too good to bury."
[laughter] -> "After. We'll use the mascot bit as the closing joke."
```

### Verifier

**None yet.** The intended probe is a 2-way forced choice: play turns 1–4 plus the spliced
vocalization, then ask which of the two turn-6 replies fits, with the pair's other reply as the
distractor.

### Comments

- 14/15 contrasts produced a valid pair. `gasp`–`sob` is the hard one: both are high-arousal
  reactions to significant news, so they tend to motivate the same next move.
- Two speakers keeps the audio simple — one synthesized voice, one spliced recording.

---

## 6. `pairing_type_upgraded/` — silent B, two vocs → two next responses

**Purpose.** Same task as `predicting_response` (does the voc pick the next line?), but with a
three-person scene: A and C talk, B has **never spoken**, and B’s first contribution is a
voc-only reaction supplied later as external audio. Where `pairing_type` asks for B’s
attitude and B also says words, this holds the spoken context fixed and asks which reply
follows the sound.

### Dataset

Three speakers. Shared context is **A and C only** (about 3–6 turns). Then B produces one
plain tag (`[gasp]`, `[grunt]`, `[laughter]`, `[sigh]`, `[sob]`, `[yawn]`) with no extra
words. Either A or C gives the next line; that responder is the same in both versions.


| Part              | Speaker | Control                                                                 |
| ----------------- | ------- | ----------------------------------------------------------------------- |
| Shared context    | A, C    | Identical across the pair. No tags. No spoken turn from B.              |
| Vocalization      | B       | Voc-only first contribution. Two different tags per pair. Not synthesized here. |
| Final response    | A or C  | Differs between versions. Must not name the sound.                      |


Six vocalizations paired every unordered way = **15 contrasts / 15 pairs**. Meanings vary
inside each voc (gasp as surprise vs disbelief, yawn as boredom vs tiredness, etc.).

Example (`gasp_grunt_001`):

```
A: The talent-show sign-up closes today.
C: I thought our class had decided not to enter.
A: We hadn't, but I put our names down for a three-minute slot.
C: And what exactly are we doing onstage?
A: I found my old card trick. It should be enough for three minutes.

[gasp]  -> A: I know it sounds sudden, but the deadline was today.
[grunt] -> A: Okay, I'll keep the slot and bring the cards tomorrow.
```

**Audio.** Each spoken line is its own clip. **91 mp3s**: 61 context turns + 30 response
options (`v1` / `v2`). B’s voc is **not** generated — it will be curated externally, then
sewn as context turns + voc. Voices: A `r1KmysJdVYZjJCm4mL3b`, C `C3x1TEM7scV4p2AXJyrp`.
TTS `eleven_v3`. Files under `pairing_type_upgraded/out/audio_turns/`.

**Generation check.** Shared context has no B and no tags; both versions use the assigned
plain tags; the two replies differ, share a responder, and do not name the voc.

### Verifier

**None yet.** Intended probe: sew the context-turn clips with a curated voc, then 2-way
forced choice between the two response clips (the pair’s other reply as the distractor).

### Comments

- Closest sibling is `predicting_response/` (2-speaker A monologue + silent B, with a
  contrast-audit rebuild loop). This folder keeps the A/C conversation so B can be a
  silent third person in the room.
- Per-turn clips are deliberate: vocs get spliced between the last context turn and the
  response options, which stay separate because they are the answer choices.

---

## Status at a glance


| Folder               | Turns              | Manipulation                | What the model is asked          | Format            | Result      |
| -------------------- | ------------------ | --------------------------- | -------------------------------- | ----------------- | ----------- |
| `pairing_type`       | 3 (A B C)          | T2 voc; words fixed         | B’s attitude                     | 4-way MCQ, audio  | 25/48 = 52% |
| `predicting_content` | 3 (A B A)          | T3 voc; gold words held out | A’s next line                    | 2-way MCQ, audio  | 24/30 = 80% |
| `transcript_curated` | 4 (A B A C)        | T3 tags; words fixed        | *(planned: C’s line or T3 vibe)* | none yet          | —           |
| `laughter_identify`  | 4 (A B A B)        | one targeted laugh function | *(planned: which function)*      | none yet          | —           |
| `predicting_response` | 6 (A×4, B, A)     | T5 voc; context fixed       | which reply follows              | none yet          | —           |
| `pairing_type_upgraded` | A/C context + B voc + reply | B voc; A/C words fixed | which reply follows              | none yet          | —           |
| `archived`           | ~4, 2 performances | tags / delivery             | what the laugh is doing          | 2-way + open      | —           |
| `v2`                 | 4 lexical          | none (ambiguity filter)     | which function from text         | 2-way, 50/50 gate | filter only |



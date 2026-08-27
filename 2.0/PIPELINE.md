# How the 2.0 dataset is built

Written for someone who has not seen this project. Each stage lists what goes in, what it does,
and what comes out. [SPEC.md](SPEC.md) is the design authority; this describes the built thing.

## The question

A speech-to-speech model hears audio and answers with audio. When two people tell a story and
laugh through it, that laughter says the story is being made light of; the same words told
through sighs say the opposite. Can a model use those sounds to decide how to answer?

The hard part is ruling out the words. If you record two versions of a conversation, one funny
and one bleak, the actors will say the words differently and the model could be responding to
that. So this dataset records the words **once** and splices non-speech sounds into copies of
that same recording. Three versions come out: one with laughter, one with sighs, one with
neither. The spoken audio is identical in all three — not paraphrased, not re-recorded, the same
samples. Anything the model does differently is down to the sounds.

## Glossary

- **vocalization** — a non-speech sound a person makes: laughter, a sigh, a gasp.
- **condition** — which version of a conversation: `happy` (laughter), `sad` (sighs),
  `neutral` (neither).
- **slot** — a position where a sound is inserted: a turn, and a word within it.
- **take** — one rendered piece of audio from the text-to-speech service.
- **gold** — the right answer, written in advance, that a model's answer is compared against.

## Stages

### 1 — Choose the situations
**In:** EmpatheticDialogues, a public dataset of 25,000 conversations grounded in emotional
situations. **Out:** 20 situations labelled `embarrassed`.

Embarrassed situations are the ones that genuinely read both ways — a public mishap can be a
funny story or a miserable one. Labels like *devastated* are excluded deliberately: laughter
over a bereavement is incoherent, and in a published benchmark, tasteless.

### 2 — Write the conversations
**In:** the situations. **Out:** one 4–8 turn conversation each, two speakers.

A language model writes each conversation **once**, and is told the words must not settle
whether the story is funny or bleak. If a line only works when read cheerfully, the words are
doing the job the sounds are supposed to do.

### 3 — Decide how many sounds
**In:** the turn count. **Out:** a number, drawn at random between 1× and 2× the turns.

So a 6-turn conversation carries 6 to 12 sounds. Drawing the count rather than fixing it stops
the number itself from being a cue.

### 4 — Decide where they go
**In:** the conversation and the count. **Out:** a list of slots, each with a laughter form and
a sigh form.

A model picks the positions — which turn, after which word — and writes each sound the way the
speech service needs it: a bracketed manner tag plus a written sound, like `[chuckle] hah`. The
tag alone produces nothing, because the service requires text after the tags are stripped.

**One set of positions serves both conditions.** Every slot gets both a laughter form and a
sigh form, so the laughter version and the sigh version differ only in which sound sits in the
gap. If each condition chose its own positions, a difference between them could be down to
timing rather than sound.

### 5 — Write the gold answers
**In:** the conversation with the sounds written into it, once per condition. **Out:** two
sentences per condition.

One sentence says how the two speakers are treating the story; the other says what tone a third
person joining should adopt. A second model writes these — not the one that wrote the
conversation — and it sees the sounds already in place, so it is describing a conversation
rather than predicting one.

A third model then verifies, and the check that matters is the **swap test**: exchange the two
conditions' answers, and both must now read as wrong. If the laughter answer still fits the sigh
version, the gold is not telling the conditions apart, and no score computed from it can either.

### 6 — Record the speech
**In:** the conversations. **Out:** one audio take per turn, plus the timing of every word.

Two voices, one male and one female. The service returns character-level timings, which is what
makes splicing inside a sentence possible: the silence between two words has a measured start
and end, so a sound can be placed in a pause the speaker actually left rather than at a guessed
point.

### 7 — Record the sounds
**In:** the slots. **Out:** one laughter clip and one sigh clip per slot.

Every slot gets its own takes. A form that occurs eight times is eight different recordings —
reusing one would put audibly identical laughter in eight places, which tells a model about the
construction rather than the conversation. Each clip is levelled against the speech it will sit
inside, and re-recorded if it comes back silent or overlong.

### 8 — Check the sounds are what they claim
**In:** the clips. **Out:** a verdict per clip.

Two speech models are drawn at random and asked whether the clip contains the intended sound.
Both must say yes. Otherwise the clip is recorded again and the same two are asked afresh, up to
three attempts. A model that fails to answer is asked once more; silence is not a verdict.

This matters more than it sounds. A text transcriber cannot check a sigh — there are no words in
it — so the only available judges are models that listen. And a model can report "no laughter
here" when what actually happened is that it received no audio at all. The two look identical
from outside, which is why every collection pass begins by playing each model a real sentence
and requiring the words back.

### 9 — Splice the three conditions
**In:** the takes, the word timings, the clips. **Out:** three audio files per conversation.

Each turn is cut at the chosen pauses, the clip is dropped in with a short gap either side, and
the pieces are joined. Both halves of every cut come from the same file, so the speech either
side of a splice is the same audio in the laughter and sigh versions. The neutral version is the
turns alone.

### 10 — Build the answer options
**In:** the gold answers and the plain conversation. **Out:** four options per conversation.

Two are the real answers — one per condition — and two are wrong for both. The wrong ones are
written by a different model from the one that wrote the real answers, because a distractor
written by the same model tends to differ in style rather than in substance, and style is what a
tested model would learn to spot.

### 11 — Test
**In:** the three conditions. **Out:** a reply per condition, plus two answers.

Each model hears each version and replies as a third speaker, having been told what the
conversation is about but nothing about how anyone feels. Then two questions, in this order:
how are the speakers treating the story, and what sound did you hear. That order is deliberate —
the second question reveals that non-speech sound is the subject, so it comes after the model
has committed to a reading.

The neutral version is heard and answered but never scored. Its reply exists only so the
appropriateness comparison has a third reply to weigh against.

## How the answers are scored

**Q1 — appropriateness.** There is no right reply, so each reply is compared against the same
model's replies to the other two versions. A judge sees the conversation with its sounds marked
and picks the better-suited reply. If the sounds changed how the model answered, its own reply
should win; if not, the replies are interchangeable and the judge is guessing. Three text judges
from three vendors, one vote each. Chance is 50%.

**Q2 — tone.** A panel of speech models listens to the reply and rates how well its delivery
matches the gold tone, 0 to 4. No model rates its own reply, and judges hear the reply alone —
giving them the conversation would tell them which version they were rating.

**Q3 — reading.** Did the model pick the answer written for the version it heard? Chance is 25%.
When it is wrong, it matters whether it picked the *other version's* answer, which means it heard
the sounds and read them the other way, or a distractor, which means it misread the conversation
altogether.

**Q4 — perception.** Did it name the sound that was there? Chance is 25%. The wrong options
include the other real vocalization, so mistaking a sigh for laughter costs the same as
inventing a yawn.

## What limits the results

**Splicing is not amused delivery.** Inserting a discrete laugh gives perfect control over the
words, at the price of prosody: a genuinely amused voice laughs *through* its speech, and that
cannot be spliced in. This measures whether a model can use a discrete sound, not whether it can
hear an amused voice.

**One judge could not hear sighs.** Grok answered yes to 25% of sigh clips where the other three
answered 98–100%, and denied real human sigh recordings 3 times in 5. Every clip that failed the
first verification pass had grok among its judges; none judged by a grok-free pair failed at
all. It was removed from the panel and kept as a tested model, since being deaf to sighs is a
result worth reporting rather than a reason to let it screen the stimuli.

**The conditions differ in length.** Laughter and sighs are not the same duration, so the two
versions of a conversation are within a few seconds of each other rather than identical, and the
neutral version is shorter than both.

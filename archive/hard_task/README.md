# hard_task — non-speech vocalizations in multi-turn conversation

A harder benchmark than the two-turn tasks in this repo. Each item is an **eight-turn
conversation** between Speaker A and Speaker B in which **exactly two turns** contain a
target non-speech vocalization, drawn from `gasp`, `grunt`, `laughter`, `sigh`, `sob`,
`yawn`.

Recognising that a sound is laughter or a sigh is only the first step. The task is to use
the surrounding conversation to work out **why** the speaker produced it and **what it
communicates in that specific context**.

## The four questions the benchmark asks

Per vocalization event:

1. Which turn contains a target non-speech vocalization?
2. What type of vocalization occurred — gasp, grunt, laughter, sigh, sob, or yawn?
3. What does that vocalization mean in this particular conversational context?
4. Which earlier part of the conversation provides the evidence for that interpretation?

Question 3 is the point of the task. The wanted answer is not "B is amused" but something
contextual — "B is playfully teasing A because A confidently attempted the repair and made
the problem worse." Question 4 asks for the turns that license that reading.

## Built backward

The pipeline never generates a conversation and then explains the sounds in it. The
causal direction is fixed:

```
intended pragmatic meaning → required contextual evidence → generated conversation
    → vocalization appears naturally
```

**The ground truth is also the rubric.** The plan written in stage 1 is what grades a
model later — each accepted item carries a `rubric` block whose four entries are exactly
the four questions above. The rubric is the object that generated the item, not a
post-hoc reading of the finished transcript.

### Stage 1 — plan the latent ground truth (no dialogue)

Picks a domain, then designs two vocalization events. Each event fixes:

| field | meaning |
| --- | --- |
| `target_turn` | which turn carries the sound (2–8; context has to accumulate first) |
| `speaker` | who produces it — determined by the turn, since turn 1 is A and speakers alternate |
| `vocalization` | one of the six |
| `interpretation` | what it communicates **in this situation** |
| `evidence_plan` | what the later transcript must establish to support that reading |

The **two target turns are assigned to the item**, not chosen by the planner. Left free,
the planner puts them on turns 4 and 7 in 13 of 15 items — which would let a model score
by guessing positions instead of listening. There are exactly 15 legal turn pairs (both in
2–8, at least 2 apart), matching the 15 vocalization pairs, so each item gets a distinct
combination and positions are spread across the whole conversation.

The evidence plan names the *required information* only — no exact sentences, no
evidence-turn numbers. Those are not knowable until the transcript exists.

Constraints enforced mechanically (`validate_plan`):

- the two events sit on different turns, at least 2 turns apart, and use different sounds
- the interpretation names its speaker, is not a bare emotion label, and never uses the
  words gasp / grunt / laugh / sigh / sob / cry / yawn — interpret the reaction, don't
  label the sound
- the interpretation must be **inferable from context that can precede the target turn**.
  "B accepts that they'll now have to redo the work" cannot be supported in advance,
  because the acceptance hasn't happened yet when B makes the sound
- the evidence plan doesn't smuggle in turn numbers or quoted dialogue

The prompt also pushes away from trivial cause-and-effect. "A says B hasn't slept for two
days, then B yawns" tests nothing beyond a stereotype; the context should make the
vocalization *meaningful* without announcing it.

### Stage 2 — realize the plan as eight turns

Receives the plan and writes the conversation that serves it. Target turns, speakers,
vocalization types, and interpretations are **not negotiable** — the writer may not drift
to an easier meaning.

Enforced mechanically (`validate_transcript`):

- exactly 8 turns; turn 1 is A and speakers strictly alternate
- each target turn is **the tag alone** (`[sigh]`), no words before or after — otherwise
  the words, not the sound, would carry the meaning
- no bracketed tags anywhere else, and no vocalization words in any spoken turn
- the turn immediately before a target turn may not announce the reaction ("you seem
  really disappointed" → `[sigh]` hands over the answer)
- every cited evidence turn precedes its target turn and contains actual words
- **at least one event must rest on evidence earlier than the immediately preceding
  turn**, so the item requires multi-turn reasoning rather than a local reaction

The writer then reports the `evidence_turns` and an `evidence_summary` describing what is
genuinely present in those turns.

### Stage 3 — independent verification

A separate verifier call judges four criteria, **separately for each event**:

| criterion | question |
| --- | --- |
| `vocalization_natural_at_that_point` | could a real person react that way there? |
| `evidence_supports_interpretation` | do the cited turns actually license the reading, and does the summary describe what those turns really say? |
| `interpretation_requires_context` | does the reading depend on this conversation, rather than on the sound category alone? |
| `intended_interpretation_clearly_best` | is the intended reading clearly better supported than genuinely competing readings? |

PASS requires all four to pass for both events.

On the fourth criterion, a competitor is a reading that changes what the speaker is
understood to be *doing* — teasing vs. reproaching, relief vs. alarm, boredom vs. concern.
A rewording of the same conversational move in a different affect register is not a
competitor: "resignation" vs. "frustration" vs. "exasperation" over the same situation,
aimed at the same person, for the same reason, are paraphrases of one interpretation. The
benchmark grades the causal and relational content, not the emotion word.

### Rejection, not repair

If a transcript fails, it is rebuilt **against the same fixed plan** (up to 3 attempts).
The ground truth is never edited to match whatever the writer happened to produce. Only
when a plan proves unrealizable after repeated attempts is a fresh plan drawn — which
discards that item rather than mutating its ground truth.

## Running it

```bash
python3 hard_task/generate.py
```

```bash
python3 hard_task/generate.py --pair laughter-sigh --verbose
```

```bash
python3 hard_task/generate.py --dry-run
```

To finish an interrupted batch without regenerating what already landed:

```bash
python3 hard_task/generate.py --resume
```

The job list is seed-deterministic, so item ids, domains, and assigned turns line up
across runs and accepted items are kept as-is.

Coverage: the 15 unordered pairs of the six vocalizations, one item each by default
(`--n` for more per pair). Three things are assigned per item rather than left to the
model, each because the model otherwise collapses the distribution:

- **which sound of a pair goes on the earlier turn** — shuffled, so neither is
  systematically heard first. A fixed alphabetical ordering in an earlier experiment in
  this repo meant `gasp` was *always* the first sound heard and `yawn` *always* the
  second, fully confounding position with identity.
- **the two target turns** — one of the 15 legal pairs per item. Free choice concentrated
  them on turns 4 and 7.
- **the domain** — otherwise the same few settings recur.

## Output

- `out/items.json` — full records: plan, transcript, per-event evidence, verifier verdict,
  attempt counts, token usage, and the `rubric` block
- `out/items.md` — readable transcripts with the ground truth under each

## Notes and open options

- **Text-only ablation.** The strongest check on "does the sound actually carry
  information" would be to hand a model the transcript with the target turns blanked and
  confirm it *cannot* recover the interpretation. Not implemented; the current defence is
  the leakage checks plus verifier criteria 3 and 4.
- **Audio.** No audio generation yet. The intended shape follows the rest of this repo:
  TTS for the spoken turns, real recordings from `audio_non-speech/` spliced in at the two
  target turns.

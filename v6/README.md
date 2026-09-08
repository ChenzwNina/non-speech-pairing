# v6 · one conversation, two vocalizations

**The same five-turn conversation, heard three ways: with one non-speech vocalization, with a
contrasting one in the identical position, and with none at all.** The words are the same, the
speakers are the same, the position is the same. Only the sound differs — so if a model answers
differently, the sound is the only thing it can be answering to.

The sound falls in the final turn, at the moment something reaches the speaker. It therefore
reframes what has already been said rather than colouring what follows, and the third party who
joins to respond has just heard it.

Where [v4](../v4/) gave the vocalization its own turn from a silent third speaker, v6 puts the
tag *inside* a spoken line, so the sound colours the delivery of the words around it. That is
the thing [v3](../laughter_sigh_contrast_v3/) explicitly could not do — its own caveat was that
"splicing is not amused delivery… a genuinely amused voice laughs *through* its speech."

## The design in one item

```
1  A: I still haven't gotten the confirmation for our trip.
2  B: Maybe the booking went through and the email's just late?
3  A: I hope so. Next week is completely open otherwise.
4  B: Wait, a confirmation email just came in. Open it.
5  A: It's for next week.                     ← baseline
5  A: (gasps) It's for next week.
5  A: (groans) It's for next week.
```

The email arrives during the conversation, so the speaker is reading it for the first time as
they speak. *It's for next week* is either the trip suddenly becoming real or the trip suddenly
becoming an imposition, and nothing in the words decides which. The first four turns are
identical across all three versions, down to the samples in the audio.

## The inventory

Four vocalizations, every pair of them used, four items each — 24 items.

| Vocalization | Dia tag | ElevenLabs tag |
| --- | --- | --- |
| laugh | `(laughs)` | `[laughs]` |
| sigh | `(sighs)` | `[sighs]` |
| gasp | `(gasps)` | `[gasps]` |
| groan | `(groans)` | `[groans]` |

**No sound is assigned a fixed emotion.** What a vocalization frames is decided per item, from
the situation it lands in, because the same laugh means different things in different
conversations — and an inventory that fixed `laugh = amusement` would assert the thing this
benchmark is meant to measure. An earlier version did fix it, and passed the mapping to the
planner: every laugh came back framed as comic absurdity and every sigh as resigned acceptance,
12 out of 12 each, which makes the pragmatic question answerable by naming the sound and
applying a rule. `out/plans_with_default_reading.json` is that run.

`scream` was dropped. EmpatheticDialogues situations are everyday interpersonal ones and a
genuine fear-scream needs stakes they do not have, so six of eight scream items read as
mock-horror; it also formed the one pair whose conditions were indistinguishable, since a scream
after a physical mishap signals pain as readily as fear, and pain is what `groan` already does.

Two tag vocabularies because two services render the audio. The transcripts carry Dia's
parenthesised tags; `make_audio.py` maps them to ElevenLabs' bracketed form. Neither is ever
spoken aloud — each is an instruction to its own model.
[vocalization_emotions.md](vocalization_emotions.md) has the details.

## How the dataset was built

Three stages, in this order for a reason.

| | |
| --- | --- |
| [seeds.py](seeds.py) | a flat random sample of EmpatheticDialogues situations, no label filter |
| [sample_items.py](sample_items.py) | draws the seeds and the vocalization pairs. **No model is called** — the assignment is an artefact you can read |
| [plan_occasions.py](plan_occasions.py) | works out *when each sound would actually be produced*, then builds one moment that carries both |
| [write_transcripts.py](write_transcripts.py) | writes five turns that arrive at that moment, and builds the three versions |
| [out/transcripts.json](out/transcripts.json) | **the dataset.** 24 items, three versions each |

**Why the middle stage exists.** The obvious pipeline writes the conversation and then attaches
the vocalization, and it produces lines like this:

```
5  A: Yeah, I kept her number. I paid twelve dollars for it. (gasps)
```

The speaker is gasping at information he is himself delivering. Sounds are not interchangeable in
*when* they can be produced: a gasp is the instant of contact with something, so it cannot be
made about what you already know, while a sigh has no such requirement and can be produced about
anything. Attaching the sound last means the strict cases fail silently.

So the planner is asked for each sound's production condition **before it sees the situation**,
then to satisfy the stricter of the two, then to outline five turns that arrive there. Asked that
way it derives the asymmetry on its own — across 24 plans it marked `gasp` as requiring something
to land in the moment 12 times out of 12, `sigh` 0 out of 12, and `laugh` and `groan` genuinely
mixed. Nothing in the prompt names a vocalization; a fifth sound would need no new rule.

The same item, rebuilt from the sound outward:

```
4  B: Wait, a confirmation email just came in. Open it.
5  A: (gasps) It's for next week.
5  A: (groans) It's for next week.
```

**The writer returns the five turns once**, with `«VOC»` marking the spot, and the three versions
are built by substitution. Identical words, identical position, exactly one vocalization and none
in the baseline are therefore true by construction rather than things a validator has to catch.
What is checked is the one thing construction cannot guarantee: that the marker sits at a
sentence boundary and not inside a clause.

[archived/](archived/) holds everything this replaced — two transcript pipelines, the first
evaluation design, the retired dataset's audio, and the data all of them produced — with a note
on what each got wrong. The progression is the argument for the current design, so it is kept
rather than deleted.

## The audio

[make_audio.py](make_audio.py) renders with ElevenLabs `eleven_v3`. **This stage renders and
records what it rendered. It makes no judgement about the result** — whether a tag actually
became a laugh needs a listener, the way v3 sent every clip to speech models before trusting it,
and that belongs in its own stage where a verdict can be recorded and revisited. The durations
in the manifest are measurements, not evidence.

**Both halves of the audio live in git, because git is how they travel.** The takes go up from
wherever the text-to-speech was called; the machine that aligns and assembles them pulls those,
sews each conversation, and pushes the results back:

```
render  →  out/audio_turns/<renderer>/  →  git  →  align and sew
                                                →  out/audio/<renderer>/  →  git  →  evaluation
```

Neither half is disposable. The takes cannot be re-rendered identically — every ElevenLabs call
returns different samples — and the assembled conversations are what the evaluation actually
plays. `make_audio.py --sew` writes a hard-cut assembly to `out/audio_local_check/`, which git
ignores; it exists only to listen to a render locally, and uses the same filenames as the real
thing, so keeping both would make provenance unreadable.
[out/audio/README.md](out/audio/README.md) is the handoff contract.

### What is in `out/audio_turns/elevenlabs/`

168 mp3 files, 8.6 MB, plus `manifest.json`. **Per-turn takes, not conversations.** Each item
contributes seven:

| File | What it is |
| --- | --- |
| `<item>__t1.mp3` … `<item>__t5.mp3` | the five spoken turns, no vocalization |
| `<item>__t5__a.mp3` | turn 5 again, carrying condition A's tag |
| `<item>__t5__b.mp3` | turn 5 again, carrying condition B's tag |

So `v6_01a` is `t1, t2, t3, t4, t5, t5__a, t5__b` — 120 plain takes and 48 tagged across the
set. The vocalization is in turn 5 for every item, since that is where the design puts it, but
read `vocalization_turn` or the `assembly` block rather than relying on it.

`__a` and `__b` are that item's `voc_a` and `voc_b`, a different pair of sounds for each pair of
items: `v6_01a`'s `__a` is a laugh, `v6_06a`'s is a gasp. The manifest gives `dia_tag` and
`elevenlabs_tag` per take, so no filename has to be decoded.

**Turns 1 to 4 are shared bit-for-bit by all three conditions.** That is the point of storing
takes rather than conversations: an assembler that re-encodes or re-times them per condition
breaks the design, because a model answering differently might be answering to that.

### Render settings

| | |
| --- | --- |
| model | `eleven_v3` |
| format | `mp3_44100_128` |
| voice, speaker A | `s3TPKV1kjDlVtZbl4Ksh` |
| voice, speaker B | `aKw9UnnjRq5scbeeGI7Z` |
| stability | `0.30` for **every** take |

One stability for all of them, deliberately. A vocalization needs loose stability to fire at
all, and rendering the tagged turn loose while its plain counterpart was tight would make the
conditions differ in delivery as well as in sound.

### Reassembling the three conditions

The sewn conversations are **not in git** — `out/audio/` is ignored, because they are derived and
are rebuilt downstream. Each item's `assembly` block in the manifest is the recipe:

```json
"assembly": {
  "gap_seconds": 0.35,
  "turn_order": [1, 2, 3, 4],
  "baseline":    ["v6_03a__t1.mp3", "v6_03a__t2.mp3",    "v6_03a__t3.mp3", "v6_03a__t4.mp3"],
  "condition_a": ["v6_03a__t1.mp3", "v6_03a__t2__a.mp3", "v6_03a__t3.mp3", "v6_03a__t4.mp3"],
  "condition_b": ["v6_03a__t1.mp3", "v6_03a__t2__b.mp3", "v6_03a__t3.mp3", "v6_03a__t4.mp3"]
}
```

Concatenate in order with the gap between turns. `sew.py` does it locally with ffmpeg; anything
that concatenates will do.

**The turns without the vocalization are one file each, shared by all three conditions.** That
is the point, not an optimisation: turns 1, 3 and 4 are literally the same samples in every
condition, so nothing outside the tagged turn can differ. Re-rendering whole conversations per
condition would let the speech drift in every turn, and a model answering differently might be
responding to that drift. It also billed 6,766 characters instead of 12,880 — 47% less — but
that is the smaller reason.

What this design does **not** give you is byte-identical words in the tagged turn itself: it is a
separate take in each condition, because the tag is inside the line. The difference is confined
to that one turn.

## The evaluation

Five metrics, kept apart. A model can hear every vocalization and still answer as though it had
heard none — which is what v3 found — and an average would hide exactly that.

| | |
| --- | --- |
| [eval_config.yaml](eval_config.yaml) | models, judges, seeds, renderers. Credentials never live here |
| [evalkit.py](evalkit.py) | config, provenance, records, schemas, seeded draws, the dry-run guard |
| [validate_dataset.py](validate_dataset.py) | twelve checks on the source before anything is built on it |
| [build_tasks.py](build_tasks.py) | freezes the perception option sets |
| [write_annotations.py](write_annotations.py) | the three reference annotations, one call per item and condition |
| [build_pairs.py](build_pairs.py) | the directed paired-content trials |
| [score.py](score.py) | the metrics, with intervals clustered by item |
| [prompts/](prompts/) · [schemas/](schemas/) · [tests/](tests/) | 7 templates, 6 schemas, 69 tests |

The annotations `write_annotations.py` produces, all for the two vocalization conditions only:

| | |
| --- | --- |
| `interpretations` | the three defensible readings of this sound here. A model answers in its own words and passes if it matches any — the set is the boundary of understanding, not one right answer |
| `response_guides` | what the other speaker's reply should accomplish, written once per interpretation, so a model is scored against the reading it actually held |
| `tone_exclusions` | only the tones that are clearly wrong. Several deliveries are fine, and a prescribed profile would mark good replies wrong |

```bash
python3 v6/validate_dataset.py --renderer elevenlabs --require-audio
python3 v6/build_tasks.py
python3 v6/score.py --dry-run
python3 -m unittest discover -s v6/tests -t v6/tests
```

**Content and tone are scored on the two vocalization conditions only.** With no vocalization
there is nothing for a response to be appropriate *to*, so nearly any sensible reply fits the
baseline and a score against it measures fluency. The baseline keeps its place in perception,
where it is the false-positive test, and in the pragmatic question. So a response is elicited
twice per item, and the paired comparison is two directed trials — `CA` asking whether RA beats
RB, `CB` asking whether RB beats RA — rather than six.

**Each rubric is written from one condition alone.** One call per (item, condition, kind), with
the writer shown that version's turns and nothing about the other. An earlier design handed it
all three at once and asked for a contrastive field; that guaranteed the contrast and destroyed
it as evidence, since a writer that knows it is looking at a laugh *and* a sigh can always
phrase two requirements that differ whether or not the conversation supports it. Whether the two
rubrics actually differ is now a measurement about the item.
[out/eval/rubrics/superseded_joint_call/](out/eval/rubrics/superseded_joint_call/) holds what the
old design produced.

Two renderers speak the same 20 transcripts and are being compared, so the renderer is an
experimental factor: each owns a subtree, every record stamps which one produced the stimulus,
and every metric breaks down by it. The frozen questions are renderer-independent — the same
four options are asked about every rendering — which is what makes the comparison meaningful.

Task sets are written once and never overwritten. Correct-answer positions are balanced
15/15/14/14/14 over the 72 stimuli, a property of the whole set — so the item set is
fingerprinted into the task file, and a rebuild says whether it moved. There are no distractors
to balance: with four vocalizations plus `none` the whole inventory fits in one question, so
every question carries every label and only the order varies.

## Running the evaluation

Every stage is resumable — rerunning skips what is already on disk unless `--redo` is passed —
and every stage takes `--dry-run`, which prints the payloads it would send and calls nothing.

**Before anything, check the audio is there.** The assembled conversations come from whichever
machine sews them, so this is the step that catches a half-finished handoff:

```bash
python3 v6/validate_dataset.py --renderer elevenlabs --require-audio
```

It must report 24 of 24. Nonzero exit means missing or empty files, named individually.

**1 — ask the models.** Perception first, then interpretation in the *same* session, then a
reply in a *fresh* one:

```bash
python3 v6/run_models.py --renderer elevenlabs
```

Writes `out/eval/judgments/perception.jsonl`, `out/eval/responses/interpretations.jsonl` and
`out/eval/responses/responses.jsonl` plus a `.wav` per reply. A condition whose vocalization was
misidentified has its interpretation marked `gated_out` and gets no reply elicited.

**2 — build the ranking trials.** This reads the perception results, so it must come after
step 1:

```bash
python3 v6/build_pairs.py --responses out/eval/responses/responses.jsonl
```

Two directed trials per eligible item, and an `_ineligible.jsonl` beside them so coverage stays
computable.

**3 — run the judges**, in this order because `content` needs to know which interpretation each
model actually held:

```bash
python3 v6/run_judges.py --stage interp
python3 v6/run_judges.py --stage content --stage rank --stage tone
```

**4 — score:**

```bash
python3 v6/score.py
```

### What the runners will not let you do

**Perception and interpretation share one session; the reply does not.** Sharing the first two
is what makes interpretation conditional on perception rather than independent of it. Keeping
the reply separate — with a prompt that never mentions a vocalization — is what makes it a test
of whether the model notices the sound on its own. Both are enforced in `run_models.py` rather
than left to whoever runs it.

**Nothing regenerates the frozen task set.** `build_tasks.py` refuses to overwrite
`out/eval/tasks/perception.json` without `--overwrite`, because every evaluated model has to see
the same 72 questions with the same option order or their accuracies are not comparable.

**The judges never learn which model they are judging.** The evaluated model's id is in the
record, not in the prompt.

**The tone judges hear two separate recordings, not one joined file.** Joining them would be
less code, but the judge would have to find the boundary itself — and the turn immediately
before it is the one carrying the vocalization, so a judge that drifts rates the stimulus
instead of the reply, in the direction of the stimulus being the more marked of the two.
`providers.ask_many` sends both in one session; only the two providers that judge tone
implement it.

### Costs, per evaluated model per renderer

| Stage | Calls |
| --- | --- |
| perception + interpretation | 72 sessions |
| replies | up to 48, perception-gated |
| interpretation panel | up to 144 |
| content panel | up to 144 |
| ranking panel | up to 144 |
| tone panel | up to 96 |

The reference annotations are already written and shared by every model — 144 Claude calls,
spent once.

### If a stage half-fails

Records are appended as they are produced, so an interruption loses at most the call in flight.
A malformed judge reply is retried once, then kept with `status: invalid` and excluded from
every denominator rather than dropped, and `score.py` reports how many there were. An eligible
item whose judging failed entirely is named as `eligible but unjudged` — it stays in the
coverage denominator and out of the accuracy.

## What is not settled

- **The evaluation runners do not exist yet.** Everything offline is built — validation, the
  frozen perception set, pair construction, parsing, scoring, 69 tests — but nothing yet asks a
  model anything. `providers.py` already speaks to all four families over realtime websockets,
  so what is missing is wiring rather than new machinery.
- **The annotations have not been run.** Three kinds × 24 items × 2 conditions = 144 Claude
  calls, unspent. The prompts and schemas are in place and `--dry-run` previews every payload.
- **`groan` splits between two readings.** The planner marked it as needing something to land
  in the moment 6 times out of 12 — bodily pain needs a physical event in the scene, a stance
  toward something known does not. Both are legitimate; whether the split matters depends on
  whether the pairs containing it stay distinguishable.
- **Framings still cluster.** Removing the fixed mapping loosened it — laugh went from 12/12
  framed as comic absurdity to 9/12 — but the residue is probably intrinsic, since laughs really
  do usually mean something is being taken lightly. The three-interpretation design absorbs some
  of this: a model is no longer choosing between one right label and three wrong ones.
- **Dia has not rendered.** `out/audio/dia/{item_id}__{condition}.wav` is a placeholder. Both
  renderers are configured and every metric splits `by_renderer`.
- **Nothing has heard any audio.** Whether a tag became a laugh is a listening question with its
  own stage still to build.

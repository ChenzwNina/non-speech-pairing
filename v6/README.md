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

Four stages. Two call a model, one calls none, and one exists to reject what the others produce.

| | | writes |
| --- | --- | --- |
| **0** [seeds.py](seeds.py) | a flat random draw over 16,646 usable EmpatheticDialogues situations, no label filter | `out/seeds.json` |
| **1** [sample_items.py](sample_items.py) | assigns each item a seed and a pair of vocalizations. **No model is called** | `out/items.json` |
| **2** [plan_occasions.py](plan_occasions.py) | works out *when each sound would actually be produced*, then builds one moment that carries both | `out/occasions.json` |
| **3** [write_transcripts.py](write_transcripts.py) | writes five turns that arrive at that moment, checks them, builds the three versions | `out/transcripts.json` |

```bash
python3 v6/seeds.py --n 60
python3 v6/sample_items.py                    # 24 items · 6 pairs × 4 · 36 spare seeds held back
python3 v6/plan_occasions.py                  # 24 calls
python3 v6/write_transcripts.py               # 24 calls + one verifier call each
```

Every stage takes `--dry-run`, which prints the payloads it would send and calls nothing, and
`--only <item_id>` to work on one item. Stages 2 and 3 skip what is already on disk unless
`--redo` is passed, so a failed run resumes.

### Stage 1 calls no model on purpose

The pairs come from a balanced pool — each of the six combinations appears `--per-pair` times,
shuffled — so the draw is random without leaving one combination with a single item and another
with seven. Keeping it out of the planning stage makes the assignment a file you can read and
diff, rather than something that happened inside a loop, and the leftover seeds are recorded as
`spare` because stage 2 can find that a situation cannot honestly carry its pair.

### Stage 2 asks about the sound before it looks at the situation

The obvious pipeline writes the conversation and then attaches the vocalization. It produces
lines like this:

```
5  A: Yeah, I kept her number. I paid twelve dollars for it. (gasps)
```

The speaker is gasping at information he is himself delivering. Sounds are not interchangeable
in *when* they can be produced: a gasp is the instant of contact with something and cannot be
made about what you already know, while a sigh has no such requirement. Attaching the sound last
lets the strict cases fail silently.

So the planner is asked for each sound's production condition **before it sees the situation**,
then to satisfy the stricter of the two, then to outline five turns that arrive there. The
schema's field order is that reasoning order, which is why it is fixed. Asked that way it derives
the asymmetry itself — across 24 plans it marked `gasp` as requiring something to land in the
moment 12 times out of 12, `sigh` 0 out of 12, and `laugh` and `groan` genuinely mixed. No
vocalization is named in the prompt, so a fifth sound would need no new rule.

The same item, rebuilt from the sound outward:

```
4  B: Wait, a confirmation email just came in. Open it.
5  A: (gasps) It's for next week.
5  A: (groans) It's for next week.
```

### Stage 3 writes the words once

The writer returns the five turns with `«VOC»` marking where the sound goes, and the three
versions are built by substitution. Identical words, identical position, exactly one
vocalization, and none in the baseline are therefore true by construction rather than things a
validator has to catch afterwards.

Two things construction cannot guarantee, so both are checked:

**The marker must sit at a sentence boundary.** Turn-initial, turn-final, or between two
complete sentences — never inside a clause. `The team gave me story feedback «VOC» and told the
manager` is rejected. Which of the three is right follows from the moment the plan describes: a
sound reacting to what was just said comes before the words it prompts, and end-of-turn is for a
speaker landing on their own words.

**Each speaker must stay the same person.** This one needs a model, and it caught ten of the
first twenty-four:

```
1 A: How've the interviews been going?
2 B: This was my third one this month.
3 A: Everything you've heard from them has sounded encouraging.
4 B: Hang on, there's a new message from the employer. I'm opening it now.
5 A: They're asking me to schedule another interview next week.
```

Turns 1 to 4 make B the job seeker. Turn 5 has A speaking as that person. **Nothing else in the
pipeline can see it** — the words are identical across the three conditions, the marker is where
it belongs, the speakers alternate correctly, and the prose reads fluently. Only something
tracking who owns what finds it.

[prompts/speaker_consistency_verifier.txt](prompts/speaker_consistency_verifier.txt) is read by
`claude-opus-5`, a different family from the writer on purpose: a model asked to find the fault
in its own prose tends to explain why it is not a fault. It returns
`{consistent, problem, turns_involved}`, and a failure goes back to the writer with the
conflicting turn numbers quoted. **A verifier reply that cannot be parsed counts as a failure**,
because a check that returns nothing must not clear a draft it might have rejected.

The prompt lists what is *not* a failure as carefully as what is — one speaker knowing about the
other's situation, a shift in who drives the conversation, someone noticing a thing on the
other's screen — since a false alarm sends a usable conversation back to be rewritten.

`--no-verify` skips it. `writers.verifier` in [eval_config.yaml](eval_config.yaml) sets the model
and transport.

### Why the writer prompt had to change too

A verifier alone would have looped. The turn order is A-B-A-B-A, so turn 5 is always speaker A,
while a plan often puts the news on the other speaker — and the writer then moved the role across
to get the landing into turn 5. The first constraint in
[prompts/transcript_writer.txt](prompts/transcript_writer.txt) now says the speaker who lands it
in turn 5 is also the speaker of turns 1 and 3, so the roles are built that way round from the
start, with the failure above quoted as the worked example. Without that, the verifier would keep
rejecting drafts the plan had already made impossible.

The ten rewritten items carry `revision: 2` in `out/transcripts.json`, with the verifier's own
account of which role moved and between which turns. The top-level `revisions` block lists what
the change left stale — 70 takes and 30 assembled conversations — and what it did not.
`out/speaker_audit.json` has the verdict on all 24.

[archived/](archived/) holds the two transcript pipelines this replaced, the first evaluation
design, the retired dataset's audio, and the data all of them produced, with a note on what each
got wrong. The progression is the argument for the current design, so it is kept rather than
deleted.

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

Five metrics, kept apart, of which four run. A model can hear every vocalization and still
answer as though it had heard none — which is what v3 found — and an average would hide
exactly that. There is no composite score: each metric is computed and reported on its own.

**Ranking is off by default.** Measuring the pairs found only 10 of 24 items where the two
versions prefer different replies, so a pairwise judge over the whole set would spend three
judges per item choosing between two equally good answers on 14 of them. Nothing else
depends on it: perception, interpretation, response quality and tone each score one
condition against its own guides and need no contrast between the versions, so all 24 items
count in all four. `run_judges.py --stage rank` opts back in.

| | |
| --- | --- |
| [eval_config.yaml](eval_config.yaml) | models, judges, seeds, renderers. Credentials never live here |
| [evalkit.py](evalkit.py) | config, provenance, records, schemas, seeded draws, the dry-run guard |
| [validate_dataset.py](validate_dataset.py) | twelve checks on the source before anything is built on it |
| [build_tasks.py](build_tasks.py) | freezes the perception option sets |
| [write_annotations.py](write_annotations.py) | the three reference annotations, one call per item and condition |
| [measure_separability.py](measure_separability.py) | whether each item's two versions prefer different replies, measured before the freeze |
| [build_pairs.py](build_pairs.py) | the directed paired-content trials |
| [score.py](score.py) | the metrics, with intervals clustered by item |
| [prompts/](prompts/) · [schemas/](schemas/) · [tests/](tests/) | 15 templates, 9 schemas, 116 tests |

The annotations `write_annotations.py` produces, all for the two vocalization conditions only:

| | |
| --- | --- |
| `interpretations` | the one to three defensible readings of this sound here, each with the words that support it. A model answers in its own words and passes if it matches any — the set is the boundary of understanding, not one right answer |
| `response_guides` | what the other speaker's reply should accomplish, written once per interpretation, so a model is scored against the reading it actually held. `required_content` carries only what the sound obliges; everything else is an acceptable variation |
| `tone_exclusions` | only the tones that are clearly wrong. Several deliveries are fine, and a prescribed profile would mark good replies wrong |

### Can the two versions be told apart at all?

Ranking only measures something if the two versions prefer different replies. That has to be
established before the freeze, and the first attempt asked the wrong question.

It asked whether a reply appropriate for one version would be *inappropriate* for the other,
and failed 23 of 24 items — evenly across all six vocalization pairs. That uniformity was the
tell. A vocalization usually changes the **stance** a reply takes, not the **action** it
performs: laugh and sigh on the same words can both leave the other speaker saying "that spot
is easy to miss", the laugh inviting shared amusement and the sigh commiseration. Sixteen of
the 23 verdicts said as much in their own words — "only tone differs, not what B must do".
Demanding exclusivity rejects almost every well-written item. The check and its verdicts are
kept in [archive/binary_separability/](archive/binary_separability/) as evidence.

[measure_separability.py](measure_separability.py) measures the preference instead of asking a
model to declare it:

1. Each condition already has one to three readings of its own, written without sight of the
   other condition, and one guide per reading.
2. One natural reply is written per reading — from the reading, never from the guide, so
   scoring it against the guides measures fit rather than recall.
3. Every reply is scored 1–5 under **both** conditions, blind: the judge sees one version, one
   unlabelled reply, and no sign that another version exists. The score is taken against that
   condition's best-matching guide, so a reply following a minority reading is judged on that
   reading.
4. A reply's preference is `home - away`. The two conditions' readings are never paired up —
   the sets are different sizes and nothing needs to correspond across them.

The scale carries the measurement, and one line in it does the work: **5 is specifically right
for this version, 4 is fully appropriate and generic.** A generic reply scores the same under
both versions, so its preference is zero and it abstains — it neither proves the item nor
condemns it. An item separates when both sides lean toward the condition they came from.

The verdict is a function of the stored scores, so changing the threshold costs no calls:

```bash
python3 v6/measure_separability.py               # replies, scores, verdict
python3 v6/measure_separability.py --stage report  # re-decide from what is on disk
```

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

**Two audio sets, differing only in where two of the four vocalization clips came from.**

ElevenLabs' gasps and groans were judged inadequate by listening, so in the second set those two
sounds are Dia clips instead, voice-cloned from `reference/ElevenLabs_ref.mp3` so each sits in
the same voice as the speech around it. Laughs and sighs are unchanged.

| | speech | laugh · sigh | gasp · groan |
| --- | --- | --- | --- |
| `elevenlabs` | ElevenLabs | ElevenLabs | ElevenLabs |
| `dia_voc` | **the same takes** | ElevenLabs | **Dia** |

**The speech is identical in both.** Turns 1 to 4 and the words of turn 5 are the same samples
throughout, because the assembler inserts the vocalization into the clean take rather than
swapping the whole turn — nothing is removed. So the only thing varying between the sets is a
fraction of a second of sound, and a difference in results is attributable to that rather than
to voice, pacing or overall audio quality. That makes this a sharper comparison than rendering
both sets end to end with different engines would have been.

Every metric splits by set, and the frozen questions are set-independent: the same 72 perception
questions in the same option order are asked about both, and each task carries one audio path
per set.

**One confound to state when reporting.** Dia supplies only two of the four sounds, so clip
source is not separable from which vocalization it is. A difference between the sets says *gasp
and groan changed*, not *Dia clips are better*. Separating those would need Dia laughs and sighs
too, which is worth doing only if ElevenLabs' laughs and sighs also come into question.

**And the substitution is a finding, not only a fix.** If both sets are run, ElevenLabs' gasp and
groan conditions should show lower perception accuracy than its laughs and sighs — which turns a
listening judgement into a measured one.

### Costs, per evaluated model per renderer

| Stage | Calls |
| --- | --- |
| perception + interpretation | 72 sessions |
| replies | up to 48, perception-gated |
| interpretation panel | up to 144 |
| content panel | up to 144 |
| ranking panel | up to 144 |
| tone panel | up to 96, one recording each |

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
  frozen perception set, pair construction, parsing, scoring, 116 tests — but nothing yet asks a
  model anything. `providers.py` already speaks to all four families over realtime websockets,
  so what is missing is wiring rather than new machinery.
- **The tone exclusions have not been run.** `interpretations` and `response_guides` are written for all 24 items and both conditions — 125 readings, one guide each — leaving `tone_exclusions` as the only annotation still unspent.
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

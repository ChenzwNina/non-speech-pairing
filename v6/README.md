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

[archived/](archived/) holds the two pipelines this replaced, with a note on what each got wrong.
`out/transcripts_tag_at_end.json` and `out/transcripts_v2_placement.json` are the intermediate
attempts, kept because the progression is the argument for the current design.

## The audio

> **The takes in git are for the retired 20-item dataset.** They were rendered from
> `out/pairs_spoken.json`, which the three-stage pipeline replaced. The layout, settings and
> reassembly recipe below all still apply; the 24 new items have not been rendered.

[make_audio.py](make_audio.py) renders with ElevenLabs `eleven_v3`. **This stage renders and
records what it rendered. It makes no judgement about the result** — whether a tag actually
became a laugh needs a listener, the way v3 sent every clip to speech models before trusting it,
and that belongs in its own stage where a verdict can be recorded and revisited. The durations
in the manifest are measurements, not evidence.

### What is in `out/audio_turns/elevenlabs/`

120 mp3 files, 6.7 MB, plus `manifest.json`. **Per-turn takes, not conversations.** Each item
contributes six:

| File | What it is |
| --- | --- |
| `<item>__t1.mp3` … `<item>__t4.mp3` | the four spoken turns, no vocalization |
| `<item>__t<voc>__a.mp3` | the vocalization turn again, carrying condition A's tag |
| `<item>__t<voc>__b.mp3` | the vocalization turn again, carrying condition B's tag |

So `v6_01a` is `t1, t2, t2__a, t2__b, t3, t4` — 80 plain takes and 40 tagged ones across the set.

**`<voc>` is not always turn 2.** It is turn 2 for 14 items and turn 3 for 6. Read
`vocalization_turn` from the manifest rather than assuming, or read the `assembly` block, which
names the files directly.

`__a` and `__b` mean condition A and condition B, which are that item's `voc_a` and `voc_b` — a
different pair of sounds for every pair of items. `v6_01a`'s `__a` is a laugh; `v6_09a`'s is a
gasp. The manifest gives `dia_tag` and `elevenlabs_tag` per take, so no filename has to be
decoded.

Every take records the exact text sent, which for a tagged take is the transcript line with the
bracketed tag substituted:

```json
{ "turn": 2, "speaker": "B", "variant": "b",
  "text": "[sighs] Looks like the safari gave them a new game.",
  "dia_tag": "(sighs)", "elevenlabs_tag": "[sighs]",
  "path": "out/audio_turns/elevenlabs/v6_01a__t2__b.mp3", "seconds": 3.28 }
```

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
| [build_tasks.py](build_tasks.py) | freezes the multiple-choice option sets |
| [write_rubrics.py](write_rubrics.py) · [write_pragmatic.py](write_pragmatic.py) | the reference annotations |
| [build_pairs.py](build_pairs.py) | the two directed paired-content trials per item |
| [score.py](score.py) | the metrics, with intervals clustered by item |
| [prompts/](prompts/) · [schemas/](schemas/) · [tests/](tests/) | 9 templates, 4 schemas, 50 tests |

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
15/15/15/15 over the 60 stimuli and each of the six perception labels is used as a distractor
exactly 30 times, both properties of the whole set — so the item set is fingerprinted into the
task file, and a rebuild says whether it moved.

## What is not settled

- **The eval side is still wired to the retired dataset.** `eval_config.dataset.transcripts`
  points at `out/pairs_spoken.json`. The ElevenLabs audio, both frozen task sets and the
  pragmatic options were all built from it, and the perception inventory it froze has six labels
  where the current one has five. Flipping the config to `out/transcripts.json` invalidates all
  of them; `items_fingerprint` in each task file is what makes that detectable rather than
  silent.
- **Nothing has been rendered for the 24 items.** About 6,800 characters at the old scale.
- **The rubrics need rewriting.** Prompts, schemas and pipeline are changed to one rubric per
  condition, written from that condition alone; the annotations have not been regenerated.
  `out/eval/rubrics/superseded_joint_call/` holds what the old three-at-once design produced.
- **`groan` splits between two readings.** The planner marked it as needing something to land in
  the moment 6 times out of 12 — bodily pain needs a physical event in the scene, a stance
  toward something known does not. Both are legitimate; whether the split is a problem depends
  on whether the pairs containing it stay distinguishable.
- **Framings still cluster.** Removing the fixed mapping loosened it — laugh went from 12/12
  framed as comic absurdity to 9/12 — but the residue is probably intrinsic, since laughs really
  do usually mean something is being taken lightly. If the shortcut matters, the fix is the
  pragmatic distractor design rather than the stimuli: build all four options to share a surface
  emotion and differ in the specific appraisal, and naming the sound stops being enough.
- **Dia's paths are assumed.** `out/audio/dia/{item_id}__{condition}.wav` is a placeholder until
  that render lands. Both renderers are configured; every metric splits `by_renderer`.
- **Nothing has heard any audio yet.** Whether a tag became a laugh is a listening question and
  has its own stage waiting to be built.

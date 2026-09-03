# v6 · one conversation, two vocalizations

**The same four-turn conversation, heard three ways: with one non-speech vocalization, with a
contrasting one in the identical position, and with none at all.** The words are the same, the
speakers are the same, the position is the same. Only the sound differs — so if a model answers
differently, the sound is the only thing it can be answering to.

Where [v4](../v4/) gave the vocalization its own turn from a silent third speaker, v6 puts the
tag *inside* a spoken line, so the sound colours the delivery of the words around it. That is
the thing [v3](../laughter_sigh_contrast_v3/) explicitly could not do — its own caveat was that
"splicing is not amused delivery… a genuinely amused voice laughs *through* its speech."

## The design in one item

```
1  A: The kids are crawling around the living room like lions.
2  B: (laughs) │ (sighs) │ ⟨nothing⟩  Looks like the safari gave them a new game.
3  A: They've been playing it since we got home.
4  B: I'll move the coffee table out of their way.
```

Turn 4 is the line the sound reinterprets: *I'll move the coffee table* is either playing along
with the joke or clearing up after an exhausting afternoon, and nothing in the transcript
decides which.

## The inventory

Each vocalization carries the one emotion it is most strongly associated with, and the ten
possible pairs are each filled twice — 20 items.

| Vocalization | Emotion | Dia tag | ElevenLabs tag |
| --- | --- | --- | --- |
| laugh | amusement | `(laughs)` | `[laughs]` |
| sigh | resignation | `(sighs)` | `[sighs]` |
| gasp | surprise | `(gasps)` | `[gasps]` |
| groan | pain | `(groans)` | `[groans]` |
| scream | fear | `(screams)` | `[screams]` |

Two tag vocabularies because two services are in play. The transcripts carry Dia's parenthesised
tags, since that is what generation wrote; `make_audio.py` maps them to ElevenLabs' bracketed
form at render time. Neither is ever spoken aloud — each is an instruction to its own model.
[vocalization_emotions.md](vocalization_emotions.md) records why each emotion was chosen.

## How the dataset was built

| | |
| --- | --- |
| [seeds.py](seeds.py) | a flat random sample of EmpatheticDialogues situations, no label filter |
| [prompt.txt](prompt.txt) | the writer prompt, used verbatim with only its `{{…}}` placeholders filled |
| [generate.py](generate.py) | one call per pair of sounds; returns all three versions and checks the minimal pair holds |
| [spoken.py](spoken.py) | rewrites the register to spoken English at the same meaning |
| [out/pairs_spoken.json](out/pairs_spoken.json) | **the dataset.** Everything downstream reads this |

`gpt-5.6-sol` writes correct stimuli in stiff prose, so `gpt-4o` rewrites each transcript as
speech: 807 words to 808, 15 contractions to 31, 65 of 80 turns reworded. The tag travels
through that rewrite as a `«VOC»` marker and the three versions are rebuilt from the result, so
the minimal pair survives by construction rather than by the rewriter's good behaviour.

[out/pairs.json](out/pairs.json) is the pre-rewrite text and [out/pairs_multi_slot.json](out/pairs_multi_slot.json)
a superseded design (two or three sounds per conversation, six turns). Both are kept for the
record; neither is the dataset.

## The audio

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
| [build_pairs.py](build_pairs.py) | the directed paired-content trials |
| [score.py](score.py) | the metrics, with intervals clustered by item |
| [prompts/](prompts/) · [schemas/](schemas/) · [tests/](tests/) | 9 templates, 4 schemas, 50 tests |

```bash
python3 v6/validate_dataset.py --renderer elevenlabs --require-audio
python3 v6/build_tasks.py
python3 v6/score.py --dry-run
python3 -m unittest discover -s v6/tests -t v6/tests
```

Two renderers speak the same 20 transcripts and are being compared, so the renderer is an
experimental factor: each owns a subtree, every record stamps which one produced the stimulus,
and every metric breaks down by it. The frozen questions are renderer-independent — the same
four options are asked about every rendering — which is what makes the comparison meaningful.

Task sets are written once and never overwritten. Correct-answer positions are balanced
15/15/15/15 over the 60 stimuli and each of the six perception labels is used as a distractor
exactly 30 times, both properties of the whole set — so the item set is fingerprinted into the
task file, and a rebuild says whether it moved.

## What is not settled

- **`scream` does not survive this seed corpus.** Six of eight scream items were flagged by the
  rubric writers: EmpatheticDialogues situations are everyday, and a genuine fear-scream needs
  stakes they do not have, so it reads as mock-horror. In the `groan`/`scream` pair it is worse —
  a scream after a trapped foot signals *pain*, which is what `groan` means, so the two
  conditions collapse. Those two items are ambiguity-flagged and excluded from every denominator.
- **`groan` has the same shape, more mildly.** Pain is bodily, so it needs a physical event in
  the scene; without one the groan reads as dismay and collapses into the sigh's resignation.
- **Dia's paths are assumed.** `out/audio/dia/{item_id}__{condition}.wav` is a placeholder until
  that render lands.
- **Nothing has heard the audio yet.** 39 of 40 tagged takes are longer than their plain
  counterparts, which is consistent with the tags firing but does not establish it.

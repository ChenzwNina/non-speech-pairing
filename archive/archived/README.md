# non-speech-pairing

A benchmark, and the agent harness that curates it, for one question:

> **Does a speech-to-speech model understand what a laugh is *doing* in a conversation, or only
> that a laugh happened?**

Each item is a **contrastive pair**: one word-for-word identical script, performed two ways. The
words never change. The prosody changes, and with it the pragmatic function of the laugh — and so
the correct answer flips.

```
Shared transcript (this is all a text-only model ever sees):

    A: You put the bowls on the top rack again.
    B: That's where they were when I opened it.
    A: They come out wet up there.
    B: They came out dry last time.
    A: I moved them before I ran it.
    B: It's a dishwasher.                    <- the laugh goes here

Performance A — benevolence induction (cooperative)
    A: [even] You put the bowls on the top rack again.
    ...
    B: [coaxing laugh][warm] It's a dishwasher. [light chuckle][hopeful]
    -> the laugh is a friendly nudge inviting A to agree this is too small to keep going over

Performance B — mocking (non-cooperative)
    A: [flat] You put the bowls on the top rack again.
    ...
    B: [snort][condescending] It's a dishwasher. [derisive laugh]
    -> the laugh talks down to A, treating the concern as something to laugh at rather than answer
```

Same words. Opposite social act. A model that transcribes `<laugh>` and reasons over the text
cannot separate these, by construction.

## What's in here

`bench/items/` — five curated pairs, all five clean under `scripts/verify.py`:

| id | pair | the laugh lands on |
| --- | --- | --- |
| 001 | `show-enjoyment` / `show-sympathy` | "Oh man." (a tray tipped into a car footwell) |
| 002 | `benevolence-induction` / `mocking` | "It's a dishwasher." |
| 003 | `show-enjoyment` / `smoothing` | "About halfway through it." (drank a stranger's coffee) |
| 004 | `mark-irony` / `show-enjoyment` | "Well, that's good to know." (spare screws left over) |
| 005 | `social-bonding` / `show-disagreement` | "Of course you do." |

## Why contrastive pairs

The taxonomy this is built on — Mazzocconi, Tian & Ginzburg, *"What's Your Laughter Doing There?"*
— makes a claim that most laughter work ignores: **the acoustic form of a laugh does not determine
its function.** A laugh is an event anaphor pointing at a *laughable*, and its function falls out
of that plus the social, situational and linguistic framing. The paper's own words: laughters with
similar acoustic features can have different functions in different contexts.

So the only honest way to test function recovery is to hold everything else fixed and vary the
framing. See [docs/laughter-taxonomy.md](docs/laughter-taxonomy.md) for the taxonomy summary — four
laughable branches, thirteen functions, and the design implications each one has for item writing.

**Pair accuracy is the metric.** An item passes only if the model gets *both* performances right.
Because the words are identical, a model answering from the transcript, or from a fixed preference
for the more common function, scores **0** — not 50%. Independent guessing scores 25%.

## The harness

Three agent roles, run headless through the Claude CLI (Opus 5 by default for all three):

| Role | Sees | Must |
| --- | --- | --- |
| **writer** | the target function pair + taxonomy entries | invent a scenario whose words fit both readings, then perform it twice |
| **blind** | the tag-free transcript only | treat both readings as live options (see below) |
| **listener** | one tagged performance | recover *that* performance's intended function |

Between the writer and the judges sit mechanical gates that cost nothing and catch the failures
that quietly ruin a contrastive pair:

- **lexical drift** — strip the tags from either performance and you must get the transcript's exact
  word sequence. One changed word and the item is measuring vocabulary, not prosody.
- **tags in the transcript**, emotive punctuation (`!`, `…`, dashes, quotes), or any word from the
  laugh family in the tag-free transcript.
- **laugh is the final turn** — anything said *after* a laugh reveals how it landed. A smooth
  continuation reads as friendly, a stung reply reads as hostile, and a careful reader will use
  that. Closing on the laugh removes the channel.
- **laugh turn ≤ 6 words**, 4–6 alternating turns, laughter tag actually present on the laugh turn
  in both performances, and the two expected answers not paraphrases of each other.

### What the blind probe actually measures

Not leakage. Since the two performances share their words *exactly*, no text-only reader can tell
them apart — that is guaranteed, not measured. The probe measures two other things:

1. **Bivalence.** Does a strong reader accept both readings on these words? If it calls one
   impossible, that performance is a stretch and the item is dead.
2. **Prior strength.** With no acoustic evidence a reader falls back on base rates — a laugh
   between equals in a low-stakes exchange is probably affiliative; someone recounting their own
   mishap is probably self-deprecating. That prior is *recorded on the item*
   (`curation.text_prior`), not gated away, and it names the harder direction of the pair
   (`prosody_must_overturn`). A **confident** prior is disqualifying, because prosody will not be
   believed against it; a unanimous but hedged prior is fine.

Getting this wrong was the first thing the harness taught us. An earlier version rejected any item
where the blind vote was unanimous, and burned four rewrite attempts on `benevolence-induction vs
mocking` before the pattern became clear: the judge kept saying *"nothing in the words signals
contempt"* — a base rate, not a leak. Pass `--strict-split` to get the old, much stricter behaviour.

### Running it

```bash
python3 scripts/curate.py --list-pairs
```

```bash
python3 scripts/curate.py --pair benevolence-induction:mocking --n 1
```

```bash
python3 scripts/curate.py --auto --n 8 --attempts 3
```

Useful flags: `--skip-judges` (mechanical gates only — a cheap dry run), `--topic` to seed the
scenario, `--writer-model` / `--judge-model`, `--blind-runs` / `--listener-runs`, `--strict-split`.
No dependencies beyond the standard library and a `claude` binary on `PATH` (or
`CLAUDE_CODE_EXECPATH` set).

Each accepted item writes a bundle to `bench/items/<id>/`:

```
item.json    the full item: transcript, both performances, taxonomy metadata, probe, curation evidence
item.md      human-readable, for reviewing an item before spending TTS credits
tts.py       ready-to-run payloads — [{"voice_id": SPEAKER_A_VOICE_ID, "text": "[coaxing laugh] Come on, ..."}]
report.json  every judge run, verbatim, including the rejected attempts
```

and appends the item to `bench/dataset.jsonl`.

## Curated contrast pairs

Pairs are chosen to be **realisable on the same words** — that is the binding constraint, and most
function combinations fail it. Seven of the eight cross a taxonomy branch:

| Pair | Contrast |
| --- | --- |
| `show-enjoyment` / `show-sympathy` | mishap as a good story vs. a mishap that still hurts |
| `benevolence-induction` / `mocking` | cooperative vs. non-cooperative — the sharpest social flip |
| `show-enjoyment` / `smoothing` | bold act retold with relish vs. accident being smoothed over |
| `mark-irony` / `show-enjoyment` | laugh re-points the speaker's own words vs. enjoys them as said |
| `social-bonding` / `show-disagreement` | pure warmth, no incongruity vs. a laugh standing in for a rebuttal |
| `self-mocking` / `mark-funniness` | laughable from self vs. laughable in the situation |
| `thanking` / `smoothing` | receiving help well vs. being uncomfortable about needing it |
| `show-agreement` / `mocking` | antiphonal ratification vs. derision at the partner |

Add your own with `--pair fn_a:fn_b` using any two keys from `--list-functions`.

## Limitations, stated plainly

- **The judges read tags; they do not hear audio.** The discriminability gate is a text-level proxy
  for whether the performance carries the function. It catches performances that are weak *on
  paper*, which is most of them, but it cannot catch a TTS engine that ignores `[scoffing laugh]`.
  Every item ships with `curation.audio_verified: false`. Render the audio, listen, and flip it —
  ideally with human raters on the rendered pair, which is the only ground truth that counts.
- **Tag vocabulary is engine-specific.** The tags follow the expressive-TTS convention this project
  started from (`[amused]`, `[sympathetic laughing]`, stacked tags). Retarget
  `taxonomy.Function.tags` for a different engine.
- **English only, dyadic only.** The source paper found which cues carry function is
  language-dependent — arousal fails to predict function in Mandarin, speech-laughter fails in
  French — so this set says nothing about cross-lingual behaviour.
- **The writer and the judges are the same model family.** An item that survives Opus judges is not
  guaranteed hard for a differently-trained model, and the discriminability gate may be measuring
  shared conventions about what `[coaxing laugh]` means.

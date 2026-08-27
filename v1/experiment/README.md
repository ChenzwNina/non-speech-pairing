# `predicting_response/` — same setup, different vocalization → different next response

Can a model use Speaker B's non-speech vocalization to pick the appropriate next
spoken turn? The words leading up to it are held fixed, so a text-only model is guessing.

## Turn structure

Each version is exactly **6 turns** (`--context-turns 4`, the default):

| Turn | Speaker | Role |
| ---- | ------- | ---- |
| 1–3  | A       | Setup, building toward the trigger. **Word-for-word identical** across both versions. |
| 4    | A       | **The trigger** — the reveal, admission, or number B reacts to. |
| 5    | B       | The target vocalization, nothing else. B's first contribution to the dialogue. |
| 6    | A       | The reply the vocalization selects. |

B stays silent through the context because the eval splices in **external audio** for
B's vocalization — B's voice must never be established by earlier speech.

### The trigger rule

Turn 4 is what B reacts to, and nothing may sit between it and the vocalization. Early
versions of this generator let turn 4 drift into housekeeping after the reveal landed at
turn 3:

```
3. A: They cleaned up the recording and put it on a drive for us.   <- the actual news
4. C: It will be waiting at the front desk whenever we want it.     <- B reacts to this?
5. B: [gasp]
```

B's reaction then lands on the wrong beat. Turn 4 must be the beat that invites a
reaction, and it must not be a question — a question makes turn 6 an answer rather than a
reaction to B. Both are enforced: the question case mechanically, the placement by the audit.

### Speaker layouts

`--speakers 2` (default) is A and B only: A tells it across turns 1–4 as separate
utterances, B reacts, A replies. `--speakers 3` restores the A/C variant, where A and C
alternate through the context and one of them replies. `--context-turns 8` gives the
10-turn variant in either layout.

## Dataset

Six vocalizations — `[gasp]` `[grunt]` `[laughter]` `[sigh]` `[sob]` `[yawn]` — paired
every way, so 15 contrasts. `--n` sets pairs per contrast; the default 1 gives 15 pairs /
30 versions.

The writer picks each version's interpretation from that vocalization's meaning list
(gasp: surprise, shock, fear, admiration, disbelief, …) to fit the scene it invented,
rather than having a meaning assigned to it. Forcing the meaning produced items where the
reaction wasn't earned — "sadness" attached to a scene with no emotional weight. Meanings
already used for a contrast are fed back in, so `--n > 1` spreads across the list.

Example (`gasp_sob_001`):

```
1. A: I finally listened to the voicemail from the animal shelter.
2. A: They said a dog was brought in this morning without a collar.
3. A: They scanned its chip and found an old registration under Dad's address.
4. A: They think it's Maple—the dog who disappeared when we were kids.

Version 1                              Version 2
5. B: [gasp]        (disbelief)        5. B: [sob]     (emotional overwhelm)
6. A: I know, it sounds impossible.    6. A: I'll call them back now and tell
      I'll ask them to verify the            them we're coming; she has waited
      chip number before we tell Dad.        long enough.
```

## Checks on the writer

Neither of these is the benchmark — they are the schema the generated data has to pass.
An item is rejected and rebuilt, up to 4 attempts.

**Mechanical.** Exactly N context turns with the right speakers and no Speaker B; no
bracketed tags in the context; turn N is not a question; no line predicting B's reaction
(`B always laughs`, `can barely keep their eyes open`); each vocalization is the exact
plain tag, so no `[annoyed grunt]`; one shared responder; the two replies differ; neither
reply merely names the sound (`you sighed`, `you sound…`); the two interpretations differ.

**Model audit** (`--no-judge` to skip). Eight properties a regex can't check:

| Property | Rejects |
| -------- | ------- |
| `trigger_is_last_shared_turn` | B reacting to logistics, a summary, or an aside |
| `both_vocalizations_natural_here` | a gasp with nothing surprising, a yawn with no tedium |
| `interpretations_fit_the_context` | a meaning forced onto a scene that doesn't earn it |
| `undecidable_from_text_alone` | context that already points at one reply |
| `replies_commit_to_different_actions` | same decision in two tones |
| `voc1_favors_reply1` / `voc2_favors_reply2` | a link that is merely compatible, not specific |
| `swapping_replies_is_clearly_worse` | replies that swap without the dialogue degrading |

The swap test earns its place. This item passed everything else and is still bad:

```
4. C: So do I put that bit before or after the case study?
[gasp]      -> "Before. That reveal is too good to bury."
[laughter]  -> "After. We'll use the mascot bit as the closing joke."
```

A gasp doesn't inherently mean "put it first". Items built on an arbitrary two-option
choice swap freely, so the audit rejects them.

Each surviving record carries its `judge` verdict, `trigger_note`, attempt count, and
token usage.

## Usage

```bash
python predicting_response/generate.py                      # 15 pairs, A+B, 6 turns
python predicting_response/generate.py --speakers 3         # A and C converse
python predicting_response/generate.py --context-turns 8    # 10-turn variant
python predicting_response/generate.py --n 2                # 30 pairs
python predicting_response/generate.py --contrast laughter-sigh
python predicting_response/generate.py --dry-run            # print prompts only
```

Writes `out/pairs.json` and `out/pairs.md`.

`verify.py` re-runs the mechanical checks over a saved `pairs.json` and tallies the audit
properties, with no API calls:

```bash
python predicting_response/verify.py
```

## Current run

14 of 15 contrasts produced a valid pair; all 14 pass every audit property. `gasp`–`sob`
did not land in 8 attempts: both are high-arousal reactions to significant news, so a reply
that one motivates — slow down and verify, or move immediately — the other motivates too.
Re-running that contrast alone may land one, since it passed once during development.

## Audio

```bash
python predicting_response/generate_audio.py             # synthesize + splice + sew
python predicting_response/generate_audio.py --limit 2   # first two pairs only
python predicting_response/generate_audio.py --sew-only  # re-sew, no TTS spend
```

Turns 1–N and the reply are synthesized with ElevenLabs `eleven_v3` in voice
`r1KmysJdVYZjJCm4mL3b` — the same voice `pairing_type` uses for A. Speaker B is never
synthesized: turn N+1 is a **real recording** drawn from `audio_non-speech/<voc>/`.

Two variants are sewn per version, from the same turn files and the same clip choice, so
they always agree:

```
audio_prompt/  turn 1 +0.40 turn 2 +0.40 turn 3 +0.40 turn 4 +0.35 [clip]
audio_full/    the same, then +0.35 reply
```

**`audio_prompt/` is the eval input** — it ends at B's vocalization, so the reply the model
is asked to choose is not audible. `audio_full/` is for reading the dataset back by ear;
`--no-full` skips it.

Turns 1–N are shared by both versions of a pair, so they are synthesized once and reused.
Existing turn files are left alone unless `--overwrite`, so re-runs don't repay for TTS.

Output:

- `out/audio_prompt/<pair_id>_v1.mp3`, `_v2.mp3` — ends at turn 5 · 14.9–25.0s
- `out/audio_full/<pair_id>_v1.mp3`, `_v2.mp3` — includes turn 6
- `out/audio_turns/<pair_id>/` — the individual synthesized turns
- `out/audio_manifest.json` — clip choice, both paths, and durations per version

### Clip selection

Clips are drawn **least-used-first, randomly among the tied** (`--seed` to change, default
0), so the dataset spreads across a folder instead of leaning on a few recordings.
`audio_manifest.json` records every choice in `clips`, a `clip_usage` tally per file, and
per-vocalization `coverage`. A re-run carries the previous tally forward so it keeps
spreading; `--reset-usage` starts over.

Note the folder name for `[sob]` is `sobbing/`, mapped in `VOC_DIRS`.

### Length guard

Only clips between 0.3s and 10s are eligible; anything outside that is skipped and listed in
the manifest's `excluded_clips`. Three files were originally long compilations that would
have dwarfed a ~20s dialogue (a 69s "gasp"); they have since been trimmed, so all six
folders are fully eligible and `excluded_clips` is empty. `audio_non-speech/extra-source/`
is not a vocalization folder and is ignored.

Clip counts: gasp 18, grunt 15, laughter 18, sigh 18, sobbing 18, yawn 18.

## Eval

```bash
python predicting_response/eval_realtime.py
python predicting_response/eval_realtime.py --limit 2
python predicting_response/eval_realtime.py --resume --seed 0
python predicting_response/eval_realtime.py --separate-sessions
```

Items are shuffled, then each `audio_prompt/` clip is played **once** and two questions are
asked in the same session, so both answers come from one listen:

1. **Which non-speech sound was at the end?** Six options — gasp, grunt, laughter, sigh,
   sob, yawn — in a shuffled order per item. Chance 16.7%.
2. **What would the speaker say next?** The two turn-6 replies from the pair, shuffled. The
   distractor is the sibling version's reply, so the words up to the vocalization are
   identical and only the sound distinguishes them. Chance 50%.

The session is told it will hear a conversation between two people where one does all the
speaking and the other reacts at the end without words.

Because Q1 comes first in the same session, its answer can scaffold Q2.
`--separate-sessions` re-plays the audio in a fresh session for Q2 to measure that effect.

Two notes on the harness: `gpt-realtime-2.1` spends output tokens on reasoning before
answering, so `MAX_OUTPUT_TOKENS` must leave real headroom — a 16-token cap returns an
empty string every time. And Q2 is asked by appending to the conversation rather than with
`conversation: "none"`, which is what keeps the audio in context.

### Result — `gpt-realtime-2.1`, seed 0, 28 items

| | score | chance |
| --- | --- | --- |
| Q1 vocalization | **24/28 = 85.7%** | 16.7% |
| Q2 next reply | **21/28 = 75.0%** | 50.0% |
| both | 19/28 = 67.9% | 8.3% |

Q2 splits sharply by whether Q1 landed: **79.2%** when the sound was identified, **50.0%**
— chance — when it wasn't. Only 4 items had Q1 wrong, so treat that split as suggestive.

Per vocalization:

| voc | Q1 | Q2 |
| --- | --- | --- |
| gasp | 4/4 | 3/4 |
| grunt | 3/5 | 5/5 |
| laughter | 4/5 | 4/5 |
| sigh | 4/5 | **1/5** |
| sob | 4/4 | 3/4 |
| yawn | 5/5 | 5/5 |

`sigh` is the outlier: recognized 4/5 but only 1/5 on the reply. The model hears the sigh
and still picks the wrong continuation, which fits sigh having the widest meaning spread in
the inventory — frustration, disappointment, relief, resignation, impatience, exhaustion —
where relief and frustration point at opposite next moves. Worth a closer look before
trusting the sigh items.

Q1 confusions are all within-family: grunt → sigh or laughter, laughter ↔ sigh. gasp, sob,
and yawn were never missed.

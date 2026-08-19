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

## Not built yet

Audio and the eval. The intended eval is a two-way forced choice: splice
`turns 1–4 speech + external B vocalization`, then ask which of the two turn-6 replies
fits, using the pair's other reply as the distractor. See `pairing_type/sew_audio.py` for
the splicing pattern and `pairing_type/eval_realtime.py` for the listening harness.

Two speakers makes the audio simpler than the A/C variant — one synthesized voice for the
context and reply, one spliced recording for B.

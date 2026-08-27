# `predicting_response_upgraded/` — 2-turn vocalization benchmark, three questions

A different benchmark shape from `predicting_response/`. There, A speaks several turns and
reacts to B's vocalization. Here the interaction is minimal: **A says one line, B answers
with only a vocalization, and the audio stops there.** Nothing else is ever synthesized —
B's predicted follow-up line is a text-only gold answer, never spoken.

## Turn structure

```
Turn 1  A: [one line]              <- identical across both versions
Turn 2  B: [vocalization]          <- the entire benchmark audio ends here
```

Each version also carries, as data (not audio):

- **gold interpretation** — one sentence on what B's vocalization means *here*
- **gold verbal continuation** — what B would plausibly say next, text only

## Three questions per clip

1. **Which vocalization?** — 6-way: gasp / grunt / laughter / sigh / sob / yawn.
2. **What does it mean here?** — 2-way, forced choice: the two versions' own gold
   interpretations, nothing else.
3. **What would B say next?** — 2-way, forced choice: the two versions' own gold
   continuations, nothing else.

Q1 is the same kind of check as `predicting_response`'s. Q2 and Q3 have no random
distractors — an earlier version of this folder generated two extra options per question,
but they kept being eliminable just by noticing they were about a different topic than the
scene, without any pragmatic reasoning at all (see "What changed" below). Removing them
makes the design cleaner: Q2 and Q3 are now purely "which of these two golds goes with which
sound," so every point of difficulty comes from the vocalization itself, not from spotting
an off-topic filler option.

## Why this is harder to generate correctly than it looks

With no distractors to fall back on, the two gold answers for Q2 and Q3 must themselves be
*individually* right and *jointly* non-interchangeable — there's nothing else in the option
set to make the question easy. The whole design rests on a **swap test**: reply 1 must
sound noticeably worse after vocalization 2 than reply 2 does, and vice versa — for both the
interpretation and the continuation. A pair that fails this test isn't wrong exactly, it's
just not testing anything: the model could get both questions right without ever needing
the audio.

## Generation + verifier

Given the swap test is exactly the kind of judgment a regex can't make, this folder splits
checking into two passes, same architecture as `predicting_response/generate.py`:

**Mechanical** (`validate()`, no API call) — shape, leakage, and gold-pair bookkeeping:

- Turn 1 doesn't literally contain a vocalization word or a giveaway phrase ("exhausted",
  "burst into tears")
- neither gold interpretation is a bare label ("B is laughing") rather than a pragmatic
  reading
- neither response/interpretation names the vocalization
- the two interpretations differ from each other; the two responses differ from each other
- word-count caps, non-empty fields, a real rationale

**Judge** (`judge_pair()`, one more model call, skip with `--no-judge`) — the parts that
need actual judgment:

- would the swap make either interpretation or either response sound about as natural as
  the intended pairing? (the real swap test)
- are the two interpretations / two responses pragmatically distinct, or the same move in
  different words?
- is a negative vocalization (grunt/sigh/sob/yawn) still answered as if B simply agreed or
  was fine — the specific bug that showed up repeatedly in `predicting_response`'s early
  rounds

An item that fails is rebuilt with the specific failed checks fed back into the prompt, up
to 4 attempts, then recorded as a failure with its last draft preserved (`--verbose` prints
every attempt live).

## Usage

```bash
python predicting_response_upgraded/generate.py                       # 15 pairs
python predicting_response_upgraded/generate.py --contrast gasp-sigh  # one contrast
python predicting_response_upgraded/generate.py --n 2                 # 30 pairs
python predicting_response_upgraded/generate.py --no-judge --verbose  # mechanical only, see every draft
python predicting_response_upgraded/generate.py --dry-run             # print prompts only
python predicting_response_upgraded/generate.py --theme family        # scope scenes to a domain
python predicting_response_upgraded/verify.py                         # re-check a saved pairs.json, no API calls
```

Writes `out/pairs.json` (records, judge verdicts, token usage, attempt counts) and
`out/pairs.md` (a readable render — option lettering there is for reading only; a real
eval would shuffle each question's two options independently, the way
`predicting_response/eval_realtime.py` does for its own questions).

`--theme` (`domestic` / `family` / `school` / `work`) isn't part of the original spec —
added so scenes can be scoped to a domain, same theme definitions as
`predicting_response/generate.py`. Themed pair ids get the theme as a prefix
(`family_gasp_grunt_001`).

## Writer model: `gpt-5.6-terra`, not `gpt-4o`

Both were tried head-to-head on the same theme and contrast (`family`, `gasp-grunt`).
`gpt-4o`'s pair passed every mechanical check and every judge property, but on inspection
the swap test was weaker than it should have been:

> A: Uncle Joe just announced he's moving to Japan next month for work.
> gasp → "I didn't even know he was considering an overseas job."
> grunt → "He always rushes into things without warning us."

Swap those and neither reads clearly wrong — both are just reactive remarks about the news,
differing in tone rather than in conversational move. The judge approved it anyway, which is
itself worth remembering: a single LLM judge pass can miss a soft failure that's obvious on
a human read. `gpt-5.6-terra`'s version of the same theme/contrast was sharper:

> A: My sister says Mom and Dad secretly renewed their vows, and she's invited the whole
> family to surprise them at a restaurant next Saturday.
> gasp → "They renewed their vows? Mom is going to be speechless when we all walk in." (celebrate)
> grunt → "She cannot expect me to miss my daughter's recital because she planned this without
> asking." (object to being excluded from scheduling)

Celebrate vs. raise a scheduling objection are genuinely different moves, not just different
tones on the same statement — swapping them visibly breaks both. `generate.py` defaults to
`gpt-5.6-terra`; `--model gpt-4o` still works if you want to compare again.

## What changed: distractors were removed

The original spec called for two extra options each for Q2 and Q3 (an interpretation
distractor pair and a response distractor pair). In practice they tended to solve
themselves: early distractors were about a different topic than the scene entirely (e.g.
"B is relieved that a sibling argument has ended" for a recipe-book handoff), so a listener
could eliminate them on subject alone, without any pragmatic reasoning. Tightening the
prompt to require distractors stay anchored to the same event fixed that specific problem,
but at that point the distractors were adding generation cost and complexity without adding
much test difficulty beyond the Gold-1-vs-Gold-2 question that was already the hard part.
They were dropped; Q2 and Q3 are now a straight forced choice between the two golds.

## First run (4-way distractor design, superseded)

`gasp-laughter` passed on attempt 1: Turn 1 ("I told the interviewer I was fluent in
Italian, and she has invited me to join a client call in Milan tomorrow.") is genuinely
open to either reaction, and the two golds land on clearly different moves — gasp → warn
("You need to tell her the truth before that call starts."), laughter → tease ("At least
you'll finally learn how to say, 'I exaggerated,' in Italian.").

`grunt-sigh` failed after 4 attempts — the judge kept correctly rejecting it because a
skeptical grunt reply and a relieved-but-wary sigh reply were both natural after the same
uncertain-good-news setup; the swap test never cleared. This is the same contrast that gave
`predicting_response` trouble (there it was `gasp-sob`) — some vocalization pairs may simply
resist a clean contrast more than others, which is itself worth tracking across runs rather
than forcing through on a 5th retry.

## Not built yet

Audio and the eval. The eval only ever needs turns 1–2 (A's line + B's spliced vocalization
recording) — the continuation text never gets synthesized, so the audio side of this is
simpler than `predicting_response`'s. See `predicting_response/generate_audio.py` for the
splicing pattern and `predicting_response/eval_realtime.py` for the listening harness; Q2/Q3
here would need a 2-way MCQ builder alongside Q1's existing 6-way one.

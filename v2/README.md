# v2 · The assistant proposes, the user reacts with a sound

**Give a speech-to-speech model a scenario, let it propose something, then answer only with a
non-speech sound. Does its next turn change with the sound?**

Unlike v1 and v3, nothing here is scripted for the model. It is told in one line what it is
helping with, it proposes something **of its own**, and the user's reply is a real recording —
a yawn, a sigh, a gasp, laughter — with no words. Then it has to speak again.

```
instructions   "You are helping the user find eight hundred dollars a month in their
                budget after a surprise tax bill."
user (text)    "Okay — what do you think we should do?"
model speaks   its own proposal, captured as audio and text
user (audio)   the vocalization, alone
model speaks   the turn we are measuring
```

## What we found

**A sound on its own moves the model. Words beating it stop it dead.**

| condition | trials | model changed course |
| --- | --- | --- |
| the sound alone | 5 | **5** |
| positive words *then* a negative sound | 10 | **0** |
| a negative sound *then* positive words | 10 | **0** |
| the same reluctance stated **in words** | 5 | **5** |

The identical message — "I don't want to do this" — is ignored as a sigh and acted on as
text, where four of five replies opened *"Totally fair to feel that way"* and visibly shrank
the plan. The capability is there; the audio channel does not reach it.

Two replies show the sound being perceived and then discarded rather than missed: a grudging
grunt relabelled as *"the happy little growl of excitement"*, and *"Love the energy, even with
the yawn."*

## The one condition that worked

**Playful mock-reproach after a tempting proposal** — the user laughs and says something like
"you're such a bad influence", which is blame for having been tempted and carries an implied
yes.

| | laughed | said flat |
| --- | --- | --- |
| played along | **5/5** | **2/5** |

Two conditions on it. The proposal has to be genuinely indulgent — with a prudent one only
3/5 worked. And it is model-specific: grok on the identical protocol scored 3/5 versus 3/5.

## What is here

```
assistant_proposal/    the live version: the model writes its own proposal
  run.py               --line none | attitude | neutral | mismatch | voc_first |
                       lexical_first | tease | tease_plain
  eval_grok.py         the same protocol on grok, for cross-model comparison
  compare.py           builds compare.md — every condition of a task side by side
  out/audio/           full conversations: proposal + the sound + the reply
  out/compare.md       the readable comparison
make_response/         the scripted precursor: a writer model builds a proposal that
                       laughter, sigh and gasp would all fit, synthesized once and reused
```

## A caveat worth knowing

In `assistant_proposal` the proposal is generated **live in each session**, so the sigh
condition and the laughter condition received *different* proposals. Nothing could be tuned
to the sound, but the control is weaker than it looks: a behavioural difference could come
from the proposals differing rather than from the reaction.

`make_response/` has the opposite trade — one synthesized proposal reused across conditions,
at the cost of the model reacting to someone else's plan. v3 resolves it: the conversation is
synthesized once and the conditions are the same audio with different sounds spliced in.

# v6 · the vocalization inventory

Four non-speech vocalizations. Every unordered pair of them is used, giving six contrasts.

| # | Vocalization | Default reading (historical) | Dia tag | ElevenLabs tag |
| --- | --- | --- | --- | --- |
| 1 | **laugh** | amusement | `(laughs)` | `[laughs]` |
| 2 | **sigh** | resignation | `(sighs)` | `[sighs]` |
| 3 | **gasp** | surprise | `(gasps)` | `[gasps]` |
| 4 | **groan** | pain | `(groans)` | `[groans]` |

**`default_reading_historical` is a record, not an input.** It is what an earlier design fixed
as each sound's meaning, kept because that decision is part of how this dataset got here. The
planning stage is *not* given it.

It was given it once, and the result is why the column is now labelled historical: every laugh
came back framed as comic absurdity and every sigh as resigned acceptance, 12 out of 12 each.
A fixed mapping makes the pragmatic task answerable by identifying the sound and applying a
rule, without using the conversation at all — which is the thing this benchmark is trying to
measure rather than assume. `out/plans_with_default_reading.json` holds that run.

**`scream` was dropped.** It was in an earlier inventory and did not survive contact with the
seed corpus: EmpatheticDialogues situations are everyday interpersonal ones, and a genuine
fear-scream needs stakes they do not have, so six of eight scream items read as mock-horror or
collapsed into pain. Removing it also removes the pair whose two conditions were
indistinguishable — a scream after a physical mishap signals pain as readily as fear, which is
what `groan` already means.

Two tag vocabularies because two services render the audio. The transcripts carry Dia's
parenthesised tags; `make_audio.py` maps them to ElevenLabs' bracketed audio tags. Neither is
ever spoken aloud — each is an instruction to its own model.

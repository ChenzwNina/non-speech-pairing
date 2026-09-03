# v6 · Vocalization → emotion

Five non-speech vocalizations, each mapped to the **one** emotion it is most strongly
associated with — the reading a listener reaches for by default when they hear the
sound with nothing else to go on.

| # | Vocalization | Emotion | Dia tag | ElevenLabs tag | How it is produced |
| --- | --- | --- | --- | --- | --- |
| 1 | **laugh** | amusement | `(laughs)` | `[laughs]` | voiced rhythmic bursts, long decay, released freely |
| 2 | **sigh** | resignation | `(sighs)` | `[sighs]` | low flat creaky exhale, no tension peak before it — the thing happened and is being accepted |
| 3 | **gasp** | surprise | `(gasps)` | `[gasps]` | abrupt sharp inhale, hard glottal onset |
| 4 | **groan** | pain | `(groans)` | `[groans]` | low sustained voiced, involuntary, tracks a hurt or an effort |
| 5 | **scream** | fear | `(screams)` | `[screams]` | high f0 with roughness and harshness, abrupt onset, sustained |

Five distinct emotions: amusement, resignation, surprise, pain, fear.

`sigh` is labelled *resignation*, not *relief* or *sadness*. Relief is the other
strong default reading and is positive, which this set does not want. Resignation fits
the action better than sadness does — a sigh is what accepting an unwanted outcome
sounds like — and it gives a clearer interpretive shift when dropped into a
conversation than plain sadness would.

`gasp` is labelled *surprise* and `scream` *fear* — the canonical labels. An earlier
draft used the narrower *alarm* and *terror*, which existed only to contrast against a
second emotion per sound; with one emotion per sound the canonical label is the right
one.

## Recordings

Not sourced from `../audio_non-speech/`. The audio is generated from the transcript with
the tag in place rather than spliced in, so the vocalization colours the delivery of the
words around it instead of being a discrete sound dropped into a gap.

Two tag vocabularies, because two services are in play. The transcripts carry Dia's
parenthesised tags, since that is what generation wrote; `make_audio.py` maps them to
ElevenLabs' bracketed audio tags when it renders. Neither is spoken aloud — each is an
instruction to its own model.

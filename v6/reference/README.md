# Voice reference

`ElevenLabs_ref.mp3` — 6.84s, 44.1 kHz mono, rendered by ElevenLabs with the two voice ids the
dataset uses. Not a stimulus; nothing in `out/` is derived from it. It exists so the voices
behind the dataset can be identified, and so a cloning renderer has something to clone from.

```
[S1] Did you end up going to that new café near campus?
[S2] Yeah, I went yesterday after class. It was actually pretty nice.
```

| Tag | Voice id | Dataset speaker |
| --- | --- | --- |
| `S1` | `aKw9UnnjRq5scbeeGI7Z` | **B** |
| `S2` | `s3TPKV1kjDlVtZbl4Ksh` | **A** |

## `ElevenLabs_correct_speaker_ref.mp3` — the voice to clone

4.05s, 44.1 kHz mono. One voice, isolated, supplied as the timbre a cloning renderer should
reproduce.

**One voice is all that is needed.** Dia supplies only the gasp and groan clips, and the
vocalization is always produced by the speaker of turn 5 — speaker A in every item, because the
turns run A-B-A-B-A. Speaker B never makes a sound, so its voice never has to be cloned.

**Two things about this file are not recorded, and both are left blank rather than guessed:**

- **Which dataset speaker it is.** Speaker A, `s3TPKV1kjDlVtZbl4Ksh`, is the inference — A
  produces every vocalization — but that is not stated anywhere and has not been confirmed by
  listening.
- **Its transcript.** A cloning renderer conditions on the recording together with the words
  spoken in it, so without them this file cannot be used reproducibly. This is the same gap the
  earlier Dia reference had.

## The two-speaker clip, and why its mapping runs backwards

**`S1` is the dataset's speaker B, and `S2` is speaker A.** `make_audio.py` pins
`A -> s3TPKV1kjDlVtZbl4Ksh` and `B -> aKw9UnnjRq5scbeeGI7Z`, which is the reverse of the tag
order here.

Wiring Dia as `S1 -> A`, `S2 -> B` would put each conversation's voices on the wrong speakers
relative to the ElevenLabs renders. It would not fail or sound broken — turn 1 would simply be
spoken by the voice that says turns 2 and 4 in the other renderer. Since every metric splits by
renderer, that swap would surface as a renderer effect and be indistinguishable from one.

## What it replaces, and why one clip is better than three

Three files: a solo clip per ElevenLabs voice, and a separate Dia clip whose transcript was
never written down. That last gap meant Dia could not be run reproducibly at all.

One two-speaker clip fixes both. It has a transcript, which is what a cloning renderer needs
alongside the recording, and it carries both voices in the arrangement the dataset uses — so
cloning from it should put Dia's speech in the same timbres as the ElevenLabs speech.

That is worth more than tidiness. The renderer comparison was previously confounded: ElevenLabs
spoke in two catalogue voices and Dia in whatever its old reference happened to sound like, so a
difference between renderers carried a difference in voice as well as in how the vocalization
was produced. Cloning from this clip removes that, and leaves the comparison closer to being
about the vocalization alone.

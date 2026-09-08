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

## `ElevenLabs_correct_speaker_ref.mp3` — the timbre to match

4.05s, 44.1 kHz mono. One voice, isolated. It is a **reference for verification, not an input
to cloning**: an audio model compares a generated gasp or groan against it and says whether the
clip sounds like the same person as the ElevenLabs speech it will be spliced into.

That check matters because `dia_voc` splices a Dia clip into ElevenLabs speech. If the clip
carries a different voice, the splice is audible, and a model hearing the stimulus is reacting
to a speaker change rather than to a vocalization.

**It needs no transcript.** A verifier comparing timbre does not read words. The transcript
requirement belongs to cloning, and the clip cloning conditions on is `ElevenLabs_ref.mp3`,
whose transcript is recorded below.

One thing about it is not recorded: **which dataset speaker it is.** Speaker A,
`s3TPKV1kjDlVtZbl4Ksh`, is the inference — A produces every vocalization, so A's is the only
voice a clip ever has to match — but that is not stated anywhere and has not been confirmed by
listening. It matters for reading a verdict, not for running the check.

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

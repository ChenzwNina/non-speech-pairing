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

## The mapping runs backwards — read this before wiring a cloning renderer

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

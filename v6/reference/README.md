# Voice references

Three clips, three jobs. None is a stimulus — nothing in `out/` is derived from them.

| File | Job |
| --- | --- |
| `ElevenLabs_ref_single_speaker.mp3` | **what a cloning renderer clones from** — one voice, speaker A, transcript recorded |
| `ElevenLabs_correct_speaker_ref.mp3` | the timbre a generated clip has to match, for a verifier to compare against |
| `ElevenLabs_ref.mp3` | documents which voice id is which dataset speaker |

## ⚠ `S1` means a different person in different files

| File | S1 | S2 |
| --- | --- | --- |
| `ElevenLabs_ref_single_speaker.mp3` | **A** | **A** (one voice throughout) |
| `ElevenLabs_ref.mp3` | **B** | **A** |

The numbering is per-file and does not carry over. Reading `S1` without checking which file it
came from gets it backwards, and a cloning renderer wired that way produces the wrong voice —
which will not fail, only sound like someone else.

## `ElevenLabs_ref_single_speaker.mp3` — the clone source

6.61s, 44.1 kHz mono, one voice throughout: dataset speaker A, `s3TPKV1kjDlVtZbl4Ksh`.

```
[S1] Yeah, I went yesterday after class. It was actually pretty nice.
[S2] We had a cup of coffee and chat a lot about what recently happened.
```

**One voice is the point.** Dia only ever produces speaker A's gasps and groans — the turns run
A-B-A-B-A, so the vocalization always falls in A's turn 5, and speaker B never makes a sound. A
reference carrying two voices lets a cloning renderer pick the wrong one or invent a second; one
voice under both tags leaves it nothing to get wrong.

The first line is verbatim what A says in the two-speaker clip, which is how the voice was
identified.


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

**It is speaker A**, `s3TPKV1kjDlVtZbl4Ksh` — confirmed, not inferred. That is the only voice
a clip ever has to match: the turns run A-B-A-B-A, so the vocalization always falls in turn 5,
which is A's. Speaker B never makes a sound.

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

# Voice references

Recordings of the voices, not stimuli. Nothing in `out/` is derived from them — they exist so
the voices behind the dataset can be identified, compared and reproduced.

| File | Renderer | Speaker | Voice id |
| --- | --- | --- | --- |
| `ref_s3TPKV1kjDlVtZbl4Ksh.mp3` | elevenlabs | A | `s3TPKV1kjDlVtZbl4Ksh` |
| `ref_aKw9UnnjRq5scbeeGI7Z.mp3` | elevenlabs | B | `aKw9UnnjRq5scbeeGI7Z` |
| `dia_reference.wav` | dia | — | cloned, not pinned |

`reference.json` carries the transcript, durations and formats.

**The two ElevenLabs clips read the same passage**, so they are directly comparable — the
difference between them is the voice, not the words:

> The old clockmaker placed the tiny brass gear onto the workbench. His hands shook, but his
> eyes were clear. For fifty years, he had fixed the broken time of the town.

The ids are pinned in `make_audio.py`, so the dataset's speech comes from these two voices and
nothing else. They were inherited from `laughter_sigh_contrast_v3/2.0`, which means v6 and v3
audio are comparable in timbre.

## Why the Dia clip is different in kind

ElevenLabs is given a voice id, so its speaker is fixed by reference to a catalogue entry and
this clip is only an illustration of it. Dia clones from a recording, so its speaker *is* this
file — change it and the dataset's voices change.

**Its transcript is not recorded.** Dia conditions on a reference recording together with the
words spoken in it, so `transcript` is null in `reference.json` rather than guessed. Dia cannot
be run reproducibly from this folder until someone writes down what is said in the clip.

That asymmetry matters when the two renderers are compared: the speaking voices are not the
same, so a difference between renderers includes a difference in timbre and delivery, not only
in how the vocalization was produced.

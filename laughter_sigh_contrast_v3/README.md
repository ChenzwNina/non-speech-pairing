# laughter_sigh_contrast

The same conversation, heard three ways — through laughter, through sighs, and plainly — with
the spoken words held physically identical across all three. Anything a model does differently
is down to the non-speech sounds.

Two generations of the same experiment.

| | what it established | state |
| --- | --- | --- |
| **[1.0](1.0/)** | Models hear the sounds (97%) and reply as though they had not: every eval sat at its baseline. | 20 items × 3 conditions × 4 models · frozen |
| **[2.0](2.0/)** | With gold written from the rendered transcript and a sound in nearly every turn, three of four models do use them. | 20 items × 3 conditions × 4 models · current |

Start with [2.0/PIPELINE.md](2.0/PIPELINE.md), which describes how the dataset is built for
someone who has not seen the project, then [2.0/README.md](2.0/README.md) for the results.

## What changed between them

1.0's conclusion rested on evals that could not have shown a difference if one existed. Its
gold was written *before* the sounds were placed — a prediction about a conversation that did
not yet exist — and tone was scored by exact match against one of six labels, so "gently wry"
counted as a failure against "dryly sympathetic". 2.0 writes the gold from the transcript that
was actually rendered, doubles the density so nearly every turn carries a sound, and replaces
label-matching with a graded judgement against a written expectation.

Under those measures perception is at ceiling for openai, gemini and qwen, pragmatic reading
runs 65–82% against a 25% chance line, and their replies are distinguishable by condition. The
2.0 README carries the numbers and the caveats, of which two matter: the Opus 5 gold
verification largely failed on specificity, and Q2's leave-one-out panel partly ranks panels
rather than models.

## Shared ground

Both generations draw their situations from EmpatheticDialogues (`embarrassed` label), render
speech with ElevenLabs, and test the same four speech-to-speech models. 2.0 reuses 1.0's
situations, dialogues and per-turn audio verbatim — stages 1, 2 and 6 are identical between
them — so the two are directly comparable, and `2.0/dialogues.py` refuses to import unless
every turn still matches the take rendered for it.

Real source recordings live in `../audio_non-speech/`; earlier probes are in `../v1/`, `../v2/`
and `../archive/`.

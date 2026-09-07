Three conversations per item, 24 items.

  <item>__baseline.mp3      the clean turn takes in order, no vocalization
  <item>__condition_a.mp3   that same audio with vocalization A spliced into the tagged turn
  <item>__condition_b.mp3   the same for B
  clips/                    the extracted vocalizations on their own, with --save-clips

Names and location follow eval_config.yaml (audio_root, audio_path_template) so the evaluation
resolves a stimulus straight from this directory; see ../README.md.

All three files for an item share one waveform and differ only by the inserted clip: the
untagged turns are the same decoded takes, the tagged turn is the same clean take, and the
vocalization is INSERTED rather than swapped in. Nothing is removed, so every lexical word is
bit-identical across neutral and both sewn versions.

The clip is cut from that item's own vocalized take of the tagged turn, at boundaries WhisperX
force-aligned:

  prefix tag   [take start .. onset of the first lexical word]
  inline tag   [end of the word before .. onset of the word after]

and inserted at the clean take's own onset of that same anchor word, followed by 75 ms of
silence before the words resume.

Unlike the Dia path, the speaking voice is not a variable here: ElevenLabs was given a pinned
voice_id per speaker, and the clean take of the tagged turn is a sibling generation of the two
vocalized takes.

The splice is done and verified in float arrays, and encoded once at the end, so the guarantee
above is established before anything is written and does not depend on the output format.
manifest.json records every cut window, insert point, clip length and loudness delta, plus any
item the cut could not be made for.

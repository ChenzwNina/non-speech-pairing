# Assembled conversations

**This directory is a handoff, and git is the transport.** Nothing local writes it.

```
render (ElevenLabs / Dia)  →  out/audio_turns/<renderer>/   →  git  →
    →  align and sew  →  out/audio/<renderer>/  →  git  →  evaluation
```

The per-turn takes go up from wherever the text-to-speech was called. The machine that aligns
and assembles them pulls those, sews each conversation, and pushes the results back here. The
evaluation reads only this directory — `eval_config.yaml` resolves a stimulus to
`out/audio/<renderer>/<item_id>__<condition>.<ext>` and never touches the takes.

## What to write

One file per stimulus, three per item:

```
v6_01a__baseline.mp3
v6_01a__condition_a.mp3
v6_01a__condition_b.mp3
```

24 items × 3 = 72 files per renderer. `eval_config.yaml` holds the extension per renderer —
`.mp3` for elevenlabs, `.wav` for dia — so match what is configured there or change it.

## How to assemble

Every item's entry in `out/audio_turns/<renderer>/manifest.json` carries the recipe:

```json
"assembly": {
  "gap_seconds": 0.35,
  "turn_order": [1, 2, 3, 4, 5],
  "baseline":    ["v6_01a__t1.mp3", "...", "v6_01a__t5.mp3"],
  "condition_a": ["v6_01a__t1.mp3", "...", "v6_01a__t5__a.mp3"],
  "condition_b": ["v6_01a__t1.mp3", "...", "v6_01a__t5__b.mp3"]
}
```

`gap_seconds` is what `make_audio.py` used for its own rough check; an aligning assembler should
use whatever its alignment supports and record what it did.

**The three versions must share their turn-1-to-4 audio exactly.** Every condition lists the
same take files for those turns, and the whole design rests on their being the same samples —
if the assembler re-encodes or re-times them per condition, a model answering differently may be
answering to that rather than to the vocalization. Only the turn-5 file differs.

## Checking it

```bash
python3 v6/validate_dataset.py --renderer elevenlabs --require-audio
```

Reports every missing or empty file against the 24 items, and fails nonzero if any are absent.

## What is deliberately not here

`make_audio.py --sew` writes its hard-cut assembly to `out/audio_local_check/`, which git
ignores. It exists only to listen to a render locally. It uses the same filenames as this
directory, so keeping both would make it impossible to tell which assembler produced a given
file.

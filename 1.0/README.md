# 1.0 · Non-speech vocalization benchmark

**Can a speech-to-speech model use laughter and sighs to decide how to respond?**

The same conversation is heard three ways. The words never change — only the non-speech
sounds around them. If a model's three replies are interchangeable, the sounds did nothing.

| condition | audio | vocalizations |
| --- | --- | --- |
| neutral | the turn recordings, concatenated | none |
| happy | the same recordings, laughter spliced in | 2–8 |
| sad | the same recordings, sighs spliced in | the same count, the same slots |

The speech is physically the same recording in all three. Happy and sad occupy identical
slots, so they differ in the *kind* of sound and nothing else.

## What is here

```
PIPELINE.md          how the data was built, stage by stage, written for an outside reader
EVALS.md             the perception eval in detail
out/audio/           60 finished recordings — 20 items x 3 conditions
out/audio_voc/       190 vocalization clips
out/audio_turns/     128 speech takes, plus halves cut for mid-sentence splices
out/responses/       240 spoken replies from the tested models
out/transcripts.json turns, placement plans, gold answers
out/audio_manifest.json  per-clip levels and a per-condition timeline to the millisecond
out/*.json / *.md    verification and evaluation results
*.py                 the pipeline: generate -> replan -> write_gold -> make_audio ->
                     verify_clips -> test_models -> eval2 / eval13 / eval4
```

## The dataset

20 items · 128 turns ·
190 clips · 60 recordings ·
neutral 22.9s mean, happy 31.3s, sad 32.5s

Seeds are EmpatheticDialogues situations labelled *embarrassed* — mishaps that can honestly
be told as funny or as bleak. Clip verification: **190/190 passed** a four-model yes/no vote,
nothing left for a human.

## Results

Tested: `gpt-realtime-2.1`, `gemini-3.1-flash-live-preview`, `qwen-audio-3.0-realtime-plus`.
Grok is excluded: its audio never arrived, so its verdicts are void. Manual turn
control has since fixed that transport (11/12, all correct) — see PIPELINE.md,
Known problems. The fix lands in 2.0; these numbers stay as collected.

| model | eval 1 no wrong sound | eval 2 appropriateness | eval 3 tone | perception |
| --- | --- | --- | --- | --- |
| qwen | 100% | 63% | 23% | 97% |
| gemini | 97% | 62% | 32% | 97% |
| openai | 93% | 60% | 18% | 97% |
| *baseline* | *near-ceiling by design* | *50% chance* | *27% constant register* | *33% chance* |

**They hear the sounds and reply as though they had not.** Perception is 97% — 58 of 60,
including the neutral condition where the answer is "neither". But eval 2 sits barely above
chance, and eval 3 is at or below what a model scores by using one tone for everything. The
judges heard qwen as "sympathetic" on 14 of 20 *happy* items: answering a story told through
laughter in the voice it uses for sighs.

Eval 1 carries little information — 93% of replies contain no vocalization at all, so almost
every pass is by omission.

## Caveats

- **Eval 4 has not been re-run** since the prompt changed; the perception column above is
  computed from the trial answers directly, not by `eval4_perception.py`.
- **The gold answers were written before placement**, as a prediction of how the sounds would
  land. `write_gold.py` fixes this for future data by writing them from the rendered
  transcript, and has not been applied here.
- **Eval 1 flags on a two-judge majority**, so a 1–1 split resolves arbitrarily. Three of its
  six failures are such splits and should be discounted.
- Splicing gives perfect word control but not genuinely amused *delivery*.

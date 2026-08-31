# Eval 4 — did the models hear the vocalizations

Mechanical scoring against the insertion list. No judge involved.

| model | overall | happy | sad | neutral (false alarms) |
| --- | --- | --- | --- | --- |
| gemini | 0.69 | 0.68 | 0.68 | 0.70  (6/20 invented) |
| grok | 0.38 | 0.15 | 0.00 | 1.00  (0/20 invented) |
| openai | 0.79 | 0.77 | 0.60 | 1.00  (0/20 invented) |
| qwen | 0.84 | 0.78 | 0.73 | 1.00  (0/20 invented) |

## Sub-scores on the conditions that have vocalizations

| model | condition | type | count | location |
| --- | --- | --- | --- | --- |
| gemini | happy | 0.85 | 0.68 | 0.50 |
| gemini | sad | 0.90 | 0.67 | 0.47 |
| grok | happy | 0.35 | 0.11 | 0.00 |
| grok | sad | 0.00 | 0.00 | 0.00 |
| openai | happy | 1.00 | 0.73 | 0.57 |
| openai | sad | 0.78 | 0.53 | 0.48 |
| qwen | happy | 1.00 | 0.80 | 0.54 |
| qwen | sad | 0.95 | 0.85 | 0.38 |

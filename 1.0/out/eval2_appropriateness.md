# Eval 2 — does the response fit the condition it was given

Judge `gpt-5.6-terra`, 3 rounds per pair, order randomized, majority decides. Chance is 50%: a model whose three responses are interchangeable scores 50%.

| model | overall | neutral | happy | sad | flagged |
| --- | --- | --- | --- | --- | --- |
| openai | 60% (72/120) | 65% (26/40) | 52% (21/40) | 62% (25/40) | 0 |
| gemini | 62% (75/120) | 62% (25/40) | 72% (29/40) | 52% (21/40) | 0 |
| qwen | 63% (76/120) | 82% (33/40) | 65% (26/40) | 42% (17/40) | 0 |

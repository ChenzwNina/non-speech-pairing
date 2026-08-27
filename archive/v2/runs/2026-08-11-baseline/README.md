# Baseline run — 2026-08-11

First full pass over all 45 pairs. The writer had NO pair conditions in its
prompt; `pair_conditions.csv` here was drafted after the run and is the long,
untightened first draft (21 workable / 24 hard / 0 impossible).

- writer: claude-opus-5, effort high
- verifier: gpt-5.4, 6 forced-choice trials, gate = mean confidence in 40-60
  and slot-2 share <= 0.70

## Results

- 45/45 generated, 0 malformed, 5 needed the duplicate-turn repair
- mean |mean P - 50| = 27.5
- 6/45 cleared the confidence gate; 2/45 cleared both gates
- passing pairs: enjoyment x scare-quoting (41.2), smoothing x scare-quoting (58.0)

Use these numbers as the comparison point for later runs.

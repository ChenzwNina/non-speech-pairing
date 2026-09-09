# The binary separability check, and why it was replaced

This check asked one question per item: *would a natural reply appropriate for one version
often also be fully appropriate for the other?* If yes, it failed the item.

It failed **23 of 24**, evenly across all six vocalization pairs (laugh/sigh 0/4, laugh/gasp
0/4, laugh/groan 0/4, sigh/gasp 0/4, sigh/groan 0/4, gasp/groan 1/4).

That uniformity is the tell. The check was not finding 23 bad situations; it was testing the
wrong property. Sixteen of the 23 verdicts say so in their own words:

- v6_01d — "Only tone differs (amused vs. annoyed), not what B must do."
- v6_04d — "Sigh and gasp differ only in inner arousal; neither shifts what B must do."
- v6_05b — "differ only in intensity, not in what B must do."

A non-speech vocalization usually changes the **stance** a reply takes, not the
**conversational action** it performs. Laugh and sigh on the same words can both leave the
other speaker saying "that spot is easy to miss" — the laugh inviting shared amusement, the
sigh commiseration. The benchmark needs the two versions to *prefer* different replies. It
never needed a reply that fits one to be *unacceptable* under the other, and demanding that
rejects almost every well-written item. The only item that passed, v6_06d, passed because its
two sounds forked in valence (gasp→delight, groan→dismay) — the rare case, not the target.

The check also compared the two conditions' interpretations against each other, which forced a
correspondence that does not exist: each condition has one to three readings of its own, the
counts differ, and nothing needs to line up across them.

Its printed remedy was wrong too. It told the caller to regenerate from a new seed because
"the situation is what failed to separate the sounds" — sound reasoning for a single failure,
but `sample_items.py --reseed` "keeps their vocalization pair", so at this scale the remedy
preserves the actual cause. It was never run.

Replaced by `v6/measure_separability.py`, which measures the preference rather than asking a
model to declare it: a reply per reading, every reply cross-scored blind under both conditions,
and `home - away` as the preference. Generic replies score equally under both, contribute zero,
and abstain instead of condemning the item.

`verdicts_23_of_24_failed.json` is the full output, kept as evidence.

# archive

Earlier experiments and one-off probes, kept for reference. Nothing here is current — the
active work is in `v1/`, `v2/` and `1.0/`.

## Datasets with a listening eval

| folder | task | result |
| --- | --- | --- |
| `pairing_type` | same words, different vocalization → B's attitude, 4-way | 25/48 = 52% (chance 25%) |
| `predicting_content` | hear the sound, predict the next line, 2-way | 24/30 = 80% |
| `predicting_response_upgraded` | a later variant of v1's question | see its own out/ |

## Datasets without an eval

`transcript_curated` — same words, different delivery, C's reply should flip.
`laughter_identify` — four-turn dialogues each targeting one laughter function.

## Probes and sketches

`logo_sketch`, `cat_deck_sketch`, `missed_train_sketch`, `printer_jam`, `group_laughter`,
`mock_impoliteness`, `soda_scatter`, `hard_task` — short scenes built to test one question
each, usually read by eye rather than scored. `missed_train_sketch` and `group_laughter` are
the closest relatives of v2: a mishap told through laughter, with the model as a third person.

`meld_search` — an attempt to source real vocalizations from MELD. Unusable: laugh track, and
no vocalization tags.

## Older material

`v1`, `v2`, `archived`, `out` — early iterations predating the current numbering, plus the
loose generation scripts that went with them. `*_viewer/` are published analysis sites for
`pairing_type`, `predicting_content`, and the upgraded response task.

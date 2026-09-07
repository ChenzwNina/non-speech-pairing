# The transcript pipeline that produced the current dataset

Superseded, kept because everything downstream still descends from what it wrote.

## The chain

| stage | file | output |
| --- | --- | --- |
| sample scenarios | [../seeds.py](../seeds.py) — still live | `out/seeds.json`, 60 situations |
| write the minimal pairs | [generate.py](generate.py) + [prompt.txt](prompt.txt) | `out/pairs.json` |
| rewrite into spoken register | [spoken.py](spoken.py) | `out/pairs_spoken.json` |

`prompt.txt` is the writer prompt as supplied, used verbatim with only its `{{...}}`
placeholders filled. It asks for four turns, A-B-A-B, one Dia tag inside one spoken turn, and
all three versions returned in full.

`spoken.py` is a second pass with GPT-4o that changes register and nothing else: 807 words to
808, contractions 15 to 31, 65 of 80 turns reworded. The vocalization travels through it as a
`«VOC»` marker and the three versions are rebuilt from the result, so the minimal pair survives
by construction rather than by the rewriter's good behaviour. Its instruction was hardcoded in
the script rather than kept as a versioned file — which is why `out/pairs_spoken.json` records
no hash for it, and why reading `spoken.py` is currently the only way to know what it was told.

## What still depends on this

`out/pairs_spoken.json` is the live dataset. The ElevenLabs audio, the frozen perception and
pragmatic task sets, and the pragmatic options were all built from it. Replacing the transcripts
invalidates all of them — see the v6 README for what has to be rebuilt.

`out/pairs.json` (pre-rewrite) and `out/pairs_multi_slot.json` (an earlier design with two or
three sounds per conversation) are kept alongside it for comparison.

## Why it was retired

Not because it failed — it produced 20 items at a 100% first-attempt rate. The design is being
revised.

# Early swims at the outdoor pool

**Setting.** A and B swim at the same outdoor pool and are getting changed afterwards.

**Pair.** `social-bonding` (Pleasantness (no incongruity)) vs `show-disagreement` (Social incongruity)  — crosses branches

## Shared transcript (no audio tags)

```
A: I was in the water before six this morning.
B: Before six.
A: The whole lane to myself.
B: Every day, then.
A: Every day since April.
B: Of course you do.   <- target laugh
```

*Why it is ambiguous on the page:* On the page, of course you do is a stock formula that reads equally as sincere recognition of someone you know well and as a wordless yeah, right, and the two flat echoes before it fit an interested listener and an unconvinced one just as well.

## Performance A — Social bonding / show closeness

- **Branch.** Pleasantness (no incongruity)
- **Framing.** A tells it plainly and unhurriedly, with no flourish — just someone describing a morning they like. B's echoes are the sound of someone being drawn in, and the closing laugh is B recognising a person they know well and are fond of.
- **Laughable.** Nothing is being found funny or doubted; the laugh points at A themselves, at the pleasure of knowing someone this well.
- **Arousal.** low
- **Expected answer.** The laugh is warmth toward A — B is showing closeness and fondness for someone whose habits they know, not doubting anything and not finding anything funny.

```
A: [relaxed] I was in the water before six this morning.
B: [softly impressed] Before six.
A: [content][soft chuckle] The whole lane to myself.
B: [warm, drawing it out] Every day, then.
A: [easy] Every day since April.
B: [warm laugh][tender] Of course you do.
```

## Performance B — Show disagreement

- **Branch.** Social incongruity
- **Framing.** A delivers each line with a bit of a flourish, pleased with the account. B's echoes come back flat and unconvinced, and rather than say they don't buy it, B lets the laugh do it.
- **Laughable.** A's claim of an unbroken daily streak since April, which B declines to accept.
- **Arousal.** mid
- **Expected answer.** The laugh rejects what A just said — instead of arguing, B laughs to make clear they don't buy the claim.

```
A: [pleased] I was in the water before six this morning.
B: [flat] Before six?
A: [relishing it] The whole lane to myself.
B: [dry, unconvinced] Every day, then?
A: [doubling down] Every day since April.
B: [disbelieving laugh][dismissive] Of course you do.
```

## Probe

Open: You just heard a short conversation. Speaker B laughs on the line “Of course you do”. What is that laugh doing — what does it convey about how B is treating what A said? Answer in one or two sentences.

Forced choice:

```
You just heard a short conversation. Speaker B laughs on the line “Of course you do”. Which better describes what that laugh is doing?
(a) The laugh is warmth toward A — B is showing closeness and fondness for someone whose habits they know, not doubting anything and not finding anything funny.
(b) The laugh rejects what A just said — instead of arguing, B laughs to make clear they don't buy the claim.
Answer with (a) or (b), then one sentence of justification.
```

Gold: performance A -> `a`, performance B -> `b`

Score the forced choice for accuracy, and the open answer against each performance's expected_answer. Report PAIR accuracy: the item counts as passed only if the model gets both performances right. Because the two performances are word-for-word identical, any model that answers from the text — or from a fixed preference for one function — scores 0 on pair accuracy, not 50%. Independent guessing scores 25%.

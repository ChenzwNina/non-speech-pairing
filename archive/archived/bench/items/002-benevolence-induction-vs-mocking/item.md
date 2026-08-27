# Bowls on the dishwasher top rack

**Setting.** Two flatmates standing at the open dishwasher in the kitchen they share.

**Pair.** `benevolence-induction` (Social incongruity) vs `mocking` (Social incongruity)

## Shared transcript (no audio tags)

```
A: You put the bowls on the top rack again.
B: That's where they were when I opened it.
A: They come out wet up there.
B: They came out dry last time.
A: I moved them before I ran it.
B: It's a dishwasher.   <- target laugh
```

*Why it is ambiguous on the page:* On the words alone, "It's a dishwasher" can either be B asking A to agree that the whole thing is too small to keep going over, or B dismissing A as too small to answer — and since both flatmates have equal standing in the shared kitchen, each has cited evidence, and neither is asking the other for anything, nothing in the text tips which one it is.

## Performance A — Benevolence induction

- **Branch.** Social incongruity
- **Framing.** Both keep an even, unbothered tone through the back-and-forth, trading their bits of evidence without heat. B's last turn arrives with the laugh first, opening the line rather than closing it, so the words land as a bid for A to agree that this is small enough to drop.
- **Laughable.** The disagreement itself — the fact that the two of them are standing at an open dishwasher comparing notes on rack placement — offered up as something A can agree is not worth it.
- **Arousal.** low
- **Expected answer.** B's laugh is a friendly nudge inviting A to come round and agree that this is too small to keep going over, keeping things easy between them.

```
A: [even] You put the bowls on the top rack again.
B: [easy] That's where they were when I opened it.
A: [matter of fact] They come out wet up there.
B: [light] They came out dry last time.
A: [plain] I moved them before I ran it.
B: [coaxing laugh][warm] It's a dishwasher. [light chuckle][hopeful]
```

## Performance B — Mocking

- **Branch.** Social incongruity
- **Framing.** The exchange tightens as it goes: A gets firmer, B gets flatter and shorter. B's last turn opens on a snort and the words come down clipped and from above, so the line answers A's point by refusing to treat it as a point.
- **Laughable.** A — specifically A's insistence on where the bowls go, which B holds up as beneath discussion.
- **Arousal.** mid
- **Expected answer.** B's laugh talks down to A, treating A's concern as something to be laughed at rather than answered, and puts B above the whole thing.

```
A: [flat] You put the bowls on the top rack again.
B: [clipped] That's where they were when I opened it.
A: [firm] They come out wet up there.
B: [unimpressed] They came out dry last time.
A: [insistent] I moved them before I ran it.
B: [snort][condescending] It's a dishwasher. [derisive laugh]
```

## Probe

Open: You just heard a short conversation. Speaker B laughs on the line “It's a dishwasher”. What is that laugh doing — what does it convey about how B is treating what A said? Answer in one or two sentences.

Forced choice:

```
You just heard a short conversation. Speaker B laughs on the line “It's a dishwasher”. Which better describes what that laugh is doing?
(a) B's laugh is a friendly nudge inviting A to come round and agree that this is too small to keep going over, keeping things easy between them.
(b) B's laugh talks down to A, treating A's concern as something to be laughed at rather than answered, and puts B above the whole thing.
Answer with (a) or (b), then one sentence of justification.
```

Gold: performance A -> `a`, performance B -> `b`

Score the forced choice for accuracy, and the open answer against each performance's expected_answer. Report PAIR accuracy: the item counts as passed only if the model gets both performances right. Because the two performances are word-for-word identical, any model that answers from the text — or from a fixed preference for one function — scores 0 on pair accuracy, not 50%. Independent guessing scores 25%.

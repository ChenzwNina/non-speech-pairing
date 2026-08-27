# Walking off with someone else's coffee

**Setting.** Two friends who see each other most mornings, talking on the walk into work.

**Pair.** `show-enjoyment` (Pleasant incongruity) vs `smoothing` (Social incongruity)  — crosses branches

## Shared transcript (no audio tags)

```
A: So I grabbed the cup off the counter and left.
B: Was it yours?
A: There was a name on it, and it wasn't mine.
B: When did you notice?
A: About halfway through it.   <- target laugh
```

*Why it is ambiguous on the page:* The words only report that A drank someone else's coffee and noticed late — nothing in them says whether A thinks that's a great story or a thing A is sheepish about having done.

## Performance A — Show enjoyment

- **Branch.** Pleasant incongruity
- **Framing.** A tells the whole thing as a story worth telling, already grinning on the first line and leaning into the punchline of having kept drinking; B is enjoying it along with A. By the final turn the mix-up is pure entertainment, and A's laugh hands it over to be enjoyed.
- **Laughable.** The goofy absurdity of getting all the way down the street on a stranger's coffee and simply carrying on with it.
- **Arousal.** mid
- **Expected answer.** A is laughing because the mix-up is funny to A, offering it up as a good story for B to enjoy too.

```
A: [amused] So I grabbed the cup off the counter and [chuckle] left.
B: [amused] Was it yours?
A: [laughing] There was a name on it, and it wasn't mine!
B: [giggling] When did you notice?
A: [delighted] About halfway through it! [laughing]
```

## Performance B — Smoothing / softening

- **Branch.** Social incongruity
- **Framing.** A brings it up flatly and a little reluctantly, like something A would rather not have to say out loud; B keeps the questions gentle. The last line is an admission A is not comfortable making, and the laugh comes in to blunt it.
- **Laughable.** A's own small norm violation — having drunk a stranger's coffee — which is awkward to be confessing at all.
- **Arousal.** low
- **Expected answer.** A is laughing to take the edge off admitting something A finds a bit shameful, softening the confession rather than enjoying it.

```
A: [uncomfortable] So I grabbed the cup off the counter and left.
B: [quiet] Was it yours?
A: [uncomfortable] There was a name on it, and... it wasn't mine.
B: [gentle] When did you notice?
A: [embarrassed] About halfway through it... [embarrassed laugh]
```

## Probe

Open: You just heard a short conversation. Speaker A laughs on the line “About halfway through it”. What is that laugh doing — what does it convey about how A is treating what B said? Answer in one or two sentences.

Forced choice:

```
You just heard a short conversation. Speaker A laughs on the line “About halfway through it”. Which better describes what that laugh is doing?
(a) A is laughing because the mix-up is funny to A, offering it up as a good story for B to enjoy too.
(b) A is laughing to take the edge off admitting something A finds a bit shameful, softening the confession rather than enjoying it.
Answer with (a) or (b), then one sentence of justification.
```

Gold: performance A -> `a`, performance B -> `b`

Score the forced choice for accuracy, and the open answer against each performance's expected_answer. Report PAIR accuracy: the item counts as passed only if the model gets both performances right. Because the two performances are word-for-word identical, any model that answers from the text — or from a fixed preference for one function — scores 0 on pair accuracy, not 50%. Independent guessing scores 25%.

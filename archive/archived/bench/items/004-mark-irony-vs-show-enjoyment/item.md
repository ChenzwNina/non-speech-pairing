# Leftover screws from the same chair

**Setting.** A and B are friends who happen to have bought the same desk chair, talking in a kitchen while the kettle boils.

**Pair.** `mark-irony` (Pragmatic incongruity) vs `show-enjoyment` (Pleasant incongruity)  — crosses branches

## Shared transcript (no audio tags)

```
A: I finally put the chair together last night.
B: How long did it take you?
A: Three hours. There were two extra screws left over.
B: Mine had a spare bracket too.
A: Well, that's good to know.   <- target laugh
```

*Why it is ambiguous on the page:* On the page 'Well, that's good to know' can be read either as A inverting their own words about a chair that ships with parts unaccounted for, or as A sincerely glad to learn they aren't the only one, and nothing in the wording or the symmetric situation picks between them.

## Performance A — Mark pragmatic incongruity (irony / scare-quoting)

- **Branch.** Pragmatic incongruity
- **Framing.** A reports the three hours and the spare screws flatly, as evidence rather than as a story, and lands the last line with a level, knowing delivery so that 'good to know' is clearly pointed back at itself — B's spare bracket confirms the chairs ship half-counted, which is the opposite of good news.
- **Laughable.** A's own phrase 'good to know', which is meant to be heard as its opposite: two people, two sets of parts nobody accounted for.
- **Arousal.** low
- **Expected answer.** A's laugh tells B not to take the line at face value — A means the opposite of what A just said, that spare parts in both boxes is bad news about the chair.

```
A: [flat] I finally put the chair together last night.
B: [level] How long did it take you?
A: [deadpan] Three hours. [dry] There were two extra screws left over.
B: [matter-of-fact] Mine had a spare bracket too.
A: [sardonic][knowing] Well, that's good to know. [dry laugh]
```

## Performance B — Show enjoyment

- **Branch.** Pleasant incongruity
- **Framing.** A tells the whole thing as a good story, already over the three hours, half-laughing through the count of screws; when B reports a spare bracket, A takes the line straight and hears it as genuinely worth knowing, and the laugh is A enjoying the coincidence and handing it back to B.
- **Laughable.** the pleasant absurdity that both of them ended up with parts left over, which A finds genuinely funny and shows it.
- **Arousal.** mid
- **Expected answer.** A's laugh shows A is enjoying the coincidence that B's chair came with spare parts as well, and is offering it up for B to enjoy too.

```
A: [amused] I finally put the chair together last night.
B: [grinning] How long did it take you?
A: [laughing] Three hours. [chuckle] There were two extra screws left over.
B: [amused] Mine had a spare bracket too.
A: [delighted] Well, that's good to know. [laughing]
```

## Probe

Open: You just heard a short conversation. Speaker A laughs on the line “Well, that's good to know”. What is that laugh doing — what does it convey about how A is treating what B said? Answer in one or two sentences.

Forced choice:

```
You just heard a short conversation. Speaker A laughs on the line “Well, that's good to know”. Which better describes what that laugh is doing?
(a) A's laugh tells B not to take the line at face value — A means the opposite of what A just said, that spare parts in both boxes is bad news about the chair.
(b) A's laugh shows A is enjoying the coincidence that B's chair came with spare parts as well, and is offering it up for B to enjoy too.
Answer with (a) or (b), then one sentence of justification.
```

Gold: performance A -> `a`, performance B -> `b`

Score the forced choice for accuracy, and the open answer against each performance's expected_answer. Report PAIR accuracy: the item counts as passed only if the model gets both performances right. Because the two performances are word-for-word identical, any model that answers from the text — or from a fixed preference for one function — scores 0 on pair accuracy, not 50%. Independent guessing scores 25%.

# Mock impoliteness: positive voc + negative words

    A: <ridiculous but earnest plan>
    B: [laughter] You are crazy.

The words attack; the sound says *I'm delighted*. A text-only model reads the
words and gets it exactly backwards, which is why this is the highest-leverage
contrast in the set: the transcript is not merely uninformative, it is
**actively misleading**.

## Why it is hard to craft

The flip is not automatic. A laugh on top of a genuine criticism does not become
warmth — it becomes a sneer. Five conditions have to hold at once, and hand-written
attempts usually break one of them silently.

### 1. The target must be a *choice*, not a *trait*

Banter licenses an attack on what A deliberately did. It does not license an
attack on what A is or cannot help.

| licensed (flips)                      | not licensed (stays an insult)      |
| ------------------------------------- | ----------------------------------- |
| A booked a flight to propose tomorrow | A forgot the meeting again          |
| A ate the whole thing on a dare       | A's presentation went badly         |
| A quit to start a hot-sauce company   | A can't afford rent                 |

### 2. The insult must come from the *admiring class*

Some negative words already carry a conventional "impressive" reading. Others
have no such reading and stay literal no matter what sound sits on them.

**Flips:** crazy · insane · out of your mind · ridiculous · unbelievable ·
the worst · a monster · an animal · shut up · I hate you · you're killing me ·
I can't stand you · nightmare · absolutely not · no way

**Never flips:** pathetic · incompetent · selfish · careless · lazy · cruel ·
disappointing · you always · you never

Rule of thumb: if the word can end a sentence that begins *"That's the most
impressive thing I've ever—"*, it flips.

### 3. B's line must carry no consequence

The moment the negative content includes an actual outcome, the sound cannot
cancel it — the outcome is still on the table.

    ok:   [laughter] You are out of your mind.
    bad:  [laughter] You are out of your mind. I'm not covering for you.

Second clause is real content. The laugh now reads as softening a refusal, which
is a different phenomenon (and a much weaker contrast).

### 4. The voc goes *before* or *inside* the words, never after

`[laughter] You're insane.` — the sound frames the words as play.
`You're insane. [laughter]` — reads as a nervous retraction, or as a laugh at
A rather than with them.

### 5. A must be *committed*, not asking

If turn 4 is a question, turn 6 becomes an answer to A instead of a reading of B.
A states the plan as decided or already done. Same rule as `predicting_response`.

## Turn template

    1-3  A   setup: the plan, voluntary and harmless, escalating
    4    A   commitment: states it as decided/done. Not a question. No hedge.
    5    B   [VOC] + NEGATIVE_LINE      <- identical words in both versions
    6    A   reply that reveals how it landed. Must not name the sound.

Only the tag on turn 5 changes between versions. Turn 6 is the answer key.

## Contrast pairs worth generating

| positive voc         | negative voc     | what turn 6 must show                          |
| -------------------- | ---------------- | ---------------------------------------------- |
| `[laughter]`         | `[scoff]`        | delight vs. contempt — the sharpest pair        |
| `[laughter]`         | `[sigh]`         | delight vs. weary disapproval                   |
| `[gasp]` (delighted) | `[gasp]` (alarm) | same tag, different realization — audio only    |
| `[laughter]`         | `[groan]`        | egging on vs. "not this again"                  |

The `[laughter]` / `[scoff]` pair is the one to build first. Both are exhales,
both sit in the same place in the turn, and the words are byte-identical — a
transcript model has literally nothing to go on and must score at chance.

## Seed inventory for turn 5

Held fixed across both versions of a pair. Short, second-person, no consequence:

    You are crazy.
    You are out of your mind.
    That's insane.
    I hate you.
    Shut up.
    You're the worst.
    Absolutely not.
    No way.
    You're a monster.
    I can't stand you.
    You're killing me.

## Worked examples

**laughter / scoff — `You are crazy.`**

    1. A: The gallery emailed back about the open call.
    2. A: They only had one slot left and it was for tomorrow night.
    3. A: I'd have to drive the whole collection down there overnight.
    4. A: I already loaded the van and told them I'd be there by nine.

    5. B: [laughter] You are crazy.
    6. A: I know, right? Come with me, you can nap in the back.

    5. B: [scoff] You are crazy.
    6. A: Fine. I'll do it myself, like everything else.

**laughter / sigh — `I hate you.`**

    1. A: Remember the sourdough starter you said would never take?
    2. A: It's been going three weeks now.
    3. A: I entered a loaf in the fair on Saturday just to see.
    4. A: It took first place, and they want me to judge next year.

    5. B: [laughter] I hate you.
    6. A: Say that again when I bring you the free bread.

    5. B: [sigh] I hate you.
    6. A: ...I didn't think it would actually bother you. I can pull out.

**laughter / groan — `Shut up.`**

    1. A: I got put on the karaoke list at the reunion by mistake.
    2. A: They had me down for the same song I did in tenth grade.
    3. A: I decided not to fight it.
    4. A: I did the whole thing, key change and all, and they made me do it twice.

    5. B: [laughter] Shut up.
    6. A: I have video. You're watching it in the car.

    5. B: [groan] Shut up.
    6. A: Okay, okay, I'll stop telling it. It was funnier in the room.

## Mechanical checks for a generator

Same style as `predicting_response/verify.py`:

- turn 5 lexical text is **byte-identical** across the two versions
- turn 5 text is drawn from the seed inventory (or passes the admiring-class list)
- turn 5 has exactly one tag, at the **start**
- turn 5 contains no second sentence carrying a consequence (no `I'm not`,
  `I won't`, `don't expect`, `you're on your own`)
- turn 4 does not end in `?` and contains no hedge (`maybe`, `I was thinking`)
- turn 6 differs between versions and names no vocalization word
- turn 6 <= MAX_REPLY_WORDS

## Judge pass

The generation check above cannot tell whether the *flip* actually happened. Add
a judge that sees one version at a time (words + tag, no audio) and answers:

1. Does B like A's plan? (yes / no)
2. Does A's reply treat B as an ally or as an obstacle?

A valid pair gets opposite answers on both questions. If the judge answers the
same way for `[laughter]` and `[scoff]`, the negative line was too literal
(condition 2) or carried a consequence (condition 3) — regenerate.

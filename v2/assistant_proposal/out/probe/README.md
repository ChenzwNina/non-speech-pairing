# Delexicalization probe — gpt-realtime-2.1

Two questions per session, both answered from one listen: *is the audio audible*
and *what emotion is in it*. 5 runs each, `probe_realtime.py`.

| | `sigh_voice.mp3` (source) | `sigh_voice_delex_0.90.wav` |
| --------------------- | ------------------------- | --------------------------- |
| audible = yes         | 5/5                       | 4/5                         |
| names a "sigh"        | 4/5                       | **0/5**                     |
| emotion = frustration | **5/5**                   | **0/5**                     |
| high confidence       | 3/5                       | 0/5 (1 was "none, high")    |
| what it reports       | "a sigh followed by someone saying 'I am frustrated'" | "repeated 'hmm' sounds", "soft humming" |

## The source clip contains the answer in words

`sigh_voice.mp3` is a sigh **plus the spoken line "I am frustrated."** The model
says so itself: *"I'm highly confident because the speaker explicitly says they
are frustrated"* and *"based on the sigh and the statement."* So the confident
read on the source is not evidence that it hears sighs — it is evidence that it
reads transcripts.

Delexicalize the words and the emotion read collapses to neutral/low-confidence,
even though the prosodic channel survived: f0 median 96.4 -> 99.2 Hz, range
56.6 -> 69.4 Hz, while MFCC 1-4 variance (formant movement, i.e. phoneme
identity) dropped 5-13x. The sound that carries the emotion is still there. The
model stops reporting the emotion anyway.

**Caveat.** This is one stimulus, one model, n=5. It is consistent with the
benchmark thesis, not a demonstration of it. The clean version of this test needs
a delexicalized *contrast set* — sigh vs laughter vs gasp, same speaker, same
treatment — so you can show the model is at chance across vocalizations rather
than just vague about one clip.

## Harness gotchas found here

- The realtime API emits `conversation.item.added` / `conversation.item.done`.
  There is no `conversation.item.created` on gpt-realtime-2.1; waiting for it
  hangs until the deadline.
- **~1 in 5 sessions returns "I don't hear any audio"** with identical input,
  and it happens on both clips. Waiting for `conversation.item.done` before
  `response.create` did not fix it. Any eval built on this harness needs enough
  samples per cell to absorb it, and should report the dropout rate rather than
  scoring those runs as a failure to perceive.

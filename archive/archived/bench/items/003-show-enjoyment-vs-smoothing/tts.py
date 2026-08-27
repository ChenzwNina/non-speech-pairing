# Walking off with someone else's coffee
# setting: Two friends who see each other most mornings, talking on the walk into work.
# --------------------------------------------------------------------
SPEAKER_A_VOICE_ID = ""  # fill in
SPEAKER_B_VOICE_ID = ""  # fill in

# ====================================================================
# PERFORMANCE_A — Show enjoyment
# branch:   Pleasant incongruity
# framing:  A tells the whole thing as a story worth telling, already grinning on the first line and leaning into the punchline of having kept drinking; B is enjoying it along with A. By the final turn the mix-up is pure entertainment, and A's laugh hands it over to be enjoyed.
# expected: A is laughing because the mix-up is funny to A, offering it up as a good story for B to enjoy too.
PERFORMANCE_A = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[amused] So I grabbed the cup off the counter and [chuckle] left."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[amused] Was it yours?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[laughing] There was a name on it, and it wasn't mine!"
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[giggling] When did you notice?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[delighted] About halfway through it! [laughing]"
        ),
    },
]

# ====================================================================
# PERFORMANCE_B — Smoothing / softening
# branch:   Social incongruity
# framing:  A brings it up flatly and a little reluctantly, like something A would rather not have to say out loud; B keeps the questions gentle. The last line is an admission A is not comfortable making, and the laugh comes in to blunt it.
# expected: A is laughing to take the edge off admitting something A finds a bit shameful, softening the confession rather than enjoying it.
PERFORMANCE_B = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[uncomfortable] So I grabbed the cup off the counter and left."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[quiet] Was it yours?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[uncomfortable] There was a name on it, and... it wasn't mine."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[gentle] When did you notice?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[embarrassed] About halfway through it... [embarrassed laugh]"
        ),
    },
]

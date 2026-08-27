# Leftover screws from the same chair
# setting: A and B are friends who happen to have bought the same desk chair, talking in a kitchen while the kettle boils.
# --------------------------------------------------------------------
SPEAKER_A_VOICE_ID = ""  # fill in
SPEAKER_B_VOICE_ID = ""  # fill in

# ====================================================================
# PERFORMANCE_A — Mark pragmatic incongruity (irony / scare-quoting)
# branch:   Pragmatic incongruity
# framing:  A reports the three hours and the spare screws flatly, as evidence rather than as a story, and lands the last line with a level, knowing delivery so that 'good to know' is clearly pointed back at itself — B's spare bracket confirms the chairs ship half-counted, which is the opposite of good news.
# expected: A's laugh tells B not to take the line at face value — A means the opposite of what A just said, that spare parts in both boxes is bad news about the chair.
PERFORMANCE_A = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[flat] I finally put the chair together last night."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[level] How long did it take you?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[deadpan] Three hours. [dry] There were two extra screws left over."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[matter-of-fact] Mine had a spare bracket too."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[sardonic][knowing] Well, that's good to know. [dry laugh]"
        ),
    },
]

# ====================================================================
# PERFORMANCE_B — Show enjoyment
# branch:   Pleasant incongruity
# framing:  A tells the whole thing as a good story, already over the three hours, half-laughing through the count of screws; when B reports a spare bracket, A takes the line straight and hears it as genuinely worth knowing, and the laugh is A enjoying the coincidence and handing it back to B.
# expected: A's laugh shows A is enjoying the coincidence that B's chair came with spare parts as well, and is offering it up for B to enjoy too.
PERFORMANCE_B = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[amused] I finally put the chair together last night."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[grinning] How long did it take you?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[laughing] Three hours. [chuckle] There were two extra screws left over."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[amused] Mine had a spare bracket too."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[delighted] Well, that's good to know. [laughing]"
        ),
    },
]

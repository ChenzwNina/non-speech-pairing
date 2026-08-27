# The tray in the car footwell
# setting: Two neighbours from the same street, standing in the driveway between their houses.
# --------------------------------------------------------------------
SPEAKER_A_VOICE_ID = ""  # fill in
SPEAKER_B_VOICE_ID = ""  # fill in

# ====================================================================
# PERFORMANCE_A — Show enjoyment
# branch:   Pleasant incongruity
# framing:  A tells it with the timing of a bit — a beat before the brake, and the footwell detail delivered as the payoff — so the whole thing arrives as something offered up to be enjoyed rather than reported.
# expected: B is joining A in enjoying how ridiculous the moment was, laughing along with a story A is clearly having fun telling.
PERFORMANCE_A = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[amused] I had the tray on the passenger seat, and then [chuckle] I had to brake."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[amused] And it went?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[laughing] Straight into the footwell, [giggling] the whole tray."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[delighted] Oh man! [loud laugh]"
        ),
    },
]

# ====================================================================
# PERFORMANCE_B — Show sympathy
# branch:   Social incongruity
# framing:  A recounts it flatly and lands on the footwell line without lift, as if the annoyance hasn't worn off yet, so B's response has to meet a still-sore moment rather than a joke.
# expected: B's small laugh is a warm show of fellow-feeling toward A, softening a moment that still bothers A rather than finding it funny.
PERFORMANCE_B = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[flat] I had the tray on the passenger seat, and then I had to brake."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[quiet] And it went."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[sad] Straight into the footwell. The whole tray."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[sympathetic laugh][soft exhale laugh][sad] Oh man..."
        ),
    },
]

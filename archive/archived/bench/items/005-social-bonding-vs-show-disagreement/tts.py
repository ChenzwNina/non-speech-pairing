# Early swims at the outdoor pool
# setting: A and B swim at the same outdoor pool and are getting changed afterwards.
# --------------------------------------------------------------------
SPEAKER_A_VOICE_ID = ""  # fill in
SPEAKER_B_VOICE_ID = ""  # fill in

# ====================================================================
# PERFORMANCE_A — Social bonding / show closeness
# branch:   Pleasantness (no incongruity)
# framing:  A tells it plainly and unhurriedly, with no flourish — just someone describing a morning they like. B's echoes are the sound of someone being drawn in, and the closing laugh is B recognising a person they know well and are fond of.
# expected: The laugh is warmth toward A — B is showing closeness and fondness for someone whose habits they know, not doubting anything and not finding anything funny.
PERFORMANCE_A = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[relaxed] I was in the water before six this morning."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[softly impressed] Before six."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[content][soft chuckle] The whole lane to myself."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[warm, drawing it out] Every day, then."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[easy] Every day since April."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[warm laugh][tender] Of course you do."
        ),
    },
]

# ====================================================================
# PERFORMANCE_B — Show disagreement
# branch:   Social incongruity
# framing:  A delivers each line with a bit of a flourish, pleased with the account. B's echoes come back flat and unconvinced, and rather than say they don't buy it, B lets the laugh do it.
# expected: The laugh rejects what A just said — instead of arguing, B laughs to make clear they don't buy the claim.
PERFORMANCE_B = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[pleased] I was in the water before six this morning."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[flat] Before six?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[relishing it] The whole lane to myself."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[dry, unconvinced] Every day, then?"
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[doubling down] Every day since April."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[disbelieving laugh][dismissive] Of course you do."
        ),
    },
]

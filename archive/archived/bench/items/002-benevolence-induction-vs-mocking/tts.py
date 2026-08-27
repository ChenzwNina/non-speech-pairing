# Bowls on the dishwasher top rack
# setting: Two flatmates standing at the open dishwasher in the kitchen they share.
# --------------------------------------------------------------------
SPEAKER_A_VOICE_ID = ""  # fill in
SPEAKER_B_VOICE_ID = ""  # fill in

# ====================================================================
# PERFORMANCE_A — Benevolence induction
# branch:   Social incongruity
# framing:  Both keep an even, unbothered tone through the back-and-forth, trading their bits of evidence without heat. B's last turn arrives with the laugh first, opening the line rather than closing it, so the words land as a bid for A to agree that this is small enough to drop.
# expected: B's laugh is a friendly nudge inviting A to come round and agree that this is too small to keep going over, keeping things easy between them.
PERFORMANCE_A = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[even] You put the bowls on the top rack again."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[easy] That's where they were when I opened it."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[matter of fact] They come out wet up there."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[light] They came out dry last time."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[plain] I moved them before I ran it."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[coaxing laugh][warm] It's a dishwasher. [light chuckle][hopeful]"
        ),
    },
]

# ====================================================================
# PERFORMANCE_B — Mocking
# branch:   Social incongruity
# framing:  The exchange tightens as it goes: A gets firmer, B gets flatter and shorter. B's last turn opens on a snort and the words come down clipped and from above, so the line answers A's point by refusing to treat it as a point.
# expected: B's laugh talks down to A, treating A's concern as something to be laughed at rather than answered, and puts B above the whole thing.
PERFORMANCE_B = [
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[flat] You put the bowls on the top rack again."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[clipped] That's where they were when I opened it."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[firm] They come out wet up there."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[unimpressed] They came out dry last time."
        ),
    },
    {
        "voice_id": SPEAKER_A_VOICE_ID,
        "text": (
            "[insistent] I moved them before I ran it."
        ),
    },
    {
        "voice_id": SPEAKER_B_VOICE_ID,
        "text": (
            "[snort][condescending] It's a dishwasher. [derisive laugh]"
        ),
    },
]

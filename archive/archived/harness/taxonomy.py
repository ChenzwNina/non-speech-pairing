"""Machine-readable form of the Mazzocconi/Tian/Ginzburg laughter taxonomy.

See ../docs/laughter-taxonomy.md for the prose summary and sources.

Three things live here:
  BRANCHES        the four laughable types (first split of the paper's decision tree)
  FUNCTIONS       terminal pragmatic functions, each tied to a branch
  CONTRAST_PAIRS  curated function pairs that are realisable on *the same words*

The `tags` on each function encode the paper's *form* tier — arousal level, stand-alone vs.
speech-laughter, valence — because those are the levers a TTS engine can actually pull.
"""

import collections

Branch = collections.namedtuple("Branch", "key name gloss")

BRANCHES = collections.OrderedDict(
    (b.key, b)
    for b in [
        Branch(
            "pleasant-incongruity",
            "Pleasant incongruity",
            "Clash between the laughable and background information, perceived as witty, "
            "rewarding or otherwise pleasant: jokes, puns, goofy behaviour, conversational humour.",
        ),
        Branch(
            "social-incongruity",
            "Social incongruity",
            "Clash between social norms and/or comfort and the laughable: embarrassment, "
            "awkwardness, norm violation, asking a favour, criticism.",
        ),
        Branch(
            "pragmatic-incongruity",
            "Pragmatic incongruity",
            "Clash between what is said and what is intended (irony, scare-quoting, hyperbole); "
            "the laugh signals that a less probable interpretation is meant.",
        ),
        Branch(
            "pleasantness",
            "Pleasantness (no incongruity)",
            "No identifiable incongruity; what is conveyed is closeness felt or displayed "
            "towards the interlocutor (thanking, warmth, ingroupness).",
        ),
    ]
)


class Function(object):
    def __init__(self, key, name, branch, cooperative, gloss, framing, arousal, tags):
        self.key = key
        self.name = name
        self.branch = branch
        self.cooperative = cooperative
        self.gloss = gloss
        self.framing = framing  # what the surrounding turns must feel like
        self.arousal = arousal  # low / mid / high, per the paper's form tier
        self.tags = tags  # candidate TTS tags that realise this function

    def as_dict(self):
        return {
            "key": self.key,
            "name": self.name,
            "branch": self.branch,
            "branch_name": BRANCHES[self.branch].name,
            "cooperative": self.cooperative,
            "gloss": self.gloss,
            "framing": self.framing,
            "arousal": self.arousal,
        }


_FUNCTION_LIST = [
    Function(
        "show-enjoyment",
        "Show enjoyment",
        "pleasant-incongruity",
        True,
        "Laugher enjoys a pleasant incongruity and shows it. The most frequent function in the corpora.",
        "The trouble in the story is retold as a good story. Nothing is actually at stake; the "
        "teller is already over it and is offering the mishap up to be enjoyed.",
        "mid",
        ["[amused]", "[laughing]", "[chuckle]", "[loud laugh]", "[delighted]", "[giggling]"],
    ),
    Function(
        "mark-funniness",
        "Mark funniness / mark incongruity",
        "pleasant-incongruity",
        True,
        "Flags that something is absurd or ridiculous when that is not otherwise salient. Does not "
        "require the laugher to enjoy it.",
        "The absurdity is deadpan and would pass unnoticed. The laugh is the only thing pointing at it.",
        "low",
        ["[dry chuckle]", "[short laugh]", "[incredulous laugh]", "[huffed laugh]", "[deadpan]"],
    ),
    Function(
        "smoothing",
        "Smoothing / softening",
        "social-incongruity",
        True,
        "Reduces intrusion or defuses a face threat — negative politeness. Second most frequent cluster.",
        "Something socially uncomfortable has just happened or is about to: a favour, an "
        "imposition, an awkward disclosure. The laugh takes the edge off.",
        "low",
        ["[soft chuckle]", "[awkward laugh]", "[nervous laugh]", "[uncomfortable]", "[embarrassed laugh]"],
    ),
    Function(
        "benevolence-induction",
        "Benevolence induction",
        "social-incongruity",
        True,
        "Induces agreement or goodwill — positive politeness. Clusters with smoothing; differs in "
        "seeking agreement rather than reducing intrusion.",
        "The speaker needs the other side to come along with them. The laugh is an invitation, "
        "slightly ahead of the agreement it is asking for.",
        "low",
        ["[light chuckle]", "[coaxing laugh]", "[warm]", "[hopeful]", "[soft laugh]"],
    ),
    Function(
        "show-agreement",
        "Show agreement",
        "social-incongruity",
        True,
        "Affiliative uptake; typically antiphonal (follows the partner's laugh), laughable from partner.",
        "The partner has just said something the laugher fully endorses. The laugh lands on top of "
        "the partner's, as ratification.",
        "mid",
        ["[laughing along]", "[knowing laugh]", "[agreeing chuckle]", "[emphatic laugh]"],
    ),
    Function(
        "show-sympathy",
        "Show sympathy",
        "social-incongruity",
        True,
        "Aligns with the interlocutor's trouble. A positive shift marked over a negative baseline.",
        "The trouble is real and still stings. The laugh is not at the event, it is toward the person.",
        "low",
        ["[sympathetic laugh]", "[gentle chuckle]", "[sad]", "[commiserating laugh]", "[soft exhale laugh]"],
    ),
    Function(
        "self-mocking",
        "Self-mocking",
        "social-incongruity",
        True,
        "Laughable from self; softens the laugher's own face threat by getting there first.",
        "The laugher is the one who looks bad, and knows it. The laugh pre-empts the judgement.",
        "mid",
        ["[self-deprecating laugh]", "[rueful chuckle]", "[wry laugh]", "[sheepish laugh]"],
    ),
    Function(
        "apology",
        "Apology",
        "social-incongruity",
        True,
        "Laughter doing apologetic work over a small transgression.",
        "A minor offence has just been committed by the laugher and is being acknowledged.",
        "low",
        ["[apologetic laugh]", "[wincing laugh]", "[sorry]", "[small laugh]"],
    ),
    Function(
        "mark-irony",
        "Mark pragmatic incongruity (irony / scare-quoting)",
        "pragmatic-incongruity",
        True,
        "Speaker's own signal that the literal reading is not the intended one — irony, "
        "scare-quoting, hyperbole.",
        "The line, read straight, says the opposite of what is meant. The laugh is the instruction "
        "to re-read it.",
        "low",
        ["[dry laugh]", "[sardonic]", "[air-quotes laugh]", "[flat chuckle]", "[knowing]"],
    ),
    Function(
        "social-bonding",
        "Social bonding / show closeness",
        "pleasantness",
        True,
        "No incongruity at all; conveys closeness and ingroupness, e.g. laughter alongside a compliment "
        "or a thank-you.",
        "Nothing is funny and nothing is awkward. The laugh is just warmth between two people who "
        "like each other.",
        "low",
        ["[warm laugh]", "[affectionate]", "[fond chuckle]", "[happy sigh laugh]", "[tender]"],
    ),
    Function(
        "thanking",
        "Show appreciation / thanking",
        "pleasantness",
        True,
        "Appreciation-marking laughter, no incongruity.",
        "The laugher has just received something — help, a gift, a kindness — and is receiving it well.",
        "low",
        ["[grateful laugh]", "[pleased chuckle]", "[touched]", "[warm]"],
    ),
    Function(
        "mocking",
        "Mocking",
        "social-incongruity",
        False,
        "Non-cooperative: laughter at the partner or the partner's laughable. Damages the flow of "
        "the interaction.",
        "The laugher is above the other person's situation and is letting them know. Derision, not "
        "shared amusement.",
        "mid",
        ["[scoffing laugh]", "[derisive laugh]", "[cold laugh]", "[sarcastic]", "[snort]", "[condescending]"],
    ),
    Function(
        "show-disagreement",
        "Show disagreement",
        "social-incongruity",
        False,
        "Non-cooperative: laughter used to reject what has just been said.",
        "The laugher rejects the claim outright and the laugh stands in for the rebuttal.",
        "mid",
        ["[disbelieving laugh]", "[dismissive laugh]", "[sharp laugh]", "[scornful]"],
    ),
]

FUNCTIONS = collections.OrderedDict((f.key, f) for f in _FUNCTION_LIST)


class ContrastPair(object):
    """A pair of functions that can plausibly sit on the same words."""

    def __init__(self, a, b, note):
        self.a = a
        self.b = b
        self.note = note

    @property
    def key(self):
        return "%s__vs__%s" % (self.a, self.b)

    def functions(self):
        return FUNCTIONS[self.a], FUNCTIONS[self.b]

    def crosses_branch(self):
        return FUNCTIONS[self.a].branch != FUNCTIONS[self.b].branch


CONTRAST_PAIRS = [
    ContrastPair(
        "show-enjoyment",
        "show-sympathy",
        "The reference pair. A mishap narrated as a good story vs. a mishap that still hurts; the "
        "responder's laugh is enjoyment vs. commiseration.",
    ),
    ContrastPair(
        "benevolence-induction",
        "mocking",
        "Same mild dig, cooperative vs. non-cooperative. Warm coaxing laugh keeps the interaction "
        "going; derisive laugh attacks it. The strongest social-consequence flip available.",
    ),
    ContrastPair(
        "show-enjoyment",
        "smoothing",
        "A bold act retold with relish vs. an accident being smoothed over. Identical report, "
        "opposite stance to the social incongruity.",
    ),
    ContrastPair(
        "mark-irony",
        "show-enjoyment",
        "Whether the laugh re-points the speaker's own words (ironic, mean the opposite) or simply "
        "enjoys them as said.",
    ),
    ContrastPair(
        "social-bonding",
        "show-disagreement",
        "Pleasantness with no incongruity at all vs. a laugh that stands in for a rebuttal. Tests "
        "whether the model hears warmth vs. rejection with zero lexical cue.",
    ),
    ContrastPair(
        "self-mocking",
        "mark-funniness",
        "Laughable from self (pre-empting judgement of oneself) vs. laughable in the situation "
        "(pointing at deadpan absurdity). Tests the laughable-origin tier.",
    ),
    ContrastPair(
        "thanking",
        "smoothing",
        "Receiving help well vs. being uncomfortable about needing it. Same acknowledgement, "
        "pleasantness branch vs. social-incongruity branch.",
    ),
    ContrastPair(
        "show-agreement",
        "mocking",
        "Antiphonal ratification vs. derision aimed at the partner who just laughed.",
    ),
]

PAIRS_BY_KEY = collections.OrderedDict((p.key, p) for p in CONTRAST_PAIRS)


def get_pair(spec):
    """Resolve a pair from `a:b`, `a__vs__b`, or an index into CONTRAST_PAIRS."""
    if spec is None:
        return None
    text = str(spec).strip()
    if text.isdigit():
        return CONTRAST_PAIRS[int(text)]
    if text in PAIRS_BY_KEY:
        return PAIRS_BY_KEY[text]
    sep = "__vs__" if "__vs__" in text else ":"
    parts = [p.strip() for p in text.split(sep)]
    if len(parts) != 2:
        raise ValueError("cannot parse pair spec %r" % spec)
    for key in parts:
        if key not in FUNCTIONS:
            raise ValueError("unknown function %r (see --list-functions)" % key)
    for pair in CONTRAST_PAIRS:
        if {pair.a, pair.b} == set(parts):
            return pair
    return ContrastPair(parts[0], parts[1], "ad-hoc pair")


def describe_function(key):
    fn = FUNCTIONS[key]
    return (
        "%s (`%s`)\n"
        "  branch:      %s — %s\n"
        "  cooperative: %s\n"
        "  function:    %s\n"
        "  framing:     %s\n"
        "  arousal:     %s\n"
        "  tag palette: %s"
        % (
            fn.name,
            fn.key,
            BRANCHES[fn.branch].name,
            BRANCHES[fn.branch].gloss,
            "yes" if fn.cooperative else "NO (damages the interaction)",
            fn.gloss,
            fn.framing,
            fn.arousal,
            " ".join(fn.tags),
        )
    )

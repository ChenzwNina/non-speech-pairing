"""Mechanical gates on a generated item.

These run before any model call — they are cheap and they catch the failure modes that make a
contrastive pair worthless (words drifting between performances, emotive punctuation in the
"neutral" transcript, tags left in the transcript).
"""

import re

TAG_RE = re.compile(r"\[[^\]]*\]")
PAREN_RE = re.compile(r"\([^)]*\)")
STAR_RE = re.compile(r"\*[^*]*\*")
WORD_RE = re.compile(r"[a-z0-9']+")

# Punctuation allowed in the tag-free transcript. Anything else colours the delivery.
LEAKY_PUNCT = re.compile(r"[!…—–\"“”*<>~]|\.\.\.|--")

LAUGH_HINT = re.compile(r"laugh|chuckl|giggl|snort|titter|guffaw|cackl|snicker", re.I)


class Failure(object):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail

    def __repr__(self):
        return "%s: %s" % (self.code, self.detail)

    def as_dict(self):
        return {"code": self.code, "detail": self.detail}


def strip_tags(text):
    text = TAG_RE.sub(" ", text)
    text = PAREN_RE.sub(" ", text)
    text = STAR_RE.sub(" ", text)
    return text


def words(text):
    """Lexical content only: tags gone, punctuation gone, case-folded."""
    return WORD_RE.findall(strip_tags(text).lower().replace("’", "'"))


def turn_words(turns):
    out = []
    for t in turns:
        out.append((t["speaker"], tuple(words(t["text"]))))
    return out


REQUIRED_TOP = ["title", "setting", "transcript", "laugh_turn", "laugher", "performance_a", "performance_b"]
REQUIRED_PERF = ["framing", "laughable", "turns", "expected_answer"]


def check(item, require_final_laugh=True):
    """Return a list of Failure. Empty list means the item passes the mechanical gates."""
    fails = []

    for key in REQUIRED_TOP:
        if key not in item:
            fails.append(Failure("missing_field", "top-level field %r" % key))
    if fails:
        return fails

    transcript = item["transcript"]
    if not isinstance(transcript, list) or not transcript:
        return [Failure("bad_transcript", "transcript must be a non-empty list")]

    for name in ("performance_a", "performance_b"):
        perf = item[name]
        if not isinstance(perf, dict):
            fails.append(Failure("bad_performance", "%s must be an object" % name))
            continue
        for key in REQUIRED_PERF:
            if key not in perf:
                fails.append(Failure("missing_field", "%s.%s" % (name, key)))
    if fails:
        return fails

    # --- transcript shape -------------------------------------------------
    if not 4 <= len(transcript) <= 6:
        fails.append(Failure("turn_count", "%d turns, want 4-6" % len(transcript)))

    speakers = [t.get("speaker") for t in transcript]
    if speakers[0] != "A":
        fails.append(Failure("turn_order", "must start with speaker A, got %r" % speakers[0]))
    for i in range(1, len(speakers)):
        if speakers[i] == speakers[i - 1]:
            fails.append(Failure("turn_order", "turns %d/%d share a speaker" % (i - 1, i)))
    if set(speakers) - {"A", "B"}:
        fails.append(Failure("turn_order", "speakers must be A/B, got %r" % sorted(set(speakers))))

    # --- transcript must be clean ----------------------------------------
    for i, t in enumerate(transcript):
        text = t.get("text", "")
        if TAG_RE.search(text) or PAREN_RE.search(text) or STAR_RE.search(text):
            fails.append(Failure("tag_in_transcript", "turn %d: %r" % (i, text)))
        leak = LEAKY_PUNCT.search(text)
        if leak:
            fails.append(
                Failure("leaky_punctuation", "turn %d contains %r: %r" % (i, leak.group(0), text))
            )
        if LAUGH_HINT.search(text):
            fails.append(Failure("laugh_named_in_transcript", "turn %d: %r" % (i, text)))

    if LAUGH_HINT.search(item.get("setting", "")):
        fails.append(Failure("laugh_named_in_setting", item["setting"]))

    # --- laugh turn ------------------------------------------------------
    laugh_turn = item["laugh_turn"]
    if not isinstance(laugh_turn, int) or not 0 <= laugh_turn < len(transcript):
        fails.append(Failure("bad_laugh_turn", "laugh_turn %r out of range" % (laugh_turn,)))
        return fails
    if transcript[laugh_turn]["speaker"] != item["laugher"]:
        fails.append(
            Failure(
                "laugher_mismatch",
                "laugher %r but turn %d is spoken by %r"
                % (item["laugher"], laugh_turn, transcript[laugh_turn]["speaker"]),
            )
        )
    if require_final_laugh and laugh_turn != len(transcript) - 1:
        # Anything said after the laugh reveals how the laugh landed: a smooth continuation reads
        # as cooperative, a stung reply reads as hostile. Closing on the laugh removes that channel.
        fails.append(
            Failure(
                "laugh_not_final",
                "laugh on turn %d of %d — the turns after it leak how it landed"
                % (laugh_turn, len(transcript)),
            )
        )
    laugh_words = words(transcript[laugh_turn]["text"])
    if len(laugh_words) > 6:
        fails.append(
            Failure("laugh_turn_too_long", "%d words on the laugh turn, want <= 6" % len(laugh_words))
        )

    # --- lexical identity across the pair --------------------------------
    base = turn_words(transcript)
    for name in ("performance_a", "performance_b"):
        turns = item[name]["turns"]
        if len(turns) != len(base):
            fails.append(
                Failure("turn_count_mismatch", "%s has %d turns, transcript has %d" % (name, len(turns), len(base)))
            )
            continue
        got = turn_words(turns)
        for i, (want, have) in enumerate(zip(base, got)):
            if want != have:
                fails.append(
                    Failure(
                        "lexical_drift",
                        "%s turn %d: transcript %r vs performance %r"
                        % (name, i, " ".join(want[1]), " ".join(have[1])),
                    )
                )

    # --- each performance must actually laugh ----------------------------
    for name in ("performance_a", "performance_b"):
        turns = item[name]["turns"]
        if laugh_turn >= len(turns):
            continue
        tags = TAG_RE.findall(turns[laugh_turn]["text"])
        if not tags:
            fails.append(Failure("no_tags_on_laugh_turn", "%s turn %d" % (name, laugh_turn)))
        elif not any(LAUGH_HINT.search(tag) for tag in tags):
            fails.append(
                Failure(
                    "no_laughter_tag",
                    "%s turn %d tags %r name no laughter" % (name, laugh_turn, tags),
                )
            )

    # --- the two expected answers must differ ----------------------------
    ans_a = set(words(item["performance_a"]["expected_answer"]))
    ans_b = set(words(item["performance_b"]["expected_answer"]))
    if ans_a and ans_b:
        overlap = len(ans_a & ans_b) / float(len(ans_a | ans_b))
        if overlap > 0.6:
            fails.append(
                Failure("answers_too_similar", "jaccard %.2f between the two expected answers" % overlap)
            )

    return fails

"""The only Dia-compatible non-verbal tags this pipeline is allowed to request or accept.

Dia recognizes roughly twenty non-verbal markers, but the v6 vocalization set
(vocalization_emotions.json) uses exactly five. Restricting to this allowlist, rather than
accepting anything shaped like `(word)`, is what rejects `<laugh>`, `[laugh]`, `(laugh)`
(missing the -s), and narrated stage directions such as "Speaker A laughs".
"""

from __future__ import annotations

# vocalization -> the exact Dia tag string for it.
ALLOWED_TAGS: dict[str, str] = {
    "laugh": "(laughs)",
    "sigh": "(sighs)",
    "gasp": "(gasps)",
    "groan": "(groans)",
    "scream": "(screams)",
}

ALLOWED_TAG_STRINGS: frozenset[str] = frozenset(ALLOWED_TAGS.values())


def validate_tag(vocalization: str, tag: str) -> str | None:
    """None if `tag` is the allowed Dia tag for `vocalization`; otherwise the problem."""
    expected = ALLOWED_TAGS.get(vocalization)
    if expected is None:
        return (f"{vocalization!r} is not a recognized vocalization; allowed vocalizations "
                f"are {sorted(ALLOWED_TAGS)}")
    if tag != expected:
        return f"tag {tag!r} for vocalization {vocalization!r} must be exactly {expected!r}"
    return None

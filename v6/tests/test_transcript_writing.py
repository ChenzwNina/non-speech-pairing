"""Stage two's guarantees: five turns, the marker in the last one, never inside a sentence."""

from __future__ import annotations

import re
import unittest

import fixtures  # noqa: F401 - puts v6 on sys.path
import write_transcripts as W

MARKER = W.MARKER


def turns(last: str, count: int = 5, speakers: str = "ABABA") -> list[dict]:
    body = ["Milo hasn't eaten since yesterday.", "Did you call the clinic?",
            "They can see him at four.", "Do you want me to drive?"]
    rows = [{"turn": n + 1, "speaker": speakers[n], "text": body[n % len(body)]}
            for n in range(count - 1)]
    rows.append({"turn": count, "speaker": speakers[count - 1], "text": last})
    return rows


def result(last: str, **over) -> dict:
    return {"turns": over.pop("turns", turns(last)), "how_a_lands": "x",
            "how_b_lands": "y", "still_open_without_sound": "z", **over}


class TestMarkerPosition(unittest.TestCase):
    def test_the_three_legal_positions(self):
        self.assertEqual(W.marker_position(f"{MARKER} They told the manager."),
                         "turn-initial")
        self.assertEqual(W.marker_position(f"They told the manager. {MARKER}"),
                         "turn-final")
        self.assertEqual(W.marker_position(f"They told the manager. {MARKER} I heard at lunch."),
                         "sentence-boundary")

    def test_mid_clause_is_rejected(self):
        """The example the design was specified against."""
        self.assertIsNone(W.marker_position(
            f"The team gave me story feedback {MARKER} and told the manager."))

    def test_other_mid_sentence_forms_are_rejected(self):
        for text in (f"I guess {MARKER} that settles it.",
                     f"So, {MARKER} that's what happened.",
                     f"They told the manager {MARKER}, which was not the plan."):
            self.assertIsNone(W.marker_position(text), text)

    def test_a_question_or_exclamation_also_ends_a_sentence(self):
        self.assertEqual(W.marker_position(f"Did they? {MARKER} That explains it."),
                         "sentence-boundary")
        self.assertEqual(W.marker_position(f"Unbelievable! {MARKER} Anyway."),
                         "sentence-boundary")


class TestProblems(unittest.TestCase):
    def test_a_clean_result_passes(self):
        self.assertEqual(W.problems(result(f"{MARKER} That's that, then.")), [])

    def test_the_marker_must_be_in_the_final_turn(self):
        rows = turns("That's that, then.")
        rows[2]["text"] = f"{MARKER} They can see him at four."
        found = W.problems(result("That's that, then.", turns=rows))
        self.assertTrue(any("must be in turn 5" in line for line in found), found)

    def test_a_mid_sentence_marker_is_caught(self):
        found = W.problems(result(f"The team gave me feedback {MARKER} and told the manager."))
        self.assertTrue(any("interrupts a sentence" in line for line in found), found)

    def test_exactly_one_marker(self):
        for last in ("No marker here at all.",
                     f"{MARKER} Two of them. {MARKER}"):
            found = W.problems(result(last))
            self.assertTrue(any("exactly one" in line for line in found), found)

    def test_speaker_order_must_alternate(self):
        rows = turns("That's that, then.", speakers="ABBAB")
        found = W.problems(result("x", turns=rows))
        self.assertTrue(any("speaker order" in line for line in found), found)

    def test_no_other_bracketed_annotation(self):
        rows = turns(f"{MARKER} That's that, then.")
        rows[1]["text"] = "(sighs) Did you call the clinic?"
        found = W.problems(result("x", turns=rows))
        self.assertTrue(any("only" in line for line in found), found)


class TestVersionBuilding(unittest.TestCase):
    def setUp(self):
        self.turns = turns(f"They told the manager. {MARKER} I heard at lunch.")

    def test_the_three_versions_share_every_word(self):
        def words(rows):
            return [(r["speaker"],
                     re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", r["text"])).strip())
                    for r in rows]

        base = words(W.version(self.turns, None))
        for tag in ("(laughs)", "(sighs)"):
            self.assertEqual(words(W.version(self.turns, tag)), base)

    def test_the_baseline_carries_no_tag_and_no_marker(self):
        text = " ".join(t["text"] for t in W.version(self.turns, None))
        self.assertNotIn(MARKER, text)
        self.assertNotIn("(", text)

    def test_each_condition_carries_exactly_its_own_tag(self):
        for tag, other in (("(laughs)", "(sighs)"), ("(sighs)", "(laughs)")):
            text = " ".join(t["text"] for t in W.version(self.turns, tag))
            self.assertEqual(text.count(tag), 1)
            self.assertNotIn(other, text)

    def test_removing_the_marker_leaves_no_double_space(self):
        for tag in (None, "(laughs)"):
            for turn in W.version(self.turns, tag):
                self.assertNotIn("  ", turn["text"])
                self.assertFalse(turn["text"].startswith(" "))


if __name__ == "__main__":
    unittest.main()

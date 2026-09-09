"""Separability: preference measured, not appropriateness declared.

The rules under test, all of them decisions rather than conveniences:

  a reply that fits both versions equally abstains — it neither proves nor condemns the item
  an item separates only when *both* sides lean toward the condition they came from
  the two conditions' readings are never paired up, and their counts need not match
  a missing score yields no verdict, so an unmeasured item cannot pass by default
  the verdict is a function of the stored scores, so a threshold change costs no calls
"""

from __future__ import annotations

import unittest

import measure_separability as M


def responses(item_id, condition, n):
    return {"item_id": item_id, "condition": condition, "status": "ok",
            "parsed": {"responses": [{"interpretation_index": i, "text": f"r{i}", "note": ""}
                                     for i in range(1, n + 1)]}}


def matrix(item_id, home_away):
    """home_away maps (condition, index) -> (home score, away score)."""
    out = {}
    for (cond, idx), (home, away) in home_away.items():
        out[f"{item_id}__{cond}__{idx}__under__{cond}"] = {"parsed": {"score": home}}
        out[f"{item_id}__{cond}__{idx}__under__{M.OTHER[cond]}"] = {"parsed": {"score": away}}
    return out


class TestSideStats(unittest.TestCase):
    def test_a_generic_reply_abstains(self):
        """Delta 0 is the user's L3 case: appropriate under both, informative about neither."""
        s = M.side_stats([2, 0])
        self.assertEqual((s["prefers_own"], s["generic"], s["prefers_other"]), (1, 1, 0))
        self.assertTrue(s["leans_right_way"], "one clear lean and one abstention still leans")

    def test_all_generic_does_not_lean(self):
        s = M.side_stats([0, 0, 0])
        self.assertEqual(s["mean_delta"], 0.0)
        self.assertFalse(s["leans_right_way"], "no preference at all is not a preference")

    def test_a_wrong_leaning_reply_counts_against(self):
        s = M.side_stats([1, -1])
        self.assertEqual(s["mean_delta"], 0.0)
        self.assertFalse(s["leans_right_way"])

    def test_majority_can_outvote_a_stray(self):
        s = M.side_stats([2, 1, -1])
        self.assertEqual((s["prefers_own"], s["prefers_other"]), (2, 1))
        self.assertTrue(s["leans_right_way"])

    def test_a_big_stray_defeats_a_bare_majority(self):
        """Two narrow wins and one heavy miss is not a separating item."""
        s = M.side_stats([1, 1, -4])
        self.assertEqual(s["prefers_own"], 2)
        self.assertFalse(s["leans_right_way"], "the mean has to agree with the count")


class TestVerdict(unittest.TestCase):
    def setUp(self):
        # the counts differ on purpose: two readings on one side, three on the other
        self.responses = {"v6_x__condition_a": responses("v6_x", "condition_a", 2),
                          "v6_x__condition_b": responses("v6_x", "condition_b", 3)}

    def verdict(self, home_away):
        return M.verdict_for("v6_x", matrix("v6_x", home_away), self.responses)

    def test_both_sides_leaning_separates(self):
        v = self.verdict({("condition_a", 1): (5, 3), ("condition_a", 2): (5, 4),
                          ("condition_b", 1): (5, 3), ("condition_b", 2): (4, 4),
                          ("condition_b", 3): (5, 4)})
        self.assertTrue(v["separable"])
        self.assertEqual(v["condition_a"]["n"], 2)
        self.assertEqual(v["condition_b"]["n"], 3)
        self.assertEqual(v["condition_b"]["generic"], 1)

    def test_one_flat_side_is_enough_to_fail(self):
        """The laugh side can be sharp and the item still not separate."""
        v = self.verdict({("condition_a", 1): (5, 3), ("condition_a", 2): (5, 3),
                          ("condition_b", 1): (4, 4), ("condition_b", 2): (4, 4),
                          ("condition_b", 3): (4, 4)})
        self.assertFalse(v["separable"])
        self.assertTrue(v["condition_a"]["leans_right_way"])
        self.assertFalse(v["condition_b"]["leans_right_way"])

    def test_margin_averages_every_reply_not_every_side(self):
        """Five replies, so the margin weighs the three-reading side more heavily."""
        v = self.verdict({("condition_a", 1): (5, 1), ("condition_a", 2): (5, 1),
                          ("condition_b", 1): (5, 4), ("condition_b", 2): (5, 4),
                          ("condition_b", 3): (5, 4)})
        self.assertEqual(v["margin"], round((4 + 4 + 1 + 1 + 1) / 5, 2))

    def test_a_missing_score_yields_no_verdict(self):
        scores = matrix("v6_x", {("condition_a", 1): (5, 3), ("condition_a", 2): (5, 4),
                                 ("condition_b", 1): (5, 3), ("condition_b", 2): (4, 4),
                                 ("condition_b", 3): (5, 4)})
        del scores["v6_x__condition_b__3__under__condition_a"]
        self.assertIsNone(M.verdict_for("v6_x", scores, self.responses),
                          "an unmeasured item must not pass by default")

    def test_an_invalid_reply_set_yields_no_verdict(self):
        self.responses["v6_x__condition_a"]["status"] = "invalid"
        self.assertIsNone(self.verdict({("condition_b", 1): (5, 3)}))


if __name__ == "__main__":
    unittest.main()

"""Ranking trials: one contrastive pair per item, both directions, gated on perception."""

from __future__ import annotations

import unittest
from collections import Counter

import fixtures
import build_pairs as P
import evalkit as K

SEED = 20260902
VOC = ("condition_a", "condition_b")


def responses(item_ids, models=("openai",), conditions=VOC):
    return [fixtures.response(item_id, condition, model)
            for item_id in item_ids for model in models for condition in conditions]


def all_heard(item_ids, models=("openai",), conditions=VOC):
    return {(m, i, c) for i in item_ids for m in models for c in conditions}


class TestTrialShape(unittest.TestCase):
    def build(self, records, heard, swap=False):
        return P.trials(P.group(records), heard, SEED, "rtest", "judge@test", swap)

    def test_one_item_gives_two_directions(self):
        built, skipped = self.build(responses(["t_01"]), all_heard(["t_01"]))
        self.assertEqual(skipped, [])
        self.assertEqual(len(built), 2)
        self.assertEqual({t["direction"] for t in built}, {"RA", "RB"})

    def test_each_direction_is_judged_in_its_own_context(self):
        built, _ = self.build(responses(["t_01"]), all_heard(["t_01"]))
        for trial in built:
            gold = trial["candidates"][trial["gold_slot"]]
            other = trial["candidates"]["B" if trial["gold_slot"] == "A" else "A"]
            self.assertEqual(gold["condition"], trial["target_condition"])
            self.assertEqual(other["condition"], trial["against_condition"])
            self.assertIn(trial["target_condition"], gold["response_text"])

    def test_the_two_directions_share_the_same_pair_of_replies(self):
        built, _ = self.build(responses(["t_01"]), all_heard(["t_01"]))
        texts = [{c["response_text"] for c in t["candidates"].values()} for t in built]
        self.assertEqual(texts[0], texts[1])

    def test_the_baseline_is_never_involved(self):
        records = responses(["t_01"]) + [fixtures.response("t_01", "baseline")]
        built, _ = self.build(records, all_heard(["t_01"]))
        self.assertEqual(len(built), 2)
        for trial in built:
            self.assertNotEqual(trial["target_condition"], "baseline")
            self.assertNotEqual(trial["against_condition"], "baseline")
            for candidate in trial["candidates"].values():
                self.assertNotEqual(candidate["condition"], "baseline")

    def test_slot_assignment_is_reproducible(self):
        first, _ = self.build(responses(["t_01", "t_02"]), all_heard(["t_01", "t_02"]))
        second, _ = self.build(responses(["t_01", "t_02"]), all_heard(["t_01", "t_02"]))
        self.assertEqual([t["gold_slot"] for t in first], [t["gold_slot"] for t in second])

    def test_both_slots_get_used_across_the_set(self):
        ids = [f"t_{n:02d}" for n in range(1, 11)]
        built, _ = self.build(responses(ids), all_heard(ids))
        self.assertEqual(set(Counter(t["gold_slot"] for t in built)), {"A", "B"})

    def test_swap_duplicate_mirrors_each_direction(self):
        plain, _ = self.build(responses(["t_01"]), all_heard(["t_01"]))
        swapped, _ = self.build(responses(["t_01"]), all_heard(["t_01"]), swap=True)
        self.assertEqual(len(swapped), 2 * len(plain))
        by_direction: dict[str, list[str]] = {}
        for trial in swapped:
            by_direction.setdefault(trial["direction"], []).append(trial["gold_slot"])
        for slots in by_direction.values():
            self.assertEqual(sorted(slots), ["A", "B"])

    def test_models_are_kept_apart(self):
        ids, models = ["t_01"], ("openai", "gemini")
        built, _ = self.build(responses(ids, models), all_heard(ids, models))
        self.assertEqual(len(built), 4)
        for trial in built:
            for candidate in trial["candidates"].values():
                self.assertIn(trial["evaluated_model"], candidate["response_text"])


class TestPerceptionGate(unittest.TestCase):
    """Asking whether a model answered a laugh better than a sigh is meaningless if it did not
    hear which was which — so both conditions must have been identified."""

    def build(self, records, heard):
        return P.trials(P.group(records), heard, SEED, "rtest", "judge@test", False)

    def test_one_condition_misheard_disqualifies_the_item(self):
        built, skipped = self.build(responses(["t_01"]),
                                    {("openai", "t_01", "condition_a")})
        self.assertEqual(built, [])
        self.assertEqual(len(skipped), 1)
        self.assertIn("perception wrong", skipped[0]["reason"])
        self.assertIn("condition_b", skipped[0]["reason"])

    def test_neither_heard_disqualifies_it_too(self):
        built, skipped = self.build(responses(["t_01"]), set())
        self.assertEqual(built, [])
        self.assertEqual(len(skipped), 1)

    def test_a_disqualified_item_is_recorded_not_dropped(self):
        """Coverage is computed from these, so they cannot be silently discarded."""
        ids = ["t_01", "t_02", "t_03"]
        built, skipped = self.build(responses(ids), all_heard(["t_01"]))
        self.assertEqual(len(built), 2)
        self.assertEqual({r["item_id"] for r in skipped}, {"t_02", "t_03"})
        for record in skipped:
            self.assertFalse(record["eligible"])
            self.assertTrue(record["reason"])

    def test_a_missing_response_is_distinguished_from_a_misheard_one(self):
        records = responses(["t_01"]) + [fixtures.response("t_02", "condition_a")]
        built, skipped = self.build(records, all_heard(["t_01", "t_02"]))
        self.assertEqual(len(built), 2)
        reasons = {r["item_id"]: r["reason"] for r in skipped}
        self.assertIn("no response", reasons["t_02"])

    def test_gating_is_per_condition_not_per_model(self):
        ids, models = ["t_01"], ("openai", "gemini")
        heard = all_heard(ids, models) - {("gemini", "t_01", "condition_b")}
        built, skipped = self.build(responses(ids, models), heard)
        self.assertEqual({t["evaluated_model"] for t in built}, {"openai"})
        self.assertEqual([r["evaluated_model"] for r in skipped], ["gemini"])


if __name__ == "__main__":
    unittest.main()

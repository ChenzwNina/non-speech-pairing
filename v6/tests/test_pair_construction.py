"""Two directed paired trials per item, with the gold identity preserved through shuffling."""

from __future__ import annotations

import unittest
from collections import Counter

import fixtures
import build_pairs as P
import evalkit as K

SEED = 20260902


def responses(item_ids, models=("openai",), conditions=K.DEFAULT_RESPONSE_CONDITIONS):
    return [fixtures.response(item_id, condition, model)
            for item_id in item_ids for model in models for condition in conditions]


class TestPairConstruction(unittest.TestCase):
    def build(self, records, swap=False):
        return P.trials(P.group(records), SEED, "rtest", "content_pairwise_judge@test", swap)

    def test_each_vocalization_condition_is_a_target_exactly_once(self):
        built, incomplete = self.build(responses(["t_01"]))
        self.assertEqual(incomplete, [])
        per_target = Counter(t["target_condition"] for t in built)
        self.assertEqual(dict(per_target), {"condition_a": 1, "condition_b": 1})

    def test_two_targets_give_two_directed_trials_per_item(self):
        built, _ = self.build(responses(["t_01", "t_02"]))
        self.assertEqual(len(built), 4)
        self.assertEqual(len({t["task_id"] for t in built}), 4)

    def test_the_baseline_is_never_a_target_or_a_candidate(self):
        """No response is elicited for it, so it cannot appear on either side."""
        built, _ = self.build(responses(["t_01", "t_02", "t_03"]))
        self.assertTrue(built)
        for trial in built:
            self.assertNotEqual(trial["target_condition"], "baseline")
            self.assertNotEqual(trial["against_condition"], "baseline")
            for candidate in trial["candidates"].values():
                self.assertNotEqual(candidate["condition"], "baseline")

    def test_a_stray_baseline_response_does_not_create_trials(self):
        records = responses(["t_01"]) + [fixtures.response("t_01", "baseline")]
        built, _ = self.build(records)
        self.assertEqual(len(built), 2)

    def test_a_target_never_faces_itself(self):
        built, _ = self.build(responses(["t_01"]))
        for trial in built:
            self.assertNotEqual(trial["target_condition"], trial["against_condition"])

    def test_the_same_candidate_pair_appears_under_both_targets(self):
        built, _ = self.build(responses(["t_01"]))
        pairs = {(t["target_condition"], t["against_condition"]) for t in built}
        self.assertIn(("condition_a", "condition_b"), pairs)
        self.assertIn(("condition_b", "condition_a"), pairs)

    def test_shuffling_preserves_the_gold_identity(self):
        built, _ = self.build(responses(["t_01", "t_02", "t_03"]))
        for trial in built:
            gold = trial["candidates"][trial["gold_slot"]]
            other = trial["candidates"]["B" if trial["gold_slot"] == "A" else "A"]
            self.assertEqual(gold["condition"], trial["target_condition"])
            self.assertEqual(other["condition"], trial["against_condition"])
            self.assertIn(trial["target_condition"], gold["response_text"])

    def test_both_slots_get_used(self):
        built, _ = self.build(responses([f"t_{n:02d}" for n in range(1, 11)]))
        slots = Counter(t["gold_slot"] for t in built)
        self.assertEqual(set(slots), {"A", "B"})

    def test_slot_assignment_is_reproducible(self):
        first, _ = self.build(responses(["t_01", "t_02"]))
        second, _ = self.build(responses(["t_01", "t_02"]))
        self.assertEqual([t["gold_slot"] for t in first], [t["gold_slot"] for t in second])

    def test_swap_duplicate_mirrors_every_trial(self):
        plain, _ = self.build(responses(["t_01"]))
        swapped, _ = self.build(responses(["t_01"]), swap=True)
        self.assertEqual(len(swapped), 2 * len(plain))
        self.assertEqual(len(swapped), 4)
        by_key = {}
        for trial in swapped:
            by_key.setdefault((trial["target_condition"], trial["against_condition"]),
                              []).append(trial["gold_slot"])
        for slots in by_key.values():
            self.assertEqual(sorted(slots), ["A", "B"])

    def test_an_item_missing_a_condition_is_skipped_not_half_built(self):
        records = responses(["t_01"]) + [fixtures.response("t_02", "condition_a")]
        built, incomplete = self.build(records)
        self.assertEqual(len(built), 2)
        self.assertEqual(len(incomplete), 1)
        self.assertIn("t_02", incomplete[0])

    def test_models_are_kept_apart(self):
        built, _ = self.build(responses(["t_01"], models=("openai", "gemini")))
        self.assertEqual(len(built), 4)
        for trial in built:
            for candidate in trial["candidates"].values():
                self.assertIn(trial["evaluated_model"], candidate["response_text"])


if __name__ == "__main__":
    unittest.main()

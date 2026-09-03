"""Six directed paired trials per item, with the gold identity preserved through shuffling."""

from __future__ import annotations

import unittest
from collections import Counter

import fixtures
import build_pairs as P
import evalkit as K

SEED = 20260902


def responses(item_ids, models=("openai",), conditions=K.CONDITIONS):
    return [fixtures.response(item_id, condition, model)
            for item_id in item_ids for model in models for condition in conditions]


class TestPairConstruction(unittest.TestCase):
    def build(self, records, swap=False):
        return P.trials(P.group(records), SEED, "rtest", "content_pairwise_judge@test", swap)

    def test_each_target_condition_produces_exactly_two_trials(self):
        built, incomplete = self.build(responses(["t_01"]))
        self.assertEqual(incomplete, [])
        per_target = Counter(t["target_condition"] for t in built)
        for condition in K.CONDITIONS:
            self.assertEqual(per_target[condition], 2, per_target)

    def test_three_targets_give_six_directed_trials_per_item(self):
        built, _ = self.build(responses(["t_01", "t_02"]))
        self.assertEqual(len(built), 12)
        self.assertEqual(len({t["task_id"] for t in built}), 12)

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
        by_key = {}
        for trial in swapped:
            by_key.setdefault((trial["target_condition"], trial["against_condition"]),
                              []).append(trial["gold_slot"])
        for slots in by_key.values():
            self.assertEqual(sorted(slots), ["A", "B"])

    def test_an_item_missing_a_condition_is_skipped_not_half_built(self):
        records = responses(["t_01"]) + [fixtures.response("t_02", "baseline")]
        built, incomplete = self.build(records)
        self.assertEqual(len(built), 6)
        self.assertEqual(len(incomplete), 1)
        self.assertIn("t_02", incomplete[0])

    def test_models_are_kept_apart(self):
        built, _ = self.build(responses(["t_01"], models=("openai", "gemini")))
        self.assertEqual(len(built), 12)
        for trial in built:
            for candidate in trial["candidates"].values():
                self.assertIn(trial["evaluated_model"], candidate["response_text"])


if __name__ == "__main__":
    unittest.main()

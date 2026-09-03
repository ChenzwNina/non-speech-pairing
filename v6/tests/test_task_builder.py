"""Frozen option sets: one correct answer, unique distractors, reproducible, balanced."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import fixtures
import build_tasks as B
import evalkit as K

ITEMS = [fixtures.item(f"t_{n:02d}", *pair) for n, pair in enumerate(
    [("laugh", "sigh"), ("laugh", "gasp"), ("gasp", "scream"), ("groan", "scream"),
     ("sigh", "groan"), ("laugh", "groan"), ("sigh", "scream"), ("gasp", "groan")], start=1)]
SEED = 20260902


class TestPerceptionOptions(unittest.TestCase):
    def setUp(self):
        self.plan = B.perception_options(ITEMS, SEED)

    def test_one_correct_option_and_three_unique_distractors(self):
        for (item_id, condition), frozen in self.plan.items():
            options = frozen["options"]
            self.assertEqual(len(options), 4)
            self.assertEqual(len({o["id"] for o in options}), 4)
            self.assertEqual(len({o["label"] for o in options}), 4,
                             f"{item_id}/{condition} repeats a label")
            correct = [o for o in options if o["id"] == frozen["correct_option"]]
            self.assertEqual(len(correct), 1)
            self.assertEqual(correct[0]["label"], frozen["correct_label"])
            self.assertNotIn(frozen["correct_label"], frozen["distractor_labels"])
            self.assertEqual(len(set(frozen["distractor_labels"])), 3)

    def test_correct_label_is_the_condition_gold(self):
        for item in ITEMS:
            for condition in K.CONDITIONS:
                frozen = self.plan[(item["item_id"], condition)]
                self.assertEqual(frozen["correct_label"],
                                 K.gold_vocalization(item, condition))

    def test_a_fixed_seed_reproduces_the_same_option_order(self):
        again = B.perception_options(ITEMS, SEED)
        self.assertEqual(self.plan, again)

    def test_a_different_seed_changes_the_option_order(self):
        other = B.perception_options(ITEMS, SEED + 1)
        self.assertNotEqual(self.plan, other)

    def test_correct_answer_positions_are_balanced(self):
        counts = Counter(f["correct_option"] for f in self.plan.values())
        self.assertEqual(set(counts), set(B.OPTION_IDS))
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_distractor_use_is_balanced(self):
        counts = Counter(l for f in self.plan.values() for l in f["distractor_labels"])
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 2, counts)

    def test_the_plan_is_global_so_the_item_set_is_fingerprinted(self):
        """Balance is a property of the whole set, so options move when the set moves.

        The spec asks for balanced positions and distractor use, which cannot be computed from
        one item in isolation. So reordering or extending the dataset does change an item's
        options — which is why the task file is written once and stamped with the item set it
        came from, rather than being quietly rebuildable.
        """
        other = B.perception_options(list(reversed(ITEMS)), SEED)
        self.assertNotEqual([f["distractor_labels"] for f in self.plan.values()],
                            [other[k]["distractor_labels"] for k in self.plan])
        self.assertNotEqual(B.fingerprint(ITEMS), B.fingerprint(list(reversed(ITEMS))))
        self.assertEqual(B.fingerprint(ITEMS), B.fingerprint(list(ITEMS)))

    def test_fingerprint_moves_when_an_item_is_added(self):
        self.assertNotEqual(B.fingerprint(ITEMS),
                            B.fingerprint(ITEMS + [fixtures.item("t_99")]))


class TestDryRun(unittest.TestCase):
    def test_guard_refuses_paid_calls_under_dry_run(self):
        K.set_dry_run(True)
        try:
            with self.assertRaises(K.DryRunViolation):
                K.guard("a paid API")
        finally:
            K.set_dry_run(False)
        K.guard("a paid API")

    def test_dry_run_build_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "tasks"
            result = subprocess.run(
                [sys.executable, str(K.HERE / "build_tasks.py"), "--dry-run",
                 "--output", str(out)],
                capture_output=True, text=True, cwd=K.HERE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(out.exists(), "a dry run created output")
            self.assertIn("dry run", result.stdout)


class TestWriteRefusesToClobber(unittest.TestCase):
    def test_write_json_will_not_overwrite_a_frozen_task_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "perception.json"
            K.write_json(path, {"tasks": []})
            with self.assertRaises(K.ConfigError):
                K.write_json(path, {"tasks": ["changed"]})
            K.write_json(path, {"tasks": ["changed"]}, overwrite=True)


if __name__ == "__main__":
    unittest.main()

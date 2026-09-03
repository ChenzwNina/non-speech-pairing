"""Scoring: contracts enforced, bad records retained, denominators honest, bootstrap by item."""

from __future__ import annotations

import unittest

import fixtures
import evalkit as K
import score as S

CFG = (200, 0.95, 20260902)


def absolute(score, item_id="t_01", judge="gpt", unjudgeable=False):
    return fixtures.judgment(f"{item_id}__condition_a__content_absolute__{judge}", item_id,
                             "content_absolute",
                             {"score": score, "rationale": "because", "unjudgeable": unjudgeable},
                             judge=judge)


class TestContracts(unittest.TestCase):
    def test_scores_outside_one_to_five_are_rejected(self):
        for bad in (0, 6, -1, 99):
            errors = K.schema_errors("judge_outputs:content_absolute",
                                     {"score": bad, "rationale": "x", "unjudgeable": False})
            self.assertTrue(errors, f"{bad} was accepted")
        self.assertEqual(K.schema_errors("judge_outputs:content_absolute",
                                         {"score": 3, "rationale": "x",
                                          "unjudgeable": False}), [])

    def test_a_non_integer_score_is_rejected(self):
        errors = K.schema_errors("judge_outputs:content_absolute",
                                 {"score": 3.5, "rationale": "x", "unjudgeable": False})
        self.assertTrue(errors)

    def test_option_letters_outside_a_to_d_are_rejected(self):
        self.assertTrue(K.schema_errors("judge_outputs:mc_answer", {"selected_option": "E"}))
        self.assertEqual(K.schema_errors("judge_outputs:mc_answer",
                                         {"selected_option": "C", "confidence": 0.4}), [])

    def test_confidence_outside_zero_to_one_is_rejected(self):
        self.assertTrue(K.schema_errors("judge_outputs:mc_answer",
                                        {"selected_option": "A", "confidence": 1.4}))


class TestMalformedRecordsRetained(unittest.TestCase):
    def test_malformed_output_is_kept_and_marked_invalid(self):
        directory = K.stage_dir("judgments") / "_test"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "cases.jsonl"
        path.unlink(missing_ok=True)
        for record in (absolute(4),
                       absolute(9, judge="grok"),
                       fixtures.judgment("t_01__condition_a__content_absolute__qwen", "t_01",
                                         "content_absolute", {"rationale": "no score"},
                                         judge="qwen"),
                       fixtures.judgment("t_01__condition_a__content_absolute__gemini", "t_01",
                                         "content_absolute", None, judge="gemini",
                                         status="parse_error")):
            K.append_jsonl(path, record)
        try:
            good, bad = S.load_judgments(directory)
            self.assertEqual(len(good), 1)
            self.assertEqual(len(bad), 3)
            for record in bad:
                self.assertTrue(record["errors"], "an invalid record kept no reason")
                self.assertIn("task_id", record)
        finally:
            path.unlink(missing_ok=True)
            directory.rmdir()


class TestDenominators(unittest.TestCase):
    def test_unjudgeable_records_leave_the_denominator_and_are_counted(self):
        rows = [absolute(5, "t_01"), absolute(3, "t_02"), absolute(4, "t_03"),
                absolute(1, "t_04", unjudgeable=True)]
        block = S.score_absolute(rows, CFG, "content")
        self.assertEqual(block["n"], 3)
        self.assertEqual(block["unjudgeable"], 1)
        self.assertAlmostEqual(block["unjudgeable_rate"], 0.25)
        self.assertAlmostEqual(block["content_absolute"]["value"], 4.0)
        self.assertAlmostEqual(block["normalized"], 0.75)

    def test_known_perception_accuracy(self):
        tasks, rows = {}, []
        for n, (gold, chosen) in enumerate(
                [("laugh", "A"), ("sigh", "A"), ("gasp", "B"), ("none", "A")], start=1):
            item_id = f"t_{n:02d}"
            task_id = f"{item_id}__condition_a__perception"
            tasks[task_id] = fixtures.mc_task(task_id, item_id, "condition_a", gold, "A")
            rows.append(fixtures.judgment(task_id, item_id, "perception",
                                          {"selected_option": chosen}))
        block = S.score_multiple_choice(rows, tasks, list(fixtures.TAGS) + ["none"], CFG)
        self.assertEqual(block["n"], 4)
        self.assertAlmostEqual(block["overall_accuracy"]["value"], 0.75)
        chosen_b = next(o["label"] for o in tasks["t_03__condition_a__perception"]["options"]
                        if o["id"] == "B")
        self.assertEqual(block["confusion"]["gasp"], {chosen_b: 1})

    def test_ambiguity_flagged_rows_are_excluded_and_reported(self):
        tasks, rows = {}, []
        for n, flagged in enumerate([False, False, True], start=1):
            item_id = f"t_{n:02d}"
            task_id = f"{item_id}__condition_a__pragmatic"
            task = fixtures.mc_task(task_id, item_id, "condition_a", "laugh", "A")
            task["ambiguity_flag"] = flagged
            tasks[task_id] = task
            rows.append(fixtures.judgment(task_id, item_id, "pragmatic",
                                          {"selected_option": "A"}))
        block = S.score_multiple_choice(rows, tasks, ["laugh"], CFG)
        self.assertEqual(block["n"], 2)
        self.assertEqual(block["flagged_excluded"], 1)
        self.assertEqual(block["flagged_items"], ["t_03"])


class TestClusterBootstrap(unittest.TestCase):
    def test_resampling_is_by_item_not_by_row(self):
        """One item, two disagreeing rows: item-level resampling cannot move the estimate.

        Resampling rows would draw (wrong, wrong), (wrong, right), (right, right) and produce
        an interval spanning 0 to 1. Resampling items can only ever redraw the single item, so
        every replicate is 0.5 and the interval collapses onto the point.
        """
        rows = [dict(fixtures.judgment("a", "t_01", "perception", {}), _correct=True),
                dict(fixtures.judgment("b", "t_01", "perception", {}), _correct=False)]
        stat = S.cluster_bootstrap(rows, S.accuracy, 200, 0.95, 1)
        self.assertAlmostEqual(stat["value"], 0.5)
        self.assertEqual(stat["items"], 1)
        self.assertAlmostEqual(stat["low"], 0.5)
        self.assertAlmostEqual(stat["high"], 0.5)

    def test_two_items_do_produce_spread(self):
        rows = [dict(fixtures.judgment("a", "t_01", "perception", {}), _correct=True),
                dict(fixtures.judgment("b", "t_02", "perception", {}), _correct=False)]
        stat = S.cluster_bootstrap(rows, S.accuracy, 400, 0.95, 1)
        self.assertEqual(stat["items"], 2)
        self.assertLess(stat["low"], stat["high"])

    def test_an_items_rows_travel_together(self):
        """Every replicate must be a multiple of the per-item row count."""
        rows = []
        for item_id in ("t_01", "t_02", "t_03"):
            for judge in ("gpt", "grok", "qwen"):
                rows.append(dict(fixtures.judgment("x", item_id, "perception", {},
                                                   judge=judge), _correct=True))
        seen = []
        S.cluster_bootstrap(rows, lambda rs: seen.append(len(rs)) or S.accuracy(rs),
                            50, 0.95, 1)
        self.assertTrue(all(size == 9 for size in seen), sorted(set(seen)))


class TestPairScoring(unittest.TestCase):
    def trials_and_rows(self, votes):
        trials, rows = {}, []
        for n, per_trial in enumerate(votes, start=1):
            item_id = f"t_{n:02d}"
            task_id = f"{item_id}__condition_a__content_pair__RA-vs-RB"
            trials[task_id] = {"task_id": task_id, "item_id": item_id,
                               "target_condition": "condition_a",
                               "against_condition": "condition_b", "gold_slot": "A",
                               "swapped": False}
            for judge, correct in per_trial.items():
                rows.append(fixtures.judgment(
                    task_id, item_id, "content_pair",
                    {"preferred_response": "A" if correct else "B", "confidence": 0.7,
                     "rationale": "because"}, judge=judge))
        return trials, rows

    def test_individual_judgements_are_the_primary_unit(self):
        trials, rows = self.trials_and_rows([
            {"gpt": True, "grok": True, "qwen": False, "gemini": False},
            {"gpt": True, "grok": True, "qwen": True, "gemini": True}])
        block = S.score_pairs(rows, trials, CFG, "individual")
        self.assertEqual(block["n"], 8)
        self.assertAlmostEqual(block["content_pair_accuracy"]["value"], 0.75)
        self.assertEqual(block["split_decisions"], 1)
        self.assertAlmostEqual(block["split_rate"], 0.5)
        self.assertEqual(block["chance"], 0.5)

    def test_half_policy_scores_a_split_as_one_half(self):
        trials, rows = self.trials_and_rows([
            {"gpt": True, "grok": False},
            {"gpt": True, "grok": True}])
        block = S.score_pairs(rows, trials, CFG, "half")
        self.assertAlmostEqual(block["aggregated_accuracy"]["value"], 0.75)

    def test_unresolved_policy_drops_the_split_trial(self):
        trials, rows = self.trials_and_rows([
            {"gpt": True, "grok": False},
            {"gpt": True, "grok": True}])
        block = S.score_pairs(rows, trials, CFG, "unresolved")
        self.assertEqual(block["aggregated_accuracy"]["n"], 1)
        self.assertAlmostEqual(block["aggregated_accuracy"]["value"], 1.0)

    def test_gold_slot_is_tracked_so_position_bias_is_visible(self):
        trials, rows = self.trials_and_rows([{"gpt": True}])
        block = S.score_pairs(rows, trials, CFG, "individual")
        self.assertEqual(block["gold_slot_balance"], {"A": 1})


if __name__ == "__main__":
    unittest.main()

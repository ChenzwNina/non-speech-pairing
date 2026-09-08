"""Scoring: contracts enforced, bad records kept, and the gating rules the design specifies.

The rules under test, all of them decisions rather than conveniences:

  perception gates everything, at the condition level
  an item ineligible for ranking is N/A, not zero — its perception failure is already counted
  ranking is per item over two directions: both right 1, one right 0.5, neither 0
  coverage is reported beside conditional accuracy, so a thin denominator cannot hide
  response quality is reported twice, conditional on hearing and end-to-end
  a split tone panel waits for a human and stays out of the denominator
"""

from __future__ import annotations

import unittest

import fixtures
import evalkit as K
import score as S

CFG = (200, 0.95, 20260902)


def judgment(task_id, item_id, task_type, parsed, judge="gpt", condition="condition_a",
             model="openai"):
    return fixtures.judgment(task_id, item_id, task_type, parsed, judge=judge,
                             condition=condition, model=model)


class TestContracts(unittest.TestCase):
    def test_scores_outside_one_to_five_are_rejected(self):
        for bad in (0, 6, -1, 99, 3.5):
            self.assertTrue(K.schema_errors("judge_outputs:content_match",
                                            {"score": bad, "rationale": "x",
                                             "unjudgeable": False}), bad)
        self.assertEqual(K.schema_errors("judge_outputs:content_match",
                                         {"score": 3, "rationale": "x",
                                          "unjudgeable": False}), [])

    def test_perception_is_a_five_way_choice(self):
        for letter in "ABCDE":
            self.assertEqual(K.schema_errors("judge_outputs:mc_answer",
                                             {"selected_option": letter}), [], letter)
        for bad in ("F", "a", ""):
            self.assertTrue(K.schema_errors("judge_outputs:mc_answer",
                                            {"selected_option": bad}), bad)

    def test_interpretation_index_zero_means_no_match(self):
        self.assertEqual(K.schema_errors("judge_outputs:interpretation_match",
                                         {"matched": False, "interpretation_index": 0,
                                          "rationale": "x"}), [])
        self.assertTrue(K.schema_errors("judge_outputs:interpretation_match",
                                        {"matched": True, "interpretation_index": 4,
                                         "rationale": "x"}))


class TestMalformedRecordsRetained(unittest.TestCase):
    def test_malformed_output_is_kept_and_marked_invalid(self):
        directory = K.stage_dir("judgments") / "_test"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "cases.jsonl"
        path.unlink(missing_ok=True)
        for record in (
                judgment("t1", "t_01", "content_match",
                         {"score": 4, "rationale": "ok", "unjudgeable": False}),
                judgment("t2", "t_01", "content_match",
                         {"score": 9, "rationale": "out of range", "unjudgeable": False}),
                judgment("t3", "t_01", "content_match", {"rationale": "no score"}),
                dict(judgment("t4", "t_01", "content_match", None), status="parse_error")):
            K.append_jsonl(path, record)
        try:
            good, bad = S.load_judgments(directory)
            self.assertEqual(len(good), 1)
            self.assertEqual(len(bad), 3)
            for record in bad:
                self.assertTrue(record["errors"], "an invalid record kept no reason")
        finally:
            path.unlink(missing_ok=True)
            directory.rmdir()


class TestMajority(unittest.TestCase):
    def test_two_of_three_carries_it(self):
        self.assertTrue(S.majority([True, True, False]))
        self.assertFalse(S.majority([False, False, True]))

    def test_an_even_split_is_not_rounded(self):
        self.assertIsNone(S.majority([True, False]))
        self.assertIsNone(S.majority([True, True, False, False]))


class TestInterpretation(unittest.TestCase):
    def rows(self, per_item):
        out = []
        for n, votes in enumerate(per_item, start=1):
            item_id = f"t_{n:02d}"
            task = f"{item_id}__condition_a__interpretation"
            for judge, (matched, which) in votes.items():
                out.append(judgment(task, item_id, "interpretation",
                                    {"matched": matched, "interpretation_index": which,
                                     "rationale": "x"}, judge=judge))
        return out

    def test_two_of_three_judges_decide(self):
        block = S.score_interpretation(self.rows([
            {"gpt": (True, 1), "grok": (True, 1), "qwen": (False, 0)},
            {"gpt": (False, 0), "grok": (False, 0), "qwen": (True, 2)}]), CFG)
        self.assertEqual(block["n"], 2)
        self.assertAlmostEqual(block["accuracy"]["value"], 0.5)

    def test_a_tied_panel_leaves_the_denominator_and_is_reported(self):
        block = S.score_interpretation(self.rows([
            {"gpt": (True, 1), "grok": (False, 0)},
            {"gpt": (True, 1), "grok": (True, 1)}]), CFG)
        self.assertEqual(block["n"], 1)
        self.assertEqual(block["ties"], 1)
        self.assertAlmostEqual(block["tie_rate"], 0.5)
        self.assertEqual(block["tie_items"], ["t_01"])


class TestRanking(unittest.TestCase):
    def build(self, per_item, ineligible=0):
        trials, rows = {}, []
        for n, directions in enumerate(per_item, start=1):
            item_id = f"t_{n:02d}"
            for direction, won in directions.items():
                condition = "condition_a" if direction == "RA" else "condition_b"
                task = f"{item_id}__{condition}__content_pair__{direction}-vs-x"
                trials[task] = {"task_id": task, "item_id": item_id,
                                "evaluated_model": "openai", "target_condition": condition,
                                "direction": direction, "gold_slot": "A"}
                rows.append(judgment(task, item_id, "content_pair",
                                     {"preferred_response": "A" if won else "B",
                                      "confidence": 0.7, "rationale": "x"},
                                     condition=condition))
        skipped = [{"evaluated_model": "openai", "item_id": f"x_{n}",
                    "reason": "perception wrong for condition_b"}
                   for n in range(ineligible)]
        return S.score_ranking(rows, trials, skipped, CFG)

    def test_both_directions_right_scores_one(self):
        block = self.build([{"RA": True, "RB": True}])
        self.assertAlmostEqual(block["conditional_accuracy"]["value"], 1.0)

    def test_one_direction_right_scores_a_half(self):
        block = self.build([{"RA": True, "RB": False}])
        self.assertAlmostEqual(block["conditional_accuracy"]["value"], 0.5)

    def test_neither_direction_right_scores_zero(self):
        block = self.build([{"RA": False, "RB": False}])
        self.assertAlmostEqual(block["conditional_accuracy"]["value"], 0.0)

    def test_the_unit_is_the_item_not_the_trial(self):
        """Three items scoring 1, 0.5 and 0 average to 0.5 — not the 3-of-6 trial rate."""
        block = self.build([{"RA": True, "RB": True},
                            {"RA": True, "RB": False},
                            {"RA": False, "RB": False}])
        self.assertEqual(block["eligible_items"], 3)
        self.assertAlmostEqual(block["conditional_accuracy"]["value"], 0.5)
        self.assertEqual(block["score_distribution"], {0.0: 1, 0.5: 1, 1.0: 1})

    def test_ineligible_items_are_not_zero_and_show_up_as_coverage(self):
        """The perception failure is already counted once; charging it again here would double it."""
        block = self.build([{"RA": True, "RB": True}], ineligible=3)
        self.assertAlmostEqual(block["conditional_accuracy"]["value"], 1.0)
        self.assertEqual(block["eligible_items"], 1)
        self.assertEqual(block["planned_items"], 4)
        self.assertAlmostEqual(block["coverage"], 0.25)
        self.assertEqual(block["ineligible_reasons"], {"perception wrong": 3})

    def test_chance_is_a_half(self):
        self.assertEqual(self.build([{"RA": True, "RB": True}])["chance"], 0.5)


class TestResponseQuality(unittest.TestCase):
    def rows(self, per_condition):
        out = []
        for n, (condition, score) in enumerate(per_condition, start=1):
            item_id = f"t_{n:02d}"
            out.append(judgment(f"{item_id}__{condition}__content_match", item_id,
                                "content_match",
                                {"score": score, "rationale": "x", "unjudgeable": False},
                                condition=condition))
        return out

    def test_conditional_counts_only_what_was_heard(self):
        rows = self.rows([("condition_a", 5), ("condition_a", 3), ("condition_a", 1)])
        heard = {("openai", "t_01", "condition_a"), ("openai", "t_02", "condition_a")}
        block = S.score_response_quality(rows, heard, CFG)
        self.assertEqual(block["n_conditional"], 2)
        self.assertAlmostEqual(block["conditional_quality"]["value"], 4.0)

    def test_end_to_end_floors_a_perception_failure_to_zero(self):
        """Not to 0.25, which a normalised 1 would give — it heard nothing, so it scores nothing."""
        rows = self.rows([("condition_a", 5), ("condition_a", 5)])
        heard = {("openai", "t_01", "condition_a")}
        block = S.score_response_quality(rows, heard, CFG)
        self.assertAlmostEqual(block["conditional_quality"]["value"], 5.0)
        self.assertAlmostEqual(block["end_to_end"]["value"], 0.5)

    def test_unjudgeable_leaves_both_denominators(self):
        rows = self.rows([("condition_a", 4), ("condition_a", 1)])
        rows[1]["parsed"]["unjudgeable"] = True
        heard = {("openai", "t_01", "condition_a"), ("openai", "t_02", "condition_a")}
        block = S.score_response_quality(rows, heard, CFG)
        self.assertEqual(block["n"], 1)
        self.assertEqual(block["unjudgeable"], 1)


class TestTone(unittest.TestCase):
    def rows(self, per_task):
        out = []
        for n, votes in enumerate(per_task, start=1):
            item_id = f"t_{n:02d}"
            task = f"{item_id}__condition_a__tone"
            for judge, present in votes.items():
                out.append(judgment(task, item_id, "tone",
                                    {"inappropriate_present": present,
                                     "tones_heard": ["brisk cheer"] if present else [],
                                     "rationale": "x", "unjudgeable": False,
                                     "unjudgeable_reason": ""}, judge=judge))
        return out

    def test_both_judges_hearing_a_wrong_tone_scores_zero(self):
        block = S.score_tone(self.rows([{"gpt-audio": True, "gemini-audio": True}]), CFG)
        self.assertAlmostEqual(block["tone_ok_rate"]["value"], 0.0)
        self.assertEqual(block["tones_heard"], {"brisk cheer": 2})

    def test_neither_hearing_one_scores_one(self):
        block = S.score_tone(self.rows([{"gpt-audio": False, "gemini-audio": False}]), CFG)
        self.assertAlmostEqual(block["tone_ok_rate"]["value"], 1.0)

    def test_a_split_waits_for_a_human_and_leaves_the_denominator(self):
        block = S.score_tone(self.rows([{"gpt-audio": True, "gemini-audio": False},
                                        {"gpt-audio": False, "gemini-audio": False}]), CFG)
        self.assertEqual(block["n"], 1)
        self.assertEqual(block["awaiting_human_review"], 1)
        self.assertAlmostEqual(block["split_rate"], 0.5)
        self.assertAlmostEqual(block["tone_ok_rate"]["value"], 1.0)
        self.assertEqual(block["review_queue"][0]["item_id"], "t_01")


class TestClusterBootstrap(unittest.TestCase):
    def test_resampling_is_by_item_not_by_row(self):
        """One item, two disagreeing rows: item-level resampling cannot move the estimate."""
        rows = [dict(judgment("a", "t_01", "perception", {}), _correct=True),
                dict(judgment("b", "t_01", "perception", {}), _correct=False)]
        stat = S.cluster_bootstrap(rows, S.accuracy, 200, 0.95, 1)
        self.assertAlmostEqual(stat["value"], 0.5)
        self.assertEqual(stat["items"], 1)
        self.assertAlmostEqual(stat["low"], 0.5)
        self.assertAlmostEqual(stat["high"], 0.5)

    def test_two_items_do_produce_spread(self):
        rows = [dict(judgment("a", "t_01", "perception", {}), _correct=True),
                dict(judgment("b", "t_02", "perception", {}), _correct=False)]
        stat = S.cluster_bootstrap(rows, S.accuracy, 400, 0.95, 1)
        self.assertEqual(stat["items"], 2)
        self.assertLess(stat["low"], stat["high"])


if __name__ == "__main__":
    unittest.main()

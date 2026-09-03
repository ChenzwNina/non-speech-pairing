"""The validator must catch the defects that would silently corrupt every downstream score."""

from __future__ import annotations

import pathlib
import unittest

import fixtures
import validate_dataset as V


def errors_for(item: dict) -> list[str]:
    found, _notes = V.check_item(item, fixtures.TAGS, fixtures.config(), False)
    return found


class TestValidation(unittest.TestCase):
    def test_clean_item_passes(self):
        self.assertEqual(errors_for(fixtures.item()), [])

    def test_catches_lexical_mismatch_across_conditions(self):
        found = errors_for(fixtures.broken("lexical_mismatch"))
        self.assertTrue(any("differs from baseline in words" in line for line in found), found)

    def test_catches_vocalization_tag_in_baseline(self):
        found = errors_for(fixtures.broken("tag_in_baseline"))
        self.assertTrue(any("baseline contains" in line for line in found), found)

    def test_catches_tag_on_the_wrong_turn(self):
        found = errors_for(fixtures.broken("tag_wrong_turn"))
        self.assertTrue(any("carries its tag on turn" in line for line in found), found)

    def test_catches_tag_attributed_to_the_wrong_speaker(self):
        found = errors_for(fixtures.broken("tag_wrong_speaker"))
        self.assertTrue(any("vocalization_speaker" in line for line in found), found)

    def test_catches_metadata_disagreeing_with_the_item_fields(self):
        found = errors_for(fixtures.broken("metadata_mismatch"))
        self.assertTrue(any("target_emotion" in line for line in found), found)

    def test_catches_a_tag_outside_the_approved_inventory(self):
        found = errors_for(fixtures.broken("unapproved_tag"))
        self.assertTrue(found)

    def test_missing_audio_is_a_note_unless_required(self):
        _found, notes = V.check_item(fixtures.item(), fixtures.TAGS, fixtures.config(), False)
        self.assertEqual(len(notes), 3)
        found, _ = V.check_item(fixtures.item(), fixtures.TAGS, fixtures.config(), True)
        self.assertEqual(len(found), 3)

    def test_missing_audio_is_reported_per_renderer(self):
        config = fixtures.config()
        config["dataset"]["renderers"]["second"] = {
            "audio_root": "out/also-missing",
            "audio_path_template": "{item_id}__{condition}.mp3"}
        _found, notes = V.check_item(fixtures.item(), fixtures.TAGS, config, False)
        self.assertEqual(len(notes), 6, notes)
        self.assertTrue(any(n.startswith("testrender:") for n in notes))
        self.assertTrue(any(n.startswith("second:") for n in notes))

    def test_one_renderer_can_be_checked_alone(self):
        config = fixtures.config()
        config["dataset"]["renderers"]["second"] = {
            "audio_root": "out/also-missing",
            "audio_path_template": "{item_id}__{condition}.mp3"}
        _found, notes = V.check_item(fixtures.item(), fixtures.TAGS, config, False,
                                     ["second"])
        self.assertEqual(len(notes), 3, notes)
        self.assertTrue(all(n.startswith("second:") for n in notes))


class TestRendererPaths(unittest.TestCase):
    def test_each_renderer_resolves_its_own_path(self):
        import evalkit as K
        config = K.load_config()
        paths = {r: K.audio_path(config, "v6_01a", "condition_a", r)
                 for r in K.renderers(config)}
        self.assertEqual(len(set(paths.values())), len(paths),
                         "two renderers resolve to the same file")
        self.assertEqual(K.audio_path(config, "v6_01a", "condition_a"),
                         paths[K.default_renderer(config)])

    def test_an_unknown_renderer_is_refused(self):
        import evalkit as K
        with self.assertRaises(K.ConfigError):
            K.audio_path(K.load_config(), "v6_01a", "baseline", "nosuch")

    def test_config_rejects_a_default_that_is_not_configured(self):
        import evalkit as K
        import tempfile, yaml
        config = yaml.safe_load(K.CONFIG.read_text())
        config["dataset"]["default_renderer"] = "nosuch"
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            yaml.safe_dump(config, handle)
            path = pathlib.Path(handle.name)
        try:
            with self.assertRaises(K.ConfigError):
                K.load_config(path)
        finally:
            path.unlink()

    def test_real_dataset_passes(self):
        import evalkit as K
        config = K.load_config()
        _source, items = K.load_items(config)
        self.assertEqual(len(items), 20)
        for item in items:
            found, _ = V.check_item(item, V.approved_tags(), config, False)
            self.assertEqual(found, [], f"{item['item_id']}: {found}")


if __name__ == "__main__":
    unittest.main()

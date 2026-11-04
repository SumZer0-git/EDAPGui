"""Tests for localization files, shared paths, reference data and constants."""

import json
import tempfile
import unittest
from pathlib import Path

from core import paths
from core.constants import commodities, ship_name_map, ship_size_map, sorted_commodities
from i18n.localization import LocalizationManager, normalize_text


class NormalizeTextTestCase(unittest.TestCase):
    def test_case_accents_and_punctuation_are_ignored(self):
        self.assertEqual(normalize_text("Drücke  zum, Deaktivieren!"), "DRUCKE ZUM DEAKTIVIEREN")

    def test_disengage_messages_exist_for_de_and_en(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        self.assertEqual(len(manager.all_values("PRESS_TO_DISENGAGE_MSG")), len(manager.available_languages))
        self.assertIn("DRÜCKE ZUM DEAKTIVIEREN", manager.all_values("PRESS_TO_DISENGAGE_MSG"))
        for language in ("de", "en"):
            manager = LocalizationManager(str(paths.LOCALES_DIR), language)
            with self.subTest(language=language):
                self.assertTrue(normalize_text(manager["PRESS_TO_DISENGAGE_MSG"]))
                self.assertTrue(normalize_text(manager["LINE_OF_SIGHT_MSG"]))

    def test_fsd_alignment_prompt_exists_in_both_languages(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        values = manager.all_values("ALIGN_WITH_TARGET_MSG")
        self.assertEqual(len(values), len(manager.available_languages))
        self.assertIn("AUF ZIEL AUSRICHTEN", values)
        self.assertIn("ALIGN WITH TARGET DESTINATION", values)


class LocalizationTestCase(unittest.TestCase):
    def test_shipped_languages_have_the_same_keys(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        self.assertIn("en", manager.available_languages)
        self.assertIn("de", manager.available_languages)
        for language in manager.available_languages:
            with self.subTest(language=language):
                manager.change_language(language)
                self.assertEqual(manager.language, language)

    def test_values_are_strings(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        for key in manager._data:
            self.assertIsInstance(manager[key], str, key)

    def test_unknown_language_raises(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        with self.assertRaises(Exception):
            manager.change_language("xx")

    def test_different_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "en.json").write_text(json.dumps({"a": "1", "b": "2"}), encoding="utf-8")
            Path(folder, "de.json").write_text(json.dumps({"a": "1"}), encoding="utf-8")

            with self.assertRaises(Exception):
                LocalizationManager(folder, "en")

    def test_lookup_and_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "en.json")
            path.write_text(json.dumps({"hello": "Hello"}), encoding="utf-8")
            manager = LocalizationManager(folder, "en")
            self.assertEqual(manager["hello"], "Hello")

            path.write_text(json.dumps({"hello": "Hi"}), encoding="utf-8")
            manager.refresh()

            self.assertEqual(manager["hello"], "Hi")


class PathsTestCase(unittest.TestCase):
    def test_project_folders_exist(self):
        for folder in (
            paths.ROOT / "src",
            paths.TEMPLATES_DIR,
            paths.LOCALES_DIR,
            paths.DATA_CONFIGS,
            paths.WAYPOINT_EXAMPLES_DIR,
        ):
            self.assertTrue(folder.is_dir(), folder)

    def test_user_data_is_created_and_seeded(self):
        for folder in (paths.CONFIG_DIR, paths.WAYPOINTS_DIR, paths.LOG_DIR, paths.DEBUG_DIR):
            self.assertTrue(folder.is_dir(), folder)
        self.assertTrue(paths.RESOLUTION_CONFIG.is_file())

    def test_copy_missing_never_overwrites(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            Path(source, "new.json").write_text('{"v": 1}', encoding="utf-8")
            Path(source, "existing.json").write_text('{"v": 1}', encoding="utf-8")
            Path(source, "ignored.txt").write_text("x", encoding="utf-8")
            Path(target, "existing.json").write_text('{"v": 2}', encoding="utf-8")

            paths._copy_missing(Path(source), Path(target))

            self.assertEqual(json.loads(Path(target, "new.json").read_text(encoding="utf-8")), {"v": 1})
            self.assertEqual(json.loads(Path(target, "existing.json").read_text(encoding="utf-8")), {"v": 2})
            self.assertFalse(Path(target, "ignored.txt").exists())

    def test_debug_path_creates_parent_folder(self):
        path = Path(paths.debug_path("offline_test", "file.png"))
        self.addCleanup(lambda: path.parent.rmdir())

        self.assertTrue(path.parent.is_dir())
        self.assertEqual(path.parent, paths.DEBUG_DIR / "offline_test")

    def test_reference_json_files_are_valid(self):
        files = list(paths.DATA.rglob("*.json")) + list(paths.LOCALES_DIR.glob("*.json"))
        self.assertTrue(files)
        for file in files:
            with self.subTest(file=file.name):
                json.loads(file.read_text(encoding="utf-8"))


class ConstantsTestCase(unittest.TestCase):
    def test_ship_sizes(self):
        # Ships without a landing pad size (fighters, SRV) have an empty size
        self.assertTrue(set(ship_size_map.values()) <= {"S", "M", "L", ""})

    def test_every_ship_with_a_size_has_a_name(self):
        self.assertEqual(set(ship_size_map) - set(ship_name_map), set())

    def test_sorted_commodities(self):
        result = sorted_commodities()

        self.assertEqual(result, sorted(result))
        self.assertEqual(len(result), sum(len(group) for group in commodities.values()))


if __name__ == "__main__":
    unittest.main()

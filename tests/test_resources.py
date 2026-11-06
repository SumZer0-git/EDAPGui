"""Tests for localization files, shared paths, reference data and constants."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import paths
from core.constants import commodities, ship_name_map, ship_size_map, sorted_commodities
from i18n.localization import LocalizationManager, normalize_text


class NormalizeTextTestCase(unittest.TestCase):
    def test_case_accents_and_punctuation_are_ignored(self):
        self.assertEqual(normalize_text("Drücke  zum, Deaktivieren!"), "DRUCKE ZUM DEAKTIVIEREN")

    def test_disengage_messages_exist_for_de_and_en(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        self.assertEqual(manager.all_values("PRESS_TO_DISENGAGE_MSG"), ["PRESS TO DISENGAGE"])
        for language in ("de", "en"):
            manager = LocalizationManager(str(paths.LOCALES_DIR), language)
            with self.subTest(language=language):
                self.assertTrue(normalize_text(manager["PRESS_TO_DISENGAGE_MSG"]))
                self.assertTrue(normalize_text(manager["LINE_OF_SIGHT_MSG"]))

    def test_fsd_alignment_prompt_exists_in_both_languages(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")

        values = manager.all_values("ALIGN_WITH_TARGET_MSG")
        self.assertEqual(values, ["ALIGN WITH TARGET DESTINATION"])
        manager.change_language("de")
        self.assertEqual(manager.all_values("ALIGN_WITH_TARGET_MSG"), ["AUF ZIEL AUSRICHTEN"])


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

        for key in manager._packs["en"]["recognition"]:
            self.assertIsInstance(manager[key], str, key)

    def test_unknown_language_warns_and_uses_english(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")
        with self.assertLogs("ed_log", level="WARNING"):
            manager.change_language("xx")
        self.assertEqual(manager.language, "en")

    def test_bad_pack_is_isolated_and_partial_pack_falls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            third = Path(folder, "xx")
            third.mkdir()
            (third / "language.json").write_text(
                json.dumps({"name": "Third language", "ocr_language": "en", "journal_languages": ["Third/XX"]}),
                encoding="utf-8",
            )
            (third / "recognition.json").write_text(
                json.dumps({"ALIGN_WITH_TARGET_MSG": ["THIRD ALIGN", "THIRD ALTERNATIVE"]}), encoding="utf-8"
            )
            broken = Path(folder, "broken")
            broken.mkdir()
            with self.assertLogs("ed_log", level="WARNING"):
                manager = LocalizationManager(folder, "xx")
            self.assertEqual(manager.available_languages, ["en", "xx"])
            self.assertEqual(manager.resolve_language("auto", "Third/XX"), "xx")
            self.assertEqual(manager.all_values("ALIGN_WITH_TARGET_MSG"), ["THIRD ALIGN", "THIRD ALTERNATIVE"])
            self.assertEqual(manager["PRESS_TO_DISENGAGE_MSG"], "PRESS TO DISENGAGE")
            self.assertEqual(manager.commodity_names()["128049152"], "Platinum")
            self.assertTrue(any("broken" in text for text in manager.take_warnings()))

    def test_lookup_and_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            path = Path(folder, "en", "recognition.json")
            original = json.loads(path.read_text(encoding="utf-8"))
            manager = LocalizationManager(folder, "en")
            original["ALIGN_WITH_TARGET_MSG"] = "CHANGED ALIGN"
            path.write_text(json.dumps(dict(reversed(list(original.items())))), encoding="utf-8")
            self.assertNotEqual(manager["ALIGN_WITH_TARGET_MSG"], "CHANGED ALIGN")
            manager.refresh()
            self.assertEqual(manager["ALIGN_WITH_TARGET_MSG"], "CHANGED ALIGN")

    def test_auto_and_manual_selection(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "en")
        self.assertEqual(manager.resolve_language("auto", "German/DE"), "de")
        self.assertEqual(manager.resolve_language("auto", "English/UK"), "en")
        self.assertEqual(manager.resolve_language("en", "German/DE"), "en")
        with self.assertLogs("ed_log", level="WARNING"):
            self.assertEqual(manager.resolve_language("auto", "Missing/XX"), "en")
            self.assertEqual(manager.resolve_language("auto", None), "en")

    def test_duplicate_keys_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            Path(folder, "en", "commodities.json").write_text(
                '{"128049152": "Platinum", "128049152": "Wrong"}', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate key"):
                LocalizationManager(folder)

    def test_english_catalogue_must_cover_all_known_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            Path(folder, "en", "commodities.json").write_text('{"128049152": "Platinum"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "every catalogue ID"):
                LocalizationManager(folder)

    def test_unknown_commodity_ids_exclude_additional_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            shutil.copytree(paths.LOCALES_DIR / "de", Path(folder, "de"))
            Path(folder, "de", "commodities.json").write_text('{"999999999": "Unknown"}', encoding="utf-8")
            with self.assertLogs("ed_log", level="WARNING"):
                manager = LocalizationManager(folder)
            self.assertEqual(manager.available_languages, ["en"])
            self.assertTrue(any("unknown commodity IDs" in warning for warning in manager.take_warnings()))

    def test_recognition_uses_cached_active_pack_only(self):
        manager = LocalizationManager(str(paths.LOCALES_DIR), "de")
        with patch.object(Path, "open", side_effect=AssertionError("Detection must not reopen pack files")):
            self.assertEqual(manager.all_values("PRESS_TO_DISENGAGE_MSG"), ["DRÜCKE ZUM DEAKTIVIEREN"])
            manager.change_language("en")
            self.assertEqual(manager.all_values("PRESS_TO_DISENGAGE_MSG"), ["PRESS TO DISENGAGE"])

    def test_duplicate_journal_alias_is_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "xx"))
            with self.assertLogs("ed_log", level="WARNING"):
                manager = LocalizationManager(folder)
            self.assertEqual(manager.available_languages, ["en"])
            self.assertTrue(any("duplicate journal languages" in warning for warning in manager.take_warnings()))


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

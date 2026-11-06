"""Game-language selection and internal-panel checks without game inputs or model downloads."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import paths
from game.journal import EDJournal
from i18n.localization import LocalizationManager
from panels.internal_status import EDInternalStatusPanel
from tests.test_journal import new_journal

try:
    from vision.ocr import OCR  # noqa: F401

    _PADDLEOCR_STUBBED = False
except ImportError:
    sys.modules["paddleocr"] = SimpleNamespace(PaddleOCR=None)
    _PADDLEOCR_STUBBED = True

from core.autopilot import EDAutopilot  # noqa: E402

if _PADDLEOCR_STUBBED:
    del sys.modules["paddleocr"]
    sys.modules.pop("vision.ocr", None)


class JournalLanguageTests(unittest.TestCase):
    def test_header_retains_language_including_documented_case(self):
        journal = new_journal()
        for event, language in (("Fileheader", "German/DE"), ("fileheader", "English/UK")):
            journal.parse_line({"event": event, "language": language})
            self.assertEqual(journal.ship["language"], language)
            self.assertFalse(journal.ship["language_pending"])
        journal.parse_line({"event": "Fileheader"})
        self.assertIsNone(journal.ship["language"])

    def test_rollover_replaces_language_and_missing_header_does_not_reuse_old_language(self):
        import io

        journal = new_journal()
        journal.ship["language"] = "German/DE"
        journal.current_log = "old.log"
        journal.last_mod_time = None
        journal.log_file = io.StringIO()
        for contents, expected in (
            ('{"event":"Fileheader","language":"English/UK"}\n', "English/UK"),
            ('{"event":"Fileheader"}\n', None),
        ):
            journal.current_log = "old.log"
            with (
                patch.object(journal, "get_latest_log", return_value="new.log"),
                patch.object(journal, "get_file_modified_time", return_value=1),
                patch("builtins.open", return_value=io.StringIO(contents)),
            ):
                self.assertEqual(journal.ship_state()["language"], expected)

    def test_partial_header_is_retried_without_restarting_app(self):
        import io

        journal = new_journal()
        journal.current_log = "current.log"
        journal.last_mod_time = None
        journal.log_file = io.StringIO('{"event":"Fileheader","language":')
        with (
            patch.object(journal, "get_latest_log", return_value="current.log"),
            patch.object(journal, "get_file_modified_time", return_value=1),
        ):
            journal.ship_state()
            self.assertIsNone(journal.last_mod_time)
            journal.log_file = io.StringIO('{"event":"Fileheader","language":"German/DE"}\n')
            self.assertEqual(journal.ship_state()["language"], "German/DE")

    def test_empty_new_journal_waits_for_header_but_complete_record_ends_pending_state(self):
        import io

        journal = new_journal()
        journal.current_log = "old.log"
        journal.log_file = io.StringIO()
        for contents in ("", '{"event":"Fileheader"'):
            journal.current_log = "old.log"
            with (
                self.subTest(contents=contents),
                patch.object(journal, "get_latest_log", return_value="new.log"),
                patch.object(journal, "get_file_modified_time", return_value=1),
                patch("builtins.open", return_value=io.StringIO(contents)),
            ):
                self.assertTrue(journal.ship_state()["language_pending"])
        journal.parse_line({"event": "Fileheader"})
        self.assertFalse(journal.ship["language_pending"])
        self.assertIsNone(journal.ship["language"])
        journal.ship["language_pending"] = True
        journal.parse_line({"event": "Music", "MusicTrack": "MainMenu"})
        self.assertFalse(journal.ship["language_pending"])

    def test_no_journal_does_not_wait_for_a_nonexistent_header(self):
        with patch.object(EDJournal, "get_latest_log", return_value=None), self.assertLogs("ed_log", level="WARNING"):
            journal = EDJournal(Mock())
            self.assertIsNone(journal.ship_state()["language"])
            self.assertFalse(journal.ship_state()["language_pending"])


class GameLanguageTests(unittest.TestCase):
    def make_ap(self):
        ap = EDAutopilot.__new__(EDAutopilot)
        ap.locale = LocalizationManager(str(paths.LOCALES_DIR))
        ap.config = {"Language": "auto"}
        ap._language_signature = None
        ap._language_failed_signature = None
        ap.jn = Mock()
        ap.jn.current_log = "current.log"
        ap.jn.ship_state.return_value = {"language": "German/DE"}
        ap.scr = Mock()
        ap.ap_ckb = Mock()
        ap.notify_user = Mock()
        ap.internal_panel = Mock()
        return ap

    def test_delayed_restart_header_never_warns_or_switches_to_english(self):
        ap = self.make_ap()
        ap.ocr = Mock(language="de")
        ap.refresh_game_language()
        ap.ap_ckb.reset_mock()
        ap.jn.current_log = "new.log"
        ap.jn.ship_state.side_effect = [
            {"language": None, "language_pending": True},
            {"language": None, "language_pending": True},
            {"language": "German/DE", "language_pending": False},
        ]
        with patch("core.autopilot.OCR") as factory, patch("core.autopilot.sleep") as wait:
            self.assertTrue(ap.refresh_game_language())
        self.assertEqual(wait.call_count, 2)
        factory.assert_not_called()
        ap.notify_user.assert_not_called()
        ap.ap_ckb.assert_called_once_with("game_language", "de")

    def test_pending_header_timeout_warns_once_and_late_header_still_applies(self):
        ap = self.make_ap()
        ap.jn.ship_state.return_value = {"language": None, "language_pending": True}
        ap.ocr = Mock(language="en")
        with (
            patch("core.autopilot.monotonic", side_effect=[0, 0, 15]),
            patch("core.autopilot.sleep") as wait,
            patch("core.autopilot.OCR") as factory,
            self.assertLogs("ed_log", level="WARNING"),
        ):
            self.assertTrue(ap.refresh_game_language())
            self.assertTrue(ap.refresh_game_language())
        wait.assert_called_once_with(0.2)
        factory.assert_not_called()
        ap.notify_user.assert_called_once()
        ap.jn.ship_state.return_value = {"language": "German/DE", "language_pending": False}
        with patch("core.autopilot.OCR", return_value=Mock(language="de")):
            self.assertTrue(ap.refresh_game_language())
        self.assertEqual(ap.locale.language, "de")

    def test_another_empty_journal_gets_its_own_wait_after_previous_fallback(self):
        ap = self.make_ap()
        ap.ocr = Mock(language="en")
        ap.jn.ship_state.return_value = {"language": None, "language_pending": False}
        with self.assertLogs("ed_log", level="WARNING"):
            ap.refresh_game_language()
        ap.jn.current_log = "next.log"
        ap.jn.ship_state.side_effect = [
            {"language": None, "language_pending": True},
            {"language": "English/UK", "language_pending": False},
        ]
        with patch("core.autopilot.sleep") as wait:
            self.assertTrue(ap.refresh_game_language())
        wait.assert_called_once_with(0.2)

    def test_missing_language_is_not_treated_as_pending_and_manual_override_never_waits(self):
        for selection, pending in (("auto", False), ("de", True)):
            with self.subTest(selection=selection):
                ap = self.make_ap()
                ap.config["Language"] = selection
                ap.jn.ship_state.return_value = {"language": None, "language_pending": pending}
                ap.ocr = Mock(language="de" if selection == "de" else "en")
                with patch("core.autopilot.sleep") as wait, patch("core.autopilot.OCR"):
                    self.assertTrue(ap.refresh_game_language())
                wait.assert_not_called()
                self.assertEqual(ap.notify_user.call_count, 1 if selection == "auto" else 0)

    def test_game_restart_changes_language_without_app_restart(self):
        ap = self.make_ap()
        german, english = Mock(language="de"), Mock(language="en")
        with patch("core.autopilot.OCR", side_effect=[german, english]) as factory:
            self.assertTrue(ap.refresh_game_language())
            self.assertEqual(ap.locale.language, "de")
            self.assertIs(ap.internal_panel.ocr, german)
            self.assertTrue(ap.refresh_game_language())
            self.assertEqual(factory.call_count, 1)
            ap.jn.ship_state.return_value = {"language": "English/UK"}
            self.assertTrue(ap.refresh_game_language())
            self.assertEqual(ap.locale.language, "en")
            self.assertIs(ap.internal_panel.ocr, english)
            self.assertEqual(factory.call_count, 2)

    def test_manual_selection_overrides_journal_and_change_is_queued(self):
        ap = self.make_ap()
        ap.ocr = Mock(language="en")
        ap.set_language("en")
        self.assertEqual(ap.config["Language"], "en")
        self.assertEqual(ap.locale.language, "en")
        with patch("core.autopilot.OCR") as factory:
            self.assertTrue(ap.refresh_game_language())
            factory.assert_not_called()
        self.assertEqual(ap.locale.language, "en")
        with self.assertRaises(ValueError):
            ap.set_language("missing")

    def test_unknown_journal_language_warns_once_and_attempts_english(self):
        ap = self.make_ap()
        ap.jn.ship_state.return_value = {"language": "Unknown/XX"}
        ap.ocr = Mock(language="en")
        with self.assertLogs("ed_log", level="WARNING"), patch("core.autopilot.OCR"):
            self.assertTrue(ap.refresh_game_language())
            self.assertTrue(ap.refresh_game_language())
        ap.notify_user.assert_called_once()
        self.assertEqual(ap.locale.language, "en")

    def test_model_failure_is_visible_and_never_uses_old_model_for_new_language(self):
        ap = self.make_ap()
        with patch("core.autopilot.OCR", side_effect=RuntimeError("model unavailable")), self.assertLogs("ed_log"):
            self.assertFalse(ap.refresh_game_language())
            self.assertFalse(ap.refresh_game_language())
        ap.notify_user.assert_called_once()
        self.assertEqual(ap.locale.language, "en")
        self.assertIsNone(ap._language_signature)

    def test_unsupported_ocr_code_uses_english_with_warning(self):
        ap = self.make_ap()
        ap.locale._packs["de"]["metadata"]["ocr_language"] = "missing"
        ap.ocr = Mock(language="en")
        with patch("core.autopilot.OCR") as factory, self.assertLogs("ed_log", level="WARNING"):
            factory.supports_language.return_value = False
            self.assertTrue(ap.refresh_game_language())
        self.assertEqual(ap.locale.language, "en")
        factory.assert_not_called()
        ap.notify_user.assert_called_once()


class InternalPanelLanguageTests(unittest.TestCase):
    def make_panel(self, language):
        panel = EDInternalStatusPanel.__new__(EDInternalStatusPanel)
        panel.locale = LocalizationManager(str(paths.LOCALES_DIR), language)
        panel.keys = Mock()
        panel.ap_ckb = Mock()
        return panel

    def test_tab_ids_do_not_depend_on_translated_text(self):
        for language, words in (("de", ["INVENTAR"]), ("en", ["INVENTORY"])):
            panel = self.make_panel(language)
            self.assertEqual(panel._tab_id(words), "inventory")
            self.assertEqual(panel._tab_id(["NO INVENTORY MATCH"]), "")
            other = ["INVENTORY"] if language == "de" else ["INVENTAR"]
            self.assertEqual(panel._tab_id(other), "")

    def test_multiple_highlights_never_confirm_inventory(self):
        panel = self.make_panel("en")
        panel.screen = SimpleNamespace(screen_width=3840, screen_height=2160)
        panel.reg = {"right_panel": {"rect": [0.30, 0.20, 0.91, 0.28]}}
        panel.ocr = Mock()
        panel.ocr.solid_highlighted_items.return_value = [Mock(), Mock()]
        self.assertEqual(panel._selected_tab(), "")
        panel.ocr.image_simple_ocr.assert_not_called()

    def test_icon_tabs_navigate_to_inventory_and_require_confirmation(self):
        for tab, steps in (("home", 4), ("playlist", 5)):
            panel = self.make_panel("en")
            panel.show_right_panel = Mock(return_value=(True, tab))
            panel.is_right_panel_active = Mock(return_value=(True, "inventory"))
            with patch("panels.internal_status.sleep"):
                self.assertTrue(panel.show_inventory_tab())
            panel.keys.send.assert_called_once_with("CycleNextPanel", repeat=steps)

    def test_navigation_requires_inventory_confirmation(self):
        panel = self.make_panel("de")
        panel.show_right_panel = Mock(return_value=(True, "modules"))
        panel.is_right_panel_active = Mock(return_value=(True, "inventory"))
        with patch("panels.internal_status.sleep"):
            self.assertTrue(panel.show_inventory_tab())
        panel.keys.send.assert_called_once_with("CycleNextPanel", repeat=3)
        panel.is_right_panel_active.return_value = (False, "")
        with patch("panels.internal_status.sleep"), self.assertLogs("ed_log"):
            self.assertFalse(panel.show_inventory_tab())

    def test_unconfirmed_inventory_never_sends_transfer_inputs(self):
        panel = self.make_panel("de")
        panel.show_inventory_tab = Mock(return_value=False)
        ap = Mock()
        self.assertFalse(panel.transfer_to_fleetcarrier(ap))
        self.assertFalse(panel.transfer_from_fleetcarrier(ap, {}))
        ap.keys.send.assert_not_called()


class LanguageSettingsTests(unittest.TestCase):
    def test_settings_selector_discovers_packs_and_stores_code_not_label(self):
        import tkinter as tk

        import ttkbootstrap as ttk

        from gui.fields import FIELDS
        from gui.pages import build_settings
        from gui.theme import Metrics, Theme

        root = ttk.Window(themename="darkly")
        self.addCleanup(root.destroy)
        root.withdraw()
        locale = LocalizationManager(str(paths.LOCALES_DIR))
        metrics = Metrics(root)
        theme = Theme(root, metrics)
        theme.apply()
        self.variables = {
            field.key: (
                tk.BooleanVar(root, value=False)
                if field.kind == "bool"
                else tk.StringVar(root, value="auto" if field.key == "Language" else "0")
            )
            for field in FIELDS
        }
        app = SimpleNamespace(
            ed_ap=SimpleNamespace(locale=locale),
            metrics=metrics,
            theme=theme,
            vars=self.variables,
            save_labels={},
            commit=Mock(),
        )
        page = ttk.Frame(root)
        build_settings(app, page)

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        selector = next(
            child for child in descendants(page) if isinstance(child, ttk.Combobox) and "Auto" in child.cget("values")
        )
        self.assertEqual(selector.get(), "Auto")
        self.assertIn("Deutsch (de)", selector.cget("values"))
        selector.set("Deutsch (de)")
        selector.event_generate("<<ComboboxSelected>>")
        self.assertEqual(self.variables["Language"].get(), "de")
        app.commit.assert_called_once_with("Settings")

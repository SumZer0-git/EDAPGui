"""Journal, assist and GUI wiring for statistics, also importable in slim CI."""

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ttkbootstrap as ttk

from core.statistics import AssistStatistics, StatisticsSnapshot
from core.types import EdapInterruptError, FsdAssistResult
from gui.pages import build_info
from gui.theme import Metrics, Theme
from routines.assists import AssistsMixin
from tests.test_journal import new_journal
from tests.test_statistics import Clock

try:
    from vision.ocr import OCR  # noqa: F401

    _STUBBED = False
except ModuleNotFoundError as error:
    if error.name != "paddleocr":
        raise
    sys.modules["paddleocr"] = SimpleNamespace(PaddleOCR=None)
    _STUBBED = True

from core.autopilot import EDAutopilot  # noqa: E402
from gui.main_window import APGui  # noqa: E402

if _STUBBED:
    del sys.modules["paddleocr"]
    sys.modules.pop("vision.ocr", None)


class StatisticsIntegrationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.clock = Clock()
        self.notify = Mock()
        self.statistics = AssistStatistics(
            Path(folder.name) / "statistics.sqlite3", self.notify, lambda: self.clock.seconds, lambda: self.clock.utc
        )
        self.addCleanup(self.statistics.close)
        self.journal = new_journal()
        self.journal.parse_line({"event": "LoadGame", "FID": "a", "ShipID": 7, "Ship": "Anaconda"})
        with patch.object(self.journal, "_read_new_lines", return_value=self.journal.ship):
            self.journal.set_statistics_observer(self.statistics.observe)
        self.statistics.begin_assist(self.journal.ship)
        self.statistics.begin_route(self.journal.ship, "End")

    def jump(self, seconds=90, system="Next"):
        self.statistics.expect_jump()
        self.journal.parse_line(
            {
                "event": "StartJump",
                "timestamp": self.clock.utc.isoformat(),
                "JumpType": "Hyperspace",
                "StarClass": "G",
            }
        )
        self.clock.advance(seconds)
        self.journal.parse_line(
            {
                "event": "FSDJump",
                "timestamp": self.clock.utc.isoformat(),
                "StarSystem": system,
                "JumpDist": 40,
            }
        )

    def test_real_journal_parser_delivers_jump_events_once(self):
        self.jump()
        self.jump()
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.ship.jumps, 2)
        self.assertEqual(snapshot.ship.samples, 1)
        self.assertEqual(snapshot.ship.average, 90)
        self.assertEqual(snapshot.commander.distance, 80)

    def test_journal_switches_account_and_ship_without_name_based_identity(self):
        self.jump()
        self.journal.parse_line({"event": "Commander", "FID": "b", "Name": "Other"})
        self.assertIsNone(self.statistics.identity)
        self.journal.parse_line({"event": "LoadGame", "FID": "b", "ShipID": 7, "Ship": "Anaconda"})
        self.assertEqual(self.statistics.snapshot().commander.jumps, 0)
        self.assertFalse(self.statistics.route_active)
        self.journal.parse_line(
            {"event": "Loadout", "ShipID": 8, "Ship": "Anaconda", "CargoCapacity": 10, "Modules": []}
        )
        self.assertEqual(self.statistics.identity.ship_id, 8)
        self.assertEqual(self.statistics.identity.ship_type, "anaconda")
        self.journal.parse_line({"event": "Loadout", "ShipID": 8, "Ship": "Type9", "CargoCapacity": 10, "Modules": []})
        self.assertEqual(self.statistics.identity.ship_type, "type9")

    def test_observer_attachment_drains_startup_before_observing(self):
        journal = new_journal()
        observer = Mock()
        with patch.object(journal, "_read_new_lines") as read:
            journal.set_statistics_observer(observer)
        read.assert_called_once_with()
        observer.assert_not_called()
        journal.parse_line({"event": "LoadGame", "FID": "a", "ShipID": 7, "Ship": "Anaconda"})
        observer.assert_called_once()

    def test_fsd_wrapper_ends_measurement_on_failure_or_interrupt(self):
        for result in (FsdAssistResult.RouteComplete, EdapInterruptError()):
            with self.subTest(result=result):
                assist = AssistsMixin()
                assist.statistics = self.statistics
                assist.jn = SimpleNamespace(ship_state=lambda: self.journal.ship)
                assist.status = Mock()
                assist.status.get_flag.return_value = False
                assist.nav_route = SimpleNamespace(get_last_system=lambda: "End")
                assist._fsd_assist = Mock()
                if isinstance(result, Exception):
                    assist._fsd_assist.side_effect = result
                    with self.assertRaises(EdapInterruptError):
                        assist.fsd_assist(None)
                else:
                    assist._fsd_assist.return_value = result
                    self.assertIs(assist.fsd_assist(None), result)
                self.assertFalse(self.statistics.route_active)

    def test_stop_callback_ends_stats_before_interrupting_flight(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.statistics = self.statistics
        autopilot.travel_assist_enabled = True
        autopilot.ap_thread = Mock()
        autopilot.ctype_async_raise = Mock(side_effect=lambda *_args: self.assertFalse(self.statistics.route_active))
        self.jump()
        autopilot.set_travel_assist(False)
        self.assertFalse(autopilot.travel_assist_enabled)
        autopilot.ctype_async_raise.assert_called_once()

    def make_overlay(self):
        autopilot = EDAutopilot.__new__(EDAutopilot)
        autopilot.statistics = self.statistics
        autopilot.config = {"OverlayTextEnable": True, "OverlayShowETA": True}
        autopilot.travel_assist_enabled = True
        autopilot.waypoint_assist_enabled = False
        autopilot.single_waypoint_enabled = False
        autopilot.ap_state = "Jump"
        autopilot.jn = SimpleNamespace(ship_state=lambda: self.journal.ship)
        autopilot._overlay_route_systems = []
        autopilot._get_overlay_route_progress = Mock(return_value=("on_route", 0, 2))
        autopilot.overlay = Mock()
        autopilot.ap_ckb = Mock()
        return autopilot

    def test_overlay_and_footer_share_eta_without_changing_status(self):
        for _ in range(4):
            self.jump()
        autopilot = self.make_overlay()
        autopilot.update_overlay()
        autopilot.update_route_info()
        segments = autopilot.overlay.overlay_text_segments.call_args.args[1]
        self.assertEqual(segments[0], ("ETA: ", "label"))
        self.assertIn(segments[1][0], autopilot.ap_ckb.call_args.args[1])
        self.assertEqual(autopilot.ap_state, "Jump")
        self.assertEqual(autopilot.ap_ckb.call_args.args[0], "route_info")
        self.assertFalse(self.notify.called)

    def test_eta_calculating_and_hidden_in_local_travel_or_off_route(self):
        autopilot = self.make_overlay()
        self.assertEqual(autopilot._route_eta_text(("on_route", 0, 2)), "Calculating...")
        self.assertIsNone(autopilot._route_eta_text(("off_route", None, 2)))
        self.assertIsNone(autopilot._route_eta_text(("complete", 2, 2)))
        self.statistics.end_route()
        self.assertIsNone(autopilot._route_eta_text(("on_route", 0, 2)))

    def test_gui_statistics_callback_does_not_change_footer_or_ap_status(self):
        self.jump()
        window = APGui.__new__(APGui)
        window.ed_ap = SimpleNamespace(statistics=self.statistics)
        window.statistics_text = Mock()
        window.status = Mock()
        window.route_info = Mock()
        window.callback("statistics", self.statistics.snapshot())
        text = window.statistics_text.set.call_args.args[0]
        self.assertIn("Current account", text)
        self.assertIn("Current ship (#7)", text)
        self.assertIn("Jumps: 1", text)
        window.status.configure.assert_not_called()
        window.route_info.configure.assert_not_called()
        self.assertEqual(window._statistics_text(StatisticsSnapshot(False, None)), "Statistics unavailable.")

    def test_ship_config_callback_preserves_autosave_cleanup_and_saved_state(self):
        window = APGui.__new__(APGui)
        calls = Mock()
        window.load_vars = calls.load_vars
        window._cancel_save_job = calls.cancel_save
        window._set_save = calls.set_save

        window.callback("update_ship_cfg")

        self.assertEqual(
            [(entry[0], entry[1]) for entry in calls.mock_calls],
            [("load_vars", ("Ship",)), ("cancel_save", ("Ship",)), ("set_save", ("Ship", "saved"))],
        )

    def test_info_statistics_fit_small_page_with_large_lifetime_totals(self):
        root = ttk.Window()
        self.addCleanup(root.destroy)
        metrics = Metrics(root)
        theme = Theme(root, metrics)
        theme.apply()
        root.geometry(f"{metrics.px(570)}x{metrics.px(500)}")
        page = ttk.Frame(root)
        page.pack(fill="both", expand=True)
        window = APGui.__new__(APGui)
        window.ed_ap = SimpleNamespace(statistics=self.statistics)
        text = (
            window._statistics_text()
            .replace("Jumps: 0", "Jumps: 1,000,000")
            .replace("Distance: 0.0", "Distance: 100,000,000.0")
        )
        app = SimpleNamespace(
            metrics=metrics,
            theme=theme,
            statistics_text=tk.StringVar(root, value=text),
            update_text=tk.StringVar(root, value="Not checked yet."),
            about=Mock(),
            open_changelog=Mock(),
            check_updates=Mock(),
            open_download=Mock(),
            refresh_update_button=Mock(),
            restart_program=Mock(),
            close_window=Mock(),
        )
        build_info(app, page)
        root.update()
        for column in page.winfo_children():
            for card in column.winfo_children():
                self.assertLessEqual(card.winfo_rooty() + card.winfo_height(), page.winfo_rooty() + page.winfo_height())
                for widget in card.winfo_children():
                    self.assertLessEqual(
                        widget.winfo_rootx() + widget.winfo_width(), card.winfo_rootx() + card.winfo_width()
                    )


if __name__ == "__main__":
    unittest.main()

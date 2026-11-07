"""Station-name navigation safety tests without game input."""

import unittest
from unittest import mock

import cv2
import numpy as np

from core.constants import GuiFocusExternalPanel
from panels.navigation import EDNavigationPanel


class StationNavigationTestCase(unittest.TestCase):
    def setUp(self):
        self.panel = EDNavigationPanel.__new__(EDNavigationPanel)
        self.panel.ap = mock.Mock()
        self.panel.keys = mock.Mock()
        self.panel.ap_ckb = mock.Mock()
        self.panel.ap.has_expected_in_system_target.return_value = False
        for patcher in (
            mock.patch("panels.navigation.sleep"),
            mock.patch("panels.navigation.monotonic", return_value=0),
            mock.patch.object(self.panel, "_navigation_tab", return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_first_exact_row_is_reread_without_scanning_further_or_returning_to_top(self):
        with (
            mock.patch.object(
                self.panel,
                "_selected_destination",
                side_effect=["OHM CITY", "OHM CITY"],
            ),
            mock.patch.object(
                self.panel,
                "_next_destination",
            ) as advance,
        ):
            self.assertTrue(self.panel.lock_destination("Ohm City"))
        self.panel.ap.wait_for_expected_in_system_target.assert_called_once_with("Ohm City")
        advance.assert_not_called()
        self.assertEqual(self.panel.keys.send.call_args_list.count(mock.call("UI_Up", hold=4)), 1)
        self.assertEqual(sum(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list), 2)

    def test_numeric_station_name_is_not_parsed_as_a_distance(self):
        with mock.patch.object(self.panel, "_selected_destination", return_value="STATION 20 3 LS"):
            self.assertTrue(self.panel.lock_destination("Station 20 3 LS"))

    def test_prefix_only_rows_never_receive_select(self):
        with (
            mock.patch.object(self.panel, "_selected_destination", return_value="OHM CITY EXTRA"),
            mock.patch.object(self.panel, "_next_destination", side_effect=["OTHER", None] * 2),
        ):
            self.assertFalse(self.panel.lock_destination("Ohm City"))
        self.assertFalse(any(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list))

    def test_target_below_initial_view_is_selected_without_scanning_after_it(self):
        rows = [f"OTHER STATION {index}" for index in range(20)]
        target = "OHM CITY"
        with (
            mock.patch.object(self.panel, "_selected_destination", side_effect=[rows[0], target]),
            mock.patch.object(self.panel, "_next_destination", side_effect=[*rows[1:], target]) as advance,
        ):
            self.assertTrue(self.panel.lock_destination("Ohm City"))
        self.assertEqual(advance.call_count, 20)
        self.assertEqual(self.panel.keys.send.call_args_list.count(mock.call("UI_Up", hold=4)), 1)
        self.panel.ap.wait_for_expected_in_system_target.assert_called_once_with("Ohm City")

    def test_unconfirmed_game_target_is_not_success(self):
        self.panel.ap.wait_for_expected_in_system_target.return_value = False
        with (
            mock.patch.object(self.panel, "_selected_destination", return_value="OHM CITY"),
            mock.patch.object(self.panel, "_next_destination", return_value=None),
        ):
            self.assertFalse(self.panel.lock_destination("Ohm City"))
        self.assertEqual(self.panel.ap.wait_for_expected_in_system_target.call_count, 2)
        self.panel.ap_ckb.assert_called_once()

    def test_delayed_down_input_waits_for_changed_selection(self):
        with (
            mock.patch.object(self.panel, "_selected_destination", side_effect=["OLD", "", "NEW"]),
        ):
            self.assertEqual(self.panel._next_destination("OLD", 10), "NEW")
        self.panel.keys.send.assert_called_once_with("UI_Down")

    def test_row_changed_before_select_sends_no_select(self):
        with (
            mock.patch.object(
                self.panel,
                "_selected_destination",
                side_effect=["OHM CITY", "OTHER"] * 2,
            ),
            mock.patch.object(self.panel, "_next_destination", return_value=None),
        ):
            self.assertFalse(self.panel.lock_destination("Ohm City"))
        self.assertFalse(any(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list))

    def test_unreadable_row_is_not_a_confirmed_list_end(self):
        with (
            mock.patch("panels.navigation.monotonic", side_effect=[0, 0, 1, 2, 3]),
            mock.patch.object(self.panel, "_selected_destination", return_value=""),
        ):
            self.assertEqual(self.panel._next_destination("OHM CITY", 10), "")

    def test_stable_readable_row_confirms_list_end(self):
        with (
            mock.patch("panels.navigation.monotonic", side_effect=[0, 0, 1, 2, 3]),
            mock.patch.object(self.panel, "_selected_destination", return_value="OHM CITY"),
        ):
            self.assertIsNone(self.panel._next_destination("OHM CITY", 10))

    def test_failed_panel_cleanup_stops_even_when_tab_is_unconfirmed(self):
        self.panel._navigation_tab.return_value = False
        self.panel.ap.ship_control.goto_cockpit_view.return_value = False
        self.assertFalse(self.panel.lock_destination("Ohm City"))
        self.panel._navigation_tab.assert_called_once()
        self.panel.ap_ckb.assert_called_once()

    def test_unreadable_scan_sends_no_select(self):
        with (
            mock.patch.object(self.panel, "_selected_destination", return_value="OTHER"),
            mock.patch.object(self.panel, "_next_destination", return_value=""),
        ):
            self.assertFalse(self.panel.lock_destination("Ohm City"))
        self.assertFalse(any(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list))

    def test_empty_name_and_already_selected_target_send_no_inputs(self):
        self.assertFalse(self.panel.lock_destination(" "))
        self.panel.ap.has_expected_in_system_target.return_value = True
        self.assertTrue(self.panel.lock_destination("Ohm City"))
        self.panel.keys.send.assert_not_called()


class NavigationDiagnosticTestCase(unittest.TestCase):
    def test_failed_tab_saves_evaluated_image_before_later_panel_context(self):
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        evaluated = np.full((40, 100, 3), 7, np.uint8)
        context = np.full((100, 200, 3), 8, np.uint8)
        panel.screen = mock.Mock(screen_width=1920, screen_height=1080)
        panel.ocr = mock.Mock()
        panel.ocr.capture_region_pct.side_effect = [evaluated, context]
        panel.ocr.solid_highlighted_items.return_value = []
        panel.reg = {"nav_panel": {"rect": [0.11, 0.21, 0.70, 0.86]}}
        with (
            mock.patch("panels.navigation.logger.isEnabledFor", return_value=True),
            mock.patch("panels.navigation.save_case") as save,
        ):
            self.assertIsNone(panel._selected_tab())
        self.assertIs(save.call_args.args[2]["evaluated"], evaluated)
        self.assertIs(save.call_args.args[2]["later-panel"], context)
        self.assertEqual(panel.ocr.capture_region_pct.call_count, 2)

    def test_failed_tab_has_no_extra_capture_with_debug_disabled(self):
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        panel.screen = mock.Mock(screen_width=1920, screen_height=1080)
        panel.ocr = mock.Mock()
        panel.ocr.capture_region_pct.return_value = np.zeros((40, 100, 3), np.uint8)
        panel.ocr.solid_highlighted_items.return_value = []
        with (
            mock.patch("panels.navigation.logger.isEnabledFor", return_value=False),
            mock.patch("panels.navigation.save_case") as save,
        ):
            self.assertIsNone(panel._selected_tab())
        self.assertEqual(panel.ocr.capture_region_pct.call_count, 1)
        save.assert_not_called()


class DestinationNameImageTestCase(unittest.TestCase):
    def test_selected_destination_reads_only_name_crop_and_preserves_numeric_name(self):
        row = np.full((80, 1600, 3), 255, dtype=np.uint8)
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        panel.screen = mock.Mock(screen_width=1920, screen_height=1080)
        panel.ocr = mock.Mock()
        panel.ocr.solid_highlighted_items.return_value = [(row, 0, 0, 1600, 80)]
        panel.ocr.image_simple_ocr.return_value = ["Station", "20", "3", "LS"]
        self.assertEqual(panel._selected_destination(), "STATION 20 3 LS")
        image = panel.ocr.image_simple_ocr.call_args.args[0]
        self.assertEqual(image.shape, (56, 1312, 3))

    def test_column_crop_excludes_leading_icons_distance_and_trailing_noise_at_each_scale(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                row = np.full((80 * scale, 1600 * scale, 3), 255, dtype=np.uint8)
                cv2.rectangle(row, (5 * scale, 20 * scale), (40 * scale, 60 * scale), (0, 0, 0), -1)
                cv2.putText(row, "STATION 20 3 LS", (100 * scale, 50 * scale), 0, scale, (0, 0, 0), 2 * scale)
                cv2.putText(row, "1187LS 0", (1400 * scale, 50 * scale), 0, scale, (0, 0, 0), 2 * scale)
                before = row.copy()
                crop = EDNavigationPanel._destination_name_image(row)
                self.assertEqual(crop.shape, (56 * scale, 1312 * scale, 3))
                np.testing.assert_array_equal(crop, row[12 * scale : 68 * scale, 64 * scale : 1376 * scale])
                np.testing.assert_array_equal(row, before)

    def test_tall_trailing_symbol_is_removed_but_text_sized_marks_are_kept(self):
        for background in ((255, 255, 255), (0, 255, 255)):
            with self.subTest(background=background):
                row = np.full((80, 1600, 3), background, dtype=np.uint8)
                cv2.rectangle(row, (120, 25), (130, 50), (0, 0, 0), -1)
                cv2.rectangle(row, (300, 10), (320, 70), (0, 0, 0), 3)
                cv2.rectangle(row, (350, 10), (370, 70), (255, 255, 0), -1)
                crop = EDNavigationPanel._destination_name_image(row)
                self.assertTrue(np.all(crop[13:39, 56:67] == 0))
                self.assertTrue(np.all(crop[:, 230:310] == background))


class NavigationTabTestCase(unittest.TestCase):
    def setUp(self):
        self.panel = EDNavigationPanel.__new__(EDNavigationPanel)
        self.panel.ap = mock.Mock()
        self.panel.ap.debug_overlay = False
        self.panel.keys = mock.Mock()
        self.panel.status_parser = mock.Mock()
        self.panel.status_parser.get_gui_focus.return_value = GuiFocusExternalPanel

    def test_tab_changes_are_confirmed_before_navigation(self):
        with (
            mock.patch("panels.tab_navigation.sleep"),
            mock.patch.object(self.panel, "_selected_tab", side_effect=["contacts", "system", "navigation"]),
        ):
            self.assertTrue(self.panel._navigation_tab())
        self.assertEqual(sum(call.args[0] == "CycleNextPanel" for call in self.panel.keys.send.call_args_list), 2)
        self.assertFalse(any(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list))

    def test_unreadable_tabs_never_confirm_navigation(self):
        with (
            mock.patch("panels.tab_navigation.sleep"),
            mock.patch.object(self.panel, "_selected_tab", return_value=None) as read,
        ):
            self.assertFalse(self.panel._navigation_tab())
        self.assertEqual(read.call_count, 24)
        self.assertFalse(any(call.args[0] == "CycleNextPanel" for call in self.panel.keys.send.call_args_list))
        self.assertFalse(any(call.args[0] == "UI_Select" for call in self.panel.keys.send.call_args_list))

    def test_closed_panel_is_not_read_or_cycled(self):
        self.panel.status_parser.get_gui_focus.return_value = 0
        with (
            mock.patch("panels.tab_navigation.sleep"),
            mock.patch.object(self.panel, "_selected_tab") as read,
        ):
            self.assertFalse(self.panel._navigation_tab())
        read.assert_not_called()
        self.assertFalse(any(call.args[0] == "CycleNextPanel" for call in self.panel.keys.send.call_args_list))


if __name__ == "__main__":
    unittest.main()

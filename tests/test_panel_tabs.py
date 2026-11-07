"""Verified tab switching and docking input safety."""

import unittest
from unittest.mock import Mock, patch

from core.constants import GuiFocusExternalPanel, GuiFocusInternalPanel
from panels.internal_status import EDInternalStatusPanel
from panels.navigation import EDNavigationPanel
from panels.tab_navigation import confirm_panel_tab
from routines.flight import FlightMixin


class PanelTabTestCase(unittest.TestCase):
    def test_timeout_does_not_send_an_input_without_a_followup_check(self):
        status, keys = Mock(), Mock()
        status.get_gui_focus.return_value = GuiFocusExternalPanel
        read = Mock(return_value="navigation")
        with patch("panels.tab_navigation.sleep"), self.assertLogs("ed_log", level="WARNING"):
            self.assertFalse(
                confirm_panel_tab(status, keys, read, GuiFocusExternalPanel, "contacts", "Navigation", attempts=1)
            )
        keys.send.assert_not_called()

    def test_target_already_selected_needs_no_cycle(self):
        status, keys = Mock(), Mock()
        status.get_gui_focus.return_value = GuiFocusInternalPanel
        with patch("panels.tab_navigation.sleep"):
            self.assertTrue(
                confirm_panel_tab(
                    status, keys, Mock(return_value="inventory"), GuiFocusInternalPanel, "inventory", "Internal"
                )
            )
        keys.send.assert_not_called()

    def test_focus_loss_prevents_reads_and_inputs_until_focus_returns(self):
        status, keys = Mock(), Mock()
        status.get_gui_focus.side_effect = [0, GuiFocusInternalPanel, 0, GuiFocusInternalPanel]
        read = Mock(side_effect=["ship", "inventory"])
        with patch("panels.tab_navigation.sleep"):
            self.assertTrue(confirm_panel_tab(status, keys, read, GuiFocusInternalPanel, "inventory", "Internal"))
        self.assertEqual(read.call_count, 2)
        keys.send.assert_called_once_with("CycleNextPanel")

    def test_delayed_switch_is_reread_before_another_input(self):
        status, keys = Mock(), Mock()
        status.get_gui_focus.return_value = GuiFocusExternalPanel
        read = Mock(side_effect=["navigation", "navigation", None, "transactions", "contacts"])
        with patch("panels.tab_navigation.sleep"):
            self.assertTrue(confirm_panel_tab(status, keys, read, GuiFocusExternalPanel, "contacts", "Navigation"))
        self.assertEqual(keys.send.call_count, 2)
        keys.send.assert_called_with("CycleNextPanel")

    def test_dropped_switch_is_retried_only_after_readable_unchanged_tab(self):
        status, keys = Mock(), Mock()
        status.get_gui_focus.return_value = GuiFocusInternalPanel
        read = Mock(side_effect=["ship"] * 4 + ["inventory"])
        with patch("panels.tab_navigation.sleep"):
            self.assertTrue(confirm_panel_tab(status, keys, read, GuiFocusInternalPanel, "inventory", "Internal"))
        self.assertEqual(keys.send.call_count, 2)

    def test_unreadable_or_unfocused_panel_never_sends_tab_input(self):
        for focus, selected in ((GuiFocusInternalPanel, ""), (0, "ship")):
            status, keys, read = Mock(), Mock(), Mock(return_value=selected)
            status.get_gui_focus.return_value = focus
            with patch("panels.tab_navigation.sleep"), self.assertLogs("ed_log", level="WARNING"):
                self.assertFalse(confirm_panel_tab(status, keys, read, GuiFocusInternalPanel, "inventory", "Internal"))
            keys.send.assert_not_called()

    def test_docking_sends_actions_only_after_contacts_confirmation(self):
        for confirmed in (True, False):
            panel = EDNavigationPanel.__new__(EDNavigationPanel)
            panel.keys = Mock()
            panel.ap_ckb = Mock()
            with (
                patch.object(panel, "_show_tab", return_value=confirmed) as show,
                patch.object(panel, "hide_nav_panel") as hide,
                patch("panels.navigation.sleep"),
            ):
                self.assertEqual(panel.request_docking(), confirmed)
            show.assert_called_once_with("contacts")
            hide.assert_called_once()
            if not confirmed:
                panel.keys.send.assert_not_called()
                panel.ap_ckb.assert_called_once()
            else:
                self.assertEqual(
                    [call.args[0] for call in panel.keys.send.call_args_list], ["UI_Up", "UI_Right", "UI_Select"]
                )

    def test_docking_closes_panel_even_if_input_fails(self):
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        panel.keys = Mock()
        panel.keys.send.side_effect = RuntimeError("input failed")
        with patch.object(panel, "_show_tab", return_value=True), patch.object(panel, "hide_nav_panel") as hide:
            with self.assertRaisesRegex(RuntimeError, "input failed"):
                panel.request_docking()
        hide.assert_called_once()

    def test_panel_opening_releases_focus_key_even_if_direction_fails(self):
        for panel_type, direction in ((EDNavigationPanel, "UI_Left"), (EDInternalStatusPanel, "UI_Right")):
            panel = panel_type.__new__(panel_type)
            panel.ap = Mock(debug_overlay=False)
            panel.keys = Mock()

            def fail_direction(key, **kwargs):
                if key == direction:
                    raise RuntimeError("input failed")

            panel.keys.send.side_effect = fail_direction
            with self.assertRaisesRegex(RuntimeError, "input failed"):
                if panel_type is EDNavigationPanel:
                    panel._show_tab("contacts")
                else:
                    panel.show_inventory_tab()
            panel.keys.send.assert_called_with("UIFocus", state=0)

    def test_failed_cockpit_reset_never_opens_either_panel(self):
        for panel_type in (EDNavigationPanel, EDInternalStatusPanel):
            panel = panel_type.__new__(panel_type)
            panel.ap = Mock()
            panel.ap.ship_control.goto_cockpit_view.return_value = False
            panel.keys = Mock()
            with self.assertLogs("ed_log", level="WARNING"):
                result = panel._show_tab("contacts") if panel_type is EDNavigationPanel else panel.show_inventory_tab()
            self.assertFalse(result)
            panel.keys.send.assert_not_called()
            panel.ap.ship_control.goto_cockpit_view.assert_called_once_with(timeout=10.0)

    def test_flight_stops_on_failed_contacts_confirmation(self):
        flight = Mock(nav_panel=Mock())
        flight.nav_panel.request_docking.return_value = False
        with self.assertRaisesRegex(RuntimeError, "contacts tab not confirmed"):
            FlightMixin.request_docking(flight)

    def test_right_panel_detection_is_passive_when_unreadable(self):
        panel = EDInternalStatusPanel.__new__(EDInternalStatusPanel)
        panel.ap = Mock(debug_overlay=False)
        panel.screen = Mock()
        panel.reg = {"right_panel": {"rect": [0.3, 0.2, 0.91, 0.28]}}
        panel.keys = Mock()
        panel.status_parser = Mock()
        with (
            patch.object(panel, "_selected_tab", return_value=""),
            patch("panels.internal_status.sleep"),
        ):
            self.assertEqual(panel.is_right_panel_active(), (False, ""))
        panel.keys.send.assert_not_called()

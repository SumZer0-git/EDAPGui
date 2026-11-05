"""Tests for bounded ship-view navigation."""

import unittest
from unittest import mock

from panels.ship_control import EDShipControl


class ShipControlTestCase(unittest.TestCase):
    def test_cockpit_return_stops_sending_back_inputs_after_timeout(self):
        ship_control = EDShipControl.__new__(EDShipControl)
        ship_control.status_parser = mock.Mock()
        ship_control.status_parser.get_gui_focus.return_value = 1
        ship_control.keys = mock.Mock()
        ship_control.ap_ckb = mock.Mock()

        with (
            mock.patch("panels.ship_control.monotonic", side_effect=[0, 0.5, 1.1]),
            mock.patch("panels.ship_control.sleep"),
            self.assertLogs("ed_log", level="WARNING"),
        ):
            self.assertFalse(ship_control.goto_cockpit_view(timeout=1))

        ship_control.keys.send.assert_called_once_with("UI_Back")
        ship_control.ap_ckb.assert_called_once_with("log", "Could not return to cockpit view. Waypoint Assist stopped.")


if __name__ == "__main__":
    unittest.main()

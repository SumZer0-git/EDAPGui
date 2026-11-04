"""Tests for the end-of-route decision in the assists."""

import unittest
from unittest.mock import Mock, patch

from routines.assists import AssistsMixin


class Assists(AssistsMixin):
    def __init__(self, compass_readings):
        self.have_destination = Mock(side_effect=compass_readings)
        self.travel_assist_enabled = True


def status(name="", body=-1):
    return {"Destination_Name": name, "Destination_Body": body}


@patch("routines.assists.sleep", Mock())
class InSystemTargetTestCase(unittest.TestCase):
    def test_a_station_in_the_status_is_a_target_without_looking_at_the_compass(self):
        assists = Assists([])

        self.assertTrue(assists.has_in_system_target(None, status("Some Station", 20)))
        assists.have_destination.assert_not_called()

    def test_main_star_or_empty_destination_without_compass_is_no_target(self):
        for current in (status(), status("Some Star", 0)):
            with self.subTest(status=current):
                self.assertFalse(Assists([False]).has_in_system_target(None, current))

    def test_compass_fallback_needs_two_readings(self):
        self.assertTrue(Assists([True, True]).has_in_system_target(None, status()))
        self.assertFalse(Assists([True, False]).has_in_system_target(None, status()))


class TravelAssistTestCase(unittest.TestCase):
    def setUp(self):
        self.assists = Assists([])
        self.assists.jn = Mock()
        self.assists.fsd_assist = Mock()
        self.assists.sc_assist = Mock()
        self.assists.update_ap_status = Mock()

    def test_system_target_runs_fsd_route_without_local_target(self):
        self.assists.jn.ship_state.return_value = {"target": "Alpha Centauri"}
        self.assists.fsd_assist.return_value = True

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_called_once_with(None)
        self.assists.sc_assist.assert_not_called()

    def test_system_route_hands_off_to_local_target(self):
        self.assists.jn.ship_state.return_value = {"target": "Alpha Centauri"}
        self.assists.fsd_assist.return_value = False

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_called_once_with(None)
        self.assists.sc_assist.assert_called_once_with(None)

    def test_local_target_runs_supercruise_without_system_route(self):
        self.assists.jn.ship_state.return_value = {"target": None}

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_not_called()
        self.assists.sc_assist.assert_called_once_with(None)

    def test_stopped_travel_assist_does_not_start_local_phase(self):
        self.assists.jn.ship_state.return_value = {"target": "Alpha Centauri"}
        self.assists.fsd_assist.return_value = False
        self.assists.travel_assist_enabled = False

        self.assists.travel_assist(None)

        self.assists.sc_assist.assert_not_called()


if __name__ == "__main__":
    unittest.main()

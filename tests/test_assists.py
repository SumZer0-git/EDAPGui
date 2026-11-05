"""Tests for the end-of-route decision in the assists."""

import unittest
from unittest.mock import Mock, patch

from core.types import ScTargetAlignReturn
from routines.assists import AssistsMixin


class Assists(AssistsMixin):
    def __init__(self, compass_readings):
        self.have_destination = Mock(side_effect=compass_readings)
        self.travel_assist_enabled = True


def status(name="", body=-1):
    return {"Destination_Name": name, "Destination_Body": body}


class InSystemTargetTestCase(unittest.TestCase):
    def test_a_station_in_the_status_is_a_target_without_looking_at_the_compass(self):
        assists = Assists([])

        self.assertTrue(assists.has_in_system_target(status("Some Station", 20)))
        assists.have_destination.assert_not_called()

    def test_main_star_or_empty_destination_does_not_use_the_compass(self):
        for current in (status(), status("Some Star", 0)):
            with self.subTest(status=current):
                assists = Assists([True, True])
                self.assertFalse(assists.has_in_system_target(current))
                assists.have_destination.assert_not_called()

    def test_explicit_waypoint_does_not_start_sc_assist_without_a_status_destination(self):
        assists = Assists([])
        assists.ap_ckb = Mock()
        assists.jn = Mock()
        assists.jn.ship_state.return_value = {"status": "in_supercruise"}
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status()
        assists.status.get_flag.return_value = False
        assists.set_ap_status = Mock()
        assists.sc_assist = Mock()

        with patch("routines.assists.sleep"):
            self.assertFalse(assists.supercruise_to_station(None, "Some Station"))

        assists.have_destination.assert_not_called()
        assists.sc_assist.assert_not_called()

    def test_sc_assist_checks_status_before_touching_the_game_window(self):
        assists = Assists([True])
        assists.ap_ckb = Mock()
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status()
        assists.ship_control = Mock()

        assists.sc_assist(None)

        assists.ship_control.goto_cockpit_view.assert_not_called()
        assists.have_destination.assert_not_called()
        assists.ap_ckb.assert_called_once_with("log", "No local target found. Select a target and try again.")


class ScAssistStatusTestCase(unittest.TestCase):
    def make_assists(self, ap_state, drop_type=None):
        assists = Assists([True])
        assists.ap_state = ap_state
        statuses = []

        def set_ap_status(text):
            assists.ap_state = text
            statuses.append(text)

        assists.set_ap_status = set_ap_status
        assists.ap_ckb = Mock()
        assists.vce = Mock()
        assists.keys = Mock()
        assists.ship_control = Mock()
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status("Some Carrier", 20)
        assists.status.get_flag.return_value = False
        assists.jn = Mock()
        assists.jn.ship_state.return_value = {
            "status": "in_supercruise",
            "interdicted": False,
            "has_adv_dock_comp": True,
            "has_std_dock_comp": False,
            "SupercruiseDestinationDrop_type": drop_type,
        }
        assists.nav_align = Mock()
        assists.sc_target_align = Mock(return_value=ScTargetAlignReturn.Disengage)
        assists.debug_overlay = False
        assists.dock = Mock()
        return assists, statuses

    def run_sc_assist(self, assists):
        with patch("routines.assists.sleep"):
            assists.sc_assist(None)

    def test_travel_assist_reports_each_phase_until_docked(self):
        assists, statuses = self.make_assists("SC to Target")

        self.run_sc_assist(assists)

        self.assertEqual(statuses, ["Align", "SC to Target", "Approaching target", "Docking Complete"])
        assists.dock.assert_called_once_with()

    def test_waypoint_station_name_is_kept_for_the_cruise_phase(self):
        assists, statuses = self.make_assists("SC to Station: Jameson Memorial")

        self.run_sc_assist(assists)

        self.assertEqual(statuses[:2], ["Align", "SC to Station: Jameson Memorial"])

    def test_target_without_docking_reports_arrival(self):
        assists, statuses = self.make_assists("SC to Target", drop_type="$USS_Type_Ceremonial;")

        self.run_sc_assist(assists)

        self.assertEqual(statuses[-1], "Arrived at target")
        assists.dock.assert_not_called()


class TravelAssistTestCase(unittest.TestCase):
    def setUp(self):
        self.assists = Assists([])
        self.assists.jn = Mock()
        self.assists.fsd_assist = Mock()
        self.assists.sc_assist = Mock()
        self.assists.set_ap_status = Mock()
        self.assists.status = Mock()
        self.assists.ap_ckb = Mock()

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
        self.assists.status.get_cleaned_data.return_value = status("Some Station", 20)

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_not_called()
        self.assists.sc_assist.assert_called_once_with(None)

    def test_local_phase_does_not_start_without_a_status_destination(self):
        self.assists.jn.ship_state.return_value = {"target": None}
        self.assists.status.get_cleaned_data.return_value = status()

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_not_called()
        self.assists.sc_assist.assert_not_called()
        self.assists.ap_ckb.assert_called_once_with("log", "No local target found. Select a target and try again.")

    def test_stopped_travel_assist_does_not_start_local_phase(self):
        self.assists.jn.ship_state.return_value = {"target": "Alpha Centauri"}
        self.assists.fsd_assist.return_value = False
        self.assists.travel_assist_enabled = False

        self.assists.travel_assist(None)

        self.assists.sc_assist.assert_not_called()


if __name__ == "__main__":
    unittest.main()

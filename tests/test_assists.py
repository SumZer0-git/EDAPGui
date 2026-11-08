"""Tests for the end-of-route decision in the assists."""

import unittest
from unittest.mock import Mock, patch

from core.constants import FlagsSupercruise
from core.types import FsdAssistResult, ScTargetAlignReturn
from routines.assists import AssistsMixin


class Assists(AssistsMixin):
    def __init__(self, compass_readings):
        self.have_destination = Mock(side_effect=compass_readings)
        self.travel_assist_enabled = True


def status(name="", body=-1):
    return {"Destination_System": "", "Destination_Name": name, "Destination_Body": body}


def system_status(name, address):
    return {"Destination_System": address, "Destination_Name": name, "Destination_Body": 0}


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

    def test_expected_local_target_requires_a_name_match(self):
        assists = Assists([])

        self.assertTrue(assists.has_expected_in_system_target(status("Kent's Legacy", 20), "KENT'S LEGACY"))
        self.assertFalse(assists.has_expected_in_system_target(status("Ohm City", 20), "Kent's Legacy"))
        self.assertFalse(assists.has_expected_in_system_target(status("Kent's Legacy", 0), "Kent's Legacy"))
        self.assertTrue(assists.has_expected_in_system_target(status("ABC-123", 20), "My Carrier ABC-123"))

    def test_wait_for_expected_local_target_until_status_updates(self):
        assists = Assists([])
        assists.status = Mock()
        assists.status.get_cleaned_data.side_effect = [
            status("Wrong Station", 20),
            status("Kent's Legacy", 20),
        ]
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 1]),
            patch("routines.assists.sleep"),
        ):
            self.assertTrue(assists.wait_for_expected_in_system_target("Kent's Legacy", timeout=5))

    def test_wait_for_expected_local_target_times_out_on_mismatch(self):
        assists = Assists([])
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status("Wrong Station", 20)
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 5]),
            patch("routines.assists.sleep"),
        ):
            self.assertFalse(assists.wait_for_expected_in_system_target("Kent's Legacy", timeout=5))

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

        with (
            patch.object(assists, "wait_for_expected_in_system_target", return_value=False),
            patch("routines.assists.sleep"),
        ):
            self.assertFalse(assists.supercruise_to_station(None, "Some Station"))

        assists.have_destination.assert_not_called()
        assists.sc_assist.assert_not_called()

    def test_explicit_waypoint_does_not_fly_to_a_different_local_destination(self):
        assists = Assists([])
        assists.ap_ckb = Mock()
        assists.jn = Mock()
        assists.jn.ship_state.return_value = {"status": "in_supercruise"}
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status("Other Station", 20)
        assists.status.get_flag.return_value = False
        assists.set_ap_status = Mock()
        assists.sc_assist = Mock()
        assists.wait_for_expected_in_system_target = Mock(return_value=False)
        assists.sc_engage = Mock()

        with patch("routines.assists.sleep"):
            self.assertFalse(assists.supercruise_to_station(None, "Kent's Legacy"))

        assists.sc_engage.assert_not_called()
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
        assists.status.get_cleaned_data.return_value = status("Jameson Memorial", 20)
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
        self.assists.fsd_assist.return_value = FsdAssistResult.RouteComplete

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_called_once_with(None)
        self.assists.sc_assist.assert_not_called()

    def test_system_route_hands_off_to_local_target(self):
        self.assists.jn.ship_state.return_value = {"target": "Alpha Centauri"}
        self.assists.fsd_assist.return_value = FsdAssistResult.InSystemTarget

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
        self.assists.fsd_assist.return_value = FsdAssistResult.InSystemTarget
        self.assists.travel_assist_enabled = False

        self.assists.travel_assist(None)

        self.assists.sc_assist.assert_not_called()

    def test_system_target_from_status_runs_fsd_route_without_journal_target(self):
        # A re-plotted route with the same next system produces no new FSDTarget after NavRouteClear.
        self.assists.jn.ship_state.return_value = {"target": None, "system_address": 1, "location": "Sol"}
        self.assists.status.get_cleaned_data.return_value = system_status("Alpha Centauri", 2)
        self.assists.fsd_assist.return_value = FsdAssistResult.RouteComplete

        self.assists.travel_assist(None)

        self.assists.fsd_assist.assert_called_once_with(None)
        self.assists.ap_ckb.assert_not_called()


class JumpTargetTestCase(unittest.TestCase):
    def make_assists(self, ship, destination):
        assists = Assists([])
        assists.jn = Mock()
        assists.jn.ship_state.return_value = ship
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = destination
        return assists

    def test_journal_target_is_preferred(self):
        assists = self.make_assists({"target": "Arima"}, system_status("Alpha Centauri", 2))

        self.assertEqual(assists.jump_target(), "Arima")
        assists.status.get_cleaned_data.assert_not_called()

    def test_other_system_in_status_is_used_without_journal_target(self):
        assists = self.make_assists(
            {"target": None, "system_address": 1, "location": "Sol"}, system_status("Alpha Centauri", 2)
        )

        self.assertEqual(assists.jump_target(), "Alpha Centauri")

    def test_status_without_another_system_is_no_jump_target(self):
        cases = {
            "no destination": ({"target": None, "system_address": 1, "location": "Sol"}, status()),
            "current system": ({"target": None, "system_address": 1, "location": "Sol"}, system_status("Sol", 1)),
            "current system by name": (
                {"target": None, "system_address": None, "location": "Sol"},
                system_status("sol", 1),
            ),
            "local body": (
                {"target": None, "system_address": 1, "location": "Sol"},
                {"Destination_System": 1, "Destination_Name": "Abraham Lincoln", "Destination_Body": 12},
            ),
        }
        for name, (ship, destination) in cases.items():
            with self.subTest(name):
                self.assertIsNone(self.make_assists(ship, destination).jump_target())


class FsdAssistResultTestCase(unittest.TestCase):
    def make_assists(self):
        assists = Assists([])
        assists.ap_ckb = Mock()
        assists.config = {"AutomaticLogout": False}
        assists.jn = Mock()
        assists.jn.ship_state.return_value = {
            "target": False,
            "status": "in_space",
            "cur_star_system": "Arima",
            "location": "Sol",
            "dist_jumped": 0,
            "jumps_remains": 0,
            "fuel_percent": 100,
        }
        assists.keys = Mock()
        assists.set_ap_status = Mock()
        assists.status = Mock()
        assists.status.get_cleaned_data.return_value = status()
        assists.status.get_flag.return_value = False
        assists.nav_route = Mock()
        assists.nav_route.get_last_system.return_value = ""
        assists.total_dist_jumped = 0
        assists.update_overlay = Mock()
        assists.vce = Mock()
        return assists

    def test_fsd_route_without_local_target_reports_route_complete(self):
        assists = self.make_assists()

        with patch("routines.assists.sleep"):
            result = assists.fsd_assist(None)

        self.assertIs(result, FsdAssistResult.RouteComplete)

    def test_fsd_route_with_local_target_reports_target_ready(self):
        assists = self.make_assists()
        assists.status.get_cleaned_data.return_value = status("Kent's Legacy", 20)

        with patch("routines.assists.sleep"):
            result = assists.fsd_assist(None)

        self.assertIs(result, FsdAssistResult.InSystemTarget)

    def test_failed_fsd_jump_does_not_report_route_complete(self):
        assists = self.make_assists()
        assists.jn.ship_state.return_value["target"] = True
        assists.jump = Mock(return_value=False)
        assists.mnvr_to_target = Mock()

        with patch("routines.assists.sleep"):
            result = assists.fsd_assist(None)

        self.assertIs(result, FsdAssistResult.Failed)

    def test_fsd_route_jumps_to_status_target_without_journal_target(self):
        assists = self.make_assists()
        ship = assists.jn.ship_state.return_value
        ship.update({"target": None, "system_address": 1})
        assists.config["FuelThreasholdAbortAP"] = 10
        assists.status.get_cleaned_data.return_value = system_status("Arima", 2)

        def arrive(_scr_reg):
            ship["system_address"] = 2
            ship["location"] = "Arima"
            return True

        assists.jump = Mock(side_effect=arrive)
        assists.mnvr_to_target = Mock()
        assists.refuel = Mock(return_value=False)
        assists.position = Mock()
        assists.honk = Mock()

        with patch("routines.assists.sleep"):
            result = assists.fsd_assist(None)

        assists.jump.assert_called_once_with(None)
        self.assertIs(result, FsdAssistResult.RouteComplete)

    def test_jump_to_system_accepts_station_bookmark_with_expected_nav_route(self):
        assists = self.make_assists()
        assists.status.get_cleaned_data.return_value = status("Kent's Legacy", 20)
        assists.nav_route = Mock()
        assists.nav_route.get_last_system.return_value = "Arima"
        assists.jn.ship_state.return_value["status"] = "in_supercruise"
        assists.fsd_assist = Mock(return_value=FsdAssistResult.InSystemTarget)

        result = assists.jump_to_system(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.InSystemTarget)

    def test_jump_to_system_rejects_mismatched_nav_route_before_flying(self):
        assists = self.make_assists()
        assists.status.get_cleaned_data.return_value = status("Kent's Legacy", 20)
        assists.nav_route = Mock()
        assists.nav_route.get_last_system.return_value = "Wrong System"
        assists.fsd_assist = Mock()

        result = assists.jump_to_system(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.Failed)
        assists.fsd_assist.assert_not_called()

    def test_jump_to_system_rejects_route_that_did_not_reach_expected_system(self):
        assists = self.make_assists()
        assists.status.get_cleaned_data.return_value = status("Arima", 0)
        assists.nav_route = Mock()
        assists.nav_route.get_last_system.return_value = "Arima"
        assists.jn.ship_state.return_value["cur_star_system"] = "LHS 20"
        assists.jn.ship_state.return_value["status"] = "in_supercruise"
        assists.fsd_assist = Mock(return_value=FsdAssistResult.RouteComplete)
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 10]),
            patch("routines.assists.sleep"),
        ):
            result = assists.jump_to_system(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.Failed)
        assists.ap_ckb.assert_any_call("log", "Failed to reach Arima.")

    def make_waypoint_jump(self, destination=None):
        assists = self.make_assists()
        assists.jn.ship_state.return_value.update(
            target="Arima", cur_star_system="LHS 20", status="in_supercruise", system_address=1
        )
        assists.nav_route.get_last_system.return_value = "Arima"
        assists.nav_route.get_next_system.return_value = ("Arima", 2)
        assists.status.get_cleaned_data.return_value = destination or status("Ohm City", 20)
        assists.status.wait_for_flag_on.return_value = True
        assists.mnvr_to_target = Mock()
        assists.jump = Mock(return_value=False)
        return assists

    def test_waypoint_stale_station_target_never_aligns_or_jumps(self):
        assists = self.make_waypoint_jump()
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 5]),
            patch("routines.assists.sleep"),
        ):
            result = assists.jump_to_system(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.Failed)
        assists.keys.send.assert_any_call("TargetNextRouteSystem")
        assists.keys.send.assert_any_call("SetSpeedZero")
        assists.mnvr_to_target.assert_not_called()
        assists.jump.assert_not_called()
        assists.ap_ckb.assert_called_once()

    def test_waypoint_waits_for_status_before_alignment(self):
        assists = self.make_waypoint_jump()
        confirmed = dict(status("ARIMA", 0), Destination_System=2)
        assists.status.get_cleaned_data.side_effect = [
            status("Ohm City", 20),
            status("Ohm City", 20),
            confirmed,
            confirmed,
        ]
        events = []
        assists.keys.send.side_effect = lambda name: events.append(name)
        assists.mnvr_to_target.side_effect = lambda _: events.append("align")
        assists.jump.side_effect = lambda _: events.append("jump") or False
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 1]),
            patch("routines.assists.sleep") as sleep,
        ):
            result = assists.fsd_assist(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.Failed)  # Deliberately stop at the mocked jump.
        self.assertEqual(events[:3], ["TargetNextRouteSystem", "align", "jump"])
        sleep.assert_any_call(0.25)
        assists.status.wait_for_flag_on.assert_called_once_with(FlagsSupercruise, 5.0)

    def test_waypoint_checks_next_hop_not_final_destination(self):
        assists = self.make_waypoint_jump()
        assists.nav_route.get_next_system.return_value = ("Intermediate", 3)
        assists.status.get_cleaned_data.return_value = dict(status("Intermediate", 0), Destination_System=3)
        with patch("routines.assists.sleep"):
            assists.fsd_assist(None, expected_system="Arima")

        assists.mnvr_to_target.assert_called_once_with(None)
        assists.jump.assert_called_once_with(None)

    def test_waypoint_rejects_wrong_address_name_or_local_body(self):
        for name, body, address in (("Arima", 0, 99), ("Wrong", 0, 2), ("Arima", 20, 2)):
            with self.subTest(name=name, body=body, address=address):
                assists = self.make_waypoint_jump(dict(status(name, body), Destination_System=address))
                with (
                    patch("routines.assists.monotonic", side_effect=[0, 0, 5]),
                    patch("routines.assists.sleep"),
                ):
                    result = assists.fsd_assist(None, expected_system="Arima")
                self.assertIs(result, FsdAssistResult.Failed)
                assists.mnvr_to_target.assert_not_called()
                assists.jump.assert_not_called()

    def test_waypoint_rejects_failed_supercruise_or_missing_next_hop(self):
        for failure in ("supercruise", "next_hop", "route_changed"):
            with self.subTest(failure=failure):
                assists = self.make_waypoint_jump()
                if failure == "supercruise":
                    assists.status.wait_for_flag_on.return_value = False
                elif failure == "next_hop":
                    assists.nav_route.get_next_system.return_value = None
                else:
                    assists.nav_route.get_last_system.return_value = "Wrong"
                with patch("routines.assists.sleep"):
                    result = assists.fsd_assist(None, expected_system="Arima")
                self.assertIs(result, FsdAssistResult.Failed)
                assists.keys.send.assert_any_call("SetSpeedZero")
                assists.mnvr_to_target.assert_not_called()
                assists.jump.assert_not_called()

    def test_waypoint_confirms_target_even_without_journal_target(self):
        assists = self.make_waypoint_jump()
        assists.jn.ship_state.return_value["target"] = None
        with (
            patch("routines.assists.monotonic", side_effect=[0, 0, 5]),
            patch("routines.assists.sleep"),
        ):
            result = assists.fsd_assist(None, expected_system="Arima")
        self.assertIs(result, FsdAssistResult.Failed)
        assists.keys.send.assert_any_call("TargetNextRouteSystem")
        assists.mnvr_to_target.assert_not_called()

    def test_waypoint_selects_only_after_undocking_and_supercruise(self):
        assists = self.make_waypoint_jump()
        assists.jn.ship_state.return_value["status"] = "in_space"
        assists.status.get_flag.return_value = True
        events = []

        def undock():
            events.append("undock")
            assists.status.get_flag.return_value = False

        def enter_supercruise():
            events.append("supercruise")
            assists.jn.ship_state.return_value["status"] = "in_supercruise"

        def send(key):
            events.append(key)
            if key == "TargetNextRouteSystem":
                assists.status.get_cleaned_data.return_value = dict(status("Arima", 0), Destination_System=2)

        assists.waypoint_undock_seq = Mock(side_effect=undock)
        assists.sc_engage = Mock(side_effect=enter_supercruise)
        assists.keys.send.side_effect = send
        assists.mnvr_to_target.side_effect = lambda _: events.append("align")
        with patch("routines.assists.sleep"):
            assists.jump_to_system(None, expected_system="Arima")

        self.assertEqual(events[:4], ["undock", "supercruise", "TargetNextRouteSystem", "align"])

    def test_waypoint_reconfirms_each_hop_and_finishes_at_final_system(self):
        assists = self.make_waypoint_jump()
        ship = assists.jn.ship_state.return_value
        assists.config["FuelThreasholdAbortAP"] = 10
        assists.refuel = Mock()
        assists.position = Mock()
        assists.honk = Mock()
        assists.nav_route.get_next_system.side_effect = lambda name, address: (
            ("Intermediate", 3) if name == "LHS 20" else ("Arima", 2)
        )
        selected = []

        def send(key):
            if key == "TargetNextRouteSystem":
                name, address = assists.nav_route.get_next_system(ship["cur_star_system"], ship["system_address"])
                selected.append(name)
                assists.status.get_cleaned_data.return_value = dict(status(name, 0), Destination_System=address)

        def jump(_):
            current = assists.status.get_cleaned_data.return_value
            ship.update(cur_star_system=current["Destination_Name"], system_address=current["Destination_System"])
            if ship["cur_star_system"] == "Arima":
                ship["target"] = None
            return True

        assists.keys.send.side_effect = send
        assists.jump.side_effect = jump
        with patch("routines.assists.sleep"), patch("routines.assists.threading.Thread"):
            result = assists.jump_to_system(None, expected_system="Arima")

        self.assertIs(result, FsdAssistResult.RouteComplete)
        self.assertEqual(selected, ["Intermediate", "Arima"])
        self.assertEqual(assists.mnvr_to_target.call_count, 2)
        self.assertEqual(assists.jump.call_count, 2)

    def test_waypoint_route_change_during_confirmation_stops_before_alignment(self):
        assists = self.make_waypoint_jump()
        assists.nav_route.get_last_system.side_effect = ["Arima", "Wrong"]
        with patch("routines.assists.sleep"):
            result = assists.fsd_assist(None, expected_system="Arima")
        self.assertIs(result, FsdAssistResult.Failed)
        assists.keys.send.assert_any_call("SetSpeedZero")
        assists.mnvr_to_target.assert_not_called()
        assists.jump.assert_not_called()

    def test_travel_assist_only_hands_off_to_supercruise_for_local_target(self):
        for result in FsdAssistResult:
            with self.subTest(result=result):
                assists = self.make_assists()
                assists.jn.ship_state.return_value["target"] = True
                assists.fsd_assist = Mock(return_value=result)
                assists.sc_assist = Mock()
                assists.travel_assist(None)

                if result is FsdAssistResult.InSystemTarget:
                    assists.sc_assist.assert_called_once_with(None)
                else:
                    assists.sc_assist.assert_not_called()


if __name__ == "__main__":
    unittest.main()

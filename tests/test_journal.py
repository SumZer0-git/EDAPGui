"""Tests for the journal parser (event handling and module checks) without a journal file."""

import contextlib
import io
import threading
import time
import unittest
from collections import deque
from unittest.mock import patch

from game.journal import (
    EDJournal,
    check_adv_docking_computer,
    check_fuel_scoop,
    check_sco_fsd,
    check_std_docking_computer,
    get_ship_fullname,
    get_ship_size,
)


def new_journal() -> EDJournal:
    """A journal object with the initial ship state, without opening a journal file."""
    journal = EDJournal.__new__(EDJournal)
    journal._read_lock = threading.RLock()
    journal._market_sequence = 0
    journal._market_transactions = deque(maxlen=128)
    journal.ship = {
        "time": 0,
        "odyssey": True,
        "status": "in_space",
        "type": None,
        "location": None,
        "star_class": None,
        "target": None,
        "fighter_destroyed": False,
        "shieldsup": True,
        "under_attack": None,
        "interdicted": False,
        "no_dock_reason": None,
        "mission_completed": 0,
        "mission_redirected": 0,
        "body": None,
        "dist_jumped": 0,
        "jumps_remains": 0,
        "fuel_capacity": None,
        "fuel_level": None,
        "fuel_percent": None,
        "is_scooping": False,
        "cur_star_system": "",
        "system_address": None,
        "cur_station": "",
        "cur_station_type": "",
        "cargo_capacity": None,
        "ship_size": None,
        "has_fuel_scoop": None,
        "SupercruiseDestinationDrop_type": None,
        "has_adv_dock_comp": None,
        "has_std_dock_comp": None,
        "has_sco_fsd": None,
        "StationServices": None,
    }
    return journal


MODULES = [
    {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size5_class5"},
    {"Slot": "Slot01", "Item": "int_fuelscoop_size4_class5"},
    {"Slot": "Slot02", "Item": "int_dockingcomputer_advanced"},
]


class ModuleChecksTestCase(unittest.TestCase):
    def test_journal_rollover_updates_filename_and_does_not_replay_old_events(self):
        journal = new_journal()
        journal.current_log = "old.log"
        journal.last_mod_time = None
        journal.log_file = io.StringIO()
        contents = '{"event":"MarketBuy","MarketID":42,"Type":"polymers","Count":2}\n'
        with (
            patch.object(journal, "get_latest_log", return_value="new.log"),
            patch.object(journal, "get_file_modified_time", return_value=1),
            patch("builtins.open", return_value=io.StringIO(contents)) as open_file,
        ):
            cursor = journal.market_transaction_cursor()
            self.assertEqual(cursor, 1)
            self.assertEqual(journal.market_transactions_since(cursor), [])
            open_file.assert_called_once_with("new.log", encoding="utf-8")

    def test_journal_keeps_pre_read_timestamp_so_late_appends_are_not_skipped(self):
        journal = new_journal()
        journal.current_log = "test.log"
        journal.last_mod_time = None
        journal.log_file = io.StringIO()
        with (
            patch.object(journal, "get_latest_log", return_value="test.log"),
            patch.object(journal, "get_file_modified_time", side_effect=[1, 2]),
        ):
            journal.market_transaction_cursor()
            self.assertEqual(journal.last_mod_time, 1)
            journal.market_transaction_cursor()
            self.assertEqual(journal.last_mod_time, 2)

    def test_concurrent_ship_state_reads_are_serialized(self):
        journal = EDJournal.__new__(EDJournal)
        journal._read_lock = threading.RLock()
        journal.ship = {}
        active = []
        overlaps = []

        def read_new_lines():
            active.append(1)
            if len(active) > 1:
                overlaps.append(len(active))
            time.sleep(0.02)
            active.pop()
            return journal.ship

        journal._read_new_lines = read_new_lines
        threads = [threading.Thread(target=journal.ship_state) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(overlaps, [])

    def test_unknown_modules_default_to_fitted(self):
        for check in (check_fuel_scoop, check_adv_docking_computer, check_std_docking_computer, check_sco_fsd):
            self.assertTrue(check(None), check.__name__)

    def test_fitted_modules_are_found(self):
        self.assertTrue(check_fuel_scoop(MODULES))
        self.assertTrue(check_adv_docking_computer(MODULES))
        self.assertTrue(check_sco_fsd(MODULES))

    def test_missing_modules_are_detected(self):
        self.assertFalse(check_std_docking_computer(MODULES))
        self.assertFalse(check_fuel_scoop([]))
        self.assertFalse(check_sco_fsd([{"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_size5_class5"}]))


class ShipLookupTestCase(unittest.TestCase):
    def test_known_ship(self):
        self.assertEqual(get_ship_size("diamondbackxl"), "S")
        self.assertEqual(get_ship_size("DiamondbackXL"), "S")
        self.assertEqual(get_ship_fullname("diamondbackxl"), "Diamondback Explorer")

    def test_unknown_ship(self):
        self.assertEqual(get_ship_size("nosuchship"), "")
        self.assertEqual(get_ship_fullname("nosuchship"), "")


class ParseLineTestCase(unittest.TestCase):
    def setUp(self):
        self.journal = new_journal()
        self.ship = self.journal.ship

    def test_market_transactions_preserve_order_and_are_not_consumed(self):
        buy = {"event": "MarketBuy", "MarketID": 42, "Type": "polymers", "Count": 2}
        sell = {**buy, "event": "MarketSell", "Count": 1}
        with patch.object(self.journal, "_read_new_lines"):
            self.journal.parse_line(buy)
            cursor = self.journal.market_transaction_cursor()
            self.journal.parse_line(sell)
            self.assertEqual(self.journal.market_transactions_since(cursor), [sell])
            self.assertEqual(self.journal.market_transactions_since(cursor), [sell])
            self.assertEqual(self.journal.market_transactions_since(0), [buy, sell])

    def test_market_transactions_are_bounded_and_survive_journal_rollover(self):
        for count in range(140):
            self.journal.parse_line({"event": "MarketBuy", "Count": count})
        self.journal.parse_line({"event": "Fileheader"})
        with patch.object(self.journal, "_read_new_lines"):
            self.assertEqual(self.journal.market_transaction_cursor(), 140)
            events = self.journal.market_transactions_since(0)
        self.assertEqual(len(events), 128)
        self.assertEqual(events[-1]["Count"], 139)

    def test_docked(self):
        self.journal.parse_line(
            {
                "event": "Docked",
                "StarSystem": "Sol",
                "StationName": "Abraham Lincoln",
                "StationType": "Orbis",
                "StationServices": ["dock", "refuel"],
            }
        )

        self.assertEqual(self.ship["status"], "in_station")
        self.assertEqual(self.ship["cur_star_system"], "Sol")
        self.assertEqual(self.ship["cur_station"], "Abraham Lincoln")
        self.assertEqual(self.ship["StationServices"], ["dock", "refuel"])

    def test_location_in_open_space_has_no_station_and_does_not_log_an_error(self):
        with patch("game.journal.logger") as journal_logger:
            self.journal.parse_line(
                {"event": "Location", "StarSystem": "Ross 584", "SystemAddress": 123, "Docked": False}
            )

        journal_logger.error.assert_not_called()
        self.assertEqual(self.ship["cur_star_system"], "Ross 584")
        self.assertEqual(self.ship["system_address"], 123)
        self.assertEqual(self.ship["cur_station"], "")
        self.assertEqual(self.ship["cur_station_type"], "")
        self.assertNotEqual(self.ship["status"], "in_station")

    def test_location_docked_sets_station(self):
        self.journal.parse_line(
            {
                "event": "Location",
                "StarSystem": "Sol",
                "StationName": "Abraham Lincoln",
                "StationType": "Orbis",
                "Docked": True,
            }
        )

        self.assertEqual(self.ship["cur_station"], "Abraham Lincoln")
        self.assertEqual(self.ship["status"], "in_station")

    def test_location_docked_restores_services_on_game_restart(self):
        self.journal.parse_line(
            {
                "event": "Location",
                "StarSystem": "LHS 20",
                "StationName": "Ohm City",
                "StationType": "Coriolis",
                "Docked": True,
                "StationServices": ["dock", "commodities"],
            }
        )
        self.assertEqual(self.ship["StationServices"], ["dock", "commodities"])

    def test_location_without_services_does_not_keep_previous_station_services(self):
        self.ship["StationServices"] = ["commodities"]
        self.journal.parse_line({"event": "Location", "StarSystem": "Sol", "Docked": False})
        self.assertIsNone(self.ship["StationServices"])

    def test_docking_denied(self):
        self.journal.parse_line({"event": "DockingDenied", "Reason": "NoSpace"})

        self.assertEqual(self.ship["status"], "dockingdenied")
        self.assertEqual(self.ship["no_dock_reason"], "NoSpace")

    def test_hyperspace_jump_sequence(self):
        self.journal.parse_line({"event": "FSDTarget", "Name": "Alpha Centauri", "RemainingJumpsInRoute": 2})
        self.assertEqual(self.ship["target"], "Alpha Centauri")
        self.assertEqual(self.ship["jumps_remains"], 2)

        self.journal.parse_line({"event": "StartJump", "JumpType": "Hyperspace", "StarClass": "K"})
        self.assertEqual(self.ship["status"], "starting_hyperspace")
        self.assertEqual(self.ship["star_class"], "K")

        self.journal.parse_line(
            {"event": "FSDJump", "StarSystem": "Alpha Centauri", "SystemAddress": 456, "JumpDist": 4.38}
        )
        self.assertEqual(self.ship["status"], "in_supercruise")
        self.assertEqual(self.ship["location"], "Alpha Centauri")
        self.assertEqual(self.ship["dist_jumped"], 4.38)
        self.assertEqual(self.ship["system_address"], 456)
        self.assertIsNone(self.ship["target"])  # arrived at the target

    def test_fsd_target_in_current_system_clears_target(self):
        self.ship["location"] = "Sol"

        self.journal.parse_line({"event": "FSDTarget", "Name": "Sol"})

        self.assertIsNone(self.ship["target"])
        self.assertEqual(self.ship["jumps_remains"], 0)

    def test_nav_route_clear(self):
        self.ship["target"] = "Somewhere"
        self.ship["jumps_remains"] = 3

        self.journal.parse_line({"event": "NavRouteClear"})

        self.assertIsNone(self.ship["target"])
        self.assertEqual(self.ship["jumps_remains"], 0)

    def test_supercruise_exit(self):
        self.ship["status"] = "in_supercruise"

        self.journal.parse_line({"event": "SupercruiseExit", "Body": "Sol A"})

        self.assertEqual(self.ship["status"], "in_space")
        self.assertEqual(self.ship["body"], "Sol A")

    def test_undocking_sequence(self):
        self.ship["status"] = "in_station"

        self.journal.parse_line({"event": "Undocked"})
        self.assertEqual(self.ship["status"], "starting_undocking")
        self.journal.parse_line({"event": "Music", "MusicTrack": "DockingComputer"})
        self.assertEqual(self.ship["status"], "in_undocking")
        self.journal.parse_line({"event": "Music", "MusicTrack": "NoTrack"})
        self.assertEqual(self.ship["status"], "in_space")

    def test_docking_sequence(self):
        self.journal.parse_line({"event": "DockingRequested"})
        self.assertEqual(self.ship["status"], "starting_docking")
        self.journal.parse_line({"event": "DockingGranted"})
        self.assertEqual(self.ship["status"], "dockinggranted")

        self.ship["status"] = "starting_docking"
        self.journal.parse_line({"event": "Music", "MusicTrack": "DockingComputer"})
        self.assertEqual(self.ship["status"], "in_docking")

    def test_music_track_is_ignored_in_other_states(self):
        self.journal.parse_line({"event": "Music", "MusicTrack": "NoTrack"})

        self.assertEqual(self.ship["status"], "in_space")

    def test_loadout(self):
        self.journal.parse_line(
            {
                "event": "Loadout",
                "Ship": "diamondbackxl",
                "CargoCapacity": 20,
                "Modules": MODULES,
                "FuelCapacity": {"Main": 32.0, "Reserve": 0.6},
            }
        )

        self.assertEqual(self.ship["type"], "diamondbackxl")
        self.assertEqual(self.ship["ship_size"], "S")
        self.assertEqual(self.ship["cargo_capacity"], 20)
        self.assertTrue(self.ship["has_fuel_scoop"])
        self.assertTrue(self.ship["has_adv_dock_comp"])
        self.assertFalse(self.ship["has_std_dock_comp"])
        self.assertTrue(self.ship["has_sco_fsd"])
        self.assertEqual(self.ship["fuel_capacity"], 32.0)

    def test_fuel_scoop_updates_percent_and_scooping(self):
        self.ship["fuel_capacity"] = 32.0

        self.journal.parse_line({"event": "FuelScoop", "Scooped": 1.0, "Total": 16.0})

        self.assertEqual(self.ship["fuel_level"], 16.0)
        self.assertEqual(self.ship["fuel_percent"], 50)
        self.assertTrue(self.ship["is_scooping"])

        self.journal.parse_line({"event": "FuelScoop", "Scooped": 16.0, "Total": 32.0})
        self.assertEqual(self.ship["fuel_percent"], 100)
        self.assertFalse(self.ship["is_scooping"])

    def test_shield_state_and_combat_events(self):
        self.journal.parse_line({"event": "ShieldState", "ShieldsUp": False})
        self.assertFalse(self.ship["shieldsup"])
        self.journal.parse_line({"event": "ShieldState", "ShieldsUp": True})
        self.assertTrue(self.ship["shieldsup"])

        self.journal.parse_line({"event": "UnderAttack"})
        self.journal.parse_line({"event": "FighterDestroyed"})
        self.journal.parse_line({"event": "Interdicted"})
        self.assertTrue(self.ship["under_attack"])
        self.assertTrue(self.ship["fighter_destroyed"])
        self.assertTrue(self.ship["interdicted"])

    def test_mission_counters(self):
        self.journal.parse_line({"event": "MissionCompleted"})
        self.journal.parse_line({"event": "MissionCompleted"})
        self.journal.parse_line({"event": "MissionRedirected"})

        self.assertEqual(self.ship["mission_completed"], 2)
        self.assertEqual(self.ship["mission_redirected"], 1)

    def test_reset_items(self):
        self.ship["under_attack"] = True
        self.ship["fighter_destroyed"] = True

        self.journal.reset_items()

        self.assertFalse(self.ship["under_attack"])
        self.assertFalse(self.ship["fighter_destroyed"])

    def test_incomplete_event_does_not_raise(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.journal.parse_line({"event": "FSDJump"})  # keys missing
            self.journal.parse_line({})  # no event at all


if __name__ == "__main__":
    unittest.main()

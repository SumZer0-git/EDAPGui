"""Processes the Elite Dangerous journal files.

Opens the latest Journal* file and keeps the ship state up to date; new lines are loaded
whenever the state is accessed. Leveraged from https://github.com/skai2/EDAutopilot."""

from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime
from json import JSONDecodeError, loads
from os import listdir
from os.path import getmtime, isfile, join
from time import sleep

from core.constants import ship_name_map, ship_size_map
from core.logger import logger
from game.known_paths import FOLDERID, UserHandle, get_path

# TODO: thinking self.ship()[name] uses the same names as in the journal, so can lookup same construct


def get_ship_size(ship: str) -> str:
    """Gets the ship size from the journal ship name.
    @ship:  The ship name from the journal (i.e. 'diamondbackxl').
    @return: The ship size ('S', 'M', 'L' or '' if ship not found or size not valid).
    """
    if ship.lower() in ship_size_map:
        return ship_size_map[ship.lower()]
    else:
        return ""


def get_ship_fullname(ship: str) -> str:
    """Gets the ship full name from the journal ship name.
    @ship:  The ship name from the journal (i.e. 'diamondbackxl').
    @return: The ship full name ('Diamondback Explorer' or '' if ship not found).
    """
    if ship.lower() in ship_name_map:
        return ship_name_map[ship.lower()]
    else:
        return ""


def check_fuel_scoop(modules: list[dict[str, any]] | None) -> bool:
    """Gets whether the ship has a fuel scoop."""
    # Default to fuel scoop fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "fuelscoop" in module["Item"].lower():
            return True

    return False


def check_adv_docking_computer(modules: list[dict[str, any]] | None) -> bool:
    """Gets whether the ship has an advanced docking computer.
    Advanced docking computer will dock and undock automatically.
    """
    # Default to docking computer fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "dockingcomputer_advanced" in module["Item"].lower():
            return True

    return False


def check_std_docking_computer(modules: list[dict[str, any]] | None) -> bool:
    """Gets whether the ship has a standard docking computer.
    Standard docking computer will dock automatically, but not undock.
    """
    # Default to docking computer fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "dockingcomputer_standard" in module["Item"].lower():
            return True

    return False


def check_sco_fsd(modules: list[dict[str, any]] | None) -> bool:
    """Gets whether the ship has an FSD with SCO."""
    # Default to SCO fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if module["Slot"] == "FrameShiftDrive":
            if "overcharge" in module["Item"].lower():
                # print("FrameShiftDrive has SCO!")
                return True

    # print("FrameShiftDrive has no SCO")
    return False


class EDJournal:
    _statistics_observer = None

    def __init__(self, cb):
        self.ap_ckb = cb
        self._read_lock = threading.RLock()
        self._market_sequence = 0
        self._market_transactions = deque(maxlen=128)
        self.last_mod_time = None
        self.log_file = None
        self.current_log = self.get_latest_log()
        self.open_journal(self.current_log)

        self.ship = {
            "language": None,
            "language_pending": self.current_log is not None,
            "time": (datetime.now() - datetime.fromtimestamp(getmtime(self.current_log))).seconds
            if self.current_log
            else 0,
            "odyssey": True,
            "status": "in_space",
            "type": None,
            "commander_id": None,
            "ship_id": None,
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
            "discovery_scans": 0,
            "body": None,
            "dist_jumped": 0,
            "jumps_remains": 0,
            "system_address": None,
            "fuel_capacity": None,
            "fuel_level": None,
            "fuel_percent": None,
            "is_scooping": False,
            "cur_star_system": "",
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
        self.ship_state()  # load up from file
        self.reset_items()

    def get_file_modified_time(self) -> float:
        return os.path.getmtime(self.current_log)

    # these items do not have respective log entries to clear them.  After initial reading of log file, clear these items
    # also the App will need to reset these to False after detecting they were True
    def reset_items(self):
        self.ship["under_attack"] = False
        self.ship["fighter_destroyed"] = False

    def get_latest_log(self, path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if not path_logs:
            path_logs = get_path(FOLDERID.SavedGames, UserHandle.current) + r"\Frontier Developments\Elite Dangerous"
        if not os.path.isdir(path_logs):
            return None
        list_of_logs = [
            join(path_logs, f) for f in listdir(path_logs) if isfile(join(path_logs, f)) and f.startswith("Journal.")
        ]
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log

    def open_journal(self, log_name):
        # if journal file is open then close it
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None

        if log_name is None:
            logger.warning("No game journal is available yet.")
            return

        logger.info("Opening new Journal: " + log_name)

        # open the latest journal
        self.log_file = open(log_name, encoding="utf-8")
        self.current_log = log_name
        self.last_mod_time = None
        if hasattr(self, "ship"):
            self.ship["language"] = None
            self.ship["language_pending"] = True

    def parse_line(self, log):
        # parse data
        try:
            # parse ship status
            log_event = log["event"]
            self.ship["language_pending"] = False

            if log_event in ("MarketBuy", "MarketSell"):
                self._market_sequence += 1
                self._market_transactions.append((self._market_sequence, dict(log)))

            elif log_event.casefold() == "fileheader":
                # self.ship['odyssey'] = log['Odyssey']
                self.ship["odyssey"] = True  # hardset to true for ED 4.0 since menus now same for Horizon
                language = log.get("language")
                if language is not None and (not isinstance(language, str) or not language.strip()):
                    logger.warning("Journal header has an invalid language: %r", language)
                    language = None
                self.ship["language"] = language

            elif log_event == "ShieldState":
                if log["ShieldsUp"]:
                    self.ship["shieldsup"] = True
                else:
                    self.ship["shieldsup"] = False

            elif log_event == "UnderAttack":
                self.ship["under_attack"] = True

            elif log_event == "FighterDestroyed":
                self.ship["fighter_destroyed"] = True

            elif log_event == "FSSDiscoveryScan":
                self.ship["discovery_scans"] += 1

            elif log_event == "MissionCompleted":
                self.ship["mission_completed"] = self.ship["mission_completed"] + 1

            elif log_event == "MissionRedirected":
                self.ship["mission_redirected"] = self.ship["mission_redirected"] + 1

            elif log_event == "StartJump":
                self.ship["status"] = str("starting_" + log["JumpType"]).lower()
                self.ship["SupercruiseDestinationDrop_type"] = None
                if log["JumpType"] == "Hyperspace":
                    self.ship["star_class"] = log["StarClass"]

            elif log_event == "SupercruiseEntry" or log_event == "FSDJump":
                self.ship["status"] = "in_supercruise"

            elif log_event == "DockingGranted":
                self.ship["status"] = "dockinggranted"

            elif log_event == "DockingDenied":
                self.ship["status"] = "dockingdenied"
                self.ship["no_dock_reason"] = log["Reason"]

            elif log_event == "SupercruiseExit":
                self.ship["status"] = "in_space"
                self.ship["body"] = log["Body"]

            elif log_event == "SupercruiseDestinationDrop":
                self.ship["SupercruiseDestinationDrop_type"] = log["Type"]

            elif log_event == "DockingCancelled":
                self.ship["status"] = "in_space"

            elif log_event == "Undocked":
                self.ship["status"] = "starting_undocking"
                # self.ship['status'] = 'in_space'

            elif log_event == "DockingRequested":
                self.ship["status"] = "starting_docking"

            elif log_event == "Music" and log["MusicTrack"] == "DockingComputer":
                if self.ship["status"] == "starting_undocking":
                    self.ship["status"] = "in_undocking"
                elif self.ship["status"] == "starting_docking":
                    self.ship["status"] = "in_docking"

            elif log_event == "Music" and log["MusicTrack"] == "NoTrack" and self.ship["status"] == "in_undocking":
                self.ship["status"] = "in_space"

                # for unodck from outpost
            elif log_event == "Music" and log["MusicTrack"] == "Exploration" and self.ship["status"] == "in_undocking":
                self.ship["status"] = "in_space"

            elif log_event == "Docked":
                # {"timestamp": "2024-09-29T00:47:08Z", "event": "Docked", "StationName": "Filipchenko City",
                #  "StationType": "Coriolis", "Taxi": false, "Multicrew": false, "StarSystem": "G 139-50",
                #  "SystemAddress": 13864557225401, "MarketID": 3229027584,
                #  "StationFaction": {"Name": "Pixel Bandits Security Force"},
                #  "StationGovernment": "$government_Democracy;", "StationGovernment_Localised": "Democracy",
                #  "StationServices": ["dock", "autodock", "blackmarket", "commodities", "contacts", "exploration",
                #                      "missions", "outfitting", "crewlounge", "rearm", "refuel", "repair", "shipyard",
                #                      "tuning", "engineer", "missionsgenerated", "flightcontroller", "stationoperations",
                #                      "powerplay", "searchrescue", "materialtrader", "stationMenu", "shop", "livery",
                #                      "socialspace", "bartender", "vistagenomics", "pioneersupplies", "apexinterstellar",
                #                      "frontlinesolutions"], "StationEconomy": "$economy_HighTech;",
                #  "StationEconomy_Localised": "High Tech", "StationEconomies": [
                #     {"Name": "$economy_HighTech;", "Name_Localised": "High Tech", "Proportion": 0.800000},
                #     {"Name": "$economy_Refinery;", "Name_Localised": "Refinery", "Proportion": 0.200000}],
                #  "DistFromStarLS": 6.950547, "LandingPads": {"Small": 6, "Medium": 12, "Large": 7}}
                self.ship["status"] = "in_station"
                self.ship["location"] = log["StarSystem"]
                self.ship["cur_star_system"] = log["StarSystem"]
                self.ship["system_address"] = log.get("SystemAddress")
                self.ship["cur_station"] = log["StationName"]
                self.ship["cur_station_type"] = log["StationType"]
                self.ship["StationServices"] = log["StationServices"]

                # parse location
            elif log_event == "Location":
                self.ship["location"] = log["StarSystem"]
                self.ship["cur_star_system"] = log["StarSystem"]
                self.ship["system_address"] = log.get("SystemAddress")
                # StationName/StationType are only written when the commander is at a station
                self.ship["cur_station"] = log.get("StationName", "")
                self.ship["cur_station_type"] = log.get("StationType", "")
                self.ship["StationServices"] = log.get("StationServices") if log.get("Docked") else None
                if log.get("Docked"):
                    self.ship["status"] = "in_station"

            elif log_event == "Interdicted":
                self.ship["interdicted"] = True

            # parse ship type
            elif log_event == "Commander":
                if log.get("FID") != self.ship.get("commander_id"):
                    self.ship["ship_id"] = None
                self.ship["commander_id"] = log.get("FID")

            elif log_event == "LoadGame":
                self.ship["commander_id"] = log.get("FID")
                self.ship["ship_id"] = log.get("ShipID")
                self.ship["type"] = log["Ship"].lower()
                self.ship["ship_size"] = get_ship_size(log["Ship"])

            # Parse Loadout
            # When written: at startup, when loading from main menu, or when switching ships,
            # or after changing the ship in Outfitting, or when docking SRV back in mothership
            elif log_event == "Loadout":
                self.ship["ship_id"] = log.get("ShipID")
                self.ship["type"] = log["Ship"].lower()
                self.ship["ship_size"] = get_ship_size(log["Ship"])
                self.ship["cargo_capacity"] = log["CargoCapacity"]
                self.ship["has_fuel_scoop"] = check_fuel_scoop(log["Modules"])
                self.ship["has_adv_dock_comp"] = check_adv_docking_computer(log["Modules"])
                self.ship["has_std_dock_comp"] = check_std_docking_computer(log["Modules"])
                self.ship["has_sco_fsd"] = check_sco_fsd(log["Modules"])

            # parse fuel
            if "FuelLevel" in log and self.ship["type"] != "TestBuggy":
                self.ship["fuel_level"] = log["FuelLevel"]
            if "FuelCapacity" in log and self.ship["type"] != "TestBuggy":
                try:
                    self.ship["fuel_capacity"] = log["FuelCapacity"]["Main"]
                except Exception:
                    self.ship["fuel_capacity"] = log["FuelCapacity"]
            if log_event == "FuelScoop" and "Total" in log:
                self.ship["fuel_level"] = log["Total"]
            if self.ship["fuel_level"] and self.ship["fuel_capacity"]:
                self.ship["fuel_percent"] = round((self.ship["fuel_level"] / self.ship["fuel_capacity"]) * 100)
            else:
                self.ship["fuel_percent"] = 10

            # parse scoop
            #
            if log_event == "FuelScoop" and self.ship["time"] < 10 and self.ship["fuel_percent"] < 100:
                self.ship["is_scooping"] = True
            else:
                self.ship["is_scooping"] = False

            if log_event == "FSDJump":
                self.ship["location"] = log["StarSystem"]
                self.ship["cur_star_system"] = log["StarSystem"]
                self.ship["system_address"] = log.get("SystemAddress")
            # TODO                if 'StarClass' in log:
            # TODO                    self.ship['star_class'] = log['StarClass']

            # parse target
            if log_event == "FSDTarget":
                if log["Name"] == self.ship["location"]:
                    self.ship["target"] = None
                    self.ship["jumps_remains"] = 0
                else:
                    self.ship["target"] = log["Name"]
                    try:
                        self.ship["jumps_remains"] = log["RemainingJumpsInRoute"]
                    except Exception:
                        pass
                        #
                        #    'Log did not have jumps remaining. This happens most if you have less than .' +
                        #    '3 jumps remaining. Jumps remaining will be inaccurate for this jump.')

            elif log_event == "FSDJump":
                if self.ship["location"] == self.ship["target"]:
                    self.ship["target"] = None
                self.ship["dist_jumped"] = log["JumpDist"]

            # parse nav route clear
            elif log_event == "NavRouteClear":
                self.ship["target"] = None
                self.ship["jumps_remains"] = 0

            elif log_event == "CarrierJump":
                self.ship["location"] = log["StarSystem"]
                self.ship["cur_star_system"] = log["StarSystem"]
                self.ship["system_address"] = log.get("SystemAddress")
                self.ship["cur_station"] = log["StationName"]
                self.ship["cur_station_type"] = log["StationType"]

        # exceptions
        except Exception as e:
            logger.error(f"Error while reading journal: {e}")
            return

        if self._statistics_observer is not None:
            self._statistics_observer(log, self.ship.copy())

    def set_statistics_observer(self, observer):
        """Attach after draining startup records, so historical jumps are never counted."""
        with self._read_lock:
            self._read_new_lines()
            self._statistics_observer = observer

    def ship_state(self):
        # The assist thread and the overlay refresh thread both read the journal through one file handle.
        with self._read_lock:
            return self._read_new_lines()

    def market_transaction_cursor(self) -> int:
        """Drain existing events before sending a trade input."""
        with self._read_lock:
            self._read_new_lines()
            return self._market_sequence

    def market_transactions_since(self, cursor: int) -> list[dict]:
        """Return fresh market transactions without consuming other readers' events."""
        with self._read_lock:
            self._read_new_lines()
            return [dict(event) for sequence, event in self._market_transactions if sequence > cursor]

    def _read_new_lines(self):
        latest_log = self.get_latest_log()
        if latest_log is None:
            return self.ship

        # open journal file if not open yet or there is a more recent journal
        if self.current_log is None or self.current_log != latest_log:
            self.open_journal(latest_log)

        # Check if file changed
        modified_time = self.get_file_modified_time()
        if modified_time == self.last_mod_time:
            return self.ship

        cnt = 0
        incomplete = False
        while True:
            position = self.log_file.tell()
            line = self.log_file.readline()
            # if end of file then break from while True
            if not line:
                break
            else:
                try:
                    log = loads(line)
                except JSONDecodeError as error:
                    if not line.endswith("\n"):
                        self.log_file.seek(position)
                        incomplete = True
                        break
                    logger.warning("Invalid journal record in %s: %s", self.current_log, error)
                    continue
                cnt = cnt + 1
                current_jrnl = self.ship.copy()
                self.parse_line(log)

                if self.ship != current_jrnl:
                    logger.debug("Journal*.log: read: " + str(cnt) + " ship: " + str(self.ship))

        # An append after EOF must still be detected on the next read.
        self.last_mod_time = None if incomplete else modified_time
        return self.ship


def dummy_cb(msg, body=None):
    pass


def main():
    jn = EDJournal(cb=dummy_cb)
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()

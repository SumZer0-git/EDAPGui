from __future__ import annotations

import json
import os
from enum import Enum
from os import environ, listdir
from os.path import join, isfile, getmtime, abspath
from json import loads
from time import sleep, time
from datetime import datetime

from EDAP_data import ship_size_map, ship_name_map
from EDlogger import logger
from WindowsKnownPaths import *

"""
File EDJournal.py  (leveraged the EDAutopilot on github, turned into a 
                   class and enhanced, see https://github.com/skai2/EDAutopilot

Description: This file perform journal file processing.  It opens the latest updated Journal* 
file in the Saved directory, loads in the entries.  Specific entries are stored in a dictionary.
Every time the dictionary is access the file will be read and if new lines exist those will be loaded
and parsed.

The dictionary can be accesses via:  
    jn = EDJournal()

    print("Ship = ", jn.ship_state())
    ... jn.ship_state()['shieldsup']

Design:
  - open the file once
  - when accessing a field in the ship_state() first see if more to read from open file, if so 
    process it
    - also check if a new journal file present, if so close current one and open new one
 
Author: sumzer0@yahoo.com
"""

"""                             
TODO: thinking self.ship()[name]  uses the same names as in the journal, so can lookup same construct     
"""


class StationType(Enum):
    Unknown = 0
    Starport = 1  # Coriolis, Orbis, Ocellus, Dodec or Asteroid Base...
    Outpost = 2  # Outpost
    FleetCarrier = 3  # Fleet Carrier
    SquadronCarrier = 4  # Squadron Fleet Carrier
    ColonisationShip = 5  # Colonisation Ship
    SpaceConstructionDepot = 6  # Orbital Construction Depot
    PlanetaryConstructionDepot = 7  # Planet Construction Depot
    SurfaceStation = 8  # Surface Station or Crater Outpost (Crater Outpost appears to be an Engineer's Surface Base)

def get_ship_size(ship: str) -> str:
    """ Gets the ship size from the journal ship name.
        @ship:  The ship name from the journal (i.e. 'diamondbackxl').
        @return: The ship size ('S', 'M', 'L' or '' if ship not found or size not valid).
    """
    if ship.lower() in ship_size_map:
        return ship_size_map[ship.lower()]
    else:
        return ''


def get_ship_fullname(ship: str) -> str:
    """ Gets the ship full name from the journal ship name.
        @ship:  The ship name from the journal (i.e. 'diamondbackxl').
        @return: The ship full name ('Diamondback Explorer' or '' if ship not found).
    """
    if ship.lower() in ship_name_map:
        return ship_name_map[ship.lower()]
    else:
        return ''


def check_fuel_scoop(modules: list[dict[str, any]] | None) -> bool:
    """ Gets whether the ship has a fuel scoop.
    """
    # Default to fuel scoop fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "fuelscoop" in module['Item'].lower():
            return True

    return False


def check_adv_docking_computer(modules: list[dict[str, any]] | None) -> bool:
    """ Gets whether the ship has an advanced docking computer.
    Advanced docking computer will dock and undock automatically.
    """
    # Default to docking computer fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "dockingcomputer_advanced" in module['Item'].lower():
            return True

    return False


def check_std_docking_computer(modules: list[dict[str, any]] | None) -> bool:
    """ Gets whether the ship has a standard docking computer.
    Standard docking computer will dock automatically, but not undock.
    """
    # Default to docking computer fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if "dockingcomputer_standard" in module['Item'].lower():
            return True

    return False


def check_sco_fsd(modules: list[dict[str, any]] | None) -> bool:
    """ Gets whether the ship has an FSD with SCO.
    """
    # Default to SCO fitted if modules is None
    if modules is None:
        return True

    # Check all modules. Could just check the internals, but this is easier.
    for module in modules:
        if module['Slot'] == "FrameShiftDrive":
            if "overcharge" in module['Item'].lower():
                #print("FrameShiftDrive has SCO!")
                return True

    #print("FrameShiftDrive has no SCO")
    return False


def check_station_type(station_type: str, station_name: str, station_services: list[str]) -> StationType:
    """ Gets the station type.
        @station_type:  The station type from the journal (i.e. 'Coriolis').
        @station_name:  The station name from the journal (i.e. 'ColonisationShip').
        @return: The station type:
            Starport
            Outpost
            etc.
    """
    station_type_upper = station_type.upper()
    station_name_upper = station_name.upper()
    station_services_upper = [s.upper() for s in station_services]

    if station_type_upper == 'SurfaceStation'.upper():
        # Special case, for some reason the colonisation ship is a SurfaceStation in the journal.
        if 'COLONISATIONSHIP' in station_name_upper:
            return StationType.ColonisationShip
        else:
            return StationType.SurfaceStation
    elif station_type_upper == 'CraterOutpost'.upper():
        return StationType.SurfaceStation

    elif station_type_upper == 'FleetCarrier'.upper():
        if 'squadronBank'.upper() in station_services_upper:
            return StationType.SquadronCarrier
        else:
            return StationType.FleetCarrier

    elif station_type_upper == 'SpaceConstructionDepot'.upper():
        return StationType.SpaceConstructionDepot
    elif station_type_upper == 'PlanetaryConstructionDepot'.upper():
        return StationType.PlanetaryConstructionDepot

    elif station_type_upper == 'Coriolis'.upper():
        return StationType.Starport
    elif station_type_upper == 'Orbis'.upper():
        return StationType.Starport
    elif station_type_upper == 'Ocellus'.upper():
        return StationType.Starport
    elif station_type_upper == 'Bernal'.upper():  # Bernal (Sphere) is an Ocellus.
        return StationType.Starport
    elif station_type_upper == 'Dodec'.upper():
        return StationType.Starport
    elif station_type_upper == 'AsteroidBase'.upper():
        return StationType.Starport

    elif station_type_upper == 'Outpost'.upper():
        return StationType.Outpost
    else:
        # Default to starport
        print(f"Unknown station type: {station_type}. Please contact the developers for it to be added to 'check_station_type'.")
        return StationType.Unknown


class EDJournal:
    def __init__(self, cb):
        self.ap_ckb = cb
        self.last_mod_time = None
        self.log_file = None
        self.current_log = self.get_latest_log()
        self.open_journal(self.current_log)
        self._prev_const_depot_details = None

        self.ship = {
            'time': (datetime.now() - datetime.fromtimestamp(getmtime(self.current_log))).seconds,
            'odyssey': True,
            'status': 'in_space',
            'type': None,
            'location': None,
            'star_class': None,
            'target': None,
            'fighter_destroyed': False,
            'shieldsup': True,
            'under_attack': None,
            'interdicted': False,
            'no_dock_reason': None,
            'mission_completed': 0,
            'mission_redirected': 0,
            'body': None,
            'dist_jumped': 0,
            'jumps_remains': 0,
            'fuel_capacity': None,
            'fuel_level': None,
            'fuel_percent': None,
            'is_scooping': False,
            'cur_star_system': "",
            'cur_station': "",
            'cur_station_type': "",
            'exp_station_type': StationType.Unknown,
            'cargo_capacity': None,
            'ship_size': None,
            'has_fuel_scoop': None,
            'SupercruiseDestinationDrop_type': None,
            'has_adv_dock_comp': None,
            'has_std_dock_comp': None,
            'has_sco_fsd': None,
            'StationServices': None,
            'ConstructionDepotDetails': dict[str, any],
            'MarketID': 0,
        }
        self.ship_state()    # load up from file
        self.reset_items()

    def get_file_modified_time(self) -> float:
        return os.path.getmtime(self.current_log)

    # these items do not have respective log entries to clear them.  After initial reading of log file, clear these items
    # also the App will need to reset these to False after detecting they were True    
    def reset_items(self):
        self.ship['under_attack'] = False
        self.ship['fighter_destroyed'] = False

    def get_latest_log(self, path_logs=None):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if not path_logs:
            path_logs = get_path(FOLDERID.SavedGames, UserHandle.current) + "\Frontier Developments\Elite Dangerous"
        list_of_logs = [join(path_logs, f) for f in listdir(path_logs) if isfile(join(path_logs, f)) and f.startswith('Journal.')]
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log

    def open_journal(self, log_name):
        # if journal file is open then close it
        if self.log_file is not None:
            self.log_file.close()

        logger.info("Opening new Journal: "+log_name)

        # open the latest journal
        self.log_file = open(log_name, encoding="utf-8")
        self.last_mod_time = None

    def parse_line(self, log):
        # parse data
        try:
            # parse ship status
            log_event = log['event']

            # If fileheader, pull whether running Odyssey or Horizons
            if log_event == 'Fileheader':
                #self.ship['odyssey'] = log['Odyssey']
                self.ship['odyssey'] = True   # hardset to true for ED 4.0 since menus now same for Horizon

            elif log_event == 'ShieldState':
                if log['ShieldsUp'] == True:
                    self.ship['shieldsup'] = True
                else:
                    self.ship['shieldsup'] = False

            elif  log_event == 'UnderAttack':
                self.ship['under_attack'] = True

            elif  log_event == 'FighterDestroyed':
                self.ship['fighter_destroyed'] = True

            elif  log_event == 'MissionCompleted':
                self.ship['mission_completed'] = self.ship['mission_completed'] + 1  

            elif  log_event == 'MissionRedirected':
                self.ship['mission_redirected'] = self.ship['mission_redirected'] + 1  

            elif log_event == 'StartJump':
                self.ship['status'] = str('starting_'+log['JumpType']).lower()
                self.ship['SupercruiseDestinationDrop_type'] = None
                if log['JumpType'] == 'Hyperspace':
                    self.ship['star_class'] = log['StarClass']

            elif log_event == 'SupercruiseEntry' or log_event == 'FSDJump':
                self.ship['status'] = 'in_supercruise'

            elif log_event == "DockingGranted":
                self.ship['status'] = 'dockinggranted'

            elif log_event == "DockingDenied":
                self.ship['status'] = 'dockingdenied'
                self.ship['no_dock_reason'] = log['Reason']

            elif log_event == 'SupercruiseExit':
                self.ship['status'] = 'in_space'
                self.ship['body'] = log['Body']

            elif log_event == 'SupercruiseDestinationDrop':
                self.ship['SupercruiseDestinationDrop_type'] = log['Type']

            elif log_event == 'DockingCancelled':
                self.ship['status'] = 'in_space'
                
            elif log_event == 'Undocked':
                self.ship['status'] = 'starting_undocking'
                #self.ship['status'] = 'in_space'

            elif log_event == 'DockingRequested':
                self.ship['status'] = 'starting_docking'

            elif log_event == "Music" and log['MusicTrack'] == "DockingComputer":
                if self.ship['status'] == 'starting_undocking':
                    self.ship['status'] = 'in_undocking'
                elif self.ship['status'] == 'starting_docking':
                    self.ship['status'] = 'in_docking'

            elif log_event == "Music" and log['MusicTrack'] == "NoTrack" and self.ship['status'] == 'in_undocking':
                self.ship['status'] = 'in_space'
                
                # for unodck from outpost
            elif log_event == "Music" and log['MusicTrack'] == "Exploration" and self.ship['status'] == 'in_undocking':
                self.ship['status'] = 'in_space'

            elif log_event == 'Docked':
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
                self.ship['status'] = 'in_station'
                self.ship['location'] = log['StarSystem']
                self.ship['cur_star_system'] = log['StarSystem']
                self.ship['cur_station'] = log['StationName']
                self.ship['cur_station_type'] = log['StationType']
                self.ship['StationServices'] = log['StationServices']
                self.ship['exp_station_type'] = check_station_type(log['StationType'], log['StationName'], self.ship['StationServices'])
                self.ship['MarketID'] = log['MarketID']

                # parse location
            elif log_event == 'Location':
                self.ship['location'] = log['StarSystem']
                self.ship['cur_star_system'] = log['StarSystem']
                self.ship['cur_station'] = log['StationName']
                self.ship['cur_station_type'] = log['StationType']
                if 'StationServices' in log:
                    self.ship['StationServices'] = log['StationServices']
                else:
                    self.ship['StationServices'] = []
                self.ship['exp_station_type'] = check_station_type(log['StationType'], log['StationName'], self.ship['StationServices'])
                self.ship['MarketID'] = log['MarketID']
                if log['Docked'] == True:
                    self.ship['status'] = 'in_station'

            elif log_event == 'Interdicted':
                self.ship['interdicted'] = True

            # parse ship type
            elif log_event == 'LoadGame':
                self.ship['type'] = log['Ship'].lower()
                self.ship['ship_size'] = get_ship_size(log['Ship'])

            # Parse Loadout
            # When written: at startup, when loading from main menu, or when switching ships,
            # or after changing the ship in Outfitting, or when docking SRV back in mothership
            elif log_event == 'Loadout':
                self.ship['type'] = log['Ship'].lower()
                self.ship['ship_size'] = get_ship_size(log['Ship'])
                self.ship['cargo_capacity'] = log['CargoCapacity']
                self.ship['has_fuel_scoop'] = check_fuel_scoop(log['Modules'])
                self.ship['has_adv_dock_comp'] = check_adv_docking_computer(log['Modules'])
                self.ship['has_std_dock_comp'] = check_std_docking_computer(log['Modules'])
                self.ship['has_sco_fsd'] = check_sco_fsd(log['Modules'])

            # parse fuel
            if 'FuelLevel' in log and self.ship['type'] != 'TestBuggy':
                self.ship['fuel_level'] = log['FuelLevel']
            if 'FuelCapacity' in log and self.ship['type'] != 'TestBuggy':
                    try:
                        self.ship['fuel_capacity'] = log['FuelCapacity']['Main']
                    except:
                        self.ship['fuel_capacity'] = log['FuelCapacity']
            if log_event == 'FuelScoop' and 'Total' in log:
                self.ship['fuel_level'] = log['Total']
            if self.ship['fuel_level'] and self.ship['fuel_capacity']:
                self.ship['fuel_percent'] = round((self.ship['fuel_level'] / self.ship['fuel_capacity'])*100)
            else:
                self.ship['fuel_percent'] = 10

            # parse scoop
            # 
            if log_event == 'FuelScoop' and self.ship['time'] < 10 and self.ship['fuel_percent'] < 100:
                self.ship['is_scooping'] = True
            else:
                self.ship['is_scooping'] = False

            if log_event == 'FSDJump':
                self.ship['location'] = log['StarSystem']
                self.ship['cur_star_system'] = log['StarSystem']
#TODO                if 'StarClass' in log:
#TODO                    self.ship['star_class'] = log['StarClass']

            # parse target
            if log_event == 'FSDTarget':
                if log['Name'] == self.ship['location']:
                    self.ship['target'] = None
                    self.ship['jumps_remains'] = 0
                else:
                    self.ship['target'] = log['Name']
                    try:
                            self.ship['jumps_remains'] = log['RemainingJumpsInRoute']
                    except:
                        pass
                            #
                            #    'Log did not have jumps remaining. This happens most if you have less than .' +
                            #    '3 jumps remaining. Jumps remaining will be inaccurate for this jump.')


            elif log_event == 'FSDJump':
                if self.ship['location'] == self.ship['target']:
                    self.ship['target'] = None
                self.ship['dist_jumped'] = log["JumpDist"]

            # parse nav route clear
            elif log_event == 'NavRouteClear':
                self.ship['target'] = None
                self.ship['jumps_remains'] = 0

            elif log_event == 'CarrierJump':
                self.ship['location'] = log['StarSystem']
                self.ship['cur_star_system'] = log['StarSystem']
                self.ship['cur_station'] = log['StationName']
                self.ship['cur_station_type'] = log['StationType']
                self.ship['StationServices'] = log['StationServices']
                self.ship['exp_station_type'] = check_station_type(log['StationType'], log['StationName'], self.ship['StationServices'])
                self.ship['MarketID'] = log['MarketID']

            elif log_event == 'ColonisationConstructionDepot':
                # {"timestamp": "2025-06-24T02:20:26Z", "event": "ColonisationConstructionDepot",
                #  "MarketID": 3953149698, "ConstructionProgress": 0.396292, "ConstructionComplete": false,
                #  "ConstructionFailed": false, "ResourcesRequired": [
                #      {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "RequiredAmount": 1278,
                #       "ProvidedAmount": 1278, "Payment": 3239},
                #      {"Name": "$fruitandvegetables_name;", "Name_Localised": "Fruit and Vegetables",
                #       "RequiredAmount": 9, "ProvidedAmount": 9, "Payment": 865},
                #      {"Name": "$waterpurifiers_name;", "Name_Localised": "Water Purifiers", "RequiredAmount": 13,
                #       "ProvidedAmount": 13, "Payment": 849}]}
                self._prev_const_depot_details = self.ship['ConstructionDepotDetails']
                self.ship['ConstructionDepotDetails'] = {'MarketID': log['MarketID'],
                                                         'ConstructionProgress': log['ConstructionProgress'],
                                                         'ConstructionComplete': log['ConstructionComplete'],
                                                         'ConstructionFailed': log['ConstructionFailed'],
                                                         'ResourcesRequired': log['ResourcesRequired']}
                # Process the construction depot details
                self.process_construction_depot_details()

        # exceptions
        except Exception as e:
            #logger.exception("Exception occurred")
            print(e)

    def process_construction_depot_details(self):
        # TODO - save this construction data to a construction.json with multiple markets and update it
        #  locally and from Inara in case other commanders deliver goods.
        if self._prev_const_depot_details != self.ship['ConstructionDepotDetails']:
            # Load construction dict
            filepath = './configs/construction.json'
            if os.path.exists(filepath):
                const = read_construction(filepath)
            else:
                const = {}

            # Get construction details
            dic = self.ship['ConstructionDepotDetails']
            if isinstance(dic, dict):
                # If Market is the current location, use the station name
                mrk = dic.get('MarketID')
                str_mrk = str(mrk)
                if mrk == self.ship['MarketID']:
                    stn = self.ship['cur_station']
                else:
                    stn = dic.get('MarketID')

                # Check if market in construction dict
                if str_mrk not in const:
                    const[str_mrk] = {}

                system = self.ship['cur_star_system']

                # Add station to the dictionary
                const[str_mrk]['SystemName'] = system
                const[str_mrk]['StationName'] = stn
                const[str_mrk]['MarketID'] = dic.get('MarketID')
                const[str_mrk]['Include'] = True
                const[str_mrk]['ConstructionProgress'] = dic.get('ConstructionProgress')
                const[str_mrk]['ConstructionComplete'] = dic.get('ConstructionComplete')
                const[str_mrk]['ConstructionFailed'] = dic.get('ConstructionFailed')
                const[str_mrk]['ResourcesRequired'] = dic.get('ResourcesRequired')

                # Get the list of resources required.
                res = dic.get('ResourcesRequired')
                if isinstance(res, list):
                    first = True
                    for good in res:
                        if good['RequiredAmount'] > good['ProvidedAmount']:
                            need = good['RequiredAmount'] - good['ProvidedAmount']
                            if first:
                                self.ap_ckb('log', f"Construction Depot Details for '{stn}'...")
                                first = False
                            self.ap_ckb('log', f"   Need {need} of {good['Name_Localised']}.")

                # Save file
                filepath = './configs/construction.json'
                write_construction(const, filepath)

    def ship_state(self):
        latest_log = self.get_latest_log()

        # open journal file if not open yet or there is a more recent journal
        if self.current_log is None or self.current_log != latest_log:
            self.open_journal(latest_log)

        # Check if file changed
        if self.get_file_modified_time() == self.last_mod_time:
            return self.ship

        cnt = 0
        while True:
            line = self.log_file.readline()
            # if end of file then break from while True
            if not line:
                break
            else:
                log = loads(line)
                cnt = cnt + 1
                current_jrnl = self.ship.copy()
                self.parse_line(log)

                if self.ship != current_jrnl:
                    logger.debug('Journal*.log: read: '+str(cnt)+' ship: '+str(self.ship))

        self.last_mod_time = self.get_file_modified_time()
        return self.ship


def write_construction(data, filename='./configs/construction.json'):
    #  TODO - move to separate class/file
    if data is None:
        return False
    try:
        with open(filename, "w") as fp:
            json.dump(data, fp, indent=4)
            return True
    except Exception as e:
        logger.warning("EDJournal.py write_construction error:" + str(e))
        return False


def read_construction(filename='./configs/construction.json'):
    #  TODO - move to separate class/file
    s = None
    try:
        with open(filename, "r") as fp:
            s = json.load(fp)
    except Exception as e:
        logger.warning("EDJournal.py read_construction error:"+str(e))
    return s


def dummy_cb(msg, body=None):
    pass


def main():
    jn = EDJournal(cb=dummy_cb)
    while True:
        sleep(5)
        print("Ship = ", jn.ship_state())


if __name__ == "__main__":
    main()




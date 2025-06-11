from __future__ import annotations

from time import sleep

from CargoParser import CargoParser
from EDAP_data import FlagsDocked
from EDKeys import EDKeys
from EDlogger import logger
import json
from MarketParser import MarketParser
from MousePt import MousePoint
from pathlib import Path

"""
File: EDWayPoint.py    

Description:
   Class will load file called waypoints.json which contains a list of System name to jump to.
   Provides methods to select a waypoint pass into it.  

Author: sumzer0@yahoo.com
"""


class EDWayPoint:
    def __init__(self, ed_ap, is_odyssey=True):
        self.ap = ed_ap
        self.is_odyssey = is_odyssey
        self.filename = './waypoints.json'
        self.stats_log = {'Colonisation': 0, 'Construction': 0, 'Fleet Carrier': 0, 'Station': 0}
        self.waypoints = {}
        #  { "Ninabin": {"DockWithTarget": false, "TradeSeq": None, "Completed": false} }
        # for i, key in enumerate(self.waypoints):
        # self.waypoints[target]['DockWithTarget'] == True ... then go into SC Assist
        # self.waypoints[target]['Completed'] == True
        # if docked and self.waypoints[target]['Completed'] == False
        #    execute_seq(self.waypoints[target]['TradeSeq'])

        ss = self.read_waypoints()

        # if we read it then point to it, otherwise use the default table above
        if ss is not None:
            self.waypoints = ss
            logger.debug("EDWayPoint: read json:" + str(ss))

        self.num_waypoints = len(self.waypoints)

        # print("waypoints: "+str(self.waypoints))
        self.step = 0

        self.mouse = MousePoint()
        self._market_parser = None
        self._cargo_parser = None

    @property
    def market_parser(self):
        """Lazy-loaded MarketParser to avoid startup issues with locked market.json files."""
        if self._market_parser is None:
            logger.debug("Initializing MarketParser...")
            try:
                self._market_parser = MarketParser()
                logger.debug("MarketParser loaded successfully")
            except Exception as e:
                logger.debug(f"MarketParser initialization failed: {e}. Attempting fallback generation...")
                # Try to generate market.json by accessing the commodities market
                if self._try_generate_market_json():
                    try:
                        self._market_parser = MarketParser()
                        logger.debug("MarketParser loaded after market.json generation")
                    except Exception as e2:
                        logger.debug(f"MarketParser still failed after generation: {e2}. Using fallback.")
                        self._market_parser = self._create_dummy_market_parser()
                else:
                    logger.debug("Market.json generation failed. Using fallback parser.")
                    self._market_parser = self._create_dummy_market_parser()
        
        return self._market_parser

    def _create_dummy_market_parser(self):
        """Creates a dummy MarketParser that returns safe defaults when market.json is unavailable."""
        class DummyMarketParser:
            def __init__(self):
                self.current_data = {
                    'timestamp': '2000-01-01T00:00:00Z',
                    'StationName': 'Market Unavailable',
                    'Items': []
                }
            
            def get_market_data(self):
                return self.current_data
                
            def get_market_name(self):
                return 'Market Unavailable'
            
            def get_sellable_items(self, cargo_parser):
                return []
            
            def get_buyable_items(self):
                return []
                
            def get_item(self, item_name):
                return None
                
            def can_buy_item(self, item_name):
                return False
                
            def can_sell_item(self, item_name):
                return False
        
        return DummyMarketParser()

    def _try_generate_market_json(self):
        """Attempts to generate market.json by accessing the commodities market in-game."""
        try:
            from time import sleep
            import os
            
            # Check if we're docked (required for market access)
            ship_status = self.ap.jn.ship_state()
            if not ship_status.get('docked', False):
                logger.info("Cannot generate market.json: not docked at a station")
                return False
            
            logger.info("Attempting to generate market.json by accessing commodities market...")
            
            # Save current state and navigate to commodities market
            self.ap.ap_ckb('log+vce', "Accessing commodities market to generate market data...")
            
            # Navigate to Station Services -> Commodities Market
            # This will trigger Elite Dangerous to create/update market.json
            self.ap.stn_svcs_in_ship.goto_station_services()
            sleep(2)  # Wait for menu to load
            
            # Navigate to commodities market
            self.ap.keys.send('UI_Down')  # Move to Commodities Market
            sleep(0.5)
            self.ap.keys.send('UI_Select')  # Select Commodities Market
            sleep(3)  # Wait for market data to load and file to be created
            
            # Exit back to main menu
            self.ap.keys.send('UI_Back')  # Back from commodities
            sleep(0.5)
            self.ap.keys.send('UI_Back')  # Back from station services
            sleep(0.5)
            
            # Check if market.json was created
            market_path = self.ap.status.file_path.replace('Status.json', 'Market.json')
            if os.path.exists(market_path):
                logger.info("Successfully generated market.json")
                return True
            else:
                logger.warning("market.json was not created after accessing commodities market")
                return False
                
        except Exception as e:
            logger.warning(f"Error while trying to generate market.json: {e}")
            return False

    @property
    def cargo_parser(self):
        """Lazy-loaded CargoParser to avoid startup issues with locked cargo.json files."""
        if self._cargo_parser is None:
            try:
                self._cargo_parser = CargoParser()
                logger.debug("CargoParser loaded successfully for trading operations")
            except Exception as e:
                logger.warning(f"Failed to load CargoParser: {e}. Attempting to generate cargo.json...")
                # Try to generate cargo.json by accessing the cargo hold
                if self._try_generate_cargo_json():
                    try:
                        self._cargo_parser = CargoParser()
                        logger.info("CargoParser loaded successfully after generating cargo.json")
                    except Exception as e2:
                        logger.warning(f"Still failed to load CargoParser after generation: {e2}. Cargo-related features will be unavailable.")
                        self._cargo_parser = self._create_dummy_cargo_parser()
                else:
                    logger.warning("Could not generate cargo.json. Cargo-related features will be unavailable.")
                    self._cargo_parser = self._create_dummy_cargo_parser()
        return self._cargo_parser

    def _create_dummy_cargo_parser(self):
        """Creates a dummy CargoParser that returns safe defaults when cargo.json is unavailable."""
        class DummyCargoParser:
            def get_cargo_count(self):
                return 0
            
            def get_cargo_items(self):
                return []
                
            def get_cargo_data(self):
                return {'Items': []}
                
            def get_item(self, item_name):
                return None
        
        return DummyCargoParser()

    def _try_generate_cargo_json(self):
        """Attempts to generate cargo.json by accessing the cargo hold in-game."""
        try:
            from time import sleep
            import os
            
            logger.info("Attempting to generate cargo.json by accessing cargo hold...")
            
            # Navigate to cargo hold - this will trigger Elite Dangerous to create/update cargo.json
            self.ap.ap_ckb('log+vce', "Accessing cargo hold to generate cargo data...")
            
            # Open the right panel (cargo/inventory)
            self.ap.keys.send('UI_Right')  # Move to right panel
            sleep(1)
            
            # Navigate to cargo tab if not already there
            # Different key sequences depending on whether we're docked or not
            ship_status = self.ap.jn.ship_state()
            if ship_status.get('docked', False):
                # When docked, cargo might be in different position
                self.ap.keys.send('UI_Right')  # Navigate through panels
                sleep(0.5)
            
            # The act of opening the right panel with cargo should trigger cargo.json creation
            sleep(2)  # Wait for cargo data to load and file to be created
            
            # Return to main view
            self.ap.keys.send('UI_Back')  # Back to main view
            sleep(0.5)
            
            # Check if cargo.json was created
            cargo_path = self.ap.status.file_path.replace('Status.json', 'Cargo.json')
            if os.path.exists(cargo_path):
                logger.info("Successfully generated cargo.json")
                return True
            else:
                logger.warning("cargo.json was not created after accessing cargo hold")
                return False
                
        except Exception as e:
            logger.warning(f"Error while trying to generate cargo.json: {e}")
            return False

    def load_waypoint_file(self, filename=None) -> bool:
        if filename is None:
            return False

        ss = self.read_waypoints(filename)

        if ss is not None:
            self.waypoints = ss
            self.filename = filename
            self.ap.ap_ckb('log', f"Loaded Waypoint file: {filename}")
            logger.debug("EDWayPoint: read json:" + str(ss))
            return True

        self.ap.ap_ckb('log', f"Waypoint file is invalid. Check log file for details.")
        return False

    def read_waypoints(self, filename='./waypoints/waypoints.json'):
        s = None
        try:
            with open(filename, "r") as fp:
                s = json.load(fp)

            # Perform any checks on the data returned
            # Check if the waypoint data contains the 'GlobalShoppingList' (new requirement)
            if 'GlobalShoppingList' not in s:
                # self.ap.ap_ckb('log', f"Waypoint file is invalid. Check log file for details.")
                logger.warning(f"Waypoint file {filename} is invalid or old version. "
                               f"It does not contain a 'GlobalShoppingList' waypoint.")
                s = None

            # Check the
            err = False
            if s is not None:
                for key, value in s.items():
                    if key == 'GlobalShoppingList':
                        # Special case
                        if 'BuyCommodities' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'BuyCommodities'.")
                            err = True
                        if 'UpdateCommodityCount' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'UpdateCommodityCount'.")
                            err = True
                        if 'Skip' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'Skip'.")
                            err = True
                    else:
                        # All other cases
                        if 'SystemName' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'SystemName'.")
                            err = True
                        if 'StationName' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'StationName'.")
                            err = True
                        if 'GalaxyBookmarkType' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'GalaxyBookmarkType'.")
                            err = True
                        if 'GalaxyBookmarkNumber' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'GalaxyBookmarkNumber'.")
                            err = True
                        if 'SystemBookmarkType' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'SystemBookmarkType'.")
                            err = True
                        if 'SystemBookmarkNumber' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'SystemBookmarkNumber'.")
                            err = True
                        if 'SellCommodities' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'SellCommodities'.")
                            err = True
                        if 'BuyCommodities' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'BuyCommodities'.")
                            err = True
                        if 'UpdateCommodityCount' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'UpdateCommodityCount'.")
                            err = True
                        if 'FleetCarrierTransfer' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'FleetCarrierTransfer'.")
                            err = True
                        if 'Skip' not in value:
                            logger.warning(f"Waypoint file key '{key}' does not contain 'Skip'.")
                            err = True
                    if 'Completed' not in value:
                        logger.warning(f"Waypoint file key '{key}' does not contain 'Completed'.")
                        err = True

            if err:
                s = None

        except Exception as e:
            logger.warning("EDWayPoint.py read_waypoints error :" + str(e))

        return s

    def write_waypoints(self, data, filename='./waypoints/waypoints.json'):
        if data is None:
            data = self.waypoints
        try:
            with open(filename, "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("EDWayPoint.py write_waypoints error:" + str(e))

    def mark_waypoint_complete(self, key):
        self.waypoints[key]['Completed'] = True
        self.write_waypoints(data=None, filename='./waypoints/' + Path(self.filename).name)

    def get_waypoint(self) -> tuple[str, dict] | tuple[None, None]:
        """ Returns the next waypoint list or None if we are at the end of the waypoints.
        """
        dest_key = "-1"

        # loop back to beginning if last record is "REPEAT"
        while dest_key == "-1":
            for i, key in enumerate(self.waypoints):
                # skip records we already processed
                if i < self.step:
                    continue

                # if this entry is REPEAT (and not skipped), mark them all as Completed = False
                if ((self.waypoints[key].get('SystemName', "").upper() == "REPEAT")
                        and not self.waypoints[key]['Skip']):
                    self.mark_all_waypoints_not_complete()
                    break

                # if this step is marked to skip... i.e. completed, go to next step
                if (key == "GlobalShoppingList" or self.waypoints[key]['Completed']
                        or self.waypoints[key]['Skip']):
                    continue

                # This is the next uncompleted step
                self.step = i
                dest_key = key
                break
            else:
                return None, None

        return dest_key, self.waypoints[dest_key]

    def mark_all_waypoints_not_complete(self):
        for j, tkey in enumerate(self.waypoints):
            # Ensure 'Completed' key exists before trying to set it
            if 'Completed' in self.waypoints[tkey]:
                self.waypoints[tkey]['Completed'] = False
            else:
                # Handle legacy format where 'Completed' might be missing
                # Or log a warning if the structure is unexpected
                logger.warning(f"Waypoint {tkey} missing 'Completed' key during reset.")
            self.step = 0
        self.write_waypoints(data=None, filename='./waypoints/' + Path(self.filename).name)
        self.log_stats()

    def is_station_targeted(self, dest_key) -> bool:
        """ Check if a station is specified in the waypoint by name or by bookmark."""
        if self.waypoints[dest_key]['StationName'] is not None:
            if self.waypoints[dest_key]['StationName'] != "":
                return True
        if self.waypoints[dest_key]['SystemBookmarkNumber'] is not None:
            if self.waypoints[dest_key]['SystemBookmarkNumber'] != -1:
                return True
        return False

    def log_stats(self):
        calc1 = 1.5 ** self.stats_log['Colonisation']
        calc2 = 1.5 ** self.stats_log['Construction']
        sleep(max(calc1, calc2))

    def execute_trade(self, ap, dest_key):
        # Get trade commodities from waypoint with comprehensive null safety
        waypoint = self.waypoints.get(dest_key) or {}
        global_shopping = self.waypoints.get('GlobalShoppingList') or {}
        
        sell_commodities = waypoint.get('SellCommodities') or {}
        buy_commodities = waypoint.get('BuyCommodities') or {}
        fleetcarrier_transfer = waypoint.get('FleetCarrierTransfer', False)
        global_buy_commodities = global_shopping.get('BuyCommodities') or {}

        # Debug logging for trading
        logger.debug(f"execute_trade for {dest_key}:")
        logger.debug(f"  sell_commodities: {sell_commodities}")
        logger.debug(f"  buy_commodities: {buy_commodities}")
        logger.debug(f"  global_buy_commodities: {global_buy_commodities}")

        if len(sell_commodities) == 0 and len(buy_commodities) == 0 and len(global_buy_commodities) == 0:
            self.ap.ap_ckb('log', f"No trading operations defined for {dest_key}. Skipping trade.")
            return

        # Does this place have commodities service?
        # From the journal, this works for stations (incl. outpost), colonisation ship and megaships
        station_services = ap.jn.ship_state()['StationServices']
        logger.debug(f"Station services: {station_services}")
        
        if station_services is not None:
            if 'commodities' not in station_services:
                self.ap.ap_ckb('log', f"No commodities market at docked location.")
                return
            else:
                logger.debug("Commodities market available - proceeding with trade")
        else:
            self.ap.ap_ckb('log', f"No station services at docked location.")
            return

        # Determine type of station we are at
        colonisation_ship = "ColonisationShip".upper() in ap.jn.ship_state()['cur_station'].upper()
        orbital_construction_site = ap.jn.ship_state()['cur_station_type'].upper() == "SpaceConstructionDepot".upper()
        fleet_carrier = ap.jn.ship_state()['cur_station_type'].upper() == "FleetCarrier".upper()
        outpost = ap.jn.ship_state()['cur_station_type'].upper() == "Outpost".upper()

        if colonisation_ship or orbital_construction_site:
            if colonisation_ship:
                # Colonisation Ship
                self.stats_log['Colonisation'] = self.stats_log['Colonisation'] + 1
                self.ap.ap_ckb('log', f"Executing trade with Colonisation Ship.")
                logger.debug(f"Execute Trade: On Colonisation Ship")
            if orbital_construction_site:
                # Construction Ship
                self.stats_log['Construction'] = self.stats_log['Construction'] + 1
                self.ap.ap_ckb('log', f"Executing trade with Orbital Construction Ship.")
                logger.debug(f"Execute Trade: On Orbital Construction Site")

            # Go to station services
            self.ap.stn_svcs_in_ship.goto_station_services()

            # --------- SELL ----------
            if len(sell_commodities) > 0:
                # Sell all to colonisation/construction ship
                self.sell_to_colonisation_ship(ap)

        elif fleet_carrier and fleetcarrier_transfer:
            # Fleet Carrier in Transfer mode
            self.stats_log['Fleet Carrier'] = self.stats_log['Fleet Carrier'] + 1
            # --------- SELL ----------
            if len(sell_commodities) > 0:
                # Transfer to Fleet Carrier
                self.ap.internal_panel.transfer_to_fleetcarrier(ap)

            # --------- BUY ----------
            if len(buy_commodities) > 0:
                self.ap.internal_panel.transfer_from_fleetcarrier(ap, buy_commodities)

        else:
            # Regular Station or Fleet Carrier in Buy/Sell mode
            self.ap.ap_ckb('log', "Executing trade.")
            logger.debug(f"Execute Trade: On Regular Station")
            self.stats_log['Station'] = self.stats_log['Station'] + 1

            logger.debug("About to access market_parser (lazy loading will trigger here)")
            try:
                logger.debug("Calling market_parser.get_market_data()...")
                market_data = self.market_parser.get_market_data()
                logger.debug(f"get_market_data() returned: {market_data}")
                logger.debug(f"market_parser.current_data = {self.market_parser.current_data}")
                logger.debug("About to access timestamp...")
                market_time_old = self.market_parser.current_data['timestamp']
                logger.debug(f"Market data accessed successfully, timestamp: {market_time_old}")
            except Exception as e:
                logger.error(f"Failed to access market data: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                self.ap.ap_ckb('log', f"Trading failed: Could not access market data.")
                return
            
            # BUG(FIX)   Hypothesis: There might be an unknown issue where fleet carriers don't always update market.json        
            #            immediately upon entering the commodities market... or there's a file locking issue specific to carrier trading?

            # We start off on the Main Menu in the Station
            self.ap.stn_svcs_in_ship.goto_station_services()

            # CONNECTED TO menu is different between stations and fleet carriers
            if fleet_carrier:
                # Fleet Carrier COMMODITIES MARKET location top right, with:
                # uni cart, redemption, trit depot, shipyard, crew lounge
                ap.keys.send('UI_Right', repeat=2)
                ap.keys.send('UI_Select')  # Select Commodities

            elif outpost:
                # Outpost COMMODITIES MARKET location in middle column
                ap.keys.send('UI_Right')
                ap.keys.send('UI_Select')  # Select Commodities

            else:
                # Orbital station COMMODITIES MARKET location bottom left
                ap.keys.send('UI_Down')
                ap.keys.send('UI_Select')  # Select Commodities

            self.ap.ap_ckb('log+vce', "Downloading commodities data from market.")

            # Wait for market to update (with timeout and retry mechanism)
            self.market_parser.get_market_data()
            market_time_new = self.market_parser.current_data['timestamp']
            timeout_seconds = 30  # Maximum wait time for market data update
            attempts = 0
            max_attempts = timeout_seconds
            retry_attempted = False
            
            while market_time_new == market_time_old and attempts < max_attempts:
                self.market_parser.get_market_data()
                market_time_new = self.market_parser.current_data['timestamp']
                attempts += 1
                sleep(1)  # wait for new menu to finish rendering
                
                # If we've waited half the timeout, try exiting and re-entering market
                if attempts >= max_attempts // 2 and not retry_attempted:
                    retry_attempted = True
                    logger.info("Market data not updating, attempting to refresh by exiting and re-entering market")
                    self.ap.ap_ckb('log', "Market data not updating, refreshing market interface...")
                    
                    # Exit to station services
                    ap.keys.send('UI_Back', repeat=2)
                    sleep(1)
                    
                    # Re-enter commodities market
                    if fleet_carrier:
                        ap.keys.send('UI_Right', repeat=2)
                        ap.keys.send('UI_Select')  # Select Commodities
                    elif outpost:
                        ap.keys.send('UI_Right')
                        ap.keys.send('UI_Select')  # Select Commodities
                    else:
                        # Orbital station COMMODITIES MARKET location bottom left
                        ap.keys.send('UI_Down')
                        ap.keys.send('UI_Select')  # Select Commodities
                    
                    sleep(2)  # Allow market to load
                    self.market_parser.get_market_data()
                    market_time_new = self.market_parser.current_data['timestamp']
                    logger.info(f"After market refresh - Old: {market_time_old}, New: {market_time_new}")
            
            if attempts >= max_attempts:
                logger.warning(f"Market data timestamp did not update after {timeout_seconds} seconds and retry attempt")
                self.ap.ap_ckb('log+vce', f"Trading aborted: Unable to get fresh market data after retry.")
                return  # Abort trading for this station

            cargo_capacity = ap.jn.ship_state()['cargo_capacity']
            logger.debug(f"Execute trade: Current cargo capacity: {cargo_capacity}")

            # --------- SELL ----------
            if len(sell_commodities) > 0:
                # Select the SELL option
                self.ap.stn_svcs_in_ship.select_sell(ap.keys)

                for i, key in enumerate(sell_commodities):
                    # Check if we have any of the item to sell
                    self.cargo_parser.get_cargo_data()
                    cargo_item = self.cargo_parser.get_item(key)
                    if cargo_item is None:
                        logger.debug(f"Unable to sell {key}. None in cargo hold.")
                        continue

                    # Sell the commodity
                    result, qty = self.ap.stn_svcs_in_ship.sell_commodity(ap.keys, key, sell_commodities[key],
                                                                          self.cargo_parser)

                    # Update counts if necessary
                    if qty > 0 and waypoint.get('UpdateCommodityCount', False):
                        sell_commodities[key] = sell_commodities[key] - qty

                # Save changes
                self.write_waypoints(data=None, filename='./waypoints/' + Path(self.filename).name)

            sleep(1)

            # --------- BUY ----------
            if len(buy_commodities) > 0 or len(global_buy_commodities) > 0:
                # Select the BUY option
                self.ap.stn_svcs_in_ship.select_buy(ap.keys)

                # Merge waypoint-specific and global shopping lists, avoiding duplicates
                # Waypoint-specific commodities take priority over global ones
                merged_buy_list = {}
                
                # Add global commodities first
                for key, qty in global_buy_commodities.items():
                    if qty > 0:  # Only include items with positive quantities
                        merged_buy_list[key] = {
                            'qty': qty,
                            'source': 'global',
                            'update_global': global_shopping.get('UpdateCommodityCount', False)
                        }
                
                # Add waypoint-specific commodities (these override global ones)
                for key, qty in buy_commodities.items():
                    if qty > 0:  # Only include items with positive quantities
                        if key in merged_buy_list:
                            logger.info(f"Execute trade: Waypoint-specific {key} ({qty}) overrides global ({merged_buy_list[key]['qty']})")
                        merged_buy_list[key] = {
                            'qty': qty,
                            'source': 'waypoint',
                            'update_waypoint': waypoint.get('UpdateCommodityCount', False)
                        }

                # Go through merged buy commodities list
                for key, item_info in merged_buy_list.items():
                    curr_cargo_qty = int(ap.status.get_cleaned_data()['Cargo'])
                    cargo_timestamp = ap.status.current_data['timestamp']

                    free_cargo = cargo_capacity - curr_cargo_qty
                    logger.debug(f"Execute trade: Free cargo space: {free_cargo}")

                    if free_cargo == 0:
                        logger.info(f"Execute trade: No space for additional cargo")
                        break

                    qty_to_buy = item_info['qty']
                    source = item_info['source']
                    logger.info(f"Execute trade: {source.capitalize()} shopping list requests {qty_to_buy} units of {key}")

                    # Attempt to buy the commodity
                    result, qty = self.ap.stn_svcs_in_ship.buy_commodity(ap.keys, key, qty_to_buy, free_cargo)
                    logger.info(f"Execute trade: Bought {qty} units of {key}")

                    # If we bought any goods, wait for status file to update with
                    # new cargo count for next commodity
                    if qty > 0:
                        ap.status.wait_for_file_change(cargo_timestamp, 5)

                    # Update counts if necessary
                    if qty > 0:
                        if source == 'waypoint' and item_info.get('update_waypoint', False):
                            buy_commodities[key] = qty_to_buy - qty
                        elif source == 'global' and item_info.get('update_global', False):
                            global_buy_commodities[key] = qty_to_buy - qty

                # Save changes
                self.write_waypoints(data=None, filename='./waypoints/' + Path(self.filename).name)

            sleep(1.5)  # give time to popdown
            # Go to ship view
            ap.ship_control.goto_cockpit_view()

    def sell_to_colonisation_ship(self, ap):
        """ Sell all cargo to a colonisation/construction ship.
        """
        ap.keys.send('UI_Left', repeat=3)  # Go to table
        ap.keys.send('UI_Down', hold=2)  # Go to bottom
        ap.keys.send('UI_Up')  # Select RESET/CONFIRM TRANSFER/TRANSFER ALL
        ap.keys.send('UI_Left', repeat=2)  # Go to RESET
        ap.keys.send('UI_Right', repeat=2)  # Go to TRANSFER ALL
        ap.keys.send('UI_Select')  # Select TRANSFER ALL
        sleep(0.5)

        ap.keys.send('UI_Left')  # Go to CONFIRM TRANSFER
        ap.keys.send('UI_Select')  # Select CONFIRM TRANSFER
        sleep(2)

        ap.keys.send('UI_Down')  # Go to EXIT
        ap.keys.send('UI_Select')  # Select EXIT

        sleep(2)  # give time to popdown menu

    def waypoint_assist(self, keys, scr_reg):
        """ Processes the waypoints, performing jumps and sc assist if going to a station
        also can then perform trades if specific in the waypoints file.
        """
        if len(self.waypoints) == 0:
            self.ap.ap_ckb('log+vce', "No Waypoint file loaded. Exiting Waypoint Assist.")
            return

        self.step = 0  # start at first waypoint
        self.ap.ap_ckb('log', "Waypoint file: " + str(Path(self.filename).name))
        self.reset_stats()

        # Loop until complete, or error
        _abort = False
        while not _abort:
            # Current location
            cur_star_system = self.ap.jn.ship_state()['cur_star_system'].upper()
            cur_station = self.ap.jn.ship_state()['cur_station'].upper()
            cur_station_type = self.ap.jn.ship_state()['cur_station_type'].upper()

            # Current in game destination
            status = self.ap.status.get_cleaned_data()
            destination_system = status['Destination_System']  # The system ID
            destination_body = status['Destination_Body']  # The body number (0 for prim star)
            destination_name = status['Destination_Name']  # The system/body/station/settlement name

            # ====================================
            # Get next Waypoint
            # ====================================

            # Get the waypoint details
            old_step = self.step
            dest_key, next_waypoint = self.get_waypoint()
            if dest_key is None:
                self.ap.ap_ckb('log+vce', "Waypoint list has been completed.")
                break

            # Is this a new waypoint?
            if self.step != old_step:
                new_waypoint = True
            else:
                new_waypoint = False

            # Flag if we are using bookmarks
            gal_bookmark = next_waypoint.get('GalaxyBookmarkNumber', -1) > 0 if next_waypoint else False
            sys_bookmark = next_waypoint.get('SystemBookmarkNumber', -1) > 0 if next_waypoint else False
            gal_bookmark_type = next_waypoint.get('GalaxyBookmarkType', '') if next_waypoint else ''
            gal_bookmark_num = next_waypoint.get('GalaxyBookmarkNumber', 0) if next_waypoint else 0
            sys_bookmark_type = next_waypoint.get('SystemBookmarkType', '') if next_waypoint else ''
            sys_bookmark_num = next_waypoint.get('SystemBookmarkNumber', 0) if next_waypoint else 0

            next_wp_system = next_waypoint.get('SystemName', '').upper() if next_waypoint else ''
            next_wp_station = next_waypoint.get('StationName', '').upper() if next_waypoint else ''

            if new_waypoint:
                self.ap.ap_ckb('log+vce', f"Next Waypoint: {next_wp_station} in {next_wp_system}")

            # ====================================
            # Target and travel to a System
            # ====================================

            # Check current system and go to next system if different and not blank
            if next_wp_system == "" or (cur_star_system == next_wp_system):
                if new_waypoint:
                    self.ap.ap_ckb('log+vce', f"Already in target System.")
            else:
                # Check if the current nav route is to the target system
                last_nav_route_sys = self.ap.nav_route.get_last_system().upper()
                # Check we have a route and that we have a destination to a star (body 0).
                # We can have one without the other.
                if ((last_nav_route_sys == next_wp_system) and
                        (destination_body == 0 and destination_name != "")):
                    # No need to target system
                    self.ap.ap_ckb('log+vce', f"System already targeted.")
                else:
                    self.ap.ap_ckb('log+vce', f"Targeting system {next_wp_system}.")

                # Select next target system
                # TODO should this be in before every jump?
                keys.send('TargetNextRouteSystem')

                # Jump to the system (this will handle galaxy map targeting internally)
                self.ap.ap_ckb('log+vce', f"Jumping to {next_wp_system}.")
                res = self.ap.jump_to_system(scr_reg, next_wp_system)
                if res:
                    self.ap.ap_ckb('log', f"System has been targeted.")
                else:
                    self.ap.ap_ckb('log+vce', f"Failed to jump to {next_wp_system}.")
                    _abort = True
                    break

                continue

            # ====================================
            # Target and travel to a local Station
            # ====================================

            # If we are in the right system, check if we are already docked.
            docked_at_stn = False
            is_docked = self.ap.status.get_flag(FlagsDocked)
            if is_docked:
                # Check if we are at the correct station. Note that for FCs, the station name
                # reported by the Journal is only the ship identifier (ABC-123) and not the carrier name.
                # So we need to check if the ID (ABC-123) is at the end of the target ('Fleety McFleet ABC-123').
                if cur_station_type == 'FleetCarrier'.upper():
                    docked_at_stn = next_wp_station.endswith(cur_station)
                elif next_wp_station == 'System Colonisation Ship'.upper():
                    if (cur_station_type == 'SurfaceStation'.upper() and
                            'ColonisationShip'.upper() in cur_station.upper()):
                        docked_at_stn = True
                # elif next_wp_station.startswith('Orbital Construction Site'.upper()):
                #     if (cur_station_type == 'SurfaceStation'.upper() and
                #             'Orbital Construction Site'.upper() in cur_station.upper()):
                #         docked_at_stn = True
                elif cur_station == next_wp_station:
                    docked_at_stn = True

            # Check current station and go to it if different
            if docked_at_stn:
                if new_waypoint:
                    self.ap.ap_ckb('log+vce', f"Already at target Station: {next_wp_station}")
            else:
                # Check if we need to travel to a station, else we are done.
                # This may be by 1) System bookmark, 2) Galaxy bookmark or 3) by Station Name text
                if sys_bookmark or gal_bookmark or next_wp_station != "":
                    # Check if we've already targeted this station to prevent repetitive targeting
                    targeting_key = f"{dest_key}_targeting_attempted"
                    if not hasattr(self, '_targeting_attempts'):
                        self._targeting_attempts = set()
                    
                    # Check if we're already en route to this destination
                    currently_targeted = (destination_name != "" and 
                                         destination_name.upper() == next_wp_station)
                    
                    if targeting_key not in self._targeting_attempts and not currently_targeted:
                        # If waypoint file has a Station Name associated then attempt targeting it
                        self.ap.ap_ckb('log+vce', f"Targeting Station: {next_wp_station}")
                        self._targeting_attempts.add(targeting_key)

                        if gal_bookmark:
                            # Set destination via gal bookmark, not system bookmark
                            res = self.ap.galaxy_map.set_gal_map_dest_bookmark(self.ap, gal_bookmark_type, gal_bookmark_num)
                            if not res:
                                self.ap.ap_ckb('log+vce', f"Unable to set Galaxy Map bookmark.")
                                _abort = True
                                break

                        elif sys_bookmark:
                            # Set destination via system bookmark
                            res = self.ap.system_map.set_sys_map_dest_bookmark(self.ap, sys_bookmark_type, sys_bookmark_num)
                            if not res:
                                self.ap.ap_ckb('log+vce', f"Unable to set System Map bookmark.")
                                _abort = True
                                break

                        elif next_wp_station != "":
                            # Need OCR added in for this (WIP)
                            need_ocr = True
                            self.ap.ap_ckb('log+vce', f"No bookmark defined. Target by Station text not supported.")
                            # res = self.nav_panel.lock_destination(station_name)
                            _abort = True
                            break

                        # Jump to the station by name
                        res = self.ap.supercruise_to_station(scr_reg, next_wp_station)
                        sleep(1)  # Allow status log to update
                        continue
                    else:
                        # Already attempted targeting or currently en route, continue to check if we need to dock
                        if currently_targeted:
                            self.ap.ap_ckb('log', f"Already en route to {next_wp_station}, proceeding to docking check.")
                        else:
                            self.ap.ap_ckb('log', f"Station targeting already attempted for {next_wp_station}, checking docking status.")
                else:
                    self.ap.ap_ckb('log+vce', f"Arrived at target System: {next_wp_system}")

            # ====================================
            # Dock and Trade at Station
            # ====================================

            # Are we at the correct station to trade?
            if docked_at_stn:  # and (next_wp_station != "" or sys_bookmark):
                # Docked - let do trade
                self.ap.ap_ckb('log+vce', f"Execute trade at Station: {next_wp_station}")
                self.execute_trade(self.ap, dest_key)

            # Mark this waypoint as completed
            self.mark_waypoint_complete(dest_key)
            # Clear targeting attempt tracking for this waypoint to allow re-targeting on subsequent runs
            if hasattr(self, '_targeting_attempts'):
                targeting_key = f"{dest_key}_targeting_attempted"
                self._targeting_attempts.discard(targeting_key)
            self.ap.ap_ckb('log+vce', f"Current Waypoint complete.")

        # Done with waypoints
        if not _abort:
            self.ap.ap_ckb('log+vce',
                           "Waypoint Route Complete, total distance jumped: " + str(self.ap.total_dist_jumped) + "LY")
            self.ap.update_ap_status("Idle")
        else:
            self.ap.ap_ckb('log+vce', "Waypoint Route was aborted.")
            self.ap.update_ap_status("Idle")

    def reset_stats(self):
        # Clear stats
        self.stats_log['Colonisation'] = 0
        self.stats_log['Construction'] = 0
        self.stats_log['Fleet Carrier'] = 0
        self.stats_log['Station'] = 0


def main():
    from ED_AP import EDAutopilot

    ed_ap = EDAutopilot(cb=None)
    wp = EDWayPoint(ed_ap, True)  # False = Horizons
    wp.step = 0  # start at first waypoint
    keys = EDKeys(cb=None)
    keys.activate_window = True
    wp.ap.stn_svcs_in_ship.select_sell(keys)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Aluminium", 1, wp.cargo_parser)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Beryllium", 1, wp.cargo_parser)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Cobalt", 1, wp.cargo_parser)
    #wp.ap.stn_svcs_in_ship.buy_commodity(keys, "Titanium", 5, 200)

    # dest = 'Enayex'
    #print(dest)

    #print("In waypoint_assist, at:"+str(dest))

    # already in doc config, test the trade
    #wp.execute_trade(keys, dest)

    # Set the Route for the waypoint^#
    #dest = wp.waypoint_next(ap=None)

    #while dest != "":

    #  print("Doing: "+str(dest))
    #  print(wp.waypoints[dest])
    # print("Dock w/station: "+  str(wp.is_station_targeted(dest)))

    #wp.set_station_target(None, dest)

    # Mark this waypoint as complated
    #wp.mark_waypoint_complete(dest)

    # set target to next waypoint and loop
    #dest = wp.waypoint_next(ap=None)


if __name__ == "__main__":
    main()

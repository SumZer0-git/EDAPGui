from __future__ import annotations

import cv2
import json
import os
import ED_AP
from MarketParser import MarketParser
from OCR import OCR
from StatusParser import StatusParser
from time import sleep
from EDlogger import logger
from Screen_Regions import reg_scale_for_station, size_scale_for_station

"""
File:StationServicesInShip.py    

Description:
  TBD 

Author: Stumpii
"""


class EDStationServicesInShip:
    """ Handles Station Services In Ship. """
    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.locale = self.ap.locale
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.status_parser = StatusParser()
        self.market_parser = MarketParser()
        # The rect is top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg = {'connected_to': {'rect': [0.0, 0.0, 0.30, 0.30]},
                    'stn_svc_layout': {'rect': [0.05, 0.40, 0.60, 0.76]},
                    'commodities_market': {'rect': [0.0, 0.0, 0.25, 0.25]},
                    'services_list': {'rect': [0.1, 0.4, 0.5, 0.9]},
                    'carrier_admin_header': {'rect': [0.4, 0.1, 0.6, 0.2]},
                    'commodities_list': {'rect': [0.2, 0.2, 0.8, 0.9]},
                    'commodity_quantity': {'rect': [0.4, 0.5, 0.6, 0.6]},
                    }
        self.commodity_item_size = {"width": 100, "height": 15}

        self.load_calibrated_regions()

    def load_calibrated_regions(self):
        calibration_file = 'configs/ocr_calibration.json'
        if os.path.exists(calibration_file):
            with open(calibration_file, 'r') as f:
                calibrated_regions = json.load(f)

            for key, value in self.reg.items():
                calibrated_key = f"EDStationServicesInShip.{key}"
                if calibrated_key in calibrated_regions:
                    self.reg[key]['rect'] = calibrated_regions[calibrated_key]['rect']
            
            calibrated_size_key = "EDStationServicesInShip.size.commodity_item"
            if calibrated_size_key in calibrated_regions:
                self.commodity_item_size = calibrated_regions[calibrated_size_key]

    def goto_station_services(self) -> bool:
        """ Goto Station Services. """
        # Go to cockpit view
        self.ap.ship_control.goto_cockpit_view()

        self.keys.send("UI_Up", repeat=3)  # go to very top (refuel line)
        self.keys.send("UI_Down")  # station services
        self.keys.send("UI_Select")  # station services

        # Scale the regions based on the target resolution.
        scl_reg = reg_scale_for_station(self.reg['connected_to'], self.screen.screen_width, self.screen.screen_height)

        # Wait for screen to appear
        res = self.ocr.wait_for_text(self.ap, [self.locale["STN_SVCS_CONNECTED_TO"]], scl_reg)

        # Store image
        # image = self.screen.get_screen_rect_pct(scl_reg['rect'])
        # cv2.imwrite(f'test/station-services/station-services.png', image)

        # After the OCR timeout, station services will have appeared, to return true anyway.
        return True

    def goto_construction_services(self) -> bool:
        """ Goto Construction Services. This is for an Orbital Construction Site. """
        # Go to cockpit view
        self.ap.ship_control.goto_cockpit_view()

        self.keys.send("UI_Up", repeat=3)  # go to very top (refuel line)
        self.keys.send("UI_Down")  # station services
        self.keys.send("UI_Select")  # station services

        # TODO - replace with OCR from OCR branch?
        sleep(3)  # wait for new menu to finish rendering

        return True

    def select_buy(self, keys) -> bool:
        """ Select Buy. Assumes on Commodities Market screen. """

        # Select Buy
        keys.send("UI_Left", repeat=2)
        keys.send("UI_Up", repeat=4)

        keys.send("UI_Select")  # Select Buy

        sleep(0.5)  # give time to bring up list
        keys.send('UI_Right')  # Go to top of commodities list
        return True

    def select_sell(self, keys) -> bool:
        """ Select Buy. Assumes on Commodities Market screen. """

        # Select Buy
        keys.send("UI_Left", repeat=2)
        keys.send("UI_Up", repeat=4)

        keys.send("UI_Down")
        keys.send("UI_Select")  # Select Sell

        sleep(0.5)  # give time to bring up list
        keys.send('UI_Right')  # Go to top of commodities list
        return True

    def _parse_quantity(self, ocr_text: list[str]) -> int:
        if not ocr_text:
            return 0
        try:
            s = "".join(ocr_text).replace(",", "").split('/')[0].strip()
            return int(s)
        except (ValueError, IndexError):
            # It could be that the OCR picked up something else.
            # Try to find a number in the string.
            import re
            numbers = re.findall(r'\d+', "".join(ocr_text).replace(",", ""))
            if numbers:
                return int(numbers[0])
        return 0

    def _set_quantity_with_ocr(self, keys, act_qty: int, name: str, is_buy: bool, max_qty: bool) -> bool:
        """
        Sets the quantity of an item using OCR verification.
        Assumes the UI is on the buy/sell panel.
        """
        sleep(0.5)  # give time to popup
        keys.send('UI_Up', repeat=2)  # go up to quantity

        scl_reg_qty = reg_scale_for_station(self.reg['commodity_quantity'], self.screen.screen_width,
                                        self.screen.screen_height)
        
        abs_rect_qty = self.screen.screen_rect_to_abs(scl_reg_qty['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('commodity_quantity', abs_rect_qty, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        if max_qty:
            keys.send("UI_Right", hold=4)
        else:
            keys.send('UI_Left', hold=4.0) # Reset to 1
            sleep(0.2)
            if act_qty > 1:
                keys.send('UI_Right', repeat=act_qty - 1)
        
        sleep(0.5)

        # Verify final quantity
        img_qty = self.ocr.capture_region_pct(scl_reg_qty)
        ocr_text = self.ocr.image_simple_ocr(img_qty)
        current_qty = self._parse_quantity(ocr_text)

        if self.ap.debug_overlay:
            self.ap.overlay.overlay_floating_text('commodity_quantity_text', f'Target: {act_qty}, OCR: {current_qty}', abs_rect_qty[0], abs_rect_qty[1] - 25, (0, 255, 0))
            self.ap.overlay.overlay_paint()

        if current_qty != act_qty:
            # Fallback to adjust loop
            for _ in range(10): # Try to adjust 10 times
                if current_qty == act_qty:
                    break
                
                diff = act_qty - current_qty
                if diff > 0:
                    keys.send('UI_Right', repeat=diff)
                else:
                    keys.send('UI_Left', repeat=-diff)
                sleep(0.5)

                img_qty = self.ocr.capture_region_pct(scl_reg_qty)
                ocr_text = self.ocr.image_simple_ocr(img_qty)
                current_qty = self._parse_quantity(ocr_text)

                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_floating_text('commodity_quantity_text', f'Target: {act_qty}, OCR: {current_qty}', abs_rect_qty[0], abs_rect_qty[1] - 25, (0, 255, 0))
                    self.ap.overlay.overlay_paint()

        if self.ap.debug_overlay:
            sleep(1)
            self.ap.overlay.overlay_remove_rect('commodity_quantity')
            self.ap.overlay.overlay_remove_floating_text('commodity_quantity_text')
            self.ap.overlay.overlay_paint()

        if current_qty != act_qty:
            self.ap_ckb('log+vce', f"Could not set quantity to {act_qty} for '{name}'.")
            logger.error(f"Could not set quantity to {act_qty} for '{name}'. Current quantity: {current_qty}")
            keys.send('UI_Back')
            return False

        return True

    def buy_commodity(self, keys, name: str, qty: int, free_cargo: int) -> tuple[bool, int]:
        """ Buy qty of commodity. If qty >= 9999 then buy as much as possible.
        Assumed to be in the commodities buy screen in the list. """

        # If we are updating requirement count, me might have all the qty we need
        if qty <= 0:
            return False, 0

        # Determine if station sells the commodity!
        self.market_parser.get_market_data()
        if not self.market_parser.can_buy_item(name):
            self.ap_ckb('log+vce', f"'{name}' is not sold or has no stock at {self.market_parser.get_market_name()}.")
            logger.debug(f"Item '{name}' is not sold or has no stock at {self.market_parser.get_market_name()}.")
            return False, 0

        # Find commodity in mar
        # ket and return the index
        index = -1
        stock = 0
        buyable_items = self.market_parser.get_buyable_items()
        if buyable_items is not None:
            for i, value in enumerate(buyable_items):
                if value['Name_Localised'].upper() == name.upper():
                    index = i
                    stock = value['Stock']
                    logger.debug(f"Execute trade: Buy {name} (want {qty} of {stock} avail.) at position {index + 1}.")
                    break

        # Actual qty we can sell
        act_qty = min(qty, stock, free_cargo)

        # See if we buy all and if so, remove the item to update the list, as the item will be removed
        # from the commodities screen, but the market.json will not be updated.
        buy_all = act_qty == stock
        if buy_all:
            for i, value in enumerate(self.market_parser.current_data['Items']):
                if value['Name_Localised'].upper() == name.upper():
                    # Set the stock bracket to 0, so it does not get included in available commodities list.
                    self.market_parser.current_data['Items'][i]['StockBracket'] = 0

        if buyable_items is None:
            return False, 0

        # Go to top of list
        keys.send('UI_Up', hold=3.0)
        sleep(0.5)

        # Find item in list with OCR
        found_on_screen = False
        scl_reg = reg_scale_for_station(self.reg['commodities_list'], self.screen.screen_width,
                                        self.screen.screen_height)
        min_w, min_h = size_scale_for_station(self.commodity_item_size['width'], self.commodity_item_size['height'], self.screen.screen_width, self.screen.screen_height)

        # Loop to find the item
        in_list = False
        abs_rect = self.screen.screen_rect_to_abs(scl_reg['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('commodities_list', abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        for _ in range(len(buyable_items) + 5):
            img = self.ocr.capture_region_pct(scl_reg)
            img_selected, ocr_data, ocr_textlist = self.ocr.get_highlighted_item_data(img, min_w, min_h)

            if self.ap.debug_overlay:
                self.ap.overlay.overlay_floating_text('commodities_list_text', f'{ocr_textlist}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
                self.ap.overlay.overlay_paint()

            if ocr_textlist and name.upper() in str(ocr_textlist).upper():
                found_on_screen = True
                break
            
            if img_selected is None and in_list:
                # End of list
                break

            in_list = True
            keys.send('UI_Down')
            sleep(0.2)

        if self.ap.debug_overlay:
            sleep(1)
            self.ap.overlay.overlay_remove_rect('commodities_list')
            self.ap.overlay.overlay_remove_floating_text('commodities_list_text')
            self.ap.overlay.overlay_paint()

        if not found_on_screen:
            self.ap_ckb('log+vce', f"Could not find '{name}' on screen in the market.")
            logger.error(f"Could not find '{name}' on screen in the market.")
            return False, 0

        keys.send('UI_Select')  # Select that commodity

        max_qty = qty >= 9999 or qty >= stock or qty >= free_cargo
        if not self._set_quantity_with_ocr(keys, act_qty, name, True, max_qty):
            return False, 0

        self.ap_ckb('log+vce', f"Buying {act_qty} units of {name}.")
        logger.info(f"Buying {act_qty} units of {name}")
        keys.send('UI_Down')
        keys.send('UI_Select')  # Select Buy
        sleep(0.5)
        # keys.send('UI_Back')  # Back to commodities list

        return True, act_qty

    def sell_commodity(self, keys, name: str, qty: int, cargo_parser) -> tuple[bool, int]:
        """ Sell qty of commodity. If qty >= 9999 then sell as much as possible.
        Assumed to be in the commodities sell screen in the list.
        @param keys: Keys class for sending keystrokes.
        @param name: Name of the commodity.
        @param qty: Quantity to sell.
        @param cargo_parser: Current cargo to check if rare or demand=1 items exist in hold.
        @return: Sale successful (T/F) and Qty.
        """

        # If we are updating requirement count, me might have sold all we have
        if qty <= 0:
            return False, 0

        # Determine if station buys the commodity!
        self.market_parser.get_market_data()
        if not self.market_parser.can_sell_item(name):
            self.ap_ckb('log+vce', f"'{name}' is not bought at {self.market_parser.get_market_name()}.")
            logger.debug(f"Item '{name}' is not bought at {self.market_parser.get_market_name()}.")
            return False, 0

        # Find commodity in market and return the index
        demand = 0
        sellable_items = self.market_parser.get_sellable_items(cargo_parser)
        if sellable_items is not None:
            for i, value in enumerate(sellable_items):
                if value['Name_Localised'].upper() == name.upper():
                    demand = value['Demand']
                    logger.debug(f"Execute trade: Sell {name} ({qty} of {demand} demanded).")
                    break
        else:
            return False, 0

        # Qty we can sell. Unlike buying, we can sell more than the demand
        # But maybe not at all stations!
        act_qty = qty

        # Go to top of list
        keys.send('UI_Up', hold=3.0)
        sleep(0.5)

        # Find item in list with OCR
        found_on_screen = False
        scl_reg = reg_scale_for_station(self.reg['commodities_list'], self.screen.screen_width,
                                        self.screen.screen_height)
        min_w, min_h = size_scale_for_station(self.commodity_item_size['width'], self.commodity_item_size['height'], self.screen.screen_width, self.screen.screen_height)

        # Loop to find the item
        in_list = False
        abs_rect = self.screen.screen_rect_to_abs(scl_reg['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('commodities_list', abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        for _ in range(len(sellable_items) + 5):
            img = self.ocr.capture_region_pct(scl_reg)
            img_selected, ocr_data, ocr_textlist = self.ocr.get_highlighted_item_data(img, min_w, min_h)

            if self.ap.debug_overlay:
                self.ap.overlay.overlay_floating_text('commodities_list_text', f'{ocr_textlist}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
                self.ap.overlay.overlay_paint()

            if ocr_textlist and name.upper() in str(ocr_textlist).upper():
                found_on_screen = True
                break
            
            if img_selected is None and in_list:
                # End of list
                break

            in_list = True
            keys.send('UI_Down')
            sleep(0.2)

        if self.ap.debug_overlay:
            sleep(1)
            self.ap.overlay.overlay_remove_rect('commodities_list')
            self.ap.overlay.overlay_remove_floating_text('commodities_list_text')
            self.ap.overlay.overlay_paint()

        if not found_on_screen:
            self.ap_ckb('log+vce', f"Could not find '{name}' on screen in the market.")
            logger.error(f"Could not find '{name}' on screen in the market.")
            return False, 0

        keys.send('UI_Select')  # Select that commodity

        max_qty = qty >= 9999
        if not self._set_quantity_with_ocr(keys, act_qty, name, False, max_qty):
            return False, 0

        keys.send('UI_Down')  # Down to the Sell button (already assume sell all)
        keys.send('UI_Select')  # Select to Sell all
        sleep(0.5)
        # keys.send('UI_Back')  # Back to commodities list

        return True, act_qty


    def goto_fleet_carrier_management(self):
        """ Navigates to the Fleet Carrier Management screen from station services. """
        self.ap_ckb('log+vce', "Navigating to Fleet Carrier Management.")
        logger.debug("goto_fleet_carrier_management: entered")

        if not self.goto_station_services():
            logger.error("Could not open station services.")
            return False

        sleep(0.2)
        self.keys.send('UI_Down') # To redemption office
        sleep(0.2)
        self.keys.send('UI_Down') # To tritium depot
        sleep(0.2)
        self.keys.send('UI_Right') # To tritium depot
        sleep(0.2)
        self.keys.send('UI_Right') # To tritium depot
        sleep(0.2)
        self.keys.send('UI_Select') # To tritium depot
        sleep(1) # Wait for screen to load


        # Scale the regions based on the target resolution.
        scl_fleet = reg_scale_for_station(self.reg['carrier_admin_header'], self.screen.screen_width, self.screen.screen_height)

        # Wait for screen to appear
        res = self.ocr.wait_for_text(self.ap, [self.locale["STN_SVCS_FC_ADMIN_HEADER"]], scl_fleet)

        # Store image
        # image = self.screen.get_screen_rect_pct(scl_reg['rect'])
        # cv2.imwrite(f'test/carrier-management/carrier-management.png', image)

        # After the OCR timeout, carrier management will have appeared, to return true anyway.
        self.ap_ckb('log+vce', "Sucessfully entered Fleet Carrier Management.")
        logger.debug("goto_fleet_carrier_management: sucess")
        return True



def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    test_ed_ap = ED_AP.EDAutopilot(cb=dummy_cb)
    test_ed_ap.keys.activate_window = True
    svcs = EDStationServicesInShip(test_ed_ap, test_ed_ap.scr, test_ed_ap.keys, test_ed_ap.ap_ckb)
    svcs.goto_station_services()




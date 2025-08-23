from __future__ import annotations

import cv2

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
        self.reg = {'connected_to': {'rect': [0.0, 0.0, 0.25, 0.25]},
                    'stn_svc_layout': {'rect': [0.05, 0.40, 0.60, 0.76]},
                    'commodities_market': {'rect': [0.0, 0.0, 0.25, 0.25]},
                    }

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

        if index > -1:
            keys.send('UI_Up', hold=3.0)  # go up to top of list
            keys.send('UI_Down', hold=0.05, repeat=index)  # go down # of times user specified
            sleep(0.5)
            keys.send('UI_Select')  # Select that commodity

            sleep(0.5)  # give time to popup
            keys.send('UI_Up', repeat=2)  # go up to quantity to buy (may not default to this)
            # Log the planned quantity
            self.ap_ckb('log+vce', f"Buying {act_qty} units of {name}.")
            logger.info(f"Attempting to buy {act_qty} units of {name}")
            # Increment count
            if qty >= 9999 or qty >= stock or qty >= free_cargo:
                keys.send("UI_Right", hold=4)
            else:
                keys.send("UI_Right", hold=0.04, repeat=act_qty)
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
        index = -1
        demand = 0
        sellable_items = self.market_parser.get_sellable_items(cargo_parser)
        if sellable_items is not None:
            for i, value in enumerate(sellable_items):
                if value['Name_Localised'].upper() == name.upper():
                    index = i
                    demand = value['Demand']
                    logger.debug(f"Execute trade: Sell {name} ({qty} of {demand} demanded) at position {index + 1}.")
                    break

        # Qty we can sell. Unlike buying, we can sell more than the demand
        # But maybe not at all stations!
        act_qty = qty

        if index > -1:
            keys.send('UI_Up', hold=3.0)  # go up to top of list
            keys.send('UI_Down', hold=0.05, repeat=index)  # go down # of times user specified
            sleep(0.5)
            keys.send('UI_Select')  # Select that commodity

            sleep(0.5)  # give time for popup
            keys.send('UI_Up', repeat=2)  # make sure at top

            # Log the planned quantity
            if qty >= 9999:
                self.ap_ckb('log+vce', f"Selling all our units of {name}.")
                logger.info(f"Attempting to sell all our units of {name}")
                keys.send("UI_Right", hold=4)
            else:
                self.ap_ckb('log+vce', f"Selling {act_qty} units of {name}.")
                logger.info(f"Attempting to sell {act_qty} units of {name}")
                keys.send('UI_Left', hold=4.0)  # Clear quantity to 0
                keys.send("UI_Right", hold=0.04, repeat=act_qty)

            keys.send('UI_Down')  # Down to the Sell button (already assume sell all)
            keys.send('UI_Select')  # Select to Sell all
            sleep(0.5)
            # keys.send('UI_Back')  # Back to commodities list

        return True, act_qty


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    test_ed_ap = ED_AP.EDAutopilot(cb=dummy_cb)
    test_ed_ap.keys.activate_window = True
    svcs = EDStationServicesInShip(test_ed_ap, test_ed_ap.scr, test_ed_ap.keys, test_ed_ap.ap_ckb)
    svcs.goto_station_services()




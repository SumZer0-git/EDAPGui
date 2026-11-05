"""Handles the station services panel."""

from __future__ import annotations

from time import monotonic, sleep

from core.logger import logger
from game.market import MarketParser
from game.status import StatusParser
from i18n.localization import normalize_text
from vision.regions import reg_scale_for_station

TRADE_DIALOG_TIMEOUT = 15.0


class TradeDialogUnconfirmedError(Exception):
    """Raised when OCR cannot confirm the selected commodity before trade inputs."""


class EDStationServicesInShip:
    """Handles Station Services In Ship."""

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
        self.reg = {
            "connected_to": {"rect": [0.0, 0.0, 0.25, 0.25]},
            "stn_svc_layout": {"rect": [0.05, 0.40, 0.60, 0.76]},
            "commodities_market": {"rect": [0.0, 0.0, 0.25, 0.25]},
        }

    def goto_station_services(self, cockpit_timeout: float | None = None) -> bool:
        """Goto Station Services."""
        # Go to cockpit view
        if cockpit_timeout is None:
            cockpit_ready = self.ap.ship_control.goto_cockpit_view()
        else:
            cockpit_ready = self.ap.ship_control.goto_cockpit_view(timeout=cockpit_timeout)
        if not cockpit_ready:
            return False

        self.keys.send("UI_Up", repeat=3)  # go to very top (refuel line)
        self.keys.send("UI_Down")  # station services
        self.keys.send("UI_Select")  # station services

        # Scale the regions based on the target resolution.
        scl_reg = reg_scale_for_station(self.reg["connected_to"], self.screen.screen_width, self.screen.screen_height)

        # Wait for screen to appear
        texts = list(dict.fromkeys(self.locale.all_values("STN_SVCS_CONNECTED_TO")))
        texts = [text for text in texts if text and text != "?"]
        logger.debug("Station services detection: language=%s texts=%s", self.locale.language, texts)
        if not self.ocr.wait_for_text(self.ap, texts, scl_reg):
            logger.warning("Station services header was not detected before the OCR timeout.")
            self.ap_ckb("log", "Could not confirm station services. Waypoint Assist stopped.")
            return False

        # Store image
        # image = self.screen.get_screen_rect_pct(scl_reg['rect'])
        # cv2.imwrite(paths.debug_path('station-services', 'station-services.png'), image)

        return True

    def goto_construction_services(self) -> bool:
        """Goto Construction Services. This is for an Orbital Construction Site."""
        # Go to cockpit view
        self.ap.ship_control.goto_cockpit_view()

        self.keys.send("UI_Up", repeat=3)  # go to very top (refuel line)
        self.keys.send("UI_Down")  # station services
        self.keys.send("UI_Select")  # station services

        # TODO - replace with OCR from OCR branch?
        sleep(3)  # wait for new menu to finish rendering

        return True

    def select_buy(self, keys) -> bool:
        """Select Buy. Assumes on Commodities Market screen."""

        # Select Buy
        keys.send("UI_Left", repeat=2)
        keys.send("UI_Up", repeat=4)

        keys.send("UI_Select")  # Select Buy

        sleep(0.5)  # give time to bring up list
        keys.send("UI_Right")  # Go to top of commodities list
        return True

    def select_sell(self, keys) -> bool:
        """Select Buy. Assumes on Commodities Market screen."""

        # Select Buy
        keys.send("UI_Left", repeat=2)
        keys.send("UI_Up", repeat=4)

        keys.send("UI_Down")
        keys.send("UI_Select")  # Select Sell

        sleep(0.5)  # give time to bring up list
        keys.send("UI_Right")  # Go to top of commodities list
        return True

    def trade_dialog_matches(self, name: str, selling: bool) -> bool:
        """Check only the modal heading and commodity name, never the background market list."""
        title_region = reg_scale_for_station(
            {"rect": [0.265, 0.196, 0.522, 0.243]}, self.screen.screen_width, self.screen.screen_height
        )
        name_region = reg_scale_for_station(
            {"rect": [0.30, 0.279 if selling else 0.29, 0.522, 0.312 if selling else 0.325]},
            self.screen.screen_width,
            self.screen.screen_height,
        )
        title_words = self.ocr.image_simple_ocr(self.ocr.capture_region_pct(title_region))
        name_words = self.ocr.image_simple_ocr(self.ocr.capture_region_pct(name_region))
        title = normalize_text(" ".join(title_words or []))
        actual = normalize_text(" ".join(name_words or []))
        expected = normalize_text(name)
        title_key = "STN_SVCS_SELL_COMMODITY" if selling else "STN_SVCS_BUY_COMMODITY"
        titles = [normalize_text(value) for value in self.locale.all_values(title_key) if value != "?"]
        matched = bool(expected) and title in titles and actual == expected
        logger.debug(
            "Trade dialog check: selling=%s expected=%r recognized=%r title=%r matched=%s",
            selling,
            expected,
            actual,
            title,
            matched,
        )
        return matched

    def confirm_trade_dialog(self, name: str, selling: bool) -> bool:
        deadline = monotonic() + TRADE_DIALOG_TIMEOUT
        while monotonic() < deadline:
            if self.trade_dialog_matches(name, selling):
                return True
            sleep(0.25)
        logger.warning(
            "Trade dialog did not confirm the requested commodity before timeout: commodity=%r selling=%s timeout=%ss",
            name,
            selling,
            TRADE_DIALOG_TIMEOUT,
        )
        return False

    def buy_commodity(self, keys, name: str, qty: int, free_cargo: int) -> tuple[bool, int]:
        """Buy qty of commodity. If qty >= 9999 then buy as much as possible.
        Assumed to be in the commodities buy screen in the list."""

        # If we are updating requirement count, me might have all the qty we need
        if qty <= 0:
            return False, 0

        # Determine if station sells the commodity!
        self.market_parser.get_market_data()
        if not self.market_parser.can_buy_item(name):
            self.ap_ckb("log+vce", f"'{name}' is not sold or has no stock at {self.market_parser.get_market_name()}.")
            logger.debug(f"Item '{name}' is not sold or has no stock at {self.market_parser.get_market_name()}.")
            return False, 0

        # Find commodity in mar
        # ket and return the index
        index = -1
        stock = 0
        buyable_items = self.market_parser.get_buyable_items()
        if buyable_items is not None:
            for i, value in enumerate(buyable_items):
                if value["Name_Localised"].upper() == name.upper():
                    index = i
                    stock = value["Stock"]
                    logger.debug(f"Execute trade: Buy {name} (want {qty} of {stock} avail.) at position {index + 1}.")
                    break

        # Actual qty we can sell
        act_qty = min(qty, stock, free_cargo)

        if index < 0 or act_qty <= 0:
            logger.warning(
                "Cannot select requested buy commodity: commodity=%r index=%s quantity=%s", name, index, act_qty
            )
            self.ap_ckb("log", f"Cannot select '{name}' for purchase. Waypoint Assist stopped.")
            return False, 0

        if index > -1:
            keys.send("UI_Up", hold=3.0)  # go up to top of list
            keys.send(
                "UI_Down",
                hold=0.05,
                repeat=index,
            )
            sleep(0.5)
            keys.send("UI_Select")  # Select that commodity

            sleep(0.5)  # give time to popup
            if not self.confirm_trade_dialog(name, selling=False):
                raise TradeDialogUnconfirmedError(name)
            keys.send("UI_Up", repeat=2)  # go up to quantity to buy (may not default to this)
            # Log the planned quantity
            self.ap_ckb("log+vce", f"Buying {act_qty} units of {name}.")
            logger.info(f"Attempting to buy {act_qty} units of {name}")
            # Increment count
            if qty >= 9999 or qty >= stock or qty >= free_cargo:
                keys.send("UI_Right", hold=4)
            else:
                keys.send("UI_Right", hold=0.04, repeat=act_qty)
            keys.send("UI_Down")
            keys.send("UI_Select")  # Select Buy
            sleep(0.5)
            # keys.send('UI_Back')  # Back to commodities list

        if act_qty == stock:
            for value in self.market_parser.current_data["Items"]:
                if value["Name_Localised"].upper() == name.upper():
                    value["StockBracket"] = 0

        return True, act_qty

    def sell_commodity(self, keys, name: str, qty: int, cargo_parser) -> tuple[bool, int]:
        """Sell qty of commodity. If qty >= 9999 then sell as much as possible.
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
            self.ap_ckb("log+vce", f"'{name}' is not bought at {self.market_parser.get_market_name()}.")
            logger.debug(f"Item '{name}' is not bought at {self.market_parser.get_market_name()}.")
            return False, 0

        # Find commodity in market and return the index
        index = -1
        demand = 0
        sellable_items = self.market_parser.get_sellable_items(cargo_parser)
        if sellable_items is not None:
            for i, value in enumerate(sellable_items):
                if value["Name_Localised"].upper() == name.upper():
                    index = i
                    demand = value["Demand"]
                    logger.debug(f"Execute trade: Sell {name} ({qty} of {demand} demanded) at position {index + 1}.")
                    break

        # Qty we can sell. Unlike buying, we can sell more than the demand
        # But maybe not at all stations!
        act_qty = qty

        if index < 0:
            logger.warning("Cannot select requested sell commodity: commodity=%r", name)
            self.ap_ckb("log", f"Cannot select '{name}' for sale. Waypoint Assist stopped.")
            return False, 0

        if index > -1:
            keys.send("UI_Up", hold=3.0)  # go up to top of list
            keys.send(
                "UI_Down",
                hold=0.05,
                repeat=index,
            )
            sleep(0.5)
            keys.send("UI_Select")  # Select that commodity

            sleep(0.5)  # give time for popup
            if not self.confirm_trade_dialog(name, selling=True):
                raise TradeDialogUnconfirmedError(name)
            keys.send("UI_Up", repeat=2)  # make sure at top

            # Log the planned quantity
            if qty >= 9999:
                self.ap_ckb("log+vce", f"Selling all our units of {name}.")
                logger.info(f"Attempting to sell all our units of {name}")
                keys.send("UI_Right", hold=4)
            else:
                self.ap_ckb("log+vce", f"Selling {act_qty} units of {name}.")
                logger.info(f"Attempting to sell {act_qty} units of {name}")
                keys.send("UI_Left", hold=4.0)  # Clear quantity to 0
                keys.send("UI_Right", hold=0.04, repeat=act_qty)

            keys.send("UI_Down")  # Down to the Sell button (already assume sell all)
            keys.send("UI_Select")  # Select to Sell all
            sleep(0.5)
            # keys.send('UI_Back')  # Back to commodities list

        return True, act_qty


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    from core.autopilot import EDAutopilot

    test_ed_ap = EDAutopilot(cb=dummy_cb)
    test_ed_ap.keys.activate_window = True
    svcs = EDStationServicesInShip(test_ed_ap, test_ed_ap.scr, test_ed_ap.keys, test_ed_ap.ap_ckb)
    svcs.goto_station_services()

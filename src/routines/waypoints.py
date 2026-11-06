"""Loads a waypoint file (list of systems and stations to visit) and provides the next waypoint."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from time import sleep

from controls.keys import EDKeys
from controls.mouse_point import MousePoint
from core import paths
from core.commodities import commodity_symbol, is_commodity_id
from core.constants import FlagsDocked
from core.logger import logger
from core.types import FsdAssistResult
from game.cargo import CargoParser
from game.market import MarketParser
from panels.ship_control import COCKPIT_VIEW_TIMEOUT
from panels.station_services import TradeDialogUnconfirmedError


class EDWayPoint:
    def __init__(self, ed_ap, is_odyssey=True):
        self.ap = ed_ap
        self.is_odyssey = is_odyssey
        self.filename = str(paths.WAYPOINTS_DIR / "waypoints.json")
        self.route_name = "waypoints"
        self.route_version = 2
        self.repeat = False
        self.progress_filename = None
        self.route_loaded = False
        self.progress_error = False
        self.executing = False
        self.waypoints = {}
        self.route_definitions = {}
        self.num_waypoints = 0
        self.step = 0

        self.mouse = MousePoint()
        self.market_parser = MarketParser()
        self.cargo_parser = CargoParser()
        last_route = self._read_last_route()
        initial_route = last_route if last_route is not None else Path(self.filename)
        if not self._load_route(initial_route, remember=False, notify=False):
            logger.warning(f"Unable to load initial waypoint route: {initial_route}")

    def load_waypoint_file(self, filename=None) -> bool:
        if filename is None:
            return False

        return self._load_route(Path(filename), remember=True, notify=True)

    @staticmethod
    def _valid_commodity_list(value, allow_all=False) -> bool:
        return isinstance(value, dict) and all(
            (
                is_commodity_id(commodity_id)
                and isinstance(quantity, int)
                and not isinstance(quantity, bool)
                and quantity >= 0
            )
            or (allow_all and commodity_id == "All" and type(quantity) is int and quantity == 0)
            for commodity_id, quantity in value.items()
        )

    @staticmethod
    def _valid_waypoint(value) -> bool:
        required = (
            "SystemName",
            "StationName",
            "GalaxyBookmarkType",
            "GalaxyBookmarkNumber",
            "SystemBookmarkType",
            "SystemBookmarkNumber",
            "SellCommodities",
            "BuyCommodities",
            "UpdateCommodityCount",
            "FleetCarrierTransfer",
            "Enabled",
        )
        if not isinstance(value, dict) or any(key not in value for key in required):
            return False
        if not all(
            isinstance(value[key], str)
            for key in ("SystemName", "StationName", "GalaxyBookmarkType", "SystemBookmarkType")
        ):
            return False
        if not all(
            isinstance(value[key], int) and not isinstance(value[key], bool) and value[key] >= 0
            for key in ("GalaxyBookmarkNumber", "SystemBookmarkNumber")
        ):
            return False
        if not all(isinstance(value[key], bool) for key in ("UpdateCommodityCount", "FleetCarrierTransfer", "Enabled")):
            return False
        if "Skip" in value or value["SystemName"].strip().upper() == "REPEAT":
            return False
        return EDWayPoint._valid_commodity_list(
            value["SellCommodities"], allow_all=True
        ) and EDWayPoint._valid_commodity_list(value["BuyCommodities"])

    @classmethod
    def _read_route(cls, filename: Path):
        try:
            with filename.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.warning(f"Waypoint file {filename} could not be read: {error}")
            return None

        return cls.parse_route(data, filename)

    @classmethod
    def parse_route(cls, data, filename: Path):
        """Validate a route definition without changing the active route."""
        if not isinstance(data, dict):
            logger.warning(f"Waypoint file {filename} must contain a JSON object.")
            return None

        if (
            type(data.get("version")) is not int
            or data["version"] != 2
            or not isinstance(data.get("name"), str)
            or not data["name"].strip()
            or type(data.get("Repeat")) is not bool
            or "RepeatLimit" not in data
            or data["RepeatLimit"] is not None
        ):
            logger.warning(
                "Waypoint file %s is not the current v2 format. Use Import legacy JSON; "
                "RepeatLimit currently supports only null.",
                filename,
            )
            return None
        raw_waypoints = data.get("waypoints")
        if not isinstance(raw_waypoints, list):
            logger.warning(f"Waypoint file {filename} must contain a 'waypoints' list.")
            return None

        global_list = data.get("GlobalShoppingList")
        if (
            not isinstance(global_list, dict)
            or "BuyCommodities" not in global_list
            or not cls._valid_commodity_list(global_list["BuyCommodities"])
            or not isinstance(global_list.get("UpdateCommodityCount"), bool)
            or not isinstance(global_list.get("Enabled"), bool)
            or "Skip" in global_list
        ):
            logger.warning(f"Waypoint file {filename} has an invalid or missing GlobalShoppingList.")
            return None

        result = {"GlobalShoppingList": dict(global_list)}
        result["GlobalShoppingList"].setdefault("Completed", False)
        ids = set()
        for item in raw_waypoints:
            if not isinstance(item, dict):
                logger.warning(f"Waypoint file {filename} contains a non-object waypoint.")
                return None
            key = item.get("Id")
            value = {field: field_value for field, field_value in item.items() if field != "Id"}
            if (
                not isinstance(key, str)
                or not key.strip()
                or key == "GlobalShoppingList"
                or key in ids
                or "Completed" in value
            ):
                logger.warning(f"Waypoint file {filename} contains an invalid Id or a progress field in a waypoint.")
                return None
            if not cls._valid_waypoint(value):
                logger.warning(f"Waypoint file {filename} has invalid fields in waypoint '{key}'.")
                return None
            ids.add(key)
            result[key] = dict(value)
            result[key].setdefault("Completed", False)

        return result, data["name"], 2, data["Repeat"]

    def read_waypoints(self, filename=paths.WAYPOINTS_DIR / "waypoints.json"):
        route = self._read_route(Path(filename))
        return route[0] if route is not None else None

    def _load_route(self, filename: Path, remember: bool, notify: bool) -> bool:
        route = self._read_route(filename)
        if route is None:
            if notify:
                self.ap.ap_ckb("log", "Waypoint file is invalid. Check log file for details.")
            return False

        waypoints, route_name, route_version, repeat = route
        progress_filename = self._progress_path(filename)
        progress = self._read_progress(progress_filename, waypoints)
        if progress is None:
            logger.error(f"Waypoint progress file is invalid: {progress_filename}")
            if notify:
                self.ap.ap_ckb("log", "Waypoint progress is invalid. The route was not loaded.")
            return False

        definitions = copy.deepcopy(waypoints)
        self._apply_progress(waypoints, progress)
        self.waypoints = waypoints
        self.route_definitions = definitions
        self.filename = str(filename.resolve())
        self.route_name = route_name
        self.route_version = route_version
        self.repeat = repeat
        self.progress_filename = progress_filename
        self.route_loaded = True
        self.num_waypoints = len(waypoints)
        self.step = 0
        self.progress_error = False

        if remember:
            self._remember_route(Path(self.filename))
        if notify:
            self.ap.ap_ckb("log", f"Loaded Waypoint file: {self.filename}")
        logger.debug(
            "Waypoint route loaded: name=%r version=%s file=%s progress_file=%s completed=%s",
            route_name,
            route_version,
            self.filename,
            progress_filename,
            [key for key, entry in waypoints.items() if key != "GlobalShoppingList" and entry["Completed"]],
        )
        return True

    @staticmethod
    def _progress_path(filename: Path) -> Path:
        route_identity = str(filename.resolve()).casefold().encode("utf-8")
        digest = hashlib.sha256(route_identity).hexdigest()
        return paths.WAYPOINT_PROGRESS_DIR / f"{digest}.json"

    def _read_progress(self, filename: Path, waypoints: dict):
        try:
            with filename.open("r", encoding="utf-8") as fp:
                progress = json.load(fp)
        except FileNotFoundError:
            logger.debug("Waypoint progress initialized from route: progress_file=%s", filename)
            return self._legacy_progress(waypoints)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.warning(f"Waypoint progress file {filename} could not be read: {error}")
            return None

        if not isinstance(progress, dict) or type(progress.get("version")) is not int or progress["version"] != 1:
            return None
        entries = progress.get("waypoints")
        global_buys = progress.get("global_buy_commodities")
        if (
            not isinstance(entries, dict)
            or "GlobalShoppingList" in entries
            or not self._valid_commodity_list(global_buys)
        ):
            return None
        for entry in entries.values():
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("completed"), bool)
                or not self._valid_commodity_list(entry.get("buy_commodities"))
                or not self._valid_commodity_list(entry.get("sell_commodities"), allow_all=True)
            ):
                return None
        logger.debug("Waypoint progress restored: progress_file=%s data=%s", filename, progress)
        return progress

    @staticmethod
    def _legacy_progress(waypoints: dict) -> dict:
        return {
            "version": 1,
            "waypoints": {
                key: {
                    "completed": entry.get("Completed", False),
                    "buy_commodities": dict(entry["BuyCommodities"]),
                    "sell_commodities": dict(entry["SellCommodities"]),
                }
                for key, entry in waypoints.items()
                if key != "GlobalShoppingList"
            },
            "global_buy_commodities": dict(waypoints["GlobalShoppingList"]["BuyCommodities"]),
        }

    @staticmethod
    def _apply_progress(waypoints: dict, progress: dict) -> None:
        for key, entry_progress in progress["waypoints"].items():
            if key not in waypoints:
                continue
            waypoint = waypoints[key]
            waypoint["Completed"] = entry_progress["completed"]
            for field, progress_field in (
                ("BuyCommodities", "buy_commodities"),
                ("SellCommodities", "sell_commodities"),
            ):
                quantities = waypoint[field]
                quantities.update(
                    {name: qty for name, qty in entry_progress[progress_field].items() if name in quantities}
                )
        global_buys = waypoints["GlobalShoppingList"]["BuyCommodities"]
        global_buys.update(
            {name: qty for name, qty in progress["global_buy_commodities"].items() if name in global_buys}
        )

    def _read_last_route(self):
        try:
            with paths.LAST_WAYPOINT_ROUTE.open("r", encoding="utf-8") as fp:
                state = json.load(fp)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.warning(f"Last waypoint route setting could not be read: {error}")
            return None

        filename = state.get("filename") if isinstance(state, dict) else None
        if not isinstance(filename, str) or not filename:
            logger.warning("Last waypoint route setting has an invalid filename.")
            return None
        return Path(filename)

    @staticmethod
    def _write_json_atomically(filename: Path, data) -> None:
        filename.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=filename.parent, prefix=f"{filename.name}.", suffix=".tmp", delete=False
            ) as fp:
                temp_name = fp.name
                json.dump(data, fp, indent=4)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temp_name, filename)
        finally:
            if temp_name is not None and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass

    def _remember_route(self, filename: Path) -> None:
        try:
            self._write_json_atomically(paths.LAST_WAYPOINT_ROUTE, {"filename": str(filename)})
        except OSError as error:
            logger.warning(f"Unable to remember the last waypoint route: {error}")
        else:
            logger.debug("Waypoint last route saved: file=%s", filename)

    def save_waypoints(self) -> bool:
        """Save route progress separately so the route definition stays unchanged."""
        if self.progress_filename is None:
            logger.error("Cannot save waypoint progress before a route is loaded.")
            return False
        try:
            progress = {
                "version": 1,
                "waypoints": {
                    key: {
                        "completed": entry["Completed"],
                        "buy_commodities": entry["BuyCommodities"],
                        "sell_commodities": entry["SellCommodities"],
                    }
                    for key, entry in self.waypoints.items()
                    if key != "GlobalShoppingList"
                },
                "global_buy_commodities": self.waypoints["GlobalShoppingList"]["BuyCommodities"],
            }
            self._write_json_atomically(self.progress_filename, progress)
        except (OSError, TypeError, KeyError) as error:
            logger.error(f"Unable to save waypoint progress to {self.progress_filename}: {error}")
            if self.ap is not None:
                self.ap.ap_ckb("log", "Unable to save waypoint progress. Check the log file.")
            return False
        self.progress_error = False
        logger.debug(
            "Waypoint progress saved: route=%s progress_file=%s data=%s",
            self.filename,
            self.progress_filename,
            progress,
        )
        return True

    def mark_waypoint_complete(self, key) -> bool:
        previous = self.waypoints[key]["Completed"]
        self.waypoints[key]["Completed"] = True
        if not self.save_waypoints():
            self.waypoints[key]["Completed"] = previous
            self.progress_error = True
            return False
        logger.debug("Waypoint completed: route=%s id=%s", self.filename, key)
        return True

    def get_waypoint(self) -> tuple[str, dict] | tuple[None, None]:
        """Returns the next waypoint list or None if we are at the end of the waypoints."""
        restarted = False
        while True:
            for i, key in enumerate(self.waypoints):
                if i < self.step:
                    continue

                if (
                    key == "GlobalShoppingList"
                    or self.waypoints[key]["Completed"]
                    or not self.waypoints[key]["Enabled"]
                ):
                    continue

                self.step = i
                logger.debug("Waypoint selected: route=%s id=%s index=%s", self.filename, key, i)
                return key, self.waypoints[key]
            else:
                if (
                    not self.repeat
                    or restarted
                    or not any(entry["Enabled"] for key, entry in self.waypoints.items() if key != "GlobalShoppingList")
                ):
                    return None, None
                logger.debug("Waypoint route repeat reached: route=%s", self.filename)
                if not self.mark_all_waypoints_not_complete():
                    return None, None
                restarted = True
                self.step = 0

    def mark_all_waypoints_not_complete(self) -> bool:
        if not self.route_loaded:
            logger.warning("Cannot reset waypoint progress because no route is loaded.")
            return False
        previous = copy.deepcopy(self.waypoints)
        previous_step = self.step
        logger.debug("Waypoint progress reset requested: route=%s", self.filename)
        self.step = 0
        for key, entry in self.waypoints.items():
            if key == "GlobalShoppingList":
                continue
            entry["Completed"] = False
            entry["BuyCommodities"] = dict(self.route_definitions[key]["BuyCommodities"])
            entry["SellCommodities"] = dict(self.route_definitions[key]["SellCommodities"])
        self.waypoints["GlobalShoppingList"]["BuyCommodities"] = dict(
            self.route_definitions["GlobalShoppingList"]["BuyCommodities"]
        )
        if not self.save_waypoints():
            self.waypoints = previous
            self.step = previous_step
            self.progress_error = True
            return False
        logger.debug(
            "Waypoint progress reset completed: route=%s completion and commodity quantities restored", self.filename
        )
        return True

    def _wait_for_market_update(self, previous_timestamp: str, timeout: float = 15) -> bool:
        started = time.monotonic()
        deadline = started + timeout
        logger.debug("Waypoint market wait started: previous_timestamp=%r timeout=%ss", previous_timestamp, timeout)
        while (now := time.monotonic()) < deadline:
            data = self.market_parser.get_market_data()
            if data is not None and self.market_parser.current_data["timestamp"] != previous_timestamp:
                logger.debug(
                    "Waypoint market updated: previous_timestamp=%r timestamp=%r elapsed=%.3fs",
                    previous_timestamp,
                    self.market_parser.current_data["timestamp"],
                    now - started,
                )
                return True
            sleep(1)
        logger.warning(
            "Waypoint market wait timed out: previous_timestamp=%r elapsed=%.3fs timeout=%ss",
            previous_timestamp,
            now - started,
            timeout,
        )
        return False

    def _open_station_market(
        self,
        ap,
        fleet_carrier: bool,
        outpost: bool,
        previous_timestamp: str,
        cockpit_timeout: float | None = None,
    ) -> bool:
        if not ap.stn_svcs_in_ship.goto_station_services(cockpit_timeout=cockpit_timeout):
            return False

        if fleet_carrier:
            ap.keys.send("UI_Right", repeat=2)
        elif outpost:
            ap.keys.send("UI_Right")
        else:
            ap.keys.send("UI_Down")
        ap.keys.send("UI_Select")

        ap.ap_ckb("log+vce", "Downloading commodities data from market.")
        if not self._wait_for_market_update(previous_timestamp):
            ap.ap_ckb("log", "Timed out waiting for market data. Waypoint Assist stopped.")
            return False
        return True

    def _recover_trade_dialog(
        self,
        ap,
        event_type: str,
        fleet_carrier: bool,
        outpost: bool,
        previous_timestamp: str,
    ) -> bool:
        logger.debug("Recovering from unconfirmed trade dialog: event=%s", event_type)
        if not ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT):
            return False
        if not self._open_station_market(
            ap,
            fleet_carrier,
            outpost,
            previous_timestamp,
            cockpit_timeout=COCKPIT_VIEW_TIMEOUT,
        ):
            return False

        if event_type == "MarketSell":
            ap.stn_svcs_in_ship.select_sell(ap.keys)
        else:
            ap.stn_svcs_in_ship.select_buy(ap.keys)
        logger.debug(
            "Trade dialog recovery ready: event=%s market_id=%s",
            event_type,
            self.market_parser.current_data["MarketID"],
        )
        return True

    def _confirmed_trade(
        self,
        ap,
        event_type,
        commodity_id,
        quantity,
        *args,
        recover_trade_dialog: Callable[[str, str], bool] | None = None,
    ) -> tuple[bool, int]:
        if quantity <= 0:
            return True, 0

        operation = (
            ap.stn_svcs_in_ship.buy_commodity if event_type == "MarketBuy" else ap.stn_svcs_in_ship.sell_commodity
        )
        for attempt in range(2):
            if not is_commodity_id(commodity_id):
                logger.error("Cannot trade unknown commodity ID %r.", commodity_id)
                ap.ap_ckb(
                    "log",
                    f"Cannot identify commodity ID {commodity_id} in the catalogue. Waypoint Assist stopped.",
                )
                return False, 0
            try:
                market = self.market_parser.get_market_data()
                item = self.market_parser.get_item(commodity_id)
            except ValueError as error:
                logger.warning("Cannot resolve market commodity ID %s: %s", commodity_id, error)
                ap.ap_ckb("log", f"Cannot identify commodity ID {commodity_id} reliably. Waypoint Assist stopped.")
                return False, 0
            localized_name = item.get("Name_Localised") if item is not None else None
            if market is None or item is None or not isinstance(localized_name, str) or not localized_name:
                logger.error("Cannot identify commodity ID %s in the current market.", commodity_id)
                ap.ap_ckb(
                    "log", f"Cannot identify commodity ID {commodity_id} in market data. Waypoint Assist stopped."
                )
                return False, 0

            commodity = commodity_symbol(commodity_id).casefold()
            market_id = market["MarketID"]
            cursor = ap.jn.market_transaction_cursor()
            try:
                result, planned = operation(ap.keys, commodity_id, quantity, *args)
            except TradeDialogUnconfirmedError:
                logger.warning(
                    "Trade dialog was not confirmed: event=%s commodity=%r attempt=%s",
                    event_type,
                    localized_name,
                    attempt + 1,
                )
                if attempt == 0 and recover_trade_dialog and recover_trade_dialog(market["timestamp"], event_type):
                    continue
                ap.ap_ckb(
                    "log",
                    f"Could not verify the selected commodity '{localized_name}'. "
                    "No trade confirmed; Waypoint Assist stopped.",
                )
                return False, 0
            if not result or planned <= 0:
                logger.warning(
                    "Trade input failed: event=%s commodity=%r planned=%s", event_type, localized_name, planned
                )
                ap.ap_ckb("log", f"Could not trade '{localized_name}'. Waypoint Assist stopped.")
                return False, 0

            start = time.monotonic()
            logger.debug(
                "Waypoint trade confirmation started: event=%s commodity=%s market_id=%s cursor=%s planned=%s",
                event_type,
                commodity,
                market_id,
                cursor,
                planned,
            )
            while time.monotonic() - start < 10:
                for event in ap.jn.market_transactions_since(cursor):
                    if (
                        event["event"] == event_type
                        and event.get("MarketID") == market_id
                        and str(event.get("Type", "")).casefold() == commodity
                    ):
                        count = event.get("Count")
                        if type(count) is int and 0 < count <= planned:
                            logger.debug(
                                "Waypoint trade confirmed: event=%s commodity=%s market_id=%s planned=%s confirmed=%s",
                                event_type,
                                commodity,
                                market_id,
                                planned,
                                count,
                            )
                            return True, count
                        logger.error("Unexpected journal trade quantity: planned=%s event=%s", planned, event)
                        ap.ap_ckb(
                            "log",
                            f"Unexpected trade quantity for '{localized_name}'. Check cargo before restarting.",
                        )
                        return False, 0
                sleep(0.1)

            logger.warning(
                "Waypoint trade confirmation timed out: event=%s commodity=%s market_id=%s planned=%s",
                event_type,
                commodity,
                market_id,
                planned,
            )
            ap.ap_ckb(
                "log",
                f"No journal confirmation for '{localized_name}'. "
                "Waypoint Assist stopped; check cargo before restarting.",
            )
            return False, 0
        return False, 0

    def execute_trade(self, ap, dest_key) -> bool:
        # Get trade commodities from waypoint
        sell_commodities = self.waypoints[dest_key]["SellCommodities"]
        buy_commodities = self.waypoints[dest_key]["BuyCommodities"]
        fleetcarrier_transfer = self.waypoints[dest_key]["FleetCarrierTransfer"]
        global_buy_commodities = (
            {}
            if not self.waypoints["GlobalShoppingList"]["Enabled"]
            else self.waypoints["GlobalShoppingList"]["BuyCommodities"]
        )
        if fleetcarrier_transfer and (buy_commodities or global_buy_commodities):
            ap.ap_ckb(
                "log",
                "Fleet Carrier inventory transfers do not support ID-based commodity shopping lists. "
                "Waypoint Assist stopped before transfer.",
            )
            logger.warning(
                "Fleet Carrier transfer blocked because ordered commodity IDs cannot be mapped safely: "
                "id=%s buy=%s global_buy=%s",
                dest_key,
                buy_commodities,
                global_buy_commodities,
            )
            return False
        logger.debug(
            "Waypoint trade started: route=%s id=%s station=%r station_type=%r sell=%s buy=%s global_buy=%s transfer=%s",
            self.filename,
            dest_key,
            ap.jn.ship_state()["cur_station"],
            ap.jn.ship_state()["cur_station_type"],
            sell_commodities,
            buy_commodities,
            global_buy_commodities,
            fleetcarrier_transfer,
        )

        if len(sell_commodities) == 0 and len(buy_commodities) == 0 and len(global_buy_commodities) == 0:
            return True

        # Does this place have commodities service?
        # From the journal, this works for stations (incl. outpost), colonisation ship and megaships
        services = ap.jn.ship_state()["StationServices"]
        if services is None or "commodities" not in services:
            logger.warning(
                "Waypoint trade unavailable: id=%s station=%r services=%s",
                dest_key,
                ap.jn.ship_state()["cur_station"],
                services,
            )
            message = (
                "Station services are unknown." if services is None else "No commodities market at docked location."
            )
            self.ap.ap_ckb("log", message + " Waypoint Assist stopped; the waypoint remains pending.")
            return False

        # Determine type of station we are at
        station_name = "".join(
            character for character in ap.jn.ship_state()["cur_station"] if character.isalnum()
        ).upper()
        colonisation_ship = "COLONISATIONSHIP" in station_name
        orbital_construction_site = ap.jn.ship_state()["cur_station_type"].upper() == "SpaceConstructionDepot".upper()
        fleet_carrier = ap.jn.ship_state()["cur_station_type"].upper() == "FleetCarrier".upper()
        outpost = ap.jn.ship_state()["cur_station_type"].upper() == "Outpost".upper()

        if colonisation_ship or orbital_construction_site:
            if buy_commodities or global_buy_commodities:
                self.ap.ap_ckb(
                    "log",
                    "ID-based commodity purchases are not supported at construction services. "
                    "Waypoint Assist stopped before transfer.",
                )
                logger.warning(
                    "Construction transfer blocked because buy lists cannot be executed safely: "
                    "id=%s buy=%s global_buy=%s",
                    dest_key,
                    buy_commodities,
                    global_buy_commodities,
                )
                return False
            if sell_commodities and sell_commodities != {"All": 0}:
                self.ap.ap_ckb(
                    "log",
                    "Construction services support only the All cargo transfer, not ID-specific sales. "
                    "Waypoint Assist stopped before transfer.",
                )
                logger.warning(
                    "Construction transfer blocked because SellCommodities is not the All sentinel: id=%s sell=%s",
                    dest_key,
                    sell_commodities,
                )
                return False
            if colonisation_ship:
                # Colonisation Ship
                self.ap.ap_ckb("log", "Executing trade with Colonisation Ship.")
                logger.debug("Execute Trade: On Colonisation Ship")
            if orbital_construction_site:
                # Construction Ship
                self.ap.ap_ckb("log", "Executing trade with Orbital Construction Ship.")
                logger.debug("Execute Trade: On Orbital Construction Site")

            # Go to station services
            self.ap.stn_svcs_in_ship.goto_construction_services()

            # --------- SELL ----------
            if len(sell_commodities) > 0:
                # Sell all to colonisation/construction ship
                self.sell_to_colonisation_ship(ap)

        elif fleet_carrier and fleetcarrier_transfer:
            # Fleet Carrier in Transfer mode
            # --------- SELL ----------
            if len(sell_commodities) > 0:
                if sell_commodities != {"All": 0}:
                    self.ap.ap_ckb(
                        "log",
                        "Fleet Carrier transfer supports only the All cargo transfer, not ID-specific sales. "
                        "Waypoint Assist stopped before transfer.",
                    )
                    logger.warning(
                        "Fleet Carrier transfer blocked because SellCommodities is not the All sentinel: id=%s sell=%s",
                        dest_key,
                        sell_commodities,
                    )
                    return False
                # Transfer to Fleet Carrier
                if not self.ap.internal_panel.transfer_to_fleetcarrier(ap):
                    return False

            # --------- BUY ----------
            if len(buy_commodities) > 0:
                if not self.ap.internal_panel.transfer_from_fleetcarrier(ap, buy_commodities):
                    return False

        else:
            if "All" in sell_commodities:
                self.ap.ap_ckb(
                    "log",
                    "All cargo transfers require a Fleet Carrier transfer or construction service. "
                    "Waypoint Assist stopped.",
                )
                logger.warning("All cargo transfer requested at a regular market: id=%s", dest_key)
                return False
            # Regular Station or Fleet Carrier in Buy/Sell mode
            self.ap.ap_ckb("log", "Executing trade.")
            logger.debug("Execute Trade: On Regular Station")

            market_time_old = ""
            data = self.market_parser.get_market_data()
            if data is not None:
                market_time_old = self.market_parser.current_data["timestamp"]

            if not self._open_station_market(ap, fleet_carrier, outpost, market_time_old):
                ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                return False

            def recover_trade_dialog(previous_timestamp: str, event_type: str) -> bool:
                return self._recover_trade_dialog(
                    ap,
                    event_type,
                    fleet_carrier,
                    outpost,
                    previous_timestamp,
                )

            cargo_capacity = ap.jn.ship_state()["cargo_capacity"]
            logger.debug(f"Execute trade: Ship's max cargo capacity: {cargo_capacity}")

            # --------- SELL ----------
            if len(sell_commodities) > 0:
                # Select the SELL option
                self.ap.stn_svcs_in_ship.select_sell(ap.keys)

                for i, key in enumerate(sell_commodities):
                    if sell_commodities[key] <= 0:
                        continue
                    # Check if we have any of the item to sell
                    try:
                        self.cargo_parser.get_cargo_data(force=True)
                        cargo_item = self.cargo_parser.get_item_by_commodity_id(key)
                    except (OSError, ValueError) as error:
                        logger.warning(
                            "Waypoint sell cargo check failed: id=%s commodity=%r error=%s", dest_key, key, error
                        )
                        ap.ap_ckb(
                            "log", "Cannot read ship cargo reliably. Waypoint Assist stopped; sale remains pending."
                        )
                        ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                        return False
                    available = cargo_item["Count"] if cargo_item is not None else 0
                    if available == 0:
                        logger.debug(
                            "Waypoint sell skipped: id=%s commodity=%r no cargo; remaining=%s",
                            dest_key,
                            key,
                            sell_commodities[key],
                        )
                        continue
                    quantity = available if sell_commodities[key] >= 9999 else min(sell_commodities[key], available)
                    logger.debug(
                        "Waypoint sell cargo check: id=%s commodity=%r requested=%s available=%s planned=%s",
                        dest_key,
                        key,
                        sell_commodities[key],
                        available,
                        quantity,
                    )

                    # Sell the commodity
                    result, qty = self._confirmed_trade(
                        ap,
                        "MarketSell",
                        key,
                        quantity,
                        self.cargo_parser,
                        recover_trade_dialog=recover_trade_dialog,
                    )
                    logger.debug(
                        "Waypoint sell result: id=%s commodity=%r requested=%s result=%s confirmed_qty=%s",
                        dest_key,
                        key,
                        sell_commodities[key],
                        result,
                        qty,
                    )

                    if not result:
                        ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                        return False

                    # Persist each confirmed transaction before sending more inputs.
                    if qty > 0 and self.waypoints[dest_key]["UpdateCommodityCount"]:
                        sell_commodities[key] = max(0, sell_commodities[key] - qty)
                        if not self.save_waypoints():
                            ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                            return False

                    try:
                        cargo_ready = self.cargo_parser.wait_for_quantity(key, available - qty)
                    except (OSError, ValueError) as error:
                        logger.warning("Post-sale cargo synchronization failed: commodity_id=%s error=%s", key, error)
                        cargo_ready = False
                    if not cargo_ready:
                        ap.ap_ckb(
                            "log",
                            "Sale confirmed, but updated ship cargo could not be verified. "
                            "Waypoint Assist stopped before further trades; check cargo and remaining requests.",
                        )
                        ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                        return False

            sleep(1)

            # --------- BUY ----------
            if len(buy_commodities) > 0 or len(global_buy_commodities) > 0:
                # Select the BUY option
                self.ap.stn_svcs_in_ship.select_buy(ap.keys)

                # Go through buy commodities list
                for i, key in enumerate(buy_commodities):
                    curr_cargo_qty = int(ap.status.get_cleaned_data()["Cargo"])
                    cargo_timestamp = ap.status.current_data["timestamp"]

                    free_cargo = cargo_capacity - curr_cargo_qty
                    logger.debug(f"Execute trade: Free cargo space: {free_cargo}")

                    if free_cargo == 0:
                        logger.debug("Execute trade: No space for additional cargo")
                        break

                    qty_to_buy = buy_commodities[key]
                    logger.debug(f"Execute trade: Shopping list requests {qty_to_buy} units of {key}")

                    # Attempt to buy the commodity
                    result, qty = self._confirmed_trade(
                        ap,
                        "MarketBuy",
                        key,
                        qty_to_buy,
                        free_cargo,
                        recover_trade_dialog=recover_trade_dialog,
                    )
                    logger.debug(
                        "Waypoint buy result: id=%s commodity=%r requested=%s result=%s confirmed_qty=%s cargo_before=%s",
                        dest_key,
                        key,
                        qty_to_buy,
                        result,
                        qty,
                        curr_cargo_qty,
                    )

                    if not result:
                        ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                        return False
                    if qty > 0 and self.waypoints[dest_key]["UpdateCommodityCount"]:
                        buy_commodities[key] = max(0, qty_to_buy - qty)
                        if not self.save_waypoints():
                            ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                            return False

                    # If we bought any goods, wait for status file to update with
                    # new cargo count for next commodity
                    if qty > 0:
                        cargo_updated = ap.status.wait_for_file_change(cargo_timestamp, 5)
                        logger.debug(
                            "Waypoint buy cargo status: id=%s commodity=%r status_updated=%s cargo_after=%s",
                            dest_key,
                            key,
                            cargo_updated,
                            ap.status.get_cleaned_data()["Cargo"],
                        )

                # Go through global buy commodities list
                for i, key in enumerate(global_buy_commodities):
                    curr_cargo_qty = int(ap.status.get_cleaned_data()["Cargo"])
                    cargo_timestamp = ap.status.current_data["timestamp"]

                    free_cargo = cargo_capacity - curr_cargo_qty
                    logger.debug(f"Execute trade: Free cargo space: {free_cargo}")

                    if free_cargo == 0:
                        logger.debug("Execute trade: No space for additional cargo")
                        break

                    qty_to_buy = global_buy_commodities[key]
                    logger.debug(f"Execute trade: Global shopping list requests {qty_to_buy} units of {key}")

                    # Attempt to buy the commodity
                    result, qty = self._confirmed_trade(
                        ap,
                        "MarketBuy",
                        key,
                        qty_to_buy,
                        free_cargo,
                        recover_trade_dialog=recover_trade_dialog,
                    )
                    logger.debug(
                        "Waypoint global buy result: id=%s commodity=%r requested=%s result=%s confirmed_qty=%s cargo_before=%s",
                        dest_key,
                        key,
                        qty_to_buy,
                        result,
                        qty,
                        curr_cargo_qty,
                    )

                    if not result:
                        ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                        return False
                    if qty > 0 and self.waypoints["GlobalShoppingList"]["UpdateCommodityCount"]:
                        global_buy_commodities[key] = max(0, qty_to_buy - qty)
                        if not self.save_waypoints():
                            ap.ship_control.goto_cockpit_view(timeout=COCKPIT_VIEW_TIMEOUT)
                            return False

                    # If we bought any goods, wait for status file to update with
                    # new cargo count for next commodity
                    if qty > 0:
                        cargo_updated = ap.status.wait_for_file_change(cargo_timestamp, 5)
                        logger.debug(
                            "Waypoint global buy cargo status: id=%s commodity=%r status_updated=%s cargo_after=%s",
                            dest_key,
                            key,
                            cargo_updated,
                            ap.status.get_cleaned_data()["Cargo"],
                        )

            sleep(1.5)  # give time to popdown
            # Go to ship view
            ap.ship_control.goto_cockpit_view()
        return True

    def sell_to_colonisation_ship(self, ap):
        """Sell all cargo to a colonisation/construction ship."""
        ap.keys.send("UI_Left", repeat=3)  # Go to table
        ap.keys.send("UI_Down", hold=2)  # Go to bottom
        ap.keys.send("UI_Up")  # Select RESET/CONFIRM TRANSFER/TRANSFER ALL
        ap.keys.send("UI_Left", repeat=2)  # Go to RESET
        ap.keys.send("UI_Right", repeat=2)  # Go to TRANSFER ALL
        ap.keys.send("UI_Select")  # Select TRANSFER ALL
        sleep(0.5)

        ap.keys.send("UI_Left")  # Go to CONFIRM TRANSFER
        ap.keys.send("UI_Select")  # Select CONFIRM TRANSFER
        sleep(2)

        ap.keys.send("UI_Down")  # Go to EXIT
        ap.keys.send("UI_Select")  # Select EXIT

        sleep(2)  # give time to popdown menu

    def waypoint_assist(self, keys, scr_reg):
        self.executing = True
        try:
            return self._run_waypoint_assist(keys, scr_reg)
        finally:
            self.executing = False

    def _run_waypoint_assist(self, keys, scr_reg):
        """Processes the waypoints, performing jumps and sc assist if going to a station
        also can then perform trades if specific in the waypoints file.
        """
        if len(self.waypoints) == 0:
            self.ap.ap_ckb("log+vce", "No Waypoint file loaded. Exiting Waypoint Assist.")
            return

        self.step = 0  # start at first waypoint
        self.ap.ap_ckb("log", "Waypoint file: " + str(Path(self.filename).name))
        logger.debug(
            "Waypoint run started: route=%s progress_file=%s",
            self.filename,
            self.progress_filename,
        )

        # Loop until complete, or error
        _abort = False
        while not _abort:
            # Current location
            cur_star_system = self.ap.jn.ship_state()["cur_star_system"].upper()
            cur_station = self.ap.jn.ship_state()["cur_station"].upper()
            cur_station_type = self.ap.jn.ship_state()["cur_station_type"].upper()

            # Current in game destination
            status = self.ap.status.get_cleaned_data()
            destination_body = status["Destination_Body"]
            destination_name = status["Destination_Name"]

            # ====================================
            # Get next Waypoint
            # ====================================

            # Get the waypoint details
            old_step = self.step
            dest_key, next_waypoint = self.get_waypoint()
            if self.progress_error:
                _abort = True
                break
            if dest_key is None:
                self.ap.ap_ckb("log+vce", "Waypoint list has been completed.")
                break

            # Is this a new waypoint?
            if self.step != old_step:
                new_waypoint = True
            else:
                new_waypoint = False

            # Flag if we are using bookmarks
            gal_bookmark = next_waypoint.get("GalaxyBookmarkNumber", -1) > 0
            sys_bookmark = next_waypoint.get("SystemBookmarkNumber", -1) > 0
            gal_bookmark_type = next_waypoint.get("GalaxyBookmarkType", "")
            gal_bookmark_num = next_waypoint.get("GalaxyBookmarkNumber", 0)
            sys_bookmark_type = next_waypoint.get("SystemBookmarkType", "")
            sys_bookmark_num = next_waypoint.get("SystemBookmarkNumber", 0)

            next_wp_system = next_waypoint.get("SystemName", "").upper()
            next_wp_station = next_waypoint.get("StationName", "").upper()
            logger.debug(
                "Waypoint target: id=%s current_system=%r current_station=%r station_type=%r "
                "target_system=%r target_station=%r galaxy_bookmark=%r/%s system_bookmark=%r/%s",
                dest_key,
                cur_star_system,
                cur_station,
                cur_station_type,
                next_wp_system,
                next_wp_station,
                gal_bookmark_type,
                gal_bookmark_num,
                sys_bookmark_type,
                sys_bookmark_num,
            )

            if new_waypoint:
                self.ap.ap_ckb("log+vce", f"Next Waypoint: {next_wp_station} in {next_wp_system}")

            # ====================================
            # Target and travel to a System
            # ====================================

            # Check current system and go to next system if different and not blank
            if next_wp_system == "" or (cur_star_system == next_wp_system):
                if new_waypoint:
                    self.ap.ap_ckb("log+vce", "Already in target System.")
            else:
                last_nav_route_sys = self.ap.nav_route.get_last_system().upper()
                local_target_matches = bool(next_wp_station) and self.ap.has_expected_in_system_target(
                    status, next_wp_station
                )
                route_already_set = last_nav_route_sys == next_wp_system and (
                    not next_wp_station
                    or local_target_matches
                    or (not gal_bookmark and destination_body == 0 and destination_name != "")
                )
                if route_already_set:
                    self.ap.ap_ckb("log+vce", "System already targeted.")
                else:
                    self.ap.ap_ckb("log+vce", f"Targeting system {next_wp_system}.")
                    res = self._set_waypoint_system_destination(
                        next_wp_system, gal_bookmark, gal_bookmark_type, gal_bookmark_num
                    )
                    if res:
                        self.ap.ap_ckb("log", "System has been targeted.")
                    else:
                        self.ap.ap_ckb("log+vce", f"Unable to target {next_wp_system} in Galaxy Map.")
                        _abort = True
                        break

                if not self._jump_to_waypoint_system(next_wp_system, scr_reg):
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
                if cur_station_type == "FleetCarrier".upper():
                    docked_at_stn = next_wp_station.endswith(cur_station)
                elif next_wp_station == "System Colonisation Ship".upper():
                    if (
                        cur_station_type == "SurfaceStation".upper()
                        and "ColonisationShip".upper() in cur_station.upper()
                    ):
                        docked_at_stn = True
                # elif next_wp_station.startswith('Orbital Construction Site'.upper()):
                #     if (cur_station_type == 'SurfaceStation'.upper() and
                #             'Orbital Construction Site'.upper() in cur_station.upper()):
                #         docked_at_stn = True
                elif cur_station == next_wp_station:
                    docked_at_stn = True
            logger.debug("Waypoint docking check: id=%s docked=%s at_target=%s", dest_key, is_docked, docked_at_stn)

            # Check current station and go to it if different
            if docked_at_stn:
                if new_waypoint:
                    self.ap.ap_ckb("log+vce", f"Already at target Station: {next_wp_station}")
            else:
                # Check if we need to travel to a station, else we are done.
                # This may be by 1) System bookmark, 2) Galaxy bookmark or 3) by Station Name text
                if sys_bookmark or gal_bookmark or next_wp_station != "":
                    if not self._set_waypoint_local_destination(
                        status,
                        next_wp_station,
                        gal_bookmark,
                        gal_bookmark_type,
                        gal_bookmark_num,
                        sys_bookmark,
                        sys_bookmark_type,
                        sys_bookmark_num,
                    ):
                        _abort = True
                        break

                    # Jump to the station by name
                    res = self.ap.supercruise_to_station(scr_reg, next_wp_station)
                    logger.debug("Waypoint station travel returned: id=%s result=%s", dest_key, res)
                    sleep(1)  # Allow status log to update
                    continue
                else:
                    self.ap.ap_ckb("log+vce", f"Arrived at target System: {next_wp_system}")

            # ====================================
            # Dock and Trade at Station
            # ====================================

            # Are we at the correct station to trade?
            if docked_at_stn:  # and (next_wp_station != "" or sys_bookmark):
                # Docked - let do trade
                self.ap.ap_ckb("log+vce", f"Execute trade at Station: {next_wp_station}")
                if not self.execute_trade(self.ap, dest_key):
                    _abort = True
                    break

            # Mark this waypoint as completed
            if not self.mark_waypoint_complete(dest_key):
                _abort = True
                break
            self.ap.ap_ckb("log+vce", "Current Waypoint complete.")

        # Done with waypoints
        logger.debug(
            "Waypoint run ended: route=%s aborted=%s progress_error=%s",
            self.filename,
            _abort,
            self.progress_error,
        )
        if not _abort:
            self.ap.ap_ckb(
                "log+vce", "Waypoint Route Complete, total distance jumped: " + str(self.ap.total_dist_jumped) + "LY"
            )
            self.ap.set_ap_status("Idle")
        else:
            self.ap.ap_ckb("log+vce", "Waypoint Route was aborted.")
            self.ap.set_ap_status("Idle")

    def _set_waypoint_system_destination(
        self,
        target_system: str,
        has_galaxy_bookmark: bool,
        galaxy_bookmark_type: str,
        galaxy_bookmark_number: int,
    ) -> bool:
        """Plot a waypoint system from its Galaxy Map bookmark, falling back to name search."""
        if has_galaxy_bookmark:
            if self.ap.galaxy_map.set_gal_map_dest_bookmark(
                self.ap,
                galaxy_bookmark_type,
                galaxy_bookmark_number,
                expected_system=target_system,
            ):
                return True
            logger.debug(
                "Galaxy Map bookmark did not confirm system %s; falling back to name search.",
                target_system,
            )

        return self.ap.galaxy_map.set_gal_map_destination_text(self.ap, target_system, self.ap.jn.ship_state)

    def _jump_to_waypoint_system(self, target_system: str, scr_reg) -> bool:
        """Treat arrival with a selected local destination as a successful system jump."""
        self.ap.ap_ckb("log+vce", f"Jumping to {target_system}.")
        result = self.ap.jump_to_system(scr_reg, expected_system=target_system)
        if result not in (FsdAssistResult.RouteComplete, FsdAssistResult.InSystemTarget):
            self.ap.ap_ckb("log", f"Failed to jump to {target_system}.")
            return False
        return True

    def _set_waypoint_local_destination(
        self,
        status,
        station_name: str,
        has_galaxy_bookmark: bool,
        galaxy_bookmark_type: str,
        galaxy_bookmark_number: int,
        has_system_bookmark: bool,
        system_bookmark_type: str,
        system_bookmark_number: int,
    ) -> bool:
        """Keep a confirmed local target, otherwise select its local bookmark."""
        if station_name and self.ap.has_expected_in_system_target(status, station_name):
            logger.debug("Waypoint local target already selected: target=%s", station_name)
            return True

        if station_name:
            self.ap.ap_ckb("log+vce", f"Targeting Station: {station_name}")

        if has_system_bookmark:
            result = self.ap.system_map.set_sys_map_dest_bookmark(self.ap, system_bookmark_type, system_bookmark_number)
            if result and self.ap.wait_for_expected_in_system_target(station_name):
                return True
            logger.debug("System bookmark did not confirm local target %r; trying fallback.", station_name)

        if has_galaxy_bookmark:
            result = self.ap.galaxy_map.set_gal_map_dest_bookmark(self.ap, galaxy_bookmark_type, galaxy_bookmark_number)
            if result and self.ap.wait_for_expected_in_system_target(station_name):
                return True
            logger.debug("Galaxy bookmark did not confirm local target %r; trying station OCR.", station_name)

        if station_name:
            return self.ap.nav_panel.lock_destination(station_name)

        self.ap.ap_ckb("log", "No local destination could be confirmed.")
        return False

    def plot_destination(self, entry, station: bool) -> bool:
        """Select a verified target without executing travel, trade or progress changes."""
        target_system = entry["SystemName"].strip()
        current_system = self.ap.jn.ship_state()["cur_star_system"]
        galaxy = bool(entry["GalaxyBookmarkType"]) and entry["GalaxyBookmarkNumber"] > 0
        system = bool(entry["SystemBookmarkType"]) and entry["SystemBookmarkNumber"] > 0
        if station:
            if target_system.casefold() != current_system.casefold():
                if not galaxy:
                    self.ap.ap_ckb("log", "Station OCR and System bookmarks require being in the target system.")
                    return False
                if not self._set_waypoint_system_destination(
                    target_system, galaxy, entry["GalaxyBookmarkType"], entry["GalaxyBookmarkNumber"]
                ):
                    return False
                return self.ap.wait_for_expected_in_system_target(entry["StationName"])
            return self._set_waypoint_local_destination(
                self.ap.status.get_cleaned_data(),
                entry["StationName"],
                galaxy,
                entry["GalaxyBookmarkType"],
                entry["GalaxyBookmarkNumber"],
                system,
                entry["SystemBookmarkType"],
                entry["SystemBookmarkNumber"],
            )
        return self._set_waypoint_system_destination(
            target_system, galaxy, entry["GalaxyBookmarkType"], entry["GalaxyBookmarkNumber"]
        )


def main():
    from core.autopilot import EDAutopilot

    ed_ap = EDAutopilot(cb=None)
    wp = EDWayPoint(ed_ap, True)  # False = Horizons
    wp.step = 0  # start at first waypoint
    keys = EDKeys(cb=None)
    keys.activate_window = True
    wp.ap.stn_svcs_in_ship.select_sell(keys)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Aluminium", 1, wp.cargo_parser)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Beryllium", 1, wp.cargo_parser)
    wp.ap.stn_svcs_in_ship.sell_commodity(keys, "Cobalt", 1, wp.cargo_parser)
    # wp.ap.stn_svcs_in_ship.buy_commodity(keys, "Titanium", 5, 200)

    # dest = 'Enayex'
    # print(dest)

    # print("In waypoint_assist, at:"+str(dest))

    # already in doc config, test the trade
    # wp.execute_trade(keys, dest)

    # Set the Route for the waypoint^#
    # dest = wp.waypoint_next(ap=None)

    # while dest != "":

    #  print("Doing: "+str(dest))
    #  print(wp.waypoints[dest])

    # wp.set_station_target(None, dest)

    # Mark this waypoint as complated
    # wp.mark_waypoint_complete(dest)

    # set target to next waypoint and loop
    # dest = wp.waypoint_next(ap=None)


if __name__ == "__main__":
    main()

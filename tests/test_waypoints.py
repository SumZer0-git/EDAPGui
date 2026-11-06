"""Tests for loading waypoint files and choosing the next waypoint, without the game."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import paths
from core.types import FsdAssistResult
from panels.station_services import TradeDialogUnconfirmedError
from routines.waypoints import EDWayPoint

GLOBAL_LIST = {
    "SystemName": "",
    "StationName": "",
    "GalaxyBookmarkType": "",
    "GalaxyBookmarkNumber": 0,
    "SystemBookmarkType": "",
    "SystemBookmarkNumber": 0,
    "SellCommodities": {},
    "BuyCommodities": {},
    "UpdateCommodityCount": True,
    "FleetCarrierTransfer": False,
    "Enabled": False,
    "Completed": False,
}


def stop(system, **values):
    entry = {**GLOBAL_LIST, "SystemName": system, "StationName": f"{system} Station", "Enabled": True}
    entry.update(values)
    return entry


def new_waypoints(waypoints) -> EDWayPoint:
    """A waypoint object without the parsers and the autopilot, which are not needed for the list handling."""
    wp = EDWayPoint.__new__(EDWayPoint)
    wp.waypoints = copy.deepcopy(waypoints)
    wp.route_definitions = copy.deepcopy(waypoints)
    wp.step = 0
    wp.filename = "test.json"
    wp.progress_filename = None
    wp.route_loaded = True
    wp.progress_error = False
    wp.repeat = False
    wp.ap = None
    # The list handling must never write into the user's waypoint folder
    for method in ("save_waypoints",):
        patcher = mock.patch.object(wp, method)
        patcher.start()
    return wp


def version_2_route(waypoint=None):
    entry = stop("Sol", BuyCommodities={"128049154": 10}) if waypoint is None else copy.deepcopy(waypoint)
    entry.pop("Completed", None)
    return {
        "version": 2,
        "name": "Test route",
        "Repeat": False,
        "RepeatLimit": None,
        "GlobalShoppingList": {
            "BuyCommodities": {},
            "UpdateCommodityCount": False,
            "Enabled": False,
        },
        "waypoints": [{"Id": "sol-stop", **entry}],
    }


class ReadWaypointsTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = Path(self._dir.name).resolve()
        self.wp = new_waypoints({})

    def write(self, data) -> Path:
        path = self.dir / "waypoints.json"
        if "version" not in data:
            data = {
                "version": 2,
                "name": "Test",
                "Repeat": False,
                "RepeatLimit": None,
                **({"GlobalShoppingList": data["GlobalShoppingList"]} if "GlobalShoppingList" in data else {}),
                "waypoints": [
                    {"Id": key, **{field: value for field, value in entry.items() if field != "Completed"}}
                    for key, entry in data.items()
                    if key != "GlobalShoppingList"
                ],
            }
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_file(self):
        data = {"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol")}

        self.assertEqual(self.wp.read_waypoints(self.write(data)), data)

    def test_version_2_file_is_normalized_to_ordered_waypoints(self):
        data = version_2_route()

        route = self.wp.read_waypoints(self.write(data))

        self.assertEqual(list(route), ["GlobalShoppingList", "sol-stop"])
        self.assertEqual(route["sol-stop"]["SystemName"], "Sol")
        self.assertFalse(route["sol-stop"]["Completed"])

    def test_version_2_rejects_duplicate_ids(self):
        data = version_2_route()
        data["waypoints"].append(copy.deepcopy(data["waypoints"][0]))

        self.assertIsNone(self.wp.read_waypoints(self.write(data)))

    def test_old_schema_and_numeric_repeat_limit_are_rejected(self):
        for change in (
            {"RepeatLimit": 3},
            {"Repeat": "true"},
        ):
            data = {**version_2_route(), **change}
            self.assertIsNone(self.wp.read_waypoints(self.write(data)))
        data = version_2_route()
        del data["Repeat"]
        self.assertIsNone(self.wp.read_waypoints(self.write(data)))
        data = version_2_route()
        data["waypoints"][0]["Skip"] = False
        self.assertIsNone(self.wp.read_waypoints(self.write(data)))
        data = version_2_route()
        data["waypoints"][0]["SystemName"] = "REPEAT"
        self.assertIsNone(self.wp.read_waypoints(self.write(data)))

    def test_route_commodities_require_ids_except_all_sell_transfer(self):
        data = version_2_route()
        entry = data["waypoints"][0]
        entry["BuyCommodities"] = {"128049154": 2}
        entry["SellCommodities"] = {"All": 0}
        self.assertIsNotNone(self.wp.read_waypoints(self.write(data)))

        for field, value in (
            ("BuyCommodities", {"Gold": 2}),
            ("BuyCommodities", {"All": 0}),
            ("SellCommodities", {"All": 1}),
            ("SellCommodities", {"Unknown": 2}),
        ):
            with self.subTest(field=field, value=value):
                invalid = version_2_route()
                invalid["waypoints"][0][field] = value
                self.assertIsNone(self.wp.read_waypoints(self.write(invalid)))

    def test_missing_global_shopping_list(self):
        self.assertIsNone(self.wp.read_waypoints(self.write({"1": stop("Sol")})))

    def test_missing_required_field(self):
        broken = stop("Sol")
        del broken["SystemBookmarkNumber"]

        self.assertIsNone(self.wp.read_waypoints(self.write({"GlobalShoppingList": GLOBAL_LIST, "1": broken})))

    def test_missing_field_in_global_shopping_list(self):
        broken = dict(GLOBAL_LIST)
        del broken["BuyCommodities"]

        self.assertIsNone(self.wp.read_waypoints(self.write({"GlobalShoppingList": broken})))

    def test_invalid_json_and_missing_file(self):
        path = self.dir / "waypoints.json"
        path.write_text("{not json", encoding="utf-8")

        self.assertIsNone(self.wp.read_waypoints(path))
        self.assertIsNone(self.wp.read_waypoints(self.dir / "missing.json"))

    def test_shipped_example_files_are_valid(self):
        examples = sorted(paths.WAYPOINT_EXAMPLES_DIR.glob("*.json"))
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example=example.name):
                self.assertIsNotNone(self.wp.read_waypoints(example))

    def test_load_waypoint_file_reports_result(self):
        self.wp.ap = mock.Mock()
        path = self.write({"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol")})

        with (
            mock.patch.object(self.wp, "_progress_path", return_value=self.dir / "progress.json"),
            mock.patch.object(self.wp, "_remember_route"),
        ):
            self.assertTrue(self.wp.load_waypoint_file(str(path)))
            self.assertFalse(self.wp.load_waypoint_file(str(self.dir / "missing.json")))

        self.assertEqual(self.wp.filename, str(path))
        self.assertIn("1", self.wp.waypoints)
        self.assertFalse(self.wp.load_waypoint_file(None))

    def test_invalid_progress_prevents_route_from_loading(self):
        self.wp.ap = mock.Mock()
        route_path = self.write({"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol")})
        progress_path = self.dir / "progress.json"
        progress_path.write_text("{invalid", encoding="utf-8")
        was_loaded = self.wp.route_loaded

        with (
            mock.patch.object(self.wp, "_progress_path", return_value=progress_path),
            mock.patch.object(self.wp, "_remember_route"),
        ):
            self.assertFalse(self.wp.load_waypoint_file(str(route_path)))

        self.assertEqual(self.wp.waypoints, {})
        self.assertEqual(self.wp.route_loaded, was_loaded)

    def test_progress_is_saved_separately_and_restored(self):
        route_data = {"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol", BuyCommodities={"128049154": 10})}
        route_path = self.write(route_data)
        route_contents = route_path.read_bytes()
        progress_path = self.dir / "progress.json"
        wp = new_waypoints(route_data)
        wp.filename = str(route_path)
        wp.progress_filename = progress_path
        wp.waypoints["1"]["BuyCommodities"]["128049154"] = 4
        wp.waypoints["1"]["Completed"] = True
        del wp.save_waypoints

        with self.assertLogs("ed_log", level="DEBUG") as logs:
            self.assertTrue(wp.save_waypoints())
        self.assertTrue(any("Waypoint progress saved:" in line and str(progress_path) in line for line in logs.output))
        self.assertEqual(route_path.read_bytes(), route_contents)
        saved = json.loads(progress_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["waypoints"]["1"]["completed"])
        self.assertEqual(saved["waypoints"]["1"]["buy_commodities"], {"128049154": 4})

        fresh = self.wp.read_waypoints(route_path)
        with self.assertLogs("ed_log", level="DEBUG") as logs:
            progress = self.wp._read_progress(progress_path, fresh)
        self.assertTrue(any("Waypoint progress restored:" in line for line in logs.output))
        self.wp._apply_progress(fresh, progress)
        self.assertTrue(fresh["1"]["Completed"])
        self.assertEqual(fresh["1"]["BuyCommodities"], {"128049154": 4})

    def test_last_route_is_remembered(self):
        selected = self.dir / "selected.json"
        with mock.patch.object(paths, "LAST_WAYPOINT_ROUTE", self.dir / "last_route.json"):
            self.wp._remember_route(selected)
            self.assertEqual(self.wp._read_last_route(), selected)


class GetWaypointTestCase(unittest.TestCase):
    def test_skips_shopping_list_completed_and_skipped_entries(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": GLOBAL_LIST,
                "1": stop("Done", Completed=True),
                "2": stop("Skipped", Enabled=False),
                "3": stop("Next"),
                "4": stop("Later"),
            }
        )

        key, entry = wp.get_waypoint()

        self.assertEqual(key, "3")
        self.assertEqual(entry["SystemName"], "Next")

    def test_progress_through_the_list(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("A"), "2": stop("B")})

        self.assertEqual(wp.get_waypoint()[0], "1")
        wp.mark_waypoint_complete("1")
        self.assertEqual(wp.get_waypoint()[0], "2")
        wp.mark_waypoint_complete("2")
        self.assertEqual(wp.get_waypoint(), (None, None))

    def test_empty_list(self):
        self.assertEqual(new_waypoints({}).get_waypoint(), (None, None))

    def test_repeat_restarts_the_list(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": GLOBAL_LIST,
                "1": stop("A", Completed=True, BuyCommodities={"128049154": 0}),
                "2": stop("B", Completed=True),
            }
        )
        wp.repeat = True
        wp.route_definitions["1"]["BuyCommodities"] = {"128049154": 10}

        with self.assertLogs("ed_log", level="DEBUG") as logs:
            key, _ = wp.get_waypoint()

        self.assertEqual(key, "1")
        self.assertTrue(any("Waypoint route repeat reached:" in line for line in logs.output))
        self.assertTrue(any("Waypoint progress reset completed:" in line for line in logs.output))
        self.assertFalse(wp.waypoints["1"]["Completed"])
        self.assertEqual(wp.waypoints["1"]["BuyCommodities"], {"128049154": 10})
        self.assertFalse(wp.waypoints["2"]["Completed"])

    def test_skipped_repeat_ends_the_list(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": GLOBAL_LIST,
                "1": stop("A", Completed=True),
            }
        )

        self.assertEqual(wp.get_waypoint(), (None, None))

    def test_repeat_only_route_finishes_instead_of_looping(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST})
        wp.repeat = True

        self.assertEqual(wp.get_waypoint(), (None, None))

    def test_disabled_repeat_route_finishes_without_resetting(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("A", Enabled=False)})
        wp.repeat = True
        self.assertEqual(wp.get_waypoint(), (None, None))
        wp.save_waypoints.assert_not_called()

    def test_reset_restores_remaining_quantities(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": {**GLOBAL_LIST, "BuyCommodities": {"128049154": 5}},
                "1": stop("A", Completed=True, BuyCommodities={"128049154": 0}),
            }
        )
        wp.route_definitions["1"]["BuyCommodities"] = {"128049154": 10}

        self.assertTrue(wp.mark_all_waypoints_not_complete())

        self.assertFalse(wp.waypoints["1"]["Completed"])
        self.assertEqual(wp.waypoints["1"]["BuyCommodities"], {"128049154": 10})
        self.assertEqual(wp.waypoints["GlobalShoppingList"]["BuyCommodities"], {"128049154": 5})

    def test_reset_save_failure_restores_in_memory_progress(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("A", Completed=True)})
        previous = copy.deepcopy(wp.waypoints)
        previous_step = 4
        wp.step = previous_step
        wp.save_waypoints.return_value = False

        self.assertFalse(wp.mark_all_waypoints_not_complete())

        self.assertEqual(wp.waypoints, previous)
        self.assertEqual(wp.step, previous_step)
        self.assertTrue(wp.progress_error)


class WaypointBookmarkSelectionTestCase(unittest.TestCase):
    def setUp(self):
        self.wp = new_waypoints({})
        self.wp.ap = mock.Mock()

    def test_galaxy_bookmark_is_used_before_system_name_search(self):
        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.return_value = True

        self.assertTrue(self.wp._set_waypoint_system_destination("Arima", True, "Station", 3))

        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.assert_called_once_with(
            self.wp.ap, "Station", 3, expected_system="Arima"
        )
        self.wp.ap.galaxy_map.set_gal_map_destination_text.assert_not_called()

    def test_system_name_search_is_used_when_bookmark_fails(self):
        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.return_value = False
        self.wp.ap.galaxy_map.set_gal_map_destination_text.return_value = True

        self.assertTrue(self.wp._set_waypoint_system_destination("Arima", True, "Station", 3))

        self.wp.ap.galaxy_map.set_gal_map_destination_text.assert_called_once_with(
            self.wp.ap, "Arima", self.wp.ap.jn.ship_state
        )

    def test_system_name_search_is_used_without_galaxy_bookmark(self):
        self.wp.ap.galaxy_map.set_gal_map_destination_text.return_value = True

        self.assertTrue(self.wp._set_waypoint_system_destination("Arima", False, "", 0))

        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.assert_not_called()
        self.wp.ap.galaxy_map.set_gal_map_destination_text.assert_called_once()

    def test_confirmed_galaxy_bookmark_local_target_is_not_selected_twice(self):
        self.wp.ap.has_expected_in_system_target.return_value = True

        self.assertTrue(
            self.wp._set_waypoint_local_destination({}, "Kent's Legacy", True, "Station", 3, True, "Station", 2)
        )

        self.wp.ap.system_map.set_sys_map_dest_bookmark.assert_not_called()
        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.assert_not_called()

    def test_system_bookmark_remains_local_target_after_galaxy_route(self):
        self.wp.ap.has_expected_in_system_target.return_value = False
        self.wp.ap.system_map.set_sys_map_dest_bookmark.return_value = True

        self.assertTrue(
            self.wp._set_waypoint_local_destination({}, "Kent's Legacy", True, "Station", 3, True, "Station", 2)
        )

        self.wp.ap.system_map.set_sys_map_dest_bookmark.assert_called_once_with(self.wp.ap, "Station", 2)
        self.wp.ap.galaxy_map.set_gal_map_dest_bookmark.assert_not_called()

    def test_station_ocr_used_when_bookmarks_do_not_confirm_target(self):
        self.wp.ap.has_expected_in_system_target.return_value = False
        self.wp.ap.wait_for_expected_in_system_target.return_value = False
        self.wp.ap.nav_panel.lock_destination.return_value = True
        self.assertTrue(self.wp._set_waypoint_local_destination({}, "Ohm City", True, "Fav", 1, True, "Station", 2))
        self.wp.ap.nav_panel.lock_destination.assert_called_once_with("Ohm City")

    def test_plot_station_in_other_system_without_galaxy_bookmark_does_not_travel(self):
        self.wp.ap.jn.ship_state.return_value = {"cur_star_system": "Arima"}
        entry = stop("LHS 20", StationName="Ohm City")
        self.assertFalse(self.wp.plot_destination(entry, True))
        self.wp.ap.jump_to_system.assert_not_called()
        self.wp.ap.nav_panel.lock_destination.assert_not_called()

    def test_plot_local_station_uses_shared_targeting_without_progress_or_flight(self):
        self.wp.ap.jn.ship_state.return_value = {"cur_star_system": "LHS 20"}
        self.wp.ap.has_expected_in_system_target.return_value = False
        self.wp.ap.nav_panel.lock_destination.return_value = True
        self.assertTrue(self.wp.plot_destination(stop("LHS 20", StationName="Ohm City"), True))
        self.wp.ap.nav_panel.lock_destination.assert_called_once_with("Ohm City")
        self.wp.ap.supercruise_to_station.assert_not_called()
        self.wp.save_waypoints.assert_not_called()

    def test_waypoint_accepts_system_arrival_with_a_local_target(self):
        self.wp.ap.jump_to_system.return_value = FsdAssistResult.InSystemTarget

        self.assertTrue(self.wp._jump_to_waypoint_system("Arima", mock.Mock()))
        self.wp.ap.ap_ckb.assert_any_call("log+vce", "Jumping to Arima.")

    def test_waypoint_aborts_when_system_jump_fails(self):
        self.wp.ap.jump_to_system.return_value = FsdAssistResult.Failed

        self.assertFalse(self.wp._jump_to_waypoint_system("Arima", mock.Mock()))
        self.wp.ap.ap_ckb.assert_any_call("log", "Failed to jump to Arima.")


class MarketWaitTestCase(unittest.TestCase):
    def test_market_wait_times_out_after_deadline(self):
        wp = new_waypoints({})
        wp.market_parser = mock.Mock()
        wp.market_parser.get_market_data.return_value = None
        with (
            mock.patch("routines.waypoints.time.monotonic", side_effect=[100, 101, 105, 116]),
            mock.patch("routines.waypoints.sleep"),
            self.assertLogs("ed_log", level="DEBUG") as logs,
        ):
            self.assertFalse(wp._wait_for_market_update("same", timeout=15))

        self.assertEqual(wp.market_parser.get_market_data.call_count, 2)
        self.assertTrue(any("WARNING" in line and "elapsed=16.000s" in line for line in logs.output))

    def test_market_wait_returns_when_market_timestamp_changes(self):
        wp = new_waypoints({})
        wp.market_parser = mock.Mock()
        wp.market_parser.get_market_data.side_effect = [None, {"market": "data"}]
        wp.market_parser.current_data = {"timestamp": "new"}
        with (
            mock.patch("routines.waypoints.time.monotonic", side_effect=[100, 101, 102]),
            mock.patch("routines.waypoints.sleep"),
            self.assertLogs("ed_log", level="DEBUG") as logs,
        ):
            self.assertTrue(wp._wait_for_market_update("old", timeout=15))

        self.assertEqual(wp.market_parser.get_market_data.call_count, 2)
        self.assertTrue(any("Waypoint market updated:" in line and "elapsed=2.000s" in line for line in logs.output))


class TradeDiagnosticsTestCase(unittest.TestCase):
    def test_localized_buy_logs_confirmed_quantity_and_observed_cargo(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol", BuyCommodities={"128049197": 2})})
        wp.ap = mock.Mock()
        wp.ap.jn.ship_state.return_value = {
            "cur_station": "Test Station",
            "cur_station_type": "Coriolis",
            "StationServices": ["commodities"],
            "cargo_capacity": 16,
        }
        wp.market_parser = mock.Mock()
        wp.market_parser.get_market_data.return_value = {"timestamp": "old"}
        wp.market_parser.current_data = {"timestamp": "old"}
        wp.ap.status.get_cleaned_data.side_effect = [{"Cargo": 0}, {"Cargo": 2}]
        wp.ap.status.current_data = {"timestamp": "before"}
        wp.ap.status.wait_for_file_change.return_value = True
        wp.ap.stn_svcs_in_ship.buy_commodity.return_value = (True, 2)

        with (
            mock.patch.object(wp, "_wait_for_market_update", return_value=True),
            mock.patch.object(wp, "_confirmed_trade", return_value=(True, 2)) as confirm,
            mock.patch("routines.waypoints.sleep"),
            self.assertLogs("ed_log", level="DEBUG") as logs,
        ):
            self.assertTrue(wp.execute_trade(wp.ap, "1"))

        confirm.assert_called_once()
        self.assertEqual(confirm.call_args.args, (wp.ap, "MarketBuy", "128049197", 2, 16))
        self.assertTrue(callable(confirm.call_args.kwargs["recover_trade_dialog"]))
        self.assertEqual(wp.waypoints["1"]["BuyCommodities"], {"128049197": 0})
        self.assertTrue(any("confirmed_qty=2 cargo_before=0" in line for line in logs.output))
        self.assertTrue(any("status_updated=True cargo_after=2" in line for line in logs.output))
        self.assertFalse(any(":INFO:" in line for line in logs.output))

    def test_market_timeout_prevents_buying_and_reports_failure(self):
        wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol", BuyCommodities={"128049197": 2})})
        wp.ap = mock.Mock()
        wp.ap.jn.ship_state.return_value = {
            "cur_station": "Test Station",
            "cur_station_type": "Coriolis",
            "StationServices": ["commodities"],
        }
        wp.market_parser = mock.Mock()
        wp.market_parser.current_data = {"timestamp": "old"}
        with mock.patch.object(wp, "_wait_for_market_update", return_value=False):
            self.assertFalse(wp.execute_trade(wp.ap, "1"))

        wp.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        wp.ap.ship_control.goto_cockpit_view.assert_called_once()
        wp.ap.ap_ckb.assert_any_call("log", "Timed out waiting for market data. Waypoint Assist stopped.")
        self.assertEqual(wp.waypoints["1"]["BuyCommodities"], {"128049197": 2})


class TradeConfirmationTestCase(unittest.TestCase):
    def setUp(self):
        self.wp = new_waypoints({"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol", BuyCommodities={"128049197": 2})})
        self.ap = self.wp.ap = mock.Mock()
        self.ap.jn.ship_state.return_value = {
            "cur_station": "Test Station",
            "cur_station_type": "Coriolis",
            "StationServices": ["commodities"],
            "cargo_capacity": 16,
        }
        self.wp.market_parser = mock.Mock()
        market_item = {
            "id": 128049197,
            "Name": "$polymers_name;",
            "Name_Localised": "Polymere",
        }
        market_data = {
            "timestamp": "old",
            "MarketID": 42,
            "Items": [market_item],
        }
        self.wp.market_parser.current_data = market_data
        self.wp.market_parser.get_market_data.return_value = market_data
        self.wp.market_parser.get_item.return_value = market_item
        self.ap.jn.market_transaction_cursor.return_value = 10
        self.event = {"event": "MarketBuy", "MarketID": 42, "Type": "polymers", "Count": 2}
        self.ap.jn.market_transactions_since.return_value = [self.event]
        self.ap.stn_svcs_in_ship.buy_commodity.return_value = (True, 2)
        self.ap.stn_svcs_in_ship.sell_commodity.return_value = (True, 2)
        self.ap.status.get_cleaned_data.return_value = {"Cargo": 0}
        self.ap.status.current_data = {"timestamp": "before"}
        for patcher in (
            mock.patch("routines.waypoints.sleep"),
            mock.patch.object(self.wp, "_wait_for_market_update", return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_localized_buy_uses_internal_commodity_and_fresh_cursor(self):
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 2, 16), (True, 2))
        self.ap.jn.market_transactions_since.assert_called_once_with(10)
        self.ap.stn_svcs_in_ship.buy_commodity.assert_called_once_with(self.ap.keys, "128049197", 2, 16)

    def test_unconfirmed_dialog_recovers_once_before_retrying(self):
        self.ap.stn_svcs_in_ship.buy_commodity.side_effect = [
            TradeDialogUnconfirmedError("Polymere"),
            (True, 2),
        ]
        recover = mock.Mock(return_value=True)

        self.assertEqual(
            self.wp._confirmed_trade(
                self.ap,
                "MarketBuy",
                "128049197",
                2,
                16,
                recover_trade_dialog=recover,
            ),
            (True, 2),
        )

        recover.assert_called_once_with("old", "MarketBuy")
        self.assertEqual(self.ap.stn_svcs_in_ship.buy_commodity.call_count, 2)
        self.ap.jn.market_transaction_cursor.assert_called()

    def test_unconfirmed_dialog_stops_when_recovery_cannot_be_confirmed(self):
        self.ap.stn_svcs_in_ship.buy_commodity.side_effect = TradeDialogUnconfirmedError("Polymere")
        recover = mock.Mock(return_value=False)

        self.assertEqual(
            self.wp._confirmed_trade(
                self.ap,
                "MarketBuy",
                "128049197",
                2,
                16,
                recover_trade_dialog=recover,
            ),
            (False, 0),
        )

        recover.assert_called_once_with("old", "MarketBuy")
        self.ap.stn_svcs_in_ship.buy_commodity.assert_called_once()
        self.ap.jn.market_transaction_cursor.assert_called_once()

    def test_second_unconfirmed_dialog_stops_without_a_third_attempt(self):
        self.ap.stn_svcs_in_ship.buy_commodity.side_effect = TradeDialogUnconfirmedError("Polymere")
        recover = mock.Mock(return_value=True)

        self.assertEqual(
            self.wp._confirmed_trade(
                self.ap,
                "MarketBuy",
                "128049197",
                2,
                16,
                recover_trade_dialog=recover,
            ),
            (False, 0),
        )

        recover.assert_called_once_with("old", "MarketBuy")
        self.assertEqual(self.ap.stn_svcs_in_ship.buy_commodity.call_count, 2)
        self.ap.jn.market_transaction_cursor.assert_called()

    def test_recovery_returns_to_cockpit_and_reopens_correct_trade_list(self):
        with mock.patch.object(self.wp, "_open_station_market", return_value=True) as open_market:
            self.assertTrue(self.wp._recover_trade_dialog(self.ap, "MarketSell", False, True, "old"))

        self.ap.ship_control.goto_cockpit_view.assert_called_once_with(timeout=10.0)
        open_market.assert_called_once_with(
            self.ap,
            False,
            True,
            "old",
            cockpit_timeout=10.0,
        )
        self.ap.stn_svcs_in_ship.select_sell.assert_called_once_with(self.ap.keys)

    def test_fleet_carrier_transfer_requires_all_sentinel_and_aborts_when_unconfirmed(self):
        state = self.ap.jn.ship_state.return_value
        state["cur_station_type"] = "FleetCarrier"
        state["cur_station"] = "ABC-123"
        self.wp.waypoints["1"]["FleetCarrierTransfer"] = True
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["1"]["SellCommodities"] = {"All": 0}
        self.ap.internal_panel.transfer_to_fleetcarrier.return_value = False

        self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.ap.internal_panel.transfer_to_fleetcarrier.assert_called_once_with(self.ap)

    def test_fleet_carrier_id_buy_list_is_explicitly_unsupported(self):
        state = self.ap.jn.ship_state.return_value
        state["cur_station_type"] = "FleetCarrier"
        state["cur_station"] = "ABC-123"
        self.wp.waypoints["1"]["FleetCarrierTransfer"] = True

        self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.ap.internal_panel.transfer_from_fleetcarrier.assert_not_called()
        self.ap.keys.send.assert_not_called()

    def test_construction_all_sentinel_transfers_cargo(self):
        state = self.ap.jn.ship_state.return_value
        state["cur_station_type"] = "SurfaceStation"
        state["cur_station"] = "System Colonisation Ship"
        self.wp.waypoints["1"]["SellCommodities"] = {"All": 0}
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.sell_to_colonisation_ship = mock.Mock()

        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.wp.sell_to_colonisation_ship.assert_called_once_with(self.ap)

    def test_trade_priority_follows_each_list_order_and_keeps_sell_phase_first(self):
        self.wp.waypoints["1"]["SellCommodities"] = {"128049155": 2, "128049154": 2}
        self.wp.waypoints["1"]["BuyCommodities"] = {"128049166": 2, "128049197": 2}
        self.wp.waypoints["GlobalShoppingList"] = {
            **GLOBAL_LIST,
            "Enabled": True,
            "BuyCommodities": {"128049152": 2, "128049188": 2},
        }
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
        with (
            mock.patch.object(self.wp, "_confirmed_trade", return_value=(True, 2)) as trade,
            mock.patch.object(self.wp, "save_waypoints", return_value=True),
        ):
            self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(
            [(call.args[1], call.args[2]) for call in trade.call_args_list],
            [
                ("MarketSell", "128049155"),
                ("MarketSell", "128049154"),
                ("MarketBuy", "128049166"),
                ("MarketBuy", "128049197"),
                ("MarketBuy", "128049152"),
                ("MarketBuy", "128049188"),
            ],
        )

    def test_missing_or_unavailable_market_does_not_report_success(self):
        for services in (None, [], ["dock", "refuel"]):
            with self.subTest(services=services):
                self.ap.jn.ship_state.return_value["StationServices"] = services
                self.assertFalse(self.wp.execute_trade(self.ap, "1"))
                self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 2})
                self.wp.save_waypoints.assert_not_called()
                self.ap.stn_svcs_in_ship.goto_station_services.assert_not_called()

    def test_missing_services_aborts_full_route_without_completing_waypoint(self):
        state = self.ap.jn.ship_state.return_value
        state.update(
            StationServices=None,
            cur_star_system="Sol",
            cur_station="Sol Station",
        )
        self.ap.status.get_cleaned_data.return_value = {"Destination_Body": 0, "Destination_Name": ""}
        self.ap.status.get_flag.return_value = True

        self.wp.waypoint_assist(self.ap.keys, mock.Mock())

        self.assertFalse(self.wp.waypoints["1"]["Completed"])
        self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 2})
        self.wp.save_waypoints.assert_not_called()
        self.ap.ap_ckb.assert_any_call("log+vce", "Waypoint Route was aborted.")
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        self.assertFalse(self.wp.executing)

    def test_startup_location_services_allow_confirmed_trade(self):
        from tests.test_journal import new_journal

        journal = new_journal()
        journal.parse_line(
            {
                "event": "Location",
                "StarSystem": "Sol",
                "StationName": "Sol Station",
                "StationType": "Coriolis",
                "Docked": True,
                "StationServices": ["dock", "commodities"],
            }
        )
        journal.ship["cargo_capacity"] = 16
        self.ap.jn.ship_state.return_value = journal.ship
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.buy_commodity.assert_called_once()
        self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 0})

    def test_confirmation_waits_past_unrelated_events(self):
        unrelated = [
            {**self.event, "MarketID": 99},
            {**self.event, "Type": "gold"},
            {**self.event, "event": "MarketSell"},
        ]
        self.ap.jn.market_transactions_since.side_effect = [unrelated, unrelated + [self.event]]
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 2, 16), (True, 2))
        self.assertEqual(self.ap.jn.market_transactions_since.call_count, 2)

    def test_sell_is_confirmed_and_saved_before_next_input(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["1"]["SellCommodities"] = {"128049197": 2}
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
        self.event["event"] = "MarketSell"
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 0})
        self.wp.save_waypoints.assert_called()

    def test_partial_confirmation_only_decrements_actual_quantity(self):
        self.event["Count"] = 1
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 1})

    def test_global_buy_also_requires_confirmation(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["GlobalShoppingList"]["BuyCommodities"] = {"128049197": 2}
        self.wp.waypoints["GlobalShoppingList"]["Enabled"] = True
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["GlobalShoppingList"]["BuyCommodities"], {"128049197": 0})

    def test_skipped_global_list_sends_no_trade_inputs(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["GlobalShoppingList"]["BuyCommodities"] = {"128049197": 2}
        self.wp.waypoints["GlobalShoppingList"]["Enabled"] = False
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        self.ap.stn_svcs_in_ship.goto_station_services.assert_not_called()

    def test_missing_confirmation_stops_without_changing_progress(self):
        self.ap.jn.market_transactions_since.return_value = []
        with mock.patch("routines.waypoints.time.monotonic", side_effect=[100, 101, 111]):
            self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 2})
        self.wp.save_waypoints.assert_not_called()
        self.ap.ship_control.goto_cockpit_view.assert_called_once()

    def test_invalid_confirmation_count_is_rejected(self):
        for count in (0, -1, 3, True, "2"):
            with self.subTest(count=count):
                self.event["Count"] = count
                self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 2, 16), (False, 0))

    def test_zero_remaining_quantity_sends_no_inputs(self):
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 0, 16), (True, 0))
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        self.ap.jn.market_transaction_cursor.assert_not_called()

    def test_station_timeout_prevents_market_navigation_and_trading(self):
        self.ap.stn_svcs_in_ship.goto_station_services.return_value = False
        self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.ap.keys.send.assert_not_called()
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        self.wp.save_waypoints.assert_not_called()

    def test_save_failure_stops_before_status_wait(self):
        self.wp.save_waypoints.return_value = False
        self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.ap.status.wait_for_file_change.assert_not_called()

    def test_confirmed_buy_is_saved_before_waiting_for_cargo_status(self):
        def wait_for_status(*args):
            self.wp.save_waypoints.assert_called_once()
            self.assertEqual(self.wp.waypoints["1"]["BuyCommodities"], {"128049197": 0})

        self.ap.status.wait_for_file_change.side_effect = wait_for_status
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))

    def test_failed_second_buy_preserves_first_confirmed_transaction(self):
        self.wp.waypoints["1"]["BuyCommodities"]["128049154"] = 1
        saved = []
        self.wp.save_waypoints.side_effect = lambda: saved.append(copy.deepcopy(self.wp.waypoints)) or True
        with mock.patch.object(self.wp, "_confirmed_trade", side_effect=[(True, 2), (False, 0)]):
            self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["1"]["BuyCommodities"], {"128049197": 0, "128049154": 1})

    def test_failed_sell_confirmation_does_not_change_remaining_quantity(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["1"]["SellCommodities"] = {"128049197": 2}
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
        with mock.patch.object(self.wp, "_confirmed_trade", return_value=(False, 0)):
            self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 2})
        self.wp.save_waypoints.assert_not_called()

    def test_missing_cargo_skips_sale_but_still_buys_and_preserves_sell_request(self):
        self.wp.waypoints["1"]["SellCommodities"] = {"128049155": 3}
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = None
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.sell_commodity.assert_not_called()
        self.ap.stn_svcs_in_ship.buy_commodity.assert_called_once()
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049155": 3})
        self.wp.cargo_parser.get_cargo_data.assert_called_once_with(force=True)

    def test_sale_is_limited_to_cargo_and_decrements_only_confirmation(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["1"]["SellCommodities"] = {"128049197": 5}
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
        self.event["event"] = "MarketSell"
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.sell_commodity.assert_called_once_with(
            self.ap.keys, "128049197", 2, self.wp.cargo_parser
        )
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 3})

    def test_zero_cargo_skips_sale_without_confirmation_or_progress_change(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["1"]["SellCommodities"] = {"128049197": 5}
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 0}
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.sell_commodity.assert_not_called()
        self.wp.save_waypoints.assert_not_called()
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 5})

    def test_cargo_read_failure_aborts_without_sale_or_buy(self):
        self.wp.waypoints["1"]["SellCommodities"] = {"128049197": 5}
        for error in (OSError("unreadable"), ValueError("invalid inventory")):
            with self.subTest(error=error):
                self.wp.cargo_parser = mock.Mock()
                self.wp.cargo_parser.get_cargo_data.side_effect = error
                self.assertFalse(self.wp.execute_trade(self.ap, "1"))
                self.ap.stn_svcs_in_ship.sell_commodity.assert_not_called()
                self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
                self.wp.save_waypoints.assert_not_called()

    def test_partial_sale_with_count_updates_disabled_preserves_definition(self):
        self.wp.waypoints["1"].update(BuyCommodities={}, SellCommodities={"128049197": 5}, UpdateCommodityCount=False)
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
        self.event["event"] = "MarketSell"
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 5})
        self.wp.save_waypoints.assert_not_called()
        self.wp.cargo_parser.wait_for_quantity.assert_called_once_with("128049197", 0)

    def test_cargo_sync_failure_preserves_confirmed_sale_and_blocks_further_trades(self):
        for failure in (False, OSError("unreadable"), ValueError("invalid cargo")):
            with self.subTest(failure=failure):
                self.wp.waypoints["1"].update(
                    BuyCommodities={"128049197": 2},
                    SellCommodities={"128049197": 2, "128049199": 1},
                )
                self.wp.cargo_parser = mock.Mock()
                self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 2}
                if isinstance(failure, Exception):
                    self.wp.cargo_parser.wait_for_quantity.side_effect = failure
                else:
                    self.wp.cargo_parser.wait_for_quantity.return_value = failure
                self.wp.save_waypoints = mock.Mock(return_value=True)
                with mock.patch.object(self.wp, "_confirmed_trade", return_value=(True, 2)) as trade:
                    self.assertFalse(self.wp.execute_trade(self.ap, "1"))
                self.assertEqual(trade.call_count, 1)
                self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 0, "128049199": 1})
                self.wp.save_waypoints.assert_called_once()
                self.wp.cargo_parser.wait_for_quantity.assert_called_once_with("128049197", 0)
                self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()

    def test_two_sales_wait_for_cargo_between_confirmed_transactions(self):
        self.wp.waypoints["1"].update(BuyCommodities={}, SellCommodities={"128049197": 1, "128049199": 1})
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 1}
        events = []
        self.wp.cargo_parser.wait_for_quantity.side_effect = lambda key, expected: (
            events.append(("cargo", key, expected)) or True
        )
        with mock.patch.object(
            self.wp,
            "_confirmed_trade",
            side_effect=lambda ap, event, key, quantity, *args, **kwargs: events.append(("sale", key)) or (True, 1),
        ):
            self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(
            events,
            [
                ("sale", "128049197"),
                ("cargo", "128049197", 0),
                ("sale", "128049199"),
                ("cargo", "128049199", 0),
            ],
        )

    def test_sell_all_uses_actual_inventory_for_confirmation_limit(self):
        self.wp.waypoints["1"].update(BuyCommodities={}, SellCommodities={"128049197": 9999})
        self.wp.cargo_parser = mock.Mock()
        self.wp.cargo_parser.get_item_by_commodity_id.return_value = {"Count": 4}
        self.event.update(event="MarketSell", Count=4)
        self.ap.stn_svcs_in_ship.sell_commodity.return_value = (True, 4)
        self.assertTrue(self.wp.execute_trade(self.ap, "1"))
        self.ap.stn_svcs_in_ship.sell_commodity.assert_called_once_with(
            self.ap.keys, "128049197", 4, self.wp.cargo_parser
        )
        self.assertEqual(self.wp.waypoints["1"]["SellCommodities"], {"128049197": 9995})

    def test_failed_global_confirmation_does_not_change_remaining_quantity(self):
        self.wp.waypoints["1"]["BuyCommodities"] = {}
        self.wp.waypoints["GlobalShoppingList"]["BuyCommodities"] = {"128049197": 2}
        self.wp.waypoints["GlobalShoppingList"]["Enabled"] = True
        with mock.patch.object(self.wp, "_confirmed_trade", return_value=(False, 0)):
            self.assertFalse(self.wp.execute_trade(self.ap, "1"))
        self.assertEqual(self.wp.waypoints["GlobalShoppingList"]["BuyCommodities"], {"128049197": 2})
        self.wp.save_waypoints.assert_not_called()

    def test_unknown_commodity_aborts_before_sending_trade_inputs(self):
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "999999999", 2, 16), (False, 0))
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()

    def test_market_name_match_without_id_match_aborts_before_trade(self):
        self.wp.market_parser.get_item.return_value = None
        self.wp.market_parser.current_data["Items"] = [{"id": 128049198, "Name_Localised": "Polymere"}]
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 2, 16), (False, 0))
        self.ap.stn_svcs_in_ship.buy_commodity.assert_not_called()
        self.ap.jn.market_transaction_cursor.assert_not_called()

    def test_failed_trade_input_does_not_wait_for_confirmation(self):
        self.ap.stn_svcs_in_ship.buy_commodity.return_value = (False, 0)
        self.assertEqual(self.wp._confirmed_trade(self.ap, "MarketBuy", "128049197", 2, 16), (False, 0))
        self.ap.jn.market_transactions_since.assert_not_called()


if __name__ == "__main__":
    unittest.main()

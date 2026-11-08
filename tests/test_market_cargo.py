"""Tests for the Market.json, Cargo.json and NavRoute.json parsers."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.commodities import load_catalogue
from game.cargo import CargoParser
from game.market import MarketParser
from game.nav_route import NavRouteParser
from tests.helpers import write_json

COMMODITY_IDS = {item["symbol"]: commodity_id for commodity_id, item in load_catalogue().items()}


def market_item(name, category, **values):
    item = {
        "id": COMMODITY_IDS.get(
            {
                "Gold": "Gold",
                "Silver": "Silver",
                "Water": "Water",
                "Bertrandite": "Bertrandite",
                "Eranin Pearl Whisky": "EraninPearlWhisky",
            }.get(name, ""),
            999999999,
        ),
        "Name": f"${name.lower()}_name;",
        "Name_Localised": name,
        "Category_Localised": category,
        "BuyPrice": 0,
        "SellPrice": 0,
        "Stock": 0,
        "Demand": 0,
        "Consumer": False,
        "Producer": False,
        "Rare": False,
    }
    item.update(values)
    return item


MARKET = {
    "event": "Market",
    "StationName": "Test Station",
    "Items": [
        market_item("Gold", "Metals", Stock=89, Producer=True),
        market_item("Silver", "Metals", Stock=0, Producer=True),
        market_item("Water", "Chemicals", Demand=50, Consumer=True),
        market_item("Eranin Pearl Whisky", "Rare", Stock=3, Rare=True),
        market_item("Bertrandite", "Minerals", Demand=1),
    ],
}

CARGO = {
    "event": "Cargo",
    "Count": 1237,
    "Inventory": [
        {"Name": "cmmcomposite", "Name_Localised": "CMM Composite", "Count": 1236, "Stolen": 0},
        {"Name": "water", "Count": 1, "Stolen": 0},
    ],
}


class TempFileTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = Path(self._dir.name)


class MarketParserTestCase(TempFileTestCase):
    def setUp(self):
        super().setUp()
        self.parser = MarketParser(file_path=str(write_json(self.dir / "Market.json", MARKET)))

    def test_market_name(self):
        self.assertEqual(self.parser.get_market_name(), "Test Station")

    def test_missing_file_gives_no_data(self):
        parser = MarketParser(file_path=str(self.dir / "Missing.json"))

        self.assertIsNone(parser.get_market_data())
        self.assertEqual(parser.get_market_name(), "")
        self.assertIsNone(parser.get_buyable_items())
        self.assertFalse(parser.can_buy_item("Gold"))

    def test_get_item_uses_commodity_id(self):
        self.assertEqual(self.parser.get_item("128049154")["Stock"], 89)
        self.assertIsNone(self.parser.get_item("Gold"))

    def test_duplicate_market_identity_is_not_selected_arbitrarily(self):
        self.parser.current_data["Items"].append(dict(self.parser.current_data["Items"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parser.get_item("128049154")

    def test_can_buy_item(self):
        self.assertTrue(self.parser.can_buy_item("128049154"))
        self.assertFalse(self.parser.can_buy_item("128049155"))  # no stock
        self.assertFalse(self.parser.can_buy_item("128049166"))  # not a producer
        self.assertTrue(self.parser.can_buy_item("128666746"))
        self.assertFalse(self.parser.can_buy_item("999999999"))

    def test_can_sell_item(self):
        self.assertTrue(self.parser.can_sell_item("128049166"))
        self.assertTrue(self.parser.can_sell_item("128666746"))
        self.assertTrue(self.parser.can_sell_item("128049156"))  # demand only
        self.assertFalse(self.parser.can_sell_item("128049154"))
        self.assertFalse(self.parser.can_sell_item("999999999"))

    def test_buyable_items_sorted_by_category_then_name(self):
        names = [item["Name_Localised"] for item in self.parser.get_buyable_items()]

        self.assertEqual(names, ["Gold", "Eranin Pearl Whisky"])

    def test_sellable_items_use_cargo(self):
        cargo = CargoParser(file_path=str(write_json(self.dir / "Cargo.json", {"Inventory": []})))

        names = [item["Name_Localised"] for item in self.parser.get_sellable_items(cargo)]

        # Only consumers qualify when nothing is in the hold
        self.assertEqual(names, ["Water"])

    def test_empty_cargo_entry_does_not_shift_the_sell_list(self):
        cargo = CargoParser(
            file_path=str(
                write_json(
                    self.dir / "Cargo.json",
                    {"Inventory": [{"Name": "bertrandite", "Count": 0}]},
                )
            )
        )
        names = [item["Name_Localised"] for item in self.parser.get_sellable_items(cargo)]
        self.assertEqual(names, ["Water"])

    def test_rare_cargo_with_no_demand_is_in_the_sell_list(self):
        self.parser.current_data["Items"].append(
            market_item("Soontill Relics", "Consumer items", id=128668018, Rare=True)
        )
        for count in (70, 0):
            with self.subTest(count=count):
                cargo = CargoParser(
                    file_path=str(
                        write_json(
                            self.dir / "Cargo.json",
                            {"Inventory": [{"Name": "soontillrelics", "Count": count}]},
                        )
                    )
                )
                self.assertTrue(self.parser.can_sell_item("128668018"))
                names = [item["Name_Localised"] for item in self.parser.get_sellable_items(cargo)]
                self.assertEqual(names, ["Water", "Soontill Relics"] if count else ["Water"])

    def test_delayed_sale_snapshot_removes_row_before_selecting_next_commodity(self):
        self.parser.current_data["Items"] = [
            market_item("Polymers", "Industrial materials", id=128049197, Demand=1),
            market_item("Semiconductors", "Industrial materials", id=128049199, Demand=1),
            market_item("Superconductors", "Industrial materials", id=128049200, Consumer=True, Demand=100),
        ]
        filename = self.dir / "Cargo.json"
        cargo = CargoParser(
            file_path=str(
                write_json(
                    filename,
                    {
                        "Inventory": [
                            {"Name": "polymers", "Count": 1},
                            {"Name": "semiconductors", "Count": 1},
                        ]
                    },
                )
            )
        )
        self.assertEqual(
            [row["Name_Localised"] for row in self.parser.get_sellable_items(cargo)],
            ["Polymers", "Semiconductors", "Superconductors"],
        )
        with mock.patch(
            "game.cargo.sleep",
            side_effect=lambda _delay: write_json(filename, {"Inventory": [{"Name": "semiconductors", "Count": 1}]}),
        ):
            self.assertTrue(cargo.wait_for_quantity("128049197", 0))
        self.assertEqual(
            [row["Name_Localised"] for row in self.parser.get_sellable_items(cargo)],
            ["Semiconductors", "Superconductors"],
        )


class CargoParserTestCase(TempFileTestCase):
    def setUp(self):
        super().setUp()
        self.parser = CargoParser(file_path=str(write_json(self.dir / "Cargo.json", CARGO)))

    def test_get_item_by_internal_and_localised_name(self):
        self.assertEqual(self.parser.get_item("cmmcomposite")["Count"], 1236)
        self.assertEqual(self.parser.get_item("CMM composite")["Count"], 1236)
        self.assertEqual(self.parser.get_item("WATER")["Count"], 1)

    def test_get_item_not_in_hold(self):
        self.assertIsNone(self.parser.get_item("gold"))

    def test_get_item_by_commodity_id_uses_catalogue_symbol(self):
        self.assertEqual(self.parser.get_item_by_commodity_id("128673856")["Count"], 1236)
        self.assertIsNone(self.parser.get_item_by_commodity_id("999999999"))

    def test_localized_name_cannot_impersonate_another_commodity_symbol(self):
        self.parser.current_data["Inventory"].insert(
            0, {"Name": "gold", "Name_Localised": "water", "Count": 20, "Stolen": 0}
        )
        self.assertEqual(self.parser.get_item_by_commodity_id("128049166")["Count"], 1)

    def test_duplicate_cargo_identity_is_not_selected_arbitrarily(self):
        self.parser.current_data["Inventory"].append(dict(self.parser.current_data["Inventory"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parser.get_item_by_commodity_id("128673856")

    def test_reads_changed_file(self):
        write_json(self.dir / "Cargo.json", {"Inventory": []})

        self.assertEqual(self.parser.get_cargo_data()["Inventory"], [])

    def test_forced_read_does_not_use_cached_inventory(self):
        write_json(self.dir / "Cargo.json", {"Inventory": []})
        with mock.patch.object(self.parser, "get_file_modified_time", return_value=self.parser.last_mod_time):
            self.assertEqual(self.parser.get_cargo_data(force=True)["Inventory"], [])

    def test_wait_for_quantity_reloads_delayed_cargo_even_with_unchanged_mtime(self):
        def update_inventory(_delay):
            write_json(self.dir / "Cargo.json", {"Inventory": []})

        with (
            mock.patch.object(self.parser, "get_file_modified_time", return_value=self.parser.last_mod_time),
            mock.patch("game.cargo.sleep", side_effect=update_inventory) as sleep,
        ):
            self.assertTrue(self.parser.wait_for_quantity("128049166", 0))
        sleep.assert_called_once_with(0.2)
        self.assertIsNone(self.parser.get_item_by_commodity_id("128049166"))

    def test_wait_for_quantity_times_out_without_changing_cargo(self):
        with self.assertLogs("ed_log", level="WARNING"):
            self.assertFalse(self.parser.wait_for_quantity("128049166", 0, timeout=0))
        self.assertEqual(self.parser.get_item_by_commodity_id("128049166")["Count"], 1)

    def test_wait_for_quantity_accepts_confirmed_partial_sale(self):
        self.assertTrue(self.parser.wait_for_quantity("128049166", 1, timeout=0))

    def test_invalid_or_unreadable_cargo_fails_after_bounded_retries(self):
        for payload in (
            "{",
            '{"Inventory": null}',
            '{"Inventory": [{"Name": "Gold", "Count": true}]}',
            '{"Vessel": "SRV", "Inventory": []}',
        ):
            with self.subTest(payload=payload):
                (self.dir / "Cargo.json").write_text(payload)
                with mock.patch("game.cargo.sleep") as sleep:
                    with self.assertRaises(ValueError):
                        self.parser.get_cargo_data(force=True)
                    self.assertEqual(sleep.call_count, 2)
        (self.dir / "Cargo.json").unlink()
        with mock.patch("game.cargo.sleep") as sleep:
            with self.assertRaises(OSError):
                self.parser.get_cargo_data(force=True)
            self.assertEqual(sleep.call_count, 2)


class NavRouteParserTestCase(TempFileTestCase):
    def test_next_system_follows_current_location_not_route_start(self):
        route = {
            "event": "NavRoute",
            "Route": [
                {"StarSystem": "LHS 20", "SystemAddress": 1},
                {"StarSystem": "Intermediate", "SystemAddress": 2},
                {"StarSystem": "Arima", "SystemAddress": 3},
            ],
        }
        parser = NavRouteParser(file_path=str(write_json(self.dir / "NavRoute.json", route)))

        self.assertEqual(parser.get_next_system("lhs 20", 1), ("Intermediate", 2))
        self.assertEqual(parser.get_next_system("Intermediate", 2), ("Arima", 3))
        self.assertEqual(parser.get_next_system("LHS 20"), ("Intermediate", 2))
        self.assertIsNone(parser.get_next_system("Arima", 3))
        self.assertIsNone(parser.get_next_system("Off route", 4))
        self.assertIsNone(parser.get_next_system("LHS 20", 4))

    def test_next_system_requires_valid_name_and_address(self):
        for next_system in (None, {}, {"StarSystem": "Arima"}, {"StarSystem": "Arima", "SystemAddress": True}):
            with self.subTest(next_system=next_system):
                route = {
                    "event": "NavRoute",
                    "Route": [{"StarSystem": "LHS 20", "SystemAddress": 1}, next_system],
                }
                parser = NavRouteParser(file_path=str(write_json(self.dir / "NavRoute.json", route)))
                self.assertIsNone(parser.get_next_system("LHS 20", 1))

    def test_missing_route_file_returns_a_cleared_route(self):
        parser = NavRouteParser(file_path=str(self.dir / "Missing.json"))

        self.assertEqual(parser.get_nav_route_data(), {"event": "NavRouteClear", "Route": []})

    def test_last_system_of_route(self):
        route = {"event": "NavRoute", "Route": [{"StarSystem": "Leesti"}, {"StarSystem": "Devataru"}]}
        parser = NavRouteParser(file_path=str(write_json(self.dir / "NavRoute.json", route)))

        self.assertEqual(parser.get_last_system(), "Devataru")

    def test_cleared_route(self):
        parser = NavRouteParser(
            file_path=str(write_json(self.dir / "NavRoute.json", {"event": "NavRouteClear", "Route": []}))
        )

        self.assertEqual(parser.get_last_system(), "")

    def test_route_change_is_detected(self):
        path = write_json(self.dir / "NavRoute.json", {"event": "NavRoute", "Route": [{"StarSystem": "A"}]})
        parser = NavRouteParser(file_path=str(path))
        self.assertEqual(parser.get_last_system(), "A")

        write_json(path, {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]})

        self.assertEqual(parser.get_last_system(), "B")

    def test_invalid_route_update_keeps_the_last_valid_route(self):
        path = write_json(
            self.dir / "NavRoute.json",
            {"event": "NavRoute", "Route": [{"StarSystem": "A"}, {"StarSystem": "B"}]},
        )
        parser = NavRouteParser(file_path=str(path))
        path.write_text("{", encoding="utf-8")

        self.assertEqual(parser.get_nav_route_data()["Route"][-1]["StarSystem"], "B")


if __name__ == "__main__":
    unittest.main()

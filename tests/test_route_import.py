"""Copied trade-result parsing and draft creation."""

import json
import re
import unittest

from gui.commodity_catalogue import load_catalogue
from gui.route_import import clean_line, imported_waypoints, parse_spansh_export, parse_trade_route, resolve_commodities

REVERSED = """Nach [Ohm City | LHS 20](https://inara.cz/elite/station-market/22700/)\ue84f\ufe0e
\ue81d\ufe0e
Von [Fermat's Folly | Core Sys Sector YO-R a4-1](https://inara.cz/elite/station-market/705333/)
Entfernung der Station
1.157 Ls
Verkauf
[Silber](https://inara.cz/elite/commodity/46/)
Verkaufspreis
48.815 Cr | +15.389 Cr (46%)
Nachfrage
42.367
Entfernung der Station
2 Ls
Kauf
[Silber](https://inara.cz/elite/commodity/46/)
Kaufpreis
33.426 Cr
Auf Lager
9.795
"""

ONE_WAY = """Von [Ohm City | LHS 20](https://inara.cz/elite/station-market/22700/)
Nach [Rota Obscura | WISE 0359-5401](https://inara.cz/elite/station-market/667420/)
Entfernung der Station
1.157 Ls
Kauf
[Polymere](https://inara.cz/elite/commodity/26/)
Kaufpreis
63 Cr
Auf Lager
31.167
Entfernung der Station
3.689 Ls
Verkauf
[Polymere](https://inara.cz/elite/commodity/26/)
Verkaufspreis
9.332 Cr | +9.269 Cr (14.712%)
Nachfrage
6.902.478
"""

ROUND_TRIP = """Von [Ohm City | LHS 20](https://inara.cz/elite/station-market/22700/)
Nach [Bosch City | LHS 1339](https://inara.cz/elite/station-market/5661/)
Entfernung der Station
1.157 Ls
Kauf
[Nichttödliche Waffen](https://inara.cz/elite/commodity/78/)
Kaufpreis
1.437 Cr
Auf Lager
102.344
Verkauf
[Silber](https://inara.cz/elite/commodity/46/)
Verkaufspreis
48.815 Cr | +8.388 Cr (20%)
Nachfrage
42.367
Entfernung der Station
2.017 Ls
Verkauf
[Nichttödliche Waffen](https://inara.cz/elite/commodity/78/)
Verkaufspreis
5.111 Cr | +3.674 Cr (255%)
Nachfrage
7.801
Kauf
[Silber](https://inara.cz/elite/commodity/46/)
Kaufpreis
40.427 Cr
Auf Lager
2.358
"""


class RouteImportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue, _verified = load_catalogue()

    def entries(self, text, repeat=False, language="de"):
        route = parse_trade_route(text)
        resolved = resolve_commodities(route, self.catalogue, language)
        return imported_waypoints(route, resolved, {item[0]: 7 for item in resolved.values()})

    def test_reverse_endpoint_order_still_buys_at_origin(self):
        origin, destination = self.entries(REVERSED)
        self.assertEqual(origin["StationName"], "Fermat's Folly")
        self.assertEqual(origin["SystemName"], "Core Sys Sector YO-R a4-1")
        self.assertEqual(origin["BuyCommodities"], {"128049155": 7})
        self.assertEqual(origin["SellCommodities"], {})
        self.assertEqual(destination["StationName"], "Ohm City")
        self.assertEqual(destination["SellCommodities"], {"128049155": 7})

    def test_forward_one_way_and_localized_commodity(self):
        origin, destination = self.entries(ONE_WAY, language="en")
        self.assertEqual(origin["BuyCommodities"], {"128049197": 7})
        self.assertEqual(destination["SellCommodities"], {"128049197": 7})
        self.assertEqual(destination["SystemName"], "WISE 0359-5401")
        self.assertEqual(origin["GalaxyBookmarkNumber"], 0)
        self.assertEqual(origin["SystemBookmarkType"], "")

    def test_browser_copy_with_inline_values_matches_multiline_results(self):
        for original in (REVERSED, ONE_WAY, ROUND_TRIP):
            plain = "\n".join(clean_line(line) for line in original.splitlines())
            for language in ("de", "en"):
                text = plain
                if language == "en":
                    for german, english in (
                        ("Entfernung der Station", "Station distance"),
                        ("Verkaufspreis", "Sell price"),
                        ("Kaufpreis", "Buy price"),
                        ("Verkauf", "Sell"),
                        ("Kauf", "Buy"),
                        ("Auf Lager", "Supply"),
                        ("Nachfrage", "Demand"),
                        ("Von ", "From "),
                        ("Nach ", "To "),
                    ):
                        text = text.replace(german, english)
                text = re.sub(
                    r"(?m)^(Entfernung der Station|Station distance|Kauf|Verkauf|Buy|Sell|"
                    r"Kaufpreis|Verkaufspreis|Buy price|Sell price|Auf Lager|Nachfrage|Supply|Demand)\n",
                    r"\1\t",
                    text,
                )
                with self.subTest(route=original[:40], language=language):
                    self.assertEqual(parse_trade_route(text), parse_trade_route(original))
                    entries = self.entries(text)
                    self.assertEqual(len(entries), 2)

    def test_round_trip_has_per_commodity_quantities_and_optional_repeat(self):
        route = parse_trade_route(ROUND_TRIP)
        resolved = resolve_commodities(route, self.catalogue, "de")
        quantities = {commodity_id: 3 if name == "Silber" else 8 for commodity_id, name in resolved.values()}
        origin, destination = imported_waypoints(route, resolved, quantities)
        self.assertEqual(origin["BuyCommodities"], {"128049236": 8})
        self.assertEqual(origin["SellCommodities"], {"128049155": 3})
        self.assertEqual(destination["SellCommodities"], {"128049236": 8})
        self.assertEqual(destination["BuyCommodities"], {"128049155": 3})
        self.assertEqual(len({entry["Id"] for entry in (origin, destination)}), 2)
        self.assertEqual(len(self.entries(ROUND_TRIP)), 2)

    def test_plain_browser_text_english_and_separate_endpoint_labels(self):
        text = """From
Müller's Rest | LHS 20
To
Ohm City | Sol
Station distance
10 Ls
Buy
Polymers
Buy price
100 Cr
Station distance
20 Ls
Sell
Polymers
Sell price
500 Cr"""
        first, second = self.entries(text)
        self.assertEqual(first["StationName"], "Müller's Rest")
        self.assertEqual(second["SellCommodities"], {"128049197": 7})

    def test_invalid_or_partial_results_are_rejected(self):
        for text in (
            "",
            ONE_WAY.replace("Nach ", "Other "),
            ONE_WAY + ONE_WAY,
            ONE_WAY.replace("Kauf\n[Polymere](https://inara.cz/elite/commodity/26/)", "Kauf"),
            ONE_WAY.replace("Entfernung der Station", "Other"),
            ONE_WAY.replace("Rota Obscura | WISE 0359-5401", "No system"),
        ):
            with self.subTest(text=text[:50]), self.assertRaises(ValueError):
                parse_trade_route(text)

    def test_unknown_ambiguous_names_and_unset_quantities_are_rejected(self):
        route = parse_trade_route(ONE_WAY.replace("Polymere", "Unknown commodity"))
        with self.assertRaises(ValueError):
            resolve_commodities(route, self.catalogue, "de")
        route = parse_trade_route(ONE_WAY.replace("Polymere", "Gewebeprobe aus dem Schlund einer Titan"))
        with self.assertRaisesRegex(ValueError, "unknown or ambiguous"):
            resolve_commodities(route, self.catalogue, "de")
        route = parse_trade_route(ONE_WAY)
        resolved = resolve_commodities(route, self.catalogue, "de")
        commodity_id = next(iter(resolved.values()))[0]
        for quantity in (None, 0, -1, True, 9999, "5"):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                imported_waypoints(route, resolved, {commodity_id: quantity})
        with self.assertRaises(ValueError):
            resolve_commodities(route, self.catalogue, "fr")

    def test_spansh_galaxy_plotter_imports_entire_jump_sequence(self):
        source = {
            "result": {
                "jumps": [
                    {"name": "Start", "must_refuel": True},
                    {"name": "Middle", "must_inject": True},
                    {"name": "Destination"},
                ]
            }
        }
        parsed = parse_spansh_export(json.dumps(source), self.catalogue)
        self.assertEqual(parsed.route_type, "Galaxy Plotter")
        self.assertEqual([entry["SystemName"] for entry in parsed.entries], ["Start", "Middle", "Destination"])
        self.assertNotIn("fuel", parsed.summary.casefold())
        self.assertEqual(parsed.warnings, [])

    def test_spansh_galaxy_csv_imports_every_row_in_order(self):
        source = (
            "System Name,Distance,Distance Remaining,Fuel Left,Fuel Used,Refuel,Neutron Star,Injection\n"
            "Start,0,20,16,0,false,false,false\n"
            "Middle,10,10,8,8,true,false,false\n"
            "Destination,10,0,0,8,false,false,true\n"
        )
        parsed = parse_spansh_export(source, self.catalogue)
        self.assertEqual([entry["SystemName"] for entry in parsed.entries], ["Start", "Middle", "Destination"])

    def test_spansh_exploration_json_keeps_endpoints_and_target_systems_once(self):
        source = {
            "result": [
                {"name": "Start", "bodies": []},
                {"name": "Transit", "bodies": []},
                {"name": "Target", "bodies": [{"name": "Target 1"}, {"name": "Target 2"}]},
                {"name": "Target", "bodies": [{"name": "Target 3"}]},
                {"name": "Destination", "bodies": []},
            ]
        }
        parsed = parse_spansh_export(json.dumps(source), self.catalogue)
        self.assertEqual(parsed.route_type, "Exploration")
        self.assertEqual(
            [entry["SystemName"] for entry in parsed.entries],
            ["Start", "Target", "Destination"],
        )
        self.assertIn("2 selected bodies", parsed.stop_details[1])

    def test_spansh_exploration_csv_groups_target_systems_and_reports_missing_endpoints(self):
        source = (
            "System Name,Body Name,Distance To Arrival\n"
            "Target A,World 1,100\n"
            "Target B,World 2,200\n"
            "Target A,World 3,300\n"
        )
        parsed = parse_spansh_export(source, self.catalogue)
        self.assertEqual([entry["SystemName"] for entry in parsed.entries], ["Target A", "Target B"])
        self.assertIn("start and destination", parsed.warnings[0])

    def test_spansh_empty_exploration_csv_does_not_create_empty_route(self):
        source = "System Name,Body Name,Distance To Arrival\n"
        with self.assertRaisesRegex(ValueError, "no selected body targets"):
            parse_spansh_export(source, self.catalogue)

    def test_spansh_trade_import_merges_adjacent_stations_and_keeps_revisited_stops(self):
        def station(name, system, market_id):
            return {"station": name, "system": system, "market_id": market_id}

        source = {
            "result": [
                {
                    "source": station("Port A", "System A", 1),
                    "destination": station("Port B", "System B", 2),
                    "commodities": [
                        {"name": "Polymers", "amount": 17},
                        {"name": "Unknown item", "amount": 5},
                    ],
                },
                {
                    "source": station("Port B", "System B", 2),
                    "destination": station("Port C", "System C", 3),
                    "commodities": [{"name": "Polymers", "amount": 4}],
                },
                {
                    "source": station("Port C", "System C", 3),
                    "destination": station("Port B", "System B", 2),
                    "commodities": [{"name": "Polymers", "amount": 9}],
                },
            ]
        }
        parsed = parse_spansh_export(json.dumps(source), self.catalogue)
        self.assertEqual(parsed.route_type, "Trade Planner")
        self.assertEqual(
            [(entry["StationName"], entry["SystemName"]) for entry in parsed.entries],
            [
                ("Port A", "System A"),
                ("Port B", "System B"),
                ("Port C", "System C"),
                ("Port B", "System B"),
            ],
        )
        self.assertEqual(parsed.entries[0]["BuyCommodities"], {"128049197": 17})
        self.assertEqual(parsed.entries[1]["SellCommodities"], {"128049197": 17})
        self.assertEqual(parsed.entries[1]["BuyCommodities"], {"128049197": 4})
        self.assertEqual(parsed.entries[2]["SellCommodities"], {"128049197": 4})
        self.assertEqual(parsed.entries[3]["SellCommodities"], {"128049197": 9})
        self.assertIn("unknown or ambiguous commodity", parsed.warnings[0])
        self.assertNotIn("no valid commodity actions", parsed.stop_details[0])

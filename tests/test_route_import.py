"""Copied trade-result parsing and draft creation."""

import re
import unittest

from gui.commodity_catalogue import load_catalogue
from gui.route_import import clean_line, imported_waypoints, parse_trade_route, resolve_commodities

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
        self.assertEqual(origin["BuyCommodities"], {"Silber": 7})
        self.assertEqual(origin["SellCommodities"], {})
        self.assertEqual(destination["StationName"], "Ohm City")
        self.assertEqual(destination["SellCommodities"], {"Silber": 7})

    def test_forward_one_way_and_localized_commodity(self):
        origin, destination = self.entries(ONE_WAY, language="en")
        self.assertEqual(origin["BuyCommodities"], {"Polymers": 7})
        self.assertEqual(destination["SellCommodities"], {"Polymers": 7})
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
        self.assertEqual(origin["BuyCommodities"], {"Nichttödliche Waffen": 8})
        self.assertEqual(origin["SellCommodities"], {"Silber": 3})
        self.assertEqual(destination["SellCommodities"], {"Nichttödliche Waffen": 8})
        self.assertEqual(destination["BuyCommodities"], {"Silber": 3})
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
        self.assertEqual(second["SellCommodities"], {"Polymere": 7})

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
        route = parse_trade_route(ONE_WAY)
        resolved = resolve_commodities(route, self.catalogue, "de")
        commodity_id = next(iter(resolved.values()))[0]
        for quantity in (None, 0, -1, True, 9999, "5"):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                imported_waypoints(route, resolved, {commodity_id: quantity})
        with self.assertRaises(ValueError):
            resolve_commodities(route, self.catalogue + [self.catalogue[0]], "fr")
        polymer = next(row for row in self.catalogue if row["symbol"] == "Polymers")
        with self.assertRaises(ValueError):
            resolve_commodities(route, [polymer, polymer], "de")

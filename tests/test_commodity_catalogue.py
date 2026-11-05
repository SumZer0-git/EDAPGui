"""Validate the bundled commodity reference data without the game or network."""

import json
import unittest

from core import paths
from gui.commodity_catalogue import load_catalogue, suggestions


class CommodityCatalogueTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads((paths.DATA / "commodities.json").read_text(encoding="utf-8"))
        cls.verification = json.loads((paths.DATA / "commodities.verification.json").read_text(encoding="utf-8"))

    def test_schema_and_unique_identities(self):
        self.assertEqual(self.catalogue["version"], 1)
        rows = self.catalogue["commodities"]
        self.assertEqual(len(rows), 411)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(len({row["symbol"].casefold() for row in rows}), len(rows))
        self.assertEqual(sum(row["rare"] for row in rows), 142)
        for row in rows:
            self.assertEqual(set(row), {"id", "symbol", "name_de", "name_en", "rare"})
            self.assertIs(type(row["id"]), int)
            self.assertGreater(row["id"], 0)
            self.assertIs(type(row["rare"]), bool)
            for key in ("symbol", "name_de", "name_en"):
                self.assertIsInstance(row[key], str)
                self.assertTrue(row[key].strip())
                self.assertEqual(row[key], row[key].strip())

    def test_verification_is_explicit_and_references_existing_ids(self):
        ids = {row["id"] for row in self.catalogue["commodities"]}
        observed = self.verification["de_market_observed_ids"]
        self.assertEqual(len(observed), 388)
        self.assertEqual(len(set(observed)), len(observed))
        self.assertTrue(set(observed) <= ids)
        self.assertEqual(self.verification["en_market_observed_ids"], [])
        self.assertEqual(self.verification["dialog_verified_ids"], [])
        rare_ids = {row["id"] for row in self.catalogue["commodities"] if row["rare"]}
        self.assertTrue(rare_ids <= set(observed))

    def test_game_names_and_reviewed_aliases(self):
        rows = {row["symbol"]: row for row in self.catalogue["commodities"]}
        for symbol, expected in {
            "Polymers": "Polymere",
            "Semiconductors": "Halbleiter",
            "MineralOil": "Mineralöl",
            "Bastnasite": "Bastnäsit",
            "PersonalGifts": "Festliche Geschenke",
        }.items():
            self.assertEqual(rows[symbol]["name_de"], expected)
        self.assertEqual(rows["Bastnasite"]["id"], 129046168)
        self.assertEqual(rows["PersonalGifts"]["id"], 128672431)

    def test_verification_documents_unchecked_names(self):
        self.assertIn("Name_Localised", self.verification["verification_method"])
        self.assertEqual(len(self.verification["limitations"]), 3)

    def test_search_both_languages_and_symbols(self):
        rows, verified = load_catalogue()
        self.assertEqual(suggestions(rows, verified, "de", "polymers"), {"Polymere": "Polymere"})
        self.assertEqual(suggestions(rows, verified, "en", "POLYMERE"), {"Polymers [unchecked]": "Polymers"})
        self.assertEqual(suggestions(rows, verified, "de", "  polymer  "), {"Polymere": "Polymere"})
        self.assertEqual(len(suggestions(rows, verified, "de", "")), 411)
        same_name_rows = [
            row for row in rows if row["symbol"] in ("ThargoidTissueSampleType10a", "ThargoidTissueSampleType10b")
        ]
        duplicates = suggestions(same_name_rows, verified, "de", "")
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len(set(duplicates.values())), 1)
        self.assertEqual(suggestions(rows, verified, "de", "no such commodity"), {})
        with self.assertRaises(ValueError):
            suggestions(rows, verified, "fr", "")

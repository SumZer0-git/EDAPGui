"""Validate the bundled commodity reference data without the game or network."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core import paths
from core.commodities import commodity_id_matches_name, get_localization
from gui.commodity_catalogue import load_catalogue, suggestions
from i18n.localization import LocalizationManager


class CommodityCatalogueTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue_data = json.loads((paths.DATA / "commodities.json").read_text(encoding="utf-8"))
        cls.verification = json.loads((paths.DATA / "commodities.verification.json").read_text(encoding="utf-8"))
        cls.names = {
            language: json.loads((paths.LOCALES_DIR / language / "commodities.json").read_text(encoding="utf-8"))
            for language in ("de", "en")
        }

    def test_schema_and_unique_identities(self):
        self.assertEqual(self.catalogue_data["version"], 1)
        rows = self.catalogue_data["commodities"]
        self.assertEqual(len(rows), 411)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(len({row["symbol"].casefold() for row in rows}), len(rows))
        self.assertEqual(sum(row["rare"] for row in rows), 142)
        for row in rows:
            self.assertEqual(set(row), {"id", "symbol", "rare"})
            self.assertIs(type(row["id"]), int)
            self.assertGreater(row["id"], 0)
            self.assertIs(type(row["rare"]), bool)
            self.assertIsInstance(row["symbol"], str)
            self.assertTrue(row["symbol"].strip())
            self.assertEqual(row["symbol"], row["symbol"].strip())

    def test_localized_names_are_id_keyed_and_complete(self):
        ids = {str(row["id"]) for row in self.catalogue_data["commodities"]}
        for names in self.names.values():
            self.assertEqual(set(names), ids)
        rows = {row["symbol"]: row for row in self.catalogue_data["commodities"]}
        for symbol, expected in {
            "Polymers": "Polymere",
            "Semiconductors": "Halbleiter",
            "MineralOil": "Mineralöl",
            "Bastnasite": "Bastnäsit",
            "PersonalGifts": "Festliche Geschenke",
        }.items():
            self.assertEqual(self.names["de"][str(rows[symbol]["id"])], expected)
        self.assertEqual(rows["Bastnasite"]["id"], 129046168)
        self.assertEqual(rows["PersonalGifts"]["id"], 128672431)

    def test_verification_is_explicit_and_references_existing_ids(self):
        ids = {row["id"] for row in self.catalogue_data["commodities"]}
        observed = self.verification["de_market_observed_ids"]
        self.assertEqual(len(observed), 388)
        self.assertEqual(len(set(observed)), len(observed))
        self.assertTrue(set(observed) <= ids)
        self.assertEqual(self.verification["en_market_observed_ids"], [])
        self.assertEqual(self.verification["dialog_verified_ids"], [])
        rare_ids = {row["id"] for row in self.catalogue_data["commodities"] if row["rare"]}
        self.assertTrue(rare_ids <= set(observed))
        self.assertIn("Name_Localised", self.verification["verification_method"])
        self.assertEqual(len(self.verification["limitations"]), 3)

    def test_search_uses_installed_languages_and_symbols(self):
        catalogue, verified = load_catalogue()
        localization = get_localization()
        self.assertEqual(
            suggestions(catalogue, verified, "de", "polymers", localization),
            {"Polymere": "128049197"},
        )
        self.assertEqual(
            suggestions(catalogue, verified, "en", "POLYMERE", localization),
            {"Polymers [unchecked]": "128049197"},
        )
        self.assertEqual(
            suggestions(catalogue, verified, "de", "  polymer  ", localization),
            {"Polymere": "128049197"},
        )
        self.assertEqual(len(suggestions(catalogue, verified, "de", "", localization)), 411)
        matching_ids = {
            commodity_id
            for commodity_id, item in catalogue.items()
            if item["symbol"] in ("ThargoidTissueSampleType10a", "ThargoidTissueSampleType10b")
        }
        duplicates = suggestions(catalogue, verified, "de", "", localization)
        labels = [label for label, commodity_id in duplicates.items() if commodity_id in matching_ids]
        self.assertEqual(len(labels), 2)
        self.assertTrue(all("(" in label for label in labels))
        self.assertEqual(suggestions(catalogue, verified, "de", "no such commodity", localization), {})
        with self.assertRaises(ValueError):
            suggestions(catalogue, verified, "fr", "", localization)

    def test_data_only_third_language_supplies_names_and_preserves_identity(self):
        catalogue, verified = load_catalogue()
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(paths.LOCALES_DIR / "en", Path(folder, "en"))
            third = Path(folder, "fr")
            third.mkdir()
            (third / "language.json").write_text(
                json.dumps({"name": "French", "ocr_language": "fr", "journal_languages": ["French/FR"]}),
                encoding="utf-8",
            )
            (third / "recognition.json").write_text("{}", encoding="utf-8")
            (third / "commodities.json").write_text('{"128049197": "Polymères"}', encoding="utf-8")
            with self.assertLogs("ed_log", level="WARNING"):
                localization = LocalizationManager(folder, "fr")
                self.assertEqual(
                    suggestions(catalogue, verified, "fr", "POLYMÈRES", localization),
                    {"Polymères [unchecked]": "128049197"},
                )
            self.assertEqual(commodity_id_matches_name("Polymères", localization), {"128049197"})
            self.assertEqual(localization.commodity_names()["128049152"], "Platinum")
            self.assertEqual(localization.resolve_language("auto", "French/FR"), "fr")

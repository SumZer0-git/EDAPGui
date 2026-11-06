"""Tests for localized station-services detection without the game."""

import unittest
from unittest import mock

from core import paths
from i18n.localization import LocalizationManager
from panels.station_services import EDStationServicesInShip, TradeDialogUnconfirmedError


class StationServicesTestCase(unittest.TestCase):
    def test_detection_uses_only_the_active_language(self):
        for language in ("en", "de"):
            with self.subTest(language=language):
                services = self.make_services(language)
                services.ocr.wait_for_text.return_value = True
                self.assertTrue(services.goto_station_services())
                texts = services.ocr.wait_for_text.call_args.args[1]
                expected = {"CONNECTED TO"} if language == "en" else {"VERBUNDEN MIT"}
                self.assertEqual(set(texts), expected)
                services.ap_ckb.assert_not_called()

    def test_timeout_is_not_reported_as_success(self):
        services = self.make_services("en")
        services.ocr.wait_for_text.return_value = False
        with self.assertLogs("ed_log", level="WARNING"):
            self.assertFalse(services.goto_station_services())
        services.ap_ckb.assert_called_once_with("log", "Could not confirm station services. Waypoint Assist stopped.")

    @staticmethod
    def make_services(language):
        services = EDStationServicesInShip.__new__(EDStationServicesInShip)
        services.ap = mock.Mock()
        services.keys = mock.Mock()
        services.ocr = mock.Mock()
        services.ap_ckb = mock.Mock()
        services.locale = LocalizationManager(str(paths.LOCALES_DIR), language)
        services.screen = mock.Mock(screen_width=1920, screen_height=1080)
        services.reg = {"connected_to": {"rect": [0.0, 0.0, 0.25, 0.25]}}
        return services


class TradeDialogSafetyTestCase(unittest.TestCase):
    def setUp(self):
        self.services = StationServicesTestCase.make_services("en")
        self.services.market_parser = mock.Mock()
        target = {
            "id": 128049197,
            "Name_Localised": "Polymere",
            "Stock": 2,
            "Demand": 1,
            "StockBracket": 3,
        }
        self.services.market_parser.current_data = {"Items": [target]}
        self.services.market_parser.get_item.return_value = target
        self.services.market_parser.can_buy_item.return_value = True
        self.services.market_parser.can_sell_item.return_value = True
        self.services.market_parser.get_buyable_items.return_value = [
            {"id": 128049204, "Name_Localised": "Halbleiter", "Stock": 10},
            target,
        ]
        self.services.market_parser.get_sellable_items.return_value = [target]
        patcher = mock.patch("panels.station_services.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mismatch_prevents_buy_and_sell_confirmation_and_quantity_inputs(self):
        for selling in (False, True):
            with self.subTest(selling=selling):
                services = self.services
                services.keys.reset_mock()
                with (
                    mock.patch.object(services, "confirm_trade_dialog", return_value=False),
                    self.assertRaises(TradeDialogUnconfirmedError),
                ):
                    if selling:
                        services.sell_commodity(services.keys, "128049197", 2, mock.Mock())
                    else:
                        services.buy_commodity(services.keys, "128049197", 2, 10)
                calls = services.keys.send.call_args_list
                self.assertEqual(sum(call.args[0] == "UI_Select" for call in calls), 1)
                self.assertFalse(any(call.args[0] in ("UI_Right", "UI_Left") for call in calls))
                self.assertEqual(services.market_parser.current_data["Items"][0]["StockBracket"], 3)

    def test_verified_dialog_allows_existing_trade_inputs(self):
        for selling in (False, True):
            with self.subTest(selling=selling):
                self.services.keys.reset_mock()
                with mock.patch.object(self.services, "confirm_trade_dialog", return_value=True) as confirm:
                    result = (
                        self.services.sell_commodity(self.services.keys, "128049197", 2, mock.Mock())
                        if selling
                        else self.services.buy_commodity(self.services.keys, "128049197", 2, 10)
                    )
                self.assertEqual(result, (True, 2))
                confirm.assert_called_once_with("Polymere", selling=selling)
                calls = self.services.keys.send.call_args_list
                self.assertEqual(sum(call.args[0] == "UI_Select" for call in calls), 2)
                self.assertIn(
                    mock.call("UI_Down", hold=0.05, repeat=0 if selling else 1),
                    calls,
                )

    def test_multi_row_selection_preserves_normal_down_input_timing(self):
        for selling in (False, True):
            with self.subTest(selling=selling):
                other_items = [
                    {"Name_Localised": f"Commodity {index}", "Stock": 10, "Demand": 10} for index in range(14)
                ]
                target = {
                    "id": 128049197,
                    "Name_Localised": "Polymere",
                    "Stock": 2,
                    "Demand": 2,
                }
                if selling:
                    self.services.market_parser.get_sellable_items.return_value = [*other_items, target]
                else:
                    self.services.market_parser.get_buyable_items.return_value = [*other_items, target]
                self.services.keys.reset_mock()
                with mock.patch.object(self.services, "confirm_trade_dialog", return_value=True):
                    result = (
                        self.services.sell_commodity(self.services.keys, "128049197", 1, mock.Mock())
                        if selling
                        else self.services.buy_commodity(self.services.keys, "128049197", 1, 10)
                    )

                self.assertEqual(result, (True, 1))
                self.assertIn(
                    mock.call("UI_Down", hold=0.05, repeat=14),
                    self.services.keys.send.call_args_list,
                )

    def test_no_matching_list_item_reports_failure(self):
        self.services.market_parser.get_buyable_items.return_value = []
        self.assertEqual(self.services.buy_commodity(self.services.keys, "128049197", 2, 10), (False, 0))
        self.services.keys.send.assert_not_called()

    def test_unknown_market_commodity_id_cannot_be_traded(self):
        self.services.market_parser.get_item.return_value = None
        self.assertEqual(self.services.buy_commodity(self.services.keys, "999999999", 2, 10), (False, 0))
        self.assertEqual(self.services.sell_commodity(self.services.keys, "999999999", 2, mock.Mock()), (False, 0))
        self.services.keys.send.assert_not_called()

    def test_buy_all_is_limited_by_stock_and_free_cargo(self):
        for stock, free_cargo, expected in ((10, 3, 3), (2, 10, 2)):
            with self.subTest(stock=stock, free_cargo=free_cargo):
                self.services.keys.reset_mock()
                self.services.market_parser.get_buyable_items.return_value = [
                    {"id": 128049197, "Name_Localised": "Polymere", "Stock": stock}
                ]
                with mock.patch.object(self.services, "confirm_trade_dialog", return_value=True):
                    self.assertEqual(
                        self.services.buy_commodity(self.services.keys, "128049197", 9999, free_cargo),
                        (True, expected),
                    )
                self.assertIn(mock.call("UI_Right", hold=4), self.services.keys.send.call_args_list)

    def test_confirmation_timeout_sends_no_inputs(self):
        with (
            mock.patch.object(self.services, "trade_dialog_matches", return_value=False),
            mock.patch("panels.station_services.monotonic", side_effect=[100, 114.9, 115.1]),
        ):
            self.assertFalse(self.services.confirm_trade_dialog("Polymere", False))
        self.services.keys.send.assert_not_called()
        self.services.ap_ckb.assert_not_called()

    def test_text_must_match_whole_name_and_trade_direction(self):
        for language, title, name, expected in (
            ("de", "WARE KAUFEN", "POLYMERE", True),
            ("en", "BUY COMMODITY", "POLYMERE", True),
            ("de", "WARE VERKAUFEN", "POLYMERE", False),
            ("de", "WARE KAUFEN", "POLYMERE EXTRA", False),
            ("de", "WARE KAUFEN", "", False),
            ("de", "", "POLYMERE", False),
            ("en", "WARE KAUFEN", "POLYMERE", False),
        ):
            with self.subTest(language=language, title=title, name=name):
                self.services.locale = LocalizationManager(str(paths.LOCALES_DIR), language)
                self.services.ocr.image_simple_ocr.side_effect = [[title], [name]]
                self.assertEqual(self.services.trade_dialog_matches("Polymere", False), expected)

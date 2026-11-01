"""Tests for the Status.json parser."""

import tempfile
import unittest
from pathlib import Path

from core.constants import FlagsDocked, FlagsSupercruise, GuiFocusNoFocus
from game.status import StatusParser
from tests.helpers import write_json

STATUS = {
    "timestamp": "2024-09-28T16:01:47Z",
    "event": "Status",
    "Flags": FlagsDocked | FlagsSupercruise,
    "Flags2": 0,
    "Pips": [4, 4, 4],
    "GuiFocus": 0,
    "Fuel": {"FuelMain": 36.16, "FuelReservoir": 0.53},
    "Cargo": 728.0,
    "LegalState": "Clean",
    "Balance": 1000,
    "Destination": {"System": 7267487524297, "Body": 12, "Name": "Some Station"},
}


class StatusParserTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.path = Path(self._dir.name) / 'Status.json'

    def test_cleaned_data(self):
        write_json(self.path, STATUS)
        data = StatusParser(file_path=str(self.path)).get_cleaned_data()

        self.assertEqual(data['Flags'], FlagsDocked | FlagsSupercruise)
        self.assertEqual(data['pips'], {'system': 2.0, 'engine': 2.0, 'weapons': 2.0})
        self.assertEqual(data['FuelMain'], 36.16)
        self.assertEqual(data['Destination_System'], 7267487524297)
        self.assertEqual(data['Destination_Body'], 12)
        self.assertEqual(data['Destination_Name'], 'Some Station')
        self.assertEqual(data['timestamp_delta'], 0.0)

    def test_optional_fields_use_defaults(self):
        write_json(self.path, {"timestamp": "2024-09-28T16:01:47Z", "event": "Status", "Flags": 0})
        data = StatusParser(file_path=str(self.path)).get_cleaned_data()

        self.assertEqual(data['Destination_Name'], '')
        self.assertEqual(data['Destination_Body'], -1)
        self.assertIsNone(data['FuelMain'])
        self.assertIsNone(data['Flags2'])

    def test_timestamp_delta_after_file_change(self):
        write_json(self.path, STATUS)
        parser = StatusParser(file_path=str(self.path))

        write_json(self.path, {**STATUS, "timestamp": "2024-09-28T16:01:52Z"})
        data = parser.get_cleaned_data()

        self.assertEqual(data['timestamp_delta'], 5.0)

    def test_unchanged_file_returns_cached_data(self):
        write_json(self.path, STATUS)
        parser = StatusParser(file_path=str(self.path))

        self.assertIs(parser.get_cleaned_data(), parser.get_cleaned_data())

    def test_get_flag(self):
        write_json(self.path, STATUS)
        parser = StatusParser(file_path=str(self.path))

        self.assertTrue(parser.get_flag(FlagsDocked))
        self.assertTrue(parser.get_flag(FlagsSupercruise))
        self.assertFalse(parser.get_flag(1 << 8))  # Lights on

    def test_get_flag2_without_flags2(self):
        write_json(self.path, {"timestamp": "2024-09-28T16:01:47Z", "event": "Status", "Flags": 0})
        parser = StatusParser(file_path=str(self.path))

        self.assertFalse(parser.get_flag2(1))

    def test_gui_focus(self):
        write_json(self.path, STATUS)
        parser = StatusParser(file_path=str(self.path))

        self.assertEqual(parser.get_gui_focus(), GuiFocusNoFocus)
        self.assertTrue(parser.wait_for_gui_focus(GuiFocusNoFocus, timeout=1))

    def test_wait_for_flag_times_out(self):
        write_json(self.path, STATUS)
        parser = StatusParser(file_path=str(self.path))

        self.assertTrue(parser.wait_for_flag_on(FlagsDocked, timeout=1))
        self.assertFalse(parser.wait_for_flag_off(FlagsDocked, timeout=0.2))

    def test_translate_flags_returns_only_set_flags(self):
        parser = _parser_without_file()

        self.assertEqual(parser.translate_flags(0), {})
        self.assertEqual(parser.translate_flags(FlagsDocked | FlagsSupercruise),
                         {"Docked": True, "Supercruise": True})

    def test_translate_flags2(self):
        parser = _parser_without_file()

        self.assertEqual(parser.translate_flags2(1 | 4096), {"OnFoot": True, "Glide Mode": True})

    def test_transform_pips_halves_values(self):
        self.assertEqual(_parser_without_file().transform_pips([8, 2, 2]),
                         {'system': 4.0, 'engine': 1.0, 'weapons': 1.0})

    def test_adjust_year_adds_1286_years(self):
        self.assertEqual(_parser_without_file().adjust_year("2024-09-28T16:01:47Z"), "3310-09-28T16:01:47Z")


def _parser_without_file() -> StatusParser:
    """ Parser object for the pure helper methods, which do not need a file. """
    return StatusParser.__new__(StatusParser)


if __name__ == '__main__':
    unittest.main()

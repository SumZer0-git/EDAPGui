"""Tests for the window settings model and the stored window state (no window needed)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from gui import fields, window_state
from gui.fields import TAB_OVERLAY


def make_ap():
    ap = MagicMock()
    ap.config = {key: 0 for key in (f.key for f in fields.FIELDS if not f.target)}
    ap.config.update({"LogDEBUG": False, "LogINFO": True})
    ap.rollrate = 80.0
    return ap


class FieldsTestCase(unittest.TestCase):
    def test_keys_are_unique(self):
        self.assertEqual(len(fields.FIELDS), len(fields.FIELDS_BY_KEY))

    def test_every_field_belongs_to_a_known_tab(self):
        tabs = {fields.TAB_SHIP, fields.TAB_SETTINGS, TAB_OVERLAY, fields.TAB_DEBUG}
        self.assertTrue(all(f.tab in tabs for f in fields.FIELDS))
        self.assertTrue(fields.fields_of(fields.TAB_SHIP))

    def test_overlay_choices_and_percent_offsets(self):
        unit = fields.FIELDS_BY_KEY["OverlayPositionUnit"]
        self.assertEqual(fields.parse(unit, "Percent"), "Percent")
        font_weight = fields.FIELDS_BY_KEY["OverlayTextFontWeight"]
        self.assertEqual(font_weight.label, "Font weight")
        self.assertEqual(fields.parse(font_weight, "SemiBold"), "SemiBold")
        with self.assertRaises(ValueError):
            fields.parse(font_weight, "ExtraBold")

        values = {
            "OverlayPositionUnit": "Percent",
            "OverlayTextXOffset": 50,
            "OverlayTextYOffset": 400,
        }
        previous = {
            "OverlayPositionUnit": "Pixels",
            "OverlayTextXOffset": 50,
            "OverlayTextYOffset": 400,
        }
        converted = fields.convert_overlay_offsets(values, previous, 1920, 1080)
        self.assertEqual(converted, ("OverlayTextXOffset", "OverlayTextYOffset"))
        self.assertEqual((values["OverlayTextXOffset"], values["OverlayTextYOffset"]), (3, 37))
        fields.validate_tab(TAB_OVERLAY, values)

        values["OverlayTextYOffset"] = 101
        with self.assertRaises(ValueError):
            fields.validate_tab(TAB_OVERLAY, values)

    def test_overlay_line_order_is_normalized_and_movable(self):
        order_field = fields.FIELDS_BY_KEY["OverlayLineOrder"]
        default = list(fields.DEFAULT_OVERLAY_LINE_ORDER)
        self.assertEqual(default.index("jumps_bar"), default.index("jumps") + 1)
        self.assertEqual(default.index("distance_bar"), default.index("distance") + 1)
        self.assertTrue(all(setting in fields.FIELDS_BY_KEY for _key, setting in fields.OVERLAY_LINES))

        parsed = fields.parse(order_field, "distance, mode,unknown,mode")
        self.assertEqual(parsed[:2], ["distance", "mode"])
        self.assertEqual(sorted(parsed), sorted(default))

        ap = make_ap()
        ap.config["OverlayLineOrder"] = parsed
        self.assertEqual(fields.read(order_field, ap), ",".join(parsed))
        self.assertEqual(fields.read(order_field, make_ap()), ",".join(default))

        self.assertEqual(fields.move_overlay_line(default, "status", -1)[:2], ["status", "mode"])
        self.assertEqual(fields.move_overlay_line(default, "mode", -1), default)
        self.assertEqual(fields.move_overlay_line(default, "distance_bar", 1), default)

    def test_parse_number_in_range(self):
        field = fields.FIELDS_BY_KEY["RollRate"]
        self.assertEqual(fields.parse(field, " 90.5 "), 90.5)

    def test_parse_rejects_invalid_numbers(self):
        field = fields.FIELDS_BY_KEY["RollRate"]
        for raw in ("abc", "", "-1", "nan", "inf", "100000"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                fields.parse(field, raw)

    def test_parse_rejects_unknown_choice(self):
        field = next(f for f in fields.FIELDS if f.kind == "choice")
        with self.assertRaises(ValueError):
            fields.parse(field, "nonsense")

    def test_parse_hotkey(self):
        field = next(f for f in fields.FIELDS if f.kind == "hotkey")
        self.assertEqual(fields.parse(field, "home"), "home")
        with self.assertRaises(ValueError):
            fields.parse(field, "")

    def test_read_and_write_attribute(self):
        ap = make_ap()
        field = fields.FIELDS_BY_KEY["RollRate"]
        self.assertEqual(fields.read(field, ap), "80.0")
        fields.write(field, ap, 70.0)
        self.assertEqual(ap.rollrate, 70.0)

    def test_log_level_roundtrip(self):
        ap = make_ap()
        field = next(f for f in fields.FIELDS if f.target == "log_level")
        self.assertEqual(fields.read(field, ap), "Info")
        fields.write(field, ap, "Debug")
        ap.set_log_debug.assert_called_once_with(True)


class WindowStateTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.file = Path(self.dir.name) / "gui.json"

    def test_missing_file_gives_defaults(self):
        self.assertEqual(window_state.load(self.file), window_state.DEFAULTS)

    def test_roundtrip(self):
        state = {"x": 10, "y": -20, "collapsed": True, "topmost": True}
        window_state.save(state, self.file)
        self.assertEqual(window_state.load(self.file), state)

    def test_invalid_content_falls_back_to_defaults(self):
        self.file.write_text("not json")
        self.assertEqual(window_state.load(self.file), window_state.DEFAULTS)

    def test_wrong_types_are_ignored(self):
        self.file.write_text(json.dumps({"x": "left", "collapsed": "yes", "topmost": True}))
        state = window_state.load(self.file)
        self.assertIsNone(state["x"])
        self.assertFalse(state["collapsed"])
        self.assertTrue(state["topmost"])


if __name__ == "__main__":
    unittest.main()

"""Tests for loading waypoint files and choosing the next waypoint, without the game."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import paths
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
    "Skip": True,
    "Completed": False,
}


def stop(system, **values):
    entry = {**GLOBAL_LIST, "SystemName": system, "StationName": f"{system} Station", "Skip": False}
    entry.update(values)
    return entry


def new_waypoints(waypoints) -> EDWayPoint:
    """A waypoint object without the parsers and the autopilot, which are not needed for the list handling."""
    wp = EDWayPoint.__new__(EDWayPoint)
    wp.waypoints = copy.deepcopy(waypoints)
    wp.step = 0
    wp.filename = "test.json"
    wp.stats_log = {"Colonisation": 0, "Construction": 0, "Fleet Carrier": 0, "Station": 0}
    # The list handling must never write into the user's waypoint folder
    for method in ("save_waypoints", "log_stats"):
        patcher = mock.patch.object(wp, method)
        patcher.start()
    return wp


class ReadWaypointsTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = Path(self._dir.name)
        self.wp = new_waypoints({})

    def write(self, data) -> Path:
        path = self.dir / "waypoints.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_file(self):
        data = {"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol")}

        self.assertEqual(self.wp.read_waypoints(self.write(data)), data)

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

        self.assertTrue(self.wp.load_waypoint_file(str(path)))
        self.assertEqual(self.wp.filename, str(path))
        self.assertIn("1", self.wp.waypoints)

        self.assertFalse(self.wp.load_waypoint_file(str(self.dir / "missing.json")))
        self.assertFalse(self.wp.load_waypoint_file(None))


class GetWaypointTestCase(unittest.TestCase):
    def test_skips_shopping_list_completed_and_skipped_entries(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": GLOBAL_LIST,
                "1": stop("Done", Completed=True),
                "2": stop("Skipped", Skip=True),
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
                "1": stop("A", Completed=True),
                "2": stop("B", Completed=True),
                "3": stop("REPEAT"),
            }
        )

        key, _ = wp.get_waypoint()

        self.assertEqual(key, "1")
        self.assertFalse(wp.waypoints["1"]["Completed"])
        self.assertFalse(wp.waypoints["2"]["Completed"])

    def test_skipped_repeat_ends_the_list(self):
        wp = new_waypoints(
            {
                "GlobalShoppingList": GLOBAL_LIST,
                "1": stop("A", Completed=True),
                "2": stop("REPEAT", Skip=True),
            }
        )

        self.assertEqual(wp.get_waypoint(), (None, None))


if __name__ == "__main__":
    unittest.main()

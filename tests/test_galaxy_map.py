import unittest
from unittest.mock import Mock, call, patch

from panels.galaxy_map import EDGalaxyMap


class GalaxyMapTestCase(unittest.TestCase):
    def setUp(self):
        self.ap = Mock()
        with patch("panels.galaxy_map.StatusParser"):
            self.galaxy_map = EDGalaxyMap(self.ap, Mock(), self.ap.keys, Mock())

    def run_destination_search(self, nav_route_values):
        self.ap.nav_route.get_last_system.side_effect = nav_route_values
        with (
            patch.object(self.galaxy_map, "goto_galaxy_map"),
            patch("panels.galaxy_map.typewrite"),
            patch("panels.galaxy_map.sleep"),
        ):
            return self.galaxy_map.set_gal_map_destination_text_odyssey(self.ap, "LHS 20")

    def test_retries_wrong_route_and_succeeds_when_destination_is_confirmed(self):
        self.assertTrue(self.run_destination_search(["", "", "WRONG", "WRONG", "LHS 20"]))

        plot_attempts = [sent for sent in self.ap.keys.send.call_args_list if sent == call("UI_Select", hold=0.75)]
        self.assertEqual(len(plot_attempts), 2)
        self.assertEqual(self.ap.keys.send.call_args_list[-1], call("GalaxyMapOpen"))

    def test_stops_after_three_unconfirmed_plot_attempts(self):
        clock = [0.0]
        self.ap.nav_route.get_last_system.return_value = ""
        with (
            patch.object(self.galaxy_map, "goto_galaxy_map"),
            patch("panels.galaxy_map.typewrite"),
            patch("panels.galaxy_map.monotonic", side_effect=lambda: clock[0]),
            patch("panels.galaxy_map.sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
        ):
            self.assertFalse(self.galaxy_map.set_gal_map_destination_text_odyssey(self.ap, "LHS 20"))

        plot_attempts = [sent for sent in self.ap.keys.send.call_args_list if sent == call("UI_Select", hold=0.75)]
        self.assertEqual(len(plot_attempts), 3)
        self.assertEqual(self.ap.keys.send.call_args_list[-1], call("GalaxyMapOpen"))

    def test_bookmark_plot_succeeds_when_nav_route_matches_expected_system(self):
        self.ap.nav_route.get_last_system.return_value = "LHS 20"
        with (
            patch.object(self.galaxy_map, "goto_galaxy_map"),
            patch("panels.galaxy_map.sleep"),
        ):
            result = self.galaxy_map.set_gal_map_dest_bookmark(self.ap, "Fav", 1, expected_system="LHS 20")

        self.assertTrue(result)
        self.assertEqual(self.ap.keys.send.call_args_list[-1], call("GalaxyMapOpen"))

    def test_bookmark_plot_fails_when_nav_route_never_matches_expected_system(self):
        clock = [0.0]
        self.ap.nav_route.get_last_system.return_value = "WRONG"
        with (
            patch.object(self.galaxy_map, "goto_galaxy_map"),
            patch("panels.galaxy_map.monotonic", side_effect=lambda: clock[0]),
            patch(
                "panels.galaxy_map.sleep",
                side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
            ),
        ):
            result = self.galaxy_map.set_gal_map_dest_bookmark(self.ap, "Fav", 1, expected_system="LHS 20")

        self.assertFalse(result)
        self.assertGreaterEqual(self.ap.nav_route.get_last_system.call_count, 60)


if __name__ == "__main__":
    unittest.main()

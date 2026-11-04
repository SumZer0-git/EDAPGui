"""Tests for the end-of-route decision in the assists."""

import unittest
from unittest.mock import Mock, patch

from routines.assists import AssistsMixin


class Assists(AssistsMixin):
    def __init__(self, compass_readings):
        self.have_destination = Mock(side_effect=compass_readings)


def status(name="", body=-1):
    return {"Destination_Name": name, "Destination_Body": body}


@patch("routines.assists.sleep", Mock())
class InSystemTargetTestCase(unittest.TestCase):
    def test_a_station_in_the_status_is_a_target_without_looking_at_the_compass(self):
        assists = Assists([])

        self.assertTrue(assists.has_in_system_target(None, status("Some Station", 20)))
        assists.have_destination.assert_not_called()

    def test_main_star_or_empty_destination_without_compass_is_no_target(self):
        for current in (status(), status("Some Star", 0)):
            with self.subTest(status=current):
                self.assertFalse(Assists([False]).has_in_system_target(None, current))

    def test_compass_fallback_needs_two_readings(self):
        self.assertTrue(Assists([True, True]).has_in_system_target(None, status()))
        self.assertFalse(Assists([True, False]).has_in_system_target(None, status()))


if __name__ == "__main__":
    unittest.main()

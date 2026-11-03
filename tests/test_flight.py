"""Tests for flight and target-alignment routines."""

import unittest
from unittest.mock import patch

from core.types import ScTargetAlignReturn
from routines.flight import FlightMixin


class Keys:
    def __init__(self):
        self.sent = []

    def send(self, key):
        self.sent.append(key)


class TargetAlignment(FlightMixin):
    def __init__(self):
        self.keys = Keys()
        self.stopped_monitoring = False

    def get_destination_offset(self, scr_reg):
        return None

    def sc_disengage_label_up(self, scr_reg):
        return True

    def sc_disengage_active(self, scr_reg):
        return True

    def ap_ckb(self, *args):
        pass

    def stop_sco_monitoring(self):
        self.stopped_monitoring = True


class TargetAlignmentTestCase(unittest.TestCase):
    def test_disengage_is_checked_when_target_is_not_found(self):
        alignment = TargetAlignment()

        with patch("routines.flight.sleep"):
            result = alignment.sc_target_align(None)

        self.assertEqual(result, ScTargetAlignReturn.Disengage)
        self.assertEqual(alignment.keys.sent, ["HyperSuperCombination"])
        self.assertTrue(alignment.stopped_monitoring)

    def test_wait_for_disengage_returns_when_requested(self):
        alignment = TargetAlignment()

        with patch("routines.flight.sleep"):
            self.assertTrue(alignment.wait_for_sc_disengage(None, 10))

        self.assertEqual(alignment.keys.sent, ["HyperSuperCombination"])

    def test_wait_for_disengage_times_out_without_message(self):
        alignment = TargetAlignment()
        alignment.sc_disengage_label_up = lambda scr_reg: False

        with patch("routines.flight.sleep"), patch("routines.flight.time.time", side_effect=[0, 1, 11]):
            self.assertFalse(alignment.wait_for_sc_disengage(None, 10))

        self.assertEqual(alignment.keys.sent, [])

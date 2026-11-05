"""Tests for flight and target-alignment routines."""

import unittest
from unittest.mock import Mock, patch

from core.constants import FlagsFsdCharging, FlagsFsdJump
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


class JumpRetryTestCase(unittest.TestCase):
    def test_target_align_shortens_holds_near_the_target_when_proportional(self):
        flight = Mock()
        flight.pitchrate = 40.0
        flight.yawrate = 24.0
        flight.get_destination_offset.side_effect = [{"x": -100, "y": 20}, {"x": 8, "y": 3}]
        flight.jn.ship_state.return_value = {"status": "in_supercruise"}

        with patch("routines.flight.sleep"):
            FlightMixin.fsd_target_align(flight, None, close=10, proportional=True)

        sent = [(call.args[0], call.kwargs["hold"]) for call in flight.keys.send.call_args_list]
        self.assertEqual(sent[0], ("YawLeftButton", 0.15))
        self.assertEqual(sent[1][0], "PitchUpButton")
        self.assertAlmostEqual(sent[1][1], 0.06)
        self.assertEqual(len(sent), 2)

    def test_target_align_keeps_fixed_holds_for_the_reference_ship(self):
        flight = Mock()
        flight.pitchrate = 40.0
        flight.yawrate = 24.0
        flight.get_destination_offset.side_effect = [{"x": -100, "y": 80}, {"x": 8, "y": 3}]
        flight.jn.ship_state.return_value = {"status": "in_supercruise"}

        with patch("routines.flight.sleep"):
            FlightMixin.fsd_target_align(flight, None, close=50)

        sent = [(call.args[0], call.kwargs["hold"]) for call in flight.keys.send.call_args_list]
        self.assertEqual(sent, [("YawLeftButton", 0.3), ("PitchUpButton", 0.15)])

    def test_target_align_scales_holds_with_ship_rates(self):
        for pitchrate, yawrate, expected_yaw, expected_pitch in (
            (20.0, 12.0, 0.6, 0.3),  # half as agile: twice as long
            (80.0, 48.0, 0.15, 0.075),  # twice as agile: half as long
            (5.0, 3.0, 0.9, 0.45),  # very sluggish: capped at three times the base hold
        ):
            with self.subTest(pitchrate=pitchrate, yawrate=yawrate):
                flight = Mock()
                flight.pitchrate = pitchrate
                flight.yawrate = yawrate
                flight.get_destination_offset.side_effect = [{"x": -150, "y": 150}, {"x": 8, "y": 3}]
                flight.jn.ship_state.return_value = {"status": "in_supercruise"}

                with patch("routines.flight.sleep"):
                    FlightMixin.fsd_target_align(flight, None, close=50)

                sent = {call.args[0]: call.kwargs["hold"] for call in flight.keys.send.call_args_list}
                self.assertAlmostEqual(sent["YawLeftButton"], expected_yaw)
                self.assertAlmostEqual(sent["PitchUpButton"], expected_pitch)

    def test_target_align_learns_the_step_size_after_an_overshoot(self):
        flight = Mock()
        flight.pitchrate = 5.0
        flight.yawrate = 3.0  # configured as sluggish, but the ship really moves 160 px per second of hold
        flight.get_destination_offset.side_effect = [{"x": 75, "y": 0}, {"x": -69, "y": 0}, {"x": 5, "y": 0}]
        flight.jn.ship_state.return_value = {"status": "in_supercruise"}

        with patch("routines.flight.sleep"):
            FlightMixin.fsd_target_align(flight, None, close=50)

        sent = [(call.args[0], call.kwargs["hold"]) for call in flight.keys.send.call_args_list]
        self.assertEqual(sent[0][0], "YawRightButton")
        self.assertAlmostEqual(sent[0][1], 0.9)
        self.assertEqual(sent[1][0], "YawLeftButton")
        self.assertAlmostEqual(sent[1][1], 0.8 * 69 / (144 / 0.9))
        self.assertEqual(len(sent), 2)

    def test_first_attempt_alignment_is_not_proportional(self):
        flight = Mock()
        flight.jn.ship_state.return_value = {"status": "in_supercruise"}

        FlightMixin.mnvr_to_target(flight, None)

        flight.fsd_target_align.assert_called_once_with(
            None, close=50, allow_starting_hyperspace=False, proportional=False
        )

    def test_failed_jump_start_realigns_before_retry(self):
        flight = Mock()
        flight.config = {"JumpTries": 2}
        flight.jn.ship_state.side_effect = [
            {"status": "in_space"},
            {"status": "starting_hyperspace"},
        ]
        flight.status.wait_for_flag_on.side_effect = [True, True]
        flight.status.wait_for_flag_off.side_effect = [True, True, True]
        flight.wait_for_fsd_jump_start.side_effect = [False, True]

        with patch("routines.flight.sleep"):
            self.assertTrue(FlightMixin.jump(flight, None))

        flight.mnvr_to_target.assert_called_once_with(None, retry=True)
        self.assertEqual(flight.wait_for_fsd_jump_start.call_count, 2)
        flight.status.wait_for_flag_off.assert_any_call(FlagsFsdJump, 5)
        flight.status.wait_for_flag_off.assert_any_call(FlagsFsdCharging, 5)

    def test_retry_alignment_allows_stale_hyperspace_journal_status(self):
        flight = Mock()
        flight.jn.ship_state.return_value = {"status": "starting_hyperspace"}

        FlightMixin.mnvr_to_target(flight, None, retry=True)

        flight.fsd_target_align.assert_called_once_with(
            None, close=20, allow_starting_hyperspace=True, proportional=True
        )

    def test_journal_jump_flag_takes_priority_over_prompt_check(self):
        flight = Mock()
        flight.status.get_flag.return_value = True

        with patch("routines.flight.time.monotonic", return_value=0):
            self.assertTrue(FlightMixin.wait_for_fsd_jump_start(flight, None))

        flight.fsd_alignment_prompt.assert_not_called()

    def test_alignment_prompt_only_requests_a_small_correction(self):
        flight = Mock()
        flight.status.get_flag.side_effect = [False, True, True]
        flight.fsd_alignment_prompt.return_value = True

        with patch("routines.flight.time.monotonic", side_effect=[0, 0]), patch("routines.flight.sleep"):
            self.assertTrue(FlightMixin.wait_for_fsd_jump_start(flight, None))

        flight.correct_fsd_alignment.assert_called_once_with(None)

    def test_no_prompt_text_preserves_wait_timeout(self):
        flight = Mock()
        flight.status.get_flag.return_value = False
        flight.status.get_flag.side_effect = [False, True, False]
        flight.fsd_alignment_prompt.return_value = False

        with patch("routines.flight.time.monotonic", side_effect=[0, 0, 31]), patch("routines.flight.sleep"):
            self.assertFalse(FlightMixin.wait_for_fsd_jump_start(flight, None))

        flight.correct_fsd_alignment.assert_not_called()

    def test_retry_cancels_running_charge_before_realigning(self):
        flight = Mock()
        flight.config = {"JumpTries": 2}
        flight.jn.ship_state.return_value = {"status": "in_space"}
        flight.status.get_flag.side_effect = lambda flag: flag == FlagsFsdCharging
        flight.status.wait_for_flag_on.return_value = True
        flight.status.wait_for_flag_off.return_value = True
        flight.wait_for_fsd_jump_start.side_effect = [False, True]

        with patch("routines.flight.sleep"):
            self.assertTrue(FlightMixin.jump(flight, None))

        sent = [call.args[0] for call in flight.keys.send.call_args_list]
        self.assertEqual(sent[:3], ["HyperSuperCombination"] * 3)
        flight.mnvr_to_target.assert_called_once_with(None, retry=True)

    def test_compass_reading_rejects_implausible_values(self):
        for nav in (
            None,
            {"z": -1, "yaw": 90, "pit": -90, "roll": 142},
            {"z": 1, "yaw": 2.74, "pit": -24.59, "roll": 174},
        ):
            with self.subTest(nav=nav):
                flight = Mock()
                flight.fsd_behind_readings = 0
                flight.get_nav_offset.return_value = nav
                self.assertIsNone(FlightMixin.read_compass_alignment(flight, None))

    def test_compass_reading_counts_target_behind(self):
        flight = Mock()
        flight.fsd_behind_readings = 0
        flight.get_nav_offset.return_value = {"z": -1, "yaw": -176.0, "pit": -107.0, "roll": -177.0}

        self.assertIsNone(FlightMixin.read_compass_alignment(flight, None))

        self.assertEqual(flight.fsd_behind_readings, 1)

    def test_prompt_with_target_behind_ends_the_wait_for_a_retry(self):
        flight = Mock()
        flight.status.get_flag.side_effect = [False, True, True]
        flight.fsd_alignment_prompt.return_value = True
        flight.correct_fsd_alignment.return_value = False
        flight.fsd_behind_readings = 5

        with patch("routines.flight.time.monotonic", side_effect=[0, 0]), patch("routines.flight.sleep"):
            self.assertFalse(FlightMixin.wait_for_fsd_jump_start(flight, None))

    def test_centered_compass_reading_must_be_confirmed(self):
        centered = {"z": 1, "yaw": 0.0, "pit": 0.0, "roll": 0}
        for readings, expected in (
            ([centered, centered], True),
            ([centered, {"z": -1, "yaw": -176.0, "pit": -107.0, "roll": -177}], False),
            ([{"z": 1, "yaw": -0.35, "pit": -25.0, "roll": -106}, centered], False),
        ):
            with self.subTest(readings=readings):
                flight = Mock()
                flight.get_nav_offset.side_effect = readings
                with patch("routines.flight.sleep"):
                    self.assertEqual(FlightMixin.compass_confirmed(flight, None, 10), expected)

    def test_compass_reading_accepts_rolled_but_plausible_values(self):
        flight = Mock()
        flight.get_nav_offset.return_value = {"z": 1, "yaw": 6.39, "pit": 12.4, "roll": 26.98}
        self.assertEqual(FlightMixin.read_compass_alignment(flight, None), (6.39, 12.4))

    def test_measurement_drops_flickering_readings_and_averages_the_rest(self):
        flight = Mock()
        flight.read_compass_alignment.side_effect = [None, (0, 11.0), None, (0.4, 12.0), (30.0, -24.6), None]
        with patch("routines.flight.sleep"):
            self.assertEqual(FlightMixin.measure_fsd_alignment(flight, None), (0.2, 11.5))

    def test_measurement_needs_two_plausible_agreeing_readings(self):
        flight = Mock()
        flight.read_compass_alignment.side_effect = [None, (0, 11.0), None, None, None, None]
        with patch("routines.flight.sleep"):
            self.assertIsNone(FlightMixin.measure_fsd_alignment(flight, None))

        flight.read_compass_alignment.side_effect = [(0, 11.0), (0, -24.6), None, None, None, None]
        with patch("routines.flight.sleep"):
            self.assertIsNone(FlightMixin.measure_fsd_alignment(flight, None))

    def test_correction_pitches_up_proportionally_toward_compass_point(self):
        flight = Mock()
        flight.status.get_flag.return_value = False
        flight.measure_fsd_alignment.return_value = (0.2, 11.0)
        flight.pitchrate = 33.0
        flight.yawrate = 8.0

        self.assertTrue(FlightMixin.correct_fsd_alignment(flight, None))

        flight.keys.send.assert_called_once()
        key = flight.keys.send.call_args.args[0]
        hold = flight.keys.send.call_args.kwargs["hold"]
        self.assertEqual(key, "PitchUpButton")
        self.assertAlmostEqual(hold, 11.0 * 0.8 / 33.0)

    def test_correction_yaws_left_and_caps_hold_time(self):
        flight = Mock()
        flight.status.get_flag.return_value = False
        flight.measure_fsd_alignment.return_value = (-20.0, 1.0)
        flight.pitchrate = 33.0
        flight.yawrate = 8.0

        FlightMixin.correct_fsd_alignment(flight, None)

        flight.keys.send.assert_called_once_with("YawLeftButton", hold=0.5)

    def test_correction_is_skipped_without_trusted_measurement(self):
        flight = Mock()
        flight.status.get_flag.return_value = False
        flight.measure_fsd_alignment.return_value = None

        self.assertFalse(FlightMixin.correct_fsd_alignment(flight, None))

        flight.keys.send.assert_not_called()

    def test_correction_is_skipped_within_tolerance(self):
        flight = Mock()
        flight.status.get_flag.return_value = False
        flight.measure_fsd_alignment.return_value = (0.5, -1.0)

        self.assertFalse(FlightMixin.correct_fsd_alignment(flight, None))

        flight.keys.send.assert_not_called()

    def test_correction_is_skipped_after_journal_reports_jump_started(self):
        flight = Mock()
        flight.status.get_flag.return_value = True

        self.assertFalse(FlightMixin.correct_fsd_alignment(flight, None))

        flight.measure_fsd_alignment.assert_not_called()
        flight.keys.send.assert_not_called()


class DockStatusTestCase(unittest.TestCase):
    def test_docking_reports_each_step_and_still_restocks(self):
        ship = {"status": "in_space", "no_dock_reason": None}
        statuses = []
        dock = FlightMixin.__new__(FlightMixin)
        dock.config = {"DockingRetries": 1, "WaitForAutoDockTimer": 3}
        dock.jn = Mock(ship_state=Mock(return_value=ship))
        dock.keys = Mock()
        dock.vce = Mock()
        dock.ap_ckb = Mock()
        dock.set_ap_status = statuses.append

        def request_docking():
            ship["status"] = "dockinggranted"

        def sleep(_seconds):
            if statuses and statuses[-1] == "Docking":
                ship["status"] = "in_station"

        dock.request_docking = request_docking
        with patch("routines.flight.sleep", side_effect=sleep):
            dock.dock()

        self.assertEqual(statuses, ["Requesting docking", "Docking", "Refueling and repairing"])
        sent = [c.args[0] for c in dock.keys.send.call_args_list]
        self.assertEqual(sent.count("UI_Select"), 3)

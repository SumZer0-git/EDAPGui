from __future__ import annotations

from typing import TypedDict

from EDAP_data import *
from RPYLineEditor import convert_curve_to_float, convert_curve_to_str, closest_angle
from Screen import set_focus_elite_window
from StatusParser import StatusParser
from time import sleep


def scale(inp: float, in_min: float, in_max: float, out_min: float, out_max: float, clamp: bool) -> float:
    """ Does scaling of the input based on input and output min/max.
    @param inp: The input, typically with the range in_min to in_max, but can extend outside.
    @param in_min: The min input value.
    @param in_max: The max input value.
    @param out_min: The min output value.
    @param out_max: The max output value.
    @param clamp: Clamp the output to out_min and out_max.
    @return: The calculated input interpolated or extrapolated by the given ranges.
    """
    x = (inp - in_min) / (in_max - in_min) * (out_max - out_min) + out_min
    if clamp:
        return max(min(x, out_max), out_min)
    else:
        return x


class CompassTargetOffset(TypedDict):
    """
    Dictionary containing navigation (compass) and/or Target information.
    """
    roll: float
    pit: float
    yaw: float
    tar_occ: bool
    tar_behind: bool
    used_nav: bool
    used_tar: bool


class ThrottleDemand(TypedDict):
    """
    Dictionary containing target information.
    """
    RollRate: dict[str, float]
    PitchRate: dict[str, float]
    YawRate: dict[str, float]


class EDShipControl:
    """ Handles ship control, FSD, SC, etc. """

    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.status_parser = StatusParser()

    def add_to_roll_curve(self, angle: float, rate: float):
        """
        Add a point to the current curve of the current ship.
        @param angle: The angle to add in degrees.
        @param rate: The rate of movement to move that angle in deg/seconds.
        @return: N/A
        """
        throttle = self.get_throttle_demand_dict()
        if throttle:
            c = convert_curve_to_float(throttle['RollRate'])
            # Add the new item. Conversion will sort them.
            a = closest_angle(angle)
            c[a] = round(rate, 2)
            # Convert back to str which will sort the values automatically.
            s = convert_curve_to_str(c)
            throttle['RollRate'] = s

            self.ap_ckb('log', f'Added a point to the {self.ap.speed_demand} '
                               f'Roll curve at {a} deg, {round(rate, 2)} deg/s.')

    def add_to_pitch_curve(self, angle: float, rate: float):
        """
        Add a point to the current curve.
        @param angle: The angle to add in degrees.
        @param rate: The rate of movement to move that angle in deg/seconds.
        @return: N/A
        """
        throttle = self.get_throttle_demand_dict()
        if throttle:
            c = convert_curve_to_float(throttle['PitchRate'])
            # Add the new item. Conversion will sort them.
            a = closest_angle(angle)
            c[a] = round(rate, 2)
            # Convert back to str which will sort the values automatically.
            s = convert_curve_to_str(c)
            throttle['PitchRate'] = s

            self.ap_ckb('log', f'Added a point to the {self.ap.speed_demand} '
                               f'Pitch curve at {a} deg, {round(rate, 2)} deg/s.')

    def add_to_yaw_curve(self, angle: float, rate: float):
        """
        Add a point to the current curve.
        @param angle: The angle to add in degrees.
        @param rate: The rate of movement to move that angle in deg/seconds.
        @return: N/A
        """
        throttle = self.get_throttle_demand_dict()
        if throttle:
            c = convert_curve_to_float(throttle['YawRate'])
            # Add the new item. Conversion will sort them.
            a = closest_angle(angle)
            c[a] = round(rate, 2)
            # Convert back to str which will sort the values automatically.
            s = convert_curve_to_str(c)
            throttle['YawRate'] = s
            self.ap_ckb('log', f'Added a point to the {self.ap.speed_demand} '
                               f'Yaw curve at {a} deg, {round(rate, 2)} deg/s.')

    def get_throttle_demand_dict(self) -> ThrottleDemand | None:
        """
        Gets the current RPY tuning curve for the current ship. Or None if neither are valid.
        @return: The ThrottleDemand dict containing the RPY curves:
            {   'RollRate': dict[str, float],
                'PitchRate': dict[str, float],
                'YawRate': dict[str, float] }
        """
        # Check if a ship config loaded
        if self.ap.current_ship_cfg:
            # Check the throttle demand is in the ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                # Select the throttle demand
                throttle_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                return throttle_demand

        return None

    def goto_cockpit_view(self) -> bool:
        """ Goto cockpit view.
        @return: True once complete.
        """
        if self.status_parser.get_gui_focus() == GuiFocusNoFocus:
            return True

        # Go down to cockpit view
        while not self.status_parser.get_gui_focus() == GuiFocusNoFocus:
            self.keys.send("UI_Back")  # make sure back in cockpit view

        return True

    def roll_clockwise_anticlockwise(self, deg: float, auto_tune: bool = False, cur_deg: float = 0.0) -> (
            CompassTargetOffset | None):
        """ Roll in deg. (> 0.0 for roll right, < 0.0 for roll left)
        @param deg: The angle to turn in degrees
        @param auto_tune: Enable auto-tuning of ship
        @param cur_deg: Our current angle used for tuning
        @return: N/A.
        """
        close = 8.0
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.rollrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        if self.ap.current_ship_cfg:
            # Roll rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'RollRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    last_deg1 = 0.0
                    last_val1 = 0.0
                    for key, value in speed_demand['RollRate'].items():
                        key_deg = float(key)
                        if last_val == 0.0:
                            # We want to clamp at the min recorded value because interpolating starting at 0.0 will
                            # produce a large rate which will cause oscillation.
                            last_val = value
                            last_val1 = value

                        if abs_deg <= key_deg:
                            # Interpolate based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value, False)
                            self.ap_ckb('log',
                                        f"Roll demand: {round(deg, 1)}. Interp value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        # Extrapolate based on the last value and the value before this value
                        ratio_val = scale(abs_deg, last_deg1, last_deg, last_val1, last_val, False)
                        self.ap_ckb('log', f"Roll demand: {round(deg, 1)}. Extrap value: {round(ratio_val, 2)} deg/s")

                        htime = abs_deg / ratio_val

        # Check if we are rolling right or left and perform the movement.
        if deg > 0.0:
            self.keys.send('RollRightButton', hold=htime)
        else:
            self.keys.send('RollLeftButton', hold=htime)

        # Calculate error
        # Calc the position we want to achieve
        sp = cur_deg - deg
        # Wait for ship to stabilize. Calc the delay from the angle 0 - 45 deg = 0.1 - 0.75 Sec. 45 deg is where the
        # rate no longer increases.
        dly = scale(abs_deg, 0.0, 45.0, 0.5, 1.0, True)
        sleep(dly)

        # Take current reading
        off = self.ap.get_compass_target_offset()
        if off:
            # Are we still too far away?
            err = sp - off['roll']
            if abs(err) > close:
                # Add angle and time to curve
                act_ang = abs(cur_deg - off['roll'])
                rate = act_ang / htime
                if auto_tune:
                    # Add a new point for the detected rate
                    self.add_to_roll_curve(act_ang, rate)
                    # Update the existing point as well
                    self.add_to_roll_curve(abs_deg, rate)
                else:
                    c_ang = closest_angle(act_ang)
                    # self.ap_ckb('log', f"Roll Tuning suggestion - Add {c_ang} deg with {round(rate, 2)} deg/s rate")

        # Return compass/target data or None
        return off

    def pitch_up_down(self, deg: float, auto_tune: bool = False, cur_deg: float = 0.0) -> CompassTargetOffset | None:
        """ Pitch in deg. (> 0.0 for pitch up, < 0.0 for pitch down)
        @param deg: The angle to turn in degrees
        @param auto_tune: Enable auto-tuning of ship
        @param cur_deg: Our current angle used for tuning
        @return: N/A.
        """
        close = 0.5
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.pitchrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        if self.ap.current_ship_cfg:
            # Pitch rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'PitchRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    last_deg1 = 0.0
                    last_val1 = 0.0
                    for key, value in speed_demand['PitchRate'].items():
                        key_deg = float(key)
                        if last_val == 0.0:
                            # We want to clamp at the min recorded value because interpolating starting at 0.0 will
                            # produce a large rate which will cause oscillation.
                            last_val = value
                            last_val1 = value

                        if abs_deg <= key_deg:
                            # Interpolate based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value, False)
                            self.ap_ckb('log',
                                        f"Pitch demand: {round(deg, 1)}. Interp value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        # Extrapolate based on the last value and the value before this value
                        ratio_val = scale(abs_deg, last_deg1, last_deg, last_val1, last_val, False)
                        self.ap_ckb('log', f"Pitch demand: {round(deg, 1)}. Extrap value: {round(ratio_val, 2)} deg/s")

                        htime = abs_deg / ratio_val

        # Check if we are pitching up or down and perform the movement.
        if deg > 0.0:
            self.keys.send('PitchUpButton', hold=htime)
        else:
            self.keys.send('PitchDownButton', hold=htime)

        # Calculate error
        # Calc the position we want to achieve
        sp = cur_deg - deg
        # Wait for ship to stabilize. Calc the delay from the angle 0 - 30 deg = 0.1 - 0.5 Sec. 30 deg is where the
        # rate no longer increases.
        dly = scale(abs_deg, 0.0, 30.0, 0.5, 0.75, True)
        sleep(dly)

        # Take current reading
        off = self.ap.get_compass_target_offset()
        if off:
            # Are we still too far away?
            err = sp - off['pit']
            if abs(err) > close:
                # Add angle and time to curve
                act_ang = abs(cur_deg - off['pit'])
                rate = act_ang / htime
                if auto_tune:
                    # Add a new point for the detected rate
                    self.add_to_pitch_curve(act_ang, rate)
                    # Update the existing point as well
                    self.add_to_pitch_curve(abs_deg, rate)
                else:
                    c_ang = closest_angle(act_ang)
                    # self.ap_ckb('log', f"Pitch Tuning suggestion - Add {c_ang} deg with {round(rate, 2)} deg/s rate")

        # Return compass/target data or None
        return off

    def yaw_right_left(self, deg: float, auto_tune: bool = False, cur_deg: float = 0.0) -> CompassTargetOffset | None:
        """ Yaw in deg. (> 0.0 for yaw right, < 0.0 for yaw left)
        @param deg: The angle to turn in degrees
        @param auto_tune: Enable auto-tuning of ship
        @param cur_deg: Our current angle used for tuning
        @return: N/A.
        """
        close = 0.5
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.yawrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        if self.ap.current_ship_cfg:
            # Yaw rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'YawRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    last_deg1 = 0.0
                    last_val1 = 0.0
                    for key, value in speed_demand['YawRate'].items():
                        key_deg = float(key)
                        if last_val == 0.0:
                            # We want to clamp at the min recorded value because interpolating starting at 0.0 will
                            # produce a large rate which will cause oscillation.
                            last_val = value
                            last_val1 = value

                        if abs_deg <= key_deg:
                            # Interpolate based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value, False)
                            self.ap_ckb('log',
                                        f"Yaw demand: {round(deg, 1)}. Interp value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg1 = last_deg
                            last_val1 = last_val
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        # Extrapolate based on the last value and the value before this value
                        ratio_val = scale(abs_deg, last_deg1, last_deg, last_val1, last_val, False)
                        self.ap_ckb('log', f"Yaw demand: {round(deg, 1)}. Extrap value: {round(ratio_val, 2)} deg/s")

                        htime = abs_deg / ratio_val

        # Check if we are yawing right or left and perform the movement.
        if deg > 0.0:
            self.keys.send('YawRightButton', hold=htime)
        else:
            self.keys.send('YawLeftButton', hold=htime)

        # Calculate error
        # Auto-tune if necessary
        # Calc the position we want to achieve
        sp = cur_deg - deg
        # Wait for ship to stabilize. Calc the delay from the angle 0 - 30 deg = 0.1 - 0.4 Sec. 30 deg is where the
        # rate no longer increases.
        dly = scale(abs_deg, 0.0, 30.0, 0.5, 0.75, True)
        sleep(dly)

        # Take current reading
        off = self.ap.get_compass_target_offset()
        if off:
            # Are we still too far away?
            err = sp - off['yaw']
            if abs(err) > close:
                # Add angle and time to curve
                act_ang = abs(cur_deg - off['yaw'])
                rate = act_ang / htime
                if auto_tune:
                    # Add a new point for the detected rate
                    self.add_to_yaw_curve(act_ang, rate)
                    # Update the existing point as well
                    self.add_to_yaw_curve(abs_deg, rate)
                else:
                    c_ang = closest_angle(act_ang)
                    # self.ap_ckb('log', f"Yaw Tuning suggestion - Add {c_ang} deg with {round(rate, 2)} deg/s rate")

        # Return compass/target data or None
        return off

    def ship_calibrate_roll(self):
        """ Performs ship roll tuning by pitching 360 degrees.
        If the ship does not rotate enough, decrease the roll value.
        If the ship rotates too much, increase the roll value.
        """
        self.ap_ckb('log', "Starting Roll Tuning.")

        if not self.ap.speed_demand or self.ap.speed_demand == '':
            self.ap_ckb('log', "WARNING: Set speed before tuning.")
            return

        if not self.ap.current_ship_cfg:
            return

        if self.ap.speed_demand not in self.ap.current_ship_cfg:
            self.ap.current_ship_cfg[self.ap.speed_demand] = dict()

        # Clear existing data
        self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate'] = dict()

        test_time = 0.05
        delta = 0.0
        for targ_ang in [2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0, 55.0, 89.0, 144.0]:
            while 1:
                set_focus_elite_window()
                off = self.ap.get_compass_target_offset()
                if not off:
                    break

                # Clear the overlays before moving
                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_remove_rect('compass')
                    self.ap.overlay.overlay_remove_floating_text('compass')
                    self.ap.overlay.overlay_remove_floating_text('nav')
                    self.ap.overlay.overlay_remove_floating_text('nav_beh')
                    self.ap.overlay.overlay_remove_floating_text('compass_rpy')
                    self.ap.overlay.overlay_paint()

                if off['roll'] > 0:
                    self.keys.send('RollRightButton', hold=test_time)
                else:
                    self.keys.send('RollLeftButton', hold=test_time)

                sleep(1)

                off2 = self.ap.get_compass_target_offset()
                if not off2:
                    break

                delta_lst = delta
                delta = round(abs(off2['roll'] - off['roll']), 1)

                test_time = test_time * 1.04
                rate = round(delta / test_time, 2)
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate'][str(delta)] = rate

                    print(f"Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")

        self.ap_ckb('log', "Completed Roll Tuning. Remember to Save.")

    def ship_calibrate_pitch(self):
        """ Performs a ship pitch tuning by pitching 360 degrees.
        If the ship does not rotate enough, decrease the pitch value.
        If the ship rotates too much, increase the pitch value.
        """
        self.ap_ckb('log', "Starting Pitch Tuning.")

        if not self.ap.speed_demand or self.ap.speed_demand == '':
            self.ap_ckb('log', "WARNING: Set speed before tuning.")
            return

        if not self.ap.current_ship_cfg:
            return

        if self.ap.speed_demand not in self.ap.current_ship_cfg:
            self.ap.current_ship_cfg[self.ap.speed_demand] = dict()

        # Clear existing data
        self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate'] = dict()

        test_time = 0.05
        delta = 0.0
        for targ_ang in [0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 16.0, 32.0, 60.0, 90.0, 120.0]:
            while 1:
                set_focus_elite_window()
                off = self.ap.get_compass_target_offset()
                if not off:
                    print(f"Target lost")
                    break

                # Clear the overlays before moving
                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_remove_rect('target')
                    self.ap.overlay.overlay_remove_floating_text('target')
                    self.ap.overlay.overlay_remove_floating_text('target_occ')
                    self.ap.overlay.overlay_remove_floating_text('target_rpy')
                    self.ap.overlay.overlay_paint()

                if off['pit'] > 0:
                    self.keys.send('PitchUpButton', hold=test_time)
                else:
                    self.keys.send('PitchDownButton', hold=test_time)

                sleep(1)

                off2 = self.ap.get_compass_target_offset()
                if not off2:
                    print(f"Target lost")
                    break

                delta_lst = delta
                delta = round(abs(off2['pit'] - off['pit']), 1)

                test_time = test_time * 1.04
                rate = round(delta / test_time, 2)
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate'][str(delta)] = rate

                    print(f"Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")

        self.ap_ckb('log', "Completed Pitch Tuning. Remember to Save.")

    def ship_calibrate_yaw(self):
        """ Performs a ship yaw tuning by pitching 360 degrees.
        If the ship does not rotate enough, decrease the yaw value.
        If the ship rotates too much, increase the yaw value.
        """
        self.ap_ckb('log', "Starting Yaw Tuning.")

        if not self.ap.speed_demand or self.ap.speed_demand == '':
            self.ap_ckb('log', "WARNING: Set speed before tuning.")
            return

        if not self.ap.current_ship_cfg:
            return

        if self.ap.speed_demand not in self.ap.current_ship_cfg:
            self.ap.current_ship_cfg[self.ap.speed_demand] = dict()

        # Clear existing data
        self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate'] = dict()

        test_time = 0.07
        delta = 0.0
        for targ_ang in [0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 16.0, 32.0, 60.0, 90.0, 120.0]:
            while 1:
                set_focus_elite_window()
                off = self.ap.get_compass_target_offset()
                if not off:
                    break

                # Clear the overlays before moving
                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_remove_rect('target')
                    self.ap.overlay.overlay_remove_floating_text('target')
                    self.ap.overlay.overlay_remove_floating_text('target_occ')
                    self.ap.overlay.overlay_remove_floating_text('target_rpy')
                    self.ap.overlay.overlay_paint()

                if off['yaw'] > 0:
                    self.keys.send('YawRightButton', hold=test_time)
                else:
                    self.keys.send('YawLeftButton', hold=test_time)

                sleep(1)

                off2 = self.ap.get_compass_target_offset()
                if not off2:
                    break

                delta_lst = delta
                delta = round(abs(off2['yaw'] - off['yaw']), 1)

                test_time = test_time * 1.05
                rate = round(delta / test_time, 2)
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate'][str(delta)] = rate

                    print(f"Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")

        self.ap_ckb('log', "Completed Yaw Tuning. Remember to Save.")

    def ship_tst_roll(self, angle: float):
        """ Performs a ship roll test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the roll value.
        If the ship rotates too much, increase the roll value.
        @param angle: The angle to move in degrees.
        @return: N/A
        """
        # if not self.ap.status.get_flag(FlagsSupercruise):
        #     self.ap_ckb('log', "Enter Supercruise and try again.")
        #     return
        #
        # if self.ap.jn.ship_state()['target'] is None:
        #     self.ap_ckb('log', "Select a target system and try again.")
        #     return

        set_focus_elite_window()
        sleep(0.25)
        # self.ap.set_speed_50()
        self.roll_clockwise_anticlockwise(angle)

    def ship_tst_pitch(self, angle: float):
        """ Performs a ship pitch test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the pitch value.
        If the ship rotates too much, increase the pitch value.
        @param angle: The angle to move in degrees.
        @return: N/A
        """
        # if not self.ap.status.get_flag(FlagsSupercruise):
        #     self.ap_ckb('log', "Enter Supercruise and try again.")
        #     return
        #
        # if self.ap.jn.ship_state()['target'] is None:
        #     self.ap_ckb('log', "Select a target system and try again.")
        #     return

        set_focus_elite_window()
        sleep(0.25)
        # self.ap.set_speed_50()
        self.ap.pitch_up_down(angle)

    def ship_tst_yaw(self, angle: float):
        """ Performs a ship yaw test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the yaw value.
        If the ship rotates too much, increase the yaw value.
        @param angle: The angle to move in degrees.
        @return: N/A
        """
        # if not self.ap.status.get_flag(FlagsSupercruise):
        #     self.ap_ckb('log', "Enter Supercruise and try again.")
        #     return
        #
        # if self.ap.jn.ship_state()['target'] is None:
        #     self.ap_ckb('log', "Select a target system and try again.")
        #     return

        set_focus_elite_window()
        sleep(0.25)
        # self.ap.set_speed_50()
        self.yaw_right_left(angle)


def main():
    pass


if __name__ == "__main__":
    main()

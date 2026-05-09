from __future__ import annotations

from typing import TypedDict

from EDAP_data import *
from RPYLineEditor import convert_curve_to_float, convert_curve_to_str
from Screen import set_focus_elite_window
from StatusParser import StatusParser
from time import sleep


def scale(inp: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    """ Does scaling of the input based on input and output min/max.
    @param inp: The input, typically with the range in_min to in_max, but can extend outside.
    @param in_min: The min input value.
    @param in_max: The max input value.
    @param out_min: The min output value.
    @param out_max: The max output value.
    @return: The calculated input interpolated or extrapolated by the given ranges.
    """
    return (inp - in_min) / (in_max - in_min) * (out_max - out_min) + out_min


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

    def roll_clockwise_anticlockwise(self, deg: float) -> float:
        """ Roll in deg. (> 0.0 for roll right, < 0.0 for roll left)
        @param deg: The angle to turn in degrees
        @return: The calculated hold time for the movement in seconds.
        """
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.rollrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        # Calculate rate for less than 45 degrees, else use default
        if self.ap.current_ship_cfg:
            # Roll rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'RollRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    for key, value in speed_demand['RollRate'].items():
                        key_deg = float(key)
                        if abs_deg <= key_deg:
                            # Interpolate based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value)
                            # print(f"Roll demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            # logger.info(f"Roll demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            self.ap_ckb('log', f"Roll demand: {round(deg, 1)}. Interp value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        htime = abs_deg / last_val
                        # print(f"Roll demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                        # logger.info(f"Roll demand: {deg}. Calc value: {round(last_val, 2)} deg/s")
                        self.ap_ckb('log', f"Roll demand: {deg}. Calc value: {round(last_val, 2)} deg/s")
                        self.ap_ckb('log', f"Roll demand: {round(deg, 1)}. Extrap value: {round(last_val, 2)} deg/s")

        # Check if we are rolling right or left
        if deg > 0.0:
            self.keys.send('RollRightButton', hold=htime)
        else:
            self.keys.send('RollLeftButton', hold=htime)

        # Return the hold time
        return htime

    def pitch_up_down(self, deg: float) -> float:
        """ Pitch in deg. (> 0.0 for pitch up, < 0.0 for pitch down)
        @param deg: The angle to turn in degrees
        @return: The hold time for the movement in seconds.
        """
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.pitchrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        # Calculate rate for less than 30 degrees, else use default
        if self.ap.current_ship_cfg:
            # Pitch rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'PitchRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    for key, value in speed_demand['PitchRate'].items():
                        key_deg = float(key)
                        if abs_deg <= key_deg:
                            # Ratio based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value)
                            # print(f"Pitch demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            # logger.info(f"Pitch demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            self.ap_ckb('log', f"Pitch demand: {round(deg, 1)}. Calc value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        htime = abs_deg / last_val
                        # print(f"Pitch demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                        # logger.info(f"Pitch demand: {deg}. Calc value: {round(last_val, 2)} deg/s")
                        self.ap_ckb('log', f"Pitch demand: {round(deg, 1)}. Calc value: {round(last_val, 2)} deg/s")

        # Check if we are pitching up or down
        if deg > 0.0:
            self.keys.send('PitchUpButton', hold=htime)
        else:
            self.keys.send('PitchDownButton', hold=htime)

        # Return the hold time
        return htime

    def yaw_right_left(self, deg: float) -> float:
        """ Yaw in deg. (> 0.0 for yaw right, < 0.0 for yaw left)
        @param deg: The angle to turn in degrees
        @return: The hold time for the movement in seconds.
        """
        abs_deg = abs(deg)
        htime = abs_deg / self.ap.yawrate

        if self.ap.speed_demand is None:
            self.ap.set_throttle_50()

        # Calculate rate for less than 30 degrees, else use default
        if self.ap.current_ship_cfg:
            # Yaw rate from ship config
            if self.ap.speed_demand in self.ap.current_ship_cfg:
                speed_demand = self.ap.current_ship_cfg[self.ap.speed_demand]
                if 'YawRate' in speed_demand:
                    last_deg = 0.0
                    last_val = 0.0
                    for key, value in speed_demand['YawRate'].items():
                        key_deg = float(key)
                        if abs_deg <= key_deg:
                            # Ratio based on the last value and this value
                            ratio_val = scale(abs_deg, last_deg, key_deg, last_val, value)
                            # print(f"Yaw demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            # logger.info(f"Yaw demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                            self.ap_ckb('log', f"Yaw demand: {round(deg, 1)}. Calc value: {round(ratio_val, 2)} deg/s")

                            htime = abs_deg / ratio_val

                            last_deg = key_deg
                            last_val = value
                            break
                        else:
                            last_deg = key_deg
                            last_val = value

                    # Check if found one curve point and we are off the scale
                    if abs_deg > last_deg and last_val > 0.0:
                        htime = abs_deg / last_val
                        # print(f"Yaw demand: {deg}. Calc value: {round(ratio_val, 2)} deg/s")
                        # logger.info(f"Yaw demand: {deg}. Calc value: {round(last_val, 2)} deg/s")
                        self.ap_ckb('log', f"Yaw demand: {round(deg, 1)}. Calc value: {round(last_val, 2)} deg/s")

        # Check if we are yawing right or left
        if deg > 0.0:
            self.ap.keys.send('YawRightButton', hold=htime)
        else:
            self.ap.keys.send('YawLeftButton', hold=htime)

        # Return the hold time
        return htime

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
        rate = self.ap.rollrate
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
                # rate = min(rate, self.ap.rollrate)  # Limit rate to no higher than the default
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate'][str(delta)] = rate

                    print(f"Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Roll Angle: {round(delta, 1)}: Time: {round(test_time, 2)} Rate: {rate}")

        # If we have logged values, add the last rate for 45 and 60 deg
        # if len(self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate']) > 0:
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate'][str(45.0)] = rate
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['RollRate'][str(60.0)] = rate
        #     self.ap_ckb('log', f"Default: Roll Angle: 45: Rate: {self.ap.rollrate}")

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
        rate = self.ap.pitchrate
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
                # rate = min(rate, self.ap.pitchrate)  # Limit rate to no higher than the default
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate'][str(delta)] = rate

                    print(f"Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Pitch Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")

        # # If we have logged values, add the last rate for 30 and 60 deg
        # if len(self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate']) > 0:
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate'][str(30.0)] = rate
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['PitchRate'][str(60.0)] = rate
        #     self.ap_ckb('log', f"Default: Pitch Angle: 30: Rate: {self.ap.pitchrate}")

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
        rate = self.ap.yawrate
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
                # rate = min(rate, self.ap.yawrate)  # Limit rate to no higher than the default
                if delta >= targ_ang and delta > delta_lst:
                    self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate'][str(delta)] = rate

                    print(f"Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    self.ap_ckb('log', f"Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")
                    break
                else:
                    print(f"Ignored Yaw Angle: {delta}: Time: {round(test_time, 2)} Rate: {rate}")

        # # If we have logged values, add the last rate for 30 and 60 deg
        # if len(self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate']) > 0:
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate'][str(30.0)] = rate
        #     self.ap.current_ship_cfg[self.ap.speed_demand]['YawRate'][str(60.0)] = rate
        #     self.ap_ckb('log', f"Default: Yaw Angle: 30: Rate: {self.ap.yawrate}")

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

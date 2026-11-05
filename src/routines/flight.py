"""Ship maneuvers: aligning, jumping, docking, undocking and refueling."""

import random
import threading
import time
from time import sleep

from controls.directinput import SCANCODE
from core.constants import (
    SCOOPABLE_STAR_CLASSES,
    Flags2FsdScoActive,
    FlagsAnalysisMode,
    FlagsDocked,
    FlagsFsdCharging,
    FlagsFsdJump,
    FlagsFsdMassLocked,
    FlagsHasLatLong,
    FlagsLanded,
    FlagsLowFuel,
    FlagsOverHeating,
    FlagsSupercruise,
)
from core.logger import logger
from core.types import ScTargetAlignReturn

# FSD alignment correction while charging (compass degrees / seconds)
FSD_ALIGN_TOLERANCE = 1.5
FSD_ALIGN_MAX_ROLL = 60
FSD_ALIGN_MAX_DIFF = 5
FSD_ALIGN_GAIN = 0.8
FSD_ALIGN_MIN_HOLD = 0.05
FSD_ALIGN_MAX_HOLD = 0.5
FSD_ALIGN_SAMPLES = 6
FSD_ALIGN_SAMPLE_DELAY = 0.15

# Target-ring alignment: pixels the target moves with one full-length hold (measured at 2160p), shortest hold
FSD_TARGET_FULL_STEP_PX = 200
FSD_REF_PITCH_RATE = 40.0
FSD_REF_YAW_RATE = 24.0
FSD_HOLD_SCALE_MAX = 3
FSD_TARGET_MIN_HOLD = 0.06
FSD_STEP_GAIN = 0.8
FSD_STEP_MIN_MOVE_PX = 15
FSD_RETRY_TARGET_CLOSE = 20

# Compass alignment: re-reads while the compass/nav point is not visible, and re-rolls when the nav point ahead is
# more than NAV_ALIGN_REROLL_YAW degrees off to the side after a pitch step
NAV_ALIGN_LOST_READS = 4
NAV_ALIGN_LOST_DELAY = 0.5
NAV_ALIGN_MAX_REROLLS = 2
NAV_ALIGN_REROLL_YAW = 30


class FlightMixin:
    # Compass readings of the last FSD alignment measurement that reported the target behind the ship
    fsd_behind_readings = 0

    def start_sco_monitoring(self):
        """Start Supercruise Overcharge Monitoring. This starts a parallel thread used to detect SCO
        until stop_sco_monitoring if called."""
        self._sc_sco_active_loop_enable = True

        if self._sc_sco_active_loop_thread is None or not self._sc_sco_active_loop_thread.is_alive():
            self._sc_sco_active_loop_thread = threading.Thread(target=self._sc_sco_active_loop, daemon=True)
            self._sc_sco_active_loop_thread.start()

    def stop_sco_monitoring(self):
        """Stop Supercruise Overcharge Monitoring."""
        self._sc_sco_active_loop_enable = False

    def _sc_sco_active_loop(self):
        """A loop to determine is Supercruise Overcharge is active.
        This runs on a separate thread monitoring the status in the background."""
        while self._sc_sco_active_loop_enable:
            # Try to determine if the disengage/sco text is there
            sc_sco_is_active_ls = self.sc_sco_is_active

            # Check if SCO active in flags
            self.sc_sco_is_active = self.status.get_flag2(Flags2FsdScoActive)

            if self.sc_sco_is_active and not sc_sco_is_active_ls:
                self.ap_ckb("log+vce", "Supercruise Overcharge activated")
            if sc_sco_is_active_ls and not self.sc_sco_is_active:
                self.ap_ckb("log+vce", "Supercruise Overcharge deactivated")

            # Protection if SCO is active
            if self.sc_sco_is_active:
                if self.status.get_flag(FlagsOverHeating):
                    logger.info("SCO Aborting, overheating")
                    self.ap_ckb("log+vce", "SCO Aborting, overheating")
                    self.keys.send("UseBoostJuice")
                elif self.status.get_flag(FlagsLowFuel):
                    logger.info("SCO Aborting, < 25% fuel")
                    self.ap_ckb("log+vce", "SCO Aborting, < 25% fuel")
                    self.keys.send("UseBoostJuice")
                elif self.jn.ship_state()["fuel_percent"] < self.config["FuelThreasholdAbortAP"]:
                    logger.info("SCO Aborting, < users low fuel threshold")
                    self.ap_ckb("log+vce", "SCO Aborting, < users low fuel threshold")
                    self.keys.send("UseBoostJuice")

            # Check again in a bit
            sleep(1)

    def undock(self):
        """Performs menu action to undock from Station"""
        # Go to cockpit view
        self.ship_control.goto_cockpit_view()

        # Now we are on initial menu, we go up to top (which is Refuel)
        self.keys.send("UI_Up", repeat=3)

        # down to Auto Undock and Select it...
        self.keys.send("UI_Down")
        self.keys.send("UI_Down")
        self.keys.send("UI_Select")
        self.keys.send("SetSpeedZero", repeat=2)

    def request_docking(self):
        """Request docking from Nav Panel."""
        self.nav_panel.request_docking()

    def dock(self):
        """Docking sequence.  Assumes in normal space, will get closer to the Station
        then zero the velocity and execute menu commands to request docking, when granted
        will wait a configurable time for dock.  Perform Refueling and Repair.
        """
        # if not in normal space, give a few more sections as at times it will take a little bit
        if self.jn.ship_state()["status"] != "in_space":
            sleep(3)  # sleep a little longer

        if self.jn.ship_state()["status"] != "in_space":
            logger.error("In dock(), after wait, but still not in_space")

        sleep(5)  # wait 5 seconds to get to 7.5km to request docking
        self.keys.send("SetSpeed50")

        if self.jn.ship_state()["status"] != "in_space":
            self.keys.send("SetSpeedZero")
            logger.error("In dock(), after long wait, but still not in_space")
            raise Exception("Docking failed (not in space)")

        sleep(12)
        # At this point (of sleep()) we should be < 7.5km from the station.  Go 0 speed
        # if we get docking granted ED's docking computer will take over
        self.keys.send("SetSpeedZero", repeat=2)
        sleep(3)  # Wait for ship to come to stop
        self.set_ap_status("Requesting docking")
        self.vce.say("Initiating Docking Procedure")
        # Request docking through Nav panel.
        self.request_docking()
        sleep(1)

        tries = self.config["DockingRetries"]
        granted = False
        if self.jn.ship_state()["status"] == "dockinggranted":
            granted = True
        else:
            for i in range(tries):
                if self.jn.ship_state()["no_dock_reason"] == "Distance":
                    self.keys.send("SetSpeed50")
                    sleep(5)
                    self.keys.send("SetSpeedZero", repeat=2)
                sleep(3)  # Wait for ship to come to stop
                # Request docking through Nav panel.
                self.request_docking()
                self.keys.send("SetSpeedZero", repeat=2)

                sleep(1.5)
                if self.jn.ship_state()["status"] == "dockinggranted":
                    granted = True
                    # Go back to navigation tab
                    # self.request_docking_cleanup()
                    break
                if self.jn.ship_state()["status"] == "dockingdenied":
                    pass

        if not granted:
            self.ap_ckb("log", "Docking denied: " + str(self.jn.ship_state()["no_dock_reason"]))
            logger.warning("Did not get docking authorization, reason:" + str(self.jn.ship_state()["no_dock_reason"]))
            raise Exception("Docking failed (Did not get docking authorization)")
        else:
            self.ap_ckb("log+vce", "Docking request granted")
            self.set_ap_status("Docking")
            # allow auto dock to take over
            for i in range(self.config["WaitForAutoDockTimer"]):
                sleep(1)
                if self.jn.ship_state()["status"] == "in_station":
                    self.set_ap_status("Refueling and repairing")
                    # go to top item, select (which should be refuel)
                    self.keys.send("UI_Up", hold=3)
                    self.keys.send("UI_Select")  # Refuel
                    sleep(0.5)
                    self.keys.send("UI_Right")  # Repair
                    self.keys.send("UI_Select")
                    sleep(0.5)
                    self.keys.send("UI_Right")  # Ammo
                    self.keys.send("UI_Select")
                    sleep(0.5)
                    self.keys.send("UI_Left", repeat=2)  # back to fuel
                    return

            self.ap_ckb("log", "Auto dock timer timed out.")
            logger.warning("Auto dock timer timed out. Aborting Docking.")
            raise Exception("Docking failed (Auto dock timer timed out)")

    # use to orient the ship to not be pointing right at the Sun
    # Checks brightness in the region in front of us, if brightness exceeds a threshold
    # then will pitch up until below threshold.
    #
    def sun_avoid(self, scr_reg):
        logger.debug("align= avoid sun")

        sleep(0.5)

        # close to core the 'sky' is very bright with close stars, if we are pitch due to a non-scoopable star
        #  which is dull red, the star field is 'brighter' than the sun, so our sun avoidance could pitch up
        #  endlessly. So we will have a fail_safe_timeout to kick us out of pitch up if we've pitch past 110 degrees, but
        #  we'll add 3 more second for pad in case the user has a higher pitch rate than the vehicle can do
        fail_safe_timeout = (120 / self.pitchrate) + 3
        starttime = time.time()

        # if sun in front of us, then keep pitching up until it is below us
        while self.is_sun_dead_ahead(scr_reg):
            self.keys.send("PitchUpButton", state=1)

            # check if we are being interdicted
            interdicted = self.interdiction_check()
            if interdicted:
                # Continue journey after interdiction
                self.keys.send("SetSpeedZero")

            # if we are pitching more than N seconds break, may be in high density area star area (close to core)
            if (time.time() - starttime) > fail_safe_timeout:
                logger.warning("Sun avoid failsafe timeout")
                break

        sleep(0.35)  # up slightly so not to overheat when scooping
        # Some ships heat up too much and need pitch up a little further
        if self.sunpitchuptime > 0.0:
            sleep(self.sunpitchuptime)
        self.keys.send("PitchUpButton", state=0)

        # Some ships run cool so need to pitch down a little
        if self.sunpitchuptime < 0.0:
            self.keys.send("PitchDownButton", state=1)
            sleep(-1.0 * self.sunpitchuptime)
            self.keys.send("PitchDownButton", state=0)

    def wait_for_sc_disengage(self, scr_reg, seconds) -> bool:
        """Wait up to the given seconds, keeping watch for the disengage prompt.
        Returns True if the supercruise exit was requested."""
        end = time.time() + seconds
        while time.time() < end:
            if self.try_sc_disengage(scr_reg):
                return True
            sleep(0.2)
        return False

    def compass_confirmed(self, scr_reg, close) -> bool:
        """Re-read the compass to confirm that the nav point is really ahead and centered."""
        for _ in range(2):
            sleep(0.2)
            off = self.get_nav_offset(scr_reg)
            if off is None or off["z"] <= 0 or abs(off["yaw"]) >= close or abs(off["pit"]) >= close:
                logger.debug(f"Compass align: confirmation reading {off} is not centered.")
                return False
        return True

    def read_nav_offset(self, scr_reg):
        """Read the compass nav point. When the compass or the nav point is not visible, wait and read again instead
        of steering on a guessed position. Returns None if it stays invisible."""
        for attempt in range(NAV_ALIGN_LOST_READS):
            off = self.get_nav_offset(scr_reg)
            if off is not None:
                return off
            if attempt < NAV_ALIGN_LOST_READS - 1:
                sleep(NAV_ALIGN_LOST_DELAY)
        return None

    @staticmethod
    def nav_needs_reroll(off, close) -> bool:
        """True when the nav point ahead is far off to the side and away from the vertical axis. Pitching cannot
        center it there: near the sphere rim small vertical offsets mean large pitch angles, so the ship overshoots
        back and forth. Rolling it to the vertical axis first lets the pitch bring it to the center."""
        return off["z"] > 0 and abs(off["yaw"]) > NAV_ALIGN_REROLL_YAW and close < abs(off["roll"]) < 180 - close

    def nav_align(self, scr_reg, abort_on_disengage=False) -> bool:
        """Use the compass to find the nav point position.  Will then perform rotation and pitching
        to put the nav point in the middle of the compass, i.e. target right in front of us.
        With abort_on_disengage the alignment is cancelled as soon as the supercruise exit was requested,
        and True is returned."""

        close = 10  # in degrees
        if not (self.jn.ship_state()["status"] == "in_supercruise" or self.jn.ship_state()["status"] == "in_space"):
            logger.error("align=err1, nav_align not in super or space")
            raise Exception("nav_align not in super or space")

        self.ap_ckb("log+vce", "Compass Align")

        # try multiple times to get aligned.  If the sun is shining on console, this it will be hard to match
        # the vehicle should be positioned with the sun below us via the sun_avoid() routine after a jump
        for ii in range(self.config["NavAlignTries"]):
            if abort_on_disengage and self.try_sc_disengage(scr_reg):
                return True
            off = self.read_nav_offset(scr_reg)
            if off is None:
                # Never steer without a reading: a guessed position turns the ship away from the target
                logger.warning("Compass Align: compass or nav point not visible, alignment stopped.")
                return False
            logger.debug(f"Compass align try {ii + 1}: {off}")

            # Check if we are close enough already; the nav point flickers, so the reading must be confirmed
            if abs(off["yaw"]) < close and abs(off["pit"]) < close:
                if self.compass_confirmed(scr_reg, close):
                    break
                logger.debug("Compass align: centered reading not confirmed, aligning again.")
                continue

            for reroll in range(NAV_ALIGN_MAX_REROLLS + 1):
                # Roll if the nav point is not directly behind us.
                if (-180 + close) < off["yaw"] < (180 - close) and (-180 + close) < off["pit"] < (180 - close):
                    for i in range(20):
                        # Calc roll time based on nav point location
                        if abs(off["roll"]) > close and (180 - abs(off["roll"]) > close):
                            # first roll to get the nav point at the vertical position
                            if off["yaw"] > 0 and off["pit"] > 0:
                                # top right quad, then roll right to get to 90 up
                                self.rotate_right(off["roll"])
                            elif off["yaw"] > 0 > off["pit"]:
                                # bottom right quad, then roll left
                                self.rotate_left(180 - off["roll"])
                            elif off["yaw"] < 0 < off["pit"]:
                                # top left quad, then roll left
                                self.rotate_left(-off["roll"])
                            else:
                                # bottom left quad, then roll right
                                self.rotate_right(180 + off["roll"])
                            sleep(1)
                            if abort_on_disengage and self.try_sc_disengage(scr_reg):
                                return True
                            off = self.read_nav_offset(scr_reg)
                            logger.debug(f"Compass align roll step {i + 1}: {off}")
                            if off is None:
                                break
                        else:
                            break
                if off is None:
                    break

                for i in range(20):
                    # Calc pitch time based on nav point location
                    if abs(off["pit"]) > close:
                        if off["pit"] < 0:
                            self.pitch_down(abs(off["pit"]))
                        else:
                            self.pitch_up(abs(off["pit"]))
                        sleep(0.5)
                        if abort_on_disengage and self.try_sc_disengage(scr_reg):
                            return True
                        off = self.read_nav_offset(scr_reg)
                        if off is None or (reroll < NAV_ALIGN_MAX_REROLLS and self.nav_needs_reroll(off, close)):
                            break
                    else:
                        break

                if off is None or reroll >= NAV_ALIGN_MAX_REROLLS or not self.nav_needs_reroll(off, close):
                    break
                logger.debug(f"Compass align: nav point far off to the side, rolling again: {off}")

            for i in range(20):
                # Calc yaw time based on nav point location
                if off is None:
                    break
                if abs(off["yaw"]) > close:
                    if off["yaw"] < 0:
                        self.yaw_left(abs(off["yaw"]))
                    else:
                        self.yaw_right(abs(off["yaw"]))
                    sleep(0.5)
                    if abort_on_disengage and self.try_sc_disengage(scr_reg):
                        return True
                    off = self.read_nav_offset(scr_reg)
                else:
                    break

            if off is None:
                logger.debug("Compass align: nav point lost while aligning, reading again.")
                continue
            sleep(0.1)
            logger.debug("final x:" + str(off["x"]) + " y:" + str(off["y"]))
        return False

    def fsd_target_align(self, scr_reg, close=50, allow_starting_hyperspace=False, proportional=False):
        """Coarse align to the target to support FSD jumping.

        With proportional=True the inputs get shorter near the target (used for retries, where precision matters).
        """

        self.vce.say("Target Align")

        logger.debug("align= fine align")
        start_time = time.monotonic()
        steps = 0

        # Base holds were tuned on a ship with yaw/pitch rates of FSD_REF_YAW_RATE/FSD_REF_PITCH_RATE deg/s;
        # scale them so other ships turn by about the same angle per step.
        hold_pitch = min(0.150 * FSD_REF_PITCH_RATE / self.pitchrate, 0.150 * FSD_HOLD_SCALE_MAX)
        hold_yaw = min(0.300 * FSD_REF_YAW_RATE / self.yawrate, 0.300 * FSD_HOLD_SCALE_MAX)
        new = None  # Initialize to avoid unbound variable
        off = None  # Initialize to avoid unbound variable

        for i in range(5):
            new = self.get_destination_offset(scr_reg)
            if new:
                off = new
                break
            sleep(0.25)

        # try one more time to align
        if new is None:
            self.nav_align(scr_reg)
            new = self.get_destination_offset(scr_reg)
            if new:
                off = new
            else:
                logger.debug("  out of fine -not off-" + "\n")
                return

        # Safety check to ensure off is valid before using it
        if off is None:
            logger.debug("  off is None, cannot continue alignment")
            return

        logger.debug(
            f"Fine align start: x={off['x']:.1f}, y={off['y']:.1f}, tolerance={close}px, proportional={proportional}."
        )
        step_gain = {"x": None, "y": None}  # measured px moved per second of hold, learned during this alignment
        while (off["x"] > close) or (off["x"] < -close) or (off["y"] > close) or (off["y"] < -close):
            yaw_hold = hold_yaw
            pitch_hold = hold_pitch
            if proportional:
                # A full hold moves the target by roughly FSD_TARGET_FULL_STEP_PX, so shorten it near the target.
                # Otherwise a fixed hold overshoots a small tolerance and the ship oscillates.
                yaw_hold = min(hold_yaw, max(FSD_TARGET_MIN_HOLD, hold_yaw * abs(off["x"]) / FSD_TARGET_FULL_STEP_PX))
                pitch_hold = min(
                    hold_pitch, max(FSD_TARGET_MIN_HOLD, hold_pitch * abs(off["y"]) / FSD_TARGET_FULL_STEP_PX)
                )
            # The configured rates can be far off for a ship, so shorten holds that would overshoot the target
            # according to the px/s measured in the previous steps.
            if step_gain["x"]:
                yaw_hold = min(yaw_hold, max(FSD_TARGET_MIN_HOLD, FSD_STEP_GAIN * abs(off["x"]) / step_gain["x"]))
            if step_gain["y"]:
                pitch_hold = min(pitch_hold, max(FSD_TARGET_MIN_HOLD, FSD_STEP_GAIN * abs(off["y"]) / step_gain["y"]))
            steps += 1
            before = dict(off)
            sent = {"x": 0.0, "y": 0.0}
            if off["x"] > close:
                self.keys.send("YawRightButton", hold=yaw_hold)
                sent["x"] = yaw_hold
            if off["x"] < -close:
                self.keys.send("YawLeftButton", hold=yaw_hold)
                sent["x"] = yaw_hold
            if off["y"] > close:
                self.keys.send("PitchUpButton", hold=pitch_hold)
                sent["y"] = pitch_hold
            if off["y"] < -close:
                self.keys.send("PitchDownButton", hold=pitch_hold)
                sent["y"] = pitch_hold

            if self.jn.ship_state()["status"] == "starting_hyperspace" and not allow_starting_hyperspace:
                return

            for i in range(5):
                sleep(0.1)
                new = self.get_destination_offset(scr_reg)
                if new:
                    off = new
                    break
                sleep(0.25)

            if not off:
                return

            for axis in ("x", "y"):
                moved = abs(off[axis] - before[axis])
                if sent[axis] > 0 and moved >= FSD_STEP_MIN_MOVE_PX:
                    step_gain[axis] = moved / sent[axis]
                    logger.debug(f"Fine align {axis}: moved {moved:.0f}px with {sent[axis]:.2f}s hold.")

        logger.debug(
            f"Fine align done in {time.monotonic() - start_time:.1f}s, {steps} steps, "
            f"final x={off['x']:.1f}, y={off['y']:.1f}, tolerance={close}px, proportional={proportional}."
        )
        logger.debug("align=complete")

    def mnvr_to_target(self, scr_reg, retry=False):
        logger.debug("align")
        ship_status = self.jn.ship_state()["status"]
        if ship_status not in ("in_supercruise", "in_space") and not (retry and ship_status == "starting_hyperspace"):
            logger.error("align() not in sc or space")
            raise Exception("align() not in sc or space")

        start_time = time.monotonic()
        self.sun_avoid(scr_reg)
        self.nav_align(scr_reg)
        self.keys.send("SetSpeed100")
        coarse_time = time.monotonic() - start_time

        self.fsd_target_align(
            scr_reg,
            close=FSD_RETRY_TARGET_CLOSE if retry else 50,
            allow_starting_hyperspace=retry,
            proportional=retry,
        )
        logger.debug(
            f"Alignment finished in {time.monotonic() - start_time:.1f}s "
            f"(sun avoid + compass align {coarse_time:.1f}s), retry={retry}."
        )

    def sc_target_align(self, scr_reg) -> ScTargetAlignReturn:
        """Stays tight on the target, monitors for disengage and obscured.
        If target could not be found, return false.
        @param scr_reg: The screen region class.
        @return: A string detailing the reason for the method return. Current return options:
            'lost': Lost target
            'found': Target found
            'disengage': Disengage text found
        """

        close = 6
        off = None

        hold_pitch = 0.100
        hold_yaw = 0.100
        for i in range(5):
            new = self.get_destination_offset(scr_reg)
            if new:
                off = new
                break
            if self.try_sc_disengage(scr_reg):
                return ScTargetAlignReturn.Disengage
            if self.is_destination_occluded(scr_reg):
                self.occluded_reposition(scr_reg)
                self.ap_ckb("log+vce", "Target Align")
            sleep(0.1)

        # Could not be found, return
        if off is None:
            logger.debug("sc_target_align not finding target")
            self.ap_ckb("log", "Target not found, terminating SC Assist")
            return ScTargetAlignReturn.Lost

        # logger.debug("sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

        while (abs(off["x"]) > close) or (abs(off["y"]) > close):
            if abs(off["x"]) > 25:
                hold_yaw = 0.2
            else:
                hold_yaw = 0.09

            if abs(off["y"]) > 25:
                hold_pitch = 0.15
            else:
                hold_pitch = 0.075

            # logger.debug("  sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

            if off["x"] > close:
                self.keys.send("YawRightButton", hold=hold_yaw)
            if off["x"] < -close:
                self.keys.send("YawLeftButton", hold=hold_yaw)
            if off["y"] > close:
                self.keys.send("PitchUpButton", hold=hold_pitch)
            if off["y"] < -close:
                self.keys.send("PitchDownButton", hold=hold_pitch)

            sleep(0.02)  # time for image to catch up

            # this checks if suddenly the target show up behind the planet
            if self.is_destination_occluded(scr_reg):
                self.occluded_reposition(scr_reg)
                self.ap_ckb("log+vce", "Target Align")

            # check for SC Disengage
            if self.try_sc_disengage(scr_reg):
                return ScTargetAlignReturn.Disengage

            new = self.get_destination_offset(scr_reg)
            if new:
                off = new

            # Check if target is outside the target region (behind us) and break loop
            if new is None:
                logger.debug("sc_target_align lost target")
                self.ap_ckb("log", "Target lost, attempting re-alignment.")
                return ScTargetAlignReturn.Lost

        # TODO - find a better way to clear these
        if self.debug_overlay:
            sleep(2)
            # self.overlay.overlay_remove_rect('sc_disengage_label_up')
            # self.overlay.overlay_remove_floating_text('sc_disengage_label_up')
            self.overlay.overlay_remove_rect("sc_disengage_active")
            self.overlay.overlay_remove_floating_text("sc_disengage_active")
            self.overlay.overlay_paint()

        return ScTargetAlignReturn.Found

    def try_sc_disengage(self, scr_reg) -> bool:
        """Check the disengage prompt and request the supercruise exit when it is active."""
        if not self.sc_disengage_label_up(scr_reg) or not self.sc_disengage_active(scr_reg):
            return False

        self.ap_ckb("log+vce", "Disengage Supercruise")
        self.keys.send("HyperSuperCombination")
        self.stop_sco_monitoring()
        return True

    def occluded_reposition(self, scr_reg):
        """Reposition is use when the target is occluded by a planet or other.
        We pitch 90 deg down for a bit, then up 90, this should make the target underneath us
        this is important because when we do nav_align() if it does not see the Nav Point
        in the compass (because it is a hollow circle), then it will pitch down, this will
        bring the target into view quickly."""
        self.ap_ckb("log+vce", "Target occluded, repositioning.")
        self.keys.send("SetSpeed50")
        sleep(5)
        self.pitch_down(90)

        # Speed away
        self.keys.send("SetSpeed100")
        sleep(15)

        self.keys.send("SetSpeed50")
        sleep(5)
        self.pitch_up(90)
        self.nav_align(scr_reg)
        self.keys.send("SetSpeed50")

    def honk(self, max_attempts=3, attempt_timeout=10):
        """Do the Discovery Scan (Honk). The scan counts as done when the journal reports
        FSSDiscoveryScan; otherwise it is retried up to max_attempts times."""

        if not self.status.get_flag(FlagsAnalysisMode):
            self.ap_ckb("log", "Not in analysis mode. Skipping discovery scan (honk).")
            return False

        fire = "PrimaryFire" if self.config["DSSButton"] == "Primary" else "SecondaryFire"
        scans_before = self.jn.ship_state()["discovery_scans"]

        for attempt in range(1, max_attempts + 1):
            logger.debug(f"position=scanning, attempt {attempt}/{max_attempts}")
            try:
                # Hold the button until the journal reports the finished scan.
                self.keys.send(fire, state=1)
                end_time = time.time() + attempt_timeout
                while time.time() < end_time:
                    sleep(0.25)
                    if self.jn.ship_state()["discovery_scans"] > scans_before:
                        logger.debug("position=scanning complete")
                        return True
            finally:
                self.keys.send(fire, state=0)

            self.ap_ckb("log", f"Discovery scan not confirmed (attempt {attempt}/{max_attempts}).")
            if not self.status.get_flag(FlagsAnalysisMode):
                break
            sleep(1)

        self.ap_ckb("log", "Discovery scan could not be confirmed.")
        return False

    def logout(self):
        """Performs menu action to log out of game"""
        self.set_ap_status("Logout")
        self.keys.send_key("Down", SCANCODE["Key_Escape"])
        sleep(0.5)
        self.keys.send_key("Up", SCANCODE["Key_Escape"])
        sleep(0.5)
        self.keys.send("UI_Up")
        sleep(0.5)
        self.keys.send("UI_Select")
        sleep(0.5)
        self.keys.send("UI_Select")
        sleep(0.5)
        self.set_ap_status("Idle")

    # position() happens after a refuel and accelerates past the sun before the discovery scan.
    def position(self, scr_reg, did_refuel=True):
        logger.debug("position")
        add_time = 12

        self.vce.say("Maneuvering")

        self.keys.send("SetSpeed100")

        # Need time to move past Sun, account for slowed ship if refuled
        pause_time = add_time
        if self.config["EnableRandomness"]:
            pause_time = pause_time + random.randint(0, 3)
        # need time to get away from the Sun so heat will disipate before we use FSD
        sleep(pause_time)

        sleep(5)  # Give the ship extra time to get away from the Sun before engaging the FSD.

        logger.debug("position=complete")
        return True

    def read_compass_alignment(self, scr_reg):
        """Read the compass nav point as (yaw, pitch) in degrees; None if the reading is implausible."""
        nav_offset = self.get_nav_offset(scr_reg)
        if nav_offset is None:
            logger.debug("FSD alignment reading rejected: no compass nav point.")
            return None
        if nav_offset["z"] < 0:
            self.fsd_behind_readings += 1
        if nav_offset["z"] <= 0 or abs(nav_offset["roll"]) > FSD_ALIGN_MAX_ROLL:
            logger.debug(f"FSD alignment reading rejected as implausible: {nav_offset}.")
            return None
        return nav_offset["yaw"], nav_offset["pit"]

    def measure_fsd_alignment(self, scr_reg):
        """Sample the compass several times; the nav point flickers while the prompt is shown, so implausible
        readings are dropped and the rest must agree. Returns (yaw, pitch) or None."""
        readings = []
        self.fsd_behind_readings = 0
        for i in range(FSD_ALIGN_SAMPLES):
            reading = self.read_compass_alignment(scr_reg)
            if reading is not None:
                readings.append(reading)
            if i < FSD_ALIGN_SAMPLES - 1:
                sleep(FSD_ALIGN_SAMPLE_DELAY)
        if len(readings) < 2:
            logger.debug(f"FSD alignment: only {len(readings)} plausible compass readings; no correction.")
            return None

        yaw_values = sorted(reading[0] for reading in readings)
        pit_values = sorted(reading[1] for reading in readings)
        yaw_median = yaw_values[len(yaw_values) // 2]
        pit_median = pit_values[len(pit_values) // 2]
        agreeing = [
            reading
            for reading in readings
            if abs(reading[0] - yaw_median) <= FSD_ALIGN_MAX_DIFF and abs(reading[1] - pit_median) <= FSD_ALIGN_MAX_DIFF
        ]
        if len(agreeing) < 2:
            logger.debug(f"FSD alignment readings disagree: {readings}; no correction.")
            return None
        return (
            sum(reading[0] for reading in agreeing) / len(agreeing),
            sum(reading[1] for reading in agreeing) / len(agreeing),
        )

    def correct_fsd_alignment(self, scr_reg):
        """Apply one small, proportional alignment input towards the compass nav point while the FSD charges.

        Returns True if an input was sent.
        """
        if self.status.get_flag(FlagsFsdJump):
            logger.debug("FSD alignment correction skipped: journal reports jump started.")
            return False

        measured = self.measure_fsd_alignment(scr_reg)
        if measured is None:
            return False
        yaw_off, pit_off = measured

        if max(abs(yaw_off), abs(pit_off)) <= FSD_ALIGN_TOLERANCE:
            logger.debug(
                f"FSD alignment correction skipped: compass yaw={yaw_off:.2f}, pit={pit_off:.2f} within tolerance."
            )
            return False

        if self.status.get_flag(FlagsFsdJump):
            logger.debug("FSD alignment correction skipped: journal reports jump started.")
            return False

        # Correct the larger axis first; the next cycle re-measures
        if abs(yaw_off) >= abs(pit_off):
            key = "YawRightButton" if yaw_off > 0 else "YawLeftButton"
            hold = abs(yaw_off) * FSD_ALIGN_GAIN / self.yawrate
        else:
            key = "PitchUpButton" if pit_off > 0 else "PitchDownButton"
            hold = abs(pit_off) * FSD_ALIGN_GAIN / self.pitchrate
        hold = min(max(hold, FSD_ALIGN_MIN_HOLD), FSD_ALIGN_MAX_HOLD)

        logger.debug(
            f"FSD alignment correction: compass yaw={yaw_off:.2f}, pit={pit_off:.2f}, key={key}, hold={hold:.2f}s."
        )
        self.keys.send(key, hold=hold)
        return True

    def wait_for_fsd_jump_start(self, scr_reg, timeout=30):
        """Wait for the journal status flag, using the HUD prompt only for small alignment corrections."""
        start_time = time.monotonic()
        next_prompt_check = start_time
        correction_count = 0
        elapsed = 0.0
        logger.debug(f"Waiting up to {timeout}s for journal FSD-jump flag.")
        while True:
            if self.status.get_flag(FlagsFsdJump):
                logger.debug(
                    f"Journal reports FSD jump started after {elapsed:.1f}s; alignment corrections={correction_count}."
                )
                return True

            now = time.monotonic()
            elapsed = now - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"Journal did not report FSD jump start within {timeout}s; alignment corrections={correction_count}."
                )
                return False

            if now >= next_prompt_check:
                next_prompt_check = now + 1
                charging = self.status.get_flag(FlagsFsdCharging)
                if not charging:
                    logger.debug("FSD alignment prompt check skipped: FSD charging flag is off.")
                else:
                    prompt_detected = self.fsd_alignment_prompt(scr_reg)
                    if prompt_detected:
                        logger.debug("FSD alignment prompt detected during charge.")
                        if self.correct_fsd_alignment(scr_reg):
                            correction_count += 1
                        elif self.fsd_behind_readings > FSD_ALIGN_SAMPLES // 2:
                            logger.warning("FSD alignment prompt shown and the compass reports the target behind.")
                            return False
                    else:
                        logger.debug("FSD alignment prompt not detected during charge.")

            sleep(0.1)

    # jump() happens after we are aligned to Target
    # TODO: nees to check for Thargoid interdiction and their wave that would shut us down,
    #       if thargoid, then we wait until reboot and continue on.. go back into FSD and align
    def jump(self, scr_reg):
        logger.debug("jump")

        self.vce.say("Frameshift Jump")

        jump_tries = self.config["JumpTries"]
        for i in range(jump_tries):
            logger.debug(f"FSD jump attempt {i + 1}/{jump_tries}.")
            ship_status = self.jn.ship_state()["status"]
            logger.debug(f"FSD jump attempt {i + 1}: journal ship status={ship_status}.")
            if i == 0 and ship_status not in ("in_supercruise", "in_space"):
                logger.error("Not ready to FSD jump. jump=err1")
                raise Exception("not ready to jump")
            if i > 0:
                if self.status.get_flag(FlagsFsdCharging) and not self.status.get_flag(FlagsFsdJump):
                    logger.info(f"FSD retry {i + 1}: cancelling the running charge.")
                    self.keys.send("HyperSuperCombination", hold=1)
                logger.debug(f"FSD retry {i + 1}: waiting for FSD jump and charge flags to clear.")
                if not self.status.wait_for_flag_off(FlagsFsdJump, 5):
                    logger.error("FSD jump is still active; cannot realign.")
                    continue
                if not self.status.wait_for_flag_off(FlagsFsdCharging, 5):
                    logger.error("FSD is still charging after cancel; cannot realign.")
                    continue
                logger.info(f"FSD retry {i + 1}: realigning before the next charge.")
                self.mnvr_to_target(scr_reg, retry=True)
            sleep(0.5)
            logger.debug(f"FSD jump attempt {i + 1}: sending HyperSuperCombination.")

            self.keys.send("HyperSuperCombination", hold=1)

            # Start SCO monitoring ready when we drop back to SC.
            self.start_sco_monitoring()

            res = self.status.wait_for_flag_on(FlagsFsdCharging, 5)
            if not res:
                logger.error("FSD failed to charge.")
                continue
            logger.debug(f"FSD jump attempt {i + 1}: charge flag detected.")

            res = self.wait_for_fsd_jump_start(scr_reg, 30)
            if not res:
                logger.warning(f"FSD jump attempt {i + 1}: start timeout; moving to retry handling.")
                continue

            logger.debug(f"FSD jump attempt {i + 1}: jump flag detected; waiting for completion.")
            # Wait for jump to complete. Should never err
            res = self.status.wait_for_flag_off(FlagsFsdJump, 360)
            if not res:
                logger.error(f"FSD jump attempt {i + 1}: completion timed out.")
                continue

            logger.debug(f"FSD jump attempt {i + 1}: jump completed.")
            self.keys.send("SetSpeedZero", repeat=3)  # Let's be triply sure that we set speed to 0% :)
            sleep(1)  # wait 1 sec after jump to allow graphics to stablize and accept inputs
            logger.debug("FSD jump handling complete.")
            return True

        logger.error(f"FSD Jump failed {jump_tries} times. jump=err2")
        raise Exception("FSD Jump failure")

    #
    def rotate_left(self, deg):
        htime = deg / self.rollrate
        self.keys.send("RollLeftButton", hold=htime)

    def rotate_right(self, deg):
        htime = deg / self.rollrate
        self.keys.send("RollRightButton", hold=htime)

    def pitch_down(self, deg):
        htime = deg / self.pitchrate
        self.keys.send("PitchDownButton", htime)

    def pitch_up(self, deg):
        htime = deg / self.pitchrate
        self.keys.send("PitchUpButton", htime)

    def yaw_left(self, deg):
        htime = deg / self.yawrate
        self.keys.send("YawLeftButton", hold=htime)

    def yaw_right(self, deg):
        htime = deg / self.yawrate
        self.keys.send("YawRightButton", hold=htime)

    def refuel(self, scr_reg):
        """Check if refueling needed, ensure correct start type."""
        # Check if we have a fuel scoop
        has_fuel_scoop = self.jn.ship_state()["has_fuel_scoop"]

        logger.debug("refuel")

        if self.jn.ship_state()["status"] != "in_supercruise":
            logger.error("refuel=err1")
            return False

        is_star_scoopable = self.jn.ship_state()["star_class"] in SCOOPABLE_STAR_CLASSES

        # if the sun is not scoopable, then set a low low threshold so we can pick up the dull red
        # sun types.  Since we won't scoop it doesn't matter how much we pitch up
        # if scoopable we know white/yellow stars are bright, so set higher threshold, this will allow us to
        #  mast out the galaxy edge (which is bright) and not pitch up too much and avoid scooping
        if not is_star_scoopable or not has_fuel_scoop:
            scr_reg.set_sun_threshold(25)
        else:
            scr_reg.set_sun_threshold(self.config["SunBrightThreshold"])

        # Lets avoid the sun, shall we
        self.vce.say("Avoiding star")
        self.set_ap_status("Avoiding star")
        self.sun_avoid(scr_reg)

        if (
            self.jn.ship_state()["fuel_percent"] < self.config["RefuelThreshold"]
            and is_star_scoopable
            and has_fuel_scoop
        ):
            logger.debug("refuel= start refuel")
            self.vce.say("Refueling")
            self.set_ap_status("Refueling")

            # mnvr into position
            self.keys.send("SetSpeed100")
            sleep(5)
            self.keys.send("SetSpeed50")
            sleep(1.7)
            self.keys.send("SetSpeedZero", repeat=3)

            # The log will not reflect a FuelScoop until first 5 tons filled, then every 5 tons until complete
            # if we don't scoop first 5 tons with 40 sec break, since not scooping or not fast enough or not at all, then abort
            startime = time.time()
            while not self.jn.ship_state()["is_scooping"] and not self.jn.ship_state()["fuel_percent"] == 100:
                # check if we are being interdicted
                interdicted = self.interdiction_check()
                if interdicted:
                    # Continue journey after interdiction
                    self.keys.send("SetSpeedZero")

                if (time.time() - startime) > int(self.config["FuelScoopTimeOut"]):
                    self.vce.say("Refueling abort, insufficient scooping")
                    return False

            logger.debug("refuel= wait for refuel")

            # We started fueling, so lets give it another timeout period to fuel up
            startime = time.time()
            while not self.jn.ship_state()["fuel_percent"] == 100:
                # check if we are being interdicted
                interdicted = self.interdiction_check()
                if interdicted:
                    # Continue journey after interdiction
                    self.keys.send("SetSpeedZero")

                if (time.time() - startime) > int(self.config["FuelScoopTimeOut"]):
                    self.vce.say("Refueling abort, insufficient scooping")
                    return True
                sleep(1)

            logger.debug("refuel=complete")
            return True

        elif not is_star_scoopable:
            self.ap_ckb("log", "Skip refuel - not a fuel star")
            logger.debug("refuel= needed, unsuitable star")
            self.pitch_up(20)
            return False

        elif self.jn.ship_state()["fuel_percent"] >= self.config["RefuelThreshold"]:
            self.ap_ckb("log", "Skip refuel - fuel level okay")
            logger.debug("refuel= not needed")
            return False

        elif not has_fuel_scoop:
            self.ap_ckb("log", "Skip refuel - no fuel scoop fitted")
            logger.debug("No fuel scoop fitted.")
            self.pitch_up(20)
            return False

        else:
            self.pitch_up(15)  # if not refueling pitch up somemore so we won't heat up
            return False

    def waypoint_undock_seq(self):
        self.set_ap_status("Executing Undocking/Launch")

        # Store current location (on planet or in space)
        on_planet = self.status.get_flag(FlagsHasLatLong)
        on_orbital_construction_site = (
            self.jn.ship_state()["cur_station_type"].upper() == "SpaceConstructionDepot".upper()
        )
        fleet_carrier = self.jn.ship_state()["cur_station_type"].upper() == "FleetCarrier".upper()

        # Leave starport or planetary port
        if not on_planet:
            # Check that we are docked
            if self.status.get_flag(FlagsDocked):
                # Check if we have an advanced docking computer
                if not self.jn.ship_state()["has_adv_dock_comp"]:
                    self.ap_ckb("log", "Unable to undock. Advanced Docking Computer not fitted.")
                    logger.warning("Unable to undock. Advanced Docking Computer not fitted.")
                    raise Exception("Unable to undock. Advanced Docking Computer not fitted.")

                # Undock from station
                self.undock()

                # need to wait until undock complete, that is when we are back in_space
                while self.jn.ship_state()["status"] != "in_space":
                    sleep(1)

                # If we are on an Orbital Construction Site we will need to pitch up 90 deg to avoid crashes
                if on_orbital_construction_site:
                    self.ap_ckb("log+vce", "Maneuvering")
                    # The pitch rates are defined in SC, not normal flights, so bump this up a bit
                    self.pitch_up(90 * 1.25)

                # If we are on a Fleet Carrier we will pitch up 90 deg and fly away to avoid planet
                elif fleet_carrier:
                    self.ap_ckb("log+vce", "Maneuvering")
                    # The pitch rates are defined in SC, not normal flights, so bump this up a bit
                    self.pitch_up(90 * 1.25)

                    self.keys.send("SetSpeed100")

                    # While Mass Locked, keep boosting.
                    while not self.status.wait_for_flag_off(FlagsFsdMassLocked, timeout=2):
                        self.keys.send("UseBoostJuice")

                    # Enter supercruise to get away from the Fleet Carrier
                    self.keys.send("Supercruise")

                    # Start SCO monitoring
                    self.start_sco_monitoring()

                    # Wait the configured time before continuing
                    self.ap_ckb("log", "Flying for configured FC departure time.")
                    sleep(self.config["FCDepartureTime"])
                    self.keys.send("SetSpeed50")

                if not fleet_carrier:
                    # In space (launched from starport or outpost etc.)
                    sleep(1.5)
                    self.set_ap_status("Undock Complete, accelerating")
                    self.keys.send("SetSpeed100")
                    sleep(1)
                    self.keys.send("UseBoostJuice")
                    sleep(13)  # get away from Station
                    self.keys.send("SetSpeed50")

        elif on_planet:
            # Check if we are on a landing pad (docked), or landed on the planet surface
            if self.status.get_flag(FlagsDocked):
                # We are on a landing pad (docked)
                # Check if we have an advanced docking computer
                if not self.jn.ship_state()["has_adv_dock_comp"]:
                    self.ap_ckb("log", "Unable to undock. Advanced Docking Computer not fitted.")
                    logger.warning("Unable to undock. Advanced Docking Computer not fitted.")
                    raise Exception("Unable to undock. Advanced Docking Computer not fitted.")

                # Undock from port
                self.undock()

                # need to wait until undock complete, that is when we are back in_space
                while self.jn.ship_state()["status"] != "in_space":
                    sleep(1)
                self.set_ap_status("Undock Complete, accelerating")

            elif self.status.get_flag(FlagsLanded):
                # We are on planet surface (not docked at planet landing pad)
                # Hold UP for takeoff
                self.keys.send("UpThrustButton", hold=6)
                self.keys.send("LandingGearToggle")
                self.set_ap_status("Takeoff Complete, accelerating")

            # Undocked or off the surface, so leave planet
            self.keys.send("SetSpeed50")
            # The pitch rates are defined in SC, not normal flights, so bump this up a bit
            self.pitch_up(90 * 1.25)
            self.keys.send("SetSpeed100")

            # While Mass Locked, keep boosting.
            while not self.status.wait_for_flag_off(FlagsFsdMassLocked, timeout=2):
                self.keys.send("UseBoostJuice")

            # Enter supercruise
            self.keys.send("Supercruise")

            # Start SCO monitoring
            self.start_sco_monitoring()

            # Wait for SC
            self.status.wait_for_flag_on(FlagsSupercruise, timeout=30)

            # Enable SCO. If SCO not fitted, this will do nothing.
            self.keys.send("UseBoostJuice")

            # Wait until out of orbit.
            self.status.wait_for_flag_off(FlagsHasLatLong, timeout=60)
            # TODO - do we need to check if we never leave orbit?

            # Disable SCO. If SCO not fitted, this will do nothing.
            self.keys.send("UseBoostJuice")
            self.keys.send("SetSpeed50")

    def sc_engage(self):
        """Engages supercruise, then returns us to 50% speed"""
        self.set_ap_status("Entering supercruise")
        self.keys.send("SetSpeed100")
        self.keys.send("Supercruise", hold=0.001)
        # Start SCO monitoring
        self.start_sco_monitoring()
        # TODO - check if we actually go into supercruise
        sleep(12)

        self.keys.send("SetSpeed50")

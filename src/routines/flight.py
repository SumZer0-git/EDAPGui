"""Ship maneuvers: aligning, jumping, docking, undocking and refueling."""

import random
import threading
import time
from time import sleep

from controls.directinput import SCANCODE
from core.constants import (
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


class FlightMixin:

    def start_sco_monitoring(self):
        """ Start Supercruise Overcharge Monitoring. This starts a parallel thread used to detect SCO
        until stop_sco_monitoring if called. """
        self._sc_sco_active_loop_enable = True

        if self._sc_sco_active_loop_thread is None or not self._sc_sco_active_loop_thread.is_alive():
            self._sc_sco_active_loop_thread = threading.Thread(target=self._sc_sco_active_loop, daemon=True)
            self._sc_sco_active_loop_thread.start()

    def stop_sco_monitoring(self):
        """ Stop Supercruise Overcharge Monitoring. """
        self._sc_sco_active_loop_enable = False

    def _sc_sco_active_loop(self):
        """ A loop to determine is Supercruise Overcharge is active.
        This runs on a separate thread monitoring the status in the background. """
        while self._sc_sco_active_loop_enable:
            # Try to determine if the disengage/sco text is there
            sc_sco_is_active_ls = self.sc_sco_is_active

            # Check if SCO active in flags
            self.sc_sco_is_active = self.status.get_flag2(Flags2FsdScoActive)

            if self.sc_sco_is_active and not sc_sco_is_active_ls:
                self.ap_ckb('log+vce', "Supercruise Overcharge activated")
            if sc_sco_is_active_ls and not self.sc_sco_is_active:
                self.ap_ckb('log+vce', "Supercruise Overcharge deactivated")

            # Protection if SCO is active
            if self.sc_sco_is_active:
                if self.status.get_flag(FlagsOverHeating):
                    logger.info("SCO Aborting, overheating")
                    self.ap_ckb('log+vce', "SCO Aborting, overheating")
                    self.keys.send('UseBoostJuice')
                elif self.status.get_flag(FlagsLowFuel):
                    logger.info("SCO Aborting, < 25% fuel")
                    self.ap_ckb('log+vce', "SCO Aborting, < 25% fuel")
                    self.keys.send('UseBoostJuice')
                elif self.jn.ship_state()['fuel_percent'] < self.config['FuelThreasholdAbortAP']:
                    logger.info("SCO Aborting, < users low fuel threshold")
                    self.ap_ckb('log+vce', "SCO Aborting, < users low fuel threshold")
                    self.keys.send('UseBoostJuice')

            # Check again in a bit
            sleep(1)

    def undock(self):
        """ Performs menu action to undock from Station """
        # Go to cockpit view
        self.ship_control.goto_cockpit_view()

        # Now we are on initial menu, we go up to top (which is Refuel)
        self.keys.send('UI_Up', repeat=3)

        # down to Auto Undock and Select it...
        self.keys.send('UI_Down')
        self.keys.send('UI_Down')
        self.keys.send('UI_Select')
        self.keys.send('SetSpeedZero', repeat=2)

    def request_docking(self):
        """ Request docking from Nav Panel. """
        self.nav_panel.request_docking()

    def dock(self):
        """ Docking sequence.  Assumes in normal space, will get closer to the Station
        then zero the velocity and execute menu commands to request docking, when granted
        will wait a configurable time for dock.  Perform Refueling and Repair.
        """
        # if not in normal space, give a few more sections as at times it will take a little bit
        if self.jn.ship_state()['status'] != "in_space":
            sleep(3)  # sleep a little longer

        if self.jn.ship_state()['status'] != "in_space":
            logger.error('In dock(), after wait, but still not in_space')

        sleep(5)  # wait 5 seconds to get to 7.5km to request docking
        self.keys.send('SetSpeed50')

        if self.jn.ship_state()['status'] != "in_space":
            self.keys.send('SetSpeedZero')
            logger.error('In dock(), after long wait, but still not in_space')
            raise Exception('Docking failed (not in space)')

        sleep(12)
        # At this point (of sleep()) we should be < 7.5km from the station.  Go 0 speed
        # if we get docking granted ED's docking computer will take over
        self.keys.send('SetSpeedZero', repeat=2)
        sleep(3)  # Wait for ship to come to stop
        self.ap_ckb('log+vce', "Initiating Docking Procedure")
        # Request docking through Nav panel.
        self.request_docking()
        sleep(1)

        tries = self.config['DockingRetries']
        granted = False
        if self.jn.ship_state()['status'] == "dockinggranted":
            granted = True
        else:
            for i in range(tries):
                if self.jn.ship_state()['no_dock_reason'] == "Distance":
                    self.keys.send('SetSpeed50')
                    sleep(5)
                    self.keys.send('SetSpeedZero', repeat=2)
                sleep(3)  # Wait for ship to come to stop
                # Request docking through Nav panel.
                self.request_docking()
                self.keys.send('SetSpeedZero', repeat=2)

                sleep(1.5)
                if self.jn.ship_state()['status'] == "dockinggranted":
                    granted = True
                    # Go back to navigation tab
                    #self.request_docking_cleanup()
                    break
                if self.jn.ship_state()['status'] == "dockingdenied":
                    pass

        if not granted:
            self.ap_ckb('log', 'Docking denied: '+str(self.jn.ship_state()['no_dock_reason']))
            logger.warning('Did not get docking authorization, reason:'+str(self.jn.ship_state()['no_dock_reason']))
            raise Exception('Docking failed (Did not get docking authorization)')
        else:
            self.ap_ckb('log+vce', "Docking request granted")
            # allow auto dock to take over
            for i in range(self.config['WaitForAutoDockTimer']):
                sleep(1)
                if self.jn.ship_state()['status'] == "in_station":
                    # go to top item, select (which should be refuel)
                    self.keys.send('UI_Up', hold=3)
                    self.keys.send('UI_Select')  # Refuel
                    sleep(0.5)
                    self.keys.send('UI_Right')  # Repair
                    self.keys.send('UI_Select')
                    sleep(0.5)
                    self.keys.send('UI_Right')  # Ammo
                    self.keys.send('UI_Select')
                    sleep(0.5)
                    self.keys.send("UI_Left", repeat=2)  # back to fuel
                    return

            self.ap_ckb('log', 'Auto dock timer timed out.')
            logger.warning('Auto dock timer timed out. Aborting Docking.')
            raise Exception('Docking failed (Auto dock timer timed out)')

    # use to orient the ship to not be pointing right at the Sun
    # Checks brightness in the region in front of us, if brightness exceeds a threshold
    # then will pitch up until below threshold.
    #
    def sun_avoid(self, scr_reg):
        logger.debug('align= avoid sun')

        sleep(0.5)

        # close to core the 'sky' is very bright with close stars, if we are pitch due to a non-scoopable star
        #  which is dull red, the star field is 'brighter' than the sun, so our sun avoidance could pitch up
        #  endlessly. So we will have a fail_safe_timeout to kick us out of pitch up if we've pitch past 110 degrees, but
        #  we'll add 3 more second for pad in case the user has a higher pitch rate than the vehicle can do
        fail_safe_timeout = (120/self.pitchrate)+3
        starttime = time.time()

        # if sun in front of us, then keep pitching up until it is below us
        while self.is_sun_dead_ahead(scr_reg):
            self.keys.send('PitchUpButton', state=1)

            # check if we are being interdicted
            interdicted = self.interdiction_check()
            if interdicted:
                # Continue journey after interdiction
                self.keys.send('SetSpeedZero')

            # if we are pitching more than N seconds break, may be in high density area star area (close to core)
            if ((time.time()-starttime) > fail_safe_timeout):
                logger.debug('sun avoid failsafe timeout')
                print("sun avoid failsafe timeout")
                break

        sleep(0.35)                 # up slightly so not to overheat when scooping
        # Some ships heat up too much and need pitch up a little further
        if self.sunpitchuptime > 0.0:
            sleep(self.sunpitchuptime)
        self.keys.send('PitchUpButton', state=0)

        # Some ships run cool so need to pitch down a little
        if self.sunpitchuptime < 0.0:
            self.keys.send('PitchDownButton', state=1)
            sleep(-1.0 * self.sunpitchuptime)
            self.keys.send('PitchDownButton', state=0)

    def nav_align(self, scr_reg):
        """ Use the compass to find the nav point position.  Will then perform rotation and pitching
        to put the nav point in the middle of the compass, i.e. target right in front of us """

        close = 10  # in degrees
        if not (self.jn.ship_state()['status'] == 'in_supercruise' or self.jn.ship_state()['status'] == 'in_space'):
            logger.error('align=err1, nav_align not in super or space')
            raise Exception('nav_align not in super or space')

        self.ap_ckb('log+vce', 'Compass Align')

        # try multiple times to get aligned.  If the sun is shining on console, this it will be hard to match
        # the vehicle should be positioned with the sun below us via the sun_avoid() routine after a jump
        for ii in range(self.config['NavAlignTries']):
            off = self.get_nav_offset(scr_reg)

            # Check if we are close enough already
            if abs(off['yaw']) < close and abs(off['pit']) < close:
                break

            # Roll if the nav point is not directly behind us.
            if ((-180 + close) < off['yaw'] < (180 - close) and
                    (-180 + close) < off['pit'] < (180 - close)):

                for i in range(20):
                    # Calc roll time based on nav point location
                    if abs(off['roll']) > close and (180 - abs(off['roll']) > close):
                        # first roll to get the nav point at the vertical position
                        if off['yaw'] > 0 and off['pit'] > 0:
                            # top right quad, then roll right to get to 90 up
                            self.rotate_right(off['roll'])
                        elif off['yaw'] > 0 > off['pit']:
                            # bottom right quad, then roll left
                            self.rotate_left(180 - off['roll'])
                        elif off['yaw'] < 0 < off['pit']:
                            # top left quad, then roll left
                            self.rotate_left(-off['roll'])
                        else:
                            # bottom left quad, then roll right
                            self.rotate_right(180 + off['roll'])
                        sleep(1)
                        off = self.get_nav_offset(scr_reg)
                    else:
                        break

            for i in range(20):
                # Calc pitch time based on nav point location
                if abs(off['pit']) > close:
                    if off['pit'] < 0:
                        self.pitch_down(abs(off['pit']))
                    else:
                        self.pitch_up(abs(off['pit']))
                    sleep(0.5)
                    off = self.get_nav_offset(scr_reg)
                else:
                    break

            for i in range(20):
                # Calc yaw time based on nav point location
                if abs(off['yaw']) > close:
                    if off['yaw'] < 0:
                        self.yaw_left(abs(off['yaw']))
                    else:
                        self.yaw_right(abs(off['yaw']))
                    sleep(0.5)
                    off = self.get_nav_offset(scr_reg)
                else:
                    break

            sleep(.1)
            logger.debug("final x:"+str(off['x'])+" y:"+str(off['y']))

    def fsd_target_align(self, scr_reg):
        """ Coarse align to the target to support FSD jumping """

        self.vce.say("Target Align")

        logger.debug('align= fine align')

        close = 50

        # TODO: should use Pitch Rates to calculate, but this seems to work fine with all ships
        hold_pitch = 0.150
        hold_yaw = 0.300
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
                logger.debug('  out of fine -not off-'+'\n')
                return

        # Safety check to ensure off is valid before using it
        if off is None:
            logger.debug('  off is None, cannot continue alignment')
            return

        while (off['x'] > close) or \
              (off['x'] < -close) or \
              (off['y'] > close) or \
              (off['y'] < -close):


            #print("off:"+str(new))
            if off['x'] > close:
                self.keys.send('YawRightButton', hold=hold_yaw)
            if off['x'] < -close:
                self.keys.send('YawLeftButton', hold=hold_yaw)
            if off['y'] > close:
                self.keys.send('PitchUpButton', hold=hold_pitch)
            if off['y'] < -close:
                self.keys.send('PitchDownButton', hold=hold_pitch)

            if self.jn.ship_state()['status'] == 'starting_hyperspace':
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

        logger.debug('align=complete')

    def mnvr_to_target(self, scr_reg):
        logger.debug('align')
        if not (self.jn.ship_state()['status'] == 'in_supercruise' or self.jn.ship_state()['status'] == 'in_space'):
            logger.error('align() not in sc or space')
            raise Exception('align() not in sc or space')

        self.sun_avoid(scr_reg)
        self.nav_align(scr_reg)
        self.keys.send('SetSpeed100')

        self.fsd_target_align(scr_reg)

    def sc_target_align(self, scr_reg) -> ScTargetAlignReturn:
        """ Stays tight on the target, monitors for disengage and obscured.
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
            if self.is_destination_occluded(scr_reg):
                self.occluded_reposition(scr_reg)
                self.ap_ckb('log+vce', 'Target Align')
            sleep(0.1)

        # Could not be found, return
        if off is None:
            logger.debug("sc_target_align not finding target")
            self.ap_ckb('log', 'Target not found, terminating SC Assist')
            return ScTargetAlignReturn.Lost

        #logger.debug("sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

        while (abs(off['x']) > close) or \
                (abs(off['y']) > close):

            if abs(off['x']) > 25:
                hold_yaw = 0.2
            else:
                hold_yaw = 0.09

            if abs(off['y']) > 25:
                hold_pitch = 0.15
            else:
                hold_pitch = 0.075

            #logger.debug("  sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

            if off['x'] > close:
                self.keys.send('YawRightButton', hold=hold_yaw)
            if off['x'] < -close:
                self.keys.send('YawLeftButton', hold=hold_yaw)
            if off['y'] > close:
                self.keys.send('PitchUpButton', hold=hold_pitch)
            if off['y'] < -close:
                self.keys.send('PitchDownButton', hold=hold_pitch)

            sleep(.02)  # time for image to catch up

            # this checks if suddenly the target show up behind the planet
            if self.is_destination_occluded(scr_reg):
                self.occluded_reposition(scr_reg)
                self.ap_ckb('log+vce', 'Target Align')

            # check for SC Disengage
            if self.sc_disengage_label_up(scr_reg):
                if self.sc_disengage_active(scr_reg):
                    self.ap_ckb('log+vce', 'Disengage Supercruise')
                    self.keys.send('HyperSuperCombination')
                    self.stop_sco_monitoring()
                    return ScTargetAlignReturn.Disengage

            new = self.get_destination_offset(scr_reg)
            if new:
                off = new

            # Check if target is outside the target region (behind us) and break loop
            if new is None:
                logger.debug("sc_target_align lost target")
                self.ap_ckb('log', 'Target lost, attempting re-alignment.')
                return ScTargetAlignReturn.Lost

        # TODO - find a better way to clear these
        if self.debug_overlay:
            sleep(2)
            # self.overlay.overlay_remove_rect('sc_disengage_label_up')
            # self.overlay.overlay_remove_floating_text('sc_disengage_label_up')
            self.overlay.overlay_remove_rect('sc_disengage_active')
            self.overlay.overlay_remove_floating_text('sc_disengage_active')
            self.overlay.overlay_paint()

        return ScTargetAlignReturn.Found

    def occluded_reposition(self, scr_reg):
        """ Reposition is use when the target is occluded by a planet or other.
        We pitch 90 deg down for a bit, then up 90, this should make the target underneath us
        this is important because when we do nav_align() if it does not see the Nav Point
        in the compass (because it is a hollow circle), then it will pitch down, this will
        bring the target into view quickly. """
        self.ap_ckb('log+vce', 'Target occluded, repositioning.')
        self.keys.send('SetSpeed50')
        sleep(5)
        self.pitch_down(90)

        # Speed away
        self.keys.send('SetSpeed100')
        sleep(15)

        self.keys.send('SetSpeed50')
        sleep(5)
        self.pitch_up(90)
        self.nav_align(scr_reg)
        self.keys.send('SetSpeed50')

    def honk(self):
        # Do the Discovery Scan (Honk)

        if self.status.get_flag(FlagsAnalysisMode):
            if self.config['DSSButton'] == 'Primary':
                logger.debug('position=scanning')
                self.keys.send('PrimaryFire', state=1)
            else:
                logger.debug('position=scanning')
                self.keys.send('SecondaryFire', state=1)

            sleep(7)  # roughly 6 seconds for DSS

            # stop pressing the Scanner button
            if self.config['DSSButton'] == 'Primary':
                logger.debug('position=scanning complete')
                self.keys.send('PrimaryFire', state=0)
            else:
                logger.debug('position=scanning complete')
                self.keys.send('SecondaryFire', state=0)
        else:
            self.ap_ckb('log', 'Not in analysis mode. Skipping discovery scan (honk).')

    def logout(self):
        """ Performs menu action to log out of game """
        self.update_ap_status("Logout")
        self.keys.send_key('Down', SCANCODE["Key_Escape"])
        sleep(0.5)
        self.keys.send_key('Up', SCANCODE["Key_Escape"])
        sleep(0.5)
        self.keys.send('UI_Up')
        sleep(0.5)
        self.keys.send('UI_Select')
        sleep(0.5)
        self.keys.send('UI_Select')
        sleep(0.5)
        self.update_ap_status("Idle")

    # position() happens after a refuel and performs
    #   - accelerate past sun
    #   - perform Discovery scan
    #   - perform fss (if enabled)
    def position(self, scr_reg, did_refuel=True):
        logger.debug('position')
        add_time = 12

        self.vce.say("Maneuvering")

        self.keys.send('SetSpeed100')

        # Need time to move past Sun, account for slowed ship if refuled
        pause_time = add_time
        if self.config["EnableRandomness"]:
            pause_time = pause_time+random.randint(0, 3)
        # need time to get away from the Sun so heat will disipate before we use FSD
        sleep(pause_time)

        if self.config["ElwScannerEnable"]:
            self.fss_detect_elw(scr_reg)
            if self.config["EnableRandomness"]:
                sleep(random.randint(0, 3))
            sleep(3)
        else:
            sleep(5)  # since not doing FSS, need to give a little more time to get away from Sun, for heat

        logger.debug('position=complete')
        return True

    # jump() happens after we are aligned to Target
    # TODO: nees to check for Thargoid interdiction and their wave that would shut us down,
    #       if thargoid, then we wait until reboot and continue on.. go back into FSD and align
    def jump(self, scr_reg):
        logger.debug('jump')

        self.vce.say("Frameshift Jump")

        jump_tries = self.config['JumpTries']
        for i in range(jump_tries):

            logger.debug('jump= try:'+str(i))
            if not (self.jn.ship_state()['status'] == 'in_supercruise' or self.jn.ship_state()['status'] == 'in_space'):
                logger.error('Not ready to FSD jump. jump=err1')
                raise Exception('not ready to jump')
            sleep(0.5)
            logger.debug('jump= start fsd')

            self.keys.send('HyperSuperCombination', hold=1)

            # Start SCO monitoring ready when we drop back to SC.
            self.start_sco_monitoring()

            res = self.status.wait_for_flag_on(FlagsFsdCharging, 5)
            if not res:
                logger.error('FSD failed to charge.')
                continue

            res = self.status.wait_for_flag_on(FlagsFsdJump, 30)
            if not res:
                logger.warning('FSD failure to start jump timeout.')
                self.mnvr_to_target(scr_reg)  # attempt realign to target
                continue

            logger.debug('jump= in jump')
            # Wait for jump to complete. Should never err
            res = self.status.wait_for_flag_off(FlagsFsdJump, 360)
            if not res:
                logger.error('FSD failure to complete jump timeout.')
                continue

            logger.debug('jump= speed 0')
            self.jump_cnt = self.jump_cnt+1
            self.keys.send('SetSpeedZero', repeat=3)  # Let's be triply sure that we set speed to 0% :)
            sleep(1)  # wait 1 sec after jump to allow graphics to stablize and accept inputs
            logger.debug('jump=complete')
            return True

        logger.error(f'FSD Jump failed {jump_tries} times. jump=err2')
        raise Exception("FSD Jump failure")

    #
    def rotate_left(self, deg):
        htime = deg/self.rollrate
        self.keys.send('RollLeftButton', hold=htime)

    def rotate_right(self, deg):
        htime = deg/self.rollrate
        self.keys.send('RollRightButton', hold=htime)

    def pitch_down(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchDownButton', htime)

    def pitch_up(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchUpButton', htime)

    def yaw_left(self, deg):
        htime = deg/self.yawrate
        self.keys.send('YawLeftButton', hold=htime)

    def yaw_right(self, deg):
        htime = deg / self.yawrate
        self.keys.send('YawRightButton', hold=htime)

    def refuel(self, scr_reg):
        """ Check if refueling needed, ensure correct start type. """
        # Check if we have a fuel scoop
        has_fuel_scoop = self.jn.ship_state()['has_fuel_scoop']

        logger.debug('refuel')
        scoopable_stars = ['F', 'O', 'G', 'K', 'B', 'A', 'M']

        if self.jn.ship_state()['status'] != 'in_supercruise':
            logger.error('refuel=err1')
            return False

        is_star_scoopable = self.jn.ship_state()['star_class'] in scoopable_stars

        # if the sun is not scoopable, then set a low low threshold so we can pick up the dull red
        # sun types.  Since we won't scoop it doesn't matter how much we pitch up
        # if scoopable we know white/yellow stars are bright, so set higher threshold, this will allow us to
        #  mast out the galaxy edge (which is bright) and not pitch up too much and avoid scooping
        if not is_star_scoopable or not has_fuel_scoop:
            scr_reg.set_sun_threshold(25)
        else:
            scr_reg.set_sun_threshold(self.config['SunBrightThreshold'])

        # Lets avoid the sun, shall we
        self.vce.say("Avoiding star")
        self.update_ap_status("Avoiding star")
        self.ap_ckb('log', 'Avoiding star')
        self.sun_avoid(scr_reg)

        if self.jn.ship_state()['fuel_percent'] < self.config['RefuelThreshold'] and is_star_scoopable and has_fuel_scoop:
            logger.debug('refuel= start refuel')
            self.vce.say("Refueling")
            self.ap_ckb('log', 'Refueling')
            self.update_ap_status("Refueling")

            # mnvr into position
            self.keys.send('SetSpeed100')
            sleep(5)
            self.keys.send('SetSpeed50')
            sleep(1.7)
            self.keys.send('SetSpeedZero', repeat=3)

            self.refuel_cnt += 1

            # The log will not reflect a FuelScoop until first 5 tons filled, then every 5 tons until complete
            #if we don't scoop first 5 tons with 40 sec break, since not scooping or not fast enough or not at all, then abort
            startime = time.time()
            while not self.jn.ship_state()['is_scooping'] and not self.jn.ship_state()['fuel_percent'] == 100:
                # check if we are being interdicted
                interdicted = self.interdiction_check()
                if interdicted:
                    # Continue journey after interdiction
                    self.keys.send('SetSpeedZero')

                if ((time.time()-startime) > int(self.config['FuelScoopTimeOut'])):
                    self.vce.say("Refueling abort, insufficient scooping")
                    return False

            logger.debug('refuel= wait for refuel')

            # We started fueling, so lets give it another timeout period to fuel up
            startime = time.time()
            while not self.jn.ship_state()['fuel_percent'] == 100:
                # check if we are being interdicted
                interdicted = self.interdiction_check()
                if interdicted:
                    # Continue journey after interdiction
                    self.keys.send('SetSpeedZero')

                if ((time.time()-startime) > int(self.config['FuelScoopTimeOut'])):
                    self.vce.say("Refueling abort, insufficient scooping")
                    return True
                sleep(1)

            logger.debug('refuel=complete')
            return True

        elif not is_star_scoopable:
            self.ap_ckb('log', 'Skip refuel - not a fuel star')
            logger.debug('refuel= needed, unsuitable star')
            self.pitch_up(20)
            return False

        elif self.jn.ship_state()['fuel_percent'] >= self.config['RefuelThreshold']:
            self.ap_ckb('log', 'Skip refuel - fuel level okay')
            logger.debug('refuel= not needed')
            return False

        elif not has_fuel_scoop:
            self.ap_ckb('log', 'Skip refuel - no fuel scoop fitted')
            logger.debug('No fuel scoop fitted.')
            self.pitch_up(20)
            return False

        else:
            self.pitch_up(15)  # if not refueling pitch up somemore so we won't heat up
            return False

    def waypoint_undock_seq(self):
        self.update_ap_status("Executing Undocking/Launch")

        # Store current location (on planet or in space)
        on_planet = self.status.get_flag(FlagsHasLatLong)
        on_orbital_construction_site = self.jn.ship_state()['cur_station_type'].upper() == "SpaceConstructionDepot".upper()
        fleet_carrier = self.jn.ship_state()['cur_station_type'].upper() == "FleetCarrier".upper()


        # Leave starport or planetary port
        if not on_planet:
            # Check that we are docked
            if self.status.get_flag(FlagsDocked):
                # Check if we have an advanced docking computer
                if not self.jn.ship_state()['has_adv_dock_comp']:
                    self.ap_ckb('log', "Unable to undock. Advanced Docking Computer not fitted.")
                    logger.warning('Unable to undock. Advanced Docking Computer not fitted.')
                    raise Exception('Unable to undock. Advanced Docking Computer not fitted.')

                # Undock from station
                self.undock()

                # need to wait until undock complete, that is when we are back in_space
                while self.jn.ship_state()['status'] != 'in_space':
                    sleep(1)

                # If we are on an Orbital Construction Site we will need to pitch up 90 deg to avoid crashes
                if on_orbital_construction_site:
                    self.ap_ckb('log+vce', 'Maneuvering')
                    # The pitch rates are defined in SC, not normal flights, so bump this up a bit
                    self.pitch_up(90 * 1.25)

                # If we are on a Fleet Carrier we will pitch up 90 deg and fly away to avoid planet
                elif fleet_carrier:
                    self.ap_ckb('log+vce', 'Maneuvering')
                    # The pitch rates are defined in SC, not normal flights, so bump this up a bit
                    self.pitch_up(90 * 1.25)

                    self.keys.send('SetSpeed100')

                    # While Mass Locked, keep boosting.
                    while not self.status.wait_for_flag_off(FlagsFsdMassLocked, timeout=2):
                        self.keys.send('UseBoostJuice')

                    # Enter supercruise to get away from the Fleet Carrier
                    self.keys.send('Supercruise')

                    # Start SCO monitoring
                    self.start_sco_monitoring()

                    # Wait the configured time before continuing
                    self.ap_ckb('log', 'Flying for configured FC departure time.')
                    sleep(self.config['FCDepartureTime'])
                    self.keys.send('SetSpeed50')

                if not fleet_carrier:
                    # In space (launched from starport or outpost etc.)
                    sleep(1.5)
                    self.update_ap_status("Undock Complete, accelerating")
                    self.keys.send('SetSpeed100')
                    sleep(1)
                    self.keys.send('UseBoostJuice')
                    sleep(13)  # get away from Station
                    self.keys.send('SetSpeed50')

        elif on_planet:
            # Check if we are on a landing pad (docked), or landed on the planet surface
            if self.status.get_flag(FlagsDocked):
                # We are on a landing pad (docked)
                # Check if we have an advanced docking computer
                if not self.jn.ship_state()['has_adv_dock_comp']:
                    self.ap_ckb('log', "Unable to undock. Advanced Docking Computer not fitted.")
                    logger.warning('Unable to undock. Advanced Docking Computer not fitted.')
                    raise Exception('Unable to undock. Advanced Docking Computer not fitted.')

                # Undock from port
                self.undock()

                # need to wait until undock complete, that is when we are back in_space
                while self.jn.ship_state()['status'] != 'in_space':
                    sleep(1)
                self.update_ap_status("Undock Complete, accelerating")

            elif self.status.get_flag(FlagsLanded):
                # We are on planet surface (not docked at planet landing pad)
                # Hold UP for takeoff
                self.keys.send('UpThrustButton', hold=6)
                self.keys.send('LandingGearToggle')
                self.update_ap_status("Takeoff Complete, accelerating")

            # Undocked or off the surface, so leave planet
            self.keys.send('SetSpeed50')
            # The pitch rates are defined in SC, not normal flights, so bump this up a bit
            self.pitch_up(90 * 1.25)
            self.keys.send('SetSpeed100')

            # While Mass Locked, keep boosting.
            while not self.status.wait_for_flag_off(FlagsFsdMassLocked, timeout=2):
                self.keys.send('UseBoostJuice')

            # Enter supercruise
            self.keys.send('Supercruise')

            # Start SCO monitoring
            self.start_sco_monitoring()

            # Wait for SC
            self.status.wait_for_flag_on(FlagsSupercruise, timeout=30)

            # Enable SCO. If SCO not fitted, this will do nothing.
            self.keys.send('UseBoostJuice')

            # Wait until out of orbit.
            self.status.wait_for_flag_off(FlagsHasLatLong, timeout=60)
            # TODO - do we need to check if we never leave orbit?

            # Disable SCO. If SCO not fitted, this will do nothing.
            self.keys.send('UseBoostJuice')
            self.keys.send('SetSpeed50')

    def sc_engage(self):
        """ Engages supercruise, then returns us to 50% speed """
        self.keys.send('SetSpeed100')
        self.keys.send('Supercruise', hold=0.001)
        # Start SCO monitoring
        self.start_sco_monitoring()
        # TODO - check if we actually go into supercruise
        sleep(12)

        self.keys.send('SetSpeed50')

"""The assist routines: FSD, SC, waypoint, AFK combat, DSS."""

import threading
import time
from time import sleep

from core.constants import Flags2GlideMode, FlagsDocked, FlagsLanded
from core.logger import logger
from core.types import ScTargetAlignReturn
from vision.screen import set_focus_elite_window


class AssistsMixin:
    def waypoint_assist(self, keys, scr_reg):
        """Processes the waypoints, performing jumps and sc assist if going to a station
        also can then perform trades if specific in the waypoints file."""
        self.waypoint.waypoint_assist(keys, scr_reg)

    def jump_to_system(self, scr_reg) -> bool:
        """Jumps to the currently targeted system. Returns True if we successfully travel there, else False."""
        # Current in game destination
        status = self.status.get_cleaned_data()
        destination_body = status["Destination_Body"]  # The body number (0 for prim star)
        destination_name = status["Destination_Name"]  # The system/body/station/settlement name

        # Check we have a route and that we have a destination to a star (body 0).
        # We can have one without the other.
        if destination_body != 0 or destination_name == "":
            self.ap_ckb("log", "A valid destination system is not selected.")
            return False

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()["status"] != "in_supercruise":
            self.sc_engage()

        # Route sent...  FSD Assist to that destination
        reached_dest = self.fsd_assist(scr_reg)
        if not reached_dest:
            return False

        return True

    def supercruise_to_station(self, scr_reg, station_name: str) -> bool:
        """Supercruise to the specified target, which may be a station, FC, body, signal source, etc.
        Returns True if we travel successfully travel there, else False."""
        # If waypoint file has a Station Name associated then attempt targeting it
        self.update_ap_status(f"Targeting Station: {station_name}")
        # res = self.nav_panel.lock_destination(station_name)
        # if not res:
        #    return False

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()["status"] != "in_supercruise":
            self.sc_engage()

        # Successful targeting of Station, lets go to it
        sleep(3)  # Wait for compass to stop flashing blue!
        if self.have_destination(scr_reg):
            self.ap_ckb("log", " - Station: " + station_name)
            self.update_ap_status(f"SC to Station: {station_name}")
            self.sc_assist(scr_reg)
        else:
            self.ap_ckb("log", f" - Could not target station: {station_name}")
            return False

        return True

    def fsd_assist(self, scr_reg):
        """FSD Route Assist."""
        # TODO - can we enable this? Seems like a better way
        # nav_route_parser = NavRouteParser()
        logger.debug("self.jn.ship_state=" + str(self.jn.ship_state()))

        starttime = time.time()
        starttime -= 20  # to account for first instance not doing positioning

        # TODO - can we enable this? Seems like a better way
        # if nav_route_parser.get_last_system() is not None:
        if self.jn.ship_state()["target"]:
            # if we are starting the waypoint docked at a station, we need to undock first
            if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
                self.update_overlay()
                self.waypoint_undock_seq()

        # Keep jumping as long as there is a system to jump to.
        # TODO - can we enable this? Seems like a better way
        # while nav_route_parser.get_last_system() is not None:
        while self.jn.ship_state()["target"]:
            self.update_overlay()

            if self.jn.ship_state()["status"] == "in_space" or self.jn.ship_state()["status"] == "in_supercruise":
                self.update_ap_status("Align")

                self.mnvr_to_target(scr_reg)

                self.update_ap_status("Jump")

                self.jump(scr_reg)

                # update jump counters
                self.total_dist_jumped += self.jn.ship_state()["dist_jumped"]
                self.total_jumps = self.jump_cnt + self.jn.ship_state()["jumps_remains"]

                # reset, upon next Jump the Journal will be updated again, unless last jump,
                # so we need to clear this out

                self.jn.ship_state()["jumps_remains"] = 0

                self.update_overlay()

                avg_time_jump = (time.time() - starttime) / self.jump_cnt
                self.ap_ckb(
                    "jumpcount",
                    "Dist: {:,.1f}".format(self.total_dist_jumped)
                    + "ly"
                    + "  Jumps: {}of{}".format(self.jump_cnt, self.total_jumps)
                    + "  @{}s/j".format(int(avg_time_jump))
                    + "  Fu#: "
                    + str(self.refuel_cnt),
                )

                # Do the Discovery Scan (Honk)
                self.honk_thread = threading.Thread(target=self.honk, daemon=True)
                self.honk_thread.start()

                # Refuel
                refueled = self.refuel(scr_reg)

                self.update_ap_status("Maneuvering")

                self.position(scr_reg, refueled)

                if self.jn.ship_state()["fuel_percent"] < self.config["FuelThreasholdAbortAP"]:
                    self.ap_ckb("log", "AP Aborting, low fuel")
                    self.vce.say("AP Aborting, low fuel")
                    break

        sleep(2)  # wait until screen stabilizes from possible last positioning

        # if there is no destination defined, we are done
        if not self.have_destination(scr_reg):
            self.keys.send("SetSpeedZero")
            self.vce.say("Destination Reached, distance jumped:" + str(int(self.total_dist_jumped)) + " lightyears")
            if self.config["AutomaticLogout"]:
                sleep(5)
                self.logout()
            return True
        # else there is a destination in System, so let jump over to SC Assist
        else:
            self.keys.send("SetSpeed100")
            self.vce.say("System Reached, preparing for supercruise")
            sleep(1)
            return False

    # Supercruise Assist loop to travel to target in system and perform autodock
    #
    def sc_assist(self, scr_reg):
        logger.debug("Entered sc_assist")

        # Goto cockpit view
        self.ship_control.goto_cockpit_view()

        align_failed = False
        # see if we have a compass up, if so then we have a target
        if not self.have_destination(scr_reg):
            self.ap_ckb("log", "Quiting SC Assist - Compass not found. Rotate ship and try again.")
            logger.debug("Quiting sc_assist - compass not found")
            return

        # if we are starting the waypoint docked at a station or landed, we need to undock/takeoff first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.update_overlay()
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()["status"] != "in_supercruise":
            self.sc_engage()

        # Ensure we are 50%, don't want the loop of shame
        # Align Nav to target
        self.keys.send("SetSpeed50")
        self.nav_align(scr_reg)  # Compass Align
        self.keys.send("SetSpeed50")

        self.jn.ship_state()["interdicted"] = False

        # Loop forever keeping tight align to target, until we get SC Disengage popup
        self.ap_ckb("log+vce", "Target Align")
        while True:
            sleep(0.05)
            if self.jn.ship_state()["status"] == "in_supercruise":
                # Align and stay on target. If false is returned, we have lost the target behind us.
                align_res = self.sc_target_align(scr_reg)
                if align_res == ScTargetAlignReturn.Lost:
                    # Continue ahead before aligning to prevent us circling the target
                    # self.keys.send('SetSpeed100')
                    sleep(10)
                    self.keys.send("SetSpeed50")
                    self.nav_align(scr_reg)  # Compass Align

                elif align_res == ScTargetAlignReturn.Found:
                    pass

                elif align_res == ScTargetAlignReturn.Disengage:
                    break

            elif self.status.get_flag2(Flags2GlideMode):
                # Gliding - wait to complete
                logger.debug("Gliding")
                self.status.wait_for_flag2_off(Flags2GlideMode, 30)
                break
            else:
                # if we dropped from SC, then we rammed into planet
                logger.debug("No longer in supercruise")
                align_failed = True
                break

            # check if we are being interdicted
            interdicted = self.interdiction_check()
            if interdicted:
                # Continue journey after interdiction
                self.keys.send("SetSpeed50")
                self.nav_align(scr_reg)  # realign with station

            # check for SC Disengage
            if self.sc_disengage_label_up(scr_reg):
                if self.sc_disengage_active(scr_reg):
                    self.ap_ckb("log+vce", "Disengage Supercruise")
                    self.keys.send("HyperSuperCombination")
                    self.stop_sco_monitoring()
                    break

        # TODO - find a better way to clear these
        if self.debug_overlay:
            sleep(2)
            self.overlay.overlay_remove_rect("sc_disengage_active")
            self.overlay.overlay_remove_floating_text("sc_disengage_active")
            self.overlay.overlay_paint()

        # if no error, we must have gotten disengage
        if not align_failed:
            sleep(4)  # wait for the journal to catch up

            # Check if this is a target we cannot dock at
            skip_docking = False
            if not self.jn.ship_state()["has_adv_dock_comp"] and not self.jn.ship_state()["has_std_dock_comp"]:
                self.ap_ckb("log", "Skipping docking. No Docking Computer fitted.")
                skip_docking = True

            if self.jn.ship_state()["SupercruiseDestinationDrop_type"] is not None:
                if (
                    self.jn.ship_state()["SupercruiseDestinationDrop_type"].startswith("$USS_Type")
                    # Bulk Cruisers
                    or "-class Cropper" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Hauler" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Reformatory" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Researcher" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Surveyor" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Traveller" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                    or "-class Tanker" in self.jn.ship_state()["SupercruiseDestinationDrop_type"]
                ):
                    self.ap_ckb("log", "Skipping docking. No docking privilege at MegaShips.")
                    skip_docking = True

            if not skip_docking:
                # go into docking sequence
                self.dock()
                self.ap_ckb("log+vce", "Docking complete, refueled, repaired and re-armed")
                self.update_ap_status("Docking Complete")
            else:
                self.keys.send("SetSpeedZero")
        else:
            self.vce.say("Exiting Supercruise, setting throttle to zero")
            self.keys.send("SetSpeedZero")  # make sure we don't continue to land
            self.ap_ckb("log", "Supercruise dropped, terminating SC Assist")

        self.ap_ckb("log+vce", "Supercruise Assist complete")

    # Simply monitor for Shields down so we can boost away or our fighter got destroyed
    # and thus redeploy another one
    def afk_combat_loop(self):
        while True:
            if not self.afk_combat.check_shields_up():
                set_focus_elite_window()
                self.vce.say("Shields down, evading")
                self.afk_combat.evade()
                # after supercruise the menu is reset to top
                self.afk_combat.launch_fighter()  # at new location launch fighter
                break

            if self.afk_combat.check_fighter_destroyed():
                set_focus_elite_window()
                self.vce.say("Fighter Destroyed, redeploying")
                self.afk_combat.launch_fighter()  # assuming two fighter bays

        self.vce.say("Terminating AFK Combat Assist")

    def dss_assist(self):
        while True:
            sleep(0.5)
            if self.jn.ship_state()["status"] == "in_supercruise":
                cur_star_system = self.jn.ship_state()["cur_star_system"]
                if cur_star_system != self._prev_star_system:
                    self.update_ap_status("DSS Scan")
                    self.ap_ckb("log", "DSS Scan: " + cur_star_system)
                    set_focus_elite_window()
                    self.honk()
                    self._prev_star_system = cur_star_system
                    self.update_ap_status("Idle")

    def single_waypoint_assist(self):
        """Travel to a system or station or both."""
        if self._single_waypoint_system == "" and self._single_waypoint_station == "":
            return False

        if self._single_waypoint_system != "":
            self.ap_ckb("log+vce", f"Targeting system {self._single_waypoint_system}.")
            # Select destination in galaxy map based on name
            res = self.galaxy_map.set_gal_map_destination_text(self, self._single_waypoint_system, self.jn.ship_state)
            if res:
                self.ap_ckb("log", "System has been targeted.")
            else:
                self.ap_ckb("log+vce", f"Unable to target {self._single_waypoint_system} in Galaxy Map.")
                return False

            # Jump to destination
            res = self.jump_to_system(self.scrReg)
            if res is False:
                return False

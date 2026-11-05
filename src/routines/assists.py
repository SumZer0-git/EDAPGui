"""The assist routines: FSD, SC, waypoint, AFK combat, DSS."""

import threading
from time import monotonic, sleep

from core.constants import Flags2GlideMode, FlagsDocked, FlagsLanded, FlagsSupercruise
from core.logger import logger
from core.types import FsdAssistResult, ScTargetAlignReturn
from vision.screen import set_focus_elite_window

IN_SYSTEM_TARGET_TIMEOUT = 5.0
IN_SYSTEM_TARGET_POLL_INTERVAL = 0.25
SYSTEM_ARRIVAL_TIMEOUT = 10.0
ROUTE_TARGET_TIMEOUT = 5.0


class AssistsMixin:
    def waypoint_assist(self, keys, scr_reg):
        """Processes the waypoints, performing jumps and sc assist if going to a station
        also can then perform trades if specific in the waypoints file."""
        self.waypoint.waypoint_assist(keys, scr_reg)

    def jump_to_system(self, scr_reg, expected_system: str | None = None) -> FsdAssistResult:
        """Jump to the targeted system and report whether a local destination is ready."""
        # Current in game destination
        status = self.status.get_cleaned_data()
        destination_body = status["Destination_Body"]  # The body number (0 for prim star)
        destination_name = status["Destination_Name"]  # The system/body/station/settlement name
        route_destination = self.nav_route.get_last_system().upper()

        # A local bookmark target may be active while NavRoute carries the inter-system route.
        if expected_system and route_destination != expected_system.upper():
            self.ap_ckb("log", f"Nav route does not target {expected_system}.")
            return FsdAssistResult.Failed
        if expected_system is None and (not destination_name or (destination_body != 0 and not route_destination)):
            self.ap_ckb("log", "A valid destination system is not selected.")
            return FsdAssistResult.Failed

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()["status"] != "in_supercruise":
            self.sc_engage()

        result = self.fsd_assist(scr_reg, expected_system=expected_system)
        if result is FsdAssistResult.Failed or expected_system is None:
            return result

        deadline = monotonic() + SYSTEM_ARRIVAL_TIMEOUT
        while monotonic() < deadline:
            current_system = self.jn.ship_state()["cur_star_system"].upper()
            if current_system == expected_system.upper():
                return result
            sleep(IN_SYSTEM_TARGET_POLL_INTERVAL)

        logger.warning(
            "FSD route ended without reaching the waypoint system: expected=%s current=%s",
            expected_system,
            self.jn.ship_state()["cur_star_system"],
        )
        self.ap_ckb("log", f"Failed to reach {expected_system}.")
        return FsdAssistResult.Failed

    def supercruise_to_station(self, scr_reg, station_name: str) -> bool:
        """Supercruise to the specified target, which may be a station, FC, body, signal source, etc.
        Returns True if we travel successfully travel there, else False."""
        if not self.wait_for_expected_in_system_target(station_name):
            logger.warning(f"Waypoint local target does not match requested station: {station_name}.")
            self.ap_ckb("log", f" - Could not target station: {station_name}")
            return False

        # If waypoint file has a Station Name associated then attempt targeting it
        self.set_ap_status(f"Targeting Station: {station_name}")
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
        if self.has_expected_in_system_target(self.status.get_cleaned_data(), station_name) and self.have_destination(
            scr_reg
        ):
            self.ap_ckb("log", " - Station: " + station_name)
            self.set_ap_status(f"SC to Station: {station_name}")
            self.sc_assist(scr_reg)
        else:
            self.ap_ckb("log", f" - Could not target station: {station_name}")
            return False

        return True

    def _select_next_route_system(self, expected_system: str) -> bool:
        """Select and confirm the active next hop, not just the route's final destination."""
        if not self.status.wait_for_flag_on(FlagsSupercruise, ROUTE_TARGET_TIMEOUT):
            logger.warning("Waypoint jump stopped: supercruise was not confirmed.")
            self.ap_ckb("log", "Could not confirm supercruise. Waypoint flight stopped.")
            return False

        ship = self.jn.ship_state()
        current_system = ship["cur_star_system"]
        next_system = self.nav_route.get_next_system(current_system, ship.get("system_address"))
        route_destination = self.nav_route.get_last_system()
        if route_destination.casefold() != expected_system.casefold() or next_system is None:
            logger.warning(
                "Waypoint jump stopped: current=%r route_destination=%r expected=%r next_system=%r",
                current_system,
                route_destination,
                expected_system,
                next_system,
            )
            self.ap_ckb("log", "Could not confirm the next route system. Waypoint flight stopped.")
            return False

        next_name, next_address = next_system
        status = self.status.get_cleaned_data()
        logger.debug(
            "Waypoint route target selection: current=%r final=%r next=%r/%s "
            "previous_name=%r previous_system=%s previous_body=%s",
            current_system,
            expected_system,
            next_name,
            next_address,
            status["Destination_Name"],
            status["Destination_System"],
            status["Destination_Body"],
        )
        self.keys.send("TargetNextRouteSystem")
        deadline = monotonic() + ROUTE_TARGET_TIMEOUT
        while monotonic() < deadline:
            status = self.status.get_cleaned_data()
            if (
                self.nav_route.get_last_system().casefold() != expected_system.casefold()
                or self.nav_route.get_next_system(current_system, ship.get("system_address")) != next_system
            ):
                logger.warning("Waypoint route changed while confirming the next jump target.")
                self.ap_ckb("log", "Route changed during target confirmation. Waypoint flight stopped.")
                return False
            if (
                status["Destination_Name"].casefold() == next_name.casefold()
                and status["Destination_System"] == next_address
                and status["Destination_Body"] == 0
            ):
                logger.debug(
                    "Waypoint route target confirmed: current=%r next=%r/%s body=0",
                    current_system,
                    next_name,
                    next_address,
                )
                return True
            logger.debug(
                "Waypoint route target pending: expected=%r/%s active_name=%r active_system=%s active_body=%s",
                next_name,
                next_address,
                status["Destination_Name"],
                status["Destination_System"],
                status["Destination_Body"],
            )
            sleep(IN_SYSTEM_TARGET_POLL_INTERVAL)

        logger.warning(
            "Waypoint route target confirmation timed out: expected=%r/%s active_name=%r active_system=%s active_body=%s",
            next_name,
            next_address,
            status["Destination_Name"],
            status["Destination_System"],
            status["Destination_Body"],
        )
        self.ap_ckb("log", f"Could not confirm jump target {next_name}. Waypoint flight stopped.")
        return False

    def fsd_assist(self, scr_reg, expected_system: str | None = None) -> FsdAssistResult:
        """FSD Route Assist."""
        # TODO - can we enable this? Seems like a better way
        # nav_route_parser = NavRouteParser()
        logger.debug("self.jn.ship_state=" + str(self.jn.ship_state()))

        # TODO - can we enable this? Seems like a better way
        # if nav_route_parser.get_last_system() is not None:
        aborted = False
        if self.jn.ship_state()["target"]:
            # if we are starting the waypoint docked at a station, we need to undock first
            if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
                self.update_overlay()
                self.waypoint_undock_seq()

        # Keep jumping as long as there is a system to jump to.
        # TODO - can we enable this? Seems like a better way
        # while nav_route_parser.get_last_system() is not None:
        while (
            self.jn.ship_state()["cur_star_system"].casefold() != expected_system.casefold()
            if expected_system
            else self.jn.ship_state()["target"]
        ):
            self.update_overlay()

            if self.jn.ship_state()["status"] == "in_space" or self.jn.ship_state()["status"] == "in_supercruise":
                if expected_system and not self._select_next_route_system(expected_system):
                    self.keys.send("SetSpeedZero")
                    return FsdAssistResult.Failed
                self.set_ap_status("Align")

                self.mnvr_to_target(scr_reg)

                self.set_ap_status("Jump")

                if not self.jump(scr_reg):
                    aborted = True
                    break

                # update the distance counter
                self.total_dist_jumped += self.jn.ship_state()["dist_jumped"]

                # reset, upon next Jump the Journal will be updated again, unless last jump,
                # so we need to clear this out

                self.jn.ship_state()["jumps_remains"] = 0

                self.update_overlay()

                # Do the Discovery Scan (Honk)
                self.honk_thread = threading.Thread(target=self.honk, daemon=True)
                self.honk_thread.start()

                # Refuel
                refueled = self.refuel(scr_reg)

                self.set_ap_status("Maneuvering")

                self.position(scr_reg, refueled)

                if self.jn.ship_state()["fuel_percent"] < self.config["FuelThreasholdAbortAP"]:
                    self.ap_ckb("log", "AP Aborting, low fuel")
                    self.vce.say("AP Aborting, low fuel")
                    aborted = True
                    break

        sleep(2)  # wait until screen stabilizes from possible last positioning

        status = self.status.get_cleaned_data()
        logger.debug(
            f"End of route: status Destination system={status['Destination_System']}, "
            f"body={status['Destination_Body']}, name='{status['Destination_Name']}', "
            f"location='{self.jn.ship_state()['location']}', journal target={self.jn.ship_state()['target']}"
        )

        if aborted:
            return FsdAssistResult.Failed

        # if there is no destination defined, we are done
        if not self.has_in_system_target(status):
            self.keys.send("SetSpeedZero")
            self.vce.say("Destination Reached, distance jumped:" + str(int(self.total_dist_jumped)) + " lightyears")
            if self.config["AutomaticLogout"]:
                sleep(5)
                self.logout()
            return FsdAssistResult.RouteComplete
        # else there is a destination in System, so let jump over to SC Assist
        else:
            self.keys.send("SetSpeed100")
            self.vce.say("System Reached, preparing for supercruise")
            sleep(1)
            return FsdAssistResult.InSystemTarget

    def travel_assist(self, scr_reg):
        """Choose the required travel phase from the currently targeted system."""
        if self.jn.ship_state()["target"]:
            self.total_dist_jumped = 0
            result = self.fsd_assist(scr_reg)
            if result is FsdAssistResult.InSystemTarget and self.travel_assist_enabled:
                self.set_ap_status("SC to Target")
                self.sc_assist(scr_reg)
        else:
            if self.has_in_system_target(self.status.get_cleaned_data()):
                self.set_ap_status("SC to Target")
                self.sc_assist(scr_reg)
            else:
                self.ap_ckb("log", "No local target found. Select a target and try again.")

    def has_in_system_target(self, status) -> bool:
        """Return whether Status.json reports a non-main-star destination for SC Assist."""
        return status["Destination_Name"] != "" and status["Destination_Body"] != 0

    def has_expected_in_system_target(self, status, target_name: str) -> bool:
        """Return whether Status.json reports the requested in-system destination."""
        if not self.has_in_system_target(status):
            return False
        if not target_name.strip():
            return True
        destination_name = status["Destination_Name"].strip().casefold()
        expected_name = target_name.strip().casefold()
        return destination_name == expected_name or (
            "-" in destination_name and expected_name.endswith(destination_name)
        )

    def wait_for_expected_in_system_target(self, target_name: str, timeout: float = IN_SYSTEM_TARGET_TIMEOUT) -> bool:
        """Wait briefly for Status.json to report the requested local destination."""
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if self.has_expected_in_system_target(self.status.get_cleaned_data(), target_name):
                return True
            sleep(IN_SYSTEM_TARGET_POLL_INTERVAL)
        return False

    # Supercruise Assist loop to travel to target in system and perform autodock
    #
    def sc_assist(self, scr_reg):
        if not self.has_in_system_target(self.status.get_cleaned_data()):
            logger.debug("SC Assist skipped because Status.json has no in-system destination.")
            self.ap_ckb("log", "No local target found. Select a target and try again.")
            return

        logger.info("Entered sc_assist")
        # Waypoint Assist sets "SC to Station: <name>" before calling; keep that text for the cruise phase.
        cruise_status = self.ap_state if self.ap_state.startswith("SC to") else "SC to Target"

        # Goto cockpit view
        self.ship_control.goto_cockpit_view()

        align_failed = False
        # see if we have a compass up, if so then we have a target
        if not self.have_destination(scr_reg):
            self.ap_ckb("log", "No local target found. Select a target and try again.")
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
        self.set_ap_status("Align")
        self.keys.send("SetSpeed50")
        self.nav_align(scr_reg)  # Compass Align
        # The target is ahead now, so cruise at 75%, where ships handle best in supercruise.
        self.keys.send("SetSpeed75")
        self.set_ap_status(cruise_status)

        self.jn.ship_state()["interdicted"] = False

        # Loop forever keeping tight align to target, until we get SC Disengage popup
        self.ap_ckb("log+vce", "Target Align")
        while True:
            sleep(0.05)
            if self.jn.ship_state()["status"] == "in_supercruise":
                # Align and stay on target. If false is returned, we have lost the target behind us.
                align_res = self.sc_target_align(scr_reg)
                if align_res == ScTargetAlignReturn.Lost:
                    # Continue ahead before aligning to prevent us circling the target.
                    # The target ring changes shortly before arrival, so keep watching for the disengage prompt.
                    if self.wait_for_sc_disengage(scr_reg, 10):
                        break
                    self.keys.send("SetSpeed50")
                    if self.nav_align(scr_reg, abort_on_disengage=True):  # Compass Align
                        break

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
            if self.try_sc_disengage(scr_reg):
                break

        # TODO - find a better way to clear these
        if self.debug_overlay:
            sleep(2)
            self.overlay.overlay_remove_rect("sc_disengage_active")
            self.overlay.overlay_remove_floating_text("sc_disengage_active")
            self.overlay.overlay_paint()

        # if no error, we must have gotten disengage
        if not align_failed:
            self.set_ap_status("Approaching target")
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
                self.set_ap_status("Docking Complete")
            else:
                self.keys.send("SetSpeedZero")
                self.set_ap_status("Arrived at target")
        else:
            self.vce.say("Exiting Supercruise, setting throttle to zero")
            self.keys.send("SetSpeedZero")  # make sure we don't continue to land
            self.ap_ckb("log", "Supercruise dropped, terminating SC Assist")

        completion_message = "Travel Assist complete" if self.travel_assist_enabled else "Supercruise Assist complete"
        self.ap_ckb("log+vce", completion_message)

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
                    self.set_ap_status("DSS Scan")
                    self.ap_ckb("log", "DSS Scan: " + cur_star_system)
                    set_focus_elite_window()
                    self.honk()
                    self._prev_star_system = cur_star_system
                    self.set_ap_status("Idle")

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
            res = self.jump_to_system(self.scrReg, expected_system=self._single_waypoint_system)
            if res is FsdAssistResult.Failed:
                return False

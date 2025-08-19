from __future__ import annotations
from time import sleep
from EDlogger import logger
from Screen_Regions import reg_scale_for_station

class FleetCarrierAutopilot:
    def __init__(self, ed_ap):
        self.ap = ed_ap
        self.waypoint = self.ap.waypoint
        self.keys = self.ap.keys
        self.journal = self.ap.jn
        self.internal_panel = self.ap.internal_panel
        self.station_services = self.ap.stn_svcs_in_ship

    def fc_waypoint_assist(self):
        """
        Processes the waypoints for the fleet carrier, performing jumps and refueling.
        """
        logger.info("Fleet Carrier Autopilot Engaged.")
        self.ap.ap_ckb('log+vce', "Fleet Carrier Autopilot Engaged.")

        # Main loop to process waypoints
        while not self.ap.terminate:
            # Get the next waypoint
            dest_key, next_waypoint = self.waypoint.get_waypoint()
            if dest_key is None:
                self.ap.ap_ckb('log+vce', "Fleet Carrier waypoint list has been completed.")
                break

            next_wp_system = next_waypoint.get('SystemName', '').upper()
            self.ap.ap_ckb('log+vce', f"Next Fleet Carrier Waypoint: {next_wp_system}")

            # 1. Refuel tritium tanks
            self.ap.ap_ckb('log+vce', "Refueling tritium from inventory.")
            self.internal_panel.refuel_tritium_from_inventory(self.ap)

            # 2. Plot route and jump
            self.plot_and_jump(next_wp_system)

            # 3. Wait for jump to complete
            jump_complete = self.wait_for_carrier_jump(next_wp_system)

            if not jump_complete:
                self.ap.ap_ckb('log+vce', "Carrier jump timed out or failed.")
                break

            # 4. Verify jump and mark waypoint as complete
            current_system = self.journal.ship_state()['cur_star_system'].upper()
            if current_system == next_wp_system:
                self.ap.ap_ckb('log+vce', f"Successfully jumped to {next_wp_system}.")
                self.waypoint.mark_waypoint_complete(dest_key)
                # 5. Wait for cooldown
                self.ap.ap_ckb('log+vce', "Waiting for cooldown (5 minutes).")
                sleep(5 * 60)
            else:
                self.ap.ap_ckb('log+vce', f"Failed to jump to {next_wp_system}. Current system: {current_system}")
                break # Abort on failure

        self.ap.ap_ckb('log+vce', "Fleet Carrier Autopilot Disengaged.")

    def wait_for_carrier_jump(self, destination_system):
        """
        Waits for a CarrierJump event to the destination system.
        This method reads the journal file directly because the main EDJournal class
        does not provide a mechanism for waiting for specific events. This approach
        is self-contained and avoids modifying the core journal reading logic.
        """
        import json
        from time import time

        self.ap.ap_ckb('log+vce', f"Waiting for carrier jump to {destination_system}.")
        log_file_path = self.journal.get_latest_log()
        with open(log_file_path, 'r', encoding='utf-8') as f:
            f.seek(0, 2) # Go to the end of the file
            timeout = time() + 16 * 60 # 16 minutes timeout
            while time() < timeout:
                line = f.readline()
                if line:
                    try:
                        log_entry = json.loads(line)
                        if (log_entry.get('event') == 'CarrierJump' and
                            log_entry.get('StarSystem', '').upper() == destination_system.upper()):
                            # Manually trigger a re-read of the journal to update the ship state
                            self.journal.ship_state()
                            return True
                    except json.JSONDecodeError:
                        # Ignore malformed lines
                        pass
                else:
                    sleep(1)
        return False

    def plot_and_jump(self, system_name):
        """ Plots the route and initiates the jump from the fleet carrier management screen. """
        self.ap.ap_ckb('log+vce', f"Plotting route to {system_name}.")
        logger.debug(f"plot_and_jump: entered for system {system_name}")

        if not self.station_services.goto_fleet_carrier_management():
            logger.error("Could not navigate to Fleet Carrier Management.")
            return False

        # Now in fleet carrier management screen
        self.ap.galaxy_map.goto_galaxy_map_from_fc()

        # 1. Open Galaxy Map
        self.keys.send('UI_Select')


        # 2. Enter System Name and plot route
        if not self.ap.galaxy_map.set_gal_map_destination_text(self.ap, system_name, self.journal.ship_state):
             logger.error(f"Failed to set destination to {system_name} in galaxy map.")
             # Back out of the galaxy map
             self.keys.send('UI_Back')
             sleep(1)
             self.keys.send('UI_Back')
             return False
        sleep(2)

        # 3. Confirm Jump from within the fleet carrier management's galaxy map
        # This is different from a normal jump. There should be a "confirm" button.
        # I'll assume it's the first selectable item after plotting the route.
        self.keys.send('UI_Select') # Select the plotted route
        sleep(1)
        self.keys.send('UI_Select') # Confirm the jump

        logger.info(f"Jump to {system_name} initiated.")
        self.ap.ap_ckb('log+vce', f"Jump to {system_name} initiated.")
        return True

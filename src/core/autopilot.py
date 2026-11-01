"""The EDAutopilot class: setup, engine loop and setters.

Ideas taken from: https://github.com/skai2/EDAutopilot"""

import ctypes
import logging
import threading
import traceback
from time import sleep

import cv2
import kthread

import vision.regions
import vision.screen
import vision.templates
from controls.keys import EDKeys
from core import paths
from core.config import ConfigMixin
from core.constants import FlagsSupercruise, ship_size_map
from core.logger import logger
from core.types import EDAP_Interrupt
from game.graphics_settings import EDGraphicsSettings
from game.journal import EDJournal, get_ship_fullname
from game.nav_route import NavRouteParser
from game.status import StatusParser
from gui.overlay import Overlay
from i18n import LocalizationManager
from integrations.edmesg.server import EDMesgServer
from integrations.tce import TceIntegration
from integrations.voice import Voice
from panels.galaxy_map import EDGalaxyMap
from panels.internal_status import EDInternalStatusPanel
from panels.navigation import EDNavigationPanel
from panels.ship_control import EDShipControl
from panels.station_services import EDStationServicesInShip
from panels.system_map import EDSystemMap
from routines.afk_combat import AFK_Combat
from routines.assists import AssistsMixin
from routines.flight import FlightMixin
from routines.robigo import Robigo
from routines.waypoints import EDWayPoint
from vision.calibration import CalibrationMixin
from vision.detection import DetectionMixin
from vision.ocr import OCR
from vision.screen import set_focus_elite_window


class EDAutopilot(ConfigMixin, CalibrationMixin, DetectionMixin, FlightMixin, AssistsMixin):

    def __init__(self, cb, doThread=True):

        # NOTE!!! When adding a new config value below, add the same after read_config() to set
        # a default value or an error will occur reading the new value!
        self.config = {
            "DSSButton": "Primary",        # if anything other than "Primary", it will use the Secondary Fire button for DSS
            "JumpTries": 3,                #
            "NavAlignTries": 3,            #
            "RefuelThreshold": 65,         # if fuel level get below this level, it will attempt refuel
            "FuelThreasholdAbortAP": 10,   # level at which AP will terminate, because we are not scooping well
            "WaitForAutoDockTimer": 240,   # After docking granted, wait this amount of time for us to get docked with autodocking
            "SunBrightThreshold": 125,     # The low level for brightness detection, range 0-255, want to mask out darker items
            "FuelScoopTimeOut": 35,        # number of second to wait for full tank, might mean we are not scooping well or got a small scooper
            "DockingRetries": 30,          # number of time to attempt docking
            "HotKey_StartFSD": "home",     # if going to use other keys, need to look at the python keyboard package
            "HotKey_StartSC": "ins",       # to determine other keynames, make sure these keys are not used in ED bindings
            "HotKey_StartRobigo": "pgup",  #
            "HotKey_StopAllAssists": "end",
            "Robigo_Single_Loop": False,   # True means only 1 loop will executed and then terminate the Robigo, will not perform mission processing
            "EnableRandomness": False,     # add some additional random sleep times to avoid AP detection (0-3sec at specific locations)
            "ActivateEliteEachKey": False, # Activate Elite window before each key or group of keys
            "OverlayTextEnable": False,    # Experimental at this stage
            "OverlayTextYOffset": 400,     # offset down the screen to start place overlay text
            "OverlayTextXOffset": 50,      # offset left the screen to start place overlay text
            "OverlayTextFont": "Eurostyle",
            "OverlayTextFontSize": 14,
            "OverlayGraphicEnable": False, # not implemented yet
            "DiscordWebhook": False,       # discord not implemented yet
            "DiscordWebhookURL": "",
            "DiscordUserID": "",
            "VoiceEnable": False,
            "VoiceID": 1,                  # my Windows only have 3 defined (0-2)
            "ElwScannerEnable": False,
            "LogDEBUG": False,             # enable for debug messages
            "LogINFO": True,
            "Enable_CV_View": 0,           # Should CV View be enabled by default
            "ShipConfigFile": None,        # Ship config to load on start - deprecated
            "TargetScale": 1.0,            # Scaling of the target when a system is selected
            "TCEDestinationFilepath": "C:\\TCE\\DUMP\\Destination.json",  # Destination file for TCE
            "TCEInstallationPath": "C:\\TCE",
            "AutomaticLogout": False,      # Logout when we are done with the mission
            "FCDepartureTime": 5.0,        # Extra time to fly away from a Fleet Carrier
            "Language": 'en',              # Language (matching assets/locales/xx.json file)
            "OCRLanguage": 'en',           # Language for OCR detection (see OCR language doc in \docs)
            "EnableEDMesg": False,
            "EDMesgActionsPort": 15570,
            "EDMesgEventsPort": 15571,
            "DebugOverlay": False,
        }
        # NOTE!!! When adding a new config value above, add the same after read_config() to set
        # a default value or an error will occur reading the new value!

        self.ship_configs = {
            "Ship_Configs": {},  # Dictionary of ship types with additional settings
        }
        self._sc_sco_active_loop_thread = None
        self._sc_sco_active_loop_enable = False
        self.sc_sco_is_active = 0
        self._sc_sco_active_on_ls = 0
        self._single_waypoint_station = None
        self._single_waypoint_system = None
        self._prev_star_system = None
        self.honk_thread = None
        self._tce_integration = None

        # used this to write the self.config table to the json file
        # self.write_config(self.config)

        cnf = self.read_config()
        # if we read it then point to it, otherwise use the default table above
        if cnf is not None:
            # NOTE!!! Add default values for new entries below!
            if 'SunBrightThreshold' not in cnf:
                cnf['SunBrightThreshold'] = 125
            if 'TargetScale' not in cnf:
                cnf['TargetScale'] = 1.0
            if 'TCEDestinationFilepath' not in cnf:
                cnf['TCEDestinationFilepath'] = "C:\\TCE\\DUMP\\Destination.json"
            if 'TCEInstallationPath' not in cnf:
                cnf['TCEInstallationPath'] = "C:\\TCE"
            if 'AutomaticLogout' not in cnf:
                cnf['AutomaticLogout'] = False
            if 'FCDepartureTime' not in cnf:
                cnf['FCDepartureTime'] = 5.0
            if 'Language' not in cnf:
                cnf['Language'] = 'en'
            if 'OCRLanguage' not in cnf:
                cnf['OCRLanguage'] = 'en'
            if 'EnableEDMesg' not in cnf:
                cnf['EnableEDMesg'] = False
            if 'EDMesgActionsPort' not in cnf:
                cnf['EDMesgActionsPort'] = 15570
            if 'EDMesgEventsPort' not in cnf:
                cnf['EDMesgEventsPort'] = 15571
            if 'DebugOverlay' not in cnf:
                cnf['DebugOverlay'] = False
            self.config = cnf
            logger.debug("read AP json:"+str(cnf))
        else:
            self.write_config(self.config)

        # Load selected language
        self.locale = LocalizationManager(str(paths.LOCALES_DIR), self.config['Language'])

        shp_cnf = self.read_ship_configs()
        # if we read it then point to it, otherwise use the default table above
        if shp_cnf is not None:
            if len(shp_cnf) != len(self.ship_configs):
                # If configs of different lengths, then a new parameter was added.
                # self.write_config(self.config)
                # Add default values for new entries
                if 'Ship_Configs' not in shp_cnf:
                    shp_cnf['Ship_Configs'] = dict()
                self.ship_configs = shp_cnf
                logger.debug("read Ships Config json:" + str(shp_cnf))
            else:
                self.ship_configs = shp_cnf
                logger.debug("read Ships Config json:" + str(shp_cnf))
        else:
            self.write_ship_configs(self.ship_configs)

        # config the voice interface
        self.vce = Voice()
        self.vce.v_enabled = self.config['VoiceEnable']
        self.vce.set_voice_id(self.config['VoiceID'])
        self.vce.say("Welcome to Autopilot")

        # set log level based on config input, defaulting to warning
        logger.setLevel(logging.WARNING)
        if self.config['LogINFO']:
            logger.setLevel(logging.INFO)
        if self.config['LogDEBUG']:
            logger.setLevel(logging.DEBUG)

        # initialize all to false
        self.fsd_assist_enabled = False
        self.sc_assist_enabled = False
        self.afk_combat_assist_enabled = False
        self.waypoint_assist_enabled = False
        self.robigo_assist_enabled = False
        self.dss_assist_enabled = False
        self.single_waypoint_enabled = False

        # Create instance of each of the needed Classes
        self.gfx_settings = EDGraphicsSettings()

        self.scr = vision.screen.Screen(cb)
        self.scr.scaleX = self.config['TargetScale']
        self.scr.scaleY = self.config['TargetScale']

        self.ocr = OCR(self.scr, self.config['OCRLanguage'])
        self.templ = vision.templates.Image_Templates(self.scr.scaleX, self.scr.scaleY, self.scr.scaleX)
        self.scrReg = vision.regions.Screen_Regions(self.scr, self.templ)
        self.jn = EDJournal(cb)
        self.keys = EDKeys(cb)
        self.keys.activate_window = self.config['ActivateEliteEachKey']
        self.afk_combat = AFK_Combat(self.keys, self.jn, self.vce)
        self.waypoint = EDWayPoint(self, self.jn.ship_state()['odyssey'])
        self.robigo = Robigo(self)
        self.status = StatusParser()
        self.nav_route = NavRouteParser()
        self.ship_control = EDShipControl(self, self.scr, self.keys, cb)
        self.internal_panel = EDInternalStatusPanel(self, self.scr, self.keys, cb)
        self.galaxy_map = EDGalaxyMap(self, self.scr, self.keys, cb, self.jn.ship_state()['odyssey'])
        self.system_map = EDSystemMap(self, self.scr, self.keys, cb, self.jn.ship_state()['odyssey'])
        self.stn_svcs_in_ship = EDStationServicesInShip(self, self.scr, self.keys, cb)
        self.nav_panel = EDNavigationPanel(self, self.scr, self.keys, cb)

        self.mesg_server = EDMesgServer(self, cb)
        self.mesg_server.actions_port = self.config['EDMesgActionsPort']
        self.mesg_server.events_port = self.config['EDMesgEventsPort']
        if self.config['EnableEDMesg']:
            self.mesg_server.start_server()

        # rate as ship dependent. Can be found on the outfitting page for the ship. However, it looks like supercruise
        # has worse performance for these rates
        # see:  https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
        #
        # If you find that you are overshoot in pitch or roll, need to adjust these numbers.
        # Algorithm will roll the vehicle for the nav point to be north or south and then pitch to get the nave point
        # to center
        self.compass_scale = 1.0
        self.yawrate   = 8.0
        self.rollrate  = 80.0
        self.pitchrate = 33.0
        self.sunpitchuptime = 0.0

        self.jump_cnt = 0
        self.total_dist_jumped = 0
        self.total_jumps = 0
        self.refuel_cnt = 0
        self.current_ship_type = None
        self.gui_loaded = False

        self.ap_ckb = cb

        # Overlay vars
        self.ap_state = "Idle"
        self.fss_detected = "nothing found"

        # Initialize the Overlay class
        self.overlay = Overlay("", elite=1)
        self.overlay.overlay_setfont(self.config['OverlayTextFont'], self.config['OverlayTextFontSize'])
        self.overlay.overlay_set_pos(self.config['OverlayTextXOffset'], self.config['OverlayTextYOffset'])
        # must be called after we initialized the objects above
        self.update_overlay()

        self.debug_overlay = self.config['DebugOverlay']

        # debug window
        self.cv_view = self.config['Enable_CV_View']
        self.cv_view_x = 10
        self.cv_view_y = 10

        #start the engine thread
        self.terminate = False  # terminate used by the thread to exit its loop
        if doThread:
            self.ap_thread = kthread.KThread(target=self.engine_loop, name="EDAutopilot")
            self.ap_thread.start()

    @property
    def tce_integration(self) -> TceIntegration:
        """ Load TCE Integration class when needed. """
        if not self._tce_integration:
            self._tce_integration = TceIntegration(self, self.ap_ckb)
        return self._tce_integration


    # draw the overlay data on the ED Window
    #
    def update_overlay(self):
        if self.config['OverlayTextEnable']:
            ap_mode = "Offline"
            if self.fsd_assist_enabled:
                ap_mode = "FSD Route Assist"
            elif self.robigo_assist_enabled:
                ap_mode = "Robigo Assist"
            elif self.sc_assist_enabled:
                ap_mode = "SC Assist"
            elif self.waypoint_assist_enabled:
                ap_mode = "Waypoint Assist"
            elif self.afk_combat_assist_enabled:
                ap_mode = "AFK Combat Assist"
            elif self.dss_assist_enabled:
                ap_mode = "DSS Assist"

            ship_state = self.jn.ship_state()['status']
            if ship_state is None:
                ship_state = '<init>'

            sclass = self.jn.ship_state()['star_class']
            if sclass is None:
                sclass = "<init>"

            location = self.jn.ship_state()['location']
            if location is None:
                location = "<init>"
            self.overlay.overlay_text('1', "AP MODE: "+ap_mode, 1, 1, (136, 53, 0))
            self.overlay.overlay_text('2', "AP STATUS: "+self.ap_state, 2, 1, (136, 53, 0))
            self.overlay.overlay_text('3', "SHIP STATUS: "+ship_state, 3, 1, (136, 53, 0))
            self.overlay.overlay_text('4', "CURRENT SYSTEM: "+location+", "+sclass, 4, 1, (136, 53, 0))
            self.overlay.overlay_text('5', "JUMPS: {} of {}".format(self.jump_cnt, self.total_jumps), 5, 1, (136, 53, 0))
            if self.config["ElwScannerEnable"]:
                self.overlay.overlay_text('6', "ELW SCANNER: "+self.fss_detected, 6, 1, (136, 53, 0))
            self.overlay.overlay_paint()

    def update_ap_status(self, txt):
        self.ap_state = txt
        self.update_overlay()
        self.ap_ckb('statusline', txt)


        # Performs left menu ops to request docking


        # a set of convience routes to pitch, rotate by specified degress


        # Disabled until SC to station enabled.
        # if self._single_waypoint_station != "":
        #     res = self.supercruise_to_station(self.scrReg, self._single_waypoint_station)
        #     if res is False:
        #         return False

    # raising an exception to the engine loop thread, so we can terminate its execution
    #  if thread was in a sleep, the exception seems to not be delivered
    def ctype_async_raise(self, thread_obj, exception):
        found = False
        target_tid = 0
        for tid, tobj in threading._active.items():
            if tobj is thread_obj:
                found = True
                target_tid = tid
                break

        if not found:
            raise ValueError("Invalid thread object")

        ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(target_tid),
                                                         ctypes.py_object(exception))
        # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
        if ret == 0:
            raise ValueError("Invalid thread ID")
        elif ret > 1:
            # Huh? Why would we notify more than one threads?
            # Because we punch a hole into C level interpreter.
            # So it is better to clean up the mess.
            ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    #
    # Setter routines for state variables
    #
    def set_fsd_assist(self, enable=True):
        if not enable and self.fsd_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.fsd_assist_enabled = enable

    def set_sc_assist(self, enable=True):
        if not enable and self.sc_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.sc_assist_enabled = enable

    def set_waypoint_assist(self, enable=True):
        if not enable and self.waypoint_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.waypoint_assist_enabled = enable

    def set_robigo_assist(self, enable=True):
        if not enable and self.robigo_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.robigo_assist_enabled = enable

    def set_afk_combat_assist(self, enable=True):
        if not enable and self.afk_combat_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.afk_combat_assist_enabled = enable

    def set_dss_assist(self, enable=True):
        if not enable and self.dss_assist_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.dss_assist_enabled = enable

    def set_single_waypoint_assist(self, system: str, station: str, enable=True):
        if not enable and self.single_waypoint_enabled:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self._single_waypoint_system = system
        self._single_waypoint_station = station
        self.single_waypoint_enabled = enable

    def set_cv_view(self, enable=True, x=0, y=0):
        self.cv_view = enable
        self.config['Enable_CV_View'] = int(self.cv_view)  # update the config
        self.update_config()  # save the config
        if enable:
            self.cv_view_x = x
            self.cv_view_y = y
        else:
            cv2.destroyAllWindows()
            cv2.waitKey(50)

    def set_randomness(self, enable=False):
        self.config["EnableRandomness"] = enable

    def set_activate_elite_eachkey(self, enable=False):
        self.config["ActivateEliteEachKey"] = enable

    def set_automatic_logout(self, enable=False):
        self.config["AutomaticLogout"] = enable

    def set_overlay(self, enable=False):
        # TODO: apply the change without restarting the program
        self.config["OverlayTextEnable"] = enable
        if not enable:
            self.overlay.overlay_clear()

        self.overlay.overlay_paint()

    def set_voice(self, enable=False):
        if enable:
            self.vce.set_on()
        else:
            self.vce.set_off()

    def set_fss_scan(self, enable=False):
        self.config["ElwScannerEnable"] = enable

    def set_log_error(self, enable=False):
        self.config["LogDEBUG"] = False
        self.config["LogINFO"] = False
        logger.setLevel(logging.ERROR)

    def set_log_debug(self, enable=False):
        self.config["LogDEBUG"] = True
        self.config["LogINFO"] = False
        logger.setLevel(logging.DEBUG)

    def set_log_info(self, enable=False):
        self.config["LogDEBUG"] = False
        self.config["LogINFO"] = True
        logger.setLevel(logging.INFO)

    # quit() is important to call to clean up, if we don't terminate the threads we created the AP will hang on exit
    # have then then kill python exec
    def quit(self):
        if self.vce is not None:
            self.vce.quit()
        if self.overlay is not None:
            self.overlay.overlay_quit()
        self.terminate = True

    #
    # This function will execute in its own thread and will loop forever until
    # the self.terminate flag is set
    #
    def engine_loop(self):
        while not self.terminate:
            self._sc_sco_active_loop_enable = True

            if self._sc_sco_active_loop_enable:
                if self._sc_sco_active_loop_thread is None or not self._sc_sco_active_loop_thread.is_alive():
                    self._sc_sco_active_loop_thread = threading.Thread(target=self._sc_sco_active_loop, daemon=True)
                    self._sc_sco_active_loop_thread.start()

            if self.fsd_assist_enabled:
                logger.debug("Running fsd_assist")
                set_focus_elite_window()
                self.update_overlay()
                self.jump_cnt = 0
                self.refuel_cnt = 0
                self.total_dist_jumped = 0
                self.total_jumps = 0
                fin = True
                # could be deep in call tree when user disables FSD, so need to trap that exception
                try:
                    fin = self.fsd_assist(self.scrReg)
                except EDAP_Interrupt:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    print("Trapped generic:"+str(e))
                    traceback.print_exc()

                self.fsd_assist_enabled = False
                self.ap_ckb('fsd_stop')
                self.update_overlay()

                # if fsd_assist returned false then we are not finished, meaning we have an in system target
                # defined.  So lets enable Supercruise assist to get us there
                # Note: this is tricky, in normal FSD jumps the target is pretty much on the other side of Sun
                #  when we arrive, but not so when we are in the final system
                if fin is False:
                    self.ap_ckb("sc_start")

                # drop all out debug windows
                #cv2.destroyAllWindows()
                #cv2.waitKey(10)

            elif self.sc_assist_enabled:
                logger.debug("Running sc_assist")
                set_focus_elite_window()
                self.update_overlay()
                try:
                    self.update_ap_status("SC to Target")
                    self.sc_assist(self.scrReg)
                except EDAP_Interrupt:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    print("Trapped generic:"+str(e))
                    traceback.print_exc()

                logger.debug("Completed sc_assist")
                self.sc_assist_enabled = False
                self.ap_ckb('sc_stop')
                self.update_overlay()

            elif self.waypoint_assist_enabled:
                logger.debug("Running waypoint_assist")

                set_focus_elite_window()
                self.update_overlay()
                self.jump_cnt = 0
                self.refuel_cnt = 0
                self.total_dist_jumped = 0
                self.total_jumps = 0
                try:
                    self.waypoint_assist(self.keys, self.scrReg)
                except EDAP_Interrupt:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    print("Trapped generic:"+str(e))
                    traceback.print_exc()

                self.waypoint_assist_enabled = False
                self.ap_ckb('waypoint_stop')
                self.update_overlay()

            elif self.robigo_assist_enabled:
                logger.debug("Running robigo_assist")
                set_focus_elite_window()
                self.update_overlay()
                try:
                    self.robigo_assist()
                except EDAP_Interrupt:
                    logger.debug("Caught stop exception")
                except Exception as e:
                    print("Trapped generic:"+str(e))
                    traceback.print_exc()

                self.robigo_assist_enabled = False
                self.ap_ckb('robigo_stop')
                self.update_overlay()

            elif self.afk_combat_assist_enabled:
                self.update_overlay()
                try:
                    self.afk_combat_loop()
                except EDAP_Interrupt:
                    logger.debug("Stopping afk_combat")
                self.afk_combat_assist_enabled = False
                self.ap_ckb('afk_stop')
                self.update_overlay()

            elif self.dss_assist_enabled:
                logger.debug("Running dss_assist")
                set_focus_elite_window()
                self.update_overlay()
                try:
                    self.dss_assist()
                except EDAP_Interrupt:
                    logger.debug("Stopping DSS Assist")
                self.dss_assist_enabled = False
                self.ap_ckb('dss_stop')
                self.update_overlay()

            elif self.single_waypoint_enabled:
                self.update_overlay()
                try:
                    self.single_waypoint_assist()
                except EDAP_Interrupt:
                    logger.debug("Stopping Single Waypoint Assist")
                self.single_waypoint_enabled = False
                self.ap_ckb('single_waypoint_stop')
                self.update_overlay()

            # Check once EDAPGUI loaded to prevent errors logging to the listbox before loaded
            if self.gui_loaded:
                # Check if ship has changed
                ship = self.jn.ship_state()['type']
                # Check if a ship and not a suit (on foot)
                if ship not in ship_size_map:
                    # Clear current ship
                    self.current_ship_type = ''
                else:
                    ship_fullname = get_ship_fullname(ship)

                    # Check if ship changed or just loaded
                    if ship != self.current_ship_type:
                        if self.current_ship_type is not None:
                            cur_ship_fullname = get_ship_fullname(self.current_ship_type)
                            self.ap_ckb('log+vce', f"Switched ship from your {cur_ship_fullname} to your {ship_fullname}.")
                        else:
                            self.ap_ckb('log+vce', f"Welcome aboard your {ship_fullname}.")

                        # Check for fuel scoop and advanced docking computer
                        if not self.jn.ship_state()['has_fuel_scoop']:
                            self.ap_ckb('log+vce', f"Warning, your {ship_fullname} is not fitted with a Fuel Scoop.")
                        if not self.jn.ship_state()['has_adv_dock_comp']:
                            self.ap_ckb('log+vce', f"Warning, your {ship_fullname} is not fitted with an Advanced Docking Computer.")
                        if self.jn.ship_state()['has_std_dock_comp']:
                            self.ap_ckb('log+vce', f"Warning, your {ship_fullname} is fitted with a Standard Docking Computer.")

                        # Store ship for change detection BEFORE loading config and GUI update
                        self.current_ship_type = ship

                        # Load ship configuration with proper hierarchy
                        self.load_ship_configuration(ship)

                        # Update GUI with ship config
                        self.ap_ckb('update_ship_cfg')

                        # Reload templates
                        self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.compass_scale)

            self.update_overlay()
            cv2.waitKey(10)
            sleep(1)

    def ship_tst_pitch(self):
        """ Performs a ship pitch test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the pitch value.
        If the ship rotates too much, increase the pitch value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb('log', "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()['target'] is None:
            self.ap_ckb('log', "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send('SetSpeed50')
        self.pitchUp(360)

    def ship_tst_roll(self):
        """ Performs a ship roll test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the roll value.
        If the ship rotates too much, increase the roll value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb('log', "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()['target'] is None:
            self.ap_ckb('log', "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send('SetSpeed50')
        self.rotateLeft(360)

    def ship_tst_yaw(self):
        """ Performs a ship yaw test by pitching 360 degrees.
        If the ship does not rotate enough, decrease the yaw value.
        If the ship rotates too much, increase the yaw value.
        """
        if not self.status.get_flag(FlagsSupercruise):
            self.ap_ckb('log', "Enter Supercruise and try again.")
            return

        if self.jn.ship_state()['target'] is None:
            self.ap_ckb('log', "Select a target system and try again.")
            return

        set_focus_elite_window()
        sleep(0.25)
        self.keys.send('SetSpeed50')
        self.yawLeft(360)


#
# This main is for testing purposes.
#
def main():
    #handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    #if handle != None:
    #    win32gui.SetForegroundWindow(handle)  # put the window in foreground

    ed_ap = EDAutopilot(cb=None, doThread=False)
    ed_ap.cv_view = True
    ed_ap.cv_view_x = 4000
    ed_ap.cv_view_y = 100
    sleep(2)

    for x in range(10):
        #target_align(scrReg)
        print("Calling nav_align")
        #ed_ap.nav_align(ed_ap.scrReg)
        ed_ap.fss_detect_elw(ed_ap.scrReg)

        #loc = get_destination_offset(scrReg)
        #print("get_dest: " +str(loc))
        #loc = get_nav_offset(scrReg)
        #print("get_nav: " +str(loc))
        cv2.waitKey(0)
        print("Done nav")
        sleep(8)

    ed_ap.overlay.overlay_quit()

if __name__ == "__main__":
    main()

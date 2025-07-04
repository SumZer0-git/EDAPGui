import math
import traceback
from math import atan, degrees
import random
from tkinter import messagebox

import cv2

from simple_localization import LocalizationManager

from EDAP_EDMesg_Server import EDMesgServer
from EDGalaxyMap import EDGalaxyMap
from EDGraphicsSettings import EDGraphicsSettings
from EDShipControl import EDShipControl
from EDStationServicesInShip import EDStationServicesInShip
from EDSystemMap import EDSystemMap
from EDlogger import logging
import Image_Templates
import Screen
import Screen_Regions
from EDWayPoint import *
from EDJournal import *
from EDKeys import *
from EDafk_combat import AFK_Combat
from EDInternalStatusPanel import EDInternalStatusPanel
from NavRouteParser import NavRouteParser
from OCR import OCR
from EDNavigationPanel import EDNavigationPanel
from Overlay import *
from StatusParser import StatusParser
from Voice import *
from Robigo import *
from TCE_Integration import TceIntegration

"""
File:EDAP.py    EDAutopilot

Description:

Note:
Ideas taken from: https://github.com/skai2/EDAutopilot

Author: sumzer0@yahoo.com
"""


# Exception class used to unroll the call tree to to stop execution
class EDAP_Interrupt(Exception):
    pass


class EDAutopilot:

    def __init__(self, cb, doThread=True):

        # NOTE!!! When adding a new config value below, add the same after read_config() to set
        # a default value or an error will occur reading the new value!
        self.config = {
            "DSSButton": "Primary",        # if anything other than "Primary", it will use the Secondary Fire button for DSS
            "JumpTries": 3,                #
            "NavAlignTries": 3,            #
            "RefuelThreshold": 65,         # if fuel level get below this level, it will attempt refuel
            "FuelThreasholdAbortAP": 10,   # level at which AP will terminate, because we are not scooping well
            "WaitForAutoDockTimer": 120,   # After docking granted, wait this amount of time for us to get docked with autodocking
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
            "Language": 'en',              # Language (matching ./locales/xx.json file)
            "OCRLanguage": 'en',           # Language for OCR detection (see OCR language doc in \docs)
            "EnableEDMesg": False,
            "EDMesgActionsPort": 15570,
            "EDMesgEventsPort": 15571,
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
            if len(cnf) != len(self.config):
                # If configs of different lengths, then a new parameter was added.
                # self.write_config(self.config)
                # Add default values for new entries
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
                    cnf['EDMesgActionsPort'] = 15570
                    cnf['EDMesgEventsPort'] = 15571
                self.config = cnf
                logger.debug("read AP json:"+str(cnf))
            else:
                self.config = cnf
                logger.debug("read AP json:"+str(cnf))
        else:
            self.write_config(self.config)

        # Load selected language
        self.locale = LocalizationManager('locales', self.config['Language'])

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

        # set log level based on config input
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

        self.scr = Screen.Screen(cb)
        self.scr.scaleX = self.config['TargetScale']
        self.scr.scaleY = self.config['TargetScale']

        self.ocr = OCR(self.scr, self.config['OCRLanguage'])
        self.templ = Image_Templates.Image_Templates(self.scr.scaleX, self.scr.scaleY, self.scr.scaleX)
        self.scrReg = Screen_Regions.Screen_Regions(self.scr, self.templ)
        self.jn = EDJournal()
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
        self.compass_scale = 0.0
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

    # Loads the configuration file
    #
    def read_config(self, fileName='./configs/AP.json'):
        s = None
        try:
            with open(fileName, "r") as fp:
                s = json.load(fp)
        except  Exception as e:
            logger.warning("EDAPGui.py read_config error :"+str(e))

        return s

    def update_config(self):
        self.write_config(self.config)

    def write_config(self, data, fileName='./configs/AP.json'):
        try:
            with open(fileName, "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("EDAPGui.py write_config error:"+str(e))

    def read_ship_configs(self, filename='./configs/ship_configs.json'):
        """ Read the user's ship configuration file."""
        s = None
        try:
            with open(filename, "r") as fp:
                s = json.load(fp)
        except  Exception as e:
            logger.warning("EDAPGui.py read_ship_configs error :"+str(e))

        return s

    def update_ship_configs(self):
        """ Update the user's ship configuration file."""
        # Check if a ship and not a suit (on foot)
        if self.current_ship_type in ship_size_map:
            self.ship_configs['Ship_Configs'][self.current_ship_type]['compass_scale'] = round(self.compass_scale, 4)
            self.ship_configs['Ship_Configs'][self.current_ship_type]['PitchRate'] = self.pitchrate
            self.ship_configs['Ship_Configs'][self.current_ship_type]['RollRate'] = self.rollrate
            self.ship_configs['Ship_Configs'][self.current_ship_type]['YawRate'] = self.yawrate
            self.ship_configs['Ship_Configs'][self.current_ship_type]['SunPitchUp+Time'] = self.sunpitchuptime

            self.write_ship_configs(self.ship_configs)

    def write_ship_configs(self, data, filename='./configs/ship_configs.json'):
        """ Write the user's ship configuration file."""
        try:
            with open(filename, "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("EDAPGui.py write_ship_configs error:"+str(e))


    # draw the overlay data on the ED Window
    #
    def update_overlay(self):
        if self.config['OverlayTextEnable']:
            ap_mode = "Offline"
            if self.fsd_assist_enabled == True:
                ap_mode = "FSD Route Assist"
            elif self.robigo_assist_enabled == True:
                ap_mode = "Robigo Assist"
            elif self.sc_assist_enabled == True:
                ap_mode = "SC Assist"
            elif self.waypoint_assist_enabled == True:
                ap_mode = "Waypoint Assist"
            elif self.afk_combat_assist_enabled == True:
                ap_mode = "AFK Combat Assist"
            elif self.dss_assist_enabled == True:
                ap_mode = "DSS Assist"

            ship_state = self.jn.ship_state()['status']
            if ship_state == None:
                ship_state = '<init>'

            sclass = self.jn.ship_state()['star_class']
            if sclass == None:
                sclass = "<init>"

            location = self.jn.ship_state()['location']
            if location == None:
                location = "<init>"
            self.overlay.overlay_text('1', "AP MODE: "+ap_mode, 1, 1, (136, 53, 0))
            self.overlay.overlay_text('2', "AP STATUS: "+self.ap_state, 2, 1, (136, 53, 0))
            self.overlay.overlay_text('3', "SHIP STATUS: "+ship_state, 3, 1, (136, 53, 0))
            self.overlay.overlay_text('4', "CURRENT SYSTEM: "+location+", "+sclass, 4, 1, (136, 53, 0))
            self.overlay.overlay_text('5', "JUMPS: {} of {}".format(self.jump_cnt, self.total_jumps), 5, 1, (136, 53, 0))
            if self.config["ElwScannerEnable"] == True:
                self.overlay.overlay_text('6', "ELW SCANNER: "+self.fss_detected, 6, 1, (136, 53, 0))
            self.overlay.overlay_paint()

    def update_ap_status(self, txt):
        self.ap_state = txt
        self.update_overlay()
        self.ap_ckb('statusline', txt)


    # draws the matching rectangle within the image
    #
    def draw_match_rect(self, img, pt1, pt2, color, thick):
        wid = pt2[0]-pt1[0]
        hgt = pt2[1]-pt1[1]

        if wid < 20:
            #cv2.rectangle(screen, pt, (pt[0] + compass_width, pt[1] + compass_height),  (0,0,255), 2)
            cv2.rectangle(img, pt1, pt2, color, thick)
        else:
            len_wid = wid/5
            len_hgt = hgt/5
            half_wid = wid/2
            half_hgt = hgt/2
            tic_len = thick-1
            # top
            cv2.line(img, (int(pt1[0]), int(pt1[1])), (int(pt1[0]+len_wid), int(pt1[1])), color, thick)
            cv2.line(img, (int(pt1[0]+(2*len_wid)), int(pt1[1])), (int(pt1[0]+(3*len_wid)), int(pt1[1])), color, 1)
            cv2.line(img, (int(pt1[0]+(4*len_wid)), int(pt1[1])), (int(pt2[0]), int(pt1[1])), color, thick)
            # top tic
            cv2.line(img, (int(pt1[0]+half_wid), int(pt1[1])), (int(pt1[0]+half_wid), int(pt1[1])-tic_len), color, thick)
            # bot
            cv2.line(img, (int(pt1[0]), int(pt2[1])), (int(pt1[0]+len_wid), int(pt2[1])), color, thick)
            cv2.line(img, (int(pt1[0]+(2*len_wid)), int(pt2[1])), (int(pt1[0]+(3*len_wid)), int(pt2[1])), color, 1)
            cv2.line(img, (int(pt1[0]+(4*len_wid)), int(pt2[1])), (int(pt2[0]), int(pt2[1])), color, thick)
            # bot tic
            cv2.line(img, (int(pt1[0]+half_wid), int(pt2[1])), (int(pt1[0]+half_wid), int(pt2[1])+tic_len), color, thick)
            # left
            cv2.line(img, (int(pt1[0]), int(pt1[1])), (int(pt1[0]), int(pt1[1]+len_hgt)), color, thick)
            cv2.line(img, (int(pt1[0]), int(pt1[1]+(2*len_hgt))), (int(pt1[0]), int(pt1[1]+(3*len_hgt))), color, 1)
            cv2.line(img, (int(pt1[0]), int(pt1[1]+(4*len_hgt))), (int(pt1[0]), int(pt2[1])), color, thick)
            # left tic
            cv2.line(img, (int(pt1[0]), int(pt1[1]+half_hgt)), (int(pt1[0]-tic_len), int(pt1[1]+half_hgt)), color, thick)
            # right
            cv2.line(img, (int(pt2[0]), int(pt1[1])), (int(pt2[0]), int(pt1[1]+len_hgt)), color, thick)
            cv2.line(img, (int(pt2[0]), int(pt1[1]+(2*len_hgt))), (int(pt2[0]), int(pt1[1]+(3*len_hgt))), color, 1)
            cv2.line(img, (int(pt2[0]), int(pt1[1]+(4*len_hgt))), (int(pt2[0]), int(pt2[1])), color, thick)
            # right tic
            cv2.line(img, (int(pt2[0]), int(pt1[1]+half_hgt)), (int(pt2[0]+tic_len), int(pt1[1]+half_hgt)), color, thick)

    def calibrate_region(self, range_low, range_high, range_step, threshold: float, reg_name: str, templ_name: str):
        """ Find the best scale value in the given range of scales with the passed in threshold
        @param reg_name:
        @param range_low:
        @param range_high:
        @param range_step:
        @param threshold: The minimum threshold to match (0.0 - 1.0)
        @param templ_name: The region name i.i 'compass' or 'target'
        @return:
        """
        scale = 0
        max_pick = 0
        i = range_low
        while i <= range_high:
            self.scr.scaleX = float(i / 100)
            self.scr.scaleY = self.scr.scaleX

            # reload the templates with this scale value
            self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.scr.scaleX)

            # do image matching on the compass and the target
            image, (minVal, maxVal, minLoc, maxLoc), match = self.scrReg.match_template_in_region(reg_name, templ_name)

            border = 10  # border to prevent the box from interfering with future matches
            reg_pos = self.scrReg.reg[reg_name]['rect']
            width = self.scrReg.templates.template[templ_name]['width'] + border + border
            height = self.scrReg.templates.template[templ_name]['height'] + border + border
            left = reg_pos[0] + maxLoc[0] - border
            top = reg_pos[1] + maxLoc[1] - border

            if maxVal > threshold and maxVal > max_pick:
                # Draw box around region
                self.overlay.overlay_rect(20, (left, top), (left + width, top + height), (0, 255, 0), 2)
                self.overlay.overlay_floating_text(20, f'Match: {maxVal:5.4f}', left, top - 25, (0, 255, 0))
            else:
                # Draw box around region
                self.overlay.overlay_rect(21, (left, top), (left + width, top + height), (255, 0, 0), 2)
                self.overlay.overlay_floating_text(21, f'Match: {maxVal:5.4f}', left, top - 25, (255, 0, 0))

            self.overlay.overlay_paint()

            # Check the match percentage
            if maxVal > threshold:
                if maxVal > max_pick:
                    max_pick = maxVal
                    scale = i
                    #self.ap_ckb('log', 'Cal: Found match:' + f'{max_pick:5.4f}' + "% with scale:" + f'{self.scr.scaleX:5.4f}')

            # Next range
            i = i + range_step

        # Leave the results for the user for a couple of seconds
        sleep(2)

        # Clean up screen
        self.overlay.overlay_remove_rect(20)
        self.overlay.overlay_remove_floating_text(20)
        self.overlay.overlay_remove_rect(21)
        self.overlay.overlay_remove_floating_text(21)
        self.overlay.overlay_paint()

        return scale, max_pick

    def calibrate(self):
        """ Routine to find the optimal scaling values for the template images. """
        msg = 'Select OK to begin Calibration. You must be in space and have a star system targeted in center screen.'
        self.vce.say(msg)
        ans = messagebox.askokcancel('Calibration', msg)
        if not ans:
            return

        self.ap_ckb('log+vce', 'Calibration starting.')

        self.set_focus_elite_window()

        # Draw the target and compass regions on the screen
        key = 'target'
        targ_region = self.scrReg.reg[key]
        self.overlay.overlay_rect1(key, targ_region['rect'], (0, 0, 255), 2)
        self.overlay.overlay_floating_text(key, key, targ_region['rect'][0], targ_region['rect'][1], (0, 0, 255))
        self.overlay.overlay_paint()

        # Calibrate system target
        self.calibrate_target()

        # Clean up
        self.overlay.overlay_clear()
        self.overlay.overlay_paint()

        self.ap_ckb('log+vce', 'Calibration complete.')

    def calibrate_compass(self):
        """ Routine to find the optimal scaling values for the template images. """
        msg = 'Select OK to begin Calibration. You must be in space and have the compass visible.'
        self.vce.say(msg)
        ans = messagebox.askokcancel('Calibration', msg)
        if not ans:
            return

        self.ap_ckb('log+vce', 'Calibration starting.')

        self.set_focus_elite_window()

        # Draw the target and compass regions on the screen
        key = 'compass'
        targ_region = self.scrReg.reg[key]
        self.overlay.overlay_rect1(key, targ_region['rect'], (0, 0, 255), 2)
        self.overlay.overlay_floating_text(key, key, targ_region['rect'][0], targ_region['rect'][1], (0, 0, 255))
        self.overlay.overlay_paint()

        # Calibrate compass
        self.calibrate_ship_compass()

        # Clean up
        self.overlay.overlay_clear()
        self.overlay.overlay_paint()

        self.ap_ckb('log+vce', 'Calibration complete.')

    def calibrate_target(self):
        """ Calibrate target """
        range_low = 30
        range_high = 200
        range_step = 1
        scale_max = 0
        max_val = 0

        # loop through the test twice. Once over the wide scaling range at 1% increments and once over a
        # small scaling range at 0.1% increments.
        # Find out which scale factor meets the highest threshold value.
        for i in range(2):
            threshold = 0.5  # Minimum match is constant. Result will always be the highest match.
            scale, max_pick = self.calibrate_region(range_low, range_high, range_step, threshold, 'target', 'target')
            if scale != 0:
                scale_max = scale
                max_val = max_pick
                range_low = scale - 5
                range_high = scale + 5
                range_step = 0.1
            else:
                break  # no match found with threshold

        # if we found a scaling factor that meets our criteria, then save it to the resolution.json file
        if max_val != 0:
            self.scr.scaleX = float(scale_max / 100)
            self.scr.scaleY = self.scr.scaleX
            self.ap_ckb('log', f'Target Cal: Best match: {max_val * 100:5.2f}% at scale: {self.scr.scaleX:5.4f}')
            self.config['TargetScale'] = round(self.scr.scaleX, 4)
            # self.scr.scales['Calibrated'] = [self.scr.scaleX, self.scr.scaleY]
            self.scr.write_config(
                data=None)  # None means the writer will use its own scales variable which we modified
        else:
            self.ap_ckb('log',
                        f'Target Cal: Insufficient matching to meet reliability, max % match: {max_val * 100:5.2f}%')

        # reload the templates with the new (or previous value)
        self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.compass_scale)

    def calibrate_ship_compass(self):
        """ Calibrate Compass """
        range_low = 30
        range_high = 200
        range_step = 1
        scale_max = 0
        max_val = 0

        # loop through the test twice. Once over the wide scaling range at 1% increments and once over a
        # small scaling range at 0.1% increments.
        # Find out which scale factor meets the highest threshold value.
        for i in range(2):
            threshold = 0.5  # Minimum match is constant. Result will always be the highest match.
            scale, max_pick = self.calibrate_region(range_low, range_high, range_step, threshold, 'compass','compass')
            if scale != 0:
                scale_max = scale
                max_val = max_pick
                range_low = scale - 5
                range_high = scale + 5
                range_step = 0.1
            else:
                break  # no match found with threshold

        # if we found a scaling factor that meets our criteria, then save it to the resolution.json file
        if max_val != 0:
            c_scaleX = float(scale_max / 100)
            self.ap_ckb('log',
                        f'Compass Cal: Max best match: {max_val * 100:5.2f}% with scale: {c_scaleX:5.4f}')
            # Keep new value
            self.compass_scale = c_scaleX

        else:
            self.ap_ckb('log',
                        f'Compass Cal: Insufficient matching to meet reliability, max % match: {max_val * 100:5.2f}%')

        # reload the templates with the new (or previous value)
        self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY, self.compass_scale)

    # Go into FSS, check to see if we have a signal waveform in the Earth, Water or Ammonia zone
    #  if so, announce finding and log the type of world found
    #
    def fss_detect_elw(self, scr_reg):

        #open fss
        self.keys.send('SetSpeedZero')
        sleep(0.1)
        self.keys.send('ExplorationFSSEnter')
        sleep(2.5)

        # look for a circle or signal in this region
        elw_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('fss', 'elw')
        elw_sig_image, (minVal1, maxVal1, minLoc1, maxLoc1), match = scr_reg.match_template_in_image(elw_image, 'elw_sig')

        # dvide the region in thirds.  Earth, then Water, then Ammonio
        wid_div3 = scr_reg.reg['fss']['width']/3

        # Exit out of FSS, we got the images we need to process
        self.keys.send('ExplorationFSSQuit')

        # Uncomment this to show on the ED Window where the region is define.  Must run this file as an App, so uncomment out
        # the main at the bottom of file
        #self.overlay.overlay_rect('fss', (scr_reg.reg['fss']['rect'][0], scr_reg.reg['fss']['rect'][1]),
        #                (scr_reg.reg['fss']['rect'][2],  scr_reg.reg['fss']['rect'][3]), (120, 255, 0),2)
        #self.overlay.overlay_paint()

        if self.cv_view:
            elw_image_d = elw_image.copy()
            elw_image_d = cv2.cvtColor(elw_image_d, cv2.COLOR_GRAY2RGB)
            #self.draw_match_rect(elw_image_d, maxLoc, (maxLoc[0]+15,maxLoc[1]+15), (255,255,255), 1)
            self.draw_match_rect(elw_image_d, maxLoc1, (maxLoc1[0]+15, maxLoc1[1]+25), (0, 0, 255), 1)
            cv2.putText(elw_image_d, f'{maxVal1:5.2f}> .70', (1, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('fss', elw_image_d)
            cv2.moveWindow('fss', self.cv_view_x, self.cv_view_y+100)
            cv2.waitKey(30)

        logger.info("elw detected:{0:6.2f} ".format(maxVal)+" sig:{0:6.2f}".format(maxVal1))

        # check if the circle or the signal meets probability number, if so, determine which type by its region
        #if (maxVal > 0.65 or (maxVal1 > 0.60 and maxLoc1[1] < 30) ):
        # only check for singal
        if maxVal1 > 0.70 and maxLoc1[1] < 30:
            if maxLoc1[0] < wid_div3:
                sstr = "Earth"
            elif maxLoc1[0] > (wid_div3*2):
                sstr = "Water"
            else:
                sstr = "Ammonia"
            # log the entry into the elw.txt file
            f = open("elw.txt", 'a')
            f.write(self.jn.ship_state()["location"]+", Type: "+sstr+
                    ", Probabilty: {0:3.0f}% ".format((maxVal1*100))+
                    ", Date: "+str(datetime.now())+str("\n"))
            f.close()
            self.vce.say(sstr+" like world detected ")
            self.fss_detected = sstr+" like world detected "
            logger.info(sstr+" world at: "+str(self.jn.ship_state()["location"]))
        else:
            self.fss_detected = "nothing found"

        self.keys.send('SetSpeed100')

        return

    def have_destination(self, scr_reg) -> bool:
        """ Check to see if the compass is on the screen. """
        icompass_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('compass', 'compass')

        logger.debug("has_destination:"+str(maxVal))

        # need > x in the match to say we do have a destination
        if maxVal < scr_reg.compass_match_thresh:
            return False
        else:
            return True

    def interdiction_check(self) -> bool:
        """ Checks if we are being interdicted. This can occur in SC and maybe in system jump by Thargoids
        (needs to be verified). Returns False if not interdicted, True after interdiction is detected and we
        get away. Use return result to determine the next action (continue, or do something else).
        """
        # Return if we are not being interdicted.
        if not self.status.get_flag(FlagsBeingInterdicted):
            return False

        # Interdiction detected.
        self.vce.say("Danger. Interdiction detected.")
        self.ap_ckb('log', 'Interdiction detected.')

        # Keep setting speed to zero to submit while in supercruise or system jump.
        while self.status.get_flag(FlagsSupercruise) or self.status.get_flag2(Flags2FsdHyperdriveCharging):
            self.keys.send('SetSpeedZero')  # Submit.
            sleep(0.5)

        # Set speed to 100%.
        self.keys.send('SetSpeed100')

        # Wait for cooldown to start.
        self.status.wait_for_flag_on(FlagsFsdCooldown)

        # Boost while waiting for cooldown to complete.
        while not self.status.wait_for_flag_off(FlagsFsdCooldown, timeout=1):
            self.keys.send('UseBoostJuice')

        # Cooldown over, get us out of here.
        self.keys.send('Supercruise')

        # Start SCO monitoring
        self.start_sco_monitoring()

        # Wait for jump to supercruise, keep boosting.
        while not self.status.get_flag(FlagsFsdJump):
            self.keys.send('UseBoostJuice')
            sleep(1)

        # Update journal flag.
        self.jn.ship_state()['interdicted'] = False  # reset flag
        return True

    def get_nav_offset(self, scr_reg):
        """ Determine the x,y offset from center of the compass of the nav point.
         Returns the x,y,z value as x,y in degrees (-90 to 90) and z as 1 or -1.
         {'roll': r, 'pit': p, 'yaw': y}
         Where 'roll' is:
            -180deg (6 o'oclock anticlockwise) to
             0deg (12 o'clock) to
             180deg (6 o'oclock clockwise)
         """

        icompass_image, (minVal, maxVal, minLoc, maxLoc), match = (
            scr_reg.match_template_in_region('compass', 'compass'))

        pt = maxLoc

        # get wid/hgt of templates
        c_wid = scr_reg.templates.template['compass']['width']
        c_hgt = scr_reg.templates.template['compass']['height']
        wid = scr_reg.templates.template['navpoint']['width']
        hgt = scr_reg.templates.template['navpoint']['height']

        # cut out the compass from the region
        pad = 5
        compass_image = icompass_image[abs(pt[1]-pad): pt[1]+c_hgt+pad, abs(pt[0]-pad): pt[0]+c_wid+pad].copy()

        # find the nav point within the compass box
        navpt_image, (n_minVal, n_maxVal, n_minLoc, n_maxLoc), match = (
            scr_reg.match_template_in_image(compass_image, 'navpoint'))
        n_pt = n_maxLoc

        compass_x_min = pad
        compass_x_max = c_wid + pad - wid
        compass_y_min = pad
        compass_y_max = c_hgt + pad - hgt

        if n_maxVal < scr_reg.navpoint_match_thresh:
            final_z_pct = -1.0  # Behind

            # find the nav point within the compass box using the -behind template
            navpt_image, (n_minVal, n_maxVal, n_minLoc, n_maxLoc), match = (
                scr_reg.match_template_in_image(compass_image, 'navpoint-behind'))
            n_pt = n_maxLoc
        else:
            final_z_pct = 1.0  # Ahead

        # Continue calc
        final_x_pct = 2*(((n_pt[0]-compass_x_min)/(compass_x_max-compass_x_min))-0.5)  # X as percent (-1.0 to 1.0, 0.0 in the center)
        final_x_pct = max(min(final_x_pct, 1.0), -1.0)

        final_y_pct = -2*(((n_pt[1]-compass_y_min)/(compass_y_max-compass_y_min))-0.5)  # Y as percent (-1.0 to 1.0, 0.0 in the center)
        final_y_pct = max(min(final_y_pct, 1.0), -1.0)

        # Calc angle in degrees starting at 0 deg at 12 o'clock and increasing clockwise
        # so 3 o'clock is +90° and 9 o'clock is -90°.
        final_roll_deg = 0.0
        if final_x_pct > 0.0:
            final_roll_deg = 90 - degrees(atan(final_y_pct/final_x_pct))
        elif final_x_pct < 0.0:
            final_roll_deg = -90 - degrees(atan(final_y_pct/final_x_pct))

        # 'longitudinal' radius of compass at given 'latitude'
        lng_rad_at_lat = math.cos(math.asin(final_y_pct))
        lng_rad_at_lat = max(lng_rad_at_lat, 0.001)  # Prevent div by zero

        # 'Latitudinal' radius of compass at given 'longitude'
        lat_rad_at_lng = math.sin(math.acos(final_x_pct))
        lat_rad_at_lng = max(lat_rad_at_lng, 0.001)  # Prevent div by zero

        # Pitch and yaw as a % of the max as defined by the compass circle
        pit_pct = max(min(final_y_pct/lat_rad_at_lng, 1.0), -1.0)
        yaw_pct = max(min(final_x_pct/lng_rad_at_lat, 1.0), -1.0)

        if final_z_pct > 0:
            final_pit_deg = (-1 * degrees(math.acos(pit_pct))) + 90  # Y in deg (-90.0 to 90.0, 0.0 in the center)
            final_yaw_deg = (-1 * degrees(math.acos(yaw_pct))) + 90  # X in deg (-90.0 to 90.0, 0.0 in the center)
        else:
            if final_y_pct > 0:
                final_pit_deg = degrees(math.acos(pit_pct)) + 90  # Y in deg (-90.0 to 90.0, 0.0 in the center)
            else:
                final_pit_deg = degrees(math.acos(pit_pct)) - 270  # Y in deg (-90.0 to 90.0, 0.0 in the center)

            if final_x_pct > 0:
                final_yaw_deg = degrees(math.acos(yaw_pct)) + 90  # X in deg (-90.0 to 90.0, 0.0 in the center)
            else:
                final_yaw_deg = degrees(math.acos(yaw_pct)) - 270  # X in deg (-90.0 to 90.0, 0.0 in the center)

        result = {'x': round(final_x_pct, 2), 'y': round(final_y_pct, 2), 'z': round(final_z_pct, 2),
                  'roll': round(final_roll_deg, 2), 'pit': round(final_pit_deg, 2), 'yaw': round(final_yaw_deg, 2)}

        if self.cv_view:
            icompass_image_d = cv2.cvtColor(icompass_image, cv2.COLOR_GRAY2RGB)
            self.draw_match_rect(icompass_image_d, pt, (pt[0]+c_wid, pt[1]+c_hgt), (0, 0, 255), 2)
            #cv2.rectangle(icompass_image_display, pt, (pt[0]+c_wid, pt[1]+c_hgt), (0, 0, 255), 2)
            #self.draw_match_rect(compass_image, n_pt, (n_pt[0] + wid, n_pt[1] + hgt), (255,255,255), 2)
            self.draw_match_rect(icompass_image_d, (pt[0]+n_pt[0]-pad, pt[1]+n_pt[1]-pad), (pt[0]+n_pt[0]+wid-pad, pt[1]+n_pt[1]+hgt-pad), (0, 255, 0), 1)
            #cv2.rectangle(icompass_image_display, (pt[0]+n_pt[0]-pad, pt[1]+n_pt[1]-pad), (pt[0]+n_pt[0] + wid-pad, pt[1]+n_pt[1] + hgt-pad), (0, 0, 255), 2)

            #   dim = (int(destination_width/3), int(destination_height/3))

            #   img = cv2.resize(dst_image, dim, interpolation =cv2.INTER_AREA)
            icompass_image_d = cv2.rectangle(icompass_image_d, (0, 0), (1000, 60), (0, 0, 0), -1)
            cv2.putText(icompass_image_d, f'Compass: {maxVal:5.4f} > {scr_reg.compass_match_thresh:5.2f}', (1, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(icompass_image_d, f'Nav Point: {n_maxVal:5.4f} > {scr_reg.navpoint_match_thresh:5.2f}', (1, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            #cv2.putText(icompass_image_d, f'Result: {result}', (1, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(icompass_image_d, f'x: {final_x_pct:5.2f} y: {final_y_pct:5.2f} z: {final_z_pct:5.2f}', (1, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(icompass_image_d, f'r: {final_roll_deg:5.2f}deg p: {final_pit_deg:5.2f}deg y: {final_yaw_deg:5.2f}deg', (1, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('compass', icompass_image_d)
            cv2.moveWindow('compass', self.cv_view_x - 400, self.cv_view_y + 600)
            cv2.waitKey(30)

        return result

    def is_destination_occluded(self, scr_reg) -> bool:
        """ Looks to see if the 'dashed' line of the target is present indicating the target
        is occluded by the planet.
        @param scr_reg: The screen region to check.
        @return: True if target occluded (meets threshold), else False.
        """
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('target_occluded', 'target_occluded', inv_col=False)

        pt = maxLoc

        if self.cv_view:
            dst_image_d = cv2.cvtColor(dst_image, cv2.COLOR_GRAY2RGB)
            destination_width = scr_reg.reg['target']['width']
            destination_height = scr_reg.reg['target']['height']

            width  = scr_reg.templates.template['target_occluded']['width']
            height = scr_reg.templates.template['target_occluded']['height']
            try:
                self.draw_match_rect(dst_image_d, pt, (pt[0]+width, pt[1]+height), (0, 0, 255), 2)
                dim = (int(destination_width/2), int(destination_height/2))

                img = cv2.resize(dst_image_d, dim, interpolation=cv2.INTER_AREA)
                img = cv2.rectangle(img, (0, 0), (1000, 25), (0, 0, 0), -1)
                cv2.putText(img, f'{maxVal:5.4f} > {scr_reg.target_occluded_thresh:5.2f}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow('occluded', img)
                cv2.moveWindow('occluded', self.cv_view_x, self.cv_view_y+650)
            except Exception as e:
                print("exception in getdest: "+str(e))
            cv2.waitKey(30)

        if maxVal > scr_reg.target_occluded_thresh:
            logger.debug(f"Target is occluded ({maxVal:5.4f} > {scr_reg.target_occluded_thresh:5.2f})")
            return True
        else:
            #logger.debug(f"Target is not occluded ({maxVal:5.4f} < {scr_reg.target_occluded_thresh:5.2f})")
            return False

    def get_destination_offset(self, scr_reg):
        """ Determine how far off we are from the target being in the middle of the screen
        (in this case the specified region). """
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('target', 'target')

        pt = maxLoc

        destination_width = scr_reg.reg['target']['width']
        destination_height = scr_reg.reg['target']['height']

        width = scr_reg.templates.template['target']['width']
        height = scr_reg.templates.template['target']['height']

        # need some fug numbers since our template is not symetric to determine center
        final_x = ((pt[0]+((1/2)*width))-((1/2)*destination_width))-7
        final_y = (((1/2)*destination_height)-(pt[1]+((1/2)*height)))+22

        #  print("get dest, final:" + str(final_x)+ " "+str(final_y))
        #  print(destination_width, destination_height, width, height)
        #  print(maxLoc)

        if self.cv_view:
            dst_image_d = cv2.cvtColor(dst_image, cv2.COLOR_GRAY2RGB)
            try:
                self.draw_match_rect(dst_image_d, pt, (pt[0]+width, pt[1]+height), (0, 0, 255), 2)
                dim = (int(destination_width/2), int(destination_height/2))

                img = cv2.resize(dst_image_d, dim, interpolation=cv2.INTER_AREA)
                img = cv2.rectangle(img, (0, 0), (1000, 25), (0, 0, 0), -1)
                cv2.putText(img, f'{maxVal:5.4f} > {scr_reg.target_thresh:5.2f}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow('target', img)
                #cv2.imshow('tt', scr_reg.templates.template['target']['image'])
                cv2.moveWindow('target', self.cv_view_x, self.cv_view_y+425)
            except Exception as e:
                print("exception in getdest: "+str(e))
            cv2.waitKey(30)

        #print (maxVal)
        # must be > x to have solid hit, otherwise we are facing wrong way (empty circle)
        if maxVal < scr_reg.target_thresh:
            result = None
        else:
            result = {'x': final_x, 'y': final_y}

        return result

    def sc_disengage_label_up(self, scr_reg) -> bool:
        """ look for messages like "PRESS [J] TO DISENGAGE" or "SUPERCRUISE OVERCHARGE ACTIVE",
         if in this region then return true.
        The aim of this function is to return that a message is there, and then use OCR to determine
        what the message is. This will only use the high CPU usage OCR when necessary."""
        dis_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('disengage', 'disengage')

        pt = maxLoc

        width = scr_reg.templates.template['disengage']['width']
        height = scr_reg.templates.template['disengage']['height']

        reg_rect = scr_reg.reg['disengage']['rect']

        if self.cv_view:
            self.draw_match_rect(dis_image, pt, (pt[0] + width, pt[1] + height), (0,255,0), 2)
            dis_image = cv2.rectangle(dis_image, (0, 0), (1000, 25), (0, 0, 0), -1)
            cv2.putText(dis_image, f'{maxVal:5.4f} > {scr_reg.disengage_thresh}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('sc_disengage_label_up', dis_image)
            cv2.moveWindow('sc_disengage_label_up', self.cv_view_x-460,self.cv_view_y+575)
            cv2.waitKey(1)

        if maxVal > scr_reg.disengage_thresh:
            return True
        else:
            return False

    def sc_disengage(self, scr_reg) -> bool:
        """ DEPRECATED - Replaced with 'sc_disengage_label_up' and 'sc_disengage_active' using OCR.
        look for the "PRESS [J] TO DISENGAGE" image, if in this region then return true
        """
        dis_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('disengage', 'disengage')

        pt = maxLoc

        width = scr_reg.templates.template['disengage']['width']
        height = scr_reg.templates.template['disengage']['height']

        if self.cv_view:
            self.draw_match_rect(dis_image, pt, (pt[0] + width, pt[1] + height), (0,255,0), 2)
            dis_image = cv2.rectangle(dis_image, (0, 0), (1000, 25), (0, 0, 0), -1)
            cv2.putText(dis_image, f'{maxVal:5.4f} > {scr_reg.disengage_thresh}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('disengage', dis_image)
            cv2.moveWindow('disengage', self.cv_view_x-460,self.cv_view_y+575)
            cv2.waitKey(1)

        #logger.debug("Disenage = "+str(maxVal))

        if maxVal > scr_reg.disengage_thresh:
            logger.info("'PRESS [] TO DISENGAGE' detected. Disengaging Supercruise")
            self.vce.say("Disengaging Supercruise")
            return True
        else:
            return False

    def sc_disengage_active(self, scr_reg) -> bool:
        """ look for the "SUPERCRUISE OVERCHARGE ACTIVE" text using OCR, if in this region then return true. """
        image = self.scr.get_screen_region(scr_reg.reg['disengage']['rect'])
        # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mask = scr_reg.capture_region_filtered(self.scr, 'disengage')
        masked_image = cv2.bitwise_and(image, image, mask=mask)
        image = masked_image

        # OCR the selected item
        sim_match = 0.35  # Similarity match 0.0 - 1.0 for 0% - 100%)
        sim = 0.0
        ocr_textlist = self.ocr.image_simple_ocr(image)
        if ocr_textlist is not None:
            sim = self.ocr.string_similarity(self.locale["PRESS_TO_DISENGAGE_MSG"], str(ocr_textlist))
            logger.info(f"Disengage similarity with {str(ocr_textlist)} is {sim}")

        if self.cv_view:
            image = cv2.rectangle(image, (0, 0), (1000, 30), (0, 0, 0), -1)
            cv2.putText(image, f'Text: {str(ocr_textlist)}', (1, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(image, f'Similarity: {sim:5.4f} > {sim_match}', (1, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('disengage2', image)
            cv2.moveWindow('disengage2', self.cv_view_x - 460, self.cv_view_y + 650)
            cv2.waitKey(30)

        if sim > sim_match:
            logger.info("'PRESS [] TO DISENGAGE' detected. Disengaging Supercruise")
            #cv2.imwrite(f'test/disengage.png', image)
            return True

        return False

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

        # Performs left menu ops to request docking

    def request_docking(self, toCONTACT):
        """ Request docking from Nav Panel. """
        self.nav_panel.request_docking(toCONTACT)

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
        self.request_docking(1)
        sleep(1)

        tries = self.config['DockingRetries']
        granted = False
        if self.jn.ship_state()['status'] == "dockinggranted":
            granted = True
            # Go back to navigation tab
            self.request_docking_cleanup()
        else:
            for i in range(tries):
                if self.jn.ship_state()['no_dock_reason'] == "Distance":
                    self.keys.send('SetSpeed50')
                    sleep(5)
                    self.keys.send('SetSpeedZero', repeat=2)
                sleep(3)  # Wait for ship to come to stop
                self.request_docking(0)
                self.keys.send('SetSpeedZero', repeat=2)
                sleep(1.5)
                if self.jn.ship_state()['status'] == "dockinggranted":
                    granted = True
                    # Go back to navigation tab
                    self.request_docking_cleanup()
                    break
                if self.jn.ship_state()['status'] == "dockingdenied":
                    pass

        if not granted:
            self.ap_ckb('log', 'Docking denied: '+str(self.jn.ship_state()['no_dock_reason']))
            logger.warning('Did not get docking authorization, reason:'+str(self.jn.ship_state()['no_dock_reason']))
            raise Exception('Docking failed (Did not get docking authorization)')
        else:
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

    def request_docking_cleanup(self):
        """ After request docking, go back to NAVIGATION tab in Nav Panel from the CONTACTS tab. """
        self.nav_panel.request_docking_cleanup()

    def is_sun_dead_ahead(self, scr_reg):
        return scr_reg.sun_percent(scr_reg.screen) > 5

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

            if abs(off['yaw']) < close and abs(off['pit']) < close:
                break

            for i in range(20):
                # Calc roll time based on nav point location
                if abs(off['roll']) > close and (180 - abs(off['roll']) > close):
                    # first roll to get the nav point at the vertical position
                    if off['yaw'] > 0 and off['pit'] > 0:
                        # top right quad, then roll right to get to 90 up
                        self.rotateRight(off['roll'])
                    elif off['yaw'] > 0 > off['pit']:
                        # bottom right quad, then roll left
                        self.rotateLeft(180 - off['roll'])
                    elif off['yaw'] < 0 < off['pit']:
                        # top left quad, then roll left
                        self.rotateLeft(-off['roll'])
                    else:
                        # bottom left quad, then roll right
                        self.rotateRight(180 + off['roll'])
                    sleep(1)
                    off = self.get_nav_offset(scr_reg)
                else:
                    break

            for i in range(20):
                # Calc pitch time based on nav point location
                if abs(off['pit']) > close:
                    if off['pit'] < 0:
                        self.pitchDown(abs(off['pit']))
                    else:
                        self.pitchUp(abs(off['pit']))
                    sleep(0.5)
                    off = self.get_nav_offset(scr_reg)
                else:
                    break

            for i in range(20):
                # Calc yaw time based on nav point location
                if abs(off['yaw']) > close:
                    if off['yaw'] < 0:
                        self.yawLeft(abs(off['yaw']))
                    else:
                        self.yawRight(abs(off['yaw']))
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
        #
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

    def sc_target_align(self, scr_reg) -> bool:
        """ Stays tight on the target, monitors for disengage and obscured.
        If target could not be found, return false."""

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
            return False

        #logger.debug("sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

        while (abs(off['x']) > close) or \
                (abs(off['y']) > close):

            if (abs(off['x']) > 25):
                hold_yaw = 0.2
            else:
                hold_yaw = 0.09

            if (abs(off['y']) > 25):
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

            new = self.get_destination_offset(scr_reg)
            if new:
                off = new

            # Check if target is outside the target region (behind us) and break loop
            if new is None:
                logger.debug("sc_target_align lost target")
                self.ap_ckb('log', 'Target lost, attempting re-alignment.')
                return False

        return True

    def occluded_reposition(self, scr_reg):
        """ Reposition is use when the target is occluded by a planet or other.
        We pitch 90 deg down for a bit, then up 90, this should make the target underneath us
        this is important because when we do nav_align() if it does not see the Nav Point
        in the compass (because it is a hollow circle), then it will pitch down, this will
        bring the target into view quickly. """
        self.ap_ckb('log+vce', 'Target occluded, repositioning.')
        self.keys.send('SetSpeed50')
        sleep(5)
        self.pitchDown(90)

        # Speed away
        self.keys.send('SetSpeed100')
        sleep(15)

        self.keys.send('SetSpeed50')
        sleep(5)
        self.pitchUp(90)
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
        if self.config["EnableRandomness"] == True:
            pause_time = pause_time+random.randint(0, 3)
        # need time to get away from the Sun so heat will disipate before we use FSD
        sleep(pause_time)

        if self.config["ElwScannerEnable"] == True:
            self.fss_detect_elw(scr_reg)
            if self.config["EnableRandomness"] == True:
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

        # a set of convience routes to pitch, rotate by specified degress

    #
    def rotateLeft(self, deg):
        htime = deg/self.rollrate
        self.keys.send('RollLeftButton', hold=htime)

    def rotateRight(self, deg):
        htime = deg/self.rollrate
        self.keys.send('RollRightButton', hold=htime)

    def pitchDown(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchDownButton', htime)

    def pitchUp(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchUpButton', htime)

    def yawLeft(self, deg):
        htime = deg/self.yawrate
        self.keys.send('YawLeftButton', hold=htime)

    def yawRight(self, deg):
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
            raise Exception('not ready to refuel')

        is_star_scoopable = self.jn.ship_state()['star_class'] in scoopable_stars

        # if the sun is not scoopable, then set a low low threshold so we can pick up the dull red
        # sun types.  Since we won't scoop it doesn't matter how much we pitch up
        # if scoopable we know white/yellow stars are bright, so set higher threshold, this will allow us to
        #  mast out the galaxy edge (which is bright) and not pitch up too much and avoid scooping
        if is_star_scoopable == False or not has_fuel_scoop:
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

        elif is_star_scoopable == False:
            self.ap_ckb('log', 'Skip refuel - not a fuel star')
            logger.debug('refuel= needed, unsuitable star')
            self.pitchUp(20)
            return False

        elif self.jn.ship_state()['fuel_percent'] >= self.config['RefuelThreshold']:
            self.ap_ckb('log', 'Skip refuel - fuel level okay')
            logger.debug('refuel= not needed')
            return False

        elif not has_fuel_scoop:
            self.ap_ckb('log', 'Skip refuel - no fuel scoop fitted')
            logger.debug('No fuel scoop fitted.')
            self.pitchUp(20)
            return False

        else:
            self.pitchUp(15)  # if not refueling pitch up somemore so we won't heat up
            return False


    # set focus to the ED window, if ED does not have focus then the key strokes will go to the window
    # that does have focus
    def set_focus_elite_window(self):
        handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
        if handle != 0:
            win32gui.SetForegroundWindow(handle)  # give focus to ED

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
                    self.pitchUp(90 * 1.25)

                # If we are on a Fleet Carrier we will pitch up 90 deg and fly away to avoid planet
                elif fleet_carrier:
                    self.ap_ckb('log+vce', 'Maneuvering')
                    # The pitch rates are defined in SC, not normal flights, so bump this up a bit
                    self.pitchUp(90 * 1.25)

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
            self.pitchUp(90 * 1.25)
            self.keys.send('SetSpeed100')

            # While Mass Locked, keep boosting.
            while not self.status.wait_for_flag_off(FlagsFsdMassLocked, timeout=2):
                self.keys.send('UseBoostJuice')

            # Enter supercruise
            self.keys.send('Supercruise')

            # Start SCO monitoring
            self.start_sco_monitoring()

            # Wait for SC
            res = self.status.wait_for_flag_on(FlagsSupercruise, timeout=30)

            # Enable SCO. If SCO not fitted, this will do nothing.
            self.keys.send('UseBoostJuice')

            # Wait until out of orbit.
            res = self.status.wait_for_flag_off(FlagsHasLatLong, timeout=60)
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

    def waypoint_assist(self, keys, scr_reg):
        """ Processes the waypoints, performing jumps and sc assist if going to a station
        also can then perform trades if specific in the waypoints file."""
        self.waypoint.waypoint_assist(keys, scr_reg)

    def jump_to_system(self, scr_reg) -> bool:
        """ Jumps to the currently targeted system. Returns True if we successfully travel there, else False. """
        # Current in game destination
        status = self.status.get_cleaned_data()
        destination_body = status['Destination_Body']  # The body number (0 for prim star)
        destination_name = status['Destination_Name']  # The system/body/station/settlement name

        # Check we have a route and that we have a destination to a star (body 0).
        # We can have one without the other.
        if destination_body != 0 or destination_name == "":
            self.ap_ckb('log', "A valid destination system is not selected.")
            return False

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()['status'] != 'in_supercruise':
            self.sc_engage()

        # Route sent...  FSD Assist to that destination
        reached_dest = self.fsd_assist(scr_reg)
        if not reached_dest:
            return False

        return True

    def supercruise_to_station(self, scr_reg, station_name: str) -> bool:
        """ Supercruise to the specified target, which may be a station, FC, body, signal source, etc.
        Returns True if we travel successfully travel there, else False. """
        # If waypoint file has a Station Name associated then attempt targeting it
        self.update_ap_status(f"Targeting Station: {station_name}")
        #res = self.nav_panel.lock_destination(station_name)
        #if not res:
        #    return False

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()['status'] != 'in_supercruise':
            self.sc_engage()

        # Successful targeting of Station, lets go to it
        sleep(3)  # Wait for compass to stop flashing blue!
        if self.have_destination(scr_reg):
            self.ap_ckb('log', " - Station: " + station_name)
            self.update_ap_status(f"SC to Station: {station_name}")
            self.sc_assist(scr_reg)
        else:
            self.ap_ckb('log', f" - Could not target station: {station_name}")
            return False

        return True

    def fsd_assist(self, scr_reg):
        """ FSD Route Assist. """
        # TODO - can we enable this? Seems like a better way
        # nav_route_parser = NavRouteParser()
        logger.debug('self.jn.ship_state='+str(self.jn.ship_state()))

        starttime = time.time()
        starttime -= 20  # to account for first instance not doing positioning

        # TODO - can we enable this? Seems like a better way
        # if nav_route_parser.get_last_system() is not None:
        if self.jn.ship_state()['target']:
            # if we are starting the waypoint docked at a station, we need to undock first
            if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
                self.update_overlay()
                self.waypoint_undock_seq()

        # Keep jumping as long as there is a system to jump to.
        # TODO - can we enable this? Seems like a better way
        # while nav_route_parser.get_last_system() is not None:
        while self.jn.ship_state()['target']:
            self.update_overlay()

            if self.jn.ship_state()['status'] == 'in_space' or self.jn.ship_state()['status'] == 'in_supercruise':
                self.update_ap_status("Align")

                self.mnvr_to_target(scr_reg)

                self.update_ap_status("Jump")

                self.jump(scr_reg)

                # update jump counters
                self.total_dist_jumped += self.jn.ship_state()['dist_jumped']
                self.total_jumps = self.jump_cnt+self.jn.ship_state()['jumps_remains']
                
                # reset, upon next Jump the Journal will be updated again, unless last jump,
                # so we need to clear this out
                
                self.jn.ship_state()['jumps_remains'] = 0

                self.update_overlay()

                avg_time_jump = (time.time()-starttime)/self.jump_cnt
                self.ap_ckb('jumpcount', "Dist: {:,.1f}".format(self.total_dist_jumped)+"ly"+
                            "  Jumps: {}of{}".format(self.jump_cnt, self.total_jumps)+"  @{}s/j".format(int(avg_time_jump))+
                            "  Fu#: "+str(self.refuel_cnt))

                # Do the Discovery Scan (Honk)
                self.honk_thread = threading.Thread(target=self.honk, daemon=True)
                self.honk_thread.start()

                # Refuel
                refueled = self.refuel(scr_reg)

                self.update_ap_status("Maneuvering")

                self.position(scr_reg, refueled)

                if self.jn.ship_state()['fuel_percent'] < self.config['FuelThreasholdAbortAP']:
                    self.ap_ckb('log', "AP Aborting, low fuel")
                    self.vce.say("AP Aborting, low fuel")
                    break

        sleep(2)  # wait until screen stabilizes from possible last positioning

        # if there is no destination defined, we are done
        if not self.have_destination(scr_reg):
            self.keys.send('SetSpeedZero')
            self.vce.say("Destination Reached, distance jumped:"+str(int(self.total_dist_jumped))+" lightyears")
            if self.config["AutomaticLogout"] == True:
                sleep(5)
                self.logout()
            return True
        # else there is a destination in System, so let jump over to SC Assist
        else:
            self.keys.send('SetSpeed100')
            self.vce.say("System Reached, preparing for supercruise")
            sleep(1)
            return False

    # Supercruise Assist loop to travel to target in system and perform autodock
    #
    def sc_assist(self, scr_reg, do_docking=True):
        logger.debug("Entered sc_assist")

        # Goto cockpit view
        self.ship_control.goto_cockpit_view()

        align_failed = False
        # see if we have a compass up, if so then we have a target
        if not self.have_destination(scr_reg):
            self.ap_ckb('log', "Quiting SC Assist - Compass not found. Rotate ship and try again.")
            logger.debug("Quiting sc_assist - compass not found")
            return

        # if we are starting the waypoint docked at a station or landed, we need to undock/takeoff first
        if self.status.get_flag(FlagsDocked) or self.status.get_flag(FlagsLanded):
            self.update_overlay()
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()['status'] != 'in_supercruise':
            self.sc_engage()

        # Ensure we are 50%, don't want the loop of shame
        # Align Nav to target
        self.keys.send('SetSpeed50')
        self.nav_align(scr_reg)  # Compass Align
        self.keys.send('SetSpeed50')

        self.jn.ship_state()['interdicted'] = False

        # Loop forever keeping tight align to target, until we get SC Disengage popup
        self.ap_ckb('log+vce', 'Target Align')
        while True:
            sleep(0.05)
            if self.jn.ship_state()['status'] == 'in_supercruise':
                # Align and stay on target. If false is returned, we have lost the target behind us.
                if not self.sc_target_align(scr_reg):
                    # Continue ahead before aligning to prevent us circling the target
                    # self.keys.send('SetSpeed100')
                    sleep(10)
                    self.keys.send('SetSpeed50')
                    self.nav_align(scr_reg)  # Compass Align
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
                self.keys.send('SetSpeed50')
                self.nav_align(scr_reg)  # realign with station

            # check for SC Disengage
            if self.sc_disengage_label_up(scr_reg):
                if self.sc_disengage_active(scr_reg):
                    self.ap_ckb('log+vce', 'Disengage Supercruise')
                    self.keys.send('HyperSuperCombination')
                    self.stop_sco_monitoring()
                    break

        # if no error, we must have gotten disengage
        if not align_failed and do_docking:
            sleep(4)  # wait for the journal to catch up

            # Check if this is a target we cannot dock at
            skip_docking = False
            if not self.jn.ship_state()['has_adv_dock_comp'] and not self.jn.ship_state()['has_std_dock_comp']:
                self.ap_ckb('log', "Skipping docking. No Docking Computer fitted.")
                skip_docking = True

            if not self.jn.ship_state()['SupercruiseDestinationDrop_type'] is None:
                if (self.jn.ship_state()['SupercruiseDestinationDrop_type'].startswith("$USS_Type")
                        # Bulk Cruisers
                        or "-class Cropper" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Hauler" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Reformatory" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Researcher" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Surveyor" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Traveller" in self.jn.ship_state()['SupercruiseDestinationDrop_type']
                        or "-class Tanker" in self.jn.ship_state()['SupercruiseDestinationDrop_type']):
                    self.ap_ckb('log', "Skipping docking. No docking privilege at MegaShips.")
                    skip_docking = True

            if not skip_docking:
                # go into docking sequence
                self.dock()
                self.ap_ckb('log+vce', "Docking complete, refueled, repaired and re-armed")
                self.update_ap_status("Docking Complete")
            else:
                self.keys.send('SetSpeedZero')
        else:
            self.vce.say("Exiting Supercruise, setting throttle to zero")
            self.keys.send('SetSpeedZero')  # make sure we don't continue to land
            self.ap_ckb('log', "Supercruise dropped, terminating SC Assist")

        self.ap_ckb('log+vce', "Supercruise Assist complete")

    def robigo_assist(self):
        self.robigo.loop(self)

    # Simply monitor for Shields down so we can boost away or our fighter got destroyed
    # and thus redeploy another one
    def afk_combat_loop(self):
        while True:
            if self.afk_combat.check_shields_up() == False:
                self.set_focus_elite_window()
                self.vce.say("Shields down, evading")
                self.afk_combat.evade()
                # after supercruise the menu is reset to top
                self.afk_combat.launch_fighter()  # at new location launch fighter
                break

            if self.afk_combat.check_fighter_destroyed() == True:
                self.set_focus_elite_window()
                self.vce.say("Fighter Destroyed, redeploying")
                self.afk_combat.launch_fighter()  # assuming two fighter bays

        self.vce.say("Terminating AFK Combat Assist")

    def dss_assist(self):
        while True:
            sleep(0.5)
            if self.jn.ship_state()['status'] == 'in_supercruise':
                cur_star_system = self.jn.ship_state()['cur_star_system']
                if cur_star_system != self._prev_star_system:
                    self.update_ap_status("DSS Scan")
                    self.ap_ckb('log', 'DSS Scan: '+cur_star_system)
                    self.set_focus_elite_window()
                    self.honk()
                    self._prev_star_system = cur_star_system
                    self.update_ap_status("Idle")

    def single_waypoint_assist(self):
        """ Travel to a system or station or both."""
        if self._single_waypoint_system == "" and self._single_waypoint_station == "":
            return False

        if self._single_waypoint_system != "":
            self.ap_ckb('log+vce', f"Targeting system {self._single_waypoint_system}.")
            # Select destination in galaxy map based on name
            res = self.galaxy_map.set_gal_map_destination_text(self, self._single_waypoint_system, self.jn.ship_state)
            if res:
                self.ap_ckb('log', f"System has been targeted.")
            else:
                self.ap_ckb('log+vce', f"Unable to target {self._single_waypoint_system} in Galaxy Map.")
                return False

            # Jump to destination
            res = self.jump_to_system(self.scrReg)
            if res is False:
                return False

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
        if enable == False and self.fsd_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.fsd_assist_enabled = enable

    def set_sc_assist(self, enable=True):
        if enable == False and self.sc_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.sc_assist_enabled = enable

    def set_waypoint_assist(self, enable=True):
        if enable == False and self.waypoint_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.waypoint_assist_enabled = enable

    def set_robigo_assist(self, enable=True):
        if enable == False and self.robigo_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.robigo_assist_enabled = enable

    def set_afk_combat_assist(self, enable=True):
        if enable == False and self.afk_combat_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.afk_combat_assist_enabled = enable

    def set_dss_assist(self, enable=True):
        if enable == False and self.dss_assist_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self.dss_assist_enabled = enable

    def set_single_waypoint_assist(self, system: str, station: str, enable=True):
        if enable == False and self.single_waypoint_enabled == True:
            self.ctype_async_raise(self.ap_thread, EDAP_Interrupt)
        self._single_waypoint_system = system
        self._single_waypoint_station = station
        self.single_waypoint_enabled = enable

    def set_cv_view(self, enable=True, x=0, y=0):
        self.cv_view = enable
        self.config['Enable_CV_View'] = int(self.cv_view)  # update the config
        self.update_config()  # save the config
        if enable == True:
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
        if enable == True:
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
        if self.vce != None:
            self.vce.quit()
        if self.overlay != None:
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

            if self.fsd_assist_enabled == True:
                logger.debug("Running fsd_assist")
                self.set_focus_elite_window()
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
                if fin == False:
                    self.ap_ckb("sc_start")

                # drop all out debug windows
                #cv2.destroyAllWindows()
                #cv2.waitKey(10)

            elif self.sc_assist_enabled == True:
                logger.debug("Running sc_assist")
                self.set_focus_elite_window()
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

            elif self.waypoint_assist_enabled == True:
                logger.debug("Running waypoint_assist")

                self.set_focus_elite_window()
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

            elif self.robigo_assist_enabled == True:
                logger.debug("Running robigo_assist")
                self.set_focus_elite_window()
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

            elif self.afk_combat_assist_enabled == True:
                self.update_overlay()
                try:
                    self.afk_combat_loop()
                except EDAP_Interrupt:
                    logger.debug("Stopping afk_combat")
                self.afk_combat_assist_enabled = False
                self.ap_ckb('afk_stop')
                self.update_overlay()

            elif self.dss_assist_enabled == True:
                logger.debug("Running dss_assist")
                self.set_focus_elite_window()
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

                        # Add ship to ship configs if missing
                        if ship is not None:
                            if ship not in self.ship_configs['Ship_Configs']:
                                self.ship_configs['Ship_Configs'][ship] = dict()

                            current_ship_cfg = self.ship_configs['Ship_Configs'][ship]
                            self.compass_scale = current_ship_cfg.get('compass_scale', self.scr.scaleX)
                            self.rollrate = current_ship_cfg.get('RollRate', 80.0)
                            self.pitchrate = current_ship_cfg.get('PitchRate', 33.0)
                            self.yawrate = current_ship_cfg.get('YawRate', 8.0)
                            self.sunpitchuptime = current_ship_cfg.get('SunPitchUp+Time', 0.0)

                            # Update GUI
                            self.ap_ckb('update_ship_cfg')

                        # Store ship for change detection
                        self.current_ship_type = ship

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

        self.set_focus_elite_window()
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

        self.set_focus_elite_window()
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

        self.set_focus_elite_window()
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

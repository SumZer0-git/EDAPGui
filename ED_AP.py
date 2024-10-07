from pickletools import read_unicodestring1
import traceback
from math import atan, degrees
import json
import random

import cv2
from PIL import Image
from pathlib import Path

from EDAP_data import *
from EDlogger import logger, logging
import Image_Templates
import Screen
import Screen_Regions
from EDWayPoint import *
from EDJournal import *
from EDKeys import *
from EDafk_combat import AFK_Combat
from ModulesInfoParser import ModulesInfoParser
from Overlay import *
from StatusParser import StatusParser
from Voice import *
from Robigo import *

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
            "Enable_CV_View": 0,  # Should CV View be enabled by default
            "ShipConfigFile": None  # Ship config to load on start
        }

        # used this to write the self.config table to the json file
        # self.write_config(self.config)

        cnf = self.read_config()
        # if we read it then point to it, otherwise use the default table above
        if cnf is not None:
            if len(cnf) != len(self.config):
                self.write_config(self.config)
            else:
                self.config = cnf
                logger.debug("read AP json:"+str(cnf))
                # Specific test since new entry
                if 'SunBrightThreshold' not in self.config:
                    self.config['SunBrightThreshold'] = 125
        else:
            self.write_config(self.config)

        # config the voice interface
        self.vce = Voice()
        self.vce.set_on()
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

        # Create instance of each of the needed Classes
        self.scr = Screen.Screen()
        self.templ = Image_Templates.Image_Templates(self.scr.scaleX, self.scr.scaleY)
        self.scrReg = Screen_Regions.Screen_Regions(self.scr, self.templ)
        self.jn = EDJournal()
        self.keys = EDKeys()
        self.afk_combat = AFK_Combat(self.keys, self.jn, self.vce)
        self.waypoint = EDWayPoint(self.jn.ship_state()['odyssey'])
        self.robigo = Robigo(self)
        self.modules_info = ModulesInfoParser()
        self.status = StatusParser()

        # rate as ship dependent.   Can be found on the outfitting page for the ship.  However, it looks like supercruise
        # has worse performance for these rates
        # see:  https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/
        #
        # If you find that you are overshoot in pitch or roll, need to adjust these numbers.
        # Algorithm will roll the vehicle for the nav point to be north or south and then pitch to get the nave point
        # to center
        self.yawrate   = 8.0
        self.rollrate  = 80.0
        self.pitchrate = 33.0
        self.sunpitchuptime = 0.0

        self.jump_cnt = 0
        self.total_dist_jumped = 0
        self.total_jumps = 0
        self.refuel_cnt = 0

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
        self.cv_view = False
        self.cv_view_x = 10
        self.cv_view_y = 10

        #start the engine thread
        self.terminate = False  # terminate used by the thread to exit its loop
        if doThread:
            self.ap_thread = kthread.KThread(target=self.engine_loop, name="EDAutopilot")
            self.ap_thread.start()

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

    # find the best scale value in the given range of scales with the passed in threshold
    #
    def calibrate_range(self, range_low, range_high, threshold):
        #print("--- new range ---")
        scale = 0
        max_pick = 0
        for i in range(range_low, range_high):
            self.scr.scaleX = float(i/100)
            self.scr.scaleY = self.scr.scaleX

            # must reload the templates with this scale value
            self.templ.reload_templates(self.scr.scaleX, self.scr.scaleY)

            # do image matching on the compass and the target
            compass_image, (minVal, maxVal, minLoc, maxLoc), match = self.scrReg.match_template_in_region('compass', 'compass')
            dst_image, (minVal1, maxVal1, minLoc1, maxLoc1), match = self.scrReg.match_template_in_region('target', 'target')

            border = 10  # border to prevent the box from interfering with future matches
            reg_compass_pos = self.scrReg.reg['compass']['rect']
            comp_width = self.scrReg.templates.template['compass']['width'] + border + border
            comp_height = self.scrReg.templates.template['compass']['height'] + border + border
            comp_left = reg_compass_pos[0] + maxLoc[0] - border
            comp_top = reg_compass_pos[1] + maxLoc[1] - border

            reg_target_pos = self.scrReg.reg['target']['rect']
            targ_width = self.scrReg.templates.template['target']['width'] + border + border
            targ_height = self.scrReg.templates.template['target']['height'] + border + border
            targ_left = reg_target_pos[0] + maxLoc1[0] - border
            targ_top = reg_target_pos[1] + maxLoc1[1] - border

            if maxVal > threshold and maxVal1 > threshold and maxVal > max_pick:
                # Draw box around compass
                self.overlay.overlay_rect(20, (comp_left, comp_top),(comp_left + comp_width, comp_top + comp_height), (0, 255, 0), 2)
                self.overlay.overlay_floating_text(20, f'Match: {maxVal:5.2f}', comp_left, comp_top - 25, (0, 255, 0))
                # Draw box around target
                self.overlay.overlay_rect(22, (targ_left, targ_top), (targ_left + targ_width, targ_top + targ_height), (0, 255, 0), 2)
                self.overlay.overlay_floating_text(22, f'Match: {maxVal1:5.2f}', targ_left, targ_top - 25, (0, 255, 0))
            else:
                # Draw box around compass
                self.overlay.overlay_rect(21, (comp_left, comp_top),(comp_left + comp_width, comp_top + comp_height), (255, 0, 0), 2)
                self.overlay.overlay_floating_text(21, f'Match: {maxVal:5.2f}', comp_left, comp_top - 25, (255, 0, 0))
                # Draw box around target
                self.overlay.overlay_rect(23, (targ_left, targ_top),  (targ_left + targ_width, targ_top + targ_height), (255, 0, 0), 2)
                self.overlay.overlay_floating_text(23, f'Match: {maxVal1:5.2f}', targ_left, targ_top - 25, (255, 0, 0))

            self.overlay.overlay_paint()

            #print("Looping i:"+str(i)+ ' scale:'+str(self.scr.scaleX)+ " maxVal:"+str(maxVal)+" maxVal1:"+str(maxVal1))

            # Show the bounding box           
            self.get_nav_offset(self.scrReg)
            self.get_destination_offset(self.scrReg)

            if maxVal > threshold and maxVal1 > threshold:
                #print("met criteria:"+f'{self.scr.scaleX:5.2f} '+str(threshold))
                if maxVal > max_pick:
                    max_pick = maxVal
                    scale = i
                    self.ap_ckb('log', 'Cal: Found match:' + f'{max_pick:5.2f}' + "% with scale:" + f'{self.scr.scaleX:5.2f}')

        return scale, max_pick

    # Routine to find the optimal scaling values for the tempalte images
    def calibrate(self):
        self.set_focus_elite_window()

        # Draw the target and compass regions on the screen
        for i, key in enumerate(self.scrReg.reg):
             if key == 'target' or key == 'compass':
                targ_region = self.scrReg.reg[key]
                self.overlay.overlay_rect(key, (targ_region['rect'][0], targ_region['rect'][1]),
                                (targ_region['rect'][2], targ_region['rect'][3]),(0, 0, 255), 2)
                self.overlay.overlay_floating_text(key, key, targ_region['rect'][0],
                                                   targ_region['rect'][1], (0, 0, 255))
        self.overlay.overlay_paint()

        range_low = 30
        range_high = 200
        match_level = 0.5
        scale_max = 0
        max_val = 0

        # loop through thresholds from 50 to 90% in 5% increments.  Find out which scale factor
        # meets the highest threshold value
        #        
        for i in range(50, 90, 5):
            threshold = float(i/100)
            scale, max_pick = self.calibrate_range(range_low, range_high, threshold)  # match from 50-> 100 by 5
            #print("i:"+str(i)+" scale:"+str(scale)+ " threshold:"+str(threshold))
            if scale != 0:
                scale_max = scale
                max_val = max_pick
                range_low = scale-2
                range_high = scale+2
                if range_high > 100:
                    range_high = 100
            else:
                break  # no match found with threshold

        if scale_max == 99:
            scale_max = 100

        # if we found a scaling factor that meets our criteria, then save it to the resolution.json file
        if max_val != 0:
            self.scr.scaleX = float(scale_max/100)
            self.scr.scaleY = self.scr.scaleX
            self.ap_ckb('log', 'Cal: Max best match:'+f'{max_val:5.2f}'+"% with scale:"+f'{self.scr.scaleX:5.2f}')
            self.scr.scales['Calibrated'] = [self.scr.scaleX, self.scr.scaleY]
            self.scr.write_config(data=None)  # None means the writer will use its own scales variable which we modified
        else:
            self.ap_ckb('log', 'Cal: Insufficient matching to meet reliability, max % match:'+str(max_val))

        # Wait, then clean up
        sleep(3)
        self.overlay.overlay_clear()
        self.overlay.overlay_paint()

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
        if (maxVal1 > 0.70 and maxLoc1[1] < 30):
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
            f.close
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
        while not self.status.wait_for_flag_off(FlagsFsdCooldown, timeout=2):
            self.keys.send('UseBoostJuice')

        # Cooldown over, get us out of here.
        self.keys.send('HyperSuperCombination', hold=0.001)

        # Wait for supercruise, keep boosting.
        while not self.status.wait_for_flag_on(FlagsSupercruise, timeout=2):
            self.keys.send('UseBoostJuice')

        # Update journal flag.
        self.jn.ship_state()['interdicted'] = False  # reset flag
        return True

    def get_nav_offset(self, scr_reg):
        """ Determine the x,y offset from center of the compass of the nav point. """

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

        # must be > x to have solid hit, otherwise we are facing wrong way (empty circle)
        if n_maxVal < scr_reg.navpoint_match_thresh:
            final_x = 0.0
            final_y = 0.0
            final_z = -1.0 # Behind
            result = {'x': final_x, 'y': final_y, 'z': final_z}
        else:
            final_x = ((n_pt[0]+((1/2)*wid))-((1/2)*c_wid))-5.5
            final_y = (((1/2)*c_hgt)-(n_pt[1]+((1/2)*hgt)))+6.5
            final_z = 1.0 # Ahead
            logger.debug(("maxVal="+str(n_maxVal)+" x:"+str(final_x)+" y:"+str(final_y)))
            result = {'x': final_x, 'y': final_y, 'z': final_z}

        if self.cv_view:
            icompass_image_d = cv2.cvtColor(icompass_image, cv2.COLOR_GRAY2RGB)
            self.draw_match_rect(icompass_image_d, pt, (pt[0]+c_wid, pt[1]+c_hgt), (0, 0, 255), 2)
            #cv2.rectangle(icompass_image_display, pt, (pt[0]+c_wid, pt[1]+c_hgt), (0, 0, 255), 2)
            #self.draw_match_rect(compass_image, n_pt, (n_pt[0] + wid, n_pt[1] + hgt), (255,255,255), 2)   
            self.draw_match_rect(icompass_image_d, (pt[0]+n_pt[0]-pad, pt[1]+n_pt[1]-pad), (pt[0]+n_pt[0]+wid-pad, pt[1]+n_pt[1]+hgt-pad), (0, 255, 0), 1)
            #cv2.rectangle(icompass_image_display, (pt[0]+n_pt[0]-pad, pt[1]+n_pt[1]-pad), (pt[0]+n_pt[0] + wid-pad, pt[1]+n_pt[1] + hgt-pad), (0, 0, 255), 2)

            #   dim = (int(destination_width/3), int(destination_height/3))

            #   img = cv2.resize(dst_image, dim, interpolation =cv2.INTER_AREA) 
            cv2.putText(icompass_image_d, f'Compass: {maxVal:5.2f} > {scr_reg.compass_match_thresh:5.2f}', (1, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(icompass_image_d, f'Nav Point: {n_maxVal:5.2f} > {scr_reg.navpoint_match_thresh:5.2f}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            #cv2.circle(icompass_image_display, (pt[0]+n_pt[0], pt[1]+n_pt[1]), 5, (0, 255, 0), 3)
            cv2.imshow('compass', icompass_image_d)
            #cv2.imshow('nav', navpt_image)
            cv2.moveWindow('compass', self.cv_view_x, self.cv_view_y)
            #cv2.moveWindow('nav', self.cv_view_x, self.cv_view_y) 
            cv2.waitKey(30)

        return result

    # Looks to see if the 'dashed' line of the target is present indicating the target is occluded by the planet
    #  return True if meets threshold 
    #
    def is_destination_occluded(self, scr_reg) -> bool:
        dst_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('target_occluded', 'target_occluded')

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
                cv2.putText(img, f'{maxVal:5.2f} > {scr_reg.target_occluded_thresh:5.2f}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow('occluded', img)
                cv2.moveWindow('occluded', self.cv_view_x, self.cv_view_y+650)
            except Exception as e:
                print("exception in getdest: "+str(e))
            cv2.waitKey(30)

        if maxVal > scr_reg.target_occluded_thresh:
            return True
        else:
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
                cv2.putText(img, f'{maxVal:5.2f} > {scr_reg.target_thresh:5.2f}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow('target', img)
                #cv2.imshow('tt', scr_reg.templates.template['target']['image'])
                cv2.moveWindow('target', self.cv_view_x+500, self.cv_view_y)
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

    # look for the "PRESS [J] TO DISENGAGE", if in this region then return true
    #
    def sc_disengage(self, scr_reg) -> bool:
        dis_image, (minVal, maxVal, minLoc, maxLoc), match = scr_reg.match_template_in_region('disengage', 'disengage')

        pt = maxLoc

        width = scr_reg.templates.template['disengage']['width']
        height = scr_reg.templates.template['disengage']['height']

        if self.cv_view:
            self.draw_match_rect(dis_image, pt, (pt[0] + width, pt[1] + height), (0,255,0), 2)
            cv2.putText(dis_image, f'{maxVal:5.2f} > {scr_reg.disengage_thresh}', (1, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.imshow('disengage', dis_image)
            cv2.moveWindow('disengage', self.cv_view_x-460,self.cv_view_y+575)
            cv2.waitKey(1)

        logger.debug("Disenage = "+str(maxVal))

        if (maxVal > scr_reg.disengage_thresh):
            self.vce.say("Disengaging Supercruise")
            return True
        else:
            return False

    # Performs menu action to undock from Station
    #  
    def undock(self):
        # Assume we are in Star Port Services                              
        # Go to interior panel which will update ModulesInfo.json if any modules have changed.
        self.keys.send('UIFocus', state=1)
        self.keys.send('UI_Right')
        self.keys.send('UIFocus', state=0)
        self.keys.send('UI_Back')

        # Now we are on initial menu, we go up to top (which is Refuel)
        self.keys.send('UI_Up', repeat=3)

        # down to Auto Undock and Select it...
        self.keys.send('UI_Down')
        self.keys.send('UI_Down')
        self.keys.send('UI_Select')
        self.keys.send('SetSpeedZero', repeat=2)

        # Performs left menu ops to request docking

    # Required that the left menu is on the "NAVIGATION" tab otherwise this doesn't work
    #
    def request_docking(self, toCONTACT):
        self.keys.send('UI_Back', repeat=10)
        self.keys.send('HeadLookReset')
        self.keys.send('UIFocus', state=1)
        self.keys.send('UI_Left')
        self.keys.send('UIFocus', state=0)
        sleep(0.5)

        # we start with the Left Panel having "NAVIGATION" highlighted, we then need to right
        # right twice to "CONTACTS".  Notice of a FSD run, the LEFT panel is reset to "NAVIGATION"
        # otherwise it is on the last tab you selected.  Thus must start AP with "NAVIGATION" selected
        if (toCONTACT == 1):
            self.keys.send('CycleNextPanel', hold=0.2)
            sleep(0.2)
            self.keys.send('CycleNextPanel', hold=0.2)

        # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # then go right, which will be "REQUEST DOCKING" and select it
        self.keys.send('UI_Up', hold=4)
        self.keys.send('UI_Right')
        self.keys.send('UI_Select')

        sleep(0.3)
        self.keys.send('UI_Back')
        self.keys.send('HeadLookReset')

    # Docking sequence.  Assumes in normal space, will get closer to the Station
    # then zero the velocity and execute menu commands to request docking, when granted
    # will wait a configurable time for dock.  Perform Refueling and Repair
    #
    def dock(self):
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
            raise Exception('Docking error')

        sleep(12)
        # At this point (of sleep()) we should be < 7.5km from the station.  Go 0 speed
        # if we get docking granted ED's docking computer will take over
        self.keys.send('SetSpeedZero', repeat=2)

        self.request_docking(1)
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
                self.request_docking(0)
                self.keys.send('SetSpeedZero', repeat=2)
                sleep(1.5)
                if self.jn.ship_state()['status'] == "dockinggranted":
                    granted = True
                    break
                if self.jn.ship_state()['status'] == "dockingdenied":
                    pass

        if not granted:
            self.ap_ckb('log', 'Docking denied: '+str(self.jn.ship_state()['no_dock_reason']))
            logger.warning('Did not get docking authorization, reason:'+str(self.jn.ship_state()['no_dock_reason']))
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
                    break

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
        sleep(self.sunpitchuptime)  # some ships heat up too much and need pitch up a little further
        self.keys.send('PitchUpButton', state=0)
        

    # we know x, y offset of the nav point from center, use arc tan to determine the angle, convert to degrees
    # we want the angle to the 90 (up) and 180 (down) axis 
    def x_angle(self, point=None):
        if not point:
            return None
        if point['x'] == 0:
            point['x'] = 0.1
        result = degrees(atan(abs(point['y'])/abs(point['x'])))

        return 90-result

    def nav_align(self, scr_reg):
        """ Use the compass to find the nav point position.  Will then perform rotation and pitching
        to put the nav point in the middle of the compass, i.e. target right in front of us """

        close = 2
        if not (self.jn.ship_state()['status'] == 'in_supercruise' or self.jn.ship_state()['status'] == 'in_space'):
            logger.error('align=err1')
            raise Exception('nav_align not in super or space')

        self.vce.say("Navigation Align")

        # get the x,y offset from center, or none, which means our point is behind us
        off = self.get_nav_offset(scr_reg)

        # check to see if we are already converged, if so return    
        if off['z'] > 0 and abs(off['x']) < close and abs(off['y']) < close:
            return

        # nav point must be behind us, pitch up until somewhat in front of us
        while off['z'] < 0:
            if off['y'] >= 0:
                self.pitchUp(90)
            if off['y'] < 0:
                self.pitchDown(90)
            off = self.get_nav_offset(scr_reg)

        # check if converged, unlikely at this point
        if off['z'] > 0 and abs(off['x']) < close and abs(off['y']) < close:
            return

        # try multiple times to get aligned.  If the sun is shining on console, this it will be hard to match
        # the vehicle should be positioned with the sun below us via the sun_avoid() routine after a jump
        for ii in range(self.config['NavAlignTries']):
            off = self.get_nav_offset(scr_reg)

            if off['z'] > 0 and abs(off['x']) < close and abs(off['y']) < close:
                break

            while off['z'] < 0:
                if off['y'] >= 0:
                    self.pitchUp(45)
                if off['y'] < 0:
                    self.pitchDown(45)
                off = self.get_nav_offset(scr_reg)

            # determine the angle and the hold time to keep the button pressed to roll that number of degrees
            ang = self.x_angle(off)%90
            htime = ang/self.rollrate

            logger.debug("Angle:"+str(ang)+" x: "+str(off['x'])+" rolltime:"+str(htime))

            # first roll to get the nav point at the vertical position
            if (abs(off['x']) > close):
                # top right quad, then roll right to get to 90 up
                if (off['x'] > 0 and off['y'] > 0):
                    self.keys.send('RollRightButton', hold=htime)
                    # bottom right quad, then roll left
                elif (off['x'] > 0 and off['y'] < 0):
                    self.keys.send('RollLeftButton', hold=htime)
                    # top left quad, then roll left
                elif (off['x'] < 0 and off['y'] > 0):
                    self.keys.send('RollLeftButton', hold=htime)
                    # bottom left quad, then roll right
                else:
                    self.keys.send('RollRightButton', hold=htime)
            else:
                #print("X is <= "+str(close))
                pass

            sleep(0.15)  # wait for image to stablize
            off = self.get_nav_offset(scr_reg)
            while off['z'] < 0:
                if off['y'] >= 0:
                    self.pitchUp(45)
                if off['y'] < 0:
                    self.pitchDown(45)
                off = self.get_nav_offset(scr_reg)

            # calc pitch time based on nav point location
            # this is assuming 40 offset is max displacement on the Y axis.  So get percentage we are offset
            #
            utime = (abs(off['y'])/40.)*(90./self.pitchrate)
            logger.debug("ptichtime:"+str(utime)+" x:"+str(off['x'])+" y:"+str(off['y']))

            if (abs(off['y']) > close):
                if (off['y'] < 0):
                    self.keys.send('PitchDownButton', hold=utime)
                else:
                    self.keys.send('PitchUpButton', hold=utime)
            else:
                #print("Y is <= "+str(close))
                pass
            sleep(.1)
            logger.debug("final x:"+str(off['x'])+" y:"+str(off['y']))

    def target_align(self, scr_reg):
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

        self.target_align(scr_reg)
        

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
            if self.is_destination_occluded(scr_reg) == True:
                self.reposition(scr_reg)
            sleep(0.1)

        # Could not be found, return
        if off == None:
            logger.debug("sc_target_align not finding target")
            self.ap_ckb('log', 'Target not found, terminating SC Assist')
            return False

        logger.debug("sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

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

            logger.debug("  sc_target_align x: "+str(off['x'])+" y:"+str(off['y']))

            if off['x'] > close:
                self.keys.send('YawRightButton', hold=hold_yaw)
            if off['x'] < -close:
                self.keys.send('YawLeftButton', hold=hold_yaw)
            if off['y'] > close:
                self.keys.send('PitchUpButton', hold=hold_pitch)
            if off['y'] < -close:
                self.keys.send('PitchDownButton', hold=hold_pitch)

            sleep(.02)  # time for image to catch up

            # this checks if suddenly the target show up behind the planete
            if self.is_destination_occluded(scr_reg) == True:
                self.reposition(scr_reg)

            new = self.get_destination_offset(scr_reg)
            if new:
                off = new

            # Check if target is outside the target region (behind us) and break loop
            if new == None:
                logger.debug("sc_target_align lost target")
                self.ap_ckb('log', 'Target lost, attempting re-alignment.')
                return False

        return True

    # Reposition is use when the target is obscured by a world
    #   We pitch 90 up for a bit, then down 90, this should make the target underneath us
    #   this is important because when we do nav_align() if it does not see the Nav Point
    #   in the compass (because it is a hollow circle), then it will pitch down, this will 
    #   bring the target into view quickly
    #
    def reposition(self, scr_reg):
        self.vce.say("Target obscured, repositioning")
        self.pitchUp(90)
        self.keys.send('SetSpeed100')
        sleep(15)
        self.pitchDown(90)
        sleep(5)
        self.nav_align(scr_reg)
        self.keys.send('SetSpeed50')

    # position() happens afer a refuel and performs
    #   - accelerate past sun
    #   - perform Discovery scan
    #   - perform fss (if enabled) 
    def position(self, scr_reg, did_refuel=True):
        logger.debug('position')
        add_time = 5

        self.vce.say("Maneuvering")

        self.keys.send('SetSpeed100')

        # Do the Discovery Scan (Honk)
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

        for i in range(self.config['JumpTries']):

            logger.debug('jump= try:'+str(i))
            if not (self.jn.ship_state()['status'] == 'in_supercruise' or self.jn.ship_state()['status'] == 'in_space'):
                logger.error('jump=err1')
                raise Exception('not ready to jump')
            sleep(0.5)
            logger.debug('jump= start fsd')
            
            self.keys.send('HyperSuperCombination', hold=1)
            sleep(16)

            if self.jn.ship_state()['status'] != 'starting_hyperspace':
                self.mnvr_to_target(scr_reg)  # attempt realign to target
            else:
                logger.debug('jump= in jump')
                while self.jn.ship_state()['status'] != 'in_supercruise':
                    sleep(1)
                logger.debug('jump= speed 0')
                self.jump_cnt = self.jump_cnt+1
                self.keys.send('SetSpeedZero', repeat=3)  # Let's be triply sure that we set speed to 0% :)
                sleep(1)  # wait 1 sec after jump to allow graphics to stablize and accept inputs
                logger.debug('jump=complete')
                return True

        logger.error('jump=err2')
        raise Exception("jump failure")

        # a set of convience routes to pitch, rotate by specified degress

    #
    def rotateLeft(self, deg):
        htime = deg/self.rollrate
        self.keys.send('RollLeftButton', hold=htime)

    def pitchDown(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchDownButton', htime)

    def pitchUp(self, deg):
        htime = deg/self.pitchrate
        self.keys.send('PitchUpButton', htime)

    def yawLeft(self, deg):
        htime = deg/self.yawrate
        self.keys.send('YawLeftButton', hold=htime)

        # check if refueling needed, ensure correct start type

    #
    def refuel(self, scr_reg):
        # Check if we have a fuel scoop
        has_fuel_scoop = self.modules_info.has_fuel_scoop()

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
        self.update_ap_status("Executing Undocking")
        self.undock()
        # need to wait until undock complete, that is when we are back in_space
        while self.jn.ship_state()['status'] != 'in_space':
            sleep(1)

        self.update_ap_status("Undock Complete, accelerating")
        # move away from station
        sleep(1.5)
        self.keys.send('SetSpeed100')
        sleep(1)
        self.keys.send('UseBoostJuice')
        sleep(13)  # get away from Station
        self.keys.send('SetSpeed50')

    def sc_engage(self):
        """ Engages supercruise, then returns us to 50% speed """
        self.keys.send('SetSpeed100')
        self.keys.send('Supercruise', hold=0.001)
        sleep(12)
        self.keys.send('SetSpeed50')

    # processes the waypoints, performing jumps and sc assist if going to a station
    # also can then perform trades if specific in the waypoints file
    #
    def waypoint_assist(self, scr_reg):
        self.waypoint.step = 0  #start at first waypoint
        docked_at_station = False

        self.ap_ckb('log', "Waypoint file: "+str(Path(self.waypoint.filename).name))

        self.jn.ship_state()['target'] = None  # clear last target

        # Set the Route for the waypoint
        dest = self.waypoint.waypoint_next(self, self.jn.ship_state)

        # if we are starting the waypoint docked at a station, we need to undock first
        if dest != "" and self.jn.ship_state()['status'] == 'in_station':
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()['status'] != 'in_supercruise':
            self.sc_engage()

        # keep looping while we have a destination defined
        while dest != "":
            self.ap_ckb('log', "Waypoint: "+dest)
            docked_at_station = False
            # Route sent...  FSD Assist to that destination
            reached_dest = self.fsd_assist(scr_reg)

            # If waypoint file has a Station Name associated then attempt targeting it
            if self.waypoint.is_station_targeted(dest) != None:

                self.update_ap_status("Targeting Station")
                self.waypoint.set_station_target(self, dest)

                # Successful targeting of Station, lets go to it
                if self.have_destination(scr_reg) == True:
                    self.ap_ckb('log', " - Station: "+self.waypoint.waypoints[dest]['DockWithStation'])
                    self.update_ap_status("SC to Station")
                    self.sc_assist(scr_reg)

                    #
                    # Successful dock, let do trade, if a seq exists
                    if self.jn.ship_state()['status'] == 'in_station':
                        self.waypoint.execute_trade(self, dest)
                        docked_at_station = True
                    else:
                        logger.warning("Waypoint: Did not dock with station in limbo")
                else:
                    self.ap_ckb('log', " - Could not target station: "+self.waypoint.waypoints[dest]['DockWithStation'])

                    # Mark this waypoint as complated
            self.waypoint.mark_waypoint_complete(dest)

            self.update_ap_status("Setting route to next waypoint")
            self.jn.ship_state()['target'] = None  # clear last target

            # set target to next waypoint and loop)
            dest = self.waypoint.waypoint_next(self, self.jn.ship_state)

            # if we have another waypoint and we're docked, then undock first before moving on
            if dest != "" and docked_at_station:
                self.waypoint_undock_seq()

                # Done with waypoints
        self.ap_ckb('log', "Waypoint Route Complete, total distance jumped: "+str(self.total_dist_jumped)+"LY")
        self.update_ap_status("Idle")

    def fsd_assist(self, scr_reg):
        """ FSD Route Assist. """

        logger.debug('self.jn.ship_state='+str(self.jn.ship_state()))

        starttime = time.time()
        starttime -= 20  # to account for first instance not doing positioning

        if self.jn.ship_state()['target']:
            # if we are starting the waypoint docked at a station, we need to undock first
            if self.jn.ship_state()['status'] == 'in_station':
                self.update_overlay()
                self.waypoint_undock_seq()

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
                
                # reset, upon next Jump the Journal will be updated again, unless last jump, so we need to clear this out
                self.jn.ship_state()['jumps_remains'] = 0

                self.update_overlay()

                avg_time_jump = (time.time()-starttime)/self.jump_cnt
                self.ap_ckb('jumpcount', "Dist: {:,.1f}".format(self.total_dist_jumped)+"ly"+
                            "  Jumps: {}of{}".format(self.jump_cnt, self.total_jumps)+"  @{}s/j".format(int(avg_time_jump))+
                            "  Fu#: "+str(self.refuel_cnt))

                refueled = self.refuel(scr_reg)

                self.update_ap_status("Maneuvering")

                self.position(scr_reg, refueled)

                if (self.jn.ship_state()['fuel_percent'] < self.config['FuelThreasholdAbortAP']):
                    self.ap_ckb('log', "AP Aborting, low fuel")
                    self.vce.say("AP Aborting, low fuel")
                    break

        sleep(2)  # wait until screen stabilizes from possible last positioning

        # if there is no destination defined, we are done
        if self.have_destination(scr_reg) == False:
            self.keys.send('SetSpeedZero')
            self.vce.say("Destination Reached, distance jumped:"+str(int(self.total_dist_jumped))+" lightyears")
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
        align_failed = False
        # see if we have a compass up, if so then we have a target
        if self.have_destination(scr_reg) == False:
            self.ap_ckb('log', "Quiting SC Assist - Compass not found. Rotate ship and try again.")
            logger.debug("Quiting sc_assist - compass not found")
            return

        # if we are starting the waypoint docked at a station, we need to undock first
        if self.jn.ship_state()['status'] == 'in_station':
            self.update_overlay()
            self.waypoint_undock_seq()

        # if we are in space but not in supercruise, get into supercruise
        if self.jn.ship_state()['status'] != 'in_supercruise':
            self.sc_engage()

        # Ensure we are 50%, don't want the loop of shame
        # Align Nav to target
        self.keys.send('SetSpeed50')
        self.nav_align(scr_reg)
        self.keys.send('SetSpeed50')

        self.jn.ship_state()['interdicted'] = False

        # Loop forever keeping tight align to target, until we get SC Disengage popup
        while True:
            sleep(0.05)
            if self.jn.ship_state()['status'] == 'in_supercruise':

                # Align and stay on target. If false is returned, we have lost the target behind us.
                if self.sc_target_align(scr_reg) == False:
                    # Continue ahead before aligning to prevent us circling the target
                    #self.keys.send('SetSpeed100')
                    sleep(10)
                    self.keys.send('SetSpeed50')
                    self.nav_align(scr_reg) # Align to target
            else:
                # if we dropped from SC, then we rammed into planet
                align_failed = True
                break

            # check if we are being interdicted
            interdicted = self.interdiction_check()
            if interdicted:
                # Continue journey after interdiction
                self.keys.send('SetSpeed50')
                self.nav_align(scr_reg)  # realign with station

            # check for SC Disengage
            if (self.sc_disengage(scr_reg) == True):
                #sleep(1)  # wait another sec
                self.keys.send('HyperSuperCombination')#, hold=0.001)
                break

        # if no error, we must have gotten disengage
        if align_failed == False and do_docking == True:
            sleep(4)  # wait for the journal to catch up
            self.update_ap_status("Initiating Docking Procedure")
            self.dock()  # go into docking sequence
            self.vce.say("Docking complete, Refueled")
            self.update_ap_status("Docking Complete")
        else:
            self.vce.say("Exiting Supercruise, setting throttle to zero")
            self.keys.send('SetSpeedZero')  # make sure we don't continue to land   
            self.ap_ckb('log', "Supercruise dropped, terminating SC Assist")

        self.vce.say("Supercruise Assist complete")

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
                    self.waypoint_assist(self.scrReg)
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

            self.update_overlay()
            cv2.waitKey(10)
            sleep(1)

#
# This main is for testing purposes.
#
def main():
    #handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    #if handle != None:
    #    win32gui.SetForegroundWindow(handle)  # put the window in foreground

    ed_ap = EDAutopilot(False)
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

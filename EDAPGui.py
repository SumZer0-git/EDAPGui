import sys
import os
import threading
import kthread
from datetime import datetime
from time import sleep
import cv2
import json
from pathlib import Path
import keyboard
import webbrowser
import requests


from PIL import Image, ImageGrab, ImageTk
import tkinter as tk
from tkinter import *
from tkinter import filedialog as fd
from tkinter import messagebox
from tkinter import ttk
from idlelib.tooltip import Hovertip

from Voice import *
from MousePt import MousePoint

from Image_Templates import *
from Screen import *
from Screen_Regions import *
from EDKeys import *
from EDJournal import *
from ED_AP import *

from EDlogger import logger


"""
File:EDAPGui.py    

Description:
User interface for controlling the ED Autopilot

Note:
Ideas taken from:  https://github.com/skai2/EDAutopilot
 
 HotKeys:
    Home - Start FSD Assist
    INS  - Start SC Assist
    PG UP - Start Robigo Assist
    End - Terminate any ongoing assist (FSD, SC, AFK)

Author: sumzer0@yahoo.com
"""

# ---------------------------------------------------------------------------
# must be updated with a new release so that the update check works properly!
# contains the names of the release.
EDAP_VERSION = "V1.1.0"
# depending on how release versions are best marked you could also change it to the release tag, see function check_update.
# ---------------------------------------------------------------------------

FORM_TYPE_CHECKBOX = 0
FORM_TYPE_SPINBOX = 1
FORM_TYPE_ENTRY = 2


def hyperlink_callback(url):
    webbrowser.open_new(url)


class APGui():
    def __init__(self, root):
        self.root = root
        root.title("EDAutopilot " + EDAP_VERSION)
        # root.overrideredirect(True)
        # root.geometry("400x550")
        # root.configure(bg="blue")
        root.protocol("WM_DELETE_WINDOW", self.close_window)
        root.resizable(False, False)

        self.tooltips = {
            'FSD Route Assist': "Will execute your route. \nAt each jump the sequence will perform some fuel scooping.",
            'Supercruise Assist': "Will keep your ship pointed to target, \nyou target can only be a station for the autodocking to work.",
            'Waypoint Assist': "When selected, will prompt for the waypoint file. \nThe waypoint file contains System names that \nwill be entered into Galaxy Map and route plotted.",
            'Robigo Assist': "",
            'ELW Scanner': "Will perform FSS scans while FSD Assist is traveling between stars. \nIf the FSS shows a signal in the region of Earth, \nWater or Ammonia type worlds, it will announce that discovery.",
            'AFK Combat Assist': "Used with a AFK Combat ship in a Rez Zone.",
            'RollRate': "Roll rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'PitchRate': "Pitch (up/down) rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'YawRate': "Yaw rate (rudder) your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'SunPitchUp+Time': "This field are for ship that tend to overheat. \nProviding 1-2 more seconds of Pitch up when avoiding the Sun \nwill overcome this problem.",
            'Sun Bright Threshold': "The low level for brightness detection, \nrange 0-255, want to mask out darker items",
            'Nav Align Tries': "How many attempts the ap should make at alignment.",
            'Jump Tries': "How many attempts the ap should make to jump.",
            'Wait For Autodock': "After docking granted, \nwait this amount of time for us to get docked with autodocking",
            'Start FSD': "Button to start FSD route assist.",
            'Start SC': "Button to start Supercruise assist.",
            'Start Robigo': "Button to start Robigo assist.",
            'Stop All': "Button to stop all assists.",
            'Refuel Threshold': "If fuel level get below this level, \nit will attempt refuel.",
            'Scoop Timeout': "Number of second to wait for full tank, \nmight mean we are not scooping well or got a small scooper",
            'Fuel Threshold Abort': "Level at which AP will terminate, \nbecause we are not scooping well.",
            'X Offset': "Offset left the screen to start place overlay text.",
            'Y Offset': "Offset down the screen to start place overlay text.",
            'Font Size': "Font size of the overlay.",
            'Ship Config Button': "Read in a file with roll, pitch, yaw values for a ship.",
            'Calibrate': "Will iterate through a set of scaling values \ngetting the best match for your system. \nSee HOWTO-Calibrate.md",
            'Waypoint List Button': "Read in a file with with your Waypoints.",
            'Cap Mouse XY': "This will provide the StationCoord value of the Station in the SystemMap. \nSelecting this button and then clicking on the Station in the SystemMap \nwill return the x,y value that can be pasted in the waypoints file",
            'Reset Waypoint List': "Reset your waypoint list, \nthe waypoint assist will start again at the first point in the list."
        }

        self.ed_ap = EDAutopilot(cb=self.callback)
        self.ed_ap.robigo.set_single_loop(self.ed_ap.config['Robigo_Single_Loop'])

        self.mouse = MousePoint()

        self.checkboxvar = {}
        self.radiobuttonvar = {}
        self.entries = {}
        self.lab_ck = {}
        self.single_waypoint_system = StringVar()
        self.single_waypoint_station = StringVar()
        self.TCE_Destination_Filepath = StringVar()

        self.FSD_A_running = False
        self.SC_A_running = False
        self.WP_A_running = False
        self.RO_A_running = False
        self.SWP_A_running = False

        self.cv_view = False

        self.TCE_Destination_Filepath.set(self.ed_ap.config['TCEDestinationFilepath'])

        self.msgList = self.gui_gen(root)

        self.checkboxvar['Enable Randomness'].set(self.ed_ap.config['EnableRandomness'])
        self.checkboxvar['Activate Elite for each key'].set(self.ed_ap.config['ActivateEliteEachKey'])
        self.checkboxvar['Enable Overlay'].set(self.ed_ap.config['OverlayTextEnable'])
        self.checkboxvar['Enable Voice'].set(self.ed_ap.config['VoiceEnable'])

        self.radiobuttonvar['dss_button'].set(self.ed_ap.config['DSSButton'])

        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['autopilot']['Sun Bright Threshold'].delete(0, END)
        self.entries['autopilot']['Nav Align Tries'].delete(0, END)
        self.entries['autopilot']['Jump Tries'].delete(0, END)
        self.entries['autopilot']['Wait For Autodock'].delete(0, END)

        self.entries['refuel']['Refuel Threshold'].delete(0, END)
        self.entries['refuel']['Scoop Timeout'].delete(0, END)
        self.entries['refuel']['Fuel Threshold Abort'].delete(0, END)

        self.entries['overlay']['X Offset'].delete(0, END)
        self.entries['overlay']['Y Offset'].delete(0, END)
        self.entries['overlay']['Font Size'].delete(0, END)

        self.entries['buttons']['Start FSD'].delete(0, END)
        self.entries['buttons']['Start SC'].delete(0, END)
        self.entries['buttons']['Start Robigo'].delete(0, END)
        self.entries['buttons']['Stop All'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, float(self.ed_ap.pitchrate))
        self.entries['ship']['RollRate'].insert(0, float(self.ed_ap.rollrate))
        self.entries['ship']['YawRate'].insert(0, float(self.ed_ap.yawrate))
        self.entries['ship']['SunPitchUp+Time'].insert(0, float(self.ed_ap.sunpitchuptime))

        self.entries['autopilot']['Sun Bright Threshold'].insert(0, int(self.ed_ap.config['SunBrightThreshold']))
        self.entries['autopilot']['Nav Align Tries'].insert(0, int(self.ed_ap.config['NavAlignTries']))
        self.entries['autopilot']['Jump Tries'].insert(0, int(self.ed_ap.config['JumpTries']))
        self.entries['autopilot']['Wait For Autodock'].insert(0, int(self.ed_ap.config['WaitForAutoDockTimer']))
        self.entries['refuel']['Refuel Threshold'].insert(0, int(self.ed_ap.config['RefuelThreshold']))
        self.entries['refuel']['Scoop Timeout'].insert(0, int(self.ed_ap.config['FuelScoopTimeOut']))
        self.entries['refuel']['Fuel Threshold Abort'].insert(0, int(self.ed_ap.config['FuelThreasholdAbortAP']))
        self.entries['overlay']['X Offset'].insert(0, int(self.ed_ap.config['OverlayTextXOffset']))
        self.entries['overlay']['Y Offset'].insert(0, int(self.ed_ap.config['OverlayTextYOffset']))
        self.entries['overlay']['Font Size'].insert(0, int(self.ed_ap.config['OverlayTextFontSize']))

        self.entries['buttons']['Start FSD'].insert(0, str(self.ed_ap.config['HotKey_StartFSD']))
        self.entries['buttons']['Start SC'].insert(0, str(self.ed_ap.config['HotKey_StartSC']))
        self.entries['buttons']['Start Robigo'].insert(0, str(self.ed_ap.config['HotKey_StartRobigo']))
        self.entries['buttons']['Stop All'].insert(0, str(self.ed_ap.config['HotKey_StopAllAssists']))

        if self.ed_ap.config['LogDEBUG']:
            self.radiobuttonvar['debug_mode'].set("Debug")
        elif self.ed_ap.config['LogINFO']:
            self.radiobuttonvar['debug_mode'].set("Info")
        else:
            self.radiobuttonvar['debug_mode'].set("Error")

        # global trap for these keys, the 'end' key will stop any current AP action
        # the 'home' key will start the FSD Assist.  May want another to start SC Assist

        keyboard.add_hotkey(self.ed_ap.config['HotKey_StopAllAssists'], self.stop_all_assists)
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartFSD'], self.callback, args=('fsd_start', None))
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartSC'],  self.callback, args=('sc_start',  None))
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartRobigo'],  self.callback, args=('robigo_start',  None))

        # check for updates
        self.check_updates()

        self.ed_ap.gui_loaded = True

    # callback from the EDAP, to configure GUI items
    def callback(self, msg, body=None):
        if msg == 'log':
            self.log_msg(body)
        elif msg == 'log+vce':
            self.log_msg(body)
            self.ed_ap.vce.say(body)
        elif msg == 'statusline':
            self.update_statusline(body)
        elif msg == 'fsd_stop':
            logger.debug("Detected 'fsd_stop' callback msg")
            self.checkboxvar['FSD Route Assist'].set(0)
            self.check_cb('FSD Route Assist')
        elif msg == 'fsd_start':
            self.checkboxvar['FSD Route Assist'].set(1)
            self.check_cb('FSD Route Assist')
        elif msg == 'sc_stop':
            logger.debug("Detected 'sc_stop' callback msg")
            self.checkboxvar['Supercruise Assist'].set(0)
            self.check_cb('Supercruise Assist')
        elif msg == 'sc_start':
            self.checkboxvar['Supercruise Assist'].set(1)
            self.check_cb('Supercruise Assist')
        elif msg == 'waypoint_stop':
            logger.debug("Detected 'waypoint_stop' callback msg")
            self.checkboxvar['Waypoint Assist'].set(0)
            self.check_cb('Waypoint Assist')
        elif msg == 'robigo_stop':
            logger.debug("Detected 'robigo_stop' callback msg")
            self.checkboxvar['Robigo Assist'].set(0)
            self.check_cb('Robigo Assist')
        elif msg == 'robigo_start':
            self.checkboxvar['Robigo Assist'].set(1)
            self.check_cb('Robigo Assist')
        elif msg == 'afk_stop':
            logger.debug("Detected 'afk_stop' callback msg")
            self.checkboxvar['AFK Combat Assist'].set(0)
            self.check_cb('AFK Combat Assist')
        elif msg == 'single_waypoint_stop':
            logger.debug("Detected 'single_waypoint_stop' callback msg")
            self.checkboxvar['Single Waypoint Assist'].set(0)
            self.check_cb('Single Waypoint Assist')

        elif msg == 'stop_all_assists':
            logger.debug("Detected 'stop_all_assists' callback msg")

            self.checkboxvar['FSD Route Assist'].set(0)
            self.check_cb('FSD Route Assist')

            self.checkboxvar['Supercruise Assist'].set(0)
            self.check_cb('Supercruise Assist')

            self.checkboxvar['Waypoint Assist'].set(0)
            self.check_cb('Waypoint Assist')

            self.checkboxvar['Robigo Assist'].set(0)
            self.check_cb('Robigo Assist')

            self.checkboxvar['AFK Combat Assist'].set(0)
            self.check_cb('AFK Combat Assist')

            self.checkboxvar['Single Waypoint Assist'].set(0)
            self.check_cb('Single Waypoint Assist')

        elif msg == 'jumpcount':
            self.update_jumpcount(body)
        elif msg == 'update_ship_cfg':
            self.update_ship_cfg()

    def update_ship_cfg(self):
        # load up the display with what we read from ED_AP for the current ship
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, self.ed_ap.pitchrate)
        self.entries['ship']['RollRate'].insert(0, self.ed_ap.rollrate)
        self.entries['ship']['YawRate'].insert(0, self.ed_ap.yawrate)
        self.entries['ship']['SunPitchUp+Time'].insert(0, self.ed_ap.sunpitchuptime)

    def calibrate_callback(self):
        self.ed_ap.calibrate()

    def calibrate_compass_callback(self):
        self.ed_ap.calibrate_compass()

    def mouse_coord_callback(self):
        ans = messagebox.askyesno('Mouse XY', 'Select OK\nYour next Mouse click should be on the Station')

        x, y = self.mouse.get_location()

        # can we auto paste into clipboard?
        xy_str = '[' + str(x) + ',' + str(y) + ']'
        self.root.clipboard_clear()
        self.root.clipboard_append(xy_str)
        self.root.update()  # it stays on the clipboard
        messagebox.showinfo('Mouse XY', 'Values: ' + xy_str + '\n has been place in your clipboard')

    def quit(self):
        logger.debug("Entered: quit")
        self.close_window()

    def close_window(self):
        logger.debug("Entered: close_window")
        self.stop_fsd()
        self.stop_sc()
        self.ed_ap.quit()
        sleep(0.1)
        self.root.destroy()

    # this routine is to stop any current autopilot activity
    def stop_all_assists(self):
        logger.debug("Entered: stop_all_assists")
        self.callback('stop_all_assists')

    def start_fsd(self):
        logger.debug("Entered: start_fsd")
        self.ed_ap.set_fsd_assist(True)
        self.FSD_A_running = True
        self.log_msg("FSD Route Assist start")
        self.ed_ap.vce.say("FSD Route Assist On")

    def stop_fsd(self):
        logger.debug("Entered: stop_fsd")
        self.ed_ap.set_fsd_assist(False)
        self.FSD_A_running = False
        self.log_msg("FSD Route Assist stop")
        self.ed_ap.vce.say("FSD Route Assist Off")
        self.update_statusline("Idle")

    def start_sc(self):
        logger.debug("Entered: start_sc")
        self.ed_ap.set_sc_assist(True)
        self.SC_A_running = True
        self.log_msg("SC Assist start")
        self.ed_ap.vce.say("Supercruise Assist On")

    def stop_sc(self):
        logger.debug("Entered: stop_sc")
        self.ed_ap.set_sc_assist(False)
        self.SC_A_running = False
        self.log_msg("SC Assist stop")
        self.ed_ap.vce.say("Supercruise Assist Off")
        self.update_statusline("Idle")

    def start_waypoint(self):
        logger.debug("Entered: start_waypoint")
        self.ed_ap.set_waypoint_assist(True)
        self.WP_A_running = True
        self.log_msg("Waypoint Assist start")
        self.ed_ap.vce.say("Waypoint Assist On")

    def stop_waypoint(self):
        logger.debug("Entered: stop_waypoint")
        self.ed_ap.set_waypoint_assist(False)
        self.WP_A_running = False
        self.log_msg("Waypoint Assist stop")
        self.ed_ap.vce.say("Waypoint Assist Off")
        self.update_statusline("Idle")

    def start_robigo(self):
        logger.debug("Entered: start_robigo")
        self.ed_ap.set_robigo_assist(True)
        self.RO_A_running = True
        self.log_msg("Robigo Assist start")
        self.ed_ap.vce.say("Robigo Assist On")

    def stop_robigo(self):
        logger.debug("Entered: stop_robigo")
        self.ed_ap.set_robigo_assist(False)
        self.RO_A_running = False
        self.log_msg("Robigo Assist stop")
        self.ed_ap.vce.say("Robigo Assist Off")
        self.update_statusline("Idle")

    def start_single_waypoint_assist(self):
        """ The debug command to go to a system or station or both."""
        logger.debug("Entered: start_single_waypoint_assist")
        system = self.single_waypoint_system.get()
        station = self.single_waypoint_station.get()

        if system != "" or station != "":
            self.ed_ap.set_single_waypoint_assist(system, station, True)
            self.SWP_A_running = True
            self.log_msg("Single Waypoint Assist start")
            self.ed_ap.vce.say("Single Waypoint Assist On")

    def stop_single_waypoint_assist(self):
        """ The debug command to go to a system or station or both."""
        logger.debug("Entered: stop_single_waypoint_assist")
        self.ed_ap.set_single_waypoint_assist("", "", False)
        self.SWP_A_running = False
        self.log_msg("Single Waypoint Assist stop")
        self.ed_ap.vce.say("Single Waypoint Assist Off")
        self.update_statusline("Idle")

    def about(self):
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui")

    def check_updates(self):
        response = requests.get("https://api.github.com/repos/SumZer0-git/EDAPGui/releases/latest")
        if EDAP_VERSION != response.json()["name"]:
            mb = messagebox.askokcancel("Update Check", "A new release version is available. Download now?")
            if mb == True:
                webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/releases/latest")

    def open_changelog(self):
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/blob/main/ChangeLog.md")

    def open_discord(self):
        webbrowser.open_new("https://discord.gg/HCgkfSc")

    def open_logfile(self):
        os.startfile('autopilot.log')

    def log_msg(self, msg):
        self.msgList.insert(END, datetime.now().strftime("%H:%M:%S: ") + msg)
        self.msgList.yview(END)
        logger.info(f"Log Msg: {msg}")

    def set_statusbar(self, txt):
        self.statusbar.configure(text=txt)

    def update_jumpcount(self, txt):
        self.jumpcount.configure(text=txt)

    def update_statusline(self, txt):
        self.status.configure(text="Status: " + txt)
        self.log_msg(f"Status update: {txt}")

    def ship_tst_pitch(self):
        self.ed_ap.ship_tst_pitch()

    def ship_tst_roll(self):
        self.ed_ap.ship_tst_roll()

    def ship_tst_yaw(self):
        self.ed_ap.ship_tst_yaw()

    def open_ship_file(self, filename=None):
        # if a filename was not provided, then prompt user for one
        if not filename:
            filetypes = (
                ('json files', '*.json'),
                ('All files', '*.*')
            )

            filename = fd.askopenfilename(
                title='Open a file',
                initialdir='./ships/',
                filetypes=filetypes)

        if not filename:
            return

        with open(filename, 'r') as json_file:
            f_details = json.load(json_file)

        # load up the display with what we read, the pass it along to AP
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, f_details['pitchrate'])
        self.entries['ship']['RollRate'].insert(0, f_details['rollrate'])
        self.entries['ship']['YawRate'].insert(0, f_details['yawrate'])
        self.entries['ship']['SunPitchUp+Time'].insert(0, f_details['SunPitchUp+Time'])

        self.ed_ap.rollrate = float(f_details['rollrate'])
        self.ed_ap.pitchrate = float(f_details['pitchrate'])
        self.ed_ap.yawrate = float(f_details['yawrate'])
        self.ed_ap.sunpitchuptime = float(f_details['SunPitchUp+Time'])

        self.ship_filelabel.set("loaded: " + Path(filename).name)
        self.ed_ap.update_config()

    def open_wp_file(self):
        filetypes = (
            ('json files', '*.json'),
            ('All files', '*.*')
        )
        filename = fd.askopenfilename(title="Waypoint File", initialdir='./waypoints/', filetypes=filetypes)
        if filename != "":
            self.ed_ap.waypoint.load_waypoint_file(filename)
            self.wp_filelabel.set("loaded: " + Path(filename).name)

    def reset_wp_file(self):
        if self.WP_A_running != True:
            mb = messagebox.askokcancel("Waypoint List Reset", "After resetting the Waypoint List, the Waypoint Assist will start again from the first point in the list at the next start.")
            if mb == True:
                self.ed_ap.waypoint.mark_all_waypoints_not_complete()
        else:
            mb = messagebox.showerror("Waypoint List Error", "Waypoint Assist must be disabled before you can reset the list.")

    def save_settings(self):
        self.entry_update()
        self.ed_ap.update_config()
        self.ed_ap.update_ship_configs()

    def load_tce_dest(self):
        filename = self.ed_ap.config['TCEDestinationFilepath']
        if os.path.exists(filename):
            with open(filename, 'r') as json_file:
                f_details = json.load(json_file)

            self.single_waypoint_system.set(f_details['StarSystem'])
            self.single_waypoint_station.set(f_details['Station'])

    # new data was added to a field, re-read them all for simple logic
    def entry_update(self, event=''):
        try:
            self.ed_ap.pitchrate = float(self.entries['ship']['PitchRate'].get())
            self.ed_ap.rollrate = float(self.entries['ship']['RollRate'].get())
            self.ed_ap.yawrate = float(self.entries['ship']['YawRate'].get())
            self.ed_ap.sunpitchuptime = float(self.entries['ship']['SunPitchUp+Time'].get())

            self.ed_ap.config['SunBrightThreshold'] = int(self.entries['autopilot']['Sun Bright Threshold'].get())
            self.ed_ap.config['NavAlignTries'] = int(self.entries['autopilot']['Nav Align Tries'].get())
            self.ed_ap.config['JumpTries'] = int(self.entries['autopilot']['Jump Tries'].get())
            self.ed_ap.config['WaitForAutoDockTimer'] = int(self.entries['autopilot']['Wait For Autodock'].get())
            self.ed_ap.config['RefuelThreshold'] = int(self.entries['refuel']['Refuel Threshold'].get())
            self.ed_ap.config['FuelScoopTimeOut'] = int(self.entries['refuel']['Scoop Timeout'].get())
            self.ed_ap.config['FuelThreasholdAbortAP'] = int(self.entries['refuel']['Fuel Threshold Abort'].get())
            self.ed_ap.config['OverlayTextXOffset'] = int(self.entries['overlay']['X Offset'].get())
            self.ed_ap.config['OverlayTextYOffset'] = int(self.entries['overlay']['Y Offset'].get())
            self.ed_ap.config['OverlayTextFontSize'] = int(self.entries['overlay']['Font Size'].get())
            self.ed_ap.config['HotKey_StartFSD'] = str(self.entries['buttons']['Start FSD'].get())
            self.ed_ap.config['HotKey_StartSC'] = str(self.entries['buttons']['Start SC'].get())
            self.ed_ap.config['HotKey_StartRobigo'] = str(self.entries['buttons']['Start Robigo'].get())
            self.ed_ap.config['HotKey_StopAllAssists'] = str(self.entries['buttons']['Stop All'].get())
            self.ed_ap.config['VoiceEnable'] = self.checkboxvar['Enable Voice'].get()
            self.ed_ap.config['TCEDestinationFilepath'] = str(self.TCE_Destination_Filepath.get())
        except:
            messagebox.showinfo("Exception", "Invalid float entered")

    # ckbox.state:(ACTIVE | DISABLED)

    # ('FSD Route Assist', 'Supercruise Assist', 'Enable Voice', 'Enable CV View')
    def check_cb(self, field):
        # print("got event:",  checkboxvar['FSD Route Assist'].get(), " ", str(FSD_A_running))
        if field == 'FSD Route Assist':
            if self.checkboxvar['FSD Route Assist'].get() == 1 and self.FSD_A_running == False:
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.start_fsd()

            elif self.checkboxvar['FSD Route Assist'].get() == 0 and self.FSD_A_running == True:
                self.stop_fsd()
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')

        if field == 'Supercruise Assist':
            if self.checkboxvar['Supercruise Assist'].get() == 1 and self.SC_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.start_sc()

            elif self.checkboxvar['Supercruise Assist'].get() == 0 and self.SC_A_running == True:
                self.stop_sc()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')

        if field == 'Waypoint Assist':
            if self.checkboxvar['Waypoint Assist'].get() == 1 and self.WP_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.start_waypoint()

            elif self.checkboxvar['Waypoint Assist'].get() == 0 and self.WP_A_running == True:
                self.stop_waypoint()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')

        if field == 'Robigo Assist':
            if self.checkboxvar['Robigo Assist'].get() == 1 and self.RO_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.start_robigo()

            elif self.checkboxvar['Robigo Assist'].get() == 0 and self.RO_A_running == True:
                self.stop_robigo()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')

        if field == 'AFK Combat Assist':
            if self.checkboxvar['AFK Combat Assist'].get() == 1:
                self.ed_ap.set_afk_combat_assist(True)
                self.log_msg("AFK Combat Assist start")
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')

            elif self.checkboxvar['AFK Combat Assist'].get() == 0:
                self.ed_ap.set_afk_combat_assist(False)
                self.log_msg("AFK Combat Assist stop")
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')

        if self.checkboxvar['Enable Randomness'].get():
            self.ed_ap.set_randomness(True)
        else:
            self.ed_ap.set_randomness(False)

        if self.checkboxvar['Activate Elite for each key'].get():
            self.ed_ap.set_activate_elite_eachkey(True)
            self.ed_ap.keys.activate_window=True
        else:
            self.ed_ap.set_activate_elite_eachkey(False)
            self.ed_ap.keys.activate_window = False

        if self.checkboxvar['Enable Overlay'].get():
            self.ed_ap.set_overlay(True)
        else:
            self.ed_ap.set_overlay(False)

        if self.checkboxvar['Enable Voice'].get():
            self.ed_ap.set_voice(True)
        else:
            self.ed_ap.set_voice(False)

        if self.checkboxvar['ELW Scanner'].get():
            self.ed_ap.set_fss_scan(True)
        else:
            self.ed_ap.set_fss_scan(False)

        if self.checkboxvar['Enable CV View'].get() == 1:
            self.cv_view = True
            x = self.root.winfo_x() + self.root.winfo_width() + 4
            y = self.root.winfo_y()
            self.ed_ap.set_cv_view(True, x, y)
        else:
            self.cv_view = False
            self.ed_ap.set_cv_view(False)

        self.ed_ap.config['DSSButton'] = self.radiobuttonvar['dss_button'].get()

        if self.radiobuttonvar['debug_mode'].get() == "Error":
            self.ed_ap.set_log_error(True)
        elif self.radiobuttonvar['debug_mode'].get() == "Debug":
            self.ed_ap.set_log_debug(True)
        elif self.radiobuttonvar['debug_mode'].get() == "Info":
            self.ed_ap.set_log_info(True)

        if field == 'Single Waypoint Assist':
            if self.checkboxvar['Single Waypoint Assist'].get() == 1 and self.SWP_A_running == False:
                self.start_single_waypoint_assist()
            elif self.checkboxvar['Single Waypoint Assist'].get() == 0 and self.SWP_A_running == True:
                self.stop_single_waypoint_assist()

    def makeform(self, win, ftype, fields, r=0, inc=1, rfrom=0, rto=1000):
        entries = {}

        for field in fields:
            row = tk.Frame(win)
            row.grid(row=r, column=0, padx=2, pady=2, sticky=(N, S, E, W))
            r += 1

            if ftype == FORM_TYPE_CHECKBOX:
                self.checkboxvar[field] = IntVar()
                lab = Checkbutton(row, text=field, anchor='w', width=27, justify=LEFT, variable=self.checkboxvar[field], command=(lambda field=field: self.check_cb(field)))
                self.lab_ck[field] = lab
            else:
                lab = tk.Label(row, anchor='w', width=20, pady=3, text=field + ": ")
                if ftype == FORM_TYPE_SPINBOX:
                    ent = tk.Spinbox(row, width=10, from_=rfrom, to=rto, increment=inc)
                else:
                    ent = tk.Entry(row, width=10)
                ent.bind('<FocusOut>', self.entry_update)
                ent.insert(0, "0")

            lab.grid(row=0, column=0)
            lab = Hovertip(row, self.tooltips[field], hover_delay=1000)

            if ftype != FORM_TYPE_CHECKBOX:
                ent.grid(row=0, column=1)
                entries[field] = ent

        return entries

    def gui_gen(self, win):

        modes_check_fields = ('FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 'Robigo Assist', 'AFK Combat Assist')
        ship_entry_fields = ('RollRate', 'PitchRate', 'YawRate', 'SunPitchUp+Time')
        autopilot_entry_fields = ('Sun Bright Threshold', 'Nav Align Tries', 'Jump Tries', 'Wait For Autodock')
        buttons_entry_fields = ('Start FSD', 'Start SC', 'Start Robigo', 'Stop All')
        refuel_entry_fields = ('Refuel Threshold', 'Scoop Timeout', 'Fuel Threshold Abort')
        overlay_entry_fields = ('X Offset', 'Y Offset', 'Font Size')

        #
        # Define all the menus
        #
        menubar = Menu(win, background='#ff8000', foreground='black', activebackground='white', activeforeground='black')
        file = Menu(menubar, tearoff=0)
        file.add_command(label="Calibrate Target", command=self.calibrate_callback)
        file.add_command(label="Calibrate Compass", command=self.calibrate_compass_callback)
        self.checkboxvar['Enable CV View'] = IntVar()
        self.checkboxvar['Enable CV View'].set(int(self.ed_ap.config['Enable_CV_View']))  # set IntVar value to the one from config
        file.add_checkbutton(label='Enable CV View', onvalue=1, offvalue=0, variable=self.checkboxvar['Enable CV View'], command=(lambda field='Enable CV View': self.check_cb(field)))
        file.add_separator()
        file.add_command(label="Restart", command=self.restart_program)
        file.add_command(label="Exit", command=self.close_window)  # win.quit)
        menubar.add_cascade(label="File", menu=file)

        help = Menu(menubar, tearoff=0)
        help.add_command(label="Check for Updates", command=self.check_updates)
        help.add_command(label="View Changelog", command=self.open_changelog)
        help.add_separator()
        help.add_command(label="Join Discord", command=self.open_discord)
        help.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=help)

        win.config(menu=menubar)

        # notebook pages
        nb = ttk.Notebook(win)
        nb.grid()
        page0 = Frame(nb)
        page1 = Frame(nb)
        page2 = Frame(nb)
        nb.add(page0, text="Main")  # main page
        nb.add(page1, text="Settings")  # options page
        nb.add(page2, text="Debug/Test")  # debug/test page

        # main options block
        blk_main = tk.Frame(page0)
        blk_main.grid(row=0, column=0, padx=10, pady=5, sticky=(E, W))
        blk_main.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # ap mode checkboxes block
        blk_modes = LabelFrame(blk_main, text="MODE")
        blk_modes.grid(row=0, column=0, padx=2, pady=2, sticky=(N, S, E, W))
        self.makeform(blk_modes, FORM_TYPE_CHECKBOX, modes_check_fields)

        # ship values block
        blk_ship = LabelFrame(blk_main, text="SHIP")
        blk_ship.grid(row=0, column=1, padx=2, pady=2, sticky=(N, S, E, W))
        self.entries['ship'] = self.makeform(blk_ship, FORM_TYPE_SPINBOX, ship_entry_fields, 0, 0.5)
        btn_tst_roll = Button(blk_ship, text='Test Roll', command=self.ship_tst_roll)
        btn_tst_roll.grid(row=4, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))
        btn_tst_pitch = Button(blk_ship, text='Test Pitch', command=self.ship_tst_pitch)
        btn_tst_pitch.grid(row=5, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))
        btn_tst_yaw = Button(blk_ship, text='Test Yaw', command=self.ship_tst_yaw)
        btn_tst_yaw.grid(row=6, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        # profile load / info button in ship values block
        self.ship_filelabel = StringVar()
        self.ship_filelabel.set("<no config loaded>")
        btn_ship_file = Button(blk_ship, textvariable=self.ship_filelabel, command=self.open_ship_file)
        btn_ship_file.grid(row=8, column=0, padx=2, pady=2, sticky=(N, E, W))
        tip_ship_file = Hovertip(btn_ship_file, self.tooltips['Ship Config Button'], hover_delay=1000)

        # waypoints button block
        blk_wp_buttons = tk.LabelFrame(page0, text="Waypoints")
        blk_wp_buttons.grid(row=1, column=0, padx=10, pady=5, columnspan=2, sticky=(N, S, E, W))
        blk_wp_buttons.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        self.wp_filelabel = StringVar()
        self.wp_filelabel.set("<no list loaded>")
        btn_wp_file = Button(blk_wp_buttons, textvariable=self.wp_filelabel, command=self.open_wp_file)
        btn_wp_file.grid(row=0, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))
        tip_wp_file = Hovertip(btn_wp_file, self.tooltips['Waypoint List Button'], hover_delay=1000)

        btn_coord = Button(blk_wp_buttons, text='Cap Mouse X,Y', command=self.mouse_coord_callback)
        btn_coord.grid(row=1, column=0, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        tip_coord = Hovertip(btn_coord, self.tooltips['Cap Mouse XY'], hover_delay=1000)

        btn_reset = Button(blk_wp_buttons, text='Reset List', command=self.reset_wp_file)
        btn_reset.grid(row=1, column=1, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        tip_reset = Hovertip(btn_reset, self.tooltips['Reset Waypoint List'], hover_delay=1000)

        # log window
        log = LabelFrame(page0, text="LOG")
        log.grid(row=3, column=0, padx=12, pady=5, sticky=(N, S, E, W))
        scrollbar = Scrollbar(log)
        scrollbar.grid(row=0, column=1, sticky=(N, S))
        mylist = Listbox(log, width=72, height=10, yscrollcommand=scrollbar.set)
        mylist.grid(row=0, column=0)
        scrollbar.config(command=mylist.yview)

        # settings block
        blk_settings = tk.Frame(page1)
        blk_settings.grid(row=0, column=0, padx=10, pady=5, sticky=(E, W))
        blk_main.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # autopilot settings block
        blk_ap = LabelFrame(blk_settings, text="AUTOPILOT")
        blk_ap.grid(row=0, column=0, padx=2, pady=2, sticky=(N, S, E, W))
        self.entries['autopilot'] = self.makeform(blk_ap, FORM_TYPE_SPINBOX, autopilot_entry_fields)
        self.checkboxvar['Enable Randomness'] = BooleanVar()
        cb_random = Checkbutton(blk_ap, text='Enable Randomness', anchor='w', pady=3, justify=LEFT, onvalue=1, offvalue=0, variable=self.checkboxvar['Enable Randomness'], command=(lambda field='Enable Randomness': self.check_cb(field)))
        cb_random.grid(row=4, column=0, columnspan=2, sticky=(W))
        self.checkboxvar['Activate Elite for each key'] = BooleanVar()
        cb_random = Checkbutton(blk_ap, text='Activate Elite for each key', anchor='w', pady=3, justify=LEFT, onvalue=1, offvalue=0, variable=self.checkboxvar['Activate Elite for each key'], command=(lambda field='Activate Elite for each key': self.check_cb(field)))
        cb_random.grid(row=5, column=0, columnspan=2, sticky=(W))

        # buttons settings block
        blk_buttons = LabelFrame(blk_settings, text="BUTTONS")
        blk_buttons.grid(row=0, column=1, padx=2, pady=2, sticky=(N, S, E, W))
        blk_dss = Frame(blk_buttons)
        blk_dss.grid(row=0, column=0, columnspan=2, padx=0, pady=0, sticky=(N, S, E, W))
        lb_dss = Label(blk_dss, width=18, anchor='w', pady=3, text="DSS Button: ")
        lb_dss.grid(row=0, column=0, sticky=(W))
        self.radiobuttonvar['dss_button'] = StringVar()
        rb_dss_primary = Radiobutton(blk_dss, pady=3, text="Primary", variable=self.radiobuttonvar['dss_button'], value="Primary", command=(lambda field='dss_button': self.check_cb(field)))
        rb_dss_primary.grid(row=0, column=1, sticky=(W))
        rb_dss_secandary = Radiobutton(blk_dss, pady=3, text="Secondary", variable=self.radiobuttonvar['dss_button'], value="Secondary", command=(lambda field='dss_button': self.check_cb(field)))
        rb_dss_secandary.grid(row=1, column=1, sticky=(W))
        self.entries['buttons'] = self.makeform(blk_buttons, FORM_TYPE_ENTRY, buttons_entry_fields, 2)

        # refuel settings block
        blk_fuel = LabelFrame(blk_settings, text="FUEL")
        blk_fuel.grid(row=1, column=0, padx=2, pady=2, sticky=(N, S, E, W))
        self.entries['refuel'] = self.makeform(blk_fuel, FORM_TYPE_SPINBOX, refuel_entry_fields)

        # overlay settings block
        blk_overlay = LabelFrame(blk_settings, text="OVERLAY")
        blk_overlay.grid(row=1, column=1, padx=2, pady=2, sticky=(N, S, E, W))
        self.checkboxvar['Enable Overlay'] = BooleanVar()
        cb_enable = Checkbutton(blk_overlay, text='Enable (requires restart)', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Enable Overlay'], command=(lambda field='Enable Overlay': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky=(W))
        self.entries['overlay'] = self.makeform(blk_overlay, FORM_TYPE_SPINBOX, overlay_entry_fields, 1, 1.0, 0.0, 3000.0)

        # tts / voice settings block
        blk_voice = LabelFrame(blk_settings, text="VOICE")
        blk_voice.grid(row=2, column=0, padx=2, pady=2, sticky=(N, S, E, W))
        self.checkboxvar['Enable Voice'] = BooleanVar()
        cb_enable = Checkbutton(blk_voice, text='Enable', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Enable Voice'], command=(lambda field='Enable Voice': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky=(W))

        # Scanner settings block
        blk_voice = LabelFrame(blk_settings, text="ELW SCANNER")
        blk_voice.grid(row=2, column=1, padx=2, pady=2, sticky=(N, S, E, W))
        self.checkboxvar['ELW Scanner'] = BooleanVar()
        cb_enable = Checkbutton(blk_voice, text='Enable', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['ELW Scanner'], command=(lambda field='ELW Scanner': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky=(W))

        # settings button block
        blk_settings_buttons = tk.Frame(page1)
        blk_settings_buttons.grid(row=3, column=0, padx=10, pady=5, sticky=(N, S, E, W))
        blk_settings_buttons.columnconfigure([0, 1], weight=1, minsize=100)
        btn_save = Button(blk_settings_buttons, text='Save All Settings', command=self.save_settings)
        btn_save.grid(row=0, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        # debug block
        blk_debug = tk.Frame(page2)
        blk_debug.grid(row=0, column=0, padx=10, pady=5, sticky=(E, W))
        blk_debug.columnconfigure([0, 1], weight=1, minsize=100, uniform="group2")

        # debug settings block
        blk_debug_settings = LabelFrame(blk_debug, text="DEBUG")
        blk_debug_settings.grid(row=0, column=0, padx=2, pady=2, sticky=(N, S, E, W))
        self.radiobuttonvar['debug_mode'] = StringVar()
        rb_debug_debug = Radiobutton(blk_debug_settings, pady=3, text="Debug + Info + Errors", variable=self.radiobuttonvar['debug_mode'], value="Debug", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_debug.grid(row=0, column=1, columnspan=2, sticky=(W))
        rb_debug_info = Radiobutton(blk_debug_settings, pady=3, text="Info + Errors", variable=self.radiobuttonvar['debug_mode'], value="Info", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_info.grid(row=1, column=1, columnspan=2, sticky=(W))
        rb_debug_error = Radiobutton(blk_debug_settings, pady=3, text="Errors only (default)", variable=self.radiobuttonvar['debug_mode'], value="Error", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_error.grid(row=2, column=1, columnspan=2, sticky=(W))
        btn_open_logfile = Button(blk_debug_settings, text='Open Log File', command=self.open_logfile)
        btn_open_logfile.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        # debug settings block
        blk_single_waypoint_asst = LabelFrame(page2, text="Single Waypoint Assist")
        blk_single_waypoint_asst.grid(row=1, column=0, padx=10, pady=5, columnspan=2, sticky=(N, S, E, W))
        blk_single_waypoint_asst.columnconfigure(0, weight=1, minsize=10, uniform="group1")
        blk_single_waypoint_asst.columnconfigure(1, weight=3, minsize=10, uniform="group1")

        lbl_system = tk.Label(blk_single_waypoint_asst, text='System:')
        lbl_system.grid(row=0, column=0, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        txt_system = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_system)
        txt_system.grid(row=0, column=1, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        lbl_station = tk.Label(blk_single_waypoint_asst, text='Station:')
        lbl_station.grid(row=1, column=0, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        txt_station = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_station)
        txt_station.grid(row=1, column=1, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        self.checkboxvar['Single Waypoint Assist'] = BooleanVar()
        cb_single_waypoint = Checkbutton(blk_single_waypoint_asst, text='Single Waypoint Assist', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Single Waypoint Assist'], command=(lambda field='Single Waypoint Assist': self.check_cb(field)))
        cb_single_waypoint.grid(row=2, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        lbl_tce = tk.Label(blk_single_waypoint_asst, text='Trade Computer Extension (TCE)', fg="blue", cursor="hand2")
        lbl_tce.bind("<Button-1>", lambda e: hyperlink_callback("https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/"))
        lbl_tce.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))
        lbl_tce_dest = tk.Label(blk_single_waypoint_asst, text='TCE Dest json:')
        lbl_tce_dest.grid(row=4, column=0, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))
        txt_tce_dest = Entry(blk_single_waypoint_asst, textvariable=self.TCE_Destination_Filepath)
        txt_tce_dest.bind('<FocusOut>', self.entry_update)
        txt_tce_dest.grid(row=4, column=1, padx=2, pady=2, columnspan=1, sticky=(N, E, W, S))

        btn_load_tce = Button(blk_single_waypoint_asst, text='Load TCE Destination', command=self.load_tce_dest)
        btn_load_tce.grid(row=5, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        blk_debug_buttons = tk.Frame(page2)
        blk_debug_buttons.grid(row=3, column=0, padx=10, pady=5, columnspan=2, sticky=(N, S, E, W))
        blk_debug_buttons.columnconfigure([0, 1], weight=1, minsize=100)

        btn_save = Button(blk_debug_buttons, text='Save All Settings', command=self.save_settings)
        btn_save.grid(row=6, column=0, padx=2, pady=2, columnspan=2, sticky=(N, E, W, S))

        # Statusbar
        statusbar = Frame(win)
        statusbar.grid(row=4, column=0)
        self.status = tk.Label(win, text="Status: ", bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=29)
        self.jumpcount = tk.Label(statusbar, text="<info> ", bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=40)
        self.status.pack(in_=statusbar, side=LEFT, fill=BOTH, expand=True)
        self.jumpcount.pack(in_=statusbar, side=RIGHT, fill=Y, expand=False)

        return mylist

    def restart_program(self):
        logger.debug("Entered: restart_program")
        print("restart now")

        self.stop_fsd()
        self.stop_sc()
        self.ed_ap.quit()
        sleep(0.1)

        import sys
        print("argv was", sys.argv)
        print("sys.executable was", sys.executable)
        print("restart now")

        import os
        os.execv(sys.executable, ['python'] + sys.argv)

def main():
    #   handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    #   if handle != None:
    #       win32gui.SetForegroundWindow(handle)  # put the window in foreground

    root = tk.Tk()
    app = APGui(root)

    root.mainloop()


if __name__ == "__main__":
    main()

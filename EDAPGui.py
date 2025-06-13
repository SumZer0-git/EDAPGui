import queue
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
from tkinter import (
    BooleanVar, Button, Checkbutton, Entry, Frame, IntVar, Label, LabelFrame, 
    Listbox, Menu, Radiobutton, Scrollbar, Spinbox, StringVar, Toplevel,
    ACTIVE, DISABLED, END, LEFT, SUNKEN, BOTH, Y, RIGHT
)
from tkinter import filedialog as fd
from tkinter import messagebox
from tkinter import ttk
from idlelib.tooltip import Hovertip

from Voice import *
from MousePt import MousePoint

from Image_Templates import *
from file_utils import read_json_file
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
EDAP_VERSION = "V1.4.2"
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
            'DSS Assist': "When selected, will perform DSS scans while you are traveling between stars.",
            'Single Waypoint Assist': "",
            'ELW Scanner': "Will perform FSS scans while FSD Assist is traveling between stars. \nIf the FSS shows a signal in the region of Earth, \nWater or Ammonia type worlds, it will announce that discovery.",
            'AFK Combat Assist': "Used with a AFK Combat ship in a Rez Zone.",
            'RollRate': "Roll rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'PitchRate': "Pitch (up/down) rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'YawRate': "Yaw rate (rudder) your ship has in deg/sec. Higher the number the more maneuverable the ship.",
            'SunPitchUp+Time': "This field are for ship that tend to overheat. \nProviding 1-2 more seconds of Pitch up when avoiding the Sun \nwill overcome this problem.",
            'Sun Bright Threshold': "The low level for brightness detection, \nrange 0-255, want to mask out darker items",
            'Nav Align Tries': "How many attempts the ap should make at alignment.",
            'Jump Tries': "How many attempts the ap should make to jump.",
            'Docking Retries': "How many attempts to make to dock.",
            'Wait For Autodock': "After docking granted, \nwait this amount of time for us to get docked with autodocking",
            'Start FSD': "Hotkey to start FSD route assist. \nClick button to capture new hotkey. Supports combinations like Ctrl+F1.",
            'Start SC': "Hotkey to start Supercruise assist. \nClick button to capture new hotkey. Supports combinations like Ctrl+F2.",
            'Start Robigo': "Hotkey to start Robigo assist. \nClick button to capture new hotkey. Supports combinations like Ctrl+F3.",
            'Start Waypoint': "Hotkey to start waypoint assist (requires waypoint file loaded). \nClick button to capture new hotkey. Supports combinations like Ctrl+F4.",
            'Stop All': "Hotkey to stop all assists. \nClick button to capture new hotkey. Supports combinations like Ctrl+End.",
            'Pause/Resume': "Hotkey to pause/resume all running assists. \nClick button to capture new hotkey. Supports combinations like Ctrl+P. Right-click to cancel.",
            'Refuel Threshold': "If fuel level get below this level, \nit will attempt refuel.",
            'Scoop Timeout': "Number of second to wait for full tank, \nmight mean we are not scooping well or got a small scooper",
            'Fuel Threshold Abort': "Level at which AP will terminate, \nbecause we are not scooping well.",
            'X Offset': "Offset left the screen to start place overlay text.",
            'Y Offset': "Offset down the screen to start place overlay text.",
            'Font Size': "Font size of the overlay.",
            'Ship Config Button': "Read in a file with roll, pitch, yaw values for a ship.",
            'Pause All Button': "Pause all currently running assists. \nThey can be resumed later with the Resume button.",
            'Resume All Button': "Resume all previously paused assists. \nOnly works if assists were paused using the Pause button.",
            'Stop All Button': "Emergency stop! Immediately stops all running assists. \nUnlike pause, stopped assists cannot be resumed and must be restarted manually.",
            'Calibrate': "Will iterate through a set of scaling values \ngetting the best match for your system. \nSee HOWTO-Calibrate.md",
            'Waypoint List Button': "Read in a file with with your Waypoints.",
            'Cap Mouse XY': "This will provide the StationCoord value of the Station in the SystemMap. \nSelecting this button and then clicking on the Station in the SystemMap \nwill return the x,y value that can be pasted in the waypoints file",
            'Reset Waypoint List': "Reset your waypoint list, \nthe waypoint assist will start again at the first point in the list."
        }

        self.gui_loaded = False
        self.log_buffer = queue.Queue()

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
        self.DSS_A_running = False
        self.SWP_A_running = False
        
        # Pause system state tracking
        self.all_paused = False
        self.paused_assists = []  # Track which assists were paused
        
        # Track unsaved changes
        self.has_unsaved_changes = False
        self.save_button = None  # Will be set when GUI is created
        self.revert_button = None  # Will be set when GUI is created
        self.original_values = {}  # Track original field values for change detection

        self.cv_view = False

        self.TCE_Destination_Filepath.set(self.ed_ap.config['TCEDestinationFilepath'])

        self.msgList = self.gui_gen(root)

        self.checkboxvar['Enable Randomness'].set(self.ed_ap.config['EnableRandomness'])
        self.checkboxvar['Activate Elite for each key'].set(self.ed_ap.config['ActivateEliteEachKey'])
        self.checkboxvar['Automatic logout'].set(self.ed_ap.config['AutomaticLogout'])
        self.checkboxvar['Enable Overlay'].set(self.ed_ap.config['OverlayTextEnable'])
        self.checkboxvar['Enable Voice'].set(self.ed_ap.config['VoiceEnable'])

        self.radiobuttonvar['dss_button'].set(self.ed_ap.config['DSSButton'])
        
        # Flag to prevent change detection during initialization
        self._initializing = True

        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['autopilot']['Sun Bright Threshold'].delete(0, END)
        self.entries['autopilot']['Nav Align Tries'].delete(0, END)
        self.entries['autopilot']['Jump Tries'].delete(0, END)
        self.entries['autopilot']['Docking Retries'].delete(0, END)
        self.entries['autopilot']['Wait For Autodock'].delete(0, END)

        self.entries['refuel']['Refuel Threshold'].delete(0, END)
        self.entries['refuel']['Scoop Timeout'].delete(0, END)
        self.entries['refuel']['Fuel Threshold Abort'].delete(0, END)

        self.entries['overlay']['X Offset'].delete(0, END)
        self.entries['overlay']['Y Offset'].delete(0, END)
        self.entries['overlay']['Font Size'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, float(self.ed_ap.pitchrate))
        self.entries['ship']['RollRate'].insert(0, float(self.ed_ap.rollrate))
        self.entries['ship']['YawRate'].insert(0, float(self.ed_ap.yawrate))
        self.entries['ship']['SunPitchUp+Time'].insert(0, float(self.ed_ap.sunpitchuptime))

        self.entries['autopilot']['Sun Bright Threshold'].insert(0, int(self.ed_ap.config['SunBrightThreshold']))
        self.entries['autopilot']['Nav Align Tries'].insert(0, int(self.ed_ap.config['NavAlignTries']))
        self.entries['autopilot']['Jump Tries'].insert(0, int(self.ed_ap.config['JumpTries']))
        self.entries['autopilot']['Docking Retries'].insert(0, int(self.ed_ap.config['DockingRetries']))
        self.entries['autopilot']['Wait For Autodock'].insert(0, int(self.ed_ap.config['WaitForAutoDockTimer']))
        self.entries['refuel']['Refuel Threshold'].insert(0, int(self.ed_ap.config['RefuelThreshold']))
        self.entries['refuel']['Scoop Timeout'].insert(0, int(self.ed_ap.config['FuelScoopTimeOut']))
        self.entries['refuel']['Fuel Threshold Abort'].insert(0, int(self.ed_ap.config['FuelThreasholdAbortAP']))
        self.entries['overlay']['X Offset'].insert(0, int(self.ed_ap.config['OverlayTextXOffset']))
        self.entries['overlay']['Y Offset'].insert(0, int(self.ed_ap.config['OverlayTextYOffset']))
        self.entries['overlay']['Font Size'].insert(0, int(self.ed_ap.config['OverlayTextFontSize']))

        # Set button text to show current hotkeys (now buttons instead of entry fields!)
        self.entries['buttons']['Start FSD'].config(text=str(self.ed_ap.config['HotKey_StartFSD']))
        self.entries['buttons']['Start SC'].config(text=str(self.ed_ap.config['HotKey_StartSC']))
        self.entries['buttons']['Start Robigo'].config(text=str(self.ed_ap.config['HotKey_StartRobigo']))
        self.entries['buttons']['Start Waypoint'].config(text=str(self.ed_ap.config['HotKey_StartWaypoint']))
        self.entries['buttons']['Stop All'].config(text=str(self.ed_ap.config['HotKey_StopAllAssists']))
        self.entries['buttons']['Pause/Resume'].config(text=str(self.ed_ap.config['HotKey_PauseResume']))

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
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartWaypoint'], self.callback, args=('waypoint_start', None))
        
        # Only register pause hotkey if it's not empty
        pause_hotkey = self.ed_ap.config.get('HotKey_PauseResume', '').strip()
        if pause_hotkey:
            try:
                keyboard.add_hotkey(pause_hotkey, self.toggle_pause_all)
            except ValueError as e:
                logger.warning(f"Invalid pause hotkey '{pause_hotkey}': {e}. Pause hotkey disabled.")
        else:
            logger.info("No pause hotkey configured. Pause function available only via GUI buttons.")

        # check for updates
        self.check_updates()

        self.ed_ap.gui_loaded = True
        self.gui_loaded = True
        
        # Store original values for change detection
        self.capture_original_values()
        
        # Clear initialization flag - now we can track real changes
        if hasattr(self, '_initializing'):
            del self._initializing
            
        logger.debug(f"Initialization complete. Original values captured: {len(self.original_values)} categories")
            
        # Send a log entry which will flush out the buffer.
        self.callback('log', 'ED Autopilot loaded successfully.')

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
        elif msg == 'waypoint_start':
            self.checkboxvar['Waypoint Assist'].set(1)
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
        elif msg == 'dss_start':
            logger.debug("Detected 'dss_start' callback msg")
            self.checkboxvar['DSS Assist'].set(1)
            self.check_cb('DSS Assist')
        elif msg == 'dss_stop':
            logger.debug("Detected 'dss_stop' callback msg")
            self.checkboxvar['DSS Assist'].set(0)
            self.check_cb('DSS Assist')
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

            self.checkboxvar['DSS Assist'].set(0)
            self.check_cb('DSS Assist')

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

    def quit(self):
        logger.debug("Entered: quit")
        self.close_window()

    def close_window(self):
        logger.debug("Entered: close_window")
        
        # Check for unsaved changes
        if self.has_unsaved_changes:
            result = messagebox.askyesnocancel(
                "Unsaved Changes", 
                "You have unsaved settings changes.\n\nDo you want to save them before closing?",
                icon="question"
            )
            if result is True:  # Yes - save and close
                self.save_settings()
            elif result is None:  # Cancel - don't close
                return
            # False (No) - close without saving, continue below
        
        # Clean up keyboard hotkeys to prevent persistence between sessions
        try:
            keyboard.unhook_all_hotkeys()
            logger.debug("Keyboard hotkeys cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error cleaning up keyboard hotkeys: {e}")
        
        self.stop_fsd()
        self.stop_sc()
        self.ed_ap.quit()
        sleep(0.1)
        self.root.destroy()

    def capture_hotkey(self, field_name):
        """Capture a hotkey by listening for the next key press"""
        button = self.entries['buttons'][field_name]
        
        # Change button appearance to show it's waiting for input
        original_text = button.cget('text')
        original_bg = button.cget('bg')
        button.config(text="Press any key...", bg='yellow')
        self.root.update()
        
        # Variables to store the captured key
        captured_key: dict[str, str | None] = {'key': None}
        
        def on_key_press(event):
            """Handle key press during capture"""
            # Build list of modifiers and main key
            modifiers = []
            
            # Check for modifier keys
            if event.state & 0x4:  # Control key
                modifiers.append('ctrl')
            if event.state & 0x8:  # Alt key  
                modifiers.append('alt')
            if event.state & 0x1:  # Shift key
                modifiers.append('shift')
            if event.state & 0x40:  # Windows/Super key
                modifiers.append('win')
            
            # Convert tkinter key names to keyboard library format
            key_name = event.keysym.lower()
            
            # Handle special keys
            key_mapping = {
                'return': 'enter',
                'prior': 'page up',
                'next': 'page down',
                'delete': 'del',
                'insert': 'ins',
                'escape': 'esc',
                'control_l': 'ctrl',
                'control_r': 'ctrl',
                'alt_l': 'alt',
                'alt_r': 'alt',
                'shift_l': 'shift',
                'shift_r': 'shift',
                'super_l': 'win',
                'super_r': 'win',
                'space': 'space',
                'tab': 'tab',
                'backspace': 'backspace',
                'pause': 'pause',
                'scroll_lock': 'scroll lock',
                'num_lock': 'num lock',
                'caps_lock': 'caps lock',
                'print': 'print screen',
                'menu': 'menu'
            }
            
            # Handle function keys
            if key_name.startswith('f') and key_name[1:].isdigit():
                key_name = key_name  # f1, f2, etc. are already correct
            elif key_name in key_mapping:
                key_name = key_mapping[key_name]
            
            # Skip if the pressed key is only a modifier key
            if key_name in ['ctrl', 'alt', 'shift', 'win']:
                return  # Don't capture, wait for a real key
            
            # Build final hotkey string
            if modifiers:
                # Remove duplicate modifiers and sort for consistency
                modifiers = sorted(list(set(modifiers)))
                hotkey_string = '+'.join(modifiers) + '+' + key_name
            else:
                hotkey_string = key_name
            
            captured_key['key'] = hotkey_string
            
            # Stop capturing
            self.root.unbind('<KeyPress>')
            self.root.focus_set()  # Remove focus from capture
            
            # Update button with captured key
            button.config(text=hotkey_string, bg=original_bg)
            
            # Mark that changes need to be saved
            self.mark_unsaved_changes()
            
            # Log the capture
            logger.info(f"Captured hotkey '{hotkey_string}' for {field_name}")
            
        # Start capturing
        self.root.bind('<KeyPress>', on_key_press)
        self.root.focus_set()  # Ensure window can receive key events
        
        # Add a cancel option with right-click
        def on_right_click(event):
            self.root.unbind('<KeyPress>')
            self.root.unbind('<Button-3>')
            button.config(text=original_text, bg=original_bg)
            logger.info(f"Hotkey capture cancelled for {field_name}")
            
        self.root.bind('<Button-3>', on_right_click)

    def on_tab_changed(self, event):
        """Handle tab change - check for unsaved changes when leaving Settings tab"""
        if self.switching_tabs:
            return  # Already handling a tab change
            
        notebook = event.widget
        new_tab_index = notebook.index(notebook.select())
        new_tab_name = notebook.tab(new_tab_index, "text")
        old_tab_name = notebook.tab(self.current_tab_index, "text") if self.current_tab_index < len(notebook.tabs()) else ""
        
        # Only check for unsaved changes when leaving the Settings tab
        # (since that's the only place where unsaved changes can exist)
        if (self.has_unsaved_changes and 
            old_tab_name == "Settings" and 
            new_tab_name != "Settings" and 
            new_tab_index != self.current_tab_index):
            
            self.switching_tabs = True
            
            result = messagebox.askyesnocancel(
                "Unsaved Changes", 
                f"You have unsaved settings changes.\n\nDo you want to save them before switching to the {new_tab_name} tab?",
                icon="question"
            )
            
            if result is True:  # Yes - save and continue
                self.save_settings()
            elif result is False:  # No - discard changes and continue
                self.clear_unsaved_changes()
            else:  # Cancel - go back to Settings tab
                self.notebook.select(self.current_tab_index)
                self.switching_tabs = False
                return
                
            self.switching_tabs = False
        
        # Update current tab tracking
        self.current_tab_index = new_tab_index

    def mark_unsaved_changes(self):
        """Mark that there are unsaved changes and highlight save button"""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            if self.save_button:
                self.save_button.config(bg='orange', text='Save All Settings *')
            if self.revert_button:
                self.revert_button.config(state='normal', bg='lightcoral')
            logger.debug("Marked unsaved changes - buttons should be highlighted")
                
    def clear_unsaved_changes(self):
        """Clear unsaved changes flag and restore normal save button"""
        self.has_unsaved_changes = False
        if self.save_button:
            self.save_button.config(bg='SystemButtonFace', text='Save All Settings')
        if self.revert_button:
            self.revert_button.config(state='disabled', bg='SystemButtonFace')
        # Refresh original values after saving
        self.capture_original_values()

    def capture_original_values(self):
        """Capture current field values as baseline for change detection"""
        self.original_values = {}
        
        # Capture entry field values
        for category in ['ship', 'autopilot', 'refuel', 'overlay']:
            if category in self.entries:
                self.original_values[category] = {}
                for field_name, entry_widget in self.entries[category].items():
                    try:
                        value = entry_widget.get()
                        self.original_values[category][field_name] = value
                        logger.debug(f"Captured {category}.{field_name} = '{value}'")
                    except Exception as e:
                        logger.debug(f"Error capturing {category}.{field_name}: {e}")
                        pass
        
        # Capture button text (hotkeys)
        if 'buttons' in self.entries:
            self.original_values['buttons'] = {}
            for field_name, button_widget in self.entries['buttons'].items():
                try:
                    self.original_values['buttons'][field_name] = button_widget.cget('text')
                except:
                    pass
        
        # Capture checkbox states
        checkbox_fields = ['Enable Randomness', 'Activate Elite for each key', 'Automatic logout', 
                          'Enable Overlay', 'Enable Voice', 'ELW Scanner']
        self.original_values['checkboxes'] = {}
        for field in checkbox_fields:
            if field in self.checkboxvar:
                try:
                    self.original_values['checkboxes'][field] = self.checkboxvar[field].get()
                except:
                    pass
        
        # Capture radio button states
        if hasattr(self, 'radiobuttonvar'):
            self.original_values['radiobuttons'] = {}
            for field_name, var in self.radiobuttonvar.items():
                try:
                    self.original_values['radiobuttons'][field_name] = var.get()
                except:
                    pass

    def has_actual_changes(self):
        """Check if any values have actually changed from their original state"""
        if not self.original_values:
            logger.debug("has_actual_changes: No original values captured yet")
            return False
            
        # Check entry fields
        for category in ['ship', 'autopilot', 'refuel', 'overlay']:
            if category in self.entries and category in self.original_values:
                for field_name, entry_widget in self.entries[category].items():
                    try:
                        current_value = entry_widget.get()
                        original_value = self.original_values[category].get(field_name, '')
                        if current_value != original_value:
                            logger.debug(f"Change detected in {category}.{field_name}: '{original_value}' -> '{current_value}'")
                            return True
                    except Exception as e:
                        logger.debug(f"Error checking {category}.{field_name}: {e}")
                        pass
        
        # Check button text (hotkeys)
        if 'buttons' in self.entries and 'buttons' in self.original_values:
            for field_name, button_widget in self.entries['buttons'].items():
                try:
                    current_value = button_widget.cget('text')
                    original_value = self.original_values['buttons'].get(field_name, '')
                    if current_value != original_value:
                        logger.debug(f"Change detected in button {field_name}: '{original_value}' -> '{current_value}'")
                        return True
                except Exception as e:
                    logger.debug(f"Error checking button {field_name}: {e}")
                    pass
        
        # Check checkbox states
        checkbox_fields = ['Enable Randomness', 'Activate Elite for each key', 'Automatic logout', 
                          'Enable Overlay', 'Enable Voice', 'ELW Scanner']
        if 'checkboxes' in self.original_values:
            for field in checkbox_fields:
                if field in self.checkboxvar:
                    try:
                        current_value = self.checkboxvar[field].get()
                        original_value = self.original_values['checkboxes'].get(field, 0)
                        if current_value != original_value:
                            return True
                    except:
                        pass
        
        # Check radio button states
        if hasattr(self, 'radiobuttonvar') and 'radiobuttons' in self.original_values:
            for field_name, var in self.radiobuttonvar.items():
                try:
                    current_value = var.get()
                    original_value = self.original_values['radiobuttons'].get(field_name, '')
                    if current_value != original_value:
                        return True
                except:
                    pass
        
        return False

    def revert_all_changes(self):
        """Revert all fields back to their original values"""
        if not self.has_unsaved_changes or not self.original_values:
            return
        
        # Confirm revert action
        result = messagebox.askyesno(
            "Revert Changes", 
            "Are you sure you want to revert all unsaved changes?\n\nThis will reset all settings to their last saved values.",
            icon="warning"
        )
        if not result:
            return
        
        # Set flag to prevent change detection during revert
        self._reverting_changes = True
        
        try:
            # Revert entry fields
            for category in ['ship', 'autopilot', 'refuel', 'overlay']:
                if category in self.entries and category in self.original_values:
                    for field_name, entry_widget in self.entries[category].items():
                        try:
                            original_value = self.original_values[category].get(field_name, '')
                            entry_widget.delete(0, tk.END)
                            entry_widget.insert(0, original_value)
                        except:
                            pass
            
            # Revert button text (hotkeys)
            if 'buttons' in self.entries and 'buttons' in self.original_values:
                for field_name, button_widget in self.entries['buttons'].items():
                    try:
                        original_value = self.original_values['buttons'].get(field_name, '')
                        button_widget.config(text=original_value)
                    except:
                        pass
            
            # Revert checkbox states
            checkbox_fields = ['Enable Randomness', 'Activate Elite for each key', 'Automatic logout', 
                              'Enable Overlay', 'Enable Voice', 'ELW Scanner']
            if 'checkboxes' in self.original_values:
                for field in checkbox_fields:
                    if field in self.checkboxvar:
                        try:
                            original_value = self.original_values['checkboxes'].get(field, 0)
                            self.checkboxvar[field].set(original_value)
                        except:
                            pass
            
            # Revert radio button states
            if hasattr(self, 'radiobuttonvar') and 'radiobuttons' in self.original_values:
                for field_name, var in self.radiobuttonvar.items():
                    try:
                        original_value = self.original_values['radiobuttons'].get(field_name, '')
                        var.set(original_value)
                    except:
                        pass
            
            # Update internal values to match reverted GUI state
            self._update_internal_values()
            
            # Clear unsaved changes
            self.clear_unsaved_changes()
            
            self.log_msg("Settings reverted to last saved values")
            
        finally:
            # Remove flag
            if hasattr(self, '_reverting_changes'):
                del self._reverting_changes

    # this routine is to stop any current autopilot activity
    def stop_all_assists(self):
        logger.debug("Entered: stop_all_assists")
        self.callback('stop_all_assists')

    def toggle_pause_all(self):
        """Toggle pause/resume all running assists"""
        logger.debug("Entered: toggle_pause_all")
        
        if not self.all_paused:
            # Pause all running assists
            self.paused_assists = []
            if self.FSD_A_running:
                self.paused_assists.append('FSD')
                self.stop_fsd()
            if self.SC_A_running:
                self.paused_assists.append('SC')
                self.stop_sc()
            if self.WP_A_running:
                self.paused_assists.append('WP')
                self.stop_waypoint()
            if self.RO_A_running:
                self.paused_assists.append('RO')
                self.stop_robigo()
            if self.DSS_A_running:
                self.paused_assists.append('DSS')
                self.stop_dss()
            if self.SWP_A_running:
                self.paused_assists.append('SWP')
                self.stop_single_waypoint_assist()
            
            self.all_paused = True
            self.btn_pause.config(state='disabled', bg='gray')
            self.btn_resume.config(state='normal', bg='lightgreen')
            self.log_msg("ALL ASSISTS PAUSED")
            self.ed_ap.vce.say("All assists paused")
            
        else:
            # Resume previously running assists
            for assist in self.paused_assists:
                if assist == 'FSD':
                    self.start_fsd()
                elif assist == 'SC':
                    self.start_sc()
                elif assist == 'WP':
                    self.start_waypoint()
                elif assist == 'RO':
                    self.start_robigo()
                elif assist == 'DSS':
                    self.start_dss()
                elif assist == 'SWP':
                    self.start_single_waypoint_assist()
            
            self.all_paused = False
            self.paused_assists = []
            self.btn_pause.config(state='normal', bg='orange')
            self.btn_resume.config(state='disabled', bg='gray')
            self.log_msg("ALL ASSISTS RESUMED")
            self.ed_ap.vce.say("All assists resumed")

    def emergency_stop_all(self):
        """Emergency stop - immediately stops all running assists without pause tracking"""
        logger.debug("Entered: emergency_stop_all")
        
        # Clear any pause tracking since this is a hard stop
        self.all_paused = False
        self.paused_assists = []
        
        # Force stop all assists
        self.callback('stop_all_assists')
        
        # Update GUI buttons to reflect emergency stop
        self.btn_pause.config(state='normal', bg='orange')
        self.btn_resume.config(state='disabled', bg='gray')
        
        self.log_msg("EMERGENCY STOP - All assists stopped")
        self.ed_ap.vce.say("Emergency stop activated")
        logger.info("Emergency stop activated - all assists stopped")

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

    def start_dss(self):
        logger.debug("Entered: start_dss")
        self.ed_ap.set_dss_assist(True)
        self.DSS_A_running = True
        self.log_msg("DSS Assist start")
        self.ed_ap.vce.say("DSS Assist On")

    def stop_dss(self):
        logger.debug("Entered: stop_dss")
        self.ed_ap.set_dss_assist(False)
        self.DSS_A_running = False
        self.log_msg("DSS Assist stop")
        self.ed_ap.vce.say("DSS Assist Off")
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
        # response = requests.get("https://api.github.com/repos/SumZer0-git/EDAPGui/releases/latest")
        # if EDAP_VERSION != response.json()["name"]:
        #     mb = messagebox.askokcancel("Update Check", "A new release version is available. Download now?")
        #     if mb == True:
        #         webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/releases/latest")
        pass

    def open_changelog(self):
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/blob/main/ChangeLog.md")

    def open_discord(self):
        webbrowser.open_new("https://discord.gg/HCgkfSc")

    def open_logfile(self):
        os.startfile('autopilot.log')

    def log_msg(self, msg):
        message = datetime.now().strftime("%H:%M:%S: ") + msg

        if not self.gui_loaded:
            # Store message in queue
            self.log_buffer.put(message)
            logger.info(msg)
        else:
            # Add queued messages to the list
            while not self.log_buffer.empty():
                self.msgList.insert(END, self.log_buffer.get())

            self.msgList.insert(END, message)
            self.msgList.yview(END)
            logger.info(msg)

    def set_statusbar(self, txt):
        self.status.configure(text=txt)

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

        f_details = read_json_file(filename)

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
            res = self.ed_ap.waypoint.load_waypoint_file(filename)
            if res:
                self.wp_filelabel.set("loaded: " + Path(filename).name)
            else:
                self.wp_filelabel.set("<no list loaded>")

    def reset_wp_file(self):
        if self.WP_A_running != True:
            mb = messagebox.askokcancel("Waypoint List Reset", "After resetting the Waypoint List, the Waypoint Assist will start again from the first point in the list at the next start.")
            if mb == True:
                self.ed_ap.waypoint.mark_all_waypoints_not_complete()
        else:
            mb = messagebox.showerror("Waypoint List Error", "Waypoint Assist must be disabled before you can reset the list.")

    def save_settings(self):
        self._saving_settings = True  # Flag to prevent marking changes during save
        try:
            self.entry_update(mark_changes=False)  # Don't mark changes during save
            self.ed_ap.update_config()
            self.ed_ap.update_ship_configs()
            self.clear_unsaved_changes()
            self.log_msg("Settings saved successfully")
        finally:
            del self._saving_settings

    def load_tce_dest(self):
        filename = self.ed_ap.config['TCEDestinationFilepath']
        if os.path.exists(filename):
            f_details = read_json_file(filename)

            self.single_waypoint_system.set(f_details['StarSystem'])
            self.single_waypoint_station.set(f_details['Station'])

    # new data was added to a field, re-read them all for simple logic
    def entry_update(self, event=None, mark_changes=True):
        logger.debug(f"entry_update called: event={event}, mark_changes={mark_changes}")
        
        # Update the internal values first
        self._update_internal_values()
        
        # Only check for changes if we're not in special states and this is a real user event
        if (mark_changes and event is not None and  # Real event (not programmatic call)
            not hasattr(self, '_saving_settings') and 
            not hasattr(self, '_initializing') and
            not hasattr(self, '_reverting_changes')):
            # Check if there are actual changes, not just focus events
            actual_changes = self.has_actual_changes()
            logger.debug(f"entry_update: has_actual_changes={actual_changes}, has_unsaved_changes={self.has_unsaved_changes}")
            if actual_changes:
                if not self.has_unsaved_changes:  # Only mark once to avoid spam
                    self.mark_unsaved_changes()
            else:
                # Clear changes if all values are back to original
                if self.has_unsaved_changes:
                    self.clear_unsaved_changes()
        else:
            logger.debug(f"entry_update: Skipped change detection - mark_changes={mark_changes}, event={event is not None}, _saving_settings={hasattr(self, '_saving_settings')}, _initializing={hasattr(self, '_initializing')}, _reverting_changes={hasattr(self, '_reverting_changes')}")

    def _update_internal_values(self):
        """Update internal config values from GUI fields"""
        try:
            self.ed_ap.pitchrate = float(self.entries['ship']['PitchRate'].get())
            self.ed_ap.rollrate = float(self.entries['ship']['RollRate'].get())
            self.ed_ap.yawrate = float(self.entries['ship']['YawRate'].get())
            self.ed_ap.sunpitchuptime = float(self.entries['ship']['SunPitchUp+Time'].get())

            self.ed_ap.config['SunBrightThreshold'] = int(self.entries['autopilot']['Sun Bright Threshold'].get())
            self.ed_ap.config['NavAlignTries'] = int(self.entries['autopilot']['Nav Align Tries'].get())
            self.ed_ap.config['JumpTries'] = int(self.entries['autopilot']['Jump Tries'].get())
            self.ed_ap.config['DockingRetries'] = int(self.entries['autopilot']['Docking Retries'].get())
            self.ed_ap.config['WaitForAutoDockTimer'] = int(self.entries['autopilot']['Wait For Autodock'].get())
            self.ed_ap.config['RefuelThreshold'] = int(self.entries['refuel']['Refuel Threshold'].get())
            self.ed_ap.config['FuelScoopTimeOut'] = int(self.entries['refuel']['Scoop Timeout'].get())
            self.ed_ap.config['FuelThreasholdAbortAP'] = int(self.entries['refuel']['Fuel Threshold Abort'].get())
            self.ed_ap.config['OverlayTextXOffset'] = int(self.entries['overlay']['X Offset'].get())
            self.ed_ap.config['OverlayTextYOffset'] = int(self.entries['overlay']['Y Offset'].get())
            self.ed_ap.config['OverlayTextFontSize'] = int(self.entries['overlay']['Font Size'].get())
            # Get hotkey values from button text (buttons instead of entry fields)
            self.ed_ap.config['HotKey_StartFSD'] = str(self.entries['buttons']['Start FSD'].cget('text'))
            self.ed_ap.config['HotKey_StartSC'] = str(self.entries['buttons']['Start SC'].cget('text'))
            self.ed_ap.config['HotKey_StartRobigo'] = str(self.entries['buttons']['Start Robigo'].cget('text'))
            self.ed_ap.config['HotKey_StartWaypoint'] = str(self.entries['buttons']['Start Waypoint'].cget('text'))
            self.ed_ap.config['HotKey_StopAllAssists'] = str(self.entries['buttons']['Stop All'].cget('text'))
            self.ed_ap.config['HotKey_PauseResume'] = str(self.entries['buttons']['Pause/Resume'].cget('text'))
            self.ed_ap.config['VoiceEnable'] = self.checkboxvar['Enable Voice'].get()
            self.ed_ap.config['TCEDestinationFilepath'] = str(self.TCE_Destination_Filepath.get())
        except:
            messagebox.showinfo("Exception", "Invalid float entered")

    # ckbox.state:(ACTIVE | DISABLED)

    # ('FSD Route Assist', 'Supercruise Assist', 'Enable Voice', 'Enable CV View')
    def check_cb(self, field):
        # Mark unsaved changes for setting checkboxes and radio buttons (not operational ones)
        # Only if we're not initializing or saving
        setting_fields = ['Enable Randomness', 'Activate Elite for each key', 'Automatic logout', 
                         'Enable Overlay', 'Enable Voice', 'ELW Scanner', 'Enable CV View', 'debug_mode']
        if (field in setting_fields and 
            not hasattr(self, '_initializing') and 
            not hasattr(self, '_saving_settings') and
            not hasattr(self, '_reverting_changes')):
            # Check if there are actual changes, not just checkbox clicks
            if self.has_actual_changes():
                if not self.has_unsaved_changes:  # Only mark once to avoid spam
                    self.mark_unsaved_changes()
            else:
                # Clear changes if all values are back to original
                if self.has_unsaved_changes:
                    self.clear_unsaved_changes()
        
        # print("got event:",  checkboxvar['FSD Route Assist'].get(), " ", str(FSD_A_running))
        if field == 'FSD Route Assist':
            if self.checkboxvar['FSD Route Assist'].get() == 1 and self.FSD_A_running == False:
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.lab_ck['DSS Assist'].config(state='disabled')
                self.start_fsd()

            elif self.checkboxvar['FSD Route Assist'].get() == 0 and self.FSD_A_running == True:
                self.stop_fsd()
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')
                self.lab_ck['DSS Assist'].config(state='active')

        if field == 'Supercruise Assist':
            if self.checkboxvar['Supercruise Assist'].get() == 1 and self.SC_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.lab_ck['DSS Assist'].config(state='disabled')
                self.start_sc()

            elif self.checkboxvar['Supercruise Assist'].get() == 0 and self.SC_A_running == True:
                self.stop_sc()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')
                self.lab_ck['DSS Assist'].config(state='active')

        if field == 'Waypoint Assist':
            if self.checkboxvar['Waypoint Assist'].get() == 1 and self.WP_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.lab_ck['DSS Assist'].config(state='disabled')
                self.start_waypoint()

            elif self.checkboxvar['Waypoint Assist'].get() == 0 and self.WP_A_running == True:
                self.stop_waypoint()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')
                self.lab_ck['DSS Assist'].config(state='active')

        if field == 'Robigo Assist':
            if self.checkboxvar['Robigo Assist'].get() == 1 and self.RO_A_running == False:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['DSS Assist'].config(state='disabled')
                self.start_robigo()

            elif self.checkboxvar['Robigo Assist'].get() == 0 and self.RO_A_running == True:
                self.stop_robigo()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['DSS Assist'].config(state='active')

        if field == 'AFK Combat Assist':
            if self.checkboxvar['AFK Combat Assist'].get() == 1:
                self.ed_ap.set_afk_combat_assist(True)
                self.log_msg("AFK Combat Assist start")
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.lab_ck['DSS Assist'].config(state='disabled')

            elif self.checkboxvar['AFK Combat Assist'].get() == 0:
                self.ed_ap.set_afk_combat_assist(False)
                self.log_msg("AFK Combat Assist stop")
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['Waypoint Assist'].config(state='active')
                self.lab_ck['Robigo Assist'].config(state='active')
                self.lab_ck['DSS Assist'].config(state='active')

        if field == 'DSS Assist':
            if self.checkboxvar['DSS Assist'].get() == 1:
                self.lab_ck['FSD Route Assist'].config(state='disabled')
                self.lab_ck['AFK Combat Assist'].config(state='disabled')
                self.lab_ck['Supercruise Assist'].config(state='disabled')
                self.lab_ck['Waypoint Assist'].config(state='disabled')
                self.lab_ck['Robigo Assist'].config(state='disabled')
                self.start_dss()

            elif self.checkboxvar['DSS Assist'].get() == 0:
                self.stop_dss()
                self.lab_ck['FSD Route Assist'].config(state='active')
                self.lab_ck['Supercruise Assist'].config(state='active')
                self.lab_ck['AFK Combat Assist'].config(state='active')
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

        if self.checkboxvar['Automatic logout'].get():
            self.ed_ap.set_automatic_logout(True)
        else:
            self.ed_ap.set_automatic_logout(False)

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
            row.grid(row=r, column=0, padx=2, pady=2, sticky="nsew")
            r += 1

            ent = None  # Initialize to avoid unbound variable issues
            
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
                ent.bind('<FocusOut>', lambda event: self.entry_update(event))
                ent.insert(0, "0")

            lab.grid(row=0, column=0)
            lab = Hovertip(row, self.tooltips[field], hover_delay=1000)

            if ftype != FORM_TYPE_CHECKBOX and ent is not None:
                ent.grid(row=0, column=1)
                entries[field] = ent

        return entries

    def gui_gen(self, win):

        modes_check_fields = ('FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 'Robigo Assist', 'AFK Combat Assist', 'DSS Assist')
        ship_entry_fields = ('RollRate', 'PitchRate', 'YawRate')
        autopilot_entry_fields = ('Sun Bright Threshold', 'Nav Align Tries', 'Jump Tries', 'Docking Retries', 'Wait For Autodock')
        buttons_entry_fields = ('Start FSD', 'Start SC', 'Start Robigo', 'Start Waypoint', 'Stop All', 'Pause/Resume')
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
        page_control = Frame(nb)
        page_settings = Frame(nb)
        page_waypoints = Frame(nb)
        nb.add(page_control, text="Control")  # operations and monitoring page (MAIN TAB)
        nb.add(page_settings, text="Settings")  # configuration page
        nb.add(page_waypoints, text="Waypoints")  # route management page
        
        # Store notebook reference and add tab change detection for unsaved changes
        self.notebook = nb
        self.current_tab_index = 0  # Track current tab
        self.switching_tabs = False  # Flag to handle tab switching
        nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # ===== SETTINGS TAB =====
        settings_main = tk.Frame(page_settings)
        settings_main.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        settings_main.columnconfigure([0], weight=1, minsize=100)

        # ship configuration block (configuration only, no testing)
        blk_ship = LabelFrame(settings_main, text="SHIP CONFIGURATION")
        blk_ship.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        blk_ship.columnconfigure([0, 1], weight=1, minsize=120)
        
        # ship parameter fields (roll/pitch/yaw rates) - custom layout with fields on right
        self.entries['ship'] = {}
        ship_fields = ('RollRate', 'PitchRate', 'YawRate')
        for i, field in enumerate(ship_fields):
            lbl = tk.Label(blk_ship, text=f"{field} (°/s):", anchor='w')
            lbl.grid(row=i, column=0, padx=2, pady=2, sticky="nsew")
            
            ent = tk.Spinbox(blk_ship, width=10, from_=0, to=1000, increment=0.5)
            ent.grid(row=i, column=1, padx=2, pady=2, sticky="nsew")
            ent.bind('<FocusOut>', self.entry_update)
            ent.insert(0, "0")
            self.entries['ship'][field] = ent

        # sun pitch up time setting
        lbl_sun_pitch_up = tk.Label(blk_ship, text='SunPitchUp +/- Time (s):', anchor='w')
        lbl_sun_pitch_up.grid(row=3, column=0, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up = tk.Spinbox(blk_ship, width=10, from_=-100, to=100, increment=0.5)
        spn_sun_pitch_up.grid(row=3, column=1, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up.bind('<FocusOut>', self.entry_update)
        self.entries['ship']['SunPitchUp+Time'] = spn_sun_pitch_up

        # test buttons for ship parameters (positioned with RPY values)
        blk_ship.columnconfigure([2], weight=1, minsize=80)  # Add third column for test buttons
        btn_tst_roll = Button(blk_ship, text='Test', command=self.ship_tst_roll)
        btn_tst_roll.grid(row=0, column=2, padx=2, pady=2, sticky="news")
        btn_tst_pitch = Button(blk_ship, text='Test', command=self.ship_tst_pitch)
        btn_tst_pitch.grid(row=1, column=2, padx=2, pady=2, sticky="news")
        btn_tst_yaw = Button(blk_ship, text='Test', command=self.ship_tst_yaw)
        btn_tst_yaw.grid(row=2, column=2, padx=2, pady=2, sticky="news")

        # ship config file loading
        self.ship_filelabel = StringVar()
        self.ship_filelabel.set("<no config loaded>")
        btn_ship_file = Button(blk_ship, textvariable=self.ship_filelabel, command=self.open_ship_file)
        btn_ship_file.grid(row=4, column=0, padx=2, pady=5, columnspan=3, sticky="news")
        tip_ship_file = Hovertip(btn_ship_file, self.tooltips['Ship Config Button'], hover_delay=1000)

        # ===== CONTROL TAB =====
        control_main = tk.Frame(page_control)
        control_main.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        control_main.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # assist modes block (moved from settings - this is where users interact!)
        blk_modes = LabelFrame(control_main, text="ASSIST MODES")
        blk_modes.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        self.makeform(blk_modes, FORM_TYPE_CHECKBOX, modes_check_fields)

        # autopilot control block
        blk_controls = LabelFrame(control_main, text="AUTOPILOT CONTROL")
        blk_controls.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        # Pause/Resume buttons (moved from ship section)
        self.btn_pause = Button(blk_controls, text='Pause All', command=self.toggle_pause_all, 
                               bg='orange', relief='raised')
        self.btn_pause.grid(row=0, column=0, padx=2, pady=2, sticky="news")
        tip_pause = Hovertip(self.btn_pause, self.tooltips['Pause All Button'], hover_delay=1000)
        
        self.btn_resume = Button(blk_controls, text='Resume All', command=self.toggle_pause_all,
                                bg='gray', state='disabled', relief='raised')
        self.btn_resume.grid(row=0, column=1, padx=2, pady=2, sticky="news")
        tip_resume = Hovertip(self.btn_resume, self.tooltips['Resume All Button'], hover_delay=1000)
        
        # Emergency Stop All button
        self.btn_stop_all = Button(blk_controls, text='STOP ALL', command=self.emergency_stop_all,
                                  bg='red', fg='white', relief='raised', font=('TkDefaultFont', 9, 'bold'))
        self.btn_stop_all.grid(row=1, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_stop_all = Hovertip(self.btn_stop_all, self.tooltips['Stop All Button'], hover_delay=1000)

        # waypoint file loading (moved from waypoints tab - needed before enabling waypoint assist)
        self.wp_filelabel = StringVar()
        self.wp_filelabel.set("<no waypoint list loaded>")
        btn_wp_file = Button(blk_controls, textvariable=self.wp_filelabel, command=self.open_wp_file)
        btn_wp_file.grid(row=2, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_wp_file = Hovertip(btn_wp_file, self.tooltips['Waypoint List Button'], hover_delay=1000)

        btn_reset = Button(blk_controls, text='Reset Waypoint List', command=self.reset_wp_file)
        btn_reset.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        tip_reset = Hovertip(btn_reset, self.tooltips['Reset Waypoint List'], hover_delay=1000)


        # log window (expanded to fill available space)
        log = LabelFrame(page_control, text="LOG & STATUS")
        log.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        log.columnconfigure(0, weight=1)
        log.rowconfigure(0, weight=1)
        
        scrollbar = Scrollbar(log)
        scrollbar.grid(row=0, column=1, sticky="ns")
        mylist = Listbox(log, width=72, yscrollcommand=scrollbar.set)
        mylist.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=mylist.yview)
        
        # Make sure the control page expands properly
        page_control.columnconfigure(0, weight=1)
        page_control.rowconfigure(1, weight=1)

        # ===== WAYPOINTS TAB =====
        # Note: Main waypoint file loading is now in Control tab near the assist modes

        # ===== SETTINGS TAB (CONTINUED) =====
        # additional settings block (moved from old page1 to settings tab)
        blk_settings = tk.Frame(page_settings)
        blk_settings.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        blk_settings.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # autopilot settings block
        blk_ap = LabelFrame(blk_settings, text="AUTOPILOT")
        blk_ap.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        self.entries['autopilot'] = self.makeform(blk_ap, FORM_TYPE_SPINBOX, autopilot_entry_fields)
        self.checkboxvar['Enable Randomness'] = BooleanVar()
        cb_random = Checkbutton(blk_ap, text='Enable Randomness', anchor='w', pady=3, justify=LEFT, onvalue=1, offvalue=0, variable=self.checkboxvar['Enable Randomness'], command=(lambda field='Enable Randomness': self.check_cb(field)))
        cb_random.grid(row=5, column=0, columnspan=2, sticky="w")
        self.checkboxvar['Activate Elite for each key'] = BooleanVar()
        cb_activate_elite = Checkbutton(blk_ap, text='Activate Elite for each key', anchor='w', pady=3, justify=LEFT, onvalue=1, offvalue=0, variable=self.checkboxvar['Activate Elite for each key'], command=(lambda field='Activate Elite for each key': self.check_cb(field)))
        cb_activate_elite.grid(row=6, column=0, columnspan=2, sticky="w")
        self.checkboxvar['Automatic logout'] = BooleanVar()
        cb_logout = Checkbutton(blk_ap, text='Automatic logout', anchor='w', pady=3, justify=LEFT, onvalue=1, offvalue=0, variable=self.checkboxvar['Automatic logout'], command=(lambda field='Automatic logout': self.check_cb(field)))
        cb_logout.grid(row=7, column=0, columnspan=2, sticky="w")

        # buttons settings block
        blk_buttons = LabelFrame(blk_settings, text="BUTTONS")
        blk_buttons.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        blk_dss = Frame(blk_buttons)
        blk_dss.grid(row=0, column=0, columnspan=2, padx=0, pady=0, sticky="nsew")
        lb_dss = Label(blk_dss, width=18, anchor='w', pady=3, text="DSS Button: ")
        lb_dss.grid(row=0, column=0, sticky="w")
        self.radiobuttonvar['dss_button'] = StringVar()
        rb_dss_primary = Radiobutton(blk_dss, pady=3, text="Primary", variable=self.radiobuttonvar['dss_button'], value="Primary", command=(lambda field='dss_button': self.check_cb(field)))
        rb_dss_primary.grid(row=0, column=1, sticky="w")
        rb_dss_secandary = Radiobutton(blk_dss, pady=3, text="Secondary", variable=self.radiobuttonvar['dss_button'], value="Secondary", command=(lambda field='dss_button': self.check_cb(field)))
        rb_dss_secandary.grid(row=1, column=1, sticky="w")
        # Create custom hotkey capture entries instead of using makeform
        self.entries['buttons'] = {}
        for i, field in enumerate(buttons_entry_fields):
            row = tk.Frame(blk_buttons)
            row.grid(row=i+2, column=0, padx=2, pady=2, sticky="nsew")
            
            lab = tk.Label(row, anchor='w', width=20, pady=3, text=field + ": ")
            lab.grid(row=0, column=0)
            
            # Create hotkey capture button instead of entry field
            btn = tk.Button(row, width=15, text="Click to set...", 
                           command=lambda f=field: self.capture_hotkey(f))
            btn.grid(row=0, column=1)
            self.entries['buttons'][field] = btn
            
            # Add tooltip
            tip = Hovertip(row, self.tooltips[field], hover_delay=1000)

        # refuel settings block
        blk_fuel = LabelFrame(blk_settings, text="FUEL")
        blk_fuel.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")
        self.entries['refuel'] = self.makeform(blk_fuel, FORM_TYPE_SPINBOX, refuel_entry_fields)

        # overlay settings block
        blk_overlay = LabelFrame(blk_settings, text="OVERLAY")
        blk_overlay.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")
        self.checkboxvar['Enable Overlay'] = BooleanVar()
        cb_enable = Checkbutton(blk_overlay, text='Enable (requires restart)', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Enable Overlay'], command=(lambda field='Enable Overlay': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")
        self.entries['overlay'] = self.makeform(blk_overlay, FORM_TYPE_SPINBOX, overlay_entry_fields, 1, 1, 0, 3000)

        # tts / voice settings block
        blk_voice = LabelFrame(blk_settings, text="VOICE")
        blk_voice.grid(row=2, column=0, padx=2, pady=2, sticky="nsew")
        self.checkboxvar['Enable Voice'] = BooleanVar()
        cb_enable = Checkbutton(blk_voice, text='Enable', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Enable Voice'], command=(lambda field='Enable Voice': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")

        # Scanner settings block
        blk_voice = LabelFrame(blk_settings, text="ELW SCANNER")
        blk_voice.grid(row=2, column=1, padx=2, pady=2, sticky="nsew")
        self.checkboxvar['ELW Scanner'] = BooleanVar()
        cb_enable = Checkbutton(blk_voice, text='Enable', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['ELW Scanner'], command=(lambda field='ELW Scanner': self.check_cb(field)))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")

        # debug settings block
        blk_debug = LabelFrame(blk_settings, text="DEBUG & LOGGING")
        blk_debug.grid(row=3, column=0, padx=2, pady=2, sticky="nsew")
        blk_debug.columnconfigure([0, 1, 2], weight=1, minsize=50)
        
        lbl_debug = tk.Label(blk_debug, text='Debug Level:', anchor='w')
        lbl_debug.grid(row=0, column=0, pady=3, sticky="nsew")
        self.radiobuttonvar['debug_mode'] = StringVar()
        rb_debug_error = Radiobutton(blk_debug, text="Error", variable=self.radiobuttonvar['debug_mode'], value="Error", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_error.grid(row=0, column=1, sticky="w")
        rb_debug_info = Radiobutton(blk_debug, text="Info", variable=self.radiobuttonvar['debug_mode'], value="Info", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_info.grid(row=1, column=1, sticky="w")
        rb_debug_debug = Radiobutton(blk_debug, text="Debug", variable=self.radiobuttonvar['debug_mode'], value="Debug", command=(lambda field='debug_mode': self.check_cb(field)))
        rb_debug_debug.grid(row=1, column=2, sticky="w")

        # log file access in debug section
        blk_logfile = LabelFrame(blk_settings, text="LOG FILE")
        blk_logfile.grid(row=3, column=1, padx=2, pady=2, sticky="nsew")
        btn_open_logfile = Button(blk_logfile, text='Open Log File', command=self.open_logfile)
        btn_open_logfile.grid(row=0, column=0, padx=2, pady=2, sticky="news")

        # settings button block
        blk_settings_buttons = tk.Frame(page_settings)
        blk_settings_buttons.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")
        blk_settings_buttons.columnconfigure([0, 1], weight=1, minsize=100)
        
        self.save_button = Button(blk_settings_buttons, text='Save All Settings', command=self.save_settings)
        self.save_button.grid(row=0, column=0, padx=2, pady=2, sticky="news")
        
        self.revert_button = Button(blk_settings_buttons, text='Revert Changes', command=self.revert_all_changes,
                                   state='disabled', bg='SystemButtonFace')
        self.revert_button.grid(row=0, column=1, padx=2, pady=2, sticky="news")

        # ===== WAYPOINTS TAB (CONTINUED) =====
        # single waypoint assist block (moved to waypoints tab)
        blk_single_waypoint_asst = LabelFrame(page_waypoints, text="SINGLE WAYPOINT ASSIST")
        blk_single_waypoint_asst.grid(row=0, column=0, padx=10, pady=5, columnspan=2, sticky="nsew")
        blk_single_waypoint_asst.columnconfigure(0, weight=1, minsize=10, uniform="group1")
        blk_single_waypoint_asst.columnconfigure(1, weight=3, minsize=10, uniform="group1")

        lbl_system = tk.Label(blk_single_waypoint_asst, text='System:')
        lbl_system.grid(row=0, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_system = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_system)
        txt_system.grid(row=0, column=1, padx=2, pady=2, columnspan=1, sticky="news")
        lbl_station = tk.Label(blk_single_waypoint_asst, text='Station:')
        lbl_station.grid(row=1, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_station = Entry(blk_single_waypoint_asst, textvariable=self.single_waypoint_station)
        txt_station.grid(row=1, column=1, padx=2, pady=2, columnspan=1, sticky="news")
        self.checkboxvar['Single Waypoint Assist'] = BooleanVar()
        cb_single_waypoint = Checkbutton(blk_single_waypoint_asst, text='Single Waypoint Assist', onvalue=1, offvalue=0, anchor='w', pady=3, justify=LEFT, variable=self.checkboxvar['Single Waypoint Assist'], command=(lambda field='Single Waypoint Assist': self.check_cb(field)))
        cb_single_waypoint.grid(row=2, column=0, padx=2, pady=2, columnspan=2, sticky="news")

        lbl_tce = tk.Label(blk_single_waypoint_asst, text='Trade Computer Extension (TCE)', fg="blue", cursor="hand2")
        lbl_tce.bind("<Button-1>", lambda e: hyperlink_callback("https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/"))
        lbl_tce.grid(row=3, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        lbl_tce_dest = tk.Label(blk_single_waypoint_asst, text='TCE Dest json:')
        lbl_tce_dest.grid(row=4, column=0, padx=2, pady=2, columnspan=1, sticky="news")
        txt_tce_dest = Entry(blk_single_waypoint_asst, textvariable=self.TCE_Destination_Filepath)
        txt_tce_dest.bind('<FocusOut>', self.entry_update)
        txt_tce_dest.grid(row=4, column=1, padx=2, pady=2, columnspan=1, sticky="news")

        btn_load_tce = Button(blk_single_waypoint_asst, text='Load TCE Destination', command=self.load_tce_dest)
        btn_load_tce.grid(row=5, column=0, padx=2, pady=2, columnspan=2, sticky="news")

        # Statusbar
        self.statusbar = Frame(win)
        self.statusbar.grid(row=4, column=0)
        self.status = tk.Label(win, text="Status: ", bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=29)
        self.jumpcount = tk.Label(self.statusbar, text="<info> ", bd=1, relief=tk.SUNKEN, anchor=tk.W, justify=LEFT, width=40)
        self.status.pack(in_=self.statusbar, side=LEFT, fill=BOTH, expand=True)
        self.jumpcount.pack(in_=self.statusbar, side=RIGHT, fill=Y, expand=False)

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

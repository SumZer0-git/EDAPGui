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

# Import our modular GUI components
from gui.settings_panel import SettingsPanel
from gui.assist_panel import AssistPanel
from gui.waypoint_panel import WaypointPanel
from gui.config_manager import ConfigManager


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


def hyperlink_callback(url):
    webbrowser.open_new(url)


class APGui():
    def __init__(self, root):
        self.root = root
        root.title("EDAutopilot " + EDAP_VERSION)
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

        # Initialize modular components
        self.config_manager = ConfigManager(self.ed_ap)
        
        # These will be set during GUI creation
        self.settings_panel: SettingsPanel | None = None
        self.assist_panel: AssistPanel | None = None
        self.waypoint_panel: WaypointPanel | None = None
        
        self.cv_view = False

        # Create GUI
        self.msgList = self._create_gui(root)

        # Initialize component values
        self._initialize_all_components()

        # Set up configuration management
        self._setup_config_management()

        # Set up hotkeys
        self._setup_hotkeys()

        # Check for updates
        self.check_updates()

        self.ed_ap.gui_loaded = True
        self.gui_loaded = True
        
        # Store original values for change detection
        self.config_manager.capture_original_values()
            
        logger.debug("Initialization complete.")
            
        # Send a log entry which will flush out the buffer.
        self.callback('log', 'ED Autopilot loaded successfully.')

    def _create_gui(self, root):
        """Create the main GUI structure with modular components"""
        # Create menus
        self._create_menus(root)

        # Create notebook pages
        nb = ttk.Notebook(root)
        nb.grid()
        
        page_control = Frame(nb)
        page_settings = Frame(nb)
        page_waypoints = Frame(nb)
        
        nb.add(page_control, text="Control")
        nb.add(page_settings, text="Settings")
        nb.add(page_waypoints, text="Waypoints")
        
        # Store notebook reference and add tab change detection
        self.notebook = nb
        self.current_tab_index = 0
        self.switching_tabs = False
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Create modular panels
        self.assist_panel = AssistPanel(page_control, self.ed_ap, self.tooltips, self._check_cb)
        self.settings_panel = SettingsPanel(page_settings, self.ed_ap, self.tooltips, 
                                           self._entry_update, self._check_cb)
        self.waypoint_panel = WaypointPanel(page_waypoints, self.ed_ap, 
                                           self._entry_update, self._check_cb)

        # Connect assist panel callbacks
        self.assist_panel.set_stop_all_callback(self.stop_all_assists)

        # Create status bar
        self._create_status_bar(root)

        return self.assist_panel.msgList

    def _create_menus(self, root):
        """Create application menus"""
        menubar = Menu(root, background='#ff8000', foreground='black', 
                      activebackground='white', activeforeground='black')
        
        file = Menu(menubar, tearoff=0)
        file.add_command(label="Calibrate Target", command=self.calibrate_callback)
        file.add_command(label="Calibrate Compass", command=self.calibrate_compass_callback)
        
        # CV View checkbox
        self.cv_view_var = IntVar()
        self.cv_view_var.set(int(self.ed_ap.config['Enable_CV_View']))
        file.add_checkbutton(label='Enable CV View', onvalue=1, offvalue=0, 
                            variable=self.cv_view_var, 
                            command=lambda: self._check_cb('Enable CV View'))
        
        file.add_separator()
        file.add_command(label="Restart", command=self.restart_program)
        file.add_command(label="Exit", command=self.close_window)
        menubar.add_cascade(label="File", menu=file)

        help = Menu(menubar, tearoff=0)
        help.add_command(label="Check for Updates", command=self.check_updates)
        help.add_command(label="View Changelog", command=self.open_changelog)
        help.add_separator()
        help.add_command(label="Join Discord", command=self.open_discord)
        help.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=help)

        root.config(menu=menubar)

    def _create_status_bar(self, root):
        """Create status bar"""
        self.statusbar = Frame(root)
        self.statusbar.grid(row=4, column=0)
        self.status = tk.Label(root, text="Status: ", bd=1, relief=tk.SUNKEN, 
                              anchor=tk.W, justify=LEFT, width=29)
        self.jumpcount = tk.Label(self.statusbar, text="<info> ", bd=1, relief=tk.SUNKEN, 
                                 anchor=tk.W, justify=LEFT, width=40)
        self.status.pack(in_=self.statusbar, side=LEFT, fill=BOTH, expand=True)
        self.jumpcount.pack(in_=self.statusbar, side=RIGHT, fill=Y, expand=False)

    def _initialize_all_components(self):
        """Initialize values in all components"""
        if self.settings_panel:
            self.settings_panel.initialize_values()
        if self.waypoint_panel:
            self.waypoint_panel.initialize_values()

    def _setup_config_management(self):
        """Set up configuration management with GUI elements"""
        gui_elements = {
            'settings_panel': self.settings_panel,
            'waypoint_panel': self.waypoint_panel,
            'save_button': self.settings_panel.save_button if self.settings_panel else None,
            'revert_button': self.settings_panel.revert_button if self.settings_panel else None
        }
        self.config_manager.set_gui_elements(gui_elements)
        
        # Connect save/revert buttons to config manager
        if self.settings_panel:
            self.settings_panel.save_button.config(command=self.config_manager.save_settings)
            self.settings_panel.revert_button.config(command=self.config_manager.revert_all_changes)
            
            # Inject dependencies into settings panel instead of monkey-patching
            self.settings_panel.set_config_manager(self.config_manager)
            self.settings_panel.set_hotkey_capture_callback(self._capture_hotkey)

    def _setup_hotkeys(self):
        """Set up global hotkeys"""
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StopAllAssists'], self.stop_all_assists)
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartFSD'], self.callback, args=('fsd_start', None))
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartSC'], self.callback, args=('sc_start', None))
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartRobigo'], self.callback, args=('robigo_start', None))
        keyboard.add_hotkey(self.ed_ap.config['HotKey_StartWaypoint'], self.callback, args=('waypoint_start', None))
        
        # Only register pause hotkey if it's not empty
        pause_hotkey = self.ed_ap.config.get('HotKey_PauseResume', '').strip()
        if pause_hotkey:
            try:
                keyboard.add_hotkey(pause_hotkey, self._toggle_pause_all)
            except ValueError as e:
                logger.warning(f"Invalid pause hotkey '{pause_hotkey}': {e}. Pause hotkey disabled.")
        else:
            logger.info("No pause hotkey configured. Pause function available only via GUI buttons.")

    # Callback from the EDAP, to configure GUI items
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
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('FSD Route Assist', 0)
                self._check_cb('FSD Route Assist')
        elif msg == 'fsd_start':
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('FSD Route Assist', 1)
                self._check_cb('FSD Route Assist')
        elif msg == 'sc_stop':
            logger.debug("Detected 'sc_stop' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Supercruise Assist', 0)
                self._check_cb('Supercruise Assist')
        elif msg == 'sc_start':
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Supercruise Assist', 1)
                self._check_cb('Supercruise Assist')
        elif msg == 'waypoint_stop':
            logger.debug("Detected 'waypoint_stop' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Waypoint Assist', 0)
                self._check_cb('Waypoint Assist')
        elif msg == 'waypoint_start':
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Waypoint Assist', 1)
                self._check_cb('Waypoint Assist')
        elif msg == 'robigo_stop':
            logger.debug("Detected 'robigo_stop' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Robigo Assist', 0)
                self._check_cb('Robigo Assist')
        elif msg == 'robigo_start':
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('Robigo Assist', 1)
                self._check_cb('Robigo Assist')
        elif msg == 'afk_stop':
            logger.debug("Detected 'afk_stop' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('AFK Combat Assist', 0)
                self._check_cb('AFK Combat Assist')
        elif msg == 'dss_start':
            logger.debug("Detected 'dss_start' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('DSS Assist', 1)
                self._check_cb('DSS Assist')
        elif msg == 'dss_stop':
            logger.debug("Detected 'dss_stop' callback msg")
            if self.assist_panel:
                self.assist_panel.set_checkbox_state('DSS Assist', 0)
                self._check_cb('DSS Assist')
        elif msg == 'single_waypoint_stop':
            logger.debug("Detected 'single_waypoint_stop' callback msg")
            if self.waypoint_panel:
                self.waypoint_panel.set_checkbox_state('Single Waypoint Assist', 0)
                self._check_cb('Single Waypoint Assist')
        elif msg == 'stop_all_assists':
            logger.debug("Detected 'stop_all_assists' callback msg")
            # Stop all assists in assist panel
            if self.assist_panel:
                for assist in ['FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 
                              'Robigo Assist', 'AFK Combat Assist', 'DSS Assist']:
                    self.assist_panel.set_checkbox_state(assist, 0)
                    self._check_cb(assist)
            # Stop single waypoint assist
            if self.waypoint_panel:
                self.waypoint_panel.set_checkbox_state('Single Waypoint Assist', 0)
                self._check_cb('Single Waypoint Assist')
        elif msg == 'jumpcount':
            self.update_jumpcount(body)
        elif msg == 'update_ship_cfg':
            self.update_ship_display()

    def update_ship_display(self):
        """Update ship configuration display"""
        if self.settings_panel:
            self.settings_panel.update_ship_display()

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
        if self.config_manager.has_unsaved_changes:
            result = messagebox.askyesnocancel(
                "Unsaved Changes", 
                "You have unsaved settings changes.\n\nDo you want to save them before closing?",
                icon="question"
            )
            if result is True:  # Yes - save and close
                if not self.config_manager.save_settings():
                    return  # Save failed, don't close
            elif result is None:  # Cancel - don't close
                return
            # False (No) - close without saving, continue below
        
        # Clean up keyboard hotkeys
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

    def _capture_hotkey(self, field_name):
        """Capture a hotkey by listening for the next key press"""
        if not self.settings_panel or 'buttons' not in self.settings_panel.entries:
            return
            
        button = self.settings_panel.entries['buttons'][field_name]
        
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
                'return': 'enter', 'prior': 'page up', 'next': 'page down',
                'delete': 'del', 'insert': 'ins', 'escape': 'esc',
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'alt_l': 'alt', 'alt_r': 'alt',
                'shift_l': 'shift', 'shift_r': 'shift',
                'super_l': 'win', 'super_r': 'win',
                'space': 'space', 'tab': 'tab', 'backspace': 'backspace',
                'pause': 'pause', 'scroll_lock': 'scroll lock',
                'num_lock': 'num lock', 'caps_lock': 'caps lock',
                'print': 'print screen', 'menu': 'menu'
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
                modifiers = sorted(list(set(modifiers)))
                hotkey_string = '+'.join(modifiers) + '+' + key_name
            else:
                hotkey_string = key_name
            
            captured_key['key'] = hotkey_string
            
            # Stop capturing
            self.root.unbind('<KeyPress>')
            self.root.focus_set()
            
            # Update button with captured key
            button.config(text=hotkey_string, bg=original_bg)
            
            # Mark that changes need to be saved
            self.config_manager.mark_unsaved_changes()
            
            logger.info(f"Captured hotkey '{hotkey_string}' for {field_name}")
            
        # Start capturing
        self.root.bind('<KeyPress>', on_key_press)
        self.root.focus_set()
        
        # Add a cancel option with right-click
        def on_right_click(event):
            self.root.unbind('<KeyPress>')
            self.root.unbind('<Button-3>')
            button.config(text=original_text, bg=original_bg)
            logger.info(f"Hotkey capture cancelled for {field_name}")
            
        self.root.bind('<Button-3>', on_right_click)

    def _on_tab_changed(self, event):
        """Handle tab change - check for unsaved changes when leaving Settings tab"""
        if self.switching_tabs:
            return
            
        notebook = event.widget
        new_tab_index = notebook.index(notebook.select())
        new_tab_name = notebook.tab(new_tab_index, "text")
        old_tab_name = notebook.tab(self.current_tab_index, "text") if self.current_tab_index < len(notebook.tabs()) else ""
        
        # Only check for unsaved changes when leaving the Settings tab
        if (self.config_manager.has_unsaved_changes and 
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
                self.config_manager.save_settings()
            elif result is False:  # No - discard changes and continue
                self.config_manager.clear_unsaved_changes()
            else:  # Cancel - go back to Settings tab
                self.notebook.select(self.current_tab_index)
                self.switching_tabs = False
                return
                
            self.switching_tabs = False
        
        # Update current tab tracking
        self.current_tab_index = new_tab_index

    def stop_all_assists(self):
        """Stop all autopilot assists"""
        logger.debug("Entered: stop_all_assists")
        self.callback('stop_all_assists')

    def _toggle_pause_all(self):
        """Toggle pause/resume all running assists"""
        if self.assist_panel:
            self.assist_panel._toggle_pause_all()

    def _entry_update(self, event=None, mark_changes=True):
        """Handle entry field updates"""
        if (mark_changes and event is not None and 
            not hasattr(self, '_saving_settings') and 
            not hasattr(self, '_initializing') and
            not hasattr(self, '_reverting_changes')):
            
            if self.config_manager.has_actual_changes():
                if not self.config_manager.has_unsaved_changes:
                    self.config_manager.mark_unsaved_changes()
            else:
                if self.config_manager.has_unsaved_changes:
                    self.config_manager.clear_unsaved_changes()

    def _check_cb(self, field):
        """Handle checkbox and radio button changes"""
        # Handle assist mode checkboxes
        if field in ['FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 
                    'Robigo Assist', 'AFK Combat Assist', 'DSS Assist']:
            self._handle_assist_checkbox(field)
        
        # Handle Single Waypoint Assist
        elif field == 'Single Waypoint Assist':
            self._handle_single_waypoint_assist()
        
        # Handle CV View
        elif field == 'Enable CV View':
            self._handle_cv_view()
        
        # Handle settings checkboxes and radio buttons
        else:
            self._handle_settings_controls(field)
        
        # Mark unsaved changes for setting controls
        setting_fields = ['Enable Randomness', 'Activate Elite for each key', 'Automatic logout', 
                         'Enable Overlay', 'Enable Voice', 'ELW Scanner', 'debug_mode', 'dss_button']
        if (field in setting_fields and 
            not hasattr(self, '_initializing') and 
            not hasattr(self, '_saving_settings') and
            not hasattr(self, '_reverting_changes')):
            
            if self.config_manager.has_actual_changes():
                if not self.config_manager.has_unsaved_changes:
                    self.config_manager.mark_unsaved_changes()
            else:
                if self.config_manager.has_unsaved_changes:
                    self.config_manager.clear_unsaved_changes()

    def _handle_assist_checkbox(self, field):
        """Handle assist mode checkbox changes"""
        if not self.assist_panel:
            return
            
        checkbox_state = self.assist_panel.get_checkbox_state(field)
        
        if field == 'FSD Route Assist':
            if checkbox_state == 1 and not self.assist_panel.FSD_A_running:
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
                self.start_fsd()
            elif checkbox_state == 0 and self.assist_panel.FSD_A_running:
                self.stop_fsd()
                self.assist_panel.enable_disable_checkboxes(field, 'active')
        
        elif field == 'Supercruise Assist':
            if checkbox_state == 1 and not self.assist_panel.SC_A_running:
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
                self.start_sc()
            elif checkbox_state == 0 and self.assist_panel.SC_A_running:
                self.stop_sc()
                self.assist_panel.enable_disable_checkboxes(field, 'active')
        
        elif field == 'Waypoint Assist':
            if checkbox_state == 1 and not self.assist_panel.WP_A_running:
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
                self.start_waypoint()
            elif checkbox_state == 0 and self.assist_panel.WP_A_running:
                self.stop_waypoint()
                self.assist_panel.enable_disable_checkboxes(field, 'active')
        
        elif field == 'Robigo Assist':
            if checkbox_state == 1 and not self.assist_panel.RO_A_running:
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
                self.start_robigo()
            elif checkbox_state == 0 and self.assist_panel.RO_A_running:
                self.stop_robigo()
                self.assist_panel.enable_disable_checkboxes(field, 'active')
        
        elif field == 'AFK Combat Assist':
            if checkbox_state == 1:
                self.ed_ap.set_afk_combat_assist(True)
                self.log_msg("AFK Combat Assist start")
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
            elif checkbox_state == 0:
                self.ed_ap.set_afk_combat_assist(False)
                self.log_msg("AFK Combat Assist stop")
                self.assist_panel.enable_disable_checkboxes(field, 'active')
        
        elif field == 'DSS Assist':
            if checkbox_state == 1:
                self.assist_panel.enable_disable_checkboxes(field, 'disabled')
                self.start_dss()
            elif checkbox_state == 0:
                self.stop_dss()
                self.assist_panel.enable_disable_checkboxes(field, 'active')

    def _handle_single_waypoint_assist(self):
        """Handle single waypoint assist checkbox"""
        if not self.waypoint_panel:
            return
            
        checkbox_state = self.waypoint_panel.get_checkbox_state('Single Waypoint Assist')
        if checkbox_state == 1 and self.assist_panel and not self.assist_panel.SWP_A_running:
            self.start_single_waypoint_assist()
        elif checkbox_state == 0 and self.assist_panel and self.assist_panel.SWP_A_running:
            self.stop_single_waypoint_assist()

    def _handle_cv_view(self):
        """Handle CV View checkbox"""
        if self.cv_view_var.get() == 1:
            self.cv_view = True
            x = self.root.winfo_x() + self.root.winfo_width() + 4
            y = self.root.winfo_y()
            self.ed_ap.set_cv_view(True, x, y)
        else:
            self.cv_view = False
            self.ed_ap.set_cv_view(False)

    def _handle_settings_controls(self, field):
        """Handle settings checkboxes and radio buttons"""
        if not self.settings_panel:
            return
            
        # Handle checkboxes
        if field in self.settings_panel.checkboxvar:
            checkbox_value = self.settings_panel.checkboxvar[field].get()
            
            if field == 'Enable Randomness':
                self.ed_ap.set_randomness(checkbox_value)
            elif field == 'Activate Elite for each key':
                self.ed_ap.set_activate_elite_eachkey(checkbox_value)
                self.ed_ap.keys.activate_window = checkbox_value
            elif field == 'Automatic logout':
                self.ed_ap.set_automatic_logout(checkbox_value)
            elif field == 'Enable Overlay':
                self.ed_ap.set_overlay(checkbox_value)
            elif field == 'Enable Voice':
                self.ed_ap.set_voice(checkbox_value)
            elif field == 'ELW Scanner':
                self.ed_ap.set_fss_scan(checkbox_value)
        
        # Handle radio buttons
        if field in self.settings_panel.radiobuttonvar:
            radio_value = self.settings_panel.radiobuttonvar[field].get()
            
            if field == 'dss_button':
                self.ed_ap.config['DSSButton'] = radio_value
            elif field == 'debug_mode':
                if radio_value == "Error":
                    self.ed_ap.set_log_error(True)
                elif radio_value == "Debug":
                    self.ed_ap.set_log_debug(True)
                elif radio_value == "Info":
                    self.ed_ap.set_log_info(True)

    # Assist control methods
    def start_fsd(self):
        logger.debug("Entered: start_fsd")
        self.ed_ap.set_fsd_assist(True)
        if self.assist_panel:
            self.assist_panel.update_assist_state('FSD', True)
        self.log_msg("FSD Route Assist start")
        self.ed_ap.vce.say("FSD Route Assist On")

    def stop_fsd(self):
        logger.debug("Entered: stop_fsd")
        self.ed_ap.set_fsd_assist(False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('FSD', False)
        self.log_msg("FSD Route Assist stop")
        self.ed_ap.vce.say("FSD Route Assist Off")
        self.update_statusline("Idle")

    def start_sc(self):
        logger.debug("Entered: start_sc")
        self.ed_ap.set_sc_assist(True)
        if self.assist_panel:
            self.assist_panel.update_assist_state('SC', True)
        self.log_msg("SC Assist start")
        self.ed_ap.vce.say("Supercruise Assist On")

    def stop_sc(self):
        logger.debug("Entered: stop_sc")
        self.ed_ap.set_sc_assist(False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('SC', False)
        self.log_msg("SC Assist stop")
        self.ed_ap.vce.say("Supercruise Assist Off")
        self.update_statusline("Idle")

    def start_waypoint(self):
        logger.debug("Entered: start_waypoint")
        self.ed_ap.set_waypoint_assist(True)
        if self.assist_panel:
            self.assist_panel.update_assist_state('WP', True)
        self.log_msg("Waypoint Assist start")
        self.ed_ap.vce.say("Waypoint Assist On")

    def stop_waypoint(self):
        logger.debug("Entered: stop_waypoint")
        self.ed_ap.set_waypoint_assist(False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('WP', False)
        self.log_msg("Waypoint Assist stop")
        self.ed_ap.vce.say("Waypoint Assist Off")
        self.update_statusline("Idle")

    def start_robigo(self):
        logger.debug("Entered: start_robigo")
        self.ed_ap.set_robigo_assist(True)
        if self.assist_panel:
            self.assist_panel.update_assist_state('RO', True)
        self.log_msg("Robigo Assist start")
        self.ed_ap.vce.say("Robigo Assist On")

    def stop_robigo(self):
        logger.debug("Entered: stop_robigo")
        self.ed_ap.set_robigo_assist(False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('RO', False)
        self.log_msg("Robigo Assist stop")
        self.ed_ap.vce.say("Robigo Assist Off")
        self.update_statusline("Idle")

    def start_dss(self):
        logger.debug("Entered: start_dss")
        self.ed_ap.set_dss_assist(True)
        if self.assist_panel:
            self.assist_panel.update_assist_state('DSS', True)
        self.log_msg("DSS Assist start")
        self.ed_ap.vce.say("DSS Assist On")

    def stop_dss(self):
        logger.debug("Entered: stop_dss")
        self.ed_ap.set_dss_assist(False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('DSS', False)
        self.log_msg("DSS Assist stop")
        self.ed_ap.vce.say("DSS Assist Off")
        self.update_statusline("Idle")

    def start_single_waypoint_assist(self):
        logger.debug("Entered: start_single_waypoint_assist")
        if not self.waypoint_panel:
            return
        system = self.waypoint_panel.get_single_waypoint_system()
        station = self.waypoint_panel.get_single_waypoint_station()

        if system != "" or station != "":
            self.ed_ap.set_single_waypoint_assist(system, station, True)
            if self.assist_panel:
                self.assist_panel.update_assist_state('SWP', True)
            self.log_msg("Single Waypoint Assist start")
            self.ed_ap.vce.say("Single Waypoint Assist On")

    def stop_single_waypoint_assist(self):
        logger.debug("Entered: stop_single_waypoint_assist")
        self.ed_ap.set_single_waypoint_assist("", "", False)
        if self.assist_panel:
            self.assist_panel.update_assist_state('SWP', False)
        self.log_msg("Single Waypoint Assist stop")
        self.ed_ap.vce.say("Single Waypoint Assist Off")
        self.update_statusline("Idle")

    # Utility methods
    def about(self):
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui")

    def check_updates(self):
        pass

    def open_changelog(self):
        webbrowser.open_new("https://github.com/SumZer0-git/EDAPGui/blob/main/ChangeLog.md")

    def open_discord(self):
        webbrowser.open_new("https://discord.gg/HCgkfSc")

    def log_msg(self, msg):
        message = datetime.now().strftime("%H:%M:%S: ") + msg

        if not self.gui_loaded:
            self.log_buffer.put(message)
            logger.info(msg)
        else:
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
    root = tk.Tk()
    app = APGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

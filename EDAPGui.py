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
    ACTIVE, DISABLED, END, LEFT, SUNKEN, BOTH, X, Y, RIGHT
)
from tkinter import filedialog as fd
from tkinter import messagebox
from tkinter import ttk
from idlelib.tooltip import Hovertip

from Voice import *
from MousePt import MousePoint

from Image_Templates import *
import importlib
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
EDAP_VERSION = "V1.4.2 Beta"
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
        self._programmatic_update = False  # Global flag for programmatic updates

        try:
            self.ed_ap = EDAutopilot(cb=self.callback)
            self.ed_ap.robigo.set_single_loop(self.ed_ap.config['Robigo_Single_Loop'])
        except Exception as e:
            raise Exception(f"Failed to initialize EDAutopilot: {e}") from e

        self.mouse = MousePoint()

        # Initialize modular components
        try:
            self.config_manager = ConfigManager(self.ed_ap)
        except Exception as e:
            raise Exception(f"Failed to initialize ConfigManager: {e}") from e
        
        # These will be set during GUI creation
        self.settings_panel: SettingsPanel | None = None
        self.assist_panel: AssistPanel | None = None
        self.waypoint_panel: WaypointPanel | None = None
        
        self.cv_view = False

        # Create GUI
        try:
            self.msgList = self._create_gui(root)
        except Exception as e:
            raise Exception(f"Failed to create GUI: {e}") from e

        # Initialize component values
        self._initialize_all_components()
        
        # Update ship display after components are initialized
        self.update_ship_display()

        # Set up configuration management
        self._setup_config_management()

        # Set up hotkeys
        self._setup_hotkeys()

        # Check for updates
        self.check_updates()

        self.ed_ap.gui_loaded = True
        self.gui_loaded = True
        
        # Send a log entry which will flush out the buffer.
        self.callback('log', 'ED Autopilot loaded successfully.')
        
        # Store original values for change detection
        self.config_manager.capture_original_values()

    def programmatic_update(self):
        """Context manager to prevent change detection during programmatic GUI updates"""
        class ProgrammaticUpdateContext:
            def __init__(self, gui):
                self.gui = gui
                
            def __enter__(self):
                self.gui._programmatic_update = True
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.gui._programmatic_update = False
                
        return ProgrammaticUpdateContext(self)

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
        
        # Add dev menu if in development mode
        if self._is_dev_mode():
            self._create_dev_menu(menubar)

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
        from EDlogger import logger
        
        # Set initialization flag to prevent change detection during initialization
        logger.debug("Setting _initializing = True")
        self._initializing = True
        
        try:
            # Initialize settings panel (ship config, autopilot settings, checkboxes, radio buttons, etc.)
            if self.settings_panel:
                logger.debug("Initializing settings panel...")
                self.settings_panel.initialize_all_values()
            
            # Initialize waypoint panel
            if self.waypoint_panel:
                logger.debug("Initializing waypoint panel...")
                self.waypoint_panel.initialize_values()
                
            # Initialize assist panel checkboxes and state
            if self.assist_panel:
                logger.debug("Initializing assist panel...")
                self._initialize_assist_panel_values()
                
        except Exception as e:
            logger.error(f"Error during component initialization: {e}")
            raise
        finally:
            # Always clear initialization flag
            logger.debug("Setting _initializing = False")
            self._initializing = False

    def _initialize_settings_panel_values(self):
        """Initialize settings panel values from configuration"""
        if not self.settings_panel:
            return
            
        # Initialize autopilot settings
        if 'autopilot' in self.settings_panel.entries:
            autopilot_entries = self.settings_panel.entries['autopilot']
            if 'Sun Bright Threshold' in autopilot_entries:
                autopilot_entries['Sun Bright Threshold'].delete(0, END)
                autopilot_entries['Sun Bright Threshold'].insert(0, str(self.ed_ap.config.get('SunBrightThreshold', 125)))
            if 'Nav Align Tries' in autopilot_entries:
                autopilot_entries['Nav Align Tries'].delete(0, END)
                autopilot_entries['Nav Align Tries'].insert(0, str(self.ed_ap.config.get('NavAlignTries', 3)))
            if 'Jump Tries' in autopilot_entries:
                autopilot_entries['Jump Tries'].delete(0, END)
                autopilot_entries['Jump Tries'].insert(0, str(self.ed_ap.config.get('JumpTries', 3)))
            if 'Docking Retries' in autopilot_entries:
                autopilot_entries['Docking Retries'].delete(0, END)
                autopilot_entries['Docking Retries'].insert(0, str(self.ed_ap.config.get('DockingRetries', 6)))
            if 'Wait For Autodock' in autopilot_entries:
                autopilot_entries['Wait For Autodock'].delete(0, END)
                autopilot_entries['Wait For Autodock'].insert(0, str(self.ed_ap.config.get('WaitForAutoDockTimer', 120)))
        
        # Initialize fuel settings
        if 'refuel' in self.settings_panel.entries:
            refuel_entries = self.settings_panel.entries['refuel']
            if 'Refuel Threshold' in refuel_entries:
                refuel_entries['Refuel Threshold'].delete(0, END)
                refuel_entries['Refuel Threshold'].insert(0, str(self.ed_ap.config.get('RefuelThreshold', 65)))
            if 'Scoop Timeout' in refuel_entries:
                refuel_entries['Scoop Timeout'].delete(0, END)
                refuel_entries['Scoop Timeout'].insert(0, str(self.ed_ap.config.get('FuelScoopTimeOut', 180)))
            if 'Fuel Threshold Abort' in refuel_entries:
                refuel_entries['Fuel Threshold Abort'].delete(0, END)
                refuel_entries['Fuel Threshold Abort'].insert(0, str(self.ed_ap.config.get('FuelThresholdAbort', 10)))
        
        # Initialize overlay settings
        if 'overlay' in self.settings_panel.entries:
            overlay_entries = self.settings_panel.entries['overlay']
            if 'X Offset' in overlay_entries:
                overlay_entries['X Offset'].delete(0, END)
                overlay_entries['X Offset'].insert(0, str(self.ed_ap.config.get('OverlayTextXoffset', 100)))
            if 'Y Offset' in overlay_entries:
                overlay_entries['Y Offset'].delete(0, END)
                overlay_entries['Y Offset'].insert(0, str(self.ed_ap.config.get('OverlayTextYoffset', 100)))
            if 'Font Size' in overlay_entries:
                overlay_entries['Font Size'].delete(0, END)
                overlay_entries['Font Size'].insert(0, str(self.ed_ap.config.get('OverlayTextFontSize', 14)))
        
        # Initialize checkboxes
        if hasattr(self.settings_panel, 'checkboxvar'):
            checkboxes = {
                'Enable Randomness': self.ed_ap.config.get('EnableRandomness', False),
                'Activate Elite for each key': self.ed_ap.config.get('EliteKeySequenceRepeat', False),
                'Automatic logout': self.ed_ap.config.get('Auto_Logout', False),
                'Enable Overlay': self.ed_ap.config.get('Enable_Overlay', False),
                'Enable Voice': self.ed_ap.config.get('Enable_Voice', True),
                'ELW Scanner': self.ed_ap.config.get('EnableElwScannerSearch', False),
            }
            
            for field, value in checkboxes.items():
                if field in self.settings_panel.checkboxvar:
                    self.settings_panel.checkboxvar[field].set(bool(value))
        
        # Initialize radio buttons
        if hasattr(self.settings_panel, 'radiobuttonvar'):
            if 'dss_button' in self.settings_panel.radiobuttonvar:
                dss_button_value = self.ed_ap.config.get('DSSButton', 'Primary')
                self.settings_panel.radiobuttonvar['dss_button'].set(dss_button_value)
            
            if 'debug_mode' in self.settings_panel.radiobuttonvar:
                # Determine debug level from current log level
                debug_level = "Info"  # default
                if hasattr(self.ed_ap, 'logger_level'):
                    level = self.ed_ap.logger_level
                    if level == 'ERROR':
                        debug_level = "Error"
                    elif level == 'DEBUG':
                        debug_level = "Debug"
                    elif level == 'INFO':
                        debug_level = "Info"
                self.settings_panel.radiobuttonvar['debug_mode'].set(debug_level)
        
        # Initialize hotkey buttons
        if 'buttons' in self.settings_panel.entries:
            button_entries = self.settings_panel.entries['buttons']
            hotkey_mappings = {
                'Start FSD': self.ed_ap.config.get('HotKey_StartFSD', 'home'),
                'Start SC': self.ed_ap.config.get('HotKey_StartSC', 'insert'),
                'Start Robigo': self.ed_ap.config.get('HotKey_StartRobigo', 'page up'),
                'Start Waypoint': self.ed_ap.config.get('HotKey_StartWaypoint', 'f12'),
                'Stop All': self.ed_ap.config.get('HotKey_StopAllAssists', 'end'),
                'Pause/Resume': self.ed_ap.config.get('HotKey_PauseResume', '')
            }
            
            for field, hotkey in hotkey_mappings.items():
                if field in button_entries and hotkey:
                    button_entries[field].config(text=hotkey)
                elif field in button_entries:
                    button_entries[field].config(text="Click to set...")

    def _initialize_assist_panel_values(self):
        """Initialize assist panel values and state"""
        if not self.assist_panel:
            return
            
        # Initialize all assist checkboxes to unchecked state
        assist_modes = ['FSD Route Assist', 'Supercruise Assist', 'Waypoint Assist', 
                      'Robigo Assist', 'AFK Combat Assist', 'DSS Assist']
        
        for mode in assist_modes:
            if mode in self.assist_panel.checkboxvar:
                self.assist_panel.checkboxvar[mode].set(0)
        
        # Reset all assist running states
        self.assist_panel.FSD_A_running = False
        self.assist_panel.SC_A_running = False
        self.assist_panel.WP_A_running = False
        self.assist_panel.RO_A_running = False
        self.assist_panel.DSS_A_running = False
        self.assist_panel.SWP_A_running = False
        
        # Reset pause system
        self.assist_panel.all_paused = False
        self.assist_panel.paused_assists = []
        self.assist_panel.btn_pause.config(state='normal', bg='orange')
        self.assist_panel.btn_resume.config(state='disabled', bg='gray')

    def _setup_config_management(self):
        """Set up configuration management with GUI elements"""
        gui_elements = {
            'settings_panel': self.settings_panel,
            'waypoint_panel': self.waypoint_panel,
            'save_button': self.settings_panel.save_button if self.settings_panel else None,
            'revert_button': self.settings_panel.revert_button if self.settings_panel else None
        }
        self.config_manager.set_gui_elements(gui_elements)
        self.config_manager.set_programmatic_update_context(self.programmatic_update)
        
        # Inject dependencies into settings panel
        if self.settings_panel:
            self.settings_panel.set_config_manager(self.config_manager)
            self.settings_panel.set_hotkey_capture_callback(self._capture_hotkey)
            self.settings_panel.set_button_commands(
                self.config_manager.save_settings,
                self.config_manager.revert_all_changes
            )

    def _setup_hotkeys(self):
        # Set up global hotkeys
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
            logger.debug(f"GUI: Received update_ship_cfg callback")
            self.update_ship_display()

    def update_ship_display(self):
        """Update ship configuration display"""
        logger.debug(f"GUI: update_ship_display called, current_ship_type='{getattr(self.ed_ap, 'current_ship_type', 'NONE')}'")
        if self.settings_panel:
            logger.debug(f"GUI: Calling settings_panel.update_ship_display()")
            self.settings_panel.update_ship_display()
        else:
            logger.debug(f"GUI: No settings_panel available")

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
        """Handle entry field updates - only trigger on meaningful changes"""
        from EDlogger import logger
        
        logger.debug(f"_entry_update called: event={event}, mark_changes={mark_changes}")
        logger.debug(f"  Guard checks: _saving_settings={getattr(self, '_saving_settings', False)}, "
                    f"_initializing={getattr(self, '_initializing', False)}, "
                    f"_reverting_changes={getattr(self, '_reverting_changes', False)}, "
                    f"_programmatic_update={self._programmatic_update}")
        
        if (mark_changes and event is not None and 
            not getattr(self, '_saving_settings', False) and 
            not getattr(self, '_initializing', False) and
            not getattr(self, '_reverting_changes', False) and
            not self._programmatic_update):
            
            logger.debug("  Guards passed, checking for changes...")
            has_changes = self.config_manager.has_actual_changes()
            logger.debug(f"  has_actual_changes() returned: {has_changes}")
            
            if has_changes:
                if not self.config_manager.has_unsaved_changes:
                    logger.debug("  Marking unsaved changes")
                    self.config_manager.mark_unsaved_changes()
                else:
                    logger.debug("  Already marked as unsaved")
            else:
                # Only clear if we previously had unsaved changes
                if self.config_manager.has_unsaved_changes:
                    logger.debug("  Clearing unsaved changes")
                    self.config_manager.clear_unsaved_changes()
                else:
                    logger.debug("  No changes detected, no action needed")
        else:
            logger.debug("  Guards failed, skipping change detection")

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

    # ===== DEVELOPMENT MODE METHODS =====
    
    def _is_dev_mode(self):
        """Check if we're in development mode"""
        return (
            os.path.exists('.git') or                    # Git repository
            '--dev' in sys.argv or                       # Command line flag
            os.getenv('EDAP_DEV_MODE') == '1' or        # Environment variable
            os.path.exists('dev_mode.txt')              # Dev mode file
        )
    
    def _create_dev_menu(self, menubar):
        """Create development menu"""
        dev_menu = Menu(menubar, tearoff=0)
        
        # Panel reloading
        dev_menu.add_command(label="🔄 Reload Waypoint Panel", command=self._reload_waypoint_panel)
        dev_menu.add_command(label="🔄 Reload Settings Panel", command=self._reload_settings_panel)
        dev_menu.add_command(label="🔄 Reload Assist Panel", command=self._reload_assist_panel)
        dev_menu.add_separator()
        
        # Debug tools
        dev_menu.add_command(label="🐛 Toggle Debug Logging", command=self._toggle_debug_logging)
        dev_menu.add_command(label="📊 Show Panel State", command=self._show_panel_state)
        dev_menu.add_command(label="🧪 Open Dev Console", command=self._open_dev_console)
        dev_menu.add_separator()
        
        # File operations
        dev_menu.add_command(label="💾 Force Save All", command=self._force_save_all)
        dev_menu.add_command(label="🔍 Validate Config Files", command=self._validate_config_files)
        
        menubar.add_cascade(label="🔧 Dev", menu=dev_menu)
        
        # Log that dev mode is active
        logger.info("🔧 Development mode enabled - Dev menu available")
    
    def _reload_waypoint_panel(self):
        """Hot reload the waypoint panel"""
        try:
            logger.info("🔄 Reloading waypoint panel...")
            
            # Save current state
            state = self._save_waypoint_panel_state()
            
            # Reload the module
            import gui.waypoint_panel
            importlib.reload(gui.waypoint_panel)
            
            # Recreate the panel
            if self.waypoint_panel:
                parent = self.waypoint_panel.parent
                
                # Destroy old panel
                for widget in parent.winfo_children():
                    widget.destroy()
                
                # Create new panel
                self.waypoint_panel = gui.waypoint_panel.WaypointPanel(
                    parent, self.ed_ap, self._entry_update, self._check_cb
                )
                
                # Restore state
                self._restore_waypoint_panel_state(state)
                
            logger.info("✅ Waypoint panel reloaded successfully")
            self.log_msg("Dev: Waypoint panel reloaded")
            
        except Exception as e:
            logger.error(f"❌ Failed to reload waypoint panel: {e}")
            messagebox.showerror("Reload Error", f"Failed to reload waypoint panel:\n{e}")
    
    def _reload_settings_panel(self):
        """Hot reload the settings panel"""
        try:
            logger.info("🔄 Reloading settings panel...")
            
            # Save current state
            state = self._save_settings_panel_state()
            
            # Reload the module
            import gui.settings_panel
            importlib.reload(gui.settings_panel)
            
            # Recreate the panel
            if self.settings_panel:
                parent = self.settings_panel.parent
                
                # Destroy old panel
                for widget in parent.winfo_children():
                    widget.destroy()
                
                # Create new panel
                self.settings_panel = gui.settings_panel.SettingsPanel(
                    parent, self.ed_ap, self._entry_update, self._check_cb
                )
                
                # Re-inject dependencies
                self.settings_panel.set_config_manager(self.config_manager)
                self.settings_panel.set_hotkey_capture_callback(self._capture_hotkey)
                self.settings_panel.set_button_commands(
                    self.config_manager.save_all_settings,
                    self.config_manager.revert_all_changes
                )
                
                # Update config manager references
                gui_elements = self.config_manager.gui_elements
                gui_elements['settings_panel'] = self.settings_panel
                gui_elements['save_button'] = self.settings_panel.save_button
                gui_elements['revert_button'] = self.settings_panel.revert_button
                self.config_manager.set_gui_elements(gui_elements)
                
                # Restore state
                self._restore_settings_panel_state(state)
                
            logger.info("✅ Settings panel reloaded successfully")
            self.log_msg("Dev: Settings panel reloaded")
            
        except Exception as e:
            logger.error(f"❌ Failed to reload settings panel: {e}")
            messagebox.showerror("Reload Error", f"Failed to reload settings panel:\n{e}")
    
    def _reload_assist_panel(self):
        """Hot reload the assist panel"""
        try:
            logger.info("🔄 Reloading assist panel...")
            
            # Save current state
            state = self._save_assist_panel_state()
            
            # Reload the module
            import gui.assist_panel
            importlib.reload(gui.assist_panel)
            
            # Recreate the panel
            if self.assist_panel:
                parent = self.assist_panel.parent
                
                # Destroy old panel
                for widget in parent.winfo_children():
                    widget.destroy()
                
                # Create new panel
                self.assist_panel = gui.assist_panel.AssistPanel(
                    parent, self.ed_ap, self._check_cb
                )
                
                # Restore state
                self._restore_assist_panel_state(state)
                
            logger.info("✅ Assist panel reloaded successfully")
            self.log_msg("Dev: Assist panel reloaded")
            
        except Exception as e:
            logger.error(f"❌ Failed to reload assist panel: {e}")
            messagebox.showerror("Reload Error", f"Failed to reload assist panel:\n{e}")
    
    def _save_waypoint_panel_state(self):
        """Save current waypoint panel state"""
        if not self.waypoint_panel:
            return {}
        
        return {
            'wp_filelabel': getattr(self.waypoint_panel, 'wp_filelabel', StringVar()).get(),
            'changed_waypoints': getattr(self.waypoint_panel, 'changed_waypoints', set()).copy(),
            'global_shopping_enabled': getattr(self.waypoint_panel, 'global_shopping_enabled', BooleanVar()).get(),
            'TCE_Destination_Filepath': getattr(self.waypoint_panel, 'TCE_Destination_Filepath', StringVar()).get(),
            'single_waypoint_system': getattr(self.waypoint_panel, 'single_waypoint_system', StringVar()).get(),
            'single_waypoint_station': getattr(self.waypoint_panel, 'single_waypoint_station', StringVar()).get(),
        }
    
    def _restore_waypoint_panel_state(self, state):
        """Restore waypoint panel state after reload"""
        if not self.waypoint_panel or not state:
            return
        
        try:
            # Restore file label
            if 'wp_filelabel' in state and hasattr(self.waypoint_panel, 'wp_filelabel'):
                self.waypoint_panel.wp_filelabel.set(state['wp_filelabel'])
            
            # Restore changed waypoints
            if 'changed_waypoints' in state and hasattr(self.waypoint_panel, 'changed_waypoints'):
                self.waypoint_panel.changed_waypoints = state['changed_waypoints']
            
            # Restore global shopping state
            if 'global_shopping_enabled' in state and hasattr(self.waypoint_panel, 'global_shopping_enabled'):
                self.waypoint_panel.global_shopping_enabled.set(state['global_shopping_enabled'])
            
            # Restore TCE and single waypoint fields
            for field in ['TCE_Destination_Filepath', 'single_waypoint_system', 'single_waypoint_station']:
                if field in state and hasattr(self.waypoint_panel, field):
                    getattr(self.waypoint_panel, field).set(state[field])
            
            # Refresh the panel
            if hasattr(self.waypoint_panel, '_wp_editor_refresh'):
                self.waypoint_panel._wp_editor_refresh()
            if hasattr(self.waypoint_panel, '_refresh_global_shopping_summary'):
                self.waypoint_panel._refresh_global_shopping_summary()
                
        except Exception as e:
            logger.warning(f"Some state could not be restored: {e}")
    
    def _save_settings_panel_state(self):
        """Save current settings panel state"""
        # Settings panel state is managed by config_manager, so we just need to capture current values
        return {
            'has_unsaved_changes': getattr(self.config_manager, 'has_unsaved_changes', False)
        }
    
    def _restore_settings_panel_state(self, state):
        """Restore settings panel state after reload"""
        # Re-initialize values from configuration
        if self.settings_panel and hasattr(self.settings_panel, 'initialize_all_values'):
            self.settings_panel.initialize_all_values()
        
        # Restore unsaved changes state if needed
        if state.get('has_unsaved_changes', False):
            self.config_manager.mark_unsaved_changes()
    
    def _save_assist_panel_state(self):
        """Save current assist panel state"""
        if not self.assist_panel:
            return {}
        
        # Get current assist states
        return {
            'assist_states': {
                'FSD': getattr(self.ed_ap, 'fsd_assist_enabled', False),
                'SC': getattr(self.ed_ap, 'sc_assist_enabled', False),
                'WP': getattr(self.ed_ap, 'waypoint_assist_enabled', False),
                'Robigo': getattr(self.ed_ap, 'robigo_assist_enabled', False),
                'AFK': getattr(self.ed_ap, 'afk_combat_assist_enabled', False),
                'DSS': getattr(self.ed_ap, 'dss_assist_enabled', False),
            }
        }
    
    def _restore_assist_panel_state(self, state):
        """Restore assist panel state after reload"""
        if not self.assist_panel or not state:
            return
        
        # Restore assist states
        assist_states = state.get('assist_states', {})
        for assist_type, enabled in assist_states.items():
            if hasattr(self.assist_panel, 'update_assist_state'):
                self.assist_panel.update_assist_state(assist_type, enabled)
    
    def _toggle_debug_logging(self):
        """Toggle debug logging level"""
        from EDlogger import logger
        current_level = logger.getEffectiveLevel()
        
        if current_level == 10:  # DEBUG
            logger.setLevel(20)  # INFO
            self.log_msg("Dev: Debug logging OFF")
        else:
            logger.setLevel(10)  # DEBUG
            self.log_msg("Dev: Debug logging ON")
    
    def _show_panel_state(self):
        """Show current panel states for debugging"""
        state_info = []
        
        # Waypoint panel state
        if self.waypoint_panel:
            wp_state = self._save_waypoint_panel_state()
            state_info.append("=== Waypoint Panel ===")
            for key, value in wp_state.items():
                state_info.append(f"{key}: {value}")
        
        # Settings panel state
        if self.settings_panel:
            state_info.append("\n=== Settings Panel ===")
            state_info.append(f"has_unsaved_changes: {getattr(self.config_manager, 'has_unsaved_changes', False)}")
        
        # Assist panel state
        if self.assist_panel:
            assist_state = self._save_assist_panel_state()
            state_info.append("\n=== Assist Panel ===")
            for assist_type, enabled in assist_state.get('assist_states', {}).items():
                state_info.append(f"{assist_type}: {enabled}")
        
        # Show in a dialog
        state_text = "\n".join(state_info)
        messagebox.showinfo("Panel State Debug", state_text)
    
    def _open_dev_console(self):
        """Open a development console window"""
        console = Toplevel(self.root)
        console.title("🧪 Dev Console")
        console.geometry("600x400")
        
        # Create text area for commands
        console_frame = Frame(console)
        console_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        Label(console_frame, text="Development Console - Python REPL", 
              font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        
        # Text widget for output
        output_text = tk.Text(console_frame, height=15, font=('Courier', 9))
        output_scrollbar = Scrollbar(console_frame, command=output_text.yview)
        output_text.configure(yscrollcommand=output_scrollbar.set)
        
        output_text.pack(side=LEFT, fill=BOTH, expand=True)
        output_scrollbar.pack(side=RIGHT, fill=Y)
        
        # Input frame
        input_frame = Frame(console)
        input_frame.pack(fill=X, padx=10, pady=5)
        
        Label(input_frame, text=">>> ").pack(side=LEFT)
        input_entry = Entry(input_frame)
        input_entry.pack(side=LEFT, fill=X, expand=True, padx=5)
        
        def execute_command(event=None):
            command = input_entry.get()
            if not command:
                return
            
            output_text.insert(END, f">>> {command}\n")
            
            try:
                # Create a safe namespace with access to main objects
                namespace = {
                    'app': self,
                    'ed_ap': self.ed_ap,
                    'waypoint_panel': self.waypoint_panel,
                    'settings_panel': self.settings_panel,
                    'assist_panel': self.assist_panel,
                    'config_manager': self.config_manager,
                    'logger': logger,
                }
                
                result = eval(command, namespace)
                if result is not None:
                    output_text.insert(END, f"{result}\n")
            except Exception as e:
                output_text.insert(END, f"Error: {e}\n")
            
            output_text.see(END)
            input_entry.delete(0, END)
        
        input_entry.bind('<Return>', execute_command)
        
        Button(input_frame, text="Execute", command=execute_command).pack(side=RIGHT)
        
        # Add some helpful info
        output_text.insert(END, "Available objects: app, ed_ap, waypoint_panel, settings_panel, assist_panel, config_manager, logger\n")
        output_text.insert(END, "Example commands:\n")
        output_text.insert(END, "  app.waypoint_panel.changed_waypoints\n")
        output_text.insert(END, "  ed_ap.config['SunBrightThreshold']\n")
        output_text.insert(END, "  logger.info('Hello from console')\n\n")
        
        input_entry.focus()
    
    def _force_save_all(self):
        """Force save all panels and configurations"""
        try:
            if self.config_manager:
                self.config_manager.save_all_settings()
            
            if self.waypoint_panel and hasattr(self.waypoint_panel, '_wp_editor_save'):
                self.waypoint_panel._wp_editor_save()
            
            logger.info("✅ Force save completed")
            self.log_msg("Dev: Force save completed")
            
        except Exception as e:
            logger.error(f"❌ Force save failed: {e}")
            messagebox.showerror("Save Error", f"Force save failed:\n{e}")
    
    def _validate_config_files(self):
        """Validate all configuration files"""
        issues = []
        
        try:
            # Check waypoint files
            waypoint_files = ['./waypoints/waypoints.json', './waypoints/completed.json', './waypoints/repeat.json']
            for file_path in waypoint_files:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            json.load(f)
                    except json.JSONDecodeError as e:
                        issues.append(f"Invalid JSON in {file_path}: {e}")
                else:
                    issues.append(f"Missing file: {file_path}")
            
            # Check ship configs
            ship_config_file = './configs/ship_configs.json'
            if os.path.exists(ship_config_file):
                try:
                    with open(ship_config_file, 'r') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    issues.append(f"Invalid JSON in {ship_config_file}: {e}")
            
            # Show results
            if issues:
                messagebox.showwarning("Config Validation", f"Found {len(issues)} issues:\n\n" + "\n".join(issues))
            else:
                messagebox.showinfo("Config Validation", "✅ All configuration files are valid!")
                
        except Exception as e:
            messagebox.showerror("Validation Error", f"Failed to validate configs:\n{e}")


def main():
    root = None
    try:
        root = tk.Tk()
        app = APGui(root)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"Startup Error: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        
        # Try to show error in GUI if possible
        if root is not None:
            try:
                messagebox.showerror("EDAPGui Startup Error", error_msg)
            except:
                pass
        
        # Always print to console and create error window
        print("=" * 60)
        print("EDAPGui STARTUP ERROR:")
        print("=" * 60)
        print(error_msg)
        print("=" * 60)
        
        # Create a simple error display window
        try:
            if root is None:
                root = tk.Tk()
            
            root.title("EDAPGui - Startup Error")
            root.geometry("800x600")
            
            # Create scrollable text widget
            text_frame = tk.Frame(root)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            error_text = tk.Text(text_frame, wrap=tk.WORD, font=('Courier', 10))
            scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=error_text.yview)
            error_text.configure(yscrollcommand=scrollbar.set)
            
            error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Insert error message
            error_text.insert(tk.END, "EDAPGui failed to start. Error details:\n\n")
            error_text.insert(tk.END, error_msg)
            error_text.insert(tk.END, "\n\nPossible solutions:\n")
            error_text.insert(tk.END, "1. Check that all required files are present\n")
            error_text.insert(tk.END, "2. Verify Python dependencies are installed\n")
            error_text.insert(tk.END, "3. Check for syntax errors in modified files\n")
            error_text.insert(tk.END, "4. Check the autopilot.log file for additional details\n")
            error_text.insert(tk.END, "5. Try reverting recent changes\n")
            error_text.config(state=tk.DISABLED)
            
            # Add buttons
            button_frame = tk.Frame(root)
            button_frame.pack(pady=10)
            
            tk.Button(button_frame, text="Copy Error to Clipboard", 
                     command=lambda: copy_to_clipboard(error_msg)).pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="Close", 
                     command=root.destroy).pack(side=tk.LEFT, padx=5)
            
            def copy_to_clipboard(text):
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
            
            root.mainloop()
            
        except Exception as display_error:
            print(f"Could not create error display window: {display_error}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()

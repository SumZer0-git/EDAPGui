import tkinter as tk
from tkinter import (
    BooleanVar, Button, Checkbutton, Entry, Frame, IntVar, Label, LabelFrame, 
    Radiobutton, Spinbox, StringVar, LEFT, END
)
from idlelib.tooltip import Hovertip


class SettingsPanel:
    """Panel for ship configuration, autopilot settings, and other configuration options"""
    
    def __init__(self, parent_frame, ed_ap, tooltips, entry_callback, check_callback):
        self.parent = parent_frame
        self.ed_ap = ed_ap
        self.tooltips = tooltips
        self.entry_callback = entry_callback
        self.check_callback = check_callback
        
        # Store references to GUI elements
        self.entries = {}
        self.checkboxvar = {}
        self.radiobuttonvar = {}
        
        # Display current active ship
        self.ship_filelabel = StringVar()
        self.ship_filelabel.set("Active Ship: <detecting...>")
        
        # Dependencies injected later
        self.config_manager = None
        self.hotkey_capture_callback = None
        
        self._create_settings_gui()
    
    def set_config_manager(self, config_manager):
        """Inject the config manager dependency"""
        self.config_manager = config_manager
    
    def set_hotkey_capture_callback(self, callback):
        """Inject the hotkey capture callback"""
        self.hotkey_capture_callback = callback
    
    def _create_settings_gui(self):
        """Create the settings panel GUI"""
        settings_main = tk.Frame(self.parent)
        settings_main.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        settings_main.columnconfigure([0], weight=1, minsize=100)

        # Ship configuration block
        self._create_ship_config_block(settings_main)
        
        # Additional settings block
        self._create_additional_settings_block(settings_main)
        
        # Settings buttons
        self._create_settings_buttons_block(settings_main)
    
    def _create_ship_config_block(self, parent):
        """Create ship configuration section"""
        blk_ship = LabelFrame(parent, text="SHIP CONFIGURATION")
        blk_ship.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        blk_ship.columnconfigure([0, 1], weight=1, minsize=120)
        
        # Ship parameter fields
        self.entries['ship'] = {}
        ship_fields = ('RollRate', 'PitchRate', 'YawRate')
        for i, field in enumerate(ship_fields):
            lbl = tk.Label(blk_ship, text=f"{field} (°/s):", anchor='w')
            lbl.grid(row=i, column=0, padx=2, pady=2, sticky="nsew")
            
            ent = tk.Spinbox(blk_ship, width=10, from_=0, to=1000, increment=0.5)
            ent.grid(row=i, column=1, padx=2, pady=2, sticky="nsew")
            ent.bind('<FocusOut>', self.entry_callback)
            ent.insert(0, "0")
            self.entries['ship'][field] = ent

        # Sun pitch up time setting
        lbl_sun_pitch_up = tk.Label(blk_ship, text='SunPitchUp +/- Time (s):', anchor='w')
        lbl_sun_pitch_up.grid(row=3, column=0, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up = tk.Spinbox(blk_ship, width=10, from_=-100, to=100, increment=0.5)
        spn_sun_pitch_up.grid(row=3, column=1, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up.bind('<FocusOut>', self.entry_callback)
        self.entries['ship']['SunPitchUp+Time'] = spn_sun_pitch_up

        # Test buttons for ship parameters
        blk_ship.columnconfigure([2], weight=1, minsize=80)
        btn_tst_roll = Button(blk_ship, text='Test', command=self.ed_ap.ship_tst_roll)
        btn_tst_roll.grid(row=0, column=2, padx=2, pady=2, sticky="news")
        btn_tst_pitch = Button(blk_ship, text='Test', command=self.ed_ap.ship_tst_pitch)
        btn_tst_pitch.grid(row=1, column=2, padx=2, pady=2, sticky="news")
        btn_tst_yaw = Button(blk_ship, text='Test', command=self.ed_ap.ship_tst_yaw)
        btn_tst_yaw.grid(row=2, column=2, padx=2, pady=2, sticky="news")

        # Active ship display and ship config file loading
        lbl_active_ship = Label(blk_ship, textvariable=self.ship_filelabel, 
                               relief="sunken", bg="lightgray")
        lbl_active_ship.grid(row=4, column=0, padx=2, pady=2, columnspan=2, sticky="news")
        
        btn_ship_file = Button(blk_ship, text="Load Ship File", command=self._open_ship_file)
        btn_ship_file.grid(row=4, column=2, padx=2, pady=2, sticky="news")
        tip_ship_file = Hovertip(btn_ship_file, self.tooltips['Ship Config Button'], hover_delay=1000)
    
    def _create_additional_settings_block(self, parent):
        """Create additional settings sections"""
        blk_settings = tk.Frame(parent)
        blk_settings.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        blk_settings.columnconfigure([0, 1], weight=1, minsize=100, uniform="group1")

        # Autopilot settings
        self._create_autopilot_settings(blk_settings)
        
        # Hotkey buttons settings
        self._create_buttons_settings(blk_settings)
        
        # Fuel settings
        self._create_fuel_settings(blk_settings)
        
        # Overlay settings
        self._create_overlay_settings(blk_settings)
        
        # Voice settings
        self._create_voice_settings(blk_settings)
        
        # Scanner settings
        self._create_scanner_settings(blk_settings)
        
        # Debug settings
        self._create_debug_settings(blk_settings)
    
    def _create_autopilot_settings(self, parent):
        """Create autopilot settings block"""
        blk_ap = LabelFrame(parent, text="AUTOPILOT")
        blk_ap.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        autopilot_entry_fields = ('Sun Bright Threshold', 'Nav Align Tries', 'Jump Tries', 
                                 'Docking Retries', 'Wait For Autodock')
        self.entries['autopilot'] = self._makeform(blk_ap, 'spinbox', autopilot_entry_fields)
        
        # Checkboxes
        self.checkboxvar['Enable Randomness'] = BooleanVar()
        cb_random = Checkbutton(blk_ap, text='Enable Randomness', anchor='w', pady=3, 
                               justify=LEFT, onvalue=1, offvalue=0, 
                               variable=self.checkboxvar['Enable Randomness'], 
                               command=lambda: self.check_callback('Enable Randomness'))
        cb_random.grid(row=5, column=0, columnspan=2, sticky="w")
        
        self.checkboxvar['Activate Elite for each key'] = BooleanVar()
        cb_activate_elite = Checkbutton(blk_ap, text='Activate Elite for each key', anchor='w', 
                                       pady=3, justify=LEFT, onvalue=1, offvalue=0, 
                                       variable=self.checkboxvar['Activate Elite for each key'], 
                                       command=lambda: self.check_callback('Activate Elite for each key'))
        cb_activate_elite.grid(row=6, column=0, columnspan=2, sticky="w")
        
        self.checkboxvar['Automatic logout'] = BooleanVar()
        cb_logout = Checkbutton(blk_ap, text='Automatic logout', anchor='w', pady=3, 
                               justify=LEFT, onvalue=1, offvalue=0, 
                               variable=self.checkboxvar['Automatic logout'], 
                               command=lambda: self.check_callback('Automatic logout'))
        cb_logout.grid(row=7, column=0, columnspan=2, sticky="w")
    
    def _create_buttons_settings(self, parent):
        """Create hotkey buttons settings block"""
        blk_buttons = LabelFrame(parent, text="BUTTONS")
        blk_buttons.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        # DSS Button radio buttons
        blk_dss = Frame(blk_buttons)
        blk_dss.grid(row=0, column=0, columnspan=2, padx=0, pady=0, sticky="nsew")
        lb_dss = Label(blk_dss, width=18, anchor='w', pady=3, text="DSS Button: ")
        lb_dss.grid(row=0, column=0, sticky="w")
        
        self.radiobuttonvar['dss_button'] = StringVar()
        rb_dss_primary = Radiobutton(blk_dss, pady=3, text="Primary", 
                                    variable=self.radiobuttonvar['dss_button'], value="Primary", 
                                    command=lambda: self.check_callback('dss_button'))
        rb_dss_primary.grid(row=0, column=1, sticky="w")
        rb_dss_secondary = Radiobutton(blk_dss, pady=3, text="Secondary", 
                                      variable=self.radiobuttonvar['dss_button'], value="Secondary", 
                                      command=lambda: self.check_callback('dss_button'))
        rb_dss_secondary.grid(row=1, column=1, sticky="w")
        
        # Hotkey capture buttons
        self.entries['buttons'] = {}
        buttons_entry_fields = ('Start FSD', 'Start SC', 'Start Robigo', 'Start Waypoint', 'Stop All', 'Pause/Resume')
        for i, field in enumerate(buttons_entry_fields):
            row = tk.Frame(blk_buttons)
            row.grid(row=i+2, column=0, padx=2, pady=2, sticky="nsew")
            
            lab = tk.Label(row, anchor='w', width=20, pady=3, text=field + ": ")
            lab.grid(row=0, column=0)
            
            # Create hotkey capture button
            btn = tk.Button(row, width=15, text="Click to set...", 
                           command=lambda f=field: self._capture_hotkey(f))
            btn.grid(row=0, column=1)
            self.entries['buttons'][field] = btn
            
            # Add tooltip
            tip = Hovertip(row, self.tooltips[field], hover_delay=1000)
    
    def _create_fuel_settings(self, parent):
        """Create fuel settings block"""
        blk_fuel = LabelFrame(parent, text="FUEL")
        blk_fuel.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")
        refuel_entry_fields = ('Refuel Threshold', 'Scoop Timeout', 'Fuel Threshold Abort')
        self.entries['refuel'] = self._makeform(blk_fuel, 'spinbox', refuel_entry_fields)
    
    def _create_overlay_settings(self, parent):
        """Create overlay settings block"""
        blk_overlay = LabelFrame(parent, text="OVERLAY")
        blk_overlay.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")
        
        self.checkboxvar['Enable Overlay'] = BooleanVar()
        cb_enable = Checkbutton(blk_overlay, text='Enable (requires restart)', onvalue=1, offvalue=0, 
                               anchor='w', pady=3, justify=LEFT, 
                               variable=self.checkboxvar['Enable Overlay'], 
                               command=lambda: self.check_callback('Enable Overlay'))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")
        
        overlay_entry_fields = ('X Offset', 'Y Offset', 'Font Size')
        self.entries['overlay'] = self._makeform(blk_overlay, 'spinbox', overlay_entry_fields, 1, 1, 0, 3000)
    
    def _create_voice_settings(self, parent):
        """Create voice settings block"""
        blk_voice = LabelFrame(parent, text="VOICE")
        blk_voice.grid(row=2, column=0, padx=2, pady=2, sticky="nsew")
        
        self.checkboxvar['Enable Voice'] = BooleanVar()
        cb_enable = Checkbutton(blk_voice, text='Enable', onvalue=1, offvalue=0, 
                               anchor='w', pady=3, justify=LEFT, 
                               variable=self.checkboxvar['Enable Voice'], 
                               command=lambda: self.check_callback('Enable Voice'))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")
    
    def _create_scanner_settings(self, parent):
        """Create scanner settings block"""
        blk_scanner = LabelFrame(parent, text="ELW SCANNER")
        blk_scanner.grid(row=2, column=1, padx=2, pady=2, sticky="nsew")
        
        self.checkboxvar['ELW Scanner'] = BooleanVar()
        cb_enable = Checkbutton(blk_scanner, text='Enable', onvalue=1, offvalue=0, 
                               anchor='w', pady=3, justify=LEFT, 
                               variable=self.checkboxvar['ELW Scanner'], 
                               command=lambda: self.check_callback('ELW Scanner'))
        cb_enable.grid(row=0, column=0, columnspan=2, sticky="w")
    
    def _create_debug_settings(self, parent):
        """Create debug settings block"""
        blk_debug = LabelFrame(parent, text="DEBUG & LOGGING")
        blk_debug.grid(row=3, column=0, padx=2, pady=2, sticky="nsew")
        blk_debug.columnconfigure([0, 1, 2], weight=1, minsize=50)
        
        lbl_debug = tk.Label(blk_debug, text='Debug Level:', anchor='w')
        lbl_debug.grid(row=0, column=0, pady=3, sticky="nsew")
        
        self.radiobuttonvar['debug_mode'] = StringVar()
        rb_debug_error = Radiobutton(blk_debug, text="Error", 
                                    variable=self.radiobuttonvar['debug_mode'], value="Error", 
                                    command=lambda: self.check_callback('debug_mode'))
        rb_debug_error.grid(row=0, column=1, sticky="w")
        rb_debug_info = Radiobutton(blk_debug, text="Info", 
                                   variable=self.radiobuttonvar['debug_mode'], value="Info", 
                                   command=lambda: self.check_callback('debug_mode'))
        rb_debug_info.grid(row=1, column=1, sticky="w")
        rb_debug_debug = Radiobutton(blk_debug, text="Debug", 
                                    variable=self.radiobuttonvar['debug_mode'], value="Debug", 
                                    command=lambda: self.check_callback('debug_mode'))
        rb_debug_debug.grid(row=1, column=2, sticky="w")

        # Log file access
        blk_logfile = LabelFrame(parent, text="LOG FILE")
        blk_logfile.grid(row=3, column=1, padx=2, pady=2, sticky="nsew")
        btn_open_logfile = Button(blk_logfile, text='Open Log File', command=self._open_logfile)
        btn_open_logfile.grid(row=0, column=0, padx=2, pady=2, sticky="news")
    
    def _create_settings_buttons_block(self, parent):
        """Create save/revert buttons"""
        blk_settings_buttons = tk.Frame(parent)
        blk_settings_buttons.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")
        blk_settings_buttons.columnconfigure([0, 1], weight=1, minsize=100)
        
        self.save_button = Button(blk_settings_buttons, text='Save All Settings', 
                                 command=self._save_settings)
        self.save_button.grid(row=0, column=0, padx=2, pady=2, sticky="news")
        
        self.revert_button = Button(blk_settings_buttons, text='Revert Changes', 
                                   command=self._revert_all_changes,
                                   state='disabled', bg='SystemButtonFace')
        self.revert_button.grid(row=0, column=1, padx=2, pady=2, sticky="news")
    
    def _makeform(self, win, ftype, fields, r=0, inc=1, rfrom=0, rto=1000):
        """Create form fields"""
        entries = {}
        
        for field in fields:
            row = tk.Frame(win)
            row.grid(row=r, column=0, padx=2, pady=2, sticky="nsew")
            r += 1

            lab = tk.Label(row, anchor='w', width=20, pady=3, text=field + ": ")
            if ftype == 'spinbox':
                ent = tk.Spinbox(row, width=10, from_=rfrom, to=rto, increment=inc)
            else:
                ent = tk.Entry(row, width=10)
            ent.bind('<FocusOut>', self.entry_callback)
            ent.insert(0, "0")

            lab.grid(row=0, column=0)
            ent.grid(row=0, column=1)
            entries[field] = ent
            
            # Add tooltip
            tip = Hovertip(row, self.tooltips[field], hover_delay=1000)

        return entries
    
    def _open_ship_file(self):
        """Open ship configuration file using the injected config manager"""
        if self.config_manager:
            return self.config_manager.open_ship_file()
        else:
            from EDlogger import logger
            logger.warning("Config manager not available for ship file loading")
            return False
    
    def _capture_hotkey(self, field_name):
        """Capture hotkey for button using the injected callback"""
        if self.hotkey_capture_callback:
            self.hotkey_capture_callback(field_name)
        else:
            from EDlogger import logger
            logger.warning("Hotkey capture callback not available")
    
    def _open_logfile(self):
        """Open log file"""
        import os
        os.startfile('autopilot.log')
    
    def _save_settings(self):
        """Save all settings - placeholder for now"""
        # This would need to be implemented with save logic
        pass
    
    def _revert_all_changes(self):
        """Revert all changes - placeholder for now"""
        # This would need to be implemented with revert logic
        pass
    
    def update_ship_display(self):
        """Update ship configuration display"""
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, self.ed_ap.pitchrate)
        self.entries['ship']['RollRate'].insert(0, self.ed_ap.rollrate)
        self.entries['ship']['YawRate'].insert(0, self.ed_ap.yawrate)
        self.entries['ship']['SunPitchUp+Time'].insert(0, self.ed_ap.sunpitchuptime)
        
        # Update active ship display with Default/Custom status
        if hasattr(self.ed_ap, 'current_ship_type') and self.ed_ap.current_ship_type:
            ship_name = self.ed_ap.current_ship_type
            config_type = "Custom" if getattr(self.ed_ap, 'using_custom_ship_config', False) else "Default"
            self.ship_filelabel.set(f"Active Ship: {ship_name} ({config_type})")
        else:
            self.ship_filelabel.set("Active Ship: <detecting...>")
    
    def initialize_values(self):
        """Initialize field values from configuration"""
        # Ship configuration
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, float(self.ed_ap.pitchrate))
        self.entries['ship']['RollRate'].insert(0, float(self.ed_ap.rollrate))
        self.entries['ship']['YawRate'].insert(0, float(self.ed_ap.yawrate))
        self.entries['ship']['SunPitchUp+Time'].insert(0, float(self.ed_ap.sunpitchuptime))
        
        # Update ship display with Default/Custom status
        if hasattr(self.ed_ap, 'current_ship_type') and self.ed_ap.current_ship_type:
            ship_name = self.ed_ap.current_ship_type
            config_type = "Custom" if getattr(self.ed_ap, 'using_custom_ship_config', False) else "Default"
            self.ship_filelabel.set(f"Active Ship: {ship_name} ({config_type})")
        else:
            self.ship_filelabel.set("Active Ship: <detecting...>")

        # Autopilot settings
        self.entries['autopilot']['Sun Bright Threshold'].delete(0, END)
        self.entries['autopilot']['Nav Align Tries'].delete(0, END)
        self.entries['autopilot']['Jump Tries'].delete(0, END)
        self.entries['autopilot']['Docking Retries'].delete(0, END)
        self.entries['autopilot']['Wait For Autodock'].delete(0, END)

        self.entries['autopilot']['Sun Bright Threshold'].insert(0, int(self.ed_ap.config['SunBrightThreshold']))
        self.entries['autopilot']['Nav Align Tries'].insert(0, int(self.ed_ap.config['NavAlignTries']))
        self.entries['autopilot']['Jump Tries'].insert(0, int(self.ed_ap.config['JumpTries']))
        self.entries['autopilot']['Docking Retries'].insert(0, int(self.ed_ap.config['DockingRetries']))
        self.entries['autopilot']['Wait For Autodock'].insert(0, int(self.ed_ap.config['WaitForAutoDockTimer']))
        
        # Refuel settings
        self.entries['refuel']['Refuel Threshold'].delete(0, END)
        self.entries['refuel']['Scoop Timeout'].delete(0, END)
        self.entries['refuel']['Fuel Threshold Abort'].delete(0, END)
        
        self.entries['refuel']['Refuel Threshold'].insert(0, int(self.ed_ap.config['RefuelThreshold']))
        self.entries['refuel']['Scoop Timeout'].insert(0, int(self.ed_ap.config['FuelScoopTimeOut']))
        self.entries['refuel']['Fuel Threshold Abort'].insert(0, int(self.ed_ap.config['FuelThreasholdAbortAP']))
        
        # Overlay settings
        self.entries['overlay']['X Offset'].delete(0, END)
        self.entries['overlay']['Y Offset'].delete(0, END)
        self.entries['overlay']['Font Size'].delete(0, END)
        
        self.entries['overlay']['X Offset'].insert(0, int(self.ed_ap.config['OverlayTextXOffset']))
        self.entries['overlay']['Y Offset'].insert(0, int(self.ed_ap.config['OverlayTextYOffset']))
        self.entries['overlay']['Font Size'].insert(0, int(self.ed_ap.config['OverlayTextFontSize']))

        # Checkboxes
        self.checkboxvar['Enable Randomness'].set(self.ed_ap.config['EnableRandomness'])
        self.checkboxvar['Activate Elite for each key'].set(self.ed_ap.config['ActivateEliteEachKey'])
        self.checkboxvar['Automatic logout'].set(self.ed_ap.config['AutomaticLogout'])
        self.checkboxvar['Enable Overlay'].set(self.ed_ap.config['OverlayTextEnable'])
        self.checkboxvar['Enable Voice'].set(self.ed_ap.config['VoiceEnable'])

        # Radio buttons
        self.radiobuttonvar['dss_button'].set(self.ed_ap.config['DSSButton'])
        
        if self.ed_ap.config['LogDEBUG']:
            self.radiobuttonvar['debug_mode'].set("Debug")
        elif self.ed_ap.config['LogINFO']:
            self.radiobuttonvar['debug_mode'].set("Info")
        else:
            self.radiobuttonvar['debug_mode'].set("Error")

        # Hotkey buttons
        self.entries['buttons']['Start FSD'].config(text=str(self.ed_ap.config['HotKey_StartFSD']))
        self.entries['buttons']['Start SC'].config(text=str(self.ed_ap.config['HotKey_StartSC']))
        self.entries['buttons']['Start Robigo'].config(text=str(self.ed_ap.config['HotKey_StartRobigo']))
        self.entries['buttons']['Start Waypoint'].config(text=str(self.ed_ap.config['HotKey_StartWaypoint']))
        self.entries['buttons']['Stop All'].config(text=str(self.ed_ap.config['HotKey_StopAllAssists']))
        self.entries['buttons']['Pause/Resume'].config(text=str(self.ed_ap.config['HotKey_PauseResume']))

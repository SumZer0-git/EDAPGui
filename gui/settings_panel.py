import tkinter as tk
from tkinter import (
    BooleanVar, Button, Checkbutton, Entry, Frame, IntVar, Label, LabelFrame, 
    Radiobutton, Spinbox, StringVar, LEFT, END
)
from tkinter.ttk import Combobox
import os
import glob
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
    
    def set_button_commands(self, save_command, revert_command):
        """Inject save and revert button commands"""
        self.save_button.config(command=save_command)
        self.revert_button.config(command=revert_command)
    
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
        # Simple header without ship name
        self.blk_ship = LabelFrame(parent, text="SHIP CONFIGURATION")
        self.blk_ship.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.blk_ship.columnconfigure([0, 1], weight=1, minsize=120)
        self.blk_ship.columnconfigure([2], weight=0, minsize=80)
        
        # Active ship and configuration status
        self.active_ship_var = StringVar()
        self.active_ship_var.set("Active Ship: <detecting...>")
        lbl_active_ship = tk.Label(self.blk_ship, textvariable=self.active_ship_var, 
                                  anchor='w', font=("TkDefaultFont", 9, "bold"))
        lbl_active_ship.grid(row=0, column=0, padx=2, pady=1, columnspan=4, sticky="nsew")
        
        self.config_type_var = StringVar()
        self.config_type_var.set("Configuration: Default")
        lbl_config_type = tk.Label(self.blk_ship, textvariable=self.config_type_var, 
                                  anchor='w', font=("TkDefaultFont", 8))
        lbl_config_type.grid(row=1, column=0, padx=2, pady=1, columnspan=4, sticky="nsew")
        
        # Configuration source selector
        lbl_config = tk.Label(self.blk_ship, text="Config:", anchor='w')
        lbl_config.grid(row=2, column=0, padx=2, pady=2, sticky="nsew")
        
        self.ship_config_var = StringVar()
        self.ship_config_dropdown = Combobox(self.blk_ship, textvariable=self.ship_config_var, 
                                           state="readonly", width=15)
        self.ship_config_dropdown.grid(row=2, column=1, padx=2, pady=2, sticky="nsew")
        self.ship_config_dropdown.bind('<<ComboboxSelected>>', self._on_config_selected)
        
        # Store reference for color updates
        self.ship_config_dropdown.configure(foreground="black")
        
        # Reset to defaults button
        self.reset_button = Button(self.blk_ship, text='Delete', command=self._reset_to_defaults, # Removes config from ship_configs.json
                                  bg='lightcoral', width=8)
        self.reset_button.grid(row=2, column=2, padx=2, pady=2, sticky="nsew")
        Hovertip(self.reset_button, "Reset current ship to default values", hover_delay=500)
        
        # Status label for config matching
        self.config_status_var = StringVar()
        self.config_status_var.set("")
        self.lbl_status = tk.Label(self.blk_ship, textvariable=self.config_status_var, 
                                  anchor='w', fg="blue", font=("TkDefaultFont", 8))
        self.lbl_status.grid(row=3, column=0, padx=2, pady=1, columnspan=4, sticky="nsew")
        
        # Ship parameter fields with tooltips
        self.entries['ship'] = {}
        ship_fields = {
            'RollRate': 'How fast your ship rotates left/right around its central axis (degrees per second)',
            'PitchRate': 'How fast your ship rotates up/down (degrees per second)', 
            'YawRate': 'How fast your ship turns left/right horizontally (degrees per second)'
        }
        
        for i, (field, tooltip_text) in enumerate(ship_fields.items()):
            row = i + 4  # Start after ship info, config selector and status
            lbl = tk.Label(self.blk_ship, text=f"{field} (°/s):", anchor='w')
            lbl.grid(row=row, column=0, padx=2, pady=2, sticky="nsew")
            
            ent = tk.Spinbox(self.blk_ship, width=10, from_=0, to=1000, increment=0.5)
            ent.grid(row=row, column=1, padx=2, pady=2, sticky="nsew")
            ent.bind('<FocusOut>', self.entry_callback)
            ent.insert(0, "0")
            self.entries['ship'][field] = ent
            
            # Add tooltip to the label
            Hovertip(lbl, tooltip_text, hover_delay=500)

        # Sun pitch up time setting
        lbl_sun_pitch_up = tk.Label(self.blk_ship, text='SunPitchUp +/- Time (s):', anchor='w')
        lbl_sun_pitch_up.grid(row=7, column=0, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up = tk.Spinbox(self.blk_ship, width=10, from_=-100, to=100, increment=0.5)
        spn_sun_pitch_up.grid(row=7, column=1, padx=2, pady=3, sticky="nsew")
        spn_sun_pitch_up.bind('<FocusOut>', self.entry_callback)
        self.entries['ship']['SunPitchUp+Time'] = spn_sun_pitch_up
        
        # Add tooltip for sun pitch up time
        Hovertip(lbl_sun_pitch_up, "Time adjustment for pitching up when too close to a star (seconds)", hover_delay=500)

        # Test buttons for ship parameters
        self.blk_ship.columnconfigure([3], weight=1, minsize=80)
        btn_tst_roll = Button(self.blk_ship, text='Test', command=self.ed_ap.ship_tst_roll)
        btn_tst_roll.grid(row=4, column=3, padx=2, pady=2, sticky="news")
        btn_tst_pitch = Button(self.blk_ship, text='Test', command=self.ed_ap.ship_tst_pitch)
        btn_tst_pitch.grid(row=5, column=3, padx=2, pady=2, sticky="news")
        btn_tst_yaw = Button(self.blk_ship, text='Test', command=self.ed_ap.ship_tst_yaw)
        btn_tst_yaw.grid(row=6, column=3, padx=2, pady=2, sticky="news")

        
        # Initialize dropdown options
        self._populate_config_dropdown()
    
    def _get_ship_display_name(self, ship_type):
        """Convert internal ship type to proper display name using existing EDAP_data"""
        try:
            from EDAP_data import ship_name_map
            return ship_name_map.get(ship_type, ship_type.replace('-', ' ').replace('_', ' ').title())
        except ImportError:
            # Fallback to automatic conversion if EDAP_data not available
            return ship_type.replace('-', ' ').replace('_', ' ').title()
    
    def _get_ship_internal_name(self, display_name):
        """Convert display name back to internal ship type using existing EDAP_data"""
        try:
            from EDAP_data import ship_name_map
            # Create reverse mapping from display names to internal names
            reverse_map = {v: k for k, v in ship_name_map.items()}
            return reverse_map.get(display_name, display_name.lower().replace(' ', '_').replace('-', '_'))
        except ImportError:
            # Fallback to automatic conversion if EDAP_data not available  
            return display_name.lower().replace(' ', '_').replace('-', '_')
    
    def _get_ship_file_name(self, ship_type):
        """Convert internal ship type to ship file name - only for ships that don't follow automatic pattern"""
        # Only include ships that need special file name mapping
        file_name_mapping = {
            'cobramkv': 'cobra-mk5',
            'federation_corvette': 'fed-corvette', 
            'type8': 'type-8',
        }
        return file_name_mapping.get(ship_type, ship_type.replace('_', '-'))
    
    def _ship_has_config_file(self, ship_type):
        """Check if ship has a config file in ships/ directory"""
        file_name = self._get_ship_file_name(ship_type)
        return os.path.exists(f"./ships/{file_name}.json")
    
    def _ship_has_custom_config(self, ship_type):
        """Check if ship has custom config saved in ship_configs.json"""
        if not hasattr(self.ed_ap, 'ship_configs'):
            return False
        
        ship_configs = self.ed_ap.ship_configs.get('Ship_Configs', {})
        if ship_type not in ship_configs:
            return False
        
        # Check if the config is not empty - empty configs {} don't count as custom
        config = ship_configs[ship_type]
        return bool(config and any(config.values()))
    
    def _populate_config_dropdown(self):
        """Populate the ship config dropdown with available options"""
        current_ship = getattr(self.ed_ap, 'current_ship_type', '')
        
        if not current_ship:
            self.ship_config_dropdown['values'] = ["Custom"]
            self.ship_config_var.set("Custom")
            return
        
        ship_display = self._get_ship_display_name(current_ship)
        options = []
        
        # Current ship section - conditionally add options based on what exists
        has_config_file = self._ship_has_config_file(current_ship)
        has_custom_config = self._ship_has_custom_config(current_ship)
        
        if has_custom_config:
            options.append(f"{ship_display} (Custom)")
        
        if has_config_file:
            options.append(f"{ship_display} (Default)")
        elif not has_custom_config:
            # No config file and no custom - show as default (uses hardcoded values)
            options.append(f"{ship_display} (Default)")
        
        # Separator for templates
        options.append("── Templates ──")
        
        # Add other ship files as templates
        ship_files = glob.glob("./ships/*.json")
        for ship_file in sorted(ship_files):
            ship_name = os.path.splitext(os.path.basename(ship_file))[0]
            # Skip current ship - already added above
            if ship_name == current_ship:
                continue
            # Convert file names to display names using mapping
            display_name = self._get_ship_display_name(ship_name)
            options.append(display_name)
        
        self.ship_config_dropdown['values'] = options
        
        # Set selection based on actual configuration state
        if has_custom_config and hasattr(self.ed_ap, 'using_custom_ship_config') and self.ed_ap.using_custom_ship_config:
            self.ship_config_var.set(f"{ship_display} (Custom)")
        else:
            self.ship_config_var.set(f"{ship_display} (Default)")
        
        # Update color coding
        self._update_dropdown_colors()
    
    def _update_dropdown_colors(self):
        """Reset dropdown to default colors (no special color coding)"""
        try:
            if hasattr(self, 'ship_config_dropdown'):
                # Always use default color
                self.ship_config_dropdown.configure(foreground="black")
        except Exception as e:
            # Defensive programming - don't let color updates break the app
            from EDlogger import logger
            logger.debug(f"Error updating dropdown colors: {e}")
    
    def _on_config_selected(self, event):
        """Handle ship config dropdown selection"""
        selected = self.ship_config_var.get()
        current_ship = getattr(self.ed_ap, 'current_ship_type', '')
        
        # Skip separator selections
        if selected == "── Templates ──":
            # Revert to previous selection based on actual state
            ship_display = self._get_ship_display_name(current_ship)
            has_custom_config = self._ship_has_custom_config(current_ship)
            if has_custom_config and hasattr(self.ed_ap, 'using_custom_ship_config') and self.ed_ap.using_custom_ship_config:
                self.ship_config_var.set(f"{ship_display} (Custom)")
            else:
                self.ship_config_var.set(f"{ship_display} (Default)")
            return
        
        # Wrap entire config switching in programmatic update context to prevent false change detection
        programmatic_context = None
        if self.config_manager and hasattr(self.config_manager, 'programmatic_update_context'):
            programmatic_context = self.config_manager.programmatic_update_context
        
        if programmatic_context:
            with programmatic_context():
                self._perform_config_switch(selected, current_ship)
                # Capture new baseline inside programmatic context after config switch is complete
                if self.config_manager:
                    self.config_manager.capture_original_values()
        else:
            self._perform_config_switch(selected, current_ship)
            # Capture new baseline after config switch is complete
            if self.config_manager:
                self.config_manager.capture_original_values()
    
    def _perform_config_switch(self, selected, current_ship):
        """Perform the actual config switching logic"""
        if selected.endswith(" (Custom)"):
            # Load custom config for current ship from ship_configs.json
            if current_ship:
                self.ed_ap.load_ship_configuration(current_ship)
                self.update_ship_display()
        elif selected.endswith(" (Default)"):
            # Load current ship's default configuration
            if current_ship:
                # Force loading defaults, bypassing custom config in ship_configs.json
                self.ed_ap.using_custom_ship_config = False
                self.ed_ap.load_ship_configuration(current_ship, force_defaults=True)
                
                # Update GUI to show we're now using defaults
                self.update_ship_display()
        else:
            # Load template from another ship - convert display name back to file name
            ship_internal_name = self._get_ship_internal_name(selected)
            ship_file_name = self._get_ship_file_name(ship_internal_name)
            self._load_ship_template(ship_file_name)
            self._update_config_status()
        
        # Update colors after selection change
        self._update_dropdown_colors()
    
    def refresh_config_status(self):
        """Refresh configuration status display - called when changes are detected"""
        if hasattr(self.ed_ap, 'current_ship_type') and self.ed_ap.current_ship_type:
            ship_name = self._get_ship_display_name(self.ed_ap.current_ship_type)
            self.active_ship_var.set(f"Active Ship: {ship_name}")
            
            # Show configuration type with modification indicator
            config_type = "Custom" if getattr(self.ed_ap, 'using_custom_ship_config', False) else "Default"
            has_unsaved = getattr(self.config_manager, 'has_unsaved_changes', False) if self.config_manager else False
            modification_indicator = " (modified*)" if has_unsaved else ""
            self.config_type_var.set(f"Configuration: {config_type}{modification_indicator}")
    
    def _load_ship_template(self, ship_file_name):
        """Load ship default values as template without affecting custom flags"""
        from file_utils import read_json_file
        
        # First try the ship file
        ship_file_path = f"./ships/{ship_file_name}.json"
        if os.path.exists(ship_file_path):
            try:
                ship_defaults = read_json_file(ship_file_path)
                
                # Load values directly into GUI fields only
                self.entries['ship']['PitchRate'].delete(0, END)
                self.entries['ship']['RollRate'].delete(0, END)
                self.entries['ship']['YawRate'].delete(0, END)
                self.entries['ship']['SunPitchUp+Time'].delete(0, END)

                self.entries['ship']['PitchRate'].insert(0, ship_defaults.get('pitchrate', 33.0))
                self.entries['ship']['RollRate'].insert(0, ship_defaults.get('rollrate', 80.0))
                self.entries['ship']['YawRate'].insert(0, ship_defaults.get('yawrate', 8.0))
                self.entries['ship']['SunPitchUp+Time'].insert(0, ship_defaults.get('SunPitchUp+Time', 0.0))
                
                # Update internal values for immediate effect (but don't save yet)
                self.ed_ap.rollrate = float(ship_defaults.get('rollrate', 80.0))
                self.ed_ap.pitchrate = float(ship_defaults.get('pitchrate', 33.0))
                self.ed_ap.yawrate = float(ship_defaults.get('yawrate', 8.0))
                self.ed_ap.sunpitchuptime = float(ship_defaults.get('SunPitchUp+Time', 0.0))
                
                # Template loaded - will be marked as modified only when user actually changes values
                
                return True
                
            except Exception as e:
                from EDlogger import logger
                logger.warning(f"Error loading ship template {ship_file_path}: {e}")
        
        # Fallback to hardcoded defaults
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, 33.0)
        self.entries['ship']['RollRate'].insert(0, 80.0)
        self.entries['ship']['YawRate'].insert(0, 8.0)
        self.entries['ship']['SunPitchUp+Time'].insert(0, 0.0)
        
        # Update internal values
        self.ed_ap.rollrate = 80.0
        self.ed_ap.pitchrate = 33.0
        self.ed_ap.yawrate = 8.0
        self.ed_ap.sunpitchuptime = 0.0
        
        # Mark as having unsaved changes since we loaded fallback defaults
        if self.config_manager:
            self.config_manager.mark_unsaved_changes()
        
        return False
    
    def _update_config_status(self):
        """Update the status text based on current config vs current ship"""
        selected = self.ship_config_var.get()
        current_ship = getattr(self.ed_ap, 'current_ship_type', '')
        
        if not current_ship:
            self.config_status_var.set("")
            return
            
        if selected.endswith(" (Custom)") or selected.endswith(" (Default)"):
            # For current ship configs, no status message needed
            self.config_status_var.set("")
            self.lbl_status.config(fg="blue")  # Reset to default color
        elif selected == "── Templates ──":
            # Skip separator
            self.config_status_var.set("")
            self.lbl_status.config(fg="blue")  # Reset to default color
        else:
            # Template from another ship - check if it matches current ship
            template_ship_display = selected
            current_ship_display = current_ship.replace('_', ' ').title()
            template_ship_file = selected.lower().replace(' ', '_')
            
            # Set the message
            message = f"Using {template_ship_display} settings as template for {current_ship_display}"
            self.config_status_var.set(message)
            
            # Color the text based on whether template matches current ship
            if template_ship_file == current_ship:
                # Green for matching ship template
                self.lbl_status.config(fg="green")
            else:
                # Red for different ship template
                self.lbl_status.config(fg="red")
    
    def _reset_to_defaults(self):
        """Reset current ship to default values"""
        current_ship = getattr(self.ed_ap, 'current_ship_type', '')
        if not current_ship:
            from tkinter import messagebox
            messagebox.showwarning("No Ship Detected", "Cannot reset - no active ship detected.")
            return
        
        # Confirm reset action
        from tkinter import messagebox
        ship_display = self._get_ship_display_name(current_ship)
        result = messagebox.askyesno(
            "Reset to Defaults", 
            f"Reset {ship_display} to default values?\\n\\nThis will clear any custom modifications.",
            icon="warning"
        )
        if not result:
            return
        
        try:
            # Clear custom config from ship_configs.json if it exists
            if current_ship in self.ed_ap.ship_configs.get('Ship_Configs', {}):
                del self.ed_ap.ship_configs['Ship_Configs'][current_ship]
                self.ed_ap.write_ship_configs(self.ed_ap.ship_configs)
            
            # Reload ship configuration (will load defaults)
            self.ed_ap.load_ship_configuration(current_ship)
            
            # Update GUI
            self.update_ship_display()
            
            # Clear unsaved changes since the reset was completed and saved immediately
            if self.config_manager:
                self.config_manager.clear_unsaved_changes()
                
            from EDlogger import logger
            logger.info(f"Reset {current_ship} to default configuration")
            
        except Exception as e:
            from EDlogger import logger
            logger.error(f"Error resetting ship to defaults: {e}")
            messagebox.showerror("Reset Error", f"Failed to reset ship configuration: {e}")
    
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
        
        # Create buttons without commands - commands will be injected by main GUI
        self.save_button = Button(blk_settings_buttons, text='Save All Settings')
        self.save_button.grid(row=0, column=0, padx=2, pady=2, sticky="news")
        
        self.revert_button = Button(blk_settings_buttons, text='Revert Changes', 
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
    
    
    def update_ship_display(self):
        """Update ship configuration display and GUI fields from internal ed_ap state"""
        self._refresh_all_ship_ui()
        
    def initialize_values(self):
        """Initialize field values from configuration - alias for update_ship_display"""
        self._refresh_all_ship_ui()
    
    def _refresh_all_ship_ui(self):
        """Update all ship-related GUI elements from ed_ap internal state"""
        from EDlogger import logger
        
        logger.debug(f"SettingsPanel: refreshing ship UI")
        logger.debug(f"SettingsPanel: ed_ap.current_ship_type = '{getattr(self.ed_ap, 'current_ship_type', 'NONE')}'")
        logger.debug(f"SettingsPanel: ed_ap.using_custom_ship_config = {getattr(self.ed_ap, 'using_custom_ship_config', 'NONE')}")
        logger.debug(f"SettingsPanel: Ship rates - Roll={getattr(self.ed_ap, 'rollrate', 'NONE')}, Pitch={getattr(self.ed_ap, 'pitchrate', 'NONE')}, Yaw={getattr(self.ed_ap, 'yawrate', 'NONE')}")
        
        # Update ship parameter fields using context manager to prevent change detection
        if (self.config_manager and 
            hasattr(self.config_manager, 'programmatic_update_context') and 
            self.config_manager.programmatic_update_context):
            with self.config_manager.programmatic_update_context():
                self._update_ship_entry_fields()
        else:
            self._update_ship_entry_fields()
        
        # Update all other ship UI elements
        self._update_ship_info_display()
        self._populate_config_dropdown()
        self._update_config_status()
    
    def _update_ship_entry_fields(self):
        """Update the ship parameter entry fields with current ed_ap values"""
        self.entries['ship']['PitchRate'].delete(0, END)
        self.entries['ship']['RollRate'].delete(0, END)
        self.entries['ship']['YawRate'].delete(0, END)
        self.entries['ship']['SunPitchUp+Time'].delete(0, END)

        self.entries['ship']['PitchRate'].insert(0, self.ed_ap.pitchrate)
        self.entries['ship']['RollRate'].insert(0, self.ed_ap.rollrate)
        self.entries['ship']['YawRate'].insert(0, self.ed_ap.yawrate)
        self.entries['ship']['SunPitchUp+Time'].insert(0, self.ed_ap.sunpitchuptime)
    
    def _update_ship_info_display(self):
        """Update the ship name and configuration type display"""
        if hasattr(self.ed_ap, 'current_ship_type') and self.ed_ap.current_ship_type:
            ship_name = self._get_ship_display_name(self.ed_ap.current_ship_type)
            self.active_ship_var.set(f"Active Ship: {ship_name}")
            
            # Show configuration type with modification indicator
            config_type = "Custom" if getattr(self.ed_ap, 'using_custom_ship_config', False) else "Default"
            has_unsaved = getattr(self.config_manager, 'has_unsaved_changes', False) if self.config_manager else False
            modification_indicator = " (modified*)" if has_unsaved else ""
            self.config_type_var.set(f"Configuration: {config_type}{modification_indicator}")
        else:
            self.active_ship_var.set("Active Ship: <detecting...>")
            self.config_type_var.set("Configuration: Unknown")
    
    def initialize_all_values(self):
        """Initialize all field values from configuration - both ship and non-ship settings"""
        # Initialize ship values
        self._refresh_all_ship_ui()
        
        # Initialize non-ship values
        self._initialize_non_ship_values()
    
    def _initialize_non_ship_values(self):
        """Initialize autopilot, fuel, overlay, and other non-ship configuration values"""
        # Use context manager to prevent change detection
        if (self.config_manager and 
            hasattr(self.config_manager, 'programmatic_update_context') and 
            self.config_manager.programmatic_update_context):
            with self.config_manager.programmatic_update_context():
                self._set_non_ship_field_values()
        else:
            self._set_non_ship_field_values()
    
    def _set_non_ship_field_values(self):
        """Set the actual field values for non-ship settings"""
        # Autopilot settings
        if 'autopilot' in self.entries:
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
        if 'refuel' in self.entries:
            self.entries['refuel']['Refuel Threshold'].delete(0, END)
            self.entries['refuel']['Scoop Timeout'].delete(0, END)
            self.entries['refuel']['Fuel Threshold Abort'].delete(0, END)
            
            self.entries['refuel']['Refuel Threshold'].insert(0, int(self.ed_ap.config['RefuelThreshold']))
            self.entries['refuel']['Scoop Timeout'].insert(0, int(self.ed_ap.config['FuelScoopTimeOut']))
            self.entries['refuel']['Fuel Threshold Abort'].insert(0, int(self.ed_ap.config['FuelThreasholdAbortAP']))
        
        # Overlay settings
        if 'overlay' in self.entries:
            self.entries['overlay']['X Offset'].delete(0, END)
            self.entries['overlay']['Y Offset'].delete(0, END)
            self.entries['overlay']['Font Size'].delete(0, END)
            
            self.entries['overlay']['X Offset'].insert(0, int(self.ed_ap.config['OverlayTextXOffset']))
            self.entries['overlay']['Y Offset'].insert(0, int(self.ed_ap.config['OverlayTextYOffset']))
            self.entries['overlay']['Font Size'].insert(0, int(self.ed_ap.config['OverlayTextFontSize']))

        # Checkboxes
        if hasattr(self, 'checkboxvar'):
            self.checkboxvar['Enable Randomness'].set(self.ed_ap.config['EnableRandomness'])
            self.checkboxvar['Activate Elite for each key'].set(self.ed_ap.config['ActivateEliteEachKey'])
            self.checkboxvar['Automatic logout'].set(self.ed_ap.config['AutomaticLogout'])
            self.checkboxvar['Enable Overlay'].set(self.ed_ap.config['OverlayTextEnable'])
            self.checkboxvar['Enable Voice'].set(self.ed_ap.config['VoiceEnable'])

        # Radio buttons
        if hasattr(self, 'radiobuttonvar'):
            self.radiobuttonvar['dss_button'].set(self.ed_ap.config['DSSButton'])
            
            if self.ed_ap.config['LogDEBUG']:
                self.radiobuttonvar['debug_mode'].set("Debug")
            elif self.ed_ap.config['LogINFO']:
                self.radiobuttonvar['debug_mode'].set("Info")
            else:
                self.radiobuttonvar['debug_mode'].set("Error")

        # Hotkey buttons
        if 'buttons' in self.entries:
            self.entries['buttons']['Start FSD'].config(text=str(self.ed_ap.config['HotKey_StartFSD']))
            self.entries['buttons']['Start SC'].config(text=str(self.ed_ap.config['HotKey_StartSC']))
            self.entries['buttons']['Start Robigo'].config(text=str(self.ed_ap.config['HotKey_StartRobigo']))
            self.entries['buttons']['Start Waypoint'].config(text=str(self.ed_ap.config['HotKey_StartWaypoint']))
            self.entries['buttons']['Stop All'].config(text=str(self.ed_ap.config['HotKey_StopAllAssists']))
            self.entries['buttons']['Pause/Resume'].config(text=str(self.ed_ap.config['HotKey_PauseResume']))

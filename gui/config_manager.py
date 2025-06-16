import json
import os
from pathlib import Path
from tkinter import messagebox
from file_utils import read_json_file
from EDlogger import logger


class ConfigManager:
    """Handles configuration loading, saving, and change tracking"""
    
    def __init__(self, ed_ap):
        self.ed_ap = ed_ap
        self.has_unsaved_changes = False
        self.original_values = {}
        
        # GUI element references (set by main GUI)
        self.save_button = None
        self.revert_button = None
        self.gui_elements = {}
        self.programmatic_update_context = None  # Will be set by main GUI
    
    def set_gui_elements(self, elements):
        """Set references to GUI elements for change tracking"""
        self.gui_elements = elements
        self.save_button = elements.get('save_button')
        self.revert_button = elements.get('revert_button')
    
    def set_programmatic_update_context(self, context_func):
        """Set the programmatic update context manager function"""
        self.programmatic_update_context = context_func
    
    def mark_unsaved_changes(self):
        """Mark that there are unsaved changes and highlight save button"""
        was_already_marked = self.has_unsaved_changes
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            if self.save_button:
                self.save_button.config(bg='orange', text='Save All Settings *')
            if self.revert_button:
                self.revert_button.config(state='normal', bg='lightcoral')
            logger.debug("Marked unsaved changes - buttons should be highlighted")
            
        # Only update ship config status once, not in a loop
        if not was_already_marked:
            settings_panel = self.gui_elements.get('settings_panel')
            if settings_panel and hasattr(settings_panel, 'refresh_config_status'):
                settings_panel.refresh_config_status()
                
    def clear_unsaved_changes(self):
        """Clear unsaved changes flag and restore normal save button"""
        self.has_unsaved_changes = False
        if self.save_button:
            self.save_button.config(bg='SystemButtonFace', text='Save All Settings')
        if self.revert_button:
            self.revert_button.config(state='disabled', bg='SystemButtonFace')
        
        # Update ship configuration status display
        settings_panel = self.gui_elements.get('settings_panel')
        if settings_panel and hasattr(settings_panel, 'refresh_config_status'):
            settings_panel.refresh_config_status()
            
        # Refresh original values after updating display to avoid timing issues
        self.capture_original_values()

    def capture_original_values(self):
        """Capture current field values as baseline for change detection"""
        self.original_values = {}
        
        # Capture entry field values from different panels
        panels = ['settings_panel', 'waypoint_panel']
        for panel_name in panels:
            if panel_name in self.gui_elements:
                panel = self.gui_elements[panel_name]
                if hasattr(panel, 'entries'):
                    for category, entries in panel.entries.items():
                        if category not in self.original_values:
                            self.original_values[category] = {}
                        for field_name, entry_widget in entries.items():
                            try:
                                if hasattr(entry_widget, 'get'):
                                    value = entry_widget.get()
                                elif hasattr(entry_widget, 'cget'):
                                    value = entry_widget.cget('text')
                                else:
                                    continue
                                self.original_values[category][field_name] = value
                                logger.debug(f"Captured {category}.{field_name} = '{value}'")
                            except Exception as e:
                                logger.debug(f"Error capturing {category}.{field_name}: {e}")
                
                # Capture checkbox states
                if hasattr(panel, 'checkboxvar'):
                    if 'checkboxes' not in self.original_values:
                        self.original_values['checkboxes'] = {}
                    for field_name, var in panel.checkboxvar.items():
                        try:
                            self.original_values['checkboxes'][field_name] = var.get()
                        except:
                            pass
                
                # Capture radio button states
                if hasattr(panel, 'radiobuttonvar'):
                    if 'radiobuttons' not in self.original_values:
                        self.original_values['radiobuttons'] = {}
                    for field_name, var in panel.radiobuttonvar.items():
                        try:
                            self.original_values['radiobuttons'][field_name] = var.get()
                        except:
                            pass

    def has_actual_changes(self):
        """Check if any GUI values have changed from their captured baseline"""
        if not self.original_values:
            logger.debug("has_actual_changes: No original values captured yet")
            return False
        
        # Simple approach: compare current GUI state with captured baseline
        # This baseline represents the "saved state" and gets reset after save/revert
        result = self._values_differ_from_original()
        logger.debug(f"has_actual_changes: {result}")
        return result
    
    def _values_differ_from_original(self):
        """Original change detection logic - compare against captured original values"""
        # Check changes in all panels
        panels = ['settings_panel', 'waypoint_panel']
        for panel_name in panels:
            if panel_name in self.gui_elements:
                panel = self.gui_elements[panel_name]
                
                # Check entry fields
                if hasattr(panel, 'entries'):
                    for category, entries in panel.entries.items():
                        if category in self.original_values:
                            for field_name, entry_widget in entries.items():
                                try:
                                    if hasattr(entry_widget, 'get'):
                                        current_value = entry_widget.get()
                                    elif hasattr(entry_widget, 'cget'):
                                        current_value = entry_widget.cget('text')
                                    else:
                                        continue
                                        
                                    original_value = self.original_values[category].get(field_name, '')
                                    if current_value != original_value:
                                        logger.debug(f"Change detected in {category}.{field_name}: '{original_value}' -> '{current_value}'")
                                        return True
                                except Exception as e:
                                    logger.debug(f"Error checking {category}.{field_name}: {e}")
                
                # Check checkbox states
                if hasattr(panel, 'checkboxvar') and 'checkboxes' in self.original_values:
                    for field_name, var in panel.checkboxvar.items():
                        try:
                            current_value = var.get()
                            original_value = self.original_values['checkboxes'].get(field_name, 0)
                            if current_value != original_value:
                                return True
                        except:
                            pass
                
                # Check radio button states
                if hasattr(panel, 'radiobuttonvar') and 'radiobuttons' in self.original_values:
                    for field_name, var in panel.radiobuttonvar.items():
                        try:
                            current_value = var.get()
                            original_value = self.original_values['radiobuttons'].get(field_name, '')
                            if current_value != original_value:
                                return True
                        except:
                            pass
        
        return False

    def save_settings(self):
        """Save all settings to configuration"""
        try:
            self._update_internal_values()
            self.ed_ap.update_config()
            
            # Always save ship configs to ship_configs.json, never to individual ship files
            self.ed_ap.update_ship_configs()
            logger.info("Settings saved successfully")
            
            # Update ship display to reflect that it's now "Custom" after saving
            settings_panel = self.gui_elements.get('settings_panel')
            if settings_panel:
                settings_panel.update_ship_display()
                
            self.clear_unsaved_changes()
            return True
        except Exception as e:
            import traceback
            logger.error(f"Error saving settings: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")
            return False

    def _update_internal_values(self):
        """Update internal config values from GUI fields"""
        settings_panel = self.gui_elements.get('settings_panel')
        waypoint_panel = self.gui_elements.get('waypoint_panel')
        
        if settings_panel:
            try:
                # Ship configuration
                if 'ship' in settings_panel.entries:
                    self.ed_ap.pitchrate = float(settings_panel.entries['ship']['PitchRate'].get())
                    self.ed_ap.rollrate = float(settings_panel.entries['ship']['RollRate'].get())
                    self.ed_ap.yawrate = float(settings_panel.entries['ship']['YawRate'].get())
                    self.ed_ap.sunpitchuptime = float(settings_panel.entries['ship']['SunPitchUp+Time'].get())

                # Autopilot settings
                if 'autopilot' in settings_panel.entries:
                    self.ed_ap.config['SunBrightThreshold'] = int(settings_panel.entries['autopilot']['Sun Bright Threshold'].get())
                    self.ed_ap.config['NavAlignTries'] = int(settings_panel.entries['autopilot']['Nav Align Tries'].get())
                    self.ed_ap.config['JumpTries'] = int(settings_panel.entries['autopilot']['Jump Tries'].get())
                    self.ed_ap.config['DockingRetries'] = int(settings_panel.entries['autopilot']['Docking Retries'].get())
                    self.ed_ap.config['WaitForAutoDockTimer'] = int(settings_panel.entries['autopilot']['Wait For Autodock'].get())
                
                # Refuel settings
                if 'refuel' in settings_panel.entries:
                    self.ed_ap.config['RefuelThreshold'] = int(settings_panel.entries['refuel']['Refuel Threshold'].get())
                    self.ed_ap.config['FuelScoopTimeOut'] = int(settings_panel.entries['refuel']['Scoop Timeout'].get())
                    self.ed_ap.config['FuelThreasholdAbortAP'] = int(settings_panel.entries['refuel']['Fuel Threshold Abort'].get())
                
                # Overlay settings
                if 'overlay' in settings_panel.entries:
                    self.ed_ap.config['OverlayTextXOffset'] = int(settings_panel.entries['overlay']['X Offset'].get())
                    self.ed_ap.config['OverlayTextYOffset'] = int(settings_panel.entries['overlay']['Y Offset'].get())
                    self.ed_ap.config['OverlayTextFontSize'] = int(settings_panel.entries['overlay']['Font Size'].get())
                
                # Hotkey buttons
                if 'buttons' in settings_panel.entries:
                    self.ed_ap.config['HotKey_StartFSD'] = str(settings_panel.entries['buttons']['Start FSD'].cget('text'))
                    self.ed_ap.config['HotKey_StartSC'] = str(settings_panel.entries['buttons']['Start SC'].cget('text'))
                    self.ed_ap.config['HotKey_StartRobigo'] = str(settings_panel.entries['buttons']['Start Robigo'].cget('text'))
                    self.ed_ap.config['HotKey_StartWaypoint'] = str(settings_panel.entries['buttons']['Start Waypoint'].cget('text'))
                    self.ed_ap.config['HotKey_StopAllAssists'] = str(settings_panel.entries['buttons']['Stop All'].cget('text'))
                    self.ed_ap.config['HotKey_PauseResume'] = str(settings_panel.entries['buttons']['Pause/Resume'].cget('text'))
                
                # Checkbox settings
                if hasattr(settings_panel, 'checkboxvar'):
                    checkbox_mapping = {
                        'Enable Randomness': 'EnableRandomness',
                        'Activate Elite for each key': 'ActivateEliteEachKey',
                        'Automatic logout': 'AutomaticLogout',
                        'Enable Overlay': 'OverlayTextEnable',
                        'Enable Voice': 'VoiceEnable'
                    }
                    for gui_field, config_field in checkbox_mapping.items():
                        if gui_field in settings_panel.checkboxvar:
                            self.ed_ap.config[config_field] = settings_panel.checkboxvar[gui_field].get()
                
                # Radio button settings
                if hasattr(settings_panel, 'radiobuttonvar'):
                    if 'dss_button' in settings_panel.radiobuttonvar:
                        self.ed_ap.config['DSSButton'] = settings_panel.radiobuttonvar['dss_button'].get()
                    if 'debug_mode' in settings_panel.radiobuttonvar:
                        debug_mode = settings_panel.radiobuttonvar['debug_mode'].get()
                        if debug_mode == "Error":
                            self.ed_ap.set_log_error(True)
                        elif debug_mode == "Debug":
                            self.ed_ap.set_log_debug(True)
                        elif debug_mode == "Info":
                            self.ed_ap.set_log_info(True)
                            
            except Exception as e:
                logger.error(f"Error updating internal values from settings panel: {e}")
                raise
        
        if waypoint_panel:
            try:
                self.ed_ap.config['TCEDestinationFilepath'] = str(waypoint_panel.TCE_Destination_Filepath.get())
            except Exception as e:
                logger.error(f"Error updating internal values from waypoint panel: {e}")
                raise

    def open_ship_file(self, filename=None):
        """Open and load a ship configuration file"""
        from tkinter import filedialog as fd
        from tkinter import END
        
        # If a filename was not provided, then prompt user for one
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
            return False

        try:
            f_details = read_json_file(filename)
            
            # Update internal values first
            self.ed_ap.rollrate = float(f_details['rollrate'])
            self.ed_ap.pitchrate = float(f_details['pitchrate'])
            self.ed_ap.yawrate = float(f_details['yawrate'])
            self.ed_ap.sunpitchuptime = float(f_details['SunPitchUp+Time'])

            # Update GUI to reflect the new internal values
            settings_panel = self.gui_elements.get('settings_panel')
            if settings_panel:
                # Loading a ship file as template doesn't make it "Custom" until saved
                # Update the ship display to reflect template loading
                settings_panel.update_ship_display()
            
            self.ed_ap.update_config()
            return True
            
        except Exception as e:
            logger.error(f"Error loading ship file {filename}: {e}")
            messagebox.showerror("Load Error", f"Failed to load ship file: {e}")
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
        
        try:
            # Revert values in all panels
            panels = ['settings_panel', 'waypoint_panel']
            for panel_name in panels:
                if panel_name in self.gui_elements:
                    panel = self.gui_elements[panel_name]
                    self._revert_panel_values(panel)
            
            # Update internal values to match reverted GUI state
            self._update_internal_values()
            
            # Clear unsaved changes
            self.clear_unsaved_changes()
            
            logger.info("Settings reverted to last saved values")
            
        except Exception as e:
            logger.error(f"Error reverting changes: {e}")
            messagebox.showerror("Revert Error", f"Failed to revert changes: {e}")

    def _revert_panel_values(self, panel):
        """Revert values for a specific panel"""
        import tkinter as tk
        
        # Revert entry fields
        if hasattr(panel, 'entries'):
            for category, entries in panel.entries.items():
                if category in self.original_values:
                    for field_name, entry_widget in entries.items():
                        try:
                            original_value = self.original_values[category].get(field_name, '')
                            if hasattr(entry_widget, 'delete') and hasattr(entry_widget, 'insert'):
                                if self.programmatic_update_context:
                                    with self.programmatic_update_context():
                                        entry_widget.delete(0, tk.END)
                                        entry_widget.insert(0, original_value)
                                else:
                                    entry_widget.delete(0, tk.END)
                                    entry_widget.insert(0, original_value)
                            elif hasattr(entry_widget, 'config'):
                                entry_widget.config(text=original_value)
                        except:
                            pass
        
        # Revert checkbox states
        if hasattr(panel, 'checkboxvar') and 'checkboxes' in self.original_values:
            for field_name, var in panel.checkboxvar.items():
                try:
                    original_value = self.original_values['checkboxes'].get(field_name, 0)
                    var.set(original_value)
                except:
                    pass
        
        # Revert radio button states
        if hasattr(panel, 'radiobuttonvar') and 'radiobuttons' in self.original_values:
            for field_name, var in panel.radiobuttonvar.items():
                try:
                    original_value = self.original_values['radiobuttons'].get(field_name, '')
                    var.set(original_value)
                except:
                    pass
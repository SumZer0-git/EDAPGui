from __future__ import annotations

import json
from os import environ, listdir
import os
from os.path import getmtime, isfile, join
from time import sleep
from typing import Any, final
from xml.etree.ElementTree import parse

import win32gui
import xmltodict

from directinput import *
from EDlogger import logger
from file_utils import read_text_file

"""
Description:  Pulls the keybindings for specific controls from the ED Key Bindings file, this class also
  has method for sending a key to the display that has focus (so must have ED with focus)

Constraints:  This file will use the latest modified *.binds file
"""


def set_focus_elite_window():
    """ set focus to the ED window, if ED does not have focus then the keystrokes will go to the window
    that does have focus. """
    handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    if handle != 0:
        win32gui.SetForegroundWindow(handle)  # give focus to ED


@final
class EDKeys:

    def __init__(self, cb):
        self.ap_ckb = cb
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100

        self.keys_to_obtain = [
            'YawLeftButton',
            'YawRightButton',
            'RollLeftButton',
            'RollRightButton',
            'PitchUpButton',
            'PitchDownButton',
            'SetSpeedZero',
            'SetSpeed50',
            'SetSpeed100',
            'HyperSuperCombination',
            'SelectTarget',
            'DeployHeatSink',
            'UIFocus',
            'UI_Up',
            'UI_Down',
            'UI_Left',
            'UI_Right',
            'UI_Select',
            'UI_Back',
            'CycleNextPanel',
            'HeadLookReset',
            'PrimaryFire',
            'SecondaryFire',
            'ExplorationFSSEnter',
            'ExplorationFSSQuit',
            'MouseReset',
            'DeployHardpointToggle',
            'IncreaseEnginesPower',
            'IncreaseWeaponsPower',
            'IncreaseSystemsPower',
            'GalaxyMapOpen',
            'CamZoomIn',  # Gal map zoom in
            'SystemMapOpen',
            'UseBoostJuice',
            'Supercruise',
            'UpThrustButton',
            'LandingGearToggle',
            'TargetNextRouteSystem',  # Target next system in route
            'CamTranslateForward',
            'CamTranslateRight',
        ]
        self.keys = self.get_bindings()
        self.bindings = self.get_bindings_dict()
        self.activate_window = False

        self.missing_keys = []
        # We want to log the keyboard name instead of just the key number so we build a reverse dictionary
        # so we can look up the name also
        self.reversed_dict = {value: key for key, value in SCANCODE.items()}

        # dump config to log
        for key in self.keys_to_obtain:
            try:
                # lookup the keyname in the SCANCODE reverse dictionary and output that key name
                keyname = self.reversed_dict.get(self.keys[key]['key'], "Key not found")
                keymod = " "
                # if key modifier, then look up that modifier name also
                if len(self.keys[key]['mods']) != 0:
                    keymod = self.reversed_dict.get(self.keys[key]['mods'][0], " ")

                logger.info('\tget_bindings_<{}>={} Key: <{}> Mod: <{}>'.format(key, self.keys[key], keyname, keymod))
                if key not in self.keys:
                    self.ap_ckb('log',
                                f"WARNING: \tget_bindings_<{key}>= does not have a valid keyboard keybind {keyname}.")
                    logger.warning(
                        "\tget_bindings_<{}>= does not have a valid keyboard keybind {}".format(key, keyname).upper())
                    self.missing_keys.append(key)
            except Exception as e:
                self.ap_ckb('log', f"WARNING: \tget_bindings_<{key}>= does not have a valid keyboard keybind.")
                logger.warning("\tget_bindings_<{}>= does not have a valid keyboard keybind.".format(key).upper())
                self.missing_keys.append(key)


        # Note: Hardcoded hotkey conflict checks removed since EDAP now uses 
        # user-configurable hotkeys. Conflicts are checked dynamically via 
        # check_edap_hotkey_conflicts() method called from ED_AP.py

    def check_edap_hotkey_conflicts(self, config):
        """Check if user-configured EDAP hotkeys conflict with Elite Dangerous keybindings"""
        hotkey_configs = [
            ('HotKey_StartFSD', 'Start FSD Assist'),
            ('HotKey_StartSC', 'Start Supercruise Assist'),
            ('HotKey_StartRobigo', 'Start Robigo Assist'),
            ('HotKey_StartWaypoint', 'Start Waypoint Assist'),
            ('HotKey_StopAllAssists', 'Stop All Assists'),
            ('HotKey_PauseResume', 'Pause/Resume Assists')
        ]
        
        for config_key, description in hotkey_configs:
            # Get the actual configured hotkey value
            hotkey = config.get(config_key, '').strip()
            if not hotkey:
                logger.debug(f"No hotkey configured for {description}")
                continue
                
            logger.debug(f"Checking conflict for {description}: '{hotkey}'")
            
            # Check for conflicts using smarter combination detection
            binding_name = self.check_exact_hotkey_combination(hotkey)
            if binding_name != "":
                # Convert to ED format to check EDAP usage
                ed_key = self._convert_hotkey_to_ed_format(hotkey)
                if ed_key:
                    # Check if EDAP actually uses this conflicting ED key
                    conflicting_actions = self._get_edap_actions_using_key(ed_key)
                    
                    if conflicting_actions:
                        # EDAP uses this key - this is a real problem
                        warn_text = (f"EDAP hotkey '{hotkey}' for '{description}' conflicts with ED keybinding '{binding_name}'. "
                                   f"EDAP also uses this key for: {', '.join(conflicting_actions)}. "
                                   f"Consider changing either the EDAP hotkey or the ED keybinding to avoid conflicts.")
                        self.ap_ckb('log', f"WARNING: {warn_text}")
                        logger.warning(f"{warn_text}")
                    else:
                        # EDAP doesn't use this key - just informational
                        info_text = (f"EDAP hotkey '{hotkey}' for '{description}' uses same key as ED keybinding '{binding_name}'. "
                                   f"No conflict expected since EDAP doesn't use this key for game controls.")
                        self.ap_ckb('log', f"INFO: {info_text}")
                        logger.info(f"{info_text}")
                else:
                    logger.debug(f"Could not convert hotkey '{hotkey}' to ED format for EDAP usage check")
            else:
                logger.debug(f"No conflicts found for hotkey '{hotkey}'")

    def _get_edap_actions_using_key(self, ed_key):
        """Check which EDAP actions use the given ED key format"""
        conflicting_actions = []
        
        # Check each ED action that EDAP uses
        for action in self.keys_to_obtain:
            if action in self.bindings.get('Root', {}):
                action_data = self.bindings['Root'][action]
                if isinstance(action_data, dict):
                    # Check primary binding
                    primary = action_data.get('Primary', {})
                    if isinstance(primary, dict) and primary.get('@Key') == ed_key:
                        conflicting_actions.append(f"{action} (Primary)")
                    
                    # Check secondary binding
                    secondary = action_data.get('Secondary', {})
                    if isinstance(secondary, dict) and secondary.get('@Key') == ed_key:
                        conflicting_actions.append(f"{action} (Secondary)")
        
        return conflicting_actions

    def _convert_hotkey_to_ed_format(self, hotkey):
        """Convert EDAP hotkey format to Elite Dangerous key format"""
        # For now, we'll check the main key since ED key combinations are complex
        # Future enhancement could include full modifier checking
        key_part = hotkey.split('+')[-1].lower().strip()  # Get the last part (main key)
        
        # Map common keys to ED format
        key_mapping = {
            # Function keys
            'f1': 'Key_F1', 'f2': 'Key_F2', 'f3': 'Key_F3', 'f4': 'Key_F4',
            'f5': 'Key_F5', 'f6': 'Key_F6', 'f7': 'Key_F7', 'f8': 'Key_F8',
            'f9': 'Key_F9', 'f10': 'Key_F10', 'f11': 'Key_F11', 'f12': 'Key_F12',
            
            # Navigation keys
            'home': 'Key_Home', 'end': 'Key_End', 
            'ins': 'Key_Insert', 'insert': 'Key_Insert',
            'del': 'Key_Delete', 'delete': 'Key_Delete',
            'page up': 'Key_PageUp', 'pageup': 'Key_PageUp',
            'page down': 'Key_PageDown', 'pagedown': 'Key_PageDown',
            
            # Special keys
            'pause': 'Key_Pause', 'backspace': 'Key_Backspace',
            'enter': 'Key_Enter', 'return': 'Key_Enter',
            'space': 'Key_Space', 'tab': 'Key_Tab',
            'esc': 'Key_Escape', 'escape': 'Key_Escape',
            
            # Arrow keys
            'up': 'Key_UpArrow', 'down': 'Key_DownArrow',
            'left': 'Key_LeftArrow', 'right': 'Key_RightArrow',
            
            # Numpad keys
            'numpad0': 'Key_Numpad_0', 'numpad1': 'Key_Numpad_1',
            'numpad2': 'Key_Numpad_2', 'numpad3': 'Key_Numpad_3',
            'numpad4': 'Key_Numpad_4', 'numpad5': 'Key_Numpad_5',
            'numpad6': 'Key_Numpad_6', 'numpad7': 'Key_Numpad_7',
            'numpad8': 'Key_Numpad_8', 'numpad9': 'Key_Numpad_9',
        }
        
        # Add letter keys (a-z)
        for letter in 'abcdefghijklmnopqrstuvwxyz':
            key_mapping[letter] = f'Key_{letter.upper()}'
        
        # Add number keys (0-9)
        for num in '0123456789':
            key_mapping[num] = f'Key_{num}'
            
        ed_key = key_mapping.get(key_part)
        logger.debug(f"Converting '{key_part}' -> '{ed_key}'")
        return ed_key

    def get_bindings(self) -> dict[str, Any]:
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        latest_bindings = self.get_latest_keybinds()
        if not latest_bindings:
            return {}
        bindings_tree = parse(latest_bindings)
        bindings_root = bindings_tree.getroot()

        for item in bindings_root:
            if item.tag in self.keys_to_obtain:
                key = None
                mods = []
                hold = None
                # Check primary
                if item[0].attrib['Device'].strip() == "Keyboard":
                    key = item[0].attrib['Key']
                    for modifier in item[0]:
                        if modifier.tag == "Modifier":
                            mods.append(modifier.attrib['Key'])
                        elif modifier.tag == "Hold":
                            hold = True
                # Check secondary (and prefer secondary)
                if item[1].attrib['Device'].strip() == "Keyboard":
                    key = item[1].attrib['Key']
                    mods = []
                    hold = None
                    for modifier in item[1]:
                        if modifier.tag == "Modifier":
                            mods.append(modifier.attrib['Key'])
                        elif modifier.tag == "Hold":
                            hold = True
                # Prepare final binding
                binding: None | dict[str, Any] = None
                try:
                    if key is not None:
                        binding = {}
                        binding['key'] = SCANCODE[key]
                        binding['mods'] = []
                        for mod in mods:
                            binding['mods'].append(SCANCODE[mod])
                        if hold is not None:
                            binding['hold'] = True
                except KeyError:
                    print("Unrecognised key '" + (
                        json.dumps(binding) if binding else '?') + "' for bind '" + item.tag + "'")
                if binding is not None:
                    direct_input_keys[item.tag] = binding

        if len(list(direct_input_keys.keys())) < 1:
            return {}
        else:
            return direct_input_keys

    def get_bindings_dict(self) -> dict[str, Any]:
        """Returns a dict of all the elite keybindings.
        @return: A dictionary of the keybinds file.
        Example:
        {
        'Root': {
            'YawLeftButton': {
                'Primary': {
                    '@Device': 'Keyboard',
                    '@Key': 'Key_A'
                },
                'Secondary': {
                    '@Device': '{NoDevice}',
                    '@Key': ''
                }
            }
        }
        }
        """
        latest_bindings = self.get_latest_keybinds()
        if not latest_bindings:
            return {}

        try:
            my_xml = read_text_file(latest_bindings)
            my_dict = xmltodict.parse(my_xml)
            return my_dict

        except OSError as e:
            logger.error(f"OS Error reading Elite Dangerous bindings file: {latest_bindings}.")
            raise Exception(f"OS Error reading Elite Dangerous bindings file: {latest_bindings}.")

    def check_hotkey_in_bindings(self, key_name: str) -> str:
        """ Check for the action keys. """
        ret = []
        for key, value in self.bindings['Root'].items():
            if type(value) is dict:
                primary = value.get('Primary', None)
                if primary is not None:
                    if primary['@Key'] == key_name:
                        ret.append(f"{key} (Primary)")
                secondary = value.get('Secondary', None)
                if secondary is not None:
                    if secondary['@Key'] == key_name:
                        ret.append(f"{key} (Secondary)")
        return " and ".join(ret)

    def check_exact_hotkey_combination(self, hotkey: str) -> str:
        """Check if the exact hotkey combination (with modifiers) exists in ED bindings"""
        # Parse the EDAP hotkey format (e.g., "alt+shift+backspace")
        parts = [p.strip() for p in hotkey.lower().split('+')]
        
        # Get the main key (last part)
        main_key = parts[-1]
        ed_key = self._convert_hotkey_to_ed_format(main_key)
        if not ed_key:
            return ""
        
        # Get modifiers (all parts except the last)
        edap_modifiers = sorted(parts[:-1]) if len(parts) > 1 else []
        
        # Check all ED bindings for exact matches
        conflicts = []
        for action, value in self.bindings.get('Root', {}).items():
            if isinstance(value, dict):
                # Check primary binding
                primary = value.get('Primary', {})
                if self._exact_binding_match(primary, ed_key, edap_modifiers):
                    conflicts.append(f"{action} (Primary)")
                
                # Check secondary binding  
                secondary = value.get('Secondary', {})
                if self._exact_binding_match(secondary, ed_key, edap_modifiers):
                    conflicts.append(f"{action} (Secondary)")
        
        return " and ".join(conflicts)

    def _exact_binding_match(self, binding: dict, ed_key: str, edap_modifiers: list) -> bool:
        """Check if ED binding exactly matches the EDAP hotkey combination"""
        if not isinstance(binding, dict) or binding.get('@Key') != ed_key:
            return False
        
        # Extract ED modifiers from the binding structure
        ed_modifiers = []
        
        # Look for Modifier elements in the binding
        for key, value in binding.items():
            if key.startswith('Modifier'):
                # Handle both single modifier and list of modifiers
                if isinstance(value, dict) and '@Key' in value:
                    mod_key = value['@Key'].lower()
                    ed_modifier = self._convert_ed_modifier_to_edap_format(mod_key)
                    if ed_modifier:
                        ed_modifiers.append(ed_modifier)
                elif isinstance(value, list):
                    for mod in value:
                        if isinstance(mod, dict) and '@Key' in mod:
                            mod_key = mod['@Key'].lower()
                            ed_modifier = self._convert_ed_modifier_to_edap_format(mod_key)
                            if ed_modifier:
                                ed_modifiers.append(ed_modifier)
        
        # Sort both lists for comparison
        ed_modifiers = sorted(ed_modifiers)
        
        # Exact match: same key and same modifiers
        return ed_modifiers == edap_modifiers

    def _convert_ed_modifier_to_edap_format(self, ed_modifier: str) -> str:
        """Convert ED modifier key to EDAP format"""
        modifier_mapping = {
            'key_lshift': 'shift',
            'key_rshift': 'shift', 
            'key_lctrl': 'ctrl',
            'key_rctrl': 'ctrl',
            'key_lalt': 'alt',
            'key_ralt': 'alt',
            'key_lwin': 'win',
            'key_rwin': 'win'
        }
        return modifier_mapping.get(ed_modifier.lower(), '')

    # Note:  this routine will grab the *.binds file which is the latest modified
    def get_latest_keybinds(self):
        path_bindings = environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous\\Options\\Bindings"
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.binds')]
        except FileNotFoundError as e:
            return None

        if not list_of_bindings:
            return None
        latest_bindings = max(list_of_bindings, key=getmtime)
        logger.info(f'Latest keybindings file:{latest_bindings}')
        return latest_bindings

    def send_key(self, type, key):
        # Focus Elite window if configured
        if self.activate_window:
            set_focus_elite_window()
            sleep(0.05)

        if type == 'Up':
            ReleaseKey(key)
        else:
            PressKey(key)

    def send(self, key_binding, hold=None, repeat=1, repeat_delay=None, state=None):
        key = self.keys.get(key_binding)
        if key is None:
            logger.warning('SEND=NONE !!!!!!!!')
            self.ap_ckb('log', f"WARNING: Unable to retrieve keybinding for {key_binding}.")
            raise Exception(
                f"Unable to retrieve keybinding for {key_binding}. Advise user to check game settings for keyboard bindings.")

        # Create simplified, readable log message
        key_name = self.reversed_dict.get(key['key'], "Key not found")
        log_parts = [key_binding, key_name]
        
        # Only add non-default parameters to reduce log spam
        if hold and hold != self.key_default_delay:
            log_parts.append(f"hold:{hold}")
        if repeat and repeat != 1:
            log_parts.append(f"repeat:{repeat}")
        if repeat_delay and repeat_delay != self.key_repeat_delay:
            log_parts.append(f"repeat_delay:{repeat_delay}")
        if state is not None:
            log_parts.append(f"state:{state}")
        if key.get('hold'):
            log_parts.append("hold_key")
        
        # Only log if this is a significant key press (reduce spam for alignment operations)
        spam_actions = ['UI_Up', 'UI_Down', 'UI_Left', 'UI_Right', 'UI_Select', 'UI_Back']
        if key_binding in spam_actions and repeat == 1 and not hold and state is None:
            # Skip logging for simple UI navigation to reduce spam
            pass
        else:
            logger.debug(' | '.join(log_parts))

        for i in range(repeat):
            # Focus Elite window if configured.
            if self.activate_window:
                set_focus_elite_window()
                sleep(0.05)

            if state is None or state == 1:
                for mod in key['mods']:
                    PressKey(mod)
                    sleep(self.key_mod_delay)

                PressKey(key['key'])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if 'hold' in key:
                sleep(0.1)

            if state is None or state == 0:
                ReleaseKey(key['key'])

                for mod in key['mods']:
                    sleep(self.key_mod_delay)
                    ReleaseKey(mod)

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)

    def get_collisions(self, key_name: str) -> list[str]:
        """ Get key name collisions (keys used for more than one binding).
        @param key_name: The key name (i.e. UI_Up, UI_Down).
        """
        key = self.keys.get(key_name)
        collisions = []
        for k, v in self.keys.items():
            if key == v:
                collisions.append(k)
        return collisions

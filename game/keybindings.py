"""Reads the keybindings used by EDAP from the latest Elite Dangerous *.binds file."""

from __future__ import annotations

import json
from os import environ, listdir
from os.path import getmtime, isfile, join
from typing import Any
from xml.etree.ElementTree import parse

import xmltodict

from controls.directinput import SCANCODE
from core.logger import logger


class KeyBindings:

    def __init__(self, cb):
        self.ap_ckb = cb

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
            except Exception:
                self.ap_ckb('log', f"WARNING: \tget_bindings_<{key}>= does not have a valid keyboard keybind.")
                logger.warning("\tget_bindings_<{}>= does not have a valid keyboard keybind.".format(key).upper())
                self.missing_keys.append(key)

        # Check for key collisions with the keys EDAP uses.
        for key in self.keys_to_obtain:
            collisions = self.get_collisions(key)
            if len(collisions) > 1:
                # lookup the keyname in the SCANCODE reverse dictionary and output that key name
                keyname = self.reversed_dict.get(self.keys[key]['key'], "Key not found")
                warn_text = (f"Key '{keyname}' is used for the following bindings: {collisions}. "
                             "This MAY causes issues when using EDAP. Monitor and adjust accordingly.")
                self.ap_ckb('log', f"WARNING: {warn_text}")
                logger.warning(f"{warn_text}")

        # Check if the hotkeys are used in ED
        binding_name = self.check_hotkey_in_bindings('Key_End')
        if binding_name != "":
            warn_text = (f"Hotkey 'Key_End' is used in the ED keybindings for '{binding_name}'. Recommend changing in"
                         f" ED to another key to avoid EDAP accidentally being triggered.")
            self.ap_ckb('log', f"WARNING: {warn_text}")
            logger.warning(f"{warn_text}")

        binding_name = self.check_hotkey_in_bindings('Key_Insert')
        if binding_name != "":
            warn_text = (f"Hotkey 'Key_Insert' is used in the ED keybindings for '{binding_name}'. Recommend changing in"
                         f" ED to another key to avoid EDAP accidentally being triggered.")
            self.ap_ckb('log', f"WARNING: {warn_text}")
            logger.warning(f"{warn_text}")

        binding_name = self.check_hotkey_in_bindings('Key_PageUp')
        if binding_name != "":
            warn_text = (f"Hotkey 'Key_PageUp' is used in the ED keybindings for '{binding_name}'. Recommend changing in"
                         f" ED to another key to avoid EDAP accidentally being triggered.")
            self.ap_ckb('log', f"WARNING: {warn_text}")
            logger.warning(f"{warn_text}")

        binding_name = self.check_hotkey_in_bindings('Key_Home')
        if binding_name != "":
            warn_text = (f"Hotkey 'Key_Home' is used in the ED keybindings for '{binding_name}'. Recommend changing in"
                         f" ED to another key to avoid EDAP accidentally being triggered.")
            self.ap_ckb('log', f"WARNING: {warn_text}")
            logger.warning(f"{warn_text}")

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
            with open(latest_bindings, 'r') as file:
                my_xml = file.read()
                my_dict = xmltodict.parse(my_xml)
                return my_dict

        except OSError:
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

    # Note:  this routine will grab the *.binds file which is the latest modified
    def get_latest_keybinds(self):
        path_bindings = environ['LOCALAPPDATA'] + "\Frontier Developments\Elite Dangerous\Options\Bindings"
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.binds')]
        except FileNotFoundError:
            return None

        if not list_of_bindings:
            return None
        latest_bindings = max(list_of_bindings, key=getmtime)
        logger.info(f'Latest keybindings file:{latest_bindings}')
        return latest_bindings

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

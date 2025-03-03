from __future__ import annotations

import json
from os import environ, listdir
import os
from os.path import getmtime, isfile, join
from time import sleep
from typing import Any, final
from xml.etree.ElementTree import parse

import win32gui

from directinput import *
from EDlogger import logger

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

    def __init__(self):
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
            'SystemMapOpen',
            'UseBoostJuice',
            'Supercruise',
            'UpThrustButton',
            'LandingGearToggle',
            'CamZoomIn',  # Gal map zoom in
        ]
        self.keys = self.get_bindings()
        self.activate_window = False

        self.missing_keys = []
        # dump config to log
        for key in self.keys_to_obtain:
            logger.info('get_bindings_<' + str(key) + '>=' + str(self.keys[key]))
            if not key in self.keys:
                logger.warning(str("get_bindings_<" + key + ">= does not have a valid keyboard keybind.").upper())
                self.missing_keys.append(key)

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

    # Note:  this routine will grab the *.binds file which is the latest modified
    def get_latest_keybinds(self):
        path_bindings = environ['LOCALAPPDATA']+"\Frontier Developments\Elite Dangerous\Options\Bindings"
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

    def send(self, key_name, hold=None, repeat=1, repeat_delay=None, state=None):
        key = self.keys.get(key_name)
        if key is None:
            logger.warning('SEND=NONE !!!!!!!!')
            raise Exception(
                f"Unable to retrieve keybinding for {key_name}. Advise user to check game settings for keyboard bindings.")

        logger.debug('send=' + key_name + ',key:' + str(key) + ',hold:' + str(hold) + ',repeat:' + str(
            repeat) + ',repeat_delay:' + str(repeat_delay) + ',state:' + str(state))

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

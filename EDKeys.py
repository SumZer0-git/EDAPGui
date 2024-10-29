from os import environ, listdir
from os.path import abspath, getmtime, isfile, join
from time import sleep, time
from xml.etree.ElementTree import parse

import win32gui

from directinput import *
from EDlogger import logger

"""
File: EDKeys.py
(most was taken from EDAutopilot on github, turned into a class and enhanced
https://github.com/skai2/EDAutopilot)

Description:  Pulls the keybindings for specific controls from the ED Key Bindings file, this class also
  has method for sending a key to the display that has focus (so must have ED with focus)

Constraints:  This file will use the latest modified *.binds file

Author: sumzer0@yahoo.com
"""


def set_focus_elite_window():
    """ set focus to the ED window, if ED does not have focus then the keystrokes will go to the window
    that does have focus. """
    handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
    if handle != 0:
        win32gui.SetForegroundWindow(handle)  # give focus to ED


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
            'Supercruise'
        ]
        self.keys = self.get_bindings(self.keys_to_obtain)
        self.activate_window = False

        # dump config to log
        for key in self.keys_to_obtain:
            try:
                logger.info('get_bindings_<'+str(key)+'>='+str(self.keys[key]))
            except Exception as e:
                logger.warning(str("get_bindings_<"+key+">= does not have a valid keyboard keybind.").upper())

    def get_bindings(self, keys_to_obtain):
        """Returns a dict struct with the direct input equivalent of the necessary elite keybindings"""
        direct_input_keys = {}
        convert_to_direct_keys = {
            'Key_LeftShift': 'LShift',
            'Key_RightShift': 'RShift',
            'Key_LeftAlt': 'LAlt',
            'Key_RightAlt': 'RAlt',
            'Key_LeftControl': 'LControl',
            'Key_RightControl': 'RControl',
            'Key_LeftBracket': 'LBracket',
            'Key_RightBracket': 'RBracket'
        }

        latest_bindings = self.get_latest_keybinds()
        bindings_tree = parse(latest_bindings)
        bindings_root = bindings_tree.getroot()

        for item in bindings_root:
            if item.tag in self.keys_to_obtain:
                key = None
                mod = None
                # Check primary
                if item[0].attrib['Device'].strip() == "Keyboard":
                    key = item[0].attrib['Key']
                    if len(item[0]) > 0:
                        mod = item[0][0].attrib['Key']
                # Check secondary (and prefer secondary)
                if item[1].attrib['Device'].strip() == "Keyboard":
                    key = item[1].attrib['Key']
                    mod = None
                    if len(item[1]) > 0:
                        mod = item[1][0].attrib['Key']
                # Adequate key to SCANCODE dict standard
                if key in convert_to_direct_keys:
                    key = convert_to_direct_keys[key]
                elif key is not None:
                    key = key[4:]
                # Adequate mod to SCANCODE dict standard
                if mod in convert_to_direct_keys:
                    mod = convert_to_direct_keys[mod]
                elif mod is not None:
                    mod = mod[4:]
                # Prepare final binding
                binding = None
                try:
                    if key is not None:
                        binding = {}
                        binding['pre_key'] = 'DIK_'+key.upper()
                        binding['key'] = SCANCODE[binding['pre_key']]
                        if mod is not None:
                            binding['pre_mod'] = 'DIK_'+mod.upper()
                            binding['mod'] = SCANCODE[binding['pre_mod']]
                except KeyError:
                    print("Unrecognised key '"+binding['pre_key']+"' for bind '"+item.tag+"'")
                    exit(1)
                if binding is not None:
                    direct_input_keys[item.tag] = binding
                #     else:
                #         logger.warning("get_bindings_<"+item.tag+">= does not have a valid keyboard keybind.")

        if len(list(direct_input_keys.keys())) < 1:
            return None
        else:
            return direct_input_keys

    # Note:  this routine will grab the *.binds file which is the latest modified
    def get_latest_keybinds(self, path_bindings=None):
        if not path_bindings:
            path_bindings = environ['LOCALAPPDATA']+"\Frontier Developments\Elite Dangerous\Options\Bindings"

        list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if isfile(join(path_bindings, f)) and f.endswith('.binds')]

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
        key = self.keys[key_name]
        if key is None:
            logger.warning('SEND=NONE !!!!!!!!')
            return

        logger.debug('send='+key_name+',key:'+str(key)+',hold:'+str(hold)+',repeat:'+str(repeat)+',repeat_delay:'+str(repeat_delay)+',state:'+str(state))
        for i in range(repeat):
            # Focus Elite window if configured.
            if self.activate_window:
                set_focus_elite_window()
                sleep(0.05)

            if state is None or state == 1:
                if 'mod' in key:
                    PressKey(key['mod'])
                    sleep(self.key_mod_delay)

                PressKey(key['key'])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if state is None or state == 0:
                ReleaseKey(key['key'])

                if 'mod' in key:
                    sleep(self.key_mod_delay)
                    ReleaseKey(key['mod'])

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)


def main():
    k = EDKeys()
    #logger.info("get_latest_keybinds="+str(k.get_latest_keybinds()))
    #k.send(k.keys['ExplorationFSSEnter'], hold=3)


if __name__ == "__main__":
    main()

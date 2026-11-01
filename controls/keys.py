from time import sleep
from typing import final

from controls.directinput import *
from core.logger import logger
from game.keybindings import KeyBindings
from vision.screen import set_focus_elite_window

"""
Sends the keys bound in Elite Dangerous to the window that has focus (ED must have focus).
"""


@final
class EDKeys(KeyBindings):

    def __init__(self, cb):
        super().__init__(cb)
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100
        self.activate_window = False

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

        key_name = self.reversed_dict.get(key['key'], "Key not found")
        logger.debug('\tsend=' + key_binding + ',key:' + str(key) + ',key_name:' + key_name + ',hold:' + str(
            hold) + ',repeat:' + str(
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

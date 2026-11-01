"""Sends the keys bound in Elite Dangerous to the game window (ED must have focus)."""

import threading
import time
from time import sleep
from typing import final

from controls.directinput import press_key, release_key
from core.logger import logger
from game.keybindings import KeyBindings
from vision.screen import set_focus_elite_window


@final
class EDKeys(KeyBindings):
    def __init__(self, cb):
        super().__init__(cb)
        self.key_mod_delay = 0.010
        self.key_default_delay = 0.200
        self.key_repeat_delay = 0.100
        self.activate_window = False
        self._cond = threading.Condition()
        self._held: dict[str, set[int]] = {}

    def _wait_for_free(self, key_binding, key, timeout=15.0):
        """Wait while another binding is held that shares a key or modifier with this one.

        Releasing a shared key (e.g. S for PitchUp and the scanner button) would otherwise cut
        off a button held by another thread, such as the discovery scan."""
        codes = {key["key"], *key["mods"]}
        deadline = time.time() + timeout
        with self._cond:
            while any(name != key_binding and codes & held for name, held in self._held.items()):
                remaining = deadline - time.time()
                if remaining <= 0:
                    logger.warning(f"Timeout waiting for held keys before sending {key_binding}.")
                    return
                self._cond.wait(remaining)

    def send_key(self, type, key):
        # Focus Elite window if configured
        if self.activate_window:
            set_focus_elite_window()
            sleep(0.05)

        if type == "Up":
            release_key(key)
        else:
            press_key(key)

    def send(self, key_binding, hold=None, repeat=1, repeat_delay=None, state=None):
        key = self.keys.get(key_binding)
        if key is None:
            logger.warning("SEND=NONE !!!!!!!!")
            self.ap_ckb("log", f"WARNING: Unable to retrieve keybinding for {key_binding}.")
            raise Exception(
                f"Unable to retrieve keybinding for {key_binding}. Advise user to check game settings for keyboard bindings."
            )

        key_name = self.reversed_dict.get(key["key"], "Key not found")
        logger.debug(
            "\tsend="
            + key_binding
            + ",key:"
            + str(key)
            + ",key_name:"
            + key_name
            + ",hold:"
            + str(hold)
            + ",repeat:"
            + str(repeat)
            + ",repeat_delay:"
            + str(repeat_delay)
            + ",state:"
            + str(state)
        )

        for i in range(repeat):
            if state is None or state == 1:
                self._wait_for_free(key_binding, key)

            # Focus Elite window if configured.
            if self.activate_window:
                set_focus_elite_window()
                sleep(0.05)

            if state == 1:
                with self._cond:
                    self._held[key_binding] = {key["key"], *key["mods"]}

            if state is None or state == 1:
                for mod in key["mods"]:
                    press_key(mod)
                    sleep(self.key_mod_delay)

                press_key(key["key"])

            if state is None:
                if hold:
                    sleep(hold)
                else:
                    sleep(self.key_default_delay)

            if "hold" in key:
                sleep(0.1)

            if state is None or state == 0:
                release_key(key["key"])

                for mod in key["mods"]:
                    sleep(self.key_mod_delay)
                    release_key(mod)

            if state == 0:
                with self._cond:
                    self._held.pop(key_binding, None)
                    self._cond.notify_all()

            if repeat_delay:
                sleep(repeat_delay)
            else:
                sleep(self.key_repeat_delay)

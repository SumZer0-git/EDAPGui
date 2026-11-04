"""Global hotkey listener that distinguishes the numeric keypad."""

import queue
from dataclasses import dataclass
from time import monotonic
from typing import Callable

HotkeySteps = tuple[tuple[frozenset[int], ...], ...]


class ActionQueue:
    """Hands actions from the keyboard listener thread over to the thread that calls run_pending (the GUI thread)."""

    def __init__(self):
        self._actions = queue.Queue()

    def put(self, action: Callable[[], None]):
        self._actions.put(action)

    def run_pending(self):
        while True:
            try:
                action = self._actions.get_nowait()
            except queue.Empty:
                return
            action()


@dataclass
class _RegisteredHotkey:
    steps: HotkeySteps
    callback: Callable[[], None]
    index: int = 0
    last_update: float = 0.0


class HotkeyListener:
    def __init__(self, keyboard):
        self.keyboard = keyboard
        self.hotkeys: list[_RegisteredHotkey] = []
        self.pressed_keys: set[int] = set()
        self.remove_hook = None

    def add_hotkey(self, hotkey, callback):
        steps = tuple(
            tuple(frozenset(combination) for combination in step)
            for step in self.keyboard.parse_hotkey_combinations(hotkey)
        )
        self.hotkeys.append(_RegisteredHotkey(steps, callback))

    def start(self):
        if self.hotkeys and self.remove_hook is None:
            self.remove_hook = self.keyboard.hook(self._handle_event)

    def stop(self):
        if self.remove_hook is not None:
            self.keyboard.unhook(self.remove_hook)
            self.remove_hook = None
        self.pressed_keys.clear()

    def _handle_event(self, event):
        if event.is_keypad:
            return

        if event.event_type == self.keyboard.KEY_DOWN:
            self.pressed_keys.add(event.scan_code)
            self._handle_key_down(event.scan_code)
        elif event.event_type == self.keyboard.KEY_UP:
            self.pressed_keys.discard(event.scan_code)

    def _handle_key_down(self, scan_code):
        now = monotonic()
        for hotkey in self.hotkeys:
            if hotkey.index and now - hotkey.last_update >= 1:
                hotkey.index = 0

            index = hotkey.index

            choices = hotkey.steps[index]
            if any(self.pressed_keys == combination for combination in choices):
                if index + 1 == len(hotkey.steps):
                    hotkey.callback()
                    index = 0
                else:
                    index += 1
                    hotkey.last_update = now
            elif index and scan_code not in set().union(*choices):
                index = 0

            hotkey.index = index

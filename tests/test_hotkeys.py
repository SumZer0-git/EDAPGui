"""Tests for global hotkey handling."""

import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import keyboard

from controls.hotkeys import ActionQueue, HotkeyListener


class FakeKeyboard:
    KEY_DOWN = keyboard.KEY_DOWN
    KEY_UP = keyboard.KEY_UP

    parse_hotkey_combinations = staticmethod(keyboard.parse_hotkey_combinations)

    def hook(self, callback):
        self.callback = callback
        return callback

    def unhook(self, callback):
        self.removed_callback = callback


class HotkeyListenerTestCase(unittest.TestCase):
    def setUp(self):
        self.keyboard = FakeKeyboard()
        self.listener = HotkeyListener(self.keyboard)
        self.calls = []
        self.listener.add_hotkey("home", lambda: self.calls.append("home"))
        self.listener.add_hotkey("ins", lambda: self.calls.append("ins"))
        self.listener.add_hotkey("end", lambda: self.calls.append("end"))
        self.listener.start()

    def tearDown(self):
        self.listener.stop()

    def send(self, key, event_type, is_keypad=False):
        self.keyboard.callback(SimpleNamespace(scan_code=key, event_type=event_type, is_keypad=is_keypad))

    def test_regular_navigation_keys_trigger_hotkeys(self):
        for name in ("home", "ins", "end"):
            with self.subTest(key=name):
                self.send(keyboard.key_to_scan_codes(name)[0], keyboard.KEY_DOWN)
                self.assertIn(name, self.calls)
                self.send(keyboard.key_to_scan_codes(name)[0], keyboard.KEY_UP)

    def test_keypad_navigation_keys_do_not_trigger_hotkeys(self):
        for name in ("home", "ins", "end"):
            with self.subTest(key=name):
                self.send(keyboard.key_to_scan_codes(name)[0], keyboard.KEY_DOWN, is_keypad=True)
                self.send(keyboard.key_to_scan_codes(name)[0], keyboard.KEY_UP, is_keypad=True)

        self.assertEqual(self.calls, [])

    def test_modifier_hotkey_still_works_and_ignores_keypad(self):
        callback = mock.Mock()
        fake_keyboard = FakeKeyboard()
        listener = HotkeyListener(fake_keyboard)
        listener.add_hotkey("ctrl+home", callback)
        listener.start()
        self.addCleanup(listener.stop)

        ctrl_scan_code = keyboard.key_to_scan_codes("left ctrl")[0]
        home_scan_code = keyboard.key_to_scan_codes("home")[0]
        fake_keyboard.callback(SimpleNamespace(scan_code=ctrl_scan_code, event_type=keyboard.KEY_DOWN, is_keypad=False))
        fake_keyboard.callback(SimpleNamespace(scan_code=home_scan_code, event_type=keyboard.KEY_DOWN, is_keypad=True))
        callback.assert_not_called()

        fake_keyboard.callback(SimpleNamespace(scan_code=home_scan_code, event_type=keyboard.KEY_DOWN, is_keypad=False))
        callback.assert_called_once_with()

    def test_action_queued_by_listener_thread_runs_on_the_processing_thread(self):
        actions = ActionQueue()
        run_on = []

        listener_thread = threading.Thread(
            target=lambda: actions.put(lambda: run_on.append(threading.current_thread()))
        )
        listener_thread.start()
        listener_thread.join()
        self.assertEqual(run_on, [])

        actions.run_pending()
        self.assertEqual(run_on, [threading.current_thread()])

        actions.run_pending()
        self.assertEqual(len(run_on), 1)

    def test_multi_step_hotkey_still_works(self):
        callback = mock.Mock()
        fake_keyboard = FakeKeyboard()
        listener = HotkeyListener(fake_keyboard)
        listener.add_hotkey("ctrl+a, b", callback)
        listener.start()
        self.addCleanup(listener.stop)

        for name, event_type in (
            ("left ctrl", keyboard.KEY_DOWN),
            ("a", keyboard.KEY_DOWN),
            ("a", keyboard.KEY_UP),
            ("left ctrl", keyboard.KEY_UP),
            ("b", keyboard.KEY_DOWN),
        ):
            fake_keyboard.callback(
                SimpleNamespace(
                    scan_code=keyboard.key_to_scan_codes(name)[0],
                    event_type=event_type,
                    is_keypad=False,
                )
            )

        callback.assert_called_once_with()

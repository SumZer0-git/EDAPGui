"""Tests for status and user-message routing."""

import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from core.autopilot import EDAutopilot
from gui.main_window import APGui


class StatusReportingTests(unittest.TestCase):
    def setUp(self):
        self.window = APGui.__new__(APGui)
        self.window.ui_queue = queue.Queue()
        self.window.status_text = "Idle"
        self.window.status = Mock()
        self.window.log_msg = Mock()
        self.window.ed_ap = SimpleNamespace(vce=Mock())

        self.autopilot = EDAutopilot.__new__(EDAutopilot)
        self.autopilot.ap_state = "Idle"
        self.autopilot.update_overlay = Mock()
        self.autopilot._ui_callback = self.window.callback
        self.autopilot.ap_ckb = self.autopilot._dispatch_callback

    def test_ap_status_is_sent_to_footer_overlay_and_log_history(self):
        self.autopilot.set_ap_status("Jump")

        self.assertEqual(self.autopilot.ap_state, "Jump")
        self.autopilot.update_overlay.assert_called_once_with()
        self.window.status.configure.assert_called_once_with(text="Jump")
        self.assertEqual(self.window.status_text, "Jump")
        self.window.log_msg.assert_called_once_with("Status update: Jump")

    def test_user_message_goes_to_gui_log_without_changing_ap_status(self):
        self.autopilot.notify_user("Abbruch wegen Treibstoffmangel")

        self.assertEqual(self.autopilot.ap_state, "Idle")
        self.autopilot.update_overlay.assert_not_called()
        self.window.status.configure.assert_not_called()
        self.window.log_msg.assert_called_once_with("Abbruch wegen Treibstoffmangel")

    def test_voice_notification_keeps_voice_and_gui_log_routing(self):
        self.autopilot.notify_user("Docking complete", speak=True)

        self.window.log_msg.assert_called_once_with("Docking complete")
        self.window.ed_ap.vce.say.assert_called_once_with("Docking complete")
        self.window.status.configure.assert_not_called()

    def test_legacy_log_callbacks_are_notifications_not_ap_status(self):
        self.autopilot.ap_ckb("log", "A warning")
        self.autopilot.ap_ckb("log+vce", "A spoken warning")

        self.assertEqual(
            self.window.log_msg.call_args_list,
            [call("A warning"), call("A spoken warning")],
        )
        self.window.ed_ap.vce.say.assert_called_once_with("A spoken warning")
        self.window.status.configure.assert_not_called()
        self.autopilot.update_overlay.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""CV frame buffering and GUI window lifecycle tests."""

import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from core.autopilot import EDAutopilot
from gui import fields
from gui.cv_view import CvFrames, CvView, fit_window
from gui.overlay import Overlay


class CvViewTestCase(unittest.TestCase):
    def test_resize_scales_cached_frames_in_both_directions_without_new_capture(self):
        root = Mock()
        frames = CvFrames()
        view = CvView(root, frames)
        window, label = Mock(), Mock()
        view.windows["target"] = window, {"target": label}
        frames.open("target")
        image = np.zeros((100, 200, 3), np.uint8)
        frames.submit("target", image)
        with patch("gui.cv_view.ImageTk.PhotoImage") as photo:
            for width, height, expected in ((400, 300, (400, 200)), (100, 100, (100, 50)), (600, 200, (400, 200))):
                window.winfo_width.return_value = width
                window.winfo_height.return_value = height
                view.refresh()
                self.assertEqual(photo.call_args.args[0].size, expected)
            count = photo.call_count
            view.refresh()
            self.assertEqual(photo.call_count, count)
        self.assertEqual(view._images["target"].size, (200, 100))
        view.close_view("target")
        self.assertEqual(view._images, {})
        self.assertEqual(view._sizes, {})

    def test_hud_resize_scales_both_cached_images_with_preserved_aspect_ratio(self):
        frames = CvFrames()
        frames.open("hud")
        view = CvView(Mock(), frames)
        window = Mock()
        window.winfo_width.return_value = 400
        window.winfo_height.return_value = 300
        view.windows["hud"] = window, {"sc_disengage_label_up": Mock(), "disengage2": Mock()}
        for source in view.windows["hud"][1]:
            frames.submit(source, np.zeros((50, 200, 3), np.uint8))
        with patch("gui.cv_view.ImageTk.PhotoImage") as photo:
            view.refresh()
            self.assertEqual([call.args[0].size for call in photo.call_args_list], [(400, 100), (400, 100)])
            window.winfo_width.return_value = 200
            view.refresh()
            self.assertEqual([call.args[0].size for call in photo.call_args_list[-2:]], [(200, 50), (200, 50)])

    def test_buffer_keeps_latest_copy_and_discards_disabled_frames(self):
        buffer = CvFrames()
        buffer.open("compass")
        image = np.zeros((20, 30, 3), np.uint8)
        worker = threading.Thread(target=lambda: buffer.submit("compass", image))
        worker.start()
        worker.join()
        image[:] = 100
        frames = buffer.take()
        self.assertTrue(np.all(frames["compass"] == 0))
        buffer.submit("compass", image)
        buffer.submit("compass", image + 1)
        self.assertEqual(len(buffer.take()), 1)
        buffer.close("compass")
        buffer.submit("target", image)
        self.assertEqual(buffer.take(), {})

    def test_positions_and_sizes_fit_negative_and_portrait_monitors(self):
        for work in ((0, 0, 1920, 1040), (-1920, 484, 0, 1564), (3840, 130, 4920, 2050)):
            for x, y in ((-5000, -5000), (6000, 6000)):
                with self.subTest(work=work, x=x):
                    px, py, width, height = fit_window(x, y, 3000, 2200, work)
                    self.assertGreaterEqual(px, work[0])
                    self.assertGreaterEqual(py - 30, work[1])
                    self.assertLessEqual(px + width, work[2])
                    self.assertLessEqual(py + height + 30, work[3])

    def test_buttons_open_focus_close_and_reopen_without_resetting_position(self):
        root = Mock()
        root.winfo_x.return_value = -500
        root.winfo_y.return_value = 500
        buffer = CvFrames()
        view = CvView(root, buffer)
        image = np.zeros((40, 60, 3), np.uint8)
        with (
            patch("gui.cv_view.tk.Toplevel") as window_factory,
            patch("gui.cv_view.tk.Label"),
            patch("gui.cv_view.ImageTk.PhotoImage"),
            patch("gui.cv_view.win32api.MonitorFromPoint"),
            patch("gui.cv_view.win32api.GetMonitorInfo", return_value={"Work": (-1920, 0, 0, 1080)}),
            patch("gui.cv_view.dark_titlebar") as dark,
        ):
            window_factory.return_value.winfo_width.return_value = 600
            window_factory.return_value.winfo_height.return_value = 300
            view.open_view("compass")
            view.open_view("compass")
            self.assertEqual(window_factory.call_count, 1)
            window_factory.return_value.lift.assert_called_once()
            dark.assert_called_once_with(window_factory.return_value)
            buffer.submit("compass", image)
            view.refresh()
            buffer.submit("compass", image)
            view.refresh()
            window_factory.return_value.geometry.assert_called_once()
            view.close_view("compass")
            buffer.submit("compass", image)
            view.refresh()
            self.assertEqual(window_factory.call_count, 1)
            view.open_view("compass")
            buffer.submit("compass", image)
            view.refresh()
            self.assertEqual(window_factory.call_count, 2)
            view.close()
            root.after_cancel.assert_called_once()
            self.assertEqual(view.windows, {})

    def test_overlay_switch_updates_runtime_and_clears_only_diagnostics(self):
        ap = EDAutopilot.__new__(EDAutopilot)
        ap.config = {}
        ap.overlay = Mock()
        field = fields.FIELDS_BY_KEY["DebugOverlay"]
        fields.write(field, ap, True)
        self.assertTrue(ap.debug_overlay)
        self.assertTrue(ap.config["DebugOverlay"])
        ap.overlay.overlay_clear_diagnostics.assert_not_called()
        fields.write(field, ap, False)
        self.assertFalse(ap.debug_overlay)
        ap.overlay.overlay_clear_diagnostics.assert_called_once()
        ap.overlay.overlay_clear.assert_not_called()

    def test_hud_sources_share_one_selection_and_close_discards_pending_images(self):
        buffer = CvFrames()
        buffer.open("hud")
        image = np.zeros((20, 30, 3), np.uint8)
        for source in ("sc_disengage_label_up", "disengage2", "target"):
            buffer.submit(source, image)
        self.assertEqual(set(buffer.take()), {"sc_disengage_label_up", "disengage2"})
        buffer.submit("disengage2", image)
        buffer.close("hud")
        self.assertEqual(buffer.take(), {})
        self.assertFalse(buffer.is_open("disengage2"))
        self.assertNotIn("Enable_CV_View", fields.FIELDS_BY_KEY)

    def test_overlay_cleanup_preserves_status_and_progress(self):
        overlay = Overlay.__new__(Overlay)
        overlay._lock = threading.Lock()
        overlay._lines = {"debug": object()}
        overlay._floating_text = {"ocr": object()}
        overlay._text = {"status": "Idle"}
        overlay._bars = {"route": 0.5}
        overlay.overlay_clear_diagnostics()
        self.assertEqual(overlay._lines, {})
        self.assertEqual(overlay._floating_text, {})
        self.assertEqual(overlay._text, {"status": "Idle"})
        self.assertEqual(overlay._bars, {"route": 0.5})

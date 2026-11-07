"""Tests for the screen region scaling."""

import unittest
from unittest.mock import Mock, patch

import numpy as np

from tests.helpers import FakeScreen, ScreenshotScreen
from vision.regions import ScreenRegions, reg_scale_for_station, size_scale_for_station
from vision.screen import Screen


class RegionScalingTestCase(unittest.TestCase):
    REGION = {"rect": [0.1, 0.3, 0.9, 0.8]}

    def test_reference_resolution_keeps_the_region(self):
        scaled = reg_scale_for_station(self.REGION, 1920, 1080)

        self.assertEqual(scaled["rect"], [0.1, 0.3, 0.9, 0.8])

    def test_same_aspect_ratio_keeps_the_region(self):
        for width, height in ((2560, 1440), (3840, 2160)):
            scaled = reg_scale_for_station(self.REGION, width, height)
            self.assertEqual(scaled["rect"][0], 0.1)
            self.assertEqual(scaled["rect"][2], 0.9)
            self.assertAlmostEqual(scaled["rect"][1], 0.3)
            self.assertAlmostEqual(scaled["rect"][3], 0.8)

    def test_taller_screen_shrinks_the_region_around_the_centre(self):
        scaled = reg_scale_for_station(self.REGION, 1920, 1200)

        self.assertAlmostEqual(scaled["rect"][1], 0.5 - (0.5 - 0.3) / (1200 / 1080))
        self.assertAlmostEqual(scaled["rect"][3], 0.5 + (0.8 - 0.5) / (1200 / 1080))

    def test_size_scales_with_width_only(self):
        self.assertEqual(size_scale_for_station(100, 40, 1920, 1080), (100, 40))
        self.assertEqual(size_scale_for_station(100, 40, 3840, 2160), (200, 80))
        self.assertEqual(size_scale_for_station(100, 40, 1920, 1200), (100, 40))

    def test_expanded_capture_returns_exact_original_region_at_screen_edges(self):
        image = np.arange(60 * 100 * 3, dtype=np.uint8).reshape((60, 100, 3))
        screen = Mock(screen_width=100, screen_height=60)
        screen.get_screen.side_effect = lambda x0, y0, x1, y1, rgb: image[y0:y1, x0:x1]
        for rect in ((5, 40, 35, 60), (25, 10, 55, 30)):
            with self.subTest(rect=rect):
                result, context = Screen.get_screen_region_with_context(screen, rect, False)
                self.assertTrue(np.array_equal(result, image[rect[1] : rect[3], rect[0] : rect[2]]))
                self.assertGreater(context.size, result.size)

    def test_normal_compass_capture_does_not_capture_extra_context(self):
        screen = FakeScreen(np.zeros((400, 400, 3), np.uint8))
        regions = ScreenRegions(screen, Mock())
        regions.templates.template = {"compass": {"image": np.ones((10, 10), np.uint8)}}
        with patch("vision.regions.logger.isEnabledFor", return_value=False):
            with patch.object(screen, "get_screen_region_with_context") as context:
                regions.match_compass_multiscale()
                context.assert_not_called()

    def test_debug_compass_uses_same_region_as_normal_capture(self):
        image = np.random.default_rng(42).integers(0, 256, (216, 384, 3), dtype=np.uint8)
        screen = ScreenshotScreen(image)
        regions = ScreenRegions(screen, Mock())
        regions.templates.template = {"compass": {"image": np.ones((10, 10), np.uint8)}}
        with patch("vision.regions.logger.isEnabledFor", return_value=False):
            normal, normal_match, normal_scale = regions.match_compass_multiscale()
        regions.compass_scale_hint = None
        with patch("vision.regions.logger.isEnabledFor", return_value=True):
            debug, debug_match, debug_scale = regions.match_compass_multiscale()
        self.assertTrue(np.array_equal(normal, debug))
        self.assertEqual(normal_match, debug_match)
        self.assertEqual(normal_scale, debug_scale)
        self.assertGreater(regions.compass_debug_context.size, debug.size)

    def test_target_callback_without_debug_does_not_capture_context(self):
        screen = FakeScreen(np.zeros((400, 400, 3), np.uint8))
        regions = ScreenRegions(screen, Mock())
        callback = Mock()
        with (
            patch("vision.regions.logger.isEnabledFor", return_value=False),
            patch.object(screen, "get_screen_region_with_context") as context,
        ):
            regions.capture_region_filtered(screen, "target", False, callback)
        context.assert_not_called()
        callback.assert_called_once_with(screen.image)

    def test_target_context_scale_and_edges(self):
        image = np.zeros((2160, 3840, 3), np.uint8)
        screen = Mock(screen_width=3840, screen_height=2160)
        screen.get_screen.side_effect = lambda x0, y0, x1, y1, rgb: image[y0:y1, x0:x1]
        result, context = Screen.get_screen_region_with_context(screen, (1267, 500, 2534, 1429), False, 1.5)
        self.assertEqual(result.shape, (929, 1267, 3))
        self.assertEqual(context.shape, (1394, 1901, 3))
        screen.get_screen.assert_called_once_with(950, 268, 2851, 1662, False)
        for rect in ((0, 0, 1267, 929), (2573, 1231, 3840, 2160)):
            with self.subTest(rect=rect):
                result, context = Screen.get_screen_region_with_context(screen, rect, False, 1.5)
                self.assertEqual(result.shape, (929, 1267, 3))
                x0, y0, x1, y1, _ = screen.get_screen.call_args.args
                self.assertTrue(0 <= x0 < x1 <= 3840)
                self.assertTrue(0 <= y0 < y1 <= 2160)

    def test_target_debug_match_preserves_original_region_and_result(self):
        image = np.random.default_rng(43).integers(0, 256, (216, 384, 3), dtype=np.uint8)
        screen = ScreenshotScreen(image)
        templates = Mock()
        templates.template = {"target": {"image": np.arange(100, dtype=np.uint8).reshape(10, 10)}}
        regions = ScreenRegions(screen, templates)
        with patch("vision.regions.logger.isEnabledFor", return_value=False):
            normal, normal_match, _ = regions.match_template_in_region("target", "target", False)
        callback = Mock()
        with (
            patch("vision.regions.logger.isEnabledFor", return_value=True),
            patch.object(
                screen, "get_screen_region_with_context", wraps=screen.get_screen_region_with_context
            ) as capture,
        ):
            debug, debug_match, _ = regions.match_template_in_region("target", "target", False, callback)
        capture.assert_called_once_with(regions.reg["target"]["rect"], False, scale=1.5)
        self.assertTrue(np.array_equal(normal, debug))
        self.assertEqual(normal_match, debug_match)
        self.assertTrue(
            np.array_equal(callback.call_args.args[0], screen.get_screen_region(regions.reg["target"]["rect"], False))
        )
        self.assertGreater(regions.target_debug_context.size, normal.size)
        with patch("vision.regions.logger.isEnabledFor", return_value=False):
            regions.capture_region_filtered(screen, "target", False)
        self.assertIsNone(regions.target_debug_context)


if __name__ == "__main__":
    unittest.main()

"""Tests for template matching and the screen detection on real screenshot crops.

The crops in tests/fixtures were captured at the 3440x1440 reference resolution, so the templates are
loaded unscaled. A fake screen returns the crop for every region, which exercises the real region
filters, templates, thresholds and offset calculations without the game or a monitor.
"""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core import paths
from routines.flight import FlightMixin
from tests.helpers import FakeScreen, load_fixture_image, pad_to_region
from vision.detection import DetectionMixin
from vision.regions import ScreenRegions
from vision.templates import ImageTemplates


class Detector(DetectionMixin):
    cv_view = False


class MatchingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = ImageTemplates(2160)
        cls.images = {
            name: pad_to_region(load_fixture_image(name))
            for name in ("compass", "navpoint", "navpoint-behind", "navpoint-rim", "target", "disengage")
        }
        cls.images["message"] = load_fixture_image("disengage")
        cls.images["empty"] = np.zeros((700, 700, 3), np.uint8)

    def regions(self, image_name):
        return ScreenRegions(FakeScreen(self.images[image_name]), self.templates)

    def detect(self, method, image_name):
        return getattr(Detector(), method)(self.regions(image_name))


class TemplateTestCase(MatchingTestCase):
    def test_all_templates_are_loaded(self):
        for name, template in self.templates.template.items():
            with self.subTest(template=name):
                self.assertIsNotNone(template["image"])
                self.assertEqual(template["image"].shape[::-1], (template["width"], template["height"]))

    def test_templates_are_scaled(self):
        half = ImageTemplates(1080)
        full = ImageTemplates(2160)

        for name in ("compass", "navpoint", "target"):
            with self.subTest(template=name):
                self.assertAlmostEqual(half.template[name]["width"], full.template[name]["width"] / 2, delta=1)
                self.assertAlmostEqual(half.template[name]["height"], full.template[name]["height"] / 2, delta=1)

    def test_template_is_found_at_its_position(self):
        regions = self.regions("empty")
        for name in ("compass", "target", "navpoint"):
            with self.subTest(template=name):
                template = self.templates.template[name]["image"]
                canvas = np.zeros((300, 400), np.uint8)
                canvas[40 : 40 + template.shape[0], 25 : 25 + template.shape[1]] = template

                _, (_, max_val, _, max_loc), _ = regions.match_template_in_image(canvas, name)

                self.assertGreater(max_val, 0.99)
                self.assertEqual(max_loc, (25, 40))

    def test_x3_matching_finds_the_template_in_a_colour_image(self):
        regions = self.regions("empty")
        template = self.templates.template["compass"]["image"]
        canvas = np.zeros((300, 400, 3), np.uint8)
        canvas[60 : 60 + template.shape[0], 90 : 90 + template.shape[1]] = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)

        _, (_, max_val, _, max_loc), _ = regions.match_template_in_image_x3(canvas, "compass")

        self.assertGreater(max_val, 0.99)
        self.assertEqual(max_loc, (90, 60))


class CompassTestCase(MatchingTestCase):
    def test_compass_is_found(self):
        for name in ("compass", "navpoint", "navpoint-behind"):
            with self.subTest(image=name):
                self.assertTrue(self.detect("have_destination", name))

    def test_no_compass_in_other_screens(self):
        for name in ("empty", "disengage"):
            with self.subTest(image=name):
                self.assertFalse(self.detect("have_destination", name))

    def test_nav_point_ahead(self):
        offset = self.detect("get_nav_offset", "compass")

        self.assertEqual(offset["z"], 1.0)
        self.assertAlmostEqual(offset["x"], 0.0, delta=0.1)
        self.assertAlmostEqual(offset["roll"], 0, delta=15)

    def test_filled_nav_point_in_sun_glare_is_ahead(self):
        offset = self.detect("get_nav_offset", "navpoint")

        self.assertEqual(offset["z"], 1.0)
        self.assertAlmostEqual(offset["x"], 0.17, delta=0.1)
        self.assertGreater(offset["roll"], 90)
        self.assertLess(abs(offset["yaw"]), 20)

    def test_nav_point_behind_at_the_top(self):
        offset = self.detect("get_nav_offset", "navpoint-behind")

        self.assertEqual(offset["z"], -1.0)
        self.assertAlmostEqual(offset["x"], 0.0, delta=0.1)
        self.assertGreater(offset["roll"], 90)
        self.assertGreater(offset["yaw"], 150)

    def test_nav_point_ahead_at_the_side_rim_needs_a_roll(self):
        # Compass crop from a log where the alignment pitched back and forth instead of rolling
        with patch.object(DetectionMixin, "dump_compass_debug"):
            offset = self.detect("get_nav_offset", "navpoint-rim")

        self.assertEqual(offset["z"], 1.0)
        self.assertLess(offset["x"], -0.8)
        self.assertLess(offset["yaw"], -60)
        self.assertTrue(FlightMixin.nav_needs_reroll(offset, 10))

    def test_white_nav_point_touching_a_bright_edge_is_found(self):
        image = np.zeros((120, 120, 3), np.uint8)
        cv2.circle(image, (60, 60), 55, (0, 80, 160), 2)
        cv2.circle(image, (66, 28), 6, (255, 255, 255), -1)
        # A bright hull edge touching the dot merges it into one large blob
        cv2.line(image, (0, 10), (60, 34), (255, 255, 255), 4)

        found = DetectionMixin.find_white_navpoint(image, (60, 60), 55)

        self.assertIsNotNone(found)
        self.assertAlmostEqual(found[0], 66, delta=4)
        self.assertAlmostEqual(found[1], 28, delta=4)
        self.assertFalse(found[2], "filled dot, not a ring")

    def test_offset_values_stay_within_range(self):
        for name in ("compass", "navpoint", "navpoint-behind"):
            with self.subTest(image=name):
                offset = self.detect("get_nav_offset", name)
                self.assertTrue(-1.0 <= offset["x"] <= 1.0)
                self.assertTrue(-1.0 <= offset["y"] <= 1.0)
                self.assertTrue(-180 <= offset["roll"] <= 180)

    def test_no_offset_without_a_visible_compass(self):
        # A guessed position would make the compass alignment steer away from the target
        for name in ("target", "empty"):
            with self.subTest(image=name), patch.object(DetectionMixin, "dump_compass_debug") as dump:
                self.assertIsNone(self.detect("get_nav_offset", name))
                self.assertEqual(dump.call_args.kwargs["kind"], "missing")


class TargetTestCase(MatchingTestCase):
    def test_target_circle_is_found_and_offset(self):
        offset = self.detect("get_destination_offset", "target")

        self.assertIsNotNone(offset)
        self.assertAlmostEqual(offset["x"], -475.6, delta=5)
        self.assertAlmostEqual(offset["y"], 220.9, delta=5)

    def test_target_match_score_and_offset_are_logged(self):
        with self.assertLogs("ed_log", level="DEBUG") as captured:
            self.detect("get_destination_offset", "target")

        target_log = next(message for message in captured.output if "Target detection:" in message)
        self.assertIn("roi=700x700", target_log)
        self.assertRegex(target_log, r"filter_pixels=\d+/490000 \(\d+\.\d+%\)")
        self.assertRegex(target_log, r"template=\d+x\d+, score=0\.\d{4}, threshold=0\.54")
        self.assertIn("offset x=", target_log)

    def test_target_miss_logs_filter_pixel_count(self):
        with self.assertLogs("ed_log", level="DEBUG") as captured:
            self.detect("get_destination_offset", "empty")

        target_log = next(message for message in captured.output if "Target detection:" in message)
        self.assertIn("filter_pixels=0/490000 (0.00%)", target_log)
        self.assertIn("score=0.0000, threshold=0.54", target_log)
        self.assertIn("(below threshold)", target_log)

    def test_target_debug_saves_the_original_failed_capture(self):
        image = np.full((700, 700, 3), (40, 20, 10), dtype=np.uint8)
        regions = ScreenRegions(FakeScreen(image), self.templates)
        detector = Detector()
        with tempfile.TemporaryDirectory() as folder, patch.object(paths, "DEBUG_DIR", Path(folder)):
            with patch.object(DetectionMixin, "_target_dumps", 0), self.assertLogs("ed_log", level="DEBUG") as logs:
                self.assertIsNone(detector.get_destination_offset(regions))
                image[:] = 0
                detector.dump_target_debug()
                detector.dump_target_debug()

            files = list((Path(folder) / "target").glob("*.png"))
            self.assertEqual(len(files), 1)
            self.assertRegex(files[0].name, r"^target-missing-\d{8}-\d{6}-\d{6}-s0\.0000\.png$")
            saved = cv2.imread(str(files[0]))
            self.assertTrue(np.all(saved == (40, 20, 10)))
            self.assertTrue(any("Saved target debug image:" in line for line in logs.output))

    def test_target_debug_is_disabled_outside_debug_and_clears_after_success(self):
        detector = Detector()
        with (
            patch("vision.detection.logger.isEnabledFor", return_value=False),
            patch("vision.detection.cv2.imwrite") as write,
        ):
            self.assertIsNone(detector.get_destination_offset(self.regions("empty")))
            detector.dump_target_debug()
            write.assert_not_called()
        with self.assertLogs("ed_log", level="DEBUG"), patch("vision.detection.cv2.imwrite") as write:
            self.assertIsNone(detector.get_destination_offset(self.regions("empty")))
            self.assertIsNotNone(detector.get_destination_offset(self.regions("target")))
            detector.dump_target_debug()
            write.assert_not_called()

    def test_target_debug_limit_and_write_failure(self):
        detector = Detector()
        with (
            self.assertLogs("ed_log", level="DEBUG"),
            patch.object(DetectionMixin, "_target_dumps", 12),
            patch("vision.detection.cv2.imwrite") as write,
        ):
            detector.get_destination_offset(self.regions("empty"))
            detector.dump_target_debug()
            write.assert_not_called()
        with (
            patch.object(DetectionMixin, "_target_dumps", 0),
            patch("vision.detection.paths.debug_path", return_value="target.png"),
            patch("vision.detection.cv2.imwrite", return_value=False),
            self.assertLogs("ed_log", level="WARNING") as logs,
        ):
            with patch("vision.detection.logger.isEnabledFor", side_effect=lambda level: level >= logging.DEBUG):
                detector.get_destination_offset(self.regions("empty"))
                detector.dump_target_debug()
            self.assertIn("Could not save target debug image", logs.output[-1])
            self.assertEqual(DetectionMixin._target_dumps, 0)

    def test_no_target_in_other_screens(self):
        for name in ("empty", "compass", "disengage"):
            with self.subTest(image=name):
                self.assertIsNone(self.detect("get_destination_offset", name))

    def test_target_is_not_occluded(self):
        for name in ("empty", "target", "disengage"):
            with self.subTest(image=name):
                self.assertFalse(self.detect("is_destination_occluded", name))

    def test_occluded_template_is_recognised(self):
        template = self.templates.template["target_occluded"]["image"]
        image = np.zeros((700, 700, 3), np.uint8)
        # The region filter keeps only pixels within the occluded colour range, so draw the template in that colour.
        mask = template > 128
        image[: template.shape[0], : template.shape[1]][mask] = cv2.cvtColor(
            np.uint8([[[20, 120, 180]]]), cv2.COLOR_HSV2BGR
        )[0, 0]
        regions = ScreenRegions(FakeScreen(image), self.templates)

        self.assertTrue(Detector().is_destination_occluded(regions))


class DisengageTestCase(MatchingTestCase):
    def test_disengage_message_is_recognised(self):
        self.assertTrue(Detector().sc_disengage_label_up(self.regions("message")))

    def test_empty_screen_has_no_message(self):
        self.assertFalse(self.detect("sc_disengage_label_up", "empty"))

    def test_small_dropout_prompt_passes_the_message_gate(self):
        image = np.zeros((100, 100, 3), np.uint8)
        prompt = np.uint8([[[90, 150, 255]]])
        image[20:40, 20:50] = cv2.cvtColor(prompt, cv2.COLOR_HSV2BGR)[0, 0]
        regions = ScreenRegions(FakeScreen(image), self.templates)

        self.assertTrue(regions.message_text_present())
        self.assertGreaterEqual(regions.last_message_fraction, 0.03)


class FsdAlignmentPromptTestCase(MatchingTestCase):
    def make_detector(self, recognized_text):
        detector = Detector()
        detector.ocr = Mock()
        detector.ocr.image_simple_ocr.return_value = recognized_text
        detector.ocr.string_similarity.side_effect = lambda expected, actual: float(expected == actual)
        detector.locale = Mock()
        detector.locale.all_values.return_value = ["ALIGN WITH TARGET DESTINATION", "AUF ZIEL AUSRICHTEN"]
        return detector

    def test_english_and_german_prompts_are_recognized(self):
        for text in ("ALIGN WITH TARGET DESTINATION", "AUF ZIEL AUSRICHTEN"):
            with self.subTest(text=text):
                detector = self.make_detector([text])
                self.assertTrue(detector.fsd_alignment_prompt(self.regions("empty")))

    def test_unrelated_or_unreadable_text_is_not_a_prompt(self):
        for text in (["PRESS TO DISENGAGE"], None, []):
            with self.subTest(text=text):
                detector = self.make_detector(text)
                self.assertFalse(detector.fsd_alignment_prompt(self.regions("empty")))


class NativeTemplateTestCase(unittest.TestCase):
    def test_native_set_is_loaded_unscaled(self):
        templates = ImageTemplates(2160)

        self.assertEqual((templates.template["compass"]["width"], templates.template["compass"]["height"]), (112, 108))
        self.assertEqual(len(templates.template["target"]["anchor"]), 2)

    def test_lower_heights_scale_the_native_set_down(self):
        templates = ImageTemplates(1080)

        self.assertEqual((templates.template["compass"]["width"], templates.template["compass"]["height"]), (56, 54))
        native = ImageTemplates(2160).template["target"]["anchor"]
        scaled = templates.template["target"]["anchor"]
        self.assertAlmostEqual(scaled[0], native[0] / 2, delta=1.0)
        self.assertAlmostEqual(scaled[1], native[1] / 2, delta=1.0)

    def test_other_heights_are_derived_from_the_native_set(self):
        for height in (540, 1440, 4320):
            with self.subTest(height=height):
                templates = ImageTemplates(height)
                self.assertAlmostEqual(templates.template["compass"]["width"], 112 * height / 2160, delta=1)


class RegionFilterTestCase(MatchingTestCase):
    def test_region_rects_follow_the_screen_size(self):
        regions = ScreenRegions(FakeScreen(None, 1920, 1080), self.templates)

        compass = regions.reg["compass"]
        self.assertEqual(compass["rect"], [633, 702, 883, 1080])
        self.assertEqual((compass["width"], compass["height"]), (250, 378))

    def test_all_regions_lie_inside_the_screen(self):
        for width, height in ((1920, 1080), (3440, 1440), (2560, 1440)):
            regions = ScreenRegions(FakeScreen(None, width, height), self.templates)
            for name, region in regions.reg.items():
                with self.subTest(resolution=f"{width}x{height}", region=name):
                    left, top, right, bottom = region["rect"]
                    self.assertTrue(0 <= left < right <= width)
                    self.assertTrue(0 <= top < bottom <= height)

    def test_equalize_returns_a_grey_image(self):
        result = self.regions("compass").equalize(self.images["compass"])

        self.assertEqual(result.shape, self.images["compass"].shape[:2])

    def test_filter_by_color_keeps_only_pixels_in_range(self):
        regions = self.regions("empty")
        orange = cv2.cvtColor(np.uint8([[[10, 200, 180]]]), cv2.COLOR_HSV2BGR)[0, 0]
        image = np.zeros((10, 10, 3), np.uint8)
        image[:, :5] = orange
        image[:, 5:] = (255, 0, 0)

        mask = regions.filter_by_color(image, regions.orange_color_range)

        self.assertTrue((mask[:, :5] == 255).all())
        self.assertTrue((mask[:, 5:] == 0).all())

    def test_sun_filter_uses_the_threshold(self):
        regions = self.regions("empty")
        image = np.full((4, 4, 3), 100, np.uint8)

        regions.set_sun_threshold(125)
        self.assertEqual(regions.filter_sun(image).sum(), 0)
        regions.set_sun_threshold(50)
        self.assertTrue((regions.filter_sun(image) == 255).all())

    def test_sun_percent(self):
        image = np.zeros((100, 100, 3), np.uint8)
        image[:, :50] = 255
        regions = ScreenRegions(FakeScreen(image), self.templates)

        self.assertEqual(regions.sun_percent(regions.screen), 50)


if __name__ == "__main__":
    unittest.main()

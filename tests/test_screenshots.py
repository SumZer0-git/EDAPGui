"""Regression tests with real game screenshots.

The screenshots are not part of the repository. Put them in tests/fixtures/screenshots/<height>p/ named
NN_<scene>_<state>[_<language>].png (for example 2160p/12_target-occluded_moon.png); the tests skip when there are
none. The file names tell what is expected:
 - target-occluded / target-visible / aligned-target: the target ring is detected as occluded or not
 - compass / aligned-target: the compass is found
 - jump-align-msg: OCR recognizes the localized FSD alignment prompt in the HUD
 - disengage-msg: the message gate (message-colored area) lets the message region pass; the OCR is not run
 - no-msg: the message gate must not pass (guards against false alarms that trigger slow OCR runs)
Screenshots whose names contain "crop" or "head-turned" are ignored.
"""

import unittest
from unittest import skipUnless

from tests.helpers import FIXTURES, ScreenshotScreen, load_screenshot
from vision.detection import DetectionMixin
from vision.regions import ScreenRegions
from vision.templates import ImageTemplates

try:
    from vision.ocr import OCR
except ImportError:
    OCR = None

SCREENSHOTS = FIXTURES / "screenshots"
IGNORED = ("crop", "head-turned")
ALIGNMENT_SCREENSHOTS = tuple(sorted(SCREENSHOTS.glob("*p/*jump-align-msg*.png")))


class NoOcr:
    def image_simple_ocr(self, image):
        return None


class Detector(DetectionMixin):
    cv_view = False
    ocr = NoOcr()


class AlignmentPromptLocale:
    def all_values(self, key):
        if key != "ALIGN_WITH_TARGET_MSG":
            raise KeyError(key)
        return ["ALIGN WITH TARGET DESTINATION", "AUF ZIEL AUSRICHTEN"]


def screenshots():
    for path in sorted(SCREENSHOTS.glob("*p/*.png")):
        if not any(word in path.name for word in IGNORED):
            yield path


@unittest.skipUnless(any(screenshots()), "no local screenshots in tests/fixtures/screenshots")
class ScreenshotTestCase(unittest.TestCase):
    def test_screenshots(self):
        templates = {}
        for path in screenshots():
            image = load_screenshot(path)
            height = image.shape[0]
            self.assertEqual(f"{height}p", path.parent.name, f"{path.name} is in the wrong folder")
            if height not in templates:
                templates[height] = ImageTemplates(height)
            regions = ScreenRegions(ScreenshotScreen(image), templates[height])
            detector = Detector()
            name = path.name

            with self.subTest(screenshot=f"{path.parent.name}/{name}"):
                self.assertEqual(
                    detector.is_destination_occluded(regions),
                    "target-occluded" in name,
                    "occluded target",
                )
                if "compass" in name or "aligned-target" in name:
                    self.assertTrue(detector.have_destination(regions), "compass")
                if "compass-behind" in name:
                    self.assertEqual(detector.get_nav_offset(regions)["z"], -1.0, "nav point behind")
                if "type9" in name and "compass" in name:
                    _, (_, score, _, _), scale = regions.match_compass_multiscale()
                    self.assertGreater(scale, 1.1, "larger compass sphere of the Type-9")
                    if "compass-behind-on-rim" in name or "aligned-target" in name or "compass-ahead" in name:
                        self.assertGreater(score, 0.75, "compass match")
                if "compass-behind-on-rim" in name:
                    offset = detector.get_nav_offset(regions)
                    self.assertGreater(max(abs(offset["x"]), abs(offset["y"])), 0.5, "nav point at the sphere rim")
                if "compass-ahead" in name:
                    self.assertEqual(detector.get_nav_offset(regions)["z"], 1.0, "nav point ahead")
                if "aligned-target_compass-ahead_type9" in name:
                    self.assertLess(abs(detector.get_nav_offset(regions)["pit"]), 6, "centered nav point")
                if "compass-ahead-off-target" in name:
                    self.assertGreater(detector.get_nav_offset(regions)["pit"], 10, "nav point above the center")
                # The message gate is only a cheap pre-check (bright scenes may pass it, the OCR decides)
                if "disengage-msg" in name:
                    self.assertTrue(regions.message_text_present(), "disengage message")
                if "no-msg" in name:
                    self.assertFalse(regions.message_text_present(), "false message alarm")


@skipUnless(OCR is not None and ALIGNMENT_SCREENSHOTS, "PaddleOCR or local FSD alignment screenshots unavailable")
class FsdAlignmentPromptScreenshotTestCase(unittest.TestCase):
    def test_alignment_prompt_is_read_in_all_local_screenshots(self):
        templates = ImageTemplates(2160)
        detector = Detector()
        detector.ocr = OCR(screen=None)
        detector.locale = AlignmentPromptLocale()

        for path in ALIGNMENT_SCREENSHOTS:
            with self.subTest(screenshot=path.name):
                image = load_screenshot(path)
                regions = ScreenRegions(ScreenshotScreen(image), templates)
                self.assertTrue(detector.fsd_alignment_prompt(regions))


if __name__ == "__main__":
    unittest.main()

"""Regression tests with real game screenshots.

The screenshots are not part of the repository. Put them in tests/fixtures/screenshots/<height>p/ named
NN_<scene>_<state>[_<language>].png (for example 2160p/12_target-occluded_moon.png); the tests skip when there are
none. The file names tell what is expected:
 - target-occluded / target-visible / aligned-target: the target ring is detected as occluded or not
 - compass / aligned-target: the compass is found
 - disengage-msg: the message gate (message-colored area) lets the message region pass; the OCR is not run
 - no-msg: the message gate must not pass (guards against false alarms that trigger slow OCR runs)
Screenshots whose names contain "crop" or "head-turned" are ignored.
"""

import unittest

from tests.helpers import FIXTURES, ScreenshotScreen, load_screenshot
from vision.detection import DetectionMixin
from vision.regions import ScreenRegions
from vision.templates import ImageTemplates

SCREENSHOTS = FIXTURES / "screenshots"
IGNORED = ("crop", "head-turned")


class NoOcr:
    def image_simple_ocr(self, image):
        return None


class Detector(DetectionMixin):
    cv_view = False
    ocr = NoOcr()


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
                # The message gate is only a cheap pre-check (bright scenes may pass it, the OCR decides)
                if "disengage-msg" in name:
                    self.assertTrue(regions.message_text_present(), "disengage message")
                if "no-msg" in name:
                    self.assertFalse(regions.message_text_present(), "false message alarm")


if __name__ == "__main__":
    unittest.main()

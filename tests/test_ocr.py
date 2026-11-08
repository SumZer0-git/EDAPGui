"""Simple check of OCR to bring back text of a known image."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core import paths

try:
    from vision.ocr import OCR
except ModuleNotFoundError as error:
    if error.name != "paddleocr":
        raise
    OCR = None

if OCR is None:
    sys.modules["paddleocr"] = SimpleNamespace(PaddleOCR=None)
    try:
        from vision.ocr import OCR as HIGHLIGHT_OCR
    finally:
        del sys.modules["paddleocr"]
        sys.modules.pop("vision.ocr", None)
else:
    HIGHLIGHT_OCR = OCR


class HighlightTestCase(unittest.TestCase):
    def test_system_tab_near_the_left_edge_is_not_clipped(self):
        from panels.navigation import EDNavigationPanel
        from tests.helpers import ScreenshotScreen

        for height in (1080, 2160):
            with self.subTest(height=height):
                width = height * 16 // 9
                image = np.zeros((height, width, 3), np.uint8)
                cv2.rectangle(
                    image,
                    (round(width * 0.103), round(height * 0.224)),
                    (round(width * 0.126), round(height * 0.260)),
                    (0, 120, 210),
                    -1,
                )
                screen = ScreenshotScreen(image)
                panel = EDNavigationPanel.__new__(EDNavigationPanel)
                panel.screen = screen
                panel.ocr = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR)
                panel.ocr.screen = screen
                panel.ocr.image_simple_ocr = Mock()
                self.assertEqual(panel._selected_tab(), "system")
                panel.ocr.image_simple_ocr.assert_not_called()

    def test_dim_slanted_highlight_is_selected_without_selecting_inactive_tabs(self):
        ocr = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR)
        for scale in (1, 2):
            for color in (
                (146, 146, 146),
                (170, 170, 170),
                (195, 195, 195),
                (207, 207, 207),
                (255, 255, 255),
                (0, 135, 225),
                (0, 120, 210),
                (0, 100, 180),
                (180, 100, 0),
            ):
                with self.subTest(scale=scale, color=color):
                    image = np.zeros((100 * scale, 600 * scale, 3), np.uint8)
                    cv2.rectangle(image, (320 * scale, 20 * scale), (590 * scale, 65 * scale), (65, 65, 65), -1)
                    polygon = np.array([[20, 35], [290, 20], [290, 65], [20, 80]], np.int32) * scale
                    cv2.fillConvexPoly(image, polygon, color)
                    cv2.putText(
                        image,
                        "NAVIGATION",
                        (45 * scale, 58 * scale),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6 * scale,
                        (0, 40, 100),
                        2 * scale,
                    )
                    before = image.copy()
                    items = ocr.solid_highlighted_items(image, 35 * scale, 35 * scale)
                    self.assertEqual(len(items), 1)
                    self.assertLess(items[0][1], 30 * scale)
                    np.testing.assert_array_equal(image, before)

    def test_dim_text_lines_and_hollow_highlights_are_not_selected(self):
        ocr = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR)
        for color in ((146,) * 3, (170,) * 3, (207,) * 3, (255,) * 3, (0, 120, 210)):
            with self.subTest(color=color):
                image = np.zeros((100, 600, 3), np.uint8)
                cv2.rectangle(image, (20, 20), (290, 80), color, 3)
                cv2.putText(image, "CONTACTS", (320, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                self.assertEqual(ocr.solid_highlighted_items(image, 35, 35), [])

    def test_shaded_orange_highlight_uses_value_without_lowering_the_brightness_floor(self):
        ocr = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR)
        for scale in (1, 2):
            with self.subTest(scale=scale):
                image = np.zeros((100 * scale, 600 * scale, 3), np.uint8)
                for y in range(20 * scale, 80 * scale):
                    color = (0, 110 + y // (3 * scale), 200 + y // (4 * scale))
                    image[y, 20 * scale : 290 * scale] = color
                image[20 * scale : 80 * scale, 320 * scale : 590 * scale] = (0, 70, 139)
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                self.assertLess(int(gray.max()), 150)
                items = ocr.solid_highlighted_items(image, 35 * scale, 35 * scale)
                self.assertEqual(len(items), 1)
                self.assertLess(items[0][1], 30 * scale)

    def test_bright_highlight_retains_priority_over_saturated_fallback(self):
        image = np.zeros((100, 600, 3), np.uint8)
        image[20:80, 20:290] = (255, 255, 255)
        image[20:80, 320:590] = (0, 120, 210)
        items = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR).solid_highlighted_items(image, 35, 35)
        self.assertEqual(len(items), 1)
        self.assertLess(items[0][1], 30)

    def test_dark_inactive_tabs_are_not_highlights_and_multiple_highlights_stay_ambiguous(self):
        ocr = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR)
        image = np.zeros((100, 600, 3), np.uint8)
        for value in (100, 139):
            with self.subTest(inactive_value=value):
                for x in (20, 320):
                    cv2.rectangle(image, (x, 20), (x + 260, 80), (value,) * 3, -1)
                self.assertEqual(ocr.solid_highlighted_items(image, 35, 35), [])
        for x in (20, 320):
            cv2.rectangle(image, (x, 20), (x + 260, 80), (207, 207, 207), -1)
        self.assertEqual(len(ocr.solid_highlighted_items(image, 35, 35)), 2)

    def test_local_dim_navigation_highlight_is_extracted(self):
        path = (
            paths.ROOT
            / "tests"
            / "fixtures"
            / "screenshots"
            / "1080p"
            / "31_crop_cockpit-left-tab-dim_sdr-hud50_de.png"
        )
        if not path.exists():
            self.skipTest("local dim navigation crop unavailable")
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        items = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR).solid_highlighted_items(image, 35, 35)
        self.assertEqual(len(items), 1)
        self.assertLess(items[0][1], 100)
        self.assertGreater(items[0][3], 250)

    def test_local_default_orange_highlight_is_extracted(self):
        path = (
            paths.ROOT
            / "tests"
            / "fixtures"
            / "screenshots"
            / "2160p"
            / "128_crop_cockpit-left-tab-orange_sdr-hud70_en.png"
        )
        if not path.exists():
            self.skipTest("local default-orange navigation crop unavailable")
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        items = HIGHLIGHT_OCR.__new__(HIGHLIGHT_OCR).solid_highlighted_items(image, 70, 70)
        self.assertEqual(len(items), 1)
        self.assertLess(items[0][1], 50)
        self.assertGreater(items[0][3], 450)


@unittest.skipIf(OCR is None, "PaddleOCR is not installed")
class OCRTestCase(unittest.TestCase):
    def test_local_default_orange_tab_is_confirmed_with_real_ocr(self):
        path = (
            paths.ROOT
            / "tests"
            / "fixtures"
            / "screenshots"
            / "2160p"
            / "128_crop_cockpit-left-tab-orange_sdr-hud70_en.png"
        )
        if not path.exists():
            self.skipTest("local default-orange navigation crop unavailable")
        from i18n.localization import LocalizationManager
        from panels.navigation import EDNavigationPanel

        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        panel.screen = Mock(screen_width=3840, screen_height=2160)
        panel.locale = LocalizationManager(str(paths.LOCALES_DIR), "en")
        panel.ocr = OCR(screen=None)
        panel.ocr.capture_region_pct = Mock(return_value=image)
        with patch.object(panel, "_save_recognition_failure"):
            self.assertEqual(panel._selected_tab(), "navigation")

    def test_local_dim_navigation_tab_is_confirmed_with_real_ocr(self):
        path = (
            paths.ROOT
            / "tests"
            / "fixtures"
            / "screenshots"
            / "1080p"
            / "31_crop_cockpit-left-tab-dim_sdr-hud50_de.png"
        )
        if not path.exists():
            self.skipTest("local dim navigation crop unavailable")
        from i18n.localization import LocalizationManager
        from panels.navigation import EDNavigationPanel

        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        panel = EDNavigationPanel.__new__(EDNavigationPanel)
        panel.screen = Mock(screen_width=1920, screen_height=1080)
        panel.locale = LocalizationManager(str(paths.LOCALES_DIR), "de")
        panel.ocr = OCR(screen=None)
        panel.ocr.capture_region_pct = Mock(return_value=image)
        with patch.object(panel, "_save_recognition_failure"):
            self.assertEqual(panel._selected_tab(), "navigation")

    def test_simple_ocr(self):
        """Simple check of OCR to bring back text of a known image."""
        ocr = OCR(screen=None)

        # Load image
        image_path = str(paths.ROOT / "tests" / "fixtures" / "ocr" / "ocr-test1.png")
        orig_image = cv2.imread(image_path)
        ocr_textlist = ocr.image_simple_ocr(orig_image)
        actual = " ".join(ocr_textlist).upper()

        # The screenshot also contains HUD text, so only check the known white text at the bottom.
        self.assertIn("LOW WAKE", actual)
        self.assertIn("RUSSELL HUTTON", actual)

    def test_similarity_test1(self):
        ocr = OCR(screen=None)
        s1 = "Orbital Construction Site: Wingrove's Inheritance"
        s2 = "Wingrove's Inheritance (Orbital Construction Site)"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.9)  # add assertion here

    def test_similarity_test2(self):
        ocr = OCR(screen=None)
        s1 = "STAR BLAZE V2V-65W"
        s2 = "STAR BLAZE (V2V-65W)"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.8)  # add assertion here


@unittest.skipIf(OCR is None, "PaddleOCR is not installed")
class PaddleOCRV3TestCase(unittest.TestCase):
    def test_project_cache_is_selected_before_paddlex_import_from_any_working_directory(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(paths.ROOT / "src")
        environment["PADDLE_PDX_CACHE_HOME"] = str(paths.USER_DATA / "wrong-cache")
        with tempfile.TemporaryDirectory() as working_directory:
            environment["EDAP_LOG_DIR"] = str(Path(working_directory) / "logs")
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from vision.ocr import OCR; "
                    "from core import paths; "
                    "from paddlex.utils.cache import CACHE_DIR; "
                    "from pathlib import Path; "
                    "assert Path(CACHE_DIR) == paths.PADDLEX_CACHE_DIR, CACHE_DIR",
                ],
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def make_ocr(self, results):
        ocr = OCR.__new__(OCR)
        ocr.paddleocr = Mock()
        ocr.paddleocr.predict.return_value = results
        return ocr

    def test_region_matches_phrase_split_into_separate_ocr_words(self):
        ocr = self.make_ocr([Mock(json={"res": {"rec_texts": ["VERBUNDEN", "MIT", "OHM", "CITY"]}})])
        ocr.capture_region_pct = Mock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))

        found, text = ocr.is_text_in_region("VERBUNDEN MIT", {"rect": [0, 0, 1, 1]})

        self.assertTrue(found)
        self.assertIn("VERBUNDEN", text)

    def test_region_matches_whole_lines_and_normalizes_case_and_whitespace(self):
        for words in (["CONNECTED TO Ohm City"], ["connected", "  to", "Ohm City"], ["VERBUNDEN MIT OHM CITY"]):
            with self.subTest(words=words):
                ocr = self.make_ocr([Mock(json={"res": {"rec_texts": words}})])
                ocr.capture_region_pct = Mock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
                expected = "VERBUNDEN MIT" if words[0].startswith("VERBUNDEN") else "connected to"
                self.assertTrue(ocr.is_text_in_region(expected, {"rect": [0, 0, 1, 1]})[0])

    def test_region_rejects_empty_or_incomplete_header(self):
        for words in ([], ["VERBUNDEN"], ["MIT"], ["VERBUNDEN", "ALS"], ["CONNECTED", "AS"]):
            with self.subTest(words=words):
                ocr = self.make_ocr([Mock(json={"res": {"rec_texts": words}})])
                ocr.capture_region_pct = Mock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
                self.assertFalse(ocr.is_text_in_region("VERBUNDEN MIT", {"rect": [0, 0, 1, 1]})[0])
                self.assertFalse(ocr.is_text_in_region("", {"rect": [0, 0, 1, 1]})[0])

    def test_region_rejects_missing_ocr_result(self):
        ocr = self.make_ocr(None)
        ocr.capture_region_pct = Mock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertFalse(ocr.is_text_in_region("VERBUNDEN MIT", {"rect": [0, 0, 1, 1]})[0])

    def test_constructor_uses_paddleocr_v3_cpu_options(self):
        with patch("vision.ocr.PaddleOCR") as paddleocr:
            OCR(screen=None, language="de")

        paddleocr.assert_called_once_with(
            lang="de",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            device="cpu",
        )

    def test_image_simple_ocr_reads_text_from_v3_results(self):
        result = Mock(json={"res": {"rec_texts": ["LOW WAKE"]}})
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        ocr = self.make_ocr([result])

        self.assertEqual(ocr.image_simple_ocr(image), ["LOW WAKE"])
        ocr.paddleocr.predict.assert_called_once_with(input=image)

    def test_simple_ocr_reads_only_recognized_text(self):
        result = Mock(json={"res": {"rec_texts": ["LOW WAKE", "RUSSELL HUTTON"]}})
        ocr = self.make_ocr([result])

        self.assertEqual(ocr.image_simple_ocr(np.zeros((10, 10, 3), dtype=np.uint8)), ["LOW WAKE", "RUSSELL HUTTON"])

    def test_simple_ocr_returns_none_when_predict_returns_none(self):
        ocr = self.make_ocr(None)

        self.assertIsNone(ocr.image_simple_ocr(np.zeros((10, 10, 3), dtype=np.uint8)))

    def test_highlighted_item_returns_selected_image_and_text(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        ocr = self.make_ocr([])
        ocr.get_highlighted_item_in_image = Mock(return_value=(image, 0, 0))
        ocr.image_simple_ocr = Mock(return_value=["NAVIGATION"])

        selected_image, textlist = ocr.get_highlighted_item_data(image, 10, 10)

        self.assertIs(selected_image, image)
        self.assertEqual(textlist, ["NAVIGATION"])

    def test_highlighted_item_returns_no_data_when_ocr_has_no_result(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        ocr = self.make_ocr([])
        ocr.get_highlighted_item_in_image = Mock(return_value=(image, 0, 0))
        ocr.image_simple_ocr = Mock(return_value=None)

        self.assertEqual(ocr.get_highlighted_item_data(image, 10, 10), (None, None))

    def test_solid_highlight_accepts_dense_lettering_but_rejects_hollow_outline(self):
        ocr = self.make_ocr([])
        image = np.zeros((100, 400, 3), dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (380, 80), (0, 255, 255), -1)
        for x in range(30, 365, 15):
            cv2.rectangle(image, (x, 25), (x + 7, 75), (0, 0, 0), -1)
        self.assertEqual(len(ocr.solid_highlighted_items(image, 200, 50)), 1)

        image[:] = 0
        cv2.rectangle(image, (20, 20), (380, 80), (0, 255, 255), 3)
        self.assertEqual(ocr.solid_highlighted_items(image, 200, 50), [])

    def test_solid_highlight_rectifies_white_and_orange_without_mutating_image(self):
        ocr = self.make_ocr([])
        for color in ((255, 255, 255), (0, 255, 255)):
            with self.subTest(color=color):
                image = np.zeros((200, 400, 4), dtype=np.uint8)
                polygon = np.array([[40, 70], [330, 40], [330, 85], [40, 115]], np.int32)
                cv2.fillConvexPoly(image, polygon, (*color, 255))
                cv2.putText(image, "TEST", (80, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0, 255), 2)
                before = image.copy()
                items = ocr.solid_highlighted_items(image, 200, 30)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0][0].shape[2], 3)
                self.assertGreater(items[0][0].shape[1], 280)
                self.assertLess(items[0][0].shape[0], 60)
                np.testing.assert_array_equal(image, before)

    def test_solid_highlight_rejects_thin_lines_and_hollow_borders(self):
        ocr = self.make_ocr([])
        image = np.zeros((200, 400, 3), dtype=np.uint8)
        cv2.line(image, (10, 20), (390, 40), (255, 255, 255), 3)
        cv2.rectangle(image, (30, 80), (370, 160), (255, 255, 255), 3)
        self.assertEqual(ocr.solid_highlighted_items(image, 200, 30), [])

    def test_solid_highlight_preserves_long_narrow_slanted_rows(self):
        ocr = self.make_ocr([])
        for scale in (1, 2):
            for filled in (True, False):
                with self.subTest(scale=scale, filled=filled):
                    image = np.zeros((160 * scale, 1200 * scale, 3), dtype=np.uint8)
                    corners = np.array([[60, 75], [1140, 25], [1140, 55], [60, 105]], np.int32) * scale
                    cv2.polylines(image, [corners], True, (0, 255, 255), 2 * scale)
                    if filled:
                        cv2.fillConvexPoly(image, corners, (0, 255, 255))
                    items = ocr.solid_highlighted_items(image, 700 * scale, 25 * scale)
                    self.assertEqual(len(items), 1 if filled else 0)
                    if filled:
                        self.assertGreater(items[0][0].shape[1], 1000 * scale)
                        self.assertLess(items[0][0].shape[0], 40 * scale)

    def test_solid_highlight_rejects_long_ellipses_and_triangles(self):
        ocr = self.make_ocr([])
        image = np.zeros((160, 1200, 3), dtype=np.uint8)
        cv2.ellipse(image, (600, 80), (540, 20), 0, 0, 360, (0, 255, 255), -1)
        self.assertEqual(ocr.solid_highlighted_items(image, 700, 25), [])
        image[:] = 0
        corners = np.array([[60, 75], [1140, 25], [1140, 65]], np.int32)
        cv2.fillConvexPoly(image, corners, (0, 255, 255))
        self.assertEqual(ocr.solid_highlighted_items(image, 700, 25), [])


if __name__ == "__main__":
    unittest.main()

"""Simple check of OCR to bring back text of a known image."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core import paths

try:
    from vision.ocr import OCR
except ImportError:  # PaddleOCR is not installed (slim CI)
    OCR = None


@unittest.skipIf(OCR is None, "PaddleOCR is not installed")
class OCRTestCase(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

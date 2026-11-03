"""Simple check of OCR to bring back text of a known image."""

import unittest
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
    def make_ocr(self, results):
        ocr = OCR.__new__(OCR)
        ocr.paddleocr = Mock()
        ocr.paddleocr.predict.return_value = results
        return ocr

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


if __name__ == "__main__":
    unittest.main()

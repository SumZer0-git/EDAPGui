"""Simple check of OCR to bring back text of a known image."""

import unittest

import cv2

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


if __name__ == "__main__":
    unittest.main()

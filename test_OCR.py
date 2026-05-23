import unittest
from OCR import OCR
from Screen import *


def dummy_cb(msg, body=None):
    pass


class OCRTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ED_AP import EDAutopilot
        cls.ed_ap = EDAutopilot(cb=dummy_cb)

    def test_simple_OCR(self):
        """ Simple check of OCR to bring back text of a know image. """
        ocr = OCR(self.ed_ap, screen=None)

        # Load image
        image_path = 'test/ocr/ocr-test1.png'
        orig_image = cv2.imread(image_path)
        ocr_textlist = ocr.image_simple_ocr(orig_image, 'test')
        actual = str(ocr_textlist)
        expected = "['DESTINATION', 'SIRIUS ATMOSPHERICS']"

        self.assertEqual(actual, expected)  # add assertion here

    def test_OCR(self):
        """ Simple check of OCR to bring back text of a know image. """
        ocr = OCR(self.ed_ap, screen=None)

        # Load image
        image_path = 'test/ocr/6-selected_item.png'
        orig_image = cv2.imread(image_path)
        ocr_data, ocr_textlist = ocr.image_ocr(orig_image, 'test')
        actual = str(ocr_textlist)
        expected = "['NAVIGATION']"

        self.assertEqual(actual, expected)  # add assertion here

    def test_simple_OCR_2(self):
        """ Simple check of OCR to bring back text of a know image. """
        ocr = OCR(self.ed_ap, screen=None)

        # Load image
        image_path = 'test/disengage/Screenshot 2024-08-13 21-32-58.png'
        orig_image = cv2.imread(image_path)
        ocr_textlist = ocr.image_simple_ocr(orig_image, 'test')
        s1 = str(ocr_textlist)
        s2 = "['PRESS TO DISENGAGE']"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.35)  # add assertion here

    def test_get_highlighted_item(self):
        """ Simple check of OCR to bring back text of a know image. """
        ocr = OCR(self.ed_ap, screen=None)

        # Load image
        image_path = 'test/ocr/tab_bar.png'
        image_path = 'test/ocr/nav_panel_location_panel.png'
        orig_image = cv2.imread(image_path)
        # im, _, _ = ocr.get_highlighted_item_in_image(orig_image, 0.23, 0.7)
        item = Quad.from_rect([0.0, 0.0, 1.0, 0.08])
        im, _ = ocr.get_highlighted_item_in_image(orig_image, item)
        cv2.imwrite('test/ocr/tab_bar_out.png', im)

        self.assertEqual(True, True)  # add assertion here

    def test_similarity_test1(self):
        ocr = OCR(self.ed_ap, screen=None)
        s1 = "Orbital Construction Site: Wingrove's Inheritance"
        s2 = "Wingrove's Inheritance (Orbital Construction Site)"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.9)  # add assertion here

    def test_similarity_test2(self):
        ocr = OCR(self.ed_ap, screen=None)
        s1 = "STAR BLAZE V2V-65W"
        s2 = "STAR BLAZE (V2V-65W)"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.8)  # add assertion here

    def test_similarity_test3(self):
        ocr = OCR(self.ed_ap, screen=None)
        s1 = "['STAR BLAZE V2V-65W']"
        s2 = "['<STARBLAZEV2V-65W>']"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.8)  # add assertion here

    def test_similarity_test4e(self):
        ocr = OCR(self.ed_ap, screen=None)
        s1 = "['NAV BEACON']"
        s2 = "['<NAVBEACON>']"
        actual = ocr.string_similarity(s1, s2)
        print(f"Dice: {actual}")

        self.assertGreater(actual, 0.8)  # add assertion here


if __name__ == '__main__':
    unittest.main()

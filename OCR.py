from __future__ import annotations

import time
import cv2
import numpy as np
from paddleocr import PaddleOCR
from strsimpy import SorensenDice
from strsimpy.jaro_winkler import JaroWinkler

from EDlogger import logger

"""
File:OCR.py    

Description:
  Class for OCR processing using PaddleOCR. 

Author: Stumpii
"""


class OCR:
    def __init__(self, screen):
        self.screen = screen
        self.paddleocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False, use_dilation=True,
                                   use_space_char=True)
        # Class for text similarity metrics
        self.jarowinkler = JaroWinkler()
        self.sorensendice = SorensenDice()

    def string_similarity(self, s1, s2):
        #return self.jarowinkler.similarity(s1, s2)
        return self.sorensendice.similarity(s1, s2)

    def image_ocr(self, image):
        """ Perform OCR with no filtering. Returns the full OCR data and a simplified list of strings.
        This routine is the slower than the simplified OCR.

        OCR Data is returned in the following format, or (None, None):
        [[[[[86.0, 8.0], [208.0, 8.0], [208.0, 34.0], [86.0, 34.0]], ('ROBIGO 1 A', 0.9815958738327026)]]]
        """
        ocr_data = self.paddleocr.ocr(image)

        # print(ocr_data)

        if ocr_data is None:
            return None, None
        else:
            ocr_textlist = []
            for res in ocr_data:
                if res is None:
                    return None, None
                for line in res:
                    ocr_textlist.append(line[1][0])

            #print(ocr_textlist)
            return ocr_data, ocr_textlist

    def image_simple_ocr(self, image) -> list[str] | None:
        """ Perform OCR with no filtering. Returns a simplified list of strings with no positional data.
        This routine is faster than the function that returns the full data. Generally good when you
        expect to only return one or two lines of text.

        OCR Data is returned in the following format, or None:
        [[[[[86.0, 8.0], [208.0, 8.0], [208.0, 34.0], [86.0, 34.0]], ('ROBIGO 1 A', 0.9815958738327026)]]]
        """
        ocr_data = self.paddleocr.ocr(image)

        # print(f"image_simple_ocr: {ocr_data}")

        if ocr_data is None:
            return None
        else:
            ocr_textlist = []
            for res in ocr_data:
                if res is None:
                    return None

                for line in res:
                    ocr_textlist.append(line[1][0])

            # print(f"image_simple_ocr: {ocr_textlist}")
            # logger.info(f"image_simple_ocr: {ocr_textlist}")
            return ocr_textlist

    def get_highlighted_item_data(self, image, min_w, min_h):
        """ Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
            rectangle with dark text, instead of orange/blue text on a dark background.
            The OCR daya of the first item matching the criteria is returned, otherwise None.
            @param image: The image to check.
            @param min_w: The minimum width of the text block.
            @param min_h: The minimum height of the text block.
        """
        # Find the selected item/menu (solid orange)
        img_selected, x, y = self.get_highlighted_item_in_image(image, min_w, min_h)
        if img_selected is not None:
            # cv2.imshow("img", img_selected)

            ocr_data, ocr_textlist = self.image_ocr(img_selected)

            if ocr_data is not None:
                return img_selected, ocr_data, ocr_textlist
            else:
                return None, None, None

        else:
            return None, None, None

    def get_highlighted_item_in_image(self, image, min_w, min_h):
        """ Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
        rectangle with dark text, instead of orange/blue text on a dark background.
        The image of the first item matching the criteria and minimum width and height is returned
        with x and y co-ordinates, otherwise None.
        @param image: The image to check.
        @param min_h: Minimum height in pixels.
        @param min_w: Minimum width in pixels.
        """
        # Perform HSV mask
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_range = np.array([0, 100, 180])
        upper_range = np.array([255, 255, 255])
        mask = cv2.inRange(hsv, lower_range, upper_range)
        masked_image = cv2.bitwise_and(image, image, mask=mask)
        cv2.imwrite('test/nav-panel/out/masked.png', masked_image)

        # Convert to gray scale and invert
        gray = cv2.cvtColor(masked_image, cv2.COLOR_BGR2GRAY)
        cv2.imwrite('test/nav-panel/out/gray.png', gray)

        # Convert to B&W to allow FindContours to find rectangles.
        ret, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)  # | cv2.THRESH_BINARY_INV)
        cv2.imwrite('test/nav-panel/out/thresh1.png', thresh1)

        # Finding contours in B&W image. White are the areas detected
        contours, hierarchy = cv2.findContours(thresh1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cropped = image
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Check the item is greater than 90% of the minimum width or height. Which allows for some variation.
            if w > (min_w * 0.9) and h > (min_h * 0.9):
                # Drawing a rectangle on the copied image
                # rect = cv2.rectangle(crop, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Crop to leave only the contour (the selected rectangle)
                cropped = image[y:y + h, x:x + w]

                # cv2.imshow("cropped", cropped)
                # cv2.imwrite('test/selected_item.png', cropped)
                return cropped, x, y

        # No good matches, then return None
        return None, 0, 0

    def capture_region_pct(self, region):
        """ Grab the image based on the region name/rect.
        Returns an unfiltered image, either from screenshot or provided image.
        @param region: The region to check in % (0.0 - 1.0).
        """
        rect = region['rect']
        image = self.screen.get_screen_region_pct(rect)
        return image

    def is_text_in_selected_item_in_image(self, img, text, min_w, min_h):
        """ Does the selected item in the region include the text being checked for.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param min_h: Minimum height in pixels.
        @param min_w: Minimum width in pixels.
        @param img: The image to check.
        @param text: The text to find.
        """
        img_selected, x, y = self.get_highlighted_item_in_image(img, min_w, min_h)
        if img_selected is None:
            logger.debug(f"Did not find a selected item in the region.")
            return None

        ocr_textlist = self.image_simple_ocr(img_selected)
        # print(str(ocr_textlist))

        if text.upper() in str(ocr_textlist):
            logger.debug(f"Found '{text}' text in item text '{str(ocr_textlist)}'.")
            return True
        else:
            logger.debug(f"Did not find '{text}' text in item text '{str(ocr_textlist)}'.")
            return False

    def is_text_in_region(self, text, region):
        """ Does the region include the text being checked for. The region does not need
        to include highlighted areas.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param text: The text to check for.
        @param region: The region to check in % (0.0 - 1.0).
        """

        img = self.capture_region_pct(region)

        ocr_textlist = self.image_simple_ocr(img)
        # print(str(ocr_textlist))

        if text.upper() in str(ocr_textlist):
            logger.debug(f"Found '{text}' text in item text '{str(ocr_textlist)}'.")
            return True
        else:
            logger.debug(f"Did not find '{text}' text in item text '{str(ocr_textlist)}'.")
            return False

    def select_item_in_list(self, text, region, keys, min_w, min_h) -> bool:
        """ Attempt to find the item by text in a list defined by the region.
        If found, leaves it selected for further actions.
        @param keys:
        @param text: Text to find.
        @param region: The region to check in % (0.0 - 1.0).
        @param min_h: Minimum height in pixels.
        @param min_w: Minimum width in pixels.
        """

        in_list = False  # Have we seen one item yet? Prevents quiting if we have not selected the first item.
        while 1:
            img = self.capture_region_pct(region)
            if img is None:
                return False

            found = self.is_text_in_selected_item_in_image(img, text, min_w, min_h)

            # Check if end of list.
            if found is None and in_list:
                logger.debug(f"Did not find '{text}' in {region} list.")
                return False

            if found:
                logger.debug(f"Found '{text}' in {region} list.")
                return True
            else:
                # Next item
                in_list = True
                keys.send("UI_Down")

    def wait_for_text(self, texts: list[str], region, timeout=30) -> bool:
        """ Wait for a screen to appear by checking for text to appear in the region.
        @param texts: List of text to check for. Success occurs if any in the list is found.
        @param region: The region to check in % (0.0 - 1.0).
        @param timeout: Time to wait for screen in seconds
        """
        start_time = time.time()
        while True:
            # Check for timeout.
            if time.time() > (start_time + timeout):
                return False

            # Check if screen has appeared.
            for text in texts:
                res = self.is_text_in_region(text, region)
                if res:
                    return True

            time.sleep(0.25)

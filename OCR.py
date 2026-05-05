from __future__ import annotations
import time
from datetime import datetime

import cv2
import numpy as np
from cv2.typing import MatLike
from paddleocr import PaddleOCR
from strsimpy import SorensenDice
from strsimpy.jaro_winkler import JaroWinkler
from strsimpy.normalized_levenshtein import NormalizedLevenshtein
from EDlogger import logger
from tkinter import messagebox
import tkinter as tk

from Screen_Regions import Quad

"""
File:OCR.py    

Description:
  Class for OCR processing using PaddleOCR. 

Author: Stumpii
"""


class OCR:
    def __init__(self, ed_ap, screen):
        """
        Initialise the OCR class.
        @param ed_ap:
        @param screen:
        @param mobile: Use the mobile (light) version which is smaller and faster, but less accurate.
        """
        self.ap = ed_ap
        self.screen = screen
        if self.ap.config['OCRMobile']:
            self.paddleocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="en_PP-OCRv5_mobile_rec")  # text detection + text recognition
        else:
            self.paddleocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False)  # text detection + text recognition

        # Class for text similarity metrics
        self.jarowinkler = JaroWinkler()
        self.sorensendice = SorensenDice()
        self.normalized_levenshtein = NormalizedLevenshtein()

    def _reinit_paddleocr(self):
        """ Reinitialize PaddleOCR after a failure. PaddleOCR's C++ layer can throw
        an 'Unknown exception' which corrupts internal state. If the same instance is
        reused, the next call will cause a hard process crash with no Python traceback.
        Creating a fresh instance prevents this. """
        try:
            logger.warning("Reinitializing PaddleOCR after failure.")
            if self.ap.config['OCRMobile']:
                self.paddleocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="en_PP-OCRv5_mobile_rec")  # text detection + text recognition
            else:
                self.paddleocr = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False)  # text detection + text recognition

        except Exception as e:
            logger.error(f"Failed to reinitialize PaddleOCR: {e}")

    def string_similarity(self, s1: str, s2: str) -> float:
        """ Performs a string similarity check and returns the result.
        @param s1: The first string to compare.
        @param s2: The second string to compare.
        @return: The similarity from 0.0 (no match) to 1.0 (identical).
        """
        s1_new = s1.replace("['",  "")
        s1_new = s1_new.replace("']",  "")
        s1_new = s1_new.replace('["',  "")
        s1_new = s1_new.replace('"]',  "")
        s1_new = s1_new.replace("', '",  "")
        s1_new = s1_new.replace("<",  "")
        s1_new = s1_new.replace(">",  "")
        s1_new = s1_new.replace("-",  "")
        s1_new = s1_new.replace("—",  "")
        s1_new = s1_new.replace(" ",  "")

        s2_new = s2.replace("['",  "")
        s2_new = s2_new.replace("']",  "")
        s2_new = s2_new.replace('["',  "")
        s2_new = s2_new.replace('"]',  "")
        s2_new = s2_new.replace("', '",  "")
        s2_new = s2_new.replace("<",  "")
        s2_new = s2_new.replace(">",  "")
        s2_new = s2_new.replace("-",  "")
        s2_new = s2_new.replace("—",  "")
        s2_new = s2_new.replace(" ",  "")

        # return self.jarowinkler.similarity(s1, s2)
        return self.normalized_levenshtein.similarity(s1_new, s2_new)
        # return self.sorensendice.similarity(s1_new, s2_new)

    def image_ocr(self, image, name=''):
        """ Perform OCR with no filtering. Returns the full OCR data and a simplified list of strings.
        This routine is slower than the simplified OCR.
        @param name:
        @param image: The image to check.

        'ocr_data' is returned in the following format, or (None, None):
        [[[[[86.0, 8.0], [208.0, 8.0], [208.0, 34.0], [86.0, 34.0]], ('ROBIGO 1 A', 0.9815958738327026)]]]
        'ocr_textlist' is returned in the following format, or None:
        ['DESTINATION', 'SIRIUS ATMOSPHERICS']
        """
        # Remove Alpha channel if it exists
        image2 = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        try:
            ocr_data = self.paddleocr.predict(image2)

            if ocr_data is None:
                return None, None
            else:
                ocr_textlist = []
                for res in ocr_data:
                    if res is None:
                        return None, None

                    # Debug - places all detected data to 'output' folder
                    if self.ap.debug_ocr:
                        # x = datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]  # Date time with mS.
                        res.save_to_img(f"./ocr_output/{name}")
                        res.save_to_json(f"./ocr_output/{name}")

                    # Added detected text to list
                    ocr_textlist.extend(res['rec_texts'])

                # print(f"image_simple_ocr: {ocr_textlist}")
                # logger.info(f"image_simple_ocr: {ocr_textlist}")
                return ocr_data, ocr_textlist

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            # Reinit to avoid hard crash on next call due to corrupted C++ state
            self._reinit_paddleocr()
            logger.error(f"Image stored to ocr_output folder.")
            cv2.imwrite(f"./ocr_output/{name}", image)
            return None, None

    def image_simple_ocr(self, image, name='') -> list[str] | None:
        """ Perform OCR with no filtering. Returns a simplified list of strings with no positional data.
        This routine is faster than the function that returns the full data. Generally good when you
        expect to only return one or two lines of text.
        @param name:
        @param image: The image to check.
        'ocr_textlist' is returned in the following format, or None:
        ['DESTINATION', 'SIRIUS ATMOSPHERICS']
        """
        if image is None:
            return None

        # start_time = time.time()

        # Remove Alpha channel if it exists
        image2 = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        try:
            ocr_data = self.paddleocr.predict(image2)

            # elapsed_time = time.time() - start_time
            # print(f"OCR took {elapsed_time} secs")

            if ocr_data is None:
                return None
            else:
                ocr_textlist = []
                for res in ocr_data:
                    if res is None:
                        return None

                    # Debug - places all detected data to 'output' folder
                    if self.ap.debug_ocr:
                        # x = datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]  # Date time with mS.
                        res.save_to_img(f"./ocr_output/{name}")
                        res.save_to_json(f"./ocr_output/{name}")
                        # res.save_to_img("ocr_output")
                        # res.save_to_json("ocr_output")

                    # Added detected text to list
                    ocr_textlist.extend(res['rec_texts'])

                # print(f"image_simple_ocr: {ocr_textlist}")
                # logger.info(f"image_simple_ocr: {ocr_textlist}")
                return ocr_textlist

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            # Reinit to avoid hard crash on next call due to corrupted C++ state
            self._reinit_paddleocr()
            logger.error(f"Image stored to ocr_output folder.")
            cv2.imwrite(f"./ocr_output/{name}", image)
            return None

    def get_highlighted_item_data(self, image, item: Quad, name=''):
        """ Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
            rectangle with dark text, instead of orange/blue text on a dark background.
            The OCR daya of the first item matching the criteria is returned, otherwise None.
            @param item: A Quad representing the item, in percentage.
            @param name:
            @param image: The image to check.
     """
        # Find the selected item/menu (solid orange)
        img_selected, quad = self.get_highlighted_item_in_image(image, item)
        if img_selected is not None:
            # cv2.imshow("img", img_selected)

            ocr_data, ocr_textlist = self.image_ocr(img_selected, name)

            if ocr_data is not None:
                return img_selected, ocr_data, ocr_textlist, quad
            else:
                return None, None, None, None

        else:
            return None, None, None, None

    @staticmethod
    def get_highlighted_item_in_image(image, item: Quad) -> (MatLike, Quad):
        """ Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
        rectangle with dark text, instead of orange/blue text on a dark background.
        The image of the first item matching the criteria and minimum width and height is returned
        with x and y co-ordinates, otherwise None.
        @param item: A Quad representing the item in percent.
        @param image: The image to check.
        @return: The highlighted image and the matching Quad position in percentage of the image size, or (None, None)
        """
        min_w = item.width
        min_h = item.height

        # Existing size
        img_h, img_w, _ = image.shape

        # The input image
        cv2.imwrite('test/nav-panel/out/1-input.png', image)

        # Perform HSV mask
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_range = np.array([0, 100, 180])
        upper_range = np.array([255, 255, 255])
        mask = cv2.inRange(hsv, lower_range, upper_range)
        masked_image = cv2.bitwise_and(image, image, mask=mask)
        cv2.imwrite('test/nav-panel/out/2-masked.png', masked_image)

        # Convert to gray scale and invert
        gray = cv2.cvtColor(masked_image, cv2.COLOR_BGR2GRAY)
        cv2.imwrite('test/nav-panel/out/3-gray.png', gray)

        # Convert to B&W to allow FindContours to find rectangles.
        ret, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)  # | cv2.THRESH_BINARY_INV)
        cv2.imwrite('test/nav-panel/out/4-thresh1.png', thresh1)

        # Perform opening. Opening  is just another name of erosion followed by dilation. This will remove specs and
        # edges and then embolden the remaining edges. This works to remove text and stray lines.
        k = int(min(img_w * min_w, img_h * min_h) / 10)  # Make kernel 10% of the smallest image side
        kernel = np.ones((k, k), np.uint8)
        opening = cv2.morphologyEx(thresh1, cv2.MORPH_OPEN, kernel)
        cv2.imwrite('test/nav-panel/out/5-opened.png', opening)

        # Finding contours in B&W image. White are the areas detected
        contours, hierarchy = cv2.findContours(opening, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        output = image
        cv2.drawContours(output, contours, -1, (0, 255, 0), 2)
        cv2.imwrite('test/nav-panel/out/6-contours.png', output)

        # bounds = image
        cropped = image
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Check the item is greater than 85% of the minimum width or height. Which allows for some variation.
            if w > (img_w * min_w * 0.85) and h > (img_h * min_h * 0.85):
                # print(f"Selected item size: {round(w / img_w, 4)}(%) x {round(h / img_h, 4)}(%)")
                # logger.debug(f"Selected item size: {round(w / img_w, 4)}(%) x {round(h / img_h, 4)}(%)")

                # Drawing a rectangle on the copied image
                # bounds = cv2.rectangle(bounds, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Crop to leave only the contour (the selected rectangle)
                cropped = image[y:y + h, x:x + w]

                # cv2.imshow("cropped", cropped)
                cv2.imwrite('test/nav-panel/out/7-selected_item.png', cropped)
                q = Quad.from_rect([x / img_w, y / img_h, (x + w) / img_w, (y + h) / img_h])
                return cropped, q

        # No good matches, then return None
        return None, None

    def capture_region_pct(self, region):
        """ Grab the image based on the region name/rect.
        Returns an unfiltered image, either from screenshot or provided image.
        @param region: The region to check in % (0.0 - 1.0).
        TODO - Move this to Region or Screen code. Make all funcs in OCR use rect/quad, not region.
        """
        rect = region['rect']
        image = self.screen.get_screen_rect_pct(rect)
        return image

    def is_text_in_selected_item_in_image(self, img, text, item: Quad, name=''):
        """ Does the selected item in the region include the text being checked for.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param item: A quad representing the item in pct. 
        @param name:
        @param img: The image to check.
        @param text: The text to find.
        """
        img_selected, _ = self.get_highlighted_item_in_image(img, item)
        if img_selected is None:
            logger.debug(f"Did not find a selected item in the region.")
            return None

        found, results = self.is_text_in_image(text, img_selected, name)
        return found, results

    def is_text_in_region(self, text, region) -> (bool, str):
        """ Does the region include the text being checked for. The region does not need
        to include highlighted areas.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param text: The text to check for.
        @param region: The region to check in % (0.0 - 1.0).
        TODO - Move this to Region or Screen code. Make all funcs in OCR use rect/quad, not region.
        """

        img = self.capture_region_pct(region)

        found, results = self.is_text_in_image(text, img)
        return found, results

    def is_text_in_image(self, text, image, name='') -> (bool, str):
        """ Does the image include the text being checked for. The image does not need
        to include highlighted areas.
        Checks if text exists in an image using OCR.
        Return True if found, False if not and None if no item was selected.
        @param text: The text to check for.
        @param image: The image to check.
        @return: True with the string of results, or False with the string of results.
        """
        if image is None:
            logger.debug(f"is_text_in_image: No image supplied.")
            return None, ""

        ocr_textlist = self.image_simple_ocr(image, name)
        # print(str(ocr_textlist))

        # PaddleOCR has difficulty detecting spaces, so strip out spaces for the compare
        text_ns = text.replace(' ', '').upper()
        ocr_textlist_ns = str(ocr_textlist).replace(' ', '').upper()

        if text_ns in ocr_textlist_ns:
            logger.debug(f"Found '{text}' text in item text '{str(ocr_textlist)}'.")
            return True, str(ocr_textlist)
        else:
            logger.debug(f"Did not find '{text}' text in item text '{str(ocr_textlist)}'.")
            return False, str(ocr_textlist)

    def select_item_in_list(self, text, region, keys, quad: Quad, name='') -> bool:
        """ Attempt to find the item by text in a list defined by the region.
        If found, leaves it selected for further actions.
        @param quad: A quad representing the item in percentage.
        @param keys:
        @param text: Text to find.
        @param region: The region to check in % (0.0 - 1.0).
        TODO - Move this to Region or Screen code. Make all funcs in OCR use rect/quad, not region.
        """

        in_list = False  # Have we seen one item yet? Prevents quiting if we have not selected the first item.
        while 1:
            img = self.capture_region_pct(region)
            if img is None:
                return False

            found = self.is_text_in_selected_item_in_image(img, text, quad, name)

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

    def wait_for_text(self, ap, texts: list[str], region, timeout=30) -> bool:
        """ Wait for a screen to appear by checking for text to appear in the region.
        @param ap: ED_AP instance.
        @param texts: List of text to check for. Success occurs if any in the list is found.
        @param region: The screen region to check in % (0.0 - 1.0) of the full screen.
        @param timeout: Time to wait for screen in seconds
        @return: True if text found, else False
        TODO - Move this to Region or Screen code. Make all funcs in OCR use rect/quad, not region.
        """
        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(region['rect'])
        if ap.debug_overlay:
            ap.overlay.overlay_rect1('wait_for_text', abs_rect, (0, 255, 0), 2)
            ap.overlay.overlay_paint()

        start_time = time.time()
        text_found = False
        while True:
            # Check for timeout.
            if time.time() > (start_time + timeout):
                break

            # Check if screen has appeared.
            for text in texts:
                text_found, ocr_text = self.is_text_in_region(text, region)

                # Overlay OCR result
                if ap.debug_overlay:
                    ap.overlay.overlay_floating_text('wait_for_text', f'{ocr_text}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
                    ap.overlay.overlay_paint()

                if text_found:
                    break

            if text_found:
                break

            time.sleep(0.25)

        return text_found


# class RegionCalibration:
#     def __init__(self, root, ed_ap, cb):
#         self.scr = ed_ap.scr
#         self.root = root
#         self.ap = ed_ap
#         self.ap_ckb = cb
#         self.calibration_overlay = None
#         self.ocr_calibration_data = None
#         self.selected_region = None
#         self.calibration_canvas = None
#         self.current_rect = None
#         self.start_y = None
#         self.start_x = None
#
#     def calibrate_ocr_region(self, ocr_calibration_data, selected_region: str):
#         # selected_region = self.calibration_region_var.get()
#         self.ocr_calibration_data = ocr_calibration_data
#         self.selected_region = selected_region
#         if not self.selected_region:
#             messagebox.showerror("Error", "Please select a region to calibrate.")
#             return
#
#         self.ap_ckb('log', f"Starting calibration for: {selected_region}")
#
#         self.calibration_overlay = tk.Toplevel(self.root)
#         self.calibration_overlay.overrideredirect(True)
#
#         screen_w = self.scr.screen_width
#         screen_h = self.scr.screen_height
#         screen_x = self.scr.screen_left
#         screen_y = self.scr.screen_top
#
#         # screen_w = self.root.winfo_screenwidth()
#         # screen_h = self.root.winfo_screenheight()
#         # screen_x = self.root.winfo_x()
#         # screen_y = self.root.winfo_y()
#         # self.calibration_overlay.geometry(f"{screen_w}x{screen_h}+0+0")
#         self.calibration_overlay.geometry(f"{screen_w}x{screen_h}+{screen_x}+{screen_y}")
#
#         self.calibration_overlay.attributes('-alpha', 0.3)
#
#         self.calibration_canvas = tk.Canvas(self.calibration_overlay, highlightthickness=0, bg='black')
#         self.calibration_canvas.pack(fill=tk.BOTH, expand=True)
#
#         # Draw current region
#         rect_pct = self.ocr_calibration_data[selected_region]['rect']
#
#         display_rect_pct = rect_pct
#
#         x1 = display_rect_pct[0] * screen_w
#         y1 = display_rect_pct[1] * screen_h
#         x2 = display_rect_pct[2] * screen_w
#         y2 = display_rect_pct[3] * screen_h
#         self.calibration_canvas.create_rectangle(x1, y1, x2, y2, outline='green1', width=5)
#
#         self.start_x = None
#         self.start_y = None
#         self.current_rect = None
#
#         self.calibration_canvas.bind("<ButtonPress-1>", self.on_calibration_press)
#         self.calibration_canvas.bind("<B1-Motion>", self.on_calibration_drag)
#         self.calibration_canvas.bind("<ButtonRelease-1>", self.on_calibration_release)
#         self.calibration_canvas.bind("<ButtonPress-3>", self.on_calibration_cancel)
#         self.calibration_overlay.bind("<Escape>", lambda e: self.calibration_overlay.destroy())
#
#     def on_calibration_cancel(self, event):
#         self.calibration_overlay.destroy()
#
#     def on_calibration_press(self, event):
#         self.start_x = event.x
#         self.start_y = event.y
#         self.current_rect = self.calibration_canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='cyan', width=5)
#
#     def on_calibration_drag(self, event):
#         if self.current_rect:
#             self.calibration_canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)
#
#     def on_calibration_release(self, event):
#         end_x = event.x
#         end_y = event.y
#
#         screen_w = self.root.winfo_screenwidth()
#         screen_h = self.root.winfo_screenheight()
#
#         # Ensure coordinates are ordered correctly
#         left = min(self.start_x, end_x)
#         top = min(self.start_y, end_y)
#         right = max(self.start_x, end_x)
#         bottom = max(self.start_y, end_y)
#
#         left_pct = left / screen_w
#         top_pct = top / screen_h
#         right_pct = right / screen_w
#         bottom_pct = bottom / screen_h
#
#         # selected_region = self.calibration_region_var.get()
#
#         # Regions that require special scaling normalization to a 1920x1080 reference resolution
#         station_scaled_regions = [
#             "EDGalaxyMap.cartographics",
#             "EDSystemMap.cartographics"
#         ]
#
#         # Get the raw percentages from the drawn box
#         raw_rect_pct = [left_pct, top_pct, right_pct, bottom_pct]
#         raw_rect_pct = [round(left_pct, 4), round(top_pct, 4), round(right_pct, 4), round(bottom_pct, 4)]
#
#         # if self.selected_region.startswith("EDStationServicesInShip.") or self.selected_region in station_scaled_regions:
#         #     new_rect_pct = self._normalize_for_station(raw_rect_pct, screen_w, screen_h)
#         #     if new_rect_pct != raw_rect_pct:
#         #         self.ap_ckb('log', f"Applying station-style normalization for {self.selected_region}.")
#         # else:
#         new_rect_pct = raw_rect_pct
#
#         self.ocr_calibration_data[self.selected_region]['rect'] = new_rect_pct
#         self.ap_ckb('log', f"New rect for {self.selected_region}: {new_rect_pct}")
#
#         # Update label
#         # self.on_region_select(None)
#
#         self.calibration_overlay.destroy()

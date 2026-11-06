"""Text recognition using PaddleOCR."""

from __future__ import annotations

import os
import time
import warnings

from core import paths

# PaddleX reads its cache location on import, before any OCR engine is created.
os.environ["PADDLE_PDX_CACHE_HOME"] = str(paths.PADDLEX_CACHE_DIR)

# Hide only the harmless Paddle startup noise (ccache hint, C++ INFO logs).
# Warnings and errors stay visible. This must be set before importing paddle.
os.environ.setdefault("GLOG_minloglevel", "1")
warnings.filterwarnings("ignore", message="No ccache found")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from paddleocr import PaddleOCR  # noqa: E402
from strsimpy import SorensenDice  # noqa: E402
from strsimpy.jaro_winkler import JaroWinkler

from core.logger import logger


class OCR:
    @staticmethod
    def supports_language(language: str) -> bool:
        # PaddleOCR is pinned; query its model mapping without creating or downloading a pipeline.
        detection, recognition = PaddleOCR._get_ocr_model_names(None, language, None)
        return detection is not None and recognition is not None

    def __init__(self, screen, language: str = "en"):
        self.screen = screen
        self.language = language
        self.paddleocr = PaddleOCR(
            lang=language,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            device="cpu",
        )
        # Class for text similarity metrics
        self.jarowinkler = JaroWinkler()
        self.sorensendice = SorensenDice()

    def string_similarity(self, s1, s2) -> float:
        """Performs a string similarity check and returns the result.
        @param s1: The first string to compare.
        @param s2: The second string to compare.
        @return: The similarity from 0.0 (no match) to 1.0 (identical).
        """
        # return self.jarowinkler.similarity(s1, s2)
        return self.sorensendice.similarity(s1, s2)

    def image_simple_ocr(self, image) -> list[str] | None:
        """Return recognized text from an image, or None when OCR produced no result.

        This is intended for callers that compare text and do not need PaddleOCR's
        positional, confidence, or other result metadata.
        """
        results = self.paddleocr.predict(input=image)
        if results is None:
            return None

        ocr_textlist = []
        for result in results:
            if result is None:
                return None
            ocr_textlist.extend(result.json["res"]["rec_texts"])

        return ocr_textlist

    def get_highlighted_item_data(self, image, min_w, min_h):
        """Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
        rectangle with dark text, instead of orange/blue text on a dark background.
        The selected image and its recognized text are returned, otherwise (None, None).
        @param image: The image to check.
        @param min_w: The minimum width of the text block.
        @param min_h: The minimum height of the text block.
        """
        # Find the selected item/menu (solid orange)
        img_selected, x, y = self.get_highlighted_item_in_image(image, min_w, min_h)
        if img_selected is not None:
            # cv2.imshow("img", img_selected)

            ocr_textlist = self.image_simple_ocr(img_selected)

            if ocr_textlist is not None:
                return img_selected, ocr_textlist
            else:
                return None, None

        else:
            return None, None

    def get_highlighted_item_in_image(self, image, min_w, min_h):
        """Attempts to find a selected item in an image. The selected item is identified by being solid orange or blue
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
        cv2.imwrite(paths.debug_path("nav-panel", "1-masked.png"), masked_image)

        # Convert to gray scale and invert
        gray = cv2.cvtColor(masked_image, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(paths.debug_path("nav-panel", "2-gray.png"), gray)

        # Blur slightly to remove thin lines
        blur = cv2.GaussianBlur(gray, (3, 3), cv2.BORDER_DEFAULT)
        cv2.imwrite(paths.debug_path("nav-panel", "3-blur.png"), blur)

        # Convert to B&W to allow FindContours to find rectangles.
        ret, thresh1 = cv2.threshold(blur, 0, 255, cv2.THRESH_OTSU)  # | cv2.THRESH_BINARY_INV)
        cv2.imwrite(paths.debug_path("nav-panel", "4-thresh1.png"), thresh1)

        # Finding contours in B&W image. White are the areas detected
        contours, hierarchy = cv2.findContours(thresh1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        output = image
        cv2.drawContours(output, contours, -1, (0, 255, 0), 2)
        cv2.imwrite(paths.debug_path("nav-panel", "5-contours.png"), output)

        # bounds = image
        cropped = image
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Check the item is greater than 90% of the minimum width or height. Which allows for some variation.
            if w > (min_w * 0.9) and h > (min_h * 0.9):
                # Drawing a rectangle on the copied image
                # bounds = cv2.rectangle(bounds, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Crop to leave only the contour (the selected rectangle)
                cropped = image[y : y + h, x : x + w]

                # cv2.imshow("cropped", cropped)
                cv2.imwrite(paths.debug_path("nav-panel", "6-selected_item.png"), cropped)
                return cropped, x, y

        # No good matches, then return None
        return None, 0, 0

    def solid_highlighted_items(self, image, min_w, min_h, *, remove_thin_lines=False):
        """Extract bright filled quadrilaterals without including neighboring slanted rows."""
        image = image[:, :, :3]
        mask = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 210, 255)
        if remove_thin_lines:
            # Holographic HUD lines can connect an otherwise solid highlight to its surroundings.
            kernel_size = max(1, round(min_h * 0.08)) | 1
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((kernel_size, kernel_size), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        items = []
        for contour in contours:
            rectangle = cv2.minAreaRect(contour)
            long_side, short_side = sorted(rectangle[1], reverse=True)
            if long_side < min_w * 0.9 or short_side < min_h * 0.9:
                continue
            if cv2.contourArea(contour) < long_side * short_side * 0.65:
                continue
            polygon = cv2.approxPolyDP(contour, 0.015 * cv2.arcLength(contour, True), True)
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue
            points = polygon.reshape(4, 2).astype(np.float32)
            sums = points.sum(axis=1)
            differences = np.diff(points, axis=1).ravel()
            corners = np.array(
                [
                    points[sums.argmin()],
                    points[differences.argmin()],
                    points[sums.argmax()],
                    points[differences.argmax()],
                ]
            )
            if len(np.unique(corners, axis=0)) != 4:
                continue
            width = int(max(np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3])))
            height = int(max(np.linalg.norm(corners[3] - corners[0]), np.linalg.norm(corners[2] - corners[1])))
            if width < min_w * 0.9 or height < min_h * 0.9:
                continue
            destination = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
            transform = cv2.getPerspectiveTransform(corners, destination)
            cropped = cv2.warpPerspective(image, transform, (width, height))
            filled = cv2.inRange(cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY), 210, 255)
            # Dense dark tab lettering can occupy almost half of a filled highlight.
            if cv2.countNonZero(filled) < width * height * 0.5:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            items.append((cropped, x, y, w, h))
        return sorted(items, key=lambda item: (item[2], item[1]))

    def capture_region_pct(self, region):
        """Grab the image based on the region name/rect.
        Returns an unfiltered image, either from screenshot or provided image.
        @param region: The region to check in % (0.0 - 1.0).
        """
        rect = region["rect"]
        image = self.screen.get_screen_rect_pct(rect)
        return image

    def is_text_in_selected_item_in_image(self, img, text, min_w, min_h):
        """Does the selected item in the region include the text being checked for.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param min_h: Minimum height in pixels.
        @param min_w: Minimum width in pixels.
        @param img: The image to check.
        @param text: The text to find.
        """
        img_selected, x, y = self.get_highlighted_item_in_image(img, min_w, min_h)
        if img_selected is None:
            logger.debug("Did not find a selected item in the region.")
            return None

        ocr_textlist = self.image_simple_ocr(img_selected)
        # print(str(ocr_textlist))

        if text.upper() in str(ocr_textlist):
            logger.debug(f"Found '{text}' text in item text '{str(ocr_textlist)}'.")
            return True
        else:
            logger.debug(f"Did not find '{text}' text in item text '{str(ocr_textlist)}'.")
            return False

    def is_text_in_region(self, text, region) -> (bool, str):
        """Does the region include the text being checked for. The region does not need
        to include highlighted areas.
        Checks if text exists in a region using OCR.
        Return True if found, False if not and None if no item was selected.
        @param text: The text to check for.
        @param region: The region to check in % (0.0 - 1.0).
        """

        img = self.capture_region_pct(region)

        ocr_textlist = self.image_simple_ocr(img)

        recognized = " ".join(" ".join(ocr_textlist or []).upper().split())
        expected = " ".join(text.upper().split())
        if expected and expected in recognized:
            logger.debug(f"Found '{text}' text in item text '{str(ocr_textlist)}'.")
            return True, str(ocr_textlist)
        else:
            logger.debug(f"Did not find '{text}' text in item text '{str(ocr_textlist)}'.")
            return False, str(ocr_textlist)

    def select_item_in_list(self, text, region, keys, min_w, min_h) -> bool:
        """Attempt to find the item by text in a list defined by the region.
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

    def wait_for_text(self, ap, texts: list[str], region, timeout=30) -> bool:
        """Wait for a screen to appear by checking for text to appear in the region.
        @param ap: ED_AP instance.
        @param texts: List of text to check for. Success occurs if any in the list is found.
        @param region: The region to check in % (0.0 - 1.0).
        @param timeout: Time to wait for screen in seconds
        """
        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(region["rect"])
        if ap.debug_overlay:
            ap.overlay.overlay_rect1("wait_for_text", abs_rect, (0, 255, 0), 2)
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

                # Over OCR result
                if ap.debug_overlay:
                    ap.overlay.overlay_floating_text(
                        "wait_for_text", f"{ocr_text}", abs_rect[0], abs_rect[1] - 25, (0, 255, 0)
                    )
                    ap.overlay.overlay_paint()

                if text_found:
                    break

            if text_found:
                break

            time.sleep(0.25)

        # Clean up screen
        if ap.debug_overlay:
            time.sleep(2)
            ap.overlay.overlay_remove_rect("wait_for_text")
            ap.overlay.overlay_remove_floating_text("wait_for_text")
            ap.overlay.overlay_paint()

        return text_found

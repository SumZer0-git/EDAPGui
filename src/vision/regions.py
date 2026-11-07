"""Screen regions to capture, with filters, and template matching within a region."""

import logging

import cv2
from numpy import array, sum

from core.logger import logger


def reg_scale_for_station(region, w: int, h: int) -> [int, int, int, int]:
    """Scale a station services region based on the target resolution.
    This is performed because the tables on the station services screen do
    not increase proportionally with the screen size. The width changes with
    the screen size, the height does not change based on the screen size
    height, but on the screen width and the position stays consistent to the
    center of the screen.
    To calculate the new region height, we take the initial region defined at
    1920x1080 and scale up the height based on the target width and apply the
    new proportion against the center line.
    @param h: The screen height in pixels
    @param w: The screen width in pixels
    @param region: The region at 1920x1080
    @return: The new region in %
    """
    ref_w = 1920
    ref_h = 1080

    # Calc the x and y scaling.
    x_scale = w / ref_w
    y_scale = h / ref_h

    # Determine centre of the region
    reg_avg = 0.5
    # This alternate method below is based on the centre of the region instead of the centre of screen.
    # This will generally NOT work for station screens that are obviously centred vertically.
    # reg_avg = (region['rect'][1] + region['rect'][3]) / 2

    # Recalc the region as a % above and below the center line.
    pct_abv = (reg_avg - region["rect"][1]) * x_scale / y_scale
    pct_blw = (region["rect"][3] - reg_avg) * x_scale / y_scale

    # Apply new % to the center line.
    new_rect1 = reg_avg - pct_abv
    new_rect3 = reg_avg + pct_blw

    # Return the update top and bottom Y percentages with the original X percentages.
    new_reg = {"rect": [region["rect"][0], new_rect1, region["rect"][2], new_rect3]}
    return new_reg


def size_scale_for_station(width: int, height: int, w: int, h: int) -> (int, int):
    """Scale an item in the station services region based on the target resolution.
    This is performed because the tables on the station services screen do
    not increase proportionally with the screen size. The width changes with
    the screen size, the height does not change based on the screen size
    height, but on the screen width and the position stays consistent to the
    center of the screen.
    To calculate the new region height, we take the initial region defined at
    1920x1080 and scale up the height based on the target width and apply the
    new proportion against the center line.
    @param width: The width of the item in pixels
    @param height: The height of the item in pixels
    @param h: The screen height in pixels
    @param w: The screen width in pixels
    """
    ref_w = 1920

    # Calc the x scaling.
    x_scale = w / ref_w

    # Increase the height by the ratio of the width
    new_width = width * x_scale
    new_height = height * x_scale

    # Return the new height in pixels.
    return new_width, new_height


class ScreenRegions:
    def __init__(self, screen, templ):
        self.screen = screen
        self.templates = templ

        # Define the thresholds for template matching to be consistent throughout the program
        self.compass_match_thresh = 0.35
        self.navpoint_match_thresh = 0.8
        self.navpoint_glare_thresh = 0.7
        # Compass template matches below this score are refined with a fit of the sphere's outer ring
        self.compass_refine_below = 0.8
        # The filled nav point is white at its core; the cyan glow of the compass crosshair (pulsing while the
        # FSD charges) can match the filled template but is clearly saturated.
        self.navpoint_max_core_saturation = 110
        self.compass_scale_step = 0.025
        self.compass_scale_count = 11  # scales 1.0 to 1.25
        self.compass_scale_margin = 0.03
        self.compass_scale_good = 0.8
        self.compass_scale_hint = None
        self.target_thresh = 0.54
        self.sun_threshold = 125
        # The templates are made from true BGR screenshots, so the regions are captured without a channel swap.
        # The occluded target is matched in a white mask.
        self.target_occluded_thresh = 0.3
        # In SDR the occluded ring is beige instead of white (HDR). The beige mask also matches some bright
        # surfaces weakly, so it needs a higher threshold.
        self.target_occluded_tan_thresh = 0.4
        # Share of the message colored (cyan) pixels in the message region above which a message may be shown.
        # The cyan text and frame lines of the message are 0.6 % to 3 % of the region, other scenes stay below 0.3 %.
        self.message_text_fraction = 0.005
        # The message has long horizontal cyan frame lines: at least this share of a pixel row must be message colored
        self.message_line_fraction = 0.25
        # A scene counts as extremely bright (sun) when this share of the target region is almost white
        self.bright_scene_fraction = 0.5

        # array is in HSV order which represents color ranges for filtering
        self.orange_color_range = [array([0, 130, 123]), array([25, 235, 220])]
        self.orange_2_color_range = [array([16, 165, 220]), array([98, 255, 255])]
        self.target_occluded_range = [array([16, 31, 85]), array([26, 160, 212])]
        self.white_color_range = [array([0, 0, 215]), array([180, 40, 255])]
        self.tan_color_range = [array([8, 40, 150]), array([30, 140, 255])]
        self.blue_color_range = [array([0, 28, 170]), array([180, 100, 255])]
        self.blue_sco_color_range = [array([10, 0, 0]), array([100, 150, 255])]
        # Cyan of the HUD messages, saturated in dark scenes and pale when overexposed
        self.message_color_range = [array([88, 60, 170]), array([102, 255, 255])]

        self.reg = {}
        # regions with associated filter and color ranges
        # The rect is [L, T, R, B] top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg["compass"] = {
            "rect": [0.33, 0.65, 0.46, 1.0],
            "width": 1,
            "height": 1,
            "filterCB": self.equalize,
            "filter": None,
        }
        self.reg["target"] = {
            "rect": [0.33, 0.27, 0.66, 0.70],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_by_color,
            "filter": self.orange_2_color_range,
        }  # also called destination
        self.reg["target_occluded"] = {
            "rect": [0.33, 0.27, 0.66, 0.70],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_by_color,
            "filter": self.white_color_range,
        }
        self.reg["target_occluded_tan"] = {
            "rect": [0.33, 0.27, 0.66, 0.70],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_by_color,
            "filter": self.tan_color_range,
        }
        self.reg["sun"] = {
            "rect": [0.30, 0.30, 0.70, 0.68],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_sun,
            "filter": None,
        }
        self.reg["disengage"] = {
            "rect": [0.42, 0.65, 0.60, 0.80],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_by_color,
            "filter": self.blue_sco_color_range,
        }
        self.reg["sco"] = {
            "rect": [0.42, 0.65, 0.60, 0.80],
            "width": 1,
            "height": 1,
            "filterCB": self.filter_by_color,
            "filter": self.blue_sco_color_range,
        }
        # "MOVE TO OBTAIN LINE OF SIGHT TO TARGET" message, which is only shown with Supercruise Assist
        self.reg["line_of_sight"] = {
            "rect": [0.30, 0.30, 0.70, 0.40],
            "width": 1,
            "height": 1,
            "filterCB": None,
            "filter": None,
        }
        self.reg["fsd_align"] = {
            "rect": [0.40, 0.325, 0.60, 0.37],
            "width": 1,
            "height": 1,
            "filterCB": None,
            "filter": None,
        }
        self.reg["nav_panel"] = {
            "rect": [0.25, 0.36, 0.60, 0.85],
            "width": 1,
            "height": 1,
            "filterCB": self.equalize,
            "filter": None,
        }

        # convert rect from percent of screen into pixel location, calc the width/height of the area
        for i, key in enumerate(self.reg):
            xx = self.reg[key]["rect"]
            self.reg[key]["rect"] = [
                int(xx[0] * screen.screen_width),
                int(xx[1] * screen.screen_height),
                int(xx[2] * screen.screen_width),
                int(xx[3] * screen.screen_height),
            ]
            self.reg[key]["width"] = self.reg[key]["rect"][2] - self.reg[key]["rect"][0]
            self.reg[key]["height"] = self.reg[key]["rect"][3] - self.reg[key]["rect"][1]

    def capture_region(self, screen, region_name):
        """Just grab the screen based on the region name/rect.
        Returns an unfiltered image."""
        return screen.get_screen_region(self.reg[region_name]["rect"])

    def capture_region_filtered(self, screen, region_name, inv_col=True, source_callback=None):
        """Grab screen region and call its filter routine.
        Returns the filtered image."""
        if region_name == "target":
            self.target_debug_context = None
        if region_name == "target" and source_callback is not None and logger.isEnabledFor(logging.DEBUG):
            scr, self.target_debug_context = screen.get_screen_region_with_context(
                self.reg[region_name]["rect"], inv_col, scale=1.5
            )
        else:
            scr = screen.get_screen_region(self.reg[region_name]["rect"], inv_col)
        if source_callback is not None:
            source_callback(scr)
        if self.reg[region_name]["filterCB"] is None:
            # return the screen region untouched in BGRA format.
            return scr
        else:
            # return the screen region in the format returned by the filter.
            return self.reg[region_name]["filterCB"](scr, self.reg[region_name]["filter"])

    def match_template_in_region(self, region_name, templ_name, inv_col=True, source_callback=None):
        """Attempt to match the given template in the given region which is filtered using the region filter.
        Returns the filtered image, detail of match and the match mask."""
        img_region = self.capture_region_filtered(
            self.screen, region_name, inv_col, source_callback
        )  # which would call, reg.capture_region('compass') and apply defined filter
        match = cv2.matchTemplate(img_region, self.templates.template[templ_name]["image"], cv2.TM_CCOEFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(match)
        return img_region, (minVal, maxVal, minLoc, maxLoc), match

    def match_compass_multiscale(self):
        """Match the compass template at several scales, because the compass sphere differs in size between ship
        cockpits (the Type-9 sphere is about 17 % larger than the Mandalay one). The template's native scale wins
        unless another scale is clearly better. The last good scale is remembered and tried first, so a full scan
        is only needed after a ship change or a poor match. Returns the image, the match details at the best
        scale and that scale."""
        self.compass_debug_context = None
        if logger.isEnabledFor(logging.DEBUG):
            img_region, self.compass_debug_context = self.screen.get_screen_region_with_context(
                self.reg["compass"]["rect"], rgb=False
            )
        else:
            img_region = self.screen.get_screen_region(self.reg["compass"]["rect"], rgb=False)
        channels = cv2.split(cv2.cvtColor(img_region, cv2.COLOR_BGR2HSV))
        base = self.templates.template["compass"]["image"]

        def match_at(scale):
            templ = base
            if scale != 1.0:
                templ = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            return max(
                (cv2.minMaxLoc(cv2.matchTemplate(channel, templ, cv2.TM_CCOEFF_NORMED)) for channel in channels),
                key=lambda r: r[1],
            )

        step = self.compass_scale_step
        known = self.compass_scale_hint
        if known is not None:
            local = [(match_at(s), s) for s in (known, round(known - step, 3), round(known + step, 3)) if s >= 1.0]
            result, scale = max(local, key=lambda item: item[0][1])
            if result[1] >= self.compass_scale_good:
                self.compass_scale_hint = scale
                return img_region, result, scale

        best = None
        for index in range(self.compass_scale_count):
            scale = round(1.0 + index * step, 3)
            result = match_at(scale)
            # Prefer the native scale unless another one is clearly better
            required = self.compass_scale_margin if best is not None and best[2] == 1.0 else 0.0
            if best is None or result[1] > best[1][1] + required:
                best = (img_region, result, scale)
        if best[1][1] >= self.compass_scale_good:
            self.compass_scale_hint = best[2]
        return best

    def match_template_in_region_x3(self, region_name, templ_name, inv_col=True):
        """Attempt to match the given template in the given region which is unfiltered.
        The region's image is split into separate HSV channels, each channel tested and the best result kept.
        Returns the image, detail of match and the match mask."""
        img_region = self.screen.get_screen_region(self.reg[region_name]["rect"], rgb=False)
        templ = self.templates.template[templ_name]["image"]

        # Convert to HSV and split.
        img_hsv = cv2.cvtColor(img_region, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(img_hsv)
        # hsv_comb = np.concatenate((h, s, v), axis=1)  # Combine 3 images
        # cv2.imshow("Split HSV", hsv_comb)

        # Perform matches
        match_h = cv2.matchTemplate(h, templ, cv2.TM_CCOEFF_NORMED)
        match_s = cv2.matchTemplate(s, templ, cv2.TM_CCOEFF_NORMED)
        match_v = cv2.matchTemplate(v, templ, cv2.TM_CCOEFF_NORMED)
        (minVal_h, maxVal_h, minLoc_h, maxLoc_h) = cv2.minMaxLoc(match_h)
        (minVal_s, maxVal_s, minLoc_s, maxLoc_s) = cv2.minMaxLoc(match_s)
        (minVal_v, maxVal_v, minLoc_v, maxLoc_v) = cv2.minMaxLoc(match_v)
        # match_comb = np.concatenate((match_h, match_s, match_v), axis=1)  # Combine 3 images
        # cv2.imshow("Split Matches", match_comb)

        # Get best result
        # V is likely the best match, so check it first
        if maxVal_v > maxVal_s and maxVal_v > maxVal_h:
            return img_region, (minVal_v, maxVal_v, minLoc_v, maxLoc_v), match_v
        # S is likely the 2nd best match, so check it
        if maxVal_s > maxVal_h:
            return img_region, (minVal_s, maxVal_s, minLoc_s, maxLoc_s), match_s
        # H must be the best match
        return img_region, (minVal_h, maxVal_h, minLoc_h, maxLoc_h), match_h

    def message_text_present(self, region_name="disengage") -> bool:
        """Cheap, language independent check if a (cyan) HUD message is shown in the message region.
        The OCR is only needed when this is True."""
        img = self.screen.get_screen_region(self.reg[region_name]["rect"], rgb=False)[:, :, :3]
        mask = self.filter_by_color(img, self.message_color_range) > 0
        self.last_message_fraction = float(mask.mean())
        self.last_message_line = float(mask.mean(axis=1).max())
        return (
            self.last_message_fraction >= self.message_text_fraction
            and self.last_message_line >= self.message_line_fraction
        )

    def message_image(self, region_name="disengage", raw=False, upscale=1):
        """Return the message region as a BGR image with everything but the HUD message text blacked out,
        ready for OCR. With raw=True the color filter is skipped, upscale enlarges the image for small text."""
        img = self.screen.get_screen_region(self.reg[region_name]["rect"], rgb=False)[:, :, :3]
        if not raw:
            mask = self.filter_by_color(img, self.blue_sco_color_range)
            img = cv2.bitwise_and(img, img, mask=mask)
        if upscale != 1:
            img = cv2.resize(img, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        return img

    def scene_is_bright(self) -> bool:
        """True if the target region is extremely bright, like looking into a sun."""
        img = self.screen.get_screen_region(self.reg["target"]["rect"], rgb=False)
        value = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV)[:, :, 2]
        return float((value >= 235).mean()) >= self.bright_scene_fraction

    def match_template_in_image(self, image, template):
        """Attempt to match the given template in the (unfiltered) image.
        Returns the original image, detail of match and the match mask."""
        match = cv2.matchTemplate(image, self.templates.template[template]["image"], cv2.TM_CCOEFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(match)
        return image, (minVal, maxVal, minLoc, maxLoc), match

    def match_template_in_image_x3(self, image, templ_name, scale=1.0):
        """Attempt to match the given template (optionally resized by scale) in the (unfiltered) image.
        The image is split into separate HSV channels, each channel tested and the best result kept.
        Returns the original image, detail of match and the match mask."""
        templ = self.templates.template[templ_name]["image"]
        if scale != 1.0:
            templ = cv2.resize(templ, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        # Convert to HSV and split.
        img_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(img_hsv)
        # hsv_comb = np.concatenate((h, s, v), axis=1)  # Combine 3 images
        # cv2.imshow("Split HSV", hsv_comb)

        # Perform matches
        match_h = cv2.matchTemplate(h, templ, cv2.TM_CCOEFF_NORMED)
        match_s = cv2.matchTemplate(s, templ, cv2.TM_CCOEFF_NORMED)
        match_v = cv2.matchTemplate(v, templ, cv2.TM_CCOEFF_NORMED)
        (minVal_h, maxVal_h, minLoc_h, maxLoc_h) = cv2.minMaxLoc(match_h)
        (minVal_s, maxVal_s, minLoc_s, maxLoc_s) = cv2.minMaxLoc(match_s)
        (minVal_v, maxVal_v, minLoc_v, maxLoc_v) = cv2.minMaxLoc(match_v)
        # match_comb = np.concatenate((match_h, match_s, match_v), axis=1)  # Combine 3 images
        # cv2.imshow("Split Matches", match_comb)

        # Get best result
        # V is likely the best match, so check it first
        if maxVal_v > maxVal_s and maxVal_v > maxVal_h:
            return image, (minVal_v, maxVal_v, minLoc_v, maxLoc_v), match_v
        # S is likely the 2nd best match, so check it
        if maxVal_s > maxVal_h:
            return image, (minVal_s, maxVal_s, minLoc_s, maxLoc_s), match_s
        # H must be the best match
        return image, (minVal_h, maxVal_h, minLoc_h, maxLoc_h), match_h

    def equalize(self, image=None, no_op=None):
        # Load the image in greyscale
        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # create a CLAHE object (Arguments are optional).  Histogram equalization, improves constrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img_out = clahe.apply(img_gray)

        return img_out

    def filter_by_color(self, image, color_range):
        """Filters an image based on a given color range.
        Returns the filtered image. Pixels within the color range are returned
        their original color, otherwise black."""
        # converting from BGR to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # filter passed in color low, high
        filtered = cv2.inRange(hsv, color_range[0], color_range[1])

        return filtered

    # not used
    def filter_bright(self, image=None, no_op=None):
        equalized = self.equalize(image)
        equalized = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)  # hhhmm, equalize() already converts to gray
        equalized = cv2.cvtColor(equalized, cv2.COLOR_BGR2HSV)
        filtered = cv2.inRange(equalized, array([0, 0, 215]), array([0, 0, 255]))  # only high value

        return filtered

    def set_sun_threshold(self, thresh):
        self.sun_threshold = thresh

    # need to compare filter_sun with filter_bright
    def filter_sun(self, image=None, no_op=None):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # set low end of filter to 25 to pick up the dull red Class L stars
        (thresh, blackAndWhiteImage) = cv2.threshold(hsv, self.sun_threshold, 255, cv2.THRESH_BINARY)

        return blackAndWhiteImage

    # percent the image is white
    def sun_percent(self, screen):
        blackAndWhiteImage = self.capture_region_filtered(screen, "sun")

        wht = sum(blackAndWhiteImage == 255)
        blk = sum(blackAndWhiteImage != 255)

        result = int((wht / (wht + blk)) * 100)

        return result

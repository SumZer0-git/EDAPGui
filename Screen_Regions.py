import numpy as np
from numpy import array, sum
import cv2
import json
import os


"""
File:Screen_Regions.py    

Description:
  Class to rectangle areas of the screen to capture along with filters to apply. Includes functions to
  match a image template to the region using opencv 

Author: sumzer0@yahoo.com
"""


def reg_scale_for_station(region, w: int, h: int) -> [int, int, int, int]:
    """ Scale a station services region based on the target resolution.
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
    pct_abv = (reg_avg - region['rect'][1]) * x_scale / y_scale
    pct_blw = (region['rect'][3] - reg_avg) * x_scale / y_scale

    # Apply new % to the center line.
    new_rect1 = reg_avg - pct_abv
    new_rect3 = reg_avg + pct_blw

    # Return the update top and bottom Y percentages with the original X percentages.
    new_reg = {'rect': [region['rect'][0], new_rect1, region['rect'][2], new_rect3]}
    return new_reg


def size_scale_for_station(width: int, height: int, w: int, h: int) -> (int, int):
    """ Scale an item in the station services region based on the target resolution.
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
    ref_h = 1080

    # Calc the x and y scaling.
    x_scale = w / ref_w
    y_scale = h / ref_h

    # Increase the height by the ratio of the width
    new_width = width * x_scale
    new_height = height * x_scale

    # Return the new height in pixels.
    return new_width, new_height


class Screen_Regions:
    def __init__(self, screen, templ):
        self.screen = screen
        self.templates = templ

        # Define the thresholds for template matching to be consistent throughout the program
        self.compass_match_thresh = 0.35
        self.navpoint_match_thresh = 0.8
        self.target_thresh = 0.54
        self.target_occluded_thresh = 0.55
        self.sun_threshold = 125
        self.disengage_thresh = 0.25

        # array is in HSV order which represents color ranges for filtering
        self.orange_color_range   = [array([0, 130, 123]),  array([25, 235, 220])]
        self.orange_2_color_range = [array([16, 165, 220]), array([98, 255, 255])]
        self.target_occluded_range= [array([16, 31, 85]),   array([26, 160, 212])]
        self.blue_color_range     = [array([0, 28, 170]), array([180, 100, 255])]
        self.blue_sco_color_range = [array([10, 0, 0]), array([100, 150, 255])]
        self.fss_color_range      = [array([95, 210, 70]),  array([105, 255, 120])]

        self.reg = {}
        # regions with associated filter and color ranges
        # The rect is [L, T, R, B] top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg['compass']   = {'rect': [0.33, 0.65, 0.46, 1.0], 'width': 1, 'height': 1, 'filterCB': self.equalize,                                'filter': None}
        self.reg['target']    = {'rect': [0.33, 0.27, 0.66, 0.70], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color, 'filter': self.orange_2_color_range}   # also called destination
        self.reg['target_occluded']    = {'rect': [0.33, 0.27, 0.66, 0.70], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color, 'filter': self.target_occluded_range} 
        self.reg['sun']       = {'rect': [0.30, 0.30, 0.70, 0.68], 'width': 1, 'height': 1, 'filterCB': self.filter_sun, 'filter': None}
        self.reg['disengage'] = {'rect': [0.42, 0.65, 0.60, 0.80], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color, 'filter': self.blue_sco_color_range}
        self.reg['sco']       = {'rect': [0.42, 0.65, 0.60, 0.80], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color, 'filter': self.blue_sco_color_range}
        self.reg['fss']       = {'rect': [0.5045, 0.7545, 0.532, 0.7955], 'width': 1, 'height': 1, 'filterCB': self.equalize, 'filter': None}
        self.reg['mission_dest']  = {'rect': [0.46, 0.38, 0.65, 0.86], 'width': 1, 'height': 1, 'filterCB': self.equalize, 'filter': None}    
        self.reg['missions']    = {'rect': [0.50, 0.78, 0.65, 0.85], 'width': 1, 'height': 1, 'filterCB': self.equalize, 'filter': None}   
        
        self.load_calibrated_regions()

        # convert rect from percent of screen into pixel location, calc the width/height of the area
        for i, key in enumerate(self.reg):
            xx = self.reg[key]['rect']
            self.reg[key]['rect'] = [int(xx[0]*screen.screen_width), int(xx[1]*screen.screen_height), 
                                     int(xx[2]*screen.screen_width), int(xx[3]*screen.screen_height)]
            self.reg[key]['width']  = self.reg[key]['rect'][2] - self.reg[key]['rect'][0]
            self.reg[key]['height'] = self.reg[key]['rect'][3] - self.reg[key]['rect'][1]

    def load_calibrated_regions(self):
        calibration_file = 'configs/ocr_calibration.json'
        if os.path.exists(calibration_file):
            with open(calibration_file, 'r') as f:
                calibrated_regions = json.load(f)

            for key, value in self.reg.items():
                calibrated_key = f"Screen_Regions.{key}"
                if calibrated_key in calibrated_regions:
                    self.reg[key]['rect'] = calibrated_regions[calibrated_key]['rect']

    def capture_region(self, screen, region_name):
        """ Just grab the screen based on the region name/rect.
        Returns an unfiltered image. """
        return screen.get_screen_region(self.reg[region_name]['rect'])

    def capture_region_filtered(self, screen, region_name, inv_col=True):
        """ Grab screen region and call its filter routine.
        Returns the filtered image. """
        scr = screen.get_screen_region(self.reg[region_name]['rect'], inv_col)
        if self.reg[region_name]['filterCB'] is None:
            # return the screen region untouched in BGRA format.
            return scr
        else:
            # return the screen region in the format returned by the filter.
            return self.reg[region_name]['filterCB'](scr, self.reg[region_name]['filter'])

    def match_template_in_region(self, region_name, templ_name, inv_col=True):
        """ Attempt to match the given template in the given region which is filtered using the region filter.
        Returns the filtered image, detail of match and the match mask. """
        img_region = self.capture_region_filtered(self.screen, region_name, inv_col)    # which would call, reg.capture_region('compass') and apply defined filter
        match = cv2.matchTemplate(img_region, self.templates.template[templ_name]['image'], cv2.TM_CCOEFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(match)
        return img_region, (minVal, maxVal, minLoc, maxLoc), match

    def match_template_in_region_x3(self, region_name, templ_name, inv_col=True):
        """ Attempt to match the given template in the given region which is unfiltered.
        The region's image is split into separate HSV channels, each channel tested and the best result kept.
        Returns the image, detail of match and the match mask. """
        img_region = self.screen.get_screen_region(self.reg[region_name]['rect'], rgb=False)
        templ = self.templates.template[templ_name]['image']

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

    def match_template_in_image(self, image, template):
        """ Attempt to match the given template in the (unfiltered) image.
        Returns the original image, detail of match and the match mask. """
        match = cv2.matchTemplate(image, self.templates.template[template]['image'], cv2.TM_CCOEFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(match)
        return image, (minVal, maxVal, minLoc, maxLoc), match     

    def match_template_in_image_x3(self, image, templ_name):
        """ Attempt to match the given template in the (unfiltered) image.
        The image is split into separate HSV channels, each channel tested and the best result kept.
        Returns the original image, detail of match and the match mask. """
        templ = self.templates.template[templ_name]['image']

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

    def equalize(self, image=None, noOp=None):
        # Load the image in greyscale
        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # create a CLAHE object (Arguments are optional).  Histogram equalization, improves constrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
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
    def filter_bright(self, image=None, noOp=None):
        equalized = self.equalize(image)
        equalized = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)    #hhhmm, equalize() already converts to gray
        equalized = cv2.cvtColor(equalized, cv2.COLOR_BGR2HSV)
        filtered  = cv2.inRange(equalized, array([0, 0, 215]), array([0, 0, 255]))  #only high value

        return filtered
    
    def set_sun_threshold(self, thresh):
        self.sun_threshold = thresh

    # need to compare filter_sun with filter_bright
    def filter_sun(self, image=None, noOp=None):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # set low end of filter to 25 to pick up the dull red Class L stars
        (thresh, blackAndWhiteImage) = cv2.threshold(hsv, self.sun_threshold, 255, cv2.THRESH_BINARY)

        return blackAndWhiteImage

    # percent the image is white
    def sun_percent(self, screen):
        blackAndWhiteImage = self.capture_region_filtered(screen, 'sun')
 
        wht = sum(blackAndWhiteImage == 255)     
        blk = sum(blackAndWhiteImage != 255)

        result = int((wht / (wht+blk))*100)

        return result

from __future__ import annotations
import os
import sys
import typing
import threading
import cv2
import win32con
import win32gui
from numpy import array
import mss
import json

from EDlogger import logger


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller bundles."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


"""
File:Screen.py    

Description:
  Class to handle screen grabs

Author: sumzer0@yahoo.com
"""
# size() return (ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1))
# TODO: consider update to handle ED running in a window
#   find the ED Window
#   win32gui.SetForegroundWindow(hwnd)
#    bbox = win32gui.GetWindowRect(hwnd)     will also then give me the resolution of the image
#     img = ImageGrab.grab(bbox)

elite_dangerous_window = "Elite - Dangerous (CLIENT)"


def set_focus_elite_window():
    """ set focus to the ED window, if ED does not have focus then the keystrokes will go to the window
    that does have focus. """
    ed_title = "Elite - Dangerous (CLIENT)"

    # TODO - determine if GetWindowText is faster than FindWindow if ED is in foreground
    if win32gui.GetWindowText(win32gui.GetForegroundWindow()) == ed_title:
        return

    handle = win32gui.FindWindow(0, ed_title)
    if handle != 0:
        try:
            win32gui.ShowWindow(handle, win32con.SW_NORMAL)  # give focus to ED
            win32gui.SetForegroundWindow(handle)  # give focus to ED
        except:
            print("set_focus_elite_window ERROR")
            pass


class Screen:
    # Thread-local storage for mss instances (mss 10.x requires per-thread instances)
    _thread_local = threading.local()

    @property
    def mss(self):
        """Get thread-local mss instance. Creates one if it doesn't exist for this thread."""
        if not hasattr(Screen._thread_local, 'mss_instance'):
            Screen._thread_local.mss_instance = mss.mss()
        return Screen._thread_local.mss_instance

    def __init__(self, cb):
        self.ap_ckb = cb
        # Note: self.mss is now a property that returns thread-local mss instance
        self.using_screen = True  # True to use screen, false to use an image. Set screen_image to the image
        self._screen_image = None  # Screen image captured from screen, or loaded by user for testing.

        # 16:9 crop offsets (for non-16:9 screens)
        self.crop_offset_x = 0
        self.crop_offset_y = 0
        self.raw_screen_width = 0
        self.raw_screen_height = 0

        # Find ED window position to determine which monitor it is on
        ed_rect = self.get_elite_window_rect()
        if ed_rect is None:
            self.ap_ckb('log', f"ERROR: Could not find window {elite_dangerous_window}.")
            logger.error(f'Could not find window {elite_dangerous_window}.')
        else:
            logger.debug(f'Found Elite Dangerous window position: {ed_rect}')

        # Examine all monitors to determine match with ED
        self.mons = self.mss.monitors
        mon_num = 0
        for item in self.mons:
            if mon_num > 0:  # ignore monitor 0 as it is the complete desktop (dims of all monitors)
                logger.debug(f'Found monitor {mon_num} with details: {item}')
                if ed_rect is None:
                    self.monitor_number = mon_num
                    self.mon = self.mss.monitors[self.monitor_number]
                    logger.debug(f'Defaulting to monitor {mon_num}.')
                    self.raw_screen_width = item['width']
                    self.raw_screen_height = item['height']
                    break
                else:
                    if item['left'] == ed_rect[0] and item['top'] == ed_rect[1]:
                        # Get information of monitor 2
                        self.monitor_number = mon_num
                        self.mon = self.mss.monitors[self.monitor_number]
                        logger.debug(f'Elite Dangerous is on monitor {mon_num}.')
                        self.raw_screen_width = item['width']
                        self.raw_screen_height = item['height']

            # Next monitor
            mon_num = mon_num + 1

        # Calculate 16:9 crop area (for non-16:9 screens like ultrawide or 4:3)
        self._calculate_16_9_crop()

        logger.debug(f'Raw screen: {self.raw_screen_width}x{self.raw_screen_height}, '
                     f'16:9 area: {self.screen_width}x{self.screen_height}, '
                     f'Offset: ({self.crop_offset_x}, {self.crop_offset_y})')

        # Add new screen resolutions here with tested scale factors
        # this table will be default, overwritten when loading resolution.json file
        self.scales = {  # scaleX, scaleY
            '1024x768': [0.39, 0.39],  # tested, but not has high match %
            '1080x1080': [0.5, 0.5],  # fix, not tested
            '1280x800': [0.48, 0.48],  # tested
            '1280x1024': [0.5, 0.5],  # tested
            '1600x900': [0.6, 0.6],  # tested
            '1920x1080': [0.75, 0.75],  # tested
            '1920x1200': [0.73, 0.73],  # tested
            '1920x1440': [0.8, 0.8],  # tested
            '2560x1080': [0.75, 0.75],  # tested
            '2560x1440': [1.0, 1.0],  # tested
            '3440x1440': [1.0, 1.0],  # tested
            # 'Calibrated': [-1.0, -1.0]
        }

        # used this to write the self.scales table to the json file
        # self.write_config(self.scales)

        ss = self.read_config()

        # if we read it then point to it, otherwise use the default table above
        if ss is not None:
            self.scales = ss
            logger.debug("read json:" + str(ss))

        # try to find the resolution/scale values in table
        # if not, then take current screen size and divide it out by 3440 x1440
        try:
            scale_key = str(self.screen_width) + "x" + str(self.screen_height)
            self.scaleX = self.scales[scale_key][0]
            self.scaleY = self.scales[scale_key][1]
        except:
            # if we don't have a definition for the resolution then use calculation
            self.scaleX = self.screen_width / 3440.0
            self.scaleY = self.screen_height / 1440.0

        # if the calibration scale values are not -1, then use those regardless of above
        # if self.scales['Calibrated'][0] != -1.0:
        #     self.scaleX = self.scales['Calibrated'][0]
        # if self.scales['Calibrated'][1] != -1.0:
        #     self.scaleY = self.scales['Calibrated'][1]

        logger.debug('screen size: ' + str(self.screen_width) + " " + str(self.screen_height))
        logger.debug('Default scale X, Y: ' + str(self.scaleX) + ", " + str(self.scaleY))

    @staticmethod
    def get_elite_window_rect() -> typing.Tuple[int, int, int, int] | None:
        """ Gets the ED window rectangle.
        Returns (left, top, right, bottom) or None.
        """
        hwnd = win32gui.FindWindow(None, elite_dangerous_window)
        if hwnd:
            rect = win32gui.GetWindowRect(hwnd)
            return rect
        else:
            return None

    @staticmethod
    def elite_window_exists() -> bool:
        """ Does the ED Client Window exist (i.e. is ED running)
        """
        hwnd = win32gui.FindWindow(None, elite_dangerous_window)
        if hwnd:
            return True
        else:
            return False

    def write_config(self, data, fileName='configs/resolution.json'):
        if data is None:
            data = self.scales
        try:
            with open(get_resource_path(fileName), "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("Screen.py write_config error:" + str(e))

    def read_config(self, fileName='configs/resolution.json'):
        s = None
        try:
            with open(get_resource_path(fileName), "r") as fp:
                s = json.load(fp)
        except Exception as e:
            logger.warning("Screen.py read_config error :" + str(e))

        return s

    def _calculate_16_9_crop(self):
        """Calculate the 16:9 crop area for non-16:9 screens.
        Centers the 16:9 area within the actual screen dimensions.
        """
        target_aspect = 16 / 9
        current_aspect = self.raw_screen_width / self.raw_screen_height if self.raw_screen_height > 0 else target_aspect

        if abs(current_aspect - target_aspect) < 0.01:
            # Already 16:9 (within tolerance)
            self.screen_width = self.raw_screen_width
            self.screen_height = self.raw_screen_height
            self.crop_offset_x = 0
            self.crop_offset_y = 0
            logger.debug('Screen is already 16:9, no cropping needed.')
        elif current_aspect > target_aspect:
            # Screen is wider than 16:9 (e.g., ultrawide 21:9)
            # Crop the sides, keep full height
            self.screen_height = self.raw_screen_height
            self.screen_width = int(self.raw_screen_height * target_aspect)
            self.crop_offset_x = (self.raw_screen_width - self.screen_width) // 2
            self.crop_offset_y = 0
            logger.debug(f'Screen is wider than 16:9 (aspect {current_aspect:.2f}), cropping sides.')
        else:
            # Screen is taller than 16:9 (e.g., 4:3, 5:4)
            # Crop top and bottom, keep full width
            self.screen_width = self.raw_screen_width
            self.screen_height = int(self.raw_screen_width / target_aspect)
            self.crop_offset_x = 0
            self.crop_offset_y = (self.raw_screen_height - self.screen_height) // 2
            logger.debug(f'Screen is taller than 16:9 (aspect {current_aspect:.2f}), cropping top/bottom.')

    # reg defines a box as a percentage of screen width and height
    def get_screen_region(self, reg, rgb=True):
        image = self.get_screen(int(reg[0]), int(reg[1]), int(reg[2]), int(reg[3]), rgb)
        return image

    def get_screen(self, x_left, y_top, x_right, y_bot, rgb=True):  # if absolute need to scale??
        # Apply 16:9 crop offsets to capture from the centered 16:9 region
        monitor = {
            "top": self.mon["top"] + self.crop_offset_y + y_top,
            "left": self.mon["left"] + self.crop_offset_x + x_left,
            "width": x_right - x_left,
            "height": y_bot - y_top,
            "mon": self.monitor_number,
        }
        image = array(self.mss.grab(monitor))
        # TODO - mss.grab returns the image in BGR format, so no need to convert to RGB2BGR
        if rgb:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image

    def get_screen_rect_pct(self, rect):
        """ Grabs a screenshot and returns the selected region as an image.
        @param rect: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: An image defined by the region.
        """
        if self.using_screen:
            abs_rect = self.screen_rect_to_abs(rect)
            image = self.get_screen(abs_rect[0], abs_rect[1], abs_rect[2], abs_rect[3])
            # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image
        else:
            if self._screen_image is None:
                return None

            image = self.crop_image_by_pct(self._screen_image, rect)
            return image

    def screen_rect_to_abs(self, rect):
        """ Converts an array of real percentage screen values to int absolutes.
        These coordinates are relative to the 16:9 cropped area, for use with screen capture.
        @param rect: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: A rect array ([L, T, R, B]) in pixels (relative to 16:9 area)
        """
        abs_rect = [int(rect[0] * self.screen_width), int(rect[1] * self.screen_height),
                    int(rect[2] * self.screen_width), int(rect[3] * self.screen_height)]
        return abs_rect

    def screen_rect_to_abs_overlay(self, rect):
        """ Converts an array of real percentage screen values to int absolutes for overlay drawing.
        These coordinates include the crop offset, for use with the overlay on the full screen.
        @param rect: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: A rect array ([L, T, R, B]) in pixels (relative to full screen with crop offset)
        """
        abs_rect = [
            int(rect[0] * self.screen_width) + self.crop_offset_x,
            int(rect[1] * self.screen_height) + self.crop_offset_y,
            int(rect[2] * self.screen_width) + self.crop_offset_x,
            int(rect[3] * self.screen_height) + self.crop_offset_y
        ]
        return abs_rect

    def abs_rect_to_overlay(self, rect):
        """ Adds crop offset to already-absolute pixel coordinates for overlay drawing.
        Use this when the rect is already in pixels (e.g., from Screen_Regions).
        @param rect: A rect array ([L, T, R, B]) already in pixels
        @return: A rect array ([L, T, R, B]) in pixels with crop offset added
        """
        return [
            rect[0] + self.crop_offset_x,
            rect[1] + self.crop_offset_y,
            rect[2] + self.crop_offset_x,
            rect[3] + self.crop_offset_y
        ]

    def get_screen_full(self):
        """ Grabs a full screenshot and returns the image.
        """
        if self.using_screen:
            image = self.get_screen(0, 0, self.screen_width, self.screen_height)
            # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image
        else:
            if self._screen_image is None:
                return None

            return self._screen_image

    def crop_image_by_pct(self, image, rect):
        """ Crop an image using a percentage values (0.0 - 1.0).
        Rect is an array of crop % [0.10, 0.20, 0.90, 0.95] = [Left, Top, Right, Bottom]
        Returns the cropped image. """
        # Existing size
        h, w, ch = image.shape

        # Crop to leave only the selected rectangle
        x0 = int(w * rect[0])
        y0 = int(h * rect[1])
        x1 = int(w * rect[2])
        y1 = int(h * rect[3])

        # Crop image
        cropped = image[y0:y1, x0:x1]
        return cropped

    def crop_image(self, image, rect):
        """ Crop an image using a pixel values.
        Rect is an array of pixel values [100, 200, 1800, 1600] = [X0, Y0, X1, Y1]
        Returns the cropped image."""
        cropped = image[rect[1]:rect[3], rect[0]:rect[2]]  # i.e. [y:y+h, x:x+w]
        return cropped

    def set_screen_image(self, image):
        """ Use an image instead of a screen capture. Sets the image and also sets the
        screen width and height to the image properties.
        @param image: The image to use.
        """
        self.using_screen = False
        self._screen_image = image

        # Existing size
        h, w, ch = image.shape

        # Set the screen size to the original image size, not the region size
        self.screen_width = w
        self.screen_height = h


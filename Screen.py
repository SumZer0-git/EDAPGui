from __future__ import annotations
import time
import typing
from copy import copy

import cv2
import win32con
import win32gui
import numpy as np
from numpy import array
import mss
import json

from EDlogger import logger
from Screen_Regions import Quad

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


def crop_image_by_pct(image, quad: Quad):
    """ Crop an image using a percentage values (0.0 - 1.0).
    Rect is an array of crop % [0.10, 0.20, 0.90, 0.95] = [Left, Top, Right, Bottom]
    Returns the cropped image. """
    # Existing size
    h, w, ch = image.shape
    # Make a local copy
    q = copy(quad)
    # Scale from percent to pixels
    q.scale_from_origin(w, h)
    # Crop image
    cropped = crop_image_pix(image, q)
    return cropped


def crop_image_pix(image, quad: Quad):
    """ Crop an image using a pixel values.
    Rect is an array of pixel values [100, 200, 1800, 1600] = [X0, Y0, X1, Y1] = [L, T, R, B]
    Returns the cropped image."""
    cropped = image[int(quad.top):int(quad.bottom),
                    int(quad.left):int(quad.right)]  # i.e. [y:y+h, x:x+w]
    return cropped


class Screen:
    def __init__(self, cb):
        self.ap_ckb = cb
        self.mss = mss.mss()
        self.using_screen = True  # True to use screen, false to use an image. Set screen_image to the image
        self._screen_image = None  # Screen image captured from screen, or loaded by user for testing.
        self.screen_width = 0
        self.screen_height = 0
        self.screen_left = 0
        self.screen_top = 0
        self.monitor_number = 0
        self.aspect_ratio = 0
        self.mon = None
        # Throttle state for repeated screen-capture failure messages so the log is not flooded.
        self._last_capture_warn_ts = 0.0
        self._capture_warn_interval = 5.0  # seconds between repeated warnings
        self._capture_failure_count = 0

        # Find ED window position to determine which monitor it is on
        ed_rect = self.get_elite_window_rect()
        if ed_rect is None:
            msg = f"Could not find window '{elite_dangerous_window}'. Once Elite Dangerous is running, restart EDAP."
            self.ap_ckb('log', f"ERROR: {msg}")
            logger.error(msg)
        else:
            logger.debug(f'Found Elite Dangerous window position: {ed_rect}')

        # Examine all monitors to determine match with ED
        self.mons = self.mss.monitors
        mon_num = 0
        default = True
        for item in self.mons:
            logger.debug(f'Found monitor {mon_num} with details: {item}')
            if mon_num > 0:  # ignore monitor 0 as it is the complete desktop (dims of all monitors)
                if ed_rect is not None:
                    if item['left'] == ed_rect[0] and item['top'] == ed_rect[1]:
                        # Get information of monitor
                        self.monitor_number = mon_num
                        self.mon = self.mss.monitors[self.monitor_number]
                        self.screen_width = item['width']
                        self.screen_height = item['height']
                        self.aspect_ratio = self.screen_width / self.screen_height
                        self.screen_left = item['left']
                        self.screen_top = item['top']
                        logger.debug(f'Elite Dangerous is on monitor {mon_num}.')
                        default = False
                        break

            # Store the first monitor incase we need it as default
            if mon_num == 1:
                self.monitor_number = mon_num
                self.mon = self.mss.monitors[self.monitor_number]
                self.screen_width = item['width']
                self.screen_height = item['height']
                self.aspect_ratio = self.screen_width / self.screen_height
                self.screen_left = item['left']
                self.screen_top = item['top']

            # Next monitor
            mon_num = mon_num + 1

        # Check if ED was found on a monitor, or if we are using the default monitor
        if default:
            msg = (f"Elite Dangerous could not be located on any monitor. Check Elite Dangerous is not minimized and "
                   f"is visible on screen.")
            self.ap_ckb('log', f"ERROR: {msg}")
            logger.error(msg)

        # Add new screen resolutions here with tested scale factors
        # this table will be default, overwritten when loading resolution.json file
        self.scales = {  # scaleX, scaleY
            '1024x768':   [0.39, 0.39],  # tested, but not has high match % 
            '1080x1080':  [0.5, 0.5],    # fix, not tested
            '1280x800':   [0.48, 0.48],  # tested
            '1280x1024':  [0.5, 0.5],    # tested
            '1600x900':   [0.6, 0.6],    # tested
            '1920x1080':  [0.75, 0.75],  # tested
            '1920x1200':  [0.73, 0.73],  # tested
            '1920x1440':  [0.8, 0.8],    # tested
            '2560x1080':  [0.75, 0.75],  # tested
            '2560x1440':  [1.0, 1.0],    # tested
            '3440x1440':  [1.0, 1.0],    # tested
            # 'Calibrated': [-1.0, -1.0]
        }

        # used this to write the self.scales table to the json file
        # self.write_config(self.scales)
        
        ss = self.read_config()

        # if we read it then point to it, otherwise use the default table above
        if ss is not None:
            self.scales = ss
            logger.debug("read json:"+str(ss))

        # try to find the resolution/scale values in table
        # if not, then take current screen size and divide it out by 3440 x1440
        try:
            scale_key = str(self.screen_width)+"x"+str(self.screen_height)
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
        
        logger.debug('screen size: w='+str(self.screen_width)+" h="+str(self.screen_height))
        logger.debug('screen position: x='+str(self.screen_left)+" y="+str(self.screen_top))
        logger.debug('Default scale X, Y: '+str(self.scaleX)+", "+str(self.scaleY))

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

    def write_config(self, data, fileName='./configs/resolution.json'):
        if data is None:
            data = self.scales
        try:
            with open(fileName,"w") as fp:
                json.dump(data,fp, indent=4)
        except Exception as e:
            logger.warning("Screen.py write_config error:"+str(e))

    def read_config(self, fileName='./configs/resolution.json'):
        s = None
        try:
            with open(fileName,"r") as fp:
                s = json.load(fp)
        except Exception as e:
            logger.warning("Screen.py read_config error :"+str(e))

        return s

    # reg defines a box as a percentage of screen width and height
    def get_screen_region(self, rect, rgb=True):
        image = self.get_screen(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]), rgb)
        return image

    def get_screen(self, x_left, y_top, x_right, y_bot, rgb=True):    # if absolute need to scale??
        """ Get screen from co-ords in pixels.
        Returns the captured image, or None if capture failed (empty grab, no monitor, etc.).
        Callers must tolerate None.
        """
        monitor = {
            "top": self.mon["top"] + int(y_top),
            "left": self.mon["left"] + int(x_left),
            "width": int(x_right - x_left),
            "height": int(y_bot - y_top),
            "mon": self.monitor_number,
        }
        try:
            image = array(self.mss.grab(monitor))
        except Exception as e:
            self._warn_capture_failure(f"mss.grab() raised {type(e).__name__}: {e}")
            return None

        if image is None or image.size == 0 or image.shape[0] == 0 or image.shape[1] == 0:
            self._warn_capture_failure(
                "mss.grab() returned an empty image. Most likely cause: Elite Dangerous is running "
                "in exclusive 'Fullscreen' mode (set Display Mode to 'Borderless' in ED's graphics "
                "options). Other causes: ED was moved to a different monitor after EDAP started "
                "(restart EDAP), or HDR / DPI scaling issues."
            )
            return None

        # TODO - mss.grab returns the image in BGR format, so no need to convert to RGB2BGR
        if rgb:
            try:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            except cv2.error as e:
                self._warn_capture_failure(f"cv2.cvtColor failed on captured image: {e}")
                return None
        return image
        
    def get_screen_rect_pct(self, rect):
        """ Grabs a screenshot and returns the selected region as an image.
        @param rect: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: An image defined by the region, or None if capture failed.
        """
        if self.using_screen:
            abs_rect = self.screen_rect_to_abs(rect)
            image = self.get_screen(abs_rect[0], abs_rect[1], abs_rect[2], abs_rect[3])
            if image is None:
                return None
            # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
            try:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            except cv2.error as e:
                self._warn_capture_failure(f"cv2.cvtColor (BGR2RGB) failed: {e}")
                return None
            return image
        else:
            if self._screen_image is None:
                return None

            q = Quad.from_rect(rect)
            image = crop_image_by_pct(self._screen_image, q)
            return image

    def screen_rect_to_abs(self, rect):
        """ Converts and array of real percentage screen values to int absolutes.
        @param rect: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: A rect array ([L, T, R, B]) in pixels
        """
        abs_rect = [int(rect[0] * self.screen_width), int(rect[1] * self.screen_height),
                    int(rect[2] * self.screen_width), int(rect[3] * self.screen_height)]
        return abs_rect

    def screen_region_pct_to_pix(self, quad: Quad) -> Quad:
        """ Converts and array of real percentage screen values to int absolutes.
        @param quad: A rect array ([L, T, R, B]) in percent (0.0 - 1.0)
        @return: A rect array ([L, T, R, B]) in pixels
        """
        q = copy(quad)
        q.scale_from_origin(self.screen_width, self.screen_height)
        return q

    def get_screen_full(self):
        """ Grabs a full screenshot and returns the image, or None if capture failed.
        """
        if self.using_screen:
            image = self.get_screen(0, 0, self.screen_width, self.screen_height)
            if image is None:
                return None
            # TODO delete this line when COLOR_RGB2BGR is removed from get_screen()
            try:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            except cv2.error as e:
                self._warn_capture_failure(f"cv2.cvtColor (BGR2RGB) failed: {e}")
                return None
            return image
        else:
            if self._screen_image is None:
                return None

            return self._screen_image

    def _warn_capture_failure(self, msg: str):
        """ Log a screen-capture failure, throttled so we do not flood the log when
        an assist loop polls the screen many times per second.
        """
        self._capture_failure_count += 1
        now = time.time()
        if now - self._last_capture_warn_ts < self._capture_warn_interval:
            return
        self._last_capture_warn_ts = now
        full_msg = f"{msg} (suppressed {self._capture_failure_count - 1} similar warnings)"
        logger.warning(full_msg)
        try:
            self.ap_ckb('log', f"WARNING: {msg}")
        except Exception:
            # ap_ckb can be None or fail during very early init; never let logging crash callers.
            pass
        self._capture_failure_count = 0

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
        self.screen_left = 0
        self.screen_top = 0

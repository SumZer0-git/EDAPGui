from __future__ import annotations
import typing
import logging

import cv2
import win32gui
from numpy import array
import mss
from pyautogui import size
import json

from EDlogger import logger


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


class Screen:
    def __init__(self):
        self.mss = mss.mss()

        # Find ED window position to determine which monitor it is on
        ed_rect = self.get_elite_window_rect()
        if ed_rect is None:
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
                    self.screen_width = item['width']
                    self.screen_height = item['height']
                    break
                else:
                    if item['left'] == ed_rect[0] and item['top'] == ed_rect[1]:
                        # Get information of monitor 2
                        self.monitor_number = mon_num
                        self.mon = self.mss.monitors[self.monitor_number]
                        logger.debug(f'Elite Dangerous is on monitor {mon_num}.')
                        self.screen_width = item['width']
                        self.screen_height = item['height']

            # Next monitor
            mon_num = mon_num + 1

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
            'Calibrated': [-1.0, -1.0]
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
        if self.scales['Calibrated'][0] != -1.0:
            self.scaleX = self.scales['Calibrated'][0]            
        if self.scales['Calibrated'][1] != -1.0:
            self.scaleY = self.scales['Calibrated'][1]
        
        logger.debug('screen size: '+str(self.screen_width)+" "+str(self.screen_height))
        logger.debug('Scale X, Y: '+str(self.scaleX)+", "+str(self.scaleY))

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
        except  Exception as e:
            logger.warning("Screen.py read_config error :"+str(e))

        return s

    # reg defines a box as a percentage of screen width and height
    def get_screen_region(self, reg):      
        image = self.get_screen(int(reg[0]), int(reg[1]), int(reg[2]), int(reg[3]))
        return image
    
    def get_screen(self, x_left, y_top, x_right, y_bot):    #  if absolute need to scale??
        monitor = {
            "top": self.mon["top"] + y_top,
            "left": self.mon["left"] + x_left,
            "width": x_right - x_left,
            "height": y_bot - y_top,
            "mon": self.monitor_number,
        }
        image = array(self.mss.grab(monitor))
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image
        
       
   


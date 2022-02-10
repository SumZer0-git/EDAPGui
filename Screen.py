import cv2
from numpy import array, sum, where
from PIL import Image, ImageGrab
from pyautogui import size

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

class Screen:
    def __init__(self):
        self.screen_width, self.screen_height = size()

        
        # scale is to adjust template images size which were generated with 3440/1440 screen
        # the following works with 1920x1080,  2560x1080, 3440x1440
        # however the X scaling is off if using 1920x1200,  1920x1040, 2560x1440, so for those
        # screen resolution of that size this scaleX will need to be played with
        #  Turn on cv_view in the GUI so you can see the bounding box on the compass to play with scaleX
        #self.scaleX = self.screen_width  / 3440.0
        self.scaleY = self.screen_height / 1440.0
        self.scaleX = self.scaleY
        logger.debug('screen size: '+str(self.screen_width)+" "+str(self.screen_height))

    # reg defines a box as a percentage of screen width and height
    def get_screen_region(self, reg):
        image = array(ImageGrab.grab(bbox=(int(reg[0]), int(reg[1]), 
                                            int(reg[2]), int(reg[3]) )))
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image
    
    def get_screen(self, x_left, y_top, x_right, y_bot):    #  if absolute need to scale??
        image = array(ImageGrab.grab(bbox=(x_left, y_top, x_right, y_bot)))
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image
        
       
   


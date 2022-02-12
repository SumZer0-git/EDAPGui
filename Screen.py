import cv2
from numpy import array, sum, where
from PIL import Image, ImageGrab
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

class Screen:
    def __init__(self):
        self.screen_width, self.screen_height = size()

        # Add new screen resolutions here with tested scale factors
        # this table will be default, overwriten when loading config-resolution.json file
        self.scales = {  #scaleX, scaleY
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
        }
 
        # used this to write the self.scales table to the json file
        # self.write_config(self.scales)
        
        ss = self.read_config()

        # if we read it then point to it, otherwise use the default table above
        if ss is not None:
            self.scales = ss
            logger.debug("read json:"+str(ss))
            
        
        # scale is to adjust template images size which were generated with 3440/1440 screen
        # to determine correct scale for a resolution, with the correct screen and ED resolution
        # 1. Add your screen resolution to the table above with a guess at the scale X, Y values
        # 2. Run EDAPGui
        # 3. Enable CV View under the File Menu
        # 4. In ED select a target system from Navigation
        # 5. Line up to target
        # 6. Select 'Home' key or Enable FSD Assist
        # 7 View the graphical image, the bounding box around the Compass must be the compass size
        #   if it is smaller or larger, you need to adjust the scale factor
        # 7a. Also the text in the graphic will tell you % match.  For the Compass we want it to be
        #     > 0.80 for matching, adjust scales to get close to .9.   Also look at the target window
        #     that too should have a match > 0.55  

        scale_key = str(self.screen_width)+"x"+str(self.screen_height)
        self.scaleX = self.scales[scale_key][0]
        self.scaleY = self.scales[scale_key][1]
        # if we don't have a definition for the resolution then use calculation
        if self.scaleX == None or self.scaleY == None:
            self.scaleX = self.screen_width  / 3440.0
            self.scaleY = self.screen_height / 1440.0
        
        logger.debug('screen size: '+str(self.screen_width)+" "+str(self.screen_height))
        logger.debug('Scale X, Y: '+str(self.scaleX)+", "+str(self.scaleY))


    def write_config(self, data, fileName='./config-resolution.json'):
        try:
            with open(fileName,"w") as fp:
                json.dump(data,fp, indent=4)
        except Exception as e:
            logger.warning("Screen.py write_config error:"+str(e))

    def read_config(self, fileName='./config-resolution.json'):
        s = None
        try:
            with open(fileName,"r") as fp:
                s = json.load(fp)
        except  Exception as e:
            logger.warning("Screen.py read_config error :"+str(e))

        return s

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
        
       
   


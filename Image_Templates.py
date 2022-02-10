import sys
from os.path import abspath, getmtime, isfile, join

import cv2

"""
File:Image_Templates.py    

Description:
  Class defines template images that will be used with opencv to match in screen regions

Author: sumzer0@yahoo.com
"""

class Image_Templates:
    def __init__(self, scaleX, scaleY):
   
        self.template = { 'elw'       : {'image': None, 'width': 1, 'height': 1},
                          'elw_sig'   : {'image': None, 'width': 1, 'height': 1}, 
                          'navpoint'  : {'image': None, 'width': 1, 'height': 1}, 
                          'compass'   : {'image': None, 'width': 1, 'height': 1},
                          'target'    : {'image': None, 'width': 1, 'height': 1},
                          'disengage' : {'image': None, 'width': 1, 'height': 1} 
                        }
 
        # load the templates and scale them.  Default templates assumed 3440x1440 screen resolution
        self.template['elw']       = self.load_template("templates/elw-template.png", scaleX, scaleY) 
        self.template['elw_sig']   = self.load_template("templates/elw-sig-template.png", scaleX, scaleY) 
        self.template['navpoint']  = self.load_template("templates/navpoint.png", scaleX, scaleY)
        self.template['compass']   = self.load_template("templates/compass.png", scaleX, scaleY)         
        self.template['target']    = self.load_template("templates/destination.png", scaleX, scaleY) 
        self.template['disengage'] = self.load_template("templates/sc-disengage.png", scaleX, scaleY) 
       

    # load the template image as grayscale (we do matching in gray only)
    #  Resize the image, as the templates are based on 3440x1440 resolution, so scale to current screen resolution  
    #  return image and size info    
    def load_template(self, file_name, scaleX, scaleY):
        template = cv2.imread(self.resource_path(file_name), cv2.IMREAD_GRAYSCALE)
        template = cv2.resize(template, (0, 0), fx=scaleX, fy=scaleY)
        width, height = template.shape[::-1]
        return {'image': template, 'width': width, 'height' : height}

    def resource_path(self,relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = abspath(".")

        return join(base_path, relative_path)

 
 
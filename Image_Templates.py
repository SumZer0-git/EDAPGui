import sys
from os.path import abspath, getmtime, isfile, join, dirname

import cv2
from EDlogger import logger

"""
File:Image_Templates.py    

Description:
  Class defines template images that will be used with opencv to match in screen regions

Author: sumzer0@yahoo.com
"""


class Image_Templates:
    def __init__(self, scale_x, scale_y):
        self.template = {'elw': {'image': None, 'width': 1, 'height': 1},
                         'elw_sig': {'image': None, 'width': 1, 'height': 1},
                         'target': {'image': None, 'width': 1, 'height': 1},
                         'disengage': {'image': None, 'width': 1, 'height': 1},
                         'missions': {'image': None, 'width': 1, 'height': 1},
                         'dest_sirius': {'image': None, 'width': 1, 'height': 1},
                         'sirius_atmos': {'image': None, 'width': 1, 'height': 1}
                         }

        # load the templates and scale them.  Default templates assumed 3440x1440 screen resolution
        self.reload_templates(scale_x, scale_y)

    def load_template(self, file_name: str, scale_x: float, scale_y: float) -> {cv2.typing.MatLike, int, int}:
        """ Load the template image in color. If we need grey scale for matching, we can apply that later as needed.
        Resize the image, as the templates are based on 3440x1440 resolution, so scale to current screen resolution
         return image and size info. """
        template = cv2.imread(self.resource_path(file_name), cv2.IMREAD_GRAYSCALE)
        template = cv2.resize(template, (0, 0), fx=scale_x, fy=scale_y)
        width, height = template.shape[::-1]
        return {'image': template, 'width': width, 'height': height}

    def reload_templates(self, scale_x, scale_y):
        """ Load the full set of image templates. """
        self.template['elw'] = self.load_template("templates/elw-template.png", scale_x, scale_y)
        self.template['elw_sig'] = self.load_template("templates/elw-sig-template.png", scale_x, scale_y)
        self.template['target'] = self.load_template("templates/destination.png", scale_x, scale_y)
        self.template['disengage'] = self.load_template("templates/sc-disengage.png", scale_x, scale_y)
        self.template['missions'] = self.load_template("templates/completed-missions.png", scale_x, scale_y)
        self.template['dest_sirius'] = self.load_template("templates/dest-sirius-atmos-HL.png", scale_x, scale_y)
        self.template['robigo_mines'] = self.load_template("templates/robigo-mines-selected.png", scale_x, scale_y)
        self.template['sirius_atmos'] = self.load_template("templates/sirius-atmos-selected.png", scale_x, scale_y)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        #try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        #    base_path = sys._MEIPASS
        #except Exception:
        #base_path = abspath(".")

        base_path = abspath(".")
        return join(base_path, relative_path)

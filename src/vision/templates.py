"""Template images used with OpenCV to match in screen regions."""

from os.path import join

import cv2

from core import paths


class ImageTemplates:
    def __init__(self, scale_x, scale_y, compass_scale: float):

        self.template = {
            "elw": {"image": None, "width": 1, "height": 1},
            "elw_sig": {"image": None, "width": 1, "height": 1},
            "navpoint": {"image": None, "width": 1, "height": 1},
            "navpoint-behind": {"image": None, "width": 1, "height": 1},
            "compass": {"image": None, "width": 1, "height": 1},
            "target": {"image": None, "width": 1, "height": 1},
            "target_occluded": {"image": None, "width": 1, "height": 1},
            "disengage": {"image": None, "width": 1, "height": 1},
            "missions": {"image": None, "width": 1, "height": 1},
            "dest_sirius": {"image": None, "width": 1, "height": 1},
            "sirius_atmos": {"image": None, "width": 1, "height": 1},
        }

        # load the templates and scale them.  Default templates assumed 3440x1440 screen resolution
        self.reload_templates(scale_x, scale_y, compass_scale)

    def load_template(self, file_name, scale_x, scale_y):
        """Load the template image in color. If we need grey scale for matching, we can apply that later as needed.
        Resize the image, as the templates are based on 3440x1440 resolution, so scale to current screen resolution
         return image and size info."""
        template = cv2.imread(self.resource_path(file_name), cv2.IMREAD_GRAYSCALE)
        # logger.debug("File:"+self.resource_path(file_name)+" template:"+str(template))
        template = cv2.resize(template, (0, 0), fx=scale_x, fy=scale_y)
        width, height = template.shape[::-1]
        return {"image": template, "width": width, "height": height}

    def reload_templates(self, scale_x, scale_y, compass_scale: float):
        """Load the full set of image templates."""
        self.template["elw"] = self.load_template("assets/templates/elw-template.png", scale_x, scale_y)
        self.template["elw_sig"] = self.load_template("assets/templates/elw-sig-template.png", scale_x, scale_y)
        self.template["navpoint"] = self.load_template("assets/templates/navpoint.png", compass_scale, compass_scale)
        self.template["navpoint-behind"] = self.load_template(
            "assets/templates/navpoint-behind.png", compass_scale, compass_scale
        )
        self.template["compass"] = self.load_template("assets/templates/compass.png", compass_scale, compass_scale)
        self.template["target"] = self.load_template("assets/templates/destination.png", scale_x, scale_y)
        self.template["target_occluded"] = self.load_template("assets/templates/target_occluded.png", scale_x, scale_y)
        self.template["disengage"] = self.load_template("assets/templates/sc-disengage.png", scale_x, scale_y)
        self.template["missions"] = self.load_template("assets/templates/completed-missions.png", scale_x, scale_y)
        self.template["dest_sirius"] = self.load_template("assets/templates/dest-sirius-atmos-HL.png", scale_x, scale_y)
        self.template["robigo_mines"] = self.load_template(
            "assets/templates/robigo-mines-selected.png", scale_x, scale_y
        )
        self.template["sirius_atmos"] = self.load_template(
            "assets/templates/sirius-atmos-selected.png", scale_x, scale_y
        )

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        # try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        #    base_path = sys._MEIPASS
        # except Exception:
        # base_path = abspath(".")

        base_path = paths.ROOT
        return join(base_path, relative_path)

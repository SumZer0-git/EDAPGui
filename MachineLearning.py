from __future__ import annotations

import enum
from dataclasses import dataclass
import cv2
from ultralytics import YOLO
from Screen_Regions import Quad

"""
File:Machine_Learning.py

Description:
  Class for Machine Learning using Yolo26.
  Ref: https://docs.ultralytics.com/

Author: Stumpii
"""


@dataclass
class MachLearnMatch:
    """ A machine learning match. """
    class_name: str  # i.e. 'compass'
    match_pct: float  # i.e. 0.0 - 1.0
    bounding_quad: Quad  # The bounding box


class ModelType(enum.Enum):
    Compass = 0
    Target = 1


class MachLearn:
    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb

        self.compass_ml_model = YOLO("Yolo26/compass-model/weights/best.pt")
        self.target_ml_model = YOLO("Yolo26/target-model/weights/best.pt")

    def model_predict(self, model: ModelType, image, class_name: str) -> list[MachLearnMatch] | None:
        """ Performs a prediction of an image using the relevant model and returns the results.
        @param model: Model type (i.e. Compass or Target)
        @param image: The image to check.
        @param class_name: The class name to filter by i.e.
         for Compass Model: 'compass', 'navpoint and 'navpoint-behind'.
         for Target Model: 'target', 'target-occluded'.
        @return: A list of learning matches.
        """
        results = None
        matches: list[MachLearnMatch] = []
        # Do prediction with ML
        if model is ModelType.Compass:
            results = self.compass_ml_model.predict(image, verbose=False)  # Predict on an image
        elif model is model.Target:
            results = self.target_ml_model.predict(image, verbose=False)  # Predict on an image

        if results and len(results) == 1:
            r = results[0]
            if len(r.boxes) > 0:
                for b in r.boxes:
                    clsid = int(b.cls.item())
                    name = r.names[clsid]  # Class name
                    # Is name wanted
                    if class_name == '' or name == class_name:
                        confidence = b.conf.item()  # Confidence %
                        rect_tmp = b.xyxy.tolist()  # Match as a rect
                        rect_tmp = rect_tmp[0]
                        res_quad = Quad.from_rect(rect_tmp)

                        # Add item
                        match = MachLearnMatch(class_name=name, match_pct=confidence, bounding_quad=res_quad)
                        matches.append(match)
                return matches
            else:
                return None


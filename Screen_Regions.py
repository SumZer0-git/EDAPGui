import json
import os
from copy import copy
from dataclasses import dataclass
from typing import TypedDict

import numpy as np
from numpy import array, sum
import cv2
from datetime import datetime

"""
File:Screen_Regions.py    

Description:
  Class to rectangle areas of the screen to capture along with filters to apply. Includes functions to
  match a image template to the region using opencv 

Author: sumzer0@yahoo.com
"""


class Point:
    """Creates a point on a coordinate plane with values x and y."""

    def __init__(self, x, y):
        """Defines x and y variables"""
        self.x: float = x
        self.y: float = y

    def __str__(self):
        return "Point(%s, %s)" % (self.x, self.y)

    def get_x(self) -> float:
        return self.x

    def get_y(self) -> float:
        return self.y

    def to_list(self) -> [float, float]:
        return [self.x, self.y]

    @classmethod
    def from_xy(cls, xy_tuple: (float, float)):
        """ From (x, y) """
        return cls(xy_tuple[0], xy_tuple[1])

    @classmethod
    def from_list(cls, xy_list: [float, float]):
        """ From (x, y) """
        return cls(xy_list[0], xy_list[1])


class Quad:
    """ Represents a quadrilateral (a four-sided polygon that has four edges and four vertices).
    It can be classified into various types, such as squares, rectangles, trapezoids, and rhombuses.
    """

    def __init__(self, p1: Point = None, p2: Point = None, p3: Point = None, p4: Point = None):
        self.pt1: Point = p1
        self.pt2: Point = p2
        self.pt3: Point = p3
        self.pt4: Point = p4

    @classmethod
    def from_list(cls, pt_list: [[float, float], [float, float], [float, float], [float, float]]):
        """ Creates a quad from a list of points as
        [[left, top], [right, top], [right, bottom], [left, bottom]]."""
        return cls(Point.from_list(pt_list[0]), Point.from_list(pt_list[1]),
                   Point.from_list(pt_list[2]), Point.from_list(pt_list[3]))

    @classmethod
    def from_rect(cls, edge_list: [float, float, float, float]):
        """ Creates a quad from a list of edges i.e. [left, top, right, bottom] """
        return cls(Point(edge_list[0], edge_list[1]), Point(edge_list[2], edge_list[1]),
                   Point(edge_list[2], edge_list[3]), Point(edge_list[0], edge_list[3]))

    def to_rect_list(self, round_dp: int = -1) -> [float, float, float, float]:
        """ Returns the bounds of the quadrilateral as a list of values [left, top, right, bottom].
        @param: round_dp: If >=0, the number of decimal places to round numbers to, otherwise no rounding.
        """
        if round_dp < 0:
            return [self.left, self.top, self.right, self.bottom]
        else:
            return [round(self.left, round_dp), round(self.top, round_dp),
                    round(self.right, round_dp), round(self.bottom, round_dp)]

    def to_list(self) -> [[float, float], [float, float], [float, float], [float, float]]:
        """ Returns the list of points of the quadrilateral as
        [[left, top], [right, top], [right, bottom], [left, bottom]]."""
        return [self.pt1.to_list(), self.pt2.to_list(), self.pt3.to_list(), self.pt4.to_list()]

    @property
    def top_left(self) -> Point:
        """ Returns the top left point. """
        pt = self.pt1
        if self.pt2.x < pt.x and self.pt2.y < pt.y:
            pt = self.pt2
        if self.pt3.x < pt.x and self.pt3.y < pt.y:
            pt = self.pt3
        if self.pt4.x < pt.x and self.pt4.y < pt.y:
            pt = self.pt4
        return copy(pt)

    @property
    def bottom_right(self) -> Point:
        """ Returns the bottom right point. """
        pt = self.pt1
        if self.pt2.x > pt.x and self.pt2.y > pt.y:
            pt = self.pt2
        if self.pt3.x > pt.x and self.pt3.y > pt.y:
            pt = self.pt3
        if self.pt4.x > pt.x and self.pt4.y > pt.y:
            pt = self.pt4
        return copy(pt)

    @property
    def left(self) -> float:
        """ Returns the value of the left most point. """
        return min(self.pt1.x, self.pt2.x, self.pt3.x, self.pt4.x)

    @property
    def top(self) -> float:
        """ Returns the value of the top most point. """
        return min(self.pt1.y, self.pt2.y, self.pt3.y, self.pt4.y)

    @property
    def right(self) -> float:
        """ Returns the value of the right most point. """
        return max(self.pt1.x, self.pt2.x, self.pt3.x, self.pt4.x)

    @property
    def bottom(self) -> float:
        """ Returns the value of the bottom most point. """
        return max(self.pt1.y, self.pt2.y, self.pt3.y, self.pt4.y)

    @property
    def width(self):
        """Returns the maximum width."""
        return self.right - self.left

    @property
    def height(self):
        """Returns the maximum height."""
        return self.bottom - self.top

    @property
    def bounds(self) -> (Point, Point):
        """ Returns the bounds of the quadrilateral as a rectangle defined by two points,
        the top-left and bottom-right."""
        return Point(self.left, self.top), Point(self.right, self.bottom)

    @property
    def center(self) -> Point:
        cx = (self.pt1.x + self.pt2.x + self.pt3.x + self.pt4.x) / 4
        cy = (self.pt1.y + self.pt2.y + self.pt3.y + self.pt4.y) / 4
        return Point(cx, cy)

    def scale(self, fx: float, fy: float):
        """ Scales the quad from the center.
        @param fy: Scaling in the Y direction.
        @param fx: Scaling in the X direction.
        """
        center = self.center
        self.pt1 = self._scale_point(self.pt1, center, fx, fy)
        self.pt2 = self._scale_point(self.pt2, center, fx, fy)
        self.pt3 = self._scale_point(self.pt3, center, fx, fy)
        self.pt4 = self._scale_point(self.pt4, center, fx, fy)

    def inflate(self, x: float, y: float):
        """ Scales the quad from the center.
        @param y: Scaling in the Y direction.
        @param x: Scaling in the X direction.
        """
        center = self.center
        self.pt1 = self._inflate_point(self.pt1, center, x, y)
        self.pt2 = self._inflate_point(self.pt2, center, x, y)
        self.pt3 = self._inflate_point(self.pt3, center, x, y)
        self.pt4 = self._inflate_point(self.pt4, center, x, y)

    def crop(self, quad):
        """ Crops the quad as region specified by the % (0.0-1.0) inputs.
        NOTE: This assumes that the quad is a rectangle or square. Won't work with other shapes!
        Example: An input of [0.0, 0.0, 1.0, 1.0] returns the quad unchanged.
        Example: An input of [0.0, 0.0, 0.25, 0.25] returns the top left quarter of the quad.
        @param quad: A quad.
        """
        new_l = (quad.left * self.width) + self.left
        new_t = (quad.top * self.height) + self.top
        new_r = (quad.right * self.width) + self.left
        new_b = (quad.bottom * self.height) + self.top

        self.pt1 = Point(new_l, new_t)
        self.pt2 = Point(new_r, new_t)
        self.pt3 = Point(new_r, new_b)
        self.pt4 = Point(new_l, new_b)

    def scale_from_origin(self, fx: float, fy: float):
        """ Scales the quad from the origin (0,0).
        @param fy: Scaling in the Y direction.
        @param fx: Scaling in the X direction.
        """
        origin = Point(0, 0)
        self.pt1 = self._scale_point(self.pt1, origin, fx, fy)
        self.pt2 = self._scale_point(self.pt2, origin, fx, fy)
        self.pt3 = self._scale_point(self.pt3, origin, fx, fy)
        self.pt4 = self._scale_point(self.pt4, origin, fx, fy)

    def offset(self, dx: float, dy: float):
        """ Offsets (moves) the quad by the given amount.
        @param dx: The amount to move in the x direction.
        @param dy: The amount to move in the y direction.
        """
        self.pt1 = self._offset_point(self.pt1, dx, dy)
        self.pt2 = self._offset_point(self.pt2, dx, dy)
        self.pt3 = self._offset_point(self.pt3, dx, dy)
        self.pt4 = self._offset_point(self.pt4, dx, dy)

    @staticmethod
    def _scale_point(pt: Point, center: Point, fx: float, fy: float) -> Point:
        return Point(
            center.x + (pt.x - center.x) * fx,
            center.y + (pt.y - center.y) * fy
        )

    @staticmethod
    def _inflate_point(pt: Point, center: Point, x: float, y: float) -> Point:
        x1 = x
        y1 = y
        if pt.x < center.x:
            x1 = -x
        if pt.y < center.y:
            y1 = -y
        return Point(pt.x + x1, pt.y + y1)

    @staticmethod
    def _offset_point(pt: Point, dx: float, dy: float) -> Point:
        """ Offsets the point.
        Using this instead of calling offset on the point directly allows shallow copy of the quad."""
        return Point(pt.x + dx, pt.y + dy)

    def __str__(self):
        return (f"Quadrilateral:\n"
                f" pt1: ({self.pt1.x}, {self.pt1.y})\n"
                f" pt2: ({self.pt2.x}, {self.pt2.y})\n"
                f" pt3: ({self.pt3.x}, {self.pt3.y})\n"
                f" pt4: ({self.pt4.x}, {self.pt4.y})")


def load_calibrated_regions(prefix: str, reg: dict):
    """ Read the custom region sizes from the calibration json file.
    @param prefix: The dictionary key prefix (i.e. 'EDStationServicesInShip')
    @param reg: Dictionary of regions which is modified.
    """
    if not prefix or prefix == '' or not reg:
        return

    calibration_file = 'configs/ocr_calibration.json'
    if os.path.exists(calibration_file):
        with open(calibration_file, 'r') as f:
            calibrated_regions = json.load(f)

        # Go through all regions in this class
        for key1, value1 in reg.items():
            calibrated_key = f"{prefix}.{key1}"
            if calibrated_key in calibrated_regions:
                # Use region details from the calibration file.
                reg[key1]['rect'] = calibrated_regions[calibrated_key]['rect']

                # Check if this region has any sub-regions
                for key2, value2 in reg.items():
                    calibrated_sub_key = f"{prefix}.{key1}.subregion.{key2}"
                    if calibrated_sub_key in calibrated_regions:
                        # Scale the regions based on the sub-region.
                        x = Quad.from_rect(reg[key1]['rect'])
                        sub_reg = Quad.from_rect(calibrated_regions[calibrated_sub_key]['rect'])
                        x.crop(sub_reg)
                        reg[key2]['rect'] = x.to_rect_list()


def load_calibrated_regions_quad(prefix: str, reg_quad: dict[str, Quad]):
    """ Read the custom region sizes from the calibration json file.
    @param reg_quad: Dictionary of regions which is modified.
    @param prefix: The dictionary key prefix (i.e. 'EDStationServicesInShip')
    """
    if not prefix or prefix == '' or not reg_quad:
        return

    calibration_file = 'configs/ocr_calibration.json'
    if os.path.exists(calibration_file):
        with open(calibration_file, 'r') as f:
            calibrated_regions = json.load(f)

        # Go through all regions in this class
        for key1, value1 in reg_quad.items():
            calibrated_key = f"{prefix}.{key1}"
            if calibrated_key in calibrated_regions:
                # Use region details from the calibration file.
                reg_quad[key1] = Quad.from_rect(calibrated_regions[calibrated_key]['rect'])

                # Check if this region has any sub-regions
                for key2, value2 in reg_quad.items():
                    calibrated_sub_key = f"{prefix}.{key1}.subregion.{key2}"
                    if calibrated_sub_key in calibrated_regions:
                        # Get the 'parent' region.
                        x = copy(reg_quad[key1])
                        # Scale the region based on the sub-region.
                        sub_reg = Quad.from_rect(calibrated_regions[calibrated_sub_key]['rect'])
                        x.crop(sub_reg)
                        reg_quad[key2] = x


class SubRegion(TypedDict):
    """ """
    rect: list[float]
    text: str


class Objects(TypedDict):
    """ """
    width: float
    height: float
    text: str


class MyRegion(TypedDict):
    """ """
    rect: list[float]
    text: str
    readonly: bool
    regions: dict[str, SubRegion]
    objects: dict[str, Objects]


def load_default_calib_data() -> dict[str, MyRegion]:
    default_calib_data = dict[str, MyRegion]
    calibration_file = 'configs/ocr_calibration.json'

    default_regions = dict[str, MyRegion]
    default_regions = {
        "Screen_Regions.full_panel": {"rect": [0.0, 0.0, 1.0, 1.0],
                                      "text": "1. Go to cockpit view.\n2. Select the optimum screen size using the predefined subregions.\nIt is likely that this value can be changed so that the default\nsubregions do not need to be changed.",
                                      "readonly": False},
        "Screen_Regions.full_panel.subregion.radar": {"rect": [0.411, 0.685, 0.588, 0.847],
                                                      "text": "The area around the radar.",
                                                      "readonly": False},
        "Screen_Regions.full_panel.subregion.compass": {"rect": [0.33, 0.6, 0.46, 1.0],
                                                        "text": "The area around the compass. Needs to be big enough for all ships while flying.",
                                                        "readonly": False},
        "Screen_Regions.full_panel.subregion.target": {"rect": [0.2, 0.15, 0.8, 0.75],
                                                       "text": "The area around the target. Needs to be big enough for all ships while flying.",
                                                       "readonly": False},
        "Screen_Regions.full_panel.subregion.sun": {"rect": [0.30, 0.30, 0.70, 0.68],
                                                    "text": "TBD",
                                                    "readonly": False},
        "Screen_Regions.full_panel.subregion.disengage": {"rect": [0.42, 0.65, 0.60, 0.80],
                                                          "text": "The area above the radar where the disengage message appears.",
                                                          "readonly": False},
        "Screen_Regions.full_panel.subregion.sco": {"rect": [0.42, 0.65, 0.60, 0.80],
                                                    "text": "The area above the radar where the supercruise overdrive active message appears.",
                                                    "readonly": False},
        "Screen_Regions.full_panel.subregion.fss": {"rect": [0.5045, 0.7545, 0.532, 0.7955],
                                                    "text": "Should be replaced with the FSS screen regions.",
                                                    "readonly": False},
        "Screen_Regions.full_panel.subregion.mission_dest": {"rect": [0.46, 0.38, 0.65, 0.86],
                                                             "text": "TBD.",
                                                             "readonly": False},
        "Screen_Regions.full_panel.subregion.missions": {"rect": [0.50, 0.78, 0.65, 0.85],
                                                         "text": "TBD.",
                                                         "readonly": False},

        "EDCodex.full_panel": {"rect": [0.0589, 0.0983, 0.9406, 0.8617],
                               "text": "1. Open the Codex from right hand cockpit panel.\n2. Size the rectangle from the top left corner of the codex 'book' to the end \nof the line above the exit button at the bottom right.",
                               "readonly": False},

        "EDInternalStatusPanel.panel_bounds1": {
            "rect": [0.1197, 0.2733, 0.6937, 0.7125],
            "text": "1. Open Internal Status Panel (right hand panel).\n2. Size the rectangle from the top left corner of the nav panel to the bottom right corner.",
            "readonly": False},
        "EDInternalStatusPanel.panel_bounds2": {
            "rect": [0.1541, 0.2408, 0.6781, 0.8],
            "text": "1. Open Internal Status Panel (right hand panel).\n2. Size the rectangle from the bottom left corner of the nav panel to the top right corner.",
            "readonly": False},
        # "EDInternalStatusPanel.tab_bar": {"rect": [0.35, 0.2, 0.85, 0.26]},
        # "EDInternalStatusPanel.inventory_list": {"rect": [0.2, 0.3, 0.8, 0.9]},
        # "EDInternalStatusPanel.size.inventory_item": {"width": 100, "height": 20},
        # "EDInternalStatusPanel.size.nav_pnl_tab": {"width": 100, "height": 20},

        "EDNavigationPanel.panel_bounds1": {
            "rect": [0.1197, 0.2733, 0.6937, 0.7125],
            "text": "1. Open Navigation Panel.\n2. Size the rectangle from the top left corner of the nav panel to the bottom right corner.",
            "readonly": False},
        "EDNavigationPanel.panel_bounds2": {
            "rect": [0.1541, 0.2408, 0.6781, 0.8],
            "text": "1. Open Navigation Panel.\n2. Size the rectangle from the bottom left corner of the nav panel to the top right corner.",
            "readonly": False},
        # "EDNavigationPanel.tab_bar": {"rect": [0.0, 0.2, 0.7, 0.35]},
        # "EDNavigationPanel.size.nav_pnl_tab": {"width": 260, "height": 35},
        # "EDNavigationPanel.size.nav_pnl_location": {"width": 500, "height": 35},

        "EDGalaxyMap.full_panel": {
            "rect": [0.0, 0.0, 0.0, 0.0],
            "text": "This is calculated automatically from the Codex screen values. Do not change.",
            "readonly": True},
        "EDGalaxyMap.full_panel.subregion.cartographics": {
            "rect": [0.0, 0.0, 0.15, 0.075],
            "text": "Contains the CARTOGRAPHICS text.",
            "readonly": False},

        "EDSystemMap.full_panel": {
            "rect": [0.0, 0.0, 0.0, 0.0],
            "text": "This is calculated automatically from the Codex screen values. Do not change.",
            "readonly": True},
        "EDSystemMap.full_panel.subregion.cartographics": {
            "rect": [0.0, 0.0, 0.15, 0.075],
            "text": "Contains the CARTOGRAPHICS text.",
            "readonly": False},

        "EDStationServicesInShip.station_services": {
            "rect": [0.0809, 0.1136, 0.9186, 0.8464],
            "text": "1. Open Station Service.\n2. Size the rectangle from the top left of the left panel box to the bottom right of the right panel box.",
            "readonly": False},
        "EDStationServicesInShip.commodities_market": {
            "rect": [0.0479, 0.0983, 0.9516, 0.8617],
            "text": "This is calculated automatically from the Codex screen values. Do not change.",
            "readonly": True},
        "EDStationServicesInShip.commodities_market.subregion.connected_to": {
            "rect": [0.0, 0.0, 0.25, 0.1],
            "text": "The connected to text.",
            "readonly": False},
        "EDStationServicesInShip.commodities_market.subregion.title": {
            "rect": [0.0, 0.0, 0.25, 0.1],
            "text": "The title (station name).",
            "readonly": False},
        "EDStationServicesInShip.commodities_market.subregion.commodity_column": {
            "rect": [0.1575, 0.205, 0.4075, 1.0],
            "text": "The commodity column.",
            "readonly": False},
        "EDStationServicesInShip.commodities_market.subregion.buy_qty_box": {
            "rect": [0.275, 0.332, 0.49, 0.402],
            "text": "The buy quantity box.",
            "readonly": False},
        "EDStationServicesInShip.commodities_market.subregion.sell_qty_box": {
            "rect": [0.275, 0.322, 0.49, 0.390],
            "text": "The sell quantity box.",
            "readonly": False},
        "EDStationServicesInShip.commodities_market.subregion.commodity_name": {
            "rect": [0.1575, 0.252, 0.4075, 0.290],
            "text": "The first commodity name cell.",
            "readonly": False},

        "EDFSS.full_panel": {
            "rect": [0.0, 0.0, 0.0, 0.0],
            "text": "This is calculated automatically from the Codex screen values. Do not change.",
            "readonly": True},
        "EDFSS.full_panel.subregion.analysis": {
            "rect": [0.0, 0.0, 0.15, 0.075],
            "text": "Select the analysis display.",
            "readonly": False},
        # "EDStationServicesInShip.carrier_admin_header": {"rect": [0.4, 0.1, 0.6, 0.2]},
        # "EDStationServicesInShip.commodities_list": {"rect": [0.2, 0.2, 0.8, 0.9]},
        # "EDStationServicesInShip.commodity_quantity": {"rect": [0.4, 0.5, 0.6, 0.6]},
        # "EDStationServicesInShip.size.commodity_item": {"width": 100, "height": 15},
        # "EDStationServicesInShip.mission_board_header": {"rect": [0.4, 0.1, 0.6, 0.2]},
        # "EDStationServicesInShip.missions_list": {"rect": [0.06, 0.25, 0.48, 0.8]},
        # "EDStationServicesInShip.mission_loaded": {"rect": [0.06, 0.25, 0.48, 0.35]},
        # "EDStationServicesInShip.size.mission_item": {"width": 100, "height": 15},
    }

    if not os.path.exists(calibration_file):
        # Create the file with default values if it doesn't exist
        with open(calibration_file, 'w') as f:
            json.dump(default_regions, f, indent=4)
        default_calib_data = default_regions
    else:
        with open(calibration_file, 'r') as f:
            default_calib_data = json.load(f)

        # Check for missing keys and add them
        updated = False
        for key, value in default_regions.items():
            if key not in default_calib_data:
                default_calib_data[key] = value
                updated = True

        # If we updated the data, save it back to the file
        if updated:
            with open(calibration_file, 'w') as f:
                json.dump(default_calib_data, f, indent=4)

    return default_calib_data


class Screen_Regions:
    def __init__(self, screen, templ):
        self.screen = screen
        self.templates = templ

        # Define the thresholds for template matching to be consistent throughout the program
        self.compass_match_thresh = 0.50
        self.navpoint_match_thresh = 0.8
        self.target_thresh = 0.50
        self.target_occluded_thresh = 0.55
        self.sun_threshold = 125
        self.disengage_thresh = 0.35

        # array is in HSV order which represents color ranges for filtering
        self.orange_color_range = [array([0, 130, 123]), array([25, 235, 220])]
        self.orange_2_color_range = [array([16, 165, 220]), array([98, 255, 255])]
        self.target_occluded_range = [array([16, 31, 85]), array([26, 160, 255])]
        self.blue_color_range = [array([0, 28, 170]), array([180, 100, 255])]
        self.blue_sco_color_range = [array([10, 0, 0]), array([100, 150, 255])]
        self.fss_color_range = [array([95, 210, 70]), array([105, 255, 120])]

        self.reg = {}
        # regions with associated filter and color ranges
        # The rect is [L, T, R, B] top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg['compass'] = {'rect': [0.33, 0.6, 0.46, 1.0], 'width': 1, 'height': 1, 'filterCB': self.equalize,
                               'filter': None}
        self.reg['target'] = {'rect': [0.2, 0.15, 0.8, 0.75], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color,
                              'filter': self.orange_2_color_range}  # also called destination
        self.reg['sun'] = {'rect': [0.30, 0.30, 0.70, 0.68], 'width': 1, 'height': 1, 'filterCB': self.filter_sun,
                           'filter': None}
        self.reg['disengage'] = {'rect': [0.42, 0.65, 0.60, 0.80], 'width': 1, 'height': 1,
                                 'filterCB': self.filter_by_color, 'filter': self.blue_sco_color_range}
        self.reg['sco'] = {'rect': [0.42, 0.65, 0.60, 0.80], 'width': 1, 'height': 1, 'filterCB': self.filter_by_color,
                           'filter': self.blue_sco_color_range}
        self.reg['fss'] = {'rect': [0.5045, 0.7545, 0.532, 0.7955], 'width': 1, 'height': 1, 'filterCB': self.equalize,
                           'filter': None}
        self.reg['mission_dest'] = {'rect': [0.46, 0.38, 0.65, 0.86], 'width': 1, 'height': 1,
                                    'filterCB': self.equalize, 'filter': None}
        self.reg['missions'] = {'rect': [0.50, 0.78, 0.65, 0.85], 'width': 1, 'height': 1, 'filterCB': self.equalize,
                                'filter': None}
        self.reg['nav_panel'] = {'rect': [0.25, 0.36, 0.60, 0.85], 'width': 1, 'height': 1, 'filterCB': self.equalize,
                                 'filter': None}

        # The rect is top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg_pct = {'full_panel': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'radar': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'compass': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'target': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'sun': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'disengage': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'sco': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'fss': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'mission_dest': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'missions': {'rect': [0.0, 0.0, 0.0, 0.0]},
                        'nav_panel': {'rect': [0.25, 0.36, 0.60, 0.85]},  # For Robigo
                        }

        # Load custom regions from file
        load_calibrated_regions('Screen_Regions', self.reg_pct)

        # convert rect from percent of screen into pixel location, calc the width/height of the area
        for i, key in enumerate(self.reg):
            # Take the percentage values
            xx = self.reg_pct[key]['rect']
            # Convert to pixels
            self.reg[key]['rect'] = [int(xx[0] * screen.screen_width), int(xx[1] * screen.screen_height),
                                     int(xx[2] * screen.screen_width), int(xx[3] * screen.screen_height)]
            self.reg[key]['width'] = self.reg[key]['rect'][2] - self.reg[key]['rect'][0]
            self.reg[key]['height'] = self.reg[key]['rect'][3] - self.reg[key]['rect'][1]

        pass

    def capture_region(self, screen, region_name, inv_col=True):
        """ Just grab the screen based on the region name/rect.
        Returns an unfiltered image. """
        return screen.get_screen_region(self.reg[region_name]['rect'], inv_col)

    def capture_region_percent(self, screen, region_name):
        """ Just grab the screen based on the region name in %.
        Returns an unfiltered image. """
        return screen.get_screen_rect_pct(self.reg_pct[region_name]['rect'])

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
        img_region = self.capture_region_filtered(self.screen, region_name,
                                                  inv_col)  # which would call, reg.capture_region('compass') and apply defined filter
        img_templ = self.templates.template[templ_name]['image']

        # now = datetime.now()
        # x = now.strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]  # Date time with mS.
        # cv2.imwrite(f'test/match/{templ_name} {x} region.png', img_region)
        # cv2.imwrite(f'test/match/{templ_name} {x} templ.png', img_templ)

        match = cv2.matchTemplate(img_region, img_templ, cv2.TM_CCOEFF_NORMED)
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
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
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
        equalized = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)  #hhhmm, equalize() already converts to gray
        equalized = cv2.cvtColor(equalized, cv2.COLOR_BGR2HSV)
        filtered = cv2.inRange(equalized, array([0, 0, 215]), array([0, 0, 255]))  #only high value

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

        result = int((wht / (wht + blk)) * 100)

        return result

from __future__ import annotations

import logging
import json
import os
from time import sleep
import cv2

from EDAP_data import GuiFocusExternalPanel
from EDKeys import EDKeys
from EDlogger import logger
from OCR import OCR
from Screen import Screen
from Screen_Regions import size_scale_for_station
from StatusParser import StatusParser

"""
File:navPanel.py    

Description:
  TBD 

Author: Stumpii
"""


class EDNavigationPanel:
    """ The Navigation (Left hand) Ship Status Panel. """
    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.locale = self.ap.locale
        self.status_parser = StatusParser()

        self.navigation_tab_text = self.locale["NAV_PNL_TAB_NAVIGATION"]
        self.transactions_tab_text = self.locale["NAV_PNL_TAB_TRANSACTIONS"]
        self.contacts_tab_text = self.locale["NAV_PNL_TAB_CONTACTS"]
        self.target_tab_text = self.locale["NAV_PNL_TAB_TARGET"]
        self.nav_pnl_coords = None  # [top left, top right, bottom left, bottom right]

        # The rect is [L, T, R, B], top left x, y, and bottom right x, y in fraction of screen resolution
        # Nav Panel region covers the entire navigation panel.
        self.reg = {'nav_panel': {'rect': [0.11, 0.21, 0.70, 0.86]},
                    'tab_bar': {'rect': [0.0, 0.2, 0.7, 0.35]},
                    'nav_list': {'rect': [0.2218, 0.3, 0.8, 1.0]}}

        self.load_calibrated_regions()

        self.nav_pnl_tab_width = 260  # Nav panel tab width in pixels at 1920x1080
        self.nav_pnl_tab_height = 35  # Nav panel tab height in pixels at 1920x1080
        self.nav_pnl_location_width = 500  # Nav panel location width in pixels at 1920x1080
        self.nav_pnl_location_height = 35  # Nav panel location height in pixels at 1920x1080

        self.deskew_angle = -1.0  # Default to -1 degrees counter-clockwise
        self.load_calibrated_sizes()
        self.load_calibrated_values()

    def load_calibrated_values(self):
        calibration_file = 'configs/ocr_calibration.json'
        if os.path.exists(calibration_file):
            with open(calibration_file, 'r') as f:
                calibrated_data = json.load(f)

            if "EDNavigationPanel.deskew_angle" in calibrated_data:
                self.deskew_angle = calibrated_data["EDNavigationPanel.deskew_angle"]

    def show_nav_panel(self):
        """ Shows the Navigation (Left) Panel.
        Returns True if successful, else False.
        """
        logger.debug("show_nav_panel: entered")

        # Is nav panel active?
        active, active_tab_name = self.is_nav_panel_active()
        if active:
            return active, active_tab_name
        else:
            print("Open Nav Panel")
            logger.debug("show_nav_panel: Open Nav Panel")
            self.ap.ship_control.goto_cockpit_view()

            self.keys.send("HeadLookReset")
            self.keys.send('UIFocus', state=1)
            self.keys.send('UI_Left')
            self.keys.send('UIFocus', state=0)
            sleep(0.5)

            # Check if it opened
            active, active_tab_name = self.is_nav_panel_active()
            if active:
                return active, active_tab_name
            else:
                return False, ""

    def is_nav_panel_active(self) -> (bool, str):
        """ Determine if the Nav Panel is open and if so, which tab is active.
            Returns True if active, False if not and also the string of the tab name.
        """
        logger.debug("is_nav_panel_active: entered")

        # Check if nav panel is open
        if not self.status_parser.wait_for_gui_focus(GuiFocusExternalPanel, 3):
            logger.debug("is_nav_panel_active: nav panel not focused")
            return False, ""

        logger.debug("is_nav_panel_active: nav panel is focused")

        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(self.reg['tab_bar']['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('nav_panel_active', abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        # Try this 'n' times before giving up
        tab_text = ""
        for i in range(10):
            # Take screenshot of the panel
            image = self.ocr.capture_region_pct(self.reg['tab_bar'])

            # De-skew the image
            if self.deskew_angle != 0:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, self.deskew_angle, 1.0)
                image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

                # --- TEMPORARY DEBUG CODE ---
                if self.ap.debug_overlay:
                    if not os.path.exists('test/nav-panel'):
                        os.makedirs('test/nav-panel')
                    cv2.imwrite('test/nav-panel/deskewed_tab_bar.png', image)
                # --- END TEMPORARY DEBUG CODE ---

            # Determine the nav panel tab size at this resolution
            scl_row_w, scl_row_h = size_scale_for_station(self.nav_pnl_tab_width, self.nav_pnl_tab_height,
                                                          self.screen.screen_width, self.screen.screen_height)

            img_selected, ocr_data, ocr_textlist = self.ocr.get_highlighted_item_data(image, scl_row_w, scl_row_h)
            if img_selected is not None:
                logger.debug("is_nav_panel_active: image selected")
                logger.debug(f"is_nav_panel_active: OCR: {ocr_textlist}")

                # Overlay OCR result
                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_floating_text('nav_panel_text', f'{ocr_textlist}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
                    self.ap.overlay.overlay_paint()

                # Test OCR string
                if self.navigation_tab_text in str(ocr_textlist):
                    tab_text = self.navigation_tab_text
                    break
                if self.transactions_tab_text in str(ocr_textlist):
                    tab_text = self.transactions_tab_text
                    break
                if self.contacts_tab_text in str(ocr_textlist):
                    tab_text = self.contacts_tab_text
                    break
                if self.target_tab_text in str(ocr_textlist):
                    tab_text = self.target_tab_text
                    break
            else:
                logger.debug("is_nav_panel_active: no image selected")

            # Wait and retry
            sleep(1)

            # In case we are on a picture tab, cycle to the next tab
            self.keys.send('CycleNextPanel')

        # Clean up screen
        if self.ap.debug_overlay:
            sleep(2)
            self.ap.overlay.overlay_remove_rect('nav_panel_active')
            self.ap.overlay.overlay_remove_floating_text('nav_panel_text')
            self.ap.overlay.overlay_paint()

        # Return Tab text or nothing
        if tab_text != "":
            return True, tab_text
        else:
            return False, ""

    def show_navigation_tab(self) -> bool | None:
        """ Shows the NAVIGATION tab of the Nav Panel. Opens the Nav Panel if not already open.
        Returns True if successful, else False.
        """
        logger.debug("show_navigation_tab: entered")

        # Show nav panel
        active, active_tab_name = self.show_nav_panel()
        if active is None:
            return None
        if not active:
            print("Nav Panel could not be opened")
            return False
        elif active_tab_name == self.navigation_tab_text:
            # Do nothing
            return True
        elif active_tab_name == self.transactions_tab_text:
            self.keys.send('CyclePreviousPanel', repeat=1)
            return True
        elif active_tab_name == self.contacts_tab_text:
            self.keys.send('CyclePreviousPanel', repeat=2)
            return True
        elif active_tab_name == self.target_tab_text:
            self.keys.send('CycleNextPanel', repeat=1)
            return True

    def show_contacts_tab(self) -> bool | None:
        """ Shows the CONTACTS tab of the Nav Panel. Opens the Nav Panel if not already open.
        Returns True if successful, else False.
        """
        logger.debug("show_contacts_tab: entered")

        # Show nav panel
        active, active_tab_name = self.show_nav_panel()
        if active is None:
            return None
        if not active:
            print("Nav Panel could not be opened")
            return False
        elif active_tab_name == self.contacts_tab_text:
            # Do nothing
            return True
        elif active_tab_name == self.navigation_tab_text:
            self.keys.send('CycleNextPanel', repeat=2)
            return True
        elif active_tab_name == self.transactions_tab_text:
            self.keys.send('CycleNextPanel', repeat=1)
            return True
        elif active_tab_name == self.target_tab_text:
            self.keys.send('CyclePreviousPanel', repeat=1)
            return True

    def select_station_by_ocr(self, station_name) -> bool:
        """ Try to select a station from the navigation panel using OCR.
        """
        self.ap_ckb('log+vce', f"Selecting station {station_name} by OCR.")
        logger.debug(f"select_station_by_ocr: entered for station {station_name}")

        # Show nav panel
        res = self.show_navigation_tab()
        if res is None:
            return None
        if not res:
            print("Navigation Panel could not be opened")
            return False

        nav_list_region = self.reg.get('nav_list', {'rect': [0.2218, 0.3, 0.8, 1.0]})
        abs_rect = self.screen.screen_rect_to_abs(nav_list_region['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('nav_list', abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        # Determine the nav location row size at this resolution
        scl_row_w, scl_row_h = size_scale_for_station(self.nav_pnl_location_width, self.nav_pnl_location_height,
                                                      self.screen.screen_width, self.screen.screen_height)

        # Find station in the list
        station_found = False
        self.keys.send('UI_Down')
        sleep(0.2)
        self.keys.send('UI_Up', hold=3) # Go to top of list
        sleep(0.2)
        for _ in range(40): # Max 40 scrolls
            image = self.ocr.capture_region_pct(nav_list_region)
            img_selected, ocr_data, ocr_textlist = self.ocr.get_highlighted_item_data(image, scl_row_w, scl_row_h)

            if self.ap.debug_overlay:
                self.ap.overlay.overlay_floating_text('nav_list_text', f'{ocr_textlist}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
                self.ap.overlay.overlay_paint()

            if img_selected is not None and station_name.upper() in str(ocr_textlist).upper():
                station_found = True
                break

            self.keys.send('UI_Down') # Scroll down
            sleep(0.05)

        if self.ap.debug_overlay:
            sleep(1)
            self.ap.overlay.overlay_remove_rect('nav_list')
            self.ap.overlay.overlay_remove_floating_text('nav_list_text')
            self.ap.overlay.overlay_paint()

        if not station_found:
            logger.error(f"Could not find station {station_name} in navigation panel.")
            self.ap_ckb('log+vce', f"Error: Could not find station {station_name}.")
            return False

        # Now on station, select it
        self.keys.send('UI_Select')
        sleep(0.5)
        self.keys.send('UI_Select')
        sleep(0.5)
        self.keys.send('UI_Back')
        # Could add further checks here to see if it was selected correctly
        
        return True

    def request_docking(self) -> bool:
        """ Try to request docking with OCR.
        """
        res = self.show_contacts_tab()
        if res is None:
            return None
        if not res:
            print("Contacts Panel could not be opened")
            return False

        # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # then go right, which will be "REQUEST DOCKING" and select it
        self.keys.send("UI_Down")  # go down
        self.keys.send('UI_Up', hold=2)  # got to top row
        self.keys.send('UI_Right')
        self.keys.send('UI_Select')
        sleep(0.3)

        self.hide_nav_panel()
        return True

    def load_calibrated_sizes(self):
        calibration_file = 'configs/ocr_calibration.json'
        if os.path.exists(calibration_file):
            with open(calibration_file, 'r') as f:
                calibrated_data = json.load(f)

            if "EDNavigationPanel.size.nav_pnl_tab" in calibrated_data:
                self.nav_pnl_tab_width = calibrated_data["EDNavigationPanel.size.nav_pnl_tab"]['width']
                self.nav_pnl_tab_height = calibrated_data["EDNavigationPanel.size.nav_pnl_tab"]['height']

            if "EDNavigationPanel.size.nav_pnl_location" in calibrated_data:
                self.nav_pnl_location_width = calibrated_data["EDNavigationPanel.size.nav_pnl_location"]['width']
                self.nav_pnl_location_height = calibrated_data["EDNavigationPanel.size.nav_pnl_location"]['height']

    def load_calibrated_regions(self):
        calibration_file = 'configs/ocr_calibration.json'
        if os.path.exists(calibration_file):
            with open(calibration_file, 'r') as f:
                calibrated_regions = json.load(f)

            for key, value in self.reg.items():
                calibrated_key = f"EDNavigationPanel.{key}"
                if calibrated_key in calibrated_regions:
                    self.reg[key]['rect'] = calibrated_regions[calibrated_key]['rect']


    def hide_nav_panel(self):
        """ Hides the Nav Panel if open.
        """
        # Is nav panel active?
        if self.status_parser.get_gui_focus() == GuiFocusExternalPanel:
            self.ap.ship_control.goto_cockpit_view()


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)  # Default to log all debug when running this file.
    from ED_AP import EDAutopilot
    ap = EDAutopilot(cb=dummy_cb)
    ap.keys.activate_window = True  # Helps with single steps testing

    from Screen import set_focus_elite_window
    set_focus_elite_window()
    nav_pnl = EDNavigationPanel(ap, ap.scr, ap.keys, dummy_cb)
    nav_pnl.request_docking()

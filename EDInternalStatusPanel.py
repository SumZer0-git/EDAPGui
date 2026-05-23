from __future__ import annotations

import json
import logging
import os
from copy import copy
from time import sleep
import cv2
from EDAP_data import *
# from EDKeys import EDKeys
from EDNavigationPanel import rects_to_quadrilateral, image_perspective_transform, image_reverse_perspective_transform
# from OCR import OCR
from Screen import Screen, crop_image_by_pct
from Screen_Regions import Quad, load_calibrated_regions
from StatusParser import StatusParser
from EDlogger import logger


class EDInternalStatusPanel:
    """ The Internal (Right hand) Ship Status Panel. """

    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.screen = screen
        self.keys = keys
        self.ap_ckb = cb
        self.locale = self.ap.locale
        self.status_parser = StatusParser()

        self.modules_tab_text = self.locale["INT_PNL_TAB_MODULES"]
        self.fire_groups_tab_text = self.locale["INT_PNL_TAB_FIRE_GROUPS"]
        self.ship_tab_text = self.locale["INT_PNL_TAB_SHIP"]
        self.inventory_tab_text = self.locale["INT_PNL_TAB_INVENTORY"]
        self.storage_tab_text = self.locale["INT_PNL_TAB_STORAGE"]
        self.status_tab_text = self.locale["INT_PNL_TAB_STATUS"]

        # The rect is [L, T, R, B] top left x, y, and bottom right x, y in fraction of screen resolution
        # Nav Panel region covers the entire navigation panel.
        self.reg = {'panel_bounds1': {'rect': [0.0, 0.2, 0.7, 0.35]},
                    'panel_bounds2': {'rect': [0.0, 0.2, 0.7, 0.35]},
                    }
        self.sub_reg = {'tab_bar': {'rect': [0.0, 0.0, 1.0, 0.08]},
                        'H': {'rect': [0.174, 0.2265, 0.75, 0.8528]},
                        'sts_pnl_tab': {'rect': [0.0, 0.0, 0.15, 0.7]},
                        }
        self.panel_quad_pct = Quad()
        self.panel_quad_pix = Quad()
        self.panel = None
        self._transform = None  # Warp transform to deskew the Nav panel
        self._rev_transform = None  # Reverse warp transform to skew to match the Nav panel

        # Load custom regions from file
        load_calibrated_regions('EDInternalStatusPanel', self.reg)

        self.customize_regions()

    def customize_regions(self):
        # Produce quadrilateral from the two bounds rectangles
        reg1 = Quad.from_rect(self.reg['panel_bounds1']['rect'])
        reg2 = Quad.from_rect(self.reg['panel_bounds2']['rect'])
        self.panel_quad_pct = rects_to_quadrilateral(reg1, reg2)
        self.panel_quad_pix = copy(self.panel_quad_pct)
        self.panel_quad_pix.scale_from_origin(self.ap.scr.screen_width, self.ap.scr.screen_height)

    def capture_panel_straightened(self):
        """ Grab the image based on the panel coordinates.
        Returns an unfiltered image, either from screenshot or provided image, or None if an image cannot
        be grabbed.
        """
        if self.panel_quad_pct is None:
            logger.warning(f"Nav Panel Calibration has not been performed. Cannot continue.")
            self.ap_ckb('log', 'Nav Panel Calibration has not been performed. Cannot continue.')
            return None

        # Get the nav panel image based on the region
        image = self.screen.get_screen(self.panel_quad_pix.left, self.panel_quad_pix.top,
                                       self.panel_quad_pix.right, self.panel_quad_pix.bottom, rgb=False)
        cv2.imwrite(f'test/status-panel/out/nav_panel_original.png', image)

        # Offset the panel co-ords to match the cropped image (i.e. starting at 0,0)
        panel_quad_pix_off = copy(self.panel_quad_pix)
        panel_quad_pix_off.offset(-panel_quad_pix_off.left, -panel_quad_pix_off.top)

        # Straighten the image
        straightened, trans, rev_trans = image_perspective_transform(image, panel_quad_pix_off)
        # Store the transforms
        self._transform = trans
        self._rev_transform = rev_trans
        # Write the file
        cv2.imwrite(f'test/status-panel/out/nav_panel_straight.png', straightened)

        if self.ap.debug_overlay:
            self.ap.overlay.overlay_quad_pct('nav_panel_active', self.panel_quad_pct, (0, 255, 0), 2, 5)
            self.ap.overlay.overlay_paint()

        return straightened

    def capture_tab_bar(self):
        """ Get the tab bar (MODULES/FIRE GROUPS/SHIP/INVENTORY/STORAGE/STATUS).
        Returns an image, or None.
        """
        # Scale the regions based on the target resolution.
        self.panel = self.capture_panel_straightened()
        if self.panel is None:
            return None

        # Convert region rect to quad
        tab_bar_quad = Quad.from_rect(self.sub_reg['tab_bar']['rect'])
        # Crop the image to the extents of the quad
        tab_bar = crop_image_by_pct(self.panel, tab_bar_quad)
        cv2.imwrite(f'test/status-panel/out/tab_bar.png', tab_bar)

        if self.ap.debug_overlay:
            # Transform the array of coordinates to the skew of the nav panel
            q_out = image_reverse_perspective_transform(self.panel, tab_bar_quad, self._rev_transform)
            # Offset to match the nav panel offset
            q_out.offset(self.panel_quad_pix.left, self.panel_quad_pix.top)

            self.ap.overlay.overlay_quad_pix('status_panel_tab_bar', q_out, (0, 255, 0), 2, 5)
            self.ap.overlay.overlay_paint()

        return tab_bar

    def capture_inventory_panel(self):
        """ Get the inventory panel from within the panel.
        Returns an image, or None.
        """
        # Scale the regions based on the target resolution.
        panel = self.capture_panel_straightened()
        if panel is None:
            return None

        # Convert region rect to quad
        inventory_panel_quad = Quad.from_rect(self.sub_reg['inventory_panel']['rect'])
        # Crop the image to the extents of the quad
        inventory_panel = crop_image_by_pct(panel, inventory_panel_quad)
        cv2.imwrite(f'test/status-panel/out/inventory_panel.png', inventory_panel)

        if self.ap.debug_overlay:
            # Transform the array of coordinates to the skew of the nav panel
            q_out = image_reverse_perspective_transform(panel, inventory_panel_quad, self._rev_transform)
            # Offset to match the nav panel offset
            q_out.offset(self.panel_quad_pix.left, self.panel_quad_pix.top)

            self.ap.overlay.overlay_quad_pix('sts_panel_inventory_panel', q_out, (0, 255, 0), 2, 5)
            self.ap.overlay.overlay_paint()

        return inventory_panel

    def show_panel(self):
        """ Shows the Status Panel. Opens the Nav Panel if not already open.
        Returns True if successful, else False.
        """
        logger.debug("show_right_panel: entered")

        # Is nav panel active?
        active, active_tab_name = self.is_panel_active()
        if active:
            # Store image
            image = self.screen.get_screen_full()
            cv2.imwrite(f'test/status-panel/int_panel_full.png', image)
            return active, active_tab_name
        else:
            print("Open Status Panel")
            logger.debug("show_right_panel: Open Internal Panel")
            self.ap.ship_control.goto_cockpit_view()

            self.keys.send("HeadLookReset")
            self.keys.send('UIFocus', state=1)
            self.keys.send('UI_Right')
            self.keys.send('UIFocus', state=0)
            sleep(0.5)

            # Check if it opened
            active, active_tab_name = self.is_panel_active()
            if active:
                # Store image
                image = self.screen.get_screen_full()
                cv2.imwrite(f'test/status-panel/internal_panel_full.png', image)
                return active, active_tab_name
            else:
                return False, ""

    def hide_panel(self):
        """ Hides the Internal Panel if open.
        """
        # Is internal panel active?
        if self.status_parser.get_gui_focus() == GuiFocusInternalPanel:
            self.ap.ship_control.goto_cockpit_view()

    def is_panel_active(self) -> (bool, str):
        """ Determine if the Nav Panel is open and if so, which tab is active.
            Returns True if active, False if not and also the string of the tab name.
        """
        logger.debug("is_right_panel_active: entered")

        # Check if nav panel is open
        if not self.status_parser.wait_for_gui_focus(GuiFocusInternalPanel, 3):
            logger.debug("is_right_panel_active: right panel not focused")
            return False, ""

        # Try this 'n' times before giving up
        tab_text = ""
        for i in range(10):
            # Is open, so proceed
            tab_bar = self.capture_tab_bar()
            if tab_bar is None:
                return False, ""

            item = Quad.from_rect(self.sub_reg['sts_pnl_tab']['rect'])
            img_selected, _, ocr_textlist, quad = self.ocr.get_highlighted_item_data(tab_bar, item, 'status panel')
            if img_selected is not None:
                if self.ap.debug_overlay:
                    tab_bar_quad = Quad.from_rect(self.sub_reg['tab_bar']['rect'])
                    # Convert to a percentage of the nav panel
                    quad.scale_from_origin(tab_bar_quad.width, tab_bar_quad.height)
                    # quad.offset(tab_bar_quad.left, tab_bar_quad.top)

                    # Transform the array of coordinates to the skew of the nav panel
                    q_out = image_reverse_perspective_transform(self.panel, quad, self._rev_transform)
                    # Offset to match the nav panel offset
                    q_out.offset(self.panel_quad_pix.left, self.panel_quad_pix.top)

                    # Overlay OCR result
                    self.ap.overlay.overlay_floating_text('sts_panel_item_text', f'{str(ocr_textlist)}', q_out.left, q_out.top - 25,                                                         (0, 255, 0))
                    self.ap.overlay.overlay_quad_pix('sts_panel_item', q_out, (0, 255, 0), 2)
                    self.ap.overlay.overlay_paint()

                # Test OCR string
                if self.modules_tab_text in str(ocr_textlist):
                    tab_text = self.modules_tab_text
                    break
                if self.fire_groups_tab_text in str(ocr_textlist):
                    tab_text = self.fire_groups_tab_text
                    break
                if self.ship_tab_text in str(ocr_textlist):
                    tab_text = self.ship_tab_text
                    break
                if self.inventory_tab_text in str(ocr_textlist):
                    tab_text = self.inventory_tab_text
                    break
                if self.storage_tab_text in str(ocr_textlist):
                    tab_text = self.storage_tab_text
                    break
                if self.status_tab_text in str(ocr_textlist):
                    tab_text = self.status_tab_text
                    break
            else:
                logger.debug("is_right_panel_active: no image selected")

            # Wait and retry
            sleep(1)

            # In case we are on a picture tab, cycle to the next tab
            self.keys.send('CycleNextPanel')

        # Return Tab text or nothing
        if tab_text != "":
            return True, tab_text
        else:
            return False, ""

    def show_inventory_tab(self) -> bool | None:
        """ Shows the INVENTORY tab of the Nav Panel. Opens the Nav Panel if not already open.
        Returns True if successful, else False.
        """
        # Show nav panel
        active, active_tab_name = self.show_panel()
        if active is None:
            return None
        if not active:
            print("Internal (Right) Panel could not be opened")
            return False
        elif active_tab_name is self.inventory_tab_text:
            # Do nothing
            return True
        elif active_tab_name is self.modules_tab_text:
            self.keys.send('CycleNextPanel', repeat=3)
            return True
        elif active_tab_name is self.fire_groups_tab_text:
            self.keys.send('CycleNextPanel', repeat=2)
            return True
        elif active_tab_name is self.ship_tab_text:
            self.keys.send('CycleNextPanel', repeat=1)
            return True
        elif active_tab_name is self.storage_tab_text:
            self.keys.send('CycleNextPanel', repeat=7)
            return True
        elif active_tab_name is self.status_tab_text:
            self.keys.send('CycleNextPanel', repeat=6)
            return True

    def transfer_to_fleetcarrier(self, ap):
        """ Transfer all goods to Fleet Carrier """
        self.ap_ckb('log+vce', "Executing transfer to Fleet Carrier.")
        logger.debug("transfer_to_fleetcarrier: entered")
        # Go to the internal (right) panel inventory tab
        self.show_inventory_tab()

        # Assumes on the INVENTORY tab
        ap.keys.send('UI_Right')
        sleep(0.1)
        ap.keys.send('UI_Up')  # To FILTERS
        sleep(0.1)
        ap.keys.send('UI_Right')  # To TRANSFER >>
        sleep(0.1)
        ap.keys.send('UI_Select')  # Click TRANSFER >>
        sleep(0.1)
        ap.keys.send('UI_Up', hold=3)
        sleep(0.1)
        ap.keys.send('UI_Up')
        sleep(0.1)
        ap.keys.send('UI_Select')

        ap.keys.send('UI_Select')
        sleep(0.1)

        ap.keys.send("UI_Back", repeat=4)
        sleep(0.2)
        ap.keys.send("HeadLookReset")
        print("End of unload FC")
        # quit()

    def transfer_from_fleetcarrier(self, ap, buy_commodities):
        """ Transfer specific good from Fleet Carrier to ship"""
        self.ap_ckb('log+vce', f"Executing transfer from Fleet Carrier.")
        logger.debug("transfer_to_fleetcarrier: entered")
        # Go to the internal (right) panel inventory tab
        self.show_inventory_tab()

        # Assumes on the INVENTORY tab
        ap.keys.send('UI_Right')
        sleep(0.1)
        ap.keys.send('UI_Up')  # To FILTERS
        sleep(0.1)
        ap.keys.send('UI_Right')  # To >> TRANSFER
        sleep(0.1)
        ap.keys.send('UI_Select')  # Click >> TRANSFER
        sleep(0.1)
        ap.keys.send('UI_Up', hold=3)  # go to top of list
        sleep(0.1)

        index = buy_commodities['Down']

        ap.keys.send('UI_Down', hold=0.05, repeat=index)  # go down # of times user specified
        sleep(0.5)
        ap.keys.send('UI_Left', hold=10)  # Transfer commodity, wait 10 sec to xfer

        sleep(0.1)
        ap.keys.send('UI_Select')  # Take us down to "Confirm Item Transfer"

        ap.keys.send('UI_Select')  # Click Transfer
        sleep(0.1)

        ap.keys.send("UI_Back", repeat=4)
        sleep(0.2)
        ap.keys.send("HeadLookReset")
        print("End of transfer from FC")


def dummy_cb(msg, body=None):
    pass


# Usage Example
if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)  # Default to log all debug when running this file.
    from ED_AP import EDAutopilot
    ap = EDAutopilot(cb=dummy_cb)
    scr = ap.scr
    mykeys = ap.keys
    mykeys.activate_window = True  # Helps with single steps testing

    from Screen import set_focus_elite_window
    set_focus_elite_window()
    nav_pnl = EDInternalStatusPanel(ap, scr, mykeys, dummy_cb)
    nav_pnl.show_inventory_tab()

from __future__ import annotations

import logging
from time import sleep
import cv2
from EDAP_data import *
from EDKeys import EDKeys
from OCR import OCR
from Screen import Screen
from Screen_Regions import size_scale_for_station
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
        self.reg = {'right_panel': {'rect': [0.2, 0.2, 1.0, 0.35]}}

        self.nav_pnl_tab_width = 140  # Nav panel tab width in pixels at 1920x1080
        self.nav_pnl_tab_height = 35  # Nav panel tab height in pixels at 1920x1080

    def show_right_panel(self):
        """ Shows the Internal (Right) Panel.
        Returns True if successful, else False.
        """
        logger.debug("show_right_panel: entered")

        # Is nav panel active?
        active, active_tab_name = self.is_right_panel_active()
        if active:
            # Store image
            image = self.screen.get_screen_full()
            cv2.imwrite(f'test/internal-panel/int_panel_full.png', image)
            return active, active_tab_name
        else:
            print("Open Internal Panel")
            logger.debug("show_right_panel: Open Internal Panel")
            self.ap.ship_control.goto_cockpit_view()

            self.keys.send("HeadLookReset")
            self.keys.send('UIFocus', state=1)
            self.keys.send('UI_Right')
            self.keys.send('UIFocus', state=0)
            sleep(0.5)

            # Check if it opened
            active, active_tab_name = self.is_right_panel_active()
            if active:
                # Store image
                image = self.screen.get_screen_full()
                cv2.imwrite(f'test/internal-panel/internal_panel_full.png', image)
                return active, active_tab_name
            else:
                return False, ""

    def show_inventory_tab(self) -> bool | None:
        """ Shows the INVENTORY tab of the Nav Panel. Opens the Nav Panel if not already open.
        Returns True if successful, else False.
        """
        logger.debug("show_inventory_tab: entered")

        # Show nav panel
        active, active_tab_name = self.show_right_panel()
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

    def is_right_panel_active(self) -> (bool, str):
        """ Determine if the Nav Panel is open and if so, which tab is active.
            Returns True if active, False if not and also the string of the tab name.
        """
        logger.debug("is_right_panel_active: entered")

        # Check if nav panel is open
        if not self.status_parser.wait_for_gui_focus(GuiFocusInternalPanel, 3):
            logger.debug("is_right_panel_active: right panel not focused")
            return False, ""

        logger.debug("is_right_panel_active: right panel is focused")

        # Draw box around region
        abs_rect = self.screen.screen_rect_to_abs(self.reg['right_panel']['rect'])
        if self.ap.debug_overlay:
            self.ap.overlay.overlay_rect1('right_panel_active', abs_rect, (0, 255, 0), 2)
            self.ap.overlay.overlay_paint()

        # Try this 'n' times before giving up
        tab_text = ""
        for i in range(10):
            # Take screenshot of the panel
            image = self.ocr.capture_region_pct(self.reg['right_panel'])
            # tab_bar = self.capture_tab_bar()
            # if tab_bar is None:
            #     return None

            # Determine the nav panel tab size at this resolution
            scl_row_w, scl_row_h = size_scale_for_station(self.nav_pnl_tab_width, self.nav_pnl_tab_height,
                                                          self.screen.screen_width, self.screen.screen_height)

            img_selected, ocr_data, ocr_textlist = self.ocr.get_highlighted_item_data(image, scl_row_w, scl_row_h)
            if img_selected is not None:
                logger.debug("is_right_panel_active: image selected")
                logger.debug(f"is_right_panel_active: OCR: {ocr_textlist}")

                # Overlay OCR result
                if self.ap.debug_overlay:
                    self.ap.overlay.overlay_floating_text('right_panel_text', f'{ocr_textlist}', abs_rect[0], abs_rect[1] - 25, (0, 255, 0))
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

        # Clean up screen
        if self.ap.debug_overlay:
            sleep(2)
            self.ap.overlay.overlay_remove_rect('right_panel_active')
            self.ap.overlay.overlay_remove_floating_text('right_panel_text')
            self.ap.overlay.overlay_paint()

        # Return Tab text or nothing
        if tab_text != "":
            return True, tab_text
        else:
            return False, ""

    def hide_right_panel(self):
        """ Hides the Internal Panel if open.
        """
        # Is internal panel active?
        if self.status_parser.get_gui_focus() == GuiFocusInternalPanel:
            self.ap.ship_control.goto_cockpit_view()

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

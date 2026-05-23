from __future__ import annotations

import json
import os

from EDAP_data import GuiFocusSystemMap
from EDlogger import logger
from Screen_Regions import Quad, load_calibrated_regions
from StatusParser import StatusParser
from time import sleep


class EDSystemMap:
    """ Handles the System Map. """
    def __init__(self, ed_ap, screen, keys, cb, is_odyssey=True):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.is_odyssey = is_odyssey
        self.screen = screen
        self.keys = keys
        self.status_parser = StatusParser()
        self.ap_ckb = cb
        # The rect is top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg = {'full_panel': {'rect': [0.1, 0.1, 0.9, 0.9]},
                    'cartographics': {'rect': [0.0, 0.0, 0.25, 0.25]},
                    }

        # Load custom regions from file
        load_calibrated_regions('EDSystemMap', self.reg)

    def set_sys_map_dest_bookmark(self, ap, bookmark_type: str, bookmark_position: int) -> bool:
        """ Set the System Map destination using a bookmark.
        @param ap: ED_AP reference.
        @param bookmark_type: The bookmark type (Favorite, Body, Station, Settlement or Navigation), Favorite
         being the default if no match is made with the other options. Navigation is unique in that it uses
         the Nav Panel instead of the System Map.
        @param bookmark_position: The position in the bookmark list, starting at 1 for the first bookmark.
        @return: True if bookmark could be selected, else False
        """
        if self.is_odyssey and bookmark_position != -1:
            # Check if this is a nav-panel bookmark
            if not bookmark_type.lower().startswith("nav"):
                res = self.goto_system_map()
                if not res:
                    return False

                ap.keys.send('UI_Left')  # Go to BOOKMARKS
                sleep(.5)
                ap.keys.send('UI_Select')  # Select BOOKMARKS
                sleep(.25)
                ap.keys.send('UI_Right')  # Go to FAVORITES
                sleep(.25)

                # If bookmark type is Fav, do nothing as this is the first item
                if bookmark_type.lower().startswith("bod"):
                    ap.keys.send('UI_Down', repeat=1)  # Go to BODIES
                elif bookmark_type.lower().startswith("sta"):
                    ap.keys.send('UI_Down', repeat=2)  # Go to STATIONS
                elif bookmark_type.lower().startswith("set"):
                    ap.keys.send('UI_Down', repeat=3)  # Go to SETTLEMENTS

                sleep(.25)
                ap.keys.send('UI_Select')  # Select bookmark type, moves you to bookmark list
                ap.keys.send('UI_Left')  # Sometimes the first bookmark is not selected, so we try to force it.
                ap.keys.send('UI_Right')
                sleep(.25)
                ap.keys.send('UI_Down', repeat=bookmark_position - 1)
                sleep(.25)
                ap.keys.send('UI_Select', hold=3.0)

                # Close System Map
                ap.keys.send('SystemMapOpen')
                sleep(0.5)
                return True

            elif bookmark_type.lower().startswith("nav"):
                # TODO - Move to, or call Nav Panel code instead?
                # This is a nav-panel bookmark
                # Goto cockpit view
                self.ap.ship_control.goto_cockpit_view()

                # get to the Left Panel menu: Navigation
                ap.keys.send("HeadLookReset")
                ap.keys.send("UIFocus", state=1)
                ap.keys.send("UI_Left")
                ap.keys.send("UIFocus", state=0)  # this gets us over to the Nav panel

                ap.keys.send('UI_Up', hold=4)
                ap.keys.send('UI_Down', repeat=bookmark_position - 1)
                sleep(1.0)
                ap.keys.send('UI_Select')
                sleep(0.25)
                ap.keys.send('UI_Select')
                ap.keys.send("UI_Back")
                ap.keys.send("HeadLookReset")
                return True

        return False

    def goto_system_map(self) -> bool:
        """ Open System Map if we are not there.
        """
        if self.status_parser.get_gui_focus() != GuiFocusSystemMap:
            logger.debug("Opening System Map")
            # Goto cockpit view
            self.ap.ship_control.goto_cockpit_view()
            # Goto System Map
            self.ap.keys.send('SystemMapOpen')

            if self.ap.debug_overlay:
                stn_svcs = Quad.from_rect(self.reg['full_panel']['rect'])
                self.ap.overlay.overlay_quad_pct('system map', stn_svcs, (0, 255, 0), 2, 5)
                self.ap.overlay.overlay_paint()

            # Wait for screen to appear. The text is the same, regardless of language.
            res = self.ocr.wait_for_text(self.ap, ["CARTOGRAPHICS"], self.reg['cartographics'], timeout=15)
            if not res:
                if self.status_parser.get_gui_focus() != GuiFocusSystemMap:
                    logger.warning("Unable to open System Map")
                    return False

            return True
        else:
            logger.debug("System Map is already open")
            self.keys.send('UI_Left')
            self.keys.send('UI_Up', hold=2)
            self.keys.send('UI_Left')
            return True

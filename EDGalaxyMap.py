from __future__ import annotations

from EDAP_data import GuiFocusGalaxyMap
from OCR import OCR
from StatusParser import StatusParser
from time import sleep
from EDlogger import logger
from pyautogui import typewrite


class EDGalaxyMap:
    """ Handles the Galaxy Map. """
    def __init__(self, ed_ap, screen, keys, cb, is_odyssey=True):
        self.ap = ed_ap
        self.is_odyssey = is_odyssey
        self.screen = screen
        self.ocr = OCR(screen)
        self.keys = keys
        self.status_parser = StatusParser()
        self.ap_ckb = cb

    def set_gal_map_dest_bookmark(self, ap, bookmark_type: str, bookmark_position: int) -> bool:
        """ Set the gal map destination using a bookmark.
        @param ap: ED_AP reference.
        @param bookmark_type: The bookmark type (Favorite, System, Body, Station or Settlement), Favorite
         being the default if no match is made with the other options.
        @param bookmark_position: The position in the bookmark list, starting at 1 for the first bookmark.
        @return: True if bookmark could be selected, else False
        """
        if self.is_odyssey and bookmark_position > 0:
            self.goto_galaxy_map()

            ap.keys.send('UI_Left')  # Go to BOOKMARKS
            sleep(.5)
            ap.keys.send('UI_Select')  # Select BOOKMARKS
            sleep(.25)
            ap.keys.send('UI_Right')  # Go to FAVORITES
            sleep(.25)

            # If bookmark type is Fav, do nothing as this is the first item
            if bookmark_type.lower().startswith("sys"):
                ap.keys.send('UI_Down')  # Go to SYSTEMS
            elif bookmark_type.lower().startswith("bod"):
                ap.keys.send('UI_Down', repeat=2)  # Go to BODIES
            elif bookmark_type.lower().startswith("sta"):
                ap.keys.send('UI_Down', repeat=3)  # Go to STATIONS
            elif bookmark_type.lower().startswith("set"):
                ap.keys.send('UI_Down', repeat=4)  # Go to SETTLEMENTS

            sleep(.25)
            ap.keys.send('UI_Select')  # Select bookmark type, moves you to bookmark list
            sleep(.25)
            ap.keys.send('UI_Down', repeat=bookmark_position - 1)
            sleep(.25)
            ap.keys.send('UI_Select', hold=3.0)

            # Close Galaxy map
            ap.keys.send('GalaxyMapOpen')
            sleep(0.5)
            return True

        return False

    def set_gal_map_destination_text(self, ap, target_name, target_select_cb=None) -> bool:
        """ Call either the Odyssey or Horizons version of the Galactic Map sequence. """
        if not self.is_odyssey:
            return ap.galaxy_map.set_gal_map_destination_text_horizons(ap, target_name, target_select_cb)
        else:
            return ap.galaxy_map.set_gal_map_destination_text_odyssey(ap, target_name)

    def set_gal_map_destination_text_horizons(self, ap, target_name, target_select_cb=None) -> bool:
        """ This sequence for the Horizons. """
        self.goto_galaxy_map()

        ap.keys.send('CycleNextPanel')
        sleep(1)
        ap.keys.send('UI_Select')
        sleep(2)

        typewrite(target_name, interval=0.25)
        sleep(1)

        # send enter key
        ap.keys.send_key('Down', 28)
        sleep(0.05)
        ap.keys.send_key('Up', 28)

        sleep(7)
        ap.keys.send('UI_Right')
        sleep(1)
        ap.keys.send('UI_Select')

        # if got passed through the ship() object, lets call it to see if a target has been
        # selected yet... otherwise we wait.  If long route, it may take a few seconds
        if target_select_cb is not None:
            while not target_select_cb()['target']:
                sleep(1)

        # Close Galaxy map
        ap.keys.send('GalaxyMapOpen')
        sleep(2)
        return True

    def set_gal_map_destination_text_odyssey(self, ap, target_name) -> bool:
        """ This sequence for the Odyssey. """
        self.goto_galaxy_map()

        # Check if the current nav route is to the target system
        last_nav_route_sys = ap.nav_route.get_last_system()
        if last_nav_route_sys.upper() == target_name.upper():
            # Close Galaxy map
            ap.keys.send('GalaxyMapOpen')
            return True

        # navigate to and select: search field
        ap.keys.send('UI_Up')
        sleep(0.05)
        ap.keys.send('UI_Select')
        sleep(0.05)

        # type in the System name
        typewrite(target_name, interval=0.25)
        sleep(0.05)

        # send enter key (removes focus out of input field)
        ap.keys.send_key('Down', 28)  # 28=ENTER
        sleep(0.05)
        ap.keys.send_key('Up', 28)  # 28=ENTER
        sleep(0.05)

        # According to some reports, the ENTER key does not always reselect the text
        # box, so this down and up will reselect the text box.
        ap.keys.send('UI_Down')
        sleep(0.05)
        ap.keys.send('UI_Up')
        sleep(0.05)

        # navigate to and select: search button
        ap.keys.send('UI_Right')  # to >| button
        sleep(0.05)

        correct_route = False
        while not correct_route:
            # Store the current nav route system
            last_nav_route_sys = ap.nav_route.get_last_system()

            # Select first (or next) system
            ap.keys.send('UI_Select')  # Select >| button

            # zoom camera which puts focus back on the map
            ap.keys.send('CamZoomIn')
            sleep(0.05)

            # plot route. Not that once the system has been selected, as shown in the info panel
            # and the gal map has focus, there is no need to wait for the map to bring the system
            # to the center screen, the system can be selected while the map is moving.
            ap.keys.send('UI_Select', hold=0.75)

            sleep(0.05)

            # if got passed through the ship() object, lets call it to see if a target has been
            # selected yet... otherwise we wait.  If long route, it may take a few seconds
            if ap.nav_route is not None:
                while 1:
                    curr_nav_route_sys = ap.nav_route.get_last_system()
                    # Check if the nav route has been changed (right or wrong)
                    if curr_nav_route_sys.upper() != last_nav_route_sys.upper():
                        # Check if this nav route is correct
                        if curr_nav_route_sys.upper() == target_name.upper():
                            # Break loop and exit
                            correct_route = True
                            break
                        else:
                            # Try the next system, go back to the search bar
                            ap.keys.send('UI_Up')
                            break
            else:
                # Cannot check route, so assume right
                correct_route = True

        # Close Galaxy map
        ap.keys.send('GalaxyMapOpen')
        return True

    def set_next_system(self, ap, target_system) -> bool:
        """ Sets the next system to jump to, or the final system to jump to.
        If the system is already selected or is selected correctly, returns True,
        otherwise False.
        """
        # Call sequence to select route
        if self.set_gal_map_destination_text(ap, target_system, None):
            return True
        else:
            # Error setting target
            logger.warning("Error setting waypoint, breaking")
            return False

    def goto_galaxy_map(self):
        """Open Galaxy Map if we are not there. Waits for map to load. Selects the search bar.
        """
        if self.status_parser.get_gui_focus() != GuiFocusGalaxyMap:
            logger.debug("Opening Galaxy Map")
            # Goto cockpit view
            self.ap.ship_control.goto_cockpit_view()
            # Goto Galaxy Map
            self.keys.send('GalaxyMapOpen')
            # Wait for map to load

            # TODO - check this to OCR check
            sleep(2)

            self.keys.send('UI_Up')  # Go up to search bar
        else:
            logger.debug("Galaxy Map is already open")
            self.keys.send('UI_Left', repeat=2)
            self.keys.send('UI_Up', hold=2)  # Go up to search bar. Allows 1 left to bookmarks.

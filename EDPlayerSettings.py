from __future__ import annotations

from os import environ, listdir
from os.path import getmtime, isfile, join
import xmltodict

from EDlogger import logger

class EDPlayerSettings:
    """ Handles the Player settings (Custom.4.3.misc) XML file. """

    def __init__(self, cb, display_file_path=None):
        self.ap_ckb = cb
        self.dashboard_gui_brightness = '' # GUI brightness ('0.0' to '1.0')
        self.hide_location_icons = '' # Hide icons in nav panel ('0'=Don't hide, '1'=Hide)
        self.language = '' # Language ('English' etc.)
        self.language_override_active = '' # ? ('0' ? or '1' ?)

        self.player_settings_filepath = display_file_path if display_file_path else self.get_latest_settings()

        if not self.player_settings_filepath or not isfile(self.player_settings_filepath):
            logger.error(
                f"Elite Dangerous player settings file does not exist: {self.player_settings_filepath}.")
            raise Exception(
                f"Elite Dangerous player settings settings file does not exist: {self.player_settings_filepath}.")

        # Read player settings xml file data
        logger.info(f"Reading ED player settings from '{self.player_settings_filepath}'.")
        self.display_settings = self.read_settings(self.player_settings_filepath)

        # Process graphics display settings
        if self.display_settings is not None:
            self.dashboard_gui_brightness = self.display_settings['Root']['DashboardGUIBrightness']['@Value']
            logger.debug(f"Elite Dangerous player setting 'DashboardGUIBrightness': {self.dashboard_gui_brightness}.")

            self.hide_location_icons = self.display_settings['Root']['HideLocationIcons']['@Value']
            logger.debug(f"Elite Dangerous player setting 'HideLocationIcons': {self.hide_location_icons}.")

            self.language = self.display_settings['Root']['Language']['@Value']
            logger.debug(f"Elite Dangerous player setting 'Language': {self.language}.")

            self.language_override_active = self.display_settings['Root']['LanguageOverrideActive']['@Value']
            logger.debug(f"Elite Dangerous player setting 'LanguageOverrideActive': {self.language_override_active}.")

        # Check settings...
        if float(self.dashboard_gui_brightness) < 1.0:
            self.ap_ckb('log', f"WARNING: Consider changing setting 'Interface Brightness' to maximum in 'R Panel > Ship > Pilot Preferences'.")
            logger.warning("Consider changing setting 'Interface Brightness' to maximum in 'R Panel > Ship > Pilot Preferences'.")

        if int(self.hide_location_icons) == 1:
            self.ap_ckb('log', f"WARNING: Consider changing setting 'Location Status Icons' to 'Show Icons' in 'R Panel > Ship > Pilot Preferences'.")
            logger.warning("Consider changing setting 'Location Status Icons' to 'Show Icons' in 'R Panel > Ship > Pilot Preferences'.")

        if self.language != 'English':
            self.ap_ckb('log', f"WARNING: ED is not set to English language. Remember to change the language setting in ap.json.")
            logger.warning("WARNING: ED is not set to English language. Remember to change the language setting in ap.json.")

    @staticmethod
    def read_settings(filename) -> dict:
        """ Reads an XML settings file to a Dict and returns the dict. """
        try:
            with open(filename, 'r') as file:
                my_xml = file.read()
                my_dict = xmltodict.parse(my_xml)
                return my_dict
        except OSError as e:
            logger.error(f"OS Error reading Elite Dangerous player settings file: {filename}.")
            raise Exception(f"OS Error reading Elite Dangerous player settings file: {filename}.")

    @staticmethod
    def get_latest_settings():
        """
        This routine will grab the *.misc file which is the latest modified
        :return:
        """
        path_bindings = environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous\\Options\\Player"
        try:
            list_of_bindings = [join(path_bindings, f) for f in listdir(path_bindings) if
                                isfile(join(path_bindings, f)) and f.endswith('.misc')]
        except FileNotFoundError as e:
            return None

        if not list_of_bindings:
            return None
        latest_bindings = max(list_of_bindings, key=getmtime)
        logger.info(f'Latest player settings file:{latest_bindings}')
        return latest_bindings

def main():
    gs = EDPlayerSettings()
    print(gs.player_settings_filepath)

if __name__ == "__main__":
    main()

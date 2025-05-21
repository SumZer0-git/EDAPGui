from os.path import isfile

from EDlogger import logger
import xmltodict
from os import environ


class EDGraphicsSettings:
    """ Handles the Graphics DisplaySettings.xml and Settings.xml files. """

    def __init__(self, display_file_path=None, settings_file_path=None):
        self.fullscreen = ''
        self.fullscreen_str = ''
        self.screenwidth = ''
        self.screenheight = ''
        self.monitor = ''
        self.fov = ''
        self.display_settings_filepath = display_file_path if display_file_path else \
            (environ[
                 'LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous\\Options\\Graphics\\DisplaySettings.xml")
        self.settings_filepath = settings_file_path if settings_file_path else \
            (environ['LOCALAPPDATA'] + "\\Frontier Developments\\Elite Dangerous\\Options\\Graphics\\Settings.xml")

        if not isfile(self.display_settings_filepath):
            logger.error(
                f"Elite Dangerous graphics display settings file does not exist: {self.display_settings_filepath}.")
            raise Exception(
                f"Elite Dangerous graphics display settings file does not exist: {self.display_settings_filepath}.")

        if not isfile(self.settings_filepath):
            logger.error(f"Elite Dangerous settings file does not exist: {self.settings_filepath}.")
            raise Exception(f"Elite Dangerous settings file does not exist: {self.settings_filepath}.")

        # Read graphics display settings xml file data
        logger.info(f"Reading ED graphics display settings from '{self.display_settings_filepath}'.")
        self.display_settings = self.read_settings(self.display_settings_filepath)

        # Read graphics display settings xml file data
        logger.info(f"Reading ED graphics settings from '{self.settings_filepath}'.")
        self.settings = self.read_settings(self.settings_filepath)

        # Process graphics display settings
        if self.display_settings is not None:
            self.screenwidth = self.display_settings['DisplayConfig']['ScreenWidth']
            logger.debug(f"Elite Dangerous Display Config 'ScreenWidth': {self.screenwidth}.")

            self.screenheight = self.display_settings['DisplayConfig']['ScreenHeight']
            logger.debug(f"Elite Dangerous Display Config 'ScreenHeight': {self.screenheight}.")

            self.fullscreen = self.display_settings['DisplayConfig'][
                'FullScreen']  # 0=Windowed, 1=Fullscreen, 2=Borderless
            options = ["Windowed", "Fullscreen", "Borderless"]
            self.fullscreen_str = options[int(self.fullscreen)]
            logger.debug(f"Elite Dangerous Display Config 'Fullscreen': {self.fullscreen_str}.")

            self.monitor = self.display_settings['DisplayConfig']['Monitor']
            logger.debug(f"Elite Dangerous Display Config 'Monitor': {self.monitor}.")

        if not self.fullscreen_str.upper() == "Borderless".upper():
            logger.error("Elite Dangerous is not set to BORDERLESS in graphics display settings.")
            raise Exception('Elite Dangerous is not set to BORDERLESS in graphics display settings.')

        # Process graphics settings
        if self.settings is not None:
            self.fov = self.settings['GraphicsOptions']['FOV']
            logger.debug(f"Elite Dangerous Graphics Options 'FOV': {self.fov}.")

    @staticmethod
    def read_settings(filename) -> dict:
        """ Reads an XML settings file to a Dict and returns the dict. """
        try:
            with open(filename, 'r') as file:
                my_xml = file.read()
                my_dict = xmltodict.parse(my_xml)
                return my_dict
        except OSError as e:
            logger.error(f"OS Error reading Elite Dangerous display settings file: {filename}.")
            raise Exception(f"OS Error reading Elite Dangerous display settings file: {filename}.")


def main():
    gs = EDGraphicsSettings()


if __name__ == "__main__":
    main()

"""Reading and writing of the autopilot and ship configuration."""

import json

from core import paths
from core.constants import ship_rpy_sc_50, ship_size_map
from core.logger import logger


class ConfigMixin:
    # Loads the configuration file
    #
    def read_config(self, file_name=paths.AP_CONFIG):
        s = None
        try:
            with open(file_name, "r") as fp:
                s = json.load(fp)
        except Exception as e:
            logger.warning("core/config.py read_config error :" + str(e))

        return s

    def update_config(self):
        self.write_config(self.config)

    def write_config(self, data, file_name=paths.AP_CONFIG):
        try:
            with open(file_name, "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("core/config.py write_config error:" + str(e))

    def read_ship_configs(self, filename=paths.SHIP_CONFIGS):
        """Read the user's ship configuration file."""
        s = None
        try:
            with open(filename, "r") as fp:
                s = json.load(fp)
        except Exception as e:
            logger.warning("core/config.py read_ship_configs error :" + str(e))

        return s

    def update_ship_configs(self):
        """Update the user's ship configuration file."""
        # Check if a ship and not a suit (on foot)
        if self.current_ship_type in ship_size_map:
            # Ensure ship entry exists in config
            if self.current_ship_type not in self.ship_configs["Ship_Configs"]:
                self.ship_configs["Ship_Configs"][self.current_ship_type] = {}
                logger.debug(f"Created new ship config entry for: {self.current_ship_type}")

            self.ship_configs["Ship_Configs"][self.current_ship_type]["PitchRate"] = self.pitchrate
            self.ship_configs["Ship_Configs"][self.current_ship_type]["RollRate"] = self.rollrate
            self.ship_configs["Ship_Configs"][self.current_ship_type]["YawRate"] = self.yawrate
            self.ship_configs["Ship_Configs"][self.current_ship_type]["SunPitchUp+Time"] = self.sunpitchuptime

            self.write_ship_configs(self.ship_configs)
            logger.debug(f"Saved ship config for: {self.current_ship_type}")

    def write_ship_configs(self, data, filename=paths.SHIP_CONFIGS):
        """Write the user's ship configuration file."""
        try:
            with open(filename, "w") as fp:
                json.dump(data, fp, indent=4)
        except Exception as e:
            logger.warning("core/config.py write_ship_configs error:" + str(e))

    def load_ship_configuration(self, ship_type):
        """Load ship configuration with the following priority:
        1. User's ship values from ship_configs.json file
        2. Default ship values from default_ships_cfg_sc_50.json file
        3. Hardcoded default values
        """
        # Step 1: Check if we have custom config in ship_configs.json (skip if forcing defaults)
        if ship_type in self.ship_configs["Ship_Configs"]:
            current_ship_cfg = self.ship_configs["Ship_Configs"][ship_type]
            # Check if the custom config has actual values (not just empty dict)
            if any(key in current_ship_cfg for key in ["RollRate", "PitchRate", "YawRate", "SunPitchUp+Time"]):
                # Use custom configuration - this means it's been modified and saved to ship_configs.json
                self.rollrate = current_ship_cfg.get("RollRate", 80.0)
                self.pitchrate = current_ship_cfg.get("PitchRate", 33.0)
                self.yawrate = current_ship_cfg.get("YawRate", 8.0)
                self.sunpitchuptime = current_ship_cfg.get("SunPitchUp+Time", 0.0)
                logger.info(f"Loaded your custom configuration for {ship_type} from ship_configs.json")
                return

        # Step 2: Try to load defaults from ship file
        if ship_type in ship_rpy_sc_50:
            ship_defaults = ship_rpy_sc_50[ship_type]
            # Use default configuration
            self.rollrate = ship_defaults.get("RollRate", 80.0)
            self.pitchrate = ship_defaults.get("PitchRate", 33.0)
            self.yawrate = ship_defaults.get("YawRate", 8.0)
            self.sunpitchuptime = ship_defaults.get("SunPitchUp+Time", 0.0)
            logger.info(f"Loaded default configuration for {ship_type} from default ship cfg file")
            return

        # Step 3: Use hardcoded defaults
        self.rollrate = 80.0
        self.pitchrate = 33.0
        self.yawrate = 8.0
        self.sunpitchuptime = 0.0
        logger.info(f"Using hardcoded default configuration for {ship_type}")

        # Add empty entry to ship_configs for future customization
        if ship_type not in self.ship_configs["Ship_Configs"]:
            self.ship_configs["Ship_Configs"][ship_type] = dict()

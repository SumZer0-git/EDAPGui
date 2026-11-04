"""The settings shown in the window: what they are called, where they are stored and which values are valid.

This module does not use Tk, so the logic can be tested without a window."""

import math
from dataclasses import dataclass

TAB_SHIP = "Ship"
TAB_SETTINGS = "Settings"
TAB_DEBUG = "Debug"

LOG_LEVELS = ("Debug", "Info", "Error")
DSS_BUTTONS = ("Primary", "Secondary")


@dataclass(frozen=True)
class Field:
    key: str  # unique name, also the name of the config entry unless target says otherwise
    tab: str
    kind: str  # int, float, text, hotkey, bool or choice
    label: str
    target: str = ""  # "attr:<name>" for an attribute of the autopilot, "log_level" or empty for config[key]
    lo: float = 0
    hi: float = 1000
    step: float = 1
    tip: str = ""
    setter: str = ""  # method of the autopilot that applies a changed value


FIELDS = (
    Field(
        "RollRate",
        TAB_SHIP,
        "float",
        "Roll Rate",
        "attr:rollrate",
        hi=1000,
        step=0.5,
        tip="Roll rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
    ),
    Field(
        "PitchRate",
        TAB_SHIP,
        "float",
        "Pitch Rate",
        "attr:pitchrate",
        hi=1000,
        step=0.5,
        tip="Pitch (up/down) rate your ship has in deg/sec. Higher the number the more maneuverable the ship.",
    ),
    Field(
        "YawRate",
        TAB_SHIP,
        "float",
        "Yaw Rate",
        "attr:yawrate",
        hi=1000,
        step=0.5,
        tip="Yaw rate (rudder) your ship has in deg/sec. Higher the number the more maneuverable the ship.",
    ),
    Field(
        "SunPitchUp+Time",
        TAB_SHIP,
        "float",
        "SunPitchUp +/- Time",
        "attr:sunpitchuptime",
        lo=-100,
        hi=100,
        step=0.5,
        tip="This field are for ship that tend to overheat. \nProviding 1-2 more seconds of Pitch up when avoiding the Sun \nwill overcome this problem.",
    ),
    Field(
        "SunBrightThreshold",
        TAB_SETTINGS,
        "int",
        "Sun Bright Threshold",
        hi=255,
        tip="The low level for brightness detection, \nrange 0-255, want to mask out darker items",
    ),
    Field(
        "NavAlignTries",
        TAB_SETTINGS,
        "int",
        "Nav Align Tries",
        tip="How many attempts the ap should make at alignment.",
    ),
    Field("JumpTries", TAB_SETTINGS, "int", "Jump Tries", tip="How many attempts the ap should make to jump."),
    Field("DockingRetries", TAB_SETTINGS, "int", "Docking Retries", tip="How many attempts to make to dock."),
    Field(
        "WaitForAutoDockTimer",
        TAB_SETTINGS,
        "int",
        "Wait For Autodock",
        tip="After docking granted, \nwait this amount of time for us to get docked with autodocking",
    ),
    Field(
        "EnableRandomness",
        TAB_SETTINGS,
        "bool",
        "Enable Randomness",
        setter="set_randomness",
        tip="Adds some random sleep times at specific places.",
    ),
    Field(
        "ActivateEliteEachKey",
        TAB_SETTINGS,
        "bool",
        "Activate Elite window for each key",
        setter="set_activate_elite_eachkey",
        tip="Brings the Elite window to the front before each key or group of keys.",
    ),
    Field("AutomaticLogout", TAB_SETTINGS, "bool", "Automatic logout", setter="set_automatic_logout"),
    Field(
        "RefuelThreshold",
        TAB_SETTINGS,
        "int",
        "Refuel Threshold",
        tip="If fuel level get below this level, \nit will attempt refuel.",
    ),
    Field(
        "FuelScoopTimeOut",
        TAB_SETTINGS,
        "int",
        "Scoop Timeout",
        tip="Number of second to wait for full tank, \nmight mean we are not scooping well or got a small scooper",
    ),
    Field(
        "FuelThreasholdAbortAP",
        TAB_SETTINGS,
        "int",
        "Fuel Threshold Abort",
        tip="Level at which AP will terminate, \nbecause we are not scooping well.",
    ),
    Field(
        "DSSButton",
        TAB_SETTINGS,
        "choice",
        "DSS Button",
        tip="Fire button that is used for the detailed surface scan.",
    ),
    Field(
        "HotKey_StartTravel",
        TAB_SETTINGS,
        "hotkey",
        "Start Travel Assist",
        tip="Hotkey that starts Travel Assist. Applied after a restart.",
    ),
    Field(
        "HotKey_StopAllAssists",
        TAB_SETTINGS,
        "hotkey",
        "Stop All",
        tip="Hotkey that stops all assists. Applied after a restart.",
    ),
    Field(
        "OverlayTextEnable",
        TAB_SETTINGS,
        "bool",
        "Enable (requires restart)",
        setter="set_overlay",
    ),
    Field(
        "OverlayTextXOffset",
        TAB_SETTINGS,
        "int",
        "X Offset",
        hi=3000,
        tip="Offset left the screen to start place overlay text.",
    ),
    Field(
        "OverlayTextYOffset",
        TAB_SETTINGS,
        "int",
        "Y Offset",
        hi=3000,
        tip="Offset down the screen to start place overlay text.",
    ),
    Field("OverlayTextFontSize", TAB_SETTINGS, "int", "Font Size", lo=1, hi=200, tip="Font size of the overlay."),
    Field("VoiceEnable", TAB_SETTINGS, "bool", "Enable voice", setter="set_voice"),
    Field("log_level", TAB_DEBUG, "choice", "Log level", "log_level"),
    Field("DebugOverlay", TAB_DEBUG, "bool", "Debug Overlay"),
    Field("Enable_CV_View", TAB_DEBUG, "bool", "Enable CV View", setter="set_cv_view"),
    Field("TCEDestinationFilepath", TAB_DEBUG, "text", "TCE Dest json"),
)

FIELDS_BY_KEY = {field.key: field for field in FIELDS}


def fields_of(tab):
    return [field for field in FIELDS if field.tab == tab]


def _log_level(config):
    if config["LogDEBUG"]:
        return "Debug"
    if config["LogINFO"]:
        return "Info"
    return "Error"


def read(field, ap):
    """Current value of the field in the autopilot: text for entries, bool for checkboxes."""
    if field.target.startswith("attr:"):
        value = getattr(ap, field.target[5:])
    elif field.target == "log_level":
        return _log_level(ap.config)
    else:
        value = ap.config[field.key]
    if field.kind == "bool":
        return bool(value)
    if field.kind == "int":
        return str(int(value))
    if field.kind == "float":
        return str(float(value))
    return str(value)


def parse(field, raw):
    """Convert and check the value typed into the window. Raises ValueError if it is not valid."""
    if field.kind == "bool":
        return bool(raw)
    if field.kind == "choice":
        choices = LOG_LEVELS if field.target == "log_level" else DSS_BUTTONS
        if raw not in choices:
            raise ValueError(f"{field.label}: unknown choice {raw!r}")
        return raw
    text = str(raw).strip()
    if field.kind in ("int", "float"):
        value = int(text) if field.kind == "int" else float(text)
        if not math.isfinite(value) or not field.lo <= value <= field.hi:
            raise ValueError(f"{field.label}: {text} is outside {field.lo} to {field.hi}")
        return value
    if field.kind == "hotkey":
        if not text:
            raise ValueError(f"{field.label}: no key entered")
        try:
            import keyboard

            keyboard.parse_hotkey_combinations(text)
        except Exception as e:
            raise ValueError(f"{field.label}: {text!r} is not a valid hotkey") from e
    return text


def write(field, ap, value, window_pos=(0, 0)):
    """Apply a parsed value to the autopilot. Persisting the config files is up to the caller."""
    if field.target.startswith("attr:"):
        setattr(ap, field.target[5:], value)
        return
    if field.target == "log_level":
        {"Debug": ap.set_log_debug, "Info": ap.set_log_info, "Error": ap.set_log_error}[value](True)
        return
    ap.config[field.key] = value
    if field.key == "ActivateEliteEachKey":
        ap.keys.activate_window = value
    if field.setter == "set_cv_view":
        ap.set_cv_view(value, *window_pos)
    elif field.setter:
        getattr(ap, field.setter)(value)

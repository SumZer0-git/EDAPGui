"""The settings shown in the window: what they are called, where they are stored and which values are valid.

This module does not use Tk, so the logic can be tested without a window."""

import math
from dataclasses import dataclass

TAB_SHIP = "Ship"
TAB_SETTINGS = "Settings"
TAB_OVERLAY = "Overlay"
TAB_DEBUG = "Debug"

LOG_LEVELS = ("Debug", "Info", "Error")
DSS_BUTTONS = ("Primary", "Secondary")
OVERLAY_ANCHORS = ("Top left", "Top right", "Bottom left", "Bottom right")
OVERLAY_POSITION_UNITS = ("Pixels", "Percent")
OVERLAY_FONT_WEIGHTS = ("Light", "Regular", "Medium", "SemiBold", "Bold")

# Overlay lines in their default order, each with the setting that shows or hides it.
OVERLAY_LINES = (
    ("mode", "OverlayShowMode"),
    ("status", "OverlayShowStatus"),
    ("ship", "OverlayShowShip"),
    ("fuel", "OverlayShowFuel"),
    ("system", "OverlayShowSystem"),
    ("destination", "OverlayShowDestination"),
    ("next_star", "OverlayShowNextStar"),
    ("jumps", "OverlayShowJumps"),
    ("jumps_bar", "OverlayShowJumpsBar"),
    ("eta", "OverlayShowETA"),
    ("distance", "OverlayShowDistance"),
    ("distance_bar", "OverlayShowDistanceBar"),
)
OVERLAY_LINE_SETTINGS = dict(OVERLAY_LINES)
DEFAULT_OVERLAY_LINE_ORDER = tuple(key for key, _setting in OVERLAY_LINES)


def normalize_overlay_line_order(order) -> list[str]:
    """Known overlay lines in the given order; unknown entries are dropped and missing lines appended."""
    if isinstance(order, str):
        order = [key.strip() for key in order.split(",")]
    elif not isinstance(order, (list, tuple)):
        order = []
    result = []
    for key in order:
        if key in OVERLAY_LINE_SETTINGS and key not in result:
            result.append(key)
    return result + [key for key in DEFAULT_OVERLAY_LINE_ORDER if key not in result]


def move_overlay_line(order, key, step: int) -> list[str]:
    """Move one overlay line up (step -1) or down (step 1) within the order."""
    order = normalize_overlay_line_order(order)
    index = order.index(key)
    target = index + step
    if 0 <= target < len(order):
        order[index], order[target] = order[target], order[index]
    return order


@dataclass(frozen=True)
class Field:
    key: str  # unique name, also the name of the config entry unless target says otherwise
    tab: str
    kind: str  # int, float, text, hotkey, bool, choice or order
    label: str
    target: str = ""  # "attr:<name>" for an attribute of the autopilot, "log_level" or empty for config[key]
    lo: float = 0
    hi: float = 1000
    step: float = 1
    tip: str = ""
    setter: str = ""  # method of the autopilot that applies a changed value
    choices: tuple[str, ...] = ()


FIELDS = (
    Field(
        "Language",
        TAB_SETTINGS,
        "language",
        "Game language",
        setter="set_language",
        tip="Auto follows the game journal, including after a game restart. This does not translate the application.",
    ),
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
        TAB_OVERLAY,
        "bool",
        "Enable overlay",
        setter="set_overlay",
    ),
    Field(
        "OverlayPositionAnchor",
        TAB_OVERLAY,
        "choice",
        "Anchor",
        choices=OVERLAY_ANCHORS,
        tip="Corner of the game window used as the overlay position anchor.",
    ),
    Field(
        "OverlayPositionUnit",
        TAB_OVERLAY,
        "choice",
        "Position units",
        choices=OVERLAY_POSITION_UNITS,
        tip="Use pixel distances or percentages of the game window.",
    ),
    Field(
        "OverlayTextXOffset",
        TAB_OVERLAY,
        "int",
        "Horizontal offset",
        hi=10000,
        tip="Distance from the selected left or right anchor edge.",
    ),
    Field(
        "OverlayTextYOffset",
        TAB_OVERLAY,
        "int",
        "Vertical offset",
        hi=10000,
        tip="Distance from the selected top or bottom anchor edge.",
    ),
    Field(
        "OverlayTextFontSize",
        TAB_OVERLAY,
        "int",
        "Font size (pt)",
        lo=1,
        hi=200,
        tip="Font size in points. Follows the monitor's Windows display scaling, not the game resolution.",
    ),
    Field(
        "OverlayTextFontWeight",
        TAB_OVERLAY,
        "choice",
        "Font weight",
        choices=OVERLAY_FONT_WEIGHTS,
        tip="Select the bundled Rajdhani font weight used by the overlay.",
    ),
    Field(
        "OverlayPanelOpacity",
        TAB_OVERLAY,
        "int",
        "Panel opacity (%)",
        hi=100,
        tip="Opacity of the background behind the status text.",
    ),
    Field(
        "OverlayCaptureVisible",
        TAB_OVERLAY,
        "bool",
        "Show in screenshots and recordings",
        tip="Allow desktop and window captures to include the overlay. Whether a capture tool shows it depends on "
        "its capture method; in-game captures such as Elite's F10 screenshots or OBS Game Capture never include it.",
    ),
    Field(
        "OverlayShowMode",
        TAB_OVERLAY,
        "bool",
        "AP mode",
        tip="Show the current assist mode.",
    ),
    Field(
        "OverlayShowStatus",
        TAB_OVERLAY,
        "bool",
        "AP status",
        tip="Show the current autopilot status.",
    ),
    Field(
        "OverlayShowShip",
        TAB_OVERLAY,
        "bool",
        "Ship status",
        tip="Show the current ship state.",
    ),
    Field(
        "OverlayShowSystem",
        TAB_OVERLAY,
        "bool",
        "Current system",
        tip="Show the current system and star class.",
    ),
    Field(
        "OverlayShowJumps",
        TAB_OVERLAY,
        "bool",
        "Jump count",
        tip="Show the current and total number of jumps.",
    ),
    Field(
        "OverlayShowJumpsBar",
        TAB_OVERLAY,
        "bool",
        "Jump progress bar",
        tip="Show a progress bar of the completed jumps on the route.",
    ),
    Field(
        "OverlayShowETA",
        TAB_OVERLAY,
        "bool",
        "Estimated arrival",
        tip="Show approximate remaining system travel time and arrival in your PC's local time.",
    ),
    Field(
        "OverlayShowDistance",
        TAB_OVERLAY,
        "bool",
        "Route distance",
        tip="Show the planned route distance remaining and total, when all route coordinates are available.",
    ),
    Field(
        "OverlayShowDistanceBar",
        TAB_OVERLAY,
        "bool",
        "Distance progress bar",
        tip="Show a progress bar of the travelled route distance, when all route coordinates are available.",
    ),
    Field(
        "OverlayShowFuel",
        TAB_OVERLAY,
        "bool",
        "Fuel",
        tip="Show the main fuel tank level, colored against the refuel and abort thresholds, and active fuel scooping.",
    ),
    Field(
        "OverlayShowDestination",
        TAB_OVERLAY,
        "bool",
        "Destination",
        tip="Show the final system of the plotted route.",
    ),
    Field(
        "OverlayShowNextStar",
        TAB_OVERLAY,
        "bool",
        "Next star",
        tip="Show the star class of the next route system and whether it can be fuel scooped.",
    ),
    Field(
        "OverlayLineOrder",
        TAB_OVERLAY,
        "order",
        "Line order",
        tip="Order of the overlay lines; hidden lines are skipped.",
    ),
    Field("VoiceEnable", TAB_SETTINGS, "bool", "Enable voice", setter="set_voice"),
    Field("log_level", TAB_DEBUG, "choice", "Log level", "log_level"),
    Field("DebugOverlay", TAB_DEBUG, "bool", "Debug Overlay", setter="set_debug_overlay"),
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
    if field.key == "Language":
        return ap.config.get("Language", "auto")
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
    if field.kind == "order":
        return ",".join(normalize_overlay_line_order(value))
    return str(value)


def parse(field, raw):
    """Convert and check the value typed into the window. Raises ValueError if it is not valid."""
    if field.kind == "bool":
        return bool(raw)
    if field.kind == "language":
        if not isinstance(raw, str) or not raw or not all(c.isascii() and (c.isalnum() or c in "_-") for c in raw):
            raise ValueError("Game language: invalid language code")
        return raw
    if field.kind == "order":
        return normalize_overlay_line_order(raw)
    if field.kind == "choice":
        choices = field.choices or (LOG_LEVELS if field.target == "log_level" else DSS_BUTTONS)
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


def validate_tab(tab, values):
    """Validate constraints that depend on multiple settings in a tab."""
    if tab == TAB_OVERLAY and values["OverlayPositionUnit"] == "Percent":
        for key in ("OverlayTextXOffset", "OverlayTextYOffset"):
            if values[key] > 100:
                raise ValueError(f"{FIELDS_BY_KEY[key].label}: percent offsets must be between 0 and 100")


def convert_overlay_offsets(values, previous, screen_width, screen_height):
    """Convert unchanged offsets when switching units, keeping their screen distance stable."""
    old_unit = previous.get("OverlayPositionUnit")
    new_unit = values["OverlayPositionUnit"]
    if old_unit not in OVERLAY_POSITION_UNITS or old_unit == new_unit:
        return ()

    dimensions = {
        "OverlayTextXOffset": screen_width,
        "OverlayTextYOffset": screen_height,
    }
    if any(extent <= 0 for extent in dimensions.values()):
        raise ValueError("Cannot convert overlay offsets without valid screen dimensions")

    converted_keys = []
    for key, extent in dimensions.items():
        if values[key] != previous.get(key):
            continue
        if old_unit == "Pixels":
            values[key] = round(values[key] * 100 / extent)
        else:
            values[key] = round(values[key] * extent / 100)
        converted_keys.append(key)
    return tuple(converted_keys)


def write(field, ap, value, window_pos=(0, 0)):
    """Apply a parsed value to the autopilot. Persisting the config files is up to the caller."""
    if field.key == "Language":
        ap.set_language(value)
        return
    if field.target.startswith("attr:"):
        setattr(ap, field.target[5:], value)
        return
    if field.target == "log_level":
        {"Debug": ap.set_log_debug, "Info": ap.set_log_info, "Error": ap.set_log_error}[value](True)
        return
    ap.config[field.key] = value
    if field.key == "ActivateEliteEachKey":
        ap.keys.activate_window = value
    if field.setter:
        getattr(ap, field.setter)(value)

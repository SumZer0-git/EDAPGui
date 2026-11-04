"""The Elite Dangerous actions EDAP needs, and the rules used to choose keys for them."""

from __future__ import annotations

from game.binds_files import GENERAL, SHIP

# In order of importance: if two of these actions share a key, the later one is the one that gets moved.
REQUIRED_ACTIONS: dict[str, str] = {
    "YawLeftButton": SHIP,
    "YawRightButton": SHIP,
    "RollLeftButton": SHIP,
    "RollRightButton": SHIP,
    "PitchUpButton": SHIP,
    "PitchDownButton": SHIP,
    "UpThrustButton": SHIP,
    "SetSpeedZero": SHIP,
    "SetSpeed50": SHIP,
    "SetSpeed75": SHIP,
    "SetSpeed100": SHIP,
    "HyperSuperCombination": SHIP,
    "Supercruise": SHIP,
    "UseBoostJuice": SHIP,
    "TargetNextRouteSystem": SHIP,
    "LandingGearToggle": SHIP,
    "PrimaryFire": SHIP,
    "SecondaryFire": SHIP,
    "DeployHardpointToggle": SHIP,
    "IncreaseEnginesPower": SHIP,
    "IncreaseWeaponsPower": SHIP,
    "IncreaseSystemsPower": SHIP,
    "HeadLookReset": SHIP,
    "UIFocus": SHIP,
    "CycleNextPanel": SHIP,
    "GalaxyMapOpen": SHIP,
    "SystemMapOpen": SHIP,
    "UI_Up": GENERAL,
    "UI_Down": GENERAL,
    "UI_Left": GENERAL,
    "UI_Right": GENERAL,
    "UI_Select": GENERAL,
    "UI_Back": GENERAL,
    "CamZoomIn": GENERAL,  # Galaxy map zoom in
}

# Keys EDAP itself listens to. They are named the same in every keyboard layout.
EDAP_HOTKEYS = ("Key_End", "Key_Insert", "Key_PageUp", "Key_Home")

# Keys proposed for actions the shipped presets leave unbound: single keys without modifiers, no letters or
# punctuation, because those are named differently depending on the keyboard layout.
PREFERRED_KEYS: dict[str, tuple[str, ...]] = {
    "PitchUpButton": ("Key_Numpad_8",),
    "PitchDownButton": ("Key_Numpad_2",),
    "RollLeftButton": ("Key_Numpad_4",),
    "RollRightButton": ("Key_Numpad_6",),
    "SetSpeed50": ("Key_Numpad_5",),
    "SetSpeed100": ("Key_Numpad_Add",),
}
FALLBACK_KEYS = (
    "Key_Numpad_8",
    "Key_Numpad_2",
    "Key_Numpad_4",
    "Key_Numpad_6",
    "Key_Numpad_5",
    "Key_Numpad_7",
    "Key_Numpad_9",
    "Key_Numpad_1",
    "Key_Numpad_3",
    "Key_Numpad_0",
    "Key_Numpad_Add",
    "Key_Numpad_Subtract",
    "Key_Numpad_Multiply",
    "Key_Numpad_Divide",
    "Key_Numpad_Decimal",
    "Key_F5",
    "Key_F6",
    "Key_F7",
    "Key_F8",
    "Key_F9",
    "Key_F10",
    "Key_F11",
    "Key_F12",
)

# Actions of other game modes (on foot, SRV, camera suite). Elite allows the same key there as in the ship.
OTHER_MODE_PREFIXES = (
    "Humanoid",
    "Buggy",
    "Vanity",
    "FixCamera",
    "FreeCam",
    "MoveFreeCam",
    "PlacementCam",
    "MovePlacementCam",
    "StoreCam",
    "Cam",
    "ToggleFreeCam",
    "CommanderCreator",
    "RotateSettlement",
    "PlaceSettlement",
    "ChangeConstruction",
)


def is_other_mode_action(name: str) -> bool:
    return name.startswith(OTHER_MODE_PREFIXES) or name.endswith("_Buggy")


def category_of(action: str) -> str:
    return REQUIRED_ACTIONS.get(action, SHIP)

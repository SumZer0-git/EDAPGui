"""Finds gaps and conflicts in the keybindings EDAP needs and writes the fixes into the .binds files.

Existing bindings are only touched for real conflicts and only when the caller applies that change. Gaps are filled
with the key of the default presets Frontier ships; if those have none, with a single key without modifiers.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from controls.directinput import key_name_for, scancode_for
from game.binds_files import active_binds_files
from game.keybind_defaults import DEFAULT_KEYS, SHARED_IN_DEFAULTS
from game.keybind_spec import (
    EDAP_HOTKEYS,
    FALLBACK_KEYS,
    PREFERRED_KEYS,
    REQUIRED_ACTIONS,
    is_other_mode_action,
)

GAME_PROCESS = "EliteDangerous64.exe"
SLOTS = ("Primary", "Secondary")

# A key as scancode plus the scancodes of its modifiers; independent of the keyboard layout
Combo = tuple[int, tuple[int, ...]]

GAP = "gap"  # No keyboard key, a free slot gets one
REPLACE = "replace"  # No keyboard key and no free slot, a slot of another device would be overwritten
CONFLICT = "conflict"  # The key is shared with an action that must not share it, the key gets replaced

HOTKEY = "hotkey"  # The key is one of the EDAP hotkeys
UNKNOWN_KEY = "unknown_key"  # The key name is not known for the keyboard layout of the file
NO_KEY_FOUND = "no_key_found"  # No free key was found


@dataclass(frozen=True)
class Slot:
    device: str
    key: str
    mods: tuple[str, ...]

    @property
    def is_keyboard(self) -> bool:
        return self.device == "Keyboard"

    @property
    def is_free(self) -> bool:
        return self.device in ("", "{NoDevice}")

    def describe(self) -> str:
        if self.is_free:
            return ""
        if self.is_keyboard:
            return "+".join((*self.mods, self.key))
        return f"{self.device}: {self.key}"


class BindsFile:
    """A .binds file, kept as text so that a fix changes nothing but the touched slots."""

    def __init__(self, path: Path, text: str, bom: bool = False) -> None:
        self.path = path
        self.text = text
        self.bom = bom
        self.newline = "\r\n" if "\r\n" in text else "\n"
        root = ET.fromstring(text.encode("utf-8"))
        self.layout = (root.findtext("KeyboardLayout") or "").strip() or None
        self.actions: dict[str, dict[str, Slot]] = {}
        for item in root:
            slots = {}
            for tag in SLOTS:
                element = item.find(tag)
                if element is not None:
                    mods = tuple(m.attrib.get("Key", "") for m in element.findall("Modifier"))
                    slots[tag] = Slot(element.attrib.get("Device", "").strip(), element.attrib.get("Key", ""), mods)
            if slots:
                self.actions[item.tag] = slots

    @classmethod
    def load(cls, path: Path) -> BindsFile:
        data = path.read_bytes()
        bom = data.startswith(b"\xef\xbb\xbf")
        return cls(path, data.decode("utf-8-sig"), bom)

    def combo(self, slot: Slot) -> Combo | None:
        try:
            mods = tuple(sorted(scancode_for(m, self.layout) for m in slot.mods))
            return scancode_for(slot.key, self.layout), mods
        except KeyError:
            return None

    def key_name(self, combo: Combo) -> str | None:
        return key_name_for(combo[0], self.layout)

    def describe(self, combo: Combo) -> str:
        names = [key_name_for(code, self.layout) or f"?{code}" for code in (*combo[1], combo[0])]
        return "+".join(names)

    def effective_slot(self, action: str) -> tuple[str, Slot] | None:
        """The keyboard slot EDAP reads: the secondary one if it is a keyboard key, else the primary one."""
        slots = self.actions.get(action, {})
        for tag in reversed(SLOTS):
            slot = slots.get(tag)
            if slot is not None and slot.is_keyboard:
                return tag, slot
        return None

    def keyboard_combos(self) -> dict[Combo, set[str]]:
        used: dict[Combo, set[str]] = {}
        for action, slots in self.actions.items():
            for slot in slots.values():
                combo = self.combo(slot) if slot.is_keyboard else None
                if combo is not None:
                    used.setdefault(combo, set()).add(action)
        return used


@dataclass
class Change:
    kind: str
    action: str
    category: str
    file: BindsFile
    slot: str
    old: str
    combo: Combo
    source: str  # "default", "preferred" or "fallback"
    partners: tuple[str, ...] = ()
    current: dict[str, str] = field(default_factory=dict)  # What each slot holds now, for display

    @property
    def new(self) -> str:
        return self.file.describe(self.combo)


@dataclass
class Note:
    kind: str
    action: str
    category: str
    file: BindsFile
    detail: str = ""


@dataclass
class Plan:
    changes: list[Change] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)


def sharing_allowed(action: str, other: str) -> bool:
    """Whether the game itself lets these two actions use the same key (default presets, other game modes)."""
    return (
        is_other_mode_action(other)
        or other in SHARED_IN_DEFAULTS.get(action, frozenset())
        or action in SHARED_IN_DEFAULTS.get(other, frozenset())
    )


def _conflicts(used: dict[Combo, set[str]], action: str, combo: Combo) -> list[str]:
    return sorted(o for o in used.get(combo, ()) if o != action and not sharing_allowed(action, o))


def _candidates(action: str, file: BindsFile):
    """Keys to try for an action, best first, as (source, combo)."""
    sources = [("default", key, mods) for key, mods in DEFAULT_KEYS.get(action, ())]
    sources += [("preferred", key, ()) for key in PREFERRED_KEYS.get(action, ())]
    sources += [("fallback", key, ()) for key in FALLBACK_KEYS]
    for source, key, mods in sources:
        combo = (scancode_for(key), tuple(sorted(scancode_for(m) for m in mods)))
        name = file.key_name(combo)
        if name is None or any(file.key_name((m, ())) is None for m in combo[1]) or name in EDAP_HOTKEYS:
            continue
        yield source, combo


def build_plan(files: dict[str, BindsFile]) -> Plan:
    """Compares the active .binds file of each category with what EDAP needs. Nothing is written."""
    plan = Plan()
    used = {id(file): file.keyboard_combos() for file in files.values()}
    order = list(REQUIRED_ACTIONS)

    for action, category in REQUIRED_ACTIONS.items():
        file = files.get(category)
        if file is None:
            continue
        taken = used[id(file)]
        current = file.effective_slot(action)
        slots = file.actions.get(action, {})

        if current is not None:
            slot_name, slot = current
            combo = file.combo(slot)
            if combo is None:
                plan.notes.append(Note(UNKNOWN_KEY, action, category, file, slot.describe()))
                continue
            if not combo[1] and file.key_name(combo) in EDAP_HOTKEYS:
                plan.notes.append(Note(HOTKEY, action, category, file, slot.describe()))
            partners = _conflicts(taken, action, combo)
            # Of two EDAP actions that clash, the less important one is moved, so it is only reported once
            movers = [p for p in partners if not (p in REQUIRED_ACTIONS and order.index(p) > order.index(action))]
            if not movers:
                continue
            kind, old = CONFLICT, slot.describe()
            partners = movers
        else:
            free = [tag for tag in SLOTS if tag not in slots or slots[tag].is_free]
            slot_name = free[0] if free else SLOTS[-1]
            kind = GAP if free else REPLACE
            old = "" if free else slots[slot_name].describe()
            combo, partners = None, []

        chosen = next(((s, c) for s, c in _candidates(action, file) if not _conflicts(taken, action, c)), None)
        if chosen is None:
            plan.notes.append(Note(NO_KEY_FOUND, action, category, file))
            continue
        source, new_combo = chosen
        if combo is not None:
            taken[combo].discard(action)
        taken.setdefault(new_combo, set()).add(action)
        shown = {tag: slots[tag].describe() for tag in SLOTS if tag in slots}
        plan.changes.append(
            Change(kind, action, category, file, slot_name, old, new_combo, source, tuple(partners), shown)
        )
    return plan


def _slot_xml(tag: str, key: str, mods: list[str], newline: str) -> str:
    if not mods:
        return f'\t\t<{tag} Device="Keyboard" Key="{key}" />'
    lines = [f'\t\t<{tag} Device="Keyboard" Key="{key}">']
    lines += [f'\t\t\t<Modifier Device="Keyboard" Key="{mod}" />' for mod in mods]
    lines.append(f"\t\t</{tag}>")
    return newline.join(lines)


def _patch(file: BindsFile, text: str, change: Change) -> str:
    key = file.key_name((change.combo[0], ()))
    mods = [file.key_name((code, ())) for code in change.combo[1]]
    new_slot = _slot_xml(change.slot, key, mods, file.newline)
    name = re.escape(change.action)
    block = re.search(rf"(?P<head>[ \t]*<{name}>\r?\n)(?P<body>.*?)(?P<tail>[ \t]*</{name}>)", text, re.S)

    if block is None:
        other = SLOTS[0] if change.slot == SLOTS[1] else SLOTS[1]
        empty = f'\t\t<{other} Device="{{NoDevice}}" Key="" />'
        ordered = [new_slot, empty] if change.slot == SLOTS[0] else [empty, new_slot]
        lines = [f"\t<{change.action}>", *ordered, f"\t</{change.action}>"]
        end = text.rindex("</Root>")
        return text[:end] + file.newline.join(lines) + file.newline + text[end:]

    body = block["body"]
    slot_pattern = re.compile(rf"[ \t]*<{change.slot}\b(?:[^>]*/>|[^>]*>.*?</{change.slot}>)", re.S)
    if slot_pattern.search(body):
        body = slot_pattern.sub(lambda _: new_slot, body, count=1)
    elif change.slot == SLOTS[0]:
        body = new_slot + file.newline + body
    else:
        body = body + new_slot + file.newline
    return text[: block.start("body")] + body + text[block.end("body") :]


def apply_changes(file: BindsFile, changes: list[Change]) -> str:
    """The text of the file with the changes applied. Raises if the result does not hold the new keys."""
    text = file.text
    for change in changes:
        text = _patch(file, text, change)
    result = BindsFile(file.path, text, file.bom)
    for change in changes:
        current = result.effective_slot(change.action)
        if current is None or result.combo(current[1]) != change.combo:
            raise ValueError(f"Could not write the key for {change.action} into {file.path.name}.")
    return text


def write_file(file: BindsFile, text: str) -> Path:
    """Writes the new text and returns the path of the backup of the old file."""
    backup = file.path.with_name(f"{file.path.name}.edap-{time.strftime('%Y%m%d-%H%M%S')}.backup")
    shutil.copy2(file.path, backup)
    temp = file.path.with_name(file.path.name + ".tmp")
    temp.write_bytes((b"\xef\xbb\xbf" if file.bom else b"") + text.encode("utf-8"))
    os.replace(temp, file.path)
    return backup


def load_active_files(folder: Path | None = None) -> dict[str, BindsFile]:
    """The BindsFile of each control category, according to StartPreset.4.start. Empty if that is not known."""
    loaded: dict[Path, BindsFile] = {}
    files = {}
    for category, path in active_binds_files(folder).items():
        if path not in loaded:
            loaded[path] = BindsFile.load(path)
        files[category] = loaded[path]
    return files


def is_game_running() -> bool:
    try:
        # tasklist prints in the OEM code page; the process name is plain ASCII, so decode leniently
        output = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/NH"], capture_output=True, timeout=20
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return GAME_PROCESS.lower() in (output or b"").decode("latin-1").lower()

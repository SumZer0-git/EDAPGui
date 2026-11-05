"""Editable route definitions, independent of Tk and runtime progress."""

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.logger import logger
from routines.waypoints import EDWayPoint


def new_waypoint():
    return {
        "Id": uuid4().hex,
        "SystemName": "",
        "StationName": "",
        "GalaxyBookmarkType": "",
        "GalaxyBookmarkNumber": 0,
        "SystemBookmarkType": "",
        "SystemBookmarkNumber": 0,
        "SellCommodities": {},
        "BuyCommodities": {},
        "UpdateCommodityCount": True,
        "FleetCarrierTransfer": False,
        "Enabled": True,
    }


@dataclass(frozen=True)
class RouteIssue:
    severity: str
    index: int | None
    field: str
    message: str

    def describe(self):
        location = "Global list" if self.index is None else f"Waypoint {self.index + 1}"
        return f"{self.severity.upper()}: {location}: {self.message}"


def entry_issues(entry, index=0, global_list=False):
    issues = []

    def add(severity, field, message):
        issues.append(RouteIssue(severity, None if global_list else index, field, message))

    for field in ("BuyCommodities",) if global_list else ("BuyCommodities", "SellCommodities"):
        for name, quantity in entry[field].items():
            if not isinstance(name, str) or not name.strip() or name != name.strip():
                add("error", field, "Commodity names must be non-empty with no surrounding spaces.")
            if type(quantity) is not int or quantity < 0:
                add("error", field, f"{name}: quantity must be a non-negative whole number.")
    if global_list:
        return issues
    if not entry["SystemName"].strip():
        add("error", "SystemName", "Enter a system name.")
    if entry["SystemName"].strip().upper() == "REPEAT":
        add("error", "SystemName", "REPEAT is no longer a destination; use Route repeat.")
    for prefix in ("Galaxy", "System"):
        field = f"{prefix}BookmarkType"
        kind = entry[field]
        allowed = ("fav", "bod", "sta", "set", "sys") if prefix == "Galaxy" else ("fav", "bod", "sta", "set", "nav")
        if kind and not kind.lower().startswith(allowed):
            add("error", field, f"Unknown {prefix.lower()} bookmark type.")
        number = entry[f"{prefix}BookmarkNumber"]
        if type(number) is not int or number < 0 or (kind and number < 1) or (not kind and number != 0):
            add("error", f"{prefix}BookmarkNumber", "Bookmark position must be 1 or higher with a type, otherwise 0.")
    return issues


class RouteDocument:
    def __init__(self):
        self.filename = None
        self.source_version = 2
        self.data = {
            "version": 2,
            "name": "New route",
            "Repeat": False,
            "RepeatLimit": None,
            "GlobalShoppingList": {"BuyCommodities": {}, "UpdateCommodityCount": True, "Enabled": False},
            "waypoints": [],
        }
        self.saved = copy.deepcopy(self.data)
        self.load_notes = []

    @property
    def dirty(self):
        # Dictionary equality ignores commodity order, which determines trade priority.
        return bool(self.load_notes) or json.dumps(self.data) != json.dumps(self.saved)

    @classmethod
    def load(cls, filename):
        filename = Path(filename)
        try:
            with filename.open(encoding="utf-8-sig") as file:
                raw = json.load(file)
        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(f"Cannot open route for editing: {error}") from error
        if (
            not isinstance(raw, dict)
            or type(raw.get("version")) is not int
            or raw["version"] != 2
            or type(raw.get("Repeat")) is not bool
            or "RepeatLimit" not in raw
            or raw["RepeatLimit"] is not None
        ):
            raise ValueError(
                "Expected the current v2 format. Use Import legacy JSON for older routes. "
                "RepeatLimit currently supports only null."
            )
        entries = raw.get("waypoints")
        if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise ValueError("Cannot edit this route: waypoints must be JSON objects in a list.")
        document = cls()
        document.filename = filename.resolve()
        document.data["Repeat"] = raw["Repeat"]
        if isinstance(raw.get("name"), str) and raw["name"].strip():
            document.data["name"] = raw["name"]
        else:
            document.data["name"] = filename.stem
            document.load_notes.append("Missing/invalid route name: filename used for the editable draft.")
        ids = set()
        for index, item in enumerate([raw.get("GlobalShoppingList", {}), *entries]):
            global_list = index == 0
            defaults = document.data["GlobalShoppingList"] if global_list else new_waypoint()
            if not isinstance(item, dict):
                raise ValueError("Cannot edit this route: GlobalShoppingList must be an object.")
            if "Skip" in item:
                raise ValueError("Old Skip fields are not supported. Use Import legacy JSON.")
            if "Completed" in item:
                document.load_notes.append(
                    f"Entry {index}: obsolete Completed field omitted from the editable definition."
                )
            entry = {}
            for field, default in defaults.items():
                if field not in item:
                    document.load_notes.append(
                        f"{'Global list' if global_list else f'Waypoint {index}'}: missing {field}; review its default."
                    )
                value = copy.deepcopy(item.get(field, default))
                if isinstance(default, dict):
                    if not isinstance(value, dict):
                        raise ValueError(f"Cannot edit {field}: expected a commodity object.")
                elif isinstance(default, str) and not isinstance(value, str):
                    document.load_notes.append(
                        f"Entry {index}: {field} expected text, found {value!r}; converted to text for review."
                    )
                    value = str(value)
                elif type(default) is bool and type(value) is not bool:
                    document.load_notes.append(
                        f"Entry {index}: {field} expected true/false, found {value!r}; default {default} needs review."
                    )
                    value = default
                entry[field] = value
            if not global_list:
                if not entry["Id"].strip() or entry["Id"] == "GlobalShoppingList" or entry["Id"] in ids:
                    entry["Id"] = new_waypoint()["Id"]
                    document.load_notes.append(f"Waypoint {index}: invalid/duplicate ID replaced for editing.")
                ids.add(entry["Id"])
                document.data["waypoints"].append(entry)
            else:
                document.data["GlobalShoppingList"] = entry
        document.saved = copy.deepcopy(document.data)
        return document

    @classmethod
    def import_legacy(cls, filename):
        """Import only destinations and trade requests into a new unsaved draft."""
        try:
            with Path(filename).open(encoding="utf-8-sig") as file:
                raw = json.load(file)
        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(f"Cannot import legacy route: {error}") from error
        if not isinstance(raw, dict):
            raise ValueError("Legacy route must be a JSON object.")
        if "version" in raw:
            if type(raw["version"]) is not int or raw["version"] != 2:
                raise ValueError("Only legacy v1 and v2 routes can be imported.")
            entries = raw.get("waypoints")
        else:
            entries = [value for key, value in raw.items() if key != "GlobalShoppingList"]
        if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
            raise ValueError("Legacy waypoints must be objects.")
        document = cls()
        document.data["name"] = Path(filename).stem
        removed = 0
        for index, old in enumerate(entries):
            system = old.get("SystemName")
            if not isinstance(system, str):
                raise ValueError(f"Waypoint {index + 1}: SystemName must be text.")
            if system.strip().upper() == "REPEAT":
                removed += 1
                if index == len(entries) - 1 and old.get("Skip") is False:
                    document.data["Repeat"] = True
                continue
            entry = new_waypoint()
            for field in ("SystemName", "StationName"):
                value = old.get(field, "")
                if not isinstance(value, str):
                    raise ValueError(f"Waypoint {index + 1}: {field} must be text.")
                entry[field] = value
            for field in ("BuyCommodities", "SellCommodities"):
                value = old.get(field, {})
                if not EDWayPoint._valid_commodity_list(value):
                    raise ValueError(f"Waypoint {index + 1}: invalid {field}.")
                entry[field] = copy.deepcopy(value)
            document.data["waypoints"].append(entry)
        document.load_notes.append(
            "Imported destinations and trade lists only. Review all options and configure bookmarks if needed. "
            "Global shopping list and progress were not imported; original file is unchanged."
        )
        if removed:
            document.load_notes.append(
                f"Removed {removed} REPEAT entry/entries; only an active final REPEAT enables route repetition."
            )
        return document

    def issues(self):
        issues = entry_issues(self.data["GlobalShoppingList"], global_list=True)
        for index, entry in enumerate(self.data["waypoints"]):
            issues.extend(entry_issues(entry, index))
        if type(self.data.get("Repeat")) is not bool:
            issues.append(RouteIssue("error", None, "Repeat", "Repeat must be true or false."))
        if "RepeatLimit" not in self.data or self.data["RepeatLimit"] is not None:
            issues.append(RouteIssue("error", None, "RepeatLimit", "Limited repetition is not supported; use null."))
        return issues

    def validate(self):
        errors = [issue.describe() for issue in self.issues() if issue.severity == "error"]
        if errors:
            raise ValueError("\n".join(errors))
        if EDWayPoint.parse_route(self.data, self.filename or Path("new-route.json")) is None:
            raise ValueError("Invalid route definition. Check the technical log for details.")

    def move(self, index, offset):
        target = index + offset
        entries = self.data["waypoints"]
        if 0 <= target < len(entries):
            entries[index], entries[target] = entries[target], entries[index]
            return target
        return index

    def save(self, filename):
        """Save v2 and reset its separate progress; restore old progress if saving the route fails."""
        self.validate()
        filename = Path(filename).resolve()
        data = {**self.data, "name": filename.stem}
        progress_path = EDWayPoint._progress_path(filename)
        previous_progress = None
        if progress_path.exists():
            with progress_path.open(encoding="utf-8") as file:
                previous_progress = json.load(file)
        fresh_progress = {
            "version": 1,
            "waypoints": {
                entry["Id"]: {
                    "completed": False,
                    "buy_commodities": entry["BuyCommodities"],
                    "sell_commodities": entry["SellCommodities"],
                }
                for entry in self.data["waypoints"]
            },
            "global_buy_commodities": self.data["GlobalShoppingList"]["BuyCommodities"],
        }
        EDWayPoint._write_json_atomically(progress_path, fresh_progress)
        try:
            EDWayPoint._write_json_atomically(filename, data)
        except OSError:
            try:
                if previous_progress is not None:
                    EDWayPoint._write_json_atomically(progress_path, previous_progress)
                else:
                    progress_path.unlink()
            except OSError:
                logger.exception("Could not restore waypoint progress after route save failure: %s", progress_path)
                raise
            raise
        self.filename = filename
        self.data = data
        self.source_version = 2
        self.saved = copy.deepcopy(self.data)
        self.load_notes.clear()
        logger.debug("Waypoint editor saved route and reset progress: route=%s", filename)

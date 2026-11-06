"""Data-only game language packs, separate from the English application interface."""

import json
import unicodedata
from pathlib import Path

from core import paths
from core.logger import logger

RECOGNITION_KEYS = {
    "PRESS_TO_DISENGAGE_MSG",
    "LINE_OF_SIGHT_MSG",
    "ALIGN_WITH_TARGET_MSG",
    *(f"INT_PNL_TAB_{tab}" for tab in ("MODULES", "FIRE_GROUPS", "SHIP", "INVENTORY", "STORAGE", "STATUS")),
    *(f"NAV_PNL_TAB_{tab}" for tab in ("NAVIGATION", "TRANSACTIONS", "CONTACTS", "TARGET")),
    "STN_SVCS_CONNECTED_TO",
    "STN_SVCS_BUY_COMMODITY",
    "STN_SVCS_SELL_COMMODITY",
}


def normalize_text(text: str) -> str:
    """Normalize OCR comparisons without changing the displayed game text."""
    text = unicodedata.normalize("NFKD", text.upper())
    text = "".join(char for char in text if char.isalnum() or char == " ")
    return " ".join(text.split())


def _read_object(path: Path) -> dict:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    try:
        with path.open(encoding="utf-8-sig") as file:
            data = json.load(file, object_pairs_hook=unique_keys)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error


class LocalizationManager:
    """Discover language folders once; use only the active pack with English fallback."""

    def __init__(self, folder_path: str, language: str = "en") -> None:
        self.folder_path = folder_path
        self.warnings: list[str] = []
        self._reported: set[str] = set()
        self._packs: dict[str, dict] = {}
        self._journal_languages: dict[str, str] = {}
        root = Path(folder_path)
        english = self._load_pack(root / "en")
        if set(english["recognition"]) != RECOGNITION_KEYS:
            raise ValueError(f"{root / 'en' / 'recognition.json'}: the English base must contain all recognition keys")
        known_ids = {str(item["id"]) for item in _read_object(paths.DATA / "commodities.json")["commodities"]}
        if set(english["commodities"]) != known_ids:
            raise ValueError(f"{root / 'en' / 'commodities.json'}: the English base must name every catalogue ID")
        self._packs["en"] = english
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.name == "en" or folder.name.startswith("."):
                continue
            try:
                pack = self._load_pack(folder)
                unknown = set(pack["recognition"]) - set(english["recognition"])
                if unknown:
                    raise ValueError(f"{folder / 'recognition.json'}: unknown keys {sorted(unknown)}")
                unknown_ids = set(pack["commodities"]) - known_ids
                if unknown_ids:
                    raise ValueError(f"{folder / 'commodities.json'}: unknown commodity IDs {sorted(unknown_ids)}")
                aliases = {alias.casefold() for alias in pack["metadata"]["journal_languages"]}
                existing = {
                    alias.casefold()
                    for loaded in self._packs.values()
                    for alias in loaded["metadata"]["journal_languages"]
                }
                if aliases & existing:
                    raise ValueError(
                        f"{folder / 'language.json'}: duplicate journal languages {sorted(aliases & existing)}"
                    )
                self._packs[folder.name] = pack
            except ValueError as error:
                self.warn(f"Language pack ignored: {error}")
        for code, pack in self._packs.items():
            for alias in pack["metadata"]["journal_languages"]:
                alias = alias.casefold()
                if alias in self._journal_languages:
                    raise ValueError(f"Duplicate journal language {alias!r} in language pack {code!r}.")
                self._journal_languages[alias] = code
        self.available_languages = sorted(self._packs)
        self.language_names = {code: pack["metadata"]["name"] for code, pack in self._packs.items()}
        self.change_language(language)

    @staticmethod
    def _load_pack(folder: Path) -> dict:
        metadata_path = folder / "language.json"
        metadata = _read_object(metadata_path)
        if (
            folder.name == "auto"
            or not folder.name
            or not all(char.isascii() and (char.isalnum() or char in "_-") for char in folder.name)
            or not isinstance(metadata.get("name"), str)
            or not metadata["name"].strip()
            or not isinstance(metadata.get("ocr_language"), str)
            or not metadata["ocr_language"].strip()
            or not isinstance(metadata.get("journal_languages"), list)
            or not metadata["journal_languages"]
            or any(not isinstance(alias, str) or not alias.strip() for alias in metadata["journal_languages"])
            or len({alias.casefold() for alias in metadata["journal_languages"]}) != len(metadata["journal_languages"])
        ):
            raise ValueError(f"{metadata_path}: invalid name, journal_languages or ocr_language")
        recognition_path = folder / "recognition.json"
        recognition = _read_object(recognition_path)
        for key, value in recognition.items():
            variants = [value] if isinstance(value, str) else value
            if (
                not isinstance(variants, list)
                or not variants
                or any(not isinstance(text, str) or not normalize_text(text) or text == "?" for text in variants)
            ):
                raise ValueError(f"{recognition_path}: {key}: expected text or a non-empty list of text variants")
            recognition[key] = list(dict.fromkeys(variants))
        commodity_path = folder / "commodities.json"
        commodities = _read_object(commodity_path) if commodity_path.exists() else {}
        for key, value in commodities.items():
            if (
                not key.isascii()
                or not key.isdecimal()
                or str(int(key)) != key
                or int(key) <= 0
                or not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
            ):
                raise ValueError(f"{commodity_path}: {key}: expected a positive commodity ID and a non-empty name")
        if folder.name == "en" and (not recognition or not commodities):
            raise ValueError(f"{folder}: the English base pack must contain recognition texts and commodity names")
        return {"metadata": metadata, "recognition": recognition, "commodities": commodities}

    def warn(self, message: str) -> None:
        if message not in self._reported:
            self._reported.add(message)
            self.warnings.append(message)
            logger.warning(message)

    def take_warnings(self) -> list[str]:
        warnings, self.warnings = self.warnings, []
        return warnings

    def resolve_language(self, selection: str, journal_language: str | None) -> str:
        if not isinstance(selection, str):
            self.warn(f"Invalid game language selection {selection!r}. Using English.")
            return "en"
        if selection == "auto":
            code = self._journal_languages.get((journal_language or "").casefold())
            if code is None:
                self.warn(f"Game language {journal_language or '(not available)'!r} is not supported. Using English.")
                return "en"
            return code
        if selection not in self._packs:
            self.warn(f"Game language pack {selection!r} is not available. Using English.")
            return "en"
        return selection

    @property
    def ocr_language(self) -> str:
        return self.ocr_language_for(self.language)

    def ocr_language_for(self, language: str) -> str:
        return self._packs[language]["metadata"]["ocr_language"]

    def __getitem__(self, key: str) -> str:
        return self.all_values(key)[0]

    def all_values(self, key: str) -> list[str]:
        """Return variants in the active language, never probe unrelated languages."""
        recognition = self._packs[self.language]["recognition"]
        if key not in recognition:
            self.warn(f"Language pack {self.language!r} has no recognition text for {key}. Using English.")
        return recognition.get(key, self._packs["en"]["recognition"][key])

    def commodity_names(self, language: str | None = None) -> dict[str, str]:
        code = self.resolve_language(language or self.language, None)
        missing = self._packs["en"]["commodities"].keys() - self._packs[code]["commodities"].keys()
        if missing:
            self.warn(
                f"Language pack {code!r} is missing {len(missing)} commodity names. Using English for these names."
            )
        return self._packs["en"]["commodities"] | self._packs[code]["commodities"]

    def commodity_name(self, commodity_id: str | int, language: str | None = None) -> str:
        code = self.resolve_language(language or self.language, None)
        key = str(commodity_id)
        return self.commodity_names(code).get(key, key)

    def change_language(self, language: str) -> None:
        self.language = self.resolve_language(language, None)
        for key in self._packs["en"]["recognition"]:
            if key not in self._packs[self.language]["recognition"]:
                self.warn(f"Language pack {self.language!r} has no recognition text for {key}. Using English.")
        self.commodity_names()

    def refresh(self) -> None:
        """Reload installed packs explicitly; ordinary detection never reads files."""
        replacement = type(self)(self.folder_path, self.language)
        self.__dict__.update(replacement.__dict__)

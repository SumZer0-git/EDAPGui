"""Commodity identities and localized names."""

import json
from functools import lru_cache

from core import paths
from i18n.localization import LocalizationManager


@lru_cache(maxsize=1)
def _catalogue():
    with (paths.DATA / "commodities.json").open(encoding="utf-8") as file:
        data = json.load(file)
    if data.get("version") != 1 or not isinstance(data.get("commodities"), list):
        raise ValueError("Unsupported commodity catalogue version.")
    catalogue = {}
    symbols = set()
    for row in data["commodities"]:
        commodity_id = row.get("id")
        symbol = row.get("symbol")
        rare = row.get("rare")
        if (
            type(commodity_id) is not int
            or commodity_id <= 0
            or not isinstance(symbol, str)
            or not symbol.strip()
            or symbol != symbol.strip()
            or type(rare) is not bool
            or str(commodity_id) in catalogue
            or symbol.casefold() in symbols
        ):
            raise ValueError("Invalid commodity catalogue entry.")
        catalogue[str(commodity_id)] = {"symbol": symbol, "rare": rare}
        symbols.add(symbol.casefold())
    return catalogue


def load_catalogue():
    return _catalogue()


def is_commodity_id(value):
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and str(int(value)) == value
        and value in _catalogue()
    )


def commodity_symbol(commodity_id):
    item = _catalogue().get(str(commodity_id))
    return item["symbol"] if item else None


def get_localization(language="en"):
    return LocalizationManager(str(paths.LOCALES_DIR), language)


def commodity_id_matches_name(name, localization=None):
    if not isinstance(name, str) or not name.strip():
        return set()
    localization = localization or get_localization()
    query = name.strip().casefold()
    matches = {
        commodity_id
        for language in localization.available_languages
        for commodity_id, localized_name in localization.commodity_names(language).items()
        if localized_name.casefold() == query
    }
    matches.update(commodity_id for commodity_id, item in _catalogue().items() if item["symbol"].casefold() == query)
    return matches

"""Offline commodity suggestions for route editing."""

import json
from collections import Counter

from core import paths
from core.commodities import get_localization
from core.commodities import load_catalogue as load_id_catalogue


def load_catalogue():
    catalogue = load_id_catalogue()
    with (paths.DATA / "commodities.verification.json").open(encoding="utf-8") as file:
        verification = json.load(file)
    if verification["version"] != 1:
        raise ValueError("Unsupported commodity verification data version.")
    verified = {
        language: set(verification.get(f"{language}_market_observed_ids", []))
        for language in get_localization().available_languages
    }
    return catalogue, verified


def suggestions(catalogue, verified, language, query, localization=None):
    localization = localization or get_localization(language)
    if language not in localization.available_languages:
        raise ValueError(f"Commodity language {language!r} is not available.")
    query = query.strip().casefold()
    names = localization.commodity_names(language)
    matching_ids = (
        {
            commodity_id
            for code in localization.available_languages
            for commodity_id, name in localization.commodity_names(code).items()
            if query in name.casefold()
        }
        if query
        else set()
    )
    displayed = {commodity_id: names.get(commodity_id, item["symbol"]) for commodity_id, item in catalogue.items()}
    counts = Counter(name.casefold() for name in displayed.values())
    return {
        name
        + (f" ({catalogue[commodity_id]['symbol']})" if counts[name.casefold()] > 1 else "")
        + ("" if int(commodity_id) in verified.get(language, set()) else " [unchecked]"): commodity_id
        for commodity_id, name in sorted(displayed.items(), key=lambda pair: pair[1].casefold())
        if not query or commodity_id in matching_ids or query in catalogue[commodity_id]["symbol"].casefold()
    }

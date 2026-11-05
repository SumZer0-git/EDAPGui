"""Offline commodity suggestions for route editing."""

import json
from collections import Counter

from core import paths


def load_catalogue():
    with (paths.DATA / "commodities.json").open(encoding="utf-8") as file:
        catalogue = json.load(file)
    with (paths.DATA / "commodities.verification.json").open(encoding="utf-8") as file:
        verification = json.load(file)
    if catalogue["version"] != 1 or verification["version"] != 1:
        raise ValueError("Unsupported commodity catalogue version.")
    return catalogue["commodities"], {
        language: set(verification[f"{language}_market_observed_ids"]) for language in ("de", "en")
    }


def suggestions(rows, verified, language, query):
    if language not in ("de", "en"):
        raise ValueError("Commodity language must be de or en.")
    query = query.strip().casefold()
    counts = Counter(row[f"name_{language}"] for row in rows)
    return {
        row[f"name_{language}"]
        + (f" ({row['symbol']})" if counts[row[f"name_{language}"]] > 1 else "")
        + ("" if row["id"] in verified[language] else " [unchecked]"): row[f"name_{language}"]
        for row in sorted(rows, key=lambda row: row[f"name_{language}"].casefold())
        if not query or any(query in row[key].casefold() for key in ("name_de", "name_en", "symbol"))
    }

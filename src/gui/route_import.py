"""Parse copied trade-route text without network access or route mutations."""

import re
import unicodedata
from dataclasses import dataclass

from gui.waypoint_model import new_waypoint


@dataclass
class TradeRoute:
    origin: tuple[str, str]
    destination: tuple[str, str]
    trades: list[tuple[int, str, str]]


def clean_line(line):
    line = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", line)
    return " ".join("".join(c for c in line if unicodedata.category(c) != "Co" and c not in "\ufe0e\ufe0f").split())


def parse_trade_route(text):
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    stations = {}
    trades = []
    block = -1
    pending = None
    for line in lines:
        heading = re.fullmatch(r"(Von|Nach|From|To)(?:\s+(.+))?", line, re.IGNORECASE)
        if heading:
            if pending:
                raise ValueError("A station name is missing.")
            role = "origin" if heading[1].casefold() in ("von", "from") else "destination"
            if role in stations:
                raise ValueError("Paste exactly one trade route, not several results.")
            pending = role
            line = heading[2] or ""
            if not line:
                continue
        if pending:
            parts = line.split("|")
            if len(parts) != 2 or not all(part.strip() for part in parts):
                raise ValueError("Expected Station | System after From/To (Von/Nach).")
            stations[pending] = tuple(part.strip() for part in parts)
            pending = None
            continue
        if re.fullmatch(r"(Entfernung der Station|Station distance)(?:\s+\d[\d., ]*\s+Ls)?", line, re.IGNORECASE):
            block += 1
            if block > 1:
                raise ValueError("Expected exactly two station trade blocks.")
            continue
        operation = re.fullmatch(r"(Kauf|Verkauf|Buy|Sell)(?:\s+(.+))?", line, re.IGNORECASE)
        if operation:
            if operation[2] and operation[2].casefold().startswith("price"):
                continue
            if block not in (0, 1):
                raise ValueError("Missing station-distance headings before the trade blocks.")
            if trades and not trades[-1][2]:
                raise ValueError("A commodity name is missing after Buy/Sell.")
            direction = "BuyCommodities" if operation[1].casefold() in ("kauf", "buy") else "SellCommodities"
            trades.append((block, direction, operation[2] or ""))
        elif trades and not trades[-1][2]:
            if re.search(r"^\d|\||https?://", line) or line.casefold() in (
                "kaufpreis",
                "verkaufspreis",
                "auf lager",
                "nachfrage",
                "buy price",
                "sell price",
                "supply",
                "demand",
            ):
                raise ValueError("A commodity name is missing after Buy/Sell.")
            index, direction, _name = trades[-1]
            trades[-1] = (index, direction, line)
    if (
        pending
        or set(stations) != {"origin", "destination"}
        or block != 1
        or not trades
        or any(not t[2] for t in trades)
    ):
        raise ValueError("Paste a complete route with From/To, two Station distance blocks and Buy/Sell names.")
    if not any(t[0] == 0 for t in trades) or not any(t[0] == 1 for t in trades):
        raise ValueError("Both station blocks must contain a trade.")
    # The first block belongs to the first displayed endpoint, not necessarily the origin.
    first_role = next(iter(stations))
    trades = [(index if first_role == "origin" else 1 - index, direction, name) for index, direction, name in trades]
    if len({(i, direction, name.casefold()) for i, direction, name in trades}) != len(trades):
        raise ValueError("Duplicate trade entries; check the pasted route.")
    return TradeRoute(stations["origin"], stations["destination"], trades)


def resolve_commodities(route, catalogue, language):
    if language not in ("de", "en"):
        raise ValueError("Select de or en as the game commodity language.")
    resolved = {}
    for _index, _direction, name in route.trades:
        matches = [
            row for row in catalogue if name.casefold() in (row["name_de"].casefold(), row["name_en"].casefold())
        ]
        if len(matches) != 1:
            raise ValueError(f"Commodity '{name}' is unknown or ambiguous. Correct the text before previewing.")
        row = matches[0]
        resolved[name] = (row["id"], row[f"name_{language}"])
    return resolved


def imported_waypoints(route, resolved, quantities):
    entries = [
        dict(new_waypoint(), StationName=station, SystemName=system)
        for station, system in (route.origin, route.destination)
    ]
    for index, direction, name in route.trades:
        commodity_id, localized = resolved[name]
        quantity = quantities.get(commodity_id)
        if type(quantity) is not int or not 1 <= quantity < 9999:
            raise ValueError("Set a quantity from 1 to 9998 for every commodity (9999 means sell all).")
        if localized in entries[index][direction]:
            raise ValueError("Several imported names resolve to the same trade. Check the text.")
        entries[index][direction][localized] = quantity
    return entries

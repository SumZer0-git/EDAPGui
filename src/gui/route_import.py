"""Parse route imports without network access or route mutations."""

import csv
import io
import json
import re
import unicodedata
from dataclasses import dataclass

from core.commodities import commodity_id_matches_name, get_localization
from core.commodities import load_catalogue as load_commodity_catalogue
from gui.waypoint_model import new_waypoint


@dataclass
class TradeRoute:
    origin: tuple[str, str]
    destination: tuple[str, str]
    trades: list[tuple[int, str, str]]


@dataclass
class SpanshRouteImport:
    route_type: str
    entries: list[dict]
    stop_details: list[str]
    warnings: list[str]
    summary: str


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


def resolve_commodities(route, catalogue, language, localization=None):
    localization = localization or get_localization(language)
    if language not in localization.available_languages:
        raise ValueError("Select an installed game commodity language.")
    resolved = {}
    for _index, _direction, name in route.trades:
        matches = commodity_id_matches_name(name, localization)
        if len(matches) != 1 or not matches <= catalogue.keys():
            raise ValueError(f"Commodity '{name}' is unknown or ambiguous. Correct the text before previewing.")
        commodity_id = matches.pop()
        resolved[name] = (commodity_id, localization.commodity_name(commodity_id, language))
    return resolved


def imported_waypoints(route, resolved, quantities):
    entries = [
        dict(new_waypoint(), StationName=station, SystemName=system)
        for station, system in (route.origin, route.destination)
    ]
    for index, direction, name in route.trades:
        commodity_id, _localized = resolved[name]
        quantity = quantities.get(commodity_id)
        if type(quantity) is not int or not 1 <= quantity < 9999:
            raise ValueError("Set a quantity from 1 to 9998 for every commodity (9999 means sell all).")
        if commodity_id in entries[index][direction]:
            raise ValueError("Several imported names resolve to the same trade. Check the text.")
        entries[index][direction][commodity_id] = quantity
    return entries


def parse_spansh_export(text, catalogue=None, language="en"):
    """Detect and parse a supported Spansh JSON or CSV export."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The selected file is empty.")
    content = text.lstrip("\ufeff \t\r\n")
    if content.startswith(("{", "[")):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON export: {error.msg}.") from error
        return _parse_spansh_json(data, catalogue, language)
    return _parse_spansh_csv(content)


def _parse_spansh_json(data, catalogue, language):
    if not isinstance(data, dict) or "result" not in data:
        raise ValueError("This JSON file is not a supported Spansh route export.")
    result = data["result"]
    if isinstance(result, dict) and isinstance(result.get("jumps"), list):
        return _parse_spansh_jumps(result["jumps"])
    if (
        isinstance(result, list)
        and result
        and all(isinstance(leg, dict) and {"source", "destination", "commodities"} <= leg.keys() for leg in result)
    ):
        return _parse_spansh_trade(result, catalogue, language)
    if isinstance(result, list) and all(
        isinstance(system, dict) and isinstance(system.get("bodies"), list) for system in result
    ):
        return _parse_spansh_exploration(result)
    raise ValueError("This JSON file is not a supported Spansh Galaxy Plotter, exploration, or Trade Planner export.")


def _parse_spansh_jumps(jumps):
    entries = []
    for jump in jumps:
        if not isinstance(jump, dict) or not isinstance(jump.get("name"), str) or not jump["name"].strip():
            raise ValueError("The Galaxy Plotter export contains a jump without a system name.")
        entries.append(dict(new_waypoint(), SystemName=jump["name"].strip()))
    if not entries:
        raise ValueError("The Galaxy Plotter export contains no systems.")
    return SpanshRouteImport(
        "Galaxy Plotter",
        entries,
        [f"{index + 1}. {entry['SystemName']}" for index, entry in enumerate(entries)],
        [],
        f"{len(entries)} systems in the exported jump sequence.",
    )


def _parse_spansh_exploration(systems):
    if not systems:
        raise ValueError("The exploration export contains no systems.")
    normalized = []
    for system in systems:
        name = system.get("name")
        bodies = system.get("bodies")
        if not isinstance(name, str) or not name.strip() or not isinstance(bodies, list):
            raise ValueError("The exploration export contains an invalid system or body list.")
        if any(not isinstance(body, dict) or not _nonempty_string(body.get("name")) for body in bodies):
            raise ValueError(f"The exploration export contains an invalid body for system '{name.strip()}'.")
        normalized.append((name.strip(), len(bodies)))

    selected = []
    if normalized:
        selected.append(normalized[0])
    selected.extend((name, count) for name, count in normalized[1:-1] if count)
    if len(normalized) > 1:
        selected.append(normalized[-1])
    unique = []
    seen = set()
    for name, count in selected:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            unique.append((name, count))
    if not unique:
        raise ValueError("The exploration export contains no importable systems.")

    entries = [dict(new_waypoint(), SystemName=system[0]) for system in unique]
    details = [
        f"{index + 1}. {name}" + (f" - {count} selected bodies" if count else "")
        for index, (name, count) in enumerate(unique)
    ]
    target_count = sum(system[1] for system in normalized)
    warnings = []
    if not target_count:
        warnings.append("No selected body targets were found; only the exported start and destination are included.")
    return SpanshRouteImport(
        "Exploration",
        entries,
        details,
        warnings,
        f"{len(entries)} system stops. Body-level visits and scans are not added as route actions.",
    )


def _parse_spansh_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("The selected CSV file has no header row.")
    headers = {header.strip() for header in reader.fieldnames if isinstance(header, str)}
    if "System Name" not in headers:
        raise ValueError("This CSV file is not a supported Spansh route export.")
    rows = [
        {key.strip(): value.strip() if isinstance(value, str) else value for key, value in row.items() if key}
        for row in reader
    ]
    galaxy_headers = {
        "Distance",
        "Distance Remaining",
        "Fuel Left",
        "Fuel Used",
        "Refuel",
        "Neutron Star",
        "Inject",
        "Injection",
    }
    if "Body Name" not in headers and headers & galaxy_headers:
        names = [row.get("System Name", "") for row in rows]
        entries = [dict(new_waypoint(), SystemName=name) for name in names if name]
        if not entries:
            raise ValueError("The Galaxy Plotter CSV contains no systems.")
        return SpanshRouteImport(
            "Galaxy Plotter",
            entries,
            [f"{index + 1}. {entry['SystemName']}" for index, entry in enumerate(entries)],
            [],
            f"{len(entries)} systems in the exported jump sequence.",
        )
    if "Body Name" in headers:
        return _parse_spansh_exploration_csv(rows)
    raise ValueError("This CSV file is not a supported Spansh Galaxy Plotter or exploration export.")


def _parse_spansh_exploration_csv(rows):
    systems = {}
    for row in rows:
        system = row.get("System Name", "")
        body = row.get("Body Name", "")
        if system and body:
            key = system.casefold()
            if key not in systems:
                systems[key] = [system, 0]
            systems[key][1] += 1
    if not systems:
        raise ValueError("The exploration CSV contains no selected body targets.")
    targets = list(systems.values())
    entries = [dict(new_waypoint(), SystemName=target[0]) for target in targets]
    details = [f"{index + 1}. {name} - {count} selected bodies" for index, (name, count) in enumerate(targets)]
    return SpanshRouteImport(
        "Exploration",
        entries,
        details,
        ["This CSV contains target systems only; start and destination systems are not included."],
        f"{len(entries)} target systems. Body-level visits and scans are not added as route actions.",
    )


def _parse_spansh_trade(legs, catalogue, language):
    if catalogue is None:
        catalogue = load_commodity_catalogue()
    localization = get_localization(language)
    entries = []
    warnings = []
    for index, leg in enumerate(legs, 1):
        source = _spansh_station(leg["source"], index, "source")
        destination = _spansh_station(leg["destination"], index, "destination")
        if not isinstance(leg["commodities"], list):
            raise ValueError(f"Trade leg {index} has an invalid commodities list.")
        source_entry = _get_spansh_stop(entries, source)
        destination_entry = _get_spansh_stop(entries, destination)
        for good in leg["commodities"]:
            if not isinstance(good, dict):
                raise ValueError(f"Trade leg {index} contains an invalid commodity.")
            name, amount = good.get("name"), good.get("amount")
            if not _nonempty_string(name):
                warnings.append(f"Leg {index}: omitted a commodity with no name.")
                continue
            matches = commodity_id_matches_name(name, localization)
            matches = {commodity_id for commodity_id in matches if commodity_id in catalogue}
            if len(matches) != 1:
                warnings.append(f"Leg {index}: omitted unknown or ambiguous commodity '{name.strip()}'.")
                continue
            if type(amount) is not int or amount <= 0:
                warnings.append(
                    f"Leg {index}: omitted '{name.strip()}' because its amount is not a positive whole number."
                )
                continue
            commodity_id = matches.pop()
            localized_name = localization.commodity_name(commodity_id, language)
            source_entry["BuyCommodities"][commodity_id] = source_entry["BuyCommodities"].get(commodity_id, 0) + amount
            destination_entry["SellCommodities"][commodity_id] = (
                destination_entry["SellCommodities"].get(commodity_id, 0) + amount
            )
            source_entry.setdefault("_display_goods", {})[commodity_id] = localized_name
            destination_entry.setdefault("_display_goods", {})[commodity_id] = localized_name

    if not entries:
        raise ValueError("The Trade Planner export contains no station stops.")
    details = []
    for index, entry in enumerate(entries, 1):
        actions = []
        for direction, label in (("BuyCommodities", "Buy"), ("SellCommodities", "Sell")):
            for commodity_id, amount in entry[direction].items():
                name = entry.get("_display_goods", {}).get(commodity_id, commodity_id)
                actions.append(f"{label} {name} x {amount}")
        details.append(
            f"{index}. {entry['StationName']} | {entry['SystemName']}"
            + (f": {'; '.join(actions)}" if actions else ": no valid commodity actions")
        )
        entry.pop("_display_goods", None)
        entry.pop("_market_id", None)
    return SpanshRouteImport(
        "Trade Planner",
        entries,
        details,
        warnings,
        f"{len(legs)} trade legs across {len(entries)} station stops. Planner prices and market snapshots are not imported.",
    )


def _spansh_station(value, leg_index, role):
    if not isinstance(value, dict):
        raise ValueError(f"Trade leg {leg_index} has an invalid {role} station.")
    nested_station = value.get("station")
    station = _spansh_field(value, ("station", "station_name", "stationName", "name"))
    system = _spansh_field(value, ("system", "system_name", "systemName"))
    if not system and isinstance(nested_station, dict):
        system = _spansh_field(nested_station, ("system", "system_name", "systemName"))
    if not _nonempty_string(station) or not _nonempty_string(system):
        raise ValueError(f"Trade leg {leg_index} has a {role} station without a station and system name.")
    market_id = value.get("market_id", value.get("marketId"))
    if market_id is None and isinstance(nested_station, dict):
        market_id = nested_station.get("market_id", nested_station.get("marketId"))
    return {
        "StationName": station.strip(),
        "SystemName": system.strip(),
        "market_id": market_id,
    }


def _spansh_field(value, names):
    for name in names:
        item = value.get(name)
        if isinstance(item, dict):
            item = item.get("name")
        if isinstance(item, str) and item.strip():
            return item
    return None


def _get_spansh_stop(entries, station):
    market_id = station["market_id"]
    if entries:
        previous = entries[-1]
        previous_market_id = previous.get("_market_id")
        if market_id is not None and previous_market_id is not None:
            same_station = str(previous_market_id) == str(market_id)
        else:
            same_station = (
                previous["SystemName"].casefold(),
                previous["StationName"].casefold(),
            ) == (station["SystemName"].casefold(), station["StationName"].casefold())
        if same_station:
            return previous
    entry = dict(
        new_waypoint(),
        SystemName=station["SystemName"],
        StationName=station["StationName"],
    )
    entry["_market_id"] = market_id
    entries.append(entry)
    return entry


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())

# Waypoint Assist

Waypoint Assist follows a JSON file in order. It travels to each `SystemName`, optionally visits a bookmarked
destination in that system, and can trade or transfer cargo after docking. Load a waypoint file from the Waypoints
section of the main tab, then enable Waypoint Assist.

Example waypoint files are in `data/waypoints/` and are copied to `user_data/waypoints/` on first start. Use valid
JSON: double quotes around strings and property names, no comments, and no trailing commas.

## File format

Every file must contain `GlobalShoppingList`. Each numbered or named waypoint must include the fields shown below;
the keys are case-sensitive.

```json
{
  "GlobalShoppingList": {
    "BuyCommodities": {},
    "UpdateCommodityCount": false,
    "Skip": true
  },
  "1": {
    "SystemName": "Sol",
    "StationName": "",
    "GalaxyBookmarkType": "",
    "GalaxyBookmarkNumber": 0,
    "SystemBookmarkType": "",
    "SystemBookmarkNumber": 0,
    "SellCommodities": {},
    "BuyCommodities": {},
    "UpdateCommodityCount": false,
    "FleetCarrierTransfer": false,
    "Skip": false,
    "Completed": false
  }
}
```

`GlobalShoppingList` is a special entry, not a destination. Its `BuyCommodities` are attempted at each supported
market after that waypoint's own buy list. `UpdateCommodityCount` updates requested buy quantities as items are
purchased; `Skip` is required by the file reader and is normally `true` for this entry.

### Waypoint fields

| Field | Description |
|---|---|
| `SystemName` | Target system name. Leave blank to use the current system. |
| `StationName` | Destination name used to confirm the station or carrier after docking. A station name alone cannot be targeted: provide a Galaxy or System Map bookmark as well. |
| `GalaxyBookmarkType`, `GalaxyBookmarkNumber` | Optional Galaxy Map bookmark category and its 1-based position. Supported categories are Favorites (`Fav`), Systems (`Sys`), Bodies (`Bod`), Stations (`Sta`), and Settlements (`Set`). Use number `0` when unused. |
| `SystemBookmarkType`, `SystemBookmarkNumber` | Optional System Map bookmark category and its 1-based position. Supported categories are Favorites (`Fav`), Bodies (`Bod`), Stations (`Sta`), Settlements (`Set`), and Navigation (`Nav`). `Nav` selects a target from the left Navigation panel. Use number `0` when unused. |
| `SellCommodities` | Commodity names and quantities to sell. |
| `BuyCommodities` | Commodity names and quantities to buy. |
| `UpdateCommodityCount` | If `true`, reduce buy quantities in the file as goods are purchased. Sell quantities are not updated. |
| `FleetCarrierTransfer` | If `true` at a Fleet Carrier, transfer cargo instead of buying and selling. |
| `Skip` | If `true`, ignore this waypoint. |
| `Completed` | Progress flag. EDAPGui sets it after the waypoint is finished and saves the file. |

Bookmark numbers start at `1` for the first bookmark in the selected category. Galaxy Map bookmarks take precedence
if both bookmark types are set. System Colonisation Ships must be selected through a Galaxy Map bookmark.

## Routes and progress

Waypoints are processed in the order they appear in the JSON file. EDAPGui plots a system route, completes its FSD
jumps, and then visits the local bookmarked destination if one is configured. Without a local destination, reaching
the system completes that waypoint. When docked at the configured destination, EDAPGui can perform its trade or cargo
transfer before marking the waypoint complete.

To repeat a route, add a final waypoint whose `SystemName` is `REPEAT` and whose `Skip` is `false`. Reaching it resets
the other waypoints' `Completed` flags and starts the list again. Set its `Skip` to `true` to let the route finish.
Use **Reset List** on the main tab to reset progress manually.

Progress is written to `user_data/waypoints/<loaded filename>`. Keep the working waypoint file in that folder if you
want progress saved alongside it.

## Trading and transfers

- At stations and Fleet Carriers in buy/sell mode, EDAPGui processes the waypoint's sell list and buy list.
- The global shopping list is bought after the waypoint's local buy list.
- For a Fleet Carrier, set `FleetCarrierTransfer` to `true` to transfer goods instead of trading them. Use `All` with
  quantity `0` to request a full cargo transfer.
- At a System Colonisation Ship or Orbital Construction Site, use `All` with quantity `0` in `SellCommodities` to
  sell all cargo.
- Trading requires a commodities service at the docked location. Only list goods that can be handled there.

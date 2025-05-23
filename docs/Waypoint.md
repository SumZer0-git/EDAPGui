# Waypoints
Waypoints are Systems that are captured in a waypoints.json file and read and processed by this Autopilot.  An example waypoint file is below:

```py
{
  "1": {
    "SystemName": "Mylaifai EP-G c27-631", "StationName": "", "GalaxyBookmarkType": "", "GalaxyBookmarkNumber": 0, "SystemBookmarkType": "", "SystemBookmarkNumber": 0, "SellCommodities": {}, "BuyCommodities": {}, "UpdateCommodityCount": false, "FleetCarrierTransfer": false, "Skip": false, "Completed": false
  },
  "2": {
    "SystemName": "Striechooe QR-S b37-0", "StationName": "", "GalaxyBookmarkType": "", "GalaxyBookmarkNumber": 0, "SystemBookmarkType": "", "SystemBookmarkNumber": 0, "SellCommodities": {}, "BuyCommodities": {}, "UpdateCommodityCount": false, "FleetCarrierTransfer": false, "Skip": false, "Completed": false
  },
  "3": {
    "SystemName": "Ploxao JV-E b31-1", "StationName": "", "GalaxyBookmarkType": "", "GalaxyBookmarkNumber": 0, "SystemBookmarkType": "", "SystemBookmarkNumber": 0, "SellCommodities": {}, "BuyCommodities": {}, "UpdateCommodityCount": false, "FleetCarrierTransfer": false, "Skip": false, "Completed": false
  },
  "4": {
    "SystemName": "Beagle Point", "StationName": "", "GalaxyBookmarkType": "", "GalaxyBookmarkNumber": 0, "SystemBookmarkType": "", "SystemBookmarkNumber": 0, "SellCommodities": {}, "BuyCommodities": {}, "UpdateCommodityCount": false, "FleetCarrierTransfer": false, "Skip": false, "Completed": false
  }
}
```

With this waypoint file this Autopilot will take you to Beagle Point without your intervention.  The Autopilot will read
and process each row, plotting the course to that **SystemName** in the Galaxy Map and executing that route via the FSD Route 
Assist.  When entering that System, if no **StationName** is defined (i.e. ''), the assist will plot the route for the next 
row in this waypoint file.  The waypoint file is read in when selecting Waypoint Assist.  When reaching the final 
waypoint, the Autopilot will go idle.  The Waypoint Assist writes to waypoints.json file, marking which Systems have
been reached by setting the Completed entity to true.

## Repeating Waypoints
A set of waypoints can be endlessly repeated by using a special row at the end of the waypoint file with the system name as **'REPEAT'**. When hitting this record and as long as **Skip** is not ture, the Waypoint Assist will start from the top jumping through the defined Systems until the user ends the Waypoint Assist.

## Docking with a Station
When entering a System via Waypoint Assist, if the **StationName** is not '' and a **GalaxyMapBookmark** or 
**SystemMapBookmark** is defined, the Waypoint Assist will go to the Galaxy Map or System Map and select the 
Station by bookmark. The position of the bookmark in the station list of the **System Map** from top to bottom and 
starting at '1' for the first bookmark. A bookmark of '0' is disabled. 
Upon arriving at the station, the SC Assist (which is acting on behalf of the Waypoint Assist), will drop your ship
out of Supercruise and attempt docking.  Once docked, the fuel and repair will automatically be commanded and Trade wil execute if necessary.

## Docking with a System Colonisation Ship and Orbital Construction Site (Odyssey only)
Refer to *Docking with a Station* above. The only difference from a regular station is that the only trade option is to sell all commodities to the ship. Refer to Trading.
<br>
_Note: Colonisation Ships and Construction Ships can only be bookmarked at the Galaxy Map level._

## Docking with a Fleet Carrier
Refer to *Docking with a Station* above. In addition to Trading (Buy/Sell), Fleet Carriers include the option to Transfer (to/from) the Fleet Carrier using the **FleetCarrierTransfer** option. Transfer will attempt to transfer all commodities on the ship/Fleet Carrier, so transfer from a Fleet Carrier is not particularly useful.
<br>
_Note: There appears to be a bug that sometimes prevents bookmarking a Fleet Carrier in the System Map. If this occurs, it is still possible to bookmark the FC through the Navigation Panel. Once bookmarked, it will be accessible through the System Map._

## Trading
The **SellCommodities** and **BuyCommodities** lists are associated with auto-trading and each waypoint will have both lists and either or both may be empty. If either of the lists are not empty, the trade executor kicks in, brings up Commodities Screen and will perform the Selling and then Buying of each listed commodity if it can be traded. The commodities will be processed in the order defined, so place the important items first. There is also an option to update the item counts as the items are bought and sold.

In addition to the **SellCommodities** and **BuyCommodities** lists defined in each waypoint, a **GlobalShoppingList** exists which is a **BuyCommodities** list common to all waypoints. These are items that will be purchased at every waypoint if they are available **after** the waypoint's **BuyCommodities** has been processed. There is also an option to update the item counts as the items are bought and sold.

# Common Actions
A simple reference for common actions:
### Travel to distant System
* Enter system data, leave station data blank.
### Travel to Station
* Enter system and station data, leave commodity data blank. For travel within the current system, leave system data blank. 
### Trade between station(s) and/or fleet carrier(s)
* Enter system (options) and station data.
* Complete Buy/Sell lists.
### Transfer to/from Fleet Carrier
* Enter system (options) and station data.
* Enter commodity 'All' with a quantity of '0' in the Buy/Sell lists to trigger a transfer.
### System Colonisation Ship / Orbital Construction Site
* Enter system (options) and station data.
* Enter commodity 'All' with a quantity of '0' in the Sell lists to trigger a sale of all commodities.

A complete example with notes:
```py
{
    "GlobalShoppingList": {                 # The Global shopping list. Will attempt to buy these items at every station
                                            #    before buying the waypoint defined items. Do not change this name.
        "BuyCommodities": {                 # The dictionary of commodities to buy. There are no global sell commodities.
            "Ceramic Composites": 14,       # Enter commodity name and quantity
            "CMM Composite": 3029,
            "Insulating Membrane": 324
        },
        "UpdateCommodityCount": true,       # Update the counts above when good purchased (not sold).
        "Skip": true,                       # Ignored for shopping list
        "Completed": false                  # Ignored for shopping list
    },
    "1": {                                  # System key. May be changed to something useful, but must be unique.
        "SystemName": "Hillaunges",         # The target system name used to find the system in the Galaxy Map. If the system
                                            # name is blank, then the current system is assumed to be the target.
        "StationName": "",                  # The destination name (station name, FC name etc). 
                                            #   If blank and no bookmark is set, then the waypoint is complete when reaching
                                            #   the system.
        "GalaxyBookmarkType": "Sys",        # The Galaxy Map bookmark type. May be:
                                            #   'Fav' or '' - Favorites
                                            #   'Sys' - System
                                            #   'Bod' - Body
                                            #   'Sta' - Station
                                            #   'Set' - Settlement
                                            # Note: System Colonisation Ships are bookmarked at the Gal Map level, so would
                                            #   be 'Sta' above.
        "GalaxyBookmarkNumber": 6,          # The bookmark index within the type specified above.
                                            #   Set to 0 or -1 if bookmarks are not used.
        "SystemBookmarkType": "Fav",        # The System Map bookmark type. May be:
                                            #   'Fav' or '' - Favorites
                                            #   'Bod' - Body
                                            #   'Sta' - Station
                                            #   'Set' - Settlement
                                            #   'Nav' - This is a special case that uses the Navigation Panel (Panel #1) to
                                            #      select the bookmark.
                                            #      This is primarily for system targets that do not show up in system map,
                                            #      like Mega Ships.
                                            #      Note that the Nav Panel list is highly variable due to what is in system
                                            #      and where you drop into a system, so filter your Nav Panel first. So use
                                            #      with caution.
                                            #   Note: System Colonisation Ships can only be bookmarked at the Gal Map level, 
                                            #       so this is not applicable to Col Ships.
        "SystemBookmarkNumber": 1,          # The bookmark index within the type specified above.
                                            #   Set to 0 or -1 if bookmarks are not used.
        "SellCommodities": {},              # The dictionary of commodities to sell. Same format as the Global shopping list
                                            #   above. Additionally, for Colonisation Ships and Fleet Carriers in 'Transfer'
                                            #   mode, as all commodities must be transferred, it is okay to put '"All": 0'
                                            #   as the sell good to trigger a sell/transfer all. 
        "BuyCommodities": {},               # The dictionary of commodities to buy. Same format as the Global shopping list
                                            #   above. If you define global and waypoint buy shopping lists, the waypoint
                                            #   shopping list will be processed first. Additionally, for Colonisation
                                            #   Ships and Fleet Carriers in 'Transfer' mode, as all commodities must be
                                            #   transferred, it is okay to put '"All": 0' as the buy good to trigger a
                                            #   transfer all.
        "UpdateCommodityCount": true,       # Update the buy counts above when goods are purchased (not sold). Sell counts
                                            #   are never updated.
        "FleetCarrierTransfer": false,      # If this 'station' is a Fleet Carrier allows option to TRANSFER goods rather
                                            #   than BUY/SELL, set to False to Buy/sell, True to Transfer. Transfer is by
                                            #   default everything you have.
        "Skip": true,                       # Skip this waypoint. EDAP will not change this value, so a good way to disable
                                            #   a waypoint without deleting it.
        "Completed": false                  # If false, process this waypoint. One complete EDAP will switch to True. Once
                                            #   all waypoints are complete, EDAP will switch to False.
    },
    "2": {
        "SystemName": "Synuefe ZX-M b54-1",
        "StationName": "System Colonisation Ship",
        "GalaxyBookmarkType": "Sys",
        "GalaxyBookmarkNumber": 1,
        "SystemBookmarkType": "",
        "SystemBookmarkNumber": -1,
        "SellCommodities": {
            "ALL": 0
        },
        "BuyCommodities": {},
        "FleetCarrierTransfer": false,
        "UpdateCommodityCount": true,
        "Skip": false,
        "Completed": false
    },
    "rep": {
        "SystemName": "REPEAT",             # System name of REPEAT causes the waypoints to be repeated.
                                            # Only the 'Skip' field below is used to 'disable' the repeat function
                                            # without deleting the row. 
        "StationName": "",
        "GalaxyBookmarkType": "",
        "GalaxyBookmarkNumber": -1,
        "SystemBookmarkType": "",
        "SystemBookmarkNumber": -1,
        "SellCommodities": {},
        "BuyCommodities": {},
        "FleetCarrierTransfer": false,
        "UpdateCommodityCount": false,
        "Skip": false,                      # Skip (disables) the REPEAT.
        "Completed": false
    }
}
```


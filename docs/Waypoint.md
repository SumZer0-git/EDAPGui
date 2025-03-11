# Waypoints
Waypoints are Systems that are captured in a waypoints.json file and read and processed by this Autopilot.  An example waypoint file is below:

```py
{
"Mylaifai EP-G c27-631": {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"Striechooe QR-S b37-0": {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} ,
"Ploxao JV-E b31-1":     {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} ,
"Beagle Point":          {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} 
}
```

With this waypoint file this Autopilot will take you to Beagle Point without your intervention.  The Autopilot will read and process each
row, plotting the course to that System in the GalaxyMap and executing that route via the FSD Route Assist.  When entering that System, 
if no Station is defined (i.e. null), the assist will plot the route for the next row in this waypoint file.  The waypoint file is read 
in when selecting Waypoint Assist.  When reaching the final waypoint, the Autopilot will go idle.  The Waypoint Assist writes to 
waypoints-completd.json file, marking which Systems that has been reached by setting the Completed entity to true.

## Repeating Waypoints
A set of waypoints can endless be repeated by using a special row at the end of the waypoint file.  When hitting this record, the Waypoint 
Assist will start from the top jumping through the defined Systems until the user ends the Waypoint Assist.
<br>
```py
{ 
"Ninabin":   {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"Wailaroju": {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"REPEAT":    {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}  
}
```

## Docking with a Station
When entering a System via Waypoint Assist, if the DockWithStation is not null and StationCoord are not [0,0], the Waypoint Assist
will go into **SystemMap** and select the Station at the StationCoord X, Y location (i.e. mouse click) to select and plot route to that 
Station. Alternatively and with Odyssey you can set a bookmark for the desired station instead of the x,y coordinates and then enter 
the position of the bookmark in the station list of the **System Map** from top to bottom and starting at 0 in StationBookmark. 
-1 means bookmark is disabled. 
Upon arriving at the station, the SC Assist (which is acting on behalf of the Waypoint Assist), will drop your ship
out of Supercruise and attempt docking.  Once docked, the fuel and repair will automatically be commanded.  The StationCoord can be 
determined by bringing up the SystemMap (and not moving it or adjusting it), going to the EDAPGui interface and selecting 
"Get Mouse X, Y", in the popup select Yes and your next Mouse click needs to be on the Station on the SystemMap.  The [X,Y]
Mouse coordinates will be copied to the Windows clipboard so it can be pasted into your waypoints file.  The X, Y values are
monitor resolution dependent.  So you may not be able to share with others unless they use the same resolution.
NOTE: When bringing up SystemMap
it will show the System the same way and if your Station is not visible (i.e. you have to zoom or move the map) then this
capability cannot be used for that Station.  The Station must be visible when bringing up SystemMap.
<br>
```py
{ 
    "Ninabin":   {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
    "Wailaroju": {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false},
    "Enayex":    {"DockWithStation": "Watt Port", "StationCoord": [1977,509], "StationBookmark": -1, "SellNumDown": 12, "BuyNumDown": 5, "Completed": false}, 
    "Eurybia":   {"DockWithStation": null, "StationCoord": [0,0], "StationBookmark": -1, "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} 
}
```

## Docking with a System Colonisation Ship (Odyssey only)
When entering a System via Waypoint Assist, if the DockWithStation is **'System Colonisation Ship'** and **StationBookmark** is not **'-1'**, then the bookmark number will be used to select the appropriate bookmark from the **systems list** of the **Galaxy Map** from top to bottom and starting at 0 for the top bookmark. *NOTE: System Colonisation Ships are bookmarked in the System bookmarks of the Galaxy Map, not the Station bookmarks of the System Map.* The **'StationCoord'** field is not used for Colonisation Ships.

Upon arriving at the station, the SC Assist (which is acting on behalf of the Waypoint Assist), will drop your ship
out of Supercruise and attempt docking.  Once docked, the fuel and repair will automatically be commanded.

Note for trading: If **'SellNumDown'** is not **'-1'**, upon docking with a System Colonisation Ship, EDAP will sell all commodities that can be sold, regardless of the value of **'SellNumDown'**. **'BuyNumDown'** is ignored as there are no commodities that can be bought from a System Colonisation Ship.

Example below:
```py
{
    "HIP 112113": {"DockWithStation": "Nomen Vision", "StationCoord": [0,0], "StationBookmark": 0, "SellNumDown": -1, "BuyNumDown": 19, "Completed": true},
    "Shui Wei Sector AL-O b6-3": {"DockWithStation": "System Colonisation Ship", "StationCoord": [0,0], "StationBookmark": 0, "SellNumDown": 9999, "BuyNumDown": -1, "Completed": true}
}
```

## Trading
The SellNumDown and BuyNumDown fields are associated with auto-trading.  If either of those number are *not* -1, the 
trade executor kicks in, brings up Commodities and will perform the Sell (if not -1) and then the Buy (if not -1).
The *NumDown value (an integer) represents the number of rows down the commodity of interest is from the top.  Note:  Each Station's 
Commondity list is unique so you need to know for the specific Station your ship is docked at what row number your commodity is 
at.  *NumDown, essentally will IU_Down that number of times.  So you will have to manually perform the trade route once to acquire
the needed data to fill in the waypoints file.

If you try to Sell a Commodity you do not have, the system currently will get stuck as the Sell button is not highlighted.




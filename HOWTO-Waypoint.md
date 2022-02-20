# Waypoints
Waypoints are Systems that are captured in a waypoints.json file and read and processed by this Autopilot.  An example waypoint file is below:

{ 
"Mylaifai EP-G c27-631": {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"Striechooe QR-S b37-0": {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} ,
"Ploxao JV-E b31-1":     {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} ,
"Beagle Point":          {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}   
}

With this waypoint file this Autopilot will take you to Beagle Point without your intervention.  The Autopilot will read and process each
row, plotting the course to that System in the GalaxyMap and executing that route via the FSD Route Assist.  When entering that System, 
if no Station is defined (i.e. null), the assist will plot the route for the next row in this waypoint file.  The waypoint file is read 
in when selecting Waypoint Assist.  When reaching the final waypoint, the Autopilot will go idle.  The Waypoint Assist writes to 
waypoints-completd.json file, marking which Systems that has been reached by setting the Completed entity to true.

## Repeating Waypoints
A set of waypoints can endless be repeated by using a special row at the end of the waypoint file.  When hitting this record, the Waypoint 
Assist will start from the top jumping through the defined Systems until the user ends the Waypoint Assist.

{ 
"Ninabin":   {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"Wailaroju": {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
"REPEAT":    {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}  
}

## Docking with a Station
When entering a System via Waypoint Assist, if the DockWithStation is not null and StationCoord are not [0,0], the Waypoint Assist
will go into SystemMap and select the Station at the StationCoord X, Y location (i.e. mouse click) to select and plot route to that 
Station.  Upon arriving at the station, the SC Assist (which is acting on behalf of the Waypoint Assist), will drop your ship
out of Supercruise and attempt docking.  Once docked, the fuel and repair will automatically be commanded.  The StationCoord can be 
determine by bringing up the SystemMap (and not moving it or adjusting it), going to the EDAPGui interface and selecting 
"Get Mouse X, Y", in the popup select Yes and your next Mouse click needs to be on the Station on the SystemMap.  The [X,Y]
Mouse coordinates will be copied to the Windows clipboard so it can be pasted into your waypoints file.  NOTE: When bringing up SystemMap
it will show the System the same way and if your Station is not visible (i.e. you have to zoom or move the map) then this
capability cannot be used for that Station.  The Station must be visible when bringing up SystemMap.

{ 
    "Ninabin":   {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false}, 
    "Wailaroju": {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false},
    "Enayex":    {"DockWithStation": "Watt Port", "StationCoord": [1977,509], "SellNumDown": 12, "BuyNumDown": 5, "Completed": false}, 
    "Eurybia":   {"DockWithStation": null, "StationCoord": [0,0], "SellNumDown": -1, "BuyNumDown": -1, "Completed": false} 
}

## Trading
The SellNumDown and BuyNummDown fields are associated with auto-trading.  If either of those number are *not* -1, the 
trade executor kicks in, brings up Commodities and will perform the Sell (if not -1) and then the Buy (if not -1).
The *NumDown value (an integer) represents the number of rows down the commodity of interest is from the top.  Note:  Each Station's 
Commondity list is unique so you need to know for the specific Station your ship is docked at what row number your commodity is 
at.  *NumDown, essentally will IU_Down that number of times.  So you will have to manually perform the trade route once to acquire
the needed data to fill in the waypoints file.

If you try to Sell a Commodity you do not have, the system currently will get stuck as the Sell button is not highlighted




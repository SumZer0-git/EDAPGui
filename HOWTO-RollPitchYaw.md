# Roll, Pitch, Yaw (RPY)
The values for Pitch and Yaw are critical for proper Autopilot behavior. Currently the Autopilot does not utilize Yaw
as it is much to slow.  A saved set of rates should be maintained for each ship you plan to use with this Autopilot.
Use the "Save As" under the File menu to do so.  Also, use Open to load these rates before you begin using any
of the Assistants this Autopilot provides.

Take the RPY values from Outfitting, pay attention to the order, it is Pitch, Roll, Yaw in Outfitting.  Also pay
attention to the order on the GUI as it is Roll, Pitch, Yaw.

The RPY values from Outfitting are the rates the ship can achieve while in normal space, while in supercruise
the rates are much lower.  Since Autopilot utilizes these rates in Supercruise, they must be adjusted.  See tests
done by one CMDR: https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/.  
Also see: https://lavewiki.com/ship-control

To start, use the values from Outfitting.  The maneuver to align to target first performs roll to get the target
on the plus or minus Y axis.  If the roll overshoots, then increase the value in the Roll field as the Roll rate
is higher.  When the ship pitches, if you notice multiple control events (slight pause while pitching), before
arriving at the Target then the pitch rate value needs to be reduce (do increments of 5 at most).  If the pitch 
overshoots the target then the pitch value needs to be increased.   Overshooting translates into not being able to 
control properly, it is better to underperform than overshoot.  

How to adjust while ED has focus.  Use the Hot keys.  Configure a route in GalaxyMap and then adjust the ship 
orientation away from target, then use the hot to enable FSD Route Assist ("home").  Once the assistant rolls and pitches
use the hot key "(end") to terminate the assistant.   Adjust your values on the GUI, reselect ED to give it focus and 
re-enable FSD Route Assist.

As of this writing, only the DBX, ASPX, Cutter, and Sidewinder configuration files (RPY values) were tested.  
Additional configs were provided in this release but not tested (based on values from Outfitting)
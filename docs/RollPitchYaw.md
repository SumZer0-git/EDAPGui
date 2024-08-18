# Roll, Pitch, Yaw (RPY)
The values for Pitch and Roll are critical for proper Autopilot behavior. Currently the Autopilot does not utilize Yaw
as it is much to slow.  A saved set of rates should be maintained for each ship you plan to use with this Autopilot.
Use the "Save As" under the File menu to do so.  Also, use Open to load these rates before you begin using any
of the Assistants this Autopilot provides.

Take the RPY values from Outfitting, pay attention to the order, it is Pitch, Roll, Yaw in Outfitting.  Also pay
attention to the order on the GUI as it is Roll, Pitch, Yaw.

The RPY values from Outfitting are the rates the ship can achieve while in normal space, while in supercruise
the rates are much lower.  Since Autopilot utilizes these rates in Supercruise, they must be adjusted.  See tests
done by one CMDR: https://forums.frontier.co.uk/threads/supercruise-handling-of-ships.396845/.  
Also see: https://lavewiki.com/ship-control

1. To start, use the values from Outfitting or start with the values from another similar ship.  
2. Go into supercruise with a space station as target. Set speed to zero.
3. For the Roll Rate:
   1. Maneuver so that the navigation dot is to the far right of the compass (at the 3 o'clock position).
   2. Enable Supercruise Assist. The ship should roll so that the navigation dot is at 12 o'clock. If the roll
   overshoots, then increase the value in the Roll field, decrease if the roll undershoots. Ignore the pitch 
   at this time.
   3. Repeat the above a couple of times until the roll rate is acceptable.
4. For the Pitch Rate:
   1. Maneuver so that the navigation dot is in the center of the compass but behind the ship.
   2. Enable Supercruise Assist. The ship will pitch the 180 deg up/down in 90 deg steps with a slight pause after each.
   If the rate is set correctly, the first pause will be at top or bottom of the compass and the ship will stop when the
   target is dead ahead. If the pitch overshoots the target then the pitch value needs to be increased. Overshooting 
   translates into not being able to control properly, it is better to undershoot than overshoot.  
   3. Repeat the above a couple of times until the pitch rate is acceptable.

How to adjust while ED has focus.  Use the Hot keys.  Configure a route in GalaxyMap and then adjust the ship 
orientation away from target, then use the hot to enable FSD Route Assist ("home").  Once the assistant rolls and pitches
use the hot key "(end") to terminate the assistant.   Adjust your values on the GUI, reselect ED to give it focus and 
re-enable FSD Route Assist.

As of this writing, only the DBX, ASPX, Cutter, and Sidewinder configuration files (RPY values) were tested.  
Additional configs were provided in this release but not tested (based on values from Outfitting)
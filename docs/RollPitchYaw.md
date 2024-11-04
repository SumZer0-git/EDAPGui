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
2. Go into supercruise with a system as target. Set speed to 50%.
3. For the Roll Rate:
   1. Maneuver so that the navigation dot is at the top of the compass (at the 12 o'clock position).
   2. Press the Test Roll button. The ship will roll 360 degrees so that the navigation dot is at 12 o'clock again.
   3. If the roll overshoots, then increase the value in the Roll field, decrease if the roll undershoots. Overshooting 
   translates into not being able to control properly, it is better to undershoot than overshoot.
   4. Repeat the above a couple of times until the roll rate is acceptable.
4. For the Pitch Rate:
   1. Maneuver so that the navigation dot is in the center of the compass ahead of the ship.
   2. Press the Test Pitch button. The ship will pitch 360 degrees so that the navigation dot is at the center again.
   3. If the pitch overshoots target then the pitch value needs to be increased, decrease if pitch undershoots. Overshooting 
   translates into not being able to control properly, it is better to undershoot than overshoot.  
   4. Repeat the above a couple of times until the pitch rate is acceptable.
5. For the Yaw Rate:
   1. Maneuver so that the navigation dot is in the center of the compass ahead of the ship.
   2. Press the Test Yaw button. The ship will yaw 360 degrees so that the navigation dot is at the center again.
   3. If the pitch overshoots target then the yaw value needs to be increased, decrease if yaw undershoots. Overshooting 
   translates into not being able to control properly, it is better to undershoot than overshoot.  
   4. Repeat the above a couple of times until the pitch rate is acceptable.
6. Save your settings.

As of this writing, only the DBX, ASPX, Cutter, and Sidewinder configuration files (RPY values) were tested.  
Additional configs were provided in this release but not tested (based on values from Outfitting)
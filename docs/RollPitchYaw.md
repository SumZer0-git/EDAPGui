# Ship roll, pitch, and yaw tuning

EDAPGui uses each ship's roll, pitch, and yaw rates to estimate how long to hold its controls while aligning in
supercruise. The rates differ between ships and may need tuning for reliable alignment. EDAPGui loads the profile
for the active ship automatically; the values and test buttons are in the **SHIP** panel on the **Main** tab.

Outfitting lists rates in **Pitch, Roll, Yaw** order; the EDAPGui fields are **Roll, Pitch, Yaw**. Outfitting values
are a starting point: ship rotation is slower in supercruise, so check and tune the values in-game.

## Tune the rates

1. Use the ship's outfitting rates as a starting point, keeping in mind the different order in the game and EDAPGui.
   The currently active ship profile is loaded automatically.
2. Enter supercruise and select a system as the target. For **Roll**, place the navigation dot at the top of the
   compass. For **Pitch** and **Yaw**, place it in the center.
3. Select the matching **Test Roll Rate**, **Test Pitch Rate**, or **Test Yaw Rate** button in the **SHIP** panel.
   EDAPGui checks that the ship is in supercruise and has a target, sets speed to 50%, then performs a 360-degree
   maneuver (roll left, pitch up, or yaw left, respectively).
4. Compare the navigation dot with its starting position. If the maneuver overshoots, increase that rate; if it
   undershoots, decrease it. Repeat until the maneuver finishes close to its starting position. A slight undershoot
   is preferable to a substantial overshoot.
5. Open **Settings** and select **Save All Settings** to save the current ship's rates.

The rates are stored per ship in `user_data/configs/ship_configs.json` and loaded when the active ship changes. The
optional **SunPitchUp +/- Time** field can adjust pitch time for ships that need more clearance from a star.

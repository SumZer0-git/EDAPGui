# Main

## Main Tab

![Main](../screen/Main.png)

## Mode

### FSD Route Assist
For the FSD Route Assist, you select your destination in the GalaxyMap and then enable this assistant and it will perform all the jumps to get you to your destination, AFK.  Furthermore while
executing route assistance it will perform detailed system scanning (honk) when jumping into a system and optionally perform FSS scanning
to determine if Earth, Water, or Ammonia type world is present.
### Supercruise Assist
The supercruise (SC) assistant (and not using ED's SC Assist which takes up a slot, for a piece of software?) 
will keep you on target and when "TO DISENGAGE" is presented and will autodrop out of SC and perform autodocking with the targeted Station. <br>
### Waypoint Assist
With Waypoint Assist you define the route in a file and this assist will jump to those waypoints.  If a Station is defined to dock at, the assistant will transition to SC Assist and
dock with the station.  A early version of a trading capability is also included.<br>
Additional information on Waypoints can be found [here](docs/Waypoint.md).
Additional information on the Waypoint Editor tab can be found [here](docs/WaypointEditor.md).
### Robigo Mines Assist
The Robigo Assist performs the Robigo Mines passenger mission loop which includes mission selection, mission completetion, and the full loop to Sirius Atmospherics.<br>
Additional information can be found [here](docs/Robigo.md). 
### AFK Combat Assist
* AFK Combat Assist: used with a AFK Combat ship in a Rez Zone.  It will detect if shields have
    dropped and if so, will boost away and go into supercruise for ~10sec... then drop, put pips to
    system and weapons and deploy fighter, then terminate.  While in the Rez Zone, if your fighter has
    been destroyed it will deploy another fighter (assumes you have two bays)
### DSS Assist
TBD

## Ship

* SunPitchUp+Time - field are for ship that tend to overheat. Providing 1-2 more seconds of Pitch up when avoiding the Sun
    will overcome this problem.  This will be Ship unique and this value will be saved along with the Roll, Pitch, Yaw values 
* Tuning - See below.

## Tuning Overview
Each ship type has different RPY (Roll, Pitch and Yaw) rates which are affected by the throttle position. 
When in space (not SC), the RPY rates are also affected by engineering (and pips). 
All rates are also affected by the mass of the ship, the ship moving slower at the beginning of movement that at the end.

Curves are defined separately for R, P and Y for the following, giving 18 curves at this time:
* In space (not SC) at 0%, 50% and 100% throttle.
* In Supercruise at 0%, 50% and 100% throttle.

The curve is used to determine the keypress time based on the difference between the current position and the target position.

Notes:
* The tuning is **never** going to be 100% perfect all the time.
* Not all curves are used all the time, so you may find tuning at **Supercruise 50%** works great, but **in-space 0%** needs more tuning.
* There is no way to reliably detect the throttle position, so the program determines the throttle position from the last throttle demand.
* Don't use auto-tune when approaching moving targets like fast orbiting stations. Auto-tune will not be able to accurately calculate how far the ship moved.

## Tuning GUI

* Enable Auto-tune RPY - Enables auto-tune. With auto-tune on, the RPY curves will be updated based on the ship movements automatically. It does this by estimating the keypress time required and determining how much the ship moved and logging that value. Enable auto-tune until the ship responds well and then disable.
* 0%/50%/100% Throttle - Changes the throttle demand for the Align to Target. 
* Align to Target - The Align to Target button will use the existing curves to center on the target based on the current position. If the movement under-shoots or over-shoots, then either enable Auto-tune and repeat to see if the curve is updated, or manually change the curve for that angle and repeat.
* Throttle dropdown - Selects a throttle position. Used for the Edit Curve buttons below.
* Edit Roll/Pitch/Yaw Curves - Edits the R/P/Y curve for the throttle selection in the throttle dropdown.

## Tuning Process
The process is pretty simple.
1. Enable auto-tune and use EDAP, ideally FSD Assist and SC Assist (not close to stations) to gather training data.
2. Once auto-tune has stopped gathering data, disable auto-tune.
3. Review the RPY curves for each throttle position. Some may just contain default data which is fine.
4. Remove any bad data (see below). Close and save the curve.

To fill in any missing data, or fine-tune, use the **Align to Target** button process. The following would be the process if the Yaw curve needs to be updated because the ship over-shoots the target:
1. Enable Auto-tune.
2. Enter/exist Supercruise as necessary.
3. Use the three throttle buttons to set the correct throttle position.
4. Manually line up at the desired position (i.e. target just to the right of the screen).
5. Press **Align to Target**. The ship will estimate the keypress time and will attempt to move to position.
6. The curve will be updated if required.
7. If the target was not reached in one go, try repeating with the target closer and farther.
8. You may also update the curve manually and try again. Lowering the RPY Rate will increase the keypress time.
9. Once complete, disable Auto-tune.

## Log
A read only log.
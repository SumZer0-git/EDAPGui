  
# Approach
## FSD Assist FLow
* Leave space station if docked.
* Enter supercruise if necessary.
* Align to selected system.
* Jump to system.
* When entering a new System, Speed to 0
* Pitch up until sun is out of field of view
* Accelerate to 100 for "some #" of seconds, speed to 50, fuel scooping will start
* If our fuel is below a threshold (hardcode, need to lookup) then put speed to 0
* If refuel required then wait for refuel complete or <#> sec elapsed
* Accel back to 100, delay some seconds while we get away from Sun
* Perform DSS on the System
* If ELW Scanner enabled, go into FSS, do image matching in specific region looking for filled circle or frequency signal present.
  If so, log wether an Earth, Water or Ammonia world based on where the frequency signal is at in the image
* Perform Nav align looking at the Compass on the console, perform roll and pitch based on Nav point in the compass
* Perform Target align (as the target should be pretty close in front of us) 
* If reached destination system then terminate, however if we still have a target to a Station, then auto-enable SC Assist
  else have not reach destination, so issue FSD and loop 
 
## SC Assist Flow
* Leave space station if docked.
* Enter supercruise if necessary.
* Loop: 
  * Do Target align, keeping is us a tight deadband on the target
  * Do image match checking to see if SC Disengage pops up, if so, break loop
  * Check for interdiction, if so execut response 
  * Check for Station occluded by the Planet, if so maneauver around planet
* Accel for ~10sec... then put speed to 0 (this put us < 7.5km)
* Do Left Menu... Right twice to get to Contact and the Right to request docking
  * Do this up to 3 times, if needed
  * if docking rejected, put that info in the log
* If docking accepted, we are at speed 0 so let Docking Computer take over
* wait for up to 120 sec for dock complete... select refuel and repair
* If a trade is defined, execute the trade

## Waypoint Assist Flow
* prompt/open/readin  waypoint file
* Loop:
  * get next waypoint System name, perform GalMap selection plotting for System
  * execute FSD Route Assist
  * if waypoint defines Station to dock with Station Coord
    * Open SystemMap select Station by Mouse clicking/hold at X, Y location defined in the file
    * execute SC Assist to travel and dock with station
    * when docked, refuel, repair
    * if a trade is defined (*NumDown fields are not -1) then execute the trade
    * undock from station
 
# Enhancement ideas
* A lot more error trapping needs to be put into the code, there is also a lot of corner cases to deal with
* Handle Thargoid interdiction will in Hyperspace
* Enhance SC Interdiction flow (hard to test)
* FSS/ELW screen region needs to be able to handle diff screen resolutions

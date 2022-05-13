
# Robigo Mines Passenger Loop (BETA)

## Run Details
- Expect $15m/loop
- Expect 17-20min per loop

## What does it do?
- Completes Robigo Mines to Sothis Athmospherics passenger missions
- Performs Mission Completion, Mission selection (fills cabins), executes the loop, docks and 
  loop again

## Constraints:
- This assists determines where you are in the loop and continues from there, otherwise
  will jump you to Robigo Mines
- Odyssey only (due to unique Mission Selection and Mission Completion menus)
- Must perform 1 Robigo loop manually
    - This will ensure that Siruis Atmospherics will be on the Nav Panel on subsequent runs
    - i.e. you must travel to Sothis A5 or Don's Inheretence, when you get less then 1000 ls, Sirius Atmospherics will
      show up in Nav Panel.  Select/Lock target to it.  From this point on (in the current session of ED) 
      Sirius Atmospheric will be on Nav Panel (which is required by this script)
- Set Nav Menu Filter to: Stations and POI only
    - Removes the clutter and allows faster selection of Robigo Mines and Sirius Atmos
- Must have Advanced Docking Computer, don't need a SC Assist module
- Does not handle interdiction and you could be attacked at Sirius Atmos if you have
  illegal passengers (AP does nothing to help with this)

## Testing
- Has only been tested with a Python ship
- Tested with resolutions of 1920x1080, 2560x1080, and 3440x1440

## Observed Behaviors
- If Robigo Mines outpost is behind the Rings as you approach, the ship will drop out of SC
  with "Too Close"..  you must terminate the AP and manually dock 
- The Cabin Autofill option is very poor (in the game), it does not optimize putting the passengers into 
  optimal cabins.  This reduces the payout

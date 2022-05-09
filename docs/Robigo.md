
# Robigo Mines Passenger Loop (BETA)

## To run
python robigo.py
'End' key used to termate the running Robigo AP
<not integrated with the GUI yet>

## Run Details
- Expect $15m/loop
- Expect 17-20min per loop

## What does it do?
- Completes Robigo Mines to Sothis Athmospherics passenger missions
- Performs Mission Completion, Mission selectsion (fills cabins), executes the loop, docks and 
  loop again

## Constraints:
- Must start off docked at Robigo Mines
- Odyssey only (due to unique Mission Selection and Mission Completion menus)
- Must perform 1 Robigo loop manually
    - This will ensure the Siruis Atmospherics will be on the Nav Panel on subsequent runs
    - i.e. you must travel to Sothis A5, when you get less then 1000ls, Sirius Atmospherics will
      show up in Nav Panel.  Select/Lock target
- Set Nav Menu Filter to: Stations and POI only
    - Removes the clutter and allows faster selection of Robigo Mines and Sirius Atmos
- Hardcoded Python setting
  - been running with a Python, not sure if the Nav Panel is same on other ships
- Must have Advanced Docking Computer, don't need a SC Assist module
- Does not handle interdiction and you could be attacked at Sirius Atmos if you have
  illegal passengers (AP does nothing to help with this)

## Observed Behaviors
- Sometime when exiting Supercruise at Sirius Atmospherics, the ship is still 700-800km away
- If Robigo Mines outpost is behind the Rings as you approach, the ship will drop out of SC
  with "Too Close"..  you must terminate the AP and manually dock 
- The Cabin Autofill option is very poor (in the game), it does not optimize putting the passengers into 
  optimal cabins.  This reduces the payout

# EDAPGui Calibration
This document explains how to perform calibration for the Elite Dangerous Autopilot (GUI) version.  You will need to perform this calibration step if the behavior of EDAPGui on your system is endless Pitching up when activating the FSD Assist.  For some user systems this calibration is needed to determine the proper scaling value for the images in the template directory.  These are dependant on screen/game resolution.   The template images were created on a 3440x1440 resolution monitor and require scaling for other target computers.

A configuration file called _config-resolution.json_ contains Screen resolution and scaling values.  This calibration sequence will update that configuration files entry called 'Calibrated'.   If those values are not -1.0 then, at startup, the EDAPGui will use those values.  Otherwise it will look for another entry that matches the users screen resolution.  This calibration exercise should only need to be done once on your system.  

``` Note: If you pull from the github repo again, the config-resolution.json will be overwritten and you will need to re-execute this calibration ```

The calibration algorithm will try matching the template images to your ED screen by looping through scaling factors and picking the most optimal scale based on the match percentage.<br>
``` Note: No commands will be sent to ED during this calibration, it will simply be performing screen grabs. ```

Also see:  HOWTO-RollPitchYaw.md on how to adjust your autopilot performance while maneuvering to target.

# Setup
* Start Elite Dangerous (ED)
* Set the ED configuration to be
    * In Supercruise (%0 thrust is ok)
    * Target system selected
    * Align to the target, as show in this screenshot:<br>
![Alt text](../screen/screen-cap-calibrate.png?raw=true "Calibrate ED Config")  

# To run the calibration
* Start EDAPGui
* Under the File menu, click 'Calibrate'
* Select OK from the popup
  * Two blue boxes appear, one around the compass and one around the center of the screen
  * Ensure that the compass and target are visible within these areas
  * The calibration will likely take less than 1 minute
  * Red boxes will appear in the blue boxes and will attempt to find matching images. When a match is found, a green box will appear over the match. This is the bext match found so far
  * The process is repeated a number of times with different matching thresholds. The green box will always indicate the best match and should be located around the compass and target
  * The match percentabe (0.0 to 1.0) is shown above the green box. A match of > 0.5 for both compass and target is required for success
  * The GUI Window will show the results 
    * Also you can open config-resolution.json to see the selected scaling values for the 'Calibrated' key
* Restart EDAPGui after this process to ensure picking up the correct scaling values

# EDAPGui Calibration
This document explains how to perform calibration for the Elite Dangerous Autopilot (GUI) version.   For some user systems this calibration is needed to determine the proper scaling value for the images in the template directory.  These are dependant on screen/game resolution.   The template images were created on a 3440x1440 resolution monitor and require scaling for other target computers.

A configuration file called _config-resolution.json_ contains Screen resolution and scaling values.  This calibration sequence will update that configuration files entry called 'Calibrated'.   If those values are not -1.0 then, at startup, the EDAPGui will use those values.  Otherwise it will look for another entry that matches the users screen resolution.

The calibration algorithm will try matching the template images to your ED screen by looping through scaling factors and picking the most optimal scale based on the match percentage.<br>
``` Note: No commands will be sent to ED during this calibration, it will simply be performing screen grabs. ```

# Setup
* Start Elite Dangerous (ED)
* Set the ED configuration to be
    * In Supercruise (%0 thrust is ok)
    * Target system selected
    * Align to the target, as show in this screenshot:<br>
![Alt text](screen/screen-cap-calibrate.png?raw=true "Calibrate ED Config")  

# To run the calibration
* Start EDAPGui   > python EDAPGui.py
* Under File, enable _CV View_ , this will allow you to see the calibration in progress, but this is not required
* Select the Calibrate button on the GUI circled in this screenshot"<br>
![Alt text](screen/EDAPGui-calibrate.png?raw=true "Calibrate ED Config") 
* Select OK from the popup
  * The calibration will likely take less than 1 minute
  * The GUI Window will show the results 
    * Also you can open config-resolution.json to see the selected scaling values for the 'Calibrated' key


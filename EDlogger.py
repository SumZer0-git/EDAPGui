import colorlog
import datetime
import logging
import os
from pathlib import Path

_filename = 'autopilot.log'

# Rename existing log file to create new one.
if os.path.exists(_filename):
    filename_only = Path(_filename).stem
    t = os.path.getmtime(_filename)
    v = datetime.datetime.fromtimestamp(t)
    x = v.strftime('%Y-%m-%d %H-%M-%S')
    os.rename(_filename, f"{filename_only} {x}.log")

# Define the logging config.
logging.basicConfig(filename=_filename, level=logging.ERROR,
                    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
                    datefmt='%H:%M:%S')

logger = colorlog.getLogger('ed_log')

# Change this to debug if want to see debug lines in log file
logger.setLevel(logging.WARNING)    # change to INFO for more... DEBUG for much more 

handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)  # change this to what is shown on console
handler.setFormatter(
    colorlog.ColoredFormatter('%(log_color)s%(levelname)-8s%(reset)s %(white)s%(message)s', 
        log_colors={
            'DEBUG':    'fg_bold_cyan',
            'INFO':     'fg_bold_green',
            'WARNING':  'bg_bold_yellow,fg_bold_blue',
            'ERROR':    'bg_bold_red,fg_bold_white',
            'CRITICAL': 'bg_bold_red,fg_bold_yellow',
	},secondary_log_colors={}

    ))
logger.addHandler(handler)

#logger.disabled = True
#logger.disabled = False


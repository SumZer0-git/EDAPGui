"""Remembers the window position, the collapsed state and always-on-top between runs."""

import json

from core import paths
from core.logger import logger

DEFAULTS = {"x": None, "y": None, "collapsed": False, "topmost": False}


def load(file_name=None):
    state = dict(DEFAULTS)
    try:
        with open(file_name or paths.GUI_STATE, "r") as fp:
            stored = json.load(fp)
        for key, default in DEFAULTS.items():
            value = stored.get(key)
            if default is None:
                valid = isinstance(value, int) and not isinstance(value, bool)
            else:
                valid = isinstance(value, bool)
            if valid:
                state[key] = value
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"gui/window_state.py could not read the window state: {e}")
    return state


def save(state, file_name=None):
    target = file_name or paths.GUI_STATE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w") as fp:
            json.dump(state, fp, indent=4)
    except Exception as e:
        logger.warning(f"gui/window_state.py could not write the window state: {e}")

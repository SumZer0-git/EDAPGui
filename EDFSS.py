from __future__ import annotations

import json
import os

from EDAP_data import GuiFocusSystemMap
from EDlogger import logger
from Screen_Regions import load_calibrated_regions, Quad, load_calibrated_regions_quad
from StatusParser import StatusParser
from time import sleep


class EDFSS:
    """ Handles the System Map. """
    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb
        # The rect is top left x, y, and bottom right x, y in fraction of screen resolution
        self.reg = {'full_panel': {'rect': [0.1, 0.1, 0.9, 0.9]},
                    'analysis': {'rect': [0.0, 0.0, 0.25, 0.25]},
                    }
        self.reg_quad: dict[str, Quad] = {
            'full_panel': Quad(),
            'analysis': Quad(),
            }

        # Load custom regions from file
        load_calibrated_regions('EDFSS', self.reg)
        load_calibrated_regions_quad('EDFSS', self.reg_quad)
        pass

def dummy_cb(msg, body=None):
    pass

def main():
    # from ED_AP import EDAutopilot

    #ed_ap = EDAutopilot(cb=None)
    ce = EDFSS(None, cb=dummy_cb)  # False = Horizons
    # ce.create_calibration_tab()


if __name__ == "__main__":
    main()

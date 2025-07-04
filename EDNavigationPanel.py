from __future__ import annotations

from time import sleep
from EDKeys import EDKeys
from OCR import OCR
from Screen import Screen
from StatusParser import StatusParser

"""
File:navPanel.py    

Description:
  TBD 

Author: Stumpii
"""


class EDNavigationPanel:
    """ The Navigation (Left hand) Ship Status Panel. """
    def __init__(self, ed_ap, screen, keys, cb):
        self.ap = ed_ap
        self.ocr = ed_ap.ocr
        self.locale = self.ap.locale
        self.screen = screen
        self.keys = keys
        self.status_parser = StatusParser()
        self.ap_ckb = cb

    def request_docking_ocr(self) -> bool:
        """ Try to request docking with OCR.
        """
        # res = self.show_contacts_tab()
        # if res is None:
        #     return None
        # if not res:
        #     print("Contacts Panel could not be opened")
        #     return False
        #
        # # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # # then go right, which will be "REQUEST DOCKING" and select it
        # self.keys.send("UI_Down")  # go down
        # self.keys.send('UI_Up', hold=2)  # got to top row
        # self.keys.send('UI_Right')
        # self.keys.send('UI_Select')
        # sleep(0.3)
        #
        # self.hide_nav_panel()
        # return True
        pass

    def request_docking(self, toCONTACT):
        """ Request docking from Nav Panel. """
        self.keys.send('UI_Back', repeat=10)
        self.keys.send('HeadLookReset')
        self.keys.send('UIFocus', state=1)
        self.keys.send('UI_Left')
        self.keys.send('UIFocus', state=0)
        sleep(0.5)

        # we start with the Left Panel having "NAVIGATION" highlighted, we then need to right
        # right twice to "CONTACTS".  Notice of a FSD run, the LEFT panel is reset to "NAVIGATION"
        # otherwise it is on the last tab you selected.  Thus must start AP with "NAVIGATION" selected
        if (toCONTACT == 1):
            self.keys.send('CycleNextPanel', hold=0.2)
            sleep(0.2)
            self.keys.send('CycleNextPanel', hold=0.2)

        # On the CONTACT TAB, go to top selection, do this 4 seconds to ensure at top
        # then go right, which will be "REQUEST DOCKING" and select it
        self.keys.send('UI_Up', hold=4)
        self.keys.send('UI_Right')
        self.keys.send('UI_Select')

        sleep(0.3)
        self.keys.send('UI_Back')
        self.keys.send('HeadLookReset')

    def request_docking_cleanup(self):
        """ After request docking, go back to NAVIGATION tab in Nav Panel from the CONTACTS tab. """
        self.keys.send('UI_Back', repeat=10)
        self.keys.send('HeadLookReset')
        self.keys.send('UIFocus', state=1)
        self.keys.send('UI_Left')
        self.keys.send('UIFocus', state=0)
        sleep(0.5)

        self.keys.send('CycleNextPanel', hold=0.2)  # STATS tab
        sleep(0.2)
        self.keys.send('CycleNextPanel', hold=0.2)  # NAVIGATION tab

        sleep(0.3)
        self.keys.send('UI_Back')
        self.keys.send('HeadLookReset')

# Usage Example
if __name__ == "__main__":
    scr = Screen()
    mykeys = EDKeys()
    mykeys.activate_window = True  # Helps with single steps testing
    nav_pnl = EDNavigationPanel(scr, mykeys, None)
    nav_pnl.scroll_to_top_of_list()
    #nav_pnl.find_destination_in_list("ssss")

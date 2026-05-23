import json
import os
import sqlite3
import webbrowser
import tkinter as tk
from tkinter import ttk
from typing import Union, Any, final

from EDlogger import logger


@final
class TceIntegration:
    """ Handles TCE Integration. """

    def __init__(self, ed_ap, cb):
        self.ap_gui = None
        self.ap = ed_ap
        self.ap_ckb = cb
        self.tce_installation_path = self.ap.config['TCEInstallationPath']  # i.e. C:\TCE
        self.tce_shoppinglist_path = self.tce_installation_path + "\\SHOP\\ED_AP Shopping List.tsl"
        self.tce_destination_filepath = self.tce_installation_path + "\\DUMP\\Destination.json"
        self.var_tce_installation_path = tk.StringVar()
        self.var_tce_shoppinglist_path = tk.StringVar()
        self.var_tce_destination_filepath = tk.StringVar()

        # Update GUI
        self.var_tce_installation_path.set(self.ap.config['TCEInstallationPath'])
        self.var_tce_shoppinglist_path.set(self.tce_shoppinglist_path)
        self.var_tce_destination_filepath.set(self.ap.config['TCEDestinationFilepath'])

    def write_shopping_list(self) -> bool:
        """ Write the global shopping list to file.
        @return: True once complete.
        """
        db_path = self.tce_installation_path + "\\DB\\Resources.db"
        public_goods = self.read_resources_db(db_path, 'public_Goods')
        if public_goods is None:
            return False

        sl = self.ap.waypoint.waypoints['GlobalShoppingList']
        if sl is None:
            return False
        global_buy_commodities = sl['BuyCommodities']
        if global_buy_commodities is None:
            return False

        with open(self.tce_shoppinglist_path, "w") as file:
            file.write("<TCE_ShoppingList>\r\n")
            file.write("   <ShoppingListItems\r\n")

            count = len(global_buy_commodities)
            file.write(f"      ItemCount=\"{count}\"\r\n")
            file.write("" + "\r\n")

            # Go through each good and check if it in the shopping list
            index = 1
            for good in public_goods:
                # Go through global buy commodities list
                for i, commodity in enumerate(global_buy_commodities):
                    qty = global_buy_commodities[commodity]
                    # if qty > 0:
                    if good['Tradegood'].upper() == commodity.upper():
                        # print(f"Need {commodity}: {global_buy_commodities[commodity]}")
                        good_id = good['ID']
                        name = good['Tradegood'].upper()
                        price = good['AvgPrice']

                        file.write(f"      Category{index}=\"1\"\r\n")
                        file.write(f"      ItemID{index}=\"{good_id}\"\r\n")
                        file.write(f"      ItemName{index}=\"{name}\"\r\n")
                        file.write(f"      ItemType{index}=\"COMMODITY\"\r\n")
                        file.write(f"      ItemNumber{index}=\"{qty}\"\r\n")
                        file.write(f"      ItemAvgPrice{index}=\"{price}\"\r\n")
                        file.write("\r\n")
                        index = index + 1
                        break

            file.write("   >" + "\r\n")
            file.write("   </ShoppingListItems>" + "\r\n")
            file.write("</TCE_ShoppingList>" + "\r\n")

    def fetch_data_as_dict(self, db_path, query) -> list[Union[dict, dict[str, Any], dict[str, str]]]:
        """ Fetch data from a SQLite database and return as a dictionary of values.
        Example return dictionary:
        [{'ID': 1, 'Tradegood': 'HYDROGEN FUEL', 'Category': 1, 'AvgPrice': 119, 'ED_ID': 128049202}, \
        {'ID': 2, 'Tradegood': 'PESTICIDES', 'Category': 1, 'AvgPrice': 412, 'ED_ID': 128049205}, \
        {'ID': 3, 'Tradegood': 'MINERAL OIL', 'Category': 1, 'AvgPrice': 416, 'ED_ID': 128049203}, \
        {'ID': 4, 'Tradegood': 'EXPLOSIVES', 'Category': 1, 'AvgPrice': 483, 'ED_ID': 128049204}, \
        {'ID': 5, 'Tradegood': 'CONSUMER TECHNOLOGY', 'Category': 2, 'AvgPrice': 6334, 'ED_ID': 128049240}, \
        {'ID': 6, 'Tradegood': 'CLOTHING', 'Category': 2, 'AvgPrice': 523, 'ED_ID': 128049241}]"""
        conn = None
        result = None
        try:
            # Connect to the SQLite database
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # Enables dictionary-like row access
            cursor = conn.cursor()

            # Execute the query
            cursor.execute(query)
            rows = cursor.fetchall()

            # Convert rows to a list of dictionaries
            result = [dict(row) for row in rows]

        except Exception as e:
            # By this way we can know about the type of error occurring
            self.ap_ckb('log', f"Error reading database '{db_path}': " + str(e))
            logger.error(f"Error reading database '{db_path}': " + str(e))

        finally:
            # Close the connection
            conn.close()
            return result

    def read_resources_db(self, filepath: str, table_name: str) -> list[Union[dict, dict[str, Any], dict[str, str]]]:
        """ Reads the resources database. Returns a dict of the data."""
        if table_name == "":
            raise Exception(f"Requested table name is blank.")

        # Connect to the SQLite database (or create it if it doesn't exist)
        if not os.path.exists(filepath):
            raise Exception(f"Database file does not exist: {filepath}.")

        query = f"SELECT * FROM {table_name}"
        data = self.fetch_data_as_dict(filepath, query)
        # print(data)
        return data

    def create_gui_tab(self, ap_gui, tab):
        self.ap_gui = ap_gui
        tab.columnconfigure(0, weight=1)

        # Description
        blk_desc = ttk.LabelFrame(tab, text="Description")
        blk_desc.grid(row=1, column=0, padx=5, pady=5, sticky="NSEW")

        lbl_tce_desc = ttk.Label(blk_desc, text="The Trade Computer Extension Mk.II is a 3rd party app for Elite "
                                                "Dangerous and supports the player in many ways.")
        lbl_tce_desc.grid(row=1, column=0, padx=5, pady=5, sticky="EW")
        lbl_tce_desc1 = ttk.Label(blk_desc, text="It's an overlay, that displays on top of the HUD of Elite "
                                                 "Dangerous, so it's not necessary to ALT-TAB away from the game.")
        lbl_tce_desc1.grid(row=2, column=0, padx=5, pady=5, sticky="EW")

        btn_tce_web = ttk.Button(blk_desc, text='Trade Computer Extension (TCE) forum page',
                                 command=self.goto_tce_webpage)
        btn_tce_web.grid(row=3, column=0, padx=5, pady=5, sticky="W")

        # Options
        blk_options = ttk.LabelFrame(tab, text="Options")
        blk_options.grid(row=2, column=0, padx=5, pady=5, sticky="NSEW")
        blk_options.columnconfigure(1, weight=1)

        lbl_tce_inst = ttk.Label(blk_options, text='TCE Installation Folder (i.e. C:\\TCE)')
        lbl_tce_inst.grid(row=3, column=0, padx=5, pady=5, sticky="NSEW")
        txt_tce_inst = ttk.Entry(blk_options, textvariable=self.var_tce_installation_path)
        txt_tce_inst.bind('<FocusOut>', self.entry_update)
        txt_tce_inst.grid(row=3, column=1, padx=5, pady=5, sticky="NSEW")

        lbl_tce_dest = ttk.Label(blk_options, text='TCE Dest json:')
        lbl_tce_dest.grid(row=4, column=0, padx=5, pady=5, sticky="NSEW")
        txt_tce_dest = ttk.Entry(blk_options, textvariable=self.var_tce_destination_filepath)
        txt_tce_dest.bind('<FocusOut>', self.entry_update)
        txt_tce_dest.grid(row=4, column=1, padx=5, pady=5, sticky="NSEW")

        lbl_tce_shoppinglist = ttk.Label(blk_options, text='Shopping list file (read only):')
        lbl_tce_shoppinglist.grid(row=5, column=0, padx=5, pady=5, sticky="NSEW")
        txt_tce_shoppinglist = ttk.Entry(blk_options, textvariable=self.var_tce_shoppinglist_path)
        txt_tce_shoppinglist.bind('<FocusOut>', self.entry_update)
        txt_tce_shoppinglist.grid(row=5, column=1, padx=5, pady=5, sticky="NSEW")

        # Control
        blk_control = ttk.LabelFrame(tab, text="Control")
        blk_control.grid(row=3, column=0, padx=5, pady=5, sticky="NSEW")

        btn_load_tce = ttk.Button(blk_control, text='Load TCE Destination', command=self.load_tce_dest)
        btn_load_tce.grid(row=1, column=0, padx=5, pady=5, sticky="W")
        lbl_load_tce = ttk.Label(blk_control, text='The current TCE destination will be loaded to the Single Waypoint fields on the debug page.')
        lbl_load_tce.grid(row=1, column=1, padx=5, pady=5, sticky="EW")

        separator = ttk.Separator(blk_control, orient='horizontal')
        separator.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="EW")

        btn_write_shopping = ttk.Button(blk_control, text='Write Global Shopping List', command=self.write_shopping_list)
        btn_write_shopping.grid(row=3, column=0, padx=5, pady=5, sticky="W")
        lbl_write_shopping = ttk.Label(blk_control, text="Writes the Global Shopping List for importing into the TCE shopping panel.")
        lbl_write_shopping.grid(row=3, column=1, padx=5, pady=5, sticky="EW")

    def entry_update(self, event):
        self.tce_installation_path = str(self.var_tce_installation_path.get())
        self.tce_shoppinglist_path = self.tce_installation_path + "\\SHOP\\ED_AP Shopping List.tsl"
        self.tce_destination_filepath = str(self.var_tce_destination_filepath.get())

        self.ap.config['TCEInstallationPath'] = str(self.var_tce_installation_path.get())
        self.ap.config['TCEDestinationFilepath'] = str(self.var_tce_destination_filepath.get())

    def load_tce_dest(self):
        filename = self.ap.config['TCEDestinationFilepath']
        if os.path.exists(filename):
            with open(filename, 'r') as json_file:
                f_details = json.load(json_file)

            if self.ap_gui:
                self.ap_gui.single_waypoint_system.set(f_details['StarSystem'])
                self.ap_gui.single_waypoint_station.set(f_details['Station'])

    @staticmethod
    def goto_tce_webpage():
        webbrowser.open_new("https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/")


def dummy_cb(msg, body=None):
    pass


if __name__ == "__main__":
    from ED_AP import EDAutopilot

    test_ed_ap = EDAutopilot(cb=dummy_cb)

    tce_integration = TceIntegration(test_ed_ap, test_ed_ap.ap_ckb)
    tce_integration.write_shopping_list()

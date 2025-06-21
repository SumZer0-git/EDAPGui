import os
import sqlite3
from typing import Union, Any, final

from EDlogger import logger


@final
class TceIntegration:
    """ Handles TCE Integration. """

    def __init__(self, ed_ap, cb):
        self.ap = ed_ap
        self.ap_ckb = cb
        self.tce_path = self.ap.config['TCEInstallationPath']  # i.e. C:\TCE
        self.tce_destination_filepath = self.tce_path + "\\DUMP\\Destination.json"

    def write_shopping_list(self) -> bool:
        """ Write the global shopping list to file.
        @return: True once complete.
        """
        db_path = self.tce_path + "\\DB\\Resources.db"
        public_goods = self.read_resources_db(db_path, 'public_Goods')
        if public_goods is None:
            return False

        sl = self.ap.waypoint.waypoints['GlobalShoppingList']
        if sl is None:
            return False
        global_buy_commodities = sl['BuyCommodities']
        if global_buy_commodities is None:
            return False

        output_filepath = self.tce_path + "\\SHOP\\ED_AP Shopping List.tsl"
        with open(output_filepath, "w") as file:
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
                    print(f"Need {commodity}: {global_buy_commodities[commodity]}")
                    if good['Tradegood'].upper() == commodity.upper():
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
            self.ap.ap_ckb('log', f"Error reading database '{db_path}': " + str(e))
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


def dummy_cb(msg, body=None):
    pass


if __name__ == "__main__":
    from ED_AP import EDAutopilot

    test_ed_ap = EDAutopilot(cb=dummy_cb)

    tce_integration = TceIntegration(test_ed_ap, test_ed_ap.ap_ckb)
    tce_integration.write_shopping_list()

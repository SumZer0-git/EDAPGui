import unittest
from EDGalaxyMap import EDGalaxyMap


def dummy_cb(msg, body=None):
    pass


class GalaxyMapTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ED_AP import EDAutopilot
        cls.ed_ap = EDAutopilot(cb=dummy_cb)

        scr = cls.ed_ap.scr
        keys = cls.ed_ap.keys
        keys.activate_window = True  # Helps with single steps testing

        cls.gal_map = EDGalaxyMap(cls.ed_ap, scr, keys, dummy_cb, True)

    def test_System1(self):
        """ A single system (no duplicates). """
        system = "ROBIGO"
        res = self.select_system(system)
        self.assertTrue(res, f"Unable to find system {system}")  # add assertion here

    def test_System2(self):
        """ A duplicate system with multiple similar named systems. """
        system = "LHS 54"
        res = self.select_system(system)
        self.assertTrue(res, f"Unable to find system {system}")  # add assertion here

    def test_System3(self):
        system = "Cubeo"
        res = self.select_system(system)
        self.assertTrue(res, f"Unable to find system {system}")  # add assertion here

    def select_system(self, target_name) -> bool:
        """ Select a system in the galaxy map. """
        # from ED_AP import EDAutopilot
        # test_ed_ap = EDAutopilot(cb=dummy_cb)
        #
        # scr = test_ed_ap.scr
        # keys = test_ed_ap.keys
        # keys.activate_window = True  # Helps with single steps testing
        #
        # gal_map = EDGalaxyMap(test_ed_ap, scr, keys, dummy_cb, True)
        return self.gal_map.set_gal_map_destination_text_odyssey(self.ed_ap, target_name)


if __name__ == '__main__':
    unittest.main()

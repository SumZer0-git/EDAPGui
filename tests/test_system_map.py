import unittest
from EDSystemMap import EDSystemMap


def dummy_cb(msg, body=None):
    pass


class SystemMapTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ED_AP import EDAutopilot
        cls.ed_ap = EDAutopilot(cb=dummy_cb)

        scr = cls.ed_ap.scr
        keys = cls.ed_ap.keys
        keys.activate_window = True  # Helps with single steps testing

        cls.sys_map = EDSystemMap(cls.ed_ap, scr, keys, dummy_cb, True)

    def test_Open_System_Map(self):
        """ Open System Map. """
        self.sys_map.goto_system_map()


if __name__ == '__main__':
    unittest.main()

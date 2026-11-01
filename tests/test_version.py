"""Tests for the application version."""

import re
import unittest

from core import version


class VersionTestCase(unittest.TestCase):
    def test_version_is_semantic(self):
        self.assertRegex(version.__version__, r"^\d+\.\d+\.\d+$")

    def test_display_version_is_derived(self):
        self.assertEqual(version.EDAP_VERSION, "V" + version.__version__)
        self.assertTrue(re.match(r"^V\d", version.EDAP_VERSION))


if __name__ == "__main__":
    unittest.main()

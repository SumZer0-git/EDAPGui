"""Tests for the update check (no network access)."""

import unittest
from unittest import mock

import requests

from core import updates


class VersionCompareTestCase(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updates.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(updates.parse_version("V0.10.0"), (0, 10, 0))
        self.assertEqual(updates.parse_version("1.7.0"), (1, 7, 0))

    def test_parse_version_rejects_other_text(self):
        for text in ("", "latest", "v1.2", "1.2.3-beta", "v1.2.3.4"):
            with self.subTest(text=text):
                self.assertIsNone(updates.parse_version(text))

    def test_is_newer(self):
        self.assertTrue(updates.is_newer("v1.7.1", "1.7.0"))
        self.assertTrue(updates.is_newer("v1.10.0", "1.9.0"))
        self.assertFalse(updates.is_newer("v1.7.0", "1.7.0"))
        self.assertFalse(updates.is_newer("v1.6.9", "1.7.0"))

    def test_unparsable_versions_are_never_newer(self):
        self.assertFalse(updates.is_newer("nightly", "1.7.0"))
        self.assertFalse(updates.is_newer("v2.0.0", "unknown"))


class LatestReleaseTestCase(unittest.TestCase):
    @staticmethod
    def response(status, payload=None):
        response = mock.Mock(status_code=status)
        response.json.return_value = payload
        response.raise_for_status.side_effect = requests.HTTPError() if status >= 400 else None
        return response

    def test_returns_the_tag(self):
        with mock.patch.object(updates.requests, "get", return_value=self.response(200, {"tag_name": "v1.8.0"})):
            self.assertEqual(updates.get_latest_release(), "v1.8.0")

    def test_no_release_published(self):
        with mock.patch.object(updates.requests, "get", return_value=self.response(404)):
            self.assertIsNone(updates.get_latest_release())

    def test_server_error(self):
        with mock.patch.object(updates.requests, "get", return_value=self.response(500)):
            self.assertIsNone(updates.get_latest_release())

    def test_network_error(self):
        with mock.patch.object(updates.requests, "get", side_effect=requests.ConnectionError()):
            self.assertIsNone(updates.get_latest_release())


if __name__ == "__main__":
    unittest.main()

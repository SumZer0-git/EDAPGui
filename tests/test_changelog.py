"""Keeps CHANGELOG.md in the Keep a Changelog format that the release workflow reads.

Only the sections in the new format (`## [...]`) are checked; the historical entries below them are left alone.
"""

import re
import unittest
from pathlib import Path

from core.version import __version__

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
ORDER = {"Important notice": -1, "Added": 0, "Changed": 1, "Fixed": 2, "Removed": 3}


def sections():
    text = CHANGELOG.read_text(encoding="utf-8")
    # The historical entries start with a "# <date>" heading and end the new-format sections
    text = re.split(r"^# (?!Changelog)", text, maxsplit=1, flags=re.M)[0]
    return [part for part in re.split(r"^## \[", text, flags=re.M)[1:]]


class ChangelogTestCase(unittest.TestCase):
    def test_keeps_an_unreleased_section_first(self):
        text = CHANGELOG.read_text(encoding="utf-8")

        self.assertRegex(text, re.compile(r"^## \[Unreleased\]\s*$", re.M))
        self.assertTrue(sections()[0].startswith("Unreleased]"))

    def test_released_sections_have_a_dated_heading(self):
        for section in sections()[1:]:
            heading = section.splitlines()[0]
            with self.subTest(heading=heading):
                self.assertRegex("## [" + heading, r"^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$")

    def test_categories_are_known_and_ordered(self):
        for section in sections():
            heading = section.splitlines()[0]
            categories = re.findall(r"^### (.+?)\s*$", section, flags=re.M)
            with self.subTest(section=heading):
                self.assertTrue(all(category in ORDER for category in categories), categories)
                ranks = [ORDER[category] for category in categories if category in ORDER]
                self.assertEqual(ranks, sorted(ranks), categories)
                self.assertEqual(len(categories), len(set(categories)), "duplicate category")

    def test_entries_are_bullets_under_a_category(self):
        for section in sections():
            heading = section.splitlines()[0]
            body = section.split("\n", 1)[1] if "\n" in section else ""
            lines = [line for line in body.splitlines() if line.strip() and not line.startswith("### ")]
            with self.subTest(section=heading):
                self.assertTrue(all(line.startswith("- ") for line in lines), "entries must be '- ' bullets")

    def test_version_has_a_dated_section(self):
        # Enabled in the first release preparation: until then there is no released section in the new format
        if len(sections()) < 2:
            self.skipTest("no released section yet (enable with the first release preparation)")
        headings = [section.splitlines()[0] for section in sections()[1:]]
        self.assertTrue(
            any(heading.startswith(f"{__version__}] - ") for heading in headings),
            f"no dated changelog section for version {__version__}",
        )


if __name__ == "__main__":
    unittest.main()

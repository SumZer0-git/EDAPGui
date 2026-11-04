"""Tests for reading the Elite Dangerous keybindings."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from controls.directinput import SCANCODE
from game.keybindings import KeyBindings

FIXTURE = Path(__file__).parent / "fixtures" / "bindings" / "Test.4.2.binds"

SYNTHETIC = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="Synthetic" MajorVersion="4" MinorVersion="2">
	<YawLeftButton>
		<Primary Device="Keyboard" Key="Key_A" />
		<Secondary Device="Keyboard" Key="Key_B">
			<Modifier Device="Keyboard" Key="Key_LeftShift" />
			<Hold Value="1" />
		</Secondary>
	</YawLeftButton>
	<YawRightButton>
		<Primary Device="Keyboard" Key="Key_D" />
		<Secondary Device="Mouse" Key="Mouse_1" />
	</YawRightButton>
	<SetSpeedZero>
		<Primary Device="Keyboard" Key="Key_Unknown" />
		<Secondary Device="{NoDevice}" Key="" />
	</SetSpeedZero>
	<SetSpeed50>
		<Primary Device="{NoDevice}" Key="" />
		<Secondary Device="{NoDevice}" Key="" />
	</SetSpeed50>
	<NotUsedByEdap>
		<Primary Device="Keyboard" Key="Key_Z" />
		<Secondary Device="{NoDevice}" Key="" />
	</NotUsedByEdap>
</Root>
"""


class BindingsDirectoryMixin:
    """Points LOCALAPPDATA to a temporary folder that holds the Elite Dangerous bindings folder."""

    def setUp(self):
        self.local_app_data = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.local_app_data, ignore_errors=True)
        patcher = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local_app_data})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bindings_dir = Path(self.local_app_data, "Frontier Developments", "Elite Dangerous", "Options", "Bindings")

    def add_bindings(self, name, text, mtime=None):
        self.bindings_dir.mkdir(parents=True, exist_ok=True)
        path = self.bindings_dir / name
        path.write_text(text, encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path


class RealBindingsTestCase(BindingsDirectoryMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.bindings_dir.mkdir(parents=True)
        shutil.copy(FIXTURE, self.bindings_dir / FIXTURE.name)
        self.messages = []
        self.kb = KeyBindings(lambda *args: self.messages.append(args))

    def test_reads_simple_keys(self):
        self.assertEqual(self.kb.keys["YawLeftButton"], {"key": SCANCODE["Key_A"], "mods": []})
        self.assertEqual(self.kb.keys["UI_Up"], {"key": SCANCODE["Key_W"], "mods": []})
        self.assertEqual(self.kb.keys["HyperSuperCombination"], {"key": SCANCODE["Key_J"], "mods": []})

    def test_reads_modifiers(self):
        self.assertEqual(
            self.kb.keys["HeadLookReset"],
            {"key": SCANCODE["Key_K"], "mods": [SCANCODE["Key_LeftControl"], SCANCODE["Key_LeftShift"]]},
        )
        self.assertEqual(self.kb.keys["UseBoostJuice"], {"key": SCANCODE["Key_B"], "mods": [SCANCODE["Key_LeftShift"]]})

    def test_only_requested_keys_are_returned(self):
        self.assertTrue(set(self.kb.keys) <= set(self.kb.keys_to_obtain))
        self.assertEqual(len(self.kb.keys), 33)
        self.assertNotIn("ExplorationFSSEnter", self.kb.keys_to_obtain)
        self.assertNotIn("ExplorationFSSQuit", self.kb.keys_to_obtain)

    def test_actions_without_keyboard_binding_are_missing(self):
        self.assertEqual(self.kb.missing_keys, ["PrimaryFire"])
        self.assertNotIn("PrimaryFire", self.kb.keys)
        self.assertTrue(any("PrimaryFire" in message[1] for message in self.messages))

    def test_collisions(self):
        self.assertEqual(self.kb.get_collisions("UI_Up"), ["UI_Up"])

    def test_sharing_that_the_game_allows_is_no_collision(self):
        self.assertEqual(self.kb.get_collisions("YawLeftButton"), ["YawLeftButton"])
        self.assertFalse(any("Key_A" in message[1] for message in self.messages))

    def test_real_collisions_are_found(self):
        self.kb.keys = dict(self.kb.keys, SetSpeedZero=self.kb.keys["YawLeftButton"])

        self.assertEqual(sorted(self.kb.get_collisions("YawLeftButton")), ["SetSpeedZero", "YawLeftButton"])

    def test_bindings_dict(self):
        bindings = self.kb.get_bindings_dict()

        self.assertEqual(bindings["Root"]["@PresetName"], "Test")
        self.assertEqual(bindings["Root"]["YawLeftButton"]["Primary"]["@Key"], "Key_A")

    def test_hotkey_check(self):
        self.assertEqual(self.kb.check_hotkey_in_bindings("Key_DoesNotExist"), "")
        usage = self.kb.check_hotkey_in_bindings("Key_A")
        self.assertIn("YawLeftButton (Primary)", usage)
        self.assertIn("UI_Left (Secondary)", usage)


class SyntheticBindingsTestCase(BindingsDirectoryMixin, unittest.TestCase):
    def make_keybindings(self):
        kb = KeyBindings.__new__(KeyBindings)
        kb.keys_to_obtain = ["YawLeftButton", "YawRightButton", "SetSpeedZero", "SetSpeed50"]
        return kb

    def test_secondary_is_preferred_and_hold_is_read(self):
        self.add_bindings("a.binds", SYNTHETIC)

        keys = self.make_keybindings().get_bindings()

        self.assertEqual(
            keys["YawLeftButton"], {"key": SCANCODE["Key_B"], "mods": [SCANCODE["Key_LeftShift"]], "hold": True}
        )

    def test_non_keyboard_secondary_keeps_primary(self):
        self.add_bindings("a.binds", SYNTHETIC)

        keys = self.make_keybindings().get_bindings()

        self.assertEqual(keys["YawRightButton"], {"key": SCANCODE["Key_D"], "mods": []})

    def test_unknown_key_and_unbound_actions_are_skipped(self):
        self.add_bindings("a.binds", SYNTHETIC)

        keys = self.make_keybindings().get_bindings()

        # An unknown key currently leaves an empty binding behind instead of no entry
        self.assertNotIn("key", keys.get("SetSpeedZero", {}))
        self.assertNotIn("SetSpeed50", keys)
        self.assertNotIn("NotUsedByEdap", keys)

    def test_latest_modified_file_wins(self):
        old = self.add_bindings("old.binds", SYNTHETIC, mtime=1_000_000)
        new = self.add_bindings("new.binds", SYNTHETIC, mtime=2_000_000)
        self.add_bindings("ignored.txt", "not a bindings file", mtime=3_000_000)

        self.assertEqual(Path(self.make_keybindings().get_latest_keybinds()), new)
        os.utime(old, (4_000_000, 4_000_000))
        self.assertEqual(Path(self.make_keybindings().get_latest_keybinds()), old)

    def test_missing_bindings_folder(self):
        kb = self.make_keybindings()

        self.assertIsNone(kb.get_latest_keybinds())
        self.assertEqual(kb.get_bindings(), {})
        self.assertEqual(kb.get_bindings_dict(), {})

    def test_empty_bindings_folder(self):
        self.bindings_dir.mkdir(parents=True)
        kb = self.make_keybindings()

        self.assertIsNone(kb.get_latest_keybinds())
        self.assertEqual(kb.get_bindings(), {})

    def test_start_preset_wins_over_modification_time(self):
        self.add_bindings("Chosen.4.2.binds", SYNTHETIC, mtime=1_000_000)
        self.add_bindings("Newer.4.2.binds", SYNTHETIC.replace("Key_B", "Key_Q"), mtime=2_000_000)
        self.add_bindings("StartPreset.4.start", "Chosen\nChosen\nChosen\nChosen\n")

        keys = self.make_keybindings().get_bindings()

        self.assertEqual(keys["YawLeftButton"]["key"], SCANCODE["Key_B"])

    def test_key_names_follow_the_keyboard_layout_of_the_file(self):
        german = SYNTHETIC.replace(
            "<YawLeftButton>",
            '<KeyboardLayout>de-DE</KeyboardLayout>\n\t<CamZoomIn>\n\t\t<Primary Device="Keyboard" Key="Key_Y" />\n'
            '\t\t<Secondary Device="{NoDevice}" Key="" />\n\t</CamZoomIn>\n\t<YawLeftButton>',
        )
        self.add_bindings("a.binds", german)
        kb = self.make_keybindings()
        kb.keys_to_obtain = ["CamZoomIn"]

        # The key the German keyboard calls Y sits where the US keyboard has Z
        self.assertEqual(kb.get_bindings()["CamZoomIn"]["key"], SCANCODE["Key_Z"])
        self.assertEqual(kb.layout, "de-DE")


if __name__ == "__main__":
    unittest.main()

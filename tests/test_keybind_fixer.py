"""Tests for the keyboard layout handling and the keybinding fixer."""

import difflib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from controls.directinput import SCANCODE, key_name_for, scancode_for
from game.binds_files import active_binds_files, preset_names
from game.keybind_fixer import (
    CONFLICT,
    GAP,
    HOTKEY,
    REPLACE,
    UNKNOWN_KEY,
    BindsFile,
    apply_changes,
    build_plan,
    load_active_files,
    write_file,
)
from game.keybind_spec import REQUIRED_ACTIONS

FIXTURE = Path(__file__).parent / "fixtures" / "bindings" / "Test.4.2.binds"


def make_file(actions, layout="en-US"):
    """A BindsFile with the given actions, each as (primary, secondary) XML snippets."""
    body = "".join(
        f"\t<{name}>\n\t\t{primary}\n\t\t{secondary}\n\t</{name}>\n" for name, (primary, secondary) in actions.items()
    )
    text = (
        '<?xml version="1.0" encoding="UTF-8" ?>\n<Root PresetName="T" MajorVersion="4" MinorVersion="2">\n'
        f"\t<KeyboardLayout>{layout}</KeyboardLayout>\n{body}</Root>\n"
    )
    return BindsFile(Path("T.4.2.binds"), text)


def key(name, *mods, slot="Primary"):
    mod_xml = "".join(f'<Modifier Device="Keyboard" Key="{m}" />' for m in mods)
    return f'<{slot} Device="Keyboard" Key="{name}">{mod_xml}</{slot}>'


FREE = '<Secondary Device="{NoDevice}" Key="" />'
FREE_PRIMARY = '<Primary Device="{NoDevice}" Key="" />'


def plan_for(file):
    return build_plan({"general": file, "ship": file})


def changes_by_action(plan):
    return {change.action: change for change in plan.changes}


class LayoutTestCase(unittest.TestCase):
    def test_german_names_move_to_the_physical_keys(self):
        self.assertEqual(scancode_for("Key_Y", "de-DE"), SCANCODE["Key_Z"])
        self.assertEqual(scancode_for("Key_Z", "de-DE"), SCANCODE["Key_Y"])
        self.assertEqual(scancode_for("Key_ä", "de-DE"), SCANCODE["Key_Apostrophe"])
        self.assertEqual(scancode_for("Key_ü", "de-DE"), SCANCODE["Key_LeftBracket"])
        self.assertEqual(scancode_for("Key_ß", "de-DE"), SCANCODE["Key_Minus"])
        self.assertEqual(scancode_for("Key_Acute", "de-DE"), SCANCODE["Key_Equals"])
        self.assertEqual(scancode_for("Key_A", "de-DE"), SCANCODE["Key_A"])
        self.assertEqual(scancode_for("Key_Numpad_5", "de-DE"), SCANCODE["Key_Numpad_5"])

    def test_us_names_are_unchanged(self):
        self.assertEqual(scancode_for("Key_Y"), SCANCODE["Key_Y"])
        self.assertEqual(scancode_for("Key_Y", "en-US"), SCANCODE["Key_Y"])
        with self.assertRaises(KeyError):
            scancode_for("Key_ä", "en-US")

    def test_names_are_translated_back(self):
        self.assertEqual(key_name_for(SCANCODE["Key_Z"], "de-DE"), "Key_Y")
        self.assertEqual(key_name_for(SCANCODE["Key_Z"], "en-US"), "Key_Z")
        self.assertEqual(key_name_for(SCANCODE["Key_Apostrophe"], "de-DE"), "Key_ä")
        self.assertIsNone(key_name_for(SCANCODE["Key_Apostrophe"] + 200, "de-DE"))


class PlanTestCase(unittest.TestCase):
    def test_gap_is_filled_with_the_default_of_the_game(self):
        plan = plan_for(make_file({"SetSpeedZero": (FREE_PRIMARY, FREE), "PitchUpButton": (key("Key_Q"), FREE)}))

        change = changes_by_action(plan)["SetSpeedZero"]
        self.assertEqual((change.kind, change.slot, change.new, change.source), (GAP, "Primary", "Key_X", "default"))

    def test_default_is_translated_for_the_layout(self):
        us = changes_by_action(plan_for(make_file({}, "en-US")))["CamZoomIn"]
        german = changes_by_action(plan_for(make_file({}, "de-DE")))["CamZoomIn"]

        # Both mean the same physical key
        self.assertEqual((us.new, german.new), ("Key_Z", "Key_Y"))
        self.assertEqual(us.combo, german.combo)

    def test_gap_without_default_gets_a_single_key(self):
        plan = plan_for(make_file({"SetSpeed50": (FREE_PRIMARY, FREE), "SetSpeed100": (FREE_PRIMARY, FREE)}))

        changes = changes_by_action(plan)
        self.assertEqual((changes["SetSpeed50"].new, changes["SetSpeed50"].source), ("Key_Numpad_5", "preferred"))
        self.assertEqual(changes["SetSpeed100"].new, "Key_Numpad_Add")
        self.assertTrue(all(not change.combo[1] for change in plan.changes))

    def test_supercruise_cruise_speed_gets_its_own_key(self):
        plan = plan_for(make_file({"SetSpeed50": (FREE_PRIMARY, FREE), "SetSpeed75": (FREE_PRIMARY, FREE)}))

        changes = changes_by_action(plan)
        self.assertIn("SetSpeed75", changes)
        self.assertNotEqual(changes["SetSpeed75"].new, changes["SetSpeed50"].new)
        self.assertFalse(changes["SetSpeed75"].combo[1])

    def test_taken_keys_are_skipped(self):
        file = make_file({"SetSpeedZero": (FREE_PRIMARY, FREE), "SomethingElse": (key("Key_X"), FREE)})

        change = changes_by_action(plan_for(file))["SetSpeedZero"]

        self.assertEqual(change.source, "fallback")
        self.assertNotEqual(change.new, "Key_X")

    def test_edap_hotkeys_are_never_proposed(self):
        plan = plan_for(make_file({}))

        for change in plan.changes:
            self.assertNotIn(change.new, ("Key_End", "Key_Insert", "Key_PageUp", "Key_Home"))
        # The default of CycleNextPanel would be Key_E first, End is only its second choice
        self.assertEqual(changes_by_action(plan)["CycleNextPanel"].new, "Key_E")

    def test_existing_keys_are_left_alone(self):
        file = make_file({"YawLeftButton": (key("Key_Q"), FREE), "SetSpeedZero": (key("Key_F2"), FREE)})

        self.assertNotIn("YawLeftButton", changes_by_action(plan_for(file)))
        self.assertNotIn("SetSpeedZero", changes_by_action(plan_for(file)))

    def test_sharing_that_the_game_allows_is_no_conflict(self):
        file = make_file({"YawLeftButton": (key("Key_A"), FREE), "UI_Left": (key("Key_A"), FREE)})

        self.assertNotIn("UI_Left", changes_by_action(plan_for(file)))
        self.assertNotIn("YawLeftButton", changes_by_action(plan_for(file)))

    def test_sharing_with_other_game_modes_is_no_conflict(self):
        file = make_file({"SetSpeedZero": (key("Key_F2"), FREE), "HumanoidFoo": (key("Key_F2"), FREE)})

        self.assertNotIn("SetSpeedZero", changes_by_action(plan_for(file)))

    def test_conflict_moves_the_less_important_action(self):
        file = make_file(
            {
                "UIFocus": (key("Key_U", "Key_LeftShift"), FREE),
                "UI_Back": (FREE_PRIMARY, key("Key_U", "Key_LeftShift", slot="Secondary")),
            }
        )

        changes = changes_by_action(plan_for(file))

        self.assertNotIn("UIFocus", changes)
        change = changes["UI_Back"]
        self.assertEqual((change.kind, change.slot, change.partners), (CONFLICT, "Secondary", ("UIFocus",)))
        self.assertEqual((change.old, change.new), ("Key_LeftShift+Key_U", "Key_Backspace"))

    def test_conflict_with_unneeded_action_moves_the_edap_action(self):
        file = make_file({"SetSpeedZero": (key("Key_F2"), FREE), "Unneeded": (key("Key_F2"), FREE)})

        change = changes_by_action(plan_for(file))["SetSpeedZero"]

        self.assertEqual((change.kind, change.partners), (CONFLICT, ("Unneeded",)))

    def test_replace_when_no_slot_is_free(self):
        mouse = '<Secondary Device="Mouse" Key="Mouse_2" />'
        pad = '<Primary Device="28DE11FF" Key="GamePad_FaceDown" />'

        change = changes_by_action(plan_for(make_file({"PrimaryFire": (pad, mouse)})))["PrimaryFire"]

        self.assertEqual((change.kind, change.slot, change.old), (REPLACE, "Secondary", "Mouse: Mouse_2"))

    def test_gamepad_in_primary_slot_leaves_it_alone(self):
        pad = '<Primary Device="28DE11FF" Key="GamePad_FaceDown" />'

        change = changes_by_action(plan_for(make_file({"SetSpeedZero": (pad, FREE)})))["SetSpeedZero"]

        self.assertEqual((change.kind, change.slot), (GAP, "Secondary"))

    def test_hotkey_and_unknown_key_are_only_reported(self):
        file = make_file({"SetSpeedZero": (key("Key_End"), FREE), "SetSpeed50": (key("Key_Nope"), FREE)})

        plan = plan_for(file)

        notes = {note.action: note.kind for note in plan.notes}
        self.assertEqual((notes["SetSpeedZero"], notes["SetSpeed50"]), (HOTKEY, UNKNOWN_KEY))
        self.assertNotIn("SetSpeedZero", changes_by_action(plan))
        self.assertNotIn("SetSpeed50", changes_by_action(plan))

    def test_each_change_is_planned_once_and_keys_do_not_clash(self):
        plan = plan_for(make_file({}))

        actions = [change.action for change in plan.changes]
        self.assertEqual(sorted(actions), sorted(REQUIRED_ACTIONS))
        # Only the pairs Elite allows may share a key
        shared = {}
        for change in plan.changes:
            shared.setdefault(change.combo, []).append(change.action)
        for actions in shared.values():
            self.assertTrue(
                len(actions) == 1
                or set(actions)
                <= {
                    "YawLeftButton",
                    "UI_Left",
                    "YawRightButton",
                    "UI_Right",
                    "UI_Up",
                    "IncreaseEnginesPower",
                    "UI_Down",
                },
                actions,
            )


class WriteTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def test_fixture_is_fixed_and_nothing_else_changes(self):
        path = self.folder / FIXTURE.name
        shutil.copy(FIXTURE, path)
        original = path.read_bytes()
        file = BindsFile.load(path)
        plan = build_plan({"general": file, "ship": file})

        self.assertEqual(
            {c.action: c.kind for c in plan.changes},
            {"PrimaryFire": REPLACE, "UI_Back": CONFLICT},
        )
        backup = write_file(file, apply_changes(file, plan.changes))

        self.assertEqual(backup.read_bytes(), original)
        changed = path.read_bytes()
        self.assertEqual(b"\r\n" in changed, b"\r\n" in original)
        old_lines, new_lines = original.decode("utf-8").splitlines(), changed.decode("utf-8").splitlines()
        touched = [line for line in difflib.ndiff(old_lines, new_lines) if line[:1] in "+-"]
        self.assertLess(len(touched), 24)
        fixed = BindsFile.load(path)
        self.assertEqual(build_plan({"general": fixed, "ship": fixed}).changes, [])

    def test_replace_shows_both_slots_and_the_chosen_slot_is_overwritten(self):
        pad = '<Primary Device="28DE11FF" Key="Pos_GamePad_RTrigger" />'
        mouse = '<Secondary Device="Mouse" Key="Mouse_2" />'
        file = make_file({"PrimaryFire": (pad, mouse)})
        change = changes_by_action(plan_for(file))["PrimaryFire"]

        self.assertEqual(change.kind, REPLACE)
        self.assertEqual(change.current, {"Primary": "28DE11FF: Pos_GamePad_RTrigger", "Secondary": "Mouse: Mouse_2"})
        change.slot = "Primary"
        fixed = BindsFile(file.path, apply_changes(file, [change]))
        self.assertEqual(fixed.actions["PrimaryFire"]["Secondary"].key, "Mouse_2")
        self.assertTrue(fixed.actions["PrimaryFire"]["Primary"].is_keyboard)

    def test_missing_action_is_added_before_the_end_of_the_file(self):
        file = make_file({"PitchUpButton": (key("Key_Q"), FREE)})
        change = changes_by_action(plan_for(file))["SetSpeedZero"]

        text = apply_changes(file, [change])

        self.assertIn('<SetSpeedZero>\n\t\t<Primary Device="Keyboard" Key="Key_X" />', text)
        self.assertTrue(text.rstrip().endswith("</Root>"))

    def test_modifier_keys_are_written_as_children(self):
        file = make_file(
            {
                "UIFocus": (key("Key_U", "Key_LeftShift"), FREE),
                "UI_Back": (FREE_PRIMARY, key("Key_U", "Key_LeftShift", slot="Secondary")),
            }
        )
        change = changes_by_action(plan_for(file))["UI_Back"]
        change.combo = (SCANCODE["Key_B"], (SCANCODE["Key_LeftControl"], SCANCODE["Key_LeftShift"]))

        text = apply_changes(file, [change])

        self.assertIn('Key="Key_B">\n\t\t\t<Modifier Device="Keyboard" Key="Key_LeftControl" />', text)

    def test_nothing_is_written_if_the_result_cannot_be_verified(self):
        file = make_file({"SetSpeedZero": (FREE_PRIMARY, FREE)})
        change = changes_by_action(plan_for(file))["SetSpeedZero"]
        with mock.patch("game.keybind_fixer._patch", side_effect=lambda f, text, c: text):
            with self.assertRaises(ValueError):
                apply_changes(file, [change])


class ActiveFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def add(self, name, text="x"):
        (self.folder / name).write_text(text, encoding="utf-8")

    def test_start_preset_names_the_files_and_the_highest_version_wins(self):
        for name in ("Mine.4.0.binds", "Mine.4.2.binds", "Other.4.2.binds", "Mine.4.2.binds.1.backup"):
            self.add(name)
        self.add("StartPreset.4.start", "Mine\nOther\nOther\nOther\n")

        files = active_binds_files(self.folder)

        self.assertEqual(files, {"general": self.folder / "Mine.4.2.binds", "ship": self.folder / "Other.4.2.binds"})

    def test_missing_start_file_gives_nothing(self):
        self.add("Mine.4.2.binds")
        self.assertEqual(active_binds_files(self.folder), {})

    def test_builtin_preset_without_file_is_left_out(self):
        self.add("Mine.4.2.binds", make_file({}).text)
        self.add("StartPreset.4.start", "Mine\nAdvancedControlPad2\n")

        self.assertEqual(active_binds_files(self.folder), {"general": self.folder / "Mine.4.2.binds"})
        self.assertEqual(preset_names(self.folder), {"general": "Mine", "ship": "AdvancedControlPad2"})
        self.assertEqual(list(load_active_files(self.folder)), ["general"])

    def test_load_active_files_shares_one_file_between_categories(self):
        self.add("Mine.4.2.binds", make_file({}).text)
        self.add("StartPreset.4.start", "Mine\nMine\n")

        files = load_active_files(self.folder)

        self.assertIs(files["general"], files["ship"])


if __name__ == "__main__":
    unittest.main()

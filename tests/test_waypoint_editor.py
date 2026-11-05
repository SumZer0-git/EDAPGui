"""Route-editor persistence and widget regression tests without the game."""

import copy
import json
import tempfile
import tkinter as tk
import tkinter.font as tkfont
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import ttkbootstrap as ttk

from core import paths
from gui.main_window import APGui
from gui.theme import Metrics, Theme
from gui.waypoint_editor import CommodityList, WaypointEditor, WaypointForm
from gui.waypoint_model import RouteDocument, new_waypoint
from gui.widgets import RoundButton
from gui.window_state import DEFAULTS
from routines.waypoints import EDWayPoint
from tests.test_gui_fields import make_ap
from tests.test_route_import import ONE_WAY, ROUND_TRIP
from tests.test_waypoints import GLOBAL_LIST, stop


class RouteDocumentTestCase(unittest.TestCase):
    def test_shipped_examples_pass_editor_validation(self):
        examples = sorted(paths.WAYPOINT_EXAMPLES_DIR.glob("*.json"))
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example=example.name):
                document = RouteDocument.load(example)
                self.assertEqual(document.load_notes, [])
                document.validate()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.filename = self.directory / "route.json"
        self.progress = self.directory / "progress.json"
        patcher = mock.patch.object(EDWayPoint, "_progress_path", return_value=self.progress)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.document = RouteDocument()
        self.document.data["waypoints"] = [dict(new_waypoint(), SystemName="LHS 20", BuyCommodities={"Polymere": 2})]

    def test_roundtrip_preserves_ids_and_definition_not_progress(self):
        self.document.save(self.filename)
        loaded = RouteDocument.load(self.filename)
        self.assertEqual(loaded.data, self.document.data)
        self.assertFalse(loaded.dirty)
        route = json.loads(self.filename.read_text())
        self.assertNotIn("Completed", route["waypoints"][0])
        progress = json.loads(self.progress.read_text())
        key = route["waypoints"][0]["Id"]
        self.assertEqual(progress["waypoints"][key]["buy_commodities"], {"Polymere": 2})
        self.assertFalse(progress["waypoints"][key]["completed"])

    def test_saved_name_follows_filename_including_save_as(self):
        self.document.data["name"] = "Old display name"
        self.document.save(self.filename)
        self.assertEqual(self.document.data["name"], self.filename.stem)
        target = self.directory / "Another route.json"
        self.document.save(target)
        self.assertEqual(json.loads(target.read_text())["name"], "Another route")
        self.assertFalse(self.document.dirty)

    def test_legacy_load_and_save_upgrades_without_mutating_original(self):
        legacy = {"GlobalShoppingList": GLOBAL_LIST, "1": stop("Sol", Completed=True)}
        self.filename.write_text(json.dumps(legacy))
        with self.assertRaises(ValueError):
            RouteDocument.load(self.filename)
        document = RouteDocument.import_legacy(self.filename)
        self.assertIsNone(document.filename)
        self.assertNotEqual(document.data["waypoints"][0]["Id"], "1")
        self.assertNotIn("Completed", document.data["waypoints"][0])
        target = self.directory / "new.json"
        document.save(target)
        self.assertEqual(json.loads(target.read_text())["version"], 2)
        self.assertEqual(document.source_version, 2)
        self.assertEqual(json.loads(self.filename.read_text()), legacy)

    def test_legacy_import_retains_only_destinations_and_trade_lists(self):
        old = dict(new_waypoint(), SystemName="Sol", StationName="Port", BuyCommodities={"Gold": 2})
        old.update(Skip=True, GalaxyBookmarkType="Fav", GalaxyBookmarkNumber=3, FleetCarrierTransfer=True)
        raw = {"version": 2, "waypoints": [old, {"SystemName": "REPEAT", "Skip": False}]}
        self.filename.write_text(json.dumps(raw))
        before = self.filename.read_bytes()
        document = RouteDocument.import_legacy(self.filename)
        entry = document.data["waypoints"][0]
        self.assertEqual(entry["BuyCommodities"], {"Gold": 2})
        self.assertNotEqual(entry["Id"], old["Id"])
        self.assertTrue(entry["Enabled"])
        self.assertFalse(entry["FleetCarrierTransfer"])
        self.assertEqual(entry["GalaxyBookmarkNumber"], 0)
        self.assertTrue(document.data["Repeat"])
        self.assertIsNone(document.data["RepeatLimit"])
        self.assertFalse(document.data["GlobalShoppingList"]["Enabled"])
        self.assertIsNone(document.filename)
        self.assertTrue(document.dirty)
        self.assertEqual(self.filename.read_bytes(), before)
        self.assertFalse(self.progress.exists())

    def test_legacy_middle_and_disabled_repeat_entries_are_removed_without_enabling_repeat(self):
        for entries in (
            [{"SystemName": "REPEAT", "Skip": False}, {"SystemName": "Sol"}],
            [{"SystemName": "Sol"}, {"SystemName": "REPEAT", "Skip": True}],
        ):
            self.filename.write_text(json.dumps({"version": 2, "waypoints": entries}))
            document = RouteDocument.import_legacy(self.filename)
            self.assertEqual(len(document.data["waypoints"]), 1)
            self.assertFalse(document.data["Repeat"])

    def test_move_preserves_ids_and_tracks_dirty(self):
        second = dict(new_waypoint(), SystemName="Sol")
        self.document.data["waypoints"].append(second)
        self.document.saved = copy.deepcopy(self.document.data)
        self.assertEqual(self.document.move(1, -1), 0)
        self.assertEqual(self.document.data["waypoints"][0]["Id"], second["Id"])
        self.assertTrue(self.document.dirty)
        self.assertEqual(self.document.move(0, -1), 0)

    def test_shared_checks_reject_invalid_bookmarks_but_allow_missing_bookmarks(self):
        first = self.document.data["waypoints"][0]
        first.update(GalaxyBookmarkType="Invalid", GalaxyBookmarkNumber="abc")
        issues = self.document.issues()
        self.assertEqual(
            {issue.field for issue in issues if issue.severity == "error"},
            {"GalaxyBookmarkType", "GalaxyBookmarkNumber"},
        )
        first.update(GalaxyBookmarkType="", GalaxyBookmarkNumber=0, StationName="Test Station", Enabled=True)
        self.assertEqual(self.document.issues(), [])
        first["Enabled"] = False
        self.assertEqual(self.document.issues(), [])
        self.document.data["waypoints"] = [dict(new_waypoint(), SystemName="REPEAT")]
        self.assertTrue(any(issue.severity == "error" for issue in self.document.issues()))

    def test_load_invalid_semantic_fields_for_repair_without_writing(self):
        entry = self.document.data["waypoints"][0]
        entry.update(SystemName="", GalaxyBookmarkType="Bad", GalaxyBookmarkNumber=-4)
        entry["BuyCommodities"] = {"Gold": "invalid"}
        self.filename.write_text(json.dumps(self.document.data))
        before = self.filename.read_bytes()
        document = RouteDocument.load(self.filename)
        self.assertEqual(document.data["waypoints"][0], entry)
        self.assertGreaterEqual(sum(i.severity == "error" for i in document.issues()), 4)
        with self.assertRaises(ValueError):
            document.save(self.filename)
        self.assertEqual(self.filename.read_bytes(), before)
        self.assertFalse(self.progress.exists())

    def test_missing_fields_and_duplicate_ids_are_explicit_repair_notes(self):
        entry = dict(new_waypoint(), SystemName="Sol")
        self.document.data["waypoints"] = [entry, dict(entry)]
        del self.document.data["waypoints"][1]["StationName"]
        self.filename.write_text(json.dumps(self.document.data))
        document = RouteDocument.load(self.filename)
        self.assertTrue(document.load_notes)
        self.assertTrue(document.dirty)
        self.assertEqual(len({entry["Id"] for entry in document.data["waypoints"]}), 2)

    def test_uneditable_json_structure_is_rejected_without_replacing_files(self):
        for data in (
            {"version": 3},
            {"version": 2, "waypoints": [None]},
            {"version": 2, "waypoints": [], "GlobalShoppingList": []},
            {"version": 2, "waypoints": [{"BuyCommodities": []}]},
        ):
            with self.subTest(data=data):
                self.filename.write_text(json.dumps(data))
                before = self.filename.read_bytes()
                with self.assertRaises(ValueError):
                    RouteDocument.load(self.filename)
                self.assertEqual(before, self.filename.read_bytes())

    def test_repair_save_clears_load_notes_and_persists_corrected_fields(self):
        self.filename.write_text(
            json.dumps({"version": 2, "Repeat": False, "RepeatLimit": None, "waypoints": [{"SystemName": "Sol"}]})
        )
        document = RouteDocument.load(self.filename)
        self.assertTrue(document.load_notes)
        document.data["waypoints"][0].update(GalaxyBookmarkType="Fav", GalaxyBookmarkNumber=1)
        document.save(self.filename)
        self.assertFalse(document.load_notes)
        self.assertFalse(document.dirty)
        loaded = RouteDocument.load(self.filename)
        self.assertEqual(loaded.issues(), [])
        self.assertFalse(loaded.load_notes)

    def test_commodity_order_only_changes_are_dirty_and_survive_save_load(self):
        entry = self.document.data["waypoints"][0]
        for values in (
            entry["BuyCommodities"],
            entry["SellCommodities"],
            self.document.data["GlobalShoppingList"]["BuyCommodities"],
        ):
            with self.subTest(values=id(values)):
                values.update({"Gold": 4, "Silver": 6})
                self.document.save(self.filename)
                name, quantity = next(iter(values.items()))
                del values[name]
                values[name] = quantity
                self.assertTrue(self.document.dirty)
                self.document.save(self.filename)
                loaded = RouteDocument.load(self.filename)
                self.assertEqual(json.dumps(loaded.data), json.dumps(self.document.data))
                self.assertFalse(loaded.dirty)

    def test_overwrite_resets_progress_to_edited_definitions(self):
        self.document.save(self.filename)
        self.progress.write_text(json.dumps({"old": "progress"}))
        self.document.data["waypoints"][0]["BuyCommodities"]["Polymere"] = 3
        self.document.save(self.filename)
        progress = json.loads(self.progress.read_text())
        key = self.document.data["waypoints"][0]["Id"]
        self.assertEqual(progress["waypoints"][key]["buy_commodities"], {"Polymere": 3})

    def test_invalid_inputs_do_not_write_files(self):
        for field, value in (("SystemName", ""), ("GalaxyBookmarkNumber", -1), ("BuyCommodities", {"Gold": True})):
            with self.subTest(field=field):
                document = copy.deepcopy(self.document)
                document.data["waypoints"][0][field] = value
                with self.assertRaises(ValueError):
                    document.save(self.filename)
                self.assertFalse(self.filename.exists())
                self.assertFalse(self.progress.exists())

    def test_bookmark_type_requires_positive_position(self):
        self.document.data["waypoints"][0]["GalaxyBookmarkType"] = "Fav"
        with self.assertRaises(ValueError):
            self.document.validate()

    def test_route_write_failure_restores_old_progress_and_keeps_dirty(self):
        self.document.save(self.filename)
        old_route = self.filename.read_bytes()
        old_progress = json.loads(self.progress.read_text())
        self.document.data["name"] = "Edited"
        write = EDWayPoint._write_json_atomically

        def fail_route(filename, data):
            if filename == self.filename:
                raise OSError("test route write failure")
            return write(filename, data)

        with mock.patch.object(EDWayPoint, "_write_json_atomically", side_effect=fail_route):
            with self.assertRaises(OSError):
                self.document.save(self.filename)
        self.assertEqual(self.filename.read_bytes(), old_route)
        self.assertEqual(json.loads(self.progress.read_text()), old_progress)
        self.assertTrue(self.document.dirty)

    def test_new_route_write_failure_removes_new_progress(self):
        write = EDWayPoint._write_json_atomically

        def fail_route(filename, data):
            if filename == self.filename:
                raise OSError("test route write failure")
            return write(filename, data)

        with mock.patch.object(EDWayPoint, "_write_json_atomically", side_effect=fail_route):
            with self.assertRaises(OSError):
                self.document.save(self.filename)
        self.assertFalse(self.progress.exists())
        self.assertFalse(self.filename.exists())

    def test_progress_write_failure_does_not_change_existing_route(self):
        self.document.save(self.filename)
        previous = self.filename.read_bytes()
        self.document.data["name"] = "Edited route"
        with mock.patch.object(EDWayPoint, "_write_json_atomically", side_effect=OSError("test disk failure")):
            with self.assertRaises(OSError):
                self.document.save(self.filename)
        self.assertEqual(previous, self.filename.read_bytes())
        self.assertTrue(self.document.dirty)


class EditorWidgetsTestCase(unittest.TestCase):
    def setUp(self):
        warning_confirmation = mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=True)
        warning_confirmation.start()
        self.addCleanup(warning_confirmation.stop)
        try:
            self.root = ttk.Window(themename="darkly")
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        metrics = Metrics(self.root)
        theme = Theme(self.root, metrics)
        theme.apply()
        self.runtime = SimpleNamespace(
            route_loaded=False, filename=str(paths.WAYPOINTS_DIR / "not-loaded.json"), waypoints={}, executing=False
        )
        self.app = SimpleNamespace(
            ed_ap=SimpleNamespace(waypoint=self.runtime, waypoint_assist_enabled=False),
            WP_A_running=False,
            SWP_A_running=False,
            active_mode=None,
            wp_filelabel=tk.StringVar(master=self.root),
            reset_wp_file=mock.Mock(),
            metrics=metrics,
            theme=theme,
        )
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update_idletasks()

    def test_new_add_move_delete_and_dirty_cancel(self):
        for name in ("Sol", "LHS 20"):
            self.editor.add()
            self.editor.form.variables["SystemName"].set(name)
            self.editor.form.apply()
        self.assertEqual(len(self.editor.tree.get_children()), 2)
        self.editor.move(-1)
        self.assertEqual(self.editor.document.data["waypoints"][0]["SystemName"], "LHS 20")
        with mock.patch("gui.waypoint_editor.messagebox.askyesnocancel", return_value=None):
            self.editor.new()
        self.assertEqual(len(self.editor.document.data["waypoints"]), 2)
        with mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=True):
            self.editor.delete()
        self.assertEqual(len(self.editor.document.data["waypoints"]), 1)

    def test_running_and_stopping_execution_lock_all_edit_actions(self):
        self.runtime.executing = True
        self.editor.set_running()
        self.assertEqual(str(self.editor.route_picker.cget("state")), "disabled")
        self.editor.add()
        self.assertEqual(self.editor.document.data["waypoints"], [])
        self.assertFalse(self.editor.prepare_start())
        self.runtime.executing = False
        self.editor.set_running()
        self.assertEqual(str(self.editor.route_picker.cget("state")), "readonly")

    def test_live_field_validation_marks_errors_but_not_missing_bookmarks(self):
        self.editor.add()
        form = self.editor.form
        self.assertTrue(form.apply_button.disabled)
        self.assertTrue(any(issue.field == "SystemName" for issue in form.live_issues))
        form.variables["SystemName"].set("Sol")
        self.assertFalse(form.apply_button.disabled)
        self.assertEqual(form.live_issues, [])
        form.variables["StationName"].set("Test Station")
        self.assertEqual(form.live_issues, [])
        self.assertFalse(form.apply_button.disabled)
        form.variables["GalaxyBookmarkType"].set("Fav")
        form.variables["GalaxyBookmarkNumber"].set("abc")
        self.assertTrue(form.apply_button.disabled)
        self.assertIn("danger", form.field_widgets["GalaxyBookmarkNumber"].cget("style").lower())
        form.variables["GalaxyBookmarkNumber"].set("1")
        self.assertFalse(form.apply_button.disabled)
        self.assertEqual(form.live_issues, [])
        form.buy.name.set("Gold")
        form.buy.quantity.set("bad")
        self.assertTrue(form.apply_button.disabled)
        self.assertIn("danger", form.buy.quantity_picker.cget("style").lower())
        form.buy.quantity.set("2")
        form.buy.set_item()
        self.assertFalse(form.apply_button.disabled)
        self.assertIn("No issues", form.checks_text.get("1.0", "end"))

    def test_activation_directly_from_list_is_dirty_and_execution_locked(self):
        target = dict(new_waypoint(), SystemName="Sol", GalaxyBookmarkType="Fav", GalaxyBookmarkNumber=1)
        self.editor.document.data["waypoints"] = [target]
        self.editor.document.saved = copy.deepcopy(self.editor.document.data)
        self.editor.refresh()
        self.editor.tree.selection_set(target["Id"])
        self.editor.toggle_selected()
        self.assertFalse(target["Enabled"])
        self.assertTrue(self.editor.document.dirty)
        self.assertIn("Disabled", self.editor.tree.item(target["Id"], "values")[2])
        self.app.WP_A_running = True
        self.editor.toggle_selected()
        self.assertFalse(target["Enabled"])

    def test_active_header_fits_and_themed_checkbox_tracks_activation_and_lock(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        entry = dict(new_waypoint(), SystemName="Sol")
        self.editor.document.data["waypoints"] = [entry]
        self.editor.refresh()
        self.root.update()
        tree = self.editor.tree
        font = tkfont.nametofont("TkDefaultFont", root=self.root)
        self.assertGreaterEqual(tree.column("enabled", "width"), font.measure("Active") + self.app.metrics.px(24))
        button, variable = tree.active_buttons[entry["Id"]]
        self.assertIsInstance(button, ttk.Checkbutton)
        self.assertTrue(button.winfo_ismapped())
        self.assertTrue(variable.get())
        layout = ttk.Style().layout(str(button.cget("style")))
        self.assertEqual(len(layout), 1)
        self.assertTrue(layout[0][0].endswith(".indicator"))
        self.assertNotIn("children", layout[0][1])
        self.assertEqual(button.winfo_reqwidth(), button.winfo_reqheight())
        x, y, width, height = tree.bbox(entry["Id"], "enabled")
        self.assertGreaterEqual(button.winfo_x(), x)
        self.assertLessEqual(button.winfo_x() + button.winfo_width(), x + width)
        self.assertGreaterEqual(button.winfo_y(), y)
        self.assertLessEqual(button.winfo_y() + button.winfo_height(), y + height)
        button.invoke()
        self.assertFalse(entry["Enabled"])
        self.assertFalse(variable.get())
        self.assertTrue(self.editor.document.dirty)
        self.app.WP_A_running = True
        self.editor.set_running()
        self.assertIn("disabled", button.state())
        button.invoke()
        self.assertFalse(entry["Enabled"])

    def test_legacy_import_button_is_inside_import_form_and_keeps_guards(self):
        self.assertFalse(any("Legacy JSON" in button.caption for button in self.editor.buttons))
        self.editor.import_route()
        form = self.editor.form
        with (
            mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=False),
            mock.patch("gui.waypoint_editor.filedialog.askopenfilename") as choose,
        ):
            form.legacy_button.invoke()
        choose.assert_not_called()
        self.assertIs(self.editor.form, form)
        self.runtime.executing = True
        with mock.patch("gui.waypoint_editor.filedialog.askopenfilename") as choose:
            form.legacy_button.invoke()
        choose.assert_not_called()
        self.runtime.executing = False
        document = RouteDocument()
        document.load_notes = ["Legacy route imported."]
        with (
            mock.patch("gui.waypoint_editor.filedialog.askopenfilename", return_value="old.json"),
            mock.patch.object(RouteDocument, "import_legacy", return_value=document) as load,
            mock.patch("gui.waypoint_editor.messagebox.showinfo"),
        ):
            form.legacy_button.invoke()
        load.assert_called_once_with("old.json")
        self.assertIs(self.editor.document, document)
        self.assertIsNone(self.editor.form)

    def test_active_checkboxes_follow_scrolling_and_remove_deleted_rows(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        entries = [dict(new_waypoint(), SystemName=f"System {index}") for index in range(25)]
        self.editor.document.data["waypoints"] = entries
        self.editor.refresh()
        self.root.update()
        tree = self.editor.tree
        first = tree.active_buttons[entries[0]["Id"]][0]
        last = tree.active_buttons[entries[-1]["Id"]][0]
        self.assertTrue(first.winfo_ismapped())
        self.assertFalse(last.winfo_ismapped())
        tree.see(entries[-1]["Id"])
        self.root.update()
        self.assertFalse(first.winfo_ismapped())
        self.assertTrue(last.winfo_ismapped())
        self.editor.document.data["waypoints"] = entries[:-1]
        self.editor.refresh()
        self.root.update()
        self.assertNotIn(entries[-1]["Id"], tree.active_buttons)
        self.assertFalse(last.winfo_exists())

    def test_route_repeat_checkbox_survives_rebuild_without_repeat_waypoint(self):
        self.editor.repeat.set(True)
        self.editor.change_repeat()
        self.assertTrue(self.editor.document.data["Repeat"])
        self.assertEqual(self.editor.document.data["waypoints"], [])
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.assertTrue(self.editor.repeat.get())
        self.assertIsNone(self.editor.document.data["RepeatLimit"])

    def test_form_plot_uses_current_inputs_and_is_locked_during_an_assist(self):
        self.app.ed_ap.set_waypoint_plot = mock.Mock(return_value=True)
        self.app.notify_user = mock.Mock()
        self.editor.add()
        form = self.editor.form
        form.variables["SystemName"].set("LHS 20")
        form.variables["StationName"].set("Ohm City")
        form.plot(True)
        self.app.ed_ap.set_waypoint_plot.assert_called_once()
        entry, station = self.app.ed_ap.set_waypoint_plot.call_args.args
        self.assertEqual(entry["StationName"], "Ohm City")
        self.assertTrue(station)
        self.assertTrue(self.app.SWP_A_running)
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.plot(True)
        error.assert_called_once()
        self.app.ed_ap.set_waypoint_plot.assert_called_once()

    def test_plot_controls_fit_the_scaled_waypoint_content_area(self):
        self.root.geometry(f"{self.app.metrics.px(570)}x{self.app.metrics.px(500)}")
        self.root.deiconify()
        self.editor.pack(fill="both", expand=True)
        self.editor.add()
        self.root.update()
        form = self.editor.form
        for button in form.plot_buttons:
            with self.subTest(button=button):
                self.assertTrue(button.winfo_ismapped())
                self.assertGreaterEqual(button.winfo_rooty(), form.notebook.winfo_rooty())
                self.assertLessEqual(
                    button.winfo_rooty() + button.winfo_height(),
                    form.notebook.winfo_rooty() + form.notebook.winfo_height(),
                )
                self.assertLessEqual(
                    button.winfo_rootx() + button.winfo_width(),
                    form.winfo_rootx() + form.winfo_width(),
                )

    def test_loading_errors_opens_repair_draft_without_runtime_activation(self):
        document = RouteDocument()
        document.data["waypoints"] = [dict(new_waypoint(), SystemName="")]
        self.runtime.load_waypoint_file = mock.Mock()
        with mock.patch.object(RouteDocument, "load", return_value=document):
            self.editor.load_route("repair.json")
        self.assertIs(self.editor.document, document)
        self.runtime.load_waypoint_file.assert_not_called()
        self.assertIn("error", self.editor.tree.item(document.data["waypoints"][0]["Id"], "tags"))
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            self.assertFalse(self.editor.prepare_start())
        error.assert_called_once()

    def test_save_errors_block_before_writes_and_load_notes_require_confirmation(self):
        self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="")]
        with (
            mock.patch("gui.waypoint_editor.messagebox.showerror") as error,
            mock.patch.object(self.editor.document, "save") as save,
        ):
            self.assertFalse(self.editor.save())
        error.assert_called_once()
        save.assert_not_called()
        self.editor.document.data["waypoints"][0]["SystemName"] = "Sol"
        self.editor.document.data["waypoints"][0]["StationName"] = "Test Station"
        self.editor.document.load_notes.append("Review imported route options.")
        with (
            mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=False) as confirm,
            mock.patch.object(self.editor.document, "save") as save,
        ):
            self.assertFalse(self.editor.save())
        self.assertEqual(confirm.call_args.args[0], "Route warnings")
        save.assert_not_called()

    def test_station_without_bookmarks_saves_without_route_warning(self):
        self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="Sol", StationName="Test Station")]
        with (
            tempfile.TemporaryDirectory() as folder,
            mock.patch(
                "gui.waypoint_editor.filedialog.asksaveasfilename", return_value=str(Path(folder) / "route.json")
            ),
            mock.patch("gui.waypoint_editor.messagebox.askokcancel") as confirm,
            mock.patch.object(self.editor.document, "save") as save,
            mock.patch.object(self.runtime, "load_waypoint_file", create=True, return_value=True),
        ):
            self.assertTrue(self.editor.save())
        confirm.assert_not_called()
        save.assert_called_once()

    def test_live_validation_survives_rebuild_with_invalid_bookmark_input(self):
        self.editor.add()
        self.editor.form.variables["SystemName"].set("Sol")
        self.editor.form.variables["GalaxyBookmarkType"].set("Fav")
        self.editor.form.variables["GalaxyBookmarkNumber"].set("not a number")
        self.app.waypoint_form_state = self.editor.form_state()
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update()
        form = self.editor.form
        self.assertTrue(form.apply_button.disabled)
        self.assertEqual(form.variables["GalaxyBookmarkNumber"].get(), "not a number")
        self.assertIn("Bookmark position", form.checks_text.get("1.0", "end"))
        form.variables["GalaxyBookmarkNumber"].set("1")
        self.assertFalse(form.apply_button.disabled)

    def test_loaded_valid_definition_stays_editable_if_runtime_progress_activation_fails(self):
        document = RouteDocument()
        document.filename = Path("test.json").resolve()
        document.data["waypoints"] = [dict(new_waypoint(), SystemName="Sol")]
        self.runtime.load_waypoint_file = mock.Mock(return_value=False)
        with mock.patch.object(RouteDocument, "load", return_value=document):
            self.editor.load_route(document.filename)
        self.assertIs(self.editor.document, document)
        self.assertTrue(document.load_notes)
        self.assertTrue(document.dirty)

    def test_waypoint_icons_have_tooltips_fit_and_obey_execution_lock(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        self.root.update()
        all_icons = [button for button in self.editor.buttons if button.icon_only]
        icon_buttons = all_icons[:6]
        self.assertEqual(len(self.editor.action_tooltips), 8)
        for button in icon_buttons:
            self.assertIsInstance(button, RoundButton)
            self.assertEqual(len(button.itemcget(button.icon_item, "text")), 1)
            self.assertTrue(button.bind("<Enter>"))
            bounds = button.bbox(button.icon_item)
            self.assertGreaterEqual(bounds[0], self.app.metrics.px(8))
            self.assertLessEqual(bounds[2], button.winfo_width() - self.app.metrics.px(8))
        self.assertIs(icon_buttons[0].master, self.editor.action_groups["Create"])
        self.assertIs(icon_buttons[-1].master, self.editor.action_groups["Create"])
        self.assertIs(icon_buttons[2].master, self.editor.action_groups["Edit"])
        self.assertIs(icon_buttons[3].master, self.editor.action_groups["Reorder"])
        for button in all_icons:
            parent = button.master
            self.assertLessEqual(button.winfo_x() + button.winfo_width(), parent.winfo_width())
            self.assertEqual(button.winfo_rooty(), icon_buttons[0].winfo_rooty())
            bounds = button.bbox(button.icon_item)
            self.assertGreaterEqual(bounds[0], self.app.metrics.px(8))
            self.assertLessEqual(bounds[2], button.winfo_width() - self.app.metrics.px(8))
        for button in all_icons[6:]:
            self.assertEqual(len(button.itemcget(button.icon_item, "text")), 1)
        for group in self.editor.action_groups.values():
            buttons = group.winfo_children()
            for left, right in zip(buttons, buttons[1:]):
                self.assertGreaterEqual(right.winfo_x() - left.winfo_x() - left.winfo_width(), self.app.metrics.px(4))
        self.runtime.executing = True
        self.editor.set_running()
        for button in icon_buttons:
            self.assertTrue(button.disabled)
            button.invoke()
            self.assertIsNone(self.editor.form)
        self.runtime.executing = False
        self.editor.set_running()
        icon_buttons[0].invoke()
        self.assertIsNotNone(self.editor.form)

    def test_all_waypoint_views_use_shared_rounded_buttons(self):
        def check(parent):
            for child in parent.winfo_children():
                self.assertNotIsInstance(child, ttk.Button)
                if isinstance(child, RoundButton):
                    self.assertTrue(child.framed)
                    self.assertTrue(child.bind("<Return>"))
                    self.assertTrue(child.bind("<space>"))
                check(child)

        check(self.editor)
        self.editor.add()
        check(self.editor.form)
        self.editor.cancel_form()
        self.editor.edit_global()
        check(self.editor.form)
        self.editor.cancel_form()
        self.editor.import_route()
        check(self.editor.form)

    def test_commodity_action_icons_match_waypoint_actions_and_keep_padding(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        self.editor.add()
        form = self.editor.form
        form.notebook.select(form.buy)
        self.root.update()
        table = form.buy
        self.assertEqual(len(table.action_tooltips), 3)
        originals = [button for button in self.editor.buttons if button.icon_only][2:5]
        for button, original in zip(table.action_buttons, originals):
            self.assertEqual(button.itemcget(button.icon_item, "text"), original.itemcget(original.icon_item, "text"))
            bounds = button.bbox(button.icon_item)
            self.assertGreaterEqual(bounds[0], self.app.metrics.px(8))
            self.assertLessEqual(bounds[2], button.winfo_width() - self.app.metrics.px(8))
        table.values = {"Gold": 1, "Silver": 2}
        table.refresh()
        table.tree.selection_set(table.tree.get_children()[1])
        table.action_buttons[1].invoke()
        self.assertEqual(list(table.values), ["Silver", "Gold"])
        table.action_buttons[0].invoke()
        self.assertEqual(table.values, {"Gold": 1})

    def test_commodity_rows_have_scaled_gaps_and_no_button_overlap(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        self.editor.add()
        tables = (self.editor.form.buy, self.editor.form.sell)
        for global_list in (False, True):
            if global_list:
                self.editor.cancel_form()
                self.editor.edit_global()
                tables = (self.editor.form.buy,)
            for table in tables:
                self.check_commodity_row_spacing(table)

    def check_commodity_row_spacing(self, table):
        self.editor.form.notebook.select(table)
        self.root.update()
        buttons = [child for child in table.winfo_children() if isinstance(child, RoundButton)]
        # Include buttons nested in layout rows.
        for child in table.winfo_children():
            buttons.extend(widget for widget in child.winfo_children() if isinstance(widget, RoundButton))
        setter = next(button for button in buttons if button.caption == "Set")
        bottom = table.tree.winfo_rooty() + table.tree.winfo_height()
        self.assertGreaterEqual(setter.winfo_rooty() - bottom, self.app.metrics.px(8))
        first = table.action_buttons[0]
        self.assertGreaterEqual(
            first.winfo_rooty() - setter.winfo_rooty() - setter.winfo_height(), self.app.metrics.px(8)
        )
        self.assertGreaterEqual(
            table.language_picker.winfo_rooty() - first.winfo_rooty() - first.winfo_height(),
            self.app.metrics.px(8),
        )
        for widget in (setter, *table.action_buttons, table.language_picker):
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(), table.winfo_rooty() + table.winfo_height()
            )

    def test_insert_before_after_and_cancel_preserve_originals(self):
        originals = [dict(new_waypoint(), SystemName=name) for name in ("Sol", "LHS 20")]
        self.editor.document.data["waypoints"] = copy.deepcopy(originals)
        self.editor.refresh()
        self.editor.tree.selection_set(originals[1]["Id"])
        self.editor.insert(False)
        self.editor.form.variables["SystemName"].set("Before")
        self.editor.form.apply()
        self.assertEqual(
            [entry["SystemName"] for entry in self.editor.document.data["waypoints"]], ["Sol", "Before", "LHS 20"]
        )
        self.editor.tree.selection_set(originals[0]["Id"])
        self.editor.insert(True)
        self.editor.form.variables["SystemName"].set("After")
        self.editor.form.apply()
        entries = self.editor.document.data["waypoints"]
        self.assertEqual([entry["SystemName"] for entry in entries], ["Sol", "After", "Before", "LHS 20"])
        self.assertEqual(entries[0], originals[0])
        self.assertEqual(entries[-1], originals[1])
        before = copy.deepcopy(entries)
        self.editor.insert(True)
        self.editor.cancel_form()
        self.assertEqual(self.editor.document.data["waypoints"], before)

    def test_duplicate_uses_definition_fresh_id_and_independent_lists(self):
        original = dict(new_waypoint(), SystemName="Sol", BuyCommodities={"Gold": 5}, SellCommodities={"Silver": 2})
        self.editor.document.data["waypoints"] = [original]
        self.editor.document.filename = Path(self.runtime.filename).resolve()
        self.editor.document.saved = copy.deepcopy(self.editor.document.data)
        self.runtime.waypoints = {
            original["Id"]: {"Completed": True, "BuyCommodities": {"Gold": 0}, "SellCommodities": {"Silver": 0}}
        }
        runtime = copy.deepcopy(self.runtime.waypoints)
        self.editor.refresh()
        self.editor.tree.selection_set(original["Id"])
        self.editor.duplicate()
        self.assertEqual(len(self.editor.document.data["waypoints"]), 1)
        self.editor.form.apply()
        duplicate = self.editor.document.data["waypoints"][1]
        self.assertNotEqual(duplicate["Id"], original["Id"])
        self.assertEqual({**duplicate, "Id": original["Id"]}, original)
        duplicate["BuyCommodities"]["Gold"] = 8
        self.assertEqual(original["BuyCommodities"], {"Gold": 5})
        self.assertEqual(self.runtime.waypoints, runtime)
        self.assertIn("Pending", self.editor.tree.item(duplicate["Id"], "values")[2])
        self.assertTrue(self.editor.document.dirty)

    def test_insert_duplicate_require_selection_and_are_locked_during_execution(self):
        for action in (lambda: self.editor.insert(False), lambda: self.editor.insert(True), self.editor.duplicate):
            with mock.patch("gui.waypoint_editor.messagebox.showinfo") as notice:
                action()
            notice.assert_called_once()
            self.assertIsNone(self.editor.form)
            self.runtime.executing = True
            with mock.patch("gui.waypoint_editor.messagebox.showinfo") as notice:
                action()
            notice.assert_not_called()
            self.assertIsNone(self.editor.form)
            self.runtime.executing = False

    def test_insert_position_and_duplicate_id_survive_widget_rebuild(self):
        original = dict(new_waypoint(), SystemName="Sol")
        self.editor.document.data["waypoints"] = [original]
        self.editor.refresh()
        self.editor.tree.selection_set(original["Id"])
        self.editor.duplicate()
        duplicate_id = self.editor.form.entry["Id"]
        self.editor.form.variables["SystemName"].set("Copy")
        self.app.waypoint_form_state = self.editor.form_state()
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update()
        self.editor.form.apply()
        entries = self.editor.document.data["waypoints"]
        self.assertEqual([entry["SystemName"] for entry in entries], ["Sol", "Copy"])
        self.assertEqual(entries[1]["Id"], duplicate_id)

    def test_widget_rebuild_preserves_unsaved_document(self):
        entry = dict(new_waypoint(), SystemName="LHS 20")
        self.editor.document.data["waypoints"].append(entry)
        document = self.editor.document
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.assertIs(self.editor.document, document)
        self.assertEqual(self.editor.document.data["waypoints"][0], entry)
        self.assertTrue(self.editor.document.dirty)

    def test_cancel_overwrite_preserves_runtime_and_document(self):
        self.editor.document.filename = Path("existing.json").resolve()
        self.editor.document.data["waypoints"].append(dict(new_waypoint(), SystemName="Sol"))
        with (
            mock.patch("gui.waypoint_editor.Path.exists", return_value=True),
            mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=False),
            mock.patch.object(self.editor.document, "save") as save,
        ):
            self.assertFalse(self.editor.save())
        save.assert_not_called()
        self.assertTrue(self.editor.document.dirty)

    def test_open_invalid_route_retains_current_document(self):
        document = self.editor.document
        with (
            mock.patch("gui.waypoint_editor.filedialog.askopenfilename", return_value="invalid.json"),
            mock.patch.object(RouteDocument, "load", side_effect=ValueError("Invalid route")),
            mock.patch("gui.waypoint_editor.messagebox.showerror") as error,
        ):
            self.editor.open()
        self.assertIs(self.editor.document, document)
        error.assert_called_once()

    def test_small_page_keeps_all_controls_visible(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        self.root.update()
        bottom = self.editor.winfo_rooty() + self.editor.winfo_height()
        for button in self.editor.buttons:
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom)
            self.assertGreater(button.winfo_height(), 1, str((button.caption, self.editor.winfo_geometry())))
            self.assertLessEqual(
                button.winfo_rootx() + button.winfo_width(),
                self.editor.winfo_rootx() + self.editor.winfo_width(),
            )

    def test_cancelled_start_does_not_activate_sidebar_mode(self):
        window = APGui.__new__(APGui)
        window.active_mode = None
        window.SWP_A_running = False
        window.ed_ap = SimpleNamespace(single_waypoint_enabled=False)
        window._start_mode = mock.Mock(return_value=False)
        window._refresh_modes = mock.Mock()
        window.set_mode("waypoint", True)
        self.assertIsNone(window.active_mode)
        window._refresh_modes.assert_not_called()

    def test_save_and_start_activate_new_route_and_reload_separate_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "route.json"
            progress = Path(directory) / "progress.json"
            self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="LHS 20")]
            self.runtime.load_waypoint_file = mock.Mock(return_value=True)
            with (
                mock.patch("gui.waypoint_editor.filedialog.asksaveasfilename", return_value=str(target)),
                mock.patch.object(EDWayPoint, "_progress_path", return_value=progress),
            ):
                self.assertTrue(self.editor.prepare_start())
            self.runtime.load_waypoint_file.assert_called_with(str(target))
            self.assertEqual(self.editor.document.filename, target)
            self.assertTrue(progress.exists())

    def test_full_main_window_build_and_rebuild_keep_route_edits(self):
        self.editor.destroy()
        ap = make_ap()
        ap.waypoint = self.runtime
        ap.waypoint_assist_enabled = False
        with mock.patch("gui.main_window.window_state.load", return_value=dict(DEFAULTS)):
            window = APGui(self.root, ed_ap=ap, services=False)
        callback_errors = []
        self.root.report_callback_exception = lambda *error: callback_errors.append(error)
        window.tabs.select(1)
        self.root.deiconify()
        self.root.update()
        editor = window.waypoint_editor
        editor.document.data["waypoints"].append(dict(new_waypoint(), SystemName="Sol"))
        document = editor.document
        self.assertGreater(editor.tree.winfo_height(), 40)
        for button in editor.buttons:
            self.assertGreater(button.winfo_height(), 1)
            self.assertLessEqual(
                button.winfo_rooty() + button.winfo_height(),
                editor.winfo_rooty() + editor.winfo_height(),
            )
            self.assertLessEqual(
                button.winfo_rootx() + button.winfo_width(),
                editor.winfo_rootx() + editor.winfo_width(),
            )
        editor.add()
        self.root.update()
        general = editor.form.notebook.nametowidget(editor.form.notebook.tabs()[0])
        for child in general.winfo_children():
            self.assertLessEqual(child.winfo_y() + child.winfo_height(), general.winfo_height())
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), general.winfo_width())
        editor.form.variables["SystemName"].set("LHS 20")
        editor.form.buy.name.set("Pending commodity")
        editor.form.buy.quantity.set("3")
        editor.form.notebook.select(1)
        window._build_all()
        self.root.update()
        self.assertIs(window.waypoint_editor.document, document)
        self.assertEqual(window.waypoint_editor.document.data["waypoints"][0]["SystemName"], "Sol")
        form = window.waypoint_editor.form
        self.assertEqual(form.variables["SystemName"].get(), "LHS 20")
        self.assertEqual(form.buy.name.get(), "Pending commodity")
        self.assertEqual(form.buy.quantity.get(), "3")
        self.assertEqual(form.notebook.index("current"), 1)
        window.waypoint_editor.cancel_form()
        window.waypoint_editor.import_route()
        form = window.waypoint_editor.form
        form.text.insert("1.0", ONE_WAY)
        self.root.update()
        form.preview()
        item = form.goods.get_children()[0]
        form.goods.selection_set(item)
        self.root.update()
        form.quantity.set("5")
        form.set_quantity()
        form.quantity.set("pending")
        window._build_all()
        self.root.update()
        form = window.waypoint_editor.form
        self.assertIsNotNone(form.route)
        self.assertEqual(form.quantity.get(), "pending")
        self.assertEqual(list(form.quantities.values()), [5])
        self.assertEqual(form.text.get("1.0", "end-1c"), ONE_WAY)
        for child in form.card.winfo_children():
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), form.card.winfo_width())
            self.assertLessEqual(child.winfo_y() + child.winfo_height(), form.card.winfo_height())
        self.editor = window.waypoint_editor
        self.assertEqual(callback_errors, [])
        self.root.unbind("<Configure>")

    def test_cancel_save_prevents_start(self):
        with mock.patch("gui.waypoint_editor.filedialog.asksaveasfilename", return_value=""):
            self.assertFalse(self.editor.prepare_start())

    def test_save_unchanged_does_not_reset_progress(self):
        self.editor.document.filename = Path("test.json")
        with mock.patch.object(self.editor.document, "save") as save:
            self.assertTrue(self.editor.save())
        save.assert_not_called()

    def test_editor_uses_definitions_and_shows_remaining_progress(self):
        entry = dict(new_waypoint(), SystemName="Sol", BuyCommodities={"Gold": 10})
        self.editor.document.data["waypoints"] = [entry]
        self.editor.document.filename = Path(self.runtime.filename).resolve()
        self.editor.document.saved = copy.deepcopy(self.editor.document.data)
        self.runtime.waypoints = {entry["Id"]: {"Completed": True, "BuyCommodities": {"Gold": 0}}}
        self.editor.refresh()
        values = self.editor.tree.item(entry["Id"], "values")
        self.assertIn("Done", values[2])
        self.assertEqual(self.editor.document.data["waypoints"][0]["BuyCommodities"], {"Gold": 10})

    def test_waypoint_summary_displays_all_without_summing_marker(self):
        entry = dict(
            new_waypoint(),
            SystemName="Sol",
            BuyCommodities={"Gold": 9999, "Silver": 3},
            SellCommodities={"Polymere": 9999},
        )
        self.editor.document.data["waypoints"] = [entry]
        self.editor.refresh()
        self.assertEqual(self.editor.tree.item(entry["Id"], "values")[2], "Pending | buy All + 3 | sell All")
        self.assertEqual(entry["BuyCommodities"]["Gold"], 9999)
        self.editor.document.filename = Path(self.runtime.filename).resolve()
        self.editor.document.saved = copy.deepcopy(self.editor.document.data)
        self.runtime.waypoints = {
            entry["Id"]: {"BuyCommodities": {"Gold": 9999}, "SellCommodities": {"Polymere": 9995}}
        }
        self.editor.refresh()
        self.assertEqual(self.editor.tree.item(entry["Id"], "values")[2], "Pending | buy All | sell 9995")

    def test_commodity_table_validates_pending_edit_and_preserves_quantities(self):
        table = CommodityList(self.root, {"Gold": 2})
        table.name.set("Polymere")
        table.quantity.set("3")
        with self.assertRaises(ValueError):
            table.get()
        table.set_item()
        self.assertEqual(table.get(), {"Gold": 2, "Polymere": 3})
        table.name.set("Silver")
        table.quantity.set("-1")
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            table.set_item()
        error.assert_called_once()

    def test_commodity_all_choice_roundtrips_numeric_marker_and_preserves_transfer_all(self):
        table = CommodityList(self.root, {"Gold": 9999, "All": 0})
        self.addCleanup(table.destroy)
        first = table.tree.get_children()[0]
        self.assertEqual(table.tree.item(first, "values"), ("All",))
        table.tree.selection_set(first)
        self.root.update()
        self.assertEqual(table.quantity.get(), "All")
        self.assertEqual(table.get(), {"Gold": 9999, "All": 0})
        table.quantity.set("5")
        with self.assertRaises(ValueError):
            table.get()
        table.set_item()
        self.assertEqual(table.get(), {"Gold": 5, "All": 0})
        table.name.set("Polymere")
        table.quantity_picker.current(0)
        with self.assertRaises(ValueError):
            table.get()
        table.set_item()
        self.assertEqual(table.get(), {"Gold": 5, "All": 0, "Polymere": 9999})

    def test_all_choice_applies_to_buy_sell_and_global_lists(self):
        self.editor.add()
        form = self.editor.form
        form.variables["SystemName"].set("Sol")
        for table in (form.buy, form.sell):
            table.name.set("Polymere")
            table.quantity.set("All")
            table.set_item()
        form.apply()
        entry = self.editor.document.data["waypoints"][0]
        self.assertEqual(entry["BuyCommodities"], {"Polymere": 9999})
        self.assertEqual(entry["SellCommodities"], {"Polymere": 9999})
        self.editor.edit_global()
        self.editor.form.buy.name.set("Gold")
        self.editor.form.buy.quantity.set("All")
        self.editor.form.buy.set_item()
        self.editor.form.apply()
        self.assertEqual(self.editor.document.data["GlobalShoppingList"]["BuyCommodities"], {"Gold": 9999})

    def test_pending_all_choice_survives_rebuild(self):
        self.editor.add()
        table = self.editor.form.buy
        table.name.set("Polymere")
        table.quantity.set("All")
        self.app.waypoint_form_state = self.editor.form_state()
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update()
        table = self.editor.form.buy
        self.assertEqual(table.quantity.get(), "All")
        with self.assertRaises(ValueError):
            table.get()
        table.set_item()
        self.assertEqual(table.get(), {"Polymere": 9999})

    def test_waypoint_form_edits_target_bookmark_and_trade_quantities(self):
        entry = new_waypoint()
        applied = mock.Mock()
        dialog = WaypointForm(self.root, entry, applied, mock.Mock(), self.app)
        dialog.variables["SystemName"].set("LHS 20")
        dialog.variables["StationName"].set("Ohm City")
        dialog.variables["GalaxyBookmarkType"].set("Fav")
        dialog.variables["GalaxyBookmarkNumber"].set("1")
        dialog.buy.name.set("Polymere")
        dialog.buy.quantity.set("2")
        dialog.buy.set_item()
        dialog.apply()
        result = applied.call_args.args[0]
        self.assertEqual(result["Id"], entry["Id"])
        self.assertEqual(result["BuyCommodities"], {"Polymere": 2})
        self.assertEqual(result["GalaxyBookmarkNumber"], 1)
        self.assertEqual(entry["BuyCommodities"], {})

    def test_waypoint_form_rejects_bad_bookmark_without_changing_original(self):
        entry = dict(new_waypoint(), SystemName="LHS 20")
        applied = mock.Mock()
        dialog = WaypointForm(self.root, entry, applied, mock.Mock(), self.app)
        dialog.variables["GalaxyBookmarkType"].set("Fav")
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            dialog.apply()
        error.assert_called_once()
        applied.assert_not_called()
        self.assertEqual(entry["GalaxyBookmarkType"], "")
        dialog.destroy()

    def test_global_list_uses_inline_form_and_cancel_does_not_change_definition(self):
        previous = copy.deepcopy(self.editor.document.data)
        with mock.patch("tkinter.Toplevel", side_effect=AssertionError("No extra window allowed")):
            self.editor.edit_global()
            self.assertTrue(self.editor.form.global_list)
            self.editor.form.buy.values["Polymere"] = 2
            self.editor.form.cancel_button.invoke()
        self.assertEqual(self.editor.document.data, previous)
        self.assertFalse(self.editor.dialog_open)

    def test_inline_global_apply_updates_draft_and_marks_dirty(self):
        self.editor.edit_global()
        self.editor.form.variables["Enabled"].set(True)
        self.editor.form.buy.values["Polymere"] = 2
        self.editor.form.apply()
        self.assertEqual(self.editor.document.data["GlobalShoppingList"]["BuyCommodities"], {"Polymere": 2})
        self.assertTrue(self.editor.document.data["GlobalShoppingList"]["Enabled"])
        self.assertTrue(self.editor.document.dirty)
        self.assertIsNone(self.editor.form)

    def test_inline_form_keeps_controls_visible_without_extra_windows(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        for global_list in (False, True):
            with self.subTest(global_list=global_list):
                with mock.patch("tkinter.Toplevel", side_effect=AssertionError("No extra window allowed")):
                    self.editor.edit_global() if global_list else self.editor.add()
                self.root.update()
                form = self.editor.form
                self.assertIsInstance(form.card, ttk.LabelFrame)
                self.assertEqual(form.notebook.master, form.card)
                self.assertGreater(form.notebook.winfo_height(), 100)
                for button in (form.apply_button, form.cancel_button):
                    self.assertGreater(button.winfo_height(), 1)
                    self.assertLessEqual(
                        button.winfo_rooty() + button.winfo_height(),
                        self.editor.winfo_rooty() + self.editor.winfo_height(),
                    )
                for tab in form.notebook.tabs():
                    form.notebook.select(tab)
                    self.root.update()
                for table in (form.buy, form.sell):
                    if table is None:
                        continue
                    form.notebook.select(table)
                    self.root.update()
                    for child in table.winfo_children():
                        self.assertLessEqual(child.winfo_x() + child.winfo_width(), table.winfo_width())
                        self.assertLessEqual(child.winfo_y() + child.winfo_height(), table.winfo_height())
                    language_row = table.language_picker.master
                    for child in language_row.winfo_children():
                        self.assertLessEqual(child.winfo_x() + child.winfo_width(), language_row.winfo_width())
                self.assertFalse(self.editor.prepare_start())
                self.editor.cancel_form()

    def test_route_dropdown_loads_local_route_and_retains_external_route(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            target = folder / "Local.json"
            target.write_text("{}")
            external = folder / "elsewhere" / "External.json"
            self.editor.document.filename = external
            self.runtime.load_waypoint_file = mock.Mock(return_value=True)
            document = RouteDocument()
            document.filename = target.resolve()
            with mock.patch("gui.waypoint_editor.paths.WAYPOINTS_DIR", folder):
                self.editor.refresh_routes()
                self.assertEqual(self.editor.route_paths["Local.json"], target)
                self.assertIn(external, self.editor.route_paths.values())
                self.editor.route_choice.set("Local.json")
                with mock.patch.object(RouteDocument, "load", return_value=document):
                    self.editor.select_route()
                self.assertIs(self.editor.document, document)
                self.runtime.load_waypoint_file.assert_called_once_with(str(target))

    def test_cancelled_dropdown_switch_restores_selection_and_unsaved_draft(self):
        target = Path("other.json").resolve()
        self.editor.route_paths = {"other": target}
        self.editor.document.data["waypoints"].append(dict(new_waypoint(), SystemName="Sol"))
        self.editor.route_choice.set("other")
        document = self.editor.document
        with mock.patch("gui.waypoint_editor.messagebox.askyesnocancel", return_value=None):
            self.editor.select_route()
        self.assertIs(self.editor.document, document)
        self.assertEqual(self.editor.route_choice.get(), "* <new unsaved route>")

    def test_running_route_cannot_be_switched_by_dropdown(self):
        target = Path("other.json").resolve()
        self.editor.route_paths = {"other": target}
        self.editor.route_choice.set("other")
        self.runtime.executing = True
        with mock.patch.object(self.editor, "load_route") as load:
            self.editor.select_route()
        load.assert_not_called()
        self.assertEqual(self.editor.route_choice.get(), "<new unsaved route>")

    def test_close_guard_preserves_open_form_when_discard_cancelled(self):
        self.editor.add()
        self.editor.form.variables["SystemName"].set("LHS 20")
        with mock.patch("gui.waypoint_editor.messagebox.askokcancel", return_value=False):
            self.assertFalse(self.editor.discard())
        self.assertEqual(self.editor.form.variables["SystemName"].get(), "LHS 20")
        self.assertTrue(self.editor.dialog_open)

    def test_existing_waypoint_inline_cancel_preserves_original(self):
        entry = dict(new_waypoint(), SystemName="LHS 20")
        self.editor.document.data["waypoints"] = [entry]
        self.editor.refresh()
        self.editor.tree.selection_set(entry["Id"])
        self.editor.edit()
        self.editor.form.variables["SystemName"].set("Sol")
        self.editor.cancel_form()
        self.assertEqual(self.editor.document.data["waypoints"][0], entry)

    def test_header_style_is_distinct_from_table_background(self):
        style = ttk.Style()
        self.editor.add()
        for tree in (self.editor.tree, self.editor.form.buy.tree, self.editor.form.sell.tree):
            actual_style = str(tree.cget("style"))
            self.assertEqual(actual_style, "Waypoint.Treeview")
            heading = style.lookup(actual_style + ".Heading", "background")
            body = style.lookup(actual_style, "background")
            self.assertNotEqual(heading, body)
            self.assertNotEqual(style.lookup(actual_style + ".Heading", "foreground"), heading)

    def test_route_and_waypoints_use_shared_cards_without_duplicate_labels(self):
        self.assertIsInstance(self.editor.route_card, ttk.LabelFrame)
        self.assertIsInstance(self.editor.waypoints_card, ttk.LabelFrame)
        self.assertEqual(self.editor.route_picker.master.master, self.editor.route_card)
        self.assertEqual(self.editor.tree.master.master, self.editor.waypoints_card)
        self.assertFalse(hasattr(self.editor, "name_entry"))
        self.assertFalse(hasattr(self.editor, "label"))
        self.assertFalse(hasattr(self.editor, "summary"))

    def test_tables_have_padded_rows_and_alternating_colors_after_refresh(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        self.editor.document.data["waypoints"] = [
            dict(new_waypoint(), SystemName=name) for name in ("Sol", "LHS 20", "Achenar")
        ]
        self.editor.refresh()
        self.editor.add()
        table = self.editor.form.buy
        table.values = {"Gold": 1, "Silver": 2, "Polymere": 3}
        table.refresh()
        self.editor.form.notebook.select(table)
        self.root.update()
        style = ttk.Style()
        line_height = tkfont.nametofont("TkDefaultFont", root=self.root).metrics("linespace")
        self.assertGreaterEqual(
            int(style.lookup("Waypoint.Treeview", "rowheight")), line_height + self.app.metrics.px(12)
        )
        for tree in (self.editor.tree, table.tree):
            items = tree.get_children()
            self.assertEqual(
                [tuple(tag for tag in tree.item(item, "tags") if tag in ("even", "odd")) for item in items],
                [("even",), ("odd",), ("even",)],
            )
            self.assertNotEqual(tree.tag_configure("even", "background"), tree.tag_configure("odd", "background"))
        row = table.tree.bbox(table.tree.get_children()[0])
        self.assertGreater(row[3], line_height)
        self.assertGreaterEqual(
            table.tree.column("quantity", "width"),
            tkfont.nametofont("TkDefaultFont", root=self.root).measure("Quantity") + self.app.metrics.px(24),
        )
        selected_background = style.lookup("Waypoint.Treeview", "background", ("selected",))
        self.assertTrue(selected_background)
        self.assertNotIn(
            selected_background,
            (table.tree.tag_configure("even", "background"), table.tree.tag_configure("odd", "background")),
        )
        table.tree.selection_set(table.tree.get_children()[1])
        table.values.pop("Gold")
        table.refresh()
        self.assertEqual([table.tree.item(item, "tags") for item in table.tree.get_children()], [("even",), ("odd",)])

    def test_unsaved_marker_in_dropdown_does_not_break_route_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Other.json"
            target.write_text("{}")
            self.editor.document.filename = Path(directory) / "Current.json"
            self.editor.document.data["waypoints"].append(dict(new_waypoint(), SystemName="Sol"))
            with mock.patch("gui.waypoint_editor.paths.WAYPOINTS_DIR", Path(directory)):
                self.editor.refresh_routes()
            self.assertEqual(self.editor.route_choice.get(), "* Current.json")
            self.editor.route_choice.set("Other.json")
            with (
                mock.patch("gui.waypoint_editor.messagebox.askyesnocancel", return_value=False),
                mock.patch.object(self.editor, "load_route") as load,
            ):
                self.editor.select_route()
            load.assert_called_once_with(target)

    def test_column_separators_span_heading_and_rows_and_follow_resize(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        entry = dict(new_waypoint(), SystemName="Sol")
        self.editor.document.data["waypoints"] = [entry]
        self.editor.refresh()
        self.root.update()
        tree = self.editor.tree
        (first, first_body), (second, second_body), _third = tree.column_separators
        self.assertEqual(len(tree.column_separators), 3)
        for heading, body in tree.column_separators:
            self.assertEqual(heading.winfo_width(), 1)
            self.assertEqual(body.winfo_width(), 1)
            self.assertEqual(heading.winfo_y(), 1)
            self.assertEqual(body.winfo_y(), heading.winfo_height() + 1)
            self.assertEqual(body.winfo_y(), tree.bbox(entry["Id"])[1])
            self.assertEqual(body.winfo_y() + body.winfo_height(), tree.winfo_height() - 1)
            self.assertEqual(heading.cget("background"), "#5a5a5a")
            for tag in ("even", "odd"):
                self.assertLess(
                    tree.winfo_rgb(body.cget("background"))[0],
                    tree.winfo_rgb(tree.tag_configure(tag, "background"))[0],
                )
        self.assertAlmostEqual(first.winfo_x(), tree.bbox(entry["Id"], "#0")[2] + tree.bbox(entry["Id"])[0], delta=2)
        self.assertEqual(second.winfo_x() - first.winfo_x(), tree.column("enabled", "width"))
        second_body.event_generate("<ButtonPress-1>", x=0, y=5)
        second_body.event_generate("<ButtonRelease-1>", x=0, y=5)
        self.root.update()
        self.assertEqual(tree.selection(), (entry["Id"],))
        old_width = tree.column("#0", "width")
        first.event_generate("<ButtonPress-1>", x=0, y=5)
        first.event_generate("<B1-Motion>", x=20, y=5)
        first.event_generate("<ButtonRelease-1>", x=20, y=5)
        self.root.update()
        self.assertGreater(tree.column("#0", "width"), old_width)
        self.assertEqual(first.winfo_x(), 1 + tree.column("#0", "width"))
        self.assertEqual(first_body.winfo_x(), first.winfo_x())
        self.root.geometry("650x500")
        self.root.update()
        self.assertEqual(first.winfo_x(), 1 + tree.column("#0", "width"))

    def test_all_commodity_tables_have_split_dividers_even_when_empty(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        for global_list in (False, True):
            self.editor.edit_global() if global_list else self.editor.add()
            form = self.editor.form
            for table in (form.buy, form.sell):
                if table is None:
                    continue
                form.notebook.select(table)
                self.root.update()
                tree = table.tree
                self.assertEqual(len(tree.column_separators), 1)
                heading, body = tree.column_separators[0]
                self.assertTrue(heading.winfo_ismapped())
                self.assertTrue(body.winfo_ismapped())
                self.assertEqual(heading.cget("background"), "#5a5a5a")
                self.assertEqual(body.cget("background"), "#343434")
                self.assertEqual(body.winfo_y(), heading.winfo_y() + heading.winfo_height())
                table.values = {"Gold": 1}
                table.refresh()
                self.root.update()
                self.assertEqual(body.winfo_y(), tree.bbox(tree.get_children()[0])[1])
                self.assertEqual(body.winfo_x(), 1 + tree.column("#0", "width"))
            self.editor.cancel_form()

    def test_searchable_picker_translates_only_selected_suggestions(self):
        self.editor.add()
        table = self.editor.form.buy
        table.name.set("polymers")
        self.assertEqual(tuple(table.name_picker.cget("values")), ("Polymere",))
        table.name.set("Polymere")
        table.name_picker.event_generate("<<ComboboxSelected>>")
        table.quantity.set("2")
        table.set_item()
        self.assertEqual(table.values, {"Polymere": 2})
        table.name.set("Custom commodity")
        table.language.set("en")
        self.assertEqual(table.name.get(), "Custom commodity")
        self.assertEqual(table.values, {"Polymere": 2})
        self.assertEqual(self.editor.form.sell.language.get(), "en")
        table.name.set("Polymere")
        self.assertEqual(tuple(table.name_picker.cget("values")), ("Polymers [unchecked]",))
        table.name.set("Polymers [unchecked]")
        table.choose_name()
        self.assertEqual(table.name.get(), "Polymers")
        table.set_item()
        self.assertIn("Polymers", table.get())
        self.assertNotIn("Polymers [unchecked]", table.get())

    def test_picker_preserves_free_text_and_language_across_form_snapshot(self):
        self.editor.edit_global()
        form = self.editor.form
        form.language.set("en")
        form.buy.name.set("Unknown future commodity")
        form.buy.quantity.set("invalid draft")
        state = self.editor.form_state()
        self.editor.cancel_form()
        self.editor.begin_form(state["entry"], state["index"], state["global_list"])
        self.editor.form.restore(state)
        self.assertEqual(self.editor.form.language.get(), "en")
        self.assertEqual(self.editor.form.buy.name.get(), "Unknown future commodity")
        self.assertEqual(self.editor.form.buy.quantity.get(), "invalid draft")
        self.editor.form.buy.quantity.set("3")
        self.editor.form.buy.set_item()
        self.editor.form.apply()
        self.assertEqual(
            self.editor.document.data["GlobalShoppingList"]["BuyCommodities"],
            {"Unknown future commodity": 3},
        )

    def test_catalogue_failure_is_reported_and_free_input_remains_available(self):
        with (
            mock.patch("gui.waypoint_editor.load_catalogue", side_effect=OSError("Catalogue unavailable")),
            mock.patch("gui.waypoint_editor.messagebox.showerror") as error,
        ):
            self.editor.edit_global()
        error.assert_called_once()
        table = self.editor.form.buy
        table.name.set("Polymere")
        table.set_item()
        self.assertEqual(table.get(), {"Polymere": 1})

    def prepare_import(self, text=ONE_WAY):
        self.editor.import_route()
        form = self.editor.form
        form.text.insert("1.0", text)
        self.root.update()
        form.preview()
        for item in form.goods.get_children():
            form.goods.selection_set(item)
            form.quantity.set("3")
            form.set_quantity()
        return form

    def test_import_new_route_is_unsaved_and_does_not_activate_runtime(self):
        original = self.editor.document
        form = self.prepare_import()
        self.runtime.load_waypoint_file = mock.Mock()
        form.apply()
        self.assertIsNot(self.editor.document, original)
        self.assertTrue(self.editor.document.dirty)
        self.assertIsNone(self.editor.document.filename)
        first, second = self.editor.document.data["waypoints"]
        self.assertEqual(first["BuyCommodities"], {"Polymere": 3})
        self.assertEqual(second["SellCommodities"], {"Polymere": 3})
        self.runtime.load_waypoint_file.assert_not_called()
        self.assertIsNone(self.editor.form)

    def test_commodity_move_preserves_values_selection_and_applied_order(self):
        self.editor.add()
        table = self.editor.form.buy
        table.values = {"Gold": 1, "Silver": 2, "Polymere": 3, "Water": 4}
        table.refresh()
        items = table.tree.get_children()
        table.tree.selection_set(items[1:3])
        table.move(-1)
        self.root.update()
        self.assertEqual(list(table.get()), ["Silver", "Polymere", "Gold", "Water"])
        self.assertEqual([table.tree.item(item, "text") for item in table.tree.selection()], ["Silver", "Polymere"])
        table.move(-1)
        self.assertEqual(list(table.values), ["Silver", "Polymere", "Gold", "Water"])
        table.move(1)
        self.root.update()
        self.assertEqual(list(table.values), ["Gold", "Silver", "Polymere", "Water"])
        self.assertEqual(table.values, {"Gold": 1, "Silver": 2, "Polymere": 3, "Water": 4})
        table.move(1)
        self.root.update()
        self.assertEqual(list(table.values), ["Gold", "Water", "Silver", "Polymere"])
        table.move(1)
        self.assertEqual(list(table.values), ["Gold", "Water", "Silver", "Polymere"])
        table.tree.selection_remove(*table.tree.selection())
        table.move(-1)
        self.assertEqual(list(table.values), ["Gold", "Water", "Silver", "Polymere"])
        self.editor.form.variables["SystemName"].set("Sol")
        self.editor.form.apply()
        self.assertEqual(
            list(self.editor.document.data["waypoints"][0]["BuyCommodities"]),
            ["Gold", "Water", "Silver", "Polymere"],
        )

    def test_import_sets_quantity_for_all_selected_goods_only(self):
        form = self.prepare_import(ROUND_TRIP)
        items = form.goods.get_children()
        self.assertEqual(str(form.goods.cget("selectmode")), "extended")
        form.goods.selection_set(items)
        self.root.update()
        self.assertEqual(form.quantity.get(), "3")
        form.quantity.set("12")
        form.set_quantity()
        self.assertEqual(form.quantities, {int(item): 12 for item in items})
        for item in items:
            self.assertEqual(form.goods.item(item, "values"), ("12",))
        form.goods.selection_set(items[0])
        self.root.update()
        form.quantity.set("4")
        form.set_quantity()
        self.assertEqual(form.quantities[int(items[0])], 4)
        self.assertEqual(form.quantities[int(items[1])], 12)
        form.goods.selection_set(items)
        self.root.update()
        self.assertEqual(form.quantity.get(), "")
        form.apply()
        self.assertIsNone(self.editor.form)

    def test_import_bulk_quantity_requires_selection_and_valid_value(self):
        form = self.prepare_import(ROUND_TRIP)
        items = form.goods.get_children()
        original = dict(form.quantities)
        form.goods.selection_set(items)
        self.root.update()
        for value in ("0", "9999", "invalid"):
            form.quantity.set(value)
            with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
                form.set_quantity()
            error.assert_called_once()
            self.assertEqual(form.quantities, original)
        form.goods.selection_remove(*items)
        self.root.update()
        form.quantity.set("20")
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.set_quantity()
        error.assert_called_once()
        self.assertEqual(form.quantities, original)

    def test_import_bulk_pending_quantity_and_selection_survive_rebuild(self):
        form = self.prepare_import(ROUND_TRIP)
        items = form.goods.get_children()
        form.quantities[int(items[1])] = 9
        form.goods.selection_set(items)
        self.root.update()
        self.assertEqual(form.quantity.get(), "")
        form.quantity.set("3")
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.apply()
        error.assert_called_once()
        self.app.waypoint_form_state = self.editor.form_state()
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update()
        restored = self.editor.form
        self.assertEqual(restored.goods.selection(), items)
        self.assertEqual(restored.quantity.get(), "3")
        restored.set_quantity()
        restored.apply()
        self.assertIsNone(self.editor.form)

    def test_import_append_preserves_current_draft_global_list_and_filename(self):
        old = dict(new_waypoint(), SystemName="Sol")
        self.editor.document.data["waypoints"] = [old]
        self.editor.document.filename = Path("existing.json").resolve()
        self.editor.document.data["GlobalShoppingList"]["Enabled"] = True
        form = self.prepare_import(ROUND_TRIP)
        form.target.set("Append to current")
        form.repeat.set(True)
        form.apply()
        self.assertEqual(len(self.editor.document.data["waypoints"]), 3)
        self.assertEqual(self.editor.document.data["waypoints"][0], old)
        self.assertEqual(self.editor.document.filename, Path("existing.json").resolve())
        self.assertTrue(self.editor.document.data["GlobalShoppingList"]["Enabled"])
        self.assertTrue(self.editor.document.data["Repeat"])

    def test_import_cancel_and_unsaved_cancel_preserve_original_document(self):
        self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="Sol")]
        document = self.editor.document
        data = copy.deepcopy(document.data)
        form = self.prepare_import()
        with mock.patch("gui.waypoint_editor.messagebox.askyesnocancel", return_value=None):
            form.apply()
        self.assertIs(self.editor.document, document)
        self.assertEqual(self.editor.document.data, data)
        self.assertIs(self.editor.form, form)
        self.editor.cancel_form()
        self.assertEqual(self.editor.document.data, data)

    def test_import_requires_current_preview_and_all_quantities(self):
        self.editor.import_route()
        form = self.editor.form
        form.text.insert("1.0", ONE_WAY)
        self.root.update()
        form.preview()
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.apply()
        error.assert_called_once()
        self.assertEqual(self.editor.document.data["waypoints"], [])
        form.language.set("en")
        self.assertIsNone(form.route)
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.apply()
        error.assert_called_once()

    def test_import_append_to_repeating_route_keeps_repeat_and_includes_new_waypoints(self):
        self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="Sol")]
        self.editor.document.data["Repeat"] = True
        form = self.prepare_import()
        form.target.set("Append to current")
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.apply()
        error.assert_not_called()
        self.assertEqual(len(self.editor.document.data["waypoints"]), 3)
        self.assertTrue(self.editor.document.data["Repeat"])

    def test_import_lock_and_rebuild_preserve_preview_and_inputs(self):
        self.runtime.executing = True
        self.editor.import_route()
        self.assertIsNone(self.editor.form)
        self.runtime.executing = False
        form = self.prepare_import()
        form.repeat.set(True)
        form.target.set("Append to current")
        form.quantity.set("unapplied")
        self.app.waypoint_form_state = self.editor.form_state()
        self.editor.destroy()
        self.editor = WaypointEditor(self.app, self.root)
        self.root.update()
        restored = self.editor.form
        self.assertIsNotNone(restored.route)
        self.assertEqual(restored.text.get("1.0", "end-1c"), ONE_WAY)
        self.assertEqual(restored.target.get(), "Append to current")
        self.assertTrue(restored.repeat.get())
        self.assertEqual(restored.quantity.get(), "unapplied")
        self.assertTrue(restored.quantities)
        self.assertFalse(self.editor.prepare_start())
        self.assertEqual(self.editor.document.data["waypoints"], [])

    def test_import_controls_fit_small_tab(self):
        self.root.geometry("570x500")
        self.root.deiconify()
        form = self.prepare_import(ROUND_TRIP)
        self.root.update()
        for tab in form.notebook.tabs():
            form.notebook.select(tab)
            self.root.update()
            page = form.notebook.nametowidget(tab)
            for child in page.winfo_children():
                self.assertLessEqual(child.winfo_x() + child.winfo_width(), page.winfo_width())
                self.assertLessEqual(child.winfo_y() + child.winfo_height(), page.winfo_height())
        for child in form.card.winfo_children():
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), form.card.winfo_width())
            self.assertLessEqual(child.winfo_y() + child.winfo_height(), form.card.winfo_height())

    def test_import_new_route_save_cancel_keeps_preview_and_original(self):
        self.editor.document.data["waypoints"] = [dict(new_waypoint(), SystemName="Sol")]
        document = self.editor.document
        form = self.prepare_import()
        with (
            mock.patch("gui.waypoint_editor.messagebox.askyesnocancel", return_value=True),
            mock.patch("gui.waypoint_editor.filedialog.asksaveasfilename", return_value=""),
        ):
            form.apply()
        self.assertIs(self.editor.document, document)
        self.assertIs(self.editor.form, form)
        self.assertTrue(self.editor.dialog_open)

    def test_import_preview_invalidates_after_edit_and_runtime_blocks_apply(self):
        form = self.prepare_import()
        form.text.insert("end", "\nextra text")
        self.root.update()
        self.assertIsNone(form.route)
        form.preview()
        self.runtime.executing = True
        with mock.patch("gui.waypoint_editor.messagebox.showerror") as error:
            form.apply()
        error.assert_called_once()
        self.assertEqual(self.editor.document.data["waypoints"], [])


if __name__ == "__main__":
    unittest.main()

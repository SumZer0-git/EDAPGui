"""Tests for bounded, debug-only vision case storage."""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from core import paths
from core.logger import logger
from panels.station_services import EDStationServicesInShip
from vision.diagnostics import save_case


class VisionDiagnosticTestCase(unittest.TestCase):
    def test_logged_prefix_is_relative_to_program_root(self):
        with tempfile.TemporaryDirectory() as folder:
            program_root = Path(folder)
            debug = program_root / "user_data" / "debug"
            with (
                patch.object(paths, "ROOT", program_root),
                patch.object(paths, "DEBUG_DIR", debug),
                self.assertLogs("ed_log", level="DEBUG") as logs,
            ):
                save_case("compass", "missing", {"evaluated": np.zeros((2, 2, 3), np.uint8)})
            message = next(
                record.getMessage() for record in logs.records if "Vision diagnostic case:" in record.getMessage()
            )
            prefix = message.split("prefix=", 1)[1]
            self.assertTrue(prefix.startswith("user_data/debug/compass/"))
            self.assertNotIn(str(program_root), message)
            self.assertTrue((program_root / (prefix + "_evaluated.png")).is_file())

    def test_limit_is_per_category_and_preserves_unmanaged_files(self):
        image = np.full((4, 5, 3), 123, np.uint8)
        with tempfile.TemporaryDirectory() as folder, patch.object(paths, "DEBUG_DIR", Path(folder)):
            legacy = Path(folder) / "compass" / "old.png"
            legacy.parent.mkdir()
            legacy.write_bytes(b"old")
            old_folder = legacy.parent / "old-case"
            old_folder.mkdir()
            (old_folder / "evaluated.png").write_bytes(b"old case")
            inbox = Path(folder).parent / (Path(folder).name + "-inbox")
            inbox.mkdir()
            self.addCleanup(inbox.rmdir)
            incoming = inbox / "dump.zip"
            incoming.write_bytes(b"external")
            self.addCleanup(incoming.unlink)
            with patch("vision.diagnostics.CASE_LIMIT", 2), self.assertLogs("ed_log", level="DEBUG"):
                save_case("compass", "missing", {"evaluated": image, "context": image})
                first = list(legacy.parent.glob("*_*.png"))
                save_case("target", "missing", {"evaluated": image})
                save_case("compass", "weak", {"evaluated": image, "context": image})
                save_case("compass", "weak", {"evaluated": image})
            remaining = list(legacy.parent.glob("*_*.png"))
            self.assertEqual(len(first), 2)
            self.assertEqual(len(remaining), 3)
            self.assertTrue(all(not filename.exists() for filename in first))
            self.assertEqual(len({filename.stem.rsplit("_", 1)[0] for filename in remaining}), 2)
            self.assertEqual(len(list((Path(folder) / "target").iterdir())), 1)
            self.assertEqual(legacy.read_bytes(), b"old")
            self.assertEqual((old_folder / "evaluated.png").read_bytes(), b"old case")
            self.assertEqual(incoming.read_bytes(), b"external")
            self.assertTrue(np.all(cv2.imread(str(remaining[0])) == image))

    def test_disabled_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(paths, "DEBUG_DIR", Path(folder)):
            with patch.object(logger, "isEnabledFor", return_value=False), patch("vision.diagnostics.cv2.imwrite") as w:
                save_case("compass", "missing", {"evaluated": np.zeros((2, 2, 3), np.uint8)})
                w.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_save_failure_logs_warning(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(paths, "DEBUG_DIR", Path(folder)):
            with patch("vision.diagnostics.cv2.imwrite", return_value=False):
                with self.assertLogs("ed_log", level=logging.DEBUG) as logs:
                    save_case("compass", "missing", {"evaluated": np.zeros((2, 2, 3), np.uint8)})
            self.assertTrue(any("Could not save vision diagnostic case" in line for line in logs.output))

    def test_partial_save_does_not_rotate_existing_case(self):
        image = np.zeros((2, 2, 3), np.uint8)
        with tempfile.TemporaryDirectory() as folder, patch.object(paths, "DEBUG_DIR", Path(folder)):
            with patch("vision.diagnostics.CASE_LIMIT", 1), self.assertLogs("ed_log", level="DEBUG"):
                save_case("compass", "missing", {"evaluated": image, "context": image})
                original = set((Path(folder) / "compass").iterdir())
                real_write = cv2.imwrite
                with patch("vision.diagnostics.cv2.imwrite") as write:
                    write.side_effect = lambda filename, data: (
                        real_write(filename, data) if write.call_count == 1 else False
                    )
                    save_case("compass", "missing", {"evaluated": image, "context": image})
                self.assertEqual(set((Path(folder) / "compass").iterdir()), original)

    def test_trade_timeout_saves_the_last_evaluated_images(self):
        services = EDStationServicesInShip.__new__(EDStationServicesInShip)
        title = np.full((20, 50, 3), 1, np.uint8)
        name = np.full((20, 50, 3), 2, np.uint8)
        context = np.full((80, 120, 3), 3, np.uint8)
        services.screen = Mock(screen_width=1920, screen_height=1080)
        services.ocr = Mock()
        services.ocr.capture_region_pct.side_effect = [title, name, context]
        services.ocr.image_simple_ocr.side_effect = [["BUY COMMODITY"], ["WRONG"]]
        services.locale = Mock()
        services.locale.all_values.return_value = ["BUY COMMODITY"]
        with (
            patch.object(logger, "isEnabledFor", return_value=True),
            patch("panels.station_services.monotonic", side_effect=[0, 0, 16]),
            patch("panels.station_services.sleep"),
            patch("panels.station_services.save_case") as save,
        ):
            self.assertFalse(services.confirm_trade_dialog("RIGHT", False))
        images = save.call_args.args[2]
        self.assertTrue(np.array_equal(images["title"], title))
        self.assertTrue(np.array_equal(images["name"], name))
        self.assertIs(images["later-dialog"], context)

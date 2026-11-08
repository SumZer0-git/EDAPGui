"""Offline statistics, ETA and backup tests; no game, GUI or OCR imports."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from core.statistics import AssistStatistics, ShipIdentity, format_eta


class Clock:
    def __init__(self):
        self.seconds = 0.0
        self.utc = datetime(2026, 11, 8, tzinfo=UTC)

    def advance(self, seconds):
        self.seconds += seconds
        self.utc += timedelta(seconds=seconds)


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.database = Path(self.folder.name) / "statistics.sqlite3"
        self.clock = Clock()
        self.notify = Mock()
        self.statistics = self.open_statistics()
        self.state = {"commander_id": "account-a", "ship_id": 7, "type": "anaconda"}
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")

    def open_statistics(self):
        statistics = AssistStatistics(self.database, self.notify, lambda: self.clock.seconds, lambda: self.clock.utc)
        self.addCleanup(statistics.close)
        return statistics

    def event(self, name, **values):
        return {"event": name, "timestamp": self.clock.utc.isoformat(), **values}

    def jump(self, seconds=90, distance=30, system="Next"):
        self.statistics.expect_jump()
        self.statistics.observe(self.event("StartJump", JumpType="Hyperspace"), self.state)
        self.clock.advance(seconds)
        self.statistics.observe(self.event("FSDJump", JumpDist=distance, StarSystem=system), self.state)

    def learn(self):
        for _ in range(4):
            self.jump()

    def test_first_jump_counts_but_three_complete_intervals_are_required_for_eta(self):
        self.jump()
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.ship.jumps, 1)
        self.assertEqual(snapshot.ship.distance, 30)
        self.assertEqual(snapshot.ship.samples, 0)
        self.assertIsNone(self.statistics.eta_seconds(2))
        self.jump()
        self.jump()
        self.assertIsNone(self.statistics.eta_seconds(2))
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.samples, 3)
        self.assertEqual(self.statistics.eta_seconds(2), 180)

    def test_eta_counts_down_and_overdue_cycle_does_not_consume_later_jumps(self):
        self.learn()
        self.clock.advance(30)
        self.assertEqual(self.statistics.eta_seconds(2), 150)
        self.clock.advance(100)
        self.assertEqual(self.statistics.eta_seconds(2), 91)
        self.assertIsNone(self.statistics.eta_seconds(0))

    def test_normal_tanking_delays_are_not_clipped(self):
        self.jump()
        self.jump(seconds=300)
        self.assertEqual(self.statistics.snapshot().ship.average, 300)

    def test_end_route_stops_eta_at_arrival_before_local_actions(self):
        self.learn()
        self.jump(system="End")
        self.assertFalse(self.statistics.route_active)
        self.assertIsNone(self.statistics.eta_seconds(1))
        self.notify.assert_any_call("System route finished: 5 jumps, 150.0 ly, 8m system travel.")
        self.clock.advance(120)
        self.statistics.end_assist()
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.ship.travel_seconds, 450)
        self.assertEqual(snapshot.ship.assist_seconds, 570)

    def test_stop_and_restart_do_not_bridge_intervals(self):
        self.jump()
        self.clock.advance(20)
        self.statistics.end_assist()
        self.clock.advance(1000)
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.jumps, 2)
        self.assertEqual(self.statistics.snapshot().ship.samples, 0)
        self.assertEqual(self.statistics.snapshot().ship.assist_seconds, 200)

    def test_fsd_sections_of_waypoint_route_do_not_include_station_time(self):
        self.jump()
        self.statistics.end_route()
        self.clock.advance(600)
        self.statistics.begin_route(self.state, "End")
        self.jump()
        self.jump()
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.ship.samples, 1)
        self.assertEqual(snapshot.ship.average, 90)
        self.assertEqual(snapshot.ship.travel_seconds, 270)
        self.assertEqual(snapshot.ship.assist_seconds, 870)

    def test_manual_supercruise_carrier_and_duplicate_events_do_not_count(self):
        self.statistics.observe(self.event("FSDJump", JumpDist=99), self.state)
        self.statistics.observe(self.event("StartJump", JumpType="Supercruise"), self.state)
        self.statistics.observe(self.event("CarrierJump"), self.state)
        self.jump()
        self.statistics.observe(self.event("FSDJump", JumpDist=30), self.state)
        self.statistics.end_assist()
        self.statistics.observe(self.event("FSDJump", JumpDist=30), self.state)
        self.assertEqual(self.statistics.snapshot().ship.jumps, 1)

    def test_invalid_distance_or_timestamp_does_not_create_a_measurement(self):
        self.jump()
        self.statistics.expect_jump()
        self.statistics.observe(self.event("StartJump", JumpType="Hyperspace"), self.state)
        self.clock.advance(90)
        with self.assertLogs("root", level="WARNING"):
            self.statistics.observe(self.event("FSDJump", JumpDist=float("nan")), self.state)
        self.statistics.expect_jump()
        self.statistics.observe(self.event("StartJump", JumpType="Hyperspace"), self.state)
        with self.assertLogs("root", level="WARNING"):
            self.statistics.observe({"event": "FSDJump", "timestamp": "invalid", "JumpDist": 30}, self.state)
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.samples, 0)

    def test_accounts_and_identical_ship_types_are_separate(self):
        self.jump()
        self.state = {**self.state, "ship_id": 8}
        self.statistics.set_identity(self.state)
        self.assertEqual(self.statistics.snapshot().commander.jumps, 1)
        self.assertEqual(self.statistics.snapshot().ship.jumps, 0)
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.jump(distance=50)
        self.state = {**self.state, "commander_id": "account-b", "ship_id": 7}
        self.statistics.set_identity(self.state)
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.commander.jumps, 0)
        self.assertEqual(snapshot.ship.jumps, 0)
        self.assertFalse(self.statistics.route_active)
        self.state["commander_id"] = "account-a"
        self.statistics.set_identity(self.state)
        self.assertEqual(self.statistics.snapshot().commander.jumps, 2)
        self.assertEqual(self.statistics.snapshot().commander.distance, 80)

    def test_renaming_ship_does_not_change_identity(self):
        self.jump()
        self.statistics.set_identity({**self.state, "ShipName": "New", "ShipIdent": "ABC"})
        self.assertEqual(self.statistics.snapshot().ship.jumps, 1)
        self.assertTrue(self.statistics.route_active)

    def test_same_account_and_ship_id_with_other_type_has_separate_statistics_and_eta(self):
        self.learn()
        self.state["type"] = "type9"
        self.statistics.set_identity(self.state)
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.assertEqual(self.statistics.snapshot().ship.jumps, 0)
        self.assertEqual(self.statistics.snapshot().commander.jumps, 4)
        self.assertIsNone(self.statistics.eta_seconds(2))
        self.jump(distance=50)
        self.state["type"] = "ANACONDA"
        self.statistics.set_identity(self.state)
        self.assertEqual(self.statistics.snapshot().ship.jumps, 4)
        self.assertEqual(self.statistics.snapshot().ship.samples, 3)
        self.assertEqual(self.statistics.snapshot().commander.jumps, 5)
        self.assertEqual(self.statistics.snapshot().commander.distance, 170)

    def test_missing_type_does_not_use_existing_ship_statistics(self):
        self.learn()
        self.statistics.set_identity({**self.state, "type": None})
        self.assertIsNone(self.statistics.identity)
        self.assertFalse(self.statistics.route_active)
        self.assertIsNone(ShipIdentity.from_state({**self.state, "type": " "}))

    def test_missing_identity_is_not_recorded_under_a_fallback_ship(self):
        self.statistics.set_identity({})
        with self.assertLogs("root", level="WARNING"):
            self.statistics.begin_assist({})
        self.statistics.begin_route({}, "End")
        self.state = {}
        self.jump()
        self.assertIsNone(self.statistics.snapshot().identity)
        self.assertTrue(self.notify.called)
        self.assertIsNone(ShipIdentity.from_state({"commander_id": "a", "ship_id": True}))

    def test_shutdown_ends_measurement_chain(self):
        self.jump()
        self.statistics.observe(self.event("Shutdown"), self.state)
        self.assertFalse(self.statistics.route_active)
        self.clock.advance(100)
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.jumps, 1)

    def test_utc_clock_adjustment_does_not_change_measured_duration(self):
        self.jump()
        self.clock.utc += timedelta(hours=1)
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.average, 90)
        self.clock.utc -= timedelta(hours=2)
        self.jump()
        self.assertEqual(self.statistics.snapshot().ship.samples, 2)
        self.assertEqual(self.statistics.snapshot().ship.average, 90)

    def test_restart_preserves_history_and_immediately_provides_eta(self):
        self.learn()
        self.statistics.close()
        self.statistics = self.open_statistics()
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.assertEqual(self.statistics.snapshot().ship.jumps, 4)
        self.assertEqual(self.statistics.eta_seconds(2), 180)

    def test_history_keeps_latest_thousand_per_ship_without_reducing_lifetime_totals(self):
        with patch.object(self.statistics, "backup_if_due"):
            for _ in range(1010):
                self.jump(seconds=2)
        with closing(sqlite3.connect(self.database)) as connection:
            rows = connection.execute("SELECT timestamp, seconds FROM measurements ORDER BY id").fetchall()
        self.assertEqual(len(rows), 1000)
        self.assertEqual(rows[-1], (self.clock.utc.isoformat(), 2))
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.ship.jumps, 1010)
        self.assertEqual(snapshot.ship.samples, 1009)
        self.assertEqual(snapshot.ship.distance, 30300)
        self.clock.advance(365 * 86400)
        self.statistics.end_assist()
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM measurements").fetchone()[0], 1000)

    def test_adaptive_estimate_changes_without_replacing_lifetime_average(self):
        self.learn()
        for _ in range(20):
            self.jump(seconds=180)
        snapshot = self.statistics.snapshot()
        self.assertGreater(snapshot.ship.estimate, 140)
        self.assertEqual(snapshot.ship.samples, 23)
        self.assertAlmostEqual(snapshot.ship.average, (3 * 90 + 20 * 180) / 23)

    def test_backup_created_after_first_write_and_not_for_each_restart_or_jump(self):
        self.jump()
        self.jump()
        self.assertEqual(len(list(self.database.parent.glob("statistics-backup-*.sqlite3"))), 1)
        self.statistics.close()
        self.statistics = self.open_statistics()
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.jump()
        self.assertEqual(len(list(self.database.parent.glob("statistics-backup-*.sqlite3"))), 1)

    def test_backup_interval_rotation_integrity_and_migration_backup(self):
        for _ in range(12):
            self.jump()
            self.statistics.end_assist()
            self.clock.advance(86400)
            self.statistics.begin_assist(self.state)
            self.statistics.begin_route(self.state, "End")
        backups = sorted(self.database.parent.glob("statistics-backup-*.sqlite3"))
        self.assertEqual(len(backups), 10)
        with closing(sqlite3.connect(backups[-1])) as connection:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone(), ("ok",))
            self.assertEqual(connection.execute("SELECT SUM(jumps) FROM totals").fetchone()[0], 12)
        migration = self.statistics.backup_if_due(migration=True)
        self.assertIsNotNone(migration)
        self.assertTrue(migration.exists())
        self.assertEqual(len(list(self.database.parent.glob("statistics-backup-*.sqlite3"))), 10)

    def test_no_backup_without_changes(self):
        self.jump()
        self.statistics.end_assist()
        self.statistics.backup_if_due()
        self.clock.advance(86400)
        self.statistics.backup_if_due()
        count = len(list(self.database.parent.glob("statistics-backup-*.sqlite3")))
        self.clock.advance(86400)
        self.statistics.backup_if_due()
        self.assertEqual(len(list(self.database.parent.glob("statistics-backup-*.sqlite3"))), count)

    def test_failed_backup_preserves_existing_backups_and_notifies(self):
        self.jump()
        backups = list(self.database.parent.glob("statistics-backup-*.sqlite3"))
        self.clock.advance(86400)
        with patch.object(Path, "replace", side_effect=OSError("disk error")):
            self.jump()
        self.assertEqual(list(self.database.parent.glob("statistics-backup-*.sqlite3")), backups)
        self.assertFalse(list(self.database.parent.glob("*.tmp")))
        self.notify.assert_any_call(
            "Statistics backup or rotation failed. Check the log and retain your existing backups."
        )

    def test_corrupt_database_is_not_overwritten_or_silently_reset(self):
        self.statistics.close()
        self.database.write_bytes(b"broken statistics")
        self.statistics = self.open_statistics()
        self.assertFalse(self.statistics.snapshot().available)
        self.assertEqual(self.database.read_bytes(), b"broken statistics")
        self.assertTrue(self.notify.called)

    def test_active_time_is_checkpointed_on_each_jump(self):
        self.jump()
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute("SELECT assist_seconds, travel_seconds FROM totals").fetchone(), (90, 90)
            )
        self.clock.advance(10)
        self.assertEqual(self.statistics.snapshot().ship.assist_seconds, 100)
        self.statistics.end_assist()
        self.assertEqual(self.statistics.snapshot().ship.assist_seconds, 100)

    def make_legacy_database(self):
        self.statistics.close()
        self.database.unlink()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript(
                """
                CREATE TABLE totals (
                    commander TEXT NOT NULL, ship_id INTEGER NOT NULL,
                    jumps INTEGER NOT NULL DEFAULT 0, distance REAL NOT NULL DEFAULT 0,
                    assist_seconds REAL NOT NULL DEFAULT 0, travel_seconds REAL NOT NULL DEFAULT 0,
                    samples INTEGER NOT NULL DEFAULT 0, sample_seconds REAL NOT NULL DEFAULT 0, estimate REAL,
                    PRIMARY KEY (commander, ship_id)
                );
                CREATE TABLE measurements (
                    id INTEGER PRIMARY KEY, commander TEXT NOT NULL, ship_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL, seconds REAL NOT NULL CHECK (seconds > 0),
                    FOREIGN KEY (commander, ship_id) REFERENCES totals (commander, ship_id)
                );
                CREATE INDEX measurements_ship ON measurements (commander, ship_id, id);
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO totals VALUES ('account-a', 7, 4, 120, 400, 360, 3, 270, 90);
                INSERT INTO measurements VALUES (1, 'account-a', 7, '2026-11-08T00:00:00+00:00', 90);
                PRAGMA user_version = 1;
                """
            )

    def test_legacy_migration_preserves_account_data_without_guessing_type(self):
        self.make_legacy_database()
        self.statistics = self.open_statistics()
        self.statistics.set_identity(self.state)
        snapshot = self.statistics.snapshot()
        self.assertEqual(snapshot.commander.jumps, 4)
        self.assertEqual(snapshot.commander.samples, 3)
        self.assertEqual(snapshot.ship.jumps, 0)
        backups = list(self.database.parent.glob("statistics-migration-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone(), (1,))
            self.assertEqual(backup.execute("SELECT jumps FROM totals").fetchone(), (4,))
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (2,))
            self.assertEqual(connection.execute("SELECT seconds FROM measurements").fetchone(), (90,))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertIn("Older statistics", self.notify.call_args.args[0])

    def test_confirmed_legacy_identity_preserves_ship_history_and_eta(self):
        self.make_legacy_database()
        self.statistics = AssistStatistics(
            self.database,
            self.notify,
            lambda: self.clock.seconds,
            lambda: self.clock.utc,
            legacy_identity=ShipIdentity("account-a", 7, "anaconda"),
        )
        self.addCleanup(self.statistics.close)
        self.statistics.begin_assist(self.state)
        self.statistics.begin_route(self.state, "End")
        self.assertEqual(self.statistics.snapshot().ship.jumps, 4)
        self.assertEqual(self.statistics.snapshot().ship.samples, 3)
        self.assertEqual(self.statistics.eta_seconds(2), 180)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT ship_type FROM measurements").fetchone(), ("anaconda",))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.statistics.close()
        self.statistics = self.open_statistics()
        self.statistics.set_identity(self.state)
        self.assertEqual(self.statistics.snapshot().ship.jumps, 4)
        self.assertEqual(len(list(self.database.parent.glob("statistics-migration-*.sqlite3"))), 1)

    def test_migration_is_refused_without_successful_backup(self):
        self.make_legacy_database()
        with patch.object(Path, "replace", side_effect=OSError("disk error")):
            self.statistics = self.open_statistics()
        self.assertFalse(self.statistics.snapshot().available)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (1,))
            self.assertEqual(connection.execute("SELECT jumps FROM totals").fetchone(), (4,))

    def test_format_eta_is_compact_and_uses_local_arrival_time(self):
        now = datetime(2026, 11, 8, 23, 46, tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(format_eta(4320, now), f"~1h 12m ({(now + timedelta(seconds=4320)).astimezone():%H:%M})")


if __name__ == "__main__":
    unittest.main()

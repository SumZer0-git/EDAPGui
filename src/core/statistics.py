"""Local assist statistics, bounded jump history and ship-specific route estimates."""

from __future__ import annotations

import math
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic

from core.logger import logger

HISTORY_LIMIT = 1000
BACKUP_LIMIT = 10
BACKUP_INTERVAL = 24 * 60 * 60
MIN_ETA_SAMPLES = 3
ETA_ALPHA = 0.05
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ShipIdentity:
    commander: str
    ship_id: int
    ship_type: str

    @classmethod
    def from_state(cls, state: dict) -> ShipIdentity | None:
        commander, ship_id = state.get("commander_id"), state.get("ship_id")
        ship_type = state.get("type")
        if (
            isinstance(commander, str)
            and commander
            and type(ship_id) is int
            and ship_id >= 0
            and isinstance(ship_type, str)
            and ship_type.strip()
        ):
            return cls(commander, ship_id, ship_type.strip().casefold())
        return None

    @property
    def key(self) -> tuple[str, int, str]:
        return self.commander, self.ship_id, self.ship_type


@dataclass(frozen=True)
class Totals:
    jumps: int = 0
    distance: float = 0
    assist_seconds: float = 0
    travel_seconds: float = 0
    samples: int = 0
    sample_seconds: float = 0
    estimate: float | None = None

    @property
    def average(self) -> float | None:
        return self.sample_seconds / self.samples if self.samples else None


@dataclass(frozen=True)
class StatisticsSnapshot:
    available: bool
    identity: ShipIdentity | None
    commander: Totals = Totals()
    ship: Totals = Totals()


def format_duration(seconds: float) -> str:
    minutes = max(0, math.ceil(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def format_eta(seconds: float, now: datetime | None = None) -> str:
    now = now if now is not None else datetime.now(UTC)
    arrival = (now.astimezone(UTC) + timedelta(seconds=seconds)).astimezone()
    return f"~{format_duration(seconds)} ({arrival:%H:%M})"


class AssistStatistics:
    def __init__(
        self,
        database: Path,
        notify: Callable[[str], None],
        clock: Callable[[], float] = monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
        legacy_identity: ShipIdentity | None = None,
    ):
        self._lock = threading.RLock()
        self._database = database
        self._notify = notify
        self._clock = clock
        self._utc_now = utc_now
        self._connection: sqlite3.Connection | None = None
        self.identity: ShipIdentity | None = None
        self._assist_started: float | None = None
        self._assist_checkpoint: float | None = None
        self._route_started: float | None = None
        self._travel_checkpoint: float | None = None
        self._last_jump: float | None = None
        self._jump_requested = False
        self._jump_started = False
        self._destination = ""
        self._route_jumps = 0
        self._route_distance = 0.0
        self._backup_attempt: datetime | None = None
        self._closed = False
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(database, check_same_thread=False)
            self._connection.execute("PRAGMA foreign_keys = ON")
            if self._connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise sqlite3.DatabaseError("Statistics database integrity check failed")
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise sqlite3.DatabaseError(f"Unsupported statistics schema version: {version}")
            if version == 0:
                with self._connection:
                    self._connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE totals (
                            commander TEXT NOT NULL, ship_id INTEGER NOT NULL, ship_type TEXT NOT NULL,
                            jumps INTEGER NOT NULL DEFAULT 0, distance REAL NOT NULL DEFAULT 0,
                            assist_seconds REAL NOT NULL DEFAULT 0, travel_seconds REAL NOT NULL DEFAULT 0,
                            samples INTEGER NOT NULL DEFAULT 0, sample_seconds REAL NOT NULL DEFAULT 0,
                            estimate REAL,
                            PRIMARY KEY (commander, ship_id, ship_type)
                        );
                        CREATE TABLE measurements (
                            id INTEGER PRIMARY KEY, commander TEXT NOT NULL, ship_id INTEGER NOT NULL,
                            ship_type TEXT NOT NULL,
                            timestamp TEXT NOT NULL, seconds REAL NOT NULL CHECK (seconds > 0),
                            FOREIGN KEY (commander, ship_id, ship_type) REFERENCES totals (commander, ship_id, ship_type)
                        );
                        CREATE INDEX measurements_ship ON measurements (commander, ship_id, ship_type, id);
                        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                        PRAGMA user_version = 2;
                        COMMIT;
                        """
                    )
            elif version == 1:
                self._migrate_ship_types(legacy_identity)
        except (OSError, sqlite3.Error) as error:
            self._storage_failed(error)

    def _migrate_ship_types(self, legacy_identity: ShipIdentity | None) -> None:
        connection = self._connection
        if connection is None:
            raise sqlite3.DatabaseError("Statistics connection is unavailable")
        if self.backup_if_due(migration=True) is None:
            raise sqlite3.DatabaseError("Cannot migrate statistics without a verified backup")
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP INDEX measurements_ship")
            connection.execute("ALTER TABLE totals RENAME TO legacy_totals")
            connection.execute("ALTER TABLE measurements RENAME TO legacy_measurements")
            connection.execute(
                "CREATE TABLE totals (commander TEXT NOT NULL, ship_id INTEGER NOT NULL, ship_type TEXT NOT NULL, "
                "jumps INTEGER NOT NULL DEFAULT 0, distance REAL NOT NULL DEFAULT 0, "
                "assist_seconds REAL NOT NULL DEFAULT 0, travel_seconds REAL NOT NULL DEFAULT 0, "
                "samples INTEGER NOT NULL DEFAULT 0, sample_seconds REAL NOT NULL DEFAULT 0, estimate REAL, "
                "PRIMARY KEY (commander, ship_id, ship_type))"
            )
            connection.execute(
                "CREATE TABLE measurements (id INTEGER PRIMARY KEY, commander TEXT NOT NULL, ship_id INTEGER NOT NULL, "
                "ship_type TEXT NOT NULL, timestamp TEXT NOT NULL, seconds REAL NOT NULL CHECK (seconds > 0), "
                "FOREIGN KEY (commander, ship_id, ship_type) REFERENCES totals (commander, ship_id, ship_type))"
            )
            connection.execute(
                "INSERT INTO totals SELECT commander, ship_id, '', jumps, distance, assist_seconds, travel_seconds, "
                "samples, sample_seconds, estimate FROM legacy_totals"
            )
            connection.execute(
                "INSERT INTO measurements SELECT id, commander, ship_id, '', timestamp, seconds FROM legacy_measurements"
            )
            if legacy_identity is not None:
                connection.execute("PRAGMA defer_foreign_keys = ON")
                for table in ("totals", "measurements"):
                    connection.execute(
                        f"UPDATE {table} SET ship_type = ? WHERE commander = ? AND ship_id = ?",
                        (legacy_identity.ship_type, legacy_identity.commander, legacy_identity.ship_id),
                    )
            for table in ("legacy_measurements", "legacy_totals"):
                connection.execute(f"DROP TABLE {table}")
            connection.execute("CREATE INDEX measurements_ship ON measurements (commander, ship_id, ship_type, id)")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise sqlite3.DatabaseError("Migrated statistics contain invalid ship references")
            connection.execute("PRAGMA user_version = 2")
            self._mark_dirty()
        if connection.execute("SELECT 1 FROM totals WHERE ship_type = '' LIMIT 1").fetchone():
            self._notify(
                "Older statistics have no recorded ship type. They remain in account totals, "
                "but are not used for ship statistics or ETA."
            )

    def _storage_failed(self, error: Exception) -> None:
        logger.error("Assist statistics unavailable: %s", error)
        self._notify(
            "Assist statistics could not be saved or loaded. Statistics and ETA are unavailable; check the log."
        )
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _ensure_identity(self) -> None:
        if self._connection is not None and self.identity is not None:
            self._connection.execute(
                "INSERT OR IGNORE INTO totals (commander, ship_id, ship_type) VALUES (?, ?, ?)",
                self.identity.key,
            )

    def set_identity(self, state: dict) -> None:
        with self._lock:
            identity = ShipIdentity.from_state(state)
            if identity != self.identity:
                self.end_assist()
                self.identity = identity

    def begin_assist(self, state: dict) -> None:
        with self._lock:
            self.set_identity(state)
            if self._closed:
                return
            if self.identity is None:
                logger.warning("Assist statistics cannot start without a commander, ship ID and ship type.")
                self._notify(
                    "Commander, ship ID or ship type is unavailable. This assist cannot be recorded in statistics."
                )
                return
            if self._assist_started is None:
                self._assist_started = self._clock()
                self._assist_checkpoint = self._assist_started

    def begin_route(self, state: dict, destination: str) -> None:
        with self._lock:
            self.end_route()
            self.set_identity(state)
            if self._closed or self.identity is None or self._assist_started is None:
                return
            self._route_started = self._clock()
            self._travel_checkpoint = self._route_started
            self._destination = destination.casefold()
            self._route_jumps = 0
            self._route_distance = 0

    def expect_jump(self) -> None:
        with self._lock:
            self._jump_requested = self._route_started is not None

    def observe(self, event: dict, state: dict) -> None:
        with self._lock:
            self.set_identity(state)
            name = event.get("event")
            if name in ("LoadGame", "Shutdown", "Died", "Resurrect", "ClearSavedGame"):
                self.end_assist()
                if name == "ClearSavedGame":
                    self.identity = None
                return
            if self._route_started is None:
                return
            if name not in ("StartJump", "FSDJump"):
                return
            try:
                timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("Journal timestamp has no timezone")
                timestamp = timestamp.astimezone(UTC)
            except (KeyError, AttributeError, TypeError, ValueError) as error:
                logger.warning("Statistics rejected a jump timestamp: %s", error)
                self._last_jump = None
                self._jump_started = False
                return
            if name == "StartJump":
                if event.get("JumpType") == "Hyperspace" and self._jump_requested:
                    self._jump_started = True
                return
            if not self._jump_started:
                return
            self._jump_requested = self._jump_started = False
            distance = event.get("JumpDist")
            if (
                isinstance(distance, bool)
                or not isinstance(distance, (float, int))
                or not math.isfinite(distance)
                or distance < 0
            ):
                logger.warning("Statistics rejected an invalid jump distance: %r", distance)
                self._last_jump = None
                return
            now = self._clock()
            seconds = None if self._last_jump is None else now - self._last_jump
            # Batched journal reads cannot provide a reliable monotonic interval for each old event.
            if seconds is not None and seconds < 1:
                logger.warning("Statistics discarded a jump interval from batched journal records.")
                seconds = None
            self._save_jump(timestamp, distance, seconds)
            self._last_jump = now
            self._route_jumps += 1
            self._route_distance += distance
            if self._destination and str(event.get("StarSystem", "")).casefold() == self._destination:
                elapsed = now - self._route_started
                self.end_route()
                self._notify(
                    f"System route finished: {self._route_jumps} jumps, "
                    f"{self._route_distance:,.1f} ly, {format_duration(elapsed)} system travel."
                )

    def _save_jump(self, timestamp: datetime, distance: float, seconds: float | None) -> None:
        if self._connection is None or self.identity is None:
            return
        key = self.identity.key
        try:
            now = self._clock()
            with self._connection:
                self._ensure_identity()
                self._checkpoint_time(now)
                self._connection.execute(
                    "UPDATE totals SET jumps = jumps + 1, distance = distance + ? "
                    "WHERE commander = ? AND ship_id = ? AND ship_type = ?",
                    (distance, *key),
                )
                if seconds is not None:
                    previous = self._connection.execute(
                        "SELECT estimate FROM totals WHERE commander = ? AND ship_id = ? AND ship_type = ?", key
                    ).fetchone()[0]
                    estimate = seconds if previous is None else previous + ETA_ALPHA * (seconds - previous)
                    self._connection.execute(
                        "UPDATE totals SET samples = samples + 1, sample_seconds = sample_seconds + ?, estimate = ? "
                        "WHERE commander = ? AND ship_id = ? AND ship_type = ?",
                        (seconds, estimate, *key),
                    )
                    self._connection.execute(
                        "INSERT INTO measurements (commander, ship_id, ship_type, timestamp, seconds) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (*key, timestamp.isoformat(), seconds),
                    )
                    self._connection.execute(
                        "DELETE FROM measurements WHERE commander = ? AND ship_id = ? AND ship_type = ? AND id NOT IN "
                        "(SELECT id FROM measurements WHERE commander = ? AND ship_id = ? AND ship_type = ? "
                        "ORDER BY id DESC LIMIT ?)",
                        (*key, *key, HISTORY_LIMIT),
                    )
                self._mark_dirty()
            if self._assist_started is not None:
                self._assist_checkpoint = now
            if self._route_started is not None:
                self._travel_checkpoint = now
            self.backup_if_due()
            if seconds is not None:
                logger.debug("Recorded assist jump cycle: %.2f s; learned estimate: %.2f s", seconds, estimate)
        except sqlite3.Error as error:
            self._storage_failed(error)

    def _mark_dirty(self) -> None:
        if self._connection is not None:
            self._connection.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('dirty', '1')")

    def _checkpoint_time(self, now: float) -> None:
        if self._connection is None or self.identity is None:
            return
        assist = 0 if self._assist_checkpoint is None else now - self._assist_checkpoint
        travel = 0 if self._travel_checkpoint is None else now - self._travel_checkpoint
        self._connection.execute(
            "UPDATE totals SET assist_seconds = assist_seconds + ?, travel_seconds = travel_seconds + ? "
            "WHERE commander = ? AND ship_id = ? AND ship_type = ?",
            (assist, travel, *self.identity.key),
        )

    def _save_time(self, column: str, seconds: float) -> None:
        if self._connection is None or self.identity is None or seconds <= 0:
            return
        if column not in ("assist_seconds", "travel_seconds"):
            raise ValueError(f"Invalid statistics time column: {column}")
        try:
            with self._connection:
                self._ensure_identity()
                self._connection.execute(
                    f"UPDATE totals SET {column} = {column} + ? WHERE commander = ? AND ship_id = ? AND ship_type = ?",
                    (seconds, *self.identity.key),
                )
                self._mark_dirty()
            self.backup_if_due()
        except sqlite3.Error as error:
            self._storage_failed(error)

    def end_route(self) -> None:
        with self._lock:
            if self._route_started is not None:
                elapsed = self._clock() - self._travel_checkpoint
                self._route_started = None
                self._travel_checkpoint = None
                self._save_time("travel_seconds", elapsed)
            self._last_jump = None
            self._jump_requested = self._jump_started = False

    def end_assist(self) -> None:
        with self._lock:
            self.end_route()
            if self._assist_started is not None:
                elapsed = self._clock() - self._assist_checkpoint
                self._assist_started = None
                self._assist_checkpoint = None
                self._save_time("assist_seconds", elapsed)

    def snapshot(self) -> StatisticsSnapshot:
        with self._lock:
            if self._connection is None or self.identity is None:
                return StatisticsSnapshot(self._connection is not None, self.identity)
            try:
                row = self._connection.execute(
                    "SELECT jumps, distance, assist_seconds, travel_seconds, samples, sample_seconds, estimate "
                    "FROM totals WHERE commander = ? AND ship_id = ? AND ship_type = ?",
                    self.identity.key,
                ).fetchone()
                total = self._connection.execute(
                    "SELECT SUM(jumps), SUM(distance), SUM(assist_seconds), SUM(travel_seconds), "
                    "SUM(samples), SUM(sample_seconds) FROM totals WHERE commander = ?",
                    (self.identity.commander,),
                ).fetchone()
                now = self._clock()
                assist = 0 if self._assist_checkpoint is None else now - self._assist_checkpoint
                travel = 0 if self._travel_checkpoint is None else now - self._travel_checkpoint
                ship = list(row) if row else [0, 0, 0, 0, 0, 0, None]
                commander = [value or 0 for value in total]
                for values in (ship, commander):
                    values[2] += assist
                    values[3] += travel
                return StatisticsSnapshot(True, self.identity, Totals(*commander), Totals(*ship))
            except sqlite3.Error as error:
                self._storage_failed(error)
                return StatisticsSnapshot(False, self.identity)

    def eta_seconds(self, remaining_jumps: int) -> float | None:
        with self._lock:
            if self._route_started is None or remaining_jumps <= 0:
                return None
            ship = self.snapshot().ship
            if ship.samples < MIN_ETA_SAMPLES or ship.estimate is None:
                return None
            elapsed = self._clock() - (self._last_jump if self._last_jump is not None else self._route_started)
            # An overdue cycle must not consume the estimates for later jumps or report a false arrival.
            current = max(1.0, ship.estimate - elapsed)
            return current + (remaining_jumps - 1) * ship.estimate

    @property
    def route_active(self) -> bool:
        with self._lock:
            return self._route_started is not None and self._connection is not None

    def backup_if_due(self, migration: bool = False) -> Path | None:
        with self._lock:
            if self._connection is None:
                return None
            now = self._utc_now().astimezone(UTC)
            try:
                dirty = self._connection.execute("SELECT value FROM metadata WHERE key = 'dirty'").fetchone()
                if not migration and dirty != ("1",):
                    return None
                last = self._connection.execute("SELECT value FROM metadata WHERE key = 'last_backup'").fetchone()
                previous = datetime.fromisoformat(last[0]) if last else None
                if not migration and any(
                    value is not None and (now - value).total_seconds() < BACKUP_INTERVAL
                    for value in (previous, self._backup_attempt)
                ):
                    return None
                self._backup_attempt = now
                prefix = "statistics-migration-" if migration else "statistics-backup-"
                target = self._database.parent / f"{prefix}{now:%Y%m%dT%H%M%S%fZ}.sqlite3"
                temporary = target.with_suffix(".tmp")
                try:
                    with closing(sqlite3.connect(temporary)) as backup:
                        self._connection.backup(backup)
                        if backup.execute("PRAGMA quick_check").fetchone() != ("ok",):
                            raise sqlite3.DatabaseError("Statistics backup integrity check failed")
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                if not migration:
                    with self._connection:
                        self._connection.execute(
                            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_backup', ?)", (now.isoformat(),)
                        )
                        self._connection.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('dirty', '0')")
                    backups = sorted(self._database.parent.glob("statistics-backup-*.sqlite3"), reverse=True)
                    for old in backups[BACKUP_LIMIT:]:
                        old.unlink()
                logger.debug("Statistics backup saved: %s", target.name)
                return target
            except (OSError, sqlite3.Error, ValueError) as error:
                logger.warning("Statistics backup failed: %s", error)
                self._notify("Statistics backup or rotation failed. Check the log and retain your existing backups.")
                return None

    def close(self) -> None:
        with self._lock:
            self.end_assist()
            self._closed = True
            if self._connection is not None:
                self._connection.close()
                self._connection = None

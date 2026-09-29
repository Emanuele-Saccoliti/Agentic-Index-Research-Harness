"""Transactional append-only local storage with versioned, chained records."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

from pydantic import JsonValue, TypeAdapter, ValidationError

from etf_harness.registry.base import RegistryError, RevisionConflict
from etf_harness.schemas.domain import Event, Record, canonical_json, digest

_RECORD: TypeAdapter[Record] = TypeAdapter(Record)
_GENESIS = "0" * 64


class SQLiteRegistry:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, isolation_level=None, timeout=5)
        try:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RegistryError(f"Unsupported registry schema version: {version}")
            if version == 0:
                tables = self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                if tables:
                    raise RegistryError("Refusing an unversioned existing database")
                self._connection.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE events (
                        record_id TEXT PRIMARY KEY,
                        campaign_id TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK(revision > 0),
                        event_json TEXT NOT NULL,
                        UNIQUE(campaign_id, revision)
                    );
                    CREATE TRIGGER events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'append-only: UPDATE denied'); END;
                    CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'append-only: DELETE denied'); END;
                    CREATE TRIGGER events_no_replace BEFORE INSERT ON events
                    WHEN EXISTS (
                        SELECT 1 FROM events WHERE record_id = NEW.record_id
                        OR (campaign_id = NEW.campaign_id AND revision = NEW.revision)
                    )
                    BEGIN SELECT RAISE(ABORT, 'append-only: replacement denied'); END;
                    PRAGMA user_version = 1;
                    COMMIT;
                """)
            triggers = {
                row[0]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                )
            }
            if not {"events_no_update", "events_no_delete", "events_no_replace"} <= triggers:
                raise RegistryError("Append-only enforcement triggers are missing")
        except (sqlite3.Error, RegistryError):
            self._connection.close()
            raise

    def __enter__(self) -> SQLiteRegistry:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def events(self, campaign_id: str) -> tuple[Event, ...]:
        rows = self._connection.execute(
            "SELECT record_id, revision, event_json FROM events "
            "WHERE campaign_id = ? ORDER BY revision",
            (campaign_id,),
        ).fetchall()
        events: list[Event] = []
        previous = _GENESIS
        for expected_revision, (record_id, revision, raw) in enumerate(rows, start=1):
            try:
                event = Event.model_validate_json(raw)
            except ValidationError as exc:
                raise RegistryError("Invalid event schema in stored history") from exc
            body = event.model_dump(mode="json", exclude={"record_digest"})
            if (
                revision != expected_revision
                or event.revision != revision
                or event.campaign_id != campaign_id
                or event.record.campaign_id != campaign_id
                or event.record.id != record_id
                or event.previous_digest != previous
                or event.record_digest != digest(body)
            ):
                raise RegistryError(f"Registry integrity check failed at revision {revision}")
            events.append(event)
            previous = event.record_digest
        return tuple(events)

    def append(
        self, campaign_id: str, expected_revision: int, records: Sequence[Record]
    ) -> tuple[Event, ...]:
        if not records:
            raise RegistryError("An append must contain at least one record")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            history = self.events(campaign_id)
            if len(history) != expected_revision:
                raise RevisionConflict("Stale campaign revision; reload before retrying")
            previous = history[-1].record_digest if history else _GENESIS
            appended: list[Event] = []
            for revision, record in enumerate(records, start=expected_revision + 1):
                # Frozen Pydantic models can still contain mutable mappings; revalidate at I/O.
                record = _RECORD.validate_json(canonical_json(record))
                if record.campaign_id != campaign_id:
                    raise RegistryError("Record belongs to a different campaign")
                body: dict[str, JsonValue] = {
                    "schema_version": 1,
                    "campaign_id": campaign_id,
                    "revision": revision,
                    "previous_digest": previous,
                    "record": record.model_dump(mode="json"),
                }
                event = Event.model_validate({**body, "record_digest": digest(body)})
                self._connection.execute(
                    "INSERT INTO events(record_id, campaign_id, revision, event_json) "
                    "VALUES (?, ?, ?, ?)",
                    (record.id, campaign_id, revision, canonical_json(event)),
                )
                appended.append(event)
                previous = event.record_digest
            self._connection.execute("COMMIT")
            return tuple(appended)
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise

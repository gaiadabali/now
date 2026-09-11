"""Idempotency ledger for `events` — a real schema gap discovered by this
ticket, not a design choice.

Every other table this loader writes has a natural, already-unique-indexed
key to upsert on: `articles.legacy_wp_id` (unique), `media.filename`
(unique — this loader encodes the attachment's wp_id into it, see
`load_media.py`), `places.slug` (unique — this loader makes slugs
collision-free across venues, see `load_places.py`), and `authors.slug`
(unique; `legacy_wp_user_id` is NOT unique-indexed despite this ticket's
brief saying it is — see the final report). `events` has none of the
above: no legacy id column, no unique business key at all in the schema
shipped by E1.6 (`engine/packages/cms/src/collections/Events.ts` — place,
startsAt, endsAt, rrule, ticketUrl only).

Rather than improvise DDL on a table this package doesn't own (forbidden —
schema changes go through senior-db/architect), this loader keeps its own
tiny mapping `(city_db_ref, source_wp_id) -> events.id` in a SQLite file
under `engine/packages/loader/state/`. It is loader-private bookkeeping,
not a second source of truth for event data (the row content always comes
from `events.jsonl`; this file only remembers *which primary key* a given
WP event was last written to, so a second run UPDATEs instead of
INSERTing a duplicate).

Follow-up recommendation (stated in the final report, not acted on here):
add `events.legacy_wp_id` (unique) in a future Payload migration and this
ledger can be retired in favour of a plain `ON CONFLICT`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parents[2] / "state"


def _db_path(city: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in city)
    return STATE_DIR / f"{safe_name}.sqlite3"


class EventLedger:
    """One ledger file per target city (keyed by the `--city` value the
    caller passed, exactly as passed — see `now_loader.cli`)."""

    def __init__(self, city: str):
        self._conn = sqlite3.connect(_db_path(city))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events_loaded ("
            " source_wp_id INTEGER PRIMARY KEY,"
            " city_event_id INTEGER NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, source_wp_id: int) -> int | None:
        row = self._conn.execute(
            "SELECT city_event_id FROM events_loaded WHERE source_wp_id = ?", (source_wp_id,)
        ).fetchone()
        return row[0] if row else None

    def record(self, source_wp_id: int, city_event_id: int) -> None:
        self._conn.execute(
            "INSERT INTO events_loaded (source_wp_id, city_event_id) VALUES (?, ?) "
            "ON CONFLICT(source_wp_id) DO UPDATE SET city_event_id = excluded.city_event_id",
            (source_wp_id, city_event_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EventLedger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

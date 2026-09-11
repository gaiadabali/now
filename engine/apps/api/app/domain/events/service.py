"""Writes a validated `EventsBatchIn` into `engine.interactions` /
`engine.impressions` for one city DB.

Raw SQL via `AsyncSession.execute(text(...), [param_dict, ...])` (SQLAlchemy
executemany), matching the rest of this codebase's "no ORM over `engine`"
style (see `app/infra/db/registry.py`). `interactions`/`impressions` are
Alembic-owned, hand-written-SQL tables (0001/0002) with no SQLAlchemy Table
metadata anywhere in this repo -- introducing one just for this insert would
be a second source of truth for a schema this package doesn't own.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events.normalize import (
    InvalidEventIdentifierError,
    extract_query,
    extract_target_url,
    interaction_entity_id,
    parse_native_entity_id,
    parse_uuid,
)
from app.domain.events.schemas import EventsBatchIn, ImpressionIn, InteractionIn

_INSERT_INTERACTIONS = text(
    """
    INSERT INTO engine.interactions
        (anon_id, user_id, session_id, entity_type, entity_id, kind, surface,
         rail, position, dwell_ms, scroll_pct, referrer, utm, device, ts, query, target_url)
    VALUES
        (:anon_id, :user_id, :session_id, :entity_type, :entity_id, :kind, :surface,
         :rail, :position, :dwell_ms, :scroll_pct, :referrer, CAST(:utm AS jsonb), :device, :ts, :query, :target_url)
    """
)

_INSERT_IMPRESSIONS = text(
    """
    INSERT INTO engine.impressions
        (session_id, anon_id, surface, rail, entity_id, position, ts)
    VALUES
        (:session_id, :anon_id, :surface, :rail, :entity_id, :position, :ts)
    """
)


class EventsWriteError(Exception):
    """Base for write-time failures that are the *client's* fault (bad
    data) rather than an infrastructure problem -- callers map these to a
    4xx, never a 500.

    `InvalidEventIdentifierError` (a beacon-supplied `anon_id`/`session_id`/
    `user_id` that isn't a real UUID -- decision C4 -- or an
    entity-referencing `entity_id` that isn't a native integer PK --
    F66/migration 0007) is folded into this same 4xx family by
    `write_events` below, rather than being allowed to escape as an
    unhandled `ValueError` (which FastAPI would otherwise turn into a
    500)."""


class EventOutOfRangeError(EventsWriteError):
    """A `ts` fell outside the range of partitions currently provisioned
    for `engine.interactions` / `engine.impressions` (see
    `now_db.partitions.ensure_daily_partitions` -- daily partitions are
    pre-created for roughly [today-1, today+7]). A client clock wildly
    wrong (or a malicious payload) can trigger this; it is a data problem,
    not a server problem."""


@dataclass(frozen=True)
class EventsWriteResult:
    interactions_written: int
    impressions_written: int


def _epoch_ms_to_datetime(epoch_ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(epoch_ms / 1000, tz=dt.timezone.utc)


def _interaction_params(row: InteractionIn) -> dict[str, object]:
    return {
        "anon_id": parse_uuid(row.anon_id, "anon_id"),
        "user_id": parse_uuid(row.user_id, "user_id") if row.user_id else None,
        "session_id": parse_uuid(row.session_id, "session_id"),
        "entity_type": row.entity_type,
        "entity_id": interaction_entity_id(row.entity_type, row.entity_id),
        "kind": row.kind,
        "surface": row.surface,
        "rail": row.rail,
        "position": row.position,
        "dwell_ms": row.dwell_ms,
        "scroll_pct": row.scroll_pct,
        "referrer": row.referrer,
        "utm": json.dumps(row.utm) if row.utm is not None else None,
        "device": row.device,
        "ts": _epoch_ms_to_datetime(row.ts),
        "query": extract_query(row.entity_type, row.entity_id),
        "target_url": extract_target_url(row.entity_type, row.entity_id),
    }


def _impression_params(row: ImpressionIn) -> dict[str, object]:
    # Impressions have no non-entity encoding (unlike interactions' search/
    # outbound cases) -- a rail always registers a real candidate row, so
    # `entity_id` here must always name one. `engine.impressions.entity_id`
    # is `text NOT NULL` as of migration 0007 (F66) -- it was left `uuid
    # NOT NULL` by decision C4 (0003 only scoped `interactions`), which
    # meant a real article/place id (a Payload integer serial, never a
    # uuid) was rejected outright. Same native-PK validation as
    # `interaction_entity_id` uses for a real `interactions.entity_id`.
    return {
        "session_id": parse_uuid(row.session_id, "session_id"),
        "anon_id": parse_uuid(row.anon_id, "anon_id"),
        "surface": row.surface,
        "rail": row.rail,
        "entity_id": parse_native_entity_id(row.entity_id, "entity_id"),
        "position": row.position,
        "ts": _epoch_ms_to_datetime(row.ts),
    }


def _is_partition_range_error(exc: IntegrityError) -> bool:
    message = str(exc.orig) if exc.orig is not None else str(exc)
    return "no partition of relation" in message


async def write_events(db: AsyncSession, batch: EventsBatchIn) -> EventsWriteResult:
    """Writes both arrays in one transaction. Either array may be empty --
    an empty `executemany` list is a documented SQLAlchemy no-op, not an
    error.

    Raises `EventsWriteError` (never lets the raw `InvalidEventIdentifierError`
    escape as an unhandled `ValueError`) when a beacon-supplied `anon_id`/
    `session_id`/`user_id` isn't a genuine UUID, or an entity-referencing
    `entity_id` isn't a native integer PK -- decision C4 (identifiers) and
    F66 (entity_id, migration 0007) both replaced a silent-hash/wrong-type
    fallback with outright rejection. Parameter building happens *before*
    anything touches the database, so a bad identifier in event N of a
    batch never leaves events 0..N-1 partially written.

    Raises `EventOutOfRangeError` (never lets the raw `IntegrityError`
    escape) when a `ts` falls outside the provisioned partition window --
    callers map both of the above to `400`.
    """
    try:
        interaction_rows = [_interaction_params(row) for row in batch.interactions]
        impression_rows = [_impression_params(row) for row in batch.impressions]
    except InvalidEventIdentifierError as exc:
        raise EventsWriteError(str(exc)) from exc

    try:
        if interaction_rows:
            await db.execute(_INSERT_INTERACTIONS, interaction_rows)
        if impression_rows:
            await db.execute(_INSERT_IMPRESSIONS, impression_rows)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_partition_range_error(exc):
            raise EventOutOfRangeError(
                "one or more events have a `ts` outside the currently retained/provisioned "
                "date range"
            ) from exc
        raise EventsWriteError(f"events batch rejected: {exc}") from exc

    return EventsWriteResult(
        interactions_written=len(batch.interactions),
        impressions_written=len(batch.impressions),
    )

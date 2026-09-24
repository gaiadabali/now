"""Synthetic type/status fixtures for testing the filter pipeline before
E2.1 classification lands (`articles.primary_type`/`.format` are NULL for
all 4,772 rows; all 177 `places` wear the F27 loader sentinel --
`type='editorial'`, `status='pending_review'` -- so NEITHER table has the
type/status variety needed to prove competitor exclusion or the F27
status gate against real data alone).

**Not a shadow-table trick.** Every table created here has a name
distinct from any real table (`now_filters_synth_places`,
`now_filters_synth_articles`) and is a session-scoped Postgres `TEMP
TABLE` (dropped automatically when the connection closes -- nothing to
clean up, no risk of leaking into another session, exactly the isolation
property `CREATE TEMP TABLE` gives for free). `hard.py`'s query builders
only ever read a synthetic table when a test explicitly passes
`places_table=SYNTH_PLACES_TABLE` / `articles_table=SYNTH_ARTICLES_TABLE`
-- production code never passes those arguments, so there is no
production code path that can read synthetic data, and no risk of the
two tables being confused for one another by name.

"Make the switch-over trivial" (task brief): the only thing that changes
between a synthetic-data test and production is which table name string
`hard.py`'s builders are given. The WHERE-clause logic, the column
projection, the competitor-exclusion join against `engine.type_relations`
-- all identical SQL text either way.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

SYNTH_PLACES_TABLE = "now_filters_synth_places"
SYNTH_ARTICLES_TABLE = "now_filters_synth_articles"
SYNTH_EVENTS_TABLE = "now_filters_synth_events"
SYNTH_PLACE_MENTIONS_TABLE = "now_filters_synth_place_mentions"
SYNTH_HIDDEN_RIVAL_FLAGS_TABLE = "now_filters_synth_hidden_rival_flags"

# The 6 venue L1 types (excludes `event`/`editorial`, which are the two
# `exclude_same=false` rows in engine.type_relations -- see ARCHITECTURE.md
# Sec.4). Used as the pool for deterministic synthetic assignment.
VENUE_TYPES = ("stay", "eat", "drink", "wellness", "shop", "do")
ALL_TYPES = VENUE_TYPES + ("event", "editorial")


@dataclass(frozen=True)
class SyntheticPlace:
    id: int
    type: str
    subtype: str = "unspecified"
    status: str = "active"
    area_term: str | None = "senopati"
    org_id: str | None = None
    price_band: str | None = "moderate"
    lat: float | None = None
    lng: float | None = None
    # Added for the hidden-rival guard (`now_filters.hidden_rival`), which
    # matches a FEATURED place_mentions row's place NAME against the
    # taxonomy subtype lexicon -- every earlier caller of this dataclass
    # left `name` unset and gets the harmless default below, so this is
    # additive, not a breaking change to the synthetic-places contract.
    name: str = "Synthetic Place"


@dataclass(frozen=True)
class SyntheticHiddenRivalFlag:
    article_id: int
    matched_type: str
    signal: str = "featured_mention"  # 'featured_mention' | 'title'


@dataclass(frozen=True)
class SyntheticPlaceMention:
    article_id: int
    place_id: int
    role: str  # 'featured' | 'reviewed' | 'mentioned' -- enum_place_mentions_role
    surface_text: str = "synthetic mention"


@dataclass(frozen=True)
class SyntheticArticle:
    id: int
    primary_type: str | None
    format: str | None = "guide"
    series_key: str | None = None
    published_at: datetime = field(default_factory=lambda: datetime(2025, 1, 1, tzinfo=timezone.utc))
    status: str = "published"
    # Added for the hidden-rival guard's TITLE signal
    # (`now_filters.hidden_rival_recompute`), which matches an article's
    # own title against the taxonomy subtype lexicon -- every earlier
    # caller left `title` unset and gets the harmless default below, so
    # this is additive, not a breaking change to the synthetic-articles
    # contract.
    title: str = "Synthetic Article"


def create_synthetic_places_table(conn: Connection, rows: list[SyntheticPlace], *, table: str = SYNTH_PLACES_TABLE) -> str:
    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {table} ("
            "id int PRIMARY KEY, type text NOT NULL, subtype text, status text NOT NULL, "
            "area_term text, org_id text, price_band text, lat double precision, lng double precision, "
            "geo geography(Point,4326), name text NOT NULL DEFAULT 'Synthetic Place'"
            ")"
        )
    )
    for r in rows:
        has_geo = r.lat is not None and r.lng is not None
        geo_expr = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography" if has_geo else "NULL"
        conn.execute(
            text(
                f"INSERT INTO {table} (id, type, subtype, status, area_term, org_id, price_band, lat, lng, geo, name) "
                "VALUES (:id, :type, :subtype, :status, :area_term, :org_id, :price_band, :lat, :lng, "
                f"{geo_expr}, :name)"
            ),
            {
                "id": r.id,
                "type": r.type,
                "subtype": r.subtype,
                "status": r.status,
                "area_term": r.area_term,
                "org_id": r.org_id,
                "price_band": r.price_band,
                "lat": r.lat,
                "lng": r.lng,
                "name": r.name,
            },
        )
    return table


def create_synthetic_place_mentions_table(
    conn: Connection, rows: list[SyntheticPlaceMention], *, table: str = SYNTH_PLACE_MENTIONS_TABLE
) -> str:
    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {table} ("
            "id serial PRIMARY KEY, article_id int NOT NULL, place_id int NOT NULL, "
            "role text NOT NULL, surface_text text"
            ")"
        )
    )
    for r in rows:
        conn.execute(
            text(
                f"INSERT INTO {table} (article_id, place_id, role, surface_text) "
                "VALUES (:article_id, :place_id, :role, :surface_text)"
            ),
            {
                "article_id": r.article_id,
                "place_id": r.place_id,
                "role": r.role,
                "surface_text": r.surface_text,
            },
        )
    return table


def create_synthetic_hidden_rival_flags_table(
    conn: Connection, rows: list[SyntheticHiddenRivalFlag], *, table: str = SYNTH_HIDDEN_RIVAL_FLAGS_TABLE
) -> str:
    """Stands in for `engine.hidden_rival_flags` (migration 0009) --
    `build_articles_hard_filter_sql(hidden_rival_flags_table=...)` reads
    whichever table name it is given, exactly like every other
    swap-in-a-synthetic-table parameter in this module (see this file's
    own docstring)."""
    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {table} ("
            "article_id text NOT NULL, matched_type text NOT NULL, signal text NOT NULL, "
            "PRIMARY KEY (article_id, matched_type, signal)"
            ")"
        )
    )
    for r in rows:
        conn.execute(
            text(f"INSERT INTO {table} (article_id, matched_type, signal) VALUES (:article_id, :matched_type, :signal)"),
            {"article_id": str(r.article_id), "matched_type": r.matched_type, "signal": r.signal},
        )
    return table


def create_synthetic_articles_table(conn: Connection, rows: list[SyntheticArticle], *, table: str = SYNTH_ARTICLES_TABLE) -> str:
    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(
        text(
            f"CREATE TEMP TABLE {table} ("
            "id int PRIMARY KEY, primary_type text, format text, series_key text, "
            "published_at timestamptz, _status text NOT NULL, title text NOT NULL DEFAULT 'Synthetic Article'"
            ")"
        )
    )
    for r in rows:
        conn.execute(
            text(
                f"INSERT INTO {table} (id, primary_type, format, series_key, published_at, _status, title) "
                "VALUES (:id, :primary_type, :format, :series_key, :published_at, :status, :title)"
            ),
            {
                "id": r.id,
                "primary_type": r.primary_type,
                "format": r.format,
                "series_key": r.series_key,
                "published_at": r.published_at,
                "status": r.status,
                "title": r.title,
            },
        )
    return table


def deterministic_type(entity_id: int, *, seed: str = "now-filters-synthetic-v1", pool: tuple[str, ...] = VENUE_TYPES) -> str:
    """Assigns one of `pool`'s types to `entity_id`, deterministically
    (same id -> same type every run, for reproducible tests) but without
    the kind of ordering bias a plain `id % len(pool)` would introduce
    (consecutive ids would cycle through types in lockstep with whatever
    order they were inserted/loaded in) -- hashed the same way
    `now_eval.datasets.type_labels` samples deterministically."""
    digest = hashlib.sha256(f"{seed}:{entity_id}".encode()).hexdigest()
    idx = int(digest[:8], 16) % len(pool)
    return pool[idx]


def generate_synthetic_place_rows(n: int, *, start_id: int = 900_001, seed: str = "now-filters-synthetic-places-v1") -> list[SyntheticPlace]:
    """`n` places spread deterministically across VENUE_TYPES, statuses
    (80% active / 10% pending_review / 10% closed -- proportions chosen
    to guarantee every status bucket is exercised at any n>=10, not to
    model the real corpus), and 5 orgs (so `max 1 per org` diversity has
    something real to cap) and 3 areas (so area-level fallback rungs have
    something to escalate through)."""
    orgs = ["org-marriott", "org-accor", "org-independent-a", "org-independent-b", "org-independent-c"]
    areas = ["senopati", "kemang", "scbd"]
    out: list[SyntheticPlace] = []
    for i in range(n):
        entity_id = start_id + i
        digest = hashlib.sha256(f"{seed}:{entity_id}".encode()).hexdigest()
        status_roll = int(digest[8:10], 16) % 10
        status = "active" if status_roll < 8 else ("pending_review" if status_roll == 8 else "closed")
        out.append(
            SyntheticPlace(
                id=entity_id,
                type=deterministic_type(entity_id, seed=seed, pool=VENUE_TYPES),
                status=status,
                org_id=orgs[int(digest[10:12], 16) % len(orgs)],
                area_term=areas[int(digest[12:14], 16) % len(areas)],
                price_band=["budget", "moderate", "upscale", "luxury"][int(digest[14:16], 16) % 4],
                lat=-6.22 + (int(digest[16:20], 16) % 1000) / 100000.0,
                lng=106.80 + (int(digest[20:24], 16) % 1000) / 100000.0,
            )
        )
    return out

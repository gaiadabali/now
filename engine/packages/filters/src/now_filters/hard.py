"""Hard filters (ARCHITECTURE.md Sec.8.A) -- "never violated". Selective,
indexed-or-indexable predicates (status, self, competitor type, area) are
pushed into SQL per Sec.8.G's ordering rule; PostGIS radius runs in the
same statement (it is itself a cheap, index-backed op via the `ix_places_geo`
GiST index) so the expensive per-row work downstream (vector kNN, in this
package's caller; per-user checks, this package's `contextual.py`) only
ever sees the already-reduced candidate set.

**Table names are parameters, not hardcoded**, specifically so tests can
point these exact query builders at an explicitly-named, explicitly-seeded
temp table instead of `public.places`/`public.articles`/`public.events`
(see `synthetic.py`) -- never at a same-named shadow of the production
table. Production code paths never pass a non-default table name; every
default is the real Payload-owned table.

F27 (PROGRESS.md, launch-blocking): all 177 places currently sit at
`status='pending_review'` wearing the `editorial`/`city-guide` loader
sentinel, which is invisible to competitor exclusion in both directions.
`_status_predicate()` below is the enforcement point -- `status='active'`
is unconditional, appears in every rung of the fallback ladder with no
relaxation path, and is asserted directly in
`tests/test_hard_filters_status.py` against the real (currently
100%-pending_review) `now_jakarta.places` table.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_filters.models import Candidate
from now_filters.type_relations import TypeRelation, excluded_types_for

DEFAULT_PLACES_TABLE = "public.places"
DEFAULT_ARTICLES_TABLE = "public.articles"
DEFAULT_EVENTS_TABLE = "public.events"

# Sec.8.A "Quality floor": one source of truth, borrowed from now-quality
# (E2.6's own reference constant) rather than a second hardcoded 0.35 --
# see now_quality/scoring.py QUALITY_FLOOR docstring for the derivation.
from now_quality.scoring import QUALITY_FLOOR  # noqa: E402


@dataclass(frozen=True)
class PlacesHardFilterQuery:
    sql: str
    params: dict


def build_places_hard_filter_sql(
    *,
    subject_type: str | None,
    relations: dict[str, TypeRelation],
    exclude_self_id: int | None = None,
    area_terms: list[str] | None = None,
    center_lat: float | None = None,
    center_lng: float | None = None,
    radius_m: float | None = None,
    quality_floor: float = QUALITY_FLOOR,
    editorial_fallback: bool = False,
    places_table: str = DEFAULT_PLACES_TABLE,
) -> PlacesHardFilterQuery:
    """Builds the SQL for every Sec.8.A hard filter that applies to
    `places`: status (F27), self, competitor, closed venue, quality
    floor. Radius (Sec.7 Row 2's "within radius (hard)") is included here
    when a center point is given -- it is itself a hard filter for the
    Nearby rail, not merely a ladder-widening knob; the ladder widens the
    *value* of `radius_m`, it does not make radius optional.

    Event expiry and offer expiry do not apply to `places` rows directly
    (see `build_events_hard_filter_sql` for event expiry; offer expiry is
    a `campaigns.ends_at` check against the platform DB -- out of this
    package's single-DB scope, exactly as now-search does not reach into
    a second database; see README "Offer expiry -- stubbed").
    Series dedup is an `articles`-only concept (`articles.series_key`).
    """
    where: list[str] = [
        "status = 'active'",  # F27 -- unconditional, every rung, no relaxation
    ]
    params: dict = {}

    if exclude_self_id is not None:
        where.append("id != :self_id")
        params["self_id"] = exclude_self_id

    if not editorial_fallback:
        excluded = excluded_types_for(relations, subject_type)
        if excluded:
            where.append("type::text != ALL(:excluded_types)")
            params["excluded_types"] = list(excluded)
        # else: excluded is only ever empty for a KNOWN, exclude_same=False
        # subject type (editorial/do/event) -- a `None`/unclassified
        # subject_type now fails closed instead (F68): excluded_types_for
        # returns every exclude_same=True type plus `unknown`, so this
        # branch is never silently skipped for the unclassified case.
        #
        # F73: no `type IS NOT NULL` guard is needed here (contrast
        # `build_articles_hard_filter_sql` below) -- `places.type` is
        # `NOT NULL` at the schema level, and F49/F57 already gave
        # unclassified places a real sentinel value (`type='unknown'`)
        # rather than leaving them typeless, so `type::text != ALL(...)`
        # never sees a NULL to propagate here. The candidate-side
        # ambiguity this ticket resolves (type_relations.is_competitor's
        # docstring) is real only for `articles.primary_type`.
    else:
        # Editorial fallback rung (Sec.8.F rung 6): curated/popular for
        # type+area. The competitor rule STILL applies -- Sec.1 principle
        # 6 and Sec.8.F both say it never relaxes -- so this branch only
        # widens *how* candidates are selected (dropping fine-grained
        # matching in favour of a popularity/curation signal the caller
        # supplies via ORDER BY upstream), never the exclusion predicate.
        excluded = excluded_types_for(relations, subject_type)
        if excluded:
            where.append("type::text != ALL(:excluded_types)")
            params["excluded_types"] = list(excluded)

    if area_terms:
        where.append("area_term::text = ANY(:area_terms)")
        params["area_terms"] = list(area_terms)

    if radius_m is not None and center_lat is not None and center_lng is not None:
        where.append("geo IS NOT NULL AND ST_DWithin(geo, ST_SetSRID(ST_MakePoint(:c_lng, :c_lat), 4326)::geography, :radius_m)")
        params["c_lat"] = center_lat
        params["c_lng"] = center_lng
        params["radius_m"] = radius_m

    if quality_floor is not None:
        # Missing score (no now_jakarta place has one yet -- see README)
        # never excludes: an un-scored entity is not the same thing as a
        # low-quality one. Only an explicit score below the floor excludes.
        where.append(
            "id NOT IN (SELECT entity_id::int FROM engine.quality_scores "
            "WHERE entity_type = 'place' AND score < :quality_floor)"
        )
        params["quality_floor"] = quality_floor

    sql = (
        "SELECT id, type::text AS type, subtype::text AS subtype, status::text AS status, "
        "area_term::text AS area_term, org_id, price_band::text AS price_band, "
        "lat::float8 AS lat, lng::float8 AS lng "
        f"FROM {places_table} WHERE " + " AND ".join(where)
    )
    return PlacesHardFilterQuery(sql=sql, params=params)


def fetch_places_hard_filtered(conn: Connection, query: PlacesHardFilterQuery) -> list[Candidate]:
    rows = conn.execute(text(query.sql), query.params).fetchall()
    return [
        Candidate(
            entity_type="place",
            entity_id=r.id,
            type=r.type,
            subtype=r.subtype,
            status=r.status,
            area_term=r.area_term,
            org_id=r.org_id,
            price_band=r.price_band,
            lat=r.lat,
            lng=r.lng,
        )
        for r in rows
    ]


@dataclass(frozen=True)
class ArticlesHardFilterQuery:
    sql: str
    params: dict


def build_articles_hard_filter_sql(
    *,
    subject_type: str | None,
    relations: dict[str, TypeRelation],
    exclude_self_id: int | None = None,
    quality_floor: float = QUALITY_FLOOR,
    series_dedup: bool = True,
    articles_table: str = DEFAULT_ARTICLES_TABLE,
) -> ArticlesHardFilterQuery:
    """Sec.8.A hard filters over `articles`: status (published only --
    `_status = 'published'`, Payload's draft/publish lifecycle; embargo
    is `published_at <= now()`, included unconditionally since a
    not-yet-embargoed article is not "hard-filterable data noise", it is
    literally not live yet), self, competitor (via `primary_type` --
    currently NULL for all 4,772 rows, E2.1 not run, see README), quality
    floor (real data: `engine.quality_scores` has 4,772 real article
    rows), series dedup (one per `series_key`, real data: 5 articles
    across 2 keys as of this ticket).

    Series dedup picks the highest-quality row per `series_key` via
    `DISTINCT ON` -- deterministic, and consistent with keeping the best
    version of a re-published "New Restaurants in Jakarta 2024/2025"
    cluster rather than an arbitrary one. Rows with `series_key IS NULL`
    are each their own group (never deduped against each other).
    """
    where: list[str] = [
        "_status = 'published'",
        "published_at IS NOT NULL AND published_at <= now()",
    ]
    params: dict = {}

    if exclude_self_id is not None:
        where.append("id != :self_id")
        params["self_id"] = exclude_self_id

    excluded = excluded_types_for(relations, subject_type)
    if excluded:
        # F73/F74 (PROGRESS.md): `primary_type` is NULL for every real
        # article until E2.1 classifies the archive (F50). Postgres's
        # `!= ALL(...)` already evaluates to NULL (excluded by the WHERE
        # clause) for a NULL `primary_type` -- this package's decision
        # (type_relations.is_competitor's docstring) is that an
        # unidentifiable candidate must fail CLOSED whenever the subject
        # excludes anything at all, the same principle F68 applies to an
        # unidentifiable subject. `primary_type IS NOT NULL` makes that
        # exclusion an explicit, intentional predicate rather than an
        # implicit consequence of SQL NULL semantics a future edit (e.g.
        # a stray COALESCE) could silently invert. Behaviour-preserving:
        # this is what the predicate already did.
        where.append("primary_type IS NOT NULL AND primary_type::text != ALL(:excluded_types)")
        params["excluded_types"] = list(excluded)

    if quality_floor is not None:
        where.append(
            "id NOT IN (SELECT entity_id::int FROM engine.quality_scores "
            "WHERE entity_type = 'article' AND score < :quality_floor)"
        )
        params["quality_floor"] = quality_floor

    base_where = " AND ".join(where)
    select_cols = (
        "id, primary_type::text AS type, format::text AS format, series_key, "
        "published_at"
    )
    if series_dedup:
        sql = (
            f"SELECT DISTINCT ON (COALESCE(series_key, 'noseries:' || id::text)) "
            f"{select_cols} "
            f"FROM {articles_table} WHERE {base_where} "
            f"ORDER BY COALESCE(series_key, 'noseries:' || id::text), "
            f"(SELECT score FROM engine.quality_scores qs WHERE qs.entity_type = 'article' "
            f"AND qs.entity_id = {articles_table}.id::text) DESC NULLS LAST, id"
        )
    else:
        sql = f"SELECT {select_cols} FROM {articles_table} WHERE {base_where}"
    return ArticlesHardFilterQuery(sql=sql, params=params)


def fetch_articles_hard_filtered(conn: Connection, query: ArticlesHardFilterQuery) -> list[Candidate]:
    rows = conn.execute(text(query.sql), query.params).fetchall()
    return [
        Candidate(
            entity_type="article",
            entity_id=r.id,
            type=r.type,
            format=r.format,
            series_key=r.series_key,
            published_at=r.published_at,
        )
        for r in rows
    ]


@dataclass(frozen=True)
class EventsHardFilterQuery:
    sql: str
    params: dict


def build_events_hard_filter_sql(
    *,
    now_expr: str = "now()",
    events_table: str = DEFAULT_EVENTS_TABLE,
    places_table: str = DEFAULT_PLACES_TABLE,
) -> EventsHardFilterQuery:
    """Event expiry (`ends_at < now()`) + closed/pending venue exclusion.
    An event tied to a place inherits that place's F27 exposure: a
    `pending_review` or `closed` venue must not surface its events either
    (place_id IS NULL events -- standalone festivals with no venue row --
    are exempt from the venue-status join, per ARCHITECTURE.md Sec.5's
    note that `events.place_id` is nullable)."""
    # `events` has no `published_at`/embargo column (unlike `articles`) --
    # verified against the real schema (engine/packages/cms migrations):
    # `events` carries only `starts_at`/`ends_at` plus Payload's `_status`
    # draft/published lifecycle flag. Status alone is this table's status
    # hard filter.
    sql = (
        "SELECT e.id, e.place_id, e.ends_at "
        f"FROM (SELECT id, place_id, ends_at, _status FROM {events_table}) e "
        f"LEFT JOIN {places_table} p ON p.id = e.place_id "
        "WHERE e._status = 'published' "
        "AND (e.ends_at IS NULL OR e.ends_at >= " + now_expr + ") "
        "AND (e.place_id IS NULL OR p.status = 'active')"
    )
    return EventsHardFilterQuery(sql=sql, params={})

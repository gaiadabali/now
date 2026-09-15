"""`GET /v1/{site}/search` -- E3.1's `now_search.SearchEngine` exposed over
HTTP, with §8's hard filters resolving the candidate pool *before*
retrieval runs.

**Filter-then-retrieve, not retrieve-then-filter.** §8.G is explicit:
"Never retrieve 100 by embedding then filter to 3." So this service
resolves the hard-filtered id set in SQL first and hands it to
`SearchEngine.search(candidate_ids=...)`, which pushes it down into both
the lexical and semantic queries. The vector kNN therefore only ever
scans rows that already passed status, embargo, quality floor and series
dedup.

**No competitor filter here, deliberately.** §8.A's competitor rule is
defined relative to a *subject* ("same L1 `type` excluded" -- excluded
from what? the article you are currently reading). A search has no
subject, so `relations={}` / `subject_type=None` is passed to
`build_articles_hard_filter_sql`, which yields no competitor predicate at
all. This is not the filter being relaxed -- §8.F's "the competitor
filter never relaxes at any rung" governs rails, where a subject exists.
Applying it here would mean a reader searching "hotels" could not be
shown hotels.

**Two connections, because the taxonomy is split across two databases.**
`engine.terms` / `engine.facets` live in the PLATFORM db -- one taxonomy
shared by every city (§4) -- while `engine.entity_terms`, the per-article
assignments, lives in the CITY db alongside the articles themselves. So
resolving `location:senopati` to a term id is a platform query, and
filtering articles by that id is a city query. `app/domain/rails/` opens
the same pair for the same reason.

Runs off the event loop via `app.infra.db.sync_bridge` for the same
reason rails does -- the whole `{now_search, now_filters, now_blender}`
stack is sync.
"""

from __future__ import annotations

import time

from now_config import SiteConfig
from now_filters.hard import build_articles_hard_filter_sql
from now_search.engine import SearchEngine
from now_search.facets import COLUMN_FACETS, ActiveFilter
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.search.schemas import SearchHitOut, SearchResponse, SearchTimingOut
from app.infra.db.sync_bridge import get_sync_city_engine, get_sync_platform_engine, run_sync

DEFAULT_K = 10
MAX_K = 50


class TermFacetResolution:
    """Resolved `facets=` selectors, split into what matched and what did not.

    Unmatched selectors are carried through to the response rather than
    dropped: a typo'd facet that silently returns the *unfiltered* corpus
    is indistinguishable, to the caller, from a filter that legitimately
    matched everything.
    """

    def __init__(self) -> None:
        self.term_ids_by_facet: dict[str, list[str]] = {}
        self.unresolved: list[str] = []


def _resolve_term_facets(platform_conn: Connection, selectors: list[str]) -> TermFacetResolution:
    """Maps `facet:term-slug` selectors to `engine.terms.id`.

    Runs against the PLATFORM connection -- `engine.terms`/`engine.facets`
    are one taxonomy shared by every city (§4), not per-city tables.

    Selectors are slugs, not uuids, because a URL is a public contract
    (§9: "URL structure = named facet queries") and a uuid in a query
    string is not a named anything.
    """
    resolution = TermFacetResolution()
    if not selectors:
        return resolution

    pairs: list[tuple[str, str]] = []
    for selector in selectors:
        facet, _, term_slug = selector.partition(":")
        if not facet or not term_slug:
            resolution.unresolved.append(selector)
            continue
        pairs.append((facet, term_slug))

    if not pairs:
        return resolution

    # Two parallel arrays joined through `unnest`, rather than the more
    # obvious `WHERE (f.key, t.slug) = ANY(:pairs)`: Postgres rejects a
    # list of tuples as a bound parameter ("input of anonymous composite
    # types is not implemented"). Still one round trip, still fully
    # parameterised.
    rows = platform_conn.execute(
        text(
            """
            SELECT f.key AS facet_key, t.slug AS term_slug, t.id::text AS term_id
              FROM unnest(CAST(:facet_keys AS text[]), CAST(:term_slugs AS text[]))
                     AS req(facet_key, term_slug)
              JOIN engine.facets f ON f.key = req.facet_key
              JOIN engine.terms t ON t.facet_id = f.id AND t.slug = req.term_slug
            """
        ),
        {
            "facet_keys": [facet for facet, _ in pairs],
            "term_slugs": [term_slug for _, term_slug in pairs],
        },
    ).fetchall()

    matched = {(r.facet_key, r.term_slug) for r in rows}
    for row in rows:
        resolution.term_ids_by_facet.setdefault(row.facet_key, []).append(row.term_id)
    for facet, term_slug in pairs:
        if (facet, term_slug) not in matched:
            resolution.unresolved.append(f"{facet}:{term_slug}")
    return resolution


def _candidate_ids(
    conn: Connection,
    *,
    types: list[str],
    formats: list[str],
    term_ids_by_facet: dict[str, list[str]],
) -> list[int]:
    """The §8.A hard-filtered pool, further narrowed by the reader's own
    §9 facet choices.

    Reader-chosen facets are applied as hard filters here -- and only
    here. §8.C's "Personalization never hard-filters" constrains what the
    *algorithm* may do on the reader's behalf; it explicitly permits "the
    reader may filter themselves", which is exactly what a `?type=eat` in
    the URL is.
    """
    hard = build_articles_hard_filter_sql(
        subject_type=None,
        relations={},  # see module docstring: no subject => no competitor rule
        series_dedup=True,
    )
    sql = f"SELECT id FROM ({hard.sql}) AS hard_filtered"
    params = dict(hard.params)
    where: list[str] = []

    for facet, values in (("type", types), ("format", formats)):
        if not values:
            continue
        column = COLUMN_FACETS[facet]
        key = f"reader_{facet}"
        where.append(f"id IN (SELECT id FROM public.articles WHERE {column}::text = ANY(:{key}))")
        params[key] = values

    for facet, term_ids in term_ids_by_facet.items():
        key = f"reader_terms_{facet}"
        where.append(
            "id IN (SELECT entity_id::int FROM engine.entity_terms "
            f"WHERE entity_type = 'article' AND term_id::text = ANY(:{key}))"
        )
        params[key] = term_ids

    if where:
        sql = f"{sql} WHERE {' AND '.join(where)}"
    return [int(r.id) for r in conn.execute(text(sql), params).fetchall()]


def _build_active_filters(
    types: list[str], formats: list[str], term_ids_by_facet: dict[str, list[str]]
) -> list[ActiveFilter]:
    """What the reader already narrowed by, handed to facet counting so
    each facet's counts are computed with the *other* facets applied but
    its own lifted -- otherwise a selected facet always reports a count of
    exactly what is on screen, which tells the reader nothing about what
    switching to a sibling value would do."""
    active: list[ActiveFilter] = []
    if types:
        active.append(ActiveFilter(facet="type", values=tuple(types)))
    if formats:
        active.append(ActiveFilter(facet="format", values=tuple(formats)))
    for facet, term_ids in term_ids_by_facet.items():
        active.append(ActiveFilter(facet=facet, values=tuple(term_ids)))
    return active


def _search(
    db_ref: str,
    query: str,
    *,
    k: int,
    types: list[str],
    formats: list[str],
    facets: list[str],
) -> SearchResponse:
    """Runs entirely off the event loop (see `sync_bridge.run_sync`)."""
    city_engine = get_sync_city_engine(db_ref)
    platform_eng = get_sync_platform_engine()
    with city_engine.connect() as conn, platform_eng.connect() as platform_conn:
        t0 = time.perf_counter()
        resolution = _resolve_term_facets(platform_conn, facets)
        candidate_ids = _candidate_ids(
            conn,
            types=types,
            formats=formats,
            term_ids_by_facet=resolution.term_ids_by_facet,
        )
        filter_ms = (time.perf_counter() - t0) * 1000

        if not candidate_ids:
            # An empty pool is a legitimate answer for a search, unlike a
            # rail -- §8.F requires every *rail* to fill, but a reader who
            # filters to an empty intersection should be told so, not
            # handed a silently widened result set.
            return SearchResponse(
                query=query,
                hits=[],
                facet_counts={name: {} for name in COLUMN_FACETS},
                candidate_count=0,
                lexical_candidate_count=0,
                semantic_candidate_count=0,
                timing=SearchTimingOut(
                    lexical_ms=0.0,
                    semantic_ms=0.0,
                    fuse_ms=0.0,
                    filter_ms=filter_ms,
                    total_ms=filter_ms,
                ),
                unresolved_facets=resolution.unresolved,
            )

        engine = SearchEngine(conn)
        result = engine.search(
            query,
            k=k,
            candidate_ids=candidate_ids,
            active_filters=_build_active_filters(types, formats, resolution.term_ids_by_facet),
        )
        summaries = engine.fetch_summaries([int(h.entity_id) for h in result.hits])

    hits: list[SearchHitOut] = []
    for position, hit in enumerate(result.hits, start=1):
        entity_id = int(hit.entity_id)
        summary = summaries.get(entity_id)
        hits.append(
            SearchHitOut(
                entity_id=entity_id,
                position=position,
                rrf_score=hit.rrf_score,
                lexical_rank=hit.lexical_rank,
                semantic_rank=hit.semantic_rank,
                title=summary.title if summary else None,
                dek=summary.dek if summary else None,
                legacy_permalink=summary.legacy_permalink if summary else None,
            )
        )

    return SearchResponse(
        query=query,
        hits=hits,
        facet_counts=result.facet_counts,
        candidate_count=len(candidate_ids),
        lexical_candidate_count=result.lexical_candidate_count,
        semantic_candidate_count=result.semantic_candidate_count,
        timing=SearchTimingOut(
            lexical_ms=result.timing.lexical_ms,
            semantic_ms=result.timing.semantic_ms,
            fuse_ms=result.timing.fuse_ms,
            filter_ms=filter_ms,
            total_ms=result.timing.total_ms + filter_ms,
        ),
        unresolved_facets=resolution.unresolved,
    )


async def search_articles(
    site_config: SiteConfig,
    query: str,
    *,
    k: int = DEFAULT_K,
    types: list[str] | None = None,
    formats: list[str] | None = None,
    facets: list[str] | None = None,
) -> SearchResponse:
    return await run_sync(
        lambda: _search(
            site_config.db_ref,
            query,
            k=k,
            types=types or [],
            formats=formats or [],
            facets=facets or [],
        )
    )

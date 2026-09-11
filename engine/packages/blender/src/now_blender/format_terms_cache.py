"""Tiny in-process TTL cache for the platform vocabulary's `format` facet
term ids (`now_platform.engine.terms`, facet key `format` -- an 11-row,
rarely-changed set today, F92's cross-DB constraint: `engine.entity_terms
.term_id` in a CITY database has no FK to `now_platform.engine.terms`, so
"which term ids belong to the format facet" must be resolved
application-side, exactly the problem `now_classifier.vocabulary.TermIndex`
already solves for the offline classifier -- this is the identical
resolution, cached, for the online ranking path.

F124/F125 (T2 decay trust gate): `now_blender.articles.fetch_article_meta`
needs this id set to LEFT JOIN `engine.entity_terms` and pick out the
format term's `(confidence, source)` -- without it, the join cannot tell a
format-facet row apart from a type/subtype/location row sharing the same
`entity_id`.

Mirrors `now_rails.relations_cache`'s shape exactly, and for the identical
reason stated there: `BlenderReranker.build()` / `RailsOrchestrator.build()`
run once per REQUEST (see `app.domain.rails.service._compute`), so an
uncached platform-DB round trip here on every request would add real,
measurable latency on top of the join itself -- this ticket's own
performance bar forbids that. Kept as its own module (not folded into
`relations_cache.py`, which lives in `now_rails` and caches a CITY-DB
table) because this cache is keyed off the PLATFORM connection, shared by
every site/city, and consumed by `now_blender.platform.load_site_ranking_config`
itself -- `now_blender` has no dependency on `now_rails`, and must not
gain one just to reuse a five-line cache.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

TTL_SECONDS = 300.0  # 5 minutes -- same judgment call as now_rails.relations_cache

_FORMAT_TERM_IDS_SQL = text(
    """
    SELECT t.id::text AS term_id
      FROM engine.terms t
      JOIN engine.facets f ON f.id = t.facet_id
     WHERE f.key = 'format'
    """
)


@dataclass
class _CacheEntry:
    term_ids: frozenset[str]
    loaded_at: float


_cache: dict[str, _CacheEntry] = {}


def _load_format_term_ids(platform_conn: Connection) -> frozenset[str]:
    rows = platform_conn.execute(_FORMAT_TERM_IDS_SQL).scalars().all()
    return frozenset(str(r) for r in rows)


def load_format_term_ids_cached(
    platform_conn: Connection, *, cache_key: str, ttl_seconds: float = TTL_SECONDS
) -> frozenset[str]:
    """Empty `frozenset` (never raises) if the platform DB has no `format`
    facet rows yet -- disclosed to the caller via `SiteRankingConfig
    .format_term_ids_source` (see `platform.py`), not hidden: an empty
    result means the T2 trust gate's LEFT JOIN matches nothing, so every
    classified format value fails closed (unknown confidence/source) until
    the vocabulary is seeded."""
    now = time.monotonic()
    entry = _cache.get(cache_key)
    if entry is not None and (now - entry.loaded_at) < ttl_seconds:
        return entry.term_ids
    term_ids = _load_format_term_ids(platform_conn)
    _cache[cache_key] = _CacheEntry(term_ids=term_ids, loaded_at=now)
    return term_ids


def clear_cache() -> None:
    """Test/tooling seam -- not called by production code."""
    _cache.clear()

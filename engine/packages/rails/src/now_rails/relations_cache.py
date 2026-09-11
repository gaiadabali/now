"""Tiny in-process TTL cache for `engine.type_relations` -- an 8-9 row
table (ARCHITECTURE.md Sec.4's L1 taxonomy) that changes only on a rare,
deliberate edit (a site overriding its competitor matrix), yet
`RailsOrchestrator.build` would otherwise re-query it on every single
request. One round trip saved per request on this dev box is ~12-15ms
(measured -- see the package README's timing section) against a table
that is, for all practical purposes, static.

Mirrors this codebase's existing precedent for exactly this shape --
`app/infra/db/registry.SiteRegistryCache` TTL-caches `engine.sites` in the
API app for the identical reason (a small, rarely-changed table, hot on
every request). Kept process-local and cheap: no cross-process
invalidation, so a live edit to `type_relations` takes up to `TTL_SECONDS`
to be picked up by a given process -- an explicit, disclosed staleness
window, not a correctness promise this module doesn't keep.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from now_filters.type_relations import TypeRelation, load_type_relations
from sqlalchemy.engine import Connection

TTL_SECONDS = 300.0  # 5 minutes -- judgment call, no product requirement to tune this against


@dataclass
class _CacheEntry:
    relations: dict[str, TypeRelation]
    loaded_at: float


_cache: dict[str, _CacheEntry] = {}


def load_type_relations_cached(conn: Connection, *, cache_key: str, ttl_seconds: float = TTL_SECONDS) -> dict[str, TypeRelation]:
    now = time.monotonic()
    entry = _cache.get(cache_key)
    if entry is not None and (now - entry.loaded_at) < ttl_seconds:
        return entry.relations
    relations = load_type_relations(conn)
    _cache[cache_key] = _CacheEntry(relations=relations, loaded_at=now)
    return relations


def clear_cache() -> None:
    """Test/tooling seam -- not called by production code."""
    _cache.clear()

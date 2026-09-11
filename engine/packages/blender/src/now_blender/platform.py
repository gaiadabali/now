"""Reads the platform DB's `sites.ranking_weights` bundle (`'blend'` +
`'decay'`) in one round trip and bundles them with the `slug` into
`SiteRankingConfig` -- the one object `reranker.py` needs per request.
Kept separate from `weights.py`/`decay.py` (which stay DB-agnostic and
unit-testable on plain dicts) so those two modules have no Connection
dependency of their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_blender.decay import DecayPolicy, FALLBACK_DECAY_POLICY
from now_blender.format_terms_cache import load_format_term_ids_cached
from now_blender.weights import BlendWeights, DEFAULT_WEIGHTS, ResolvedWeights, load_blend_weights

DECAY_SOURCE = "sites.ranking_weights['decay']"
DECAY_FALLBACK_SOURCE = "now-blender package fallback (site row or 'decay' key missing)"

# F124/F125 (T2 decay trust gate): where `SiteRankingConfig.format_term_ids`
# came from, disclosed the same way `weights_source`/`decay_source` already
# are -- an empty/fallback set is a legible, reported state, never a silent
# "the gate happens to withhold everything" surprise.
FORMAT_TERM_IDS_SOURCE = "platform.engine.terms (facet='format')"
FORMAT_TERM_IDS_EMPTY_SOURCE = "platform.engine.terms (facet='format') returned zero rows"
FORMAT_TERM_IDS_FALLBACK_SOURCE = "now-blender package fallback (no platform connection given -- T2 gate fails closed for every classified format)"


@dataclass(frozen=True)
class SiteRankingConfig:
    site_slug: str
    weights: BlendWeights
    weights_source: str
    decay: DecayPolicy
    decay_source: str
    # F124/F125 (T2): the platform vocabulary's `format` facet term ids,
    # resolved once (TTL-cached, see format_terms_cache.py) and threaded
    # into `now_blender.articles.fetch_article_meta`'s LEFT JOIN so it can
    # tell a format-facet `engine.entity_terms` row apart from a
    # type/subtype/location row sharing the same `entity_id`.
    format_term_ids: frozenset[str] = frozenset()
    format_term_ids_source: str = FORMAT_TERM_IDS_FALLBACK_SOURCE


def load_site_ranking_config(platform_conn: Connection, site_slug: str) -> SiteRankingConfig:
    resolved: ResolvedWeights = load_blend_weights(platform_conn, site_slug)

    row = platform_conn.execute(
        text("SELECT ranking_weights FROM engine.sites WHERE slug = :slug"),
        {"slug": site_slug},
    ).first()
    ranking_weights = (row[0] if row is not None else None) or {}
    decay_dict = ranking_weights.get("decay")
    if decay_dict:
        decay = DecayPolicy.from_dict(decay_dict, source=DECAY_SOURCE)
        decay_source = DECAY_SOURCE
    else:
        decay = FALLBACK_DECAY_POLICY
        decay_source = DECAY_FALLBACK_SOURCE

    cache_key = platform_conn.engine.url.database or "default"
    format_term_ids = load_format_term_ids_cached(platform_conn, cache_key=cache_key)
    format_term_ids_source = FORMAT_TERM_IDS_SOURCE if format_term_ids else FORMAT_TERM_IDS_EMPTY_SOURCE

    return SiteRankingConfig(
        site_slug=site_slug,
        weights=resolved.weights,
        weights_source=resolved.source,
        decay=decay,
        decay_source=decay_source,
        format_term_ids=format_term_ids,
        format_term_ids_source=format_term_ids_source,
    )


# A config with pure package defaults, for callers with no platform DB
# connection at hand (unit tests, or a caller happy to accept "not
# per-site-tuned" -- never used silently in `reranker.py`'s DB-backed
# `.build()` path, only exposed for tests/tools that want it explicitly).
# `format_term_ids` is deliberately empty here (see
# FORMAT_TERM_IDS_FALLBACK_SOURCE): with no platform connection, the T2
# trust gate cannot resolve which `entity_terms` row is the format one, so
# it fails closed -- consistent with this whole ticket's "unknown is not
# trusted" stance, not a special case for the no-DB path.
DEFAULT_SITE_RANKING_CONFIG = SiteRankingConfig(
    site_slug="(none)",
    weights=DEFAULT_WEIGHTS,
    weights_source="now-blender package default (no platform connection given)",
    decay=FALLBACK_DECAY_POLICY,
    decay_source="now-blender package fallback (no platform connection given)",
    format_term_ids=frozenset(),
    format_term_ids_source=FORMAT_TERM_IDS_FALLBACK_SOURCE,
)

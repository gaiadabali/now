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
from now_blender.weights import BlendWeights, DEFAULT_WEIGHTS, ResolvedWeights, load_blend_weights

DECAY_SOURCE = "sites.ranking_weights['decay']"
DECAY_FALLBACK_SOURCE = "now-blender package fallback (site row or 'decay' key missing)"


@dataclass(frozen=True)
class SiteRankingConfig:
    site_slug: str
    weights: BlendWeights
    weights_source: str
    decay: DecayPolicy
    decay_source: str


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

    return SiteRankingConfig(
        site_slug=site_slug,
        weights=resolved.weights,
        weights_source=resolved.source,
        decay=decay,
        decay_source=decay_source,
    )


# A config with pure package defaults, for callers with no platform DB
# connection at hand (unit tests, or a caller happy to accept "not
# per-site-tuned" -- never used silently in `reranker.py`'s DB-backed
# `.build()` path, only exposed for tests/tools that want it explicitly).
DEFAULT_SITE_RANKING_CONFIG = SiteRankingConfig(
    site_slug="(none)",
    weights=DEFAULT_WEIGHTS,
    weights_source="now-blender package default (no platform connection given)",
    decay=FALLBACK_DECAY_POLICY,
    decay_source="now-blender package fallback (no platform connection given)",
)

"""Reads/writes the §7 blend weights from `now_platform.engine.sites.
ranking_weights['blend']` -- the sibling key to `['decay']`, which
`now-db`'s `site:create`/`site:migrate` already seeds (see
`engine/packages/db/src/now_db/provisioning.py`'s `_seed_site_decay_defaults`
and `engine/packages/taxonomy/seed/format_decay.json`). This module does
exactly the same thing for `['blend']`, deliberately mirroring that
function's shape (an idempotent `UPDATE ... WHERE NOT jsonb_exists(...)`)
so per-site tuning, once made, is never clobbered by a re-seed -- this is
the acceptance-criterion proof that "weights are editable without
deploy": editing the `blend` key in `sites.ranking_weights` on a live
platform DB changes the next request's ranking with no code change and
no restart, because `load_blend_weights` below reads it fresh on every
call.

**Why this package owns its own reader instead of `now_config.SiteConfig`
or `now_db.sites_registry.SiteRow`**: both exist and both read `sites`,
but neither is a fit here. `now_config.SiteConfigLoader` is async
(`AsyncConnection`) and this whole engine/packages/{search,filters,
quality,embeddings} stack -- and now this package -- is sync
(`sqlalchemy.engine.Connection`); mixing an async loader into a sync
call path means an event loop for one query, which is exactly the kind
of impedance mismatch `now_search.connections`/`now_filters.connections`
avoid by each reading `sites`/`type_relations` directly instead. And
`now_db.sites_registry.SiteRow` deliberately does not carry
`ranking_weights` at all (documented in that module: "a full ORM mapping
would be more surface area than the job requires" -- for `site:create`'s
registry upsert, which never touches ranking weights). Three different,
narrow readers of the same table for three different needs is already
this repo's own pattern -- not a new one.

## Weight defaults and why

Six named terms in §7's formula, weighted to sum to 1.0 (interpretable
as "how much of the ranking decision this term is worth when every term
is available" -- see `compute_blend`'s renormalization for what happens
when a term genuinely isn't, which today is most of them: no
covisitation traffic yet, no geo context in plain keyword search, no
partnerships/promo inventory built (E4)):

| term | weight | why |
|---|---|---|
| w_sem   | 0.35 | Semantic match to query/seed intent is the dominant signal for a magazine search/rail product -- nothing else here can compensate for "this isn't what they asked for". |
| w_qual  | 0.20 | Editorial quality is explicitly a first-class filter *and* ranking signal in §7/§8.A (the quality floor is a hard cut; this is the graded signal above that floor) -- now-quality's E2.6 score is real data for all 4,772 articles today, unlike covis/geo/promo. |
| w_cf    | 0.15 | Cross-type covisitation is named right after semantic in §7's formula -- once E7.3 populates `engine.covisitation` (~50k sessions), behavioural co-occurrence should out-predict content similarity for "what to show next", but it is 0 rows today (verified), so this weight currently contributes nothing to any real score. |
| w_fresh | 0.15 | Freshness matters (48% of the archive is 2019) but must not dominate, or evergreen guides -- weighted 0 decay by design -- would still be crowded out by any residual scoring noise if this term were large. Kept modest, matching its role as a corrective rather than the primary signal. |
| w_geo   | 0.10 | Proximity is Row 2's whole reason to exist (§7: "within radius (hard)" is already a *hard* filter there, so this soft term mostly matters for Row 1/Row 3 and general search, where it is usually unavailable -- see below). |
| w_promo | 0.05 | Deliberately the smallest: §11 says a promo boost must stay "capped within a relevance floor" -- a small weight is the mechanism that keeps a paid slot from being able to outrank genuine relevance no matter how it's tuned, without needing a separate cap parameter. |

Sum = 1.00, which is a convenience for reading the number (a
candidate with every term available and maxed scores ~1.0), not a
correctness requirement -- `compute_blend` renormalizes over whichever
terms are actually available for a given candidate, so unavailable
terms never silently deflate every candidate's score by the same
constant (see that module's docstring for why this does not change
ranking ORDER when a term is uniformly unavailable, which is the case
for w_cf/w_geo/w_promo on every real query today).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields

from sqlalchemy import text
from sqlalchemy.engine import Connection

BLEND_KEY = "blend"

DEFAULT_WEIGHTS_SOURCE = "now-blender package default (sites.ranking_weights['blend'] absent)"
SITE_WEIGHTS_SOURCE = "sites.ranking_weights['blend']"


@dataclass(frozen=True)
class BlendWeights:
    """One term per §7 formula component, excluding diversity_penalty
    (that is MMR's own `(1-lambda)*max_sim` term -- see `mmr.py`'s
    docstring for the F39 reconciliation of why this is not a seventh
    weight here)."""

    w_sem: float = 0.35
    w_cf: float = 0.15
    w_fresh: float = 0.15
    w_qual: float = 0.20
    w_geo: float = 0.10
    w_promo: float = 0.05

    def as_dict(self) -> dict[str, float]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "BlendWeights":
        known = {f.name for f in fields(cls)}
        filtered = {k: float(v) for k, v in data.items() if k in known}
        return cls(**filtered)


DEFAULT_WEIGHTS = BlendWeights()


@dataclass(frozen=True)
class ResolvedWeights:
    """`BlendWeights` plus where they came from -- the Inspector/hand-check
    output should always be able to say "these are the live
    sites.ranking_weights" vs. "the site row/key was missing, this is our
    packaged default", never blur the two."""

    weights: BlendWeights
    source: str
    site_slug: str | None


def load_blend_weights(platform_conn: Connection, site_slug: str) -> ResolvedWeights:
    """Reads `ranking_weights['blend']` for `site_slug` from the platform
    DB, live, on every call -- no caching, no process-start snapshot --
    so an edit to the row takes effect on the very next request. Falls
    back to `DEFAULT_WEIGHTS` (clearly labelled, never silently) if the
    site row does not exist or the `blend` key has not been seeded yet."""
    row = platform_conn.execute(
        text("SELECT ranking_weights FROM engine.sites WHERE slug = :slug"),
        {"slug": site_slug},
    ).first()
    if row is None:
        return ResolvedWeights(weights=DEFAULT_WEIGHTS, source=f"{DEFAULT_WEIGHTS_SOURCE} (site {site_slug!r} not found)", site_slug=site_slug)
    ranking_weights = row[0] or {}
    blend = ranking_weights.get(BLEND_KEY)
    if not blend:
        return ResolvedWeights(weights=DEFAULT_WEIGHTS, source=DEFAULT_WEIGHTS_SOURCE, site_slug=site_slug)
    return ResolvedWeights(weights=BlendWeights.from_dict(blend), source=SITE_WEIGHTS_SOURCE, site_slug=site_slug)


_SET_BLEND_DEFAULTS = text(
    """
    UPDATE engine.sites
       SET ranking_weights = ranking_weights || jsonb_build_object('blend', CAST(:blend AS jsonb)),
           updated_at = now()
     WHERE slug = :slug
       AND NOT jsonb_exists(ranking_weights, 'blend')
    RETURNING slug
    """
)


def seed_default_blend_weights(
    platform_conn: Connection, site_slug: str, weights: BlendWeights = DEFAULT_WEIGHTS
) -> bool:
    """Writes this package's default weights into `ranking_weights['blend']`
    for one site, unless that key already exists -- same "written once,
    never overwritten, per-site tuning survives" contract as
    `now_db.provisioning._seed_site_decay_defaults`. Returns True if
    written, False if the key was already present (a no-op, not an
    error -- callable repeatedly, e.g. from `site:create`-equivalent
    tooling, without disturbing a site that has already been tuned)."""
    row = platform_conn.execute(
        _SET_BLEND_DEFAULTS, {"slug": site_slug, "blend": json.dumps(weights.as_dict(), sort_keys=True)}
    ).first()
    return row is not None

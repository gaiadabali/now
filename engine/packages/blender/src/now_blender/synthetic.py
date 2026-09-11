"""Synthetic `format` overlay for exercising type-aware freshness decay
against real articles (F50: `public.articles.format` is NULL for all
4,772 rows -- E2.1 classification has not run). Same problem `now_filters
.synthetic` solves for `primary_type`/competitor exclusion, solved the
same well-known way (a deterministic hash of the entity id into a fixed
pool -- same technique `now_eval.datasets.type_labels` and
`now_filters.synthetic.deterministic_type` each independently apply, not
imported from either: this package does not depend on `now-eval`, and
`now_filters.synthetic.deterministic_type`'s pool is the 6 *venue* L1
types, not the 11 *format* terms this module needs, so it is not a fit to
import even though it lives in a dependency this package already has).

**Never silent.** Every call site in this package that can use a
synthetic overlay takes an explicit `synthetic_format_overlay: bool`
parameter defaulting to `False`; the production default path leaves
`format=None` and lets `decay.freshness_component` honestly return `None`
("not classified yet"), exactly matching real data. Overlay output is
also never treated as if it were the number of record for the eval
comparison in `README.md`'s "both nDCG numbers" section -- it exists so
`tests/test_decay.py` and the `now-blender handcheck --synthetic-formats`
CLI flag can prove the *mechanism* (evergreen formats score 1.0 no matter
how old; news/event decay fast; review/listing decay slowly) against
something with format variety, which no real row has today.
"""

from __future__ import annotations

import hashlib

# The 11 §4 format terms (10 published in format_decay.json's "formats"
# object plus "opinion", a proposed format already present in the seeded
# decay policy -- see decay.py's FALLBACK_DECAY_POLICY_DICT).
FORMAT_POOL: tuple[str, ...] = (
    "news",
    "event",
    "offer",
    "review",
    "listing",
    "guide",
    "feature",
    "heritage",
    "people",
    "city-guide",
    "opinion",
)


def deterministic_format(entity_id: int, *, seed: str = "now-blender-synthetic-format-v1") -> str:
    """Same id -> same format every run (reproducible tests/hand-checks),
    without the lockstep-cycling bias a plain `id % len(pool)` would
    introduce for consecutively-loaded ids."""
    digest = hashlib.sha256(f"{seed}:{entity_id}".encode()).hexdigest()
    idx = int(digest[:8], 16) % len(FORMAT_POOL)
    return FORMAT_POOL[idx]

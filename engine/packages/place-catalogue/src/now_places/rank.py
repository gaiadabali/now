"""P1.1 -- the per-city evidence score and queue order.

Sec.9.1: "Ranking for the queue: 3 x featured mentions + article count +
2 x (linked to an org with a partnership) + recency of the newest mention,
computed per city into a materialised score."

The plan names the terms but not the scale of "recency". It is defined
here as a value in [0, 1]: 1 for a mention published today, falling
linearly to 0 at five years old. Kept small on purpose -- the counts should
order the queue and recency should only break near-ties between places
with the same evidence. A place with no dated mention scores 0 on it.

The desk (engine/apps/web/src/lib/placeDesk.ts) computes the same score in
SQL for its live queue; `tests/test_rank.py` and the web test pin both to
the same worked examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from now_places.db import PlaceEvidence

RECENCY_HORIZON_DAYS = 1825  # five years
TOP_N = 500


def recency(newest: datetime | None, *, now: datetime | None = None) -> float:
    if newest is None:
        return 0.0
    now = now or datetime.now(timezone.utc)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - newest).total_seconds() / 86400.0)
    return max(0.0, 1.0 - age_days / RECENCY_HORIZON_DAYS)


def evidence_score(featured: int, articles: int, partnered: bool, newest: datetime | None, *, now: datetime | None = None) -> float:
    return 3.0 * featured + float(articles) + (2.0 if partnered else 0.0) + recency(newest, now=now)


def score_place(p: PlaceEvidence, *, now: datetime | None = None) -> float:
    return evidence_score(p.featured, p.articles, p.partnered, p.newest, now=now)


def queue_order(places: list[PlaceEvidence], *, now: datetime | None = None) -> list[tuple[PlaceEvidence, float]]:
    """Highest score first; ties by featured, then articles, then the older
    (lower) id -- deterministic across runs."""
    scored = [(p, score_place(p, now=now)) for p in places]
    scored.sort(key=lambda ps: (-ps[1], -ps[0].featured, -ps[0].articles, ps[0].id))
    return scored


@dataclass
class Coverage:
    """How much of a city's featured mentions the top N covers.

    Two denominators, both reported, because they answer different
    questions. `share` divides by EVERY featured mention. `share_of_venues`
    leaves out the featured mentions sitting on junk rows ("Hotel's" is
    Jakarta's twentieth most-featured "place"): those stories featured an
    extraction fragment, no curated venue can ever cover them, and they
    return to the pool only when the mention is re-linked to a real row.
    The plan's "top 500 covers 70-76%" (Sec.1.1) was measured by featured
    count alone, before any junk was identified."""

    top_n: int
    featured_in_top: int
    featured_total: int
    featured_on_junk: int = 0

    @property
    def share(self) -> float:
        return self.featured_in_top / self.featured_total if self.featured_total else 0.0

    @property
    def share_of_venues(self) -> float:
        denom = self.featured_total - self.featured_on_junk
        return self.featured_in_top / denom if denom else 0.0


def featured_coverage(ordered: list[tuple[PlaceEvidence, float]], featured_total: int, top_n: int = TOP_N, *, featured_on_junk: int = 0) -> Coverage:
    top = ordered[:top_n]
    return Coverage(top_n=top_n, featured_in_top=sum(p.featured for p, _ in top), featured_total=featured_total, featured_on_junk=featured_on_junk)

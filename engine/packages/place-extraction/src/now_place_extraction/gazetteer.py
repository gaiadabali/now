"""Index of known places (existing `public.places` rows for one city) used
to resolve extracted candidate phrases to a real place_id before ever
considering creating a new place.

Exact-name and fuzzy lookup are DELIBERATELY separate tiers with
different trust levels -- see `GazetteerMatch.tier`:

  - "exact"  -- normalized full-name match. Always safe to auto-link,
    city-loading-bug notwithstanding (see README.md "Finding #1"): if an
    article's text contains the literal string "Viceroy Bali", it refers
    to that real-world venue regardless of which city's `public.places`
    row happens to hold it today.
  - "fuzzy"  -- similarity-scored match below exact. NEVER auto-linked to
    an existing place by this module alone -- the caller (pipeline.py)
    must run it through the same confidence gate as a new-candidate
    merge, and Jakarta's fuzzy tier additionally carries a flag noting
    the known contamination (README.md Finding #1) so a reviewer sees
    why matching against "Jakarta's" 177 places needs extra scrutiny.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from now_place_extraction.match import similarity
from now_place_extraction.normalize import blocking_key, normalize_full


@dataclass(frozen=True)
class KnownPlace:
    id: int
    name: str
    slug: str
    org_id: str | None
    status: str


@dataclass(frozen=True)
class GazetteerMatch:
    place: KnownPlace
    tier: str  # "exact" | "fuzzy"
    score: float


class Gazetteer:
    def __init__(self, places: list[KnownPlace]):
        self._by_exact: dict[str, KnownPlace] = {}
        self._by_block: dict[str, list[KnownPlace]] = defaultdict(list)
        for p in places:
            norm = normalize_full(p.name)
            if norm and norm not in self._by_exact:
                self._by_exact[norm] = p
            self._by_block[blocking_key(p.name)].append(p)

    def lookup(self, candidate_name: str, *, fuzzy_floor: float = 0.75) -> GazetteerMatch | None:
        norm = normalize_full(candidate_name)
        if norm in self._by_exact:
            return GazetteerMatch(place=self._by_exact[norm], tier="exact", score=1.0)

        block = blocking_key(candidate_name)
        pool = self._by_block.get(block, [])
        best: GazetteerMatch | None = None
        for p in pool:
            result = similarity(candidate_name, p.name)
            if result.score >= fuzzy_floor and (best is None or result.score > best.score):
                best = GazetteerMatch(place=p, tier="fuzzy", score=result.score)
        return best

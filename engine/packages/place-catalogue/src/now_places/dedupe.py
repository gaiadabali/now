"""P1.2 -- duplicate detection within one city's `places`.

Uses the extraction package's own scorer and thresholds rather than a
second opinion: `now_place_extraction.match.similarity` and
`now_place_extraction.dedup.AUTO_MERGE_THRESHOLD` (0.85) /
`REVIEW_FLOOR` (0.55), blocked by `normalize.blocking_key` exactly as the
extractor blocks its own candidates.

  * score >= 0.85 and no guard objects -> a MERGE (applied only with
    --apply, one transaction each, see merge.py);
  * 0.55 <= score < 0.85, or >= 0.85 with a guard objecting -> QUEUED for
    an editor, never merged by this package;
  * below 0.55 -> unrelated, not reported.

Guards are the cases where a high string score is not enough evidence on
its own, because the cost of a wrong merge (Sec.12 P1.2: "a bad merge
silently corrupts mentions archive-wide") is far higher than a queued pair:
an area name on either side, an outlet "at" a venue, two different kinds
of venue (a hotel and its spa share a name), both rows already
editor-approved, two different Google place ids, two different orgs, two
different legacy (WordPress venue) records, or two different region
signals.

Junk-shaped rows (junk.py's high-precision tier) are left out: "Hotel's"
should become junk, not be merged into a hotel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from now_place_extraction.dedup import AUTO_MERGE_THRESHOLD, REVIEW_FLOOR
from now_place_extraction.match import similarity
from now_place_extraction.extract import is_non_venue_phrase
from now_place_extraction.normalize import blocking_key, normalize_full

from now_places.db import PlaceEvidence
from now_places.junk import classify
from now_places.region import region_verdict

_SOURCE_PRIORITY = {"editor": 3, "partner": 3, "legacy_venue": 2, "extracted": 1}


@dataclass
class MergeOp:
    loser: PlaceEvidence
    survivor: PlaceEvidence
    score: float


@dataclass
class QueuedPair:
    a: PlaceEvidence
    b: PlaceEvidence
    score: float
    why: str  # "mid-band" or the guard that stopped an auto-merge


@dataclass
class DedupePlan:
    site: str
    candidates: int
    blocks_compared: int
    pairs_scored: int
    merges: list[MergeOp] = field(default_factory=list)
    queued: list[QueuedPair] = field(default_factory=list)


# What kind of venue a name says it is. A hotel and its spa, restaurant or
# beach club share the hotel's name ("Spa Alila Seminyak" / "Alila
# Seminyak Resort") and score as duplicates, but they are different
# places -- and different TYPES, which competitor exclusion depends on
# (a wellness story's featured spa must not become a stay).
_KIND_WORDS = {
    "stay": {"hotel", "hotels", "resort", "resorts", "villa", "villas", "suites", "inn", "hostel", "residence", "residences", "lodge"},
    "eat": {"restaurant", "restaurants", "cafe", "café", "bistro", "kitchen", "grill", "warung", "eatery", "diner", "steakhouse", "bakery", "deli", "pizzeria", "trattoria", "brasserie"},
    "drink": {"bar", "bars", "lounge", "pub", "brewery", "taproom", "speakeasy", "rooftop"},
    "club": {"club", "nightclub"},
    "wellness": {"spa", "spas", "wellness", "yoga", "gym", "retreat", "clinic"},
    "shop": {"boutique", "gallery", "shop", "store", "mall", "market"},
    "sight": {"temple", "museum", "park", "beach", "waterfall", "school"},
}


_DROPPABLE_KINDS = {"stay", "club"}


def _kinds(name: str) -> set[str]:
    words = set(normalize_full(name).split())
    return {kind for kind, vocab in _KIND_WORDS.items() if words & vocab}


def _guard(a: PlaceEvidence, b: PlaceEvidence, site: str) -> str | None:
    if is_non_venue_phrase(a.name) or is_non_venue_phrase(b.name):
        return "one side is an area name"
    if " at " in f" {a.name.lower()} " or " at " in f" {b.name.lower()} ":
        return "one side is an outlet at a venue"
    ka, kb = _kinds(a.name), _kinds(b.name)
    if ka and kb and not (ka & kb):
        return f"different kinds of venue ({'/'.join(sorted(ka))} vs {'/'.join(sorted(kb))})"
    # A kind word on one side only is usually a dropped suffix ("Karma
    # Kandara Resort" / "Karma Kandara") -- but only for hotels and clubs.
    # "Double Six Beach" / "Double Six Rooftop" or "Spa Alila Seminyak" /
    # "Alila Seminyak" is a different place with the same brand.
    one_sided = ka ^ kb
    if one_sided - _DROPPABLE_KINDS:
        return f"only one name says {'/'.join(sorted(one_sided - _DROPPABLE_KINDS))}"
    if a.status == "active" and b.status == "active":
        return "both rows already approved"
    if a.google_place_id and b.google_place_id and a.google_place_id != b.google_place_id:
        return "different Google place ids"
    if a.org_id and b.org_id and a.org_id != b.org_id:
        return "linked to different orgs"
    if a.legacy_wp_id and b.legacy_wp_id and a.legacy_wp_id != b.legacy_wp_id:
        return "two separate legacy venue records"
    ra = region_verdict(site, a.name, a.address, a.area_term)
    rb = region_verdict(site, b.name, b.address, b.area_term)
    if ra.region and rb.region and ra.region != rb.region:
        return "names point at different regions"
    return None


def survivor_key(p: PlaceEvidence) -> tuple:
    """Who survives a merge: an approved row, then an editor/partner/legacy
    row over an extracted one, then more evidence, then the older id."""
    return (
        1 if p.status == "active" else 0,
        _SOURCE_PRIORITY.get(p.source or "", 0),
        p.featured,
        p.articles,
        p.mentions,
        -p.id,
    )


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def plan_dedupe(site: str, places: list[PlaceEvidence]) -> DedupePlan:
    pool = [
        p for p in places
        if p.merged_into_id is None
        and p.status in {"pending_review", "active"}
        and not classify(p.name).is_junk
    ]
    by_id = {p.id: p for p in pool}
    blocks: dict[str, list[PlaceEvidence]] = defaultdict(list)
    for p in pool:
        key = blocking_key(p.name)
        if key:
            blocks[key].append(p)

    plan = DedupePlan(site=site, candidates=len(pool), blocks_compared=0, pairs_scored=0)
    uf = _UnionFind()
    auto_edges: list[tuple[int, int, float]] = []
    for group in blocks.values():
        if len(group) < 2:
            continue
        plan.blocks_compared += 1
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                res = similarity(a.name, b.name)
                plan.pairs_scored += 1
                if res.score < REVIEW_FLOOR:
                    continue
                if res.score < AUTO_MERGE_THRESHOLD:
                    plan.queued.append(QueuedPair(a, b, res.score, "mid-band"))
                    continue
                guard = _guard(a, b, site)
                if guard:
                    plan.queued.append(QueuedPair(a, b, res.score, guard))
                    continue
                uf.union(a.id, b.id)
                auto_edges.append((a.id, b.id, res.score))

    clusters: dict[int, list[int]] = defaultdict(list)
    for a_id, b_id, _ in auto_edges:
        for pid in (a_id, b_id):
            root = uf.find(pid)
            if pid not in clusters[root]:
                clusters[root].append(pid)

    for members in clusters.values():
        survivor = max((by_id[m] for m in members), key=survivor_key)
        for m in members:
            if m == survivor.id:
                continue
            loser = by_id[m]
            # Union-find is transitive; similarity is not. Every loser must
            # itself clear the gate against the survivor, or it is queued.
            res = similarity(loser.name, survivor.name)
            guard = _guard(loser, survivor, site)
            if loser.status == "active":
                guard = guard or "the duplicate is already approved"
            if res.score >= AUTO_MERGE_THRESHOLD and guard is None:
                plan.merges.append(MergeOp(loser, survivor, res.score))
            else:
                plan.queued.append(QueuedPair(loser, survivor, res.score, guard or "only similar through a third row"))

    plan.merges.sort(key=lambda op: (op.survivor.id, op.loser.id))
    plan.queued.sort(key=lambda q: -q.score)
    return plan

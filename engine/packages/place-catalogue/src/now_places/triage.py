"""P1.1 -- triage: junk proposals, out-of-region flags, and the queue.

Pure over `PlaceEvidence` rows (no database access here) so the whole
decision can be tested without Postgres.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from now_places.db import PlaceEvidence
from now_places.junk import classify
from now_places.rank import Coverage, featured_coverage, queue_order
from now_places.region import region_verdict

# Rows in these states are already decided and take no part in triage.
_DECIDED_STATUSES = {"junk", "closed"}


@dataclass
class TriageResult:
    site: str
    total_rows: int
    already_decided: int
    merged: int
    junk: list[PlaceEvidence] = field(default_factory=list)  # proposed status=junk (high-precision tier)
    junk_skipped_not_pending: list[PlaceEvidence] = field(default_factory=list)  # junk-shaped but active: editor's call
    suspect: list[PlaceEvidence] = field(default_factory=list)  # doubtful shape: editor decides
    out_of_region: list[PlaceEvidence] = field(default_factory=list)  # kept, flagged, never moved
    queue: list[tuple[PlaceEvidence, float]] = field(default_factory=list)  # rank order, junk excluded
    coverage: Coverage | None = None
    coverage_all_rows: Coverage | None = None  # the plan's Sec.1.1 baseline (no junk removed)
    partnership_term: str = "read"  # "read" | "unavailable"


def triage(site: str, places: list[PlaceEvidence], featured_total: int, *, partnered: tuple[set[str], set[str]] | None = None, top_n: int = 500) -> TriageResult:
    result = TriageResult(site=site, total_rows=len(places), already_decided=0, merged=0)
    if partnered is None:
        result.partnership_term = "unavailable"
    else:
        place_ids, org_ids = partnered
        for p in places:
            p.partnered = str(p.id) in place_ids or (p.org_id is not None and p.org_id in org_ids)

    candidates: list[PlaceEvidence] = []
    for p in places:
        if p.merged_into_id is not None:
            result.merged += 1
            continue
        if p.status in _DECIDED_STATUSES:
            result.already_decided += 1
            continue
        verdict = classify(p.name)
        region = region_verdict(site, p.name, p.address, p.area_term)
        p.flags = {
            "tier": verdict.tier,
            "reason": verdict.reason,
            "out_of_region": region.out_of_region,
            "region": region.region,
            "region_match": region.matched,
        }
        if verdict.is_junk:
            if p.status == "pending_review":
                result.junk.append(p)
            else:
                result.junk_skipped_not_pending.append(p)
                candidates.append(p)
            continue
        if verdict.suspect:
            result.suspect.append(p)
        if region.out_of_region:
            result.out_of_region.append(p)
        candidates.append(p)

    result.queue = queue_order(candidates)
    on_junk = sum(p.featured for p in result.junk) + sum(p.featured for p in result.junk_skipped_not_pending)
    result.coverage = featured_coverage(result.queue, featured_total, top_n, featured_on_junk=on_junk)
    result.coverage_all_rows = featured_coverage(queue_order([p for p in places if p.merged_into_id is None]), featured_total, top_n)
    return result

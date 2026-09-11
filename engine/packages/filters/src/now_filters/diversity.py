"""Diversity, post-filter (ARCHITECTURE.md Sec.8.D):

    MMR lambda ~= 0.7 . max 1 per org . max 2 per area . max 2 per format . max 1 paid per rail

"`max 1 per org` matters: marriott.com appears 63x in the archive." Caps
are enforced INSIDE the greedy MMR loop (not as a separate post-hoc
pass over the MMR-ordered list) so that a capped-out candidate never
consumes a slot -- the next-best remaining candidate fills it instead,
which is the only way to guarantee `k` results are returned whenever the
underlying candidate pool actually has `k` cap-satisfying items, rather
than under-filling because the naive top-k happened to violate a cap.

MMR needs a similarity measure between two candidates. This package does
not own embeddings (`engine/packages/embeddings/` is out of scope, and
Row 3's semantic kNN belongs to E3.5-3.7) so `similarity_fn` is an
injected callable -- callers with real vectors pass a cosine-similarity
closure over `engine.embeddings`; `default_facet_similarity` below is a
zero-dependency fallback (shared type/subtype/area/price_band overlap)
used by this package's own tests and available for a caller with no
embedding access yet.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from now_filters.models import Candidate

DEFAULT_LAMBDA = 0.7
MAX_PER_ORG = 1
MAX_PER_AREA = 2
MAX_PER_FORMAT = 2
MAX_PAID_PER_RAIL = 1

SimilarityFn = Callable[[Candidate, Candidate], float]


def default_facet_similarity(a: Candidate, b: Candidate) -> float:
    """Zero-dependency stand-in: fraction of {type, subtype, area_term,
    price_band} that match between two candidates. Real deployments
    should inject a cosine-similarity closure over `engine.embeddings`
    instead -- this exists so MMR is exercisable and testable without an
    embeddings dependency, not as a recommended production similarity
    measure."""
    fields = (
        (a.type, b.type),
        (a.subtype, b.subtype),
        (a.area_term, b.area_term),
        (a.price_band, b.price_band),
    )
    comparable = [(x, y) for x, y in fields if x is not None and y is not None]
    if not comparable:
        return 0.0
    matches = sum(1 for x, y in comparable if x == y)
    return matches / len(comparable)


@dataclass(frozen=True)
class DiversityCaps:
    max_per_org: int = MAX_PER_ORG
    max_per_area: int = MAX_PER_AREA
    max_per_format: int = MAX_PER_FORMAT
    max_paid_per_rail: int = MAX_PAID_PER_RAIL


def _violates_caps(candidate: Candidate, counts: dict[str, dict[object, int]], caps: DiversityCaps) -> bool:
    if candidate.org_id is not None and counts["org"].get(candidate.org_id, 0) >= caps.max_per_org:
        return True
    if candidate.area_term is not None and counts["area"].get(candidate.area_term, 0) >= caps.max_per_area:
        return True
    if candidate.format is not None and counts["format"].get(candidate.format, 0) >= caps.max_per_format:
        return True
    if candidate.is_paid and counts["paid"].get("_", 0) >= caps.max_paid_per_rail:
        return True
    return False


def _record(candidate: Candidate, counts: dict[str, dict[object, int]]) -> None:
    if candidate.org_id is not None:
        counts["org"][candidate.org_id] = counts["org"].get(candidate.org_id, 0) + 1
    if candidate.area_term is not None:
        counts["area"][candidate.area_term] = counts["area"].get(candidate.area_term, 0) + 1
    if candidate.format is not None:
        counts["format"][candidate.format] = counts["format"].get(candidate.format, 0) + 1
    if candidate.is_paid:
        counts["paid"]["_"] = counts["paid"].get("_", 0) + 1


def diversify(
    candidates: list[Candidate],
    relevance: dict[tuple[str, int], float],
    *,
    k: int,
    similarity_fn: SimilarityFn = default_facet_similarity,
    lambda_: float = DEFAULT_LAMBDA,
    caps: DiversityCaps | None = None,
) -> list[Candidate]:
    """Standard greedy MMR:  argmax_i  [ lambda * relevance(i) - (1-lambda)
    * max_{j in selected} sim(i, j) ]  -- re-picked at every step among
    candidates not yet selected and not currently cap-violating. A
    candidate that is cap-violating *right now* is skipped for this slot
    but stays eligible for a later slot if the cap-holder set changes...
    it never can for a monotonically-increasing count, so in practice a
    capped-out candidate is simply never selected once its cap is hit --
    documented rather than special-cased, since re-eligibility cannot
    occur with these particular caps (counts only increase)."""
    caps = caps or DiversityCaps()
    pool = list(candidates)
    selected: list[Candidate] = []
    counts: dict[str, dict[object, int]] = {"org": {}, "area": {}, "format": {}, "paid": {}}

    while pool and len(selected) < k:
        best_idx: int | None = None
        best_score = float("-inf")
        for idx, cand in enumerate(pool):
            if _violates_caps(cand, counts, caps):
                continue
            rel = relevance.get(cand.key, 0.0)
            if selected:
                max_sim = max(similarity_fn(cand, s) for s in selected)
            else:
                max_sim = 0.0
            score = lambda_ * rel - (1 - lambda_) * max_sim
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            break  # every remaining candidate violates a cap -- stop, do not silently ignore caps
        chosen = pool.pop(best_idx)
        selected.append(chosen)
        _record(chosen, counts)

    return selected

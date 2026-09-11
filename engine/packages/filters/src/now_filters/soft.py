"""Soft / personalization filters (ARCHITECTURE.md Sec.8.C):

    down-weight:  low facet affinity . seen-not-clicked . over-represented area
    hard filter:  explicit thumbs-down . user-muted facets   <- only user-chosen

"Personalization never hard-filters. The reader may filter themselves;
the algorithm may not." That sentence is enforced here by construction,
not just by comment: `apply_personalization_hard_filters` is the ONLY
function in this module that can remove a candidate, and it accepts
exactly one input type (`ActiveFacetFilters`, from `models.py`) whose two
fields are named for the two things Sec.8.C permits -- there is no
parameter through which an affinity score or an algorithmic signal could
be threaded into a hard exclusion. Every other function in this module
returns a *multiplier*, never a boolean.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from now_filters.models import ActiveFacetFilters, Candidate

# Down-weight multipliers -- tunable, not load-bearing for correctness
# (unlike the hard filters, getting these wrong degrades ranking quality,
# it does not create a commercial/compliance failure), so kept as named
# constants rather than buried literals.
LOW_AFFINITY_MULTIPLIER = 0.7
SEEN_NOT_CLICKED_MULTIPLIER = 0.85
OVER_REPRESENTED_AREA_MULTIPLIER = 0.9
OVER_REPRESENTED_AREA_THRESHOLD = 3  # candidates already selected from the same area this rail


@dataclass(frozen=True)
class SoftSignals:
    """Caller-resolved personalization inputs (from `user_profiles.facet_affinity`,
    `engine.interactions` -- both outside this single-DB-scoped package's
    reach for the platform-side data, matching now-search's precedent)."""

    facet_affinity: dict[str, float] = field(default_factory=dict)  # e.g. "cuisine:japanese" -> 0..1
    candidate_facets: dict[tuple[str, int], frozenset[str]] = field(default_factory=dict)
    seen_not_clicked: frozenset[tuple[str, int]] = frozenset()
    low_affinity_threshold: float = 0.3


def affinity_multiplier(candidate: Candidate, signals: SoftSignals) -> float:
    facets = signals.candidate_facets.get(candidate.key, frozenset())
    if not facets:
        return 1.0  # no facet data -> no opinion, never penalize for missing data
    scores = [signals.facet_affinity.get(f) for f in facets if f in signals.facet_affinity]
    if not scores:
        return 1.0
    avg = sum(scores) / len(scores)
    return LOW_AFFINITY_MULTIPLIER if avg < signals.low_affinity_threshold else 1.0


def seen_not_clicked_multiplier(candidate: Candidate, signals: SoftSignals) -> float:
    return SEEN_NOT_CLICKED_MULTIPLIER if candidate.key in signals.seen_not_clicked else 1.0


def over_represented_area_multiplier(candidate: Candidate, area_counts_so_far: dict[str, int]) -> float:
    if not candidate.area_term:
        return 1.0
    count = area_counts_so_far.get(candidate.area_term, 0)
    return OVER_REPRESENTED_AREA_MULTIPLIER if count >= OVER_REPRESENTED_AREA_THRESHOLD else 1.0


def compute_soft_weight(
    candidate: Candidate,
    signals: SoftSignals,
    *,
    already_read_weight: float = 1.0,
    area_counts_so_far: dict[str, int] | None = None,
) -> float:
    """Combined down-weight multiplier -- multiplicative, so several mild
    penalties compound rather than one dominating; never exceeds 1.0 and
    never hard-excludes (always > 0)."""
    weight = already_read_weight
    weight *= affinity_multiplier(candidate, signals)
    weight *= seen_not_clicked_multiplier(candidate, signals)
    weight *= over_represented_area_multiplier(candidate, area_counts_so_far or {})
    return weight


def apply_personalization_hard_filters(
    candidates: list[Candidate], facet_filters: ActiveFacetFilters
) -> list[Candidate]:
    """The ONLY user-chosen hard exclusions Sec.8.C permits: explicit
    thumbs-down on a specific entity, and facets the user has explicitly
    muted in their own preferences. Both are opt-in reader actions, not
    algorithmic inference -- see module docstring."""
    survivors = []
    for c in candidates:
        if c.key in facet_filters.thumbs_down_ids:
            continue
        candidate_facets = facet_filters.candidate_facet_values.get(c.key, frozenset())
        if candidate_facets & facet_filters.muted_facet_values:
            continue
        survivors.append(c)
    return survivors

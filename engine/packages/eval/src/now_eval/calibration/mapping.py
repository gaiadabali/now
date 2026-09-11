"""Step 6: turn per-(city, facet, confidence-value) accuracy estimates into
(a) an evidence-based label->number recommendation and (b) a concrete
statement of what the 0.85 gate would then imply for F97's queue.

Kept deliberately simple and legible rather than a black-box optimizer:
this package's job is to hand whoever owns the taxonomy rules (per F96's own
recommendation) a clear number and the reasoning behind it, not to auto-tune
the gate. **This module never writes to `now_classifier`.** Acting on its
recommendation -- and re-running classification -- is explicitly the
follow-on step the task brief says must not race the F101 audit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .stats import TwoStageEstimate

AUTO_APPLY_AT_OR_ABOVE = 0.85  # rules.confidence_gate, unchanged by this package


@dataclass(frozen=True)
class ValueRecommendation:
    confidence_value: float       # the OLD invented number
    n_sampled: int
    accuracy_point: float | None
    accuracy_low: float | None    # Wilson 95% CI lower bound
    accuracy_high: float | None
    recommended_number: float | None   # accuracy_point, rounded -- None if unadjudicated
    crosses_gate_now: bool
    crosses_gate_after: bool | None


def combine_across_cells(estimates: dict[str, TwoStageEstimate], confidence_value: float) -> TwoStageEstimate | None:
    """Pools every (city, facet) cell that currently shares the same raw
    confidence number -- e.g. 0.95 covers both `type` and `format` in both
    cities today, all four sharing one invented number, so the corrected
    number should be evaluated the same way: one pooled estimate per
    distinct value, not four disconnected ones the gate can't actually use
    differently (the gate compares a single float)."""
    matching = [e for cell, e in estimates.items() if cell.endswith(f":{confidence_value}")]
    if not matching:
        return None
    n_sampled = sum(e.n_sampled for e in matching)
    n_agree = sum(e.n_agree for e in matching)
    n_disagree = sum(e.n_disagree for e in matching)
    n_agree_adj = sum(e.n_agree_adjudicated for e in matching)
    n_agree_adj_correct = sum(e.n_agree_adjudicated_correct for e in matching)
    n_disagree_correct = sum(e.n_disagree_adjudicated_correct_for_classifier for e in matching)
    n_total = sum(e.n_total for e in matching)
    from .stats import estimate_cell_accuracy

    return estimate_cell_accuracy(
        cell=f"pooled:{confidence_value}",
        n_total=n_total,
        n_sampled=n_sampled,
        n_agree=n_agree,
        n_disagree=n_disagree,
        n_agree_adjudicated=n_agree_adj,
        n_agree_adjudicated_correct=n_agree_adj_correct,
        n_disagree_adjudicated_correct_for_classifier=n_disagree_correct,
    )


def recommend(confidence_value: float, estimates: dict[str, TwoStageEstimate]) -> ValueRecommendation:
    import math

    pooled = combine_across_cells(estimates, confidence_value)
    crosses_now = confidence_value >= AUTO_APPLY_AT_OR_ABOVE
    if pooled is None or math.isnan(pooled.estimated_correct):
        return ValueRecommendation(
            confidence_value=confidence_value, n_sampled=pooled.n_sampled if pooled else 0,
            accuracy_point=None, accuracy_low=None, accuracy_high=None,
            recommended_number=None, crosses_gate_now=crosses_now, crosses_gate_after=None,
        )
    point = round(pooled.interval.point, 3)
    return ValueRecommendation(
        confidence_value=confidence_value, n_sampled=pooled.n_sampled,
        accuracy_point=point, accuracy_low=round(pooled.interval.low, 3), accuracy_high=round(pooled.interval.high, 3),
        recommended_number=point, crosses_gate_now=crosses_now, crosses_gate_after=point >= AUTO_APPLY_AT_OR_ABOVE,
    )


@dataclass(frozen=True)
class CoverageImpact:
    confidence_value: float
    population: int          # articles currently carrying this exact confidence value (both facets, both cities, per the frame)
    was_auto_applied: bool
    now_auto_applied: bool | None
    flips_to_review: int
    flips_to_auto_apply: int


def simulate_coverage(
    recommendations: list[ValueRecommendation],
    population_by_value: dict[float, int],
) -> list[CoverageImpact]:
    out = []
    for rec in recommendations:
        pop = population_by_value.get(rec.confidence_value, 0)
        now_auto = rec.crosses_gate_after
        flips_to_review = pop if (rec.crosses_gate_now and now_auto is False) else 0
        flips_to_auto_apply = pop if (not rec.crosses_gate_now and now_auto is True) else 0
        out.append(
            CoverageImpact(
                confidence_value=rec.confidence_value, population=pop,
                was_auto_applied=rec.crosses_gate_now, now_auto_applied=now_auto,
                flips_to_review=flips_to_review, flips_to_auto_apply=flips_to_auto_apply,
            )
        )
    return out

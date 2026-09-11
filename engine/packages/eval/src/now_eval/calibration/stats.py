"""Pure statistics: no DB, no network, no filesystem. Kept separate so it is
always unit-testable regardless of whether the `calibration` extra is
installed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WilsonInterval:
    point: float
    low: float
    high: float
    n: int

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.point:.2f} (95% CI {self.low:.2f}-{self.high:.2f}, n={self.n})"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
    """Wilson score interval for a binomial proportion -- better-behaved than
    the normal approximation at small n or p near 0/1, both of which happen
    a lot in this dataset (n as low as 12 per cell; some cells near-certain).
    """
    if n <= 0:
        return WilsonInterval(point=float("nan"), low=float("nan"), high=float("nan"), n=0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half_width = (z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / denom
    return WilsonInterval(point=p, low=max(0.0, center - half_width), high=min(1.0, center + half_width), n=n)


@dataclass(frozen=True)
class TwoStageEstimate:
    """Accuracy estimate from the two-stage design this package uses:

    1. Every disagreement (LLM proxy label != classifier proposal) in the
       cell is sent to human adjudication -- so its true-positive/false rate
       is *known exactly*, not estimated.
    2. Only a random control slice of the *agreements* (LLM and classifier
       independently landed on the same value) is adjudicated. Agreement is
       necessary but not sufficient for correctness (both could share a
       blind spot), so the control slice measures agreement's own hit rate
       rather than assuming it is 1.0, and that rate is extrapolated across
       the un-adjudicated agreements in the same cell.

    `accuracy` = (adjudicated disagreements ruled correct-for-classifier
    + estimated-correct among all agreements) / n. The variance this
    reports is a plug-in approximation (Wilson interval on the blended
    proportion, treating it as if it were a single simple sample) -- stated
    explicitly as approximate because the true two-stage variance would need
    to combine the finite-population disagreement count with the sampling
    variance of the control-agreement rate, which read as false precision
    when n is 12-30. Good enough for the order-of-magnitude judgement this
    calibration exists to support; not a substitute for a bigger sample if
    someone later needs a tighter number.
    """

    cell: str
    n_total: int                 # population size of the stratum in the DB
    n_sampled: int                # how many were drawn into the calibration sample
    n_agree: int
    n_disagree: int
    n_agree_adjudicated: int
    n_agree_adjudicated_correct: int
    n_disagree_adjudicated_correct_for_classifier: int
    estimated_correct: float      # blended estimate of #correct within n_sampled
    interval: WilsonInterval

    @property
    def agreement_rate(self) -> float:
        return self.n_agree / self.n_sampled if self.n_sampled else float("nan")

    @property
    def agreement_reliability(self) -> float | None:
        """Fraction of the adjudicated *agreement* control slice Hansel
        actually confirmed correct -- None until at least one has been
        adjudicated."""
        if self.n_agree_adjudicated == 0:
            return None
        return self.n_agree_adjudicated_correct / self.n_agree_adjudicated


def estimate_cell_accuracy(
    cell: str,
    n_total: int,
    n_sampled: int,
    n_agree: int,
    n_disagree: int,
    n_agree_adjudicated: int,
    n_agree_adjudicated_correct: int,
    n_disagree_adjudicated_correct_for_classifier: int,
) -> TwoStageEstimate:
    if n_agree_adjudicated > 0:
        agreement_reliability = n_agree_adjudicated_correct / n_agree_adjudicated
    else:
        # No control slice adjudicated yet: cannot claim agreement is
        # correct. Report a NaN-safe estimate that is explicitly marked
        # unadjudicated by the caller rather than silently assuming 1.0.
        agreement_reliability = float("nan")

    estimated_agree_correct = n_agree * agreement_reliability if n_agree_adjudicated > 0 else float("nan")
    if math.isnan(estimated_agree_correct):
        estimated_correct = float("nan")
        interval = WilsonInterval(point=float("nan"), low=float("nan"), high=float("nan"), n=n_sampled)
    else:
        estimated_correct = n_disagree_adjudicated_correct_for_classifier + estimated_agree_correct
        interval = wilson_interval(round(estimated_correct), n_sampled)

    return TwoStageEstimate(
        cell=cell,
        n_total=n_total,
        n_sampled=n_sampled,
        n_agree=n_agree,
        n_disagree=n_disagree,
        n_agree_adjudicated=n_agree_adjudicated,
        n_agree_adjudicated_correct=n_agree_adjudicated_correct,
        n_disagree_adjudicated_correct_for_classifier=n_disagree_adjudicated_correct_for_classifier,
        estimated_correct=estimated_correct,
        interval=interval,
    )

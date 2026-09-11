"""Freshness / decay display, per ARCHITECTURE.md §4 "Format -> decay
half-life":

    news, event                         14-30 days
    offer                               hard expiry at campaign.ends_at (not decay)
    review, listing                     ~18 months
    guide, feature, heritage, people,
      city-guide                        evergreen, no decay

Nothing in the codebase computes a numeric decay curve yet (`format` is
NULL on every one of the 4,772 rows -- E2.1 hasn't run). This module is
therefore two things at once, clearly separated:

1. `classify_format(format)` -- an honest lookup into the table above.
   Returns `None`/"not classified yet" when `format` is NULL, which is
   the real, current state of every article in this corpus. This is the
   part the Inspector actually trusts.
2. `illustrative_decay(days_old, half_life_days)` -- a textbook
   exponential-decay curve (`0.5 ** (days_old / half_life_days)`) used
   ONLY to give the per-result "freshness 0.22"-style number something
   to show when a half-life midpoint is known. It is explicitly labelled
   "illustrative" in every value it produces, because ARCHITECTURE.md
   does not specify a decay *function*, only half-life *ranges* -- the
   real function is E3.3's to design and tune. Do not read this as the
   blender's real freshness formula.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from now_inspector.models import FreshnessResult

# (label, midpoint used for the illustrative curve, or None = evergreen/no decay)
_HALF_LIFE_DAYS: dict[str, tuple[str, float | None]] = {
    "news": ("14-30 days", 22.0),
    "event": ("14-30 days", 22.0),
    "offer": ("hard expiry at campaign.ends_at -- not decay", None),
    "review": ("~18 months", 548.0),
    "listing": ("~18 months", 548.0),
    "guide": ("evergreen, no decay", None),
    "feature": ("evergreen, no decay", None),
    "heritage": ("evergreen, no decay", None),
    "people": ("evergreen, no decay", None),
    "city-guide": ("evergreen, no decay", None),
}


def days_old(published_at: str | None, *, now: datetime | None = None) -> float | None:
    if not published_at:
        return None
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    return max((ref - dt).total_seconds() / 86400.0, 0.0)


def illustrative_decay(age_days: float, half_life_days: float) -> float:
    """Textbook exponential decay -- see module docstring. Not the
    blender's real formula (that is E3.3's to define)."""
    if half_life_days <= 0:
        return 0.0
    return 0.5 ** (age_days / half_life_days)


def classify(format_: str | None, published_at: str | None) -> FreshnessResult:
    age = days_old(published_at)

    if format_ is None:
        return FreshnessResult(
            format=None,
            half_life_label="not classified yet",
            days_old=age,
            decay_component=None,
            note="public.articles.format is NULL for this article (E2.1 has not run over the "
            "corpus yet). ARCHITECTURE.md §4's format->half-life table cannot be applied. "
            "No freshness component can be computed -- this is the honest state, not a bug.",
        )

    entry = _HALF_LIFE_DAYS.get(format_)
    if entry is None:
        return FreshnessResult(
            format=format_,
            half_life_label="unrecognised format value",
            days_old=age,
            decay_component=None,
            note=f"format={format_!r} is not one of the §4 formats this module knows about.",
        )

    label, half_life = entry
    if half_life is None:
        return FreshnessResult(
            format=format_,
            half_life_label=label,
            days_old=age,
            decay_component=None,
            note="No decay applies to this format per §4 (evergreen, or hard-expiry-not-decay "
            "for offers).",
        )

    component = illustrative_decay(age, half_life) if age is not None else None
    return FreshnessResult(
        format=format_,
        half_life_label=label,
        days_old=age,
        decay_component=component,
        note="ILLUSTRATIVE: exponential decay curve fitted to the §4 half-life midpoint. "
        "ARCHITECTURE.md specifies a half-life range, not a decay function -- E3.3 owns the "
        "real formula. Shown here only so the freshness slot in the blend is not a blank.",
    )

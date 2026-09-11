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

from now_blender.decay import DecayPolicy, FALLBACK_DECAY_POLICY, describe_format_trust
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


def classify(
    format_: str | None,
    published_at: str | None,
    *,
    format_confidence: float | None = None,
    format_source: str | None = None,
    trust_policy: DecayPolicy = FALLBACK_DECAY_POLICY,
) -> FreshnessResult:
    """F124/F125 (T2): `withheld_reason` on every branch below is computed
    by the REAL gate (`now_blender.decay.describe_format_trust`), not
    reimplemented here -- this module's own decay CURVE stays illustrative
    (see module docstring; E3.3 owns the real formula), but the trust gate
    is real production logic and must not drift into a second, parallel
    implementation. `trust_policy` defaults to the package fallback
    (0.85, `now_blender.decay.DEFAULT_MIN_FORMAT_CONFIDENCE`); a caller with
    a live platform connection should pass the site's real, possibly-tuned
    `DecayPolicy` instead (see `service.py`)."""
    age = days_old(published_at)
    withheld = describe_format_trust(format_, format_confidence, format_source, trust_policy)

    if format_ is None:
        return FreshnessResult(
            format=None,
            half_life_label="not classified yet",
            days_old=age,
            decay_component=None,
            note="public.articles.format is NULL for this article (E2.1 has not run over the "
            "corpus yet). ARCHITECTURE.md §4's format->half-life table cannot be applied. "
            "No freshness component can be computed -- this is the honest state, not a bug.",
            withheld_reason=withheld,
        )

    entry = _HALF_LIFE_DAYS.get(format_)
    if entry is None:
        return FreshnessResult(
            format=format_,
            half_life_label="unrecognised format value",
            days_old=age,
            decay_component=None,
            note=f"format={format_!r} is not one of the §4 formats this module knows about.",
            withheld_reason=withheld,
        )

    label, half_life = entry

    # F133: an untrusted format no longer means "no freshness at all" -- the
    # real `freshness_component` falls back to the NEUTRAL default curve
    # (365d) instead of returning None, so the Inspector must show that curve
    # rather than a WITHHELD pill. This block sits ABOVE the evergreen/
    # hard-expiry branch deliberately: an untrusted `guide` does not get to
    # claim "evergreen, no decay" either -- that claim is exactly what is not
    # trusted. Getting this wrong would make the Inspector state the opposite
    # of what the blend does, which is worse than showing nothing.
    if withheld is not None:
        default_half_life = trust_policy.default.half_life_days
        return FreshnessResult(
            format=format_,
            half_life_label=f"{label} (not trusted -> neutral {default_half_life:g}d default)",
            days_old=age,
            decay_component=(
                illustrative_decay(age, default_half_life)
                if age is not None and default_half_life is not None
                else None
            ),
            note="Format-specific decay NOT trusted -- see withheld_reason. The real blend "
            "applies the neutral default curve instead of this format's own, so freshness "
            "still contributes; only the format-specific half-life is declined.",
            withheld_reason=withheld,
        )

    if half_life is None:
        return FreshnessResult(
            format=format_,
            half_life_label=label,
            days_old=age,
            decay_component=None,
            note="No decay applies to this format per §4 (evergreen, or hard-expiry-not-decay "
            "for offers).",
            withheld_reason=withheld,
        )

    # F124/F125: a format that fails the trust gate never reaches the
    # illustrative decay curve either -- the real `freshness_component`
    # returns None in exactly this case (see `now_blender.decay`), so this
    # display must not show a computed number the real blend would never
    # produce.
    component = illustrative_decay(age, half_life) if age is not None and withheld is None else None
    note = (
        "WITHHELD by the F124/F125 decay trust gate -- see withheld_reason. The real blend "
        "excludes this term and renormalises over what remains, exactly as it does for a NULL "
        "format."
        if withheld is not None
        else "ILLUSTRATIVE: exponential decay curve fitted to the §4 half-life midpoint. "
        "ARCHITECTURE.md specifies a half-life range, not a decay function -- E3.3 owns the "
        "real formula. Shown here only so the freshness slot in the blend is not a blank."
    )
    return FreshnessResult(
        format=format_,
        half_life_label=label,
        days_old=age,
        decay_component=component,
        note=note,
        withheld_reason=withheld,
    )

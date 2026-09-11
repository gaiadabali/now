"""Type-aware freshness decay (ARCHITECTURE.md §4 "Format -> decay
half-life") -- the real formula, not the Inspector's illustrative one.

    news, event                             14-30 days
    offer                                   hard expiry at campaign.ends_at (not decay)
    review, listing                         ~18 months
    guide, feature, heritage, people,
      city-guide                            evergreen, no decay

"48% of the archive is from 2019. A global decay either buries half the
library or resurfaces dead events." -- so this module refuses to have a
single half-life; it reads a per-format policy and applies exponential
decay only where the policy says decay applies at all.

## Source of truth

Per `engine/packages/taxonomy/seed/format_decay.json`'s own `"contract"`
field: "Consumers (E3.3 blender) read `SiteConfig.ranking_weights['decay']`."
`now-db`'s `site:create`/`site:migrate` has already written this policy
into `now_platform.engine.sites.ranking_weights['decay']` for every site
(jakarta/bali/test -- verified directly against the running platform DB).
This module therefore reads the **DB-seeded copy** (`load_decay_policy`
in `platform.py`), never the JSON file directly -- this package does not
depend on `now-taxonomy` and does not reach into another package's data
directory. `FALLBACK_DECAY_POLICY` below is a defensive, clearly-labelled
last resort matching the same published values, used only if a site row
or its `decay` key is somehow missing (should not happen after
`site:create`, per that command's own contract) so a decay lookup never
raises for an as-yet-unprovisioned site.

## Why exponential decay, and why the real formula (not "illustrative")

ARCHITECTURE.md specifies half-life *ranges*, not a decay function --
E3.3 (this package) is where the function is chosen.
`now_inspector.freshness.illustrative_decay` already prototypes exactly
this curve (`0.5 ** (age_days / half_life_days)`) and explicitly defers
the real formula to this ticket. Exponential decay is the standard choice
for a half-life-specified curve (half-life is only a meaningful concept
for exponential decay in the first place -- "the point where it's worth
half as much" already implies the shape), so this module keeps that
curve and promotes it from illustrative to real: it IS the freshness
term the blend consumes, weighted by `w_fresh`.

## Null-half-life formats are NOT all the same reason, but ARE the same score

`half_life_days is None` covers two different §4 cases -- `evergreen:
true` (guide/feature/heritage/people/city-guide: no decay because the
content genuinely does not go stale) and `evergreen: false` with
`hard_expiry` set (offer: no decay curve because eligibility is a hard
cutoff, not a fade -- §8.A's event/offer expiry hard filter is what
removes it from candidacy at all, upstream of this module and owned by
`now-filters`, not duplicated here). Both cases return a freshness
component of **1.0** ("fully fresh," no penalty) from this module,
because by the time a candidate reaches the blend it has already survived
whatever hard-expiry filter applies to it (or has none) -- there is
nothing left for a *soft* freshness signal to penalize either way. The
`evergreen` flag is kept in `DecayEntry` for labelling/display, not
because the score computation branches on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

FRESH_SCORE_NO_DECAY = 1.0

# Mirrors engine/packages/taxonomy/seed/format_decay.json's `"decay"`
# object exactly (same version, same values) -- used only as a fallback;
# see module docstring. Kept as a plain module-level constant (not
# re-derived from the JSON file) so this package has zero filesystem
# dependency on another package's data directory.
FALLBACK_DECAY_POLICY_DICT: dict = {
    "version": 1,
    "unit": "days",
    "default": {"half_life_days": 365, "evergreen": False},
    "formats": {
        "news": {"half_life_days": 21, "evergreen": False},
        "event": {"half_life_days": 14, "evergreen": False, "hard_expiry": "event.ends_at"},
        "offer": {"half_life_days": None, "evergreen": False, "hard_expiry": "campaign.ends_at"},
        "review": {"half_life_days": 540, "evergreen": False},
        "listing": {"half_life_days": 540, "evergreen": False},
        "guide": {"half_life_days": None, "evergreen": True},
        "feature": {"half_life_days": None, "evergreen": True},
        "heritage": {"half_life_days": None, "evergreen": True},
        "people": {"half_life_days": None, "evergreen": True},
        "city-guide": {"half_life_days": None, "evergreen": True},
        "opinion": {"half_life_days": 540, "evergreen": False},
    },
}


@dataclass(frozen=True)
class DecayEntry:
    half_life_days: float | None
    evergreen: bool
    hard_expiry: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "DecayEntry":
        return cls(
            half_life_days=data.get("half_life_days"),
            evergreen=bool(data.get("evergreen", False)),
            hard_expiry=data.get("hard_expiry"),
        )


@dataclass(frozen=True)
class DecayPolicy:
    default: DecayEntry
    formats: dict[str, DecayEntry] = field(default_factory=dict)
    source: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict, *, source: str = "unknown") -> "DecayPolicy":
        default = DecayEntry.from_dict(data.get("default", {"half_life_days": 365, "evergreen": False}))
        formats = {k: DecayEntry.from_dict(v) for k, v in (data.get("formats") or {}).items()}
        return cls(default=default, formats=formats, source=source)

    def entry_for(self, format_: str | None) -> DecayEntry | None:
        """None (not `self.default`) when `format_` itself is None --
        "not classified yet" is a different, honest state from "classified
        as a format with no specific policy row", and callers (see
        `freshness_component`) must be able to tell them apart rather
        than silently falling back to a 365-day default for content that
        was never typed at all."""
        if format_ is None:
            return None
        return self.formats.get(format_, self.default)


FALLBACK_DECAY_POLICY = DecayPolicy.from_dict(FALLBACK_DECAY_POLICY_DICT, source="package fallback (not sites.ranking_weights)")


def age_days(published_at: datetime | None, *, now: datetime | None = None) -> float | None:
    if published_at is None:
        return None
    ref = now or datetime.now(timezone.utc)
    pub = published_at if published_at.tzinfo is not None else published_at.replace(tzinfo=timezone.utc)
    return max((ref - pub).total_seconds() / 86400.0, 0.0)


def decay_factor(entry: DecayEntry, days_old: float | None) -> float | None:
    """The real (non-illustrative) exponential decay curve. `None` only
    when `days_old` is unknown (no `published_at`) -- a missing age is
    not the same thing as a fully-decayed item and must not be scored as
    0.0, which would be indistinguishable from "this is provably stale"
    in the blend and in the Sec.10 feature log."""
    if entry.half_life_days is None:
        return FRESH_SCORE_NO_DECAY
    if days_old is None:
        return None
    return 0.5 ** (days_old / entry.half_life_days)


def freshness_component(
    format_: str | None,
    published_at: datetime | None,
    policy: DecayPolicy,
    *,
    now: datetime | None = None,
) -> float | None:
    """The blend's `w_fresh` input. `None` (excluded from the blend,
    renormalized -- see `blend.py`) whenever `format_` is `None`, which
    is EVERY real `public.articles` row today (F50) -- this is the
    honest, unavoidable state of the production default path. Type-aware
    decay is real code, exercised and proven correct against synthetic
    format overlays (see `synthetic.py` and `tests/test_decay.py`), not
    against real data, because real data cannot exercise it yet."""
    entry = policy.entry_for(format_)
    if entry is None:
        return None
    return decay_factor(entry, age_days(published_at, now=now))

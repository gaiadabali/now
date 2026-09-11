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

## F124/F125 -- the decay TRUST gate (PROGRESS.md ticket T2)

`format` has exactly one live consumer: this module. F124 measured that a
WRONG `format` is strictly worse for ranking than no `format` at all: NULL
already takes the honest, neutral `None` path below (excluded from the
blend, renormalised), while a wrong value flips the entire `w_fresh` term --
on this archive (49% of Jakarta is 2019) a 3-year-old article typed `news`
(21-day half-life) scores freshness ~= 0 while any evergreen label scores
1.0. F125 re-stamped every auto-applied classifier value's
`engine.entity_terms.confidence`/`.source` with its MEASURED accuracy and
provenance, specifically so a consumer could gate on it -- this module is
that consumer.

`is_format_trusted`/`describe_format_trust` implement the gate:
`source='editor'` (a human decided) is unconditionally trusted, matching
`now_classifier.db`'s own no-clobber convention for editor-sourced facts.
Everything else is trusted only if `confidence >= policy
.min_format_confidence`. A `format_` value with NO entity_terms row at all
(confidence and source both `None` -- e.g. a legacy value set before this
column existed) is NOT trusted either: an unverifiable provenance is not
a reason to apply a signal whose failure mode this ticket exists to avoid
-- "unknown" fails closed here, the same stance `embed_routing.py` takes
when an instrument abstains.

`TRUSTED_FORMAT_SOURCES` is deliberately a set, not a single string
literal: F121's offline LLM batch is expected to add an LLM-verified
provenance marker later (PROGRESS.md), at which point extending trust to
it is a one-line addition here, not a second gate.

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

# F124/F125 (PROGRESS.md T2) -- matches format_decay.json's seeded default
# and now_platform.engine.sites.ranking_weights['decay']['min_format_confidence'].
DEFAULT_MIN_FORMAT_CONFIDENCE = 0.85

# source='editor' is a human decision (now_classifier.db's own no-clobber
# convention: an editor-sourced entity_terms row is never overwritten by a
# classifier re-run) -- always trusted regardless of confidence. See the
# module docstring for why this is a set, not a literal: F121's LLM batch
# is expected to add a second trusted marker later.
TRUSTED_FORMAT_SOURCES = frozenset({"editor"})

# Mirrors engine/packages/taxonomy/seed/format_decay.json's `"decay"`
# object exactly (same version, same values) -- used only as a fallback;
# see module docstring. Kept as a plain module-level constant (not
# re-derived from the JSON file) so this package has zero filesystem
# dependency on another package's data directory.
FALLBACK_DECAY_POLICY_DICT: dict = {
    "version": 1,
    "unit": "days",
    "min_format_confidence": DEFAULT_MIN_FORMAT_CONFIDENCE,
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
    # F124/F125 (T2): read from this same dict's 'min_format_confidence' key
    # (`sites.ranking_weights['decay']['min_format_confidence']` in
    # production -- see now_db.provisioning's backfill for why a plain seed
    # edit alone does not reach an already-provisioned site). Falls back to
    # DEFAULT_MIN_FORMAT_CONFIDENCE when the key is absent (an
    # older-than-this-ticket site row, or a test fixture that doesn't set
    # it) rather than raising -- the gate degrades to the documented
    # default, never to "no gate at all".
    min_format_confidence: float = DEFAULT_MIN_FORMAT_CONFIDENCE

    @classmethod
    def from_dict(cls, data: dict, *, source: str = "unknown") -> "DecayPolicy":
        default = DecayEntry.from_dict(data.get("default", {"half_life_days": 365, "evergreen": False}))
        formats = {k: DecayEntry.from_dict(v) for k, v in (data.get("formats") or {}).items()}
        min_format_confidence = float(data.get("min_format_confidence", DEFAULT_MIN_FORMAT_CONFIDENCE))
        return cls(default=default, formats=formats, source=source, min_format_confidence=min_format_confidence)

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


def is_format_trusted(format_confidence: float | None, format_source: str | None, policy: DecayPolicy) -> bool:
    """F124/F125 (T2) trust gate. `format_source` in `TRUSTED_FORMAT_SOURCES`
    (today: `'editor'`) is trusted unconditionally -- a human decision is
    not something a measured-accuracy threshold should override. Otherwise
    trusted only if `format_confidence >= policy.min_format_confidence`.
    `format_confidence is None` (no `engine.entity_terms` row matched --
    e.g. a `public.articles.format` value with no recorded provenance)
    fails closed: an unverifiable value is not trusted, matching this
    ticket's own premise that a wrong format is worse than none at all, so
    "we don't know" must not default to "assume it's fine"."""
    if format_source in TRUSTED_FORMAT_SOURCES:
        return True
    if format_confidence is None:
        return False
    return format_confidence >= policy.min_format_confidence


def describe_format_trust(
    format_: str | None, format_confidence: float | None, format_source: str | None, policy: DecayPolicy
) -> str | None:
    """A human-readable reason the format-specific decay curve was NOT
    applied, for the Inspector (E3.4) to surface -- per this ticket's own
    acceptance criterion that a signal which silently changes is a
    debugging nightmare. Returns `None` when there is nothing
    gate-specific to report: `format_` itself is `None` (the ordinary
    "not classified" case `blend.py`'s static explanation already covers)
    or the value IS trusted.

    Wording tracks behaviour deliberately. This said "freshness withheld"
    while the gate returned no freshness at all; since F133 it falls back
    to the neutral `default` curve instead, so freshness IS applied and
    only the format-specific half-life is declined. Leaving the old text
    would have been worse than no explanation -- an Inspector that says a
    signal was withheld while the signal is in fact contributing sends a
    reader hunting for a bug that is not there."""
    if format_ is None:
        return None
    if is_format_trusted(format_confidence, format_source, policy):
        return None
    conf_str = f"{format_confidence:.2f}" if format_confidence is not None else "unknown"
    source_str = format_source or "unknown"
    half_life = policy.default.half_life_days
    return (
        f"format-specific decay not trusted: {conf_str} < {policy.min_format_confidence:.2f} "
        f"(source={source_str}) -- using neutral {half_life:g}d default curve "
        f"instead of the '{format_}' curve (F124/F133 decay trust gate)"
    )


def freshness_component(
    format_: str | None,
    published_at: datetime | None,
    policy: DecayPolicy,
    *,
    format_confidence: float | None,
    format_source: str | None,
    now: datetime | None = None,
) -> float | None:
    """The blend's `w_fresh` input. `None` (excluded from the blend,
    renormalized -- see `blend.py`) whenever `format_` is `None` (not yet
    classified -- F50) OR whenever `format_` IS classified but fails the
    F124/F125 trust gate (`is_format_trusted`) -- both reuse the identical
    NULL path, deliberately: the blend already renormalises correctly for
    "not classified", so an untrusted classification degrades to that same
    honest state rather than a new, separately-handled case. `format_confidence`/
    `format_source` are REQUIRED (no default): this ticket's whole premise
    is that a wrong format is worse than none, so a caller must consciously
    supply what it knows (including `None`/`None` for "unknown") rather than
    silently inheriting pre-gate behaviour by omitting them."""
    entry = policy.entry_for(format_)
    if entry is None:
        return None
    if not is_format_trusted(format_confidence, format_source, policy):
        # Classified, but we do not trust WHICH format -- fall back to the
        # neutral `default` curve (365d) rather than dropping freshness.
        #
        # Withholding entirely was the first implementation, and measurement
        # showed it overshoots (F133): every live format value carries its
        # MEASURED accuracy (0.40-0.72) after F125's re-stamping, so nothing
        # clears the 0.85 gate and freshness was being withheld from 100% of
        # classified articles -- 7,508 rows. That leaves a news-carrying
        # magazine with NO recency signal at all: a 2019 piece and a 2026
        # piece score identically.
        #
        # That is avoidable, because `published_at` is not in doubt -- only
        # WHICH half-life applies is. F124's actual finding was that a wrong
        # format flips the whole term (news 21d -> ~0 vs evergreen -> 1.0 on
        # a 2019-heavy archive); a single neutral curve cannot produce that
        # swing. It degrades to a graded age penalty instead of a flip, which
        # is the honest position: "newer is worth more, and we decline to
        # guess by how much for this format."
        #
        # `format_ is None` above still returns None -- "never classified" is
        # a genuinely different state from "classified, not trusted", and the
        # blend renormalising for it remains correct.
        entry = policy.default
    return decay_factor(entry, age_days(published_at, now=now))

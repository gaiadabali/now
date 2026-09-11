"""Contextual filters (ARCHITECTURE.md Sec.8.B). Per Sec.8.G's ordering
rule these run last, in memory, over the already-reduced (~40 row)
candidate set produced by `hard.py` + the caller's rail-specific retrieval
(vector kNN / PostGIS / semantic). None of these touch a database
directly -- every input (already-read timestamps, session-shown ids,
itinerary membership, trip dates, party constraints) is resolved by the
caller from wherever it actually lives (the beacon's `interactions` table,
the platform DB's `itinerary_stops` -- a second database this
single-DB-scoped package does not connect to, matching now-search's
precedent) and handed in as a `SessionState`.

Unlike Sec.8.A, none of these are absolute: "already-read" **decays**
rather than hard-excluding forever (Open decision #4 default: 14 days,
then decay back -- ARCHITECTURE.md Sec.18), so it is implemented as a
down-weight multiplier here, exposed alongside the two genuinely hard
contextual exclusions (already-shown-this-session, already-in-itinerary)
so callers can choose to hard-filter or just penalize."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from now_filters.models import Candidate, SessionState

ALREADY_READ_DECAY_DAYS = 14.0  # ARCHITECTURE.md Sec.18 open decision #4 default


def _now(session: SessionState) -> datetime:
    return session.now or datetime.now(timezone.utc)


def already_read_weight(candidate: Candidate, session: SessionState) -> float:
    """1.0 = no suppression, 0.0 = fully suppressed. Linear decay back to
    1.0 over `ALREADY_READ_DECAY_DAYS` from the read timestamp -- a
    reasonable, simple curve given Sec.18 specifies only the window, not
    a shape; documented here as a judgment call, not a shape a real study
    has validated yet."""
    read_at = session.already_read.get(candidate.key)
    if read_at is None:
        return 1.0
    age_days = (_now(session) - read_at).total_seconds() / 86400.0
    if age_days >= ALREADY_READ_DECAY_DAYS:
        return 1.0
    if age_days <= 0:
        return 0.0
    return age_days / ALREADY_READ_DECAY_DAYS


def is_hard_excluded_by_session(candidate: Candidate, session: SessionState) -> bool:
    """The two Sec.8.B items that ARE effectively absolute for the
    duration they apply: don't show the same card twice in one session,
    and don't recommend something already committed to an itinerary."""
    return (
        candidate.key in session.already_shown_this_session
        or candidate.key in session.already_in_itinerary
    )


def _parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


_DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def is_open_at(candidate: Candidate, when: datetime) -> bool:
    """`places.hours` is a set of (day, opens, closes) rows (Payload's
    `places_hours` join table). No hours rows at all is treated as "hours
    unknown, not closed" (open) -- ARCHITECTURE.md doesn't specify a
    default and geocoding/hours coverage is known-sparse (Sec.6), so
    failing an entire rail closed for missing hours data would be a worse
    outcome than occasionally recommending a venue that turns out to be
    shut, which the reader discovers on arrival at the place page (which
    does show hours) rather than never seeing the recommendation at all.
    """
    if not candidate.hours:
        return True
    dow = _DOW[when.weekday()]
    prev_dow = _DOW[(when.weekday() - 1) % 7]
    minutes_now = when.hour * 60 + when.minute
    for day, opens, closes in candidate.hours:
        if not opens or not closes:
            continue
        oh, om = _parse_hhmm(opens)
        ch, cm = _parse_hhmm(closes)
        open_min, close_min = oh * 60 + om, ch * 60 + cm
        crosses_midnight = close_min <= open_min
        if day == dow:
            if crosses_midnight:
                # e.g. wed 18:00-02:00: open from 18:00 through end of Wednesday.
                if minutes_now >= open_min:
                    return True
            elif open_min <= minutes_now < close_min:
                return True
        elif day == prev_dow and crosses_midnight:
            # Yesterday's overnight window (e.g. wed 18:00-02:00) spills
            # into today's early hours (thu 00:00-02:00).
            if minutes_now < close_min:
                return True
    return False


def within_trip_window(candidate: Candidate, session: SessionState) -> bool:
    """Applies to event-shaped candidates (`ends_at` populated). A
    candidate with no `ends_at` (a place, or an evergreen article) is not
    date-bound and always passes -- trip windows constrain *occurrences*,
    not venues."""
    if session.trip_start is None and session.trip_end is None:
        return True
    if candidate.ends_at is None:
        return True
    if session.trip_start is not None and candidate.ends_at < session.trip_start:
        return False
    if session.trip_end is not None and candidate.ends_at > session.trip_end:
        return False
    return True


# Party-constraint -> amenity mapping. A judgment call interpreting the
# existing Payload `enum_places_amenities` values (no new column needed) --
# NOT a schema decision, since every value referenced already exists in
# the real enum (see engine/packages/cms migration
# 20260908_131927_initial_schema.ts). Flagged plainly as an interim
# mapping a UX/product decision could reasonably override.
PARTY_AMENITY_MAP: dict[str, tuple[str, ...]] = {
    "accessibility": ("wheelchair-accessible",),
    "halal": ("halal-certified",),
    "vegetarian": ("vegetarian-friendly", "vegan-options"),
    "kids": ("kids-club",),
}

_PRICE_ORDER = ("budget", "moderate", "upscale", "luxury")


def satisfies_party_constraints(candidate: Candidate, session: SessionState) -> bool:
    if session.party_accessibility and not (candidate.amenities & set(PARTY_AMENITY_MAP["accessibility"])):
        return False
    if session.party_halal and not (candidate.amenities & set(PARTY_AMENITY_MAP["halal"])):
        return False
    if session.party_vegetarian and not (candidate.amenities & set(PARTY_AMENITY_MAP["vegetarian"])):
        return False
    if session.party_kids and not (candidate.amenities & set(PARTY_AMENITY_MAP["kids"])):
        return False
    if session.party_budget_ceiling and candidate.price_band:
        try:
            if _PRICE_ORDER.index(candidate.price_band) > _PRICE_ORDER.index(session.party_budget_ceiling):
                return False
        except ValueError:
            pass  # unrecognized price_band value -- do not exclude on a value we can't rank
    return True


@dataclass(frozen=True)
class ContextualResult:
    survivors: list[Candidate]
    weights: dict[tuple[str, int], float]  # already-read decay multiplier per surviving candidate


def apply_contextual_filters(
    candidates: list[Candidate],
    session: SessionState,
    *,
    require_open_now: bool = False,
) -> ContextualResult:
    """Applies, in order: session/itinerary hard exclusion -> party
    constraints -> trip window -> (optional) open-at-time -> already-read
    decay weight (never excludes, only informs downstream soft ranking)."""
    when = session.open_at or _now(session)
    survivors: list[Candidate] = []
    weights: dict[tuple[str, int], float] = {}
    for c in candidates:
        if is_hard_excluded_by_session(c, session):
            continue
        if not satisfies_party_constraints(c, session):
            continue
        if not within_trip_window(c, session):
            continue
        if require_open_now and not is_open_at(c, when):
            continue
        survivors.append(c)
        weights[c.key] = already_read_weight(c, session)
    return ContextualResult(survivors=survivors, weights=weights)

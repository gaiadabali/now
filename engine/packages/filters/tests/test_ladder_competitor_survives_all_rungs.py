"""THE proof for the launch-blocking guarantee: "Competitor exclusion
proven to survive every fallback rung" (ARCHITECTURE.md Sec.8.F closing
sentence / Sec.1 principle 6). Two independent proofs, both against real
Postgres:

1. **The real pipeline, walked to exhaustion.** A synthetic dataset
   engineered so the rail is starved at every rung (fewer than
   `slots_needed` non-competitor actives exist even with the area
   constraint fully dropped) forces `run_nearby_ladder` through all 8
   rungs in `DEFAULT_LADDER`, ending at `editorial_fallback`. At EVERY
   rung -- not just the one the ladder lands on -- the raw SQL result is
   asserted to contain zero `stay`-type rows, for a `stay` subject.

2. **Defense-in-depth**, independent of whether `hard.py`'s own SQL is
   correct: an adversarial `fetch_fn` that deliberately LEAKS a same-type
   competitor at every single rung is handed to `run_ladder` directly.
   `ladder.py` re-derives the excluded-type set from `engine.type_relations`
   itself and strips the leak at every rung regardless of what the
   rail-specific fetch function returned -- proving the guarantee does
   not rely on every future rail implementation (E3.5-3.7) remembering to
   re-apply the predicate correctly.

Tier is deliberately not modelled here because it doesn't need to be:
`hard.py`'s query and `ladder.py`'s defensive re-check both operate purely
on `type`/`status`, with no parameter through which a tier could enter --
see `test_hard_filters_competitor.py::test_exclusion_identical_regardless_of_partnership_tier`
for the structural proof that tier cannot affect this at all.
"""

from __future__ import annotations

from dataclasses import replace

from now_filters.ladder import run_ladder
from now_filters.models import DEFAULT_LADDER, Candidate
from now_filters.pipeline import NearbySubject, build_nearby_fetch_fn, run_nearby_ladder
from now_filters.synthetic import SYNTH_PLACES_TABLE, SyntheticPlace, create_synthetic_places_table

SUBJECT = NearbySubject(place_id=None, type="stay", lat=-6.22, lng=106.80, area_term="senopati")


def _starved_dataset() -> list[SyntheticPlace]:
    """Engineered so that even with the area constraint fully dropped
    (city-wide), fewer than 10 non-competitor actives exist -- guaranteeing
    the ladder cannot satisfy `slots_needed=10` at any rung and must walk
    all the way to `editorial_fallback`. Includes `stay` competitors at
    every distance band (500m / 3km / 10km / 40km) plus a pending_review
    and a closed `stay` row, specifically to tempt a buggy widen-radius or
    drop-status implementation into leaking one."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active", lat=-6.2205, lng=106.8005),  # ~80m -- competitor
        SyntheticPlace(id=2, type="stay", status="active", lat=-6.245, lng=106.825),  # ~3.4km -- competitor
        SyntheticPlace(id=3, type="stay", status="active", lat=-6.31, lng=106.90),  # ~13km -- competitor
        SyntheticPlace(id=4, type="stay", status="active", lat=-6.60, lng=107.20),  # ~55km -- competitor
        SyntheticPlace(id=5, type="stay", status="pending_review", lat=-6.2205, lng=106.8005),  # F27 + competitor
        SyntheticPlace(id=6, type="stay", status="closed", lat=-6.2205, lng=106.8005),  # closed + competitor
        SyntheticPlace(id=7, type="eat", status="active", lat=-6.2206, lng=106.8006),
        SyntheticPlace(id=8, type="drink", status="active", lat=-6.221, lng=106.801),
        SyntheticPlace(id=9, type="do", status="active", lat=-6.60, lng=107.20),
        SyntheticPlace(id=10, type="wellness", status="active", lat=-6.60, lng=107.20),
    ]
    return rows


def test_ladder_walks_to_editorial_fallback_and_never_leaks_stay(conn, relations):
    rows = _starved_dataset()
    create_synthetic_places_table(conn, rows)

    run = run_nearby_ladder(conn, SUBJECT, relations, slots_needed=10, places_table=SYNTH_PLACES_TABLE)

    # Sanity: the dataset really is starved all the way down.
    assert run.rungs_evaluated == [r.name for r in DEFAULT_LADDER]
    assert run.result.rung_name == "editorial_fallback"
    assert run.result.starved  # only 4 non-competitor actives exist (ids 7-10) against slots_needed=10

    final_types = {c.type for c in run.result.candidates}
    assert "stay" not in final_types
    final_ids = {c.entity_id for c in run.result.candidates}
    assert final_ids == {7, 8, 9, 10}


def test_every_individual_rung_raw_output_excludes_stay(conn, relations):
    """Stronger than checking only the landed rung: re-runs each rung's
    fetch function independently and asserts the invariant at every one,
    including the ones the ladder orchestrator skips past because they
    under-filled."""
    rows = _starved_dataset()
    create_synthetic_places_table(conn, rows)
    fetch_fn = build_nearby_fetch_fn(conn, SUBJECT, relations, places_table=SYNTH_PLACES_TABLE)

    for rung in DEFAULT_LADDER:
        raw = fetch_fn(rung)
        types = {c.type for c in raw}
        assert "stay" not in types, f"rung {rung.name!r} leaked a `stay` competitor: {raw}"
        # F27, re-checked at every rung too: no pending_review/closed id.
        ids = {c.entity_id for c in raw}
        assert 5 not in ids, f"rung {rung.name!r} leaked pending_review id=5"
        assert 6 not in ids, f"rung {rung.name!r} leaked closed id=6"


def test_defense_in_depth_ladder_strips_leak_from_adversarial_fetch_fn(relations):
    """No DB needed: proves `ladder.py` itself -- not just `hard.py`'s
    SQL -- enforces the invariant, by handing it a `fetch_fn` that
    deliberately returns a `stay` competitor (and a pending_review place)
    at every single rung."""
    leaking_competitor = Candidate(entity_type="place", entity_id=999, type="stay", status="active")
    leaking_pending = Candidate(entity_type="place", entity_id=998, type="eat", status="pending_review")
    good = Candidate(entity_type="place", entity_id=1, type="eat", status="active")

    def adversarial_fetch(_rung):
        return [leaking_competitor, leaking_pending, good]

    run = run_ladder(adversarial_fetch, subject_type="stay", relations=relations, slots_needed=5)

    # The ladder is starved every rung (only 1 valid candidate ever
    # returned), so it walks to the last rung -- but at NO point does the
    # leaked competitor or the leaked pending_review row survive.
    assert run.result.rung_name == DEFAULT_LADDER[-1].name
    ids = {c.entity_id for c in run.result.candidates}
    assert 999 not in ids
    assert 998 not in ids
    assert ids == {1}


NONE_SUBJECT = NearbySubject(place_id=None, type=None, lat=-6.22, lng=106.80, area_term="senopati")
VENUE_TYPES = ("stay", "eat", "drink", "wellness", "shop")


def _starved_dataset_unknown_subject() -> list[SyntheticPlace]:
    """F68 counterpart to `_starved_dataset`: a `subject_type=None` page
    cannot rule out ANY venue-shaped type as its own, so every one of the
    5 venue L1 types (plus `unknown`) is a potential competitor here, not
    just `stay`. Includes one of each venue type at close range (so a
    buggy None-handling implementation would happily return them) plus
    two genuinely non-venue rows (`do`, `editorial`) that must survive."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active", lat=-6.2205, lng=106.8005),
        SyntheticPlace(id=2, type="eat", status="active", lat=-6.2206, lng=106.8006),
        SyntheticPlace(id=3, type="drink", status="active", lat=-6.2207, lng=106.8007),
        SyntheticPlace(id=4, type="wellness", status="active", lat=-6.2208, lng=106.8008),
        SyntheticPlace(id=5, type="shop", status="active", lat=-6.2209, lng=106.8009),
        SyntheticPlace(id=6, type="unknown", status="active", lat=-6.221, lng=106.801),
        SyntheticPlace(id=7, type="do", status="active", lat=-6.60, lng=107.20),
        SyntheticPlace(id=8, type="editorial", status="active", lat=-6.60, lng=107.20),
    ]
    return rows


def test_f68_ladder_walks_to_editorial_fallback_and_never_leaks_any_venue_type_for_unknown_subject(conn, relations):
    """F68's exact reported defect, reproduced end-to-end through the real
    ladder + real Postgres: with `subject_type=None` (NearbySubject.type),
    the dataset is starved all the way to `editorial_fallback` (only 2
    non-venue actives exist against slots_needed=10), and at NO point may
    any of the 5 venue types or `unknown` survive -- only `do`/`editorial`
    (ids 7-8) may."""
    rows = _starved_dataset_unknown_subject()
    create_synthetic_places_table(conn, rows)

    run = run_nearby_ladder(conn, NONE_SUBJECT, relations, slots_needed=10, places_table=SYNTH_PLACES_TABLE)

    assert run.rungs_evaluated == [r.name for r in DEFAULT_LADDER]
    assert run.result.rung_name == "editorial_fallback"
    assert run.result.starved

    final_types = {c.type for c in run.result.candidates}
    assert not final_types & (set(VENUE_TYPES) | {"unknown"}), (
        f"F68 regression: a venue-shaped type leaked for subject_type=None: {final_types}"
    )
    final_ids = {c.entity_id for c in run.result.candidates}
    assert final_ids == {7, 8}


def test_f68_every_individual_rung_raw_output_excludes_all_venue_types_for_unknown_subject(conn, relations):
    """F68 counterpart to `test_every_individual_rung_raw_output_excludes_stay`:
    re-runs each rung's fetch independently for `subject_type=None` and
    asserts NO venue-shaped type (nor `unknown`) survives at any single
    rung, including (per the defect report) `editorial_fallback`
    specifically."""
    rows = _starved_dataset_unknown_subject()
    create_synthetic_places_table(conn, rows)
    fetch_fn = build_nearby_fetch_fn(conn, NONE_SUBJECT, relations, places_table=SYNTH_PLACES_TABLE)

    for rung in DEFAULT_LADDER:
        raw = fetch_fn(rung)
        types = {c.type for c in raw}
        leaked = types & (set(VENUE_TYPES) | {"unknown"})
        assert not leaked, f"rung {rung.name!r} leaked venue-shaped type(s) for subject_type=None: {leaked}"


def test_f68_defense_in_depth_strips_venue_leak_for_none_subject_type(relations):
    """F68 counterpart to `test_defense_in_depth_ladder_strips_leak_from_adversarial_fetch_fn`:
    proves `ladder.py`'s own defensive re-check -- not just `hard.py`'s
    SQL -- fails closed for `subject_type=None` too. Before the fix,
    `_enforce_competitor_invariant` called `excluded_types_for(relations,
    None)`, got back an empty set, and let every leaked candidate
    through regardless of type."""
    leaking_stay = Candidate(entity_type="place", entity_id=901, type="stay", status="active")
    leaking_unknown = Candidate(entity_type="place", entity_id=902, type="unknown", status="active")
    good_editorial = Candidate(entity_type="place", entity_id=1, type="editorial", status="active")

    def adversarial_fetch(_rung):
        return [leaking_stay, leaking_unknown, good_editorial]

    run = run_ladder(adversarial_fetch, subject_type=None, relations=relations, slots_needed=5)

    ids = {c.entity_id for c in run.result.candidates}
    assert 901 not in ids, "F68 regression: ladder's defensive re-check let a 'stay' leak through for subject_type=None"
    assert 902 not in ids, "F68 regression: ladder's defensive re-check let an 'unknown' leak through for subject_type=None"
    assert ids == {1}


def test_f68_defense_in_depth_holds_at_editorial_fallback_rung_specifically_for_none_subject(relations):
    """Isolates rung 6 by name for `subject_type=None`, mirroring
    `test_defense_in_depth_holds_at_editorial_fallback_rung_specifically`
    -- this is the exact rung F68 reported as broken."""
    editorial_rung = next(r for r in DEFAULT_LADDER if r.name == "editorial_fallback")
    leaking = [
        Candidate(entity_type="place", entity_id=1, type="stay", status="active"),
        Candidate(entity_type="place", entity_id=2, type="editorial", status="active"),
    ]

    def fetch(_rung):
        return leaking

    run = run_ladder(fetch, subject_type=None, relations=relations, slots_needed=1, ladder=(editorial_rung,))
    ids = {c.entity_id for c in run.result.candidates}
    assert ids == {2}


def test_f73_ladder_defensive_check_fails_closed_on_null_typed_candidate(relations):
    """F73/F74 (PROGRESS.md): `_enforce_competitor_invariant` had its OWN
    copy of the same disagreement -- a plain `c.type not in excluded`
    check treats `None not in {...}` as `True` (survives), which silently
    disagreed with `hard.py`'s SQL (fails closed on NULL) and the
    pre-fix `is_competitor` (failed open, matching this bug rather than
    catching it). An unclassified article candidate (`type=None`, the
    real state of every real article today -- F50) reaching this
    defensive re-check on a genuine `stay` subject must now be dropped,
    exactly like an explicit `stay` competitor, and exactly like the SQL
    stage it is meant to double-check."""
    leaking_null_typed = Candidate(entity_type="article", entity_id=997, type=None, status=None)
    leaking_competitor = Candidate(entity_type="place", entity_id=999, type="stay", status="active")
    good = Candidate(entity_type="place", entity_id=1, type="eat", status="active")

    def adversarial_fetch(_rung):
        return [leaking_null_typed, leaking_competitor, good]

    run = run_ladder(adversarial_fetch, subject_type="stay", relations=relations, slots_needed=5)

    ids = {c.entity_id for c in run.result.candidates}
    assert 997 not in ids, "F73 regression: ladder's defensive re-check let a NULL-typed candidate through"
    assert 999 not in ids
    assert ids == {1}


def test_defense_in_depth_holds_at_editorial_fallback_rung_specifically(relations):
    """Isolates rung 6 by name, since that is the rung Sec.8.F calls out
    explicitly ("editorial fallback curated/popular for type+area") as
    the last resort -- the one most tempting to implement as "just show
    something popular" without re-checking type."""
    editorial_rung = next(r for r in DEFAULT_LADDER if r.name == "editorial_fallback")
    leaking = [
        Candidate(entity_type="place", entity_id=1, type="stay", status="active"),
        Candidate(entity_type="place", entity_id=2, type="eat", status="active"),
    ]

    def fetch(_rung):
        return leaking

    run = run_ladder(fetch, subject_type="stay", relations=relations, slots_needed=1, ladder=(editorial_rung,))
    ids = {c.entity_id for c in run.result.candidates}
    assert ids == {2}

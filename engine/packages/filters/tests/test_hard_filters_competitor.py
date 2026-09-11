"""Competitor exclusion (ARCHITECTURE.md Sec.8.A/Sec.1 principle 6) at the
single-rung SQL level. The multi-rung "survives every rung" proof lives in
`test_ladder_competitor_survives_all_rungs.py` -- this file proves the
underlying predicate itself is correct in isolation, including across all
five `exclude_same=true` types (not just `stay`) and across partnership
tier (Sec.11: "identical across all three tiers... tier controls link
rendering only" -- `is_paid` must have zero effect on exclusion)."""

from __future__ import annotations

from now_filters.hard import (
    build_articles_hard_filter_sql,
    build_places_hard_filter_sql,
    fetch_articles_hard_filtered,
    fetch_places_hard_filtered,
)
from now_filters.synthetic import (
    SYNTH_ARTICLES_TABLE,
    SYNTH_PLACES_TABLE,
    SyntheticArticle,
    SyntheticPlace,
    create_synthetic_articles_table,
    create_synthetic_places_table,
)
from now_filters.type_relations import is_competitor


def test_same_type_excluded_for_every_exclude_same_type(conn, relations):
    """For each of the 5 `exclude_same=true` L1 types, a same-type
    competitor must be excluded and a complement of a DIFFERENT type must
    survive."""
    for subject_type in ("stay", "eat", "drink", "wellness", "shop"):
        rows = [
            SyntheticPlace(id=1, type=subject_type, status="active"),  # competitor
            SyntheticPlace(id=2, type="editorial", status="active"),  # never excluded (exclude_same=false)
        ]
        create_synthetic_places_table(conn, rows)
        query = build_places_hard_filter_sql(subject_type=subject_type, relations=relations, places_table=SYNTH_PLACES_TABLE)
        survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
        assert 1 not in survivors, f"same-type competitor leaked for subject_type={subject_type}"
        assert 2 in survivors


def test_villa_is_still_a_competitor_to_a_hotel(conn, relations):
    """ARCHITECTURE.md Sec.4: "Exclusion operates at L1. A villa is still
    a competitor to a hotel." Both `hotel` and `villa` are `subtype`
    values under L1 `type=stay` (Sec.4 type tree) -- exclusion keys off
    `type`, so a villa (same L1, different subtype) is excluded from a
    hotel's page exactly as another hotel would be."""
    rows = [
        SyntheticPlace(id=1, type="stay", subtype="hotel", status="active"),
        SyntheticPlace(id=2, type="stay", subtype="villa", status="active"),
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(
        subject_type="stay", relations=relations, exclude_self_id=1, places_table=SYNTH_PLACES_TABLE
    )
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert survivors == set()


def test_exclusion_identical_regardless_of_partnership_tier(conn, relations):
    """ARCHITECTURE.md Sec.11: "Competitor exclusion is identical across
    all three tiers." `hard.py`'s query never references tier/`is_paid`
    at all -- there is no parameter through which a tier could loosen the
    predicate. This test proves it structurally: the exact same
    competing hotel (whether it WOULD be free/listed/paid downstream,
    which is a link-rendering decision made elsewhere, per Sec.11) is
    excluded regardless, because the query has no code path that could
    special-case it."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active"),
        SyntheticPlace(id=2, type="stay", status="active"),  # this would be the "paid, free" competitor in prod
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(
        subject_type="stay", relations=relations, exclude_self_id=1, places_table=SYNTH_PLACES_TABLE
    )
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert 2 not in survivors


def test_f57_unknown_venue_does_not_leak_onto_genuine_subject_page(conn, relations):
    """F57 (PROGRESS.md): the cross-type leak F49 left open. An `unknown`-
    typed place that has been activated before E2.3 reclassifies it (the
    scenario `test_f27_mislabelled_venue_scenario` in
    `test_hard_filters_status.py` documents as a plausible operational
    mistake) must not surface as an "unrecognised competitor" on a
    genuine venue subject's page -- id=1 here plays that exact role: an
    `active` `unknown` place, real `status='active'`, on a `stay`
    subject's rail. Before the F57 fix, `excluded_types_for('stay')` was
    `{'stay'}` and id=1 leaked through; after, it is `{'stay', 'unknown'}`
    and id=1 is excluded, symmetric with F49's already-proven self-
    exclusion direction (id=2 excludes id=1 the same way `unknown`
    excludes `unknown`)."""
    rows = [
        SyntheticPlace(id=1, type="unknown", status="active"),  # activated-too-early sentinel
        SyntheticPlace(id=2, type="eat", status="active"),  # genuine complement, must survive
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(subject_type="stay", relations=relations, places_table=SYNTH_PLACES_TABLE)
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert 1 not in survivors, "unknown-typed place leaked onto a genuine stay subject's page -- F57 regression"
    assert 2 in survivors


def test_editorial_fallback_rung_still_excludes_competitors(conn, relations):
    """Sec.8.F: "The competitor filter never relaxes at any rung" --
    including rung 6, editorial fallback."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active"),
        SyntheticPlace(id=2, type="eat", status="active"),
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(
        subject_type="stay", relations=relations, editorial_fallback=True, places_table=SYNTH_PLACES_TABLE
    )
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert survivors == {2}


def test_f68_none_subject_type_excludes_every_venue_type_strict_rung(conn, relations):
    """F68 (PROGRESS.md): `subject_type=None` at a normal (non-editorial-
    fallback) rung must exclude every venue-shaped type, not just fail to
    apply any exclusion at all. Only the genuinely non-venue `editorial`
    row survives."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active"),
        SyntheticPlace(id=2, type="eat", status="active"),
        SyntheticPlace(id=3, type="drink", status="active"),
        SyntheticPlace(id=4, type="wellness", status="active"),
        SyntheticPlace(id=5, type="shop", status="active"),
        SyntheticPlace(id=6, type="unknown", status="active"),
        SyntheticPlace(id=7, type="editorial", status="active"),
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(subject_type=None, relations=relations, places_table=SYNTH_PLACES_TABLE)
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert survivors == {7}, f"a venue-shaped competitor leaked for subject_type=None: survivors={survivors}"


def test_f73_sql_and_python_agree_on_null_candidate_type(conn, relations):
    """F73 (PROGRESS.md): the SQL builder and `type_relations.is_competitor`
    used to disagree on a NULL candidate type -- the SQL failed CLOSED
    (excluded it, via Postgres NULL propagation through `!= ALL(...)`),
    `is_competitor` failed OPEN (returned `False`, i.e. "not a competitor",
    letting it through). Only `articles` can exhibit this in practice --
    `places.type` is `NOT NULL`, and F49/F57's `unknown` sentinel already
    gives an unclassified place a real string value, never SQL NULL -- so
    this proves the agreement against a synthetic `articles` table: an
    unclassified (`primary_type=None`) article on a genuine `stay`
    subject's rail must be excluded by BOTH paths, identically, alongside
    an explicit same-type competitor and a genuine cross-type complement
    for contrast."""
    rows = [
        SyntheticArticle(id=1, primary_type=None),  # unclassified -- the F73/F74 case, must fail closed
        SyntheticArticle(id=2, primary_type="eat"),  # genuine complement -- must survive
        SyntheticArticle(id=3, primary_type="stay"),  # explicit same-type competitor -- must be excluded
    ]
    create_synthetic_articles_table(conn, rows)

    query = build_articles_hard_filter_sql(
        subject_type="stay", relations=relations, series_dedup=False, articles_table=SYNTH_ARTICLES_TABLE
    )
    survivors = {c.entity_id for c in fetch_articles_hard_filtered(conn, query)}
    assert survivors == {2}, f"SQL path: expected only the genuine complement to survive, got {survivors}"

    # The Python path must reach the identical verdict for every row the
    # SQL just decided, id-by-id -- this is F73's "proven, not asserted
    # separately" requirement.
    assert is_competitor(relations, "stay", None) is True, "Python path disagreed with SQL on the NULL-typed candidate (id=1)"
    assert is_competitor(relations, "stay", "eat") is False, "Python path disagreed with SQL on the genuine complement (id=2)"
    assert is_competitor(relations, "stay", "stay") is True, "Python path disagreed with SQL on the explicit competitor (id=3)"


def test_f68_none_subject_type_excludes_every_venue_type_at_editorial_fallback_rung(conn, relations):
    """The exact defect as reported: "the editorial-fallback rung drops
    the competitor-exclusion predicate entirely when subject_type is
    None." Same dataset as the strict-rung test above, but through the
    `editorial_fallback=True` branch -- rung 6 in `DEFAULT_LADDER`, the
    ladder's last resort."""
    rows = [
        SyntheticPlace(id=1, type="stay", status="active"),
        SyntheticPlace(id=2, type="eat", status="active"),
        SyntheticPlace(id=3, type="drink", status="active"),
        SyntheticPlace(id=4, type="wellness", status="active"),
        SyntheticPlace(id=5, type="shop", status="active"),
        SyntheticPlace(id=6, type="unknown", status="active"),
        SyntheticPlace(id=7, type="editorial", status="active"),
    ]
    create_synthetic_places_table(conn, rows)
    query = build_places_hard_filter_sql(
        subject_type=None, relations=relations, editorial_fallback=True, places_table=SYNTH_PLACES_TABLE
    )
    survivors = {c.entity_id for c in fetch_places_hard_filtered(conn, query)}
    assert survivors == {7}, (
        f"F68 regression: a venue-shaped competitor leaked at the editorial-fallback rung "
        f"for subject_type=None: survivors={survivors}"
    )

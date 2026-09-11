"""engine.type_relations: real seed data, real Postgres. Verifies the
exact matrix ARCHITECTURE.md Sec.4 specifies, and the exclude_same-only
(not complements) exclusion semantics F27 / QA.2 pinned down."""

from __future__ import annotations

from now_filters.type_relations import excluded_types_for, is_competitor

# 2026-09-11 -- the six VENUE types are now mutually complementary. Hansel hit
# this live: "when a restaurant page is open, never suggest another restaurant.
# always hotel or other thing." `eat` excluded its own kind correctly, but its
# complements were {drink, do, event} -- `stay` was MISSING, while `stay` did
# list `eat`. Since `complements` is a strict whitelist (`type = ANY(...)` in
# row1_complementary.py), that asymmetry was a hard structural exclusion: hotel
# pages could show restaurants, restaurant pages could never show hotels.
#
# Row 1's job is literally "a different type" (ARCHITECTURE.md Sec.8), so an
# asymmetry among venue types is an oversight rather than curation, and all 15
# were closed -- not just the one that was reported. `event` and `editorial`
# stay as they were: cross-cutting rather than venue competitors, both
# `exclude_same: False`.
#
# NOTE this touches `complements` ONLY. The exclusion semantics F27/QA.2 pinned
# down are unchanged -- `complements` is a co-recommendation whitelist and is
# still explicitly NOT unioned into the excluded set (see `excluded_types_for`).
EXPECTED = {
    "stay": (True, {"eat", "drink", "wellness", "do", "shop"}),
    "eat": (True, {"stay", "drink", "wellness", "do", "shop", "event"}),
    "drink": (True, {"eat", "stay", "wellness", "do", "shop"}),
    "wellness": (True, {"eat", "stay", "drink", "do", "shop"}),
    "shop": (True, {"eat", "stay", "drink", "wellness", "do"}),
    "do": (False, {"eat", "stay", "drink", "wellness", "shop"}),
    "event": (False, {"eat", "drink", "stay"}),
    "editorial": (False, {"stay", "eat", "drink", "wellness", "shop", "do", "event"}),
    # F49: the fail-closed sentinel for unclassified venues. `exclude_same=True`
    # with NO complements means it excludes its own kind and offers nothing as a
    # complement — the opposite of `editorial`, which was the old sentinel and
    # was invisible to exclusion in both directions.
    "unknown": (True, set()),
}


def test_matrix_matches_architecture_spec(relations):
    assert set(relations) == set(EXPECTED)
    for type_, (exclude_same, complements) in EXPECTED.items():
        rel = relations[type_]
        assert rel.exclude_same is exclude_same, type_
        assert set(rel.complements) == complements, type_


def test_exclude_same_true_types_exclude_themselves(relations):
    """F57: every `exclude_same=True` (venue-shaped) subject also excludes
    `unknown` -- the F49 sentinel is possibly-any-type, so it cannot be
    ruled out as a same-type competitor of ANY venue-shaped subject, not
    just of another `unknown`. See type_relations.py docstring."""
    for type_ in ("stay", "eat", "drink", "wellness", "shop"):
        assert excluded_types_for(relations, type_) == {type_, "unknown"}


def test_exclude_same_false_types_exclude_nothing(relations):
    for type_ in ("do", "event", "editorial"):
        assert excluded_types_for(relations, type_) == set()


def test_complements_never_leak_into_excluded_set(relations):
    """QA.2's key finding (PROGRESS.md F27): `complements` is a
    co-recommendation whitelist, not a competitor list. A `stay` subject's
    complements include `eat`/`drink`/`wellness`/`do` -- none of those may
    ever appear in the excluded set."""
    excluded = excluded_types_for(relations, "stay")
    for complement in relations["stay"].complements:
        assert complement not in excluded


def test_unclassified_string_type_with_no_relation_row_excludes_nothing(relations):
    """A type string that simply has no `type_relations` row (garbage
    data, not the `None`/unclassified state F68 covers) has no relation to
    consult and excludes nothing. This is a distinct, narrower case from
    `subject_type is None` -- see `test_f68_*` below -- and is NOT
    currently known to occur on any real code path (place/article
    `type`/`primary_type` are always either a real taxonomy value or SQL
    NULL, i.e. Python `None`, never an arbitrary string), so it is left
    as-is rather than folded into F68's fix. Flagged as a residual note in
    the F68 ticket report, not fixed here."""
    assert excluded_types_for(relations, "totally-unclassified") == set()


def test_f68_none_subject_type_fails_closed_to_every_venue_type_plus_unknown(relations):
    """F68 (PROGRESS.md): `subject_type=None` -- the REAL state of every
    article in the archive today (F50: `primary_type` is NULL
    archive-wide) -- used to return an EMPTY excluded set, i.e. "unknown
    means exclude nothing". ARCHITECTURE.md Sec.8.A is explicit that
    competitor exclusion is a commercial guarantee, never a preference:
    "we don't know the subject's type" must mean "exclude everything
    venue-shaped", the exact opposite of the old behaviour. The fix is
    data-driven (every `exclude_same=True` row, i.e. the 5 real venue L1
    types) plus the `unknown` sentinel, not a hardcoded type list."""
    excluded = excluded_types_for(relations, None)
    assert excluded == {"stay", "eat", "drink", "wellness", "shop", "unknown"}


def test_f68_known_editorial_subjects_not_conflated_with_unknown(relations):
    """The F68 fix must fire ONLY for `subject_type is None` -- a KNOWN
    subject_type of `editorial`/`do`/`event` (exclude_same=False) is a
    completely different fact ("we know it's editorial") from "we don't
    know the type at all", and must keep excluding nothing, exactly as
    before the fix."""
    for subject_type in ("editorial", "do", "event"):
        assert excluded_types_for(relations, subject_type) == set()


def test_is_competitor_symmetric_pairs(relations):
    assert is_competitor(relations, "stay", "stay") is True
    assert is_competitor(relations, "stay", "eat") is False
    assert is_competitor(relations, "do", "do") is False  # do has exclude_same=false
    # F73: a NULL/unknown candidate_type on a KNOWN venue subject now fails
    # CLOSED (was `False` pre-fix -- see type_relations.is_competitor's
    # docstring). A candidate we cannot identify cannot be vouched for as
    # safe when the subject excludes anything at all.
    assert is_competitor(relations, "stay", None) is True
    # ...but when the subject excludes NOTHING (a known non-venue type),
    # an unidentifiable candidate is still not treated as a competitor --
    # there is nothing for it to compete with.
    assert is_competitor(relations, "do", None) is False
    assert is_competitor(relations, "editorial", None) is False


def test_f68_is_competitor_none_subject_fails_closed_for_venue_types(relations):
    """Mirrors `test_f68_none_subject_type_fails_closed_to_every_venue_type_plus_unknown`
    at the `is_competitor` entry point, which had its OWN independent
    `not subject_type` early-return short-circuiting to `False` -- a
    second copy of the same bug that had to be fixed alongside
    `excluded_types_for` itself, not merely inherited from it."""
    for venue_type in ("stay", "eat", "drink", "wellness", "shop", "unknown"):
        assert is_competitor(relations, None, venue_type) is True
    for editorial_type in ("editorial", "do", "event"):
        assert is_competitor(relations, None, editorial_type) is False


def test_f57_unknown_excluded_from_every_venue_subject(relations):
    """F57: closes the cross-type leak F49 left open. F49 proved an
    `unknown` subject excludes other `unknown` candidates (self-direction).
    This proves the other direction: a genuine venue subject (any of the 5
    `exclude_same=True` L1 types) must ALSO exclude `unknown` candidates --
    a mislabelled/unclassified place wearing the sentinel type must not
    surface as an unrecognised competitor on, e.g., a real hotel's page."""
    for subject_type in ("stay", "eat", "drink", "wellness", "shop", "unknown"):
        excluded = excluded_types_for(relations, subject_type)
        assert "unknown" in excluded, f"unknown not excluded for venue subject {subject_type!r}"
        assert is_competitor(relations, subject_type, "unknown") is True


def test_f57_editorial_subjects_unaffected(relations):
    """F57 explicitly scopes the fix to venue subjects: `editorial`/`do`/
    `event` (the `exclude_same=False` rows) must still exclude nothing,
    `unknown` included -- they are not commercial venues and already list
    every venue type, `unknown`'s real type among them, as a complement."""
    for subject_type in ("editorial", "do", "event"):
        excluded = excluded_types_for(relations, subject_type)
        assert excluded == set()
        assert is_competitor(relations, subject_type, "unknown") is False

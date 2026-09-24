"""`competes_with` logic (migration 0008), constructed entirely in-process --
no Postgres, no `relations` fixture. `test_type_relations.py` already
exercises the real seeded `now_jakarta` data end to end; this file exists so
the exclusion ALGORITHM itself (not the live data) can be checked in an
environment where `now_jakarta` is unreachable, and so a synthetic type
vocabulary can probe shapes the real 9-row matrix does not happen to cover
(three-way competition, asymmetric `competes_with`).
"""

from __future__ import annotations

from now_filters.type_relations import TypeRelation, excluded_types_for, is_competitor


def _relations(*rows: TypeRelation) -> dict[str, TypeRelation]:
    return {r.type: r for r in rows}


def test_competes_with_is_unioned_into_excluded_set():
    relations = _relations(
        TypeRelation(type="eat", exclude_same=True, complements=("stay",), competes_with=("drink",)),
        TypeRelation(type="drink", exclude_same=True, complements=("stay",), competes_with=("eat",)),
        TypeRelation(type="stay", exclude_same=True, complements=("eat", "drink"), competes_with=()),
    )
    assert excluded_types_for(relations, "eat") == {"eat", "drink", "unknown"}
    assert excluded_types_for(relations, "drink") == {"drink", "eat", "unknown"}
    assert is_competitor(relations, "eat", "drink") is True
    assert is_competitor(relations, "drink", "eat") is True
    assert is_competitor(relations, "eat", "stay") is False


def test_competes_with_is_a_noop_when_exclude_same_is_false():
    """A `competes_with` entry on an `exclude_same=False` row is inert --
    `excluded_types_for` returns the empty set for such a subject before it
    ever looks at `competes_with`, matching the existing rule that
    editorial-shaped subjects (`do`/`event`/`editorial`) exclude nothing.
    Nothing in the real seed data does this (every `competes_with` entry
    lives on an `exclude_same=True` row), but the algorithm must not
    silently activate the axis for a row that opted out of exclusion
    altogether."""
    relations = _relations(
        TypeRelation(type="event", exclude_same=False, complements=("eat",), competes_with=("eat",)),
    )
    assert excluded_types_for(relations, "event") == set()
    assert is_competitor(relations, "event", "eat") is False


def test_competes_with_can_be_asymmetric_and_each_side_is_read_independently():
    """`excluded_types_for` looks up `competes_with` on the SUBJECT's own
    row only (mirroring how `complements`/`exclude_same` already work per
    the module's own docstring: "keyed off subject_type only"). An
    asymmetric edit (A competes with B, B does not declare A) is not
    rejected by this function -- data hygiene for that lives in
    `now_db.provisioning`'s seed validation, not here."""
    relations = _relations(
        TypeRelation(type="a", exclude_same=True, complements=(), competes_with=("b",)),
        TypeRelation(type="b", exclude_same=True, complements=(), competes_with=()),
    )
    assert "b" in excluded_types_for(relations, "a")
    assert "a" not in excluded_types_for(relations, "b")
    assert is_competitor(relations, "a", "b") is True
    assert is_competitor(relations, "b", "a") is False


def test_three_way_competitive_class():
    """The owner's rule generalises beyond a pair: nothing about
    `competes_with` assumes exactly two members. A hypothetical third
    F&B-shaped type would just add itself to both existing lists."""
    relations = _relations(
        TypeRelation(type="eat", exclude_same=True, complements=(), competes_with=("drink", "street-food-cart")),
        TypeRelation(type="drink", exclude_same=True, complements=(), competes_with=("eat", "street-food-cart")),
        TypeRelation(
            type="street-food-cart", exclude_same=True, complements=(), competes_with=("eat", "drink")
        ),
    )
    for subject in ("eat", "drink", "street-food-cart"):
        others = {"eat", "drink", "street-food-cart"} - {subject}
        assert others <= excluded_types_for(relations, subject)


def test_none_subject_fail_closed_unions_competes_with_of_every_exclude_same_row():
    """F68's fail-closed None branch (docstring: 'must stay a superset of
    every KNOWN venue subject's own excluded set') has to hold even when a
    `competes_with` entry points OUTSIDE the `exclude_same=True` set --
    an edge case the real data does not exercise (eat/drink are both
    exclude_same=True) but the invariant must still hold for it."""
    relations = _relations(
        TypeRelation(type="stay", exclude_same=True, complements=(), competes_with=("weird-editorial-type",)),
        TypeRelation(type="weird-editorial-type", exclude_same=False, complements=(), competes_with=()),
    )
    excluded = excluded_types_for(relations, None)
    # Superset property: stay's own excluded_types_for(relations, "stay")
    # must be entirely contained in the fail-closed None answer.
    assert excluded_types_for(relations, "stay") <= excluded
    assert "weird-editorial-type" in excluded

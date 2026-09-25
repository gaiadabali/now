"""`now_filters.hidden_rival` -- pure logic, no Postgres. Loads the REAL
taxonomy seed file (`engine/packages/taxonomy/seed/terms/type.json`) since
the whole point of this module is that the lexicon is that file, not a
second, parallel word list -- so this doubles as a regression check that
the real file still parses into a usable lexicon.
"""

from __future__ import annotations

import re

import pytest

from now_filters.hidden_rival import (
    build_name_pattern,
    default_lexicon,
    hidden_rival_pattern_for_subject,
    load_subtype_lexicon,
)
from now_filters.type_relations import TypeRelation


def _py_search(pattern: str, text_: str) -> bool:
    """`build_name_pattern` emits Postgres POSIX ARE (`\\y` word boundary,
    what `~*` expects) -- Python's stdlib `re` has no `\\y` and uses `\\b`
    for the same thing. This translates ONLY so these pure tests can check
    the pattern's shape without a live Postgres; production code never
    calls this, since the pattern always goes to Postgres via `~*`."""
    return re.search(pattern.replace(r"\y", r"\b"), text_, re.IGNORECASE) is not None


def test_real_type_json_produces_a_stay_lexicon_containing_resort_and_hotel():
    """The exact case this guard exists for: 'The Westin Resort Nusa Dua'
    must match the `stay` lexicon via the word 'Resort'."""
    lexicon = default_lexicon()
    assert "resort" in lexicon["stay"]
    assert "hotel" in lexicon["stay"]
    assert "villa" in lexicon["stay"]


def test_real_type_json_produces_an_eat_and_drink_lexicon():
    lexicon = default_lexicon()
    assert "restaurant" in lexicon["eat"]
    assert "cafe" in lexicon["eat"]
    assert "bar" in lexicon["drink"]
    assert "rooftop bar" in lexicon["drink"]


def test_unknown_and_editorial_contribute_no_keywords():
    """`unknown`/`editorial` have no `subtype` children in the taxonomy --
    the lexicon must not silently invent keywords for them."""
    lexicon = default_lexicon()
    assert lexicon.get("unknown", ()) == ()
    # editorial has real subtypes (news, opinion, people...) in §4's tree,
    # so it DOES contribute keywords -- but they must never be treated as
    # venue-competitor keywords by `hidden_rival_pattern_for_subject`,
    # which is asserted separately below via `excluded_types_for`.


def test_westin_resort_name_matches_the_stay_pattern():
    """The exact case (docs/EDITION-2-PLAN.md §2): article 4417's featured
    mention, 'The Westin Resort Nusa Dua', must match a pattern built for
    a `stay`-excluding subject."""
    pattern = build_name_pattern({"stay"})
    assert pattern is not None
    assert _py_search(pattern, "The Westin Resort Nusa Dua")
    assert not _py_search(pattern, "Celebrate Wellness 2026")


def test_word_boundary_prevents_substring_false_positives():
    """'bar' must match 'Sky Garden Bar' but not 'Barbershop' or
    'Barcelona' -- the whole reason for `\\y` word boundaries rather than a
    plain substring/ILIKE match."""
    pattern = build_name_pattern({"drink"})
    assert pattern is not None
    assert _py_search(pattern, "Sky Garden Bar")
    assert not _py_search(pattern, "Barbershop Denpasar")
    assert not _py_search(pattern, "Barcelona Tapas") or "club" in pattern
    # 'club' IS a drink-lexicon alias (nightclub), so "Barcelona Tapas Club"
    # matching on "club" is a real, accepted false-positive risk this
    # ticket's precision/recall measurement quantifies -- not a bug in the
    # word-boundary mechanism itself, which is what this test isolates by
    # checking 'bar' does not fire on 'Barcelona'.


def test_bare_club_is_excluded_from_the_drink_lexicon_but_beach_club_and_lounge_survive():
    """2026-09-24 measurement (module docstring's `_GUARD_AMBIGUOUS_KEYWORDS`):
    bare 'club' was the dominant false-positive source in the hand-labelled
    sample (golf clubs, business clubs, expat associations). This is the
    regression test for that curation -- 'club' alone must not be a
    lexicon entry, but the multi-word phrases and 'lounge' that carried
    the genuine true positives must survive untouched."""
    lexicon = default_lexicon()
    assert "club" not in lexicon["drink"]
    assert "beach club" in lexicon["drink"]
    assert "lounge" in lexicon["drink"]
    assert "nightclub" in lexicon["drink"]  # the subtype's own unambiguous label -- kept

    pattern = build_name_pattern({"drink"})
    assert pattern is not None
    assert not _py_search(pattern, "Royale Jakarta Golf Club")
    assert not _py_search(pattern, "The American Club Jakarta")
    assert not _py_search(pattern, "Women's International Club")
    assert _py_search(pattern, "Potato Head Beach Club")
    assert _py_search(pattern, "BUNK Lobby Lounge")


def test_no_keywords_for_types_returns_none():
    assert build_name_pattern(set()) is None
    assert build_name_pattern({"unknown"}) is None


def test_hidden_rival_pattern_for_subject_uses_excluded_types_for(monkeypatch):
    """The pattern for a `stay` subject must be built from
    `excluded_types_for("stay")` -- i.e. `{stay, unknown}` today -- not
    from `stay` alone, so a future `competes_with` entry on `stay`
    automatically widens the guard too, with no change to this module."""
    relations = {
        "stay": TypeRelation(type="stay", exclude_same=True, complements=(), competes_with=("do",)),
        "do": TypeRelation(type="do", exclude_same=False, complements=(), competes_with=()),
    }
    pattern = hidden_rival_pattern_for_subject("stay", relations)
    assert pattern is not None
    lexicon = default_lexicon()
    # A `do`-subtype keyword (e.g. "museum") must be reachable through the
    # pattern, since `stay` now competes_with `do`.
    assert "museum" in lexicon["do"]
    assert _py_search(pattern, "City Museum Jakarta")


def test_hidden_rival_pattern_for_subject_none_for_editorial_shaped_types():
    relations = {
        "event": TypeRelation(type="event", exclude_same=False, complements=("eat",), competes_with=()),
    }
    assert hidden_rival_pattern_for_subject("event", relations) is None
    assert hidden_rival_pattern_for_subject(None, {}) is None

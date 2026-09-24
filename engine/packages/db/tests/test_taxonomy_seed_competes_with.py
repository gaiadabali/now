"""`competes_with` (migration 0008, Edition 2 2026-09-24) as parsed and
validated by `now_db.provisioning.load_taxonomy_seed`. Pure-logic, no
Postgres: this exercises the real seed file at
`engine/packages/taxonomy/seed/type_relations.json` plus a handful of
synthetic malformed fixtures, none of which need a database connection --
unlike `seed_city`/`seed_platform_taxonomy` (DB-integration, tested
elsewhere), the file-parsing/validation half of the taxonomy seed contract
is ordinary Python and should be checkable without Postgres reachability.
"""

from __future__ import annotations

import json

import pytest

from now_db.provisioning import TaxonomySeedError, load_taxonomy_seed

MINIMAL_FACETS = {
    "facets": [
        {"key": "type", "label": "Type", "cardinality": "single", "required": True},
        {"key": "format", "label": "Format", "cardinality": "single", "required": True},
    ]
}
MINIMAL_TYPE_TERMS = {
    "facet": "type",
    "terms": [
        {"slug": "stay", "label": "Stay"},
        {"slug": "eat", "label": "Eat"},
        {"slug": "drink", "label": "Drink"},
    ],
}
MINIMAL_FORMAT_TERMS = {
    "facet": "format",
    "terms": [{"slug": "news", "label": "News"}],
}
MINIMAL_DECAY = {
    "decay": {"formats": {"news": {"half_life_days": 14}}},
}


def _write_minimal_seed(tmp_path, relations_doc: dict) -> None:
    (tmp_path / "terms").mkdir()
    (tmp_path / "facets.json").write_text(json.dumps(MINIMAL_FACETS), encoding="utf-8")
    (tmp_path / "terms" / "type.json").write_text(json.dumps(MINIMAL_TYPE_TERMS), encoding="utf-8")
    (tmp_path / "terms" / "format.json").write_text(json.dumps(MINIMAL_FORMAT_TERMS), encoding="utf-8")
    (tmp_path / "type_relations.json").write_text(json.dumps(relations_doc), encoding="utf-8")
    (tmp_path / "format_decay.json").write_text(json.dumps(MINIMAL_DECAY), encoding="utf-8")


def test_real_seed_file_parses_eat_drink_competes_with_and_no_longer_complement():
    """The real, committed seed file: `eat`/`drink` compete, and neither
    lists the other in `complements` any more (migration 0008's data step
    mirrors this file's own eat/drink pairing change)."""
    seed = load_taxonomy_seed()
    eat_exclude_same, eat_complements, eat_competes = seed.type_relations["eat"]
    drink_exclude_same, drink_complements, drink_competes = seed.type_relations["drink"]

    assert eat_exclude_same is True
    assert drink_exclude_same is True
    assert eat_competes == ["drink"]
    assert drink_competes == ["eat"]
    assert "drink" not in eat_complements
    assert "eat" not in drink_complements
    # Nothing else in either array was touched by the competes_with change.
    assert set(eat_complements) == {"stay", "wellness", "do", "shop", "event"}
    assert set(drink_complements) == {"stay", "wellness", "do", "shop"}


def test_real_seed_file_other_types_have_empty_competes_with():
    seed = load_taxonomy_seed()
    for type_slug in ("stay", "wellness", "shop", "do", "event", "editorial"):
        _, _, competes = seed.type_relations[type_slug]
        assert competes == [], f"{type_slug} should not compete with anything"


def test_real_seed_file_unknown_type_default_has_competes_with_key():
    seed = load_taxonomy_seed()
    assert seed.unknown_type_default == (True, [], [])


def test_competes_with_referencing_unknown_type_rejected(tmp_path):
    _write_minimal_seed(
        tmp_path,
        {
            "relations": [
                {"type": "stay", "exclude_same": True, "complements": [], "competes_with": ["not-a-real-type"]},
                {"type": "eat", "exclude_same": True, "complements": [], "competes_with": []},
                {"type": "drink", "exclude_same": True, "complements": [], "competes_with": []},
            ]
        },
    )
    with pytest.raises(TaxonomySeedError, match="competes_with unknown types"):
        load_taxonomy_seed(tmp_path)


def test_type_cannot_compete_with_itself(tmp_path):
    _write_minimal_seed(
        tmp_path,
        {
            "relations": [
                {"type": "stay", "exclude_same": True, "complements": [], "competes_with": ["stay"]},
                {"type": "eat", "exclude_same": True, "complements": [], "competes_with": []},
                {"type": "drink", "exclude_same": True, "complements": [], "competes_with": []},
            ]
        },
    )
    with pytest.raises(TaxonomySeedError, match="cannot compete with itself"):
        load_taxonomy_seed(tmp_path)


def test_same_type_cannot_be_both_complement_and_competitor(tmp_path):
    """A type cannot simultaneously be whitelisted for co-recommendation
    (`complements`) and hard-excluded (`competes_with`) -- that would make
    `excluded_types_for`'s answer depend on which array the caller happened
    to consult first, which is exactly the kind of ambiguity a commercial
    guarantee (ARCHITECTURE.md Sec.8.A) cannot tolerate."""
    _write_minimal_seed(
        tmp_path,
        {
            "relations": [
                {"type": "stay", "exclude_same": True, "complements": ["eat"], "competes_with": ["eat"]},
                {"type": "eat", "exclude_same": True, "complements": [], "competes_with": []},
                {"type": "drink", "exclude_same": True, "complements": [], "competes_with": []},
            ]
        },
    )
    with pytest.raises(TaxonomySeedError, match="both complements and"):
        load_taxonomy_seed(tmp_path)


def test_competes_with_absent_defaults_to_empty_for_backward_compatibility(tmp_path):
    """A seed file written before migration 0008 (no `competes_with` key at
    all, on any relation or on `unknown_type_default`) must still load --
    absence means 'nothing', not a parse error."""
    _write_minimal_seed(
        tmp_path,
        {
            "relations": [
                {"type": "stay", "exclude_same": True, "complements": ["eat"]},
                {"type": "eat", "exclude_same": True, "complements": ["stay"]},
                {"type": "drink", "exclude_same": True, "complements": []},
            ]
        },
    )
    seed = load_taxonomy_seed(tmp_path)
    assert seed.type_relations["stay"] == (True, ["eat"], [])
    assert seed.unknown_type_default == (True, [], [])

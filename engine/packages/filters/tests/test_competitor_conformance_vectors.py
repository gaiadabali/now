"""The ONE conformance-vector file both suites assert against (Edition 2,
docs/EDITION-2-PLAN.md WS1 deliverable #3): `engine/packages/taxonomy/seed/
competitor_conformance.json`. This is the Python half; `engine/apps/web/src/
lib/__tests__/competitorPolicy.conformance.test.ts` is the TypeScript half.
Both load the SAME two files -- `type_relations.json` (the matrix) and
`competitor_conformance.json` (the (subject, candidate) -> verdict pairs) --
so a change to either the matrix or the expected policy is caught on both
sides of the engine-api / web-fallback split by construction, not by
someone remembering to update both a Python and a TS copy.

Pure logic: no Postgres. `now_db.provisioning.load_taxonomy_seed()` already
parses+validates `type_relations.json`; this test builds `TypeRelation`
objects from that parsed seed rather than a live `engine.type_relations`
table, which is the same real data city-database rows are seeded from
(see that module's docstring) -- differences from a live-migrated row
would only appear before this ticket's migration 0008 has been run
against the caller's own environment, in which case the LIVE-data test
suite (`test_type_relations.py`, DB-integration) is the one that catches it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from now_db.provisioning import TAXONOMY_SEED_DIR, load_taxonomy_seed
from now_filters.type_relations import TypeRelation, is_competitor

CONFORMANCE_PATH = TAXONOMY_SEED_DIR / "competitor_conformance.json"


def _relations_from_seed() -> dict[str, TypeRelation]:
    seed = load_taxonomy_seed()
    return {
        type_slug: TypeRelation(
            type=type_slug, exclude_same=exclude_same, complements=tuple(complements), competes_with=tuple(competes_with)
        )
        for type_slug, (exclude_same, complements, competes_with) in seed.type_relations.items()
    }


def _load_vectors() -> list[dict]:
    doc = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
    return doc["vectors"]


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: f"{v['subject_type']}_vs_{v['candidate_type']}")
def test_conformance_vector(vector: dict):
    relations = _relations_from_seed()
    got = is_competitor(relations, vector["subject_type"], vector["candidate_type"])
    assert got is vector["expect_excluded"], (
        f"subject={vector['subject_type']!r} candidate={vector['candidate_type']!r}: "
        f"expected excluded={vector['expect_excluded']}, got {got} ({vector.get('note', '')})"
    )


def test_conformance_file_is_not_empty():
    """A conformance file that failed to load silently (e.g. an empty
    `vectors` list from a bad merge) would make every parametrized case
    above vacuously pass nothing -- this is the tripwire for that."""
    assert len(_load_vectors()) >= 15

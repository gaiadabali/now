"""Integration coverage for `now_classifier.facet_tagging.db` against a
real `now_test` `engine.entity_terms` table (no FK to `now_platform`, so
arbitrary uuids are fine here -- see the table's own DDL). Covers exactly
the three guarantees the WS5 ticket asks for: idempotent re-run, clean
stale retraction, and never touching an `editor` row.
"""
from __future__ import annotations

import uuid

import pytest
from now_db.settings import city_database_url
from sqlalchemy import create_engine, text

from now_classifier.facet_tagging.db import remove_all, write_tags

TOPIC_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TOPIC_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
VIBE_X = "cccccccc-cccc-cccc-cccc-cccccccccccc"
FACET_TERM_IDS = {"topic": [TOPIC_A, TOPIC_B], "vibe": [VIBE_X]}


@pytest.fixture
def engine():
    eng = create_engine(city_database_url("now_test"))
    yield eng
    eng.dispose()


@pytest.fixture
def entity_id(engine):
    eid = str(uuid.uuid4())
    yield eid
    with engine.begin() as conn:
        conn.execute(text("delete from engine.entity_terms where entity_type='article' and entity_id=:e"), {"e": eid})


def _rows(engine, entity_id: str) -> list[tuple[str, str, float]]:
    with engine.connect() as conn:
        result = conn.execute(
            text("select term_id::text, source, confidence from engine.entity_terms "
                 "where entity_type='article' and entity_id=:e order by term_id"),
            {"e": entity_id},
        ).fetchall()
    return [(r[0], r[1], float(r[2])) for r in result]


def test_write_then_rerun_with_same_proposal_is_idempotent(engine, entity_id) -> None:
    proposals = {entity_id: {"topic": {TOPIC_A: 0.80}}}
    write_tags(engine, proposals, FACET_TERM_IDS)
    write_tags(engine, proposals, FACET_TERM_IDS)
    rows = _rows(engine, entity_id)
    assert rows == [(TOPIC_A.lower(), "inferred", 0.80)]


def test_rerun_with_fewer_proposals_retracts_the_stale_row(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80, TOPIC_B: 0.80}}}, FACET_TERM_IDS)
    assert len(_rows(engine, entity_id)) == 2

    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}}}, FACET_TERM_IDS)
    rows = _rows(engine, entity_id)
    assert rows == [(TOPIC_A.lower(), "inferred", 0.80)]


def test_rerun_with_zero_proposals_for_a_facet_retracts_everything_for_it(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}, "vibe": {VIBE_X: 0.92}}}, FACET_TERM_IDS)
    assert len(_rows(engine, entity_id)) == 2

    # This run finds nothing for `topic` any more, but still proposes `vibe`.
    write_tags(engine, {entity_id: {"topic": {}, "vibe": {VIBE_X: 0.92}}}, FACET_TERM_IDS)
    rows = _rows(engine, entity_id)
    assert rows == [(VIBE_X.lower(), "inferred", 0.92)]


def test_retraction_never_touches_a_different_facets_row(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}, "vibe": {VIBE_X: 0.92}}}, FACET_TERM_IDS)
    # Re-run only reconciles `topic` this time (vibe key absent) -- the
    # vibe row must survive untouched.
    write_tags(engine, {entity_id: {"topic": {}}}, FACET_TERM_IDS)
    rows = _rows(engine, entity_id)
    assert rows == [(VIBE_X.lower(), "inferred", 0.92)]


def test_editor_row_is_never_overwritten_or_retracted(engine, entity_id) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence) "
                 "values ('article', :e, cast(:t as uuid), 1.0, 'editor', 1.0)"),
            {"e": entity_id, "t": TOPIC_A},
        )
    # This run tries to write a DIFFERENT value AND tries to propose nothing
    # (which would otherwise retract) -- the editor row must survive both.
    write_tags(engine, {entity_id: {"topic": {}}}, FACET_TERM_IDS)
    rows = _rows(engine, entity_id)
    assert rows == [(TOPIC_A.lower(), "editor", 1.0)]


def test_dry_run_writes_nothing(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}}}, FACET_TERM_IDS, dry_run=True)
    assert _rows(engine, entity_id) == []


def test_remove_all_deletes_only_inferred_rows_for_the_given_term_ids(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}, "vibe": {VIBE_X: 0.92}}}, FACET_TERM_IDS)
    n = remove_all(engine, [TOPIC_A])
    assert n == 1
    rows = _rows(engine, entity_id)
    assert rows == [(VIBE_X.lower(), "inferred", 0.92)]


def test_remove_all_dry_run_counts_without_deleting(engine, entity_id) -> None:
    write_tags(engine, {entity_id: {"topic": {TOPIC_A: 0.80}}}, FACET_TERM_IDS)
    n = remove_all(engine, [TOPIC_A], dry_run=True)
    assert n == 1
    assert len(_rows(engine, entity_id)) == 1

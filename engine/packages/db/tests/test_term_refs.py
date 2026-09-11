"""F92 (PROGRESS.md): `now_db.term_refs.find_orphaned_term_refs` against
the real local databases (`now_test` + `now_platform`), same pattern
`platform-db`'s `test_partnerships_expiry.py` uses and for the same
reason — this proves DB-level behavior (real cross-database uuid
comparison against real `information_schema` introspection), not Python
logic a mock could stand in for.

Every test wraps its work in a transaction rolled back in fixture
teardown, so this suite never leaves rows behind in `now_test` or
`now_platform` regardless of pass/fail.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from now_db.settings import city_database_url
from now_db.term_refs import find_orphaned_term_refs, format_orphan_report, has_live_orphans


@pytest.fixture
def platform_conn():
    from now_platform_db.settings import platform_database_url

    engine = create_engine(platform_database_url())
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def city_conn():
    engine = create_engine(city_database_url("now_test"))
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def real_term_id(platform_conn):
    """A genuine `now_platform.engine.terms.id` -- any seeded term will do."""
    row = platform_conn.execute(text("SELECT id FROM engine.terms LIMIT 1")).first()
    assert row is not None, "expected at least one seeded term in now_platform.engine.terms"
    return str(row[0])


class TestFindOrphanedTermRefs:
    def test_clean_city_reports_nothing(self, city_conn, platform_conn, real_term_id):
        """A term_id that genuinely exists in the platform vocabulary is not orphaned."""
        city_conn.execute(
            text(
                "INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, source, confidence) "
                "VALUES ('article', 'test-clean-1', CAST(:term_id AS uuid), 'ai', 0.9)"
            ),
            {"term_id": real_term_id},
        )
        orphans = find_orphaned_term_refs(city_conn, platform_conn)
        assert orphans == []

    def test_orphaned_entity_terms_row_is_detected(self, city_conn, platform_conn):
        """A term_id with no matching platform row IS reported, and marked live."""
        fake_term_id = str(uuid.uuid4())
        city_conn.execute(
            text(
                "INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, source, confidence) "
                "VALUES ('place', 'test-orphan-1', CAST(:term_id AS uuid), 'ai', 0.4)"
            ),
            {"term_id": fake_term_id},
        )
        orphans = find_orphaned_term_refs(city_conn, platform_conn)
        assert len(orphans) == 1
        assert orphans[0].term_id == fake_term_id
        assert orphans[0].source == "engine.entity_terms.term_id"
        assert orphans[0].live is True
        assert orphans[0].row_count == 1
        assert has_live_orphans(orphans) is True

    def test_orphaned_embeddings_term_row_is_detected(self, city_conn, platform_conn):
        """The exact shape of the real, pre-existing bug this ticket found live in
        now_jakarta: engine.embeddings entity_type='term' pointing at a
        deleted platform term (pruning is deliberately disabled for
        entity_type='term' -- see now_embeddings/cli.py)."""
        fake_term_id = str(uuid.uuid4())
        fake_vec = "[" + ",".join(["0.001"] * 384) + "]"  # engine.embeddings.vec is vector(384)
        city_conn.execute(
            text(
                "INSERT INTO engine.embeddings (entity_type, entity_id, model, dim, text_hash, vec) "
                "VALUES ('term', :term_id, 'test-model', 384, 'deadbeef', :vec)"
            ),
            {"term_id": fake_term_id, "vec": fake_vec},
        )
        orphans = find_orphaned_term_refs(city_conn, platform_conn)
        assert len(orphans) == 1
        assert orphans[0].source == "engine.embeddings.entity_id (entity_type='term')"
        assert orphans[0].live is True

    def test_missing_public_schema_is_skipped_not_errored(self, city_conn, platform_conn):
        """now_test has no Payload `public` schema at all (only PostGIS's
        spatial_ref_sys) -- classification_reviews must be skipped, not raise."""
        # No fixture rows needed: the assertion is simply that this does not raise.
        orphans = find_orphaned_term_refs(city_conn, platform_conn)
        assert orphans == []

    def test_format_orphan_report_distinguishes_live_from_historical(self):
        from now_db.term_refs import OrphanedTermRef

        live = OrphanedTermRef(term_id="a", source="engine.entity_terms.term_id", live=True, entity_label="article", row_count=1, sample=["x"])
        historical = OrphanedTermRef(term_id="b", source="public.classification_reviews.term_id", live=False, entity_label="place", row_count=2, sample=["y", "z"])

        lines = format_orphan_report("now_example", [live, historical])
        joined = "\n".join(lines)
        assert "1 live" in joined
        assert "1 historical" in joined
        assert "[LIVE]" in joined
        assert "[historical]" in joined
        assert has_live_orphans([historical]) is False
        assert has_live_orphans([live, historical]) is True

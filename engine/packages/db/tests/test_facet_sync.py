"""F132 self-test: `now_db.facet_sync.find_facet_drift` must actually
detect the two shapes of drift found live in `now_jakarta`/`now_bali`
(see PROGRESS.md F132 and `now_classifier.db`'s module docstring) --
`articles.primary_type`/`.format` disagreeing with `engine.entity_terms`,
and `articles` carrying a value with no corresponding `entity_terms` row
at all. Proven against a real `now_test` scratch schema (the same
faithful `public` schema subset `now_eval`'s LLM-apply tests and
`now_classifier`'s F132 regression tests use), not a mock -- this is a
DB-introspection check (real enum casts, a real cross-database join
against `now_platform`), exactly like `test_term_refs.py` next to it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from now_db.facet_sync import find_facet_drift, format_facet_drift_report, has_facet_drift
from now_db.settings import city_database_url

from _scratch_public_schema import create_scratch_public_schema, drop_scratch_public_schema


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(city_database_url("now_test"))
    create_scratch_public_schema(eng)
    try:
        yield eng
    finally:
        drop_scratch_public_schema(eng)
        eng.dispose()


@pytest.fixture
def platform_conn():
    from now_platform_db.settings import platform_database_url

    pg_engine = create_engine(platform_database_url())
    connection = pg_engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
        pg_engine.dispose()


@pytest.fixture
def real_type_term(platform_conn):
    """(uuid, slug) for a real `type`-facet platform term."""
    row = platform_conn.execute(
        text(
            "select t.id::text, t.slug from engine.terms t "
            "join engine.facets f on f.id = t.facet_id "
            "where f.key = 'type' order by t.slug limit 1"
        )
    ).first()
    assert row is not None, "expected at least one seeded `type` term in now_platform"
    return str(row[0]), row[1]


@pytest.fixture
def real_type_term_alt(platform_conn, real_type_term):
    """A SECOND, different `type`-facet term -- for the 'disagree' case."""
    row = platform_conn.execute(
        text(
            "select t.id::text, t.slug from engine.terms t "
            "join engine.facets f on f.id = t.facet_id "
            "where f.key = 'type' and t.slug <> :exclude order by t.slug limit 1"
        ),
        {"exclude": real_type_term[1]},
    ).first()
    assert row is not None, "expected at least two distinct `type` terms in now_platform"
    return str(row[0]), row[1]


@pytest.fixture
def article_row(engine):
    with engine.begin() as conn:
        article_id = conn.execute(
            text("insert into articles (title, legacy_wp_id) values ('F132 facet_sync self-test', :wp) returning id"),
            {"wp": 900101},
        ).scalar_one()
    yield article_id
    with engine.begin() as conn:
        conn.execute(text("delete from articles where id = :id"), {"id": article_id})
        conn.execute(
            text("delete from engine.entity_terms where entity_type='article' and entity_id = :id"),
            {"id": str(article_id)},
        )


class TestFindFacetDrift:
    def test_clean_state_reports_no_drift(self, engine, platform_conn, article_row, real_type_term):
        term_id, slug = real_type_term
        with engine.begin() as conn:
            conn.execute(text(f"update articles set primary_type = '{slug}' where id = :id"), {"id": article_row})
            conn.execute(
                text(
                    "insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence) "
                    "values ('article', :eid, cast(:tid as uuid), 1.0, 'ai', 0.9)"
                ),
                {"eid": str(article_row), "tid": term_id},
            )
        with engine.connect() as city_conn:
            groups = find_facet_drift(city_conn, platform_conn)
        assert groups == []
        assert has_facet_drift(groups) is False

    def test_detects_a_disagreeing_value(self, engine, platform_conn, article_row, real_type_term, real_type_term_alt):
        articles_term_id, articles_slug = real_type_term
        entity_terms_id, _entity_slug = real_type_term_alt
        with engine.begin() as conn:
            conn.execute(text("update articles set primary_type = :slug where id = :id"),
                         {"slug": articles_slug, "id": article_row})
            conn.execute(
                text(
                    "insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence) "
                    "values ('article', :eid, cast(:tid as uuid), 1.0, 'ai', 0.9)"
                ),
                {"eid": str(article_row), "tid": entity_terms_id},
            )
        with engine.connect() as city_conn:
            groups = find_facet_drift(city_conn, platform_conn)

        assert has_facet_drift(groups) is True
        disagree = [g for g in groups if g.facet == "type" and g.kind == "disagree"]
        assert len(disagree) == 1
        assert disagree[0].count == 1
        assert "900101" in disagree[0].sample_legacy_wp_ids
        report = format_facet_drift_report("now_test", groups)
        assert any("disagree" in line for line in report)

    def test_detects_a_missing_entity_terms_row(self, engine, platform_conn, article_row, real_type_term):
        _term_id, slug = real_type_term
        with engine.begin() as conn:
            conn.execute(text("update articles set primary_type = :slug where id = :id"),
                         {"slug": slug, "id": article_row})
            # Deliberately NO engine.entity_terms row -- the "downgraded to
            # review, retracted" shape (F132's 924 live rows).

        with engine.connect() as city_conn:
            groups = find_facet_drift(city_conn, platform_conn)

        assert has_facet_drift(groups) is True
        missing = [g for g in groups if g.facet == "type" and g.kind == "missing_entity_terms_row"]
        assert len(missing) == 1
        assert missing[0].count == 1
        assert "900101" in missing[0].sample_legacy_wp_ids

    def test_skips_cities_with_no_public_articles_table(self, platform_conn):
        """`now_test` without the scratch schema applied has no
        `public.articles` at all (its normal, real shape) -- must not
        error, must return clean/empty."""
        from sqlalchemy import create_engine as _create_engine

        eng = _create_engine(city_database_url("now_test"))
        with eng.connect() as conn:
            # Confirm the precondition this test relies on: no scratch
            # schema is active for THIS connection's view (module-scoped
            # `engine` fixture above is a different engine/connection, but
            # since the scratch schema is real DDL in the same database,
            # skip this assertion if some other test module left it up).
            exists = conn.execute(
                text("select 1 from information_schema.tables where table_schema='public' and table_name='articles'")
            ).first()
        eng.dispose()
        if exists:
            pytest.skip("public.articles exists in now_test (another test module's scratch schema is active)")
        with _create_engine(city_database_url("now_test")).connect() as city_conn:
            groups = find_facet_drift(city_conn, platform_conn)
        assert groups == []

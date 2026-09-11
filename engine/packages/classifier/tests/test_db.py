"""F132 regression coverage: `now_classifier.db.write_results` must write
ONE classification decision to `public.articles.primary_type`/`.format`
AND `engine.entity_terms` atomically -- the two stores disagreeing
(~1,795 live rows, plus 924 with no `entity_terms` row at all) was the
actual bug (see `db.py`'s F132 module docstring for the root cause).

Against `now_test` (real DB, real transaction, real enums) -- not a mock
-- using the same faithful `public` schema subset + real platform
vocabulary pattern `now_eval`'s `apply_llm_labels` integration tests
already established for the identical "no provenance column" problem.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from now_classifier.db import WriteStats, write_results
from now_classifier.resolve import ClassificationResult, FacetDecision
from now_classifier.vocabulary import load_term_index, term_uuid
from now_db.settings import city_database_url

from _scratch_public_schema import (
    create_scratch_public_schema,
    drop_scratch_public_schema,
    wipe_engine_entity_terms_for_test_entities,
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(city_database_url("now_test"))
    create_scratch_public_schema(eng)
    try:
        yield eng
    finally:
        drop_scratch_public_schema(eng)
        eng.dispose()


@pytest.fixture(scope="module")
def terms():
    return load_term_index()


@pytest.fixture
def article(engine):
    """One fresh `public.articles` row per test, cleaned up (with its
    `entity_terms` rows) at teardown regardless of pass/fail -- leaves no
    fixtures in `now_test` (F87/F91)."""
    with engine.begin() as conn:
        article_id = conn.execute(
            text("insert into articles (title, legacy_wp_id) values ('F132 test article', :wp) returning id"),
            {"wp": 900001},
        ).scalar_one()
    yield article_id
    with engine.begin() as conn:
        conn.execute(
            text("delete from classification_reviews where id in "
                 "(select parent_id from classification_reviews_rels where articles_id = :id)"),
            {"id": article_id},
        )
        conn.execute(text("delete from classification_reviews_rels where articles_id = :id"), {"id": article_id})
        conn.execute(text("delete from articles where id = :id"), {"id": article_id})
    wipe_engine_entity_terms_for_test_entities(engine, [str(article_id)])


def _result(wp_id: int, type_value: str, type_conf: float = 0.95, type_source: str = "ai",
            format_value: str = "feature", format_conf: float = 0.95) -> ClassificationResult:
    return ClassificationResult(
        wp_id=wp_id,
        category_method="test",
        category_name="Test",
        category_ambiguous=False,
        type=FacetDecision("type", type_value, type_conf, type_source, "test reasoning"),
        subtype=FacetDecision("subtype", "unknown", 0.0, "inferred", "test reasoning"),
        format=FacetDecision("format", format_value, format_conf, "ai", "test reasoning"),
        locations=[],
    )


def _fetch_articles_facets(engine, article_id):
    with engine.connect() as conn:
        row = conn.execute(
            text("select primary_type::text, format::text from articles where id = :id"), {"id": article_id}
        ).fetchone()
    return row[0], row[1]


def _fetch_entity_term_value(engine, terms, article_id, facet_key):
    all_ids = [uuid_ for uuid_, _parent in terms.by_facet.get(facet_key, {}).values()]
    slug_by_uuid = {uuid_.lower(): slug for slug, (uuid_, _parent) in terms.by_facet.get(facet_key, {}).items()}
    with engine.connect() as conn:
        row = conn.execute(
            text("select term_id::text from engine.entity_terms where entity_type='article' "
                 "and entity_id=:eid and term_id = any(cast(:tids as uuid[]))"),
            {"eid": str(article_id), "tids": all_ids},
        ).fetchone()
    if row is None:
        return None
    return slug_by_uuid.get(row[0].lower())


class TestWriteResultsF132Sync:
    def test_first_write_syncs_both_stores(self, engine, terms, article):
        """The common case: articles is NULL, this is the article's first
        classification -- both stores must land on the SAME value."""
        r = _result(900001, "wellness")
        stats = write_results(engine, {900001: article}, [r], terms, site_slug="test")

        primary_type, fmt = _fetch_articles_facets(engine, article)
        assert primary_type == "wellness"
        assert fmt == "feature"
        assert _fetch_entity_term_value(engine, terms, article, "type") == "wellness"
        assert _fetch_entity_term_value(engine, terms, article, "format") == "feature"
        assert stats.articles_facets_synced == 2
        assert stats.articles_facet_drift_skipped == 0

    def test_reclassification_moves_articles_together_with_entity_terms(self, engine, terms, article):
        """This is the actual F132 bug: a SECOND run (e.g. F125's routing
        re-classification) proposing a DIFFERENT value for an
        already-classified article must update `articles` too, not just
        `entity_terms`. Before the fix, `articles.primary_type` stayed
        'wellness' forever (`coalesce(primary_type, ...)`) while
        `entity_terms` moved on to 'editorial' -- exactly the wp11 sample
        F132 reported live."""
        write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")

        stats = write_results(engine, {900001: article}, [_result(900001, "editorial")], terms, site_slug="test")

        primary_type, _fmt = _fetch_articles_facets(engine, article)
        assert primary_type == "editorial", (
            "articles.primary_type must move with entity_terms on a re-run -- "
            "this is the exact F132 defect (stores writable independently)"
        )
        assert _fetch_entity_term_value(engine, terms, article, "type") == "editorial"
        assert stats.articles_facet_drift_skipped == 0

    def test_downgrade_to_review_retracts_articles_value_too(self, engine, terms, article):
        """F132's other face: 924 live articles carry a `primary_type` with
        NO corresponding `entity_terms` row because a later run downgraded
        the facet to review (F125's stale-retraction fix deletes the
        entity_terms row) but `articles` had no retraction path at all.
        Going forward, a downgrade must retract `articles` too."""
        write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")

        low_conf = ClassificationResult(
            wp_id=900001, category_method="test", category_name="Test", category_ambiguous=False,
            type=FacetDecision("type", "wellness", 0.40, "inferred", "abstain, low confidence"),
            subtype=FacetDecision("subtype", "unknown", 0.0, "inferred", "test"),
            format=FacetDecision("format", "feature", 0.95, "ai", "test"),
            locations=[],
        )
        stats = write_results(engine, {900001: article}, [low_conf], terms, site_slug="test")

        primary_type, _fmt = _fetch_articles_facets(engine, article)
        assert primary_type is None, "articles must not keep a value entity_terms has retracted"
        assert _fetch_entity_term_value(engine, terms, article, "type") is None
        assert stats.type_reviewed == 1

    def test_editor_owned_entity_term_protects_articles_from_being_overwritten(self, engine, terms, article):
        """F86's guarantee, extended to this write path: if `entity_terms`
        already carries a human (`editor`-sourced) decision for a facet,
        a re-run must never treat `articles` as safely machine-owned and
        must not touch it, even if a fresh, different value clears the
        gate."""
        write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")
        # Simulate an editor decision landing in entity_terms (as engine-worker/CMS would).
        wellness_uuid = term_uuid(terms, "type", "wellness")
        with engine.begin() as conn:
            conn.execute(
                text("update engine.entity_terms set source='editor' where entity_type='article' "
                     "and entity_id=:eid and term_id=cast(:tid as uuid)"),
                {"eid": str(article), "tid": wellness_uuid},
            )

        stats = write_results(engine, {900001: article}, [_result(900001, "editorial")], terms, site_slug="test")

        primary_type, _fmt = _fetch_articles_facets(engine, article)
        assert primary_type == "wellness", "an editor-owned entity_terms row must block the articles write"
        assert stats.articles_facet_drift_skipped >= 1

    def test_preexisting_drift_is_detected_and_articles_left_untouched(self, engine, terms, article):
        """The reconciliation-relevant case: if `articles` and
        `entity_terms` ALREADY disagree (this ticket's own live defect,
        pre-fix) a re-run must not silently guess which one is right --
        it must leave `articles` alone and count the drift."""
        write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")
        # Force the exact drifted shape found live: articles says one thing,
        # entity_terms already says another (as if an earlier buggy run, or
        # a genuine CMS edit, had already diverged them).
        with engine.begin() as conn:
            conn.execute(text("update articles set primary_type = 'do' where id = :id"), {"id": article})

        stats = write_results(engine, {900001: article}, [_result(900001, "editorial")], terms, site_slug="test")

        primary_type, _fmt = _fetch_articles_facets(engine, article)
        assert primary_type == "do", "a pre-existing drift must not be silently overwritten by a guess"
        assert stats.articles_facet_drift_skipped >= 1
        # entity_terms is still the freshest decision -- downstream facet
        # queries/F131/F133 must see the up-to-date value even while the
        # articles-side drift awaits human/reconciliation attention.
        assert _fetch_entity_term_value(engine, terms, article, "type") == "editorial"

    def test_idempotent_rerun_with_same_value_is_a_no_op_on_articles(self, engine, terms, article):
        write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")
        stats = write_results(engine, {900001: article}, [_result(900001, "wellness")], terms, site_slug="test")
        primary_type, _fmt = _fetch_articles_facets(engine, article)
        assert primary_type == "wellness"
        # Same value proposed again: in sync, and the combined UPDATE is a
        # same-value no-op (not asserted at the SQL level here, just that
        # nothing drifts and nothing is flagged).
        assert stats.articles_facet_drift_skipped == 0

    def test_dry_run_never_writes_to_either_store(self, engine, terms, article):
        stats = write_results(engine, {900001: article}, [_result(900001, "wellness")], terms,
                               site_slug="test", dry_run=True)
        primary_type, fmt = _fetch_articles_facets(engine, article)
        assert primary_type is None
        assert fmt is None
        assert _fetch_entity_term_value(engine, terms, article, "type") is None
        assert isinstance(stats, WriteStats)
        assert stats.type_accepted == 1  # stats are still computed in dry-run

"""Real-DB integration + attack tests for the LLM-batch apply step (Wave 18
T3), against `now_test` (a scratch/CI database, never `now_jakarta`/
`now_bali` -- see `test_apply_llm_labels_readonly.py` for the live-city
read-only proof).

Stands up a faithful SUBSET of the Payload `public` schema in `now_test`
(`_scratch_public_schema.py`, copied verbatim from the real migrations)
because `now_test` today carries only the alembic `engine` schema. The
fixture creates it once per test module and drops it at teardown --
`now_test` is left exactly as found, per this ticket's "leave no fixtures
in any table" requirement (F87/F91).

Real platform vocabulary is read from `now_platform` (read-only, via
`now_classifier.vocabulary.load_term_index`) -- this is the shared term
vocabulary DB every classifier/eval component already depends on, not one
of the two live CITY databases this ticket restricts.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# `now_classifier` ships only with the `calibration` extra, and CI's eval job
# installs `--extra dev` alone (the harness gate is meant to need no DB). This
# module is a DB-integration test of the calibration path, so without the
# extra it skips like the package's other DB tests rather than failing
# collection and taking the whole suite down with it.
pytest.importorskip("now_classifier")

from now_classifier.vocabulary import load_term_index, term_uuid  # noqa: E402
from now_db.settings import city_database_url

from now_eval.calibration.apply_llm_labels import (
    LLM_BATCH_CONFIDENCE,
    LLM_BATCH_SOURCE,
    RefusedLiveWriteError,
    apply_change,
    run_apply,
)

from _scratch_public_schema import (
    create_scratch_public_schema,
    drop_scratch_public_schema,
    wipe_engine_entity_terms_for_test_entities,
)

CITY = "testcity"  # deliberately not "jakarta"/"bali" -- keeps these tests visibly separate
                    # from anything LIVE_CITY_DBS cares about.


@pytest.fixture(scope="module")
def engine():
    # A DB-integration module: with no reachable `now_test` (CI's eval job has
    # no Postgres) it skips rather than erroring, the same contract as the
    # `now_classifier` import guard above.
    eng = create_engine(city_database_url("now_test"), connect_args={"connect_timeout": 5})
    try:
        with eng.connect():
            pass
    except OperationalError as exc:
        eng.dispose()
        pytest.skip(f"now_test database not reachable ({exc.__class__.__name__})")
    create_scratch_public_schema(eng)
    try:
        yield eng
    finally:
        drop_scratch_public_schema(eng)
        eng.dispose()


@pytest.fixture(scope="module")
def terms():
    try:
        return load_term_index()
    except OperationalError as exc:
        pytest.skip(f"platform vocabulary not reachable ({exc.__class__.__name__})")


@pytest.fixture
def cleanup(engine):
    """Per-test cleanup: every article/entity_terms row a test creates is
    tracked here and deleted at teardown, regardless of pass/fail."""
    article_ids: list[int] = []
    entity_ids: list[str] = []
    yield article_ids, entity_ids
    with engine.begin() as conn:
        if article_ids:
            conn.execute(text("delete from classification_reviews_rels where articles_id = any(:ids)"), {"ids": article_ids})
            conn.execute(text("delete from classification_reviews where id in "
                               "(select parent_id from classification_reviews_rels where articles_id = any(:ids))"),
                         {"ids": article_ids})
            conn.execute(text("delete from articles where id = any(:ids)"), {"ids": article_ids})
    wipe_engine_entity_terms_for_test_entities(engine, entity_ids)


def _insert_article(engine, article_ids, wp_id: int, primary_type: str | None, fmt: str | None) -> int:
    with engine.begin() as conn:
        article_id = conn.execute(
            text(
                "insert into articles (title, legacy_wp_id, primary_type, format) "
                "values (:t, :wp, cast(:pt as enum_articles_primary_type), cast(:fmt as enum_articles_format)) "
                "returning id"
            ),
            {"t": f"test article {wp_id}", "wp": wp_id, "pt": primary_type, "fmt": fmt},
        ).scalar_one()
    article_ids.append(article_id)
    return article_id


def _insert_entity_term(engine, entity_ids, article_id: int, term_id: str, source: str, confidence: float) -> None:
    entity_id = str(article_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                "insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence) "
                "values ('article', :eid, cast(:tid as uuid), 1.0, :source, :confidence)"
            ),
            {"eid": entity_id, "tid": term_id, "source": source, "confidence": confidence},
        )
    if entity_id not in entity_ids:
        entity_ids.append(entity_id)


def _insert_decided_review(engine, article_ids, article_id: int) -> int:
    """A human-decided classification_reviews row (source='editor',
    review_state != 'pending') -- the exact shape F86's trigger protects."""
    with engine.begin() as conn:
        review_id = conn.execute(
            text(
                "insert into classification_reviews "
                "(entity_type, facet_key, proposed_value, confidence, reasoning, source, review_state, final_value) "
                "values ('article', 'type', 'stay', 0.75, 'human decided this', 'editor', 'accepted', 'stay') "
                "returning id"
            )
        ).scalar_one()
        conn.execute(
            text("insert into classification_reviews_rels (parent_id, path, articles_id, \"order\") "
                 "values (:pid, 'entity', :aid, 0)"),
            {"pid": review_id, "aid": article_id},
        )
    return review_id


def _write_ledger(tmp_path: Path, city: str, records: list[dict]) -> Path:
    ledger_dir = tmp_path / "llm_batch"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{city}_llm_labels.full.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return ledger_dir


def _entity_terms_rows(engine, article_id: int) -> list[tuple]:
    with engine.connect() as conn:
        return conn.execute(
            text("select term_id::text, source, confidence from engine.entity_terms "
                 "where entity_type='article' and entity_id=:eid"),
            {"eid": str(article_id)},
        ).fetchall()


def _articles_row(engine, article_id: int) -> tuple:
    with engine.connect() as conn:
        return conn.execute(
            text("select primary_type::text, format::text from articles where id=:id"),
            {"id": article_id},
        ).fetchone()


# --------------------------------------------------------------------------
# End-to-end dry-run + execute + idempotency
# --------------------------------------------------------------------------

class TestEndToEnd:
    def test_dry_run_then_execute_then_idempotent_second_run(self, engine, terms, tmp_path, cleanup):
        article_ids, entity_ids = cleanup
        news_id = term_uuid(terms, "format", "news")
        feature_id = term_uuid(terms, "format", "feature")
        assert news_id and feature_id

        wp_id = 900101
        article_id = _insert_article(engine, article_ids, wp_id, primary_type=None, fmt="news")
        # category_fixed_high band for format (0.560) -- low-accuracy, replaceable.
        _insert_entity_term(engine, entity_ids, article_id, news_id, "ai", 0.560)

        ledger_dir = _write_ledger(tmp_path, CITY, [
            {"city": CITY, "wp_id": wp_id, "type": None, "format": "feature",
             "type_reasoning": "", "format_reasoning": "reads as evergreen long-form, not news"},
        ])

        # --- dry run: plans the change, writes nothing ---
        report = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                            engine_factory=lambda ref: engine, dry_run=True)
        matching = [p for p in report.planned if p.wp_id == wp_id and p.facet == "format"]
        assert len(matching) == 1
        assert matching[0].old_slug == "news" and matching[0].new_slug == "feature"
        assert matching[0].band == "category_fixed_high"

        rows = _entity_terms_rows(engine, article_id)
        assert len(rows) == 1 and rows[0][0] == news_id and rows[0][1] == "ai"
        assert _articles_row(engine, article_id) == (None, "news")

        # --- execute: writes exactly this one change ---
        report2 = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                             engine_factory=lambda ref: engine, dry_run=False)
        applied_ok = [a for a in report2.applied if a.ok and a.change.wp_id == wp_id]
        assert len(applied_ok) == 1

        rows_after = _entity_terms_rows(engine, article_id)
        assert len(rows_after) == 1
        assert rows_after[0][0] == feature_id
        assert rows_after[0][1] == LLM_BATCH_SOURCE
        assert float(rows_after[0][2]) == LLM_BATCH_CONFIDENCE
        assert _articles_row(engine, article_id) == (None, "feature")

        # --- idempotency: a second execute run is a no-op ---
        report3 = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                             engine_factory=lambda ref: engine, dry_run=False)
        matching3 = [p for p in report3.planned if p.wp_id == wp_id]
        assert matching3 == []  # confidence is now the sentinel -- band_for_confidence finds nothing
        skip3 = [s for s in report3.skipped if s.wp_id == wp_id and s.facet == "format"]
        assert len(skip3) == 1 and skip3[0].reason == "unrecognized_provenance"

        rows_final = _entity_terms_rows(engine, article_id)
        assert rows_final == rows_after  # byte-identical to after the first execute
        assert _articles_row(engine, article_id) == (None, "feature")

    def test_type_band_above_threshold_is_left_alone_even_on_disagreement(self, engine, terms, tmp_path, cleanup):
        article_ids, entity_ids = cleanup
        stay_id = term_uuid(terms, "type", "stay")
        eat_id = term_uuid(terms, "type", "eat")
        assert stay_id and eat_id

        wp_id = 900102
        article_id = _insert_article(engine, article_ids, wp_id, primary_type="stay", fmt=None)
        # cue_confident band for type = 0.840 -- a KEEP band (>= 0.70 threshold).
        _insert_entity_term(engine, entity_ids, article_id, stay_id, "ai", 0.840)

        ledger_dir = _write_ledger(tmp_path, CITY, [
            {"city": CITY, "wp_id": wp_id, "type": "eat", "format": None},
        ])
        report = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                            engine_factory=lambda ref: engine, dry_run=False)
        assert [p for p in report.planned if p.wp_id == wp_id] == []
        skip = [s for s in report.skipped if s.wp_id == wp_id and s.facet == "type"]
        assert len(skip) == 1 and skip[0].reason == "not_low_accuracy_band"

        rows = _entity_terms_rows(engine, article_id)
        assert rows[0][0] == stay_id  # unchanged
        assert _articles_row(engine, article_id) == ("stay", None)


# --------------------------------------------------------------------------
# Attack tests the ticket names explicitly
# --------------------------------------------------------------------------

class TestAttacks:
    def test_editor_sourced_entity_terms_row_survives_an_apply(self, engine, terms, tmp_path, cleanup):
        article_ids, entity_ids = cleanup
        news_id = term_uuid(terms, "format", "news")
        wp_id = 900201
        article_id = _insert_article(engine, article_ids, wp_id, primary_type=None, fmt="news")
        _insert_entity_term(engine, entity_ids, article_id, news_id, "editor", 0.560)

        ledger_dir = _write_ledger(tmp_path, CITY, [
            {"city": CITY, "wp_id": wp_id, "type": None, "format": "feature"},
        ])
        report = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                            engine_factory=lambda ref: engine, dry_run=False)

        skip = [s for s in report.skipped if s.wp_id == wp_id and s.facet == "format"]
        assert len(skip) == 1 and skip[0].reason == "editor_sourced_present"

        rows = _entity_terms_rows(engine, article_id)
        assert len(rows) == 1
        assert rows[0][0] == news_id and rows[0][1] == "editor" and float(rows[0][2]) == 0.560
        assert _articles_row(engine, article_id) == (None, "news")  # articles column untouched too

    def test_non_pending_classification_reviews_row_survives(self, engine, terms, tmp_path, cleanup):
        article_ids, entity_ids = cleanup
        news_id = term_uuid(terms, "format", "news")
        wp_id = 900202
        article_id = _insert_article(engine, article_ids, wp_id, primary_type="stay", fmt="news")
        _insert_entity_term(engine, entity_ids, article_id, news_id, "ai", 0.560)  # a real, unrelated replaceable fact
        review_id = _insert_decided_review(engine, article_ids, article_id)

        with engine.connect() as conn:
            before = conn.execute(text("select * from classification_reviews where id=:id"), {"id": review_id}).mappings().one()

        ledger_dir = _write_ledger(tmp_path, CITY, [
            {"city": CITY, "wp_id": wp_id, "type": None, "format": "feature"},
        ])
        report = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                            engine_factory=lambda ref: engine, dry_run=False)
        # the format fact was in fact replaced (proves this isn't vacuous)
        assert any(a.ok and a.change.wp_id == wp_id for a in report.applied)

        with engine.connect() as conn:
            after = conn.execute(text("select * from classification_reviews where id=:id"), {"id": review_id}).mappings().one()
        assert dict(before) == dict(after)  # byte-for-byte unchanged

        # and the trigger itself still rejects a realistic automated-writer
        # clobber attempt, proving this isn't "unchanged because we got
        # lucky" -- F86 remains live in this scratch schema. Per F86's own
        # documented design, the trigger fires on `NEW.source IS DISTINCT
        # FROM 'editor'` -- i.e. it catches a writer whose UPDATE (like every
        # real automated writer in this codebase) itself asserts a non-editor
        # `source` (defaulting to 'ai'), the same shape QA.6/F86's own
        # verification exercises. A hand-written UPDATE that surgically
        # omits `source` from its SET list leaves NEW.source unchanged
        # (still 'editor') and does not trip this particular guard -- a
        # known, documented narrowness of F86's own trigger (see its
        # migration docstring), not something this ticket's writer relies
        # on or is trying to re-prove exhaustively.
        with pytest.raises(Exception) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    text("update classification_reviews set proposed_value='drink', source='ai' where id=:id"),
                    {"id": review_id},
                )
        assert "restrict_violation" in str(excinfo.value).lower() or "F86" in str(excinfo.value)

    def test_concurrent_editor_decision_after_planning_is_detected_not_clobbered(self, engine, terms, tmp_path, cleanup):
        """Simulates the exact race `docs/llm-batch-apply-design.md` calls
        out: a live editor decision lands on `entity_terms` AFTER this
        batch already planned a replacement but BEFORE `apply_change`
        actually writes. `apply_change`'s own `SELECT ... FOR UPDATE`
        re-check must catch it and refuse, not silently overwrite."""
        article_ids, entity_ids = cleanup
        news_id = term_uuid(terms, "format", "news")
        feature_id = term_uuid(terms, "format", "feature")
        wp_id = 900203
        article_id = _insert_article(engine, article_ids, wp_id, primary_type=None, fmt="news")
        _insert_entity_term(engine, entity_ids, article_id, news_id, "ai", 0.560)

        ledger_dir = _write_ledger(tmp_path, CITY, [
            {"city": CITY, "wp_id": wp_id, "type": None, "format": "feature"},
        ])
        # plan (dry run) -- captures the PlannedChange as of BEFORE the race
        report = run_apply((CITY,), ledger_dir, terms, city_db_map={CITY: "now_test"},
                            engine_factory=lambda ref: engine, dry_run=True)
        change = next(p for p in report.planned if p.wp_id == wp_id)

        # the race: a real editor decision lands between planning and applying
        with engine.begin() as conn:
            conn.execute(
                text("update engine.entity_terms set source='editor', confidence=1.0 "
                     "where entity_type='article' and entity_id=:eid and term_id=cast(:tid as uuid)"),
                {"eid": str(article_id), "tid": news_id},
            )

        from now_eval.calibration.apply_llm_labels import _facet_term_ids
        result = apply_change(engine, change, _facet_term_ids(terms, "format"))
        assert result.ok is False
        assert result.reason == "race_editor_appeared"

        rows = _entity_terms_rows(engine, article_id)
        assert len(rows) == 1 and rows[0][0] == news_id and rows[0][1] == "editor"
        assert _articles_row(engine, article_id) == (None, "news")  # never touched

    def test_concurrent_writer_blocks_on_row_lock_no_lost_update(self, engine, terms, tmp_path, cleanup):
        """Genuine concurrency (two real connections/threads), not just a
        sequential race simulation: proves `SELECT ... FOR UPDATE` actually
        serializes a concurrent writer against the same row, rather than
        the guard being purely an application-level check that a second
        connection could race past."""
        article_ids, entity_ids = cleanup
        news_id = term_uuid(terms, "format", "news")
        wp_id = 900204
        article_id = _insert_article(engine, article_ids, wp_id, primary_type=None, fmt="news")
        _insert_entity_term(engine, entity_ids, article_id, news_id, "ai", 0.560)

        held = threading.Event()
        release = threading.Event()
        order: list[str] = []

        def holder():
            with engine.begin() as conn:
                conn.execute(
                    text("select confidence from engine.entity_terms where entity_type='article' "
                         "and entity_id=:eid and term_id=cast(:tid as uuid) for update"),
                    {"eid": str(article_id), "tid": news_id},
                )
                held.set()
                release.wait(timeout=5)
                order.append("holder_commit")
                time.sleep(0.05)

        def blocked_writer():
            held.wait(timeout=5)
            start = time.monotonic()
            with engine.begin() as conn:
                conn.execute(
                    text("update engine.entity_terms set weight=weight where entity_type='article' "
                         "and entity_id=:eid and term_id=cast(:tid as uuid)"),
                    {"eid": str(article_id), "tid": news_id},
                )
            elapsed = time.monotonic() - start
            order.append("writer_unblocked")
            # It must have waited for the holder to release the lock, not
            # returned immediately -- proving real row-level serialization.
            assert elapsed >= 0.05, f"writer returned in {elapsed:.3f}s -- lock was not actually held"

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=blocked_writer)
        t1.start()
        t2.start()
        held.wait(timeout=5)
        time.sleep(0.1)
        release.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert order == ["holder_commit", "writer_unblocked"]


# --------------------------------------------------------------------------
# Safety: refusal against live db_refs, even when the caller passes one by name
# --------------------------------------------------------------------------

class TestLiveRefusal:
    @pytest.mark.parametrize("live_db", ["now_jakarta", "now_bali"])
    def test_execute_refuses_before_touching_a_live_city_db(self, terms, tmp_path, live_db):
        ledger_dir = _write_ledger(tmp_path, "jakarta" if live_db == "now_jakarta" else "bali", [])
        city = "jakarta" if live_db == "now_jakarta" else "bali"
        with pytest.raises(RefusedLiveWriteError):
            run_apply((city,), ledger_dir, terms, city_db_map={city: live_db}, dry_run=False)

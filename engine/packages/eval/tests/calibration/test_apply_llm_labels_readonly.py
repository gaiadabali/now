"""Proves this ticket's ONE hard scope boundary: zero writes to
`now_jakarta`/`now_bali`, ever, from this module -- not "we didn't call
apply", but measured before/after row counts across the real tables this
writer's SQL touches, exactly as the ticket requires ("Read-only against
`now_jakarta`/`now_bali` -- prove it with before/after row counts").

Runs against the REAL local `now_jakarta`/`now_bali` databases (the same
ones every prior Wave 18 ticket measured against) -- read-only queries
only, never inside a transaction this test itself commits any write in.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from now_db.settings import city_database_url

from now_eval.calibration.apply_llm_labels import RefusedLiveWriteError, run_apply

LIVE_CITIES = ("jakarta", "bali")
LIVE_DB_REF = {"jakarta": "now_jakarta", "bali": "now_bali"}


def _row_counts(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            "articles": conn.execute(text("select count(*) from public.articles")).scalar(),
            "entity_terms": conn.execute(text("select count(*) from engine.entity_terms")).scalar(),
            "classification_reviews": conn.execute(text("select count(*) from public.classification_reviews")).scalar(),
            # a content hash over the exact columns this writer could touch --
            # row COUNT alone would not catch an in-place value change.
            "articles_type_format_hash": conn.execute(
                text("select md5(string_agg(coalesce(primary_type::text,'') || '|' || coalesce(format::text,''), ',' "
                     "order by id)) from public.articles")
            ).scalar(),
            "entity_terms_hash": conn.execute(
                text("select md5(string_agg(entity_id || '|' || term_id::text || '|' || source || '|' || confidence::text, ',' "
                     "order by entity_id, term_id)) from engine.entity_terms")
            ).scalar(),
        }


@pytest.fixture(scope="module")
def real_engines():
    engines = {city: create_engine(city_database_url(LIVE_DB_REF[city])) for city in LIVE_CITIES}
    yield engines
    for eng in engines.values():
        eng.dispose()


class TestReadOnlyAgainstLiveCities:
    def test_dry_run_leaves_every_row_and_value_byte_identical(self, real_engines, tmp_path):
        from now_classifier.vocabulary import load_term_index

        terms = load_term_index()
        before = {city: _row_counts(eng) for city, eng in real_engines.items()}

        # An empty ledger dir -- this test's job is to prove the READ side
        # (which runs regardless of ledger contents) never writes, not to
        # exercise planning logic (that's covered against now_test).
        ledger_dir = tmp_path / "llm_batch"
        ledger_dir.mkdir()

        report = run_apply(
            LIVE_CITIES, ledger_dir, terms,
            city_db_map=dict(LIVE_DB_REF),
            engine_factory=lambda ref: real_engines[{v: k for k, v in LIVE_DB_REF.items()}[ref]],
            dry_run=True,
        )
        # sanity: this really did read real data (proves the test isn't
        # vacuously passing against empty tables)
        assert report.planned or report.skipped
        assert (len(report.planned) + len(report.skipped)) > 1000

        after = {city: _row_counts(eng) for city, eng in real_engines.items()}
        assert after == before, "dry-run must never change any row count or any stored value"

    def test_execute_mode_refuses_before_reading_or_writing_anything(self, tmp_path):
        from now_classifier.vocabulary import load_term_index

        terms = load_term_index()
        ledger_dir = tmp_path / "llm_batch"
        ledger_dir.mkdir()

        def _engine_factory_that_must_never_be_called(ref):
            raise AssertionError(f"engine_factory({ref!r}) was called -- execute mode must refuse before opening any connection")

        with pytest.raises(RefusedLiveWriteError) as excinfo:
            run_apply(
                LIVE_CITIES, ledger_dir, terms,
                city_db_map=dict(LIVE_DB_REF),
                engine_factory=_engine_factory_that_must_never_be_called,
                dry_run=False,
            )
        assert "now_jakarta" in str(excinfo.value) and "now_bali" in str(excinfo.value)

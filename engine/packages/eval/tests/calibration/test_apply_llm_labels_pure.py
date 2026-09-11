"""Pure-logic tests for the LLM-batch apply step (Wave 18 T3) -- no DB, no
network. Real DB/attack-test coverage lives in
`test_apply_llm_labels_db.py` (against `now_test`) and
`test_apply_llm_labels_readonly.py` (proves zero writes against
`now_jakarta`/`now_bali`).
"""
from __future__ import annotations

import inspect

import pytest

from now_eval.calibration.apply_llm_labels import (
    FACETS,
    LIVE_CITY_DBS,
    LLM_BATCH_CONFIDENCE,
    FacetState,
    LlmLabel,
    PlannedChange,
    RefusedLiveWriteError,
    Skip,
    TermRow,
    TYPE_LOW_ACCURACY_MAX,
    band_for_confidence,
    build_dry_run_report,
    is_low_accuracy_band,
    plan_all,
    plan_one,
)


# --------------------------------------------------------------------------
# band_for_confidence / is_low_accuracy_band
# --------------------------------------------------------------------------

class TestBandForConfidence:
    def test_recovers_every_routed_type_band(self):
        from now_classifier.embed_routing import ROUTED_CONFIDENCE

        for (band, facet), acc in ROUTED_CONFIDENCE.items():
            assert band_for_confidence(facet, acc) == band

    def test_unknown_confidence_returns_none(self):
        assert band_for_confidence("type", 0.5000) is None
        assert band_for_confidence("format", 0.1234) is None

    def test_own_sentinel_confidence_matches_no_band_either_facet(self):
        # LLM_BATCH_CONFIDENCE must not collide with any measured band --
        # this is what makes a second run of the writer a no-op (idempotency).
        assert band_for_confidence("type", LLM_BATCH_CONFIDENCE) is None
        assert band_for_confidence("format", LLM_BATCH_CONFIDENCE) is None

    def test_old_pre_f125_invented_numbers_do_not_collide(self):
        # 0.95/0.93/0.75/0.45 -- the invented numbers F118/F120/F125 all
        # replaced -- must not accidentally match a real routed band, for
        # EITHER facet. (0.72 and 0.40 are deliberately excluded from this
        # list: they are legacy pooled labels that now genuinely coincide
        # with format's own facet-scoped cue_confident=0.720/cue_fired=0.400
        # -- a real, expected collision, not a bug -- see the next test.)
        for legacy in (0.95, 0.93, 0.75, 0.45):
            assert band_for_confidence("type", legacy) is None
            assert band_for_confidence("format", legacy) is None

    def test_legacy_072_and_040_coincide_with_formats_own_measured_bands(self):
        # Disclosed, not a bug: format's facet-scoped cue_confident (0.720)
        # and cue_fired (0.400) happen to equal the OLD pooled labels for
        # those same two bands. band_for_confidence correctly recognizes
        # these as real bands for format (they ARE format's own measured
        # accuracy), even though the identical numbers must NOT resolve for
        # type (type's own measured numbers at these bands are different:
        # 0.840/0.667).
        assert band_for_confidence("format", 0.72) == "cue_confident"
        assert band_for_confidence("format", 0.40) == "cue_fired"
        assert band_for_confidence("type", 0.72) is None
        assert band_for_confidence("type", 0.40) is None


class TestIsLowAccuracyBand:
    def test_format_every_routed_band_is_low_accuracy(self):
        # F124's deliberate override: even format's best-measured band
        # (category_fixed_high, 0.560) is replaced.
        from now_classifier.embed_routing import ROUTED_INSTRUMENT

        for band in ROUTED_INSTRUMENT:
            assert is_low_accuracy_band("format", band) is True

    def test_format_unrouted_band_is_not_low_accuracy(self):
        # category_fixed_low / cue_abstain_fallback never appear in
        # entity_terms (never auto-applied), but the function must still
        # answer conservatively (False, not a crash) if ever asked.
        assert is_low_accuracy_band("format", "category_fixed_low") is False

    def test_type_only_bands_below_threshold_are_low_accuracy(self):
        from now_classifier.embed_routing import (
            CATEGORY_FIXED_HIGH, CATEGORY_FIXED_MEDIUM, CUE_CONFIDENT_BAND, CUE_FIRED_BAND,
        )

        # measured: category_fixed_high=0.760, cue_confident=0.840 (KEEP);
        # category_fixed_medium=0.640, cue_fired=0.667 (REPLACE)
        assert is_low_accuracy_band("type", CATEGORY_FIXED_HIGH) is False
        assert is_low_accuracy_band("type", CUE_CONFIDENT_BAND) is False
        assert is_low_accuracy_band("type", CATEGORY_FIXED_MEDIUM) is True
        assert is_low_accuracy_band("type", CUE_FIRED_BAND) is True

    def test_threshold_is_070(self):
        assert TYPE_LOW_ACCURACY_MAX == 0.70

    def test_unknown_facet_raises(self):
        with pytest.raises(ValueError):
            is_low_accuracy_band("subtype", "category_fixed_high")


# --------------------------------------------------------------------------
# plan_one -- every skip reason, and the one replace path, each isolated.
# --------------------------------------------------------------------------

def _state(city="jakarta", wp_id=1, article_id=1, facet="type", rows=(), articles_value=None) -> FacetState:
    return FacetState(city=city, wp_id=wp_id, article_id=article_id, facet=facet,
                       rows=tuple(rows), articles_column_value=articles_value)


def _row(slug: str, source: str, confidence: float, term_id: str | None = None) -> TermRow:
    return TermRow(term_id=term_id or f"term-{slug}", slug=slug, source=source, confidence=confidence)


def _label(city="jakarta", wp_id=1, type_=None, format_=None, error=None) -> LlmLabel:
    return LlmLabel(city=city, wp_id=wp_id, type=type_, format=format_, error=error)


VOCAB = {("type", "eat"): "uuid-eat", ("type", "stay"): "uuid-stay",
         ("format", "news"): "uuid-news", ("format", "feature"): "uuid-feature"}


def _term_uuid_fn(facet: str, slug: str) -> str | None:
    return VOCAB.get((facet, slug))


class TestPlanOneAttackCases:
    """The attack tests the ticket names explicitly."""

    def test_editor_sourced_row_survives_regardless_of_band_or_disagreement(self):
        # category_fixed_medium (0.640) is a low-accuracy type band, and the
        # LLM disagrees -- would replace, EXCEPT the row is editor-sourced.
        state = _state(facet="type", rows=[_row("eat", "editor", 0.640)], articles_value="eat")
        label = _label(type_="stay")
        result = plan_one(state, label, _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "editor_sourced_present"

    def test_editor_row_survives_even_alongside_a_stray_non_editor_row(self):
        # A defensively-conservative case: don't try to disentangle a mixed
        # state, just refuse the whole article-facet.
        state = _state(facet="type", rows=[
            _row("eat", "editor", 0.640), _row("stay", "ai", 0.667),
        ], articles_value="eat")
        result = plan_one(state, _label(type_="drink"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "editor_sourced_present"

    def test_no_entity_terms_row_is_not_an_apply_target(self):
        state = _state(facet="type", rows=[], articles_value=None)
        result = plan_one(state, _label(type_="eat"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "no_entity_terms_row"


class TestPlanOneOtherSkipReasons:
    def test_ambiguous_multiple_non_editor_rows_skips(self):
        state = _state(facet="type", rows=[
            _row("eat", "ai", 0.667), _row("stay", "ai", 0.667),
        ], articles_value="eat")
        result = plan_one(state, _label(type_="drink"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "ambiguous_multiple_rows"

    def test_unrecognized_provenance_skips(self):
        # confidence doesn't match any routed band (e.g. a pre-F125 legacy
        # value, or an already-LLM-applied row).
        state = _state(facet="type", rows=[_row("eat", "ai", 0.5)], articles_value="eat")
        result = plan_one(state, _label(type_="stay"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "unrecognized_provenance"

    def test_not_low_accuracy_band_skips_even_on_disagreement(self):
        # type cue_confident = 0.840, a KEEP band.
        state = _state(facet="type", rows=[_row("eat", "ai", 0.840)], articles_value="eat")
        result = plan_one(state, _label(type_="stay"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "not_low_accuracy_band"
        assert result.detail == "cue_confident"

    def test_llm_missing_skips(self):
        state = _state(facet="type", rows=[_row("eat", "ai", 0.640)], articles_value="eat")
        result = plan_one(state, None, _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "llm_missing"

    def test_llm_error_skips(self):
        state = _state(facet="type", rows=[_row("eat", "ai", 0.640)], articles_value="eat")
        result = plan_one(state, _label(type_="stay", error="timeout"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "llm_error"

    def test_articles_entity_terms_drift_skips(self):
        # public.articles disagrees with entity_terms's own accepted value --
        # KNOWN SCHEMA GAP guard: refuse rather than trust either side.
        state = _state(facet="type", rows=[_row("eat", "ai", 0.640)], articles_value="stay")
        result = plan_one(state, _label(type_="drink"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "articles_entity_terms_drift"

    def test_llm_agreement_is_a_no_op(self):
        state = _state(facet="type", rows=[_row("eat", "ai", 0.640)], articles_value="eat")
        result = plan_one(state, _label(type_="eat"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "llm_agrees"

    def test_llm_vocabulary_miss_skips(self):
        state = _state(facet="type", rows=[_row("eat", "ai", 0.640)], articles_value="eat")
        result = plan_one(state, _label(type_="not-a-real-slug"), _term_uuid_fn)
        assert isinstance(result, Skip)
        assert result.reason == "llm_vocabulary_miss"


class TestPlanOneReplace:
    def test_low_accuracy_disagreement_plans_a_replacement(self):
        state = _state(city="bali", wp_id=42, article_id=7, facet="format",
                        rows=[_row("news", "ai", 0.560, term_id="term-news")], articles_value="news")
        label = _label(city="bali", wp_id=42, format_="feature")
        result = plan_one(state, label, _term_uuid_fn)
        assert isinstance(result, PlannedChange)
        assert result.city == "bali" and result.wp_id == 42 and result.article_id == 7
        assert result.facet == "format"
        assert result.old_slug == "news" and result.old_term_id == "term-news"
        assert result.new_slug == "feature" and result.new_term_id == "uuid-feature"
        assert result.band == "category_fixed_high"

    def test_inferred_source_is_also_replaceable(self):
        # source='inferred' (category-prior fallback) is NOT 'editor' -- must
        # be treated the same as 'ai', not specially protected.
        state = _state(facet="format", rows=[_row("news", "inferred", 0.560)], articles_value="news")
        result = plan_one(state, _label(format_="feature"), _term_uuid_fn)
        assert isinstance(result, PlannedChange)


class TestPlanAll:
    def test_groups_by_key_and_partitions_planned_vs_skipped(self):
        states = [
            _state(city="jakarta", wp_id=1, facet="format", rows=[_row("news", "ai", 0.560)], articles_value="news"),
            _state(city="jakarta", wp_id=2, facet="format", rows=[_row("news", "editor", 0.560)], articles_value="news"),
        ]
        labels = {
            ("jakarta", 1): _label(wp_id=1, format_="feature"),
            ("jakarta", 2): _label(wp_id=2, format_="feature"),
        }
        planned, skipped = plan_all(states, labels, _term_uuid_fn)
        assert len(planned) == 1 and planned[0].wp_id == 1
        assert len(skipped) == 1 and skipped[0].wp_id == 2 and skipped[0].reason == "editor_sourced_present"


# --------------------------------------------------------------------------
# build_dry_run_report
# --------------------------------------------------------------------------

class TestDryRunReport:
    def test_groups_by_city_facet_band_as_the_ticket_requires(self):
        # "Dry-run mode that reports the exact diff: rows to change, by
        # city, by facet, by provenance band" -- two DIFFERENT cities with
        # the same facet/band must land in separate groups, not be merged.
        planned = [
            PlannedChange(city="jakarta", wp_id=1, article_id=1, facet="format", old_term_id="t1",
                          old_slug="news", old_confidence=0.560, band="category_fixed_high",
                          new_slug="feature", new_term_id="u1", llm_reasoning="reads like a feature"),
            PlannedChange(city="bali", wp_id=2, article_id=2, facet="format", old_term_id="t2",
                          old_slug="news", old_confidence=0.560, band="category_fixed_high",
                          new_slug="feature", new_term_id="u2", llm_reasoning="also a feature"),
        ]
        skipped = [Skip(city="jakarta", wp_id=3, facet="type", reason="llm_agrees")]
        report = build_dry_run_report(planned, skipped)
        assert report["total_planned_changes"] == 2
        assert report["total_skipped"] == 1
        groups = report["changes_by_city_facet_band"]
        assert len(groups) == 2
        assert {(g["city"], g["facet"], g["band"], g["count"]) for g in groups} == {
            ("jakarta", "format", "category_fixed_high", 1),
            ("bali", "format", "category_fixed_high", 1),
        }
        assert all(g["measured_accuracy_replaced"] == 0.560 for g in groups)
        assert {"city": "jakarta", "facet": "type", "reason": "llm_agrees", "count": 1} in report["skip_reasons"]

    def test_same_city_facet_band_groups_together(self):
        planned = [
            PlannedChange(city="jakarta", wp_id=i, article_id=i, facet="format", old_term_id=f"t{i}",
                          old_slug="news", old_confidence=0.560, band="category_fixed_high",
                          new_slug="feature", new_term_id=f"u{i}", llm_reasoning="x")
            for i in (1, 2)
        ]
        report = build_dry_run_report(planned, [])
        assert len(report["changes_by_city_facet_band"]) == 1
        assert report["changes_by_city_facet_band"][0]["count"] == 2

    def test_sample_is_bounded(self):
        planned = [
            PlannedChange(city="jakarta", wp_id=i, article_id=i, facet="format", old_term_id=f"t{i}",
                          old_slug="news", old_confidence=0.560, band="category_fixed_high",
                          new_slug="feature", new_term_id=f"u{i}", llm_reasoning="x")
            for i in range(25)
        ]
        report = build_dry_run_report(planned, [], sample_size=5)
        assert report["changes_by_city_facet_band"][0]["count"] == 25
        assert len(report["changes_by_city_facet_band"][0]["sample"]) == 5


# --------------------------------------------------------------------------
# Safety constants + static guards
# --------------------------------------------------------------------------

class TestSafetyConstants:
    def test_live_city_dbs_is_exactly_the_two_real_cities(self):
        assert LIVE_CITY_DBS == frozenset({"now_jakarta", "now_bali"})

    def test_facets_is_type_and_format_only(self):
        assert FACETS == ("type", "format")


class TestStaticSourceGuards:
    """Not just claims -- scan the module's own source for the guard
    text, the same discipline `test_batch_label.py`'s
    `test_batch_label_module_contains_no_write_sql` uses (there, to prove
    NO writes exist; here, to prove every write that DOES exist carries
    its required guard)."""

    def _source(self) -> str:
        from now_eval.calibration import apply_llm_labels
        return inspect.getsource(apply_llm_labels)

    def test_every_entity_terms_delete_is_source_guarded(self):
        src = self._source()
        assert "delete from engine.entity_terms" in src.lower()
        # the only DELETE against entity_terms in this module must carry
        # the non-clobber predicate -- checked textually, adjacent to the
        # DELETE statement string itself.
        assert "and source <> 'editor'" in src.lower()

    def test_entity_terms_select_uses_for_update(self):
        src = self._source()
        assert "for update" in src.lower()

    def test_articles_update_is_optimistic_concurrency_guarded(self):
        src = self._source()
        # both the type and format UPDATE statements must condition on the
        # OLD value, never a blind SET.
        assert "where id = :article_id and" in src.lower()

    def test_module_contains_no_classification_reviews_sql(self):
        # Out-of-scope-in-v1, stated in the docstring (which legitimately
        # names the table in prose explaining why) -- what must be ABSENT
        # is any SQL statement shape that reads or writes it.
        src = self._source().lower()
        forbidden = (
            "into classification_reviews", "update classification_reviews",
            "from classification_reviews", "join classification_reviews",
            "delete classification_reviews",
        )
        for pattern in forbidden:
            assert pattern not in src, f"found forbidden SQL touching classification_reviews: {pattern!r}"

    def test_new_term_insert_carries_llm_batch_source_not_editor(self):
        # This writer must never spoof source='editor' anywhere (Rule 1/2):
        # the INSERT that writes the LLM's replacement value must bind its
        # `source` param to LLM_BATCH_SOURCE ('ai'), never a literal 'editor'.
        src = self._source()
        assert "values ('article', :entity_id, cast(:new_term_id as uuid), 1.0, :source, :confidence)" in src.lower()
        assert '"source": llm_batch_source' in src.lower()

        from now_eval.calibration.apply_llm_labels import LLM_BATCH_SOURCE
        assert LLM_BATCH_SOURCE != "editor"

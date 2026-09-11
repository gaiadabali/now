"""F120 routing: `now_classifier.embed_routing`'s own logic (band->instrument
table, abstain handling, artifact loading), independent of `resolve.py`'s
wiring (see test_resolve.py for that)."""
from __future__ import annotations

import json

import pytest

from now_classifier.embed_routing import (
    CATEGORY_FIXED_HIGH,
    CATEGORY_FIXED_MEDIUM,
    CUE_CONFIDENT_BAND,
    CUE_FIRED_BAND,
    EMBEDDINGS_ABSTAIN_FALLBACK,
    ROUTED_BANDS,
    ROUTED_CONFIDENCE,
    ROUTED_INSTRUMENT,
    CentroidModel,
    load_centroid_models,
    route,
)


def test_routing_table_matches_progress_md_f120_decision():
    """Locks in the exact four-band table PROGRESS.md's F120 ticket
    specifies, facet-scoped (a pooled number was found to misrepresent
    `format` -- see `embed_routing.ROUTED_CONFIDENCE`'s module comment and
    `f120_facet_scoped_report.py`). A change here should only ever follow a
    new measurement, never an unrelated refactor."""
    assert ROUTED_BANDS == {CATEGORY_FIXED_HIGH, CUE_CONFIDENT_BAND, CATEGORY_FIXED_MEDIUM, CUE_FIRED_BAND}
    assert ROUTED_INSTRUMENT[CATEGORY_FIXED_HIGH] == "keyword_cue"
    assert ROUTED_INSTRUMENT[CATEGORY_FIXED_MEDIUM] == "keyword_cue"
    assert ROUTED_INSTRUMENT[CUE_CONFIDENT_BAND] == "embeddings_centroid"
    assert ROUTED_INSTRUMENT[CUE_FIRED_BAND] == "embeddings_centroid"
    assert ROUTED_CONFIDENCE[(CATEGORY_FIXED_HIGH, "type")] == pytest.approx(0.760)
    assert ROUTED_CONFIDENCE[(CATEGORY_FIXED_HIGH, "format")] == pytest.approx(0.560)
    assert ROUTED_CONFIDENCE[(CUE_CONFIDENT_BAND, "type")] == pytest.approx(0.840)
    assert ROUTED_CONFIDENCE[(CUE_CONFIDENT_BAND, "format")] == pytest.approx(0.720)
    assert ROUTED_CONFIDENCE[(CATEGORY_FIXED_MEDIUM, "type")] == pytest.approx(0.640)
    assert ROUTED_CONFIDENCE[(CATEGORY_FIXED_MEDIUM, "format")] == pytest.approx(0.580)
    assert ROUTED_CONFIDENCE[(CUE_FIRED_BAND, "type")] == pytest.approx(0.667)
    assert ROUTED_CONFIDENCE[(CUE_FIRED_BAND, "format")] == pytest.approx(0.400)
    # None of these reuse THEIR OWN band's old invented number (F96/F111:
    # those never meant anything) -- guards against silently reverting to
    # them. (A different band's old number can legitimately coincide by
    # chance with a real measured value here -- e.g. format's measured
    # cue_confident accuracy, 0.720, happens to numerically collide with
    # cue_fired's old invented 0.72 constant; that is not a reversion,
    # it is an unrelated real number that happens to round the same way,
    # so the check below is band-specific, not a blanket "value never
    # equals any old constant" rule.)
    old_invented_for_band = {
        CATEGORY_FIXED_HIGH: 0.95, CUE_CONFIDENT_BAND: 0.93,
        CATEGORY_FIXED_MEDIUM: 0.75, CUE_FIRED_BAND: 0.72,
    }
    for band, old_value in old_invented_for_band.items():
        for facet in ("type", "format"):
            assert ROUTED_CONFIDENCE[(band, facet)] != old_value


def test_facet_scoped_numbers_pool_back_to_the_published_f118_f120_numbers():
    """Cross-check: population-weighted pooling of the facet-scoped numbers
    (roughly equal type/format population per band in the 253-item sample)
    must reproduce F118/F120's own already-published pooled numbers -- a
    live guard that this is a REFINEMENT of the same measurement, not a
    disagreement with it."""
    pooled = {
        CATEGORY_FIXED_HIGH: 0.660, CUE_CONFIDENT_BAND: 0.78,
        CATEGORY_FIXED_MEDIUM: 0.610, CUE_FIRED_BAND: 0.53,
    }
    for band, expected in pooled.items():
        avg = (ROUTED_CONFIDENCE[(band, "type")] + ROUTED_CONFIDENCE[(band, "format")]) / 2
        assert avg == pytest.approx(expected, abs=0.005)


def test_keyword_cue_band_returns_base_value_unchanged_at_measured_confidence():
    d = route(CATEGORY_FIXED_HIGH, "type", base_value="eat", base_source="inferred",
              article_vector=[1.0, 0.0], centroid_model=CentroidModel("type", {"eat": [1.0, 0.0]}, {"eat": 10}, frozenset(), 5))
    assert d.value == "eat"
    assert d.confidence == pytest.approx(0.760)
    assert d.source == "inferred"
    assert d.auto_apply is True
    assert "keyword_cue" in d.reasoning_suffix


def test_keyword_cue_band_uses_the_format_specific_number_for_format():
    d = route(CATEGORY_FIXED_HIGH, "format", base_value="news", base_source="inferred",
              article_vector=None, centroid_model=None)
    assert d.confidence == pytest.approx(0.560)  # NOT the pooled 0.660, NOT type's 0.760


def test_embeddings_band_predicts_from_centroid_and_auto_applies():
    model = CentroidModel("type", {"drink": [1.0, 0.0], "eat": [0.0, 1.0]}, {"drink": 10, "eat": 10}, frozenset(), 5)
    d = route(CUE_CONFIDENT_BAND, "type", base_value="eat", base_source="ai", article_vector=[0.9, 0.1], centroid_model=model)
    assert d.value == "drink"  # nearest centroid, not the base cue value
    assert d.confidence == pytest.approx(0.840)
    assert d.source == "ai"
    assert d.auto_apply is True


def test_embeddings_band_uses_the_format_specific_number_for_format():
    model = CentroidModel("format", {"news": [1.0, 0.0], "feature": [0.0, 1.0]}, {"news": 10, "feature": 10}, frozenset(), 5)
    d = route(CUE_CONFIDENT_BAND, "format", base_value="news", base_source="ai", article_vector=[0.9, 0.1], centroid_model=model)
    assert d.confidence == pytest.approx(0.720)  # NOT the pooled 0.78, NOT type's 0.840


def test_embeddings_band_abstains_with_no_vector():
    model = CentroidModel("type", {"drink": [1.0, 0.0]}, {"drink": 10}, frozenset(), 5)
    d = route(CUE_FIRED_BAND, "type", base_value="drink", base_source="ai", article_vector=None, centroid_model=model)
    assert d.value == "drink"  # falls back to the base value
    assert d.confidence == pytest.approx(EMBEDDINGS_ABSTAIN_FALLBACK)
    assert d.auto_apply is False


def test_embeddings_band_abstains_with_no_centroid_model_loaded():
    d = route(CUE_FIRED_BAND, "type", base_value="drink", base_source="ai", article_vector=[1.0, 0.0], centroid_model=None)
    assert d.value == "drink"
    assert d.confidence == pytest.approx(EMBEDDINGS_ABSTAIN_FALLBACK)
    assert d.auto_apply is False


def test_embeddings_band_abstains_when_model_has_no_trusted_classes():
    empty_model = CentroidModel("type", {}, {"wellness": 2}, frozenset({"wellness"}), 5)
    d = route(CUE_CONFIDENT_BAND, "type", base_value="eat", base_source="ai", article_vector=[1.0, 0.0], centroid_model=empty_model)
    assert d.confidence == pytest.approx(EMBEDDINGS_ABSTAIN_FALLBACK)
    assert d.auto_apply is False


def test_load_centroid_models_from_artifact(tmp_path):
    artifact = {
        "min_class_n": 5,
        "facets": {
            "type": {
                "centroids": {"eat": [1.0, 0.0], "drink": [0.0, 1.0]},
                "class_n": {"eat": 6, "drink": 5, "wellness": 2},
                "excluded_classes": ["wellness"],
                "min_class_n": 5,
            }
        },
    }
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    models = load_centroid_models(path)
    assert set(models) == {"type"}
    assert models["type"].centroids["eat"] == [1.0, 0.0]
    assert models["type"].excluded_classes == frozenset({"wellness"})
    assert models["type"].class_n["wellness"] == 2


def test_load_centroid_models_missing_artifact_returns_empty_not_raise(tmp_path):
    assert load_centroid_models(tmp_path / "does-not-exist.json") == {}


def test_real_artifact_excludes_the_f120_disclosed_thin_classes():
    """Regression: F120 explicitly flagged `wellness`=2, `shop`=3 for
    `type` as too thin to trust. The real, committed artifact (built by
    `engine/packages/eval/scripts/build_routing_centroids.py`) must
    exclude them, not silently include a noisy 2-item mean."""
    models = load_centroid_models()
    if not models:
        pytest.skip("embed_routing_centroids.json not built in this checkout")
    assert "wellness" in models["type"].excluded_classes
    assert "shop" in models["type"].excluded_classes
    assert "wellness" not in models["type"].centroids
    assert "shop" not in models["type"].centroids

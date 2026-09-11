"""Pure-logic tests for `now_eval.calibration.embed_instrument` (F118 option
(a) -- the embeddings-based type/format instrument). No DB, no network,
matching `test_stats.py`'s convention -- this module never imports the
`calibration` extra."""
from __future__ import annotations

import math

from now_eval.calibration.embed_instrument import (
    Prediction,
    build_cell_estimates_for_predictions,
    build_centroids,
    centroid_predict,
    coverage_curve,
    cosine,
    cv_centroid_predictions,
    kfold_indices,
    knn_predict,
    loo_knn_predictions,
    overall_accuracy,
    zero_shot_predict,
)


def test_cosine_identical_vectors_is_one():
    assert math.isclose(cosine([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_cosine_orthogonal_is_zero():
    assert math.isclose(cosine([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_cosine_zero_vector_is_safe():
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_zero_shot_predict_picks_highest_cosine_and_margin():
    article = [1.0, 0.0]
    terms = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [0.9, 0.1]}
    best, margin = zero_shot_predict(article, terms)
    assert best == "a"
    assert margin > 0


def test_zero_shot_predict_empty_terms_abstains():
    best, margin = zero_shot_predict([1.0, 0.0], {})
    assert best == ""
    assert margin == float("-inf")


def test_knn_predict_majority_vote():
    query = [1.0, 0.0]
    neighbours = [("a", [1.0, 0.0]), ("a", [0.99, 0.01]), ("b", [0.0, 1.0])]
    val, margin = knn_predict(query, neighbours, k=3)
    assert val == "a"
    assert margin > 0


def test_loo_knn_never_lets_item_see_its_own_label():
    # Two well-separated clusters; each item's own vector is a perfect
    # match for itself, so if LOO leaked, every item would trivially vote
    # for its own (guaranteed-correct) label. With it excluded, an
    # isolated point with no same-class neighbour should NOT trivially win.
    items = [
        ("k1", "x", [1.0, 0.0]),
        ("k2", "y", [0.0, 1.0]),
        ("k3", "y", [0.0, 0.99]),
    ]
    preds = loo_knn_predictions(items, k=2)
    by_key = {p.key: p for p in preds}
    # k1 ("x") has no same-class neighbour at all -- its LOO prediction
    # must come from the "y" pool, proving its own label was excluded.
    assert by_key["k1"].predicted_value == "y"


def test_build_centroids_is_class_mean():
    labelled = [("a", [1.0, 1.0]), ("a", [3.0, 3.0]), ("b", [0.0, 0.0])]
    centroids = build_centroids(labelled)
    assert centroids["a"] == [2.0, 2.0]
    assert centroids["b"] == [0.0, 0.0]


def test_centroid_predict_nearest_mean():
    centroids = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    val, margin = centroid_predict([0.9, 0.1], centroids)
    assert val == "a"
    assert margin > 0


def test_kfold_indices_covers_every_index_exactly_once():
    perm = [4, 1, 3, 0, 2]
    folds = kfold_indices(5, 2, perm)
    flat = sorted(i for fold in folds for i in fold)
    assert flat == [0, 1, 2, 3, 4]


def test_cv_centroid_predictions_never_uses_test_items_own_label():
    # 4 items, 2 classes, 2-fold CV: fold containing an "a" item must have
    # its centroid built only from the OTHER "a" item plus "b"s, not itself.
    items = [
        ("k1", "a", [1.0, 0.0]),
        ("k2", "a", [0.9, 0.1]),
        ("k3", "b", [0.0, 1.0]),
        ("k4", "b", [-0.1, 0.9]),
    ]
    perm = [0, 2, 1, 3]  # fold0=[k1,k3], fold1=[k2,k4]
    preds = cv_centroid_predictions(items, k_folds=2, seed_perm=perm)
    assert {p.predicted_value for p in preds} <= {"a", "b"}
    assert len(preds) == 4


def test_coverage_curve_monotonic_coverage_non_increasing_with_threshold():
    preds = [
        Prediction(key="1", true_value="a", predicted_value="a", margin=0.5),
        Prediction(key="2", true_value="a", predicted_value="b", margin=0.1),
        Prediction(key="3", true_value="b", predicted_value="b", margin=0.3),
    ]
    curve = coverage_curve(preds, [0.0, 0.2, 0.4])
    coverages = [pt.coverage for pt in curve]
    assert coverages == sorted(coverages, reverse=True)
    assert curve[0].n_applied == 3
    assert curve[-1].n_applied == 1  # only margin=0.5 clears 0.4


def test_overall_accuracy():
    preds = [
        Prediction(key="1", true_value="a", predicted_value="a", margin=0.0),
        Prediction(key="2", true_value="a", predicted_value="b", margin=0.0),
    ]
    correct, n, acc = overall_accuracy(preds)
    assert (correct, n) == (1, 2)
    assert math.isclose(acc, 0.5)


def _row(city, wp_id, facet, confidence, proposed, llm_value, agree):
    return {
        "key": f"{city}:{wp_id}:{facet}", "city": city, "wp_id": wp_id, "facet": facet,
        "confidence": confidence, "proposed_value": proposed, "llm_value": llm_value, "agree": agree,
    }


def test_build_cell_estimates_for_predictions_matches_hand_computation():
    # One cell, one disagreement (adjudicated "llm" -- true value is the
    # LLM's) and one control agreement (adjudicated "classifier" -- true
    # value is the shared proposed_value). A predictor that gets both
    # right should score 100% on this cell via the two-stage estimator.
    merged_rows = [
        _row("jakarta", 1, "type", 0.95, "eat", "drink", agree=False),
        _row("jakarta", 2, "type", 0.95, "stay", "stay", agree=True),
    ]
    verdicts = {"jakarta:1:type:disagreement": "llm", "jakarta:2:type:control": "classifier"}
    predictions = {"jakarta:1:type": "drink", "jakarta:2:type": "stay"}
    pop = {"jakarta:type:0.95": 2}

    estimates = build_cell_estimates_for_predictions(merged_rows, verdicts, predictions, pop)
    est = estimates["jakarta:type:0.95"]
    assert est.n_sampled == 2
    assert est.n_disagree == 1
    assert est.n_agree == 1
    assert est.interval.point == 1.0


def test_build_cell_estimates_for_predictions_penalises_wrong_predictions():
    # One disagreement the predictor gets wrong, plus one control
    # agreement it gets right -- so the cell has adjudicated agreement
    # data (a computable estimate) but is dragged below 1.0 by the miss.
    merged_rows = [
        _row("jakarta", 1, "type", 0.95, "eat", "drink", agree=False),
        _row("jakarta", 2, "type", 0.95, "stay", "stay", agree=True),
    ]
    verdicts = {
        "jakarta:1:type:disagreement": "llm",       # true value is "drink"
        "jakarta:2:type:control": "classifier",       # true value is "stay"
    }
    predictions = {
        "jakarta:1:type": "eat",   # predictor said the classifier's (wrong) value -- miss
        "jakarta:2:type": "stay",  # predictor got the control item right
    }
    pop = {"jakarta:type:0.95": 2}

    estimates = build_cell_estimates_for_predictions(merged_rows, verdicts, predictions, pop)
    est = estimates["jakarta:type:0.95"]
    assert est.interval.point == 0.5

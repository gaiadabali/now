from now_eval.calibration.mapping import recommend, simulate_coverage
from now_eval.calibration.stats import estimate_cell_accuracy


def test_recommend_unadjudicated_cell_gives_no_number():
    estimates = {
        "jakarta:type:0.95": estimate_cell_accuracy(
            "jakarta:type:0.95", n_total=2062, n_sampled=25, n_agree=20, n_disagree=5,
            n_agree_adjudicated=0, n_agree_adjudicated_correct=0,
            n_disagree_adjudicated_correct_for_classifier=0,
        )
    }
    rec = recommend(0.95, estimates)
    assert rec.recommended_number is None
    assert rec.crosses_gate_now is True


def test_recommend_pools_across_cities_and_facets():
    est_a = estimate_cell_accuracy("jakarta:type:0.75", n_total=639, n_sampled=25, n_agree=20, n_disagree=5,
                                    n_agree_adjudicated=10, n_agree_adjudicated_correct=10,
                                    n_disagree_adjudicated_correct_for_classifier=5)
    est_b = estimate_cell_accuracy("bali:type:0.75", n_total=789, n_sampled=25, n_agree=15, n_disagree=10,
                                    n_agree_adjudicated=10, n_agree_adjudicated_correct=5,
                                    n_disagree_adjudicated_correct_for_classifier=0)
    rec = recommend(0.75, {"jakarta:type:0.75": est_a, "bali:type:0.75": est_b})
    # pooled: n_sampled=50, agree=35 (10 adjudicated correct=15 total across both -> reliability 15/20=0.75),
    # disagree correct-for-classifier = 5+0=5
    assert rec.n_sampled == 50
    assert rec.accuracy_point is not None
    assert rec.crosses_gate_now is False


def test_recommend_flags_crossing_gate_after_correction():
    # A value currently below the gate (0.75) whose real accuracy turns out high (0.95) should flip.
    est = estimate_cell_accuracy("jakarta:type:0.75", n_total=100, n_sampled=20, n_agree=19, n_disagree=1,
                                  n_agree_adjudicated=19, n_agree_adjudicated_correct=19,
                                  n_disagree_adjudicated_correct_for_classifier=0)
    rec = recommend(0.75, {"jakarta:type:0.75": est})
    assert rec.crosses_gate_now is False
    assert rec.crosses_gate_after is True


def test_simulate_coverage_flips_population_when_gate_side_changes():
    recs = [
        # 0.75 flips from review -> auto-apply
        recommend(0.75, {"jakarta:type:0.75": estimate_cell_accuracy(
            "jakarta:type:0.75", 100, 20, 19, 1, 19, 19, 0)}),
        # 0.93 flips from auto-apply -> review
        recommend(0.93, {"jakarta:type:0.93": estimate_cell_accuracy(
            "jakarta:type:0.93", 100, 20, 5, 15, 5, 2, 3)}),
    ]
    impacts = simulate_coverage(recs, {0.75: 1000, 0.93: 500})
    by_value = {i.confidence_value: i for i in impacts}
    assert by_value[0.75].flips_to_auto_apply == 1000
    assert by_value[0.93].flips_to_review == 500

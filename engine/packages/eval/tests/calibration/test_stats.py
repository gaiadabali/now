from now_eval.calibration.stats import estimate_cell_accuracy, wilson_interval


def test_wilson_interval_midpoint_matches_proportion():
    w = wilson_interval(8, 10)
    assert abs(w.point - 0.8) < 1e-9
    assert w.low < 0.8 < w.high
    assert w.n == 10


def test_wilson_interval_empty_n():
    w = wilson_interval(0, 0)
    assert w.n == 0


def test_wilson_interval_narrows_with_larger_n():
    small = wilson_interval(8, 10)
    large = wilson_interval(80, 100)
    assert (large.high - large.low) < (small.high - small.low)


def test_estimate_cell_accuracy_unadjudicated_is_nan_not_optimistic():
    # No agreement control slice adjudicated yet -- must not silently assume
    # agreements are correct.
    est = estimate_cell_accuracy(
        cell="jakarta:type:0.75",
        n_total=639,
        n_sampled=25,
        n_agree=20,
        n_disagree=5,
        n_agree_adjudicated=0,
        n_agree_adjudicated_correct=0,
        n_disagree_adjudicated_correct_for_classifier=0,
    )
    assert est.agreement_reliability is None
    import math
    assert math.isnan(est.estimated_correct)


def test_estimate_cell_accuracy_blends_disagreement_and_control_slice():
    # 25 sampled: 20 agreements (control slice of 10, 8 confirmed correct),
    # 5 disagreements (all adjudicated, 3 ruled for the classifier).
    est = estimate_cell_accuracy(
        cell="jakarta:type:0.75",
        n_total=639,
        n_sampled=25,
        n_agree=20,
        n_disagree=5,
        n_agree_adjudicated=10,
        n_agree_adjudicated_correct=8,
        n_disagree_adjudicated_correct_for_classifier=3,
    )
    assert est.agreement_reliability == 0.8
    # estimated_correct = 3 + 20*0.8 = 19.0
    assert abs(est.estimated_correct - 19.0) < 1e-9
    assert abs(est.interval.point - 19 / 25) < 1e-9

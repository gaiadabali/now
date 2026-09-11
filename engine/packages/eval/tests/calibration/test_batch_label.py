import json

import pytest

from now_eval.calibration.batch_label import (
    PRIORITY_ORDER,
    RateBudget,
    RateBudgetExceeded,
    already_labelled,
    build_priority_queue,
    tier_index,
    weekly_usage_fraction,
)


def test_priority_order_is_worst_measured_accuracy_first():
    # F113/F120: 0.72 -> 0.283 accuracy, 0.93 -> 0.450, 0.75 -> 0.610, 0.95 -> 0.660.
    # The worst-measured bands must come first so a rate-limited run buys the
    # most correction per call, as the brief instructs.
    assert PRIORITY_ORDER[0] == 0.72
    assert PRIORITY_ORDER.index(0.93) < PRIORITY_ORDER.index(0.75)
    assert PRIORITY_ORDER.index(0.75) < PRIORITY_ORDER.index(0.95)
    assert PRIORITY_ORDER[-1] == 0.95  # best-measured band goes last


def test_tier_index_picks_the_worst_band_present():
    # an article whose type=0.95 (best) but format=0.72 (worst) must be
    # tiered by its worst facet, since one call fixes both at once.
    assert tier_index({0.95, 0.72}) == PRIORITY_ORDER.index(0.72)
    assert tier_index({0.95}) == PRIORITY_ORDER.index(0.95)


def test_tier_index_unknown_value_sorts_last():
    assert tier_index({0.61}) == len(PRIORITY_ORDER)


def test_build_priority_queue_orders_worst_band_first_then_deterministic():
    articles = [
        {"city": "jakarta", "wp_id": 3},
        {"city": "jakarta", "wp_id": 1},
        {"city": "bali", "wp_id": 2},
    ]
    bands = {
        ("jakarta", 3): {0.95},
        ("jakarta", 1): {0.72},
        ("bali", 2): {0.93},
    }
    queue = build_priority_queue(articles, bands)
    assert [(a["city"], a["wp_id"]) for a in queue] == [
        ("jakarta", 1),  # 0.72 -- worst, first
        ("bali", 2),     # 0.93 -- next
        ("jakarta", 3),  # 0.95 -- last
    ]


def test_build_priority_queue_ties_break_by_city_then_wp_id():
    articles = [
        {"city": "jakarta", "wp_id": 9},
        {"city": "bali", "wp_id": 1},
        {"city": "jakarta", "wp_id": 2},
    ]
    bands = {k: {0.72} for k in [("jakarta", 9), ("bali", 1), ("jakarta", 2)]}
    queue = build_priority_queue(articles, bands)
    assert [(a["city"], a["wp_id"]) for a in queue] == [
        ("bali", 1), ("jakarta", 2), ("jakarta", 9),
    ]


def test_already_labelled_reads_across_multiple_ledger_files(tmp_path):
    jak = tmp_path / "jakarta_llm_labels.full.jsonl"
    bal = tmp_path / "bali_llm_labels.full.jsonl"
    jak.write_text(json.dumps({"city": "jakarta", "wp_id": 101, "type": "eat"}) + "\n", encoding="utf-8")
    bal.write_text(json.dumps({"city": "bali", "wp_id": 202, "type": "stay"}) + "\n", encoding="utf-8")

    done = already_labelled(jak, bal)
    assert done == {("jakarta", 101), ("bali", 202)}


def test_already_labelled_missing_files_return_empty(tmp_path):
    assert already_labelled(tmp_path / "does_not_exist.jsonl") == set()


def test_already_labelled_skips_blank_lines(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text("\n" + json.dumps({"city": "jakarta", "wp_id": 5}) + "\n\n", encoding="utf-8")
    assert already_labelled(p) == {("jakarta", 5)}


def test_rate_budget_below_soft_ceiling_is_full_speed():
    budget = RateBudget(soft_ceiling=0.55, hard_ceiling=0.75)
    assert budget.sleep_multiplier(0.20) == 1.0
    assert budget.sleep_multiplier(0.549) == 1.0


def test_rate_budget_above_soft_ceiling_slows_down():
    budget = RateBudget(soft_ceiling=0.55, hard_ceiling=0.75, slowdown_factor=4.0)
    assert budget.sleep_multiplier(0.60) == 4.0


def test_rate_budget_above_hard_ceiling_raises():
    budget = RateBudget(soft_ceiling=0.55, hard_ceiling=0.75)
    with pytest.raises(RateBudgetExceeded):
        budget.sleep_multiplier(0.80)


def test_weekly_usage_fraction_reads_the_documented_shape():
    doc = {"limits": {"weekly": {"usage": 0.126, "models": []}}}
    assert weekly_usage_fraction(doc) == 0.126


def test_weekly_usage_fraction_defaults_to_zero_on_missing_keys():
    assert weekly_usage_fraction({}) == 0.0


def test_batch_label_module_contains_no_write_sql():
    # Static guard, not just a claim: this module's only DB access
    # (fetch_priority_map) must stay read-only. Anyone adding a write path
    # here later trips this test.
    import inspect

    from now_eval.calibration import batch_label

    src = inspect.getsource(batch_label).lower()
    for forbidden in ("insert into", "update ", "delete from", " drop ", "truncate"):
        assert forbidden not in src, f"batch_label.py must stay read-only against the DB, found {forbidden!r}"

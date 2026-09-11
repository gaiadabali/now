from now_eval.calibration.adjudication import build_queue, merge


def _sample_row(city, wp_id, facet, value, confidence, key=None):
    return {
        "key": key or f"{city}:{wp_id}:{facet}",
        "city": city, "wp_id": wp_id, "facet": facet, "proposed_value": value,
        "confidence": confidence, "outcome": "accepted",
        "title": "t", "excerpt": "e", "text_excerpt": "b", "categories": [],
    }


def _label(city, wp_id, type_="eat", format_="review"):
    return {"city": city, "wp_id": wp_id, "type": type_, "format": format_,
            "type_reasoning": "tr", "format_reasoning": "fr", "error": None}


def test_merge_flags_agreement_and_disagreement():
    rows = [_sample_row("jakarta", 1, "type", "eat", 0.95), _sample_row("jakarta", 2, "type", "eat", 0.95)]
    labels = [_label("jakarta", 1, type_="eat"), _label("jakarta", 2, type_="stay")]
    merged = merge(rows, labels)
    by_wp = {m["wp_id"]: m for m in merged}
    assert by_wp[1]["agree"] is True
    assert by_wp[2]["agree"] is False
    assert by_wp[2]["llm_value"] == "stay"


def test_merge_skips_failed_llm_calls():
    rows = [_sample_row("jakarta", 1, "type", "eat", 0.95)]
    labels = [{"city": "jakarta", "wp_id": 1, "type": None, "format": None,
               "type_reasoning": "", "format_reasoning": "", "error": "timeout"}]
    merged = merge(rows, labels)
    assert merged == []


def test_build_queue_includes_every_disagreement():
    rows = [_sample_row("jakarta", i, "type", "eat", 0.95) for i in range(10)]
    labels = [_label("jakarta", i, type_=("stay" if i < 4 else "eat")) for i in range(10)]
    merged = merge(rows, labels)
    queue = build_queue(merged, total_budget=100)
    disagreements = [q for q in queue if q.kind == "disagreement"]
    assert len(disagreements) == 4
    assert {q.wp_id for q in disagreements} == {0, 1, 2, 3}


def test_build_queue_control_slice_never_exceeds_agreements_available():
    rows = [_sample_row("jakarta", i, "type", "eat", 0.95) for i in range(3)]
    labels = [_label("jakarta", i, type_="eat") for i in range(3)]
    merged = merge(rows, labels)
    queue = build_queue(merged, total_budget=1000)
    assert len(queue) == 3  # can't sample more control items than exist


def test_build_queue_spreads_control_slice_across_cells():
    rows = (
        [_sample_row("jakarta", i, "type", "eat", 0.95, key=f"a-{i}") for i in range(50)]
        + [_sample_row("jakarta", 100 + i, "type", "eat", 0.40, key=f"b-{i}") for i in range(5)]
    )
    labels = [_label("jakarta", i, type_="eat") for i in range(50)] + [
        _label("jakarta", 100 + i, type_="eat") for i in range(5)
    ]
    merged = merge(rows, labels)
    queue = build_queue(merged, total_budget=10)
    cells = {q.cell for q in queue}
    assert "jakarta:type:0.95" in cells
    assert "jakarta:type:0.4" in cells


def test_build_queue_deterministic():
    rows = [_sample_row("jakarta", i, "type", "eat", 0.95, key=f"x-{i}") for i in range(20)]
    labels = [_label("jakarta", i, type_="eat") for i in range(20)]
    merged = merge(rows, labels)
    a = build_queue(merged, total_budget=5)
    b = build_queue(merged, total_budget=5)
    assert [i.item_id for i in a] == [i.item_id for i in b]

from now_eval.calibration.location import build_validation_prompt, stratified_sample, target_n


def test_target_n_gives_075_the_biggest_budget():
    # The flagged band (category-fixed, below the gate) must get the largest
    # n of any location stratum -- that's the whole point of this module.
    n_075 = target_n("inferred", 0.75, 10_000)
    n_095 = target_n("inferred", 0.95, 10_000)
    n_045 = target_n("inferred", 0.45, 10_000)
    assert n_075 > n_095 > n_045


def test_target_n_disambiguates_090_by_source():
    site_home = target_n("inferred", 0.90, 10_000)
    title_match = target_n("ai", 0.90, 10_000)
    assert site_home != title_match  # different mechanisms, different budgets


def _row(city, wp_id, value, confidence, source, key=None):
    return {
        "key": key or f"{city}:{wp_id}:location:{value}:{confidence}:{source}",
        "city": city, "wp_id": wp_id, "facet": "location", "proposed_value": value,
        "confidence": confidence, "source": source, "outcome": "review",
        "title": "t", "excerpt": "e", "text_excerpt": "b", "categories": [],
    }


def test_stratified_sample_keeps_090_cells_separate():
    site_home = [_row("jakarta", i, "jakarta", 0.90, "inferred", key=f"sh-{i}") for i in range(20)]
    title_match = [_row("jakarta", 100 + i, "senopati", 0.90, "ai", key=f"tm-{i}") for i in range(20)]
    sample = stratified_sample(site_home + title_match)
    sources = {r["source"] for r in sample}
    assert sources == {"inferred", "ai"}


def test_validation_prompt_lists_all_candidates_and_stays_blind():
    messages = build_validation_prompt("Title", "Excerpt", "Body text", ["bali", "lombok"])
    rendered = "\n".join(m["content"] for m in messages)
    assert "bali" in rendered and "lombok" in rendered
    for forbidden in ("wp category", "confidence", "category-fixed", "decided_by"):
        assert forbidden not in rendered.lower()

from now_eval.calibration.strata import FrameRecord, stratified_sample, target_n


def test_target_n_caps_at_population():
    assert target_n(0.95, 5) == 5
    assert target_n(0.95, 1000) == 25


def test_target_n_default_for_unknown_value():
    assert target_n(0.61, 1000) == 15


def test_target_n_covers_subtypes_own_confidence_values():
    # 0.70 (subtype keyword match) and 0.35 (subtype no-match fallback) are
    # F115's additions -- distinct from every type/format value, so this
    # cannot change type/format's existing sampling.
    assert target_n(0.70, 1000) == 35
    assert target_n(0.35, 1000) == 15
    # 0.70 is subtype's biggest single review population and the newest,
    # least-evidenced instrument -- it must get the largest n of the two.
    assert target_n(0.70, 1000) > target_n(0.35, 1000)


def test_stratified_sample_keeps_subtype_cells_independent_of_type_at_same_confidence():
    # subtype reuses 0.95/0.75 (CATEGORY_FIXED_CONFIDENCE) -- a subtype cell
    # at 0.95 must not be pooled with a type cell also at 0.95.
    records = _records("jakarta", "type", 0.95, {"eat": 100}) + _records(
        "jakarta", "subtype", 0.95, {"restaurant": 100}, seed="subtype"
    )
    sample = stratified_sample(records)
    type_n = sum(1 for r in sample if r.facet == "type")
    subtype_n = sum(1 for r in sample if r.facet == "subtype")
    assert type_n == target_n(0.95, 100)
    assert subtype_n == target_n(0.95, 100)


def _records(city, facet, confidence, values_and_counts, seed="k"):
    out = []
    i = 0
    for value, count in values_and_counts.items():
        for _ in range(count):
            out.append(FrameRecord(key=f"{seed}-{i}", city=city, facet=facet, proposed_value=value, confidence=confidence))
            i += 1
    return out


def test_stratified_sample_respects_cell_target():
    records = _records("jakarta", "type", 0.95, {"eat": 200, "event": 50})
    sample = stratified_sample(records)
    assert len(sample) == target_n(0.95, 250)


def test_stratified_sample_spreads_across_values_not_just_the_largest():
    # 190 'eat' vs 10 'event' at n=25 -- a plain random sample would almost
    # certainly draw zero 'event' rows; the round-robin must not.
    records = _records("jakarta", "type", 0.95, {"eat": 190, "event": 10})
    sample = stratified_sample(records)
    values = {r.proposed_value for r in sample}
    assert "event" in values
    assert "eat" in values


def test_stratified_sample_is_deterministic():
    records = _records("bali", "format", 0.72, {"news": 40, "guide": 30, "review": 20})
    a = stratified_sample(records)
    b = stratified_sample(records)
    assert [r.key for r in a] == [r.key for r in b]


def test_stratified_sample_keeps_cells_independent():
    records = _records("jakarta", "type", 0.95, {"eat": 100}) + _records(
        "bali", "type", 0.95, {"eat": 100}, seed="bali"
    )
    sample = stratified_sample(records)
    jakarta_n = sum(1 for r in sample if r.city == "jakarta")
    bali_n = sum(1 for r in sample if r.city == "bali")
    assert jakarta_n == target_n(0.95, 100)
    assert bali_n == target_n(0.95, 100)

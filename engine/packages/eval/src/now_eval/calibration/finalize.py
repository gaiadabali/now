"""Step 7: pull the whole calibration together into one report -- population
counts (live DB, for the coverage-impact simulation), preliminary LLM-vs-
classifier agreement (available immediately, before any adjudication), and
-- once `calibration_verdicts.json` / `location_calibration_verdicts.json`
exist (exported from the HTML tool) -- the real adjudicated accuracy
estimates and the evidence-based mapping recommendation.

Always states which numbers are `preliminary` (agreement only) vs
`adjudicated` (human-verified) -- see `analyze.py`'s module docstring for
why the distinction matters.
"""
from __future__ import annotations

import json
from pathlib import Path

from .analyze import build_cell_estimates, preliminary_agreement_rate
from .mapping import combine_across_cells, recommend, simulate_coverage
from .stats import wilson_interval


def type_format_population_counts(root: Path) -> dict[str, int]:
    """`{city}:{facet}:{confidence}` -> full DB population (not sample
    size) -- read live rather than hardcoded so this stays correct if the
    audit re-runs after more articles are classified."""
    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import _load_term_map, build_sampling_frame
    from collections import Counter

    term_map = _load_term_map(create_engine(platform_database_url()))
    counts: Counter = Counter()
    for city in ("jakarta", "bali"):
        frame = build_sampling_frame(city, root, term_map)
        for row in frame:
            counts[f"{row['city']}:{row['facet']}:{round(row['confidence'], 2)}"] += 1
    return dict(counts)


def value_population_counts(root: Path) -> dict[float, int]:
    """Raw confidence value -> population, pooled across city AND facet --
    what `mapping.simulate_coverage` needs, since the gate compares one
    float regardless of which facet produced it."""
    from collections import Counter

    cell_counts = type_format_population_counts(root)
    out: Counter = Counter()
    for cell, n in cell_counts.items():
        _, _, value = cell.rpartition(":")
        out[round(float(value), 2)] += n
    return dict(out)


def subtype_population_counts(root: Path) -> dict[str, int]:
    """`{city}:subtype:{confidence}` -> full DB population. Kept as its own
    function (mirroring `type_format_population_counts`) rather than folded
    into it, because `subtype_value_population_counts` below deliberately
    does NOT pool with `value_population_counts` -- see that function's
    docstring."""
    from collections import Counter

    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import load_term_slug_map
    from .subtype import build_subtype_frame

    term_slug_map = load_term_slug_map(create_engine(platform_database_url()))
    counts: Counter = Counter()
    for city in ("jakarta", "bali"):
        frame = build_subtype_frame(city, root, term_slug_map)
        for row in frame:
            counts[f"{row['city']}:{row['facet']}:{round(row['confidence'], 2)}"] += 1
    return dict(counts)


def subtype_value_population_counts(root: Path) -> dict[float, int]:
    """Raw confidence value -> population, pooled across both cities, for
    `subtype` only. Deliberately kept SEPARATE from `value_population_counts`
    (type/format): `subtype` reuses the same `CATEGORY_FIXED_CONFIDENCE`
    numbers (0.95/0.75/0.45) as type/format, so pooling all three facets'
    populations under one number would be defensible in principle (the gate
    genuinely does compare one float regardless of facet) -- but it would
    also silently blend three independently-measured instruments' coverage
    impact into a single number nobody asked for, obscuring subtype's own
    6,023-row queue behind type/format's much larger one. Reported
    separately so "what would fixing 0.75 do to the SUBTYPE queue
    specifically" stays answerable on its own. See PROVENANCE.md §8.6."""
    from collections import Counter

    cell_counts = subtype_population_counts(root)
    out: Counter = Counter()
    for cell, n in cell_counts.items():
        _, _, value = cell.rpartition(":")
        out[round(float(value), 2)] += n
    return dict(out)


def location_population_counts(root: Path) -> dict[str, int]:
    """`{city}:{provenance}` -> full DB population."""
    from collections import Counter

    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import load_term_slug_map
    from .location import build_location_frame

    term_slug_map = load_term_slug_map(create_engine(platform_database_url()))
    counts: Counter = Counter()
    for city in ("jakarta", "bali"):
        frame = build_location_frame(city, root, term_slug_map)
        for row in frame:
            counts[f"{row['city']}:{row['provenance']}"] += 1
    return dict(counts)


def _as_plain(obj):
    """Recursively flatten dataclasses (and the nested intervals inside them)
    into json-serialisable primitives, leaving plain values untouched."""
    import dataclasses
    import math

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _as_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _as_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_as_plain(v) for v in obj]
    # NaN is legal in Python but not in strict JSON, and these estimates
    # produce it for cells with no adjudicated rows.
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def load_verdicts(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


SUBTYPE_CONFIDENCE_VALUES = (0.95, 0.75, 0.70, 0.45, 0.35)


def build_report(root: Path, calibration_dir: Path) -> dict:
    from .adjudication import merge as merge_tf
    from .location import merge as merge_loc

    sample_rows = [json.loads(l) for l in open(calibration_dir / "sample.jsonl", encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(calibration_dir / "llm_labels.jsonl", encoding="utf-8") if l.strip()]
    merged_tf = merge_tf(sample_rows, llm_labels)

    loc_sample_rows = [json.loads(l) for l in open(calibration_dir / "location_sample.jsonl", encoding="utf-8") if l.strip()] \
        if (calibration_dir / "location_sample.jsonl").is_file() else []
    loc_llm_labels = [json.loads(l) for l in open(calibration_dir / "location_llm_labels.jsonl", encoding="utf-8") if l.strip()] \
        if (calibration_dir / "location_llm_labels.jsonl").is_file() else []
    merged_loc = merge_loc(loc_sample_rows, loc_llm_labels) if loc_sample_rows else []

    # subtype (F115) -- reuses `adjudication.merge` unchanged: it is already
    # facet-agnostic (`label.get(row["facet"])` picks up the "subtype" key
    # generically). See `subtype.py` module docstring.
    subtype_sample_rows = [json.loads(l) for l in open(calibration_dir / "subtype_sample.jsonl", encoding="utf-8") if l.strip()] \
        if (calibration_dir / "subtype_sample.jsonl").is_file() else []
    subtype_llm_labels = [json.loads(l) for l in open(calibration_dir / "subtype_llm_labels.jsonl", encoding="utf-8") if l.strip()] \
        if (calibration_dir / "subtype_llm_labels.jsonl").is_file() else []
    merged_subtype = merge_tf(subtype_sample_rows, subtype_llm_labels) if subtype_sample_rows else []

    tf_verdicts = load_verdicts(calibration_dir / "calibration_verdicts.json")
    loc_verdicts = load_verdicts(calibration_dir / "location_calibration_verdicts.json")
    subtype_verdicts = load_verdicts(calibration_dir / "subtype_calibration_verdicts.json")

    tf_pop = type_format_population_counts(root)
    value_pop = value_population_counts(root)
    loc_pop = location_population_counts(root)
    subtype_pop = subtype_population_counts(root)
    subtype_value_pop = subtype_value_population_counts(root)

    tf_prelim = preliminary_agreement_rate(merged_tf)
    tf_estimates = build_cell_estimates(merged_tf, tf_verdicts, tf_pop) if tf_verdicts else {}

    subtype_prelim = preliminary_agreement_rate(merged_subtype) if merged_subtype else {}
    subtype_estimates = build_cell_estimates(merged_subtype, subtype_verdicts, subtype_pop) if subtype_verdicts else {}

    loc_prelim = {}
    if merged_loc:
        from collections import defaultdict

        n, agree = defaultdict(int), defaultdict(int)
        for r in merged_loc:
            cell = f"{r['city']}:{r['provenance']}"
            n[cell] += 1
            if r["agree"]:
                agree[cell] += 1
        loc_prelim = {c: agree[c] / n[c] for c in n}

    recommendations = {}
    if tf_verdicts:
        for value in (0.95, 0.93, 0.75, 0.72, 0.45, 0.40):
            recommendations[value] = recommend(value, tf_estimates)

    coverage_impacts = []
    if recommendations:
        coverage_impacts = simulate_coverage(list(recommendations.values()), value_pop)

    # subtype's own recommendation/coverage pass, pooled SEPARATELY from
    # type/format's (see `subtype_value_population_counts` docstring) --
    # `mapping.combine_across_cells` only matches cells inside
    # `subtype_estimates`, so this cannot pick up a type/format cell.
    subtype_recommendations = {}
    if subtype_verdicts:
        for value in SUBTYPE_CONFIDENCE_VALUES:
            subtype_recommendations[value] = recommend(value, subtype_estimates)

    subtype_coverage_impacts = []
    if subtype_recommendations:
        subtype_coverage_impacts = simulate_coverage(list(subtype_recommendations.values()), subtype_value_pop)

    return {
        "n_sample_rows_type_format": len(sample_rows),
        "n_labelled_type_format": len(merged_tf),
        "n_sample_rows_location": len(loc_sample_rows),
        "n_labelled_location": len(merged_loc),
        "n_sample_rows_subtype": len(subtype_sample_rows),
        "n_labelled_subtype": len(merged_subtype),
        "type_format_population": tf_pop,
        "value_population": value_pop,
        "location_population": loc_pop,
        "subtype_population": subtype_pop,
        "subtype_value_population": subtype_value_pop,
        "preliminary_agreement_type_format": tf_prelim,
        "preliminary_agreement_location": loc_prelim,
        "preliminary_agreement_subtype": subtype_prelim,
        "adjudicated": bool(tf_verdicts),
        "adjudicated_location": bool(loc_verdicts),
        "adjudicated_subtype": bool(subtype_verdicts),
        "n_adjudications_type_format": len(tf_verdicts),
        "n_adjudications_location": len(loc_verdicts),
        "n_adjudications_subtype": len(subtype_verdicts),
        # These three are the entire point of the adjudication pass and were
        # computed above but never returned -- so `report` emitted only the
        # PRELIMINARY (LLM-proxy) agreement even with `adjudicated: true`,
        # silently discarding the measured accuracy, the recommended mapping
        # and the coverage simulation. Found when Hansel's 405 verdicts came
        # back and the report showed nothing new.
        # `TwoStageEstimate` / `ValueRecommendation` / `CoverageImpact` are
        # dataclasses, so they must be flattened before json.dumps -- the
        # earlier omission may well have started as a serialisation error
        # that got "fixed" by dropping the keys instead.
        "adjudicated_estimates_type_format": {k: _as_plain(v) for k, v in tf_estimates.items()},
        "mapping_recommendations": {str(k): _as_plain(v) for k, v in recommendations.items()},
        "coverage_impacts": [_as_plain(c) for c in coverage_impacts],
        # Same three, for subtype (F115) -- covered by
        # tests/calibration/test_finalize.py's F114-class regression test.
        "adjudicated_estimates_subtype": {k: _as_plain(v) for k, v in subtype_estimates.items()},
        "subtype_mapping_recommendations": {str(k): _as_plain(v) for k, v in subtype_recommendations.items()},
        "subtype_coverage_impacts": [_as_plain(c) for c in subtype_coverage_impacts],
    }

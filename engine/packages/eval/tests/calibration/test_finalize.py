"""Regression coverage for the F114 class of bug: `build_report` computed
`tf_estimates` / `recommendations` / `coverage_impacts` and then omitted all
three from its returned dict, so the CLI printed only preliminary LLM-proxy
agreement even with `"adjudicated": true` -- Hansel's 405 real verdicts
produced visibly identical output until this was caught and fixed.

No test existed for `finalize.build_report` before this file. These tests
exercise the exact failure shape (adjudication verdicts present -> the
computed numbers must appear in the OUTPUT, not just flip an internal
flag) for both the pre-existing type/format path and the subtype path this
ticket (F115) adds -- the whole point of writing it is that the same silent
omission must not be reintroduced for subtype.

All DB-touching population-count functions are monkeypatched: this test
must run without a live database (the `calibration` extra's own tests stay
opt-in-network-free wherever the logic under test doesn't itself require
the DB).
"""
from __future__ import annotations

import json

from now_eval.calibration import finalize as fin


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def _stub_population_counts(monkeypatch, *, subtype_pop=None, subtype_value_pop=None):
    monkeypatch.setattr(fin, "type_format_population_counts", lambda root: {})
    monkeypatch.setattr(fin, "value_population_counts", lambda root: {})
    monkeypatch.setattr(fin, "location_population_counts", lambda root: {})
    monkeypatch.setattr(fin, "subtype_population_counts", lambda root: subtype_pop or {})
    monkeypatch.setattr(fin, "subtype_value_population_counts", lambda root: subtype_value_pop or {})


def test_build_report_surfaces_adjudicated_type_format_estimates(tmp_path, monkeypatch):
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()

    sample_row = {
        "key": "jakarta:1:type", "city": "jakarta", "wp_id": 1, "facet": "type",
        "proposed_value": "eat", "confidence": 0.93, "outcome": "review",
        "title": "t", "excerpt": "e", "text_excerpt": "b", "categories": [],
    }
    llm_label = {"city": "jakarta", "wp_id": 1, "type": "drink", "format": "review",
                 "type_reasoning": "r", "format_reasoning": "r", "error": None}
    _write_jsonl(calib_dir / "sample.jsonl", [sample_row])
    _write_jsonl(calib_dir / "llm_labels.jsonl", [llm_label])
    (calib_dir / "calibration_verdicts.json").write_text(
        json.dumps({sample_row["key"] + ":disagreement": "classifier"}), encoding="utf-8",
    )

    _stub_population_counts(monkeypatch)

    report = fin.build_report(tmp_path, calib_dir)

    assert report["adjudicated"] is True
    # This is the exact shape of the F114 bug: these three keys must be
    # present AND non-empty once verdicts exist, not just the boolean flag.
    assert report["adjudicated_estimates_type_format"], "adjudicated estimates were computed and then dropped"
    assert report["mapping_recommendations"], "mapping recommendations were computed and then dropped"
    assert report["coverage_impacts"] is not None
    cell = report["adjudicated_estimates_type_format"]["jakarta:type:0.93"]
    assert cell["n_disagree_adjudicated_correct_for_classifier"] == 1


def test_build_report_surfaces_adjudicated_subtype_estimates_end_to_end(tmp_path, monkeypatch):
    """The path this ticket (F115) adds. Must not repeat F114 for subtype."""
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()

    _write_jsonl(calib_dir / "sample.jsonl", [])
    _write_jsonl(calib_dir / "llm_labels.jsonl", [])

    # One disagreement (classifier vs blind LLM) + one control agreement --
    # the two-stage estimator (`stats.estimate_cell_accuracy`) needs at
    # least one adjudicated agreement to produce a non-NaN accuracy point
    # (see `stats.py`); a cell with zero adjudicated agreements reports
    # "not enough evidence yet" by design, which is correct behaviour but
    # not what this test is exercising.
    disagree_row = {
        "key": "jakarta:1:subtype", "city": "jakarta", "wp_id": 1, "facet": "subtype",
        "proposed_value": "restaurant", "confidence": 0.70, "source": "ai", "outcome": "review",
        "title": "t", "excerpt": "e", "text_excerpt": "b", "categories": [],
    }
    agree_row = {
        "key": "jakarta:2:subtype", "city": "jakarta", "wp_id": 2, "facet": "subtype",
        "proposed_value": "cafe", "confidence": 0.70, "source": "ai", "outcome": "review",
        "title": "t2", "excerpt": "e2", "text_excerpt": "b2", "categories": [],
    }
    llm_labels = [
        {"city": "jakarta", "wp_id": 1, "subtype": "cafe", "reasoning": "r",
         "format_reasoning": "r", "raw": "", "error": None},
        {"city": "jakarta", "wp_id": 2, "subtype": "cafe", "reasoning": "r",
         "format_reasoning": "r", "raw": "", "error": None},
    ]
    _write_jsonl(calib_dir / "subtype_sample.jsonl", [disagree_row, agree_row])
    _write_jsonl(calib_dir / "subtype_llm_labels.jsonl", llm_labels)
    (calib_dir / "subtype_calibration_verdicts.json").write_text(
        json.dumps({
            disagree_row["key"] + ":disagreement": "classifier",
            agree_row["key"] + ":control": "classifier",
        }),
        encoding="utf-8",
    )

    _stub_population_counts(monkeypatch, subtype_pop={"jakarta:subtype:0.7": 2}, subtype_value_pop={0.70: 2})

    report = fin.build_report(tmp_path, calib_dir)

    assert report["adjudicated_subtype"] is True
    assert report["n_adjudications_subtype"] == 2
    assert report["adjudicated_estimates_subtype"], "subtype adjudicated estimates were computed and then dropped"
    cell = report["adjudicated_estimates_subtype"]["jakarta:subtype:0.7"]
    assert cell["n_disagree_adjudicated_correct_for_classifier"] == 1
    assert report["subtype_mapping_recommendations"], "subtype mapping recommendations were dropped"
    assert report["subtype_mapping_recommendations"]["0.7"]["accuracy_point"] == 1.0
    assert report["subtype_coverage_impacts"], "subtype coverage simulation was computed and then dropped"


def test_build_report_without_any_verdicts_stays_preliminary_only(tmp_path, monkeypatch):
    """Before adjudication, the adjudicated-* keys must be present but
    empty/false -- distinguishing 'not adjudicated yet' from 'adjudicated
    but silently dropped' is the entire point of this file."""
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()
    _write_jsonl(calib_dir / "sample.jsonl", [])
    _write_jsonl(calib_dir / "llm_labels.jsonl", [])
    _stub_population_counts(monkeypatch)

    report = fin.build_report(tmp_path, calib_dir)

    assert report["adjudicated"] is False
    assert report["adjudicated_subtype"] is False
    assert report["adjudicated_estimates_type_format"] == {}
    assert report["adjudicated_estimates_subtype"] == {}
    assert report["mapping_recommendations"] == {}
    assert report["subtype_mapping_recommendations"] == {}

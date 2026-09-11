import json

from now_eval.baseline import (
    build_baseline_document,
    check_gates,
    load_baseline,
    save_baseline,
)
from now_eval.harness import HarnessReport, SurfaceResult


def _make_report(
    related=0.6, search=0.7, facet_precision=0.9, facet_recall=0.9, type_acc=0.97
) -> HarnessReport:
    return HarnessReport(
        {
            "related_articles": SurfaceResult("related_articles", "precision@6", related, 200),
            "search": SurfaceResult("search", "ndcg@10", search, 200),
            "facet_tagging": SurfaceResult(
                "facet_tagging", "precision", facet_precision, 222, extra={"recall": facet_recall}
            ),
            "type_classification": SurfaceResult("type_classification", "accuracy", type_acc, 200),
        }
    )


def test_no_baseline_yet_min_thresholds_still_enforced():
    report = _make_report(facet_precision=0.5, type_acc=0.5)
    failures = check_gates(report, baseline=None)
    surfaces = {f.gate.surface for f in failures}
    assert "facet_tagging" in surfaces
    assert "type_classification" in surfaces
    # no_regression gates cannot fail with no baseline recorded
    assert "related_articles" not in surfaces
    assert "search" not in surfaces


def test_passing_report_has_no_failures():
    report = _make_report()
    failures = check_gates(report, baseline=None)
    assert failures == []


def test_min_threshold_gate_hand_computed_boundary():
    # Exactly at threshold must pass (>=, not >).
    report = _make_report(facet_precision=0.85, facet_recall=0.85, type_acc=0.95)
    failures = check_gates(report, baseline=None)
    assert failures == []


def test_min_threshold_gate_fails_just_below_boundary():
    report = _make_report(type_acc=0.9499)
    failures = check_gates(report, baseline=None)
    assert any(f.gate.surface == "type_classification" for f in failures)


def test_deliberate_regression_is_caught_by_no_regression_gate():
    baseline_report = _make_report(related=0.6, search=0.7)
    baseline_doc = build_baseline_document(baseline_report, sut_name="trivial-most-popular", label="test-baseline")

    # Simulate a deliberately regressed later run: related-articles
    # precision@6 drops from 0.6 to 0.4.
    regressed_report = _make_report(related=0.4, search=0.7)
    failures = check_gates(regressed_report, baseline_doc)

    assert len(failures) == 1
    assert failures[0].gate.surface == "related_articles"
    assert failures[0].current == 0.4
    assert failures[0].baseline == 0.6


def test_improvement_never_fails_no_regression_gate():
    baseline_report = _make_report(related=0.4)
    baseline_doc = build_baseline_document(baseline_report, sut_name="x", label="y")
    improved_report = _make_report(related=0.9)
    assert check_gates(improved_report, baseline_doc) == []


def test_equal_to_baseline_passes_exactly():
    baseline_report = _make_report(related=0.5)
    baseline_doc = build_baseline_document(baseline_report, sut_name="x", label="y")
    same_report = _make_report(related=0.5)
    assert check_gates(same_report, baseline_doc) == []


def test_save_and_load_baseline_roundtrip(tmp_path):
    report = _make_report()
    doc = build_baseline_document(report, sut_name="trivial-random", label="first baseline")
    path = tmp_path / "baseline.json"
    save_baseline(doc, path)

    loaded = load_baseline(path)
    assert loaded is not None
    assert loaded["sut_name"] == "trivial-random"
    assert loaded["results"]["related_articles"]["value"] == report.results["related_articles"].value

    # Written JSON should be human-diffable in a PR (indented, stable key order).
    raw = path.read_text(encoding="utf-8")
    assert json.loads(raw) == loaded


def test_load_baseline_missing_file_returns_none(tmp_path):
    assert load_baseline(tmp_path / "does_not_exist.json") is None

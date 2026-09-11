"""End-to-end CLI tests (via Click's CliRunner, the actual entrypoint
CI invokes) against the small synthetic fixture -- fast and hermetic,
independent of the real archive. This is what makes the "CI fails on a
deliberately regressed result" acceptance criterion checked by an
actual automated test, not only a manually-run demonstration.
"""
import json

from click.testing import CliRunner

from now_eval.cli import cli


def _run(runner, args):
    result = runner.invoke(cli, args)
    return result


def test_build_datasets_end_to_end(tmp_path, articles_sample_path, taxonomy_sample_path):
    runner = CliRunner()
    out_dir = tmp_path / "data"
    result = _run(
        runner,
        [
            "build-datasets",
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "related_articles.labelled.jsonl").exists()
    assert (out_dir / "search_queries.provisional.jsonl").exists()
    assert (out_dir / "facet_labels.holdout.jsonl").exists()
    assert (out_dir / "type_labels.sample.jsonl").exists()

    # Cross-check against the hand-derived counts in test_datasets.py.
    type_rows = [json.loads(l) for l in (out_dir / "type_labels.sample.jsonl").read_text().splitlines()]
    assert len(type_rows) == 6
    facet_rows = [json.loads(l) for l in (out_dir / "facet_labels.holdout.jsonl").read_text().splitlines()]
    assert len(facet_rows) == 4


def test_build_datasets_is_idempotent(tmp_path, articles_sample_path, taxonomy_sample_path):
    runner = CliRunner()
    out1, out2 = tmp_path / "run1", tmp_path / "run2"
    for out_dir in (out1, out2):
        _run(
            runner,
            [
                "build-datasets",
                "--articles",
                str(articles_sample_path),
                "--taxonomy",
                str(taxonomy_sample_path),
                "--out-dir",
                str(out_dir),
            ],
        )
    for name in (
        "related_articles.labelled.jsonl",
        "search_queries.provisional.jsonl",
        "facet_labels.holdout.jsonl",
        "type_labels.sample.jsonl",
    ):
        assert (out1 / name).read_text() == (out2 / name).read_text(), f"{name} not byte-identical across runs"


def test_run_and_record_baseline_end_to_end(tmp_path, articles_sample_path, taxonomy_sample_path):
    runner = CliRunner()
    baseline_path = tmp_path / "baseline.json"
    result = _run(
        runner,
        [
            "run",
            "--sut",
            "trivial-random",
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--record-baseline",
            str(baseline_path),
            "--label",
            "test baseline",
        ],
    )
    assert result.exit_code == 0, result.output
    assert baseline_path.exists()
    doc = json.loads(baseline_path.read_text())
    assert doc["sut_name"] == "trivial-random"
    assert doc["label"] == "test baseline"
    assert set(doc["results"]) == {"related_articles", "search", "facet_tagging", "type_classification"}


def test_check_passes_no_regression_against_its_own_recorded_baseline(
    tmp_path, articles_sample_path, taxonomy_sample_path
):
    runner = CliRunner()
    baseline_path = tmp_path / "baseline.json"
    _run(
        runner,
        [
            "run",
            "--sut",
            "trivial-random",
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--record-baseline",
            str(baseline_path),
        ],
    )
    # Same SUT, same source data, same deterministic seed -> identical
    # results -> no regression -> the no-regression gate must pass.
    result = _run(
        runner,
        [
            "check",
            "--sut",
            "trivial-random",
            "--baseline",
            str(baseline_path),
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--gates",
            "no-regression",
        ],
    )
    assert result.exit_code == 0, result.output


def test_check_fails_on_deliberately_regressed_baseline(tmp_path, articles_sample_path, taxonomy_sample_path):
    """The acceptance-criterion test: CI's exact entrypoint (`now-eval
    check`) must exit non-zero when the current run scores below a
    recorded baseline. We simulate "a later change regressed
    related_articles precision" by recording a real run's baseline and
    then editing the recorded related_articles value upward (as if a
    better system had been recorded previously), then re-running the
    same (unchanged) SUT and confirming the no-regression gate fires.
    """
    runner = CliRunner()
    baseline_path = tmp_path / "baseline.json"
    _run(
        runner,
        [
            "run",
            "--sut",
            "trivial-random",
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--record-baseline",
            str(baseline_path),
        ],
    )

    doc = json.loads(baseline_path.read_text())
    original_value = doc["results"]["related_articles"]["value"]
    doc["results"]["related_articles"]["value"] = original_value + 0.5  # force a regression
    baseline_path.write_text(json.dumps(doc))

    result = _run(
        runner,
        [
            "check",
            "--sut",
            "trivial-random",
            "--baseline",
            str(baseline_path),
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--gates",
            "no-regression",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "related_articles" in result.output
    assert "regressed below baseline" in result.output


def test_check_all_gates_reports_hard_threshold_failures_for_trivial_sut(
    tmp_path, articles_sample_path, taxonomy_sample_path
):
    """Documents the expected, correct behaviour: --gates all against a
    trivial baseline fails the hard §17 minimums. This is not a defect
    -- it is direct evidence the facet/type gates have teeth (see
    tests/test_baseline.py for the gate arithmetic in isolation)."""
    runner = CliRunner()
    baseline_path = tmp_path / "baseline.json"
    _run(
        runner,
        [
            "run",
            "--sut",
            "trivial-random",
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--record-baseline",
            str(baseline_path),
        ],
    )
    result = _run(
        runner,
        [
            "check",
            "--sut",
            "trivial-random",
            "--baseline",
            str(baseline_path),
            "--articles",
            str(articles_sample_path),
            "--taxonomy",
            str(taxonomy_sample_path),
            "--gates",
            "all",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "required minimum" in result.output

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .baseline import build_baseline_document, check_gates, load_baseline, save_baseline
from .datasets.facet_labels import build_facet_labels
from .datasets.related_articles import build_related_articles_labels
from .datasets.search_queries import build_provisional_query_set
from .datasets.sources import load_articles
from .datasets.type_labels import build_type_labels
from .harness import run_harness
from .sut import TrivialMostPopularSUT, TrivialRandomSUT

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _dataclass_to_dict(obj) -> dict:
    from dataclasses import asdict, is_dataclass

    return asdict(obj) if is_dataclass(obj) else obj


def _write_jsonl(rows, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(_dataclass_to_dict(row), sort_keys=True) + "\n")


@click.group()
def cli() -> None:
    """now-eval -- E2.7 evaluation harness + CI gate. See ARCHITECTURE.md §17."""


@cli.command("build-datasets")
@click.option("--articles", "articles_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--taxonomy", "taxonomy_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
def build_datasets(articles_path: Path | None, taxonomy_path: Path | None, out_dir: Path) -> None:
    """Regenerate every labelled set from articles.jsonl + taxonomy-mapping.json.

    Deterministic and idempotent: re-running with the same source files
    overwrites the outputs byte-for-byte (all sampling is seeded hashes
    of wp_id, never wall-clock or unseeded random state).
    """
    related = build_related_articles_labels(articles_path, taxonomy_path)
    _write_jsonl(related, out_dir / "related_articles.labelled.jsonl")
    click.echo(f"related_articles: {len(related)} queries -> {out_dir / 'related_articles.labelled.jsonl'}")

    search = build_provisional_query_set(articles_path, taxonomy_path)
    _write_jsonl(search, out_dir / "search_queries.provisional.jsonl")
    click.echo(f"search: {len(search)} queries -> {out_dir / 'search_queries.provisional.jsonl'}")

    facets = build_facet_labels(articles_path)
    _write_jsonl(facets, out_dir / "facet_labels.holdout.jsonl")
    click.echo(f"facet_tagging: {len(facets)} labels -> {out_dir / 'facet_labels.holdout.jsonl'}")

    types = build_type_labels(articles_path, taxonomy_path)
    _write_jsonl(types, out_dir / "type_labels.sample.jsonl")
    click.echo(f"type_classification: {len(types)} labels -> {out_dir / 'type_labels.sample.jsonl'}")


def _make_sut(name: str, articles_path: Path | None, taxonomy_path: Path | None):
    if name == "trivial-random":
        return TrivialRandomSUT(seed=0)
    if name == "trivial-most-popular":
        sut = TrivialMostPopularSUT()
        train_types = build_type_labels(articles_path, taxonomy_path, split="train")
        sut.fit_type({t.article_id: t.type for t in train_types})
        articles = load_articles(articles_path)
        # crude popularity proxy: corpus order (wp_id ascending) is the
        # closest thing to "recency" this baseline has without the
        # wpb_post_views_count field wired in -- fine for a trivial
        # baseline, not meant to be a real popularity prior.
        sut.fit_popularity_order([a.article_id for a in articles])
        return sut
    raise click.ClickException(f"unknown --sut {name!r} (expected trivial-random or trivial-most-popular)")


@cli.command("run")
@click.option("--sut", "sut_name", type=click.Choice(["trivial-random", "trivial-most-popular"]), required=True)
@click.option("--articles", "articles_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--taxonomy", "taxonomy_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--record-baseline", "baseline_path", type=click.Path(path_type=Path), default=None,
              help="If given, write the report as the new recorded baseline at this path.")
@click.option("--label", default="", help="Free-text note stored alongside a recorded baseline.")
def run(sut_name: str, articles_path: Path | None, taxonomy_path: Path | None, baseline_path: Path | None, label: str) -> None:
    """Run one SUT against every labelled set and print the report."""
    sut = _make_sut(sut_name, articles_path, taxonomy_path)
    report = run_harness(sut, articles_path=articles_path, taxonomy_path=taxonomy_path)
    click.echo(json.dumps(report.as_dict(), indent=2, sort_keys=True))

    if baseline_path is not None:
        dataset_counts = {name: r.n for name, r in report.results.items()}
        doc = build_baseline_document(report, sut_name=sut_name, label=label, dataset_counts=dataset_counts)
        save_baseline(doc, baseline_path)
        click.echo(f"\nBaseline recorded at {baseline_path} ({doc['recorded_at']})", err=True)


@cli.command("check")
@click.option("--sut", "sut_name", type=click.Choice(["trivial-random", "trivial-most-popular"]), required=True)
@click.option("--baseline", "baseline_path", type=click.Path(path_type=Path), required=True)
@click.option("--articles", "articles_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--taxonomy", "taxonomy_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option(
    "--gates",
    "gates",
    type=click.Choice(["all", "no-regression"]),
    default="all",
    help=(
        "'all' (default) enforces both the no-regression gates and the "
        "hard §17 minimums (facet>=0.85, type>=0.95) -- use this once a "
        "real SUT is wired in (E2.1/E2.2). 'no-regression' enforces only "
        "the no-regression gates -- use this for a trivial baseline, "
        "which is *expected* to fail the hard minimums (that failure is "
        "the metric working, not a bug)."
    ),
)
def check(
    sut_name: str,
    baseline_path: Path,
    articles_path: Path | None,
    taxonomy_path: Path | None,
    gates: str,
) -> None:
    """The CI entrypoint: run the harness, compare against the recorded
    baseline, exit non-zero on any failure. See --gates for which gate
    kinds are enforced."""
    sut = _make_sut(sut_name, articles_path, taxonomy_path)
    report = run_harness(sut, articles_path=articles_path, taxonomy_path=taxonomy_path)
    baseline = load_baseline(baseline_path)

    click.echo(json.dumps(report.as_dict(), indent=2, sort_keys=True))

    kinds = ("no_regression",) if gates == "no-regression" else ("no_regression", "min_threshold")
    failures = check_gates(report, baseline, kinds=kinds)
    if not failures:
        click.echo("\nAll gates passed.", err=True)
        return

    click.echo(f"\n{len(failures)} gate(s) failed:", err=True)
    for f in failures:
        click.echo(f"  - {f.detail}", err=True)
    sys.exit(1)


DEFAULT_CALIBRATION_DIR = DEFAULT_DATA_DIR / "calibration"


def _repo_root() -> Path:
    from .datasets.sources import find_repo_root

    return find_repo_root()


@cli.group("calibration")
def calibration() -> None:
    """F96/F97 confidence-mapping calibration (needs the `calibration` extra:
    `uv sync --extra calibration`). See `now_eval.calibration` package docstring."""


@calibration.command("sample")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "sample.jsonl")
def calibration_sample(out_path: Path) -> None:
    """Build the type/format sampling frame from live now_jakarta/now_bali
    and draw the stratified sample."""
    from .calibration.sample import build_and_sample, summarize, write_sample

    rows = build_and_sample(_repo_root())
    write_sample(rows, out_path)
    click.echo(json.dumps(summarize(rows), indent=2))
    click.echo(f"\nwritten to {out_path}", err=True)


@calibration.command("label")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "sample.jsonl")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "llm_labels.jsonl")
@click.option("--model", default=None, help="Override OLLAMA_CLOUD_MODEL_GENERAL")
def calibration_label(sample_path: Path, out_path: Path, model: str | None) -> None:
    """Blind-label every unique article in the sample via Ollama Cloud.
    Resumable: safe to re-run after an interruption."""
    from .calibration.label import label_sample

    stats = label_sample(sample_path, out_path, model=model)
    click.echo(json.dumps(stats, indent=2))


@calibration.command("location-sample")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "location_sample.jsonl")
def calibration_location_sample(out_path: Path) -> None:
    """Build the location sampling frame (stratified by source+confidence,
    i.e. category-fixed vs. title-match vs. site-home-fallback etc.)."""
    from .calibration.location import build_and_sample, summarize, write_sample

    rows = build_and_sample(_repo_root())
    write_sample(rows, out_path)
    click.echo(json.dumps(summarize(rows), indent=2))
    click.echo(f"\nwritten to {out_path}", err=True)


@calibration.command("location-label")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "location_sample.jsonl")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "location_llm_labels.jsonl")
@click.option("--model", default=None, help="Override OLLAMA_CLOUD_MODEL_FAST")
def calibration_location_label(sample_path: Path, out_path: Path, model: str | None) -> None:
    """Blind-validate every sampled proposed location via Ollama Cloud."""
    from .calibration.location import label_sample

    stats = label_sample(sample_path, out_path, model=model)
    click.echo(json.dumps(stats, indent=2))


@calibration.command("adjudication-prep")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "sample.jsonl")
@click.option("--labels", "labels_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "llm_labels.jsonl")
@click.option("--out-jsonl", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "adjudication_queue.jsonl")
@click.option("--out-html", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "adjudicate.html")
@click.option("--budget", type=int, default=220)
def calibration_adjudication_prep(sample_path: Path, labels_path: Path, out_jsonl: Path, out_html: Path, budget: int) -> None:
    """Merge type/format sample + LLM labels, build the adjudication queue
    (every disagreement + a proportional random control slice of
    agreements), and render the offline HTML tool."""
    from dataclasses import asdict

    from .calibration.adjudication import build_queue, merge, write_queue
    from .calibration.render_html import write_html

    sample_rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(labels_path, encoding="utf-8") if l.strip()]
    merged = merge(sample_rows, llm_labels)
    queue = build_queue(merged, total_budget=budget)
    write_queue(queue, out_jsonl)
    write_html([asdict(q) for q in queue], out_html)

    n_disagree = sum(1 for q in queue if q.kind == "disagreement")
    click.echo(f"merged {len(merged)} rows ({sum(1 for m in merged if not m['agree'])} disagreements observed)")
    click.echo(f"adjudication queue: {len(queue)} items ({n_disagree} disagreements + {len(queue) - n_disagree} control)")
    click.echo(f"queue: {out_jsonl}")
    click.echo(f"tool:  {out_html}  (open directly in a browser)")


@calibration.command("location-adjudication-prep")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "location_sample.jsonl")
@click.option("--labels", "labels_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "location_llm_labels.jsonl")
@click.option("--out-jsonl", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "location_adjudication_queue.jsonl")
@click.option("--out-html", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "location_adjudicate.html")
@click.option("--budget", type=int, default=150)
def calibration_location_adjudication_prep(sample_path: Path, labels_path: Path, out_jsonl: Path, out_html: Path, budget: int) -> None:
    """Same as `adjudication-prep`, for the location-validation pipeline."""
    from .calibration import location as loc
    from .calibration.render_html import write_html

    sample_rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    llm_verdicts = [json.loads(l) for l in open(labels_path, encoding="utf-8") if l.strip()]
    merged = loc.merge(sample_rows, llm_verdicts)
    queue = loc.build_queue(merged, total_budget=budget)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for item in queue:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_html(queue, out_html)

    n_disagree = sum(1 for q in queue if q["kind"] == "disagreement")
    click.echo(f"merged {len(merged)} rows ({sum(1 for m in merged if not m['agree'])} LLM-flagged-wrong observed)")
    click.echo(f"location adjudication queue: {len(queue)} items ({n_disagree} flagged + {len(queue) - n_disagree} control)")
    click.echo(f"queue: {out_jsonl}")
    click.echo(f"tool:  {out_html}  (open directly in a browser)")


@calibration.command("subtype-sample")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "subtype_sample.jsonl")
def calibration_subtype_sample(out_path: Path) -> None:
    """Build the subtype sampling frame from live now_jakarta/now_bali and
    draw the stratified sample (F115: subtype had no calibration coverage
    before this ticket). Reuses the type/format stratified-sampling engine
    unchanged -- see `now_eval.calibration.subtype` module docstring."""
    from .calibration.sample import summarize, write_sample
    from .calibration.subtype import build_and_sample

    rows = build_and_sample(_repo_root())
    write_sample(rows, out_path)
    click.echo(json.dumps(summarize(rows), indent=2))
    click.echo(f"\nwritten to {out_path}", err=True)


@calibration.command("subtype-label")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "subtype_sample.jsonl")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "subtype_llm_labels.jsonl")
@click.option("--model", default=None, help="Override OLLAMA_CLOUD_MODEL_GENERAL")
def calibration_subtype_label(sample_path: Path, out_path: Path, model: str | None) -> None:
    """Blind-label every unique article in the subtype sample via Ollama
    Cloud (forced choice over the full 66-slug vocabulary). Resumable."""
    from .calibration.subtype import label_sample

    stats = label_sample(sample_path, out_path, model=model)
    click.echo(json.dumps(stats, indent=2))


@calibration.command("subtype-adjudication-prep")
@click.option("--sample", "sample_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "subtype_sample.jsonl")
@click.option("--labels", "labels_path", type=click.Path(exists=True, path_type=Path),
              default=DEFAULT_CALIBRATION_DIR / "subtype_llm_labels.jsonl")
@click.option("--out-jsonl", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "subtype_adjudication_queue.jsonl")
@click.option("--out-html", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR / "subtype_adjudicate.html")
@click.option("--budget", type=int, default=150)
def calibration_subtype_adjudication_prep(sample_path: Path, labels_path: Path, out_jsonl: Path, out_html: Path, budget: int) -> None:
    """Merge subtype sample + LLM labels, build the adjudication queue
    (every disagreement + a proportional random control slice of
    agreements), and render the offline HTML tool. Reuses the type/format
    adjudication engine unchanged -- see `now_eval.calibration.subtype`
    module docstring for why that's safe."""
    from dataclasses import asdict

    from .calibration.adjudication import build_queue, merge, write_queue
    from .calibration.render_html import write_html

    sample_rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(labels_path, encoding="utf-8") if l.strip()]
    merged = merge(sample_rows, llm_labels)
    queue = build_queue(merged, total_budget=budget,
                         seed="now-eval-calibration-subtype-adjudication-v1")
    write_queue(queue, out_jsonl)
    write_html([asdict(q) for q in queue], out_html)

    n_disagree = sum(1 for q in queue if q.kind == "disagreement")
    click.echo(f"merged {len(merged)} rows ({sum(1 for m in merged if not m['agree'])} disagreements observed)")
    click.echo(f"subtype adjudication queue: {len(queue)} items ({n_disagree} disagreements + {len(queue) - n_disagree} control)")
    click.echo(f"queue: {out_jsonl}")
    click.echo(f"tool:  {out_html}  (open directly in a browser)")


@calibration.command("report")
@click.option("--calibration-dir", type=click.Path(path_type=Path), default=DEFAULT_CALIBRATION_DIR)
def calibration_report(calibration_dir: Path) -> None:
    """Print the current state of the calibration: population counts,
    preliminary LLM-vs-classifier agreement, and -- once
    calibration_verdicts.json / location_calibration_verdicts.json exist --
    the adjudicated accuracy + mapping recommendation."""
    from .calibration.finalize import build_report

    report = build_report(_repo_root(), calibration_dir)
    click.echo(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()

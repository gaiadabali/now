"""`now-partner-roster build articles.jsonl -o partner_roster.jsonl` — batch
runner over the E1.1-contract JSONL, producing the E1.5 deliverables:
`partner_roster.jsonl`, `partner_roster_exclusions.jsonl`, and
`partner_roster.md`.

Re-runnable / idempotent: `run()` is a pure function of the input file's
contents (plus the static heuristic tables in `domains.py`/`cluster.py`),
so re-running over the same input overwrites the outputs with
byte-identical content — no external state is read or written.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import click

from now_partner_roster.pipeline import iter_jsonl, run
from now_partner_roster.report import render_markdown


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output", "output_path", type=click.Path(path_type=Path), required=True,
    help="partner_roster.jsonl output path",
)
@click.option(
    "--exclusions", "exclusions_path", type=click.Path(path_type=Path), default=None,
    help="exclusion-list JSONL output path (default: <output>_exclusions.jsonl next to --output)",
)
@click.option(
    "--markdown", "markdown_path", type=click.Path(path_type=Path), default=None,
    help="human-readable summary path (default: <output stem>.md next to --output)",
)
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="optional machine-readable stats JSON")
def build(
    input_path: Path,
    output_path: Path,
    exclusions_path: Path | None,
    markdown_path: Path | None,
    report_path: Path | None,
) -> None:
    """Cluster outbound links from INPUT_PATH (JSONL, E1.1 contract) into a
    candidate partner-org roster."""

    if exclusions_path is None:
        exclusions_path = output_path.with_name(output_path.stem + "_exclusions.jsonl")
    if markdown_path is None:
        markdown_path = output_path.with_suffix(".md")

    org_rows, exclusions, stats = run(iter_jsonl(input_path))

    ranked = sorted(org_rows, key=lambda r: (-r.link_count, r.org_slug))

    with output_path.open("w", encoding="utf-8") as fout:
        for row in ranked:
            record = dataclasses.asdict(row)
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    with exclusions_path.open("w", encoding="utf-8") as fout:
        for exc in sorted(exclusions, key=lambda e: (-e.link_count, e.domain)):
            record = {
                "domain": exc.domain,
                "reason": exc.reason,
                "link_count": exc.link_count,
                "article_count": len(exc.article_ids),
                "sample_articles": exc.sample_articles,
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

    markdown_path.write_text(render_markdown(org_rows, exclusions, stats), encoding="utf-8")

    report = {
        "articles": stats.articles,
        "articles_with_ext_link": stats.articles_with_ext_link,
        "total_raw_hrefs": stats.total_raw_hrefs,
        "total_upload_links": stats.total_upload_links,
        "total_non_http_links": stats.total_non_http_links,
        "total_external_links": stats.total_external_links,
        "total_excluded_links": stats.total_excluded_links,
        "total_candidate_links": stats.total_candidate_links,
        "distinct_domains_candidate": stats.distinct_domains_candidate,
        "distinct_domains_excluded": stats.distinct_domains_excluded,
        "orgs": len(org_rows),
        "orgs_synthesized": sum(1 for r in org_rows if r.synthesized),
        "orgs_flagged_ambiguous": sum(1 for r in org_rows if r.notes),
        "orgs_with_parent": sum(1 for r in org_rows if r.parent_org_slug),
        "rel_totals": stats.rel_totals,
    }
    click.echo(json.dumps(report, indent=2))
    if report_path:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    cli()

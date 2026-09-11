"""`now-content-clean clean articles.jsonl -o blocks.jsonl` — batch runner
over the E1.1-contract JSONL, used both for local verification during this
ticket and, later, by E1.8's loader.

Re-runnable / idempotent: re-running over the same input file overwrites
the output with byte-identical content (the pipeline is a pure function of
`content_html`); no state is read from or written to anything but the two
files named on the command line.
"""

from __future__ import annotations

import dataclasses
import json
import statistics
from collections import Counter
from pathlib import Path

import click

from now_content_clean.pipeline import clean_article


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None)
def clean(input_path: Path, output_path: Path, report_path: Path | None) -> None:
    """Convert every article's `content_html` in INPUT_PATH (JSONL,
    E1.1 contract) into blocks, writing one JSON object per line to
    --output: {"wp_id":..., "blocks":[...], "links":[...], "uploads":[...], "stats":{...}}."""
    n = 0
    loss_pcts: list[float] = []
    outliers: list[dict] = []
    unhandled_tags: Counter = Counter()
    gutenberg_types: Counter = Counter()
    dropped_reasons: Counter = Counter()

    with input_path.open(encoding="utf-8") as fin, output_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            result = clean_article(article)
            n += 1

            record = {
                "wp_id": result.wp_id,
                "blocks": result.blocks,
                "links": [dataclasses.asdict(link) for link in result.links],
                "uploads": [dataclasses.asdict(u) for u in result.uploads],
                "stats": result.stats,
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")

            loss = result.stats.get("content_loss", {})
            loss_pcts.append(loss.get("loss_pct", 0.0))
            if loss.get("chars_in", 0) > 10_000 and abs(loss.get("loss_pct", 0.0)) > 1.0:
                outliers.append({"wp_id": result.wp_id, **loss})
            for tag, cnt in result.stats.get("unhandled_tags", {}).items():
                unhandled_tags[tag] += cnt
            for name, cnt in result.stats.get("gutenberg_block_types", {}).items():
                gutenberg_types[name] += cnt
            for key in ("dropped_empty", "dropped_decorative", "dropped_non_visible"):
                dropped_reasons[key] += result.stats.get(key, 0)

    report = {
        "articles": n,
        "loss_pct": {
            "median": round(statistics.median(loss_pcts), 3) if loss_pcts else None,
            "p95": round(sorted(loss_pcts)[int(len(loss_pcts) * 0.95)], 3) if loss_pcts else None,
            "max": round(max(loss_pcts), 3) if loss_pcts else None,
        },
        "outliers_over_10k_chars": outliers,
        "unhandled_tags": dict(unhandled_tags.most_common()),
        "gutenberg_block_types": dict(gutenberg_types.most_common()),
        "dropped": dict(dropped_reasons),
    }
    click.echo(json.dumps(report, indent=2))
    if report_path:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    cli()

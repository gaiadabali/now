from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from now_place_extraction.pipeline import run_city

PROJECT_ROOT = Path(__file__).resolve().parents[5]  # .../now

CITY_DB_REF = {"jakarta": "now_jakarta", "bali": "now_bali"}
CITY_CONTENT_DIR = {
    "jakarta": PROJECT_ROOT / "jakarta" / "content" / "extracted",
    "bali": PROJECT_ROOT / "bali" / "content" / "extracted",
}


@click.group()
def cli() -> None:
    """E2.3 -- place entity extraction + dedup."""


@cli.command()
@click.option("--city", type=click.Choice(["jakarta", "bali"]), required=True)
@click.option("--limit", type=int, default=None, help="Process only the first N articles (testing).")
@click.option("--dry-run", is_flag=True, default=False, help="Report only, no DB writes / no review-queue file.")
@click.option("--use-llm", is_flag=True, default=False, help="Enable LLM adjudication for ambiguous merge pairs (capped, see llm.py).")
@click.option("--llm-max-calls", type=int, default=150)
def run(city: str, limit: int | None, dry_run: bool, use_llm: bool, llm_max_calls: int) -> None:
    llm_adjudicate = None
    if use_llm:
        from now_place_extraction.llm import Adjudicator

        llm_adjudicate = Adjudicator(max_calls=llm_max_calls)

    report = run_city(
        city=city,
        db_ref=CITY_DB_REF[city],
        content_dir=CITY_CONTENT_DIR[city],
        limit=limit,
        dry_run=dry_run,
        llm_adjudicate=llm_adjudicate,
    )
    click.echo(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    cli()

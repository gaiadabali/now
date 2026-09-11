"""Manual verification CLI -- not required by any acceptance criterion,
but useful to eyeball a resolve+render against the real DBs by hand.
`now-link-resolver resolve --site-id ... --place-id ...` prints the
`LinkDecision` as JSON; nothing here is exercised by the test suite.
"""

from __future__ import annotations

import dataclasses
import json

import click

from now_link_resolver.connections import city_engine, platform_engine
from now_link_resolver.resolver import resolve_mention


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--city-db", required=True, help="City DB ref, e.g. now_jakarta")
@click.option("--site-id", required=True)
@click.option("--place-id", required=True)
def resolve(city_db: str, site_id: str, place_id: str) -> None:
    city_eng = city_engine(city_db)
    platform_eng = platform_engine()
    with city_eng.connect() as city_conn, platform_eng.connect() as platform_conn:
        decision = resolve_mention(city_conn, platform_conn, site_id=site_id, place_id=place_id)
    payload = dataclasses.asdict(decision)
    payload["rel"] = decision.rel
    payload["href"] = decision.href
    click.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":
    cli()

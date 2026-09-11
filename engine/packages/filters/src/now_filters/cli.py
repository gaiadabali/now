"""`now-filters` CLI -- demo/inspection commands. Mirrors `now-search`'s
CLI shape (`connections.city_engine` + click). Not consumed by any other
package; exists so a human (or the Inspector, later) can see the real SQL
and real EXPLAIN output this package produces, per ARCHITECTURE.md
Sec.8.G ("show the query plan")."""

from __future__ import annotations

import json

import click
from sqlalchemy import text

from now_filters.connections import city_engine
from now_filters.hard import build_places_hard_filter_sql, fetch_places_hard_filtered
from now_filters.pipeline import NearbySubject, run_nearby_ladder
from now_filters.synthetic import SYNTH_PLACES_TABLE, create_synthetic_places_table, generate_synthetic_place_rows
from now_filters.type_relations import load_type_relations


@click.group()
def cli() -> None:
    pass


@cli.command("explain-places")
@click.option("--db", default="now_jakarta", show_default=True)
@click.option("--subject-type", default="stay", show_default=True)
@click.option("--radius-m", default=2000.0, show_default=True, type=float)
@click.option("--lat", default=-6.22, show_default=True, type=float)
@click.option("--lng", default=106.80, show_default=True, type=float)
def explain_places(db: str, subject_type: str, radius_m: float, lat: float, lng: float) -> None:
    """Prints the real SQL + EXPLAIN ANALYZE for the places hard filter
    against `db` (default: `now_jakarta`, real data -- currently 0 rows
    survive `status='active'`, which is F27's point exactly)."""
    engine = city_engine(db)
    with engine.connect() as conn:
        relations = load_type_relations(conn)
        query = build_places_hard_filter_sql(
            subject_type=subject_type, relations=relations, center_lat=lat, center_lng=lng, radius_m=radius_m
        )
        click.echo("SQL:\n" + query.sql)
        click.echo("PARAMS: " + json.dumps(query.params))
        plan = conn.execute(text("EXPLAIN ANALYZE " + query.sql), query.params).fetchall()
        click.echo("\nEXPLAIN ANALYZE:")
        for row in plan:
            click.echo(row[0])
        rows = fetch_places_hard_filtered(conn, query)
        click.echo(f"\nSurviving candidates: {len(rows)}")


@cli.command("ladder-demo")
@click.option("--db", default="now_jakarta", show_default=True)
@click.option("--n-synthetic", default=40, show_default=True, type=int)
def ladder_demo(db: str, n_synthetic: int) -> None:
    """Seeds `n_synthetic` synthetic places (session-scoped temp table,
    never touches real data) and walks the fallback ladder for a `stay`
    subject, printing which rung filled the rail and proving no `stay`
    competitor appears in the result at any rung."""
    engine = city_engine(db)
    with engine.connect() as conn:
        relations = load_type_relations(conn)
        rows = generate_synthetic_place_rows(n_synthetic)
        create_synthetic_places_table(conn, rows)
        subject = NearbySubject(place_id=None, type="stay", lat=-6.22, lng=106.80, area_term="senopati")
        run = run_nearby_ladder(conn, subject, relations, slots_needed=8, places_table=SYNTH_PLACES_TABLE)
        click.echo(f"Rungs evaluated: {run.rungs_evaluated}")
        click.echo(f"Landed on rung {run.result.rung_index} ({run.result.rung_name}), {len(run.result.candidates)} candidates")
        types_seen = sorted({c.type for c in run.result.candidates})
        click.echo(f"Types in result: {types_seen}")
        assert "stay" not in types_seen, "competitor leaked through the ladder!"
        click.echo("OK: no `stay` competitor in result at the landed rung.")


if __name__ == "__main__":
    cli()

"""`now-itinerary` -- solve and print an itinerary from synthetic stops.

Deliberately synthetic-only for now: E5.4 wires `public.places` in, and
until then a CLI that pretended to read real venues would be lying about
where its numbers came from. What this *is* good for is exercising the
solver by hand -- seeing what a budget ceiling or a wheelchair
requirement actually does to a trip, without writing a test first.
"""

from __future__ import annotations

import click

from now_itinerary.models import ItineraryRequest, Mobility, Party
from now_itinerary.solver import InfeasibleItineraryError, solve
from now_itinerary.synthetic import make_stops
from now_itinerary.travel import HaversineMatrix
from now_itinerary.validate import validate


def _hm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


@click.group()
def cli() -> None:
    """now-itinerary -- E5 itinerary engine. See ARCHITECTURE.md §12."""


@cli.command()
@click.option("--stops", default=80, help="Size of the synthetic candidate pool.")
@click.option("--days", default=2)
@click.option("--seed", default=2026)
@click.option("--start-weekday", default=0, help="0=Monday.")
@click.option("--children", default=0)
@click.option("--wheelchair", is_flag=True)
@click.option("--halal", is_flag=True)
@click.option("--budget", type=int, default=None, help="Total price-band ceiling.")
@click.option("--partner-stops", default=0)
def demo(
    stops: int,
    days: int,
    seed: int,
    start_weekday: int,
    children: int,
    wheelchair: bool,
    halal: bool,
    budget: int | None,
    partner_stops: int,
) -> None:
    """Solve one itinerary over a synthetic pool and print it."""
    request = ItineraryRequest(
        stops=make_stops(stops, seed=seed),
        days=days,
        start_weekday=start_weekday,
        party=Party(
            children=children,
            mobility=Mobility.WHEELCHAIR if wheelchair else Mobility.FULL,
            halal_only=halal,
        ),
        budget_ceiling=budget,
        required_partner_stops=partner_stops,
    )
    travel = HaversineMatrix()

    try:
        itinerary = solve(request, travel=travel)
    except InfeasibleItineraryError as exc:
        # The diagnosable cases carry an actionable message; print it
        # rather than a traceback, since that message is the whole point
        # of solver._precheck.
        raise SystemExit(f"infeasible: {exc.reason}") from None

    for day in itinerary.days:
        click.echo(
            f"\n=== Day {day.day_index + 1} (weekday {day.weekday}) "
            f"-- {day.travel_minutes}min travelling"
        )
        for planned in day.stops:
            click.echo(
                f"  {_hm(planned.arrive_minute)}-{_hm(planned.depart_minute)}  "
                f"{planned.slot.value:9} {planned.stop.name:14} "
                f"({planned.stop.type}, band {planned.stop.price_band}) "
                f"+{planned.travel_minutes_from_previous}min"
            )

    report = validate(itinerary, request, travel=travel)
    click.echo(
        f"\nstatus={itinerary.solver_status} "
        f"solve={itinerary.solve_seconds * 1000:.0f}ms "
        f"price_band_total={itinerary.total_price_band}"
    )
    click.echo(f"valid={report.ok} violations={len(report.violations)}")
    for violation in report.violations:
        click.echo(f"  ! {violation}")
    if report.unverified_hours:
        click.echo(
            f"  note: {len(report.unverified_hours)} stop(s) have no opening-hours data "
            f"-- scheduled, but not verified open"
        )
    if report.travel_was_estimated:
        click.echo(
            "  note: travel times are haversine estimates (E5.1 OSRM matrix not wired yet) "
            "-- optimistic for Jakarta"
        )


if __name__ == "__main__":
    cli()

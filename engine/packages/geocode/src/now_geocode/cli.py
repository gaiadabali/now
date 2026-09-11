"""`now-geocode build venues.jsonl geo.jsonl -o geocoded_places.jsonl`

Provider selection:
  --provider none      (default) free rung-1 seed only — the honest,
                       zero-cost result in an environment with no
                       Google API key. Everything else lands in the
                       review queue, unresolved, never guessed.
  --provider google    real Geocoding + Places Text Search. Requires
                       --google-api-key or GOOGLE_MAPS_API_KEY.
  --provider nominatim OSM reference geocoder. Free, no key. Strong on
                       structured addresses (rung 2).
  --provider photon    Komoot's OSM search. Free, no key. Better than
                       Nominatim at venue-name lookup (rung 3).
  --provider chain     ordered fallback, e.g. --chain photon,google —
                       free rungs first, Google billed only for the
                       residue. See providers/chain.py for why a
                       transient failure is never cached as a negative.
  --provider offline   deterministic synthetic provider — refuses to run
                       unless --dry-run is also passed, and --dry-run
                       forces the output path to contain "dryrun" so a
                       demo run can never overwrite the real deliverable.
                       See providers/offline.py for why.

The OSM providers default to the public instances, which cap at 1 req/s
and forbid bulk use. For a real batch, self-host against a Geofabrik
Indonesia extract and pass --osm-base-url plus --osm-min-interval 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from now_geocode.pipeline import iter_jsonl, run
from now_geocode.pgdemo import render_st_dwithin_demo_sql
from now_geocode.providers.base import GeocodeProvider, ProviderConfigError
from now_geocode.providers.chain import ChainProvider
from now_geocode.providers.google import GoogleProvider
from now_geocode.providers.offline import OfflineProvider
from now_geocode.providers.osm import (
    NOMINATIM_PUBLIC_URL,
    PHOTON_PUBLIC_URL,
    NominatimProvider,
    PhotonProvider,
)
from now_geocode.report import render_markdown
from now_geocode.state import StateStore

# Names usable inside --chain. "none"/"offline" are deliberately absent:
# chaining a no-op or a synthetic generator behind a real provider would
# either do nothing or smuggle fabricated points into a real run.
CHAINABLE = ("nominatim", "photon", "google")


def build_provider(
    provider: str,
    *,
    chain: str = "photon,google",
    google_api_key: str | None = None,
    osm_base_url: str | None = None,
    osm_min_interval: float = 1.0,
    osm_user_agent: str | None = None,
    on_event: object = None,
) -> GeocodeProvider | None:
    """Construct the provider named by `--provider`. Split out of `build`
    so the wiring is unit-testable without running a whole pipeline."""

    def _osm(cls, default_url: str):
        kwargs = {"min_interval_s": osm_min_interval}
        if osm_user_agent:
            kwargs["user_agent"] = osm_user_agent
        return cls(osm_base_url or default_url, **kwargs)

    def _one(name: str) -> GeocodeProvider:
        if name == "google":
            built = GoogleProvider(api_key=google_api_key)
            if built.api_key is None:
                raise click.UsageError(
                    "No Google API key. Supply --google-api-key or set GOOGLE_MAPS_API_KEY. "
                    "See README.md 'What Hansel must supply' for which API to enable and the "
                    "cost estimate, or use --provider photon/nominatim for a free run."
                )
            return built
        if name == "nominatim":
            return _osm(NominatimProvider, NOMINATIM_PUBLIC_URL)
        if name == "photon":
            return _osm(PhotonProvider, PHOTON_PUBLIC_URL)
        raise click.UsageError(f"unknown provider {name!r} (chainable: {', '.join(CHAINABLE)})")

    if provider == "none":
        return None
    if provider == "offline":
        return OfflineProvider()
    if provider == "chain":
        names = [n.strip() for n in chain.split(",") if n.strip()]
        if not names:
            raise click.UsageError("--chain needs at least one provider name")
        unknown = [n for n in names if n not in CHAINABLE]
        if unknown:
            raise click.UsageError(
                f"--chain contains unusable provider(s): {', '.join(unknown)}. "
                f"Chainable: {', '.join(CHAINABLE)}."
            )
        if len(names) != len(set(names)):
            raise click.UsageError(f"--chain lists a provider twice: {chain}")
        return ChainProvider([_one(n) for n in names], on_event=on_event)
    return _one(provider)


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.argument("venues_path", type=click.Path(exists=True, path_type=Path))
@click.argument("geo_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option(
    "--provider",
    type=click.Choice(["none", "google", "nominatim", "photon", "chain", "offline"]),
    default="none",
    help="Resolution provider for rungs 2-3. 'none' = free seed only (default, zero cost).",
)
@click.option("--dry-run", is_flag=True, help="Required alongside --provider offline. Marks output as synthetic.")
@click.option("--google-api-key", default=None, help="Overrides GOOGLE_MAPS_API_KEY env var.")
@click.option(
    "--chain", default="photon,google", show_default=True,
    help=f"Comma-separated provider order for --provider chain. Chainable: {', '.join(CHAINABLE)}.",
)
@click.option(
    "--osm-base-url", default=None,
    help="Self-hosted Nominatim/Photon base URL. Defaults to the public instance (1 req/s, no bulk use).",
)
@click.option(
    "--osm-min-interval", type=float, default=1.0, show_default=True,
    help="Seconds between OSM calls. The public instances require >=1.0; set 0 when self-hosting.",
)
@click.option(
    "--osm-user-agent", default=None,
    help="Overrides the default identifying User-Agent. Nominatim answers a generic/absent UA with 403.",
)
@click.option(
    "--state", "state_path", type=click.Path(path_type=Path), default=None,
    help="Resumable cache JSONL (default: <output>.state.jsonl next to --output).",
)
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="Markdown verification report (default: <output stem>.md).")
@click.option("--review-queue", "review_queue_path", type=click.Path(path_type=Path), default=None,
              help="JSONL of unresolved/flagged rows only (default: <output stem>_review_queue.jsonl).")
def build(
    venues_path: Path,
    geo_path: Path,
    output_path: Path,
    provider: str,
    dry_run: bool,
    google_api_key: str | None,
    chain: str,
    osm_base_url: str | None,
    osm_min_interval: float,
    osm_user_agent: str | None,
    state_path: Path | None,
    report_path: Path | None,
    review_queue_path: Path | None,
) -> None:
    """Resolve VENUES_PATH (venues.jsonl) + GEO_PATH (geo.jsonl) to
    geocoded_places.jsonl via the E2.5 source ladder."""

    if provider == "offline" and not dry_run:
        raise click.UsageError(
            "--provider offline produces synthetic, non-real coordinates and must be run "
            "with --dry-run (see providers/offline.py). It is a pipeline self-test, not a "
            "way to fill in real geocodes without a Google key."
        )
    if dry_run and "dryrun" not in output_path.name.lower():
        raise click.UsageError(
            f"--dry-run output path must contain 'dryrun' in its filename (got {output_path.name}) "
            "so a synthetic demo run can never be mistaken for, or overwrite, the real deliverable."
        )

    # Per-provider tallies, so a chained run reports which rung of the
    # chain actually did the work — the number that decides whether a
    # Google key is worth buying at all.
    chain_tally: dict[str, int] = {}

    def _on_chain_event(kind: str, provider_name: str, detail: str) -> None:
        if kind == "resolved":
            chain_tally[provider_name] = chain_tally.get(provider_name, 0) + 1
        elif kind == "disabled":
            click.echo(f"  chain: {provider_name} disabled for this run: {detail}", err=True)

    provider_obj = build_provider(
        provider,
        chain=chain,
        google_api_key=google_api_key,
        osm_base_url=osm_base_url,
        osm_min_interval=osm_min_interval,
        osm_user_agent=osm_user_agent,
        on_event=_on_chain_event,
    )

    if state_path is None:
        # NB: output_path.with_suffix("") is not "the stem" when the
        # filename itself contains a dot (e.g. "geocoded_places.dryrun.jsonl"
        # -> stripping ".jsonl" leaves a path whose *own* suffix is now
        # ".dryrun", so a second .with_suffix(".state.jsonl") would replace
        # that instead of appending — silently colliding two different
        # runs' state/cache files. with_name(stem + ...) does not have
        # this problem because .stem always strips exactly one suffix.
        state_path = output_path.with_name(output_path.stem + ".state.jsonl")
    if report_path is None:
        report_path = output_path.with_suffix(".md")
    if review_queue_path is None:
        review_queue_path = output_path.with_name(output_path.stem + "_review_queue.jsonl")

    venue_rows = iter_jsonl(venues_path)
    geo_rows = iter_jsonl(geo_path)
    state = StateStore(state_path)

    try:
        places, stats = run(
            venue_rows,
            geo_rows,
            provider=provider_obj,
            state=state,
            allow_synthetic=dry_run,
        )
    except ProviderConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    with output_path.open("w", encoding="utf-8") as f:
        for place in places:
            f.write(json.dumps(place.to_json(), ensure_ascii=False) + "\n")

    with review_queue_path.open("w", encoding="utf-8") as f:
        for place in places:
            if place.status.value != "resolved" or place.flags:
                f.write(json.dumps(place.to_json(), ensure_ascii=False) + "\n")

    report_path.write_text(render_markdown(places, stats), encoding="utf-8")

    resolved = stats.by_status.get("resolved", 0) + stats.by_status.get("resolved_synthetic", 0)
    click.echo(
        f"{len(places)} places -> {resolved} resolved, "
        f"{stats.by_status.get('unresolved', 0)} unresolved, "
        f"{stats.by_status.get('rejected', 0)} rejected "
        f"(provider calls: {stats.resolved_from_provider_calls}, from cache: {stats.resolved_from_cache})"
    )
    if chain_tally:
        breakdown = ", ".join(f"{name} {count}" for name, count in sorted(chain_tally.items()))
        click.echo(f"chain resolutions by provider: {breakdown}")
        click.echo(
            "  ^ read this before buying a Google key: anything the free "
            "providers resolved is spend you do not need."
        )
    click.echo(f"wrote {output_path}, {review_queue_path}, {report_path}, state at {state_path}")


@cli.command("postgis-sql")
@click.argument("geocoded_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", "output_path", type=click.Path(path_type=Path), default=None,
              help="Write SQL here instead of stdout.")
@click.option("--radius-m", type=float, default=2000.0, help="ST_DWithin radius in meters.")
def postgis_sql(geocoded_path: Path, output_path: Path | None, radius_m: float) -> None:
    """Emit a self-contained SQL script (TEMP TABLE, dropped on commit)
    that proves ST_DWithin nearby-radius queries work against the
    resolved coordinates in GEOCODED_PATH. Pipe it into any PostGIS-
    enabled Postgres, e.g.:

        now-geocode postgis-sql geocoded_places.jsonl | \\
            docker exec -i now-postgres psql -U now -d now_test
    """

    from now_geocode.models import GeocodedPlace, Rung, SourceRef, Status

    rows = iter_jsonl(geocoded_path)
    places = [
        GeocodedPlace(
            place_key=r["place_key"],
            name=r["name"],
            slug=r["slug"],
            address=r.get("address"),
            city=r.get("city"),
            province=r.get("province"),
            country=r.get("country"),
            lat=r.get("lat"),
            lng=r.get("lng"),
            status=Status(r["status"]),
            source=Rung(r["source"]),
            confidence=r.get("confidence", 0.0),
            google_place_id=r.get("google_place_id"),
            area_term=r.get("area_term"),
            area_term_source=r.get("area_term_source"),
            area_term_confidence=r.get("area_term_confidence"),
            flags=r.get("flags", []),
            source_refs=[],
            review_reason=r.get("review_reason"),
            location_type=r.get("location_type"),
        )
        for r in rows
    ]
    sql = render_st_dwithin_demo_sql(places, radius_m=radius_m)
    if output_path:
        output_path.write_text(sql, encoding="utf-8")
        click.echo(f"wrote {output_path}", err=True)
    else:
        sys.stdout.write(sql)

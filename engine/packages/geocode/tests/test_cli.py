import json
from pathlib import Path

from click.testing import CliRunner

from now_geocode.cli import cli


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_build_provider_none_zero_cost(tmp_path):
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [{"wp_id": 1, "name": "Test Venue", "status": "publish", "city": "Ubud"}])
    _write_jsonl(geo, [])
    out = tmp_path / "geocoded_places.jsonl"

    runner = CliRunner()
    result = runner.invoke(cli, ["build", str(venues), str(geo), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "unresolved"
    assert rows[0]["area_term"] == "ubud"
    assert out.with_suffix(".md").exists()


def test_offline_provider_without_dry_run_is_rejected(tmp_path):
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [])
    _write_jsonl(geo, [])
    out = tmp_path / "geocoded_places.jsonl"

    runner = CliRunner()
    result = runner.invoke(cli, ["build", str(venues), str(geo), "-o", str(out), "--provider", "offline"])
    assert result.exit_code != 0
    assert "dry-run" in result.output.lower() or "dry_run" in result.output.lower() or "dryrun" in result.output.lower()
    assert not out.exists()


def test_offline_dry_run_requires_dryrun_in_filename(tmp_path):
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [])
    _write_jsonl(geo, [])
    out = tmp_path / "geocoded_places.jsonl"  # deliberately missing "dryrun"

    runner = CliRunner()
    result = runner.invoke(
        cli, ["build", str(venues), str(geo), "-o", str(out), "--provider", "offline", "--dry-run"]
    )
    assert result.exit_code != 0
    assert "dryrun" in result.output.lower()


def test_offline_dry_run_with_correct_filename_produces_synthetic_rows(tmp_path):
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [{"wp_id": 1, "name": "Test Venue", "status": "publish", "address": "Jl. Test No 1"}])
    _write_jsonl(geo, [])
    out = tmp_path / "geocoded_places.dryrun.jsonl"

    runner = CliRunner()
    result = runner.invoke(
        cli, ["build", str(venues), str(geo), "-o", str(out), "--provider", "offline", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "resolved_synthetic"
    assert rows[0]["lat"] is not None


def test_default_state_path_does_not_collide_when_output_stem_has_a_dot(tmp_path):
    # Regression: "geocoded_places.dryrun.jsonl"'s stem is
    # "geocoded_places.dryrun", whose *own* suffix is ".dryrun" — a naive
    # output_path.with_suffix("").with_suffix(".state.jsonl") replaces
    # that instead of appending, silently reusing the real run's state
    # file. A dry run must never read or write the real cache.
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [{"wp_id": 1, "name": "Test Venue", "status": "publish", "address": "Jl. Test No 1"}])
    _write_jsonl(geo, [])

    real_out = tmp_path / "geocoded_places.jsonl"
    runner = CliRunner()
    runner.invoke(cli, ["build", str(venues), str(geo), "-o", str(real_out)])
    real_state = tmp_path / "geocoded_places.state.jsonl"
    assert real_state.exists()
    real_state_content_before = real_state.read_text(encoding="utf-8")

    dryrun_out = tmp_path / "geocoded_places.dryrun.jsonl"
    result = runner.invoke(
        cli, ["build", str(venues), str(geo), "-o", str(dryrun_out), "--provider", "offline", "--dry-run"]
    )
    assert result.exit_code == 0, result.output

    dryrun_state = tmp_path / "geocoded_places.dryrun.state.jsonl"
    assert dryrun_state.exists(), "dry run must write its own state file, not reuse the real one"
    assert real_state.read_text(encoding="utf-8") == real_state_content_before, "dry run must not mutate the real state file"


def test_google_provider_without_key_gives_actionable_error(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    venues = tmp_path / "venues.jsonl"
    geo = tmp_path / "geo.jsonl"
    _write_jsonl(venues, [])
    _write_jsonl(geo, [])
    out = tmp_path / "geocoded_places.jsonl"

    runner = CliRunner()
    result = runner.invoke(cli, ["build", str(venues), str(geo), "-o", str(out), "--provider", "google"])
    assert result.exit_code != 0
    assert "GOOGLE_MAPS_API_KEY" in result.output


def test_postgis_sql_command_roundtrip(tmp_path):
    geocoded = tmp_path / "geocoded_places.jsonl"
    _write_jsonl(
        geocoded,
        [
            {
                "place_key": "k1", "name": "A", "slug": "a", "lat": -6.2, "lng": 106.8,
                "status": "resolved", "source": "existing_coordinates", "confidence": 0.9,
                "area_term": "jakarta", "flags": [],
            }
        ],
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["postgis-sql", str(geocoded)])
    assert result.exit_code == 0, result.output
    assert "ST_DWithin" in result.output

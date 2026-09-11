"""Adversarial probe: can a synthetic (offline provider) coordinate reach a
non-dryrun output file by way of a shared/overridden --state cache file?

Guardrail #1 (CLI): --provider offline requires --dry-run, and --dry-run
forces "dryrun" to appear in the OUTPUT filename.
Guardrail #2 (pipeline): a synthetic ProviderResult is coerced to
Status.UNRESOLVED unless allow_synthetic=True (only ever True when --dry-run
was passed).

Neither guardrail says anything about the --state cache file path. This
script:
  1. Runs a legit dry-run (offline provider) that resolves one candidate to
     a synthetic point, using an explicit --state file: shared.state.jsonl.
  2. Runs a second, "real" build (provider=none, no --dry-run) against the
     SAME candidate, pointed at the SAME --state file, writing to a
     non-dryrun output filename.
  3. Inspects whether the synthetic-derived row leaks into the real output,
     and if so, whether it is still labeled distinguishably
     (status=resolved_synthetic / location_type contains "offline").

This is exploratory/adversarial testing only -- no product code is modified.
"""
import json
import shutil
import tempfile
from pathlib import Path

from click.testing import CliRunner

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geocode" / "src"))

from now_geocode.cli import cli  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="geocode_attack_"))
    print(f"workdir: {tmp}")

    venues = tmp / "venues.jsonl"
    geo = tmp / "geo.jsonl"
    write_jsonl(venues, [
        {"wp_id": 1, "name": "Jakarta Attack Cafe", "status": "publish", "address": "Jl. Test No 1"},
    ])
    write_jsonl(geo, [])

    shared_state = tmp / "shared.state.jsonl"
    dryrun_out = tmp / "geocoded_places.dryrun.jsonl"
    real_out = tmp / "geocoded_places.jsonl"  # the REAL deliverable filename, no "dryrun"

    runner = CliRunner()

    print("\n=== STEP 1: dry-run with offline provider, explicit shared --state ===")
    r1 = runner.invoke(cli, [
        "build", str(venues), str(geo),
        "-o", str(dryrun_out),
        "--provider", "offline",
        "--dry-run",
        "--state", str(shared_state),
    ])
    print("exit_code:", r1.exit_code)
    print(r1.output)
    if r1.exception:
        import traceback
        traceback.print_exception(type(r1.exception), r1.exception, r1.exception.__traceback__)

    print("state file contents after step 1:")
    print(shared_state.read_text() if shared_state.exists() else "<missing>")

    print("\n=== STEP 2: 'real' build, provider=none, SAME --state, non-dryrun filename ===")
    r2 = runner.invoke(cli, [
        "build", str(venues), str(geo),
        "-o", str(real_out),
        "--provider", "none",
        "--state", str(shared_state),
    ])
    print("exit_code:", r2.exit_code)
    print(r2.output)
    if r2.exception:
        import traceback
        traceback.print_exception(type(r2.exception), r2.exception, r2.exception.__traceback__)

    print("\n=== RESULT: rows in the REAL (non-dryrun) output file ===")
    if real_out.exists():
        for line in real_out.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            print(json.dumps(row, indent=2))
            print("--- verdict for this row ---")
            print("  status:", row["status"])
            print("  lat/lng non-null:", row["lat"] is not None or row["lng"] is not None)
            print("  location_type mentions offline:", "offline" in str(row.get("location_type")))
    else:
        print("real_out does not exist")

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

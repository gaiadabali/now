"""Wave 18 ticket 3 (T3) -- LLM-batch APPLY step CLI.

Defaults to `--dry-run` and there is no way to make it write to
`now_jakarta`/`now_bali` (`apply_llm_labels.RefusedLiveWriteError` --
`LIVE_CITY_DBS` is checked before any write-mode DB call). To actually
write, pass `--execute --db-ref now_test` (or another scratch db_ref) --
`--execute` against a bare `jakarta`/`bali` city name always refuses.

Run from the `eval` package venv:

    engine/packages/eval> .venv/Scripts/python.exe scripts/run_llm_apply.py --dry-run
    engine/packages/eval> .venv/Scripts/python.exe scripts/run_llm_apply.py --dry-run --out report.json
    engine/packages/eval> .venv/Scripts/python.exe scripts/run_llm_apply.py --execute --db-ref now_test

Per PROGRESS.md/this ticket's brief: **do not run `--execute` against the
live city databases.** This ticket's own deliverable is the writer, its
dry-run report, and its tests -- Hansel schedules the real apply once the
F121 batch completes and he has seen the diff.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from now_eval.calibration.apply_llm_labels import (  # noqa: E402
    CITY_DB,
    LIVE_CITY_DBS,
    RefusedLiveWriteError,
    run_apply,
)


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "ARCHITECTURE.md").is_file():
            return candidate
    raise FileNotFoundError("could not find repo root (no ARCHITECTURE.md above scripts/run_llm_apply.py)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cities", nargs="+", default=["jakarta", "bali"], choices=["jakarta", "bali"])
    parser.add_argument("--ledger-dir", type=Path, default=None,
                         help="default: engine/packages/eval/data/llm_batch")
    parser.add_argument("--execute", action="store_true",
                         help="actually write. Refused outright if --db-ref resolves to now_jakarta/now_bali.")
    parser.add_argument("--db-ref", default=None,
                         help="override db_ref for every requested city (e.g. now_test). "
                              "Without this, cities resolve to their real now_jakarta/now_bali db_refs, "
                              "which --execute always refuses.")
    parser.add_argument("--out", type=Path, default=None, help="write the JSON report here as well as stdout")
    args = parser.parse_args()

    root = find_repo_root()
    ledger_dir = args.ledger_dir or (root / "engine" / "packages" / "eval" / "data" / "llm_batch")

    from now_classifier.vocabulary import load_term_index
    terms = load_term_index()

    city_db_map = dict(CITY_DB)
    if args.db_ref:
        city_db_map = {c: args.db_ref for c in args.cities}

    try:
        report = run_apply(
            tuple(args.cities), ledger_dir, terms,
            city_db_map=city_db_map, dry_run=not args.execute,
        )
    except RefusedLiveWriteError as exc:
        print(f"[run_llm_apply] REFUSED: {exc}", file=sys.stderr)
        print(f"[run_llm_apply] LIVE_CITY_DBS = {sorted(LIVE_CITY_DBS)}", file=sys.stderr)
        return 2

    summary = report.summary()
    text = json.dumps(summary, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"[run_llm_apply] wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

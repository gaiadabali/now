"""Wave 18 -- offline LLM batch labelling over the full 9,201-article corpus
(both cities), worst-measured-band first. Writes labels to
`engine/packages/eval/data/llm_batch/{city}_llm_labels.full.jsonl` only --
never touches `now_jakarta` / `now_bali`. See
`docs/llm-batch-apply-design.md` for how these get applied later (not part
of this ticket).

Run from the `eval` package venv (uv is currently locked -- use the venv
python directly, per the ticket):

    engine/packages/eval> ../../../.venv/Scripts/python.exe scripts/run_llm_batch.py --dry-run
    engine/packages/eval> .venv/Scripts/python.exe scripts/run_llm_batch.py

Safe to Ctrl-C and re-run at any time -- it re-derives the same
priority-ordered queue and skips everything already in the ledger.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from now_eval.calibration.batch_label import (  # noqa: E402
    DEFAULT_OUT_DIR,
    RateBudget,
    fetch_usage,
    run_batch,
    weekly_usage_fraction,
)
from now_eval.calibration.llm_client import load_ollama_env  # noqa: E402


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "ARCHITECTURE.md").is_file():
            return candidate
    raise FileNotFoundError("could not find repo root (no ARCHITECTURE.md above scripts/run_llm_batch.py)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cities", nargs="+", default=["jakarta", "bali"])
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--limit", type=int, default=None, help="cap articles processed THIS invocation")
    ap.add_argument("--sleep-between", type=float, default=1.0)
    ap.add_argument("--usage-check-every", type=int, default=50)
    ap.add_argument("--soft-ceiling", type=float, default=0.55)
    ap.add_argument("--hard-ceiling", type=float, default=0.75)
    ap.add_argument("--model", default=None)
    ap.add_argument("--dry-run", action="store_true", help="print the queue plan, make zero network calls")
    ap.add_argument("--usage-only", action="store_true", help="just print live /api/usage and exit")
    args = ap.parse_args()

    if args.usage_only:
        env = load_ollama_env()
        doc = fetch_usage(env)
        print(f"weekly usage fraction: {weekly_usage_fraction(doc):.4f}")
        print(f"weekly models: {doc.get('limits', {}).get('weekly', {}).get('models')}")
        return

    root = find_repo_root()
    budget = RateBudget(soft_ceiling=args.soft_ceiling, hard_ceiling=args.hard_ceiling)
    summary = run_batch(
        root,
        out_dir=args.out_dir,
        cities=tuple(args.cities),
        limit=args.limit,
        sleep_between=args.sleep_between,
        usage_check_every=args.usage_check_every,
        rate_budget=budget,
        model=args.model,
        dry_run=args.dry_run,
    )
    print(summary)


if __name__ == "__main__":
    main()

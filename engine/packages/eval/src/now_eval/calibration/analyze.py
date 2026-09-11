"""Step 5: turn (sample + LLM labels + Hansel's adjudication verdicts) into
per-cell accuracy figures, and those into an evidence-based label->number
mapping recommendation.

Two report modes, always labelled which one a given number is:
- `preliminary`: LLM-vs-classifier agreement rate only, before any human
  adjudication. Informative (it already shows where the two independent
  signals disagree) but NOT an accuracy number -- agreement is not the same
  as correctness, which is the entire reason the adjudication step exists.
- `adjudicated`: once Hansel's verdicts exist for a cell's disagreements and
  at least one control-slice agreement, `stats.estimate_cell_accuracy` gives
  a real accuracy estimate with a Wilson interval.
"""
from __future__ import annotations

import json
from pathlib import Path

from .stats import TwoStageEstimate, estimate_cell_accuracy


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def cell_key(row: dict) -> str:
    return f"{row['city']}:{row['facet']}:{round(row['confidence'], 2)}"


def population_by_cell(sample_rows: list[dict]) -> dict[str, int]:
    """Cell -> sample size actually drawn (n_sampled), NOT the full DB
    population -- `n_total` per cell is tracked separately by whoever calls
    this with the live population counts (see `report.py` / the CLI, which
    reads them straight from `db_frame` rather than guessing)."""
    from collections import Counter

    return dict(Counter(cell_key(r) for r in sample_rows))


def build_cell_estimates(
    merged_rows: list[dict],
    adjudications: dict[str, str],
    population_by_cell_total: dict[str, int],
) -> dict[str, TwoStageEstimate]:
    """`adjudications`: item_id -> verdict, where verdict is one of
    "classifier" (classifier's value is correct), "llm" (the LLM's value is
    correct instead), "neither" (both wrong), or "both_wrong" (alias for
    "neither"). Only "classifier" counts as classifier-correct.
    """
    from collections import defaultdict

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for row in merged_rows:
        by_cell[cell_key(row)].append(row)

    out: dict[str, TwoStageEstimate] = {}
    for cell, rows in by_cell.items():
        agree_rows = [r for r in rows if r["agree"]]
        disagree_rows = [r for r in rows if not r["agree"]]

        agree_adjudicated = 0
        agree_adjudicated_correct = 0
        for r in agree_rows:
            item_id = r["key"] + ":control"
            verdict = adjudications.get(item_id)
            if verdict is not None:
                agree_adjudicated += 1
                if verdict == "classifier":
                    agree_adjudicated_correct += 1

        disagree_correct_for_classifier = 0
        for r in disagree_rows:
            item_id = r["key"] + ":disagreement"
            verdict = adjudications.get(item_id)
            if verdict == "classifier":
                disagree_correct_for_classifier += 1

        out[cell] = estimate_cell_accuracy(
            cell=cell,
            n_total=population_by_cell_total.get(cell, len(rows)),
            n_sampled=len(rows),
            n_agree=len(agree_rows),
            n_disagree=len(disagree_rows),
            n_agree_adjudicated=agree_adjudicated,
            n_agree_adjudicated_correct=agree_adjudicated_correct,
            n_disagree_adjudicated_correct_for_classifier=disagree_correct_for_classifier,
        )
    return out


def preliminary_agreement_rate(merged_rows: list[dict]) -> dict[str, float]:
    from collections import defaultdict

    n = defaultdict(int)
    agree = defaultdict(int)
    for row in merged_rows:
        cell = cell_key(row)
        n[cell] += 1
        if row["agree"]:
            agree[cell] += 1
    return {cell: agree[cell] / n[cell] for cell in n}

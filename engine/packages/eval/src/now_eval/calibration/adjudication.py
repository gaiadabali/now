"""Step 3: merge classifier proposals with the blind LLM proxy labels,
compute agreement, and build the queue Hansel actually adjudicates.

**Design: adjudicate every disagreement, spot-check a random control slice
of agreements.** Agreement between the classifier and an independently
blind LLM is *necessary but not sufficient* for correctness -- both could
share a blind spot (e.g. a genuinely ambiguous article, or a subject neither
instrument was ever going to get right). The control slice measures that
risk directly rather than assuming agreement == correct; `stats.py`'s
`estimate_cell_accuracy` blends the two: disagreements contribute their
adjudicated truth exactly, agreements contribute at the *rate the control
slice measured*, not at 1.0.

Total adjudication budget: sized to keep Hansel's time bounded (target
~200-250 items; task brief's own math -- 18,192 rows at 10s/row is "~50
hours", i.e. unreviewable -- so this queue is deliberately two orders of
magnitude smaller). All disagreements are included unconditionally (they are
the highest-information items and the whole reason this design exists); the
remaining budget is spent on a per-cell-proportional random control slice of
agreements so every stratum gets at least a little verification, not just
the cells that happened to disagree a lot.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_TOTAL_BUDGET = 220
MIN_CONTROL_PER_CELL = 2


@dataclass(frozen=True)
class AdjudicationItem:
    item_id: str
    city: str
    wp_id: int
    facet: str
    cell: str                 # "{city}:{facet}:{confidence}"
    confidence: float
    outcome: str               # "accepted" | "review" (classifier's own gate outcome)
    classifier_value: str
    llm_value: str | None
    kind: str                  # "disagreement" | "control"
    title: str
    excerpt: str
    text_excerpt: str
    llm_type_reasoning: str
    llm_format_reasoning: str


def _stable(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def merge(sample_rows: list[dict], llm_labels: list[dict]) -> list[dict]:
    """Returns sample rows augmented with `llm_value` and `agree`."""
    by_article: dict[tuple[str, int], dict] = {(l["city"], l["wp_id"]): l for l in llm_labels}
    merged = []
    for row in sample_rows:
        label = by_article.get((row["city"], row["wp_id"]))
        if label is None or label.get("error"):
            continue  # never adjudicate an item the LLM call itself failed on
        llm_value = label.get(row["facet"])  # "type" or "format" key on the label dict
        merged.append(
            {
                **row,
                "llm_value": llm_value,
                "llm_type_reasoning": label.get("type_reasoning", ""),
                "llm_format_reasoning": label.get("format_reasoning", ""),
                "agree": llm_value is not None and llm_value == row["proposed_value"],
            }
        )
    return merged


def build_queue(merged_rows: list[dict], *, total_budget: int = DEFAULT_TOTAL_BUDGET,
                 seed: str = "now-eval-calibration-adjudication-v1") -> list[AdjudicationItem]:
    disagreements = [r for r in merged_rows if not r["agree"]]
    agreements = [r for r in merged_rows if r["agree"]]

    items: list[AdjudicationItem] = [_to_item(r, "disagreement") for r in disagreements]

    control_budget = max(0, total_budget - len(disagreements))
    by_cell: dict[str, list[dict]] = {}
    for r in agreements:
        cell = f"{r['city']}:{r['facet']}:{round(r['confidence'], 2)}"
        by_cell.setdefault(cell, []).append(r)

    total_agreements = len(agreements) or 1
    for cell, rows in by_cell.items():
        share = round(control_budget * len(rows) / total_agreements)
        n = min(len(rows), max(MIN_CONTROL_PER_CELL, share) if control_budget > 0 else 0)
        ranked = sorted(rows, key=lambda r: _stable(seed, r["key"]))
        for r in ranked[:n]:
            items.append(_to_item(r, "control"))
    return items


def _to_item(row: dict, kind: str) -> AdjudicationItem:
    return AdjudicationItem(
        item_id=row["key"] + f":{kind}",
        city=row["city"],
        wp_id=row["wp_id"],
        facet=row["facet"],
        cell=f"{row['city']}:{row['facet']}:{round(row['confidence'], 2)}",
        confidence=row["confidence"],
        outcome=row["outcome"],
        classifier_value=row["proposed_value"],
        llm_value=row.get("llm_value"),
        kind=kind,
        title=row["title"],
        excerpt=row["excerpt"],
        text_excerpt=row["text_excerpt"],
        llm_type_reasoning=row.get("llm_type_reasoning", ""),
        llm_format_reasoning=row.get("llm_format_reasoning", ""),
    )


def write_queue(items: list[AdjudicationItem], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

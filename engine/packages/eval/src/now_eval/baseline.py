"""Dated, recorded baseline + the regression gate CI actually enforces.

§17's gate table has two shapes:
  - "no regression"      (related articles, search)      -> current >= baseline - epsilon
  - "hard minimum"        (facet tagging >=0.85, type >=0.95, itinerary 100%) -> current >= threshold, independent of any baseline

Both are expressed as `Gate` entries below. `check_gates` evaluates a
fresh `HarnessReport` against a loaded baseline file and returns every
failure (not just the first), so a CI log shows the whole picture in
one run.
"""
from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .harness import HarnessReport

EPSILON = 1e-9


@dataclass(frozen=True)
class Gate:
    surface: str
    metric: str  # "value" for the surface's primary metric, or a key in .extra
    kind: str  # "no_regression" | "min_threshold"
    threshold: float | None = None  # required for "min_threshold"


GATES: tuple[Gate, ...] = (
    Gate("related_articles", "value", "no_regression"),
    Gate("search", "value", "no_regression"),
    Gate("facet_tagging", "value", "min_threshold", 0.85),  # precision
    Gate("facet_tagging", "recall", "min_threshold", 0.85),
    Gate("type_classification", "value", "min_threshold", 0.95),
)


def _metric_value(report_dict: dict, surface: str, metric: str) -> float:
    entry = report_dict[surface]
    if metric == "value":
        return entry["value"]
    return entry["extra"][metric]


@dataclass(frozen=True)
class GateFailure:
    gate: Gate
    current: float
    baseline: float | None
    detail: str


def check_gates(
    report: HarnessReport,
    baseline: dict | None,
    *,
    kinds: tuple[str, ...] = ("no_regression", "min_threshold"),
) -> list[GateFailure]:
    """Evaluate GATES against a fresh report.

    `kinds` restricts which gate *kind* is enforced -- see the
    `now-eval check --gates` CLI flag. This exists because the
    min_threshold gates (facet >=0.85, type >=0.95) are §17's
    production bar for a *real* system (E2.1/E2.2), not something a
    trivial random/most-popular baseline is expected to clear. This
    package's own CI runs the trivial baseline and, correctly, fails
    those thresholds every time -- that failure is proof the metric
    discriminates, not a defect to chase away by weakening the gate.
    Default is still "all" (both kinds) so a caller who doesn't pass
    `kinds` gets the full, honest §17 gate set.
    """
    current = report.as_dict()
    failures: list[GateFailure] = []
    for gate in GATES:
        if gate.kind not in kinds:
            continue
        current_value = _metric_value(current, gate.surface, gate.metric)
        if gate.kind == "min_threshold":
            assert gate.threshold is not None
            if current_value < gate.threshold - EPSILON:
                failures.append(
                    GateFailure(
                        gate,
                        current_value,
                        None,
                        f"{gate.surface}.{gate.metric}={current_value:.4f} "
                        f"< required minimum {gate.threshold}",
                    )
                )
        elif gate.kind == "no_regression":
            if baseline is None:
                continue  # nothing recorded yet -- first run establishes it, doesn't fail
            baseline_results = baseline.get("results", {})
            if gate.surface not in baseline_results:
                continue
            baseline_value = _metric_value(baseline_results, gate.surface, gate.metric)
            if current_value < baseline_value - EPSILON:
                failures.append(
                    GateFailure(
                        gate,
                        current_value,
                        baseline_value,
                        f"{gate.surface}.{gate.metric}={current_value:.4f} regressed "
                        f"below baseline {baseline_value:.4f} "
                        f"(recorded {baseline.get('recorded_at', 'unknown date')})",
                    )
                )
        else:
            raise ValueError(f"unknown gate kind {gate.kind!r}")
    return failures


def build_baseline_document(
    report: HarnessReport,
    *,
    sut_name: str,
    label: str,
    dataset_counts: dict[str, int] | None = None,
) -> dict:
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "sut_name": sut_name,
        "label": label,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dataset_counts": dataset_counts or {},
        "results": report.as_dict(),
    }


def save_baseline(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_baseline(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

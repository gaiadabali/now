"""Accuracy (type classification) and multi-label precision/recall
(facet tagging)."""
from __future__ import annotations

from collections.abc import Mapping, Set


def accuracy(predictions: Mapping[str, str], labels: Mapping[str, str]) -> float:
    """Single-label accuracy over the intersection of item ids present in
    both maps. Used for the type-classification gate (>=0.95).

    Raises ValueError if there is no overlap at all — an empty
    intersection almost always means a wiring bug (mismatched id
    scheme), and a silent 0.0/0.0 -> 0.0 would hide that.
    """
    keys = [k for k in labels if k in predictions]
    if not keys:
        raise ValueError("no overlapping item ids between predictions and labels")
    correct = sum(1 for k in keys if predictions[k] == labels[k])
    return correct / len(keys)


def confusion_counts(
    predictions: Mapping[str, str], labels: Mapping[str, str]
) -> dict[str, dict[str, int]]:
    """label -> predicted -> count, for inspecting *what* a classifier
    confuses (e.g. is `stay` misclassified as `editorial`, which is
    harmless, or as a rival `eat`, which is the commercial-guarantee
    failure mode §17 gates on)."""
    keys = [k for k in labels if k in predictions]
    table: dict[str, dict[str, int]] = {}
    for k in keys:
        true_label = labels[k]
        pred_label = predictions[k]
        table.setdefault(true_label, {}).setdefault(pred_label, 0)
        table[true_label][pred_label] += 1
    return table


def multilabel_precision_recall(
    predicted: Mapping[str, Set[str]], true: Mapping[str, Set[str]]
) -> tuple[float, float]:
    """Micro-averaged precision/recall for multi-label facet tagging.

    Pools true/false positives across every item rather than averaging
    per-item precision, so items with more facets don't get
    under-weighted. Used for the facet-tagging gate (>=0.85 before
    auto-apply — both precision AND recall must clear the bar, since a
    system that recalls everything by over-tagging isn't safe to
    auto-apply either).

    Items present in only one of the two maps are treated as having an
    empty set on the other side (a predicted item with no gold labels
    contributes only false positives, and vice versa).
    """
    tp = fp = fn = 0
    for key in set(predicted) | set(true):
        p = set(predicted.get(key, ()))
        t = set(true.get(key, ()))
        tp += len(p & t)
        fp += len(p - t)
        fn += len(t - p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall

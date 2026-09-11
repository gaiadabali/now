from __future__ import annotations

from collections import Counter
from pathlib import Path

from .db import WriteStats
from .resolve import ClassificationResult


def _pct(n: int, total: int) -> str:
    return f"{100.0 * n / total:.1f}%" if total else "n/a"


def write_report(path: Path, city: str, results: list[ClassificationResult], stats: WriteStats) -> None:
    total = len(results)
    method_counts = Counter(r.category_method for r in results)
    ambiguous = sum(1 for r in results if r.category_ambiguous)
    no_category = sum(1 for r in results if r.category_name is None)

    conf_buckets = {"type": Counter(), "format": Counter(), "subtype": Counter()}
    for r in results:
        for key, dec in (("type", r.type), ("format", r.format), ("subtype", r.subtype)):
            # F120: a routed decision's explicit `auto_apply` can be True
            # below 0.85 (Hansel's F120 acceptance) or, in principle, False
            # at/above it (an abstain fallback should not happen there, but
            # the bucketing must reflect what was actually WRITTEN, not
            # just the raw number) -- so bucket by the same effective gate
            # `db.py` uses, not the raw confidence alone.
            auto_applied = dec.auto_apply if dec.auto_apply is not None else dec.confidence >= 0.85
            if auto_applied:
                conf_buckets[key]["auto-applied"] += 1
            elif dec.confidence >= 0.6:
                conf_buckets[key]["medium (0.6-0.85), not auto-applied"] += 1
            else:
                conf_buckets[key]["low (<0.6), not auto-applied"] += 1

    n_locations = sum(len(r.locations) for r in results)
    location_accepted_articles = sum(1 for r in results if any(d.confidence >= 0.85 for d in r.locations))

    lines: list[str] = []
    lines.append(f"# E2.1 classification report -- {city}\n")
    lines.append(f"Articles processed: **{total}**\n")

    lines.append("## D10 category resolution (yoast_primary -> deepest_child -> parent_container)\n")
    for method in ("yoast_primary", "deepest_child", "parent_container", "none"):
        n = method_counts.get(method, 0)
        lines.append(f"- `{method}`: {n} ({_pct(n, total)})")
    lines.append(f"- deepest_child ties requiring a tiebreak beyond yoast: **{ambiguous}**")
    lines.append(f"- articles whose category(ies) had no entry in taxonomy-review.json: **{no_category}**\n")

    lines.append("## Facet gate outcomes (auto-apply at >=0.85)\n")
    lines.append("| Facet | Auto-applied | -> review queue | Vocabulary misses |")
    lines.append("|---|---|---|---|")
    lines.append(f"| type | {stats.type_accepted} ({_pct(stats.type_accepted, total)}) | {stats.type_reviewed} ({_pct(stats.type_reviewed, total)}) | -- |")
    lines.append(f"| subtype | {stats.subtype_accepted} ({_pct(stats.subtype_accepted, total)}) | {stats.subtype_reviewed} ({_pct(stats.subtype_reviewed, total)}) | -- |")
    lines.append(f"| format | {stats.format_accepted} ({_pct(stats.format_accepted, total)}) | {stats.format_reviewed} ({_pct(stats.format_reviewed, total)}) | -- |")
    lines.append(f"| location (term-rows) | {stats.location_accepted} | {stats.location_reviewed} | -- |")
    lines.append(f"\ntotal `engine.terms` slugs proposed but not found in the platform vocabulary: **{stats.vocabulary_misses}**\n")
    lines.append(f"stale same-facet term rows removed (F120: a re-run's flipped type/format/subtype value "
                 f"retracting a PREVIOUS run's different accepted value for the same article): "
                 f"**{stats.stale_facet_terms_removed}**\n")
    lines.append(f"location term-rows written per article (avg): {n_locations / total:.2f}" if total else "")
    lines.append(f"articles with at least one auto-applied location: {location_accepted_articles} ({_pct(location_accepted_articles, total)})\n")

    lines.append("## Confidence distribution\n")
    for key in ("type", "format", "subtype"):
        lines.append(f"**{key}**: " + ", ".join(f"{k}={v}" for k, v in conf_buckets[key].items()))
    lines.append("")

    write_ok = path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

"""Renders the human-reviewable verification report (ARCHITECTURE.md
E2.5 deliverable #4: "A verification report a human can review")."""

from __future__ import annotations

from now_geocode.models import GeocodedPlace, Status
from now_geocode.pipeline import RunStats


def render_markdown(places: list[GeocodedPlace], stats: RunStats) -> str:
    lines: list[str] = []
    lines.append("# E2.5 geocoding — verification report")
    lines.append("")
    lines.append(f"Candidates after dedup: **{stats.total_candidates}**")
    if stats.merge_report:
        mr = stats.merge_report
        lines.append(
            f"Inputs: {mr.total_venue_rows} venue rows + {mr.total_geo_rows} geo rows "
            f"-> {len(mr.merges)} name merges "
            f"({mr.dropped_draft_venues} draft/non-published venues kept but flagged, not dropped)."
        )
        if mr.conflicts:
            lines.append(
                f"**{len(mr.conflicts)} merge(s) flagged for conflicting city/province** "
                "— possible false-positive name merge, needs human review:"
            )
            for c in mr.conflicts:
                lines.append(f"  - `{c['normalized_name']}`: cities {c['distinct_cities']}")
    lines.append("")

    lines.append("## Resolution by source (rung)")
    lines.append("")
    lines.append("| source | count |")
    lines.append("|---|---|")
    for source, count in sorted(stats.by_source.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {source} | {count} |")
    lines.append("")

    lines.append("## Status")
    lines.append("")
    lines.append("| status | count |")
    lines.append("|---|---|")
    for status, count in sorted(stats.by_status.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {status} | {count} |")
    lines.append("")

    resolved = sum(
        v for k, v in stats.by_status.items() if k in (Status.RESOLVED.value, Status.RESOLVED_SYNTHETIC.value)
    )
    if stats.total_candidates:
        pct = 100.0 * resolved / stats.total_candidates
        lines.append(f"**{resolved}/{stats.total_candidates} ({pct:.1f}%) have a coordinate.**")
    lines.append("")

    lines.append("## Confidence distribution (resolved only)")
    lines.append("")
    lines.append("| bucket | count |")
    lines.append("|---|---|")
    for bucket, count in sorted(stats.confidence_buckets.items()):
        lines.append(f"| {bucket} | {count} |")
    lines.append("")

    lines.append("## Area-term assignment method")
    lines.append("")
    lines.append("| method | count |")
    lines.append("|---|---|")
    for method, count in sorted(stats.by_area_source.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {method} | {count} |")
    area_covered = sum(1 for p in places if p.area_term)
    if stats.total_candidates:
        lines.append("")
        lines.append(
            f"**{area_covered}/{stats.total_candidates} "
            f"({100.0 * area_covered / stats.total_candidates:.1f}%) have an area term** "
            "— including places with no coordinate at all (Row 2's same-area fallback)."
        )
    lines.append("")

    lines.append("## Quality-gate flags")
    lines.append("")
    if not stats.flagged:
        lines.append("None raised.")
    else:
        lines.append("| flag | count |")
        lines.append("|---|---|")
        for flag, count in sorted(stats.flagged.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {flag} | {count} |")
    lines.append("")

    rejected = [p for p in places if p.status == Status.REJECTED]
    if rejected:
        lines.append("### Rejected (quality gate failed — coordinate present but not usable)")
        lines.append("")
        for p in rejected:
            lines.append(f"- `{p.place_key}` **{p.name}** ({p.lat}, {p.lng}) — flags: {p.flags}")
        lines.append("")

    dup_flagged = [p for p in places if "duplicate_centroid" in p.flags]
    if dup_flagged:
        lines.append("### Duplicate-centroid flagged (review before trusting the point)")
        lines.append("")
        for p in dup_flagged:
            lines.append(f"- `{p.place_key}` **{p.name}** ({p.lat}, {p.lng}), source={p.source.value}")
        lines.append("")

    unresolved = [p for p in places if p.status == Status.UNRESOLVED]
    if unresolved:
        lines.append(f"## Review queue — unresolved ({len(unresolved)})")
        lines.append("")
        lines.append("No coordinate fabricated for any of these; each still has an area term below.")
        lines.append("")
        lines.append("| name | area term | reason |")
        lines.append("|---|---|---|")
        for p in unresolved:
            lines.append(f"| {p.name} | {p.area_term} ({p.area_term_source}) | {p.review_reason} |")
        lines.append("")

    return "\n".join(lines)

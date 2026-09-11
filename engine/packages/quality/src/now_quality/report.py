"""Markdown report generation -- the human-eyeball surface the ticket
demands ("Show the clusters", "a human must be able to eyeball whether the
merges are right") plus the quality/popularity verification evidence.
"""

from __future__ import annotations

from now_quality.series import ClusterReport


def render_score_report(
    *,
    n_articles: int,
    scores: list[float],
    stubs: list[tuple[int, str, int, float]],  # (id, title, chars, score)
    floor: float,
    head_n: int,
    head_min_views: int,
    weights: dict,
) -> str:
    scores_sorted = sorted(scores)
    n = len(scores_sorted)

    def pct(p: float) -> float:
        if n == 0:
            return 0.0
        idx = min(n - 1, int(n * p))
        return scores_sorted[idx]

    below_floor = sum(1 for s in scores if s < floor)
    lines = [
        "# E2.6 -- Quality score report",
        "",
        f"Articles scored: **{n_articles}**",
        "",
        "## Weighting",
        "",
        "| component | weight |",
        "|---|---|",
    ]
    for k, v in weights.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "See `now_quality/scoring.py` module docstring for the justification of each weight.",
        "",
        "## Score distribution",
        "",
        f"- min: {scores_sorted[0] if n else 'n/a'}",
        f"- p25: {pct(0.25):.4f}",
        f"- median: {pct(0.5):.4f}",
        f"- p75: {pct(0.75):.4f}",
        f"- max: {scores_sorted[-1] if n else 'n/a'}",
        f"- below floor ({floor}): **{below_floor}** / {n_articles}",
        "",
        f"## Sub-{500}-char stubs -- must fall below the floor ({floor})",
        "",
        "| id | title | chars | score | below floor? |",
        "|---|---|---|---|---|",
    ]
    for aid, title, chars, score in stubs:
        ok = "✅" if score < floor else "❌"
        lines.append(f"| {aid} | {title[:70]} | {chars} | {score} | {ok} |")
    if not stubs:
        lines.append("| (none found) | | | | |")

    lines += [
        "",
        "## Popularity prior",
        "",
        f"- head cutoff: top **{head_n}** articles by `wpb_post_views_count`",
        f"- views floor to be 'in head': **{head_min_views}**",
        "- everything outside the head: `prior_score = 0.0`, `discarded_as_bot_noise: true`",
        "- see `now_quality/popularity.py` module docstring for the full percentile table and justification",
        "",
    ]
    return "\n".join(lines)


def _cluster_table(clusters, heading: str) -> list[str]:
    lines = [f"## {heading}", ""]
    if not clusters:
        lines.append("(none)")
        lines.append("")
        return lines
    for c in clusters:
        lines.append(f"### `{c.series_key}`")
        lines.append("")
        lines.append(f"_{c.reason}_")
        lines.append("")
        lines.append("| id | title | published | current? |")
        lines.append("|---|---|---|---|")
        for m in sorted(c.members, key=lambda m: m.published_at or ""):
            marker = "⭐ current" if m.id == c.current_id else ""
            lines.append(f"| {m.id} | {m.title} | {m.published_at} | {marker} |")
        lines.append("")
    return lines


def render_series_report(report: ClusterReport, applied: bool) -> str:
    lines = [
        "# E2.6 -- Series clustering report",
        "",
        f"Mode: {'APPLIED (series_key written for NULL rows)' if applied else 'DRY RUN (no writes)'}",
        "",
        f"Confident series (auto-clustered): **{len(report.confident)}**",
        f"Uncertain groups (flagged, not merged): **{len(report.uncertain)}**",
        f"Fuzzy candidate pairs (report-only, not merged): **{len(report.fuzzy_candidates)}**",
        "",
    ]
    lines += _cluster_table(report.confident, "Confident series clusters")
    lines += _cluster_table(report.uncertain, "Uncertain -- needs human review")

    lines += ["## Fuzzy candidate pairs (near-duplicate titles, no exact normalized match)", ""]
    if report.fuzzy_candidates:
        lines.append("| title A | title B | similarity |")
        lines.append("|---|---|---|")
        for a, b, ratio in report.fuzzy_candidates:
            lines.append(f"| ({a.id}) {a.title} | ({b.id}) {b.title} | {ratio} |")
    else:
        lines.append("(none above threshold)")
    lines.append("")
    return "\n".join(lines)

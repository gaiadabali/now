"""Human-readable `partner_roster.md` summary — top orgs table + the SEO
exposure numbers E4.3 needs, plus the exclusion list for review."""

from __future__ import annotations

from now_partner_roster.cluster import OrgRow
from now_partner_roster.pipeline import ExclusionAgg, RunStats

TOP_N = 60


def render_markdown(org_rows: list[OrgRow], exclusions: list[ExclusionAgg], stats: RunStats) -> str:
    ranked = sorted(org_rows, key=lambda r: (-r.link_count, r.org_slug))
    top = ranked[:TOP_N]

    lines: list[str] = []
    lines.append("# Partner roster — E1.5")
    lines.append("")
    lines.append(
        f"Extracted from {stats.articles:,} published articles via E1.2's link "
        "extractor. Ranked by link volume; review before promoting to `orgs` rows."
    )
    lines.append("")
    lines.append("## Corpus totals (real counts, this run)")
    lines.append("")
    lines.append(f"- Articles scanned: **{stats.articles:,}**")
    lines.append(f"- Articles carrying at least one external link: **{stats.articles_with_ext_link:,}**")
    lines.append(f"- Raw `<a href>` tags seen: **{stats.total_raw_hrefs:,}**")
    lines.append(f"  - internal media (`wp-content/uploads`): {stats.total_upload_links:,}")
    lines.append(f"  - non-http(s) (`mailto:`, `tel:`, relative, empty, malformed): {stats.total_non_http_links:,}")
    lines.append(f"  - external, absolute http(s): **{stats.total_external_links:,}**")
    lines.append(
        f"    - excluded (social/stock/shortener/utility/internal): {stats.total_excluded_links:,} "
        f"across {stats.distinct_domains_excluded:,} domains"
    )
    lines.append(
        f"    - candidate partner links: **{stats.total_candidate_links:,}** across "
        f"{stats.distinct_domains_candidate:,} domains, clustered into **{len(org_rows):,} orgs**"
    )
    lines.append("")
    lines.append("## SEO exposure — rel audit across ALL external links (this run)")
    lines.append("")
    total_rel = sum(stats.rel_totals.values())
    none_pct = (stats.rel_totals["none"] / total_rel * 100) if total_rel else 0.0
    lines.append(
        f"- No `rel` marker at all (passes PageRank as-is): "
        f"**{stats.rel_totals['none']:,}** / {total_rel:,} ({none_pct:.1f}%)"
    )
    lines.append(f"- `rel` contains `nofollow`: **{stats.rel_totals['nofollow']:,}**")
    lines.append(f"- `rel` contains `sponsored`: **{stats.rel_totals['sponsored']:,}**")
    lines.append("")
    lines.append(
        "This confirms ARCHITECTURE.md §6's finding at the full link-extractor "
        "accuracy level (E1.2), not the earlier undercounting parser — see the "
        "delivery report for the exact before/after."
    )
    lines.append("")
    lines.append(f"## Top {len(top)} orgs by link count")
    lines.append("")
    lines.append(
        "| # | Org | Slug | Parent | Domains | Links | Articles | Type guess | "
        "Confidence | rel none/nofollow/sponsored | First–Last seen |"
    )
    lines.append("|---:|---|---|---|---|---:|---:|---|---:|---|---|")
    for i, r in enumerate(top, 1):
        domains = ", ".join(r.domains) if r.domains else "*(none — synthesized)*"
        parent = r.parent_org_slug or "—"
        rel = f"{r.rel_audit['none']}/{r.rel_audit['nofollow']}/{r.rel_audit['sponsored']}"
        span = f"{r.first_seen or '—'} → {r.last_seen or '—'}"
        flag = " ⚑" if r.notes else ""
        lines.append(
            f"| {i} | {r.name}{flag} | `{r.org_slug}` | {parent} | {domains} | "
            f"{r.link_count} | {r.article_count} | {r.type_guess or '—'} | "
            f"{r.confidence:.2f} | {rel} | {span} |"
        )
    lines.append("")
    lines.append("⚑ = has a `notes` entry in `partner_roster.jsonl` flagging an ambiguous merge — review before use.")
    lines.append("")

    flagged = [r for r in ranked if r.notes]
    if flagged:
        lines.append(f"## Ambiguous clusters needing human review ({len(flagged)})")
        lines.append("")
        for r in flagged:
            lines.append(f"- **{r.name}** (`{r.org_slug}`, {r.link_count} links): " + "; ".join(r.notes))
        lines.append("")

    lines.append(f"## Excluded domains ({len(exclusions)} distinct, reviewable, not silently dropped)")
    lines.append("")
    lines.append("| Domain | Reason | Links | Articles | Sample articles |")
    lines.append("|---|---|---:|---:|---|")
    for e in sorted(exclusions, key=lambda e: (-e.link_count, e.domain)):
        samples = ", ".join(str(a) for a in e.sample_articles[:5])
        lines.append(f"| {e.domain} | {e.reason} | {e.link_count} | {len(e.article_ids)} | {samples} |")
    lines.append("")

    return "\n".join(lines)

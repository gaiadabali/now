"""Markdown reports for `now-places triage` and `now-places dedupe`.

Written for an editor, not a developer: counts first, then samples an
editor can eyeball in a minute, then the queue head.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from now_places.dedupe import DedupePlan
from now_places.triage import TriageResult

_SAMPLES = 8


def _esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _sample(items: list, k: int, seed: str) -> list:
    rng = random.Random(seed)
    return items if len(items) <= k else rng.sample(items, k)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_triage(result: TriageResult, *, db_ref: str, dedupe: DedupePlan | None = None, coverage_after_merges: tuple[int, float] | None = None) -> str:
    r = result
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Place triage — {r.site}",
        "",
        f"Generated {now} by `now-places triage {r.site}` against `{db_ref}` (dry run unless stated). "
        "Nothing in this report was written to the database.",
        "",
        "## Counts",
        "",
        "| | rows |",
        "|---|---:|",
        f"| places in the table | {r.total_rows:,} |",
        f"| already decided (junk/closed) | {r.already_decided:,} |",
        f"| already merged into another row | {r.merged:,} |",
        f"| **proposed junk** (`--apply` writes `status = junk`) | **{len(r.junk):,}** |",
        f"| junk-shaped but not pending (left alone) | {len(r.junk_skipped_not_pending):,} |",
        f"| suspect — editor decides in the desk | {len(r.suspect):,} |",
        f"| names another region — flagged, kept, never moved | {len(r.out_of_region):,} |",
        f"| in the curation queue | {len(r.queue):,} |",
        "",
        "## Does the top 500 cover the featured mentions?",
        "",
        f"Featured mentions in this city: **{r.coverage.featured_total:,}**.",
        "",
        f"Of those, {r.coverage.featured_on_junk:,} sit on rows proposed as junk — fragments no curated venue can cover.",
        "",
        "| list | featured mentions in the top 500 | share of all featured | share of featured on real venues |",
        "|---|---:|---:|---:|",
        f"| the queue (junk removed) | {r.coverage.featured_in_top:,} | {_pct(r.coverage.share)} | **{_pct(r.coverage.share_of_venues)}** |",
        f"| every row, nothing removed | {r.coverage_all_rows.featured_in_top:,} | {_pct(r.coverage_all_rows.share)} | — |",
    ]
    if coverage_after_merges is not None:
        denom = r.coverage.featured_total - r.coverage.featured_on_junk
        lines.append(f"| the queue after the proposed auto-merges | {coverage_after_merges[0]:,} | {_pct(coverage_after_merges[1])} | {_pct(coverage_after_merges[0] / denom if denom else 0)} |")
    lines += [
        "",
        "A featured mention on a junk row means the story featured a fragment, not a venue; it counts again once "
        "the mention is re-linked to a real row.",
        "",
    ]
    if r.partnership_term == "unavailable":
        lines += ["> The platform database could not be read, so the partnership term (+2) scored 0 for every row.", ""]

    lines += ["## Proposed junk, by reason", "", "| reason | rows | examples |", "|---|---:|---|"]
    by_reason: dict[str, list] = defaultdict(list)
    for p in r.junk:
        by_reason[(p.flags.get("reason") or "").split(" (")[0]].append(p)
    for reason, rows in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        ex = "; ".join(_esc(p.name) for p in _sample(rows, _SAMPLES, reason))
        lines.append(f"| {_esc(reason)} | {len(rows):,} | {ex} |")

    lines += ["", "### Proposed junk with the most evidence (check these first)", "", "| id | name | featured | articles | reason |", "|---:|---|---:|---:|---|"]
    for p in sorted(r.junk, key=lambda p: (-p.featured, -p.articles, p.id))[:25]:
        lines.append(f"| {p.id} | {_esc(p.name)} | {p.featured} | {p.articles} | {_esc(p.flags.get('reason') or '')} |")

    lines += ["", "## Suspect — shapes an editor should look at", "", "| reason | rows | examples |", "|---|---:|---|"]
    by_reason = defaultdict(list)
    for p in r.suspect:
        by_reason[(p.flags.get("reason") or "").split(" (")[0]].append(p)
    for reason, rows in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        ex = "; ".join(_esc(p.name) for p in _sample(rows, _SAMPLES, reason))
        lines.append(f"| {_esc(reason)} | {len(rows):,} | {ex} |")

    lines += ["", "## Names that point at another region", "",
              "Kept: this city's stories mention them. Flagged so the desk never makes one an itinerary candidate here "
              "(`region_ok` stays false until P1.3 geocodes the row).", "",
              "| region | rows | examples |", "|---|---:|---|"]
    by_region: dict[str, list] = defaultdict(list)
    for p in r.out_of_region:
        by_region[p.flags.get("region") or "?"].append(p)
    for region, rows in sorted(by_region.items(), key=lambda kv: -len(kv[1])):
        ex = "; ".join(f"{_esc(p.name)} ({_esc(p.flags.get('region_match') or '')})" for p in _sample(rows, _SAMPLES, region))
        lines.append(f"| {region} | {len(rows):,} | {ex} |")

    lines += ["", "## The queue — first 50 in rank order", "",
              "Score = 3 × featured mentions + articles + 2 × partnership + recency (0–1, newest mention within five years).", "",
              "| # | id | name | score | featured | articles | flag |", "|---:|---:|---|---:|---:|---:|---|"]
    for i, (p, score) in enumerate(r.queue[:50], start=1):
        flag = []
        if p.flags.get("tier") == "suspect":
            flag.append(f"suspect: {p.flags.get('reason')}")
        if p.flags.get("out_of_region"):
            flag.append(f"other region: {p.flags.get('region_match')}")
        lines.append(f"| {i} | {p.id} | {_esc(p.name)} | {score:.2f} | {p.featured} | {p.articles} | {_esc('; '.join(flag))} |")

    if dedupe is not None:
        lines += ["", render_dedupe_summary(dedupe)]
    return "\n".join(lines) + "\n"


def render_dedupe_summary(plan: DedupePlan) -> str:
    why = Counter(q.why for q in plan.queued)
    lines = [
        "## Duplicates",
        "",
        f"{plan.candidates:,} rows compared in {plan.blocks_compared:,} blocks ({plan.pairs_scored:,} pairs scored).",
        "",
        f"- **{len(plan.merges):,} merges** clear 0.85 with no guard objecting (applied only with `now-places dedupe --apply`).",
        f"- **{len(plan.queued):,} pairs queued** for an editor, never merged: "
        + ", ".join(f"{n:,} {w}" for w, n in why.most_common()),
        "",
        "| merge (loser → survivor) | score | mentions moved |",
        "|---|---:|---:|",
    ]
    for op in plan.merges[:25]:
        lines.append(f"| {_esc(op.loser.name)} (#{op.loser.id}) → {_esc(op.survivor.name)} (#{op.survivor.id}) | {op.score:.2f} | {op.loser.mentions} |")
    lines += ["", "| queued pair | score | why |", "|---|---:|---|"]
    for q in plan.queued[:25]:
        lines.append(f"| {_esc(q.a.name)} (#{q.a.id}) / {_esc(q.b.name)} (#{q.b.id}) | {q.score:.2f} | {_esc(q.why)} |")
    return "\n".join(lines)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")

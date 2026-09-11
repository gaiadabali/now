"""The filter trace panel -- ARCHITECTURE.md §17 names this "the
highest-value panel": *"why is this article not showing"*.

`engine/packages/filters` (E3.2) is being built concurrently this wave
and is not this package's to touch or depend on for its core logic (see
`filters_adapter.py` for the *optional*, defensive integration with it --
that only covers fallback-rung display, not the trace below). This
module is the Inspector's OWN, read-only re-application of
ARCHITECTURE.md §8's **hard filters** against real rows, built
specifically so this panel has real output before E3.2 ships anything
importable. It is a debug re-derivation for display, not a second
production filter implementation -- nothing here is meant to be reused
by `search`, `filters`, or `apps/api`.

Every rule below is evaluated with real data where the data exists, and
explicitly marked `data_status="not classified yet"` or `"not
applicable"` where it doesn't -- per the ticket's design note: absence of
data must be visible, never rendered as a silent pass.

Rules implemented (§8.A "Hard -- never violated"):

| Rule | Real today? | Why |
|---|---|---|
| status | yes | `public.articles._status`, real column, always populated |
| self | yes | trivial identity check, only meaningful in article-id mode |
| competitor (same L1 type) | **no data** | `primary_type` is NULL on all 4,772 rows (E2.1 pending) |
| quality floor | yes | `engine.quality_scores` is 4,772/4,772 populated (E2.6 done) |
| series dedup | yes | `articles.series_key` + `quality_scores.components.series.is_current` |
| event expiry | not applicable here | this generator only ever returns `kind='article'` rows |
| offer expiry | not applicable here | same -- no `format='offer'` rows reachable via this generator |
| venue closed | not applicable here | this generator returns articles, not places |
| tenancy (site_id) | not applicable | single-city-DB deployment; no cross-tenant rows possible in this query |

Only "status", "self", "competitor" and "series dedup" are exercised per
candidate; "quality floor" is exercised as a document-level check using
the real stored floor reference (`components.quality_floor_reference`,
written by `now-quality`, not re-declared here to avoid the two drifting).
"""

from __future__ import annotations

from now_inspector.models import ArticleRow, FilterTraceEntry, QualityBreakdown

_SEC_A = "ARCHITECTURE.md §8.A (Hard filters)"


def trace_status(article: ArticleRow | None) -> FilterTraceEntry:
    if article is None:
        return FilterTraceEntry(
            rule="status",
            rule_source=_SEC_A,
            removed=True,
            reason="Article row not found (deleted, or id does not exist).",
        )
    is_published = article.status == "published"
    return FilterTraceEntry(
        rule="status",
        rule_source=_SEC_A,
        removed=not is_published,
        reason=f"_status = {article.status!r}" + ("" if is_published else " -- excluded, not published"),
    )


def trace_self(article_id: int, seed_article_id: int | None) -> FilterTraceEntry | None:
    """Only meaningful in article-id mode (a query has no 'self' to
    exclude). Returns None when not applicable so callers can skip it."""
    if seed_article_id is None:
        return None
    is_self = article_id == seed_article_id
    return FilterTraceEntry(
        rule="self",
        rule_source=_SEC_A,
        removed=is_self,
        reason="This is the seed article itself." if is_self else "Different article than the seed.",
    )


def trace_competitor(article: ArticleRow | None, seed_article: ArticleRow | None) -> FilterTraceEntry:
    if seed_article is None:
        # Query mode: no seed type to compare against. The rule still exists
        # (relevant once a UI adds a "current article" context) but has
        # nothing to compare here.
        return FilterTraceEntry(
            rule="competitor (same L1 type)",
            rule_source=_SEC_A,
            removed=False,
            reason="Query mode has no seed article to compare `type` against.",
            data_status="not applicable",
        )
    if article is None or article.primary_type is None or seed_article.primary_type is None:
        return FilterTraceEntry(
            rule="competitor (same L1 type)",
            rule_source=_SEC_A,
            removed=False,
            reason="primary_type is NULL (E2.1 classification has not run) -- this rule cannot "
            "execute and defaults to NOT removing the candidate. That is a real gap, not a "
            "silent pass: once E2.1 lands, some of these candidates may turn out to be "
            "competitors and should start being excluded.",
            data_status="not classified yet",
        )
    same_l1 = _l1(article.primary_type) == _l1(seed_article.primary_type)
    return FilterTraceEntry(
        rule="competitor (same L1 type)",
        rule_source=_SEC_A,
        removed=same_l1,
        reason=f"primary_type={article.primary_type!r} vs seed {seed_article.primary_type!r}",
    )


def _l1(primary_type: str) -> str:
    # primary_type values are expected as "l1/subtype" or a bare L1 value;
    # be tolerant of either since E2.1's exact encoding is not finalised.
    return primary_type.split("/", 1)[0]


def trace_series_dedup(article: ArticleRow | None, quality: QualityBreakdown | None) -> FilterTraceEntry:
    if article is None or article.series_key is None:
        return FilterTraceEntry(
            rule="series dedup (one per series_key)",
            rule_source=_SEC_A,
            removed=False,
            reason="No series_key on this article -- rule not applicable.",
            data_status="not applicable",
        )
    is_current = None
    if quality is not None and quality.components:
        is_current = (quality.components.get("series") or {}).get("is_current")
    if is_current is None:
        return FilterTraceEntry(
            rule="series dedup (one per series_key)",
            rule_source=_SEC_A,
            removed=False,
            reason=f"series_key={article.series_key!r} but quality_scores.components.series."
            "is_current is unavailable -- cannot determine which member is canonical, so this "
            "candidate is not removed by default.",
            data_status="not classified yet",
        )
    return FilterTraceEntry(
        rule="series dedup (one per series_key)",
        rule_source=_SEC_A,
        removed=not is_current,
        reason=f"series_key={article.series_key!r}, is_current={is_current} "
        + ("(kept -- most recent member)" if is_current else "(removed -- superseded by a newer member)"),
    )


def trace_quality_floor(quality: QualityBreakdown | None) -> FilterTraceEntry:
    if quality is None or not quality.found or quality.score is None:
        return FilterTraceEntry(
            rule="quality floor",
            rule_source=_SEC_A,
            removed=False,
            reason="No engine.quality_scores row for this article -- floor cannot be evaluated.",
            data_status="not classified yet",
        )
    floor = 0.35
    if quality.components:
        floor = quality.components.get("quality_floor_reference", floor)
    below = quality.score < floor
    return FilterTraceEntry(
        rule="quality floor",
        rule_source=_SEC_A,
        removed=below,
        reason=f"score={quality.score:.4f} vs floor={floor:.2f}"
        + ("" if not below else " -- below floor, excluded"),
    )


def trace_event_expiry_not_applicable() -> FilterTraceEntry:
    return FilterTraceEntry(
        rule="event expiry",
        rule_source=_SEC_A,
        removed=False,
        reason="This generator only returns kind='article' rows; event expiry applies to the "
        "events table, not exercised by this candidate set.",
        data_status="not applicable",
    )


def build_trace(
    *,
    article: ArticleRow | None,
    entity_id: str,
    quality: QualityBreakdown | None,
    seed_article: ArticleRow | None,
    seed_article_id: int | None,
) -> list[FilterTraceEntry]:
    """Full §8.A hard-filter trace for one candidate. Order matches §8.G's
    stated cheap-to-expensive ordering (status/self/competitor are free
    column checks; quality floor and series dedup need the quality join)."""
    entries: list[FilterTraceEntry] = [trace_status(article)]

    self_entry = trace_self(int(entity_id), seed_article_id)
    if self_entry is not None:
        entries.append(self_entry)

    entries.append(trace_competitor(article, seed_article))
    entries.append(trace_series_dedup(article, quality))
    entries.append(trace_quality_floor(quality))
    entries.append(trace_event_expiry_not_applicable())
    return entries


def survived(entries: list[FilterTraceEntry]) -> tuple[bool, str]:
    for e in entries:
        if e.removed:
            return False, f"removed by {e.rule!r} ({e.reason})"
    return True, "passed every hard filter"

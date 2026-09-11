"""Full run: articles.jsonl -> (org rows, exclusion rows, stats).

Pure functions over in-memory data — the CLI (`cli.py`) owns file I/O so
this module stays testable without touching disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from now_content_clean.pipeline import clean_article

from now_partner_roster.cluster import DomainAgg, OrgRow, build_clusters
from now_partner_roster.domains import classify, extract_netloc

_SAMPLE_CAP = 8


@dataclass
class ExclusionAgg:
    domain: str
    reason: str
    link_count: int = 0
    article_ids: set[int] = field(default_factory=set)
    sample_articles: list[int] = field(default_factory=list)


@dataclass
class RunStats:
    articles: int = 0
    articles_with_ext_link: int = 0
    total_raw_hrefs: int = 0  # every <a href>, before any filtering
    total_upload_links: int = 0
    total_non_http_links: int = 0  # mailto:, tel:, relative, empty, javascript:
    total_external_links: int = 0  # absolute http(s), not our own site, not upload
    total_excluded_links: int = 0  # subset of the above: social/stock/shortener/utility/internal
    total_candidate_links: int = 0  # external_links minus excluded
    rel_totals: dict[str, int] = field(default_factory=lambda: {"none": 0, "nofollow": 0, "sponsored": 0})
    distinct_domains_candidate: int = 0
    distinct_domains_excluded: int = 0


def run(articles_iter) -> tuple[list[OrgRow], list[ExclusionAgg], RunStats]:
    """`articles_iter` yields article dicts (E1.1 contract: wp_id,
    content_html, date, ...)."""

    domain_aggs: dict[str, DomainAgg] = {}
    exclusions: dict[str, ExclusionAgg] = {}
    stats = RunStats()

    for article in articles_iter:
        stats.articles += 1
        wp_id = article.get("wp_id")
        date = (article.get("date") or "")[:10] or None

        result = clean_article(article)
        had_ext = False

        for link in result.links:
            stats.total_raw_hrefs += 1
            if link.is_upload:
                stats.total_upload_links += 1
                continue

            netloc = extract_netloc(link.href)
            if netloc is None:
                stats.total_non_http_links += 1
                continue

            stats.total_external_links += 1
            had_ext = True

            rel_tokens = (link.rel or "").lower().split()
            if "sponsored" in rel_tokens:
                rel_bucket = "sponsored"
            elif "nofollow" in rel_tokens:
                rel_bucket = "nofollow"
            else:
                rel_bucket = "none"
            stats.rel_totals[rel_bucket] += 1

            classification = classify(netloc)
            if classification.excluded:
                stats.total_excluded_links += 1
                exc = exclusions.setdefault(
                    netloc, ExclusionAgg(domain=netloc, reason=classification.reason)
                )
                exc.link_count += 1
                exc.article_ids.add(wp_id)
                if wp_id not in exc.sample_articles and len(exc.sample_articles) < _SAMPLE_CAP:
                    exc.sample_articles.append(wp_id)
                continue

            stats.total_candidate_links += 1
            agg = domain_aggs.setdefault(netloc, DomainAgg(netloc=netloc))
            agg.link_count += 1
            agg.article_ids.add(wp_id)
            if date:
                agg.dates.append(date)
            if rel_bucket == "sponsored":
                agg.rel_sponsored += 1
            elif rel_bucket == "nofollow":
                agg.rel_nofollow += 1
            else:
                agg.rel_none += 1
            if wp_id not in agg.sample_articles and len(agg.sample_articles) < _SAMPLE_CAP:
                agg.sample_articles.append(wp_id)

        if had_ext:
            stats.articles_with_ext_link += 1

    stats.distinct_domains_candidate = len(domain_aggs)
    stats.distinct_domains_excluded = len(exclusions)

    org_rows = build_clusters(domain_aggs)
    return org_rows, list(exclusions.values()), stats


def iter_jsonl(path) -> "list[dict]":
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

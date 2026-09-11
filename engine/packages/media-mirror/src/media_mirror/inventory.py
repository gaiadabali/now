from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit

from .config import CANONICAL_HOST, REPO_ROOT, SITE_HOSTS
from .extract import canonical_key, extract_article_urls

ARTICLES_REL = "content/extracted/articles.jsonl"
ATTACHMENTS_REL = "content/extracted/attachments.jsonl"


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


@dataclass
class InventoryEntry:
    canonical_key: str
    city: str
    urls: set[str] = field(default_factory=set)
    in_articles: bool = False
    in_attachments: bool = False
    attachment_wp_id: int | None = None
    attachment_alt: str | None = None
    attachment_credit: str | None = None
    article_count: int = 0


def base_url_for(city: str) -> str:
    return f"https://{CANONICAL_HOST[city]}"


def build_inventory(repo_root: Path = REPO_ROOT) -> dict[str, InventoryEntry]:
    """Union of inline-HTML URLs and attachments.jsonl URLs, per city, keyed
    on host+path with www/bare-host folded together (config.canonical_key).
    """
    entries: dict[str, InventoryEntry] = {}

    def get(city: str, url: str) -> InventoryEntry:
        key = f"{city}:{canonical_key(url)}"
        entry = entries.get(key)
        if entry is None:
            entry = InventoryEntry(canonical_key=key, city=city)
            entries[key] = entry
        entry.urls.add(url)
        return entry

    for city in SITE_HOSTS:
        base_url = base_url_for(city)
        articles_path = repo_root / city / ARTICLES_REL
        for article in _iter_jsonl(articles_path):
            html = article.get("content_html") or ""
            seen_in_article: set[str] = set()
            for url in extract_article_urls(html, base_url):
                entry = get(city, url)
                entry.in_articles = True
                seen_in_article.add(entry.canonical_key)
            for key in seen_in_article:
                entries[key].article_count += 1

        attachments_path = repo_root / city / ATTACHMENTS_REL
        for attachment in _iter_jsonl(attachments_path):
            url = attachment.get("url")
            if not url:
                continue
            host = urlsplit(url).netloc
            if host not in SITE_HOSTS[city]:
                continue  # F11: a handful of attachment URLs point off-host
            entry = get(city, url)
            entry.in_attachments = True
            entry.attachment_wp_id = attachment.get("wp_id")
            entry.attachment_alt = attachment.get("alt")
            entry.attachment_credit = attachment.get("credit")

    return entries


def write_inventory(entries: dict[str, InventoryEntry], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for entry in entries.values():
            # Prefer the canonical (www) form as the fetch URL when present,
            # else whatever variant we actually saw.
            city_host = CANONICAL_HOST[entry.city]
            preferred = next((u for u in entry.urls if urlsplit(u).netloc == city_host), None)
            fetch_url = preferred or sorted(entry.urls)[0]
            record = {
                "key": entry.canonical_key,
                "city": entry.city,
                "fetch_url": fetch_url,
                "url_variants": sorted(entry.urls),
                "in_articles": entry.in_articles,
                "in_attachments": entry.in_attachments,
                "article_ref_count": entry.article_count,
                "attachment_wp_id": entry.attachment_wp_id,
                "attachment_alt": entry.attachment_alt,
                "attachment_credit": entry.attachment_credit,
            }
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
    tmp.replace(out_path)


def summarize(entries: dict[str, InventoryEntry]) -> dict[str, Any]:
    by_city: dict[str, dict[str, int]] = {}
    for city in SITE_HOSTS:
        city_entries = [e for e in entries.values() if e.city == city]
        both = sum(1 for e in city_entries if e.in_articles and e.in_attachments)
        articles_only = sum(1 for e in city_entries if e.in_articles and not e.in_attachments)
        attachments_only = sum(1 for e in city_entries if e.in_attachments and not e.in_articles)
        variant_dupes = sum(len(e.urls) - 1 for e in city_entries if len(e.urls) > 1)
        by_city[city] = {
            "total_distinct_assets": len(city_entries),
            "in_articles": sum(1 for e in city_entries if e.in_articles),
            "in_attachments": sum(1 for e in city_entries if e.in_attachments),
            "overlap_both_sources": both,
            "articles_only_no_attachment_row": articles_only,
            "attachments_only_not_inlined": attachments_only,
            "host_variant_duplicates_folded": variant_dupes,
        }
    total_union = len(entries)
    return {"by_city": by_city, "total_union_distinct_assets": total_union}

"""`articles` <- `articles.jsonl` (E1.1 contract; 4,772 published posts).

`content_html` -> `body_blocks` goes through `now_content_clean.clean_article`
unmodified (ARCHITECTURE.md §6: "Use it; do not re-parse HTML") and is
written to the `jsonb` column as-is via `CAST(:body_blocks AS jsonb)` —
byte-for-byte what the cleaner produced, satisfying the round-trip
acceptance criterion (compare field-by-field, never by raw string, because
`jsonb` reorders object keys).

**F83 — content-loss reporting only ever surfaced `max`, never median/p95,
and never the word-delta at all.** `now_content_clean.metrics.content_loss`
returns both a char-based `loss_pct` *and* a `word_delta` (`words_lost`/
`words_gained`) specifically because a character count cannot see word
welding (`<br>` collapsing "the" + "colonial" into "thecolonial" moves 0
chars but 2 words) — the docstring there is explicit that the two must
never be reported apart. `load_events.py` already aggregates median/p95/
word-delta totals; this module only ever tracked `content_loss_max`,
silently dropping the word-delta signal for every one of the 4,772/4,429
articles run through it. Fixed here (see `textutil.summarize_content_loss`,
unit-tested in isolation since this package has no DB-backed test harness
for `articles` — `now_test` carries no Payload schema).

**Scope guard (explicit ticket instruction):** `primary_type` and `format`
are never set by this loader — they stay `NULL` for E2.1 to fill after
Hansel's taxonomy-mapping review. This module has no code path that writes
either column at all (not even to a default), so there is nothing to
accidentally regress later.

**`media_ref` values inside `body_blocks` are left as original WordPress
URLs.** E1.3 (media -> Garage) has not run. See the final report for the
exact rewrite recipe.

Idempotency key: `legacy_wp_id` (verified `UNIQUE` in the live schema).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from now_content_clean import clean_article
from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.series import derive_series_keys
from now_loader.sources import iter_jsonl
from now_loader.textutil import strip_tags_light, summarize_content_loss

_UPSERT = text(
    """
    INSERT INTO "public"."articles"
        (kind, title, dek, body_blocks, hero_media_id, author_id,
         published_at, legacy_wp_id, legacy_permalink, series_key,
         _status, updated_at, created_at)
    VALUES
        ('article', :title, :dek, CAST(:body_blocks AS jsonb), :hero_media_id, :author_id,
         :published_at, :legacy_wp_id, :legacy_permalink, :series_key,
         'published', now(), now())
    ON CONFLICT (legacy_wp_id) DO UPDATE
       SET title = EXCLUDED.title,
           dek = EXCLUDED.dek,
           body_blocks = EXCLUDED.body_blocks,
           hero_media_id = EXCLUDED.hero_media_id,
           author_id = EXCLUDED.author_id,
           published_at = EXCLUDED.published_at,
           legacy_permalink = EXCLUDED.legacy_permalink,
           series_key = EXCLUDED.series_key,
           _status = 'published',
           updated_at = now()
    RETURNING id
    """
)


@dataclass
class ArticlesLoadResult:
    read: int = 0
    inserted_or_updated: int = 0
    missing_author: int = 0
    missing_hero_media: int = 0
    dek_from_excerpt: int = 0
    dek_from_yoast_metadesc: int = 0
    dek_missing: int = 0
    series_key_assigned: int = 0
    content_loss_max: float = 0.0
    content_loss_median: float | None = None
    content_loss_p95: float | None = None
    words_lost_total: int = 0
    words_gained_total: int = 0
    total_uploads_referenced: int = 0
    uploads_unresolved: int = 0
    wp_id_to_article_id: dict[int, int] = field(default_factory=dict)


def _dek_for(article: dict, result: ArticlesLoadResult) -> str | None:
    excerpt = strip_tags_light(article.get("excerpt"))
    if excerpt:
        result.dek_from_excerpt += 1
        return excerpt
    metadesc = strip_tags_light((article.get("meta") or {}).get("_yoast_wpseo_metadesc"))
    if metadesc:
        result.dek_from_yoast_metadesc += 1
        return metadesc
    result.dek_missing += 1
    return None


def load_articles(
    conn: Connection,
    articles_path: Path,
    author_wp_id_to_author_id: dict[int, int],
    media_wp_id_to_media_id: dict[int, int],
    known_upload_urls: set[str],
) -> ArticlesLoadResult:
    result = ArticlesLoadResult()
    loss_pcts: list[float] = []

    # series_key needs the whole corpus's titles at once (a series is
    # defined by >=2 articles sharing a derived key) — read titles first.
    titles_by_wp_id: dict[int, str] = {}
    for article in iter_jsonl(articles_path):
        titles_by_wp_id[article["wp_id"]] = article["title"]
    series_keys = derive_series_keys(titles_by_wp_id)
    result.series_key_assigned = len(series_keys)

    for article in iter_jsonl(articles_path):
        result.read += 1
        wp_id = article["wp_id"]

        clean = clean_article(article)
        loss = clean.stats.get("content_loss") or {}
        loss_pct = loss.get("loss_pct", 0.0)
        try:
            result.content_loss_max = max(result.content_loss_max, float(loss_pct))
        except (TypeError, ValueError):
            pass
        # F83: chars_in > 0 gate mirrors load_events.py — an empty body has
        # no meaningful loss_pct (division-by-zero guard already makes it
        # 0.0 upstream) and would otherwise dilute the median/p95 with a
        # false "perfect" data point.
        if loss.get("chars_in", 0) > 0:
            loss_pcts.append(loss_pct)
            word_delta = loss.get("word_delta") or {}
            result.words_lost_total += word_delta.get("words_lost", 0)
            result.words_gained_total += word_delta.get("words_gained", 0)

        for upload in clean.uploads:
            result.total_uploads_referenced += 1
            if upload.url not in known_upload_urls:
                result.uploads_unresolved += 1

        author_id = author_wp_id_to_author_id.get(article.get("author_id"))
        if article.get("author_id") and author_id is None:
            result.missing_author += 1

        thumbnail_id = article.get("thumbnail_id")
        hero_media_id = media_wp_id_to_media_id.get(thumbnail_id) if thumbnail_id else None
        if thumbnail_id and hero_media_id is None:
            result.missing_hero_media += 1

        legacy_permalink = urlparse(article["permalink"]).path if article.get("permalink") else None

        article_id = conn.execute(
            _UPSERT,
            {
                "title": article.get("title"),
                "dek": _dek_for(article, result),
                "body_blocks": _dump_json(clean.blocks),
                "hero_media_id": hero_media_id,
                "author_id": author_id,
                "published_at": article.get("date"),
                "legacy_wp_id": wp_id,
                "legacy_permalink": legacy_permalink,
                "series_key": series_keys.get(wp_id),
            },
        ).scalar_one()

        result.wp_id_to_article_id[wp_id] = article_id
        result.inserted_or_updated += 1

    summary = summarize_content_loss(loss_pcts)
    result.content_loss_median = summary["median"]
    result.content_loss_p95 = summary["p95"]

    return result


def _dump_json(blocks: list[dict]) -> str:
    return json.dumps(blocks, ensure_ascii=False)

"""Turn parsed WXR items into the same frozen JSONL contract now-wp-extract
produces, field-for-field, as confirmed by inspecting
`jakarta/content/extracted/*.jsonl` directly.

Known, deliberate deviations from a byte-for-byte match (all forced by what
WXR does and does not carry — see the final report for full evidence):

- Article `categories` are NOT reordered to put the Yoast primary category
  first. wp-extract can do that because the MariaDB dump gives it numeric
  category term_ids to match `_yoast_wpseo_primary_category` against. WXR's
  inline <category domain="category"> elements carry only a slug
  ("nicename") and display name, never a numeric term_id, and neither
  export defines the `category` taxonomy in a channel-level <wp:term> block
  either (confirmed: zero <wp:term taxonomy="category"> anywhere). There is
  no honest way to resolve the primary-category id to a name from WXR
  alone, so the meta value is preserved verbatim and no reordering happens.
- `tags` are still always `[]`, matching wp-extract (discarded per
  ARCHITECTURE.md §6 regardless of source).
- Attachment `mime` is inferred from the file extension via the stdlib
  `mimetypes` module. WXR has no `wp:post_mime_type` element at all
  (confirmed: absent from every attachment <item> in both exports) — the
  dump-derived extractor reads it straight from `wp_posts.post_mime_type`,
  which WXR simply does not export.
- Attachment `url` prefers WXR's own `<wp:attachment_url>` (the file URL
  WordPress itself recorded at export time) over reconstructing from
  `_wp_attached_file`, since the former is directly authoritative here and
  needs no site_home guessing; falls back to `_wp_attached_file` then
  `guid` if attachment_url is ever missing.
- `events.jsonl` / `venues.jsonl` are empty for both cities: WXR contains
  no `tribe_events`, `upcoming-events`, or `tribe_venue` items at all
  (confirmed by a full post_type census of every export) — WordPress's own
  exporter silently omits `upcoming-events` (`can_export => false`, per
  PROGRESS.md B1) and Events Calendar Pro's CPTs were never used on either
  site's exported content, matching Jakarta's dump (Bali's REST harvest
  reported `upcoming-events` counts, but those posts are not tribe_events/
  tribe_venue rows in the DB export sense wp-extract targets).
- `geo.jsonl`'s MapPress rows are unreachable from WXR by construction: the
  MapPress map data lives in a plugin table (`mappress_maps`/
  `mappress_posts`) that WXR — a posts/postmeta/terms/comments export —
  never includes. Only the ACF `google_map` postmeta path is reachable, and
  a direct scan of every <wp:postmeta> in both exports found ZERO real
  posts carrying a `google_map` meta_key (the only 22 occurrences of the
  string in Bali's export are the ACF field *definition* on the `acf-field`
  CPT, not stored values on real posts) — so geo.jsonl is genuinely empty
  from WXR for both cities. This is a hard limit of the source, not a bug.
"""

from __future__ import annotations

import mimetypes
from collections import Counter, defaultdict
from typing import Any

from wxr_extract.jsonl import iso
from wxr_extract.wp_extract_shim import (
    ARTICLE_META_KEYS,
    ATTACHMENT_META_KEYS,
    php_unserialize,
)
from wxr_extract.wxr_parser import ChannelMeta, WxrItem

CONTENT_TAXONOMIES = {"category", "post_tag", "tribe_events_cat", "event_category", "event-tag"}


def permalink_for(site_home: str, slug: str | None) -> str:
    return f"{site_home}/{slug or ''}/"


def dedupe_items(items_by_source: list[list[WxrItem]]) -> tuple[list[WxrItem], int]:
    """Merge items from multiple WXR files (e.g. Jakarta's all/attachment/
    pages exports), de-duplicating by wp_id. First occurrence wins; later
    duplicates are counted and reported so a real content difference
    between the two copies would be visible rather than silently dropped.
    """
    seen: dict[int, WxrItem] = {}
    dupes = 0
    for items in items_by_source:
        for it in items:
            if it.wp_id in seen:
                dupes += 1
                continue
            seen[it.wp_id] = it
    ordered = sorted(seen.values(), key=lambda i: i.wp_id)
    return ordered, dupes  # type: ignore[return-value]


def author_id_for(login: str | None, authors_by_login: dict[str, dict[str, Any]]) -> int | None:
    if not login:
        return None
    a = authors_by_login.get(login)
    return a["wp_id"] if a else None


def build_articles(
    items: list[WxrItem], authors_by_login: dict[str, dict[str, Any]], site_home: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    posts = [it for it in items if it.post_type == "post" and it.status == "publish"]

    with_categories = 0
    rows: list[dict[str, Any]] = []
    for p in posts:
        cats = [name for domain, _nicename, name in p.categories if domain == "category" and name]
        if cats:
            with_categories += 1

        meta_out = {k: v for k, v in p.postmeta.items() if k in ARTICLE_META_KEYS and k != "_thumbnail_id"}
        thumb = p.postmeta.get("_thumbnail_id")

        rows.append(
            {
                "wp_id": p.wp_id,
                "type": "post",
                "status": p.status,
                "title": p.title,
                "slug": p.slug,
                "content_html": p.content_html,
                "excerpt": p.excerpt,
                "date": iso(p.post_date),
                "modified": iso(p.post_modified),
                "author_id": author_id_for(p.creator_login, authors_by_login),
                "permalink": permalink_for(site_home, p.slug),
                "categories": cats,
                "tags": [],
                "meta": meta_out,
                "thumbnail_id": int(thumb) if thumb not in (None, "") else None,
            }
        )

    stats = {
        "posts_in": len(posts),
        "posts_out": len(rows),
        "with_categories": with_categories,
        "coverage_pct": round(100 * with_categories / len(rows), 1) if rows else 0.0,
    }
    return rows, stats


_FILE_EXT_RE_FALLBACK = "application/octet-stream"


def build_attachments(items: list[WxrItem], site_home: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    posts = [it for it in items if it.post_type == "attachment"]

    with_alt = 0
    with_dims = 0
    rows: list[dict[str, Any]] = []
    for p in posts:
        meta = {k: v for k, v in p.postmeta.items() if k in ATTACHMENT_META_KEYS}
        alt = meta.get("_wp_attachment_image_alt")
        if alt:
            with_alt += 1

        width = height = None
        raw_meta = php_unserialize(meta.get("_wp_attachment_metadata"))
        if isinstance(raw_meta, dict):
            width = raw_meta.get("width")
            height = raw_meta.get("height")
        if width and height:
            with_dims += 1

        attached_file = meta.get("_wp_attached_file")
        url = p.attachment_url or (
            f"{site_home}/wp-content/uploads/{attached_file}" if attached_file else p.guid
        )
        mime, _enc = mimetypes.guess_type(url or "")

        rows.append(
            {
                "wp_id": p.wp_id,
                "url": url,
                "guid": p.guid,
                "file": attached_file,
                "mime": mime,
                "title": p.title,
                "alt": alt,
                "credit": None,
                "width": width,
                "height": height,
                "parent_post_id": p.post_parent,
                "date": iso(p.post_date),
            }
        )

    stats = {
        "attachments_in": len(posts),
        "attachments_out": len(rows),
        "with_alt_text": with_alt,
        "with_dimensions": with_dims,
    }
    return rows, stats


def build_terms(items: list[WxrItem], channel_terms: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # category / post_tag: only available inline per-item, no numeric
    # term_id anywhere in either export. Aggregate by (taxonomy, slug).
    counters: dict[tuple[str, str], Counter] = defaultdict(Counter)
    names: dict[tuple[str, str], str] = {}
    for it in items:
        for domain, nicename, name in it.categories:
            taxonomy = "post_tag" if domain == "post_tag" else ("category" if domain == "category" else None)
            if taxonomy is None or not nicename:
                continue
            key = (taxonomy, nicename)
            counters[taxonomy][nicename] += 1
            names[key] = name

    for taxonomy, counter in counters.items():
        for slug, count in counter.items():
            rows.append(
                {
                    "term_id": None,  # not present in WXR for category/post_tag — see module docstring
                    "term_taxonomy_id": None,
                    "taxonomy": taxonomy,
                    "name": names[(taxonomy, slug)],
                    "slug": slug,
                    "parent": None,
                    "count": count,
                    "description": None,
                }
            )

    # event_category / event-tag / nav_menu (and whatever else) DO come
    # through as channel-level <wp:term> blocks with real term_ids.
    for t in channel_terms:
        if t["taxonomy"] not in CONTENT_TAXONOMIES:
            continue
        rows.append(
            {
                "term_id": t["term_id"],
                "term_taxonomy_id": t["term_id"],
                "taxonomy": t["taxonomy"],
                "name": t["name"],
                "slug": t["slug"],
                "parent": t["parent"],
                "count": None,  # WXR's <wp:term> carries no usage count
                "description": None,
            }
        )

    by_taxonomy: dict[str, int] = {}
    for r in rows:
        by_taxonomy[r["taxonomy"]] = by_taxonomy.get(r["taxonomy"], 0) + 1

    stats = {"terms_out": len(rows), "by_taxonomy": by_taxonomy}
    return rows, stats


def build_users(
    authors_by_login: dict[str, dict[str, Any]], articles: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counts_by_author: Counter = Counter(a["author_id"] for a in articles if a["author_id"] is not None)

    rows = [
        {
            "wp_id": a["wp_id"],
            "login": a["login"],
            "nicename": a["login"],  # WXR's wp:author has no separate nicename field
            "display_name": a["display_name"],
            "email": a["email"],
            "url": None,  # WXR's wp:author has no author URL field
            "registered": None,  # WXR's wp:author has no registration-date field
            "published_post_count": counts_by_author.get(a["wp_id"], 0),
        }
        for a in authors_by_login.values()
    ]
    rows.sort(key=lambda r: r["wp_id"])

    stats = {
        "users_out": len(rows),
        "users_with_published_posts": sum(1 for r in rows if r["published_post_count"] > 0),
    }
    return rows, stats


def build_geo(items: list[WxrItem]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """ACF `google_map` postmeta only — see module docstring for why
    MapPress cannot be reached from WXR at all.
    """
    rows: list[dict[str, Any]] = []
    google_map_total = 0
    google_map_deserialized = 0

    for it in items:
        raw = it.postmeta.get("google_map")
        if raw is None:
            continue
        google_map_total += 1
        obj = php_unserialize(raw)
        if not isinstance(obj, dict):
            continue
        google_map_deserialized += 1
        lat, lng = obj.get("lat"), obj.get("lng")
        try:
            lat_f = float(lat) if lat not in (None, "") else None
            lng_f = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            lat_f = lng_f = None
        rows.append(
            {
                "source": "google_map",
                "wp_id": it.wp_id,
                "map_id": None,
                "poi_index": None,
                "title": obj.get("name"),
                "address": obj.get("address"),
                "lat": lat_f,
                "lng": lng_f,
                "place_id": obj.get("place_id"),
            }
        )

    stats = {
        "mappress_maps_total": 0,
        "mappress_pois_with_coords": 0,
        "mappress_note": "unreachable from WXR — plugin table, not exported (see module docstring)",
        "google_map_postmeta_total": google_map_total,
        "google_map_deserialized_ok": google_map_deserialized,
        "geo_rows_out": len(rows),
    }
    return rows, stats


def build_events_and_venues(items: list[WxrItem]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """WXR contains none of tribe_events / upcoming-events / tribe_venue in
    either export (confirmed by full post_type census) — always empty.
    """
    present_types = {"tribe_events", "upcoming-events", "tribe_venue"} & {it.post_type for it in items}
    events_stats = {
        "tribe_events_in": 0,
        "upcoming_events_in": 0,
        "events_out": 0,
        "note": (
            "WXR contains none of these post types (confirmed by census)"
            if not present_types
            else f"WXR unexpectedly contains: {sorted(present_types)} — extraction logic not yet written for these, escalate"
        ),
    }
    venues_stats = {
        "venues_in": 0,
        "venues_out": 0,
        "note": events_stats["note"],
    }
    return [], events_stats, [], venues_stats

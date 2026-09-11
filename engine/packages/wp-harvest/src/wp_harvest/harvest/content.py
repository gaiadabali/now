from __future__ import annotations

import html
import re
from typing import Any

TAG_RE = re.compile(r"<[^>]+>")


def rendered(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("rendered")
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def plain_title(value: Any) -> str | None:
    """Titles arrive HTML-encoded (``&amp;``); the extract stores them decoded."""
    text = rendered(value)
    if text is None:
        return None
    return html.unescape(TAG_RE.sub("", text)).strip() or None


def raw_or_rendered(value: Any) -> str | None:
    """Prefer ``raw`` (only present under ``context=edit``) over ``rendered``.

    This is the whole reason the authenticated harvest exists: ``rendered``
    has been through the_content filters, so shortcodes are expanded and the
    cache plugin's lazy-load attributes are baked in. ``raw`` is the actual
    ``post_content`` column, which is what the dump-based Jakarta extract fed
    to the content cleaner.
    """
    if isinstance(value, dict):
        if value.get("raw") is not None:
            text = str(value["raw"])
            return text if text.strip() else None
        return rendered(value)
    return rendered(value)


def content_is_raw(record: dict[str, Any]) -> bool:
    content = record.get("content")
    return isinstance(content, dict) and content.get("raw") is not None


def project_term(record: dict[str, Any]) -> dict[str, Any]:
    """Shape follows ``extracted/terms.jsonl``."""
    return {
        "term_id": record.get("id"),
        "term_taxonomy_id": record.get("id"),
        "taxonomy": record.get("taxonomy"),
        "name": html.unescape(record.get("name") or "") or None,
        "slug": record.get("slug"),
        "parent": record.get("parent") or None,
        "count": record.get("count"),
        "description": record.get("description") or None,
    }


def project_user(record: dict[str, Any]) -> dict[str, Any]:
    """Shape follows ``extracted/users.jsonl``.

    ``email`` and ``login`` are absent unauthenticated — WordPress does not
    expose them to anonymous callers. Left as None rather than invented.
    """
    return {
        "wp_id": record.get("id"),
        "login": record.get("slug"),
        "nicename": record.get("slug"),
        "display_name": html.unescape(record.get("name") or "") or None,
        "email": record.get("email"),
        "url": record.get("url") or None,
        "registered": record.get("registered_date"),
        "description": record.get("description") or None,
        "avatar_urls": record.get("avatar_urls") or None,
        "published_post_count": None,
    }


def project_post(
    record: dict[str, Any],
    category_names: dict[int, str] | None = None,
    tag_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Shape follows ``extracted/articles.jsonl``, plus live-only extras.

    Taxonomy is emitted as *names* (as the extract does) with the raw ids kept
    alongside, so a consumer can join on either without a second lookup.
    """
    cats = category_names or {}
    tags = tag_names or {}
    category_ids = list(record.get("categories") or [])
    tag_ids = list(record.get("tags") or [])

    return {
        "wp_id": record.get("id"),
        "type": record.get("type"),
        "status": record.get("status"),
        "title": plain_title(record.get("title")),
        "content_html": raw_or_rendered(record.get("content")),
        "content_is_raw": content_is_raw(record),
        "excerpt": raw_or_rendered(record.get("excerpt")),
        "date": record.get("date"),
        "date_gmt": record.get("date_gmt"),
        "modified": record.get("modified"),
        "author_id": record.get("author"),
        "permalink": record.get("link"),
        "slug": record.get("slug"),
        "categories": [cats[cid] for cid in category_ids if cid in cats],
        "tags": [tags[tid] for tid in tag_ids if tid in tags],
        "category_ids": category_ids,
        "tag_ids": tag_ids,
        "meta": record.get("meta") or {},
        "acf": record.get("acf") or None,
        "thumbnail_id": record.get("featured_media") or None,
        "comment_status": record.get("comment_status"),
        "format": record.get("format"),
        "template": record.get("template") or None,
    }


def project_comment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "wp_id": record.get("id"),
        "post_wp_id": record.get("post"),
        "parent_wp_id": record.get("parent") or None,
        "author_wp_id": record.get("author") or None,
        "author_name": html.unescape(record.get("author_name") or "") or None,
        "author_url": record.get("author_url") or None,
        "date": record.get("date"),
        "date_gmt": record.get("date_gmt"),
        "content_html": raw_or_rendered(record.get("content")),
        "status": record.get("status"),
        "type": record.get("type"),
    }


def name_index(terms: list[dict[str, Any]]) -> dict[int, str]:
    """term_id -> name, from already-projected term rows."""
    index: dict[int, str] = {}
    for term in terms:
        term_id, name = term.get("term_id"), term.get("name")
        if isinstance(term_id, int) and name:
            index[term_id] = name
    return index

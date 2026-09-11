from __future__ import annotations

import re
from typing import Any

import pymysql

from wp_extract.config import Config
from wp_extract.extract.common import fetch_postmeta, fetch_posts
from wp_extract.jsonl import iso
from wp_extract.phpunserialize import php_unserialize

ATTACHMENT_META_KEYS = [
    "_wp_attached_file",
    "_wp_attachment_image_alt",
    "_wp_attachment_metadata",
]

_FILE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp|pdf|mp4|svg|mov|avi)$", re.IGNORECASE)


def extract_attachments(conn: pymysql.connections.Connection, cfg: Config) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    posts = fetch_posts(conn, "attachment", status=None)
    meta_by_post = fetch_postmeta(conn, ATTACHMENT_META_KEYS)

    with_alt = 0
    with_dims = 0
    guid_not_a_file_url = 0
    rows: list[dict[str, Any]] = []
    for p in posts:
        pid = p["ID"]
        meta = meta_by_post.get(pid, {})
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
        guid = p["guid"]
        if not _FILE_EXT_RE.search(guid or ""):
            guid_not_a_file_url += 1
        # `guid` is unreliable as a download URL for this dump: ~20% of
        # attachments (mostly ones whose guid domain is a staging alias,
        # `nj.gaiada.com`) have a pretty attachment-page-style guid
        # (".../element5-digital-xyz-jpg/") instead of the raw upload path.
        # `_wp_attached_file` is present on 13,820/13,817 rows and is
        # authoritative, so the real file URL is always reconstructed from
        # it against the live site's uploads base — guid is kept only as a
        # fallback for the handful of rows missing `_wp_attached_file`.
        url = f"{cfg.site_home}/wp-content/uploads/{attached_file}" if attached_file else guid

        rows.append(
            {
                "wp_id": pid,
                "url": url,
                "guid": guid,
                "file": attached_file,
                "mime": p["post_mime_type"],
                "title": p["post_title"],
                "alt": alt,
                # No credit/attribution meta key exists anywhere in this dump
                # (searched for %credit%/%caption%/%source% postmeta keys —
                # zero hits). Left null rather than fabricated; see report.
                "credit": None,
                "width": width,
                "height": height,
                "parent_post_id": p["post_parent"] or None,
                "date": iso(p["post_date"]),
            }
        )

    stats = {
        "attachments_in": len(posts),
        "attachments_out": len(rows),
        "with_alt_text": with_alt,
        "with_dimensions": with_dims,
        "guid_not_a_direct_file_url": guid_not_a_file_url,
    }
    return rows, stats

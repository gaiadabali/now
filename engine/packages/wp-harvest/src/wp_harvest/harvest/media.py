from __future__ import annotations

import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

# WordPress appends -WIDTHxHEIGHT for a resized derivative and -N for a
# numbered duplicate filename. F29 traced 3,359 unmatched inline media
# references to exactly these two suffixes, so both are stripped when
# building the basename match keys.
SIZE_SUFFIX_RE = re.compile(r"-\d{1,5}x\d{1,5}$")
DUP_SUFFIX_RE = re.compile(r"-\d{1,3}$")


def _rendered(value: Any) -> str | None:
    """Unwrap WordPress's ``{"rendered": ...}`` envelope."""
    if isinstance(value, dict):
        value = value.get("rendered")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def path_of(url: str | None) -> str | None:
    """Host-independent, percent-decoded path — the F29 host-variant fix."""
    if not url:
        return None
    return unquote(urlsplit(url).path) or None


def match_keys(source_url: str | None, file_path: str | None) -> list[str]:
    """Every key an inline ``<img src>`` might plausibly be matched on.

    Ordered most to least specific. A consumer should try them in order and
    stop at the first hit, so an exact path always beats a stripped basename.
    """
    keys: list[str] = []

    def add(key: str | None) -> None:
        if key and key not in keys:
            keys.append(key)

    add(path_of(source_url))
    add(f"/wp-content/uploads/{file_path}" if file_path else None)

    basename = posixpath.basename(path_of(source_url) or file_path or "")
    if not basename:
        return keys
    add(basename)

    stem, dot, ext = basename.rpartition(".")
    if not dot:
        return keys

    stripped = SIZE_SUFFIX_RE.sub("", stem)
    add(f"{stripped}.{ext}")
    add(f"{DUP_SUFFIX_RE.sub('', stripped)}.{ext}")
    return keys


def project(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten one REST attachment into the migration's manifest shape.

    Field names follow ``jakarta/content/extracted/attachments.jsonl`` so the
    two sources are directly comparable, with the live-only additions
    (``source_url``, ``sizes``, ``filesize``, ``match_keys``) appended.
    """
    details = record.get("media_details") or {}
    image_meta = details.get("image_meta") or {}
    source_url = record.get("source_url") or _rendered(record.get("guid"))
    file_path = details.get("file")

    sizes = []
    for name, size in (details.get("sizes") or {}).items():
        sizes.append(
            {
                "name": name,
                "file": size.get("file"),
                "width": size.get("width"),
                "height": size.get("height"),
                "mime": size.get("mime_type"),
                "source_url": size.get("source_url"),
                "filesize": size.get("filesize"),
            }
        )
    sizes.sort(key=lambda s: (s["name"] or ""))

    return {
        "wp_id": record.get("id"),
        # source_url is the download URL. guid is kept only as evidence, never
        # as a fetch target: F11 found it wrong for ~20% of Jakarta's
        # attachments (it points at a different host entirely).
        "url": source_url,
        "source_url": source_url,
        "guid": _rendered(record.get("guid")),
        "file": file_path,
        "path": path_of(source_url),
        "filename": record.get("filename") or posixpath.basename(file_path or ""),
        "mime": record.get("mime_type"),
        "media_type": record.get("media_type"),
        "title": _rendered(record.get("title")),
        "slug": record.get("slug"),
        "alt": (record.get("alt_text") or "").strip() or None,
        "caption": _rendered(record.get("caption")),
        "credit": (image_meta.get("credit") or "").strip() or None,
        "copyright": (image_meta.get("copyright") or "").strip() or None,
        "width": details.get("width"),
        "height": details.get("height"),
        "filesize": record.get("filesize") or details.get("filesize"),
        "parent_post_id": record.get("post") or None,
        "author_wp_id": record.get("author") or None,
        "date": record.get("date"),
        "date_gmt": record.get("date_gmt"),
        "modified_gmt": record.get("modified_gmt"),
        "sizes": sizes,
        "match_keys": match_keys(source_url, file_path),
    }

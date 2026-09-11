"""`media` <- `attachments.jsonl` (E1.1 contract: wp_id, url, guid, file,
mime, title, alt, credit, width, height, parent_post_id, date).

**F11 compliance:** uses `url` (already reconstructed from
`_wp_attached_file` by wp-extract), never `guid` — `guid` is wrong for
~20% of rows per ARCHITECTURE.md §6 / PROGRESS.md F11.

**E1.3 has not run** (blocked on the uploads archive) — `media.url` is
loaded pointing at the *original* `nowjakarta.co.id` WordPress URL. See
this ticket's final report for the exact rewrite recipe once Garage
migration lands.

**Idempotency key: `filename` (unique-indexed), computed as
`f"{wp_id}-{basename(file)}"`.** Two independent reasons this loader does
not use the bare basename:

  1. Collision: 164 of 13,817 attachments (355 rows) share a basename
     across different upload-date directories (e.g. two different
     "Picture1.jpg" from different months) — a bare-basename `filename`
     would violate `media_filename_idx UNIQUE` on the second insert.
  2. Even the full relative `file` path (`"2022/07/x.jpg"`) still has 17
     residual collisions (42 rows) — apparent genuine duplicate WP media
     library entries for the same physical file.

Prefixing with `wp_id` (verified unique across all 13,817 attachments)
guarantees uniqueness *and* keeps the mapping obviously traceable back to
the source row, and is fully deterministic across runs (same wp_id -> same
filename every time), which is what idempotency requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.sources import iter_jsonl
from now_loader.textutil import basename, strip_tags_light

_UPSERT = text(
    """
    INSERT INTO "public"."media"
        (alt, credit, url, filename, mime_type, width, height, updated_at, created_at)
    VALUES
        (:alt, :credit, :url, :filename, :mime_type, :width, :height, now(), now())
    ON CONFLICT (filename) DO UPDATE
       SET alt = EXCLUDED.alt,
           credit = EXCLUDED.credit,
           url = EXCLUDED.url,
           mime_type = EXCLUDED.mime_type,
           width = EXCLUDED.width,
           height = EXCLUDED.height,
           updated_at = now()
    RETURNING id
    """
)


@dataclass
class MediaLoadResult:
    read: int = 0
    inserted_or_updated: int = 0
    alt_from_alt: int = 0
    alt_from_title: int = 0
    alt_fallback_empty: int = 0
    wp_id_to_media_id: dict[int, int] = field(default_factory=dict)
    wp_id_to_original_url: dict[int, str] = field(default_factory=dict)


def load_media(conn: Connection, attachments_path: Path) -> MediaLoadResult:
    result = MediaLoadResult()

    for row in iter_jsonl(attachments_path):
        result.read += 1
        wp_id = row["wp_id"]
        file_rel = row.get("file") or ""
        base = basename(file_rel or row.get("url") or f"wp-{wp_id}")
        filename = f"{wp_id}-{base}"

        alt = strip_tags_light(row.get("alt"))
        if alt:
            result.alt_from_alt += 1
        else:
            alt = strip_tags_light(row.get("title"))
            if alt:
                result.alt_from_title += 1
            else:
                alt = ""  # media.alt is NOT NULL; no signal at all for ~4/13,817 rows
                result.alt_fallback_empty += 1

        media_id = conn.execute(
            _UPSERT,
            {
                "alt": alt,
                "credit": strip_tags_light(row.get("credit")),
                "url": row.get("url"),  # original WP URL — see module docstring
                "filename": filename,
                "mime_type": row.get("mime"),
                "width": row.get("width"),
                "height": row.get("height"),
            },
        ).scalar_one()

        result.wp_id_to_media_id[wp_id] = media_id
        if row.get("url"):
            result.wp_id_to_original_url[wp_id] = row["url"]
        result.inserted_or_updated += 1

    return result

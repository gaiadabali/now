"""`authors` <- `users.jsonl` (E1.1 contract: wp_id, login, nicename,
display_name, email, url, registered, published_post_count).

Idempotency key: **`slug`, not `legacy_wp_user_id`.**

This ticket's brief states "`authors.legacyWpUserId` is unique-indexed —
use it as an idempotency key" (mirroring ARCHITECTURE.md's framing of
`articles.legacyWpId`). That is true for articles but NOT for authors as
actually shipped by E1.6: `\\d authors` on a live `now_jakarta` shows

    "authors_legacy_wp_user_id_idx" btree (legacy_wp_user_id)   -- NOT unique
    "authors_slug_idx" UNIQUE btree (slug)

(confirmed against the real migration SQL,
`engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts`,
which only marks `articles_legacy_wp_id_idx` and `media_filename_idx` and
`places_slug_idx` etc. as `UNIQUE` — `authors_legacy_wp_user_id_idx` is a
plain index). `ON CONFLICT (legacy_wp_user_id)` is rejected by Postgres for
a non-unique column, so this loader upserts on `slug` instead — WP
nicenames are already unique per user, so `slug` is a safe, equivalent
natural key, and `legacy_wp_user_id` is still written and still useful for
lookups; it just isn't the constraint the upsert hangs off. See the final
report's "contradicts ticket brief" note.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.sources import iter_jsonl
from now_loader.textutil import slugify

_UPSERT = text(
    """
    INSERT INTO "public"."authors" (name, slug, legacy_wp_user_id, updated_at, created_at)
    VALUES (:name, :slug, :legacy_wp_user_id, now(), now())
    ON CONFLICT (slug) DO UPDATE
       SET name = EXCLUDED.name,
           legacy_wp_user_id = EXCLUDED.legacy_wp_user_id,
           updated_at = now()
    RETURNING id
    """
)


@dataclass
class AuthorsLoadResult:
    read: int = 0
    inserted_or_updated: int = 0
    skipped_no_slug: int = 0
    wp_id_to_author_id: dict[int, int] | None = None


def load_authors(conn: Connection, users_path: Path) -> AuthorsLoadResult:
    result = AuthorsLoadResult(wp_id_to_author_id={})
    used_slugs: dict[str, int] = {}  # slug -> wp_id that claimed it, for dedupe reporting

    for row in iter_jsonl(users_path):
        result.read += 1
        wp_id = row["wp_id"]
        base_slug = slugify(row.get("nicename") or row.get("login") or f"user-{wp_id}")
        if not base_slug:
            result.skipped_no_slug += 1
            continue

        slug = base_slug
        if slug in used_slugs and used_slugs[slug] != wp_id:
            # Extremely unlikely (WP nicenames are already unique) but
            # slugify() could theoretically collapse two distinct
            # nicenames onto the same ASCII slug — stay deterministic
            # rather than silently overwriting one author with another.
            slug = f"{base_slug}-{wp_id}"
        used_slugs[slug] = wp_id

        name = row.get("display_name") or row.get("login") or slug

        author_id = conn.execute(
            _UPSERT,
            {"name": name, "slug": slug, "legacy_wp_user_id": wp_id},
        ).scalar_one()

        result.wp_id_to_author_id[wp_id] = author_id
        result.inserted_or_updated += 1

    return result

"""`events` <- `events.jsonl` (E1.1 contract: 837 rows, two legacy WP post
types — 347 `tribe_events`, 490 `upcoming-events`).

**F32 — editorial content backfill.** F28 added `title, dek, body_blocks,
hero_media_id, article_id, legacy_wp_id` to `events` (ARCHITECTURE.md §5).
E1.8 could only write the five business columns that existed at the time
(`place_id, starts_at, ends_at, rrule, ticket_url`), so all 837 rows still
carried `title='Untitled event'` and NULL content until this ran. Mapping
(exactly as F28 specified — this loader does not re-litigate it):

    wp_id         -> legacy_wp_id   (now unique-indexed)
    title         -> title          direct copy
    excerpt       -> dek            `strip_tags_light`, NULL if empty
    content_html  -> body_blocks    `now_content_clean.clean_article`, same
                                     cleaner articles use, invoked directly
                                     on the event row (it only needs
                                     `wp_id`/`content_html`, both present)
    thumbnail_id  -> hero_media_id  via `load_media`'s `wp_id_to_media_id`
    (nothing)     -> article_id     NEVER populated — see F28/ARCHITECTURE.md
                                     §5: editorial-only, would create a
                                     second source of truth for the same
                                     content this loader already writes.

`place_id`, `starts_at`, `ends_at`, `_status` are **left untouched** by the
backfill path — those are E1.8/F26 decisions (508 undated events forced to
`_status='draft'` so a published-but-dateless event can't defeat the
§8.A expiry filter) and this ticket does not revisit them. They are only
ever computed here for a genuinely new row (one this loader has never seen
before), on the INSERT branch below.

**Two write paths, exactly per the F32 ticket:**

1. **Backfill UPDATE, keyed by the existing SQLite ledger** (`(city, wp_id)
   -> events.id`, see `now_loader.ledger`). All 837 rows were inserted by
   E1.8 with `legacy_wp_id` still NULL, so the ledger — not the column —
   is the only way to find them on this first run. Only the content
   columns are SET; place/dates/status are never touched on this path.
2. **Upsert on `legacy_wp_id`**, same `ON CONFLICT ... DO UPDATE` pattern
   `load_articles.py` already uses, for any row with no ledger entry (a
   genuinely new wp_id, or a re-run after the ledger file has been deleted
   now that `legacy_wp_id` carries the key). This is the only path that
   computes `place_id`/`starts_at`/`ends_at`/`_status`, and only for the
   INSERT case — the `DO UPDATE` clause still touches content columns
   only.

**The ledger can be retired once this has run once**: after it, every one
of the 837 rows has `legacy_wp_id` populated (unique-indexed), so path 2
alone is sufficient for all future runs — the code already prefers path 1
only when the ledger *has* an entry, so deleting
`engine/packages/loader/state/<city>.sqlite3` is safe and simply routes
every row through path 2 from then on. Final report says explicitly
whether this was verified.

**F12 (undated events) and the venue-link logic are unchanged from E1.8**
and only exercised by the path-2 INSERT branch — see the original
docstring text preserved below for that decision's rationale.

**F12 — 490 `upcoming-events` (+18 `tribe_events`) have no occurrence
date, only a publish date (`date`), which is not the same thing.** Decision
(explicitly authorized by the ticket to make and state, same as the
undated-events call): load them anyway — content and any place link is
still real and worth keeping — with `starts_at = ends_at = NULL` (the
column is nullable; no date is invented) and **`_status` forced to
`'draft'` regardless of the source WP `status`**, because a "published"
event that can never resolve `ends_at` would silently break the
event-expiry hard filter (ARCHITECTURE.md §8.A: `ends_at < now()`) and any
calendar/listing UI that assumes a published event has a date. Find them
with `SELECT id FROM events WHERE starts_at IS NULL`.

`place_id` is resolved via `venue_id` against the `wp_id -> place_id` map
`load_places` returns; 285/837 events carry a `venue_id` and all 285
resolve (100% match against `venues.jsonl` — verified before writing this
loader). `rrule` and `ticket_url` have no source field at all (not in the
E1.1 `events.jsonl` contract) and are always NULL.

**Titles with no source value (4/837, all blank-title `tribe_events`
drafts — wp_id 34992/39446/46279/47089):** left NULL, not defaulted back
to the placeholder string and not invented. `'Untitled event'` was the
schema's *default*, not real content; the acceptance bar is "zero
`'Untitled event'` remaining", not "zero NULL titles" — inventing prose for
these 4 would violate the ticket's explicit "report the count rather than
inventing placeholder prose" instruction. Counted in
`EventsLoadResult.blank_title`.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from now_content_clean import clean_article
from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_loader.ledger import EventLedger
from now_loader.sources import iter_jsonl
from now_loader.textutil import strip_tags_light

# Path 2 — upsert on legacy_wp_id (articles pattern). Only exercised for a
# genuinely new row (INSERT branch) or once the ledger no longer has an
# entry for a wp_id it already knows about (retirement path). The DO UPDATE
# branch deliberately does not touch place_id/starts_at/ends_at/_status.
_UPSERT = text(
    """
    INSERT INTO "public"."events"
        (place_id, starts_at, ends_at, _status, title, dek, body_blocks, hero_media_id,
         legacy_wp_id, updated_at, created_at)
    VALUES
        (:place_id, :starts_at, :ends_at, :status, :title, :dek, CAST(:body_blocks AS jsonb), :hero_media_id,
         :legacy_wp_id, now(), now())
    ON CONFLICT (legacy_wp_id) DO UPDATE
       SET title = EXCLUDED.title,
           dek = EXCLUDED.dek,
           body_blocks = EXCLUDED.body_blocks,
           hero_media_id = EXCLUDED.hero_media_id,
           updated_at = now()
    RETURNING id
    """
)

# Path 1 — first-pass backfill, keyed by the SQLite ledger's (wp_id) ->
# events.id mapping from the original E1.8 insert. Content columns only.
_BACKFILL_UPDATE = text(
    """
    UPDATE "public"."events"
       SET title = :title,
           dek = :dek,
           body_blocks = CAST(:body_blocks AS jsonb),
           hero_media_id = :hero_media_id,
           legacy_wp_id = :legacy_wp_id,
           updated_at = now()
     WHERE id = :id
    RETURNING id
    """
)


@dataclass
class EventsLoadResult:
    read: int = 0
    inserted: int = 0
    updated: int = 0
    undated_forced_draft: int = 0
    place_linked: int = 0
    place_unresolved_venue_id: int = 0
    no_venue_id: int = 0
    missing_body: int = 0
    missing_hero_media: int = 0
    dek_from_excerpt: int = 0
    dek_missing: int = 0
    blank_title: int = 0
    content_loss_median: float | None = None
    content_loss_p95: float | None = None
    content_loss_max: float | None = None
    words_lost_total: int = 0
    words_gained_total: int = 0


def _dek_for(row: dict, result: EventsLoadResult) -> str | None:
    dek = strip_tags_light(row.get("excerpt"))
    if dek:
        result.dek_from_excerpt += 1
        return dek
    result.dek_missing += 1
    return None


def load_events(
    conn: Connection,
    events_path: Path,
    venue_wp_id_to_place_id: dict[int, int],
    media_wp_id_to_media_id: dict[int, int],
    ledger: EventLedger,
) -> EventsLoadResult:
    result = EventsLoadResult()
    loss_pcts: list[float] = []

    for row in iter_jsonl(events_path):
        result.read += 1
        wp_id = row["wp_id"]

        title = row.get("title") or None
        if not title:
            result.blank_title += 1

        dek = _dek_for(row, result)

        content_html = row.get("content_html") or ""
        if not content_html:
            result.missing_body += 1

        # Same cleaner articles use, invoked directly — clean_article only
        # needs wp_id/content_html, both present on an event row.
        clean = clean_article(row)
        loss = clean.stats.get("content_loss") or {}
        if loss.get("chars_in", 0) > 0:
            loss_pcts.append(loss.get("loss_pct", 0.0))
            word_delta = loss.get("word_delta", {})
            result.words_lost_total += word_delta.get("words_lost", 0)
            result.words_gained_total += word_delta.get("words_gained", 0)
        body_blocks_json = json.dumps(clean.blocks, ensure_ascii=False)

        thumbnail_id = row.get("thumbnail_id")
        hero_media_id = media_wp_id_to_media_id.get(thumbnail_id) if thumbnail_id else None
        if thumbnail_id and hero_media_id is None:
            result.missing_hero_media += 1

        content_params = {
            "title": title,
            "dek": dek,
            "body_blocks": body_blocks_json,
            "hero_media_id": hero_media_id,
            "legacy_wp_id": wp_id,
        }

        existing_id = ledger.get(wp_id)
        if existing_id is not None:
            conn.execute(_BACKFILL_UPDATE, {**content_params, "id": existing_id})
            result.updated += 1
            continue

        # No ledger entry — either a wp_id never loaded before, or the
        # ledger has been retired now that legacy_wp_id carries the key.
        # Only this branch derives place_id/starts_at/ends_at/_status,
        # exactly as E1.8/F26 originally did, and only for a real INSERT.
        venue_id = row.get("venue_id")
        place_id = None
        if venue_id:
            place_id = venue_wp_id_to_place_id.get(venue_id)
            if place_id is not None:
                result.place_linked += 1
            else:
                result.place_unresolved_venue_id += 1
        else:
            result.no_venue_id += 1

        starts_at = row.get("start_date")
        ends_at = row.get("end_date")
        undated = not starts_at
        if undated:
            result.undated_forced_draft += 1
        status = "draft" if undated else ("published" if row.get("status") == "publish" else "draft")

        new_id = conn.execute(
            _UPSERT,
            {
                **content_params,
                "place_id": place_id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "status": status,
            },
        ).scalar_one()
        ledger.record(wp_id, new_id)
        result.inserted += 1

    if loss_pcts:
        result.content_loss_median = round(statistics.median(loss_pcts), 3)
        result.content_loss_p95 = round(sorted(loss_pcts)[int(len(loss_pcts) * 0.95)], 3)
        result.content_loss_max = round(max(loss_pcts), 3)

    return result

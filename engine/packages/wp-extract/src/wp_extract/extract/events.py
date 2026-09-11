from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.extract.common import fetch_postmeta, fetch_posts, fetch_term_names_by_object
from wp_extract.jsonl import iso

# tribe_events (Events Calendar Pro) and upcoming-events (an older/simpler
# plugin) use *different* taxonomies for "category" — verified against the
# restored DB: tribe_events -> tribe_events_cat + post_tag;
# upcoming-events -> event_category + event-tag. Neither is the regular
# `category` taxonomy used by articles.
TRIBE_EVENT_META_KEYS = [
    "_EventStartDate",
    "_EventEndDate",
    "_EventStartDateUTC",
    "_EventEndDateUTC",
    "_EventAllDay",
    "_EventVenueID",
    "_EventOrganizerID",
    "_EventCost",
    "_EventCurrencySymbol",
    "_EventURL",
    "_thumbnail_id",
    "_yoast_wpseo_metadesc",
]


def extract_events(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # ARCHITECTURE.md's counts for these post types (490 / 347) are raw
    # post_type totals, not publish-only — matched here across all
    # statuses; each row carries its own `status` field for downstream
    # filtering.
    tribe_posts = fetch_posts(conn, "tribe_events", status=None)
    upcoming_posts = fetch_posts(conn, "upcoming-events", status=None)

    tribe_categories = fetch_term_names_by_object(conn, "tribe_events_cat")
    upcoming_categories = fetch_term_names_by_object(conn, "event_category")
    meta_by_post = fetch_postmeta(conn, TRIBE_EVENT_META_KEYS)

    organizer_titles = {
        p["ID"]: p["post_title"] for p in fetch_posts(conn, "tribe_organizer", status=None)
    }

    rows: list[dict[str, Any]] = []
    with_dates = 0

    for p in tribe_posts:
        pid = p["ID"]
        meta = meta_by_post.get(pid, {})
        thumb = meta.get("_thumbnail_id")
        organizer_id = meta.get("_EventOrganizerID")
        organizer_id = int(organizer_id) if organizer_id not in (None, "", "0") else None
        start = iso(meta.get("_EventStartDate"))
        end = iso(meta.get("_EventEndDate"))
        if start:
            with_dates += 1
        rows.append(
            {
                "wp_id": pid,
                "type": "tribe_events",
                "status": p["post_status"],
                "title": p["post_title"],
                "slug": p["post_name"],
                "content_html": p["post_content"],
                "excerpt": p["post_excerpt"],
                "start_date": start,
                "end_date": end,
                "all_day": meta.get("_EventAllDay") == "yes",
                "venue_id": int(meta["_EventVenueID"]) if meta.get("_EventVenueID") not in (None, "", "0") else None,
                "organizer_id": organizer_id,
                "organizer_name": organizer_titles.get(organizer_id) if organizer_id else None,
                "cost": meta.get("_EventCost") or None,
                "currency": meta.get("_EventCurrencySymbol") or None,
                "categories": tribe_categories.get(pid, []),
                "thumbnail_id": int(thumb) if thumb not in (None, "") else None,
                "date": iso(p["post_date"]),
                "modified": iso(p["post_modified"]),
            }
        )

    for p in upcoming_posts:
        pid = p["ID"]
        meta = meta_by_post.get(pid, {})
        thumb = meta.get("_thumbnail_id")
        # This plugin stores no structured start/end date at all — verified
        # (only _thumbnail_id present in postmeta for a representative
        # sample). post_date (publish date) is the only temporal signal
        # available; it is NOT the event's occurrence date. Flagged in the
        # extraction report as a known data gap, per ARCHITECTURE.md's
        # instruction to explain rather than swallow discrepancies.
        rows.append(
            {
                "wp_id": pid,
                "type": "upcoming-events",
                "status": p["post_status"],
                "title": p["post_title"],
                "slug": p["post_name"],
                "content_html": p["post_content"],
                "excerpt": p["post_excerpt"],
                "start_date": None,
                "end_date": None,
                "all_day": None,
                "venue_id": None,
                "organizer_id": None,
                "organizer_name": None,
                "cost": None,
                "currency": None,
                "categories": upcoming_categories.get(pid, []),
                "thumbnail_id": int(thumb) if thumb not in (None, "") else None,
                "date": iso(p["post_date"]),
                "modified": iso(p["post_modified"]),
            }
        )

    stats = {
        "tribe_events_in": len(tribe_posts),
        "upcoming_events_in": len(upcoming_posts),
        "events_out": len(rows),
        "tribe_events_with_start_date": with_dates,
        "upcoming_events_with_structured_date": 0,
    }
    return rows, stats

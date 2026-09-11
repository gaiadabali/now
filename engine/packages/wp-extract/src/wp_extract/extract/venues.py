from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.extract.common import fetch_postmeta, fetch_posts
from wp_extract.jsonl import iso

VENUE_META_KEYS = [
    "_VenueVenue",
    "_VenueAddress",
    "_VenueCity",
    "_VenueState",
    "_VenueProvince",
    "_VenueStateProvince",
    "_VenueZip",
    "_VenueCountry",
    "_VenuePhone",
    "_VenueURL",
    "_thumbnail_id",
]


def extract_venues(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    posts = fetch_posts(conn, "tribe_venue", status=None)
    meta_by_post = fetch_postmeta(conn, VENUE_META_KEYS)

    with_address = 0
    rows: list[dict[str, Any]] = []
    for p in posts:
        pid = p["ID"]
        meta = meta_by_post.get(pid, {})
        address = meta.get("_VenueAddress") or None
        if address:
            with_address += 1
        thumb = meta.get("_thumbnail_id")
        rows.append(
            {
                "wp_id": pid,
                "type": "tribe_venue",
                "status": p["post_status"],
                "name": meta.get("_VenueVenue") or p["post_title"],
                "slug": p["post_name"],
                "address": address,
                "city": meta.get("_VenueCity") or None,
                "state": meta.get("_VenueState") or meta.get("_VenueStateProvince") or None,
                "province": meta.get("_VenueProvince") or None,
                "zip": meta.get("_VenueZip") or None,
                "country": meta.get("_VenueCountry") or None,
                "phone": meta.get("_VenuePhone") or None,
                "url": meta.get("_VenueURL") or None,
                "thumbnail_id": int(thumb) if thumb not in (None, "") else None,
                "date": iso(p["post_date"]),
            }
        )

    stats = {
        "venues_in": len(posts),
        "venues_out": len(rows),
        "with_street_address": with_address,
        "address_coverage_pct": round(100 * with_address / len(rows), 1) if rows else 0.0,
    }
    return rows, stats

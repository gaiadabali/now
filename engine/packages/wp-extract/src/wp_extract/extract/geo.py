from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.config import TABLE_PREFIX
from wp_extract.db import query
from wp_extract.phpunserialize import extract_lat_lng, php_unserialize

P = TABLE_PREFIX


def extract_geo(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # --- MapPress: nb15_mappress_maps.obj is a serialized Mappress_Map with
    # a center {lat,lng} and a `pois` array, each poi itself a serialized
    # Mappress_Poi with its own {lat,lng}. nb15_mappress_posts links
    # mapid -> the WordPress post that embeds the map.
    maps_raw = query(conn, f"SELECT mapid, obj FROM {P}mappress_maps ORDER BY mapid")
    map_to_posts: dict[int, list[int]] = {}
    for r in query(conn, f"SELECT postid, mapid FROM {P}mappress_posts"):
        map_to_posts.setdefault(r["mapid"], []).append(r["postid"])

    mappress_maps_total = len(maps_raw)
    mappress_maps_deserialized = 0
    mappress_pois_with_coords = 0

    for m in maps_raw:
        obj = php_unserialize(m["obj"])
        if not isinstance(obj, dict):
            continue
        mappress_maps_deserialized += 1
        post_ids = map_to_posts.get(m["mapid"], [None])

        center = extract_lat_lng(obj.get("center"))
        map_title = obj.get("title")

        pois = obj.get("pois") or []
        if isinstance(pois, dict):
            pois = list(pois.values())

        if not pois:
            # No POIs — fall back to the map's own center point.
            if center:
                mappress_pois_with_coords += 1
            for post_id in post_ids:
                rows.append(
                    {
                        "source": "mappress",
                        "wp_id": post_id,
                        "map_id": m["mapid"],
                        "poi_index": None,
                        "title": map_title,
                        "address": None,
                        "lat": center[0] if center else None,
                        "lng": center[1] if center else None,
                    }
                )
            continue

        for i, poi in enumerate(pois):
            if not isinstance(poi, dict):
                continue
            point = extract_lat_lng(poi.get("point")) or center
            if point:
                mappress_pois_with_coords += 1
            for post_id in post_ids:
                rows.append(
                    {
                        "source": "mappress",
                        "wp_id": post_id,
                        "map_id": m["mapid"],
                        "poi_index": i,
                        "title": poi.get("title") or map_title,
                        "address": poi.get("address") or poi.get("correctedAddress"),
                        "lat": point[0] if point else None,
                        "lng": point[1] if point else None,
                    }
                )

    # --- ACF `google_map` postmeta: serialized associative array with
    # address/lat/lng/place_id directly (no wrapper class, unlike MapPress).
    google_map_rows = query(
        conn,
        f"SELECT post_id, meta_value FROM {P}postmeta WHERE meta_key = 'google_map'",
    )
    google_map_total = len(google_map_rows)
    google_map_populated = 0
    google_map_deserialized = 0

    for r in google_map_rows:
        if not r["meta_value"]:
            continue
        google_map_populated += 1
        obj = php_unserialize(r["meta_value"])
        if not isinstance(obj, dict):
            continue
        google_map_deserialized += 1
        latlng = extract_lat_lng(obj)
        rows.append(
            {
                "source": "google_map",
                "wp_id": r["post_id"],
                "map_id": None,
                "poi_index": None,
                "title": obj.get("name"),
                "address": obj.get("address"),
                "lat": latlng[0] if latlng else None,
                "lng": latlng[1] if latlng else None,
                "place_id": obj.get("place_id"),
            }
        )

    stats = {
        "mappress_maps_total": mappress_maps_total,
        "mappress_maps_deserialized_ok": mappress_maps_deserialized,
        "mappress_pois_with_coords": mappress_pois_with_coords,
        "google_map_postmeta_total": google_map_total,
        "google_map_populated": google_map_populated,
        "google_map_deserialized_ok": google_map_deserialized,
        "geo_rows_out": len(rows),
    }
    return rows, stats

"""Deserialize PHP `serialize()` payloads (ACF google_map fields, MapPress
`Mappress_Map`/`Mappress_Poi` objects) into plain JSON-able Python values.

This is the piece that makes geo.jsonl possible per the frozen contract
("MapPress serialised-PHP coordinates deserialised into usable lat/lng").
"""

from __future__ import annotations

from typing import Any

import phpserialize


def _to_plain(value: Any) -> Any:
    """Recursively convert phpobject/dict/list PHP values to plain JSON types."""
    if isinstance(value, phpserialize.phpobject):
        fields = {k: _to_plain(v) for k, v in value._asdict().items()}
        return {"__php_class__": value.__name__, **fields}
    if isinstance(value, dict):
        # PHP associative arrays decode as dict keyed by int or str. A dict
        # with purely consecutive int keys starting at 0 is really a list.
        keys = list(value.keys())
        if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(len(keys))):
            return [_to_plain(value[k]) for k in range(len(keys))]
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def php_unserialize(raw: str | bytes | None) -> Any | None:
    """Best-effort PHP unserialize -> plain Python. Returns None on empty/invalid input."""
    if raw is None:
        return None
    if isinstance(raw, str):
        if raw == "":
            return None
        data = raw.encode("utf-8")
    else:
        data = raw
    try:
        return _to_plain(
            phpserialize.loads(data, decode_strings=True, object_hook=phpserialize.phpobject)
        )
    except Exception:
        return None


def extract_lat_lng(obj: Any) -> tuple[float, float] | None:
    """Pull a (lat, lng) pair out of a deserialized ACF google_map value or
    a MapPress center/point dict. Returns None if not found/not numeric.
    """
    if not isinstance(obj, dict):
        return None
    lat, lng = obj.get("lat"), obj.get("lng")
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None

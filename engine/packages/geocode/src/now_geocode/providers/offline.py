"""Offline / dry-run provider — no network, no API key, fully
deterministic. Exists so the whole ladder (rungs 2 and 3, the quality
gates, area assignment, dedup, and the report) can be exercised and
tested end to end in an environment with **no Google API key**, per the
task's "no API key required to build this" requirement.

**This provider never contributes to the real `geocoded_places.jsonl`
deliverable.** Every `ProviderResult` it returns has `is_synthetic=True`,
and `pipeline.run(..., allow_synthetic=False)` (the default) turns any
synthetic result into `Status.UNRESOLVED` before it's written out —
see `pipeline.py`. The CLI's `build` command refuses `--provider offline`
outright unless `--dry-run` is also passed, and `--dry-run` forces the
output filename to contain "dryrun" so a synthetic run can never
overwrite the real deliverable by accident (see `cli.py`).

The synthetic point is a deterministic hash-based jitter (~0-5km) around
whichever of Jakarta/Bali/Indonesia the input text mentions, *not* a
lookup of the real place — it is exercise data, not a guess at the truth.
"""

from __future__ import annotations

import hashlib
import math

from now_geocode.models import ProviderResult
from now_geocode.textnorm import normalize_name

_JAKARTA = (-6.2088, 106.8456)
_BALI = (-8.4095, 115.1889)
_INDONESIA = (-2.5, 118.0)


def _seeded_jitter(basis: str, *, spread_km: float = 5.0) -> tuple[float, float]:
    digest = hashlib.sha256(basis.encode("utf-8")).digest()
    # Two independent [0,1) floats from the digest, deterministic per input.
    u1 = int.from_bytes(digest[:8], "big") / 2**64
    u2 = int.from_bytes(digest[8:16], "big") / 2**64
    angle = u1 * 2 * math.pi
    radius_km = u2 * spread_km
    dlat = (radius_km * math.cos(angle)) / 111.0
    dlng = (radius_km * math.sin(angle)) / (111.0 * math.cos(math.radians(-6.5)))
    return dlat, dlng


def _base_point(text: str) -> tuple[float, float]:
    norm = normalize_name(text)
    if "bali" in norm:
        return _BALI
    if "jakarta" in norm:
        return _JAKARTA
    return _INDONESIA


class OfflineProvider:
    name = "offline"

    def geocode_address(self, address: str) -> ProviderResult | None:
        if not address or not address.strip():
            return None
        base_lat, base_lng = _base_point(address)
        dlat, dlng = _seeded_jitter(f"address:{normalize_name(address)}")
        return ProviderResult(
            lat=base_lat + dlat,
            lng=base_lng + dlng,
            formatted_address=address,
            google_place_id=None,
            location_type="offline_stub_address",
            confidence=0.42,
            provider=self.name,
            is_synthetic=True,
            raw={"basis": "address", "input": address},
        )

    def find_place(self, name: str, context: str | None) -> ProviderResult | None:
        if not name or not name.strip():
            return None
        basis_text = f"{name} {context or ''}"
        base_lat, base_lng = _base_point(basis_text)
        dlat, dlng = _seeded_jitter(f"name:{normalize_name(basis_text)}", spread_km=8.0)
        return ProviderResult(
            lat=base_lat + dlat,
            lng=base_lng + dlng,
            formatted_address=None,
            google_place_id=None,
            location_type="offline_stub_place_search",
            confidence=0.3,
            provider=self.name,
            is_synthetic=True,
            raw={"basis": "name", "input": name, "context": context},
        )

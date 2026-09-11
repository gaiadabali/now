"""Throwaway QA verification script for Wave 4 claim E2.5 (geocoding pipeline).
Read-only: inspects jakarta/content/extracted/geocoded_places.jsonl.
Does not modify product code or the deliverable.
"""
import json
import sys
from pathlib import Path
from collections import Counter

PATH = Path(__file__).resolve().parents[3] / "jakarta" / "content" / "extracted" / "geocoded_places.jsonl"

def main():
    rows = []
    with PATH.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rows.append((i, json.loads(line)))

    total = len(rows)
    print(f"file: {PATH}")
    print(f"total rows: {total}")

    status_counts = Counter(r.get("status") for _, r in rows)
    print("status counts:", dict(status_counts))

    source_counts = Counter(r.get("source") for _, r in rows)
    print("source(rung) counts:", dict(source_counts))

    # area_term coverage
    missing_area = [(i, r["place_key"], r.get("area_term")) for i, r in rows
                    if not r.get("area_term")]
    print(f"rows missing area_term (null/missing/empty): {len(missing_area)} / {total}")
    for i, key, at in missing_area[:20]:
        print(f"  line {i} place_key={key} area_term={at!r}")

    # UNRESOLVED must have lat=null AND lng=null
    bad_unresolved = [(i, r) for i, r in rows
                       if r.get("status") == "unresolved" and (r.get("lat") is not None or r.get("lng") is not None)]
    print(f"UNRESOLVED rows with non-null lat/lng (should be 0): {len(bad_unresolved)}")
    for i, r in bad_unresolved[:10]:
        print(f"  line {i}: {json.dumps(r)}")

    # resolved_synthetic must never appear in the real deliverable
    synthetic_rows = [(i, r) for i, r in rows if r.get("status") == "resolved_synthetic"]
    print(f"resolved_synthetic rows in real deliverable (should be 0): {len(synthetic_rows)}")
    for i, r in synthetic_rows[:10]:
        print(f"  line {i}: {json.dumps(r)}")

    # location_type mentioning offline stub anywhere
    offline_loctype = [(i, r) for i, r in rows if r.get("location_type") and "offline" in str(r.get("location_type"))]
    print(f"rows with offline-stub location_type (should be 0): {len(offline_loctype)}")
    for i, r in offline_loctype[:10]:
        print(f"  line {i}: {json.dumps(r)}")

    # Non-null lat/lng rows -> inspect provenance (source/status/location_type)
    resolved_rows = [(i, r) for i, r in rows if r.get("lat") is not None or r.get("lng") is not None]
    print(f"\nrows with non-null lat/lng: {len(resolved_rows)}")
    prov_counter = Counter((r.get("status"), r.get("source"), r.get("location_type")) for _, r in resolved_rows)
    for k, v in prov_counter.items():
        print(f"  {k}: {v}")

    # sanity: any row where lat is null but lng isn't, or vice versa (partial nulls -- schema violation on its own)
    partial_null = [(i, r) for i, r in rows if (r.get("lat") is None) != (r.get("lng") is None)]
    print(f"\nrows with partial null lat/lng (inconsistent pair): {len(partial_null)}")
    for i, r in partial_null[:10]:
        print(f"  line {i}: {json.dumps(r)}")

if __name__ == "__main__":
    main()

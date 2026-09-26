"""Regenerate tests/fixtures/junk_golden.jsonl from the Python rules.

Run after ANY change to src/now_places/junk.py, then run both suites:
the Python tests (which must still pass) and engine/apps/web's
`npm test` (whose TypeScript port must be updated to match):

    uv run python scripts/build_junk_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

from now_places.junk import classify

HERE = Path(__file__).resolve().parent
FIX = HERE.parent / "tests" / "fixtures"
SOURCES = [
    "junk_hand_labeled_100.jsonl",
    "junk_heldout_jakarta_100.jsonl",
    "junk_blind_bali_100.jsonl",
    "junk_blind_jakarta_100.jsonl",
]
# Probes for rule edges the fixtures do not cover.
PROBES = [
    "", "   ", "Hotel's", "Their Spa and Lunch", "Its Relish Bistro", "Nyanyi Beach's", "TS Suites",
    "Best Western Premier", "Holiday Inn Express", "Festival Walk", "Bali Festival Park", "1945 Restaurant",
    "1945 Restaurant at Fairmont", "2013 Serpentine Gallery Pavilion", "1971 at Pike Place Market Seattle",
    "World Trade Centre", "New Kuta Golf Course", "New Thai Restaurant", "Moon Rabbit Liquor Bar & Dim Sum",
    "Champagne Bar by Moet & Chandon", "Mesa Hotel and Resorts", "Art Gallery of New South Wales",
    "Temple Dances of Bali", "Hotel Santika Premiere", "International Conference Center Bali",
    "Mason Elephant Park and Lodge Desa Taro", "Bumbu Bali Restaurant & Cooking School", "After Seven Restaurant",
    "The Kitchen Cook Off", "Resort Credit of IDR 600,000", "Three Days Bike Retreat", "10pm at the Rooftop",
    "Dahana Restaurant Level 2", "Bali's Leading Lifestyle Hotel", "Global Wellness Day", "All Day",
    "Presidential Suite", "The Haven Suites", "Aksari Suite", "One Bedroom Lagoon Villas", "River Villa",
    "CONRAD Hilton Hotel", "The Ritz-Carlton Ritz Carlton", "Central Park Tribeca Park", "Bar & Caf",
    "Imari Japanese Restaurant and Vis", "Sari Delicatessen and Caf", "Li Lian at Park Hyatt Jakarta",
    "As PARKROYAL Serviced Suites Jakarta", "Copa Restaurant La Floriane Bistro", "Nusa Dua", "South Jakarta",
    "www.example.com", "Villa Air Bali", "Sunday Market at La Brisa", "Kuta Beach and 10",
    "Executive Chef of Kilo Kitchen Jakarta", "Chef Gilles Marx of Amuz Restaurant", "The Best Hotel",
    "Grand Two-Bedroom Villa", "DELUXE SUITE For 2", "Meritus Club Floors", "Bene Italian Kitchen Exterior",
    "Whisky Bar", "24-Hour Gym", "Emergency & Medical Centre", "Kids Water Park",
]


def main() -> None:
    names: list[str] = []
    seen: set[str] = set()
    for src in SOURCES:
        for line in (FIX / src).read_text(encoding="utf-8").splitlines():
            if line.strip():
                n = json.loads(line)["name"]
                if n not in seen:
                    seen.add(n)
                    names.append(n)
    for n in PROBES:
        if n not in seen:
            seen.add(n)
            names.append(n)
    out = FIX / "junk_golden.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for n in names:
            v = classify(n)
            f.write(json.dumps({"name": n, "tier": v.tier, "reason": v.reason}, ensure_ascii=False) + "\n")
    print(f"wrote {len(names)} verdicts to {out}")


if __name__ == "__main__":
    main()

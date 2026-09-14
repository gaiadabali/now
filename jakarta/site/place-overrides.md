# Place overrides — research trail

Human-verified corrections for the 15 rows that `quality.find_duplicate_centroids`
flagged in the 2026-09-14 geocode run. Machine-readable form:
[`place-overrides.jsonl`](place-overrides.jsonl).

These are **source data**, not derived — they are tracked in git, unlike
`jakarta/content/extracted/`, because no pipeline can regenerate them.

## Why these 15 existed

Their source addresses are street names without house numbers
(`"Jl. Pura Mertasari"`, `"Jalan Kartika Plaza"`). Any geocoder answers a
street query with the street, so every venue on one street landed on one
point. That is a **source-data** problem, not a query-construction one —
see `ladder._WHY_RUNG_2_IS_BARE` for the measurement that ruled out the
obvious fix.

There is also a structural contributor: **the ladder stops at the first
success.** A street-level rung-2 hit pre-empts the rung-3 name search that
would have found the venue. Eight of these eleven corrections came from a
name search that the ladder never ran because rung 2 had already
"succeeded". See *Follow-ups* below.

## What the research actually found

Not all 15 were geocoding errors. Three distinct categories:

### Genuinely wrong coordinates — 11 rows corrected

| Venue | Moved | How it was verified |
|---|---:|---|
| Hotel Tugu Bali | **1838 m** | OSM exact name + hotel's own listing, agree to ~30 m |
| Red Carpet (Champagne Bar) | **1004 m** | OSM + Wanderlog, agree to ~10 m |
| Discovery Kartika Plaza Hotel | 799 m | OSM exact name |
| The Anvaya Beach Resort Bali | 528 m | OSM (`The ANVAYA Hotel`) |
| Anantara Seminyak | 431 m | OSM under its **new** name, Grand Seminyak |
| Finns Recreation Club | 391 m | Google Maps listing + TripAdvisor |
| Opera Bali | 308 m | OSM `amenity=nightclub`; weakest of the set |
| The Mill at Starbucks Reserve Dewata | 160 m | OSM + Starbucks' own Dewata site |
| The Trans Resort Bali | 145 m | OSM exact name |
| The Legian Seminyak Bali | 58 m | OSM (`The Legian Bali`) + LHW |
| Ayodya Resort Bali | 0 m | OSM exact name — already correct |

### Not a geocoding problem at all — 3 rows

- **`Trans Resort Bali` / `The Trans Resort Bali` — a dedup miss.** One
  hotel, two rows. `dedupe.py` keys on `normalize_name`, which does not
  strip a leading "The", so the merge never happened. They share a
  coordinate because they *are* the same place. Recorded as
  `action: merge_into`.
- **`Ayodya Beach Club` / `Ayodya Resort Bali` — a false-positive flag.**
  Ayodya Beach Club & Grill is a restaurant *inside* Ayodya Resort. Sharing
  the resort's coordinate is correct. The duplicate-centroid gate cannot
  distinguish genuine co-location from a geocoder collapse, and should not
  be expected to.

### Not a venue — 1 row

- **`The Great 50 Show - Bali`** is Oriental Circus Indonesia's 50th
  anniversary show, a temporary run from **1 May to 25 Aug 2019** on Sunset
  Road. An expired event that place-extraction picked up as a venue. It
  gets no coordinate, and it probably should not be in `places` at all —
  that is an editorial call, so it is flagged rather than deleted.

### Still unresolved — 1 row

- **`Salon Bali`**, Jalan Camplung Tanduk No.10. Not in OSM under any
  variant tried; no source gives a venue-level coordinate. Likely a small
  business that no longer trades. Left deliberately without a coordinate —
  better unresolved than guessed.

## Two source-data defects worth fixing upstream

Both are in `venues.jsonl` and will keep causing trouble until corrected:

1. **`Hotel Tugu Bali` has the wrong street.** The row says
   *Jalan Pantai Berawa*; the hotel is on *Jl. Pantai Batu Bolong*. That
   single wrong street is what produced the largest error here (1.8 km) and
   what collapsed it onto Finns Recreation Club.
2. **`The Anvaya Becah Resort Bali` — "Becah" should be "Beach".** The typo
   would defeat any future name-based match.

## Confidence, and what it means

`confidence` reflects **source strength**, not precision:

- `0.95` — two independent sources agreeing to tens of metres
- `0.90` — exact-name match in OSM
- `0.85` — identified via a rebrand, or a deliberate building-level point
- `0.80` — right building, not a distinct interior point
- `0.75` — **Opera Bali only.** OSM's node is a single generic lowercase
  token (`opera`); corroboration is indirect (hotel listings place the
  resort "within 10 minutes walk of opera Club"). Wants an editor's eye.

## Follow-ups — status

1. ~~Let rung 3 challenge a coarse rung-2 hit.~~ **Done.** A coarse rung-2
   result (street or weaker) is now challenged with a rung-3 name search
   and the more *specific* result wins. Measured: venue-level 104 -> 125,
   street-level 33 -> 10, duplicate centroids 15 -> 2.

   It also independently rediscovered five of the venues researched here
   — Discovery Kartika Plaza, Opera Bali, The Legian, Ayodya Resort and
   The Trans Resort all now resolve automatically to within 150 m of the
   hand-verified coordinate. That cross-validation is worth more than
   either result alone.

2. ~~Nothing consumes this file yet.~~ **Done.** It is rung 0, ahead of
   the free seed, via `--overrides`. Overridden rows bypass the state
   cache, so editing this file takes effect without deleting
   `.state.jsonl`.

3. **Strip a leading article in `dedupe.candidate_key`** — still open, and
   deliberately so. It would change `place_key` for every venue starting
   with "The", invalidating the keys in this file and every cached state
   entry, to merge one pair. The `merge_into` action handles that pair at
   no such cost.

## What the automation still cannot do

Six of the twelve overrides remain necessary — the pipeline does not
reach them even with the challenge:

| Venue | Why automation fails |
|---|---|
| Hotel Tugu Bali | source address names the wrong street entirely |
| Red Carpet | OSM node is 1 km from the Kayu Aya address; only cross-checking two sources settles it |
| The Anvaya | OSM name differs enough that rung 2's street hit stands |
| Anantara Seminyak | rebranded; no automated path knows the old name |
| Finns Recreation Club | not in OSM under this name |
| The Mill at Starbucks Reserve Dewata | OSM node is plain "Starbucks"; the name gate correctly refuses it |

Each of those needed a human to read a page and decide. That is exactly
what rung 0 is for.

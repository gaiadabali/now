# now-geocode

E2.5 — resolves places to coordinates via a strict source ladder, assigns
an area term from the seeded location tree even when precise geo fails,
and emits `geocoded_places.jsonl` for E2.3/E1.8 to load. See
`ARCHITECTURE.md` §15 (Maps), §8 (Filters/fallback ladder), §6 (geo
coverage finding).

## Scope

Consumes `jakarta/content/extracted/venues.jsonl` (136-ish `tribe_venue`
rows with structured addresses) and `jakarta/content/extracted/geo.jsonl`
(MapPress + ACF `google_map` points, already-resolved coordinates — the
free seed). Does **not** touch `engine/packages/loader/`, `cms/`, `db/`,
or `apps/api/`, and does not write to any database. Its only durable
output is `jakarta/content/extracted/geocoded_places.jsonl` plus a
review queue and a markdown report next to it.

## Install / run

```bash
cd engine/packages/geocode
uv venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/ -q

# The honest, zero-cost run — free seed only, everything else unresolved.
.venv/Scripts/now-geocode build \
    ../../../jakarta/content/extracted/venues.jsonl \
    ../../../jakarta/content/extracted/geo.jsonl \
    -o ../../../jakarta/content/extracted/geocoded_places.jsonl \
    --provider none
```

This also writes `geocoded_places_review_queue.jsonl` (everything
unresolved or flagged) and `geocoded_places.md` (human-reviewable
report) next to `-o`, and a resumable `geocoded_places.state.jsonl`
cache. All paths are overridable — see `now-geocode build --help`.

Re-runnable / idempotent: `pipeline.run` is a pure function of its
inputs plus the state cache. Re-running with the same `--state` file
never re-bills a provider call that already produced a final (resolved,
or stably zero-result) answer — see `state.py`.

## The source ladder (never skipped, never guessed past)

```
1. existing coordinates (geo.jsonl)          free, use first
2. structured address (venues.jsonl)         -> geocode
3. venue name + city context                 -> Places text search
4. unresolved                                -> review queue, NOT a guess
```

`dedupe.py` merges `venues.jsonl` and `geo.jsonl` rows into one
`PlaceCandidate` list *before* the ladder runs, by normalized name (not
`wp_id` — the two files' `wp_id`s are different identity spaces
entirely; see the module docstring). Every merge is recorded in the
report; a merge across rows with conflicting city/province is flagged
rather than silently trusted.

Every output row carries `source` (which rung), `confidence`, and
`google_place_id` where applicable. `lat`/`lng` are `null` whenever
nothing was found — never a fabricated fallback coordinate, per the
task's hard requirement.

## Providers

`providers/base.py` defines the interface (`geocode_address`,
`find_place`); `ladder.py` only ever calls through it.

- **`OfflineProvider`** (`providers/offline.py`) — no network, no key,
  fully deterministic (same input -> same synthetic point every time).
  Exists to exercise rungs 2/3, the quality gates, and the report
  end-to-end with **no Google API key available**, per the task spec.
  Every result is marked `is_synthetic=True` and the CLI enforces two
  guardrails so it can never contaminate the real deliverable:
  - `--provider offline` is refused unless `--dry-run` is also passed.
  - `--dry-run` refuses unless the output filename contains `dryrun`.

  Demo run (writes `geocoded_places.dryrun_demo.jsonl` etc., fully
  separate from the real deliverable and its state cache):

  ```bash
  .venv/Scripts/now-geocode build \
      ../../../jakarta/content/extracted/venues.jsonl \
      ../../../jakarta/content/extracted/geo.jsonl \
      -o ../../../jakarta/content/extracted/geocoded_places.dryrun_demo.jsonl \
      --provider offline --dry-run
  ```

- **`GoogleProvider`** (`providers/google.py`) — real Geocoding API
  (rung 2) + Places Text Search (rung 3), both with Indonesia bias
  (`region=id`, `components=country:ID`) per §15/§6's same-named-street
  warning. Unit-tested against recorded fixture JSON in
  `tests/fixtures/google/` — zero network access, zero API key needed to
  run the test suite. To run for real:

  ```bash
  export GOOGLE_MAPS_API_KEY=...
  .venv/Scripts/now-geocode build venues.jsonl geo.jsonl \
      -o geocoded_places.jsonl --provider google
  ```

- **`NominatimProvider` / `PhotonProvider`** (`providers/osm.py`) — OSM
  backed, **free, no API key**. Nominatim is the stronger rung-2
  (structured address) geocoder; Photon is materially better at rung 3
  (venue-name lookup), which is why both exist. Same Indonesia bias
  intent as the Google provider (`countrycodes=id` + viewbox, derived
  from `quality.INDONESIA_BBOX` so bias and gate cannot drift apart).

  Two behaviours that differ from Google and matter:

  - **`google_place_id` is always `None`.** An OSM id never travels in a
    Google-named field; OSM identity stays in `raw`, and provenance
    rides on `location_type` (`osm_poi`, `osm_street`, `osm_area`, ...),
    the same way rung 1 distinguishes `mappress_poi` from
    `google_map_acf`.
  - **Rung 3 is name-gated.** OSM free-text search does not return zero
    results on a miss — it returns the enclosing suburb, a real
    coordinate for the wrong thing. `name_agrees()` requires the
    returned feature's *own* name to overlap the queried venue name and
    returns `None` otherwise. Without this, a miss ships as a resolved
    place.

  Confidence is mapped by feature granularity onto the same scale as the
  Google provider, every bucket deliberately at or below its Google
  counterpart (OSM POI geometry is community-contributed, so claiming
  ROOFTOP-grade 0.95 would overstate what we know):

  | granularity | OSM | Google equivalent |
  |---|---|---|
  | `poi` / `building` | 0.90 / 0.85 | `ROOFTOP` 0.95 |
  | `street` | 0.65 | `RANGE_INTERPOLATED` 0.75 |
  | `locality` | 0.45 | `GEOMETRIC_CENTER` 0.55 |
  | `area` | 0.30 | `APPROXIMATE` 0.35 |

  ```bash
  # Free run, public instance (1 req/s — fine for the 141, not for 12k).
  .venv/Scripts/now-geocode build venues.jsonl geo.jsonl \
      -o geocoded_places.jsonl --provider photon
  ```

  **Self-host for any real batch.** The public instances cap at 1 req/s
  and forbid bulk use outright; a 403/429 is the answer, not a result.
  E5.1 needs a Geofabrik Indonesia extract on disk for OSRM anyway, so
  the marginal cost of pointing Nominatim/Photon at the same extract is
  low:

  ```bash
  .venv/Scripts/now-geocode build venues.jsonl geo.jsonl \
      -o geocoded_places.jsonl --provider nominatim \
      --osm-base-url http://nominatim.internal:8080 --osm-min-interval 0
  ```

- **`ChainProvider`** (`providers/chain.py`) — ordered fallback. This is
  how to answer "is the Google key worth buying?" with a measurement
  instead of a guess: put the free providers first, run the batch, and
  read the per-provider breakdown the CLI prints.

  ```bash
  # Free rungs first; Google billed only for what OSM could not resolve.
  .venv/Scripts/now-geocode build venues.jsonl geo.jsonl \
      -o geocoded_places.jsonl --provider chain --chain photon,google

  # Fully free — no key needed at all.
  .venv/Scripts/now-geocode build venues.jsonl geo.jsonl \
      -o geocoded_places.jsonl --provider chain --chain photon,nominatim
  ```

  The chain's error semantics are the load-bearing part: a
  `RetryableProviderError` from one provider is **never** reported to the
  ladder as `None`, because `state.py` caches `None` as a *final* stable
  negative that no later run will re-ask. If Photon rate-limits and
  Google then legitimately finds nothing, the chain re-raises rather than
  returning `None`, so the candidate stays resumable. A
  `ProviderConfigError` (missing key, 403) instead disables that provider
  for the rest of the run rather than raising on every candidate.

### What Hansel must supply to run this for real

> **You may not need to supply anything.** The `--provider chain
> --chain photon,nominatim` run above costs nothing and needs no
> account. Run it first, read the coverage, and only buy a key for the
> residue. The Google notes below apply only if you choose to.

- A Google Cloud project with **Geocoding API** and **Places API**
  (legacy Text Search endpoint) enabled, billing attached, and an API
  key restricted to those two APIs (and ideally to a server IP).
- Set `GOOGLE_MAPS_API_KEY` in the environment that runs `now-geocode build`.
- **Cost estimate — measured, not assumed.** The original ~$25 figure
  extrapolated from "~2,500 venue-ish articles". The actual run says
  otherwise: `geocoded_places.md` reports **203 candidates, 62 resolved
  free from existing coordinates, 141 unresolved**. So the real Jakarta
  bill is **141 rung-2 calls plus however many fall through to rung 3**,
  not 5,000 requests. At Google's ballpark **$5 per 1,000** that is
  **well under $2** — and plausibly $0, since the March 2025 pricing
  rework replaced the universal credit with per-SKU monthly free tiers
  and Geocoding's sits at 10,000 calls/month. Verify against the current
  Google Maps Platform pricing page before budgeting; these numbers move.

  Two caveats that push the other way:

  - **Bali has no free seed at all.** `bali/content/extracted/geo.jsonl`
    and `venues.jsonl` are both **0 rows**, so Bali gets none of
    Jakarta's 30.5% rung-1 head start — every Bali candidate needs a
    provider call.
  - **E2.3 extracted 6,589 Jakarta + 5,783 Bali places** (all
    `pending_review`). If those are eventually geocoded, that is ~12,000
    calls, which is where cost stops being a rounding error and
    self-hosted OSM stops being optional.

  The `--state` cache means a batch can be split across days/budgets
  without re-paying for anything already resolved.

## Runbook — the real run (self-hosted, free)

This is the production path. It needs no API key and costs nothing.

```bash
# 1. Bring up the geocoder. FIRST START IMPORTS asia/indonesia:
#    ~1 hour, ~37 GB volume, 6 threads / 6 GB. It is not resumable —
#    if interrupted, `docker volume rm now-engine_nominatim-data` and start again.
docker compose --profile geo up -d nominatim

# 2. Wait for the import. /status answers only when it is finished;
#    `docker ps` shows (unhealthy) throughout, which is correct.
until curl -fsS http://localhost:8088/status >/dev/null 2>&1; do sleep 60; done

# 3. Run the batch.
cd engine/packages/geocode
.venv/Scripts/now-geocode build     ../../../jakarta/content/extracted/venues.jsonl     ../../../jakarta/content/extracted/geo.jsonl     -o ../../../jakarta/content/extracted/geocoded_places.jsonl     --provider nominatim --osm-base-url http://localhost:8088 --osm-min-interval 0

# 4. Stop it. Nothing in production queries this (see ARCHITECTURE.md §15);
#    it is build-time infrastructure and should not hold 6 GB indefinitely.
docker compose --profile geo stop nominatim
```

Result on the Jakarta corpus as of 2026-09-14:

```
203 candidates -> 137 resolved, 9 rejected, 57 unresolved
  venue-level   104/203 = 51.2%
  + street-level 137/203 = 67.5%
```

(Before this pipeline: 62 resolved, all from the free MapPress/ACF seed.)

### ⚠️ The state cache and `--provider none`

`--provider none` records nothing as a permanent negative — a run with
no provider describes the run's configuration, not the world, so it
stays retryable (`LadderOutcome.cacheable`). A genuine zero-result from
a provider that *did* answer is still cached as final, which is the
point of `--state`.

If you are re-running after changing provider or query construction and
want every candidate re-attempted regardless, delete the state file:

```bash
rm ../../../jakarta/content/extracted/geocoded_places.state.jsonl
```

### Attribution is required

Coordinates whose `location_type` starts with `osm_` are ODbL. Any
surface that displays one must credit **"© OpenStreetMap contributors"**.
See `docs/data-provenance.md`.

### Known limits of this run

- **15 rows share coordinates with another venue** (`duplicate_centroid`).
  Their source addresses are street names without house numbers, so any
  geocoder returns the street. This is a source-data problem; a Google
  key does not fix it.
- **9 rows were rejected as region centroids** (`below_venue_confidence_floor`)
  — "Bali", "Ubud", "Nusa Dua". They keep their coordinate and flag for
  audit but are deliberately not `resolved`.
- **57 remain unresolved.** Mostly venue names with no usable address —
  the case where Google's Places index genuinely beats OSM. That residue,
  not the original 141, is what a key would buy.

## Area-term fallback

`area.py` assigns a node from the seeded 85-term location tree
(`engine/packages/taxonomy/seed/terms/location.json`) to **every**
place, independent of whether a coordinate was ever found:

```
1. text match on address           -> highest confidence, it's a citation
2. text match on venue name
3. text match on city/province
4. geometric nearest centroid (<=60km, only if a coordinate exists)
5. `country` field says non-Indonesia -> "international"
6. no signal at all                -> "indonesia" (low confidence)
```

`terms.py` matches deepest-node-first (Kemang beats South Jakarta beats
Jakarta) and excludes a small stopword list of aliases that are also
common Indonesian/English dictionary words (`batu` "stone", `kota`
"city", `bukit` "hill", `tim` "team", `solo` "alone") — a real false
positive was caught on the actual corpus (a Bali venue on "Jl. Pantai
**Batu** Belig" was mis-assigned to Malang's Batu district) and is now a
regression test (`tests/test_terms.py::test_generic_dictionary_word_alias_does_not_false_positive`).

## Quality gates (`quality.py`)

- **Indonesia bounding box**: a resolved point outside roughly 11.5°S-
  6.5°N, 94.5°E-141.5°E is `rejected` (not dropped — the raw point is
  kept in the row for audit, `status=rejected`, flag `out_of_bounds`).
- **Duplicate centroid**: >=2 *distinct* places (already deduped by name)
  sharing a coordinate to 5 decimal places (~1m) are flagged
  `duplicate_centroid`. A repeat among rows that are the *same* merged
  free-seed place is expected and excluded from triggering this on its
  own — see the module docstring for the exact rule.

## Proving the PostGIS `ST_DWithin` claim (§15)

`now-geocode` has no database dependency — `pgdemo.py` only *generates*
a self-contained SQL script (`CREATE TEMP TABLE ... ON COMMIT DROP`, so
nothing persists) that loads the resolved coordinates and runs a real
`ST_DWithin` nearby-radius query:

```bash
.venv/Scripts/now-geocode postgis-sql \
    ../../../jakarta/content/extracted/geocoded_places.jsonl \
    -o ../../../jakarta/content/extracted/geocode_st_dwithin_demo.sql

docker exec -i now-postgres psql -U now -d now_test \
    < ../../../jakarta/content/extracted/geocode_st_dwithin_demo.sql
```

Run against the real 62 free-seed points on 2026-09-08: 25 distinct-place
pairs within 3km computed entirely in PostGIS, temp table confirmed
gone (`\dt geocode_demo_points` -> no relation found) once the session
ended. `now_test` was used deliberately — a scratch DB, not a table this
package owns (E2.3/E1.8 own `places` in `now_jakarta`/`now_bali`).

## Pipeline (file layout)

1. `dedupe.build_candidates` — merge `venues.jsonl` + `geo.jsonl` by name.
2. `ladder.resolve_candidate` — walk the 4-rung ladder for one candidate.
3. `area.assign_area` — area-term fallback, independent of rung 2/3 result.
4. `quality.find_duplicate_centroids` — post-hoc pass over everything resolved.
5. `pipeline.run` — orchestrates 1-4, `state.StateStore` for resumability.
6. `report.render_markdown` / `cli.py` — output.

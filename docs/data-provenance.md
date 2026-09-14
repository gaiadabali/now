# Data provenance: what's on disk but not in git (F48)

Written during the F48 pre-init audit (2026-09-09). Explains why the tree
under `jakarta/` and `bali/` has directories full of data that `git status`
will never show as untracked-and-worrying — they're gitignored on purpose,
and this is the reasoning plus the regen path.

## The pipeline

```
jakarta/db/dumps/wxr/*.xml   (raw WordPress export — production data)
        │  wp-extract / wp-harvest (engine/packages/wp-extract, wp-harvest)
        ▼
jakarta/content/extracted/*.jsonl   (parsed, normalized records)
jakarta/content/harvested/*.jsonl   (harvested via WP REST API, alt path)
        │  downstream packages (cms, blender, taxonomy, search, ...) read
        │  these JSONL files as their input
        ▼
engine/packages/cms, search, taxonomy, ...
```

Same shape under `bali/`, minus the `extracted/` stage (bali only has
`harvested/` today).

## What's ignored and why

| Path | Size (2026-09-09) | Ignored by | Why |
|---|---|---|---|
| `*/db/dumps/` | jakarta 87M+45M+, bali 145M | `.gitignore` (pre-existing) | Full copy of production WordPress content, including anything non-public in it. Never belongs in git history — history is forever, a scrub after the fact doesn't remove it from clones already made. |
| `*/content/extracted/` | jakarta 42M | `.gitignore` (added by this audit) | Derived from the dumps above. Regenerable, not source. |
| `*/content/harvested/` | jakarta 78M, bali 123M | `.gitignore` (added by this audit) | Same reasoning — derived, regenerable, and large. |

Combined, the derived JSONL alone is ~240MB. Added to the 280MB of raw
dumps, that's over half a gigabyte that would otherwise sit in the first
commit and in every clone thereafter.

## Why derived data is excluded, not just the raw dumps

The extracted/harvested JSONL is *not* a secret — it's already public
content published on jakarta/bali's live sites. The case against tracking
it is purely about repo hygiene:

- **Regenerable.** Every downstream package's README describes running the
  extractor/harvester against the dumps. Losing this data means re-running
  a documented command, not losing work.
- **Git doesn't shrink.** Once a 240MB blob lands in history, every future
  clone pays for it forever, even after the file is later deleted or
  replaced — unless someone does a history rewrite, which is its own
  can of worms on a shared repo.
- **It changes on every re-run.** As wp-extract/wp-harvest gets fixed
  (there is active work on exactly this — see PROGRESS.md F-series on
  wxr-extract/blender/taxonomy), the JSONL will be regenerated repeatedly.
  Tracking it would mean a 240MB diff-churn file in git blame for every
  extraction bugfix, which defeats the purpose of using git at all here.

**Counter-consideration, recorded for whoever revisits this:** every
downstream package (cms, search, taxonomy, blender, ...) reads this JSONL
as its actual input, and there is currently no committed fixture/sample
version for local dev or CI to run against without first running the full
extraction pipeline locally. If CI or a fresh clone needs to exercise those
packages end-to-end without network access to production WordPress, that's
a gap — the fix should be a *small, curated fixture* (a few dozen records)
checked into each package's `tests/fixtures/`, not committing the full
production-sized JSONL. Several packages already do this correctly (see
`engine/packages/content-clean/tests/fixtures/articles_sample.jsonl`,
`engine/packages/eval/tests/fixtures/*`) — extend that pattern rather than
un-ignoring the full files.

## Geocoding: OpenStreetMap, and the attribution it obliges

`jakarta/content/extracted/geocoded_places.jsonl` is derived like every
other file above, but it is the one whose *source* carries a licence
obligation, so it gets its own note.

Coordinates come from a **self-hosted Nominatim** built from the
Geofabrik `asia/indonesia` extract (`docker compose --profile geo up -d
nominatim`). Rows resolved that way carry `location_type` beginning
`osm_` — `osm_poi`, `osm_street`, `osm_area` — and their
`google_place_id` is always `null`. Rows from the original WordPress
MapPress/ACF seed carry `mappress_poi` / `google_map_acf` instead. The
`location_type` prefix is therefore the provenance marker: it says which
licence a given coordinate is under, per row.

### The obligation

OpenStreetMap data is **ODbL 1.0**. Unlike Google's terms — which permit
storing `place_id` indefinitely but restrict caching other fields — ODbL
lets us store coordinates permanently, which is what makes it the right
fit for a database that *is* the canonical record. The trade is
attribution:

> **Any surface that displays an `osm_*`-sourced coordinate must credit
> "© OpenStreetMap contributors".**

Concretely, that means the map component (§15 uses MapLibre GL) and any
place page rendering a pin from one of these rows. This is a deployment
requirement, not a nicety: shipping the coordinates without the credit
is a licence breach.

It does **not** apply to rows seeded from MapPress/ACF (`mappress_poi`,
`google_map_acf`) — those predate this pipeline and carry their own
history.

### Why the geocoder is not a production service

ARCHITECTURE.md §15 is explicit that nearby-radius queries run on
PostGIS and that a geocoder is never called per request. Nominatim is
therefore **build-time infrastructure**: it turns venue rows into
`geocoded_places.jsonl` once, E1.8 loads that into Postgres, and
production never speaks to it again. It is profiled off (`geo`) and set
`restart: "no"` for that reason, and it is entirely reasonable to run
the import on a laptop and ship only the JSONL.

## Regenerating

See each package's README for the exact command; as of this audit:
- `engine/packages/wp-extract/README.md` — dumps → `content/extracted/`
- `engine/packages/wp-harvest/README.md` — WP REST API → `content/harvested/`
- `engine/packages/geocode/README.md` — venues + geo seed → `geocoded_places.jsonl`
  (needs the `geo` compose profile up; see that README's runbook)

## Scope note

This file documents a DevOps/repo-hygiene decision made as part of F48
(git init). It does not change, own, or comment on the correctness of the
extraction/harvest pipelines themselves — that's wxr-extract/blender/
taxonomy territory, actively being worked by other agents per PROGRESS.md.

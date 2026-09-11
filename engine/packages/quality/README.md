# now-quality (E2.6)

Quality scoring + series clustering for a city DB. Owns `engine/packages/quality/**` only;
writes data into `engine.quality_scores` and `public.articles.series_key` — no schema changes.

## Setup

```
cd engine/packages/quality
uv venv
uv sync
uv pip install pytest   # dev only
```

Connects via `now_db.settings.city_database_url` (same `NOW_PG_HOST/PORT/USER/PASSWORD` env vars
as `now-db`/`now-embeddings`; `--url` accepts a bare db_ref like `now_jakarta` or a full DSN).

## Commands

```
now-quality series --url now_jakarta [--apply] [--fuzzy-threshold 0.87] [--report path.md]
now-quality score  --url now_jakarta --articles-jsonl jakarta/content/extracted/articles.jsonl \
                    [--popularity-head 300] [--report path.md] [--dry-run]
```

`series` is dry-run by default (writes a report only); pass `--apply` to actually write
`series_key`. It only ever fills `NULL` rows — an existing value (loader-seeded or a prior manual
correction) is never overwritten, so reruns are safe. `score` always recomputes and upserts
(idempotent by construction: same input -> same output row).

Run `series` before `score` if you want the freshly-clustered series reflected in
`quality_scores.components.series`; `score` also works fine standalone (it reads whatever
`series_key` is live in the DB at the time and recomputes the current-member flag itself).

## Design notes

Each module carries the actual rationale in its docstring:

- `scoring.py` — the five quality components, their weights, and why; the stub floor guarantee.
- `popularity.py` — where the popularity-prior cutoff is set and why (percentile table included).
- `series.py` — the clustering method, what gets auto-merged vs. flagged, and why.
- `entity_id.py` — **read this one** — documents an unresolved cross-cutting schema gap
  (`engine.*` uuid entity columns vs. `public.articles`'s integer PK) this package works around,
  and a partial fix that already landed elsewhere in this wave (migration 0004, `engine.embeddings`)
  that `quality_scores` still needs.

## Tests

```
.venv/Scripts/python.exe -m pytest -q
```

Pure-function unit tests only (no DB required) — `scoring`, `popularity`, `series`, `entity_id`,
`source` are all DB-free by design so they're fast and don't need Docker running to test.

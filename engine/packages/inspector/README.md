# now-inspector (E3.4 -- Engine Inspector)

Internal debug UI (ARCHITECTURE.md §17): given a free-text query or an article id, show every
candidate generator's raw output before fusion, per-component scores, the RRF fusion (both input
ranks + fused score), the **filter trace** (what was removed, by which rule -- the highest-value
panel per the ticket), the fallback rung reached per rail (when `now_filters`/E3.2 is importable),
MMR/diversity status, and the full quality-score component breakdown.

Server-rendered FastAPI + Jinja2. No build step -- `now-inspector serve` and open a browser.

## Quickstart

```bash
cd engine/packages/inspector
uv venv
uv sync --extra dev

# Serve the UI (city db_ref is required, no default -- ARCHITECTURE.md §3.5, every city is a
# separate DB; matches now-search's own --db being required with no default)
.venv/Scripts/now-inspector serve --url now_jakarta --port 8899
# then open http://127.0.0.1:8899/

# Or capture one rendered report to a static HTML file, no browser needed:
.venv/Scripts/now-inspector capture --url now_jakarta --article-id 3899 --out out.html
.venv/Scripts/now-inspector capture --url now_jakarta --query "rooftop bar senopati" --out out.html

# Pure unit tests (no DB required):
.venv/Scripts/python.exe -m pytest -q
```

Connection: same `NOW_PG_HOST/PORT/USER/PASSWORD` convention as `now-search`/`now-quality`/
`now-db` (`now_db.settings.city_database_url`), reading the project's `.env` per F31. On this
host: the CLI reads the project `.env` automatically (F31), so no env vars are needed. To override, set `NOW_PG_PORT` / `NOW_PG_PASSWORD` from `.env`.

## What each panel is and where its data comes from

1. **Candidate generators** (`generators.py`) -- calls `now_search.lexical.search_lexical` and
   `now_search.semantic.search_semantic` directly (not `SearchEngine.search()`, which only
   returns the fused top-k) so the raw, separate, pre-fusion output of each rail is visible.
   `now_search`'s public signatures are used as-is; this package does not modify that one.
   - **Query mode**: literal free-text search, same as `now-search search`.
   - **Article-id mode**: no "more-like-this" entry point exists in `now-search`'s public API,
     so this builds the closest honest approximation: lexical rail runs the seed's
     `title + dek` as the search text; semantic rail runs kNN against the seed's *own* stored
     vector (`engine.embeddings`, always `WHERE model = :model` per F42). Documented as an
     approximation in the module docstring, not presented as a real "related articles" rail.
2. **RRF fusion** (`generators.fuse`, reusing `now_search.rrf.reciprocal_rank_fusion` unmodified)
   -- table shows each candidate's lexical rank, lexical raw score, semantic rank, semantic raw
   score, and fused RRF score side by side.
3. **Per-component scores** (`blender.py`) -- semantic / rrf / quality / freshness, each labelled
   with what it is and how it was derived; `covis`/`geo`/`promo` always shown as unavailable
   (nothing in the repo computes them yet). The "illustrative composite" is an **unweighted mean
   of available components only** -- explicitly not E3.3's tuned blend (`sites.ranking_weights`
   does not exist yet). See the module docstring for why this is safe to show without being
   mistaken for the real blend.
4. **Filter trace** (`filters_trace.py`) -- the highest-value panel. Re-derives ARCHITECTURE.md
   §8.A's hard filters (status, self, competitor/same-L1-type, series dedup, quality floor, event
   expiry) against real rows for display. This is an Inspector-owned re-derivation for debugging,
   not a second production filter implementation -- `engine/packages/filters` (E3.2) is being
   built concurrently and is not depended on for this logic. Every rule that cannot execute today
   (competitor exclusion needs `primary_type`, NULL on all 4,772 rows pending E2.1) is marked
   `data_status="not classified yet"` rather than silently passing without a label.
5. **Fallback rung** (`filters_adapter.py`) -- best-effort, defensive integration with
   `now_filters` (E3.2). Tries a few plausible import paths and entry-point names; if the package
   isn't importable, or is importable but its API doesn't match any guessed entry point, the panel
   renders an honest "not available" state with the reason -- never raises, never fabricates a
   rung number.
6. **MMR / diversity** (`diversity.py`) -- always renders the honest stub: nothing in this repo
   implements MMR yet (confirmed by grep), and it depends on `org`/`area`/`format` linkage that
   doesn't exist yet either (E1.5/E2.3/E2.5/E2.1). Lists exactly what's missing.
7. **Quality-score components** (`articles.fetch_quality`/`fetch_quality_bulk`) -- reads
   `engine.quality_scores.components` (jsonb) directly and renders every key now-quality wrote,
   expanded, plus the stored `score`. No re-derivation, no drift risk from a second scoring
   implementation.

## NULL / not-classified-yet handling

`primary_type` and `format` are NULL on all 4,772 `now_jakarta` articles as of this ticket (E2.1
hasn't run). Every panel that depends on them renders an explicit `not classified yet` label
(`models.py`'s `FilterTraceEntry.data_status`, `FreshnessResult.half_life_label`,
`ArticleRow.primary_type`/`.format` displayed via the `not-classified` CSS class in
`templates/report.html`) rather than a blank cell -- per the ticket's design note, absence of
data must be visible.

## Filters package (E3.2) integration

`engine/packages/filters` does not exist in this tree as of this ticket. `filters_adapter.py`
probes for a `now_filters` module at runtime, catches every failure mode (not installed, import
error, no recognised API), and returns `available=False` fallback-rung entries with an
explanatory note instead of raising or guessing. When E3.2 ships a real API, update
`filters_adapter.py`'s `probe()`/`get_fallback_rungs()` entry-point names to match it -- the rest
of this package (the `FallbackRungInfo` shape, the template rendering) should not need to change.

## Verified against real data

Real Postgres, `now_jakarta`, 4,772 articles (see the ticket report for captured HTML/output).
Two things worth knowing when reading the captures:

- `engine.article_search` (the materialised lexical table F41 introduced this wave in
  `now-search`, replacing its old `pg_temp` cache) is **0 rows** in this environment as of this
  ticket -- that migration/backfill hasn't run here yet. The lexical generator panel therefore
  legitimately shows 0 hits for every query; this is real, current state of a package this ticket
  does not own, surfaced honestly, not an Inspector bug.
- `engine.quality_scores` (E2.6) and `engine.embeddings` (E2.4) are both fully populated
  (4,772 and 5,216 rows respectively), so the quality-components and semantic-generator panels
  show real, non-degraded data.
- Article ids `3433`/`3899`/`4466` (`series_key="new-restaurants-in-jakarta-latest-openings"`)
  and `3141`/`3655` (`"artmoments-jakarta"`) are the only `series_key`-populated rows in the
  corpus and are the best real demonstration of the series-dedup filter trace actually removing
  a superseded sibling while keeping the current one.

## Scope

Owns only `engine/packages/inspector/**`. No migration, no DDL, no writes -- every query in this
package is a SELECT. Does not modify `search`, `filters`, `db`, `quality`, `embeddings`, or
`apps/api`.

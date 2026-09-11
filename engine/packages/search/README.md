# now-search (E3.1/F41 — Hybrid search: BM25 + vector + RRF)

Hybrid retrieval over `now_jakarta`: Postgres full-text (`ts_rank_cd`,
title > dek > body weighted) over the materialised `engine.article_search`
table, fused with pgvector kNN over `engine.embeddings`
(`BAAI/bge-small-en-v1.5`, always model-filtered) via Reciprocal Rank
Fusion. See ARCHITECTURE.md §7 "Search", §8.G (filter ordering), §17
(evaluation).

`engine.article_search` (migration `0006`, owned by this same ticket) is
a real, GIN-indexed, persisted table — no `pg_temp` cache, no per-query
jsonb parsing, no per-connection warm-up cost on the lexical side. It is
kept fresh by `tsv_worker.py`, a Redis Stream consumer on its own
consumer group. See "F41: from `pg_temp` cache to a materialised table"
below for the full before/after story and why this migration exists.

## Quickstart

```bash
cd engine/packages/search
uv sync --extra dev
uv run now-search backfill-tsv --db now_jakarta   # build/refresh engine.article_search
uv run now-search search "rooftop bar senopati" --db now_jakarta -k 10
uv run now-search handcheck --db now_jakarta        # the 10 canonical hand-check queries
uv run now-search bench --db now_jakarta -n 200     # p50/p95/p99 over 200 queries
uv run now-search eval --db now_jakarta             # wires into now-eval, reports nDCG@10 vs baseline
uv run now-search tsv-worker --once                 # process pending article.published events, then exit
uv run pytest                                       # pure tests always run; integration tests
                                                     # skip cleanly if now_jakarta is unreachable
```

Connection: `NOW_PG_HOST/PORT/USER/PASSWORD` — same convention as
`now-db`/`now-embeddings`/`now-quality` (see `now_search/connections.py`).
The CLI reads the project's `.env` automatically (F31), so no env vars
are needed on a normal dev checkout; to override, set `NOW_PG_PASSWORD`
to the `POSTGRES_PASSWORD` value from `.env` (never hardcode it in a
committed file — see `now_db.settings`/`now_platform_db.settings` for the
resolution order).

## F41: from a `pg_temp` cache to a materialised table

**History, for context.** E3.1 was built under a "no migration, no DDL"
constraint (another agent owned Alembic that wave) and had to approximate
`engine.article_search` in a session-scoped `pg_temp` table instead. Two
real problems came out of that constraint, both closed by this ticket's
migration `0006`:

1. **Latency.** A literal per-query CTE — extract body text from
   `body_blocks` jsonb via `jsonb_array_elements` + `regexp_replace` and
   recompute `to_tsvector` for the whole corpus on every call — measured
   **2,619 ms/query** (`EXPLAIN ANALYZE`, directly against `now_jakarta`).
   The `pg_temp` memoization (build once per *session*, ~3.0s + ~0.86s
   index build, then 2–6ms/query) got this under budget, but only by
   introducing a warm-up step every connection had to pay once.

2. **A real relevance bug (F40).** The `pg_temp` cache's body-text
   extraction was a simplified SQL approximation — it pulled `html`/
   `text`/`caption` string values off each `body_blocks` element and
   stripped tags with a regex. That handles `paragraph`/`quote`/
   `raw_html`/`heading`/`image` but **silently skips `list` (text lives
   in an `items` array), `gallery` (`images` array), and nested `columns`
   blocks**. NOW! Jakarta's top-traffic content is listicles — "7 Best
   Padel Courts", "10 Best Spas in Jakarta" — which are built almost
   entirely from `list` blocks. Their actual content (venue names,
   details) was therefore invisible to lexical search.

**The fix**: `engine.article_search` (migration `0006`) is a real table,
refreshed by `tsv_pipeline.py`/`tsv_worker.py` using
`now_content_clean.metrics.visible_text_out` — the exact same lxml-based
block-walker `now-embeddings` already uses for the semantic side, which
walks `list`/`gallery`/`columns` correctly. This closes both problems at
once: the GIN index lives on a real table (survives across connections
and processes, so there is no warm-up left to pay), and the indexed text
is now the real visible text of every block type, not a regex
approximation of some of them.

**Verified, not assumed** (see the ticket report for the full
before/after): a sponsor name that lives *only* inside a `list` block's
`items` array (e.g. "Givaudan" in article 290, "SwissCham Indonesia Golf
Tournament 2019") does not match under the old SQL-approximation logic
replayed as a query (`0 rows`) but does match `engine.article_search`
today (`lex_rank=1`). `tests/test_lexical_integration.py::
test_f40_listicle_list_block_text_is_indexed` asserts the same class of
fact generically, against whatever `list`-block articles exist at test
time, not one hardcoded example.

**Honest caveat, stated plainly**: F40's original motivating example —
*"brunch spots kemang"* ranking "7 Best Padel Courts in Jakarta" at #2 —
is **still reproducible after this fix**, and root-caused: that
particular article uses no `list` blocks at all (`heading`+`paragraph`
per numbered item), and its *paragraph* prose already contains the words
"brunch" ("Ladies Brunch" package), "spot" ("the perfect spot to enjoy
this... sport"), and "Kemang" (a court's location) — all three literally,
independent of any list-block gap. `websearch_to_tsquery` ANDs bare words
by default, so any document containing all three stems matches regardless
of whether they describe what the reader meant. This is a genuine lexical
ambiguity BM25 alone cannot resolve and was never in F41's scope to fix
(no amount of "index the right blocks" changes what words are actually,
legitimately, present in this specific article's prose) — see the ticket
report's "hand-checks" section for the full read across all 10 queries,
most of which *did* improve or were already good.

## Model filter

Every semantic query filters `WHERE entity_type = 'article' AND model =
:model` (`now_search/semantic.py`, `_KNN_SQL*`) — there is no code path
in this module that omits it. Verified with a real Postgres test
(`tests/test_semantic_integration.py::test_model_filter_excludes_other_models`)
that queries under a model name guaranteed not to exist and asserts zero
rows, not a fallback to "any model". The query text is embedded with
`now_embeddings.providers.local.LocalProvider` (the exact same provider
class, not a re-implementation) specifically so the query vector and the
corpus vectors can never silently drift onto different models.

## F67 — the restricted (`candidate_ids`) kNN path used to silently return zero rows

`search_semantic(..., candidate_ids=[...])` — the documented mechanism
for pushing a pre-filtered id set into semantic ranking (ARCHITECTURE.md
§8.G "constrain before the vector search") — used to return an empty
result, with no error, whenever the restriction had no overlap with the
handful of nodes `pgvector`'s HNSW index approximates its way to (default
`hnsw.ef_search = 40`, `hnsw.iterative_scan` off in this DB). Root-caused
with `EXPLAIN (ANALYZE, BUFFERS)`, not guessed — full mechanism, proof,
and the fix (`_KNN_SQL_RESTRICTED` now filters inside a `MATERIALIZED`
CTE, forcing an exact scan-then-sort instead of a filtered ANN scan) are
in `now_search/semantic.py`'s module docstring, with a real-data
regression test at
`tests/test_semantic_integration.py::test_f67_small_restriction_far_from_query_does_not_silently_return_zero`.
`now_rails.row3_similar` hit this independently and worked around it with
its own numpy exact-cosine (`_restricted_semantic_knn`) rather than
patching a package it doesn't own — see that module's docstring for its
own repro. That workaround's *ranking* half is now redundant (this
module's own restricted path is correct); see this repo's F67 ticket
report for a fuller discussion of what `now_rails` could retire, since
`engine/packages/rails/` is out of this package's scope to edit.

## F60 — query embedding latency: onnxruntime version, not contention

`query_embedder.py`'s single-query embed dominates end-to-end p95 (it
always will, by construction — see `row3_similar.py`'s docstring on why
Row 3 avoids it entirely). F53 found a ~30-40ms gap between measured and
documented embed latency that host-load contention alone didn't explain,
and named unpinned `onnxruntime` version drift as the leading unconfirmed
hypothesis. This session confirmed it directly: `onnxruntime` had no
version pin anywhere in this repo, `uv sync` had silently resolved it to
`1.29.0`, and re-testing across releases with everything else held
constant showed a **~15-20x** regression specific to `1.29.0` (p50 ~100ms)
versus every version from 1.19.2-1.25.1 (p50 5.5-27ms), at comparable or
worse host load. Fixed by pinning
`onnxruntime>=1.21.0,<1.25,!=1.24.0,!=1.24.1` in `pyproject.toml`
(resolved to `1.24.4`) — end-to-end `now-search bench` now measures
**p95 42-48ms**, comfortably under the p95 < 80ms target, versus the
109-196ms this box measured before the pin. Full numbers, method, and the
re-baselined embedder benchmark: `BENCHMARK.md`'s "F60" section.

## Facet counts — mechanism built, unexercised

`now_search/facets.py` implements the ecommerce rule ("when counting
facet F, apply every filter except F") for two kinds of facets:
- **column facets** (`type` → `public.articles.primary_type`, `format` →
  `.format`) — real columns, real data path, but every row is NULL as of
  this ticket (E2.1 classification hasn't run).
- **term facets** (`engine.entity_terms.term_id`, keyed by a facet name
  the caller supplies term_ids for) — `engine.entity_terms` has 0 rows
  as of this ticket (E2.2 hasn't run).

Both are computed in one round trip (`UNION ALL` of per-facet aggregate
branches — see the module docstring for why that counts as "one
aggregate pass" operationally). Tests
(`tests/test_facets_integration.py`) run this against real Postgres and
assert the honestly degenerate result ("every row is in the NULL
bucket") rather than faking a populated distribution.

**Term facet label resolution** (a note for whoever wires facets into a
real API): `engine.entity_terms.term_id` resolves to a human label only
via the *platform* DB (`now_platform.engine.terms` joined to
`engine.facets`) — a second database. This package intentionally stays
single-database (matches every other package's per-DB scoping) and
returns raw term_ids; resolving labels is the caller's job, done once
per response against `now_platform`, not per facet-count query.

## `engine.article_search`: schema, backfill, and the keep-fresh worker

Migration `0006` (`engine/packages/db/src/now_db/migrations/versions/
0006_article_search_and_travel_matrix_widen.py`):

```sql
CREATE TABLE engine.article_search (
    entity_id      integer PRIMARY KEY,   -- public.articles.id, verbatim, NO FK -- see below
    tsv            tsvector NOT NULL,
    body_text_hash text NOT NULL,          -- same idempotency pattern as engine.embeddings.text_hash
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_article_search_tsv ON engine.article_search USING gin(tsv);
```

**No foreign key to `public.articles(id)`**, despite the task brief's
sketch DDL including one — verified two independent ways that it would be
unsafe, not assumed (full reasoning in migration `0006`'s docstring):

1. `now_test` (the synthetic third tenant, ARCHITECTURE.md §3.5/E0.6) has
   no `public.articles` table at all — a hard FK would make `upgrade()`
   fail outright on one of the three databases this migration must apply
   to.
2. Payload's own `down()` migration (`engine/packages/cms/src/migrations/
   20260908_131927_initial_schema.ts`) does `DROP TABLE "articles"
   CASCADE`, which would silently drop the FK constraint (data survives,
   referential integrity does not, and is never automatically restored on
   the next `up()`) — exactly the "Payload's own migrations dropping/
   recreating the table" ordering hazard the task brief warned about.

Migration `0001`'s baseline already established "no FK against `public`,
enforced by the API/worker layer instead" for every other `engine.*`
table that logically references `public.articles`/`public.places`
(`embeddings`, `entity_terms`, `quality_scores`, `covisitation`,
`rail_cache`, `travel_matrix`) — `article_search` follows the same rule
for the same reason.

**Backfill**: `now-search backfill-tsv --db <db_ref>`
(`tsv_pipeline.backfill_tsv`) fetches every published article, computes
`(title, dek, visible_text_out(body_blocks))` and a sha256 hash of that
triple, diffs against `body_text_hash` already stored, and upserts only
what changed — a rerun with nothing changed rewrites nothing. Also prunes
`article_search` rows for articles no longer published (`--no-prune` to
skip).

**Keep-fresh worker**: `now-search tsv-worker [--once]`
(`tsv_worker.TsvRefreshWorker`) consumes `article.published`/
`article.republished` off the same Redis Stream
`now:domain-events:stream` that `now-embeddings`'s `ReembedWorker` already
reads, under its **own consumer group** (`now-search-tsv-worker`, vs.
`now-embeddings`'s `now-embeddings-worker`) — Redis Streams consumer
groups each get an independent copy of every message, so two groups on
one stream never steal each other's work, but two workers sharing one
group would. Article-only by design (`engine.article_search` has no place
rows — places have no body prose to index, see
`now_embeddings.textbuild.build_place_text`'s docstring), so
`place.published` is correctly ignored, not an oversight.

**Environment gotcha found while verifying the worker end-to-end** (not
this package's bug to fix -- `now_platform_db` is owned elsewhere, noting
it here for whoever runs this worker next): `now_db.settings` reads the
project `.env` automatically (F31), but `now_platform_db.settings.
platform_database_url()` does **not** -- it only honours
`NOW_PLATFORM_DATABASE_URL` or the discrete `NOW_PG_*` env vars, falling
back to `localhost:5432`. `TsvRefreshWorker` (and `now-embeddings`'s
`ReembedWorker`, which has the identical dependency) therefore need
`NOW_PG_HOST/PORT/USER/PASSWORD` exported explicitly when run outside the
docker-compose network, even though every other command in this
package's Quickstart works with zero env vars set.

## Reciprocal Rank Fusion

`now_search/rrf.py` — pure functions, no I/O, `k ≈ 60`
(`DEFAULT_K`), unit-tested directly against the formula
(`tests/test_rrf.py`). RRF (not min-max score normalisation) is used
because `ts_rank_cd` and cosine similarity live on incomparable scales
— see the module docstring for the full reasoning, matching
ARCHITECTURE.md §7's own stated rationale.

## Eval wiring (nDCG@10)

`now_search/eval_sut.py` implements `now_eval`'s `SystemUnderTest`
Protocol for the `search` surface (`rank()` only — `related`/
`tag_facets`/`classify_type` are out of scope and raise
`NotImplementedError`, so this SUT must never be passed to
`now_eval.harness.run_harness()`, only to `evaluate_search()` directly,
exactly as `now-search eval`'s CLI command does).

**Why the adapter lives here and not under
`engine/packages/eval/src/now_eval/sut/`**, despite the task brief
naming that path: verified directly that `now_eval/sut.py` already
exists as a plain module, and creating a *package* directory
`now_eval/sut/` alongside it does not coexist — Python's import system
resolves the package and the sibling module becomes completely
unreachable, silently breaking `harness.py`'s `from .sut import
SystemUnderTest` and every existing eval test. That is "modifying
existing eval files" by a different mechanism, which the task brief
scopes this adapter to avoid. Wiring it in by calling `now_eval`'s
*unmodified* public API (`evaluate_search`, `build_provisional_query_set`,
`load_baseline`) from this package instead achieves the same goal with
zero risk to eval's existing behaviour or tests.

Article-id bridge: `now_eval` keys everything by `f"wp:{wp_id}"`
(WordPress's legacy id); this package keys by `public.articles.id`
(Payload's PK). `public.articles.legacy_wp_id` is the verified,
unique, fully-populated bridge column (`WpIdBridge` in `eval_sut.py`).

**F38 caveat, restated (do not read the headline number as "relevance
improved 127x")**: the eval query set (`now_eval.datasets.search_queries.
build_provisional_query_set`) derives each query from an article's own
title/focus keyword and grades that SAME article relevance=3 in its own
query's relevance map — so nDCG@10 is dominated by "find the document
this phrase came from," a task hybrid search trivially wins even without
F41. QA-verification's `e31_ndcg_source_excluded.py` script (read-only,
not owned by this package) recomputes nDCG@10 with each query's own
source-article entry removed, leaving only genuine same-category peer
documents as "relevant." Both numbers, measured against this ticket's
`engine.article_search`-backed lexical path:

| | as reported (source incl.) | source excluded (peers only) |
|---|---|---|
| E3.1 (pre-F41, `pg_temp`) | 0.7642 | 0.0682 (QA-measured, QA.3) |
| F41 (this ticket, `article_search`) | 0.764701 | 0.068391 |

Both numbers moved by roughly +0.0005/+0.0002 — statistically
indistinguishable from "unchanged." **This is expected, not a sign F41
did nothing**: F40's fix is about surfacing list-block-only content for
queries that specifically depend on it (the "Givaudan" example above),
and this eval query set's construction (title/focus-keyword-derived,
graded against the source article and its same-category peers) was never
built to reward that. The nDCG number is too saturated by the
self-referential signal to move on a fix like this one; **the hand-check
queries are the real signal** — see the ticket report.

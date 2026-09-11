# now-rails

E3.5-E3.8 — the three reader-facing rails (ARCHITECTURE.md §7) and the `engine.rail_cache`
read-through cache backing `GET /v1/{site}/articles/{id}/rails` (§16). Composes `now-search`
(stored embeddings, kNN), `now-filters` (hard filters, fallback ladder, MMR diversity caps,
competitor exclusion) and `now-blender` (weighted blend, freshness decay) — this package owns no
retrieval/scoring math of its own beyond what each rail's shape genuinely needs.

## The three rails

| Rail | Module | Pool | Real-data status |
|---|---|---|---|
| Row 1 Complementary | `row1_complementary.py` | `complements[subject_type]` places | **Structurally empty on real data** — F27 (0/177 places `status='active'`) |
| Row 2 Nearby | `row2_nearby.py` | any geo'd place, radius hard filter | **Structurally empty on real data** — same F27 gate |
| Row 3 Similar | `row3_similar.py` | semantic kNN over articles, series-deduped | **Structurally empty on real data too, as of F68** — see below; mechanism (semantic ranking + series dedup) proven real, end to end, with competitor exclusion neutralized via a known type override |

All three exclude the subject's own L1 type at every fallback rung, enforced twice: once in the
SQL hard filter (`now_filters.hard`) and once more, unconditionally, in
`now_filters.ladder.run_ladder`'s defensive re-check. When a subject's own type is unknown (F50:
`articles.primary_type` is NULL for all 4,772 real rows), every rail **fails closed** — returns
empty rather than guessing — because the exclusion cannot be computed without one; this is the
correct behaviour per the brief ("do not weaken the exclusion to make a rail return rows"), not a
bug. See each module's docstring for the exact reasoning.

## What is validated on real data, and what is not

Verified directly against `now_jakarta` before writing a line of code:

| Fact | Value |
|---|---|
| Articles, published | 4,772 |
| Articles with `primary_type`/`format` set | **0** (F50) |
| Places | 177, all `type='unknown'`, all `status='pending_review'` (F27) |
| Places with lat/lng | **0/177** |
| Places with `price_band`/vibe tags/`org_id` | **0/177** |
| `place_mentions` rows | **0** — no article names a specific place today |
| Real `series_key` groups | 2 (3-member + 2-member) |
| Article embeddings (`BAAI/bge-small-en-v1.5`) | 4,772/4,772 |
| Place embeddings (same model) | 177/177 |
| `engine.quality_scores` | articles only (4,772); **0 place rows** — no places quality scorer exists yet |

Consequences, stated plainly:

- **Row 1 and Row 2 cannot return a single real result today.** Not a defect in this package —
  every real place is `pending_review`, and `status='active'` is F27's unconditional, never-relaxed
  gate. Both rails are fully implemented, tested, and exercised end-to-end against
  `now_filters.synthetic` places (deterministic type/status/geo/org/area variety). The moment E2.3
  activates real places, these rails read from the identical code path with no changes.
- **Row 1's facet compatibility (price band, vibe)** is implemented per §7's literal formula
  (`price_band_proximity × vibe_overlap × geo_proximity × user_taste`) and unit-tested, but every
  real candidate has neither a price band nor a vibe tag, so every real compat score is a uniform
  1.0 (both factors default to neutral when absent) — indistinguishable from "not implemented" on
  real content alone. The mechanism is real; the real data to exercise it is not.
- **Row 3, called the ordinary way on real content, now also returns empty — as of F68, and
  correctly so.** `now_filters.excluded_types_for(subject_type=None)` (F68) fails closed to
  "exclude every venue-shaped type, including unknown" — right, for the commercial guarantee's
  sake — but the SQL predicate it drives (`primary_type::text != ALL(:excluded_types)`) evaluates
  to SQL `NULL`, and therefore excludes, every real candidate row, because `primary_type` is `NULL`
  archive-wide (F50). A real subject's type is *always* `None` today, so `compute_row3` called on
  any real article id now resolves zero eligible candidates and returns before ever reaching
  `search_semantic` — proven directly, not assumed
  (`tests/test_row3_similar.py::test_row3_real_subject_with_unknown_type_returns_empty`). This is
  F68's guarantee working as intended on real content, not a defect in this switch — see
  "Performance" below for what that does to the honest end-to-end number.
- **The semantic-ranking + series-dedup mechanism is still proven real, end to end.**
  `test_row3_series_dedup_on_real_data` overrides the subject's `primary_type` to `"editorial"` — a
  real, `engine.type_relations`-known, `exclude_same=False` type, the same technique F68's own fix
  used for its two equivalent `now_filters` tests — so the (unrelated) competitor predicate is
  skipped entirely and real, `NULL`-typed candidates flow through on their own merits (status/
  quality/series-dedup, all still fully enforced). This is not a relaxation of any guard; it is the
  only way left to exercise real embeddings + the real 3-member series end to end now that F68
  closed the accidental hole that used to let this happen with `subject_type=None` too. Competitor
  exclusion itself remains provable only against a `now_filters.synthetic` articles table
  (`test_row3_competitor_exclusion_and_series_dedup_synthetic`), for the same F50 reason as Row 1/2.

## A bug found while building this — fixed upstream (F67), workaround retired (F70)

`now_search.semantic.search_semantic`'s `candidate_ids`-restricted query used to return **zero
rows**, silently, whenever the restriction set was a small fraction of `engine.embeddings` —
verified with `EXPLAIN`: the HNSW index (`ix_embeddings_hnsw`) applied the `entity_id = ANY(...)`
restriction as a post-filter over its own *approximate* nearest-neighbour traversal, and if none of
the globally-nearest candidates the index actually visited happened to satisfy the filter, the
query returned nothing even though real matches existed elsewhere in the table. Row 3 originally
worked around this with its own `_restricted_semantic_knn` (numpy exact-cosine over a batched
vector-as-text fetch) rather than serve wrong (silently empty) results from a package this ticket
could not modify.

**F67 fixed the root cause in `now_search` itself** — a `MATERIALIZED` CTE forces the restricted
path to be exact at every restriction size (see `now_search/src/now_search/semantic.py`'s own
docstring). **F70 retired the workaround**: `row3_similar.py` now calls
`search_semantic(candidate_ids=eligible_ids, limit=rerank_pool)` directly, which does the identical
exact cosine ranking, in SQL, over the identical restricted set. `_restricted_semantic_knn` no
longer exists. `fast_similarity.py` is unchanged in *purpose* — it still does pairwise
candidate-to-candidate similarity for MMR diversification, a genuinely different job
`search_semantic` does not and should not provide — but now sources its vectors via `.load()`
(a live, small fetch) rather than a preloaded batch, since `search_semantic` ranks without handing
vectors back. See "Performance" below for what was measured, not assumed, about this switch.

## Performance — p95 < 120ms

**F70 re-measurement (this session), post-F60 (onnxruntime pinned to 1.24.4) and post-F67/F70
(`search_semantic` restricted-kNN fix + this package's switch to it).** Host load sampled with
`Get-CimInstance Win32_Processor | Select LoadPercentage` immediately before/after each run: **2-14%
throughout — a quiet box**, unlike F41/F53's contended ones.

### Warm and honest end-to-end cold, on real article ids, unmodified

30 distinct real article ids, `engine.rail_cache` rows for those ids deleted before each cold call
(genuine cache miss, not a stale-row overwrite), `RailsOrchestrator.compute_rails` called the
ordinary way (no overrides):

| Path | p50 | p95 | max | min |
|---|---|---|---|---|
| **Warm (cache hit)** | 2.94ms | 4.46ms | 4.99ms | 1.55ms |
| **Cold (cache miss, ordinary call, real ids)** | 19.99ms | 34.56ms | 38.26ms | 13.90ms |

Both **comfortably clear 120ms** — a large, real improvement over the previously-documented cold
182ms p50 / 229ms p95. **But this number is not what it looks like, and reporting it without the
caveat below would be dishonest.**

**F68 (a separate, upstream `now_filters` fix, out of this package's scope, landed the same day)
changed what an "ordinary cold call" on today's real data actually does.** `excluded_types_for
(subject_type=None)` now fails closed to "exclude every venue-shaped type, including unknown" —
correct, per that ticket's own commercial-safety brief. But the SQL predicate it drives
(`primary_type::text != ALL(:excluded_types)`) evaluates to SQL `NULL`, and therefore excludes,
every real candidate row, because `primary_type` is `NULL` archive-wide (F50). A real subject's type
is *always* `None` today (E2.1 hasn't run) — so **every rail, on every real article id, now resolves
zero eligible candidates and returns before reaching any expensive downstream work** (Row 1/Row 2
already did, per F27; Row 3 now does too, per F68). The 19.99ms/34.56ms cold number above is
therefore mostly measuring three cheap "resolve zero candidates" SQL round trips plus a subject
fetch and a cache write — not a genuine compute. This is F68 working as intended on real content
(PROGRESS.md), not a regression from this ticket's `search_semantic` switch — but it means this
number cannot answer "does the switched ranking code meet 120ms", because that code never runs on
real content today at all. Verified directly, not assumed:
`tests/test_row3_similar.py::test_row3_real_subject_with_unknown_type_returns_empty`.

### Genuine full-compute cold path (the number that answers the actual question)

To measure `compute_row3` doing real work — hard filter, ladder, `search_semantic` ranking, meta/
quality fetch, MMR via `FastEmbeddingSimilarity.load()`, title fetch — against real embeddings and
the real 3-member series, the subject's `primary_type` was overridden to `"editorial"` (a real,
`exclude_same=False` type; same technique as `test_row3_series_dedup_on_real_data`, see that
section above) so the *unrelated* competitor predicate does not zero out real candidates before
ranking ever runs. Three independent runs, 30 real article ids each, direct `compute_row3` calls
(no cache, no orchestrator overhead):

| Run | p50 | p95 | p99 | max | min |
|---|---|---|---|---|---|
| 1 | 122.93ms | 174.17ms | 201.66ms | 201.66ms | 88.41ms |
| 2 | 133.85ms | 217.36ms | 431.92ms | 431.92ms | 91.75ms |
| 3 | 109.46ms | 198.22ms | 207.69ms | 207.69ms | 85.30ms |

**Verdict: p95 < 120ms is NOT met on the genuine full-compute path** — p95 clusters 174-217ms
(worse than the 120ms target by 45-95%), and even p50 (109-134ms) sits at or above it. This *is* a
real, measured improvement over the previously-documented 182ms p50 / 229ms p95 bundle-cold numbers
(that figure included Row 1+Row 2, but those cost near-nothing on real data even before F68 — so
the comparison is fair, roughly Row-3-then vs. Row-3-now): **~25-40% faster at p50, ~5-24% faster at
p95**, run-to-run. What is left is NOT the vector-fetch step this ticket targeted — see the
breakdown below — it is `resolve_eligible_articles` (the SQL hard-filter + ladder stage), unchanged
by this ticket and out of its scope to fix (composes `now_filters.hard.build_articles_hard_filter_sql`,
whose `DISTINCT ON` + `NOT IN` quality-floor subquery over 4,772 rows was already this package's own
prior diagnosis of the round-trip-cost floor, before this ticket started).

### Per-stage breakdown of the switched code, and the measured vector-fetch reduction

Same override technique, 20 real article ids, independent timers around each stage (`eligible_ids`
pool size fixed at 120 = `rerank_pool * 3` default in all runs):

| Stage | p50 | p95 | max |
|---|---|---|---|
| `resolve_eligible_articles` (hard filter + ladder SQL) | 71.99ms | 103.54ms | 112.14ms |
| `search_semantic(candidate_ids=eligible_ids)` — replaces `_restricted_semantic_knn` | 9.60ms | 13.80ms | 16.28ms |
| `FastEmbeddingSimilarity.load()` — replaces `.from_preloaded()` | 9.55ms | 10.86ms | 11.15ms |

`resolve_eligible_articles` alone accounts for roughly 70-75% of `compute_row3`'s own cost — this is
what actually dominates cold latency today, not ranking or MMR.

**The expected side benefit (fewer/smaller vector fetches) is real, measured directly, not
assumed** — apples-to-apples on the same 20 real candidate-id sets, comparing the OLD
`_restricted_semantic_knn` (reconstructed for measurement only, not reintroduced into source: one
batched `vector::text` fetch + parse for the WHOLE `eligible_ids` pool, then a numpy rank) against
the NEW `search_semantic` + `FastEmbeddingSimilarity.load()` pair:

| | p50 | p95 | max | min |
|---|---|---|---|---|
| OLD: fetch+parse ~120 vectors as text, rank in numpy | 24.48-25.82ms | 36.00-37.28ms | 37.22-38.35ms | 20.89-21.31ms |
| NEW: SQL-side exact rank (no vectors to Python) + fetch only the final 40 for MMR | 17.37-18.44ms | 24.63-28.45ms | 27.04-32.94ms | 12.64-14.25ms |

**~30% faster at both p50 and p95, consistently across repeated runs** — real, not cosmetic, and in
the expected direction: the old workaround fetched and parsed vector text for the *entire*
`eligible_ids` pool (120 by default; the docstring's own "~400" example was a wider real case) to do
its own ranking; the new path ranks that same pool in SQL and fetches vector text only for the
*final* `rerank_pool` (40) MMR needs. **Result equivalence was checked, not assumed**: for every one
of the 20 real ids tested, the top-40 id SET returned by the OLD numpy ranking and the NEW
`search_semantic` ranking were identical (script asserted this on every iteration, zero mismatches).
Order can legally differ only by float-precision rounding between numpy's cosine and pgvector's
exact `<=>` distance over the same restricted set — both are exact, over the same set, so the sets
themselves must and do match.

### Bottom line

- **Warm path**: ~3ms p50 / ~4.5ms p95 — clears 120ms with enormous margin, unchanged in shape from
  before, still never calls the embedder (verified by construction: `now_search.query_embedder
  .model_name()` is a pure constant lookup, no ONNX load; `embed_query` is never called anywhere in
  `now_rails`).
- **Cold path, as real production traffic will actually experience it today**: ~20ms p50 / ~35ms
  p95 — but this reflects F68's (correct, out-of-scope) fail-closed short-circuit on unclassified
  real content, not a fast genuine compute. This will change again, in the other direction, the
  moment E2.1 backfills real `primary_type` values and real candidates start reaching the ranking
  stage — at which point the genuine-full-compute numbers below are the ones that will matter.
- **Cold path, genuine full compute (what this ticket actually needed to know)**: ~110-134ms p50 /
  ~174-217ms p95. **120ms is not met.** The switch this ticket made (`search_semantic` +
  `FastEmbeddingSimilarity.load()`) is a real, measured ~30% win on the specific sub-step it
  targeted, but `resolve_eligible_articles`'s hard-filter + ladder SQL — untouched by this ticket,
  out of its scope, and already the prior report's own diagnosis — is 6-10x larger than that
  sub-step and dominates. The original conclusion still stands: `engine.rail_cache`'s read-through
  cache is not an optimisation, it is the mechanism by which this ticket's p95 target is reachable
  at all. `engine.rail_cache` needs a real precompute/refresh job (a scheduler this package does not
  own) to keep the warm path warm in production; see "Notes for future work" below.

## Diversity caps

`now_filters.diversity.DiversityCaps()` defaults (max 1/org, 2/area, 2/format, 1 paid/rail) are
used unmodified on every rail. Real `org_id`/`area_term` variety only exists on synthetic places
today (0/177 real places have an `org_id`); format variety only exists via the same
`synthetic_format_overlay` flag `now_blender.reranker` already established for exactly this reason.

## Fallback rung reporting

Every `RailResult` carries `rung_name`, `rung_index`, and the full `rungs_evaluated` list — the
Inspector's stated need (ARCHITECTURE.md §17: "which fallback rung each rail landed on"), cached
and fresh alike.

## CLI

    now-rails show --db now_jakarta --article-id 13 [--synthetic-overlay] [--force-refresh] [--json]

## Notes for E3.4 (Inspector wiring)

- `RailResult`/`RailItem`/`ComponentScoreOut` (`models.py`) are the shapes to adapt — `ComponentScoreOut`
  is field-for-field the same shape as `now_blender.components.ComponentScore` /
  `now_inspector.models.ComponentExplained`, so wiring is a mapping, not a redesign.
- `mmr_missing_embeddings`/`mmr_fallback_calls`-equivalent observability (`FastEmbeddingSimilarity
  .missing_keys`/`.fallback_calls`) is computed but **not yet surfaced** on `RailResult` — the same
  gap `now_blender.reranker.BlendedSearchResult` already has for its own surface. A seam, not an
  oversight; trivial to add to `RailResult` when the Inspector needs it.
- `RailsBundle.timing` (subject/row1/row2/row3/total ms) is populated on every cold compute and
  zeroed (not omitted) on a cache hit, so the Inspector can show "warm" vs. "cold" explicitly rather
  than inferring it from an absent field.

## Notes for E4.7 (promo slot injection)

- `BlendComponents.promo` is already wired through every rail's `compute_blend` call (always `None`
  today, E4 hasn't started) — the slot exists, nothing needs adding to the blend itself.
- `Candidate.is_paid` and `DiversityCaps.max_paid_per_rail` (already 1, the §8.D default) are both
  read from `now_filters` unmodified; a paid campaign only needs to set `is_paid=True` on the
  `Candidate` it builds upstream of diversify — no rail-level change.
- None of the three rails currently distinguish "organic slot" from "promo slot" in `RailItem`
  (there is no `is_paid` writer anywhere yet, E4 not started) — `RailItem.is_paid` exists on the
  model already, defaulting `False`, for exactly this reason.

## Notes for future work (not this ticket's scope)

- **A real offline precompute worker.** This package only implements read-through
  (compute-on-miss-then-cache); ARCHITECTURE.md's own diagram describes a scheduled worker
  populating `rail_cache` ahead of request time. `RailsOrchestrator.compute_rails` /
  `cache.write_rail_caches` are the exact functions such a worker would call — no new API needed,
  just a scheduler this package does not own.
- **Segments** (`DEFAULT_SEGMENT = "default"`) and **personalized re-rank**
  (`personalize.rerank_for_user`) are both explicit no-op seams, not implementations — E7.1-E7.2 gate
  them.
- ~~`now_search.semantic`'s HNSW-restricted-query bug~~ — fixed upstream (F67) and the workaround
  here retired (F70); see "A bug found while building this" above.
- **`resolve_eligible_articles`'s hard-filter + ladder SQL now dominates Row 3's own cold cost**
  (see "Performance" above, per-stage breakdown: ~70-75% of `compute_row3`'s time). Composes
  `now_filters.hard.build_articles_hard_filter_sql` unmodified — out of this package's scope to
  optimize further; flagged here for whoever next works on cold-path latency.

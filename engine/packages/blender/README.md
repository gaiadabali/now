# now-blender (E3.3 — Blender + MMR)

Implements ARCHITECTURE.md §7 (Blender) and §8.D (Diversity) on top of
`engine/packages/search/`'s hybrid retrieval and `engine/packages/
filters/`'s candidate model — both consumed, neither modified.

## F39 — the design decision (RRF vs. weighted blend)

**Decision: RRF stays the retrieval-fusion layer, unmodified. The §7
weighted blend runs as a re-ranker over RRF's fused candidate pool.**
This is the resolution PROGRESS.md's F39 flagged as "likely" — implemented,
not merely adopted on faith. Reasoning:

1. **RRF and a weighted sum solve different problems and neither
   substitutes for the other.** BM25's `ts_rank_cd` is unbounded and
   corpus/query-length-dependent; cosine similarity is bounded and,
   empirically, tightly clustered. Summing them with any fixed weight
   lets whichever rail has more spread on a given query dominate — this
   is `now_search.rrf`'s own documented reason for choosing rank-based
   fusion, and it does not stop being true just because E3.3 exists.
   Re-deriving a weighted sum straight from raw BM25 + raw cosine would
   silently reintroduce that problem one layer up.
2. **Downstream of fusion, §7's terms genuinely are comparable.** Cosine
   similarity, a 0–1 quality score, an exponential decay factor, an
   exponential proximity factor — every term `compute_blend` weights is
   already on a similar scale. A weighted sum is meaningful exactly
   where RRF's candidate pool hands off to it, and not before.
3. **§8.D's diversity_penalty is not a seventh weight — it is MMR's own
   term.** `now_filters.diversity.diversify` already implements
   `argmax λ·relevance − (1−λ)·max_sim`. This package feeds it
   `compute_blend(...).normalized_score` as `relevance`; MMR's own
   subtraction *is* §7's `− diversity_penalty`. Implementing a second,
   separate diversity subtraction inside `blend.py` would double-count
   it under a different name.

Net effect: `now_search.SearchEngine.search()` and `now_search.rrf` are
untouched (per scope) and still do exactly what they did before this
ticket; `now_blender.reranker.BlenderReranker` calls `search()` for a
wider pool (`rerank_pool`, default 40, per §7's "top ~40"), computes a
per-candidate `BlendResult`, and hands the result to `now_filters.
diversity.diversify` with a real embedding-similarity closure. Three
independently-owned, independently-tested pieces; one glue class.

## Weights — editable without deploy, proven

`sites.ranking_weights['blend']` (platform DB) holds the six §7 term
weights; `sites.ranking_weights['decay']` (already seeded by `now-db`'s
`site:create`) holds the §4 format→half-life policy. Both are read live,
on every `rerank()` call — no process-start snapshot, no cache.

Proof (`tests/test_weights_integration.py`, real Postgres, transactional
— never committed): write a distinctive weight vector directly into the
jsonb column, and `load_blend_weights()` returns exactly that vector on
the very next call. Live demonstration, actually run against the running
`now_platform` DB during this ticket:

```
$ now-blender show-weights --site jakarta
source: sites.ranking_weights['blend']
{"w_sem": 0.35, ...}

$ psql ... "UPDATE engine.sites SET ranking_weights = jsonb_set(ranking_weights,'{blend,w_sem}','0.99') WHERE slug='jakarta'"
$ now-blender show-weights --site jakarta
source: sites.ranking_weights['blend']
{"w_sem": 0.99, ...}          # <- changed, no code change, no restart
```

`seed-weights` (idempotent, mirrors `now_db.provisioning`'s own decay
seeder) has been run for real against `jakarta`/`bali`/`test` on this
dev DB so `now-blender search`/`eval` read live site weights by default
rather than the package fallback.

## Per-component scores — retained, not collapsed

`compute_blend()` returns a `BlendResult` with a `ComponentScore` per §7
term (`key`, `label`, `value`, `weight`, `explanation`, `available`) —
field-for-field compatible with `now_inspector.models.ComponentExplained`
(not imported from it; see `components.py`'s docstring for why the
dependency direction stays data→display, never the reverse). `now-blender
search --json` prints the full breakdown per hit.

## Type-aware freshness decay

Real exponential decay (`decay.py`), reading the live per-site policy.
Proven mechanically (`tests/test_decay.py`, no DB needed): news/event
decay to <1% within a year; review/listing decay slowly; guide/feature/
heritage/people/city-guide score **exactly 1.0 regardless of age**,
tested explicitly at 10 years old.

**F50 applies exactly as it did to E3.2**: `public.articles.format` is
NULL for all 4,772 real rows, so type-aware decay cannot be exercised
against real data — it is proven against a deterministic synthetic
`format` overlay (`synthetic.py`, same technique as `now_filters.
synthetic.deterministic_type`, independently applied to the 11 §4 format
terms rather than the 6 venue types). The overlay is opt-in
(`synthetic_format_overlay=True`), never silent: the production default
leaves `format=None` and freshness genuinely `None` ("not classified
yet"), which is the honest state of every real article today
(`tests/test_reranker_integration.py::test_without_synthetic_overlay_freshness_is_none_for_every_real_article`).
With the overlay on, evergreen formats score 1.0 even when
`published_at` is a decade old
(`test_synthetic_overlay_makes_freshness_available_and_evergreen_scores_one`).

## Real MMR

`now_filters.diversity`'s stand-in (`default_facet_similarity`) is
replaced by `similarity.build_similarity_fn`: one bulk query per
`rerank()` call against `engine.embeddings` (model-filtered, F42),
cached in memory, cosine computed in pure Python for every MMR pairwise
call. Verified against a direct SQL `1 - (a.vec <=> b.vec)` computation
(`tests/test_similarity_integration.py`) — not merely "runs without
crashing". Falls back to the facet stand-in, per-pair, only when a
specific candidate has no embedding row under the active model —
counted (`fallback_calls`), never silent. `λ=0.7` is a parameter
(`mmr_lambda`), defaulting to §8.D's value, imported from `now_filters.
diversity.DEFAULT_LAMBDA` rather than re-declared.

## Stage-4 feature vector, logged at serve time

All 16 §10 fields, always present (JSON `null`, never a dropped key).
`engine.impressions` (the only serve-time table that exists) is shaped
for click/impression beacon events and cannot hold a 16-field vector; a
proper `engine.ranking_features` table is a schema decision this ticket
has no authority to make (**write no migration**). So `feature_log.py`
emits one structured JSON line per (query, candidate) via Python
`logging` (`now_blender.feature_log`, INFO level) — immediately
inspectable, trivially promotable to a real ingestion job the day a
table exists. Field-by-field availability today:

| field | status | needs |
|---|---|---|
| semantic_sim | ✅ real | — |
| bm25 | ✅ real | — |
| quality | ✅ real | — |
| popularity_prior | ✅ real (mostly 0.0 — see below) | more beacon traffic |
| position_bias | ✅ real (raw position; IPW correction is a later stage) | — |
| freshness | ⚠️ real formula, `None` on real data | E2.1 classification (F50) |
| covis_score | `None` (real, empty table) | E7.3, ~50k sessions |
| type_compat, price_compat, geo_distance, same_area | `None` (no subject in plain search) | a rail with a subject entity (E3.5/E3.6) |
| user_facet_affinity, user_vec_sim, session_intent_sim, author_affinity | `None` | E7.1–E7.2 |
| seen_before | `None` unless caller supplies session state | beacon/session wiring |

`popularity_prior` is real but near-uniformly 0.0 today: `engine.
quality_scores.components.popularity.prior_score` is 0.0 for 4,473/4,772
articles (`discarded_as_bot_noise` in the same jsonb blob) — verified
directly, not assumed.

## Both nDCG numbers (F38)

`now-blender eval` (real data only — `synthetic_format_overlay=False`
throughout, see `eval_sut.py`) and `scripts/ndcg_source_excluded.py`
(mirrors QA.3's `e31_ndcg_source_excluded.py`, not edited — that script
is read-only per scope) were both run against the same 200-query
provisional set, same `now_jakarta`:

| | E3.1 (recorded) | now-blender (this ticket, measured) |
|---|---|---|
| headline (source included) | 0.7642 | **0.375108** |
| **source-excluded (number of record, F38)** | **0.0684** | **0.065276** |

**Read this honestly, per the task brief's explicit permission to report
a flat/worse result:**

- **Source-excluded — the number that matters — is flat, marginally
  lower** (0.0653 vs 0.0684, on 107/200 queries that have any peer
  signal at all once the self-match is excluded). With no facets, no
  covisitation, and no geo, the blend has exactly two real levers
  (semantic similarity, quality) plus MMR diversification — not enough
  new signal to move a metric this close to its 0.0060 floor. **This is
  not "the blend works"; it is "the blend does not regress the honest
  number, on real data, today."**
- **The headline dropped hard** (0.7642 → 0.375) — and this is
  mechanically explainable, not a bug: §7's formula has **no lexical/
  BM25 term**. RRF's candidate pool includes documents that rank #1
  purely on `ts_rank_cd` (near-exact title match — exactly what most of
  these 200 queries are, per F38), but the blend only weights cosine
  similarity, not lexical score, for the "how relevant is this"
  question. A document that won on lexical match with middling semantic
  similarity or middling quality can be — and often is — outranked by a
  document that is a strong match on both blend terms. That is §7 as
  written, faithfully implemented; it is also a real, reportable tension
  worth naming rather than quietly working around: **§7's formula, taken
  literally, discounts the exact-lexical-match signal that RRF's fusion
  currently rewards most heavily.** Whether that is correct product
  behaviour (don't just find "the document with these words in the
  title", find "the *best*, quality-weighted, semantically-matching
  document") or a formula gap (lexical match should be a term too) is a
  product/architecture call, not this ticket's to make unilaterally —
  flagged for the architect.

## Hand-check — honest read

`now-blender handcheck --db now_jakarta --site jakarta -k 6` (10
canonical queries, output captured during this ticket — see PR/ticket
notes for the full transcript):

- **Exact-shaped queries still land well**: "rooftop bar senopati",
  "best italian restaurant" surface genuinely on-topic results in the
  top 3.
- **Vague/adjective-as-location queries are still weak**
  ("coworking space jakarta", "cheap eats jakarta") — this is the same
  weakness E3.1 already documented (no filters/facets to disambiguate);
  the blend does not fix a retrieval-recall problem, because it re-ranks
  the pool RRF already built, it cannot invent a better candidate that
  was never fetched.
- **Final order is visibly non-monotonic in raw blend_score** — e.g. a
  rank-6 result can score higher than rank-5. This is MMR working as
  designed, not a bug: the greedy pick at each slot is `λ·relevance −
  (1−λ)·max_sim`, not relevance alone, so a slightly-lower-relevance,
  more-diverse candidate is correctly preferred over a near-duplicate of
  something already selected.
- **A single, exactly-on-topic top RRF result can drop several places**
  once quality is blended in (concretely checked: article 3377, the #1
  RRF hit for "rooftop bar senopati" with genuine semantic score 0.71,
  lands at rank 7 of the reranked pool because other pool members scored
  higher on the combined semantic+quality blend). This is the same
  mechanism as the headline-nDCG drop above, visible on one hand-picked
  example instead of averaged over 200 queries.

## Zero site-name literals

No production code path branches on a site slug/hostname literal —
`weights.py`/`platform.py`/`reranker.py`/`decay.py` all take `site_slug`/
`db_ref` as parameters. The strings `"jakarta"`/`"bali"`/`now_jakarta`
that do appear are: (a) test fixtures pointing at the real dev DB
(`tests/conftest.py`, `CITY_DB_REF = "now_jakarta"`) and (b) CLI
example/help text and hand-check query strings (`"cheap eats jakarta"`
is query *content*, not a branch) — the exact same pattern already
established in `now_search`/`now_filters`'s own test suites and CLIs
(e.g. `now_filters/tests/conftest.py`: `DB_REF = "now_jakarta"`). No
`if slug == "jakarta"`-shaped conditional exists anywhere in `src/`.

## What remains unvalidated (mirrors E3.2's honesty pattern)

- **Freshness, type_compat, price_compat**: real formulas, `None` on
  real data (F50 — `primary_type`/`format` NULL archive-wide). Proven
  only against synthetic overlays.
- **covis**: real query against a real, empty table (E7.3 gate, ~50k
  sessions — beacon not deployed per PROGRESS.md).
- **geo, promo**: real formulas exist (`geo.py`), unreachable from the
  search-rerank path because plain keyword search has no subject
  location — will light up the moment E3.5/E3.6 pass a subject
  `Candidate` with lat/lng.
- **user_facet_affinity / user_vec_sim / session_intent_sim /
  author_affinity**: no personalization runtime exists yet (E7.1–E7.2
  gated). Always `None`, by construction, not by omission.

## Notes for E3.5–E3.8 (the rails)

- `BlenderReranker.rerank()` is written for the search surface
  specifically (no subject entity). Row 1/Row 2/Row 3 have a subject
  place/article — `build_stage4_features`, `geo.py`'s
  `geo_distance_m`/`same_area`/`price_compat`, and `type_compat`'s
  complement-vs-competitor logic all already accept a `subject:
  Candidate` and will populate the fields that are structurally `None`
  today the moment a rail passes one in. No redesign needed, just a new
  thin orchestration class alongside `reranker.py` (or an extended
  `rerank`-shaped method) that builds a candidate pool from your rail's
  own retrieval instead of `SearchEngine.search()`.
- `now_filters.pipeline`'s own README ("Notes for E3.3 / E3.5-3.7")
  describes the `FetchFn` + `run_ladder` wiring shape for a rail with a
  fallback ladder — that composes directly with this package: run your
  ladder to get a filtered `list[Candidate]`, then feed it through
  `compute_blend` per candidate and `mmr.diversify_ranked` exactly as
  `reranker.py` does for the search pool.
- `covisitation.fetch_covis_scores` takes a `subject_entity_id` for
  exactly this reason — Row 1 is the first real consumer with a subject
  to pass.
- The Inspector's `now_inspector.models.CandidateTrace` already has
  `blended_score`/`blend_components: list[ComponentExplained]` slots
  waiting (see that file's docstring — "ready to display yours"). This
  package's `components.py` produces the field-compatible
  `ComponentScore`; wiring the Inspector up to real data is a
  now-inspector-owned follow-up, out of this ticket's scope (`Do NOT
  touch .../inspector/`).

## Quickstart

No env vars needed — the CLI reads the project `.env` (F31); never paste
a credential into a committed file (F47b).

```bash
cd engine/packages/blender
uv sync --extra dev
uv run pytest                                                          # 51 tests, real Postgres + pure-Python
uv run python -m now_blender.cli search "rooftop bar senopati" --db now_jakarta --site jakarta -k 6
uv run python -m now_blender.cli handcheck --db now_jakarta --site jakarta
uv run python -m now_blender.cli eval --db now_jakarta
uv run python scripts/ndcg_source_excluded.py
uv run python -m now_blender.cli show-weights --site jakarta
```

Connection: `NOW_PG_HOST/PORT/USER/PASSWORD` (or the project `.env`) --
same convention as `now-db`/`now-search`/`now-filters`/`now-quality`
(`now_blender/connections.py`).

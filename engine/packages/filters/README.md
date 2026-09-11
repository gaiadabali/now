# now-filters (E3.2 — Filter pipeline + fallback ladder)

Implements ARCHITECTURE.md §8 in full: hard filters (§8.A), contextual
filters (§8.B), soft/personalization down-weighting (§8.C), MMR diversity
with caps (§8.D), and the starvation fallback ladder with rung tracking
(§8.F). Selective predicates (status, type, area, radius) are pushed into
SQL against `public.places`/`public.articles`/`public.events`; expensive
per-user work runs in memory over the already-reduced candidate set
(§8.G). `engine/packages/search/`'s `search()` — `candidate_ids` and
`active_filters` — is not modified; this package produces the
`candidate_ids` that feed it.

## Quickstart

```bash
cd engine/packages/filters
uv sync --extra dev
uv run pytest       # 57 tests, real Postgres + pure-Python
uv run python -m now_filters.cli explain-places   # real SQL + EXPLAIN ANALYZE
uv run python -m now_filters.cli ladder-demo      # real ladder walk, real Postgres
```

(`uv run now-filters ...` also works once installed as a script; on some
Windows hosts an Application Control policy blocks spawning the built
`.exe` shim directly — `python -m now_filters.cli` always works.)

Connection: `NOW_PG_HOST/PORT/USER/PASSWORD` — same convention as
`now-db`/`now-search`/`now-embeddings`/`now-quality`
(`now_filters/connections.py`).

## F27 — the launch-blocking guarantee this package enforces

All 177 real `now_jakarta.places` rows currently sit at
`type='editorial'`, `subtype='city-guide'`, `status='pending_review'` — a
loader sentinel (`places.type` is `NOT NULL` and classification, E2.1,
hasn't run). Verified directly: `editorial` has `exclude_same=false` and
`complements={stay,eat,drink,wellness,shop,do,event}`, so a **venue**
wearing that sentinel is invisible to competitor exclusion in **both**
directions — it never self-excludes, and no venue type excludes it.

`hard.py`'s `status = 'active'` predicate is unconditional: it is not a
parameter, appears in every hard-filter SQL build, and is never one of
the knobs the fallback ladder relaxes. Proven against the REAL,
currently-100%-`pending_review` `now_jakarta.places` table in
`tests/test_hard_filters_status.py::test_real_active_places_filter_returns_zero`
— not a synthetic scenario, the actual live database returns zero
candidates for every subject type today.

### Recommendation: a dedicated `unknown` sentinel type

**Not implemented here — this package owns no schema.** A dedicated
`unknown` type in `engine.type_relations` with `exclude_same=true` and
**no** complements would fail closed in both directions: an
unclassified venue would (a) never be recommended as anyone's
complement, and (b) exclude itself from its own future rail once
reclassified would naturally supersede it. This is strictly safer than
`editorial`, which is a real, legitimately-permissive type for genuine
editorial content (news/opinion/city-guides) and should not be
overloaded as an "I don't know yet" sentinel.

`test_hard_filters_status.py::test_f27_mislabelled_venue_scenario` proves
the residual gap concretely: if a real hotel mislabelled `editorial` is
ever manually flipped to `status='active'` *before* being reclassified
(a plausible operational mistake, not a hypothetical), `status='active'`
alone no longer catches it — it survives the status gate and is then
genuinely invisible to competitor exclusion in both directions. The
`unknown` sentinel closes exactly that gap; `status='active'`-only closes
today's actual, narrower gap (100% of places are still `pending_review`).

## Competitor exclusion — proven to survive every fallback rung

Two independent proofs, both in
`tests/test_ladder_competitor_survives_all_rungs.py`, both against real
Postgres:

1. **The real pipeline, walked to exhaustion.** A synthetic dataset is
   engineered so the rail is starved at every rung (fewer non-competitor
   actives exist than `slots_needed`, even with the area constraint fully
   dropped), forcing `run_nearby_ladder` through all 8 `DEFAULT_LADDER`
   rungs to `editorial_fallback`. `test_every_individual_rung_raw_output_excludes_stay`
   re-runs each rung's fetch independently (not just the rung the ladder
   lands on) and asserts zero same-type competitors at every one.
2. **Defense-in-depth**, independent of `hard.py`'s own correctness:
   `ladder.py`'s `run_ladder` re-derives the excluded-type set from
   `engine.type_relations` itself and strips any competitor an adversarial
   `fetch_fn` deliberately leaks, at every rung including
   `editorial_fallback` specifically (Sec.8.F's own callout as the rung
   most tempting to implement as "just show something popular" without
   re-checking type). This proves the guarantee does not depend on every
   future rail implementation (E3.5-3.7) remembering the predicate.

Partnership tier is proven structurally incapable of affecting exclusion:
`test_hard_filters_competitor.py::test_exclusion_identical_regardless_of_partnership_tier`
— neither `hard.py`'s SQL nor `ladder.py`'s defensive re-check has any
parameter tier could enter through (ARCHITECTURE.md §11: "Competitor
exclusion is identical across all three tiers").

## Synthetic data — how, and why it's not a shadow-table trick

`articles.primary_type`/`.format` are NULL for all 4,772 rows and all 177
`places` wear the F27 sentinel, so neither real table has type/status
variety to prove discrimination. `now_filters/synthetic.py` creates
session-scoped Postgres `TEMP TABLE`s with names distinct from any real
table (`now_filters_synth_places`, `now_filters_synth_articles`,
`now_filters_synth_events`) and every `hard.py` builder takes the table
name as an explicit parameter — production code never passes a
non-default value, so there is no code path that could accidentally read
synthetic data. This is deliberately NOT the "unqualified name shadows
the real table via Postgres's implicit pg_temp search" trick (verified to
work, empirically, but rejected as a pattern here — see task history: the
search package is mid-migration away from its own `pg_temp` idiom this
wave, and an explicit table-name parameter is more legible/reviewable
than implicit schema-resolution shadowing regardless).

`deterministic_type(entity_id, seed, pool)` hashes an id to one of a type
pool deterministically (same id → same type every run), the same
technique `now_eval.datasets.type_labels` uses for its own deterministic
sampling — not copied from it (this package does not depend on
`now-eval`), independently applying the same well-known technique.

## No empty rail across a 500-article sample

`tests/test_pipeline_500_sample.py` draws the first 500 REAL article ids
(`id`, `published_at`, `series_key`, and their REAL
`engine.quality_scores` rows — E2.6 already scored all 4,772) and
overlays a SYNTHETIC `primary_type` via `deterministic_type`. For every
one of the 8 L1 types, the hard-filtered pool (competitor-excluded,
quality-floor'd, series-deduped) is non-empty, and every result is
verified competitor-clean, not just non-empty. A second test repeats this
with the real quality floor active, proving the two real filters compose
without starving the rail together.

**Explicitly NOT proven**: this says nothing about real classification
accuracy or real type distribution — see "What remains unvalidated"
below.

## What remains unvalidated until E2.1 (classification) runs

- **Every result above using real `primary_type`/`format` values is
  currently vacuous**: `build_articles_hard_filter_sql` against real,
  unmodified `public.articles` returns **zero** rows whenever a
  competitor exclusion is active for the subject type, because
  `primary_type::text != ALL(:excluded_types)` evaluates to `NULL` (→
  `false` in a `WHERE`) for every NULL-typed row. This is fail-closed by
  design (an unclassified article cannot be proven safe to show
  alongside a specific competitor-sensitive subject) and is exactly why
  the "no empty rail" criterion is tested against synthetic types, not
  live data — see `hard.py`'s `build_articles_hard_filter_sql` docstring.
  **F73/F74 (PROGRESS.md)**: this SQL behaviour was already correct, but
  `type_relations.is_competitor()` and `ladder._enforce_competitor_invariant`
  independently disagreed with it for the identical NULL-candidate input —
  one failed open, the other let `None not in {...}` slip a NULL-typed
  candidate through a defensive re-check. All three now apply the same
  rule (`type_relations.is_competitor`'s docstring has the full reasoning,
  including the `places`-vs-`articles` asymmetry): an unidentifiable
  candidate fails closed wherever the subject excludes anything at all.
  This does not change whether real content flows today (it already
  didn't) — it makes the two/three paths that decide so agree, and stop
  being silently inconsistent the moment any one of them is used alone.
- Facet-based soft signals (`facet_affinity`, muted facets) have no real
  data source yet (`engine.entity_terms` is empty, E2.2 hasn't run) —
  `soft.py` is unit-tested with synthetic `SoftSignals`, never against a
  real facet.
- Real place `quality_scores` do not exist (`entity_type='place'` has 0
  rows) — the places quality-floor predicate has real SQL and passes a
  real EXPLAIN, but its "score < floor excludes" branch is only exercised
  against synthetic data (`test_hard_filters_competitor.py`'s smoke
  fixture), never a real place score.
- Party-constraint → amenity mapping (`contextual.PARTY_AMENITY_MAP`) is
  a judgment call interpreting existing enum values, not a validated UX
  decision.
- Offer expiry (`campaigns.ends_at`) is **not implemented** — campaigns
  live in the platform DB (a second database, out of this package's
  single-DB scope, matching now-search's precedent) and don't exist yet
  (E4 hasn't shipped). A caller with a resolved expiry set can filter for
  it the same way `contextual.py`'s `SessionState` pattern works, but
  this package has no direct code path for it today. Flagged, not
  silently skipped.
- Area→district→city escalation degrades to area→city (no true district
  tier) because `places.area_term` is a flat enum — the real hierarchy
  lives in the platform DB's `terms.parent_id`, a second database. See
  `pipeline.py` module docstring.

## Recommended follow-up: composite index

`public.places` has no index on `(status, type)` — only `places_pkey`,
`places_slug_idx`, and `ix_places_geo` (GiST) exist today (verified via
`pg_indexes`; `test_query_plan.py::test_status_and_type_predicates_currently_have_no_supporting_index`
pins this down as a regression trip-wire). At 177 rows this doesn't
matter; it will once classification lands and volume grows. Not created
here — this package writes no migrations (another agent owns Alembic
this wave; `places` is Payload-owned, another schema boundary again).
Suggested for whoever next touches places' indexing:

```sql
CREATE INDEX ix_places_status_type ON places (status, type) WHERE status = 'active';
```

## Notes for E3.3 (blender) and E3.5–3.7 (the three rails)

- **Wiring shape**: build a `FetchFn` (any callable
  `RungSpec -> list[Candidate]`) around your rail's real retrieval (Row 1
  complement matching / Row 3 semantic kNN), and hand it to
  `now_filters.ladder.run_ladder(fetch_fn, subject_type=..., relations=...,
  slots_needed=...)`. You get rung tracking (`RungResult.rung_index`/
  `.rung_name`, retrievable for the Inspector per §17) and the defensive
  competitor/status re-check for free — see `pipeline.py`'s
  `build_nearby_fetch_fn`/`run_nearby_ladder` for the reference wiring
  (Row 2, the one rail shape this package could fully own end-to-end
  since it's exactly a `places` radius query).
- **`Candidate` is the contract** between this package and everything
  downstream (`models.py`). Populate `org_id`/`area_term`/`format`/
  `is_paid` on your rows before calling `diversity.diversify` — those
  four fields are what the caps key off.
- **Ordering**: call `hard.py` (SQL) → your rail's own ranking/vector
  work on the reduced candidate_ids → `contextual.apply_contextual_filters`
  → `soft.apply_personalization_hard_filters` + `soft.compute_soft_weight`
  (folded into your relevance score before MMR, not after) →
  `diversity.diversify`. This is the §8.G ordering translated into a call
  sequence.
- **MMR similarity**: `diversity.default_facet_similarity` is a
  zero-dependency stand-in. Once real embeddings are available, inject a
  cosine-similarity closure over `engine.embeddings` as `similarity_fn`
  instead — the MMR loop itself does not change.
- **Quality floor** is imported from `now_quality.scoring.QUALITY_FLOOR`
  (0.35) — one source of truth, not a second hardcoded constant. If that
  package's value changes, this one moves with it automatically.

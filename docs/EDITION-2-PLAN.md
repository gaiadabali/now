# Edition 2 — the front page, the desk, and an engine the page actually uses

**Status:** started 2026-09-24. Branch `feat/edition-2`.
**Companion to:** [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) (the look, rewritten by WS2),
[SURFACES-PLAN.md](SURFACES-PLAN.md) (S1–S7, whose open items this picks up),
[ARCHITECTURE.md](../ARCHITECTURE.md) (§4 type matrix, §7 rails, §8 filters).

## 1. The ask, in the owner's words (2026-09-24)

> Both NOW! Bali and Jakarta show the latest award-winning news layout. Fast,
> with proper animation. Professionalism meets journalism — modern, not too
> rigid and boring. The CMS and platform easy for non-developers, with all
> that is needed. The engines smart and powerful: personalization and article
> suggestions. **On a hotel story, never suggest a hotel — suggest restaurants
> and other things. On a restaurant story, suggest hotels and other things,
> never a restaurant, café or F&B.**

## 2. What is true today (measured 2026-09-24, local, both cities)

- **The suggestion rule is broken on the page, not in the engine.** The engine
  (`now_filters.type_relations`) excludes the same L1 type at every fallback
  rung. The reader site never calls it. `getRelated()` excludes the story's own
  *section* and then fills from the Guides section **by format alone** — so a
  restaurant story can be handed "10 best cafés in Canggu" (type `eat`, format
  `guide`), and a hotel story a hotel guide. The rail is labelled "Chosen by
  the engine". It is not.
- **The engine's F&B rule is narrower than the owner's.** `eat` and `drink` are
  separate L1 types and each lists the other as a *complement*. The owner's
  rule is "never restaurant/café/**F&B**" — so a bar must not be suggested on
  a restaurant story, and vice versa. That is one competitive class.
- **A rival can hide under another type.** On the Kimpton Suntaya (hotel)
  story, Read Next offers "The Westin Resort Nusa Dua presents Celebrate
  Wellness 2026" — typed `event` (ai, 0.84). Every article carries exactly one
  `type` term, and every place is still `pending_review` with the loader's
  `editorial` sentinel, so neither secondary types nor place types can catch it.
- **Every published article has an embedding** (bge-small, 4,429 Bali, 4,772
  Jakarta). Semantic Read Next and content-based personalization are possible
  in Postgres today. The beacon is collecting, but traffic is tiny (≈40 events
  per city), so learned personalization is still data-gated (E7).
- **Front page:** one 21:9 cover, then bands. The cover story is repeated as
  the Hotels lead. All headlines are Cormorant 300, which reads faint in the
  Latest index. No motion. No sticky header. At 390px the cover headline is
  clipped at the top and the nav scrolls sideways.
- **CMS:** Payload's default dashboard; no desk home, no way for an editor to
  choose the front page, no publish checklist. Platform console: partnerships
  are read-only (S5.2/S5.3 open), no classification health (S5.5).

## 3. Contracts — so four workstreams do not collide

1. **`apps/web/src/lib/recommend.ts`** — `getArticleRails(article, reader)` and
   `getForYou(reader)`. Pages render what comes back, in order, already
   labelled. Pages never build a recommendation rail of their own.
2. **`HomeRail.pins`** in `lib/site.ts` — article ids pinned to lead a home band,
   stored in `engine.sites.home_rails` (the registry, already the config spine).
   Band keys: `lead`, `edit`, `for-you`, `department:<section>`, `guides`,
   `latest`, `explore`. The desk writes them (WS3); the home page reads them (WS2).
3. **Tokens are additive during this work.** WS2 owns `tokens.css`; existing
   token names keep working because the admin reads them.

## 4. Workstreams

| | Owns | Delivers |
|---|---|---|
| **WS1 Engine** | `engine/packages/**`, `engine/apps/api/**`, Alembic, `lib/recommend.ts` | F&B as one competitive class (data, not a literal) · the hidden-rival guard · Read Next and "plan around this" rails from the engine's policy · `getForYou` · conformance tests shared by Python and TS · a full-archive check that no venue story is shown a competitor |
| **WS2 Reader** | `styles/` (not `admin.css`), `components/`, `app/(site)/**`, `DESIGN-SYSTEM.md` | the new front page, article page, section/latest/search/areas pages, motion, sticky header, mobile nav, performance budget |
| **WS3 Desk** | `app/(payload)/**` except `platform/` and `commerce/`, `packages/cms/**`, `admin.css` (own section) | desk home, front-page editor (pins + band order, with preview), publish checklist with search/social preview |
| **WS4 Platform** | `app/(payload)/team-editor/platform/**`, `commerce/**`, `admin.css` (own section) | partnership write path + audit (S5.2), blast radius (S5.3), classification health (S5.5), with access-rule tests |

Then: merge, one full gate (typecheck · build · every test suite · both
site-literal lints · smoke), QA driving both cities end to end, screenshots.

## 5. Not in this plan

Cross-city moves (S5.4 — they bridge through `now_platform`, never city to city), a reader dark
palette, learned personalization (E7, data-gated), the itinerary UI (E5.4).

## 6. WS1 (Engine) — status, 2026-09-24

**Delivered.**

- **F&B is one competitive class, as data.** `engine.type_relations` gained
  `competes_with text[]` (now-db migration 0008), seeded `eat<->drink`, and
  un-paired them from each other's `complements`. Applied to `now_jakarta`,
  `now_bali` and `now_test` (the migration carries its own idempotent data
  step, since `seed_city`'s `ON CONFLICT DO NOTHING` back-fill cannot touch
  already-seeded rows); `schema_baseline.json` regenerated.
  `now_filters.type_relations.excluded_types_for` unions `competes_with`
  unconditionally. ARCHITECTURE §4/§8 updated.
- **Hidden-rival guard.** `now_filters.hidden_rival` / `engine/apps/web/src/
  lib/hiddenRival.ts`: a `role='featured'` place mention whose NAME matches
  a competitor type's taxonomy vocabulary (`type.json` labels/aliases —
  never a hardcoded brand list) excludes the candidate even when its own
  declared type passed the ordinary check. Measured against ~250+ real,
  hand-reviewed `place_mentions`/`places` rows in both cities: the bare word
  "club" was the dominant false-positive source for `drink` and was dropped
  from the guard's lexicon only (shared curation file,
  `hidden_rival_lexicon_overrides.json`, loaded by both languages).
  Post-curation measured precision on the four venue categories is ~86%
  (n=142); real counts today are 213 Bali / 269 Jakarta published articles
  whose featured mention names a venue type their own `primary_type` does
  not declare. First-pass honest limit (closed in the second pass below):
  the literal reported article (Bali 4417) was not caught by this signal
  alone — its hotel mention is `role='mentioned'`, split across two
  unlinked `place_id` rows, an entity-extraction fragment.
- **`getArticleRails`/`getForYou`** (`apps/web/src/lib/recommend.ts`):
  computed directly against `engine.*` in the web process this iteration
  (pgvector Read Next, complement rails grouped by section, both competitor-
  and hidden-rival-filtered) rather than via the engine-api HTTP call —
  **a decision for the owner/architect to revisit**, see §7 below.
  `lib/competitorPolicy.ts` + `lib/hiddenRival.ts` are independently-tested
  TypeScript ports of the Python policy, asserted against the SAME
  conformance-vector file
  (`engine/packages/taxonomy/seed/competitor_conformance.json`) both the
  Python and TS suites load — the ONE source of truth for the exclusion
  policy the ticket required. `getForYou` builds a weighted taste centroid
  from `engine.interactions` (§10 weights) + `engine.saved_items`, kNN via
  pgvector, `null` when there is no signal. `readerContextFromRequest()`
  reads the `nowb_aid` beacon cookie and the reader session
  (`lib/reader.ts#currentReader`). `getRelated` (the old same-section
  fallback that was the reported defect) is removed from `lib/content.ts` —
  it had exactly one caller, `recommend.ts`'s own stub, replaced in the same
  change.

## 6a. WS1 second pass (coordinator review, 2026-09-24)

Four items, all closed:

1. **Article 4417 is now caught.** A second, independent signal: a
   candidate whose own `primary_type` is NOT a venue type (event/editorial/
   do, or NULL) and whose own TITLE names a subtype label/alias of a type
   the subject excludes. Same `type.json` lexicon + overrides file, no
   brand names. Hand-reviewed ~440 real title matches across both cities:
   `stay` measured ~85.5% (Bali, 59/69) / ~94% (Jakarta) precision — shipped.
   `eat`/`shop`/`wellness` measured 37–71%, dominated by this magazine's own
   recurring "Best Restaurant/Bar/Cafe Awards" franchise and abstract nouns
   ("beauty", "craft", "market", "library") naming no specific venue — **not
   shipped**; the exact noise and a proposed curated override (an awards/
   association negative-phrase exclusion for `eat`; dropping single generic
   words for `shop`/`wellness`) are recorded in
   `hidden_rival_lexicon_overrides.json` rather than silently widened.
   `drink` measured borderline (~84%, small/noisy sample, "walk into a bar"
   idiom + a Pilates-studio brand coincidence) and is also not shipped.
   Confirmed directly: article 4417 no longer appears in the Kimpton story's
   (id 4429) Read Next candidate pool (2,854 eligible candidates, checked).
2. **Speed.** `EXPLAIN (ANALYZE, BUFFERS)` found the live hidden-rival
   `place_mentions`/`places` regex join costing ~27ms of a ~49ms Read Next
   query. Moved offline: `engine.hidden_rival_flags` (migration 0009), a
   precomputed (article_id, matched_type, signal) table, refreshed by
   `now_filters.hidden_rival_recompute` — both signals (featured-mention
   and title) write into it; the live path is now an indexed lookup, not a
   regex join. Complement rails also went from up to 4 round trips to 1
   (`lib/recommendSql.ts#resolveComplementCandidates`, one query for every
   eligible section). Measured, full-archive verification (real data, both
   cities): **Bali 322ms/article → 18.2ms/article**; **Jakarta 162ms/article
   → 23.4ms/article** (~14–18×). A single Read Next query alone: ~49ms →
   ~22ms warm.
3. **Rail count and overlap.** At most 3 "plan around it" rails now
   (`MAX_PLAN_AROUND_RAILS`), ordered by the subject's own
   `type_relations.complements` array — now-db migration 0010 reordered
   that array (same membership, new position) to double as display
   priority, so the priority lives in DATA, not a TS literal per type:
   stay → dining, things-to-do, wellness; eat → stay, things-to-do, events
   (matching the coordinator's own two examples exactly). No story may
   appear in more than one rail on a page, Read Next included — "plan
   around it" resolves first and its ids are excluded from Read Next's
   pool before that rail is finalised. 6 items/rail cap unchanged. Verified
   over the full archive: 0 articles with >3 plan-around rails, 0 cross-
   rail overlaps, both cities.
4. **One copy of the SQL.** `lib/recommendSql.ts` (no `server-only` import,
   takes its `pg.Pool` as a parameter) now holds every query and row-
   shaping function; both `recommend.ts` (passing `cityPool()`) and
   `scripts/verify-competitor-policy.mjs` (passing its own bare `pg.Pool`,
   since it cannot load the CMS-config-importing `lib/payload.ts`) call the
   SAME functions. Full-archive verification re-run against this shared
   module, 2026-09-24: **Bali** 2,047 checked, 0 empty, 8,188 rails, mean
   5.84 items/rail, 0 rail-count violations, 0 cross-rail overlaps, **0
   competitor violations**, 18.2ms/article. **Jakarta** 1,632 checked, 0
   empty, 5,939 rails, mean 5.77/rail, 0/0/**0**, 23.4ms/article.

## 6b. WS1 third pass (coordinator review, 2026-09-24) — freshness

The second pass made `engine.hidden_rival_flags` fast; it did not keep it
fresh. A story published after the last recompute silently carried no
guard at all. Closed with three mechanisms:

1. **Per-article recompute on the domain-event path.**
   `now_filters.hidden_rival_recompute.recompute_flags_for_article`/
   `remove_flags_for_article` (both diff-aware and idempotent — see below)
   are called from `engine/apps/worker/app/consumer.py`'s
   `DomainEventWorker`, the SAME class and stream the re-embed worker
   already consumes (`article.published`/`.republished` recompute;
   `article.unpublished` deletes). Neither replaces the base class's own
   re-embed handling — both run. `now-filters` added as a dependency of
   `engine-worker`.
2. **Place-mentions-only changes have no event to hook.** Searched:
   `now_place_extraction` (the pipeline that writes `public.place_mentions`)
   is an offline CLI batch job (`now-place-extract run --city <city>`), not
   triggered by any CMS hook or domain event. Stated plainly rather than
   assumed away — this gap is covered by (3), up to one night's staleness,
   not by (1).
3. **Nightly full recompute as a safety net.**
   `app/jobs.py#recompute_hidden_rival_flags_job`, registered at 03:55 UTC
   (`app/main.py`), fans out over every active site
   (`app/sites.py#for_each_site`, the same pattern `ensure_partitions`
   already uses). `recompute_hidden_rival_flags` is now DIFF-AWARE (was a
   blind TRUNCATE + re-INSERT in the second pass) — it reports
   added/removed/unchanged per site and logs a WARNING when added/removed
   is non-zero, which is the "the event path missed something" signal the
   coordinator asked for.

**Freshness guarantee, stated in `recommend.ts`'s own header now:** a
newly published or republished story is excluded from rails within the
same at-least-once domain-event delivery that already re-embeds it — not
a fixed "N seconds," since it rides real event delivery rather than a
poll, but in practice within seconds of the save. A place-mentions-only
change with no article-level event is fresh within one night (the 03:55
UTC recompute). An unpublished article's flags are removed on the same
event.

**Tests.** `now_filters`: 2 new full-recompute + 4 new per-article
DB-integration tests (`test_hidden_rival_recompute_db.py`, synthetic
tables throughout — same skip-cleanly-without-`now_jakarta` convention as
every other DB-integration test in this package; genuinely exercises the
diff logic when run against a real DB). `engine-worker`: 7 new dispatch
tests for the consumer's hidden-rival handler (`test_hidden_rival_consumer
.py`, faked engine, no DB) + 2 new tests for the nightly job's per-site
diff reporting and failure isolation (`test_worker.py`); one pre-existing
test (`test_other_events_still_reach_the_re_embed_handler`) updated for
the new (additive) return-value shape.

## 7. Open for the owner/architect

- **Where rails compute.** Left as documented (coordinator: "I'll take it
  to the owner"). This iteration computes both article rails directly in
  the web tier (`lib/recommendSql.ts`), a documented exception to `lib/
  payload.ts`'s "a page may never query Postgres directly" rule, made
  because (a) the engine-api's existing `/articles/{id}/rails` endpoint
  serves Row 1 as PLACES, not the ARTICLE-shaped "plan around it" rail this
  ticket specifies, and (b) this sandboxed session had no way to verify
  `ENGINE_API_URL` reachability. Wiring the HTTP call as the preferred path,
  with this implementation kept as the graceful-degradation fallback, is
  the natural next step.
- **F&B-on-F&B for a hidden rival specifically raised, not decided:** an
  `eat`-typed article titled "...at Sofitel Bali Nusa Dua Beach Resort" on
  a `stay` subject's page stays eligible — venue-typed candidates are
  untouched by the title signal, unchanged from the first pass. Whether a
  rival hotel's own restaurant write-up should count as a `stay` competitor
  is the owner's call, raised, not engineered around.
- **`eat`/`shop`/`wellness` title-signal overrides** (item 1 above) are
  documented, not implemented — a follow-up once someone signs off on the
  proposed curation.
- **`getForYou`'s label** ("Because of what you read") does not yet name a
  specific driving article — a weighted-centroid taste vector does not
  preserve per-item provenance the way a top-1-nearest-neighbour approach
  would.

## 8. Integrated state, 2026-09-24 — what was proven, and how to ship it

All four workstreams are merged on `feat/edition-2`. Measured on the merged
branch, production build (`output: standalone`), both cities, local DBs:

| Check | Result |
|---|---|
| Web typecheck · tests · site-literal lint · account-gate lint | clean · **62/62** · clean · clean |
| CMS tests · CMS site-literal lint | **51/51** · clean |
| Python, against the real DB (filters · worker · link-resolver · rails) | **123 · 61 · 31 · 18**, 0 skipped |
| `scripts/smoke.sh`, both cities | **39/39** |
| `verify:competitor-policy` (shared SQL module), every venue story | Bali 2,047 · Jakarta 1,632 — **0 violations**, 0 empty, 5.88 / 5.60 items per rail |
| Rendered-page crawl, every venue story, rail items read from the HTML | Bali 2,047 pages · Jakarta 1,632 — **0 competitor items** in 81,375 |
| Desk pin → home page | a registry pin led the live home page within the 30 s TTL, once, in the saved band order |

`apps/api` tests need the dedicated test Postgres on :55510 (`now-api-test`,
torn down under F4); `apps/api` is unchanged on this branch.

**Found by the integration pass, not by any workstream's own checks**, and fixed:

- The plan-around rails checked `hidden_rival_flags` against the rail's own
  types instead of the subject's exclusions, so it never fired: 2,895 rival
  items on rendered Bali pages while the SQL-level proof passed. The proof
  now checks type, untyped-fails-closed and rival flags on every rail.
- Three legacy addresses with non-ASCII characters 404ed (percent-encoded
  in the DB, decoded by Next).
- The front-page editor seeded a never-saved site with twelve bands; the
  first Save would have replaced the home page with six department bands in
  a row. It now starts from `lib/homeBands.ts`, the home page's own default.

**Owner decisions, 2026-09-24.** F&B (eat + drink) is one competitive class.
A restaurant or spa inside another hotel is fine on a hotel story as long as
that hotel is not the story's main topic — which is what the rule already
keys off (own type, featured venue, and headline for non-venue types).

**Deploy order — migrations before the image, every one additive:**

1. now-db Alembic `0008` (`type_relations.competes_with` + eat/drink data),
   `0009` (`engine.hidden_rival_flags`), `0010` (complements reordered as
   display priority) — on every city DB, via `site:migrate`.
2. Populate the flags once: `now_filters.hidden_rival_recompute` per city
   (the worker keeps them fresh from then on; nightly job at 03:55 UTC).
3. Payload `20260924_111729_articles_created_by` on every city DB (SQL twin:
   `packages/cms/scripts/articles-created-by.sql`). The new image selects
   `articles.created_by`; without the column every article query 500s while
   `/healthz` stays green — the S1.1 trap again.
4. Roll the web and worker images. Smoke, then `verify:competitor-policy` per city.

## 9. WS6 — Embeddings (2026-09-25)

**The question.** The roadmap asks for "a stronger multilingual embedding
model, for better similarity across English and Indonesian". This section is
the measurement. **Decision: stay on `BAAI/bge-small-en-v1.5`.** No candidate
beats it on the English search or related-article ground truth. The one
large win is on Indonesian queries, which the archive and its readers do not
currently produce. The model is now a single config value, so a later switch
is a config change plus a backfill.

### Corpus facts (census of every published article, both cities)

| | Bali (4,429) | Jakarta (4,772) |
|---|---|---|
| English / mixed / Indonesian, **langdetect** per segment | 97.13% / 2.53% / 0.34% | 98.41% / 1.55% / 0.04% |
| same, **Indonesian function-word rate** (independent check) | 99.93% / 0% / 0.07% | 99.98% / 0.02% / 0% |
| agreement between the two instruments | 97.2% | 98.4% |
| full body instead of the embedded prefix (langdetect) | 97.04% / 2.62% / 0.34% | 98.41% / 1.57% / 0.02% |
| articles naming an Indonesian loanword/place (warung, nasi, Ubud, ...) | 52.2% | 15.2% |
| embedded text, median chars | 1,794 | 1,689 |
| tokens, median / p90 / >512: bge-small (WordPiece) | 377 / 420 / 0.07% | 362 / 407 / 0.02% |
| tokens, median / p90 / >512: e5 and bge-m3 (XLM-R) | 421 / 462 / 0.05% | 400 / 447 / 0.10% |
| Yoast focus keywords containing an Indonesian function word | 8 of 2,856 (0.28%) | 2 of 1,136 (0.18%) |
| logged reader searches (`engine.interactions.query`) | 2, English | 3, English |

**What gets embedded** (`textbuild.build_article_text`): title, dek, then
`type:`/`format:`/facets when present, then the first 1,600 characters of
visible body text. Terms are `"<facet>: <label> (<slug>)"`. Almost nothing is
truncated at 512 tokens under any of the tokenizers.

The "mixed" and "Indonesian" buckets are mostly English articles that quote
Indonesian: temple calendars full of *pura* names, and Ramadan listings.
langdetect segments text into sentences and needs about 20 letters per
segment, and name-dense lines fool it. The function-word check is stricter
and finds almost no Indonesian prose. So the corpus is English, and a
multilingual model can only help through **Indonesian queries**. None have
been logged yet.

### Candidates, and why

| Model | Dim | Why it is in the comparison |
|---|---|---|
| `BAAI/bge-small-en-v1.5` | 384 | the live model (baseline) |
| `intfloat/multilingual-e5-small` | 384 | the only multilingual model that fits the existing `vector(384)` column, so a switch needs no migration |
| `BAAI/bge-m3` | 1024 | the strongest widely used multilingual model that runs on CPU (ONNX export, fastembed custom model) |
| `BAAI/bge-base-en-v1.5` | 768 | the English control: if the corpus is English, a larger English model is the honest alternative |

All four run through `fastembed`/ONNX (no torch), via `now_embeddings.models.REGISTRY`.

### Method

- **Slice.** Embedding the full corpus with bge-m3 is not feasible here: it
  took 1.0 s per article on the Bali pass (827 s for 800), and the Jakarta
  pass took 7.8 h because the host slept or throttled partway through. So every model was embedded on
  the same frozen **800-article slice per city** (`compare_embedding_models
  make-slice`). The slice holds every article a query or classifier label
  points at, about 200 articles in whole same-venue groups, and a hash
  sample for the rest. It also holds all 407 terms. Absolute scores on 800
  articles are higher than on the full corpus. Only the differences between
  models are the result. The live model was scored twice: on its stored
  vectors (`--from-db`) and on a fresh re-embedding (`@fresh`). The stored
  vectors are what production serves. Both are baselines.
- **Search.** The production lexical leg (`now_search.lexical`, restricted to
  the slice) plus each model's exact-cosine semantic leg, fused with
  production RRF (k=60). Before any comparison, the offline pipeline for the
  live model was checked against the real `SearchEngine` on the full corpus:
  **100/100 identical top-10s in each city.** Query sets:
  - every distinct focus keyword (518 Bali, 216 Jakarta after the slice
    cut);
  - 128 topic-shaped focus keywords with a hand-written Indonesian twin
    (`eval/data/search_queries.crosslingual_id.jsonl`, provenance in
    `eval/data/PROVENANCE.md` §9; no native-speaker review yet);
  - the harness's provisional set (Jakarta).

  Significance is a paired bootstrap on per-query nDCG@10, 2,000 resamples,
  95% interval.
- **Related articles.** Four checks:
  - same featured venue: the other articles featuring the same place should
    rank in the top 10;
  - series siblings: only 1 group in the slice, so not usable;
  - editor primary category: now-eval's labelled set, precision@6;
  - classifier: F120 centroid 5-fold CV and term zero-shot accuracy on the
    253 adjudicated labels.

  Plus a **blind hand-label pass**, described below.
- **Latency and size.** The `recommendSql.ts` Read Next query was run
  verbatim against a session-local TEMP copy of `engine.embeddings`, over
  the full row count, 200 subjects, with serial HNSW builds. The shared
  table was never written. Read Next sorts exactly, so its cost depends on
  width and row count, not on what the vectors mean. The 768-d and 1024-d
  rows are therefore random vectors at full size.

**Hand labels.** 24 seeds (12 per city) were drawn by hash from the slice.
For each seed I pooled every model's top 2 neighbours, which gave 121
distinct pairs. I shuffled them and graded them blind, reading the seed and
candidate title, dek and lead with no model attribution, and unblinded only
after grading:

- **2**: a reader would want it next (same venue or brand, same event or
  series, same narrow subject);
- **1**: same broad subject or genre;
- **0**: unrelated, or linked only by a word or format.

Labeller: the WS6 agent. Grades are in
`eval/data/related_articles.handlabel_ws6.jsonl`.

### Results

**(a) Search, hybrid nDCG@10 (recall@10)** on the 800-article slice. Δ is
the change against bge-small's stored vectors, with its 95% interval.
**Bold** marks an interval that excludes 0.

| Query set | bge-small (stored) | e5-small | bge-base | bge-m3 |
|---|---|---|---|---|
| Bali focus keywords (518) | 0.909 (0.981) | 0.876 · **Δ −0.034** | 0.902 · Δ −0.007 | 0.907 · Δ −0.002 |
| Jakarta focus keywords (216) | 0.929 (0.986) | 0.926 · Δ −0.003 | 0.935 · Δ +0.006 | 0.937 · Δ +0.007 |
| Bali topic queries, English (62) | 0.947 (1.000) | 0.919 | 0.935 | 0.956 |
| Jakarta topic queries, English (66) | 0.938 (0.977) | 0.919 | 0.935 | 0.941 |
| Bali, same queries in **Indonesian** (62) | 0.280 (0.323) | **0.680 (0.807)** | 0.337 | **0.854 (0.952)** |
| Jakarta, same queries in **Indonesian** (66) | 0.366 (0.462) | **0.784 (0.894)** | 0.458 | **0.854 (0.947)** |
| Jakarta harness provisional set (119) | 0.315 | 0.321 | 0.312 | 0.310 |

The deltas in the table are against bge-small's stored vectors. The
bootstrap intervals were computed against the fresh re-embedding; against
it, bge-m3's Indonesian gain is +0.59 in Bali and +0.48 in Jakarta, and
e5-small's is +0.41 in both, all significant. No English-query difference
between bge-m3 or bge-base and bge-small is significant in either city.
e5-small is significantly worse on Bali focus keywords (−0.039) and on Bali
English topic queries (−0.042). The same live model on stored versus fresh
vectors differs by at most 0.014.

Full-corpus figures for the live model: Bali 0.831, Jakarta 0.878 (focus
keywords); Jakarta provisional set 0.774. In Bali "hybrid" is semantic only:
`now_bali.engine.article_search` has 0 rows, so the lexical leg returns
nothing there. That is a follow-up, not a WS6 change.

**(b) Related articles**

| | bge-small (stored) | e5-small | bge-base | bge-m3 |
|---|---|---|---|---|
| Same featured venue, nDCG@10, Bali (258 seeds) | 0.678 | 0.634 · **Δ −0.039** | 0.697 · **Δ +0.024** | 0.665 · Δ −0.008 |
| Same featured venue, nDCG@10, Jakarta (242 seeds) | 0.632 | 0.596 · **Δ −0.034** | 0.663 · **Δ +0.034** | 0.648 · Δ +0.019 |
| Primary category precision@6, Jakarta (37 seeds) | 0.243 | 0.225 | 0.239 | 0.248 (all n.s.) |
| Classifier centroid CV accuracy, type (111) / format (142) | 0.595 / 0.458 | 0.667 / 0.437 | 0.640 / 0.472 | 0.658 / 0.444 |
| Term zero-shot accuracy, type / format | 0.351 / 0.162 | 0.243 / 0.155 | 0.315 / 0.148 | 0.306 / 0.197 |
| **Hand labels**, mean grade 0–2 (48 top-2 slots each) | 1.208 | 1.104 | 1.208 | 1.271 |
| Hand labels, share graded ≥1 / graded 2 | 0.79 / 0.42 | 0.69 / 0.42 | 0.77 / 0.44 | 0.79 / 0.48 |

In this table Δ and its interval are against the fresh re-embedding of
bge-small (0.673 in Bali, 0.630 in Jakarta), not the stored column shown.
The hand-label sample is small (48 slots per model, one labeller). It
agrees with the venue proxy: e5-small is the weakest, and bge-m3 and
bge-base are level with or slightly above bge-small. It shows no clear
winner.

**(c) Cost** (this machine, 16 cores. Embedding runs were benchmarked with
no other embedding job running, but host load was not otherwise controlled)

| | bge-small | e5-small | bge-base | bge-m3 |
|---|---|---|---|---|
| Embed, ms per article (batch, 16 threads) | 115 | 108 | 222 | 618 |
| Embed one query, p50 / p95 ms (4 threads, the search path) | 3.3 / 4.0 | 4.3 / 5.6 | 10.9 / 12.7 | 39.9 / 46.7 |
| Read Next SQL p50 / p95 ms, Bali, full row count | 10.2 / 15.3 | same width as bge-small | 19.2 / 34.7 | 22.9 / 37.7 |
| Read Next SQL p50 / p95 ms, Jakarta | 12.9 / 19.5 | same width | 20.3 / 33.7 | 25.3 / 40.8 |
| Bytes per row, table + HNSW | 3,864–3,873 | same | 8,432–8,449 | 13,919–13,931 |
| Articles-only table + index, Bali / Jakarta | 17.2 / 18.4 MB | same | 37.4 / 40.2 MB | 61.7 / 66.4 MB |
| Fits `engine.embeddings.vec vector(384)` | yes | **yes** | no, needs a migration | no, needs a migration |

With both 384-d models in one graph (800 + 800 rows per city), the live
model's approximate HNSW path returned a short result in 0 of 200 probes
per city. Coexistence is safe at this scale.

### Decision

**No switch.** The brief's bar is a clear win on both search (a) and
related articles (b), at acceptable cost (c). None of the candidates clears
it:

- **bge-m3** ties bge-small on every English measure: focus keywords, topic
  queries, venue proxy, primary category and hand labels. On Indonesian
  queries its nDCG@10 is 2.3 to 3.1 times bge-small's (0.854 against 0.366
  and 0.280). It costs 5.4 times more per article,
  12 times more per query embed (40 ms on the search p95 path), about 2
  times more Read Next latency and 3.6 times more storage, and it needs a
  migration.
- **e5-small** is the only candidate that needs no migration. It is
  significantly worse on English search in Bali and on the venue proxy in
  both cities. Buying Indonesian recall with English quality on an English
  corpus is the wrong trade.
- **bge-base** is the only candidate with a significant English win (+0.024
  and +0.034 on the venue proxy). It shows none on search, and it needs a
  migration and 1.6 to 1.9 times the Read Next latency.

**When to revisit.** Revisit if real Indonesian queries appear. Logged
searches (`engine.interactions.query`) are the signal to watch. At that
point bge-m3 is the model to move to. It needs a senior-db-reviewed
migration first, because `vec` is fixed at `vector(384)`: for example a
separate `engine.embeddings_1024` table with its own HNSW index. That is not
built here.

### The config point (off by default)

- `engine/packages/embeddings/src/now_embeddings/models.py`: `REGISTRY`,
  `DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"`, and the `NOW_EMBEDDING_MODEL`
  env override. An unregistered name raises an error. A model wider than
  384-d is refused by the backfill, the worker and the CLI.
- These readers follow it: the backfill and `now-embeddings` CLI (`--model`),
  the publish worker (`_provider("local")`), `now_search.query_embedder`
  (which applies e5's `query:` marker), and the web tier's Read Next via
  `apps/web/src/lib/embeddingModel.ts`. `recommendSql.ts` changed only its
  constant. `tests/test_models.py` pins the web fallback literal to
  `DEFAULT_MODEL`.
- These stay **pinned on purpose**: the classifier's F120 centroid routing
  (`now_taxonomy_evidence.vectors`) and `now_eval.calibration.embed_data`.
  Their artifacts were trained in bge-small's space. If they followed the
  switch, they would compare vectors across two spaces, and nothing would
  error. The same test pins them to the default.

**Rollout, if a later decision says switch** (the model must be registered
and 384-d, or have a reviewed migration):

1. `uv run python scripts/rollout_embedding_model.py backfill --model <m>`
   in `engine/packages/embeddings`. It writes new rows under the new model
   and leaves the old rows alone.
2. `... rollout_embedding_model.py check --model <m>`. It exits non-zero
   unless every published article in every city has a row.
3. Rebuild the classifier centroids with `eval/scripts/build_routing_centroids.py`
   and re-measure F120 (`f120_routing_report.py`), then update the two
   pinned literals.
4. Set `NOW_EMBEDDING_MODEL=<m>` on web, engine-api and worker, restart them,
   then run `verify:competitor-policy` per city.

**Rollback:** unset `NOW_EMBEDDING_MODEL` and restart. The bge-small rows
are never modified by a backfill under another model. While the new model
was live, the worker embedded new articles only under the new model, so run
`now-embeddings backfill --city <db> --model BAAI/bge-small-en-v1.5` after
rolling back. Until then those articles' Read Next rails are empty, not
wrong.

**Storage this work added to the shared databases: 0 bytes.** No rows were
written. Candidate vectors live in local files. The TEMP tables were
session-local and dropped.

**Found along the way:**

- 4,253 of 4,429 Bali and 4,275 of 4,772 Jakarta stored bge-small vectors
  have a `text_hash` that no longer matches the article's current text: they
  predate the classification fill. A re-embed moves the scores by at most
  0.014 nDCG, but it is still owed. It is a plain `now-embeddings backfill`
  per city, which rewrites the live model's rows, so it was not run here.
- Bali's `engine.article_search` is empty.
- The first latency run built a 1024-d HNSW index with parallel workers and
  took the shared Postgres into crash recovery once (container `/dev/shm`
  is 64 MB). The script now builds serially. The container was later found
  exited (137); it is not known what caused that.

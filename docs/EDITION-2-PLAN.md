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

## 9. WS1 fourth pass (2026-09-24) — stated preferences, session intent, covisitation, A/B

The owner's ticket: "use the preferences readers choose at sign-up," plus
building out the rest of the §10 roadmap now that the sign-up picker
(`lib/preferences.ts`, `engine.identities.stated_prefs`) has been live long
enough to have real picks in it. Six pieces, all on `apps/web/src/lib/
recommend.ts` (+ two new sibling modules) and `engine/apps/worker`:

1. **Stated preferences drive "For you" from the first visit.** §10's
   `α = n_meaningful/(n_meaningful+20)`, `taste = α·revealed +
   (1−α)·stated_seed` — a reader with zero clicks gets `taste =
   stated_seed` outright, not a null rail until 20 interactions accumulate.
   `stated_seed` (new: `loadStatedSeed` in `recommend.ts`) is the mean of
   the picked terms' own embeddings (`engine.embeddings` entity_type='term'
   in the PLATFORM db), blended with the article centroid where
   `entity_terms` coverage exists for that facet — today `type` (75–82%)
   and `location` (full); `topic`/`audience`/`price_band` are 0% pending a
   parallel WS5 tagging effort, so a picked topic still contributes its own
   term embedding, just no article centroid yet. A soft re-rank bonus
   (never a hard filter, §8.C) nudges matching `type`/`location` picks.
   Label is honest about which side won: "Because you like {terms}" vs
   "Because of what you read" (`labelFor`, `lib/taste.ts`).
2. **Anonymous readers.** `app/(site)/page.tsx` called `currentReader()`
   and handed `getFrontPage` only `{ identityId }`, dropping the beacon's
   `anonId` — "For you" could never fire before sign-up however much
   history existed. Now calls `readerContextFromRequest()`
   (`lib/recommend.ts`, already existed, was simply not used here).
3. **Session intent.** §5's `taste_vec_short`: the current session's reads
   (last 30 minutes, by `anon_id`/`user_id`) blended at `β=0.6` (3+
   qualifying reads this session) or `β=0.2` (fewer). Blended into "For
   you" unconditionally; blended into Read Next's ORDER ONLY (pool and
   exclusions unchanged) behind the `read-next` A/B experiment (item 5),
   so its effect is measured, not assumed.
4. **Covisitation.** `engine.covisitation` was real, read-wired
   (`now_blender.covisitation`), and had 0 rows in every city — nothing
   ever wrote to it. New: `now_filters.covisitation_recompute
   .recompute_covisitation`, a full nightly recompute (worker cron, 04:15
   UTC) from `engine.interactions`, diff-aware like the hidden-rival job.
   Blended into Read Next's order unconditionally when rows exist for a
   subject; a new "Readers also read" rail appears on the article page
   ONLY when ≥3 competitor-clean covisited items clear the score floor
   (`MIN_READERS_ALSO_READ`, `meetsReadersAlsoReadFloor`) — hidden, never
   padded, below it (S2 honesty rule applied to a rail's existence). The
   verify script checks this rail with the same type/untyped/hidden-rival
   guard as every other rail.
5. **A/B testing.** `lib/experiments.ts`: deterministic `anon_id`-hash
   bucketing, variants as data (`ACTIVE_EXPERIMENTS`). One experiment
   wired: `read-next` (`control` vs `session-intent`). The beacon contract
   is frozen, so the variant rides inside the existing `rail` value —
   `<rail>~<variant>`, only while active for that reader; no suffix means
   no experiment. WS4's dashboard reads this convention directly.
6. **Proof.**
   - Unit tests: `test/taste.test.ts` (α at 0/20/past-20, the three-way
     blend branch, the honest label, incl. the exact-0.5 boundary),
     `test/experiments.test.ts` (deterministic bucketing, spread across
     variants, the suffix rule), `test/recommendSql.test.ts`
     (`meetsReadersAlsoReadFloor` at/below the line).
   - `engine/packages/filters/tests/test_covisitation_recompute_db.py`:
     directional scoring, `min_support` floor, unqualified dwell/scroll
     excluded, idempotent re-run, stale-pair removal — DB-integration,
     synthetic tables, skips cleanly without a DB.
   - `engine/apps/worker/tests/test_worker.py`: the new cron job's
     per-site reporting, failure isolation, and that it is actually
     registered on `WorkerSettings` (not just defined — see this repo's
     own `run_forever`-vs-`run` postmortem for why that check exists).
   - Gates re-run after this pass: web typecheck clean, web tests
     **83/83** (was 62), `lint:site-literals`/`lint:account-gate` clean,
     `now_filters` **128/128** (was 123), `engine-worker` **64/64** (was
     61). `verify:competitor-policy`: Bali 2,047 articles, **0
     violations**, 14.6ms/article warm; Jakarta 1,632 articles, **0
     violations**, 40.8ms/article warm (some individual queries hit the
     script's own 10s statement timeout under this session's concurrent
     multi-agent DB load — not reproduced in isolation, flagged rather
     than hidden).
   - Synthetic-reader demonstration:
     `engine/apps/web/scripts/demo-stated-prefs.mjs` — creates a throwaway
     `engine.identities` row with `stated_prefs = {interests:['wellness'],
     areas:['ubud']}` on the platform DB, calls `getForYou` for it, reports
     the share of returned items matching the picked type/area against the
     base (unpersonalized-population) rate, then deletes the row. Run
     manually (writes to the platform DB; not part of the CI gate).

### Follow-ups flagged, not solved

- `n_meaningful` is computed on read (count of qualifying 180-day
  interactions) rather than a persisted `user_profiles.n_meaningful`
  counter — no writer for that column exists yet.
- The Read Next re-rank's "how good was the subject-similarity order"
  input is a rank-based proxy, not the raw cosine distance (that SQL never
  needed one before this pass) — fine for a small pool, worth revisiting if
  the blend weights ever need tuning against real click data.
- `read-next`'s A/B variants are not yet analysed anywhere — WS4's
  dashboard reads the beacon convention this pass establishes, but nobody
  has looked at the numbers yet.

## 10. WS5 (Tagging) — topic/audience/vibe/cuisine/price_band/occasion, 2026-09-24/25

F137: the preference picker (`engine/apps/web/src/lib/preferences.ts`) offers
topics, personas (audience) and budgets (price_band); vibe/cuisine/occasion
feed §9's filters and facet_affinity. All six measured at **zero** tagged
articles in both cities before this work (`select count(*) from
engine.entity_terms where term_id = any(<the 139 term ids for these six
facets>)` — 0 in `now_bali`, 0 in `now_jakarta`, confirmed live, not just
quoted from F137). No LLM is available (the shared Ollama Cloud key is
Unauthorized; no Anthropic key exists), so the primary method is entirely
local: lexical + embedding evidence, calibrated against a hand-labelled
sample. New package code lives in `engine/packages/classifier/src/
now_classifier/facet_tagging/` (a subpackage of the existing classifier, not
a new package — it shares vocabulary loading, DB settings and the
title/lead/body zone-trust convention `now_taxonomy_evidence.text` already
established).

### Method

For the five facets with real vocabulary aliases (topic, audience, vibe,
cuisine, occasion — `engine/packages/taxonomy/seed/terms/*.json`), every
article↔term pair is scored on:

1. **Lexical zone** (`lexicon.py`): a literal, word-boundary match of the
   term's label or any alias, checked title → dek/lead(400 chars) →
   body(400-1600 chars), reported as whichever zone is strongest (title
   beats lead beats body) — the same trust ordering
   `now_taxonomy_evidence.text`'s location matcher already uses ("a name in
   the headline is a stronger, more deliberate editorial signal").
2. **Embedding similarity** (`embed.py`), only when no lexical zone matched:
   direct cosine between the article's own embedding (`engine.embeddings`,
   `BAAI/bge-small-en-v1.5`, already backfilled for all 4,429 Bali / 4,772
   Jakarta published articles) and the SAME model's embedding of the
   candidate term (also already present, per-city, `entity_type='term'`,
   407 rows in each city DB — no cross-DB join needed). A few-shot centroid
   path (`build_facet_centroids`, reusing
   `now_taxonomy_evidence.embed_similarity.build_trusted_centroids`, the
   same machinery `now_classifier.embed_routing` uses for type/format) is
   implemented and tested but not used in production this round: at
   ~90-100 labelled positives per facet spread across 15-44 terms, almost
   no term reaches the `min_class_n=5` exemplar floor — disclosed as a
   follow-up, not silently skipped.

`price_band` has no lexical vocabulary at all (its labels are literally
"$".."$$$$") — `price_cues.py` is a small, hand-authored keyword-cue
instrument in the exact shape of `now_taxonomy_evidence.text.TYPE_CUES`
(regex/weight, zone-weighted, argmax + abstain), since `price_band` is
single-cardinality like `type`/`format`, not multi like the other five.

**Scope** (`scope.py`): `cuisine` only on `eat`/`drink` articles;
`price_band` only on venue types (`stay`/`eat`/`drink`/`wellness`/`shop`,
reusing `now_taxonomy_evidence.text.VENUE_TYPES`); the other four apply to
every article, per the ticket spec.

### Calibration — how, and the full precision table

For each facet, `scripts/build_calibration_sample.py` drew a **seeded
random, stratified sample of 100 candidates** (25 per band: title / lead /
body / embed_only; or 50 each of cue_confident / cue_fired for
`price_band`) from the full published archive of BOTH cities — not
cherry-picked. Hansel read each candidate's title + dek/excerpt + opening
text and judged, one at a time, whether the proposed term genuinely applies
— yes/no, no partial credit — recorded in a labels file.
`scripts/score_calibration.py` computes precision = true / n per band.
Ship bar: **precision ≥ 0.80** (`calibration.SHIP_AT_OR_ABOVE`). A band that
misses it is never written — its candidates are simply dropped, not queued
for review (this job never touches `classification_reviews`, so the
6,442-item pending queue is untouched).

| Facet | Band | n | precision | Ship? |
|---|---|---:|---:|---|
| topic | **title** | 25 | **0.80** | **YES** |
| topic | lead | 25 | 0.44 | no |
| topic | body | 25 | 0.20 | no |
| topic | embed_only | 25 | 0.04 | no |
| vibe | **title** | 25 | **0.92** | **YES** |
| vibe | lead | 25 | 0.72 | no |
| vibe | body | 25 | 0.20 | no |
| vibe | embed_only | 25 | 0.00 | no |
| cuisine | **title** | 25 | **0.84** | **YES** |
| cuisine | lead | 25 | 0.52 | no |
| cuisine | body | 25 | 0.04 | no |
| cuisine | embed_only | 25 | 0.00 | no |
| audience | title (raw, "local" included) | 25 | 0.56 | no |
| audience | **title, excl. "local"** | 13 | **0.92** | **YES** |
| audience | lead | 25 | 0.44 | no |
| audience | body | 25 | 0.12 | no |
| audience | embed_only | 25 | 0.04 | no |
| occasion | title (raw, "date-night" included) | 25 | 0.72 | no |
| occasion | **title, excl. "date-night"/"anniversary"** | 19 | **0.95** | **YES** |
| occasion | lead | 25 | 0.56 | no |
| occasion | body | 25 | 0.04 | no |
| occasion | embed_only | 25 | 0.00 | no |
| price_band | **cue_confident** | 50 | **0.86** | **YES** |
| price_band | **cue_fired** | 50 | **0.84** | **YES** |

**A repeated, not facet-specific, finding**: `embed_only` (no lexical hit,
bare direct-term-embedding cosine ≥ 0.45) measured 0.00–0.04 on every one
of the five alias-based facets. A term embedded as `"vibe: trendy
(trendy)"` (`now_embeddings.textbuild.build_term_text`) is not semantically
specific enough on this corpus to beat "generic hospitality article" —
confirmed by five independent measurements landing in the same place, not
assumed. `body`-only lexical evidence never cleared the bar either
(0.04–0.20 everywhere it was measured). **Title-zone literal matches are
the only signal, of everything measured, that consistently works.**

**Two disclosed alias exclusions** (`calibration.ALIAS_EXCLUSIONS`), each
found by reading the false positives in the raw sample, not guessed:
- `audience`/`local` — excluded ENTIRELY (label too, not just its
  aliases). "Local" is an ordinary English adjective ("local flavours",
  "local diners") that appears constantly in hospitality copy having
  nothing to do with the AUDIENCE meaning ("this piece targets residents,
  not tourists"). Measured on its own: 2/12 title, 1/13 body, 0/2
  embed_only — nowhere near the bar, and large enough (40 of the original
  100 audience candidates) to sink the whole `title` band by itself (raw
  0.56; 0.92 with it excluded).
- `occasion`/`date-night`'s `anniversary` alias only (its other aliases —
  Valentine's, romantic dinner — are untouched, though none happened to be
  measured in this sample; they simply never fired). Every one of 6
  `date-night` title hits in the raw sample was a HOTEL'S OWN business
  anniversary ("celebrating its 8th anniversary"), never a reader's
  romantic occasion. 0/6 on its own; excluding just that alias moves
  `occasion`/title from 0.72 (18/25) to 0.95 (18/19).

**Approximate recall** (true positives in the shipped band ÷ true positives
found across ALL measured bands in the same sample — the honest ceiling
this method can even see; an article with a true tag but zero lexical or
embedding signal anywhere is invisible to this estimate and to the shipped
job alike): topic ≈ 20/37 = 54%, vibe ≈ 23/46 = 50%, cuisine ≈ 21/35 = 60%,
audience and occasion are similar order (title-only, so recall is real but
modest — most true instances live in the lead/body zones this method
correctly declined to ship). `price_band`'s cue instrument fires or
abstains per-article (no separate "did we even look" step), so this ratio
isn't meaningful there; both its firing bands ship.

### Counts written, both cities (source `inferred`, confidence = the measured
precision above)

| Facet | Bali articles (of 4,429) | Bali rows | Jakarta articles (of 4,772) | Jakarta rows |
|---|---:|---:|---:|---:|
| topic | 1,012 (22.8%) | 1,184 | 1,410 (29.5%) | 1,632 |
| audience | 180 (4.1%) | 181 | 198 (4.1%) | 199 |
| vibe | 534 (12.1%) | 581 | 477 (10.0%) | 503 |
| cuisine | 324 (7.3%) | 353 | 300 (6.3%) | 318 |
| price_band | 657 (14.8%) | 657 | 521 (10.9%) | 521 |
| occasion | 385 (8.7%) | 423 | 456 (9.6%) | 548 |
| **total** | | **3,379** | | **3,721** |

Before: 0 rows, 0 articles, every facet, both cities (measured, see above).

### Picker-combination matches (before → after)

| Combination | Bali | Jakarta |
|---|---:|---:|
| topics: sustainability OR food-drink | 0 → **165** | 0 → **212** |
| personas: tourist | 0 → **25** | 0 → **22** |
| budgets: luxury | 0 → **486** | 0 → **381** |

("personas" in the picker is `audience` restricted to `PERSONA_SLUGS =
['expat','local','tourist','business-traveller']` — `preferences.ts`'s own
constant. A reader who picks the **"local" persona** specifically will
still match zero of this job's rows: `local` is the one audience term this
job deliberately never tags, for the measured reason above. Everything
else `audience` offers — `tourist`, `expat`, `business-traveller`, plus the
eleven non-picker audience terms like `family`/`couples`/`foodies` — is
tagged normally.)

### Writes: idempotent, scoped, removable

- **`source = 'inferred'`** for the base job; **`source = 'ai'`** for the
  optional LLM-refinement pass (below) — the two non-`editor` values the
  existing `entity_terms_source_check` CHECK constraint allows
  (`ai`/`editor`/`inferred`; no migration taken — a new `source` value or a
  provenance column is senior-db/architect territory, flagged as an open
  follow-up, not improvised here). Both are scoped by `term_id ∈` the 139
  term ids belonging to these six facets specifically, which is what makes
  either producer's rows unambiguously its own for re-run/removal, given
  `inferred` is already heavily used elsewhere (location) and cannot be
  claimed as "only this job" without that scoping.
- `confidence` = the measured precision of the (facet, band) that produced
  the row (or the fixed, disclosed `LLM_CONFIDENCE = 0.75` for the `ai`
  rows) — never invented, matching `now_classifier.confidence`'s own
  stated discipline.
- Every write is `INSERT ... ON CONFLICT ... WHERE source <> 'editor'` (an
  editor override is never touched) and every re-run **retracts** a
  previously-written row this run no longer proposes, scoped to
  `(entity, that facet's term ids, that same source)` — so a base-job
  re-run can never delete an `ai`-sourced row and vice versa, and a
  retraction for one facet can never touch another. Covered by
  `tests/test_facet_db.py` (idempotent re-run, stale retraction, editor
  protection, dry-run, `remove_all`) against `now_test`'s real
  `engine.entity_terms`.

**Rerun** (safe, any time — re-derives from the current article text and
the current `MEASURED_PRECISION`/`ALIAS_EXCLUSIONS` tables):
```
cd engine/packages/classifier
uv run now-classifier tag-facets bali
uv run now-classifier tag-facets jakarta
```
Add `--dry-run` to see counts without writing, `--limit N` to sample.

**Removal** (all six facets, one city):
```
uv run now-classifier remove-facet-tags bali
uv run now-classifier remove-facet-tags jakarta
```
`--facet <key>` (repeatable) to remove just one or a few facets;
`--dry-run` to count without deleting. This deletes `source='inferred'`
rows only (pass nothing else) — add nothing for the base job's rows; there
is no flag needed for `ai` rows because none exist yet (the refinement
pass has not been run against a real provider — see below).

### Optional LLM refinement (deliverable #4) — OFF by default, unused today

`facet_tagging/llm_refine.py` + `now-classifier refine-facets <city>`.
Reviews ONLY the `lead` band — the borderline band every alias-based facet
measured just under the ship bar (0.44–0.72 above) — and writes
`source='ai'` for whatever the model judges `applies: true`, at the fixed
`LLM_CONFIDENCE = 0.75`. Provider-agnostic: `ANTHROPIC_API_KEY` first (if
one ever appears), else the Ollama Cloud OpenAI-compatible endpoint per the
user's own global notes (`OLLAMA_CLOUD_API_KEY`/`OLLAMA_CLOUD_BASE_URL`,
env or `~/.claude/secrets/ollama-cloud.env`, base `https://ollama.com/v1`,
model `deepseek-v4-flash`). **No valid key exists in this environment**
(Ollama Cloud key returns Unauthorized; no Anthropic key) — `load_llm_config()`
returns `None`, `refine-facets` prints one line and exits 0, no partial
write, exactly the "fails closed and cleanly on auth errors, as today"
requirement. A live 401/403 from either provider is treated identically
(abstain, no retry — retrying an auth failure wastes the shared weekly cap
for nothing). Responses are cached on disk by exact prompt hash, so a
re-run costs zero calls for anything already judged. Unit-tested
(`tests/test_llm_refine.py`) against a mocked HTTP layer — config loading
(both providers, fails-closed), response parsing (including markdown-fenced
JSON), disk caching, and the 401 fail-closed path — since no real request
has ever been made against a working key. **To run it once a valid key
exists**: `uv run now-classifier refine-facets bali` (add `--dry-run`
first).

### Gate

`uv run pytest tests/` in `engine/packages/classifier`: **128/128 passed**
(scope rules, lexicon zone/exclusion logic, price_band cue instrument and
its documented title-anchoring exception, candidate band precedence and
the embed-only floor, the calibration gate itself — every shipped band
`>= SHIP_AT_OR_ABOVE`, idempotent/retraction/editor-protection DB
integration tests against `now_test`, and the LLM-refinement fail-closed
path). The job ran end to end, real writes, both cities (counts above).

### Open follow-ups (not blocking, flagged rather than improvised)

- **A `primary_type_source`-shaped provenance gap for `entity_terms` too**:
  like F132's `articles.primary_type`, `entity_terms` has no per-row
  "which run/method wrote this" column beyond `source`+`confidence` — fine
  at today's scale (two producers, six facets, both scoped by term_id) but
  worth a real column if a third automated producer for these facets ever
  appears. Senior-db/architect call, not taken here.
- **Few-shot centroids are implemented but not fed by enough labels yet**
  (`embed.build_facet_centroids`, `min_class_n=5`) — a larger calibration
  round (or accumulating this job's own high-confidence title-band hits as
  exemplars, carefully, to avoid circularity) could let `embed_only`
  clear the bar where bare direct-term cosine could not. Not attempted
  this round because it needs more labelled positives per term than a
  ~100-item calibration sample gives most terms.
- **`vibe`/`occasion` recall is real but modest** (title-only). If the
  owner wants deeper coverage before the LLM path has a working key, the
  next-cheapest lever is re-authoring `occasion`/`vibe`'s weakest aliases
  (the same "resort-style"/"anniversary" class of generic alias that hurt
  `audience`/`occasion`) and re-measuring `lead` on a fresh sample — not
  done here because it would invalidate the measured 0.44–0.72 lead
  numbers above without a re-measurement, which was out of scope for this
  pass.

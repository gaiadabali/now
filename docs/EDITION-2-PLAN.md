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
  not declare. **Honest limit:** the literal reported article (Bali 4417,
  "The Westin Resort Nusa Dua... Celebrate Wellness 2026") is NOT caught —
  its hotel mention is `role='mentioned'`, split across two unlinked
  `place_id` rows, an entity-extraction fragment. A recurrence-based
  extension for `mentioned` rows measured 8/11 precision on a small sample
  and is a flagged follow-up, not shipped against 11 examples.
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
- **Verification.** `apps/web/scripts/verify-competitor-policy.mjs` runs the
  competitor/hidden-rival predicates over every published venue article
  (stay/eat/drink/wellness/shop) in a city and asserts zero violations —
  `npm run verify:competitor-policy`, once per city
  (`--env-file=.env.local` / `.env.jakarta.local`). Full-archive results,
  2026-09-24: **Bali** 2,047 articles checked, 0 with no rail items, 9,408
  rails produced, mean 9.92 candidates/rail, **0 violations**. **Jakarta**
  1,632 checked, 0 empty, 7,633 rails, mean 9.85/rail, **0 violations**.
  3,679 venue articles total, zero competitor leaks either city.

## 7. Open for the owner/architect

- **Where rails compute.** This iteration computes both article rails
  directly in the web tier (`lib/recommend.ts`), a documented exception to
  `lib/payload.ts`'s "a page may never query Postgres directly" rule, made
  because (a) the engine-api's existing `/articles/{id}/rails` endpoint
  serves Row 1 as PLACES, not the ARTICLE-shaped "plan around it" rail this
  ticket specifies, and (b) this sandboxed session had no way to verify
  `ENGINE_API_URL` reachability. Wiring the HTTP call as the preferred path,
  with this implementation kept as the graceful-degradation fallback, is
  the natural next step.
- **The Westin/Kimpton case's own entity-resolution gap** (place mentions
  fragmented across two unlinked rows for one real venue) is a data-quality
  issue for E2.x place extraction, not something the hidden-rival guard can
  close by itself.
- **`getForYou`'s label** ("Because of what you read") does not yet name a
  specific driving article — a weighted-centroid taste vector does not
  preserve per-item provenance the way a top-1-nearest-neighbour approach
  would.

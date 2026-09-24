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

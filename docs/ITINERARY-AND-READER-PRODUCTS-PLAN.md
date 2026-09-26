# Itineraries, reading state, the print edition, subscriptions and partner offers — plan

**Status:** proposed 2026-09-26; owner answers recorded in §11a (2026-09-26). Build starting.
**Companion to:** [ARCHITECTURE.md](../ARCHITECTURE.md) (§5 data model, §10 personalization,
§11 partner tiers, §12 itinerary engine), [READER-IDENTITY.md](READER-IDENTITY.md) (accounts,
the reader/staff boundary), [SURFACES-PLAN.md](SURFACES-PLAN.md) (the admin shell and console
pattern), [EDITION-2-PLAN.md](EDITION-2-PLAN.md) (rails, `getForYou`, the competitor rule),
[DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) (the dashboard's panels and empty states).

## 0. Executive summary

The owner defined six reader products on 2026-09-26. Five of them are small once the sixth is
fixed, and the sixth is not a feature: it is the place catalogue.

- **Itineraries** are the reader's own list of destinations — saved from articles, places and
  offers — grouped however they like, and turned into a day-by-day plan on request. The solver
  that does the planning exists and is proven. What it plans *over* does not: all 12,507 places
  in both cities are unreviewed, untyped, ungeocoded and carry no opening hours. So the first
  workstream is a place catalogue of about 500 trustworthy venues per city, built "top N first"
  from what the archive already names most, and the itinerary product ships in a *loose* mode
  (a list you can order and share) before the *planned* mode (the solver) — the loose mode needs
  no coordinates and is useful on day one.
- **Continue reading** and **Saved** are two different things and get two different tables: a
  reading-position record the article page writes as the reader scrolls, and the read-later
  bookmark that already ships. The plan defines exactly when an article counts as started, when
  it counts as finished and leaves the list, and when it expires.
- **This month's edition** is a `editions` collection in each city's CMS (cover, issue, on-sale
  date, contents) and a purchase flow behind it. Print commerce (orders, addresses, payment,
  shipping) lives in the platform database because a buyer is a person, not a city.
- **Two subscriptions, kept apart:** the email side (a weekly editorial list and a separate,
  unticked promotions consent, both double-opt-in, with a working unsubscribe) and the print
  side (single issue, or a prepaid 6- or 12-issue term). Auto-renewal is deliberately a later
  phase. The payment gateway is a decision for the owner; §6.3 lays out the choice.
- **Partner offers** are vouchers a partner issues against its own venue: shared codes or unique
  single-use codes, with caps, expiry, blackout dates, verified-email claims and a venue-side
  redemption page. They attach to places, and therefore to any destination or itinerary stop
  that is that place. They never widen a recommendation rail and never bypass the competitor
  rule, which is a policy about the page, not about the reader's own plan.
- **The CMS and console** gain: a place-curation desk, an editions collection, an offers console
  with approval, a circulation screen for print, an email-audience screen, and — later — a
  partner self-service portal, which is a third identity population and gets its own cookie.

The recommended first phase is the place catalogue (top 500 per city) in parallel with the
loose itinerary, destinations, continue reading and the email consent repair. Everything else
stacks on those.

---

## 1. What is true today (measured 2026-09-26, local databases)

The local databases are the same schema as production and carry the same content; reader-side
tables are empty locally (no accounts have been created here), which is stated where it matters.

### 1.1 Places — the blocker, quantified

```
                          Bali      Jakarta
public.places rows        5,918     6,589
status = pending_review   5,918     6,589     (100%)
type = editorial          5,783     6,412     loader sentinel, not a type
type = unknown              135       177
subtype = city-guide      5,918     6,589     sentinel on every row
lat/lng, geo, google_place_id, org_id, price_band, avg_dwell_min, booking_url:  0 on every row
address present             130       167
area_term present            69        81
legacy_wp_id present        177         0     the tribe_venue import
places_hours rows             0         0     (Payload child table of the `hours` array)
places_cuisine / _amenities / _vibe rows      0 / 0 / 0
```

Three corrections to documents this plan builds on:

- `ARCHITECTURE.md` §5 sketches `places(... hours jsonb, amenities jsonb ...)`. As shipped,
  hours are a Payload array (`public.places_hours`: `_parent_id, day, opens, closes` text
  "HH:MM") and amenities, cuisine and vibe are `hasMany` selects with their own child tables.
  All four are empty in both cities.
- `engine/packages/itinerary/README.md` says "only 24 of Jakarta's places carry hours today".
  Zero do. The solver's hours input has no source at all until §9 fills it.
- `now_link_resolver/resolver.py`'s header says `engine.partnerships.place_id` is `uuid` and
  so no real place can hold a place-level partnership. Migration 0005 widened it to `text`; the
  check constraint `num_nonnulls(org_id, place_id) = 1` is live. Place-level partnerships work.

**The rows are extraction fragments, not a catalogue.** A random sample of Bali reads
"Nyanyi Beach's", "Christmas Edition at Feast Restaurant", "Shopping at Ubud Art Market",
"Their Spa and Lunch", "Its Relish Bistro"; Jakarta's twentieth most-featured "place" is
`Hotel's` (33 mentions). Cheap heuristics on Bali alone flag 145 names that open with a generic
word (*best, their, new, shopping, christmas…*) and 12 possessives. Within-city exact
duplicates are few (44 normalised-name collisions in Bali, 34 in Jakarta), but **Jakarta's
table holds Bali**: 301 Jakarta rows carry a Bali area name, and Jakarta's top featured venues
include Karma Kandara (Ungasan), InterContinental Bali, the Gaia Hotel Bandung and Vasa Hotel
Surabaya. That is the region model working as designed for *mentions* (a Jakarta story may
genuinely be about a Bali resort) and a problem only for *itinerary candidates*, which must be
filtered to the site's region — see §9.

**Concentration is the good news.** `place_mentions` is heavily skewed, which is what makes
"top N first" a plan rather than a hope:

```
                                       Bali          Jakarta
place_mentions                         11,316        10,525
  of which role = featured              1,423         1,428
articles with a featured mention        1,196 (27%)   1,209 (25%)
places mentioned in >= 5 articles         352           251
places mentioned in >= 2 articles       1,441         1,242
places featured at least once             847           927
top 500 places: share of all mentions     33%           27%
top 500 places: share of FEATURED         76%           70%
top 1,000 places: share of all mentions   47%           37%
```

Curating 500 places per city covers three-quarters of every venue the magazine has ever led a
story with.

### 1.2 The itinerary engine

`engine/packages/itinerary` (E5.2 solver, E5.3 validator) is complete and tested: it assigns a
stop to each `(day, slot)` under opening hours, dwell, travel feasibility, budget, per-type and
per-org caps, party constraints and guaranteed partner slots, and proves OPTIMAL at 1,000
candidates / 7 days in 1.2 s. `stay` is eligible for no slot by design. The validator is an
independent re-derivation and reports `unverified_hours` and `travel_was_estimated` rather than
silently passing them.

What it cannot do yet, and this plan needs:

- **Pin a stop.** A reader's saved restaurant is a "must include", and `ItineraryRequest` has
  no such field — only `required_partner_stops` and a soft `interest_types` bonus.
- **Anchor a day on a hotel.** The reader's saved hotel is not a stop, but it is where the day
  starts and ends; travel from it is currently ignored.
- **Span two cities.** A trip with Bali days and Jakarta days is two candidate pools and two
  travel matrices.
- **Read real places.** E5.4 (the `public.places` → `Stop` adapter, API and persistence) is not
  built. `engine.travel_matrix` is empty (F44's `text` widening is done; E5.1 OSRM is not).

`engine.itineraries / itinerary_days / itinerary_stops` exist in `now_platform.engine` with
`itineraries.site_id NOT NULL`, `itinerary_stops.place_id text`, `campaign_id → campaigns`, and
`share_token UNIQUE`. `apps/api/app/domain/itineraries/__init__.py` is a docstring.

### 1.3 Reader side

Live in code and on staging, gated on SMTP (`accountsEnabled()` derives from the mail transport;
staging has none): accounts, the preference picker, `/account` with *Picked for you* (real, from
`getForYou`), *Saved* (real — `engine.saved_items`, article-only, via `SaveButton` and the
`toggleSaved` server action), *Continue reading* (empty state), *Membership* and *This month's
edition* (placeholders). `engine.saved_items` has the PK `(identity_id, site_id, entity_type,
entity_id)`, a `note` column nobody writes, and `entity_id text`.

The beacon emits `scroll` at 25/50/75/100% of the **document** (not the article body), and a
`dwell` on leave carrying `dwell_ms` and the maximum `scroll_pct`; it is SPA-aware via
`NOWB('page')` and consent/DNT-gated. Its contract is frozen (E0.2). Traffic is tiny
(Bali 38 rows, Jakarta 22, locally). Anonymous history is stitched to an account at sign-in,
bounded to 30 days and 5,000 rows.

`engine.newsletter_subscribers` is per `(site_slug, email_norm)` and already carries
`confirm_token_hash`, `confirm_expires_at`, `confirm_sent_at`, `unsubscribed_at`; `@now/mailer`
already ships a `newsletterConfirm` template. Nothing calls it: every subscriber is written
`pending` and stays there (F135). There is no promotions consent anywhere.

### 1.4 Partners and the console

`engine.orgs` 1,562 rows; `partnerships`, `campaigns`, `placements` all 0. The partnership
write path with audit and blast radius (S5.2/S5.3) and venue linking (`places.orgId` via
Payload's local API) shipped in Edition 2. Access is two independent role dimensions on
`now_platform.public.users` — editorial `admin|editor|author|none`, commerce
`admin|partner_manager|viewer|none` — with `partner_manager` scoped to the site the process
serves and `admin` platform-wide. Partners have no login; ADMIN-CONSOLIDATION D-S1 names "a
partner ever gets a login of their own" as the point at which the one-app trade-off changes.

`sites.enabled_modules` is `{feed,search,events}` on both cities and `SiteConfig.has(module)`
exists; nothing else reads it yet. It is the right home for `itineraries`, `offers`, `print`
and `newsletter` feature flags.

---

## 2. Product definitions, in plain words

These are the owner's definitions (2026-09-26), sharpened only where the code forces a choice.

**Destination.** A place the reader wants to go. Saved from a place page, from an article (the
article's featured venue, or every venue a guide mentions), or from an offer (the offer's venue,
with the offer pinned). A destination belongs to the reader, not to an itinerary; it can sit in
several itineraries, or in none — unfiled destinations show under *Destinations* on the
dashboard, the way Google Maps' "Want to go" list holds saves that are not in a custom list.

**Itinerary.** A named group of destinations. Two modes, switchable at any time:

- *Loose* — an ordered list, no dates. Reorder by hand, or "sort by area" so the list reads as
  a sensible route. Shareable. Needs nothing from the solver.
- *Planned* — days and slots. The reader gives dates, party (adults, children, mobility,
  halal/vegetarian) and budget; the solver places the pinned destinations, fills the required
  meals around them from the catalogue, and explains anything it could not fit. Stops can be
  moved, swapped or removed by hand afterwards; the validator re-checks and shows warnings
  rather than refusing edits.

Grouping is free: an itinerary carries labels the reader types ("Bali", "Java", "honeymoon",
"with kids"), and the dashboard also groups automatically by city, by island/region and by
country from the places themselves — no configuration needed for the common cases.

**Save (read later).** A bookmark on a story. Exactly what ships today. Unchanged.

**Continue reading.** Stories the reader opened and did not finish. Defined precisely in §4:
started means real reading happened, finished means the end of the body was reached, and a
finished story leaves the list on its own.

**This month's edition.** The latest printed issue: cover, issue label, contents, on-sale date.
A reader can buy that issue, or subscribe in print. This is the *paid, physical* product.

**Email and promotions.** Two consents, separately given and separately withdrawable: the
weekly editorial email, and promotional messages from partners. Both double-opt-in. Neither
costs money and neither is the print subscription.

**Partner offer.** A voucher a partner issues for one of its venues: "15% off dinner, Mon–Thu,
until 30 Nov, 200 redemptions". A reader claims it (verified account), shows it at the venue,
and the venue marks it redeemed. Offers appear wherever the venue already appears — its place
page, the story that features it, the reader's destinations and itineraries, and an offers
index — always labelled *Partner offer*.

---

## 3. Destinations and itineraries

### 3.1 Decisions

**D1 — Itineraries stay in the platform database, and every place reference carries its
site.** A reader spans cities and the owner wants grouping "by island or country", so an
itinerary must be able to hold Bali days and Jakarta days. The tables are already in
`now_platform.engine`. The cost is that a stop cannot be a foreign key to a city row — true
already for `itinerary_stops.place_id` and `saved_items.entity_id` — so each reference is the
pair `(site_id, place_id)` and the reader site resolves them through the city pool for each
site present (at most one fan-out per city, on a page the reader owns; §2's "cross-city reads
are rare and not a hot path" holds). Rejected: per-city itineraries with a platform index —
it forbids the cross-city trip outright and does not remove the fan-out for the dashboard.

**D2 — One entity, two modes; no separate "collections".** The owner's "categorise by city,
island, country, or anything else" is grouping of itineraries, not a second object. A loose
itinerary *is* the collection. `mode` switches; `labels` group; the automatic city/region/
country groupings come from the places' own location terms via the platform term tree. A
second "collection" object would have needed a converter to become a trip, which is exactly
the join Wanderlog avoids by making the unscheduled bucket part of the trip.

**D3 — Destinations are their own table, many-to-many with itineraries.** They are not
`saved_items` rows with a flag: a destination resolves to a place, carries a denormalised area
for grouping, can sit in several itineraries, and can be an article or an offer that expands to
places at planning time. Read-later stays article-only in `saved_items`, unchanged.

**D4 — Persistence in the web tier, computation in the engine API.** The web app already
writes reader tables directly (`saved_items`, `stated_prefs`, `identities`); itineraries and
destinations follow that precedent, in server actions behind the reader session. The solver and
the travel matrix are Python and run behind `engine-api`; the web app calls
`POST /v1/{site}/itineraries/plan` through the same same-origin proxy shape the beacon uses
(`apps/web/src/app/v1/[site]/events/route.ts`), with the API key from server env. Nothing in the
browser talks to the API. EDITION-2-PLAN §7's open question (rails in the web tier vs the API)
is not reopened here: planning is compute, not ranking, and there is no TypeScript CP-SAT.

**D5 — Sharing is by token and stored, forking copies.** A share link shows the stored
itinerary, never a re-solve (the solver is non-deterministic on ties by design). Visibility is
`private | link | public`; `public` is what curated itineraries use. Fork creates a new
itinerary owned by the forker with `forked_from_id` set; the original never changes.

**D6 — The reader's own plan is not a recommendation surface.** The competitor rule (§8.A,
"never relaxes for any tier") governs what a *page about a venue* may suggest. An itinerary has
no subject; the reader may pin two hotels and three restaurants if they like. Where partners
enter a plan — the `required_partner_stops` mechanism, driven by `partnerships.itinerary_eligible`
— they are capped (at most one partner-placed stop per day), labelled *Partner*, and never
displace a reader-pinned stop. Offers do not add candidates to the pool at all (§7.4).

### 3.2 Data model — platform database (Alembic, `now_platform.engine`)

DDL sketch; the senior-db seat owns the migration. Tables are empty today, so the itinerary
reshape is additive plus one relaxation.

```sql
-- A reader's saved destinations. One row per (reader, thing), whatever
-- itineraries it is filed in.
CREATE TABLE engine.destinations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_id   uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
  site_id       uuid NOT NULL REFERENCES engine.sites(id),
  kind          text NOT NULL CHECK (kind IN ('place','article','event','offer')),
  entity_id     text NOT NULL,                 -- the city row (or offers.id for kind=offer)
  place_id      text,                          -- resolved venue; NULL for a multi-venue article
  offer_id      uuid REFERENCES engine.offers(id) ON DELETE SET NULL,   -- §7
  area_term     text,                          -- denormalised for grouping; refreshed lazily
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (identity_id, site_id, kind, entity_id)
);

ALTER TABLE engine.itineraries
  ALTER COLUMN site_id DROP NOT NULL,          -- becomes the "home" site for display; NULL = mixed
  ADD COLUMN mode          text NOT NULL DEFAULT 'loose' CHECK (mode IN ('loose','planned')),
  ADD COLUMN kind          text NOT NULL DEFAULT 'reader' CHECK (kind IN ('reader','curated')),
  ADD COLUMN labels        text[] NOT NULL DEFAULT '{}',
  ADD COLUMN visibility    text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','link','public')),
  ADD COLUMN slug          text,               -- curated only; UNIQUE (site_id, slug)
  ADD COLUMN end_date      date,
  ADD COLUMN forked_from_id uuid REFERENCES engine.itineraries(id) ON DELETE SET NULL,
  ADD COLUMN published_at  timestamptz,        -- curated only
  ADD COLUMN plan_status   text,               -- planned only: solved | edited | stale | infeasible
  ADD COLUMN plan_report   jsonb;              -- last ValidationReport + solver diagnostics

-- The loose list / the unscheduled bucket of a planned trip.
CREATE TABLE engine.itinerary_items (
  itinerary_id   uuid NOT NULL REFERENCES engine.itineraries(id) ON DELETE CASCADE,
  destination_id uuid NOT NULL REFERENCES engine.destinations(id) ON DELETE CASCADE,
  position       integer NOT NULL,
  pinned         boolean NOT NULL DEFAULT true,  -- must be placed when planning
  note           text,
  added_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (itinerary_id, destination_id)
);

ALTER TABLE engine.itinerary_days
  ADD COLUMN site_id uuid REFERENCES engine.sites(id),   -- a day is in one city
  ADD COLUMN date    date,
  ADD COLUMN stay_site_id uuid, ADD COLUMN stay_place_id text;  -- the day's anchor hotel, optional

ALTER TABLE engine.itinerary_stops
  ADD COLUMN site_id        uuid REFERENCES engine.sites(id),
  ADD COLUMN destination_id uuid REFERENCES engine.destinations(id) ON DELETE SET NULL,
  ADD COLUMN offer_id       uuid REFERENCES engine.offers(id) ON DELETE SET NULL,
  ADD COLUMN end_time       time,
  ADD COLUMN travel_min_from_previous integer;
-- `source` gains a vocabulary: reader | solver | partner | curated
```

`itinerary_stops.campaign_id` stays: a partner-placed stop still bills against a campaign when
one exists (§11's "guaranteed slots").

Two limits, borrowed from Google Maps' saved lists so they are known to be livable: 500 items
per itinerary, and a note of at most 4,000 characters on an item or a destination. Both are
application checks with a sentence, not database errors.

**Cross-database integrity is the application's job**, as it already is for `saved_items`. The
reader site drops a destination whose city row no longer resolves (the `getByIds` rule for
since-unpublished saves) and shows a "no longer listed" marker on an itinerary stop rather than
a hole, because a plan with a silently missing dinner is worse than one that says so.

### 3.3 Grouping without configuration

`engine.terms` is the location tree (138 terms, `parent_id`), and `sites.location_term_id`
points at each site's region root. A destination's `area_term` therefore answers "which
neighbourhood", its ancestors answer "which region/island" (Bali; Jakarta/Jabodetabek; Other →
Yogyakarta, Lombok…), and the root answers "which country" (Indonesia; `international` for the
rest). The dashboard groups on those three levels, plus the reader's own labels. No new
vocabulary is needed; a NOW! Yogyakarta site adds a branch, not code.

### 3.4 How the solver consumes an itinerary (planned mode)

```
1. SEGMENT     group the itinerary's days by site (a Bali day, a Jakarta day) — one solve per site
2. CANDIDATES  per site: pinned destinations resolved to places (must be active, geocoded, typed)
               + catalogue candidates from §9's active set, scored by the blender / stated prefs,
               filtered to the site's region, excluding places the reader thumbs-downed
3. ANCHOR      if the itinerary holds a `stay` destination for that site, it is the day's origin
               and return point for travel time — never a stop
4. SOLVE       CP-SAT with `pinned_place_ids` (each placed exactly once across the segment),
               the slot ladder, party, budget, `required_partner_stops` (≤ 1/day, only
               `itinerary_eligible` partnerships), travel from `engine.travel_matrix`
5. VALIDATE    the E5.3 gate; `unverified_hours` and `travel_was_estimated` are surfaced to the
               reader as "we could not confirm opening hours for…" rather than hidden
6. PERSIST     days + stops written; `plan_status = solved`; unplaced pins listed in `plan_report`
7. NARRATE     E5.5, later: prose about what was picked; picks nothing
```

Solver changes required (E5.2b): `pinned_place_ids: frozenset[int]` with a precheck that names
an unplaceable pin ("Locavore is closed on Sunday, the only day left"); an optional
`origin: Stop` per day for the first and last legs; and a per-site `ItineraryRequest` so the
API can run two segments. `place_id: int` and `org_id: int` on `Stop` stay — the adapter maps
uuid org ids to small integers in-process. A pinned `eat` place that would violate a per-type cap
is a diagnosed infeasibility, not a silent drop.

A reader's edit after solving (move a stop, swap one) sets `plan_status = edited`, re-runs only
the validator, and shows warnings inline. "Re-plan" solves again with the edits as new pins.

### 3.5 Contracts

Server actions (web tier, reader session required; all idempotent; all site-scoped through
`getSiteConfig()` exactly as `savedItems.ts` does):

```
saveDestination({ kind, entityId, note?, itineraryId? })      → { destinationId, placeResolved }
removeDestination(destinationId)
createItinerary({ title, labels?, mode? })                      → { itineraryId }
updateItinerary(id, { title?, labels?, visibility?, mode?, startDate?, endDate?, party?, prefs? })
addToItinerary(itineraryId, destinationId, { position?, pinned? })
removeFromItinerary(itineraryId, destinationId)
reorderItinerary(itineraryId, [destinationId…])
sortItineraryByArea(itineraryId)            -- greedy nearest-neighbour over the travel matrix; loose mode
planItinerary(itineraryId)                  -- calls the API; writes days/stops; returns the report
moveStop / swapStop / removeStop(...)        -- planned mode edits; validator only
forkItinerary(tokenOrId)                    → { itineraryId }
```

Engine API (Python, `apps/api/app/api/v1/itineraries.py`, `Depends(require_api_key)`):

```
POST /v1/{site}/itineraries/plan
  body: { days: [{ index, weekday, date, origin?: {lat,lng,place_id} }],
          pinned: [place_id…], party: {...}, prefs: { budget_ceiling?, max_price_band?,
          max_travel_minutes_per_day?, interest_types? }, partner_stops?: 0|1 }
  200:  { days: [{ index, stops: [{ place_id, slot, arrive, depart, travel_min, source }] }],
          unfilled: [...], unplaced_pins: [{ place_id, reason }],
          report: { ok, violations, unverified_hours, travel_was_estimated }, solve_seconds }
  422:  { reason }   -- InfeasibleItineraryError, named
GET  /v1/{site}/itineraries/{token}      -- public read of a stored itinerary (assistant, embeds)
```

The web proxy route is `apps/web/src/app/v1/[site]/itineraries/plan/route.ts`, POST only,
site checked against the process's own slug, called only from the `planItinerary` action.

### 3.6 Reader surfaces

| Route | What |
|---|---|
| `/account` | *Destinations* panel (unfiled, grouped by city/region) and *Your itineraries* (cards: title, labels, n stops, mode, city chips) |
| `/account/destinations` | the full list, filters by city/region/type, "Add to itinerary" |
| `/account/itineraries/[id]` | the builder: loose list or day columns; drag between the bucket and days; *Plan my days*; share and fork controls |
| `/itinerary/[token]` | public, read-only, `noindex` unless `visibility = public`; *Copy to my itineraries* |
| `/itineraries` and `/itineraries/[slug]` | curated itineraries (E5.6): editorial, indexable, forkable |
| Article page | the Save control becomes a small menu: *Read later* · *Save as destination* · *Add to itinerary…*; a guide with many venues offers *Save all 12 places* |
| Place page | *Save as destination* / *Add to itinerary…*; offers (§7) |

"Export to Google Maps" is one link per stop (`https://www.google.com/maps/search/?api=1&query=…&query_place_id=…`)
— what Wanderlog and TripAdvisor both fall back to; it costs nothing and readers expect it.

### 3.7 Personalization hooks

§10 already weights "added to itinerary" at 1.2, the strongest positive signal, and
`getForYou` reads `saved_items` at 1.0. `destinations` and `itinerary_items` join the same
centroid with the same weights; the destination's place gives a *place* signal that the
article-only feed has never had. The beacon contract is not touched: these are first-party
product tables, not analytics.

---

## 4. Reading state — Continue reading and Saved

### 4.1 Decision: an explicit reading-position record, not a beacon by-product

The beacon measures the **document**, is consent- and DNT-gated, batches on a timer, and its
contract is frozen. *Continue reading* needs the **article body**'s progress (a reader who has
read to the end of the prose but not scrolled past four rails has finished), must work even when
analytics consent is denied (it is a product the reader asked for, not measurement), and must
be deletable on request. So the article page writes its own record.

Rejected: deriving the list from `interactions.dwell.scroll_pct`. It is the wrong denominator,
it is absent for a reader who declines tracking, and on a shared device the stitch bound means
the list would be a stranger's. Kept as a **one-time seed** at first sign-in only (below).

### 4.2 Semantics — stated exactly, so QA can test them

| | Rule |
|---|---|
| Progress | share of the article body (`.prose`, from first block to last) that has passed the viewport bottom; 0–100. Never the whole page. |
| Started | body progress ≥ 5% **and** ≥ 10 s on the page, or body progress ≥ 25% regardless of time. A bounce writes nothing. |
| Finished | body progress ≥ 90%, or the last body block has been on screen. Finished stories leave *Continue reading* and appear in *Recently read*. |
| Position | the index of the body block nearest the viewport top, stored with the progress; `?resume=1` scrolls to `[data-block-index=N]`. Approximate on re-layout, which is acceptable (Kindle "location" semantics). |
| Order | most recently read first. |
| Expiry | an unfinished story drops off after **60 days** without progress; the row is kept for *Recently read* until 180 days, then deleted by a nightly job. |
| Cap | 50 unfinished rows per reader; the oldest is evicted. The dashboard shows 6 with *See all*. |
| Dismiss | *Remove* on a row sets `dismissed_at`; it never returns unless the story is opened again. |
| Signed-out | not recorded (the dashboard is signed-in only). The article page still works without it. |
| Seed | on first sign-in, after the anonymous-history stitch, `dwell` rows from the stitched window with `scroll_pct` in 25–90 become unfinished rows with `progress = scroll_pct`, flagged `seeded = true` so the copy can say "picked up from before you signed in". One-time. |
| Opt-out | *Preferences → Don't keep my reading history*: stops writes, deletes existing rows. Export/delete (READER-IDENTITY "privacy obligations") includes this table. |

### 4.3 Data model and write path

```sql
CREATE TABLE engine.reading_progress (
  identity_id   uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
  site_id       uuid NOT NULL REFERENCES engine.sites(id),
  article_id    text NOT NULL,
  progress_pct  smallint NOT NULL CHECK (progress_pct BETWEEN 0 AND 100),
  block_index   integer,
  dwell_ms      integer NOT NULL DEFAULT 0,          -- cumulative
  started_at    timestamptz NOT NULL DEFAULT now(),
  last_read_at  timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  dismissed_at  timestamptz,
  seeded        boolean NOT NULL DEFAULT false,
  PRIMARY KEY (identity_id, site_id, article_id)
);
CREATE INDEX ix_reading_progress_continue
  ON engine.reading_progress (identity_id, last_read_at DESC)
  WHERE finished_at IS NULL AND dismissed_at IS NULL;
```

A small client component on the article page (`ReadingProgress.tsx`, signed-in only, rendered
by the server so signed-out readers ship no script) measures the body with an
`IntersectionObserver` over `[data-block-index]` wrappers, and posts `{ articleId, progress,
blockIndex, dwellMs }` to `POST /account/reading` — a route handler, not a server action, so
`navigator.sendBeacon` can carry the final write on `pagehide`. Writes are throttled to body
milestones (5, 25, 50, 75, 90, 100) plus leave; the handler upserts with `GREATEST(progress)`.
Authentication is the reader cookie (same-origin POST, `Origin` checked, JSON only); a
rate limit of 60 writes/minute/identity in Redis (E8.3a's limiter).

*Saved* stays exactly as built. One addition: the `note` column `saved_items` already has is
exposed as an optional one-line note on the dashboard row.

---

## 5. The print edition

### 5.1 Decision: editions are city content in Payload; commerce is platform data

NOW! Jakarta and NOW! Bali are two printed magazines, so an edition is a per-city editorial
object with a cover, an issue label and a contents list — Payload's job, in the *Editorial*
group, next to Articles. Buying it is a person doing something with money and an address, which
is platform data like every other reader table. An order line therefore references
`(site_id, edition_id)` — the same cross-database pattern as everything above.

### 5.2 `editions` collection (city DB, Payload migration)

```
editions
  title            text          "October 2026"
  issue_label      text          "No. 214"  (optional)
  issue_date       date          the cover date; unique per city. The cadence is data, not code:
                                 NOW! Jakarta's live site sells a bi-monthly magazine today
  cover            media         required
  status           draft | published    (Payload versions/drafts)
  on_sale_at       date          "this month's edition" = latest published with on_sale_at <= today
  sold_out         boolean
  price_idr        integer       single-copy price; NULL = not sold individually
  contents         array of { heading, article (relationship, optional), blurb }
  replica_pdf      media         optional; served only to buyers/subscribers (later phase)
  notes            textarea      internal
```

For scale: the live nowjakarta.co.id subscribe page lists IDR 50,000 per copy and IDR 300,000
for a year (six bi-monthly issues), "not inclusive of delivery", with a free PDF download via
Payhip and an order form that is only an email address and a phone number. Those are the
prices and the term this plan replaces with a real checkout; the owner confirms them in §11.

### 5.3 Reader surfaces

`/edition` (the current issue: cover, contents linking to the articles that are online, *Buy
this issue*, *Subscribe in print*), `/edition/[yyyy-mm]` (archive), and the dashboard aside
panel *This month's edition* showing the cover and the two buttons — or, for a subscriber, "Your
copy of October is on its way" once a shipment exists.

### 5.4 Commerce data model (platform, Alembic)

```sql
CREATE TABLE engine.print_plans (          -- what can be bought, per city
  id uuid PK, site_id uuid NOT NULL → sites, kind text CHECK (kind IN ('single_issue','term')),
  term_issues integer,                     -- 6 or 12 for a term; NULL for single issue
  price_idr integer NOT NULL, delivery_zone text NOT NULL,   -- e.g. 'bali', 'jabodetabek', 'indonesia'
  active boolean NOT NULL DEFAULT true, created_at, updated_at
);
CREATE TABLE engine.print_orders (
  id uuid PK, identity_id uuid → identities ON DELETE SET NULL,   -- guest checkout allowed, email kept
  site_id uuid NOT NULL → sites, email text NOT NULL, email_norm text NOT NULL,
  status text NOT NULL CHECK (status IN ('pending_payment','paid','fulfilling','shipped','cancelled','refunded','expired')),
  subtotal_idr integer NOT NULL, shipping_idr integer NOT NULL, total_idr integer NOT NULL, currency text NOT NULL DEFAULT 'IDR',
  delivery jsonb NOT NULL,                 -- snapshot: name, phone, address lines, city, province, postcode
  gateway text, gateway_order_ref text UNIQUE, paid_at timestamptz, expires_at timestamptz,
  created_at, updated_at
);
CREATE TABLE engine.print_order_items (
  id uuid PK, order_id uuid NOT NULL → print_orders ON DELETE CASCADE, plan_id uuid NOT NULL → print_plans,
  edition_site_id uuid, edition_id text,   -- for single issues: which issue
  qty integer NOT NULL CHECK (qty > 0), unit_price_idr integer NOT NULL
);
CREATE TABLE engine.print_subscriptions (
  id uuid PK, identity_id uuid NOT NULL → identities ON DELETE RESTRICT, site_id uuid NOT NULL → sites,
  plan_id uuid NOT NULL → print_plans, order_id uuid → print_orders,
  status text NOT NULL CHECK (status IN ('active','expiring','expired','cancelled')),
  issues_total integer NOT NULL, issues_sent integer NOT NULL DEFAULT 0,
  starts_with_issue date NOT NULL, ends_after_issue date NOT NULL,
  delivery jsonb NOT NULL, auto_renew boolean NOT NULL DEFAULT false, payment_token_ref text,
  created_at, updated_at
);
CREATE TABLE engine.shipments (
  id uuid PK, order_id uuid → print_orders, subscription_id uuid → print_subscriptions,
  edition_site_id uuid NOT NULL, edition_id text NOT NULL,
  courier text, tracking_no text, shipped_at timestamptz, created_at
);
CREATE TABLE engine.payment_events (        -- the gateway's webhook ledger; append-only
  id uuid PK, gateway text NOT NULL, event_ref text NOT NULL, order_id uuid → print_orders,
  kind text NOT NULL, signature_ok boolean NOT NULL, payload jsonb NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(), UNIQUE (gateway, event_ref)
);
```

**Before money lands in this database, two recorded gaps become blocking**: F7 (one Postgres
role does provisioning, migration and runtime — split roles and grants first) and F6 (no RLS on
site-scoped platform tables). Both are already tracked; this plan makes them prerequisites of
Phase 5 rather than nice-to-haves.

### 5.5 Purchase flow

```
/edition  →  Buy this issue / Subscribe  →  /shop/checkout?plan=…
   1. email (prefilled when signed in; guest allowed), delivery address, phone (couriers need it)
   2. order created `pending_payment`, expires in 24 h
   3. hosted payment page (gateway's own — no card data ever touches this app)
   4. webhook → payment_events (idempotent on event_ref) → order `paid` → email receipt
   5. /account/orders shows status; circulation console marks shipped with a tracking number
```

Subscriptions are **prepaid terms** (6 or 12 issues) in this plan. Auto-renewal is where the
complexity of payments lives — tokenised instruments, retries, dunning, cancellation law — and
at hundreds of copies a month a renewal-reminder email 30 days before the last issue, with a
one-click re-purchase, captures most of the value at a fraction of the risk. The schema carries
`auto_renew` and `payment_token_ref` so the later phase is additive. It is also the honest
shape for Indonesia: QRIS, virtual accounts and Alfamart/Indomaret are push payments and cannot
auto-renew on any gateway; only cards and (on some gateways) e-wallet tokens can. A reader who
paid by QRIS renews by paying again, whichever gateway is chosen.

**Tax and shipping, verified for the plan rather than assumed.** A monthly or bi-monthly
magazine is a periodical and is *not* covered by the printed-book VAT exemption (PP 49/2022
and PMK 5/PMK.010/2020 define an exempt "buku" as non-periodical), so print sales carry PPN at
the effective 11% (12% headline on an 11/12 base since PMK 131/2024). VAT registration (PKP) is
mandatory only above IDR 4.8 bn annual turnover; a PKP selling B2C online reports aggregated
retail invoices ("faktur pajak digunggung") in Coretax rather than a per-customer e-Faktur
(PER-11/PJ/2025). Prices on the site are therefore shown VAT-inclusive, and the order stores
the tax line for the books. Shipping: mark-shipped-with-a-tracking-number by hand is enough for
the first hundreds of parcels; when it is not, Biteship's pay-per-hit rate and order API (JNE,
J&T, SiCepat, AnterAja, Ninja, Grab, Gojek) is the fit at this volume, ahead of
RajaOngkir/Komerce's monthly tiers.

---

## 6. Subscriptions, split in two

### 6.1 Email and promotions — repair and split

**Decision: keep one subscriber row per person per city, add lists and a separate promotions
consent, and build the double opt-in that migration 0006 already describes.** A reader who signs
in with a matching verified email sees and edits the same row from the dashboard.

```sql
ALTER TABLE engine.newsletter_subscribers
  ADD COLUMN identity_id  uuid REFERENCES engine.identities(id) ON DELETE SET NULL,
  ADD COLUMN lists        text[] NOT NULL DEFAULT '{weekly}',     -- weekly | events | offers
  ADD COLUMN promo_consent_at   timestamptz,   -- explicit, separate, unticked by default
  ADD COLUMN promo_consent_source text,
  ADD COLUMN consent_ip_hash text, ADD COLUMN consent_user_agent text,
  ADD COLUMN manage_token_hash text;           -- for the preference centre and one-click unsubscribe
```

The consent record (what was ticked, when, from where) is the evidence Indonesia's personal
data law and the bulk-sender rules both expect; hashing the IP keeps the row from becoming a
tracking record.

Flows:

- **Subscribe** (any form on the site): insert `pending`, send `newsletterConfirm` (the
  template exists) with a hashed single-use token, 48 h expiry. Same response whether new or
  existing (the current anti-enumeration stance stays).
- **Confirm** `/subscribe/confirm?token=` → `confirmed`, `confirmed_at`; if the form carried the
  promotions tick, `promo_consent_at` is set **at confirmation**, not at submit.
- **Manage** `/subscribe/manage?token=` → lists and the promotions toggle; signed-in readers
  reach the same screen from *Email & offers* on the dashboard without a token.
- **Unsubscribe** `/subscribe/unsubscribe?token=` works on GET (one click, no login) and every
  message carries `List-Unsubscribe` (an HTTPS URI with an opaque token) and
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers (RFC 8058), both inside the
  DKIM-signed header set, honoured within two days. Gmail and Yahoo have required this of
  senders above 5,000 messages a day since February 2024, together with aligned SPF, DKIM and
  DMARC — which makes F140 (no DKIM published for `gaiada.com`) a prerequisite of the first
  real send, not a hygiene item.
- **Promotions** are only ever sent to rows with `promo_consent_at` set; the weekly never
  carries a partner offer body unless that consent exists. This is the concrete line between
  "editorial newsletter" and "promotions" the owner asked for, and it is also what Indonesia's
  PDP Law (UU 27/2022) asks: consent that is explicit, "clearly distinguishable from other
  matters", provable on demand, and whose withdrawal stops processing — no pre-ticked box, no
  opt-out consent. The consent columns above are the proof.

Sending the weekly itself (a compose-and-send screen) is not in this plan; the transport,
templates and consent are. Bounce handling needs a provider webhook and stays an open item from
the mailer README.

### 6.2 Print — the paid product

Defined in §5. The two subscriptions never share a table, a page or a button: *Subscribe* in
the masthead stays the email list; the print product is reached from `/edition` and from the
dashboard panel, and is worded "Subscribe in print".

### 6.3 Payment gateway — options for the owner

Checked against the gateways' own pricing and documentation pages in September 2026 (Midtrans
midtrans.com/pricing and docs.midtrans.com; Xendit docs.xendit.co and its help centre; Stripe
stripe.com/global and its Indonesia support pages; DOKU doku.com/pricing and docs.doku.com).
Fees exclude VAT unless stated; they matter little at hundreds of orders a month — instruments
and onboarding friction are what decide this.

| | Midtrans (GoTo) | Xendit | DOKU | Stripe |
|---|---|---|---|---|
| Local methods | VA all major banks IDR 4,000 flat · QRIS 0.7% · GoPay/ShopeePay 2% · DANA/OVO 1.5% · cards 2.9% + IDR 2,000 · Alfamart/Indomaret IDR 5,000 · paylater | cards, GoPay, DANA, OVO, ShopeePay, LinkAja, QRIS, VA (7 banks), Alfamart/Indomaret, BRI direct debit, paylater; fee page not machine-readable — a fixed processing fee applies on top, verify in a browser | cards 2.8% + IDR 2,000 · VA IDR 4,000 · QRIS 0.7% · wallets 1.5–3% · retail IDR 5,000–6,500 | "Indonesia Bank Transfer" (VA) only for an Indonesian account; wallets/QRIS not documented |
| Hosted checkout | Snap (popup or redirect), Payment Links | Invoice/checkout page, Payment Links | DOKU Checkout | Checkout |
| Auto-renew in IDR | cards (one-click token) and **GoPay** tokenisation, Subscription API, retries; account must be enabled for recurring | **widest**: cards, GoPay, OVO, DANA, ShopeePay, BRI direct debit; scheduler with retries | cards, OVO recurring (1-year token), some wallet/direct-debit tokens | not for Indonesian accounts |
| Webhook | signed (`signature_key` = SHA-512 of order id, status, amount, server key), plus a Get Status re-check | `x-callback-token` header | HTTP notification | signed events |
| Sandbox | full | test-mode keys | full | full |
| Onboarding | individual (KTP + NPWP) **or** PT/CV/PMA | legal entity only (NIB ≤ 5 years, NPWP, akta, director e-KTP) | individual or badan usaha | preview/invite-only, no cross-border, PT documents |
| Refunds via API | cards, GoPay, DANA, ShopeePay, OVO (full), QRIS on some acquirers; **not** VA or retail | cards, wallets; not VA/retail | on settled funds | — |
| Settlement | cards D+1 16:00, funds payout-eligible after ~3 business days | T+1 (GoPay) to T+5 BD (cards, retail) | T+1 to T+4 | — |

**Recommendation: Midtrans.** Snap for one-off issues and prepaid terms in Phase 5; the
Subscription API (cards and GoPay) if auto-renew is ever built, with VA/QRIS renewals handled
by a payment link plus reminder. It has the lowest published fees, accepts an individual or a
PT, ships a full sandbox and a refund API, and its webhook is signed and re-checkable. The
one thing it cannot do is auto-renew on OVO, DANA or ShopeePay; if that becomes a product
requirement, **Xendit** is the alternative (legal-entity onboarding, a heavier API, fees not
published to bots). **Stripe is out**: Indonesia is invite-only preview with VA as the only
documented local method. The decision stays the owner's (§11, question 4) because it is also
the merchant-of-record and settlement-account decision.

---

## 7. Partner offers and vouchers

### 7.1 What a partner can issue

An **offer** belongs to an active partnership (org-level or place-level, tier `listed` or
`paid` — a `free` tier has no relationship to attach it to; see open question 5) and names
the venues it applies to. Types: percentage off, fixed amount off, a freebie ("complimentary
dessert"), or a bundle. Redemption modes:

| Mode | How it works | Fraud exposure | Use for |
|---|---|---|---|
| `shared_code` | one code, printed on the offer; reader shows it | highest — the code leaks | "Mention NOW! for 10% off" style deals, uncapped or lightly capped |
| `reader_confirm` | the reader opens the claimed offer and swipes *Redeem now* in front of staff; the swipe is irreversible and timestamped, the screen turns into a "redeemed at 20:14" receipt | low-medium — needs staff to watch the swipe, no venue setup at all | the default for restaurants and cafés: it is what Chope and Fave trained Bali and Jakarta diners to do |
| `unique_code` | a code minted per claim (HMAC-derived, 8 chars, single use), shown as text and QR; the venue enters or scans it on `/redeem` with its PIN | low — a code is worth one redemption and the venue confirms it | capped or high-value offers, and partners who want their own record |

Limits and validity, all on the offer: `valid_from`, `valid_to`, weekday mask, time window,
`blackout_dates`, `total_cap`, `daily_cap`, `per_reader_cap` (default 1), `claim_ttl_hours`
(default 72 — an unredeemed claim expires and its slot returns to the cap), `min_spend_idr`,
`requires_verified_email` (default true), `terms` text.

### 7.2 Data model (platform, Alembic)

```sql
CREATE TABLE engine.offers (
  id uuid PK, partnership_id uuid NOT NULL → partnerships, org_id uuid → orgs, site_id uuid NOT NULL → sites,
  campaign_id uuid → campaigns,            -- optional: bill/pace against a campaign
  title text NOT NULL, summary text, terms text,
  kind text NOT NULL CHECK (kind IN ('percent_off','amount_off','freebie','bundle')),
  value_pct numeric, value_idr integer,
  redemption_mode text NOT NULL CHECK (redemption_mode IN ('shared_code','reader_confirm','unique_code')),
  validity_kind text NOT NULL DEFAULT 'open' CHECK (validity_kind IN ('open','fixed_date')),   -- Klook's distinction
  fixed_date date,
  shared_code text,
  valid_from timestamptz NOT NULL, valid_to timestamptz NOT NULL,
  weekdays smallint[] NOT NULL DEFAULT '{0,1,2,3,4,5,6}', hours_from time, hours_to time,
  blackout_dates date[] NOT NULL DEFAULT '{}',
  total_cap integer, daily_cap integer, per_reader_cap integer NOT NULL DEFAULT 1,
  claim_ttl_hours integer NOT NULL DEFAULT 72, min_spend_idr integer,
  requires_verified_email boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_approval','live','paused','ended','rejected')),
  approved_by uuid, approved_at timestamptz, venue_pin_hash text,   -- for /redeem
  created_by uuid, created_at, updated_at
);
CREATE TABLE engine.offer_places (offer_id uuid → offers ON DELETE CASCADE, site_id uuid NOT NULL, place_id text NOT NULL,
  PRIMARY KEY (offer_id, site_id, place_id));
CREATE TABLE engine.voucher_claims (
  id uuid PK, offer_id uuid NOT NULL → offers, identity_id uuid NOT NULL → identities ON DELETE CASCADE,
  code text UNIQUE,                        -- unique_code mode; NULL otherwise
  itinerary_id uuid → itineraries ON DELETE SET NULL,   -- attribution: claimed from a plan
  status text NOT NULL CHECK (status IN ('claimed','redeemed','expired','revoked')),
  claimed_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
  redeemed_at timestamptz, redeemed_via text, redeemed_place_id text, redeemed_by text,   -- 'venue_pin' | 'partner_user:<id>' | 'staff:<id>'
  claim_ip_hash text, claim_anon_id uuid
);
CREATE TABLE engine.offer_events (        -- impressions/claims/redemptions for partner reporting; partitioned like ad_events
  id uuid, offer_id uuid NOT NULL, kind text NOT NULL CHECK (kind IN ('impression','view','claim','redeem','expire','revoke')),
  identity_id uuid, session_id uuid, surface text, ts timestamptz NOT NULL
) PARTITION BY RANGE (ts);
CREATE TABLE engine.offer_audit (id uuid PK, offer_id uuid, actor_id uuid, before jsonb, after jsonb, ts timestamptz);
```

`ad_events` is not reused: it requires a `placement_id` and models impressions of a booked
slot; an offer is claimed and redeemed. Where a partner also runs a campaign, `campaign_id`
links the two for billing.

### 7.3 Claim and redemption

```
CLAIM     signed-in, verified email (unless the offer waives it) → checks: live, in window,
          caps (total/daily/per-reader, counting claimed+redeemed, not expired), rate limit
          (5 claims/hour/identity, 20/day/IP-hash in Redis) → row + code → wallet at /account/offers
          → optional "add the venue to an itinerary"
SHOW      the wallet renders the code, a QR, the venue, the terms and the countdown to expiry;
          expiring-soon claims are grouped first (Chope's expiry grouping)
REDEEM    reader_confirm: the reader swipes Redeem now in front of staff → status redeemed,
          redeemed_via = reader_confirm; the screen becomes a receipt with the time; a swipe
          cannot be undone, and the wallet says so before it happens.
          unique_code: /redeem (mobile page, no login): venue staff enter the code + the offer's
          venue PIN (per offer, rotated from the console), or scan the QR which opens
          /redeem?c=…; the page confirms "valid, 15% off dinner, claimed by a reader on 12 Oct",
          staff tap Redeem → status redeemed, redeemed_by = venue_pin.
          shared_code: the venue simply applies the deal; a claim row exists only if the reader
          tapped "Claim" (for reporting), and /redeem accepts the shared code to count it.
EXPIRE    a nightly job flips claims past expires_at to expired and releases the cap slot;
          offers past valid_to to ended.
REVOKE    console action on a claim or a whole offer; the wallet shows "no longer valid".
```

Fraud controls, listed so they can be tested: verified email; per-reader cap; per-identity and
per-IP rate limits; codes of 40+ bits of entropy, never sequential; claims only for signed-in
readers (a shared code is visible to all, and that is the partner's choice, labelled as such in
the console); the venue PIN is hashed and rotatable; redemption is idempotent (a second scan or
swipe says "already redeemed at 20:14"); a reader-confirmed redemption is final ("refunds are
not allowed once redeemed" is Chope's rule and ours); a daily anomaly line in the console
(claims vs redemptions, top claimers, redemptions outside the offer's hours); `offer_events`
gives the partner an honest funnel. A partner can also insist on `unique_code` for any offer,
which moves the confirming act from the reader's thumb to the venue's PIN.

### 7.4 Policy: exclusion, tiers, disclosure

- **Offers never widen a recommendation.** An offer renders only where its venue already
  legitimately renders: the venue's place page, the story whose *featured* mention it is, the
  reader's own destinations, itineraries and wallet, the `/offers` index, and the promotions
  email (consent-gated). Rails are built by `lib/recommend.ts` and the engine, and an offer is
  not a candidate source for either; the solver's candidate pool is the catalogue, and an
  offer's venue enters it on the same terms as any other place. The competitor rule is not
  relaxed by an offer at any rung, for any tier — an offer on a rival hotel cannot appear on a
  hotel story, because the rival cannot.
- **Tier controls rendering, as §11 says.** A `paid` partnership's offer links out with
  `rel="sponsored"` and the badge; a `listed` one links to the place page. Both carry the red
  *Partner offer* label (DESIGN-SYSTEM: red is for the mark, the Partner label, section labels
  and the primary action). The wallet, the itinerary stop and the email all label it.
- **Approval is editorial-adjacent.** A partner-created offer (later, via the portal) is
  `pending_approval` until a `partner_manager` or commerce `admin` approves; staff-created
  offers can go live directly. The audit table records both.
- **Reporting to the partner** counts `offer_events` and `voucher_claims`, never a reader's
  identity.

---

## 8. CMS and console impact

### 8.1 Screens

| Where | Screen | Who | Reads/writes |
|---|---|---|---|
| Payload · Editorial | **Editions** collection | editor+ (author drafts) | city `public.editions` |
| Payload · Places | **Places** (fields extended §9.2) | author+ (approve: editor+) | city `public.places` |
| Admin view · Places | **Place desk** — prioritised curation queue: keep / merge / junk, type & subtype, area, geocode confirm, hours, approve | editor+ (`isReviewer` rule: review is not writing) | Payload local API (versions, hooks); read-only joins to `place_mentions` for evidence |
| Admin view · Editorial | **Curated itineraries** — create/edit a `kind = curated` itinerary, pick stops from active places, publish with a slug | editor+ | platform `engine.itineraries` (direct SQL, commerce-page pattern) |
| Commerce | **Offers** — list, create, approve, pause, end, per-offer funnel, claims, revoke, rotate venue PIN | `partner_manager` (own site), commerce `admin` | platform `engine.offers…`, audit |
| Commerce · Org detail | **Offers panel** beside Partnerships and Venues | same | same |
| Commerce | **Circulation** — orders, subscriptions, mark shipped with tracking, refunds, export for the printer/courier; plans and prices per city | commerce `admin`, `partner_manager`; see open question 6 | platform `engine.print_*` |
| Audience | **Email & offers** — subscribers per list, consent status, exports, suppression | commerce `admin` (marketing) | platform `engine.newsletter_subscribers` |
| Audience | **Readers** — a reader's destinations/itineraries/orders for support; export/delete | editorial `admin` | platform |
| Platform · Sites | `enabled_modules` toggles for `itineraries`, `offers`, `print`, `newsletter` | platform admin | `engine.sites` |
| Partner portal (later) | `/partners` — own offers, funnel, redemptions; create → pending approval | partner users (new population) | scoped to `org_id` |

Every platform-data screen follows the pattern SURFACES-PLAN S5 and READER-IDENTITY settled:
plain Next pages inside the admin shell, direct SQL, `requireUser()`-style gates, tests as the
deliverable because the access rules are security-critical (the same sentence
ADMIN-CONSOLIDATION wrote about commerce reads now covers money and vouchers).

### 8.2 Roles

No new dimension. The two existing ladders cover it:

- editorial `editor`/`admin` — editions, place curation (approve), curated itineraries;
  `author` — drafts and place edits, no approval, no review.
- commerce `partner_manager` (site-scoped) / `admin` — offers, approvals, circulation;
  `viewer` — read-only on all of it.

Two things need the owner's word (open questions 6 and 7): whether print circulation is a
different person from partnerships (if so, a `circulation` value on `commerce_role` is a
one-enum-value change), and when partners get logins.

### 8.3 Partner self-service — a third population

READER-IDENTITY's argument for two identity stores applies a third time. Partner users are
neither staff (they must never reach `/team-editor`) nor readers (they act for an organisation).
When built: `engine.partner_users(id, org_id, email, hash, salt, status, …)`, cookie
`__Host-now-partner`, its own signing secret, `aud: 'partner'`, a `/partners` route group in
the same web app (D-S1's reasoning — one app, no fourth deploy — still holds), and every query
scoped by `org_id` from the session, never from a request field. Scope for v1 of the portal:
see own offers and funnels, create an offer into `pending_approval`, rotate the venue PIN, see
redemptions. Not in v1: editing partnership terms, seeing other partners, any reader data.

---

## 9. Place data quality — the first-class workstream

### 9.1 Strategy: top 500 first, then the tail by machine, junk never

```
                 12,507 pending rows
                       │
   ┌───────────────────┼───────────────────────┐
   junk (fragments)    top N by evidence         long tail
   ~1,000-1,500?       500 per city              the rest
   hidden, kept        human-curated             machine-resolved where evidence is
                       geocoded + typed + hours  strong (≥ 2 articles), auto-approved
                       → status active           at high confidence, else stays pending
```

Ranking for the queue: `3 × featured mentions + article count + 2 × (linked to an org with a
partnership) + recency of the newest mention`, computed per city into a materialised score.
The queue is worked in that order. 500 per city is the first gate because it covers 70–76% of
featured mentions (§1.1) and is one editor-week of work at two minutes a place.

### 9.2 Schema additions (Payload migration on `public.places`)

```
source            select   extracted | legacy_venue | editor | partner              (who created the row)
merged_into       relationship → places   (a duplicate points at its survivor; hidden everywhere)
quality_score     number   read-only, computed (evidence, completeness, freshness)
business_status   select   operational | temporarily_closed | permanently_closed | unknown
                           (from the open gazetteers or an editor's confirmation — never written from Google)
external_types    json     the category list from the open gazetteers, for typing evidence
geo_source        select   fsq | overture | osm | mappress | editor | partner
                           (licence per row: OSM is ODbL with attribution; FSQ/Overture carry their notices)
geo_confidence    number
region_ok         checkbox computed: coordinates fall inside the site's region; false = mention-only
hours_source      select   editor | partner                     (Google's hours may not be stored — §9.4)
hours_checked_at  date
```

`status` keeps its three values; a junk row becomes `status = closed` with `source` unchanged
and a `merged_into` of NULL? No — junk is a fourth outcome and deserves its own value:
**add `junk` to `enum_places_status`**. A junk row is never rendered, never a candidate, and
its `place_mentions` are kept (they are evidence of what the extractor did) but ignored.

The review-queue pattern (`classification_reviews`) is reused in spirit, not in table:
place-extraction's README already found that its facet ENUM cannot hold a merge decision. The
place desk is therefore a custom admin view over `places` itself with per-row actions, the
same shape as the classification review desk, and every decision is a Payload `update` (a
version, `reviewedBy`, hooks) rather than raw SQL.

### 9.3 Pipeline

1. **Junk detection** (`now-places triage`): fragments by rule (possessives, generic-lead
   words, "at <venue>" event phrases, award/franchise titles, single dictionary words), plus
   the extractor's own noise list; writes a report and a proposed `junk` list; editors confirm
   in bulk from the desk. Precision over recall: a doubtful row stays pending.
2. **Entity resolution** (`now-places dedupe`): normalised-name and cross-city clustering with
   the existing `now_place_extraction.match` scorer (0.85 auto-merge, 0.55–0.85 review pair);
   merges rewrite `place_mentions.place_id` to the survivor inside a transaction and set
   `merged_into`. Cross-city: a Bali venue in Jakarta's table is *kept* (Jakarta stories mention
   it) with `region_ok = false`; it is never an itinerary candidate for Jakarta.
3. **Resolution** (`now-geocode`, extended) — open data first, Google only as an identity
   resolver, because of the terms in §9.4:
   - *Rung A, offline gazetteers:* match each queued name (+ area/address when present) against
     **Foursquare OS Places** (Apache 2.0; 8.57 million Indonesian records with names,
     coordinates, categories, addresses and `date_closed`) and **Overture Places**
     (CDLA-Permissive 2.0; names, addresses, websites, socials, brand, `operating_status`,
     `confidence`), both as monthly Parquet downloads loaded into a scratch schema. These are
     the store of record for coordinates and categories where they match at ≥ 0.85 on the
     existing `now_place_extraction.match` scorer with area agreement.
   - *Rung B, self-hosted OSM:* Photon (POI names) then Nominatim (addresses) on the Indonesia
     extract already in compose (`--profile geo`); ODbL, attribution required, coordinates kept
     forever. Good for hotels, temples, landmarks; patchy for cafés and shops.
   - *Rung C, Google Places (New) Text Search, `id` and Essentials fields only:* for the
     residue, to obtain a `place_id` and confirm identity (name, formatted address, `types`).
     The `place_id` is stored indefinitely (permitted); Google's coordinates are used only to
     pick the right open-data or OSM record and are then discarded (they may be cached at most
     30 days). Nothing else from Google is written to `places`.
   Every write records `geo_source` (`fsq | overture | osm | editor | partner`) and the
   `google_place_id` separately, so the licence of every coordinate is auditable per row.
4. **Typing** (`now-classifier type-places`): L1 type + subtype from three signals — the
   gazetteer categories (FSQ/Overture taxonomies mapped once to our vocabulary; Google `types`
   at resolution time only as evidence in the desk, never stored), the *featured* articles' own
   `primary_type` (a hotel story's featured venue is a `stay` with high prior), and the mention
   context; LLM adjudication (the existing `now_place_extraction.llm` path, capped) only for
   conflicts. Writes with a confidence; ≥ 0.90 auto-applies to the row, below queues for the
   desk. `type` accuracy gates competitor exclusion (§17: ≥ 0.95), so the desk double-checks
   the top 500 by hand regardless.
5. **Hours are editorial and partner data, not Google's.** No free source carries opening
   hours at scale (FSQ OS and Overture have none; OSM's `opening_hours` is sparse), and Google's
   may not be stored. So the desk captures hours for the top 500 from the venue's own site or
   Instagram as part of curation (about a minute per place), the partner portal lets a partner
   maintain its own (§8.3, `hours_source = partner`), and `places_hours` is written only from
   those two sources. After-midnight closes are kept as "02:00" and converted to > 1440
   minutes in the adapter. A place without hours is a valid Stop the validator reports as
   `unverified_hours` — the design the solver already has, now with a real reason behind it.
6. **Approval**: the desk's *Approve* sets `status = active`, `verified_at`, and the place
   page (which 404s on anything else today) goes live. A nightly `quality_score` recompute
   feeds the solver's `score` prior at cold start.
7. **Freshness** (monthly job) produces a **report for the desk**, not writes: for every active
   place with a `google_place_id`, Place Details with the `businessStatus` field only (Pro SKU,
   5,000 free a month — free at this size) and, from the FSQ/Overture refresh, `date_closed`/
   `operating_status`. An editor confirms a closure in the desk, which sets `status = closed`
   (§8.A already hard-filters it) and flags itineraries holding the place (`plan_status =
   stale`). The decision is ours and stored; Google's answer is looked at and not kept.

### 9.4 Cost and terms (Google Maps Platform, post-March-2025 model, checked September 2026)

- **Pricing is per SKU with monthly free caps, no pooled credit.** Text Search Pro $32 per
  1,000 (5,000 free a month); Text Search and Place Details "IDs only" free and unlimited; Place
  Details Essentials $5 per 1,000 (10,000 free), Pro $17 (5,000 free), Enterprise $20 (1,000
  free — this is the SKU opening hours sit in). A request bills at the highest SKU any field in
  its mask triggers.
- **What this plan spends:** rung C for the top 500 per city is ~1,000 Text Search calls —
  inside the free cap. The long tail with ≥ 2 mentions (~2,700 rows) resolves over two months
  for nothing. The monthly closure report is ≤ 2,000 `businessStatus` calls — inside Pro's
  free cap. Expected Google bill: **$0 a month**; the ceiling if every one of the 12,507 rows
  were sent through Text Search Pro in one month is about $224. The real cost is editor time.
- **Terms that shape §9.3:** `place_id` may be stored indefinitely; Places latitude/longitude may
  be cached for at most 30 consecutive days; names, hours, status and ratings may not be
  pre-fetched, cached or stored and must be fetched by `place_id` at render time; Places content
  may be shown without a Google map but must carry Google attribution and **must not be used in
  conjunction with a non-Google map**. The site displays MapLibre, so Google content (hours,
  status, even a Google pin) cannot sit on a place page beside it. That is why hours are
  editorial, closures are editor-confirmed, and the only Google artefact on a reader page is the
  "Open in Google Maps" deep link. If the owner wants Google's live hours rendered, that is a
  Google-map-or-no-map decision for the place page and needs legal advice, not a code change.
- **OSM-sourced coordinates** carry the "© OpenStreetMap contributors" obligation
  `docs/data-provenance.md` already records; FSQ OS Places and Overture require their licence
  notices in the same attribution line.

### 9.5 Acceptance for "the catalogue is usable"

Per city: ≥ 400 `active` places with open-licence coordinates inside the region, an L1 type
other than `editorial`/`unknown`, and a subtype; ≥ 70% of them with editor- or
partner-entered hours; 0 junk rows active; no Google field other than `place_id` stored on
any row (a test greps the schema and a sample); every `featured` mention of a top-500 place
resolves to a surviving row; `verify:competitor-policy` still 0 violations (typed places
strengthen the hidden-rival guard rather than weaken it).

---

## 10. Risks

- **The catalogue is the critical path, and it is human time.** 500 places × 2 cities × ~3
  minutes (confirm identity and type, enter hours) is about a week and a half of editor
  attention; without it planned mode ships empty. Mitigation: the loose mode and destinations
  do not wait for it, and the desk is ordered so the first hundred places per city carry the
  most featured stories.
- **SMTP is still unset.** Accounts, the newsletter repair, order receipts and voucher claims
  all need mail; F140 (no DKIM) and the Workspace app password are owner actions. Nothing in
  phases 2–6 is verifiable on staging until they land.
- **Money in a database with one role and no RLS.** F6/F7 move from "tracked" to "prerequisite"
  for Phase 5. Webhook handling must be idempotent and signature-checked; the `payment_events`
  unique key is the guard.
- **Vouchers invite abuse.** Shared codes leak by design; unique codes and verified-email claims
  are the default for anything with a cap. The console's anomaly line is the early warning.
- **Cross-database references have no integrity.** Already true; more tables now depend on it.
  Every reader surface must tolerate a missing city row (marker, not hole), and QA should test
  unpublishing a place that sits in a plan.
- **Google terms on stored data.** Only `place_id` may be kept; coordinates for 30 days;
  hours, status and names not at all; and none of it beside a MapLibre map. The plan stores
  open-licence coordinates (FSQ OS, Overture, OSM) and editorial hours, and uses Google purely
  as a resolver and a closure-alert source. `geo_source` per row makes the licence auditable;
  the §9.5 gate greps for leakage. The cost of compliance is that hours coverage is editor and
  partner time, not an API call.
- **Beacon consent vs product records.** Reading progress and destinations are first-party
  product data the reader can see, opt out of and delete; they must never be repurposed as
  covert analytics, and the preferences page has to say so.
- **Solver infeasibility is a UX problem, not a bug.** A pinned place that is closed on the only
  free day must produce a sentence, not a spinner. The API returns named reasons for exactly
  this.
- **Region semantics.** Jakarta's table holding Bali venues is correct for mentions and wrong
  for candidates; `region_ok` is the line, and it must be computed from coordinates, never from
  the name.

---

## 11. Open questions for the owner

1. **Offers on which tiers?** Proposed: `listed` and `paid` may issue offers; `free` cannot.
   Alternative: `paid` only, which keeps voucher operations to paying partners.
2. **Membership.** The dashboard has a *Membership* placeholder. Is there a membership product
   distinct from the print subscription and the email lists? If not, the panel becomes
   *Email & offers* and *Your print subscription*.
3. **Print terms and delivery.** The live site sells IDR 50,000 a copy and IDR 300,000 a year
   (six issues), delivery extra. Keep those? Add a 12-issue term? Which delivery zones and
   shipping prices (Bali, Jabodetabek, rest of Indonesia, none abroad)? Gifting (Monocle's
   voucher-to-recipient flow) now, or later?
4. **Payment gateway.** Midtrans (recommended, §6.3), or Xendit if e-wallet auto-renewal is a
   requirement — and which legal entity and bank account receive settlements, and whether the
   business is (or will be) PKP-registered for VAT. Auto-renewal deliberately later.
5. **Guest checkout.** Allow buying a single issue without an account (email + address only)?
   Proposed: yes for single issues, account required for a term subscription.
6. **Who runs circulation?** If a different person from partnerships, a `circulation` commerce
   role is added; otherwise `partner_manager`/`admin` cover it.
7. **Partner logins — now or after the console?** Proposed: the staff-run offers console first
   (Phase 6), the portal after the first ten offers have run.
8. **Curated itineraries' voice.** Are "48 Hours in Canggu" pieces written as itineraries
   (stops with times) or as articles that *link* an itinerary? Proposed: both — an itinerary
   object with a slug, and a story that embeds it.

### 11a. The owner's answers (Hansel, 2026-09-26) — these supersede the proposals above

1. **Partners and offers.** A partner is a venue under contract with NOW! that pays for exposure
   in the articles (e.g. a restaurant that wants to give readers a discount). Offers are a
   partner benefit: only venues under an active paid partnership issue them.
2. **No membership product.** Two reader products, named separately:
   **Newsletter** (the standard email subscription, promotions opt-in inside it) and a
   **print subscription** to buy the magazine — a year, or month by month. The dashboard's
   Membership panel is retired.
3. **Print terms, prices and delivery** follow the current live site (take them from its
   subscribe page; do not invent).
4. **Payment gateway: not decided.** Build behind a provider interface and ship a
   **simulated gateway** first (full order lifecycle, webhooks, refunds, failures), so
   Midtrans or Xendit is a later drop-in.
5. **An account is required** to buy print. No guest checkout.
6. **NOW! handles everything** — circulation, offers and partnerships. No separate
   circulation role.
7. **Partner logins are needed now**, not after ten offers. The partner portal (P8.1, the third
   identity population) moves up to run alongside the offers console.
8. **Curated itineraries: both** — itinerary objects with a slug, and stories that embed them.
9. **Media storage: MinIO** (S3-compatible), replacing the planned Garage bucket.

---

## 12. Roadmap

Sizes: **S** ≤ 1 day, **M** 2–3 days, **L** 4–6 days, **XL** > 1 week. Tiers as the army uses
them; model·effort is the seat default unless flagged. Every ticket's "done when" is something
QA can drive. Phases 1, 2 and 4 can run in parallel; 3 depends on 1 and 2; 5 and 6 depend on 4
(mail) and on the F6/F7 hardening.

```
P1 catalogue (top 500) ──┬──► P3 planned mode (solver) ──► P7 long tail + freshness
P2 destinations · loose ─┘            ▲
P4 email consent (needs SMTP) ───────┬┴─► P5 print edition + orders
                                     └──► P6 offers + vouchers ──► P8 partner portal
```

### Phase 0 — foundations (S–M each; parallel)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P0.1 | **Platform migration 0010**: `destinations`, `itinerary_items`, `reading_progress`; `itineraries`/`days`/`stops` reshape per §3.2; `newsletter_subscribers` consent columns per §6.1. Alembic, `schema_baseline.json` regenerated, downgrade guarded. | senior-db · default | Applies to `now_platform` and the `test` tenant; `now-platform-db check` clean; a Bali stop and a Jakarta stop coexist in one itinerary in a DB-integration test. | — |
| P0.2 | **Payload migration on `places`**: §9.2 fields and the `junk` status value, with SQL twin for the production path. | senior-db · default | Both cities migrate; `verify-places-geo` still passes; existing rows untouched (`status` unchanged, counts identical before/after). | — |
| P0.3 | **`enabled_modules` flags** `itineraries · offers · print · newsletter` read by `getSiteConfig()`; every new reader route 404s when its module is off. | medior · default | Toggling a flag in `/team-editor/platform/sites` hides the routes and the dashboard panels within the TTL. | — |
| P0.4 | **F7 role split + F6 RLS on site-scoped platform tables** (partnerships, campaigns, placements, and the new offers/print tables). | senior-db · **opus·high** — RLS on a shared database that both city processes write, one policy mistake leaks or blocks a city | A `partner_manager` session for Bali cannot read a Jakarta offer through any console query; migrations run under the migration role only; runtime role cannot DDL. | P0.1 |
| P0.5 | **SMTP + DKIM on staging** (owner supplies the app password; devops wires it). | devops · default | `/account/register` sends a real mail on staging; `accountsEnabled()` true. | owner |

### Phase 1 — place catalogue, top 500 per city (the blocker)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P1.1 | **Triage + ranking CLI** (`now-places triage`, `now-places rank`): junk heuristics, per-city evidence score, queue order; report with samples. | medior · default | Report lists ≥ 90% of a 100-row hand-labelled junk sample; the top-500 list per city covers ≥ 70% of featured mentions (measured, not asserted). | P0.2 |
| P1.2 | **Dedupe/merge CLI** using `now_place_extraction.match`; merges rewrite mentions transactionally and set `merged_into`; cross-city rows get `region_ok = false` once geocoded. | senior-be · **opus·medium** — a bad merge silently corrupts mentions archive-wide and is hard to reverse | Dry-run report; a merge round-trips (mentions moved, survivor keeps both names as aliases); a 0.55–0.85 pair is queued, never merged. | P1.1 |
| P1.3 | **Gazetteer rung in `now_geocode`**: load FSQ OS Places and Overture Places (Indonesia slices, monthly Parquet) into a scratch schema; match queued names with the existing scorer + area agreement; write open-licence coordinates, categories and `geo_source`. Then the Google Places (New) rung for the residue — `id` + Essentials fields only, `place_id` stored, Google coordinates used to pick the open record and discarded — behind the ladder and the state cache. | senior-be · default | Top-500 batch per city: ≥ 85% resolve to open-licence coordinates inside the region and ≥ 90% carry a `place_id`; re-running bills 0 new Google calls; `geo_source` set on every resolved row; no Google field other than `place_id` is written (asserted). | P0.2, P1.1 |
| P1.4 | **Hours + attributes entry**: `places_hours` editing in the desk (weekday grid, split service, after-midnight) written only from `editor`/`partner` sources; `external_types` from the gazetteers; FSQ `date_closed`/Overture `operating_status` surfaced as evidence, never auto-applied. | medior · default | An 18:00–02:00 bar entered in the desk round-trips to `closes = 1560` in the adapter test; `hours_source` is never `google`; the desk's hours form takes under a minute per place (timed with an editor). | P1.3, P1.6 |
| P1.5 | **Place typing** (`now-classifier type-places`): three-signal L1/subtype with confidence; auto-apply ≥ 0.90; queue below. | senior-be · **opus·medium** — the type feeds competitor exclusion, and the evidence sources disagree in non-obvious ways | ≥ 0.95 accuracy on a 200-row hand-labelled sample of the top 500; `editorial`/`city-guide` sentinels gone from every active row. | P1.3 |
| P1.6 | **Place desk** admin view: queue in rank order, evidence (mentions, articles, resolver result, map pin), actions keep/merge/junk/type/area/approve, bulk junk confirm, throughput. | senior-fe · default (+ senior-uiux for the screen) | An editor approves a place end-to-end and its place page returns 200; `author` cannot approve; every decision is a Payload version with the actor. | P0.2, P1.1 |
| P1.7 | **Catalogue gate script** (`verify:catalogue`): §9.5 numbers per city, runs in CI against the real DB. | qa · default | Prints the acceptance table; fails below thresholds; both cities pass before P3 starts. | P1.3–P1.6 |

### Phase 2 — destinations, loose itineraries, reading state

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P2.1 | **Destinations write path** (`lib/destinations.ts` + actions): save from article (featured venue, or all venues of a guide), place, offer; unfiled list; grouping by city/region/country from the term tree. | senior-fe · default | Saving a hotel story creates one destination resolved to its featured place; saving a "10 cafés" guide offers *Save all*; the dashboard groups them under Bali → Canggu. Site-scoped exactly as `savedItems.ts`. | P0.1 |
| P2.2 | **Save control menu** on article and place pages: *Read later · Save as destination · Add to itinerary…*; no client JS beyond a `<details>` menu. | medior · default | All three paths write the right table; signed-out shows the sign-in link; `aria-pressed` states correct after each action (Router-cache trap from `savedActions.ts` respected). | P2.1 |
| P2.3 | **Itinerary CRUD, loose mode** + dashboard panels + `/account/itineraries/[id]` list builder (reorder, labels, notes, move between bucket and list). | medior · default (+ senior-uiux) | A reader creates "Honeymoon", adds Bali and Jakarta destinations, reorders, and the dashboard shows both cities' chips; deleting a destination removes it from every itinerary. | P2.1 |
| P2.4 | **Share and fork**: `/itinerary/[token]`, visibility, `forked_from_id`, "Copy to my itineraries"; `noindex` unless public. | medior · default | A link opens for a signed-out visitor; forking creates an owned copy; changing the original does not change the fork. | P2.3 |
| P2.5 | **Sort by area** (loose mode) — greedy nearest-neighbour over `travel_matrix` with haversine fallback; labelled "estimated" when the matrix is missing. | medior · default | A 6-stop list in three areas sorts into contiguous area runs; the button is hidden when < 3 stops have coordinates. | P2.3, P3.1 optional |
| P2.6 | **Reading progress**: table (P0.1), `ReadingProgress.tsx`, `POST /account/reading` route with rate limit, `Continue reading` and *Recently read* panels, resume anchor, dismiss, opt-out + delete, first-sign-in seed. | medior · default | §4.2's table is a test matrix: bounce writes nothing; 25% body + leave → listed; 90% → moves to Recently read; 61 days idle → gone; opt-out deletes rows; seeded rows carry the flag. | P0.1 |
| P2.7 | **`getForYou` reads destinations and itinerary items** at §10 weights (1.2), including the place signal. | junior · default | Unit test: an itinerary add outranks a save in the centroid weights; label logic unchanged. | P2.1 |
| P2.8 | **Export to Google Maps** link per stop/destination. | junior · default | Link opens the venue by `place_id` when present, by name+city otherwise. | P2.3 |
| P2.9 | **Privacy export/delete** covers destinations, itineraries, reading progress, claims, orders. | medior · default | Deleting an account leaves zero rows in the new tables except orders (retained per finance, anonymised). | P0.1 |

### Phase 3 — planned mode (the solver)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P3.1 | **E5.1 travel matrix**: OSRM self-hosted (compose profile) on Java + Nusa Tenggara merged from Geofabrik (~7 GiB scratch, ~2.5 GiB to serve; all-Indonesia is ~11 GiB / 3–4 GiB if preferred), contracted with CH for table queries, `--max-table-size` ≥ 2,000; `now-travel-matrix build --city` over active places in row blocks, writing `engine.travel_matrix` (text ids); peak/off-peak `mode` rows from a sampled Google Distance Matrix multiplier per city; nightly delta for new active places. | devops + senior-be · default | Matrix covers 100% of active-place pairs per city; a Kuta→Ubud pair returns a plausible car time in both modes; `PrecomputedMatrix.coverage()` = 1.0 in the gate; the OSRM container is `restart: "no"` and profiled like Nominatim (build-time infrastructure). | P1.7 |
| P3.2 | **E5.4a `public.places` → `Stop` adapter** (`now_itinerary.candidates`): eligibility (active, in-region, geocoded, typed), hours from `places_hours`, price band mapping, dwell defaults by type, party flags from amenities, `is_partner` from `partnerships_active.itinerary_eligible`, org id mapping. | senior-be · default | Adapter tests over a synthetic `public` schema; an `editorial`-typed or `region_ok = false` row never becomes a Stop; an OSM-sourced row is a Stop (licence is a display concern). | P1.7 |
| P3.3 | **E5.2b solver extensions**: `pinned_place_ids`, per-day `origin` (stay anchor), per-site segments, partner cap ≤ 1/day, named diagnostics for unplaceable pins. | senior-be · **opus·medium** — constraint modelling where a wrong encoding passes the solver and fails only the independent validator | All existing 25 tests green; new tests: a pin closed on the only day is diagnosed by name; a pin is placed exactly once; the anchor's travel counts on the first and last legs; the validator agrees on every case. | — |
| P3.4 | **E5.4b API + proxy + persistence**: `POST /v1/{site}/itineraries/plan`, `GET …/{token}`, web proxy route, `planItinerary` action writing days/stops and `plan_report`. | senior-be + medior · default | A two-city itinerary produces two solves and one stored plan; a 422 reason reaches the reader as a sentence; the API key is never in client HTML. | P3.2, P3.3 |
| P3.5 | **Planner UI**: day columns, bucket, drag (a destination is *moved* between bucket and day, never copied), *Plan my days* and *Re-plan this day* (scoped to one day so it never reorders the rest — Wanderlog's rule), warnings from the validator on manual edits, "we could not confirm hours for…" notices, partner label on partner-placed stops. | senior-fe · default (+ senior-uiux) | Driven end to end on staging with the top-500 catalogue: plan, move a stop into a closed hour → warning, re-plan one day → only that day changes; phone width has no horizontal scroll. | P3.4 |
| P3.6 | **Constraint gate in CI over real data** (`verify:itinerary-gate`): 50 random plans per city, 100% validator pass, `travel_was_estimated = false`. | qa · default | Fails the build on any violation; report lists unverified-hours rate per city. | P3.4 |
| P3.7 | **E5.6 curated itineraries**: editor screen, `kind = curated`, slug, publish; `/itineraries` index and detail; fork into a reader's own. | medior · default | "48 Hours in Canggu" publishes, is indexable, and forks; unpublishing hides it but keeps forks. | P2.4, P3.4 |
| P3.8 | **E5.5 narration** (optional, later): prose per stop from the stored plan; never reorders. | senior-be · default | A narrated plan's stops are byte-identical to the stored plan; text is cached per (plan version). | P3.4 |

### Phase 4 — email and promotions consent (needs P0.5)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P4.1 | **Double opt-in**: confirmation send on subscribe, `/subscribe/confirm`, expiry, resend; anti-enumeration kept. | senior-be · default | A new address is `pending` until the link is clicked, then `confirmed`; an expired link says so; no path confirms without the token. | P0.1, P0.5 |
| P4.2 | **Lists + promotions consent + preference centre + one-click unsubscribe** with RFC 8058 headers on every list message; consent evidence recorded. | medior · default | Promotions toggle is unticked by default and recorded only at confirmation; unsubscribe works on GET without login; headers present on a test send. | P4.1 |
| P4.3 | **Dashboard *Email & offers* panel** bound to the same row for a verified signed-in reader. | junior · default | Toggling on the dashboard changes the subscriber row; a mismatched email shows the subscribe form instead. | P4.2 |
| P4.4 | **Audience console screen**: lists, statuses, exports, suppression list. | medior · default | Counts match SQL; export excludes unsubscribed and pending. | P4.2 |

### Phase 5 — the print edition and orders (needs P0.4, P0.5, owner answers 3–6)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P5.1 | **Editions collection** + `/edition`, `/edition/[yyyy-mm]`, dashboard panel with cover. | medior · default | Publishing an edition with `on_sale_at` today makes it "this month's"; drafts are invisible; the panel links to checkout. | P0.3 |
| P5.2 | **Commerce migration** (§5.4) + plans seeded per city. | senior-db · default | Tables exist under the runtime role's grants; `payment_events` rejects a duplicate `(gateway, event_ref)`. | P0.4 |
| P5.3 | **Gateway integration**: order creation, hosted payment session, webhook receiver with signature verification and idempotent state transitions, expiry job, refunds/void from the console. | senior-integrator · **opus·high** — money, a public webhook, replay and race conditions; a mistake is a refund dispute or a free magazine | Sandbox end-to-end: pay → webhook → `paid` → receipt mail; replayed webhook is a no-op; forged signature is 401 and logged; an order expires unpaid at 24 h. | P5.2, owner Q4 |
| P5.4 | **Checkout + address + receipts** (`/shop/checkout`, `/account/orders`), guest allowed per Q5. | senior-fe + medior · default | Address validation (phone required), price shown in IDR, order visible on the dashboard, receipt mail delivered. | P5.3 |
| P5.5 | **Circulation console**: orders, subscriptions, mark shipped + tracking, export for the printer/courier, plan prices. | medior · default | Marking shipped emails the buyer with the tracking number; export matches SQL counts; `viewer` is read-only. | P5.2 |
| P5.6 | **Prepaid term subscriptions** + issue counting + 30-day renewal reminder with one-click re-purchase. | medior · default | A 6-issue term shows "4 of 6 sent"; the reminder goes once; expiry flips status. | P5.4 |

### Phase 6 — partner offers and vouchers (needs P0.4, P0.5, owner Q1)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P6.1 | **Offers migration** (§7.2) with partitions for `offer_events`, audit, and the RLS policies from P0.4 extended to the new tables. | senior-db · default | Site-scoped reads enforced; a claim cannot exist for a non-live offer (trigger or app check, tested). | P0.4 |
| P6.2 | **Offers console**: create/edit/approve/pause/end, venues picker (active places of the partnership's org), venue PIN rotate, funnel and claims list, revoke. | senior-fe + medior · default | `partner_manager` for Bali cannot open a Jakarta offer; approval writes audit with the actor; a `free`-tier partnership cannot be chosen (per Q1). | P6.1 |
| P6.3 | **Reader surfaces**: offer cards on the place page, the featuring story, destinations, itinerary stops, `/offers`, wallet `/account/offers` with code + QR + countdown; claim action with caps and rate limits; *Partner offer* label everywhere; `rel="sponsored"` by tier. | senior-fe · default | Claim → wallet in one click for a verified reader; unverified is told to confirm email; the 2nd claim over the cap is refused with a sentence; a rail never shows an offer (crawl assertion). | P6.2, P2.1 |
| P6.4 | **Redemption page `/redeem`** + venue PIN + QR flow + idempotent redeem + nightly expiry job + anomaly line. | senior-be · **opus·medium** — an unauthenticated public endpoint that changes money-equivalent state; replay, brute force and enumeration must all be closed | Wrong PIN ×5 locks the offer's PIN for 15 min; a redeemed code scanned again says when it was used; expired claims release cap slots; codes are not enumerable (8-char, 40+ bits, rate-limited). | P6.3 |
| P6.5 | **Policy conformance**: extend `verify:competitor-policy` and the page crawl to assert no offer appears in any rail, every offer card carries the label, and outbound links from `paid` offers carry `rel="sponsored"`. | qa · default | 0 violations across every venue story in both cities with offers seeded on rival venues. | P6.3 |
| P6.6 | **Promotions email hook**: an offer can be included in the promotions list send only for `promo_consent_at` rows. | medior · default | A test send to a weekly-only subscriber contains no offer body. | P4.2, P6.2 |

### Phase 7 — long tail and freshness (ongoing)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P7.1 | Machine resolution + typing for places with ≥ 2 mentions; auto-approve ≥ 0.90; weekly desk sample of 50 for precision. | medior · default | ≥ 1,500 active per city; sampled precision ≥ 0.9 on type. | P1.x |
| P7.2 | Monthly closure report for the desk (Google `businessStatus` by `place_id`, Pro SKU, not stored; FSQ/Overture status from the refreshed gazetteers); editor-confirmed closures set `status = closed`, flag itineraries `stale` and notify their owners. | medior · default | A place the report marks closed and an editor confirms disappears from candidates and its itineraries show the marker within a day; the report's Google answers are not persisted anywhere (asserted). | P3.4 |
| P7.3 | Place page *Our coverage* wired to `place_mentions`, offers and "Save as destination". | junior · default | A place page lists its stories newest-first, competitor rule untouched (no rails on place pages until designed). | P1.6 |

### Phase 8 — partner portal (after ten offers have run; owner Q7)

| # | Ticket | Tier · model | Done when | Deps |
|---|---|---|---|---|
| P8.1 | `partner_users`, cookie/secret/`aud`, `/partners` route group, org-scoped queries, invitation by a `partner_manager`. | senior-be · **opus·high** — a third identity population on the same origin as staff and readers; the boundary is the whole risk | A partner token cannot satisfy a reader or staff check (three independent defences, tested); every portal query is scoped by the session's `org_id`. | P6.x |
| P8.2 | Portal screens: own offers and funnels, create into `pending_approval`, rotate PIN, redemptions. | senior-fe · default | A partner sees only its org; an approval by staff makes the offer live. | P8.1 |

### Recommended first phase

**Phase 1 (place catalogue, top 500 per city) and Phase 2 (destinations, loose itineraries,
reading state) in parallel, with P0.1–P0.3 first and P0.5 requested from the owner today.**
Phase 1 unblocks everything the solver needs and is mostly editor time; Phase 2 gives the
dashboard three real panels (*Destinations*, *Your itineraries*, *Continue reading*) without
waiting on it. Phase 4 starts the moment SMTP exists. Phase 3 follows when P1.7's gate passes.
Money (Phase 5) and vouchers (Phase 6) wait for the role split and RLS, and for the owner's
answers in §11.

---

## Appendix A — what this borrows, and from where

Checked against the products' own help centres and documentation in September 2026 (a
research pass by a helper agent; the sources are the official pages named, with secondary
sources only where the official page blocks automated reads).

- **Google Maps Saved** (support.google.com/maps/answer/7280933) — fixed default lists plus
  custom lists; privacy as a per-list enum (private, or shared by link with view-or-edit);
  a per-item note of up to 4,000 characters owned by the list entry; 500 entries per list;
  saved places drawn as a map layer that can be shown or hidden. → `destinations` as the
  unfiled bucket, `visibility` per itinerary, `note` on items, the two limits in §3.2, and
  itinerary stops as a MapLibre layer.
- **Wanderlog** (help.wanderlog.com, "Places and lists"; wanderlog.com/plan-a-trip) — a trip is
  unscheduled lists plus day columns; a place is *moved* between them, never copied; "optimise
  route" is scoped to a single day and is a button, not a mode; "paste a link" treats an
  article as a source of places, not a destination. → loose/planned as one object,
  `itinerary_items` as the bucket, *Re-plan this day*, and D3's rule that an article
  destination resolves to its venues.
- **TripAdvisor Trips** (tripadvisor.com/Trips; its 2024 AI-planner announcement and the
  Medium engineering write-up) — "Save to a Trip" from any content; forum posts and articles
  save as title-only, second-class items readers complained about; the AI builder takes
  destination, dates, party and interests and returns an ordinary editable, shareable trip.
  → the four planner inputs in §3.4, and the reason articles become *place* destinations.
- **The Guardian** (github.com/guardian/mobile-save-for-later) — saved-for-later is a per-user
  array of `{id, shortUrl, date, read}` with a version timestamp, capped at 1,000, synced only
  when signed in. **Kindle** — a title is marked read when the last page is turned, with a
  manual override; Whispersync keeps a monotonic furthest-position. **Medium**
  (help.medium.com, "Your reading list", "Refine recommendations") — reading history is
  visible, per-item removable and clearable, and feeds recommendations. → §4's
  furthest-progress upsert, the 90% "finished" rule with *Remove*, the cap, signed-in only,
  and the opt-out that also clears the history.
- **Chope** (chope.co, "redeem dining vouchers") and **Fave** (help.myfave.com) — "swipe to
  redeem in front of staff" as an irreversible transition; vouchers grouped by expiry with the
  expiring ones highlighted; a flag for time-restricted vouchers; no refunds once redeemed.
  → the `reader_confirm` mode, wallet ordering and the finality rule in §7.3.
- **Klook Partner** and **Traveloka AXES** merchant apps (App Store listings; Traveloka's
  voucher-redemption help) — QR scan or manual code entry, search by code or visitor name, bulk
  redeem for groups, separate unredeemed/redeemed buckets, and voucher validity as a field
  (fixed-date vs open-dated). → `unique_code` with `/redeem`, `validity_kind`, and the Phase 8
  portal's redemption screen.
- **Google Search Central** (qualify-outbound-links) and **Google News publisher policies** —
  paid placements carry `rel="sponsored"`; sponsored content must be clearly disclosed and
  never presented as independent editorial. → §7.4's labelling and tier-driven `rel`.
- **Monocle** (monocle.com/faqs; the issues page) — the issues page is a grid of covers with
  number and month and a Subscribe call to action; 14-day cancellation then non-refundable to
  the end of the cycle; auto-renew switchable off until two business days before renewal;
  gifting as a voucher the recipient redeems with their own address, one cycle, no auto-renew;
  newsletter opt-ins in account preferences independent of paid status. **The Economist** —
  auto-renew per term (quarterly or yearly); single copies only through third parties.
  → `/edition` and the archive grid, prepaid terms first, the separation of email consent from
  the paid product, and gifting as a question for the owner.
- **NOW! Jakarta's own live site** (nowjakarta.co.id/subscribe) — IDR 50,000 a copy, IDR
  300,000 a year, delivery extra, a free PDF via Payhip, an order form that is an email and a
  phone number. → the price points in §5 and the reason a real checkout is the product.
- **Gmail bulk-sender requirements, Yahoo's, RFC 8058, and UU 27/2022 with GR 71/2019**
  (support.google.com/a/answer/81126; senders.yahooinc.com; rfc-editor.org/rfc/rfc8058; FPF and
  Baker McKenzie summaries of the PDP Law) — one-click unsubscribe headers under DKIM honoured
  within two days; explicit, distinguishable, provable consent with withdrawal that stops
  processing; marketing that does not "disturb" the data subject. → §6.1.

## Appendix B — corrections to ARCHITECTURE.md this plan implies

- §5 city `places`: hours/amenities/cuisine/vibe are Payload child tables, not jsonb; new
  provenance and curation columns per §9.2; `junk` status.
- §5 platform: `itineraries.site_id` nullable (home site), `mode`, `kind`, `labels`,
  `visibility`, `forked_from_id`; new `destinations`, `itinerary_items`, `reading_progress`,
  `offers*`, `voucher_claims`, `print_*`, `payment_events`, `shipments`; `newsletter_subscribers`
  consent columns.
- §12: pinned stops, a per-day origin, per-site segments; the reader's plan is not a
  recommendation surface (D6).
- §16: `POST /v1/{site}/itineraries/plan` replaces the sketched `POST /v1/{site}/itineraries`
  (persistence is in the web tier, D4); `GET /v1/{site}/itineraries/{token}` stays.
- §11: offers as a partner product beside link policy and campaigns; `ad_events` unchanged.

---

## Phase 0 — shipped

Delivered as `feat/phase0-foundations`, restarted 2026-09-26 after an earlier attempt on this
same branch was interrupted mid-task by a usage limit and, before stopping, dropped and
recreated the local `now_platform` database to get a "clean" state — losing every local seed row
(1,562 orgs, 407 terms, and, on inspection, every other `engine` table too: `sites`, `identities`,
`partnerships`, everything). That data loss is **not** addressed by this work; the owner decides
separately how (or whether) to restore it. What follows applies **additive schema only** on top
of whatever `engine.alembic_version` already recorded (0009), never a resend of missing rows.

This section widens P0.1's original scope (destinations/itinerary_items/reading_progress/
newsletter consent) to also include the print-commerce and offers data models (originally Phase
5/6) and the partner-identity table (originally P8.1) — per this ticket's brief and the owner's
§11a answers 4 ("ship a simulated gateway now") and 7 ("partner logins are needed now"), which
together pull those data models forward so nothing downstream needs a schema change to start.

### Tables and migrations

Eight linear Alembic migrations, `now_platform.engine`, revisions 0010-0017 (all reversible;
`downgrade()` tested round-trip on a scratch database):

| # | Migration | Adds |
|---|---|---|
| 0010 | `reading_progress` | `engine.reading_progress` (§4.3) |
| 0011 | `newsletter_consent_and_lists` | consent/list columns on `engine.newsletter_subscribers` (§6.1) |
| 0012 | `offers_and_vouchers` | `engine.offers`, `offer_places`, `voucher_claims`, `offer_events` (partitioned), `offer_audit` (§7.2) |
| 0013 | `destinations_and_itinerary_reshape` | `engine.destinations`, `itinerary_items`; reshapes `itineraries`/`itinerary_days`/`itinerary_stops` (§3.2) |
| 0014 | `print_commerce` | `engine.print_plans`, `print_orders`, `print_order_items`, `print_subscriptions`, `shipments`, `payment_events` (§5.4) |
| 0015 | `partner_identities` | `engine.partner_users`, `partner_user_tokens` (§8.3) |
| 0016 | `role_split_migrator_and_runtime` | `now_migrator`/`now_runtime` roles, ownership reassignment, transition-period default privileges (F7) |
| 0017 | `rls_site_scoped_platform_tables` | `engine.current_site_id()`, RLS + `FORCE` on 14 tables, the full `now_runtime` grant set (F6) |

City-DB side (Payload, `engine/packages/cms`), both cities, SQL twins in `scripts/`:

| Migration | Adds | SQL twin |
|---|---|---|
| `20260926_090000_places_junk_status_enum_value` | `junk` added to `enum_places_status` (own migration — an enum label can't be added and used in the same transaction) | `places-junk-status-enum-value.sql` |
| `20260926_090100_places_provenance_and_curation_fields` | §9.2's ten columns on `public.places` (+ `_places_v` mirror): `source`, `merged_into`, `quality_score`, `business_status`, `external_types`, `geo_source`, `geo_confidence`, `region_ok`, `hours_source`, `hours_checked_at` | `places-provenance-and-curation-fields.sql` |
| `20260926_100000_editions_collection` | `editions` collection (§5.2): `editions`, `editions_contents`, `_editions_v`, `_editions_v_version_contents` | `editions-collection.sql` |

`src/collections/Places.ts` and the new `src/collections/Editions.ts` (registered in
`payload.config.ts`) ship in the same commits as their migrations, per the standing rule that
Payload selects every declared column.

**Caveat, stated plainly**: the two Places migrations and the Editions migration were
hand-authored against a live, already-migrated city database's confirmed column/index/constraint
naming (relationship → `<field>_id` + `ON DELETE SET NULL`; array → a child table; `versions.
drafts` → a `_status` enum + `_<collection>_v`), not machine-generated by `payload migrate:
create` — this worktree's `npm install` could not produce a usable `node_modules` for the `cms`
package standalone (an `engine/`-level npm workspace was the actual install root; a scoped
install inside `packages/cms` silently produced almost nothing and, worse, dirtied the
workspace's own lockfile — reverted before committing). Before merge: run `payload migrate:
create` in an environment with a working install and a real `DATABASE_URI`, against a database
already at `20260926_090100_...`, and diff the result against `20260926_100000_editions_
collection.ts` — the strongest remaining check this ticket could not fully close itself.

### enabled_modules (P0.3)

Already exists: `engine.sites.enabled_modules text[]` shipped in baseline migration 0001 and is
fully wired through `now_config.SiteConfig.has_module()` (`engine/packages/config`). Nothing to
add at the schema layer. `now_runtime`'s grant on `engine.sites` is `SELECT, UPDATE` (0017) —
covers the `/team-editor/platform/sites` toggle the roadmap's P0.3 describes — but the web app's
`getSiteConfig()`-side module names (`itineraries`, `offers`, `print`, `newsletter`) and the
per-route 404 gating are app code, not schema, and are left to the medior ticket the roadmap
already assigns them to (routes for those modules do not exist yet — Phases 1-6 build them).

### RLS and the role model (F6/F7)

**Roles.** `now_migrator` (runs migrations, owns every object in `engine`, `BYPASSRLS`, no
`SUPERUSER`) and `now_runtime` (what the application should connect as: `LOGIN`, no DDL rights on
`engine` — `USAGE` only, no `CREATE` — no `BYPASSRLS`, subject to every policy below). Neither
migration sets a password (committing one to git history is not an option); that is the first
rollout step below. **Today's `now` superuser is untouched and the app still connects as it** —
a superuser bypasses RLS and every grant unconditionally, so shipping these two migrations alone
changes nothing about how the app behaves. RLS becomes load-bearing only at the deliberate
cutover step in the checklist below.

**Session convention.** `engine.current_site_id()` reads a GUC, `app.site_id`, set per request/
transaction by the application (`SET LOCAL app.site_id = '<uuid>'`), and fails closed — an unset
or unparseable value returns SQL `NULL`, which matches no `site_id`, rather than raising an error
or (worse) matching every row. A cross-site admin read fans out at the application layer,
exactly as ARCHITECTURE.md §2 already describes cross-city reads working — no grant or policy
lets one query see two sites' rows.

**RLS + `FORCE ROW LEVEL SECURITY` is on 14 tables**: `partnerships`, `campaigns`, `placements`
(this ticket's named list) plus every new offers/print table one join away from a `site_id`
column — `offers`, `offer_places`, `voucher_claims`, `offer_events`, `offer_audit`, `print_plans`,
`print_orders`, `print_order_items`, `print_subscriptions`, `shipments`, `payment_events`. Direct-
`site_id` tables filter on `site_id = current_site_id()`; join tables filter through an `EXISTS`/
`IN` subquery to their site-scoped parent (e.g. `placements` via `campaign_id → campaigns.
site_id`). **Not yet covered, flagged rather than silently skipped**: `ad_events` and
`partnership_audit` are exactly as site-scoped as the tables above but sit outside this ticket's
named list — a fast-follow. `partner_users`/`partner_user_tokens` get an `org_id`-scoped policy
when P8.1 defines the session/`aud` model that policy needs to reason about, not before.
Reader-owned tables (`itineraries`, `destinations`, `reading_progress`, `saved_items`,
`newsletter_subscribers`) are scoped by `identity_id`, out of F6's stated scope.

**Grants restrict the operation, RLS restricts the row** — the two together are what makes
"the runtime role cannot write audit/ledger history it shouldn't" true regardless of which rows
it can see: `ad_events`, `partnership_audit`, `offer_events`, `offer_audit`, `payment_events` get
`SELECT, INSERT` only from `now_runtime` — no `UPDATE`, no `DELETE`, ever. `offers`, `print_plans`,
`print_orders`, `print_order_items`, `print_subscriptions`, `shipments`, `voucher_claims` get
`SELECT, INSERT, UPDATE`, no `DELETE` — every one is superseded by a status change, never erased.
`engine.sites`: `SELECT, UPDATE` only. `terms`/`facets`: `SELECT` only. `alembic_version`: nothing.
Everything else gets ordinary `SELECT, INSERT, UPDATE, DELETE`. A trigger,
`engine.offers_require_paid_partnership_trg`, additionally enforces the owner's §11a.1 ruling at
the database layer: an `INSERT`/`UPDATE` of `offers.partnership_id` against anything but a
`tier = 'paid'` partnership is rejected, not merely discouraged in application code.

**Verification performed** — `engine/packages/platform-db/tests/test_rls_site_isolation.py`, 11
tests, run against the real, restored-to-schema-only local `now_platform` (migrated through
0017), each inside one transaction rolled back at teardown (same convention
`test_partnerships_expiry.py` already uses — proven safe to run against a shared database, not
only a scratch one):

```
11 passed — test_runtime_sees_only_its_own_site_partnerships
            test_runtime_with_no_site_context_sees_nothing
            test_runtime_with_garbage_site_context_sees_nothing
            test_runtime_cannot_read_other_site_row_by_explicit_id
            test_runtime_cannot_insert_cross_site_row
            test_migrator_role_bypasses_rls_and_sees_every_site
            test_joined_policy_placements_scoped_via_campaign_site
            test_joined_policy_voucher_claims_scoped_via_offer_site
            test_runtime_cannot_update_or_delete_append_only_ledgers
            test_runtime_cannot_ddl_in_engine_schema
            test_offers_require_paid_partnership_trigger
```

Additionally, against a throwaway `now_platform_p0_scratch` database (created, migrated 0001→head
from empty, exercised, then dropped — per this ticket's hard safety rules): the full migration
chain applies cleanly from zero (24 tests pass, including this package's pre-existing suite with
its own locally-seeded `test` site — seeded only in the scratch DB, never in `now_platform`); a
`downgrade` to 0009 and re-`upgrade` to head round-trips cleanly; `now-platform-db check` matches
the regenerated `schema_baseline.json` before and after that round-trip;
`check_no_payload_uuid_refs.py` reports zero violations on both `now_platform` and the scratch DB.

**A pre-existing, unrelated gap surfaced by this exercise**: `test_partnerships_expiry.py`'s
`test_site_id` fixture requires a pre-seeded `engine.sites` row with `slug = 'test'`, which the
Phase 0 incident's database reset removed (it was never part of any migration's seed data) and
no CI workflow currently runs this test file to have caught its absence. Six of its tests
currently error locally against `now_platform` for that reason alone — unrelated to any change in
this PR (confirmed: the same 6 fail identically on plain `main`'s migrations, and pass cleanly
once a `test` site is seeded, as the scratch-DB run above did). Not fixed here per the hard
safety rule against seeding `now_platform`; flagged for whoever restores the lost local data.

### Production rollout checklist

Nothing in this PR touches production. When it is time to roll these migrations out:

1. **Apply the schema migrations** (Alembic + the two Payload SQL twins), in this order, each
   verified with the query the corresponding file's footer gives:
   `now-platform-db migrate` (0010→0017, one deploy step, all additive) → per city:
   `places-junk-status-enum-value.sql` → `places-provenance-and-curation-fields.sql` →
   `editions-collection.sql`. All four are inert against the app running today (new tables/
   columns nothing yet reads) — no ordering hazard against the currently-deployed image, unlike
   `articles-slug.sql`'s "before the image that reads the column" rule.
2. **Set real passwords for the two new roles**, out of band (never in a migration file, never
   in this repo): `ALTER ROLE now_migrator WITH PASSWORD '<secret A>';` `ALTER ROLE now_runtime
   WITH PASSWORD '<secret B>';` — from the deploy secrets store, one time, per environment.
3. **Add two new `.env` entries** wherever `NOW_PLATFORM_DATABASE_URL` is set today (this does
   not remove or change the existing one):
   ```
   NOW_PLATFORM_MIGRATOR_DATABASE_URL=postgresql+psycopg://now_migrator:<secret A>@<host>/now_platform
   NOW_PLATFORM_RUNTIME_DATABASE_URL=postgresql+psycopg://now_runtime:<secret B>@<host>/now_platform
   ```
   Point CI/deploy's migration step at the first; leave every running service on the existing
   `NOW_PLATFORM_DATABASE_URL` (the historical superuser) until step 5.
4. **Verify the roles work** before cutting anything over:
   `psql "$NOW_PLATFORM_MIGRATOR_DATABASE_URL" -c "CREATE TABLE engine._rollout_probe(id int); DROP TABLE engine._rollout_probe;"`
   (must succeed) and
   `psql "$NOW_PLATFORM_RUNTIME_DATABASE_URL" -c "CREATE TABLE engine._rollout_probe(id int);"`
   (must fail: `permission denied for schema engine`). Then, as part of this same verification
   step and BEFORE step 5 below, smoke-test the console's actual read and write paths against
   `now_runtime` directly (not yet through the app): a partnerships `SELECT` scoped to one
   `app.site_id` and an `INSERT`/`UPDATE` of a partnership row, both over `psql` or a one-off
   script — this is what catches a missing `SET LOCAL app.site_id` call before it reaches a
   real request, rather than after.
5. **Hard prerequisite, tracked as its own ticket, checked before this step is attempted at
   all**: nothing in the application sets `app.site_id` today.
   `git grep "app.site_id\|SET LOCAL\|current_site_id" engine/apps` returns zero hits, and
   `engine/apps/web/src/lib/db.ts` — the console's entire data layer — is a bare `pg.Pool`:
   one query per call, no per-request transaction, nowhere a `SET LOCAL` could even be placed
   today. Cutting the console over to `now_runtime` in this state does not degrade gracefully —
   every RLS-covered table (§ above) reads as zero rows and every write is rejected, for every
   request, immediately, because `engine.current_site_id()` reads an `app.site_id` that is
   simply never set. This is not a corner case step 5 might hit; it is the certain outcome of
   running step 5 (below) before this prerequisite ships. That prerequisite is: `lib/db.ts`
   moves from "one pool, checkout-per-query" to "one transaction per request", opened with
   `SET LOCAL app.site_id = '<the resolved site's uuid>'` as its first statement, using
   whatever site-resolution the console already does for that request. This is an application
   change, scoped to its own ticket — **not made by this PR**, which is schema and roles only.
6. **Cut the application over to `now_runtime`**, one service at a time, each verified
   immediately after: `docker exec <container> printenv NOW_PLATFORM_DATABASE_URL` shows the new
   DSN (DEPLOY.md's own rule — verify inside the container, never trust the `.env` file alone),
   then exercise one read and one write path per service (e.g. the reader dashboard's saved
   items, a partnership edit in the console) and confirm they still work. This is the step that
   makes RLS load-bearing for the first time; because step 5 is a hard prerequisite, "a code path
   forgot to set `app.site_id`" should no longer be a possible outcome by the time this runs — if
   it still happens, that is a bug in step 5's ticket, not a surprise this step should have to
   absorb. Roll back by reverting the env var alone; nothing else has to change.
7. **Retire the historical superuser's direct use** once every service is confirmed on
   `now_runtime` and `now_migrator` — do not drop the `now` role itself (other tooling may still
   reference it), just stop pointing application/migration traffic at it.

Nothing above is applied by this PR. Steps 2-7 are a separate, deliberate rollout the owner or
devops runs when ready, and step 5 is itself a separate ticket's worth of application code before
step 6 can safely run at all — this ticket's job was the schema, the roles, the policies and the
proof they work, not the cutover itself.

### For the owner

- The local `now_platform` database's pre-existing data (1,562 orgs, 407 terms, and, in fact,
  every row in every `engine` table) is gone, per the incident that opened this ticket. This PR
  does not restore it and was instructed not to attempt to. That restoration remains a separate
  decision.
- ARCHITECTURE.md §2's claim that "the `engine` schema can be dropped and rebuilt from `public`
  at any time" is not true of this database in practice — `engine.orgs`, `engine.terms`,
  `engine.identities`, `engine.partnerships` and now everything added in this PR are
  platform-authored data with no `public`-schema source to rebuild from (there is no Payload
  instance on `now_platform.public` yet, per this same package's own README). Worth a documentation
  fix independent of this ticket, since it appears to be exactly what led the previous attempt on
  this branch to treat a `DROP DATABASE` as a safe way to reach a "clean" state.
- `payload migrate:create`'s output for the Editions/Places migrations was not diffed against
  this PR's hand-authored versions (environment limitation — see "Tables and migrations" above).
  Worth doing once a working Node install is available, before this merges.

---

## Phase 1 — shipped so far (P1.1, P1.2, P1.6)

Delivered as `feat/p1-place-catalogue`. P1.3's Google rung, P1.4 (hours) and P1.5 (typing) are
not in it.

### Schema (city databases, Payload migrations with SQL twins)

| Migration | Adds | Why |
|---|---|---|
| `20260927_090000_places_aliases_and_reviewed_by` | `places.aliases` (jsonb), `places.reviewed_by_id` (→ users) | §9.2 names `reviewedBy` in its text but not its column list; P1.2 needs the survivor to keep the loser's name, and each alias entry is also the merge's audit record |
| `20260927_090100_locked_documents_editions_rel` | `payload_locked_documents_rels.editions_id` | **Phase 0 fix.** The Editions migration left out Payload's lock-table column, so since Phase 0 every signed-in save in the admin failed |

Both are applied locally to `now_bali` and `now_jakarta` through `payload migrate`. The local
city databases turned out to be missing all three Phase 0 city migrations as well; the same run
applied them. Place and mention counts were identical before and after.

### P1.1 — `now-places triage` / `now-places rank` (engine/packages/place-catalogue)

- **Junk.** The rules are written as shapes, in two tiers. The **junk** tier is the only one
  `--apply` writes, and only on `pending_review` rows. The **suspect** tier is listed for an
  editor and never written. Recall was measured on four hand-labelled 100-row samples:

  | sample | listed (junk + suspect) | junk tier | junk-tier false positives |
  |---|---:|---:|---:|
  | Bali, the ticket's fixture (tuning) | 96% | 95% | 0/45 |
  | Jakarta (tuning) | 94% | 90% | 0/49 |
  | Bali, labelled blind, then tuned on | 95% | 91% | 1/45 |
  | **Jakarta, labelled blind, never tuned on** | **82%** | **57%** | 1/56 |

  The last row is the honest generalisation figure. The gate is met on the ticket's fixture.
  On unseen data, roughly one junk row in five reaches the desk unflagged.
- **Dry run on the live local databases:**

  | | Bali | Jakarta |
  |---|---:|---:|
  | proposed junk | 1,931 | 1,936 |
  | suspect | 873 | 1,005 |
  | names another region (kept, flagged) | 110 | 700 |
  | proposed auto-merges | 15 | 28 |
  | pairs queued for an editor | 1,453 | 1,459 |

  Full reports: `bali/site/place-triage-report.md` and `jakarta/site/place-triage-report.md`.
- **Top-500 coverage** uses §9.1's score (`3 × featured + articles + 2 × partnership +
  recency`). It reaches **76.5% (Bali) and 73.8% (Jakarta)** of the featured mentions that sit
  on real venues. Measured against all featured mentions it is 67.3% and 63.1%, because 170
  and 207 featured mentions sit on junk rows. For example, Jakarta's "Hotel's" is featured 33
  times. §1.1's 76%/70% was measured by featured count alone, before any junk was known.

### P1.2 — dedupe / merge / unmerge

- **Scoring.** Dedupe uses the extractor's scorer and its 0.85 and 0.55 thresholds. Guards
  send high-scoring pairs to the queue when the score alone cannot settle them:
  - a hotel and its spa or restaurant sharing a name;
  - an outlet "at" a venue;
  - an area name;
  - distinct legacy records;
  - approved rows.
- **Applying a merge.** Each merge is one transaction. The mentions move, `merged_into` is set,
  and an audit entry is added to the survivor's `aliases`. `unmerge` reverses a merge exactly.
- **Proven on scratch copies.** Both cities were taken through the full apply and then the full
  reversal. The mention checksum was identical afterwards.

### P1.6 — the place desk (`/team-editor/place-desk`)

- **Screens.** The queue is shown in rank order, with five filters: to review, looks like junk
  (bulk confirm), needs a look, another region, and kept. Each place shows its evidence:
  mentions with the story's own wording, the resolver fields, the region check, an
  OpenStreetMap pin when it has coordinates, and duplicate candidates.
- **Decisions.** The desk offers keep, merge, junk, kind of place, area and approve, plus a
  throughput counter.
- **Every decision is a Payload write** with the reviewer attached. The collection's
  `placeReviewGate` hook makes approve, junk and merge editor- or admin-only, and stamps
  `reviewedBy` and `verifiedAt`. `author` cannot approve. The desk redirects authors, and the
  hook refuses them.
- **Approval needs a real venue type.** The placeholder types (`editorial`/`unknown`) and the
  `city-guide` subtype are refused. Merged rows are now hidden from `/places` and the place page.
- **Driven end to end** on a scratch copy: set the kind, set the area, approve, and the place
  page returns 200. A merge, a keep and a bulk junk were driven the same way.
  `verify:competitor-policy` passes with 0 violations on both cities and on the scratch copy.

### P1.3, open-data half — plan (not built)

1. Load the Indonesia slices of FSQ OS Places and Overture Places (monthly Parquet) into a scratch
   schema: `geo_fsq`, `geo_overture` (name, normalised name, lat/lng, categories, address,
   `date_closed`/`operating_status`, source id). This needs one DDL decision from senior-db:
   the schema should live in each city database, not in `now_platform`.
2. For each queued place, block by `blocking_key` against both tables within the city's bounding
   box, score with the same `similarity`, and require area agreement. At ≥ 0.85, write `lat`,
   `lng`, `geo_source`, `geo_confidence`, `external_types` and `region_ok` through the same
   dry-run/`--apply` CLI. At 0.55–0.85, send the candidate to the desk's "Where it is" panel.
3. Rung B (Photon, then Nominatim) handles the residue. Rung C (Google) stays blocked on the
   owner's key and budget.

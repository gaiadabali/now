# NOW! Engine — Architecture

Multi-city lifestyle magazine platform. One engine, many cities.
First deployment: **NOW! Jakarta**. Second: **NOW! Bali**.

**Status:** design locked, implementation starting.
**Last updated:** 2026-09-08

---

## 1. Principles

1. **Places are first-class entities**, not article metadata. A hotel exists independently of any article about it. This single decision makes the suggestion rails, the itinerary builder and the partner system possible from one graph.
2. **Humans write `public`, machines write `engine`.** Payload owns editorial tables; Alembic owns derived tables. The `engine` schema can be dropped and rebuilt from `public` at any time.
3. **Articles never contain partner links.** They contain entity references. Link policy is resolved at render time from the current partnership.
4. **Deterministic engine decides, LLM narrates.** The itinerary solver picks stops; the LLM writes prose about what was picked. Never the reverse.
5. **Every recommendation cites a row.** The assistant may not name a venue that isn't in the database.
6. **Type exclusion is commercial policy, not a ranking preference.** It never relaxes, at any fallback rung, for any tier.
7. **No `if (site === 'bali')` in application code, ever.** Site differences live in config rows.

---

## 2. Topology

Three databases. City content is isolated; identity, commerce and vocabulary are shared.

```
┌───────────────────────────────────────────────────────┐
│  now_platform                                         │
│  public/  ← Payload    orgs · campaigns · placements  │
│                        sites registry · partner users │
│  engine/  ← Alembic    ad_events ledger · pacing      │
│                        facets + canonical terms       │
│                        identities · itineraries       │
└───────────────────────────────────────────────────────┘
          ▲                              ▲
┌─────────┴──────────┐        ┌──────────┴─────────┐
│  now_jakarta       │        │  now_bali          │
│  public/ ← Payload │ SAME   │  public/           │
│    articles·places │ SCHEMA │  places·events     │
│  engine/ ← Alembic │        │  engine/           │
│    embeddings      │        │    embeddings      │
│    entity_terms    │        │    entity_terms    │
│    interactions    │        │    interactions    │
│    covisitation    │        │    covisitation    │
│    travel_matrix   │        │    travel_matrix   │
└────────────────────┘        └────────────────────┘
```

Cross-city reads (rare) fan out at the application layer and merge. Not a hot path.

### Migration discipline — the price of DB-per-city

- `engine/packages/db/migrations/` is the **only** source of DDL.
- `site:migrate --all` iterates the site registry and applies in order.
- CI fails if any city DB's schema hash differs from expected.
- **Zero manual DDL on a city database, ever.**
- `site:create <slug>` provisions DB, runs migrations, seeds taxonomy from platform, inserts registry row.

### Services

| Service | Stack | Role |
|---|---|---|
| `engine-api` | Python 3.12 · FastAPI · SQLAlchemy 2 | read/write API, OpenAPI → TS client |
| `engine-worker` | Python · arq | embeddings, tagging, covisitation, pacing, matrix precompute |
| `cms-{site}` | Next.js + Payload 3 | one instance per city, same config package |
| `console` | Next.js | partner + campaign management (platform DB) |
| `postgres` | PG 16 + pgvector + PostGIS | 3 databases, one instance |
| `garage` | Rust, S3-compatible | media object store |
| `imgproxy` | — | on-demand image derivatives |
| `redis` | — | queue + cache |
| `caddy` | — | TLS, routing |

Host: Hetzner CPX41 (8 vCPU / 16 GB / 240 GB) + Cloudflare CDN.

---

## 3. Repository layout

```
now!/
  engine/
    packages/
      db/            ONE migration set → every city DB
      platform-db/   platform schema + client
      cms/           ONE Payload config → instantiated per city
      core/          ranking, itinerary solver, taxonomy logic
      ai/            prompts, embeddings, tagging, assistant tools
      config/        SiteConfig types + loader
    apps/
      api/  worker/  web/  console/
  jakarta/
    db/  site/  cms/  content/
  bali/
    db/  site/  cms/  content/
```

**`jakarta/` and `bali/` contain config, data and assets. Zero application code.**

---

## 3.4 What a "site" actually covers — a region, not a city

**A site covers a metro/region, which usually maps to an Indonesian province but is not required to.**
Confirmed with Hansel 2026-09-09.

| Site | Covers | Province-clean? |
|---|---|---|
| **NOW! Bali** | Provinsi Bali — 8 regencies + Denpasar. Ubud is in Gianyar; Canggu/Seminyak/Uluwatu in Badung. | ✅ exactly one province |
| **NOW! Jakarta** | **Jabodetabek** — DKI Jakarta **plus** Bogor, Depok, Tangerang, Bekasi | ❌ those four are in **West Java and Banten** |

So "province" is right for Bali and slightly too narrow for Jakarta. The location tree already models
this correctly (Jakarta's `Greater` branch holds BSD/Tangerang/Bekasi/Bogor) — only the *label* would
have been wrong. **Use `region` as the concept name**; `sites.location_term_id` points at that root.

This is not pedantry: the next city hits the same edge. A NOW! Yogyakarta would cover DI Yogyakarta
**plus Borobudur, which is in Central Java**. Coverage follows where readers actually go, not
administrative boundaries.

**Adding a region is five things, none of them code:**

```bash
site:create bandung     # DB + migrations + taxonomy seed + registry row + folder scaffold
```
then ① a location-tree branch (taxonomy **data**), ② brand tokens in the `sites` row,
③ one `cms-<slug>` compose service, ④ DNS.

**Zero application code — and that is enforced, not aspirational:** a CI lint fails the build on any
`'jakarta'`/`'bali'` literal under `engine/`, and a synthetic third tenant `test` runs the full suite
every build. `site:create test` produces a **byte-identical schema hash** to jakarta.

**One consequence to settle before Bali launches:** Jakarta currently holds **111 "Bali Updates"
articles**. Under the region model those are Bali's. `platform.engine.syndications` exists for exactly
this — they can move, be syndicated to both, or stay. An editorial call, not a technical one.

## 3.5 Site separation — how Jakarta and Bali differ

The sites are identical except for **five things, all of them configuration**:

| # | Differs | Where it lives |
|---|---|---|
| 1 | Content | separate city database |
| 2 | Brand, nav, rails, ranking weights, locale, timezone, currency | `sites` row in platform DB |
| 3 | Logo, fonts, OG images, copy overrides | `jakarta/site/` · `bali/site/` |
| 4 | CMS instance binding | `DATABASE_URI` env var |
| 5 | Hostname | DNS + Caddy |

Nothing else. **No forked code, no branches, no per-site modules.**

### Runtime topology — only Payload duplicates

```
engine-api    ONE instance   multi-tenant; site from /v1/{site}/… → city pool
engine-worker ONE instance   iterates the site registry
web           ONE instance   hostname → SiteConfig → city pool
cms-jakarta   ┐ same image, different DATABASE_URI
cms-bali      ┘ (Payload binds one DB per instance)
console       ONE instance   platform DB only
```

Payload is the only service that duplicates, because a Payload instance is bound to a single database. Everything else is one deployment serving all cities.

```
nowjakarta.co.id       → web
nowbali.co.id          → web
cms.nowjakarta.co.id   → cms-jakarta
cms.nowbali.co.id      → cms-bali
engine.now.id          → engine-api
```

### Connection routing

The API keeps a lazily-created connection pool per city, keyed by slug and built from the `sites` registry:

```python
Depends(get_city_db)      # site from path → pooled engine for that city DB
Depends(get_platform_db)  # single shared platform pool
```

Adding a city creates a pool. It does not create a deployment.

### Adding a city

```bash
site:create bandung          # provision DB · run all migrations · seed taxonomy
                             # · insert registry row · scaffold sites/bandung/
```

Then: add brand tokens, point DNS, add one `cms-bandung` compose service. No code change, no migration written, no redeploy of the API.

### Keeping them identical — enforcement

The rule is only real if it's enforced mechanically:

- **CI lint bans site-name literals** in `engine/` — a match on `'jakarta'` or `'bali'` fails the build.
- Any behavioural difference **must** be expressible as a `sites` column or an `enabled_modules` flag. If it can't be, that's a design bug, not a licence to branch.
- **A synthetic third tenant `test` runs in CI.** The full suite executes against it. If anything is implicitly Jakarta-shaped, this catches it long before Bali launch.

### Genuine per-site differences — handled by config

Real differences will appear. Bali skews tourist, Jakarta skews resident expat; Bali needs surf and diving subtypes, Jakarta needs traffic-aware itineraries. All of these are data or config:

| Difference | Mechanism |
|---|---|
| Different areas | location tree already branches per city |
| Different content types | `subtype` terms are scoped per site |
| Different ranking balance | `sites.ranking_weights` — Bali weights geo/freshness higher |
| Feature on/off | `sites.enabled_modules` |
| Different partner mix | separate `partnerships` rows, same schema |

### Cross-site content

Jakarta already carries 111 "Bali Updates" articles, so syndication is a real requirement, not a hypothetical.

With DB-per-city, the hot path must not do cross-database joins. Instead the article row is **physically copied into the target city DB with provenance**:

```sql
articles.origin_site_id       -- which city authored it
articles.origin_article_id    -- the source row
syndications(origin_site, origin_article_id, target_site, target_path, published_at)
```

Edits propagate origin → targets via the publish hook. Reads stay single-database and fast. The platform DB holds the syndication index so the console can see one article's full distribution.

---

## 4. Taxonomy

The legacy 75 WordPress categories conflate three orthogonal dimensions. Decomposed:

```
"Dining Offers"     → type:eat/restaurant + format:offer
"Dining News"       → type:eat/restaurant + format:news
"Restaurant Guides" → type:eat/restaurant + format:guide
"Bali Updates"      → format:news + location:bali
"Kids & Family"     → audience:family        (not a type)
"Green Living"      → topic:sustainability   (not a type)
```

### Facets

| Facet | Cardinality | Required | Drives |
|---|---|---|---|
| `type` | single | ✅ | competitor exclusion, Row 1 |
| `subtype` | single | ✅ | fine matching |
| `location` | multi, hierarchical | ✅ | Row 2, area clustering |
| `format` | single | ✅ | **decay half-life**, layout |
| `price_band` | single | venues | compatibility |
| `cuisine` | multi | eat | restaurant matching |
| `vibe` | multi | — | romantic, luxury, hidden-gem |
| `occasion` | multi | — | date night, business trip |
| `audience` | multi | — | expat, tourist, local, family |
| `amenities` | multi | venues | pool, rooftop, beachfront |
| `topic` | multi | — | sustainability, heritage, health |

### Type tree

Exclusion operates at **L1**. A villa is still a competitor to a hotel.

```
stay       hotel · resort · villa · serviced-apartment · boutique · glamping
eat        restaurant · cafe · bakery · fine-dining · street-food · food-court
drink      bar · rooftop-bar · cocktail-bar · beach-club · nightclub · pub · wine-bar
do         attraction · museum · gallery · adventure · watersports · tour · workshop
wellness   spa · gym · yoga · clinic
shop       mall · boutique · market · artisan
event      festival · concert · exhibition · conference · sports · community
editorial  news · opinion · people · business · education · heritage · city-guide
```

### Type relation matrix

```
type        exclude_same   complements
stay        true           eat, drink, wellness, do
eat         true           drink, do, event
drink       true           eat, do
wellness    true           eat, stay, do
shop        true           eat, drink
do          false          eat, drink, stay
event       false          eat, drink, stay
editorial   false          (all)
```

Stored in `engine.type_relations`, per-site overridable, editable without deploy.

### Location tree

Three levels. The area node is the fallback when geocoding is missing.

```
Indonesia
├─ Jakarta   South   Senopati·SCBD·Kemang·Blok M·Pondok Indah·Senayan·Cipete
│            Central Menteng·Thamrin·Sudirman·Gambir
│            North   PIK·Kelapa Gading·Ancol
│            West    Puri Indah·Kebon Jeruk
│            Greater BSD·Tangerang·Bekasi·Bogor
├─ Bali      South   Seminyak·Canggu·Kuta·Uluwatu·Jimbaran·Sanur·Nusa Dua
│            Central Ubud
│            East    Amed·Candidasa       North  Lovina
└─ Other     Yogyakarta·Bandung·Lombok·Komodo·Raja Ampat
```

### Format → decay half-life

48% of the archive is from 2019. A global decay either buries half the library or resurfaces dead events.

| format | half-life |
|---|---|
| news, event | 14–30 days |
| offer | hard expiry at `campaign.ends_at` — not decay |
| review, listing | ~18 months |
| guide, feature, heritage, people, city-guide | **evergreen, no decay** |

---

## 5. Data model

### City DB — `public` (Payload)

```sql
articles(id, kind, title, dek, body_blocks jsonb, hero_media_id, author_id,
         primary_type, format, published_at, legacy_wp_id, legacy_permalink,
         status, series_key)
places(id, org_id, name, slug, geo geography(Point,4326), address, area_term_id,
       type, subtype, price_band, hours jsonb, amenities jsonb, avg_dwell_min,
       booking_url, google_place_id, status, verified_at)
-- extended by F28: the 837 legacy events are their own WordPress post type, NOT
-- articles, each carrying its own title/body/thumbnail. An FK-only design would
-- have stranded that content with nowhere to land.
events(id, place_id, starts_at, ends_at, rrule, ticket_url,
       title, dek, body_blocks jsonb, hero_media_id,
       article_id,        -- OPTIONAL, editorial-only: link a recurring festival to
                          -- a feature. Never populated by the loader — body_blocks
                          -- is the source of truth, so there is only ever one.
       legacy_wp_id)      -- unique-indexed → idempotent upserts, same as articles
place_mentions(article_id, place_id, offset, surface_text, role)
media(id, storage_key, mime, width, height, alt, credit)
```

**`articles.body_blocks` schema — as shipped by E1.2, verified over all 4,772 articles:**

```json
[{"type":"heading","level":2,"text":"…","html":"…"},
 {"type":"paragraph","html":"…"},
 {"type":"image","media_ref":"…","alt":"…","caption":"…","href":"…"},
 {"type":"gallery","images":[{"media_ref":"…","alt":"…","caption":"…","href":null}],"caption":null},
 {"type":"list","ordered":false,"items":["…"]},
 {"type":"quote","html":"…","cite":"…"},
 {"type":"embed","provider":"youtube","url":"…"},
 {"type":"separator"},
 {"type":"columns","columns":[[…],[…]]},
 {"type":"raw_html","html":"…","reason":"unhandled_tag:table"}]
```

`gallery`, `separator` and `columns` were added beyond the original sketch — all three are more
common in the real corpus than several types the sketch guessed at. `raw_html.reason` is always
populated so unhandled constructs stay countable rather than invisible.

Content loss across the full archive: **median 0.000%, p95 0.000%, max 1.207%**; 4,764/4,772
articles at exactly zero. The 8 exceptions are bare oEmbed URL text deliberately excluded from the
visible-text metric. Only `<table>` (8 occurrences archive-wide) falls through to `raw_html`.

`media_ref` values are still original WordPress URLs — **E1.3's URL map is applied at load time**
(E1.8), using the `uploads[]` list which captures every inline reference including those outside a
structured `image` block.

### City DB — `engine` (Alembic)

```sql
entity_terms(entity_type, entity_id, term_id, weight, source, confidence)
embeddings(entity_type, entity_id, model, vec vector(1536))
-- AS SHIPPED (E0.2) — frozen contract with the beacon, do not change unilaterally
interactions(id, anon_id, user_id, session_id, entity_type, entity_id,
             kind, surface, rail, position, dwell_ms, scroll_pct,
             referrer, utm jsonb, device, ts)        -- PARTITION BY RANGE (ts)
  -- kind ∈ view|scroll|dwell|click|outbound|search|exit|thumbs_down
  -- TODO(C1): add `query text NULL` — search query text has no home; the beacon
  --           currently smuggles it through entity_id. Migration 0002.
impressions(id, session_id, anon_id, surface, rail, entity_id, position, ts)
                                                     -- PARTITION BY RANGE (ts)
covisitation(entity_a, entity_b, score, window, computed_at)
travel_matrix(place_a, place_b, seconds, meters, mode, computed_at)
rail_cache(article_id, segment_id, rail, candidates jsonb, rung, computed_at)
quality_scores(entity_type, entity_id, score, components jsonb)
```

### Platform DB

> **As shipped (E0.2):** every platform table lives in `now_platform.engine`, not split
> across `public`/`engine` as the §2 diagram suggests. A Payload instance will own
> platform `public` later, when the partner console (E4.4) needs an editing surface.
> `db_ref` is a **bare database name** (e.g. `now_jakarta`).
>
> **Not yet done, tracked:** platform tables carrying `site_id` (`partnerships`,
> `campaigns`, `placements`) are logically tenant-scoped inside one shared database but
> have **no RLS**. DB-per-city already isolates the highest-value boundary, so this is a
> real but secondary gap — revisit at E4.4. Likewise, one Postgres role currently does
> provisioning, migration and runtime queries; split roles/grants before the append-only
> `ad_events` ledger carries billing data (E4).

```sql
sites(id, slug, hostname, name, locale, timezone, currency, brand_tokens jsonb,
      nav jsonb, home_rails jsonb, ranking_weights jsonb, db_ref, status)
orgs(id, parent_org_id, name, slug, website, booking_url, logo_media_id, type)
partnerships(id, org_id, place_id, site_id, tier, starts_at, ends_at, status,
             link_policy, custom_url, utm_template, show_badge, badge_label,
             itinerary_eligible, boost_cap)
partnership_audit(id, partnership_id, actor_id, before jsonb, after jsonb, ts)
campaigns(id, org_id, site_id, objective, budget, pacing, targeting jsonb, status)
placements(id, campaign_id, surface, slot, boost_factor,
           guaranteed_impressions, freq_cap)
ad_events(id, campaign_id, placement_id, session_id, kind, ts)  -- partitioned, append-only
facets(id, key, label, cardinality, required)
terms(id, facet_id, slug, label, parent_id, geo, embedding vector(1536))
identities(id, email, created_at, stated_prefs jsonb)
user_profiles(user_id, site_id, taste_vec_long vector, taste_vec_short vector,
              facet_affinity jsonb, n_meaningful, updated_at)
itineraries(id, site_id, user_id, title, start_date, party jsonb, prefs jsonb, share_token)
itinerary_days(itinerary_id, day_index, area_term_id)
itinerary_stops(day_id, seq, slot, place_id, start_time, duration_min, note,
                source, campaign_id)
```

---

## 6. Ingest & enrichment (one-shot from WordPress)

WordPress is a **migration source only**. No ongoing sync, no adapter, no WP in production.

Source: `nowjakarta.co.id`, UpdraftPlus dump, MariaDB, prefix `nb15_`, 354 MB.

> **Figures corrected 2026-09-08 by E1.1.** The original numbers came from stream-parsing the
> gzip, which systematically **undercounts** — the same desync that zeroed `term_relationships`
> also dropped rows from large-blob tables. Every streaming-derived figure was a lower bound.
> The values below come from a real MariaDB restore + SQL and supersede them.

| | Real (SQL) | Was (stream-parsed) |
|---|---|---|
| Published articles | **4,772** (2019–2026) | 4,679 |
| Category coverage | **100%**, 93% single-category | 98.3% |
| Category terms | **76** (75 in active use) | 75 |
| Yoast focus keywords | **1,465** | 1,376 |
| Yoast meta descriptions | **2,057** | 2,019 |
| Attachments | 13,817 ✓ | 13,817 |
| `term_relationships` | 7,028 ✓ | 0 (parser failed) |
| Content length | median 4,802 chars | — |
| Tags | 1,347 — 1,071 unused → **discard** | — |
| Page builder | **none** — 86% plain HTML, 44% Gutenberg | — |
| Articles with ≥1 external link | **3,459 (72.5%)** | 2,529 (54%) |
| External links (absolute http/s) | **9,135** | "1,780+" |
| Distinct external domains | **1,835** raw / 1,768 after exclusions | 1,549 |
| Candidate partner orgs | **1,562** (from 3,914 partner links) | — |

**Geo coverage is far worse than first estimated.** Of the 261 `google_map` postmeta rows, only
**13** hold non-empty data — the rest are empty fields. Usable sources are 13 ACF points, a small
number of MapPress maps, and 136 `tribe_venue` addresses. Against ~2,500 venue-ish articles that
is **low single-digit percent**, not 15%. Geocoding (E2.5) is unambiguously the critical path for
Row 2 and the itinerary builder.

**Two extraction gotchas, both already handled in `wp-extract`:**
- `guid` is not a download URL for ~2,767/13,817 attachments (20%) — many carry a "pretty"
  attachment-page URL or the `nj.gaiada.com` staging host. Reconstruct from `_wp_attached_file`.
  **E1.3 must not trust `guid`.** *Verified against live 2026-09-08: the reconstruction is exactly
  right — 13,715 of 13,715 comparable attachments match the live `source_url` byte for byte.*
- `upcoming-events` (490 rows) carry **no structured start/end date** — only `post_date`, which is
  the publish date, not the occurrence date. A real data gap, not an extraction bug.

**Restore the dump into a throwaway MariaDB container and extract with SQL.** Do not stream-parse the gzip — it desyncs on `term_relationships`.

```
MariaDB restore
  ↓ extract    posts · postmeta · terms · relationships · users · redirections
  ↓ clean      HTML → blocks; strip shortcodes; preserve <p>/headings/embeds
  ↓ media      13,817 attachments → Garage; rewrite URL map
  ↓ links      outbound domains → org clustering → partner roster seed
  ↓ classify   type · subtype · format · location  (WP category = prior)
  ↓ extract    venue entities → places → geocode
  ↓ facet      vibe · cuisine · occasion · audience · amenities + confidence
  ↓ summarize  dek · key points
  ↓ embed      title + dek + facets + body
  ↓ score      quality
  ↓ review     confidence < 0.85 → human queue
```

**Cost:** ~4,772 × (2k in / 400 out) ≈ **under $25** on a Haiku-class model. Re-runnable.

**Ground truth for eval:** 1,465 `_yoast_wpseo_focuskw` + 2,455 `_yoast_wpseo_primary_category`.
Not reachable over REST — Yoast's `yoast_head_json` is disabled on both sites, so **Bali has no
equivalent until a dump exists**.

### 6.1 NOW! Bali — source analysis

Read from the live REST API on 2026-09-08 (`engine/packages/wp-harvest`); **no dump yet**.
Full detail in [LIVE_RECON.md](LIVE_RECON.md).

| | Bali | Jakarta (for comparison) |
|---|---:|---:|
| Published posts | **4,429** (2013-03 → 2026-09) | 4,772 (2019 → 2026) |
| Media library | **25,832** (24,746 enumerable) | 13,817 |
| `upcoming-events` | **182** | 489 |
| Categories | **50** | 76 |
| Tags | 2,319 | 2,311 |
| Authors | 53 | 70 |
| Comments | **4,103** | 0 |
| Pages | 37 | 64 |
| Originals to migrate | ≈5.4 GB (est.) | 3.7 GB (exact) |

**Bali's taxonomy is mostly not Jakarta's.** Only **16 of 50** category slugs are shared; **34 are
Bali-only**, and they carry markedly stronger venue-type signal than Jakarta's editorial
categories — `restaurants-bars` (360), `spa` (209), `hotels-resorts` (140), `activities` (119),
`explore-bali` (117), `bali-bar-guide` (76). The facet mapping review therefore spans **110
categories across two cities**, and Bali's typing (E2.3) may well be *easier* than Jakarta's was.

**Content quality is high**: 0 missing titles, 0 missing bodies, 100% category coverage, 4.4%
without a featured image, ~5% Gutenberg (the rest classic-editor HTML).

**Bali has no legacy CKEditor store** — zero such refs, against 6,161 on Jakarta. Its inline media
resolves to the manifest at **96.7%**.

**What is still missing for Bali, and why a dump is required** (see F37): REST returns rendered
`the_content`, not the raw column; it omits unregistered `postmeta` entirely (**no Yoast focus
keywords, no MapPress geo, no ACF**); it hides drafts; and it cannot enumerate 1,086 of the
attachments. The harvest is sound for planning, sizing and taxonomy work. **It must not be loaded
as though it were dump-derived.**

---

### Known data issues

- **`wpb_post_views_count` is bot-contaminated.** Median 1,066, p25 856, zero articles at 0, top 10% = only 27% of views. Use the head (~top 300) as a popularity prior; **discard the tail.**
- **~~No analytics installed~~ — WRONG, corrected 2026-09-08 by live recon.** Google Tag Manager
  is **hardcoded inline in both themes**: Jakarta `GTM-5JTV355` (plus a Facebook Pixel), Bali
  `GTM-NJF57G3`. It is absent from the `options` table precisely because it was pasted into the
  theme, which is why a dump-only check missed it. **Behavioural history may therefore exist** in
  whatever GA4 property those containers feed — enumerating it needs GTM access, not DB access.
  Google Search Console (16 months of query→page→click) is still worth having and needs no plugin.
- **SEO exposure — measured, not estimated (E1.5).** Of **9,135** external links across the archive,
  **9,128 (99.9%) carry no `rel` attribute at all.** `nofollow` appears on 7; **`sponsored` on zero.**
  Every historic paid placement has been passing full PageRank. Against 911 articles in the
  "Offers" categories and 1,562 candidate partner orgs, that is a live link-scheme exposure on a
  domain whose top traffic is SEO listicles. Fixed structurally by tier-driven rendering (§11) —
  `rel="sponsored"` becomes a property of the tier, applied by the renderer, archive-wide.
  *(My earlier figure of "~1,780+ links, nofollow 5" came from the undercounting parser.)*
- **Series duplicates**: "New Restaurants in Jakarta 2024 / 2025 [Updated]" — cluster via `series_key`.

---

## 7. Retrieval & ranking

### Offline / online split

```
OFFLINE (worker)                        ONLINE (p95 < 120ms)
embeddings · facets · geocode           resolve article
travel matrix · covisitation            ├─ Row 1 complementary
popularity priors                       ├─ Row 2 nearby (PostGIS)
segment rail precompute ──────────────→ └─ Row 3 similar (pgvector)
                                             ↓ parallel
                                        filter pipeline
                                        personalized re-rank (top ~40)
                                        MMR diversify
                                        promo slot injection
```

Rails are precomputed per `(article_id, segment)` — ~20 coarse taste segments — then re-ranked against the individual user vector at request time. A dot product over 40 rows, sub-millisecond.

### Blender

**Corrected 2026-09-09 by E3.3.** The original formula below had two defects, both found by
implementing it:

```
score = w_sem·semantic + w_cf·covis + w_fresh·decay(format) + w_qual·quality
      + w_geo·proximity + w_promo·boost − diversity_penalty          ← WRONG
```

① **No lexical term.** Re-ranking by this formula *discards* the BM25 signal, so a document that
won RRF's pool on an exact-phrase match gets outranked by a merely-semantically-similar one with a
better quality score. Measured: headline nDCG fell 0.7642 → 0.375 for exactly this reason.
② **`− diversity_penalty` is not a weight.** It is MMR's own `(1−λ)·max_sim` term. Treating it as a
seventh blend component double-counts diversity.

The three stages are distinct and must stay that way:

```
1. FUSE      fused = RRF(lexical_rank, semantic_rank)      rank-based, scale-free
             BM25 and cosine are not comparable scales — this is why RRF exists.

2. RE-RANK   score = w_rrf·fused                           ← carries the lexical signal forward
                   + w_sem·semantic + w_cf·covis
                   + w_fresh·decay(format) + w_qual·quality
                   + w_geo·proximity + w_promo·boost
             Post-fusion these ARE comparable, so a weighted sum is meaningful here.

3. DIVERSIFY final = MMR(score, λ≈0.7)                     diversity lives here, not in the sum
```

Weights in `sites.ranking_weights`, tuned **per surface**, editable without deploy.

### The three rails

| | Row 1 Complementary | Row 2 Nearby | Row 3 Similar |
|---|---|---|---|
| Pool | `complements[type]` | any geo'd place | semantic kNN |
| Type rule | exclude same L1 | exclude same L1 | exclude same L1 |
| Geo | same area preferred | **within radius (hard)** | ignored |
| Price | compatible band | — | — |
| Extra | vibe compatibility | open-now soft | series dedup |

Row 1 compatibility at cold start:

```
compat(stay, eat) = price_band_proximity × vibe_overlap × geo_proximity × user_taste
```

Replaced by learned cross-type covisitation once traffic exists.

### Search

Hybrid: `tsvector` BM25 + `pgvector` cosine, fused with Reciprocal Rank Fusion. All in Postgres. No Elasticsearch until >100k documents.

---

## 8. Filters

### A. Hard — never violated

| Filter | Rule |
|---|---|
| Tenancy | `site_id` matches or explicitly syndicated |
| Status | published, not draft/trash/private, embargo respected |
| Self | never the current article |
| **Competitor** | same L1 `type` excluded — **all tiers, free included** |
| Event expiry | `ends_at < now()` |
| Offer expiry | past `campaign.ends_at` |
| Venue closed | `place.status = closed` |
| Quality floor | below `quality_score` threshold |
| Series dedup | one per `series_key` |

### B. Contextual

already-read (decaying) · already-shown-this-session · already-in-itinerary ·
open-at-time · trip date window · party constraints (kids, accessibility, halal,
vegetarian, budget ceiling)

### C. Soft — down-weight only

```
down-weight:  low facet affinity · seen-not-clicked · over-represented area
hard filter:  explicit thumbs-down · user-muted facets   ← only user-chosen
```

Personalization never hard-filters. The reader may filter themselves; the algorithm may not.

### D. Diversity (post-filter)

```
MMR λ ≈ 0.7 · max 1 per org · max 2 per area · max 2 per format · max 1 paid per rail
```

`max 1 per org` matters: marriott.com appears 63× in the archive.

### E. Commercial

targeting · frequency cap · budget pacing · category exclusivity

**A budget-exhausted campaign stays eligible organically** — it simply isn't logged as a billable impression. Relevance and billing are separate decisions.

### F. Fallback ladder (starvation)

Every rail must fill. Evaluate rungs until slot count is met; record the rung reached.

```
1. strict            all filters
2. widen radius      2km → 5km → 15km
3. drop open-now
4. area → district → city
5. drop freshness decay
6. editorial fallback  curated/popular for type+area
```

**The competitor filter never relaxes at any rung.** If Row 2 hits rung 5 on >30% of pages, that is the geocoding backlog surfacing as a metric.

### G. Filter ordering (performance)

```
site → status → type → area      cheap, selective, indexed  → push into SQL
      ↓
  vector kNN / PostGIS           expensive → runs on small candidate set
      ↓
  session, already-read, caps    per-user → in memory, ~40 rows
```

Never retrieve 100 by embedding then filter to 3. Partial indexes on `(site_id, type, status)` and GiST on `geo`; constrain the vector search rather than post-filtering.

**Corrected 2026-09-14 by the `/search` endpoint.** "Constrain rather than post-filter" holds when the
candidate set is **selective**. It *inverts* when the set is most of the corpus: `= ANY(:ids)` with a
near-corpus-sized array defeats both indexes. Measured on Jakarta's 4,772 articles with the 3,421-id
pool the §8.A hard filters alone produce — i.e. the **default, unfiltered request**:

```
                 constrained        unconstrained
semantic            49.2 ms             1.2 ms      ← 41×, HNSW degraded to a scan
lexical             49.3 ms            15.2 ms      ← 3.2×, GIN index bypassed
```

So the rule is selectivity-dependent, and the threshold is a real number, not a vibe
(`now_search.engine.LARGE_CANDIDATE_SET`, currently 1,000):

| Candidate set | Path |
|---|---|
| ≤ threshold (reader picked facets) | push into SQL — §8.G as written |
| > threshold (hard filters only) | retrieve unconstrained, over-fetch, filter in memory |

**The trap that makes this dangerous.** The post-filter path is only sound if the unconstrained query
is *exact*. pgvector's HNSW is **approximate**: at `hnsw.ef_search = 40` with `iterative_scan = off`,
asking for 400 rows returned **28** — a short result that a post-filtering caller reads as "the index
is exhausted" when it means "the ANN scan stopped early". Recall drops silently behind a healthy
`200`. This is F67 resurfacing in a new caller. The fix is `search_semantic(exact=True)`: the same
materialized-CTE plan the restricted path uses, minus the id filter — exact, complete, and *faster*
than the large array (35 ms vs 49 ms).

Net: `/search` p95 **195 ms → 69 ms**, results byte-identical to the constrained path across the
hand-check query set (`packages/search/tests/test_candidate_set_strategy.py` is the regression gate).

---

## 9. Reader-facing filters

Same facets, exposed. Live counts computed in one aggregate pass.

```
Type ▸ subtype          Area ▸ district ▸ neighbourhood
Price  $ · $$ · $$$ · $$$$        Cuisine (when type=eat)
Vibe                    Occasion            Amenities
Open now ▢              Date range (events)
```

**Combination logic**
- Within a facet: **OR** — `cuisine ∈ {japanese, italian}`
- Across facets: **AND** — `type=eat AND area=senopati AND price=$$`
- Hierarchical: selecting a parent includes descendants — `area=South Jakarta` ⊃ Senopati

**Facet counts** use the ecommerce rule: when computing counts for facet *F*, apply every filter **except** *F*. Otherwise unselected options all read zero.

**Partner tier is never exposed as a filter or sort.** Readers must not be able to sort by who paid.

### URL structure = named facet queries

Preserves SEO (the top-traffic listicles) while being facet-driven underneath.

```
/{section}              dining · hotels · bars · things-to-do · events · wellness
/{section}/{area}       /dining/senopati
/areas/{area}           area landing
/places/{slug}          place profile
/{slug}                 article — MUST match legacy WP permalink
/search?q=&type=&area=&price=
/guides/{slug}          curated guide
/itinerary/{token}      shared itinerary
```

Legacy permalinks are preserved in `articles.legacy_permalink`; the `nb15_redirection_items` table is imported as an additional 301 map.

---

## 10. Personalization & ML

### Stated vs revealed

```python
α = n_meaningful / (n_meaningful + 20)
taste = α · revealed + (1 − α) · stated_seed
```

No cutoff, no cliff. Registration picks remain a prior forever.

### Two representations, both required

| | Facet affinity (sparse) | Taste embedding (dense) |
|---|---|---|
| Use | filtering, **explaining**, user-editable | ranking, nuance |
| Cold start | direct from registration | centroid of chosen term embeddings |

### Two speeds

```python
long_term  = Σ wᵢ · decay(tᵢ, half_life=180d) · embed(itemᵢ)
short_term = Σ wᵢ · embed(itemᵢ)              # last ~10 interactions
β = 0.6 if session_interactions ≥ 3 else 0.2
intent = β · short_term + (1 − β) · long_term
```

A reader planning a trip has a session intent unrelated to their year-round taste.

### Signal weights

```
impression, no click   −0.1     saved / shared         1.0
click                   0.3     added to itinerary      1.2   ← strongest
dwell ≥ 30s             0.6     thumbs down            −1.0
scroll ≥ 70%            0.8
```

### Registration (keep under 30 seconds)

```
1. What are you into?   eat·drink·stay·do·wellness·culture·events    pick 3+
2. Where do you spend time?   area chips, 1–3
3. You're...  expat · local · visiting · business
4. Budget  $ · $$ · $$$ · $$$$   (skippable)
```

Expose it back: a preferences page showing "we think you like: Japanese food, Senopati, rooftop bars", editable. Corrections are high-quality training signal.

### ML roadmap

| Stage | What | Needs | When |
|---|---|---|---|
| **0** | LLM enrichment + embeddings | nothing | week 2–3 |
| **1** | Hybrid retrieval, heuristic blender, popularity prior | nothing | week 4–5 |
| **2** | Beacon → covisitation, cross-type affinity | ~50k sessions | +6–8 wks |
| **3** | Taste vectors, stated↔revealed blend, **LightFM** | ~3 months | +3 mo |
| **4** | **LightGBM LambdaMART** re-ranker | ~6 months clicks | +6 mo |

**LightFM, not plain ALS.** A magazine publishes constantly — every new article is a cold item. Pure collaborative filtering cannot rank what nobody has clicked. Hybrid MF uses content features *and* behaviour.

### Stage-4 feature vector — log from day one

```
semantic_sim · bm25 · covis_score · type_compat · price_compat
geo_distance · same_area · freshness(type-aware) · quality · popularity_prior
user_facet_affinity · user_vec_sim · session_intent_sim
author_affinity · seen_before · position_bias
```

Logged at serve time while the blender is still hand-tuned, so the training set accumulates.

### Presentation-bias warning

Readers can only click what was shown. Training a ranker on legacy widget clicks teaches it to reproduce the old plugin.

| Data | Safe for | Not safe for |
|---|---|---|
| Organic navigation paths | covisitation, cross-type affinity | — |
| Dwell / scroll | quality scoring | — |
| Widget clicks | weak popularity | **stage-4 ranker training** |
| Impressions + position | position-bias correction (IPW) | — |

---

## 11. Partnerships & commerce

### Mechanism

Articles store entity references, never URLs.

```html
… stayed at <span data-place="viceroy-bali">The Viceroy Bali</span> …
```

Resolved at render:

```
mention(place_id) → place.org_id → active partnership (org|place, site, now())
   ├─ paid    → <a href=… rel="sponsored" data-partner=…> + badge + click log
   ├─ listed  → internal link → /places/viceroy-bali
   └─ free    → plain text
```

- Partner signs → **all historical mentions become links instantly**, no article edits
- Contract lapses → reverts **automatically at `ends_at`**
- `rel="sponsored"` enforced by tier, archive-wide, cannot be forgotten

### Tier ladder

| Tier | In-article | Place page | Itinerary | Rails |
|---|---|---|---|---|
| **free** | plain text | listed | eligible | organic only |
| **listed** | internal link | enriched + photos | eligible | organic only |
| **paid** | external link + badge | full profile + booking CTA | guaranteed slots | capped boost |

**Competitor exclusion is identical across all three tiers.** Tier controls link rendering only.

### Admin

One screen: org, tier, status, contract dates, linked mention count, impressions/clicks.
On save, show blast radius — *"this affects 40 articles across 3 venues"* — before committing.

### Commercial guardrails

- Slots, not silent boosts. Surfaces declare slots; campaigns book into them.
- Boost capped within a relevance floor.
- Immutable append-only `ad_events` ledger — the invoice basis.
- Pacing + frequency caps.
- Always labelled: "Partner" / "Presented by".

---

## 12. Itinerary engine

**OR-Tools CP-SAT.** An itinerary is a VRP with time windows: opening hours, dwell times, travel matrix, budget ceiling, category diversity, guaranteed partner slots. No TypeScript equivalent comes close — this is why the engine is Python.

```
1. CANDIDATES   site · dates · party (kids/budget/mobility) · interest facets · open-at
2. GEO CLUSTER  PostGIS cluster into day-groups by area
3. SLOT FILL    breakfast → morning → lunch → afternoon → dinner → night
4. SEQUENCE     order within day by travel time
5. LOCAL SEARCH swap for variety, price fit, partner placement
6. NARRATE      LLM writes "why this stop" — picks nothing
```

Curated itineraries are first-class content ("48 Hours in Canggu") — good SEO and ground-truth training data. Users fork, edit, share.

**Constraint satisfaction is programmatically checkable** — no closed venues, travel budget respected, category diversity, price ceiling. Gate at 100%.

---

## 13. AI assistant

Two agents, one grounding rule.

**Reader-facing** tools:
```
search_content(query, filters)     find_places(facets, geo, open_at)
get_events(date_range, area)       build_itinerary(params)
save_itinerary / share             escalate_to_human
```

**Every recommendation must cite a `place_id` or `article_id`.** Not in the DB → the assistant says it doesn't know.

**Editor-facing** (bigger near-term ROI): auto-facet-tagging, entity extraction and linking, dek + SEO meta, image alt text, EN↔ID translation, related-archive suggestions.

Model routing: cheap model for batch tagging and embeddings, strong model for conversation.

---

## 14. Media

```
Browser → Cloudflare CDN → imgproxy → Garage (Hostinger VPS)
```

**Garage** (Rust, AGPL-3.0, S3-compatible) over MinIO: ~100 MB RAM idle, and MinIO gutted its community console in 2025. The object store is not the bottleneck — behind a CDN, >95% of image requests never reach origin.

**imgproxy** generates derivatives on demand rather than pre-rendering every size for 13,817 attachments.

Portable: Garage → R2/S3 is an endpoint change.

---

## 15. Maps — split four ways

| Job | Use | Why |
|---|---|---|
| Geocoding | **Google Places/Geocoding**, one-time | Indonesian addresses are messy; accuracy matters. Store `place_id`. |
| Nearby radius | **PostGIS `ST_DWithin`** | µs, free, no ToS limits. **Never call Google per request.** |
| Travel time | **OSRM** self-hosted + Google Distance Matrix *sampled* for traffic multipliers | Jakarta traffic is the problem; needs a cached matrix, not live calls |
| Display | **MapLibre GL** | Google Maps JS gets expensive fast |

Google ToS permits storing `place_id` indefinitely but restricts caching other fields. Treat Google as a **resolution service**; keep your own canonical record.

Free seed: MapPress holds real coordinates for ~261 posts; 136 `tribe_venue` rows have addresses.

---

## 16. API surface

The **API is the durable deliverable** — the legacy UI is a probe that gets replaced.

> Design endpoints for the domain, never for the legacy theme's markup.

```
GET  /v1/{site}/feed?surface=home&rail=trending
GET  /v1/{site}/articles/{slug}
GET  /v1/{site}/articles/{id}/rails          → all three rows          ✅ served
GET  /v1/{site}/search?q=&type=&format=&facets=                        ✅ served
GET  /v1/{site}/places?facets=&near=&open_at=
GET  /v1/{site}/places/{slug}
POST /v1/{site}/itineraries
GET  /v1/{site}/itineraries/{token}
POST /v1/{site}/assistant/messages           SSE
POST /v1/{site}/events                       interaction beacon        ✅ served
```

`/search` takes `format=` where this list originally said `price=`: `price` is not an attribute any
article carries today, and `area` is not a column but a **term facet**, reached through the generic
`facets=location:senopati` selector rather than its own parameter. Unmatched selectors come back in
`unresolved_facets` instead of being silently dropped — a typo'd filter that returns the whole corpus
is indistinguishable, to the caller, from one that legitimately matched everything.

OpenAPI → `openapi-typescript` → TS client in CI.

---

## 17. Evaluation

### Engine Inspector — build before any public widget

Internal page: enter an article or query, see every candidate generator's output, per-component scores (`semantic 0.71 · fresh 0.22 · quality 0.55 · geo 0.10 · promo 0.00`), MMR penalty applied, final order with reasons, and **which fallback rung each rail landed on**. Tuning a blender without this is guesswork.

### Eval harness — CI gate

| Surface | Metric | Gate |
|---|---|---|
| Related articles | precision@6 vs ~200 editor-labelled pairs | no regression |
| Search | nDCG@10 vs labelled query set (seed from GSC) | no regression |
| Facet tagging | precision/recall vs held-out Yoast labels | ≥0.85 before auto-apply |
| Type classification | accuracy vs reviewed sample | ≥0.95 — gates competitor exclusion |
| Itinerary | constraint satisfaction | **100%, hard fail** |
| Itinerary | editor plausibility 1–5 | tracked |

### Shadow mode

Once retrieval works, compute what the engine *would* recommend for live traffic and log it against what readers actually did. Offline evaluation on real traffic, zero user impact, months before launch.

---

## 18. Open decisions

| # | Question | Default if unanswered |
|---|---|---|
| 1 | Google Search Console verified? 16mo of query→page data | assume unavailable |
| 2 | Is a GA tag hardcoded in the theme? | assume none |
| 3 | Legacy permalink structure — `/{slug}` or dated? | preserve exactly as found |
| 4 | Already-read suppression window | 14 days, then decay back |
| 5 | EN only, or EN + ID? | EN only for v1 |
| 6 | `wp-content/uploads` size | pending — needed to size media migration |
| 7 | Bali content source — new, or split from Jakarta? | new |

---

## 19. Sequence

| Phase | Ships |
|---|---|
| **E0** | Foundations: compose, schemas, migration runner, API skeleton, **beacon** |
| **E1** | Ingest: MariaDB extract, cleaning, media → Garage, taxonomy, partner roster |
| **E2** | Enrichment: classification, facets, places, geocode, embeddings, **eval harness + Inspector** |
| **E3** | Retrieval: hybrid search, three rails, filter pipeline, API v1 |
| **E4** | Commerce: partnerships, link resolution, campaigns, ledger, console |
| **E5** | Itinerary: OR-Tools solver, travel matrix, narration |
| **E6** | Assistant + Bali provisioning |

**The beacon ships in E0, before anything consumes it.** Behavioural data cannot be backfilled, and there is currently no analytics on the live site. Every week without it delays Stage 2 by a week.

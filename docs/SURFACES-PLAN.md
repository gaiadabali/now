# The three surfaces — consolidation and plan

**Status:** plan agreed 2026-09-18. Shipped the same day: **S1** (foundations),
**S2** (site honesty), **S3** in full (one admin chrome, grouping, article tabs,
wording), **S4.1–S4.2** (preview) and **S5.1** (the sites registry console).
Open: **S4.3**, **S5.2–S5.5**, **S6** (visual direction), **S7** (engine wiring).

Nothing is deployed. See §7.
**Companion to:** [ARCHITECTURE.md](../ARCHITECTURE.md) (decisions),
[PROGRESS.md](../PROGRESS.md) (execution state),
[ADMIN-CONSOLIDATION.md](ADMIN-CONSOLIDATION.md) (how six hostnames became two).

**Supersedes:** PROGRESS.md's "STATUS AT A GLANCE" critical-path claim. That
section still headlines *"F50: every `primary_type` is NULL, the rails do not
run"*. Measured against the live local databases on 2026-09-18:

```
now_jakarta   4,772 published   3,589 typed (75%)
now_bali      4,429 published   3,636 typed (82%)
```

F50 is closed for three quarters of the archive. It is no longer the thing
gating everything, and treating it as such has kept attention off the three
surfaces that are now the actual bottleneck.

---

## 1. Why all three complaints are one complaint

The owner's report, in his words: the website needs redesign and better
layout; the CMS needs better layout and easier-to-see tools and preview,
*for writers and not engineers*; the platform console needs major redesign
and **connectability to the CMS and the websites**.

Those read as three jobs. They are one, and it is worth stating precisely
because it decides the order of the work:

> **The engine is built and the surfaces do not reach it.** There is one
> design system and four stylesheets that half-share it. There is one site
> registry and nothing reads it. There is a ranked-retrieval API and the
> reader site calls one endpoint of it.

Concretely, and each of these is verified in §2 rather than asserted:

- `engine.sites` carries `nav`, `home_rails`, `brand_tokens` and
  `ranking_weights`. All four are `{}` on all three rows, and
  `getSiteConfig()` reads a baked JSON file anyway. **The console governs
  nothing because nothing reads the registry.**
- `public.articles` has **no `slug` column**. The public URL is
  `legacyPermalink`, and that field is labelled DO NOT EDIT. **The CMS cannot
  publish a new article to a reachable address.**
- The homepage's "The Guides" and "What's On" render a fixture file.
  **The reader site shows invented content in two of its six slots.**

Fix the seams and most of the "redesign" becomes layout over real content.
That is why the first ticket is not a stylesheet.

---

## 2. What is true today

### 2.1 The reader site — `apps/web/src/app/(site)`

The visual language is real work and is not the problem.
[`tokens.css`](../engine/apps/web/src/styles/tokens.css) is a considered
broadsheet system: warm paper ground, logo ink rather than black, three rule
weights and never a fourth, prose capped at 66ch, a fluid thirds-based scale
whose display sizes are deliberately larger than a blog would dare. There is
a `/design` reference page. Cormorant and Heebo are the brand's own faces,
self-hosted through `next/font`.

What is wrong is underneath it.

| | Evidence |
|---|---|
| **"The Guides" and "What's On" are fixtures** | [`src/fixtures/editorial.ts`](../engine/apps/web/src/fixtures/editorial.ts) — four hardcoded guides with counts its own comment calls "illustrative", and four Bali events (Ubud Writers, Sanur Village). Rendered on Jakarta too. |
| **"Most Read" is recency** | `getMostRead()` is `return getLatest(limit)`. The comment is honest about it; the page label is not. |
| **`/latest` 404s, linked twice from the homepage** | Not in `SECTION_MAP`, so `isSectionSlug` is false, so `[slug]` looks it up as an article and calls `notFound()`. No article has that address. |
| **The four guide cards 404** | They link to `/guides/dining` and siblings. `[slug]` is one segment. |
| **"Read Next — chosen by the engine" is not** | Same-section recency. `GET /v1/{site}/articles/{id}/rails` is live; the code comment defers wiring it until the beacon ships so impressions are logged. **The beacon shipped in wave 24.** The stated precondition is met. |
| **The homepage layout is hardcoded** | `sites.home_rails` exists for exactly this and is `{}`. |
| **Two breakpoints** | `62rem` and `36rem` across all 646 lines of `magazine.css`. The masthead nav never collapses; it scrolls sideways, which the component comment defends and which is still the only mobile affordance in the app. |
| **Reader-facing filters stop at section + format** | §9's URL-as-named-facet-query is half-built. Of seven facets, four carry any data at all. |

Facet coverage, measured across both databases on 2026-09-18:

```
location  8,052    format  3,906    type  3,589    subtype  1,690
topic · audience · price_band · vibe · cuisine  →  0
```

The zero-coverage facets matter twice over: the 30-second preference picker
collects 36 topics, and nothing in either archive is tagged with one.

### 2.2 The CMS — `/team-editor`

The owner's framing is the right one: this is for news and article writers,
not engineers or site maintainers. Held to that standard:

**The blocker, which is not on any existing list.** `public.articles` columns
are `id kind title dek body_blocks hero_media_id author_id primary_type
format published_at legacy_wp_id legacy_permalink series_key updated_at
created_at _status`. There is no `slug`. `getBySlug()` matches
`legacyPermalink = '/{slug}/'` exactly, and the `legacyPermalink` field's
own description reads *"DO NOT EDIT — every redirect from the old site is
matched on this exact string."*

So a writer who creates a new article produces a row with no public address,
and the only field that could give it one is correctly marked untouchable.
Places and Authors both have `slug`. Articles were the collection that
needed it most and are the one that never got it.

**Everything else, in order of how much it costs a writer per day:**

- **No preview, of any kind.** No `admin.preview`, no `admin.livePreview`,
  nowhere in the package. The body editor
  ([`BodyBlocksEditor.tsx`](../engine/packages/cms/src/fields/BodyBlocksEditor.tsx))
  has a read-it-back pane, and its own header says the real route in an
  iframe "is the better answer eventually; it needs draft-mode plumbing
  through the public site, which is not a thing to reach into for a writing
  convenience." That plumbing is now the job.
- **One flat field column.** Zero `type: 'tabs'`, zero `type: 'group'`,
  zero `type: 'collapsible'`, zero `position: 'sidebar'` across every
  collection. On `articles` that puts **Legacy WP ID** and **Legacy
  permalink** inline in the writer's column, between the dek and the body.
- **No collection grouping.** Articles, Places, Classification reviews,
  Events, Place mentions, Media, Authors and Users are one flat sidebar
  list. No `admin.group` anywhere.
- **Three unrelated chromes under one path.** Payload's own shell for
  collections; `classification/report.css` (866 lines) with its own
  masthead; `commerce/console.css` (261) with another. The two bespoke
  mastheads **replace** Payload's sidebar rather than sitting inside it, so
  the only way back is a small `editor` badge in the corner. Plus
  `staff/staff.css` (215). Four stylesheets, one token file.
- **Engineer's vocabulary on writers' screens.** "Primary type", "Dek
  (standfirst)", "Series key", "Legacy WP ID", "Unclassified".

What is genuinely good and should be kept: the writing surface itself. It was
rebuilt from a JSON code editor, its toolbar is always visible and labelled
in words after the owner asked what the two halves were for, it counts the
11,042 run-on paragraph blocks and offers to split them, and it refuses to
render `white-space: pre-wrap` because that would make the editor the one
surface telling a flattering lie. That reasoning stands.

### 2.3 The platform console — `/team-editor/commerce`

It is not a console. It is four read-only tables behind a role gate.

- `apps/console` builds nothing. Its own `package.json` says so: *"NOT an
  app: its pages became /team-editor/commerce and its admin is retired. It
  exists so `public.users` has a migration home."*
- The surface is Overview, Partners, Partnership detail, Campaigns. Every
  page opens with `await requireCommerceAccess()` and then `SELECT`s. There
  is no write path anywhere.
- `engine.partnerships` has **0 rows**. `campaigns` 0. `placements` 0.
  `orgs` has 1,562. So the one table the console exists to manage is empty,
  and the tier ladder in §11 has never been exercised against real data.
- ARCHITECTURE §11 specifies *"One screen: org, tier, status, contract
  dates, linked mention count, impressions/clicks. On save, show blast
  radius — 'this affects 40 articles across 3 venues' — before committing."*
  None of it is built.
- **Connectability is zero, and it is one function.** `SiteRow` in
  `sites_registry.py` does not even select `nav`, `brand_tokens`,
  `home_rails` or `ranking_weights`.
  [`lib/site.ts`](../engine/apps/web/src/lib/site.ts) already names the fix:
  *"Swapping the body of `getSiteConfig()` for a registry read is the only
  change that migration needs — every consumer is already typed against the
  contract, not the file."*
- No cross-city surface. `engine.syndications` exists and nothing uses it.
  A Jakarta ↔ Bali article move must bridge through `now_platform` and never
  city-to-city; that is the console's job and it has no screen.
- Commerce tables live in `engine`, Alembic-owned, because
  `now_link_resolver` reads `engine.partnerships` **on the request path**.
  Moving them into `public` for Payload to own is E4.4 and has its own blast
  radius. It is not a side effect of adding a write form.

---

## 3. Decisions taken

### D-S1 — the platform console is a section of `/team-editor`, not a fourth app

A new `/team-editor/platform` area beside commerce. One login, no DNS
record, no CloudPanel site, no container, and it inherits whatever admin
shell §4's CMS work produces.

This accepts the isolation trade-off ADMIN-CONSOLIDATION.md already wrote
down and chose once: platform data is reachable from a city admin session,
prevented by access rules rather than by hostname separation. That document's
sentence applies unchanged — *"it means the access rules become
security-critical code and must be tested as such, not eyeballed."*

Rejected: reviving `apps/console` as its own app on `now-console.gaiada.com`.
It buys real separation and is the natural home for a view that is not
"inside Jakarta", and it costs a DNS record, a certificate, a container, a
second deploy path and a second session audience — to serve, today, five
staff accounts. Revisit if staff grows or if a partner ever gets a login of
their own, which is the point at which the trade-off actually changes.

### D-S2 — the reader site gets a new visual direction

Not an evolution of the broadsheet system. The token file, the type pairing,
the grid and the chrome are all open.

Two constraints on that work, because they are architectural rather than
aesthetic and a redesign that breaks them is a redesign that gets reverted:

1. **§3.5 holds.** One image serves every city, differentiated only by
   `SITE_SLUG` at runtime. No site-name literal may enter `src/`;
   `npm run lint:site-literals` enforces it mechanically. A new direction
   that hardcodes one city's palette fails the build, correctly.
2. **Nothing may be prerendered** under `(site)`. Both root layouts are
   `force-dynamic` for a reason that cost a production incident: a static
   build resolves `getSiteConfig()` at build time and bakes one city's
   masthead, nav and `metadataBase` into the shared image, and freezes
   `new Date()` into the dateline forever.

The `/design` page is noindexed and exists to be the reference for whatever
the direction becomes. It gets rewritten, not deleted.

**Sequencing, stated plainly:** the visual direction is designed against
real content in every slot, not against fixtures. That is why S2 (honesty)
precedes S6 (direction) even though the owner's list put the website first.
Designing a "What's On" rail around four invented Bali events produces a
layout that fits invented Bali events.

### D-S3 — first move is the article slug and the config spine

The two blockers underneath everything else, and both are small. A slug is
what makes the CMS able to publish; a registry read is what makes a console
able to govern. Neither is a redesign, and every later phase is cheaper once
they exist.

---

## 4. The plan

Seven phases. Each ships and is useful on its own. Phases with no dependency
arrow between them can run in parallel.

```
S1 foundations ──┬── S2 site honesty ──┐
                 │                     ├── S6 visual direction ── S7 engine wiring
                 ├── S3 admin shell ───┤
                 │        │            │
                 │        └── S4 preview
                 │
                 └── S5 platform console
```

### S1 — foundations *(the two blockers)* — ✅ **SHIPPED 2026-09-18**

| # | Ticket | Acceptance | |
|---|---|---|---|
| S1.1 | **`articles.slug`** — Payload migration adding `slug` unique + indexed to `public.articles` and `version_slug` to `_articles_v`; a `slug` field on the collection, auto-derived from the title and editable; backfill all 9,201 rows from `legacyPermalink`. | A new article created in `/team-editor` resolves at its own URL. Every one of the 9,201 existing articles keeps resolving at its **legacy** address — by count, not spot check. | ✅ |
| S1.2 | **`getBySlug` resolves both** — slug first, then `legacyPermalink`. | Legacy URL and new slug both resolve; a legacy URL never 404s because a slug was edited. | ✅ |
| S1.3 | **Config spine** — `getSiteConfig()` reads `engine.sites` (`nav`, `brand_tokens`, `home_rails`) with the config file as the floor; registry rows seeded from each city's `site.config.json`. | Editing `engine.sites.nav` changes the masthead without a redeploy. A platform-DB outage falls back to the file and the masthead still renders — verified by breaking the connection, not by reading the code. | ✅ |

**Evidence.**

- The backfill was **exact**: measured before writing the migration, both
  cities had zero NULL, zero empty and zero non-`/{slug}/` permalinks, and
  fully distinct derived slugs — 4,772 and 4,429. After: 9,201 slugs set,
  all distinct, **zero** disagreeing with their own permalink in either city.
  The unique index is created *after* the backfill so a future city whose
  data does collide fails the migration loudly instead of silently seating a
  duplicate.
- `scripts/verify-article-slug.mjs` (new, wired as
  `npm run verify:article-slug -w @now-engine/cms`) drives the whole thing
  through Payload's Local API — the same path the admin takes, hooks
  included — and passed 8/8 on **both** cities: a new article gets an address
  from its headline, has no legacy permalink so the slug is its only address,
  resolves the way the reader app resolves, an imported article still
  resolves at its old URL, retitling does not move the address, and a
  duplicate address is refused rather than silently renamed.
- 12 new unit tests on the derivation (`test/slug.test.ts`), cms suite
  **39 → 51**. The one that matters is *"an address that already exists is
  never re-derived"*: re-deriving on every title edit is the standard way a
  CMS breaks its own URLs.
- The registry spine was verified by appending a nav item to
  `engine.sites.nav` **in the database only** — no file edit, no restart —
  and watching it appear in the rendered masthead after the TTL. Then by
  pointing the registry pool at a closed port: HTTP **200**, the nav fell
  back to the file's six items, and the reason was logged.
- Gate: web typecheck clean · web build clean (every route `ƒ` dynamic,
  nothing prerendered) · both site-literal lints clean · account-gate lint
  clean · cms 51 · web 20.

**Corrections to this plan, made while doing it.**

- **`SiteRow` was not widened, deliberately.** The plan said to. It would be
  dead code: `now_db.sites_registry.SiteRow` exists for provisioning
  fan-out, and the Python consumer that actually reads these columns —
  `now_config.SiteConfig` — already selects all four. Adding four jsonb
  columns to every maintenance fan-out read buys nothing.
- **`now_config` needed a change the plan did not anticipate.** It typed
  `nav` and `home_rails` as `dict[str, Any]`, which was safe only while
  nothing wrote them. A seeded row holds a JSON **array**, so the loader
  would have failed validation on every request the API served for that
  city. Both are now `dict | list`, with the reason recorded in the model:
  `{}` is the column default and means *absent*, a list means *governed*.
  Nothing in Python reads either field yet — this was a latent break, found
  by looking rather than by an outage.
- **The seed is Node, not `now_db`.** The plan put it in `now_db` beside the
  decay-defaults backfill. Its source is `<slug>/site/site.config.json` and
  its consumer is `apps/web/src/lib/site.ts`; a Python implementation would
  re-derive that file's shape and could then disagree with the only code
  that reads it. `apps/web/scripts/seed-site-registry.mjs`, with
  `--dry-run`, `--slug` and `--force`, and it **refuses to overwrite a
  column that is already governed** unless forced — re-running it after a
  console edit must not put the old nav back.
- **`lib/db.ts` accepted only `PLATFORM_DATABASE_URL`** while
  `lib/payload.ts` accepted either that or `_URI`. The deployed compose sets
  both to the same value and says why; local environments set one. So a
  correctly configured dev machine could reach the vocabulary and not the
  registry. One resolution now, `platformConnectionString()`, used by every
  platform reader in the app.

Migration ownership, for the record: Payload owns `public` through its own
migration runner and Alembic must never touch it, which is why S1.1 is a
Payload migration. The `sites` seed is data, not DDL.

### S2 — site honesty — ✅ **SHIPPED 2026-09-18**

| # | Ticket | Acceptance | |
|---|---|---|---|
| S2.1 | Retire `fixtures/editorial.ts`. Each rail renders only if it has real content. | No fixture import remains anywhere under `src/`. Jakarta never shows a Bali event. | ✅ |
| S2.2 | "Most Read" becomes real from `engine.interactions`, behind a signal floor. | The label and the query agree. | ✅ |
| S2.3 | Every internal link resolves; `/latest` becomes a real archive index. | A link crawl of the homepage and an article page returns zero 404s. | ✅ |

**What deleting the fixtures revealed, which is the reason to do it before any
redesign rather than after.** Measured on both cities:

```
guides             314 Jakarta · 230 Bali     a real rail
upcoming events      0 Jakarta ·   0 Bali     every published event is 2016–2020
most read           63 interactions           not a ranking yet
```

So the homepage renders **one** of those three rails and the other two are
absent rather than fabricated. The precedent for hiding an empty rail is
`areasWithCounts`, which drops terms with no articles because *"an index of
empty links is worse than a shorter index"*. Both reappear on their own — the
events rail the moment a future-dated event is published, Most Read once the
beacon passes its floor — with no code change.

**`/guides` was showing a fraction of the guides it had.** The section
filtered on the `city-guide` format alone while the vocabulary also carries
`guide`, with nothing in either term's description distinguishing them. Bali's
Guides section showed **51 of 230**; Jakarta's 267 of 314. The other 226 were
reachable only at their direct URL. Both terms now feed the section and the
homepage rail from one constant. This is a surface decision, not a taxonomy
change — if the taxonomy review draws a real distinction, `GUIDE_FORMATS` is
the one line that changes.

**Most Read has a floor of 500 interactions over 30 days, and no rail below
it.** Ranking five articles out of 63 events, most of them ours, is the same
objection ARCHITECTURE §6 raises to importing WordPress's bot-contaminated
view counts. The SQL was run directly against the real table before being
trusted, because it sits in a `try/catch` that returns `[]` — a syntax error
would otherwise have hidden the rail silently and forever.

**The two new smoke checks are not hypothetical.** Run against the *currently
deployed* build they fail on both cities with exactly the predicted defects:

```
FAIL  5 of 37 internal links are broken:
        /guides/bars      -> HTTP 404
        /guides/dining    -> HTTP 404
        /guides/ubud-stays -> HTTP 404
        /guides/weekend   -> HTTP 404
        /latest           -> HTTP 404
FAIL  jakarta home page is rendering fixture events
FAIL  bali home page is rendering fixture events
```

Against this branch: **39 pass, 0 fail**, both cities.

### S3 — the CMS layout — **S3.2/S3.3/S3.4 shipped 2026-09-18 · S3.1 open**

| # | Ticket | Acceptance | |
|---|---|---|---|
| S3.2 | `admin.group` on every collection: **Editorial** (Articles, Events, Media, Authors) · **Places** · **Engine** (Classification reviews, Place mentions) · **Settings** (Users). | The sidebar is grouped; a writer's four collections are together and first. | ✅ |
| S3.3 | `articles` into tabs — **Story** · **Old site** — with the date, type, format and kind in the sidebar. | A writer's default screen contains no legacy or engine field. Nothing removed, only moved. | ✅ |
| S3.4 | Editorial wording pass on the collections a writer opens. | Plain language on every label a writer sees. | ✅ |
| S3.1 | One chrome for all of `/team-editor` — classification, commerce, staff and the platform area become sections **inside** Payload's nav rather than mastheads that replace it; `report.css` + `console.css` + `staff.css` (+ `platform.css`) fold into one sheet. | Every admin screen has the same sidebar and the same way home. | ✅ |

**S3.3, stated as the defect it fixed.** The editing screen was one flat
column of twelve fields in the order they had been added over the project's
life: kind, title, dek, body, hero, author, type, format, date, **legacy WP
id, legacy permalink**, series key. A writer scrolled past *"The old WordPress
post number. Nothing to change here."* and a field whose description shouts DO
NOT EDIT on the way to the bottom of their own article.

The tabs are **unnamed**, which is why this needed no migration — a named tab
nests its children's data under that name and would have renamed every column.
Verified rather than assumed: the generated types list exactly the 13 fields
`public.articles` already has, and `verify:article-admin` asserts against the
**sanitised** config that no tab is named and no field was dropped or
duplicated. Writing that check found two of my own assumptions wrong, which is
the argument for running it against the real config rather than a hand-built
one.

**S3.1, and the thing nobody had written down.** The three bespoke chromes
were not a styling accident. classification, commerce and staff were literal
Next routes under `(payload)/team-editor/**`, and Next resolves a literal route
before a catch-all at the same level — so each of them **shadowed Payload's own
router**. That is why they needed their own mastheads, why the three
stylesheets existed at all, and why the only way between them was an `editor`
badge in a corner. They are now Payload custom views, so Payload's catch-all is
the admin's one and only router, and the route table collapses from nine
literal routes to a single `/team-editor/[[...segments]]`.

Two findings worth keeping, because both cost real time to discover:

- **A custom view gets no sidebar unless it renders one itself.** This document
  previously said the mechanism was "confirmed available in 3.88" and stopped
  there, which was true and incomplete. `AdminViewConfig` has no template
  field, and Payload only assigns `templateType` for its own **built-in** view
  names; anything reaching a view through the generic fallback — which is all
  four of ours — renders as bare content. It was found by driving the
  acceptance criterion rather than trusting a 200: curl returned the right
  heading, the right data, and a `template-default` string that turned out to
  be RSC flight data, while the DOM had no `<aside class="nav">` at all.
  Deleting the mastheads had replaced them with nothing.
  `AdminViewFrame.tsx` wraps each view in Payload's own `DefaultTemplate`.
- **Component paths are `@/…` bare specifiers.** A path starting with neither
  `.` nor `/` is written verbatim into the generated import map — and that file
  lives in the *app*, so it resolves through the app's own `@/*` alias. That is
  what lets `payload.config.ts` hold only a string while the app keeps owning
  the components and their `@/lib/auth` imports, so `packages/cms` still never
  imports app code and the city-DB/platform-DB boundary stays intact.

One registration per area, not one per screen: `admin.components.views` matches
by pattern and takes the **first** match in object order, with no "literal
beats dynamic" rule of the sort Next's file router has. Four registrations
would have baked an ordering hazard into a config file permanently.

### S4 — preview — ✅ **SHIPPED 2026-09-18** *(S4.1 and S4.2; one follow-up)*

| # | Ticket | Acceptance | |
|---|---|---|---|
| S4.1 | Draft mode through `(site)`: a preview route that renders an unpublished article at its real URL with the real layout. | An editor previews a draft nobody else can see; an unauthenticated request to the same URL gets a 404. | ✅ |
| S4.2 | `admin.preview` and `admin.livePreview` on Articles, sized for the real breakpoints. | The Preview button and the side-by-side view both open the real page. | ✅ |
| S4.3 | `@payloadcms/live-preview-react` + `RefreshRouteOnSave`, for keystroke-level updating. | The iframe tracks typing without waiting for autosave. | ⬜ |

The body editor's own header named this as the missing piece —
*"it needs draft-mode plumbing through the public site"* — and it was blocked
on something else first: until S1.1 an unpublished article had no address to
preview it at. That is the whole reason S1 came before S4.

**Authorised by the staff session, not a signed token.** The admin is this
same app on this same origin, so the Payload cookie is already on the request
and `payload.auth()` is the same check every `/team-editor` page makes. A
token in a query string is a bearer credential that lands in browser history
and in whatever an editor pastes into chat. There was nothing for one to buy.

**Driven end to end, seven cases:** anonymous cannot read the draft's URL
(404) · anonymous cannot enable preview (404) · staff can (307 + cookie) · the
draft renders at its real address with a banner and `noindex, nofollow` ·
leaving preview works · the same browser 404s again afterwards ·
`?to=https://evil.example/x` on the exit route redirects to `/`.

S4.3 is open because it is a new npm dependency and a lockfile change on the
path `npm ci` takes in the image build. Autosave at 1.5s already refreshes the
iframe within a second or two, so the gap is small and the risk was not worth
taking inside a larger change.

### S5 — the platform console — **S5.1 shipped 2026-09-18 · S5.2–S5.5 open**

| # | Ticket | Acceptance | |
|---|---|---|---|
| S5.1 | **Sites registry editing** at `/team-editor/platform/sites` — nav, brand tokens, home rails, ranking weights. | Changing a nav item in the console changes the reader masthead. This is the connectability the owner asked for, and it is first because it is the screen that proves the spine. | ✅ |
| S5.2 | **Partnership write path** (§11's one screen) — org, tier, status, contract dates, linked mention count. `partnership_audit` records the actor. | A partnership is created and edited in the UI; the audit row names who did it; `now_link_resolver` picks it up on the request path. |
| S5.3 | **Blast radius before commit** — "this affects 40 articles across 3 venues". | Shown on save, computed, and dismissible only by confirming. |
| S5.4 | **Cross-city** — one article's distribution across both cities via `engine.syndications`; a move that bridges through `now_platform` and never city-to-city. | A Jakarta article appears in Bali by an approved bridge, with the origin still authoritative. |
| S5.5 | **Classification health** across both cities — §2.1's facet coverage table, live, with the zero-coverage facets named. | An admin can see that five of seven facets are empty without running SQL. |

Not in S5, deliberately: moving the commerce tables from `engine` to
`public`. That is E4.4, `now_link_resolver` reads them on the request path,
and it does not need to happen for a write form to exist.

### S6 — the visual direction *(depends on S2; runs alongside S3/S4)*

| # | Ticket | Acceptance |
|---|---|---|
| S6.1 | Direction: type pairing, palette, grid, chrome, motion. Presented as comps before any component is touched. | Owner picks a direction. |
| S6.2 | New token file and `/design` reference rebuilt to match. | `lint:site-literals` clean; both cities render from one image. |
| S6.3 | Homepage, section index and article page rebuilt on the direction, with the layout driven by `sites.home_rails`. | Reordering a rail in the console reorders the homepage. |
| S6.4 | Responsive pass — a real breakpoint set, a nav that collapses, and the article page checked at phone width. | No horizontal page scroll at 360px on any reader route. |

### S7 — wire the engine into the site *(depends on S2.3, S6.3)*

| # | Ticket | Acceptance |
|---|---|---|
| S7.1 | "Read Next" becomes `GET /v1/{site}/articles/{id}/rails`, with rail and position logged to the beacon on impression. | The rail is the engine's, in the engine's order, and the site does not re-sort it. §10's presentation-bias warning is respected. |
| S7.2 | §9 facet filters on section indexes, for the four facets that carry data. | A filtered section is shareable and back-button-able; the URL expresses the filter. |
| S7.3 | Inspector surface for editors — "why is this here" on a rail slot. | An editor sees the filter trace on a real removal. §17 wants this before any public widget. |

---

## 5. Outstanding, and not in this plan

Recorded so that surface work does not quietly become the reason these were
forgotten. None of them is a surface problem.

**Blocked on someone other than an agent**

- **DNS + CloudPanel** for `now-engine-api`, `now-jakarta`, `now-bali`.
  None resolve. Nothing is publicly live.
- **SMTP** — a Google Workspace app password. `gaiada.com` MX is Google and
  its DMARC demands strict alignment, so sending anywhere else fails SPF.
  Without it `/account/*` is broken in production while the rest is fine.
- **F140 — `gaiada.com` publishes no DKIM** while its own DMARC record
  requires strict DKIM alignment.
- **Rotate the GHCR PAT.** It was pasted in chat and is in
  `/root/.docker/config.json` on the box.
- **B3 — mirror the media.** ~3.7 GB Jakarta + ~5.4 GB Bali of originals,
  plus a 650 MB legacy CKEditor store outside `wp-content`. E1.3 is blocked
  on it.
- **Google Search Console** — 16 months of query→page data, which is what
  would make the search eval trustworthy (F38).
- **B6/B7 — the live WordPress sites have no working backup.** Both
  UpdraftPlus schedules are `manual`, failure email is off, and all 17
  remote-storage slots are empty. No off-server copy has ever existed.

**Engine and data**

- **F137 — five of seven facets have zero tagged articles.** `topic`,
  `audience`, `price_band`, `vibe`, `cuisine`. The preference picker
  collects 36 topics that match nothing. Blocks topic-based recommendation
  and half of §9's filters.
- **Type/format classification tops out at 0.66** against 405 human
  verdicts and earns auto-apply at no threshold (F113/F118/F120/F124).
  Location clears 0.85 on every mechanism. The instrument is being fixed,
  not re-gated. `subtype` (6,023 rows) is still unmeasured.
- **Taxonomy mapping review** — 110 categories across both cities, ~1–2
  hours of reading, still the highest-leverage thing the owner can do.
- **E4 commerce is 1/8.** Schema and 1,562 orgs exist; `partnerships` is
  empty. S5.2 is the first real use of it.
- **E5 itinerary is 2/7.** Solver and validator ship; E5.4 (places→Stop
  adapter, API, persistence) is next and is what the reader dashboard's
  saved-itineraries panel is waiting on.
- **E6 assistant — not started.**
- **E7 personalization — data-gated** at ~50k sessions. The beacon is
  deployed, so the clock is running.
- **F135 — the newsletter has never sent anything.** Every subscriber is
  stuck at `pending`; the mailer and the template exist and nothing calls
  them. Tracked as E8.1b.
- **E8.3a — rate limiting is in-process**, per container, lost on restart.
  Redis is already in compose.
- **E8 is 8/13.** Reading history and saved itineraries are the open
  dashboard panels.

**Infrastructure and hygiene**

- **F6 — no RLS** on the platform tables carrying `site_id`
  (`partnerships`, `campaigns`, `placements`). DB-per-city covers the
  primary boundary. This becomes load-bearing the moment S5.2 writes.
- **F7 — one Postgres role** does provisioning, migration and runtime.
  Split before `ad_events` carries billing data.
- **No smoke test in `publish-images`.** CI proves images build, never that
  they start. Five latent bugs reached the box because of it; the browser
  smoke test added in #36 is the start of the answer, not the whole of it.
- **`deploy.sh` applies no migrations** — documented as a trap rather than
  a gap, and still a trap.
- **The console image cannot run its own migrations.** The standalone build
  carries `src/migrations/` but no `tsconfig.json` and no payload module, so
  every platform migration needs the manual `psql` path.
- **F4 — `now-api-test` on :55510** has been up 23 hours from E0.3. Tear it
  down.
- **PROGRESS.md is stale by two days and two waves.** The 2026-09-17 work
  (#32–#43 — the writing surface, the S3 plugin fix, the admin blank-page
  fix, the deploy runbook rewrite) is in git and not in the tracker, and its
  dashboard still leads on F50.

---

## 6. Risks worth holding in view

**S1.1 is a migration against 9,201 rows in two databases, and the thing it
touches is the SEO estate.** Legacy permalinks *are* the traffic. The
acceptance criterion is a count of resolving legacy URLs before and after,
not a spot check, and the backfill needs a collision report before it runs
rather than a unique-violation halfway through.

**S3.1 folds four stylesheets into one.** That is the change most likely to
break a screen nobody opens often — the staff console and the cluster
decision desk. Both need driving, not compiling.

**S6 is a redesign of a system that is already good.** The failure mode is
not ugliness, it is losing the reasoning embedded in the current one: the
66ch measure, the three rule weights, ink that is not black, display sizes
larger than a blog would dare. Those are conclusions, not decoration. A new
direction should reach its own conclusions deliberately, not lose these by
default.

**S5 makes the access rules security-critical.** Today the commerce console
is read-only, so a bug in `requireCommerceAccess()` leaks partner terms. The
moment S5.2 writes, the same bug edits them, from a city admin session, on a
public hostname. The tests are the deliverable there, as they were in
ADMIN-CONSOLIDATION Phase 1.

---

## 7. Nothing here is deployed, and what it takes to change that

Every ticket above is on `feat/surfaces-s1-foundations` (PR #45, CI green).
**Live is still `sha-1dded08`** — the commit before any of this. Two steps
were refused by the working session's own permission gates and neither was
worked around:

| Step | Gate |
|---|---|
| `gh pr merge 45` | *Merge Without Review* |
| Applying the Payload migration to production | *Production Deploy* |

Delegating to subagents does not move this: they run under the same
permissions.

**The order is not negotiable, and only one direction is safe.** The new code
reads `articles.slug`. Against a database without that column every article
page returns 500 while `/healthz` stays green — the exact shape of failure
[DEPLOY.md](DEPLOY.md) spends forty lines warning about. The migration is
additive and the deployed build does not know the column exists, so applying
it *ahead* of the rollout is invisible to readers.

```bash
gh pr merge 45 --squash --delete-branch          # then wait for publish-images

# on helios, BEFORE the image rolls
docker cp articles-slug.sql now-postgres:/tmp/
docker exec now-postgres psql -U now -d now_jakarta -v ON_ERROR_STOP=1 -f /tmp/articles-slug.sql
docker exec now-postgres psql -U now -d now_bali    -v ON_ERROR_STOP=1 -f /tmp/articles-slug.sql

deploy/deploy.sh <new-sha> && scripts/smoke.sh   # expect 39/39
```

Pre-change dumps of both city databases are already on the box at
`/root/.now-deploy/pre-s1/`. They were taken because the only other dumps
there were from the initial seed on 2026-09-15, which is not a safety net for
editorial work done since. The SQL twin is
`engine/packages/cms/scripts/articles-slug.sql`.

### Also found while verifying, and not fixed

- **`npm start` cannot run this app.** `output: 'standalone'` makes
  `next start` refuse — it prints *"does not work with output: standalone"*
  and then serves 500s on every route that touches the database, which looks
  exactly like a broken build. The real artifact runs with
  `node apps/web/server.js` from `.next/standalone`, and needs `sharp` and
  `@img` copied in beside it the way the Dockerfile does. The `start` script
  in `apps/web/package.json` is therefore misleading and cost a false alarm
  during this wave; worth either fixing or deleting.
- **The sites registry has no audit trail.** Every write logs the actor's
  email to stdout and nothing more, so "who changed the nav, and when" is a
  grep. `partnership_audit` is the precedent for what it should look like;
  adding one needs an Alembic revision, which is single-threaded and was
  deliberately out of scope here.
- **`ranking_weights` is displayed but not editable.** It already holds real
  content on every site from an earlier wave, so "governed" does not mean
  "set by this console". No write form, because nothing in `SiteConfig` reads
  that column yet and a form editing a value nothing consumes is a screen
  that lies about having an effect.

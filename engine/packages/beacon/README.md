# NOW! Beacon

Vanilla-JS, zero-dependency behavioural beacon. This is the **only** source of
reader behaviour data for the NOW! Engine — the live WordPress site has no
GA4/GTM/Matomo installed and no history can be backfilled (ARCHITECTURE.md
§6). It ships in E0, before anything downstream consumes it, because every
week without it delays the ML roadmap (§10) by a week.

Task: **E0.4**. Owns `engine/packages/beacon/**` only. The server endpoint
that receives this payload is wired separately in **E0.5**
(`POST /v1/{site}/events`) — this package defines the client and the payload
shape, nothing server-side.

---

## What it does

- Emits `view · scroll · dwell · click · outbound · search · exit` automatically.
- Emits `impression` **with rail and position** whenever a rail registers what
  it rendered — not only what was clicked. Per ARCHITECTURE.md §10, readers
  can only click what they were shown; without impressions + position, the
  Stage 3/4 ranker cannot correct for position bias.
- Exposes `thumbs_down` as an explicit, user-initiated signal (§10 signal
  weights: `-1.0`, the only user-chosen hard signal).
- Identifies readers with an opaque `anon_id` (1-year first-party cookie) and
  a `session_id` (30-minute sliding window), both stable enough to merge into
  a real account at registration.
- Batches everything and flushes on a timer, on a size threshold, and —
  critically — on `pagehide` / `visibilitychange` via `navigator.sendBeacon`,
  so the final `dwell`/`exit` event survives tab close.
- Respects Do Not Track and an explicit consent flag; no-ops cleanly for
  either, and revoking consent mid-session drops anything already queued.
- Never throws into the host page. Every code path that touches the DOM,
  cookies, storage, or the network is wrapped; a failure degrades silently
  instead of breaking the WordPress theme it's dropped onto.
- No PII, no page content, no keystroke capture. Identity is a random opaque
  id. The one piece of user-entered text it carries — a search query — is
  capped at 200 chars and travels as an entity reference (see below), not a
  free-text field.

---

## Integration on the legacy site

Single script tag, config via `data-*` attributes:

```html
<script
  src="https://engine.now.id/b.js"
  data-site="jakarta"
  data-entity="12345"
  data-entity-type="article"
  data-surface="article"
  async
></script>
```

| Attribute | Required | Default | Meaning |
|---|---|---|---|
| `data-site` | yes | `''` | Site slug — becomes `/v1/{site}/events` |
| `data-entity` | for view/dwell/exit | `''` | The current page's entity id (article/place id) |
| `data-entity-type` | no | `article` | Entity type for automatic events |
| `data-surface` | no | `article` | Surface label (`article`, `home`, `search`, …) |
| `data-endpoint` | no | derived from script `src` origin | Override the events endpoint (used by the demo/tests) |
| `data-consent` | no | unset | `"denied"` to start opted-out until the CMP grants consent |
| `data-debug` | no | unset | `"true"` to `console.warn` internal errors (silent otherwise) |

If the script must run with `async` (it should), and the host page wants to
call the API *before* the script has finished loading (e.g. to register
impressions as soon as a rail renders), install the standard queuing shim
first:

```html
<script>
  window.NOWB = window.NOWB || function () { (window.NOWB.q = window.NOWB.q || []).push(arguments); };
</script>
<script src="https://engine.now.id/b.js" data-site="jakarta" data-entity="12345" async></script>
```

Calls made through the shim are replayed, in order, the instant the real
script installs itself.

### Programmatic API

```js
// Register what a rail actually rendered — do this for every card shown,
// not just the ones clicked.
NOWB('impression', { surface: 'article', rail: 'complementary', entityId: '4821', position: 1 });

// Equivalent direct method form:
NOWB.impression({ surface: 'article', rail: 'complementary', entityId: '4821', position: 1 });

// Tell the beacon the host navigated WITHOUT a document load (SPA routing).
// Emits `dwell` for the page being left, then `view` for the new one, and
// resets the per-page scroll milestones. Re-declaring the page already in
// view is a no-op, so it is safe to call unconditionally on every mount.
NOWB('page', { entity: '4429', entityType: 'article', surface: 'article' });

// Explicit user signal
NOWB('thumbsDown', { entityType: 'place', entityId: '4821' });

// Identify at registration/login — merges anon history server-side via anon_id
NOWB('identify', 'user_abc123');

// Consent (CMP integration) — 'denied' hard-stops and drops the queue
NOWB('consent', 'granted');
NOWB('consent', 'denied');

// Force an immediate flush (rarely needed — batching handles this)
NOWB('flush');
```

On a single-page app — the NOW! reader site is one — `NOWB('page', …)` is not
optional decoration: the script executes once per document, so without it
every article a reader opens by clicking a link is attributed to whatever page
they first landed on, and only the landing page ever gets a `view`.

Automatic instrumentation (no calls needed): `view` fires on load; `scroll`
fires at 25/50/75/100% depth; `click`/`outbound` fire from a single
capturing document click listener (internal vs external is decided by
`location.host`); `search` fires from `?q=`/`?s=` on load or from a
`role="search"` form submit; `dwell` + `exit` fire together on unload.

Anchors can carry `data-nowb-entity`, `data-nowb-entity-type`,
`data-nowb-rail`, `data-nowb-position` to enrich the automatic click/outbound
event — otherwise `entity_id` falls back to the link's `href`.

---

## Payload contract

Fixed by the schema task (E0.2) against `engine.interactions` /
`engine.impressions`. **Field names below are exact and must not change**
without a schema-owning agent's sign-off.

### `interaction`

```
{ anon_id, user_id?, session_id, entity_type, entity_id,
  kind, surface, rail?, position?, dwell_ms?, scroll_pct?,
  referrer?, utm?, device, ts }

kind ∈ view | scroll | dwell | click | outbound | search | exit | thumbs_down
```

| Field | Type | Notes |
|---|---|---|
| `anon_id` | string (UUID) | RFC4122 UUID; cookie-backed (1yr) or memory-only if cookies are blocked |
| `user_id` | string (UUID), optional | only present after `NOWB('identify', id)` and only if the id is a valid UUID (8-4-4-4-12 hex format) — non-UUIDs are silently omitted and will be rejected by the server |
| `session_id` | string (UUID) | RFC4122 UUID; opaque, 30-min sliding window |
| `entity_type` | string | e.g. `article`, `place`, `url` (outbound), `search_query` (search — see below) |
| `entity_id` | string | the entity, or the raw href for an untagged outbound link, or the query text for `search` |
| `kind` | enum | see above |
| `surface` | string | e.g. `article`, `home`, `search` |
| `rail` | string, optional | present on rail-sourced clicks (`data-nowb-rail`) |
| `position` | number, optional | 1-based position within the rail |
| `dwell_ms` | number, optional | present on `dwell`/`exit` |
| `scroll_pct` | number, optional | present on `scroll`/`dwell`/`exit` |
| `referrer` | string, optional | `document.referrer`, when non-empty |
| `utm` | object, optional | `{source, medium, campaign, term, content}`, only keys present in the landing URL |
| `device` | enum | `mobile` \| `tablet` \| `desktop`, coarse UA sniff, not a fingerprint |
| `ts` | number | client epoch ms at event time |

**`search` and the missing `query` field:** the fixed contract has no
dedicated free-text field for a search query. Rather than adding one
unilaterally, the query travels as `entity_type: "search_query"`,
`entity_id: <query text, truncated to 200 chars>`. If E0.2 later adds a
first-class `query` field, this is the one deliberate deviation to revisit.

**`entity_type: "url"` is the encoding for "this is a URL, not an entity".**
The server writes it to `engine.interactions.target_url` and leaves
`entity_id` NULL; every *other* `entity_type` must carry a native integer
Payload PK, and anything else is a `400` that drops the entire batch. Three
cases produce it:

| Case | `kind` | `entity_id` |
|---|---|---|
| An untagged link, off-site | `outbound` | the absolute `href` |
| An untagged link, on-site | `click` | the absolute `href` |
| A page that names no entity (home, section index, search) | `view`/`scroll`/`dwell`/`exit` | `location.href` |

The last two were the bugs that kept `engine.interactions` at zero rows: an
internal click used to send the href under the *page's* `entity_type`, and a
page with no `data-entity`/`nowb:entity` used to send `entity_id: ""` — a
`400` and a `422` respectively, each taking every good event queued beside it.
A first-class `page_url` column would be a cleaner home for the third case;
until the schema has one, `target_url` holds it losslessly rather than the
event being dropped.

### `impression`

```
{ session_id, anon_id, surface, rail, entity_id, position, ts }
```

No optional fields — a rail must know its own `rail` name and the
`position` of everything it renders. `impression()` refuses to enqueue
(logs a debug warning, drops silently) if `entityId`, `rail`, or `position`
is missing.

### Transport

`POST /v1/{site}/events` (or the URL configured via `data-endpoint`),
`Content-Type: application/json`, body:

```json
{ "interactions": [ /* interaction objects */ ], "impressions": [ /* impression objects */ ] }
```

Either array may be empty but the request is only sent when at least one of
them is non-empty. Delivered via `navigator.sendBeacon` when available and
on the unload path; via `fetch(..., {keepalive})` otherwise; via
`XMLHttpRequest` as the last-resort fallback for very old browsers with
neither.

Flush triggers: every 5s if the queue is non-empty, immediately once the
combined queue reaches 10 events, and once on `pagehide` /
`visibilitychange→hidden` (unload-safe, via `sendBeacon`). A hard cap of 200
queued events per array prevents unbounded memory growth if the endpoint is
unreachable for a long-lived tab.

---

## Privacy

- **DNT**: `navigator.doNotTrack === '1'` (or the legacy `window.doNotTrack` /
  `window.externalDoNotTrack`) disables *all* tracking for the page lifetime
  — the boot sequence never even attaches listeners.
- **Consent**: `data-consent="denied"` on the script tag starts the beacon
  opted-out; call `NOWB('consent', 'granted')` once your CMP confirms
  consent. Calling `NOWB('consent', 'denied')` at any point immediately
  drops anything already queued and stops further collection — verified in
  `test/beacon.test.js`.
- **No PII**: identity is a random id, never an email/name/IP. No page body
  text is ever read. No keystrokes are captured — the `search` event reads
  a submitted value (or the URL's `?q=`), not individual keypresses.
- **Cookie degradation**: if `document.cookie` throws or silently doesn't
  persist (privacy mode, cookie blockers), the beacon falls back to an
  in-memory `anon_id` for the tab's lifetime rather than crashing or
  retrying. Verified in `test/beacon.test.js` and in the Playwright run
  below.

---

## Build

```bash
cd engine/packages/beacon
npm install         # devDependencies only: terser (minify), jsdom (tests)
npm run build        # -> dist/beacon.min.js, prints raw/gzip/brotli size, fails if >= 4KB gzipped
npm test             # jsdom-based regression suite, no browser needed
```

The shipped artifact is `dist/beacon.min.js` — a single file, no runtime
dependencies, safe to serve directly or through a CDN in front of
`engine.now.id/b.js`.

### Measured size (this build)

```
$ npm run build

Built: dist\beacon.min.js
  raw:     6743 bytes
  gzip:    2948 bytes (2.88 KB)
  brotli:  2596 bytes (2.54 KB)
OK: within < 4 KB gzipped budget (1148 bytes to spare)
```

`scripts/build.js` fails the build (non-zero exit) if the gzipped size ever
reaches 4 KB, so the budget is enforced mechanically, not just documented.

---

## Verification performed

This environment has no interactive browser, but Playwright's headless
Chromium is available and was used for real end-to-end verification — not
simulated. All of the following were run against the actual built
`dist/beacon.min.js`, served by `demo/server.js` (a zero-dependency static +
mock-endpoint server), and driven by Playwright Python scripts.

1. **`npm test`** — 11/11 passing, browser-less regression suite
   (`test/beacon.test.js`) covering: global install, automatic `view`,
   exact field-name conformance for both `interaction` and `impression`,
   `kind` enum restriction, the `search`-query encoding, DNT no-op,
   consent-denied no-op (including queue purge), cookie-blocked
   degradation, the unload `sendBeacon` path carrying `dwell`+`exit`, and a
   thrown-error-inside-a-handler containment check.

2. **Real-browser run against `demo/index.html`** (headless Chromium via
   Playwright), exercising every event type through actual user actions —
   clicking buttons, submitting a form, scrolling, closing/navigating pages
   — and inspecting what the mock server actually received on the wire.
   Sample of what arrived (trimmed, one interaction per kind, real ids
   redacted to `…`):

   ```json
   {"kind":"view","entity_type":"article","entity_id":"13","surface":"article"}
   {"kind":"click","entity_type":"article","entity_id":"4821","surface":"article","rail":"complementary","position":1}
   {"kind":"outbound","entity_type":"url","entity_id":"4821","surface":"article"}
   {"kind":"search","entity_type":"search_query","entity_id":"rooftop bar senopati","surface":"search"}
   {"kind":"thumbs_down","entity_type":"place","entity_id":"4821","surface":"article"}
   {"kind":"scroll","entity_type":"article","entity_id":"...","surface":"article","scroll_pct":25}
   {"kind":"scroll","...":"...","scroll_pct":50}
   {"kind":"scroll","...":"...","scroll_pct":75}
   {"kind":"scroll","...":"...","scroll_pct":100}
   {"kind":"dwell","entity_type":"article","entity_id":"...","dwell_ms":1470,"scroll_pct":20}
   {"kind":"exit","entity_type":"article","entity_id":"...","dwell_ms":1471,"scroll_pct":20}
   ```
   ```json
   {"session_id":"...","anon_id":"...","surface":"article","rail":"complementary","entity_id":"4821","position":1}
   {"session_id":"...","anon_id":"...","surface":"article","rail":"complementary","entity_id":"place:demo-2","position":2}
   {"session_id":"...","anon_id":"...","surface":"article","rail":"complementary","entity_id":"place:demo-3","position":3}
   ```

3. **Unload safety** — navigating the tab away (`pagehide`) with a queued
   but not-yet-flushed `view` event still in the buffer produced exactly one
   `sendBeacon` POST containing that `view` plus the final `dwell` and
   `exit` — confirmed via the network log and the server's received-batch
   log. (Note: calling Playwright's `page.close()` directly does **not**
   reliably fire `pagehide` in headless Chromium — that's a
   headless-teardown quirk, not a beacon bug; real navigation/tab-close and
   `visibilitychange` both fire correctly and are the two paths the beacon
   actually relies on.)

4. **DNT** — with `navigator.doNotTrack` stubbed to `'1'`, zero requests to
   `/events` were observed across a full interaction sequence (impressions,
   scroll, explicit flush, and navigation-away).

5. **Cookies blocked** — with `document.cookie`'s setter made to throw
   (simulating strict privacy mode / a cookie blocker), the script loaded
   without any uncaught page error, generated a memory-only `anon_id`, and
   still delivered events.

If you re-run this yourself: `node demo/server.js`, then open
`http://localhost:8933/` in a real browser, open devtools, and work through
the numbered sections on the page — every batch the beacon sends is echoed
both to the browser console (with `data-debug="true"`) and to the terminal
running `demo/server.js`.

---

## Notes for E0.5 (wiring the server endpoint)

- Expect `POST /v1/{site}/events`, `Content-Type: application/json`
  (sendBeacon sends a `Blob` with that content type; fetch/XHR set it
  explicitly), body `{ interactions: [...], impressions: [...] }`, either
  array possibly empty but not both.
- No auth header is sent by this client — ARCHITECTURE.md §17/E0.3 calls for
  API-key auth for beacon + widgets; if that key must be included, it needs
  a config surface here (a `data-key` attribute or a same-origin proxy path)
  — currently unimplemented, flagged as a follow-up rather than guessed at,
  since it's a contract decision.
- `entity_id` is always a string. For `outbound` clicks with no
  `data-nowb-entity`, it will be the raw absolute `href` — expect URLs, not
  just ids, in that kind.
- `search` carries the query in `entity_type: "search_query"` /
  `entity_id: <query>` rather than a new field (see contract section above)
  — the endpoint should special-case `kind === 'search'` if it wants the
  literal query text out.
- Batches can arrive with duplicate-looking `view` events across tabs/reload
  loops; dedup, if needed, is a server-side concern (this client does not
  suppress repeat views of the same entity across page loads).
- Rate-limiting and payload validation (per E0.5's own acceptance criteria)
  should tolerate: up to ~210 events per POST (10 batch trigger size + up to
  200 queued if the endpoint was briefly unreachable), and should 4xx
  rather than 5xx on malformed bodies — this client does not retry failed
  sends, so a hard failure silently drops that batch (acceptable for a
  best-effort analytics beacon per ARCHITECTURE.md's tone; flagging in case
  that tradeoff needs revisiting once real traffic hits it).

## You cannot test the origin allowlist with OPTIONS

The beacon posts to `/v1/{site}/events` on its **own** origin, and the reader
app proxies that to the engine API (`apps/web/src/app/v1/[site]/events/route.ts`).
That route exports `POST` and nothing else, so an `OPTIONS` request is answered
by Next itself and **never reaches the API** — it returns 204 regardless of the
`Origin` header, including for an origin the allowlist would refuse.

This cost real time on 2026-09-17. A preflight was used as a write-free way to
check the allowlist after deploying a fix to it, `https://evil.example` came
back 204, and it briefly looked like the gate was wide open. It was not: the
API logged zero OPTIONS requests for the period, because none arrived.

Two consequences worth keeping straight:

- **To test the allowlist, POST.** A valid batch from a refused origin returns
  403 before anything is written, so it is safe to use as a probe.
- **Nothing is broken by the missing OPTIONS handler.** Same-origin requests
  never preflight, and the beacon is same-origin by construction — that is the
  whole reason the proxy exists. The handler is absent because it is unreachable,
  not because it was forgotten.

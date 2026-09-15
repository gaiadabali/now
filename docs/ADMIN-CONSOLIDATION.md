# Consolidating the admin surfaces

**Status:** planned, not started. Decided 2026-09-15.
**Supersedes:** the six-hostname layout in [DEPLOY.md §4](DEPLOY.md).

## What changes

Six hostnames become two. The reader site, the CMS and the commerce console
become **one application per city**, with a single sign-in whose role decides
what the user sees.

```
now-jakarta.gaiada.com/              reader site          public
now-jakarta.gaiada.com/team-editor   admin               staff, role-gated
now-jakarta.gaiada.com/v1/…          engine-api          path-routed

now-bali.gaiada.com/                 same, for Bali
```

Retired: `now-engine-api`, `now-cms-jakarta`, `now-cms-bali`, `now-console`
— four DNS records, four CloudPanel sites, three containers.

| | today | after |
|---|---|---|
| DNS records | 6 | **2** |
| CloudPanel sites | 6 | **2** |
| app containers | 6 (api, worker, 2×web, 2×cms, console) | **4** (api, worker, 2×web) |
| logins | 3 (cms-jkt, cms-bali, console) | **1** |

## Why this is smaller than it looks

The console was never really a second CMS. **Its Payload owns exactly one
table — `public.users`.** Every commerce page (`orgs`, `campaigns`) is a
plain Next page reading `now_platform.engine.*` read-only over direct SQL,
behind an auth check. Those pages need *an* auth context and a role; they do
not need a Payload instance of their own.

So the console does not get "merged" so much as **absorbed**: its pages move,
its Payload disappears, and its `users` table is promoted to the single
identity store.

All three apps are already on identical versions — Next 15.4.11, React
19.0.1, Payload 3.88.0 — so there is no framework migration hiding in here.

## The one real constraint

**Payload binds to exactly one database per instance.**

The merged per-city app binds to its **city** database, because that is where
the editorial content lives. But staff identity and commerce data live in the
**platform** database. That is the whole difficulty, and everything below is
downstream of it.

### Decided: shared identity in the platform DB

`now_platform.public.users` becomes the single source of truth for staff
accounts. One account works in Jakarta and Bali.

Payload still requires the collection named by `admin.user` to exist in *its
own* database, so the city DB keeps a **shadow projection** of each user who
signs in:

```
1. credentials POSTed to the city app
2. custom Payload auth strategy verifies them against
   now_platform.public.users  (source of truth: hash, salt, role, lockout)
3. on success, upsert a local shadow row in <city>.public.users
   — email, name, role. NEVER a password hash.
4. Payload issues its session against that shadow row
```

**Role is re-read from the platform on every sign-in**, so a revoked role
cannot survive in a stale shadow row. The shadow holds no secret: a dump of a
city database yields no credential that authenticates anywhere.

Rejected alternatives, and why:

- **Per-city accounts.** Simplest — Payload's built-in auth untouched. But
  the same person working both cities needs two accounts and two passwords,
  and every role change is made twice. Contradicts the stated goal that one
  login decides what you see.
- **External SSO (Keycloak/OIDC).** The right destination if staff grows or
  more internal tools appear, and the repo already anticipates it. Too much
  to take on in the same change as the merge. The custom strategy below is a
  clean seam to swap for OIDC later — it is one module.

### Decided: commerce is visible in both cities, role-gated

The commerce section appears under `/team-editor` on both hostnames, shown
only to `admin` and `partner_manager`.

**Stated plainly, because it is a real reduction in isolation:** commerce data
is platform-wide, so a compromised Jakarta admin session can read Bali's
partner terms. Today that is prevented by process and hostname separation;
afterwards it is prevented by access rules alone. That is an accepted
trade-off, not an oversight — but it means the access rules become
security-critical code and must be tested as such, not eyeballed.

## Sequence

Four phases. Each one ships and is reversible on its own; nothing is retired
until its replacement is proven.

### Phase 1 — shared identity, nothing else moves

Build the custom auth strategy and point **both** existing CMS instances and
the console at `now_platform.public.users`. Six hostnames still, three apps
still — but one account now works everywhere.

- [ ] `packages/auth` (new): verify credentials against platform users;
      shadow-row upsert; role refresh
- [ ] Migrate existing city `users` rows into the platform table; keep the
      city tables as shadows
- [ ] Both CMS instances and the console adopt the strategy
- [ ] **Tests are the deliverable here, not the feature:** wrong password,
      unknown user, revoked role, role downgrade mid-session, lockout,
      password reset, shadow row absent, platform DB unreachable

Doing identity *first* means the merge later is a routing change, not a
routing change plus an auth change. If this phase is wrong, it is wrong while
the old surfaces still work.

### Phase 2 — the reader site and the CMS become one app

- [ ] `apps/web` gains the `(payload)` route group; `routes.admin` =
      `/team-editor`
- [ ] `packages/cms` stays the **shared Payload config package** — §3.5's
      "ONE Payload config, instantiated per city" is preserved, the app
      imports it rather than owning it
- [ ] `SITE_SLUG` continues to select the city; no new per-city code
- [ ] Deploy under the existing city hostnames. `now-cms-*` still up, unused.

### Phase 3 — commerce moves in

- [ ] `apps/console/src/app/(console)/*` → `/team-editor/commerce`
- [ ] Platform read-only pool, as today
- [ ] Role gate on every route, enforced server-side, not in a layout
- [ ] Console still up, unused, as a rollback

### Phase 4 — retire

- [ ] Path-route `/v1/*` → `engine-api` on both city hostnames
- [ ] Re-point the beacon's endpoint (it derives `origin + /v1/{site}/events`
      and accepts a `data-endpoint` override, so this is config)
- [ ] Drop `cms-jakarta`, `cms-bali`, `console` from compose
- [ ] Remove the four CloudPanel sites and the four DNS records

## Risks worth holding in view

**Auth is where auth bugs live.** A custom strategy replaces the
best-tested part of Payload with our own code. Phase 1 exists as its own
shippable step for exactly this reason.

**The reader site and the admin share a process.** An admin-side crash takes
the public site with it. Acceptable at this scale, and the reason `engine-api`
stays a separate container — the API is the durable deliverable (§16) and
should not share a failure domain with an admin panel.

**The admin path is on a public hostname.** `/team-editor` is
unguessable-ish, which is worth something and is not a control. Rate-limit
the sign-in route and keep failed-attempt lockout on.

**`site:create` gets simpler, not harder.** A new city is still one command
plus config; it now provisions one app instead of two.

## What this does not change

- DB-per-city. Cities stay isolated; this is an *admin surface* merge, not a
  data merge.
- Alembic owns `engine`; Payload owns `public`. Commerce stays read-only
  until E4.4 moves those tables deliberately.
- `engine-api` stays one multi-tenant deployment, reached by path instead of
  its own hostname.

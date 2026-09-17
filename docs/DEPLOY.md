# Deploying NOW! Engine to helios

The target is **helios** (`187.77.116.133`, Ubuntu 24.04), a CloudPanel box
with 8 vCPU / 32 GB / 387 GB. Everything deploy-related lives in
[`deploy/`](../deploy).

> Moved here from delphi (`72.61.142.88`) deliberately. delphi is 2 vCPU with
> ~4 GB free and 11 GB of disk, already carrying three other stacks; the full
> NOW! stack measured 4.38 GB of limits, which left it with no headroom at
> all. helios runs only a server-side GTM pair in Docker and has ~25 GB
> available. Both hosts use the same pattern, so the only things that changed
> are the hostname, the IP and the sizing.

---

## 1. What can go live today, and what cannot

| Service | State |
|---|---|
| `postgres` · `redis` | ready — custom PG image carries pgvector + PostGIS |
| `engine-api` | ready — ARCHITECTURE.md §16 calls this the durable deliverable |
| `web-jakarta` · `web-bali` | ready — one image, one process per city. **Also serves the admin and the commerce console at `/team-editor`** |
| `garage` · `imgproxy` | **off** — behind the `media` profile, see §6 |
| `engine-worker` | ready — arq cron + the re-embed stream consumer |

> **`cms-jakarta`, `cms-bali` and `console` are gone.** They were absorbed
> into the web image at `/team-editor`
> ([ADMIN-CONSOLIDATION.md](ADMIN-CONSOLIDATION.md) Phase 4): four services
> and four hostnames became none. Anything below that still names them is
> superseded by that document, which is the one to follow.

### The console's auth

`console` is a Payload instance owning platform `public`, which is
ARCHITECTURE.md's own plan for it ("a Payload instance will own platform
`public` later, when the partner console (E4.4) needs an editing surface").
Payload provides real sessions, lockout, password reset and roles; every
console page calls `requireUser()` *before* it queries anything, and
unauthenticated visitors land on Payload's own `/admin/login`.

Its `users` table is separate from the CMS's on purpose. The CMS's lives in
each **city** database and gates editorial work; this one lives in the
**platform** database and gates commercial data. An editor who can publish in
Jakarta should not thereby read every partner's terms.

It owns `public.users` and nothing else. Commerce data is still **read-only**,
because `orgs`, `partnerships`, `campaigns` and `placements` remain in
`engine`, Alembic-owned — `now_link_resolver` reads `engine.partnerships` on
the **request path**, so moving them into `public` for Payload to own would
break link resolution, the loader and the CMS's Places collection. That is a
deliberate migration with its own blast radius, and it is E4.4's work, not a
side effect of adding auth.

**First deploy runs the migration once**, then creates the first admin.

> ⚠️ **`npx payload migrate` does NOT work against the deployed image.**
> Found on the first real deploy (2026-09-15). The runner stage is a Next.js
> **standalone** build: it carries `src/migrations/` but no `tsconfig.json`
> and no `payload` module, so `npx` downloads a fresh Payload that then dies
> with `TypeError: Cannot read properties of null (reading 'config')` in
> `getTSConfigPaths`. The migration files ship; the CLI that applies them
> does not.
>
> Applied instead by extracting the `up()` SQL — it is plain SQL in a
> `sql\`...\`` template, and it creates `payload_migrations` itself — then
> recording it:
>
> ```bash
> docker exec now-postgres psql -U now -d now_platform -v ON_ERROR_STOP=1 -f /tmp/m.sql
> docker exec now-postgres psql -U now -d now_platform >   -c "INSERT INTO payload_migrations (name, batch) VALUES ('<migration name>', 1)"
> ```
>
> **The proper fix is to make the console image able to migrate itself**
> (keep `tsconfig.json` + the payload CLI in the runner, or add a dedicated
> migrate target). Until that lands, every console migration needs the manual
> path above.

Then create the first admin **immediately, in the same session** — until one
exists, `POST /api/users/first-register` is open to anyone who reaches the
public hostname:

```bash
curl -s -X POST http://127.0.0.1:4316/api/users/first-register   -H 'Content-Type: application/json'   -d '{"email":"...","password":"...","name":"...","role":"admin"}'
```

Verify it closed: a second call must return
`{"errors":[{"message":"You are not allowed to perform this action."}]}`.

## 2. Capacity

helios is **8 vCPU / 32 GB / 387 GB**, with **~25 GB RAM and 172 GB of disk
free**. The limits in `deploy/docker-compose.yml` total **11.5 GB** with the
`media` profile off — comfortable, not tight.

Worth noting: this is *more* than ARCHITECTURE.md §2's own production target
(a Hetzner CPX41, 8 vCPU / 16 GB / 240 GB). The stack is not being squeezed
onto this box.

The limits still matter. They exist so an OOM lands on the container that
caused it rather than on Postgres, and so one runaway Payload instance cannot
take down the 18 other sites CloudPanel serves from this host.

Two things the headroom unlocks that delphi could not host:

- **The media path.** 172 GB will hold the ~9 GB `wp-content/uploads` mirror
  with room to spare, so `garage` + `imgproxy` are a data question (E1.3) and
  no longer a capacity one — see §6.
- **Self-hosted Nominatim.** The geocoder's imported database is ~37 GB.
  That was impossible on delphi and is unremarkable here, which matters for
  re-running E2.5 and for E5.1's OSRM travel matrix.

## 3. Why images are built on GitHub, never on the box

`next build` is the most memory-hungry step in this stack and is what gets
OOM-killed on a small box, with an error that reads like a code fault rather
than a capacity one. helios has the RAM to build, but the images are still
built on GitHub: the artifact CI tested is then the artifact that runs, and
the box never needs a toolchain.

`.github/workflows/publish-images.yml` builds all six and pushes them to
GHCR; the VPS only pulls. Six images, **one tag** — deploy.sh pins them
together so a rollout cannot mix a new API with an old CMS:

```
ghcr.io/gaiadabali/now-postgres:sha-<short>
ghcr.io/gaiadabali/now-api:sha-<short>
ghcr.io/gaiadabali/now-worker:sha-<short>
ghcr.io/gaiadabali/now-web:sha-<short>
```

Four images, not six: `now-cms` and `now-console` are no longer built — the
CI matrix in `publish-images.yml` is the authority, and it lists these four.

`latest` is refused by `deploy.sh`. A rollback has to be able to name what it
is rolling back to.

**The packages are private** — they inherit the repository's visibility. A
token belonging to a different GitHub account cannot pull them even if that
account can read the repo. On the VPS, once:

```bash
docker login ghcr.io -u <github-user> -p <PAT with read:packages>
```

## 4. Routing: host nginx, not Caddy

helios's **host nginx owns 80/443** and terminates TLS with certs under
`/etc/nginx/ssl-certificates/`. The root `docker-compose.yml` runs Caddy;
`deploy/docker-compose.yml` deliberately does not. A containerised Caddy here
would either fail to bind or win the race and break every other site on the
box.

Every container publishes on **`127.0.0.1` only**. This is not decoration:
without it Docker publishes on `0.0.0.0` *and* writes its own iptables rules,
which bypass ufw entirely — the app would be reachable from the internet on a
raw unencrypted port while `ufw status` still claimed only 80/443 were open.

| Hostname | → | Port |
|---|---|---|
| `now-engine-api.gaiada.com` | | 4310 |
| `now-jakarta.gaiada.com` | | 4311 (web-jakarta) |
| `now-bali.gaiada.com` | | 4315 (web-bali) |

The three CMS/console hostnames that used to sit here (`now-cms-jakarta`,
`now-cms-bali`, `now-console`, ports 4312/4313/4316) are retired. The admin
is a path on the city hostnames now — `now-bali.gaiada.com/team-editor` —
behind the staff sign-in, so there is nothing separate to route or to "put
auth in front of".

There are two web processes, not one. `src/lib/site.ts` requires `SITE_SLUG`
and says plainly that the app "serves exactly one city per process", so a
single service fed both hostnames would throw at startup.

**Sites are created with `clpctl`, not by hand-writing vhosts.** helios runs
CloudPanel, which owns `/etc/nginx/sites-enabled/` and the certs; a
hand-written vhost there is liable to be overwritten and will not get a
certificate. Same command every other site on this host was made with:

```bash
clpctl site:add:reverse-proxy \
  --domainName=now-engine-api.gaiada.com \
  --reverseProxyUrl='http://127.0.0.1:4310' \
  --siteUser=nowapionl \
  --siteUserPassword='<generated>'
```

### Choosing a port needs two checks, not one

`ss -tlnp` only finds what is *listening*. A port can be referenced by
another project's vhost with nothing behind it — a naive check calls it free,
and taking it makes that project's domain quietly serve this application to
its visitors. That has already happened on a sibling host once (snap's
DEPLOY.md §11). So grep nginx as well:

```bash
ss -tlnH "sport = :4310"                    # nothing listening
grep -rE '127\.0\.0\.1:4310' /etc/nginx/  # and nothing pointing at it
```

Verified on helios 2026-09-14: 4310-4316 are all unlistened AND unreferenced.

## 5. First deploy

```bash
ssh helios
git clone https://github.com/gaiadabali/now.git /opt/now-engine
cd /opt/now-engine

cp deploy/.env.example deploy/.env
$EDITOR deploy/.env          # every blank value; openssl rand -hex 32

docker login ghcr.io -u <github-user> -p <PAT>
deploy/deploy.sh --pull --tag sha-<short sha>
```

`deploy.sh` pulls all six images **before** stopping anything — a new API
against an old CMS is worse than no rollout — then starts in dependency order
and verifies: Postgres and Redis healthy, `engine-api` answering `/healthz`,
and both web instances responding. It fails loudly rather than leaving a
half-deployed stack running.

There are no CMS or console instances to check any more — `deploy.sh`'s own
`SERVICES` list is postgres, redis, engine-api, engine-worker, web-jakarta,
web-bali, and the admin is a path on the two web instances.

The databases still need loading (E1.8) and migrations (`now-db`). `deploy.sh`
does not do this yet — it is a rollout driver, not a migration runner.

## 6. The media path is off

`garage` and `imgproxy` sit behind the `media` compose profile and do not
start by default. E1.3 — mirroring `wp-content/uploads` into Garage — is
still blocked, so they would serve an empty bucket. On helios that is purely
a data question — 172 GB holds the ~9 GB mirror easily — and no longer a
capacity one. `web/next.config.mjs` still points `remotePatterns` at the
legacy WordPress hosts, which is where images come from today.

Turn them on in the same change that unblocks the mirror:

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env \
  --profile media up -d
```

## 7. Routine deploy and rollback

```bash
git pull && deploy/deploy.sh --pull --tag sha-<short>   # after CI is green
deploy/deploy.sh --rollback sha-<previous>              # no migration
deploy/deploy.sh --status
```

Rollback does not reverse migrations, and nothing in this script touches the
postgres volume. A migration that must be undone is a separate, deliberate
act.

## 8. Still required, and not doable from here

- **DNS** for the six hostnames in §4, pointing at `187.77.116.133`.

  `gaiada.com` is on **Hostinger** — checked, not assumed: its nameservers
  are `ns1.dns-parking.com` / `ns2.dns-parking.com`, which is Hostinger's
  parking/DNS pair. (An earlier draft of this file said GoDaddy; that was
  carried over from a sibling project's runbook and was wrong.)

  Three A records in hPanel → Domains → DNS Zone, each `Type A`, `Points to
  187.77.116.133`, TTL default:

  | Name | |
  |---|---|
  | `now-engine-api` | the API |
  | `now-jakarta` | web-jakarta — reader site **and** `/team-editor` |
  | `now-bali` | web-bali — reader site **and** `/team-editor` |

  It was six. `now-cms-jakarta`, `now-cms-bali` and `now-console` are not
  needed: the admin is a path on the city hostnames
  ([ADMIN-CONSOLIDATION.md](ADMIN-CONSOLIDATION.md)). Three records never
  created is three fewer certificates to renew.

  Hostinger's DNS Zone editor takes the subdomain only, not the full name.

  Verified 2026-09-14: none resolve yet, while an existing sibling
  (`bsc.gaiada.online`) resolves to this host, so the check is sound.
- **CloudPanel sites**, one per hostname (`clpctl site:add:reverse-proxy`),
  which also issues the certificate. DNS must resolve first or issuance
  fails.
- **A GHCR pull token** on the box (§3).
- **A staff account in `now_platform.public.users`.** Identity is the
  platform's, not a city's: the admin's sign-in verifies against that table
  and projects a shadow row into the city database
  ([ADMIN-CONSOLIDATION.md](ADMIN-CONSOLIDATION.md) Phase 1). A row with no
  `hash`/`salt` cannot sign in, so seed one deliberately — there is no
  "create the first user" screen to race anyone to, because the collection
  sets `disableLocalStrategy`:

  ```bash
  PLATFORM_DATABASE_URI=... npm run staff-account -w @now/auth --     --email you@example.com --name "Your Name" --editorial admin --commerce admin
  ```

  It prints a generated password once. The same command resets a password and
  clears a lockout, so it is also the answer to "I am locked out of the admin".
  The city shadow row is created by the first sign-in, not by this.
- **Database load + migrations** — the images will start against an empty
  Postgres and the API will answer `/healthz` regardless, because that probe
  does not touch a city database. Do not read a green deploy as "the content
  is live".
- **A Google Workspace app password, and the two secrets that depend on it**
  (E8, reader accounts). Without these `/account/*` is broken in production
  while the rest of the site is fine — sign-up, verification and password reset
  all need mail, and the app refuses to start with a console transport under
  `NODE_ENV=production` rather than pretending to send.

  **Google Workspace, not Hostinger.** An earlier draft of this file said
  Hostinger, on the assumption that mail follows the DNS registrar. It does
  not. Checked live 2026-09-16:

  ```
  MX    gaiada.com        ->  smtp.google.com (1)
  TXT   gaiada.com        ->  v=spf1 include:_spf.google.com ~all
  TXT   _dmarc.gaiada.com ->  v=DMARC1; p=none; ...; adkim=s; aspf=s
  ```

  SPF authorises Google **and nothing else**, and DMARC asks for strict
  alignment on both legs. Sending through Hostinger would have failed SPF and
  landed every verification mail in spam — which, from a reader's side, is
  indistinguishable from no mail ever being sent.

  1. Use (or create) a Workspace mailbox to send as — `hello@gaiada.com` is
     what `.env.example` assumes.
  2. Google account → Security → **App passwords** (needs 2-Step
     Verification). Google rejects the plain account password over SMTP.
  3. Set on each web service:

     ```
     MAIL_TRANSPORT=smtp
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=465            # implicit TLS; SMTP_SECURE is derived from this
     SMTP_USER=hello@gaiada.com
     SMTP_PASSWORD=…          # the 16-character app password
     MAIL_FROM_EMAIL=hello@gaiada.com    # must align with SMTP_USER (aspf=s)
     MAIL_FROM_NAME="NOW! Jakarta"       # per city
     MAIL_SUPPORT_EMAIL=hello@gaiada.com
     SITE_BASE_URL=https://now-jakarta.gaiada.com   # per city
     READER_SESSION_SECRET=…  # openssl rand -base64 48
     ```

     `READER_SESSION_SECRET` **must differ from `PAYLOAD_SECRET`**; the app
     throws at startup if they match. Readers and staff are separate
     populations with separate cookies, and a shared signing key would leave
     the `aud` claim as the only thing between a reader token and the admin
     (docs/READER-IDENTITY.md).

  **Limit:** 2,000 messages/day on `smtp.gmail.com`. Ample for verification and
  reset mail. `smtp-relay.gmail.com` allows 10,000/day and authenticates by IP
  — helios has a static one — if that ever becomes the constraint.

  ⚠️ **DKIM is not published for `gaiada.com`.** `google._domainkey.gaiada.com`
  does not resolve (checked 2026-09-16), while the DMARC record already asks
  for strict DKIM alignment (`adkim=s`). Nothing is being rejected today
  because the policy is `p=none`, so this is a deliverability and
  reputation problem rather than an outage — but every message sent is failing
  the DKIM leg of its own DMARC policy, and it must be fixed before that policy
  is ever tightened to `quarantine` or `reject`. Workspace admin → Apps →
  Gmail → Authenticate email → generate the key, then publish the TXT record in
  hPanel.
- **`ENGINE_API_EXTRA_ALLOWED_ORIGINS` on the API, while the engine is served
  from a domain `sites.hostname` does not name.**

  The beacon's only gate is a CORS origin allowlist built from
  `sites.hostname` (decision C2). The registry currently holds the
  **post-cutover** hostnames — `nowjakarta.co.id`, `nowbali.co.id`, which
  resolve to `187.77.123.72`, the legacy WordPress site on another host —
  while the engine is served from `now-jakarta.gaiada.com` /
  `now-bali.gaiada.com`. Until those agree, every beacon batch is rejected
  `403`: the site's own front end judged exactly like a hostile one, silently,
  collecting nothing. Measured 2026-09-17 — zero interactions on either city
  since 2026-09-09.

  ```
  ENGINE_API_EXTRA_ALLOWED_ORIGINS={"jakarta":["https://now-jakarta.gaiada.com"],"bali":["https://now-bali.gaiada.com"]}
  ```

  Keyed by site slug, never a flat list — a flat list would let one city's
  origin write behaviour into another city's database. **Delete these entries
  after the cutover**, when the registry hostname becomes the served hostname
  and they turn redundant. That they expire is the point; do not treat this as
  permanent parallel config.

  Do NOT "fix" this by editing `sites.hostname` instead. That column also
  drives `metadataBase` in the reader app, so moving it would drag canonical
  and OG URLs onto the staging domain.

- **`SITE_BASE_URL` per city, before the account surface is switched on.**

  `lib/reader.ts`'s `siteBaseUrl()` falls back to `https://${site.hostname}`
  when this is unset — so with the registry as above, every verification and
  password-reset link would point at the **legacy WordPress site**, on a
  different server, and simply not work. Latent today only because
  `/account/*` correctly serves 404 while mail is unconfigured (F141).

  ```
  SITE_BASE_URL=https://now-jakarta.gaiada.com     # per city
  ```

  Treat this as a precondition of enabling accounts, alongside the Workspace
  app password and `READER_SESSION_SECRET` above — not as a default that
  happens to be right.

  The same fallback shape sits behind `metadataBase`, which is why canonical
  URLs currently point at the legacy site. That one is a deliberate SEO
  decision to make, not a bug to patch here.

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
| `web-jakarta` · `web-bali` | ready — one image, one process per city |
| `cms-jakarta` · `cms-bali` | ready — one image, two databases (§3.5) |
| `garage` · `imgproxy` | **off** — behind the `media` profile, see §6 |
| `engine-worker` | ready — arq cron + the re-embed stream consumer |
| `console` | ready — Payload auth, **read-only** against commerce data |

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
ghcr.io/gaiadabali/now-console:sha-<short>
ghcr.io/gaiadabali/now-web:sha-<short>
ghcr.io/gaiadabali/now-cms:sha-<short>
```

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
| `now-cms-jakarta.gaiada.com` | | 4312 |
| `now-cms-bali.gaiada.com` | | 4313 |
| `now-console.gaiada.com` | | 4316 — **put auth in front of this** |

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
and both web instances, both CMS instances and the console responding. It fails loudly rather than leaving a
half-deployed stack running.

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

  Six A records in hPanel → Domains → DNS Zone, each `Type A`, `Points to
  187.77.116.133`, TTL default:

  | Name | |
  |---|---|
  | `now-engine-api` | the API |
  | `now-jakarta` | web-jakarta |
  | `now-bali` | web-bali |
  | `now-cms-jakarta` | Payload, Jakarta |
  | `now-cms-bali` | Payload, Bali |
  | `now-console` | commerce console — **auth first** |

  Hostinger's DNS Zone editor takes the subdomain only, not the full name.

  Verified 2026-09-14: none of the six resolve yet, while an existing
  sibling (`bsc.gaiada.online`) resolves to this host, so the check is sound.
- **CloudPanel sites**, one per hostname (`clpctl site:add:reverse-proxy`),
  which also issues the certificate. DNS must resolve first or issuance
  fails.
- **A GHCR pull token** on the box (§3).
- **The console's Payload migration + first admin user** (§1). Until that
  runs there is no account, and `/admin` will offer to create the first one
  to whoever reaches it — so do it in the same session the host goes live.
- **Database load + migrations** — the images will start against an empty
  Postgres and the API will answer `/healthz` regardless, because that probe
  does not touch a city database. Do not read a green deploy as "the content
  is live".

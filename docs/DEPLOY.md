# Deploying NOW! Engine to delphi

The target is **delphi** (`72.61.142.88`, Ubuntu 24.04), a shared KVM box that
already runs `snap-apps`, `cosmedic-staging` and `infisical`. Everything
deploy-related lives in [`deploy/`](../deploy).

---

## 1. What can go live today, and what cannot

| Service | State |
|---|---|
| `postgres` · `redis` | ready — custom PG image carries pgvector + PostGIS |
| `engine-api` | ready — ARCHITECTURE.md §16 calls this the durable deliverable |
| `web` | ready — one instance, hostname selects the city |
| `cms-jakarta` · `cms-bali` | ready — one image, two databases (§3.5) |
| `garage` · `imgproxy` | **off** — behind the `media` profile, see §6 |
| `engine-worker` | **cannot deploy** — `engine/apps/worker/` has no source |
| `console` | **cannot deploy** — `engine/apps/console/` has no source |

The last two are empty directories. They have compose placeholders in the
root dev stack and are deliberately absent from `deploy/docker-compose.yml`:
there is nothing to build an image from, and a Dockerfile for code that does
not exist would only produce something that looks deployable.

## 2. Capacity — read this before adding anything

delphi is **2 vCPU / 7 GB**, with roughly **4 GB free** and **11 GB of disk**
(89% used). The memory limits in `deploy/docker-compose.yml` total ~3.4 GB
with the `media` profile off. That is deliberate and it is tight.

The limits are not there to be generous, they are there so that an OOM lands
on the container that caused it rather than on Postgres. If the box gets
unhappy, **stopping `cms-bali` is the first lever** — two Payload instances
are the heavy part, and Bali has no editors on it yet.

ARCHITECTURE.md specs a Hetzner CPX41 (8 vCPU / 16 GB / 240 GB) for this
stack. delphi is a staging host, not that.

## 3. Why images are built on GitHub, never on the box

`next build` is the most memory-hungry step in this stack and is what gets
OOM-killed on a small box, with an error that reads like a code fault rather
than a capacity one. `.github/workflows/publish-images.yml` builds all four
images on GitHub and pushes them to GHCR; the VPS only pulls.

The larger benefit is that the artifact CI tested is the artifact that runs.

Four images, one tag:

```
ghcr.io/gaiadabali/now-postgres:sha-<short>
ghcr.io/gaiadabali/now-api:sha-<short>
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

delphi's **host nginx owns 80/443** and terminates TLS with certs under
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
| `now-jakarta.gaiada.com` | | 4311 (web) |
| `now-bali.gaiada.com` | | 4311 (web — same instance, Host header selects the city) |
| `cms-jakarta.gaiada.com` | | 4312 |
| `cms-bali.gaiada.com` | | 4313 |

**Sites are created with `clpctl`, not by hand-writing vhosts.** delphi runs
CloudPanel (6.0.8), which owns `/etc/nginx/sites-enabled/` and the certs; a
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
its visitors. That has already happened on this box once (snap's DEPLOY.md
§11). So grep nginx as well:

```bash
ss -tlnH "sport = :4310"                    # nothing listening
grep -rE '127\.0\.0\.1:4310' /etc/nginx/  # and nothing pointing at it
```

Verified for 4310-4314 on 2026-09-14: unlistened and unreferenced.

## 5. First deploy

```bash
ssh delphi
git clone https://github.com/gaiadabali/now.git /opt/now-engine
cd /opt/now-engine

cp deploy/.env.example deploy/.env
$EDITOR deploy/.env          # every blank value; openssl rand -hex 32

docker login ghcr.io -u <github-user> -p <PAT>
deploy/deploy.sh --pull --tag sha-<short sha>
```

`deploy.sh` pulls all four images **before** stopping anything — a new API
against an old CMS is worse than no rollout — then starts in dependency order
and verifies: Postgres and Redis healthy, `engine-api` answering `/healthz`,
and web/both CMS instances responding. It fails loudly rather than leaving a
half-deployed stack running.

The databases still need loading (E1.8) and migrations (`now-db`). `deploy.sh`
does not do this yet — it is a rollout driver, not a migration runner.

## 6. The media path is off

`garage` and `imgproxy` sit behind the `media` compose profile and do not
start by default. E1.3 — mirroring `wp-content/uploads` into Garage — is
still blocked, so they would serve an empty bucket while costing ~640 MB on a
box with ~4 GB free. `web/next.config.mjs` still points `remotePatterns` at
the legacy WordPress hosts, which is where images come from today.

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

- **DNS** for the five hostnames in §4, pointing at `72.61.142.88`.
  `gaiada.com` is on GoDaddy (`ns37/ns38.domaincontrol.com`).
- **CloudPanel sites**, one per hostname (`clpctl site:add:reverse-proxy`),
  which also issues the certificate. DNS must resolve first or issuance
  fails.
- **A GHCR pull token** on the box (§3).
- **Database load + migrations** — the images will start against an empty
  Postgres and the API will answer `/healthz` regardless, because that probe
  does not touch a city database. Do not read a green deploy as "the content
  is live".

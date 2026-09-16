# web — the reader site. ONE Next.js image serving every city
# (ARCHITECTURE.md §3.5): the hostname selects the SiteConfig and the city
# connection pool at request time, so nothing city-specific is baked in and a
# new region needs no rebuild.
#
# BUILD CONTEXT IS THE REPO ROOT, NOT this directory and no longer `engine/`.
#
#     docker build -f engine/apps/web/Dockerfile .
#
# It used to build from `engine/apps/web`, then from `engine/`. Two reasons it
# is now the root:
#
#   1. This app is an npm workspace member. The lockfile lives at the
#      workspace root and `npm ci` inside a single member has no lockfile to
#      read. The workspace is not optional either — this app imports the CMS's
#      Payload config to run the Local API in-process (docs/ui-data-layer.md).
#      That is why the context could not stay `apps/web`.
#
#   2. The city config (`<slug>/site/site.config.json`) lives at the repo
#      root, and it is now BAKED IN rather than bind-mounted. It used to be
#      mounted so that a brand or nav change was a restart instead of a
#      rebuild — but that benefit was never once used, and its cost was a
#      silent drift trap: new code running against old config, no error
#      anywhere, a footer quietly missing the links the build had added. An
#      image that carries its own config cannot disagree with itself.
#
# `engine/` is still the workspace root INSIDE the image (WORKDIR /app), so
# every COPY below names its source with an `engine/` prefix while its
# destination is unchanged. The API image already builds from the root; the
# root .dockerignore is tuned for exactly this and keeps the city `site/`
# directories while excluding the ~600 MB of dumps and extracted content.

FROM node:22.11-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

FROM base AS deps
# Manifests only, before the source: this layer is then cached across every
# build that does not change a dependency, which is most of them.
COPY engine/package.json engine/package-lock.json ./
COPY engine/apps/web/package.json ./apps/web/
# apps/console serves nothing any more — it is the migration home for
# `now_platform.public` (see its README). Its manifest is still copied
# because `npm ci` below installs the WHOLE workspace and refuses to run
# against a lockfile whose members it cannot all find.
COPY engine/apps/console/package.json ./apps/console/
COPY engine/packages/cms/package.json ./packages/cms/
COPY engine/packages/auth/package.json ./packages/auth/
COPY engine/packages/beacon/package.json ./packages/beacon/
# `npm ci` installs the WHOLE workspace, not just this member. That is
# deliberate: the web app's dependency graph reaches into packages/cms (the
# Payload config) and transitively packages/auth, so a members-only install
# would be missing exactly the things this image needs.
RUN npm ci
# sharp ships a per-platform binary as an OPTIONAL dependency, and this
# lockfile is generated on a developer's machine — so the linuxmusl-x64
# package it needs in this image is simply not in it. `npm ci` honours the
# lockfile exactly and installs nothing extra, which is normally the point.
#
# The failure is at RUNTIME, not build: the image builds clean and then every
# request 500s with
#   Could not load the "sharp" module using the linuxmusl-x64 runtime
# because Payload's config constructs an image processor at module load.
RUN npm install --no-save --os=linux --libc=musl --cpu=x64 sharp

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
# `engine/`, not `.`: the context is the repo root now, but /app must remain
# the npm workspace root or every relative path in the build breaks.
COPY engine/ ./
ENV NEXT_TELEMETRY_DISABLED=1
# Nothing here evaluates a database at build time — pages read through the
# Local API at REQUEST time — but importing the Payload config does construct
# the postgres adapter at module load, so it needs a syntactically valid URI
# to get through `next build`. No query runs against it.
ARG DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ARG PLATFORM_DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ENV DATABASE_URI=$DATABASE_URI
ENV PLATFORM_DATABASE_URI=$PLATFORM_DATABASE_URI
# The beacon FIRST. The web app's `prebuild` runs `scripts/sync-beacon.mjs`,
# which copies `packages/beacon/dist/beacon.min.js` into `public/` and exits
# 1 rather than skipping when it is missing — deliberately, because a site
# that silently stops collecting behaviour cannot be backfilled.
#
# That dist/ is gitignored, so it exists on a developer's machine and in no
# clone. The image built fine until the beacon gained a prebuild step, then
# failed here with a bare `npm error command sh -c node scripts/sync-beacon.mjs`
# and no mention of the beacon at all. Building it here is what makes the
# image self-sufficient: `npm ci` above installs the whole workspace
# including devDependencies, so terser is present.
RUN npm run build --workspace=@now-engine/beacon
RUN npm run build --workspace=@now-engine/web

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# next/image writes optimised variants into .next/cache at runtime, so the
# runtime user needs to own the app directory.
RUN addgroup --system --gid 10001 nodejs \
 && adduser --system --uid 10001 nextjs

# `output: 'standalone'` with a workspace `outputFileTracingRoot` emits the
# bundle rooted at the WORKSPACE, so server.js sits at apps/web/server.js
# rather than at the top. The three COPYs below mirror that layout; getting
# them wrong produces an image that starts and 500s on every request.
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
# sharp, copied EXPLICITLY rather than left to Next's dependency tracing.
#
# The deps stage installs the linuxmusl binary, but the runner takes the
# traced standalone bundle — and the tracer does not follow a package added
# with `--no-save` after `npm ci`, because nothing in package.json points at
# it. The image then starts, serves most pages, and throws
#   Could not load the "sharp" module using the linuxmusl-x64 runtime
# the first time anything optimises an image. That is why a smoke test on the
# homepage alone missed it: the homepage never asks sharp for anything.
#
# @img/* carries the actual platform binaries; sharp/ alone is not enough.
COPY --from=deps --chown=nextjs:nodejs /app/node_modules/sharp ./node_modules/sharp
COPY --from=deps --chown=nextjs:nodejs /app/node_modules/@img ./node_modules/@img
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./apps/web/public

# The city config, baked in — read straight from the build context, since it
# lives at the repo root rather than under engine/.
#
# `getSiteConfig()` resolves `<NOW_REPO_ROOT>/<slug>/site/site.config.json`,
# so the layout here has to mirror the repo's. Only the config file is copied,
# not the rest of `<slug>/site/` — taxonomy mappings and place overrides are
# pipeline inputs that nothing reads at request time.
#
# Both cities ship in ONE image. That is the same promise as §3.5: the image
# is city-agnostic and SITE_SLUG picks which row it reads at startup.
COPY --chown=nextjs:nodejs jakarta/site/site.config.json ./sites/jakarta/site/site.config.json
COPY --chown=nextjs:nodejs bali/site/site.config.json ./sites/bali/site/site.config.json
ENV NOW_REPO_ROOT=/app/sites

USER nextjs
EXPOSE 3100
ENV PORT=3100
ENV HOSTNAME=0.0.0.0

CMD ["node", "apps/web/server.js"]

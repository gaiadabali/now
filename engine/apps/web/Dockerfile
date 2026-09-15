# web — the reader site. ONE Next.js image serving every city
# (ARCHITECTURE.md §3.5): the hostname selects the SiteConfig and the city
# connection pool at request time, so nothing city-specific is baked in and a
# new region needs no rebuild.
#
# BUILD CONTEXT IS engine/, NOT this directory.
#
#     docker build -f engine/apps/web/Dockerfile engine
#
# It used to build from `engine/apps/web`. It cannot any more: this app is an
# npm workspace member, the lockfile lives at the workspace root, and
# `npm ci` inside a single member has no lockfile to read. The workspace
# itself is not optional — this app imports the CMS's Payload config to run
# the Local API in-process (docs/ui-data-layer.md), and before hoisting there
# were three copies of payload in the tree.

FROM node:22.11-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

FROM base AS deps
# Manifests only, before the source: this layer is then cached across every
# build that does not change a dependency, which is most of them.
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
COPY apps/console/package.json ./apps/console/
COPY packages/cms/package.json ./packages/cms/
COPY packages/auth/package.json ./packages/auth/
COPY packages/beacon/package.json ./packages/beacon/
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
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Nothing here evaluates a database at build time — pages read through the
# Local API at REQUEST time — but importing the Payload config does construct
# the postgres adapter at module load, so it needs a syntactically valid URI
# to get through `next build`. No query runs against it.
ARG DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ARG PLATFORM_DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ENV DATABASE_URI=$DATABASE_URI
ENV PLATFORM_DATABASE_URI=$PLATFORM_DATABASE_URI
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
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3100
ENV PORT=3100
ENV HOSTNAME=0.0.0.0

CMD ["node", "apps/web/server.js"]

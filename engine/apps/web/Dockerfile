# web — the reader site. ONE Next.js image serving every city
# (ARCHITECTURE.md §3.5): the hostname selects the SiteConfig and the city
# connection pool at request time, so nothing city-specific is baked in and
# a new region needs no rebuild.
#
# Build context is THIS directory — unlike engine-api, the web app has no
# dependencies outside its own package.json.
#
# Mirrors engine/packages/cms/Dockerfile deliberately: same base image, same
# deps/builder/runner split, same standalone output. Two Next apps that
# build differently is a maintenance cost with no upside.

FROM node:22.11-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Unlike the CMS, nothing here evaluates a database at build time — the web
# app reads through engine-api at request time, so no DATABASE_URI
# placeholder is needed to get through `next build`.
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# next/image writes optimised variants into .next/cache at runtime, so the
# runtime user needs to own the app directory.
RUN addgroup --system --gid 10001 nodejs \
 && adduser --system --uid 10001 nextjs

COPY --from=builder /app/public ./public
# `output: 'standalone'` (next.config.mjs) emits a server bundle carrying
# only the node_modules actually imported. Without that setting this COPY
# fails — which is exactly how the CMS Dockerfile was broken.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3100
ENV PORT=3100
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]

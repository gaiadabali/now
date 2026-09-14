# console — partner + campaign management. ONE instance, serving every city:
# it binds the PLATFORM database only (ARCHITECTURE.md §2), so unlike web and
# cms there is nothing per-city about it and no SITE_SLUG to set.
#
# This is a Payload app (auth, /admin) that also serves its own read pages,
# so it builds like engine/packages/cms rather than like web.
#
# Build context is THIS directory — no dependencies outside its package.json.
# Mirrors engine/apps/web/Dockerfile; two Next apps that build differently is
# a maintenance cost with no upside.

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
# DATABASE_URI is required for `next build` to statically evaluate
# payload.config.ts, which constructs the Postgres adapter at module-load
# time. A build-time-only placeholder is fine — nothing queries it during
# the build, only at `next start`. Same reasoning as the CMS image.
ARG DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ARG PAYLOAD_SECRET=build-placeholder
ENV DATABASE_URI=$DATABASE_URI
ENV PAYLOAD_SECRET=$PAYLOAD_SECRET
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 10001 nodejs \
 && adduser --system --uid 10001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Migrations ship with the image so `payload migrate` can run against the
# platform database from inside the container that owns the schema.
COPY --from=builder --chown=nextjs:nodejs /app/src/migrations ./src/migrations

USER nextjs
EXPOSE 3200
ENV PORT=3200
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]

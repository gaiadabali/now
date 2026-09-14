# console — partner + campaign management. ONE instance, serving every city:
# it reads the PLATFORM database only (ARCHITECTURE.md §2), so unlike web and
# cms there is nothing per-city about it and no SITE_SLUG to set.
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
# Every page is `dynamic = 'force-dynamic'`, so no database is reached during
# `next build` and no placeholder DATABASE_URL is needed — unlike the CMS,
# whose payload.config.ts constructs its adapter at module-load time.
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 10001 nodejs \
 && adduser --system --uid 10001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3200
ENV PORT=3200
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]

# cms — ONE image, one process per city (ARCHITECTURE.md §3.5). The image
# is identical for every deployment; only the container's env vars differ
# (DATABASE_URI above all). docker-compose.yml's `cms-<city>` services both
# point `build.context` at this directory and pass a different
# DATABASE_URI/SITE_SLUG — that env-only differentiation is the whole
# point of this package, not something this Dockerfile has to know about.

FROM node:22.11-alpine AS base
WORKDIR /app
# sharp (image processing) needs these at runtime on alpine.
RUN apk add --no-cache libc6-compat vips-dev

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev=false

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# DATABASE_URI is required for `next build` to statically evaluate
# payload.config.ts (it fetches the vocabulary and constructs the Postgres
# adapter at module-load time). A build-time-only placeholder is fine —
# no query runs against it during `next build`, only during `next start`.
ARG DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ARG PLATFORM_DATABASE_URI=postgresql://build:build@localhost:5432/build_placeholder
ENV DATABASE_URI=$DATABASE_URI
ENV PLATFORM_DATABASE_URI=$PLATFORM_DATABASE_URI
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/src/migrations ./src/migrations
EXPOSE 3000
CMD ["node", "server.js"]

# UI data layer — how the reader site gets its content

Companion to [ARCHITECTURE.md](../ARCHITECTURE.md) §3.5, §9 and §16.
Status: **comp phase.** `engine/apps/web` renders from fixtures today; this
document is the contract the replacement must satisfy.

## The split

The reader app reads from **two** sources, and the boundary is not negotiable:

| Need | Source | Why |
|---|---|---|
| Articles, places, events, media, taxonomy terms | **Payload Local API**, city DB `public` | Same process, no HTTP hop, types come from `payload-types.ts` |
| Ranked rails, hybrid search, facet counts, itinerary, assistant | **engine-api** (`/v1/...`) | Ranking lives in Python; the site must never reimplement it |

A page may call both. A page may never query Postgres directly, and may never
re-rank what engine-api returned — presentation-bias warning, §10.

## Why Local API and not the REST/GraphQL endpoint

`engine/apps/web` and `engine/packages/cms` bind to the **same city database**.
Importing the Payload config and calling `getPayload({ config })` runs the query
in-process: no network, no serialisation, no second auth hop, and the returned
objects are already typed by the generated `Config`. The REST endpoint exists for
outside consumers, not for our own server components.

Consequence: the web app takes `@now-engine/cms` as a dependency and reads
`DATABASE_URI` the same way the CMS does. It must **never write**.

## Swapping the fixtures out

Every function in `src/lib/content.ts` already has its final signature. The
migration is function-by-function, and no page changes:

```ts
// today
export async function getBySlug(slug: string): Promise<Article | undefined> {
  return ARTICLES.find((a) => a.slug === slug)
}

// after
export async function getBySlug(slug: string): Promise<Article | undefined> {
  const payload = await getPayload({ config })
  const { docs } = await payload.find({
    collection: 'articles',
    where: { slug: { equals: slug }, _status: { equals: 'published' } },
    limit: 1,
    depth: 1,
  })
  return docs[0] ? toArticle(docs[0]) : undefined
}
```

`toArticle()` is the one place the Payload row shape meets the view model. Keep
it; pages should not learn what a Payload document looks like.

| Fixture | Replaced by |
|---|---|
| `getLatest`, `getBySection`, `getBySlug` | Payload `find` on `articles` |
| `getMostRead` | engine-api — view counts are bot-contaminated in WP (§6) and must be recomputed from beacon data, not imported |
| `getRelated` | `GET /v1/articles/{id}/rails` — **already live** |
| `GUIDES` | curated `guides` collection (not yet built) |
| `EVENTS` | `events` collection, filtered to upcoming in site timezone |
| `PLACE` | `places` collection + PostGIS for the Nearby rail |
| Section facet counts | engine-api aggregate pass — count each facet with every filter **except** that facet (§9) |

## Routing constraints

- **`/{slug}` is flat and must stay flat.** Legacy permalinks are
  `/%postname%/` on both sites (LIVE_RECON), and they are the traffic. The
  single `[slug]` route resolves section-first, then article. Do not split it
  into sibling dynamic routes.
- `articles.legacy_permalink` plus the imported `nb15_redirection_items` map
  drive 301s. Those belong in middleware, not in the page.
- A Redirection-plugin rule **beats** a live article with the same slug
  (F17). Whatever implements the 301 map must preserve that precedence, and
  must keep query strings on the two external targets.

## Caching

- Article and section pages: static with ISR. Content changes arrive via a
  revalidation hook from Payload's `afterChange` — the same hook that already
  publishes to Redis (`publishArticleEvent.ts`).
- Rails and facet counts: server-rendered, cached briefly. They are personalised
  later (E7), at which point they become dynamic and must not be in the static
  payload.
- Never cache anything keyed to an identity in a shared cache.

## Media

Images are still served from the legacy WordPress hosts, allowlisted in
`next.config.mjs`. Once E1.3 mirrors uploads into Garage, imgproxy fronts them
and those `remotePatterns` entries are deleted — that is the whole change.

## Budget

Article and index pages ship **zero page-level client JS**. `'use client'` is
allowed only for the nav drawer, facet panel, search box and map. Check with
`npm run build` and read the per-route Size column; it is currently 181 B.

import 'server-only'

import { toArticles, type Article } from '@/lib/content'
import { cityPool, payloadClient } from '@/lib/payload'
import type { TypeRelations } from '@/lib/competitorPolicy'
import {
  complementSectionsFor,
  dedupeBySeries,
  diversify,
  groupComplementCandidatesBySection,
  loadRelations,
  resolveComplementCandidates,
  resolveReadNextCandidates,
  type CandidateRow,
  EMBEDDING_MODEL,
  QUALITY_FLOOR,
} from '@/lib/recommendSql'

/**
 * What the reader site asks the engine for, and nothing else.
 *
 * This file is a CONTRACT first and an implementation second. Two pieces of
 * work build against it at once: the recommendation engine fills in the
 * bodies, and the reader redesign renders whatever comes back. Neither should
 * need to open the other's files to do its job, which is why the page never
 * learns how a rail was chosen — it gets rails, in order, already labelled.
 *
 * ## The one rule the page must never break
 *
 * On a venue story, nothing on the page may suggest a competitor of that
 * venue. A hotel story never suggests a hotel (or a villa, or a resort — the
 * rule is the L1 `type`, ARCHITECTURE §4). A restaurant story never suggests a
 * restaurant, a café or any other food-and-drink venue — F&B is ONE
 * competitive class (migration 0008, 2026-09-24). The owner's words, thrice
 * now (2026-09-11, twice on 2026-09-24): suggest the *other* things a reader
 * needs — somewhere to eat after the hotel, somewhere to stay after dinner.
 *
 * That rule is enforced HERE and in the engine, never in a component. A page
 * that adds its own "More from this section" rail under a hotel story has
 * broken it, however the rail is styled.
 *
 * ## Where this computes, and why (WS1, Edition 2, documented per the ticket)
 *
 * `GET /v1/{site}/articles/{id}/rails` (ARCHITECTURE §16) already exists,
 * server-side, fully tested (`engine/packages/rails`) — Row 3 (semantic
 * similarity) is article-shaped and could be consumed directly. Row 1
 * (complementary) is PLACE-shaped, not article-shaped, so it does not
 * directly serve this file's "plan around it" contract without an extra
 * place->article resolution step. This iteration computes both rails
 * directly against `engine.*` (the actual SQL lives in `lib/recommendSql
 * .ts`, shared with `scripts/verify-competitor-policy.mjs` so the proof
 * and the product can never silently diverge) rather than calling the
 * HTTP API — a deliberate, DOCUMENTED exception to `lib/payload.ts`'s "a
 * page may never query Postgres directly" rule, left as-is per the
 * coordinator's second-pass review ("leave the engine-API-vs-web-tier
 * decision as documented; I'll take it to the owner").
 *
 * Ranking may legitimately differ between this path and the engine-api
 * path — the exclusion policy may not, and is asserted identically on
 * both sides via `lib/competitorPolicy.ts` + `lib/hiddenRival.ts`, sharing
 * ONE conformance-vector file both suites assert against
 * (`engine/packages/taxonomy/seed/competitor_conformance.json`).
 *
 * ## Speed (second pass)
 *
 * Budget: ARCHITECTURE §7 says article-page rail work should cost
 * p95 <= 150ms server time, warm. `EXPLAIN (ANALYZE, BUFFERS)` against
 * real data found the first version's live hidden-rival regex join
 * costing ~27ms of a ~49ms Read Next query — moved offline into
 * `engine.hidden_rival_flags` (migration 0009,
 * `now_filters.hidden_rival_recompute`), measured ~22ms warm afterward.
 * The complement rail is now ONE query (was up to 4), and Read Next +
 * complement rails run in parallel (`Promise.all` below). Ticket report
 * has the full before/after numbers for both cities.
 *
 * ## Rail count and overlap (second pass)
 *
 * At most `MAX_PLAN_AROUND_RAILS` (3) "plan around it" rails, in the
 * subject's own `complements` order (now-db migration 0010 reordered
 * that array to double as display priority — see `recommendSql
 * .complementSectionsFor`). No article may appear in more than one rail
 * on the page, complement rails included Read Next: complement rails are
 * resolved first (they are the more specific recommendation), and any id
 * they used is excluded when Read Next's own pool is diversified down to
 * its final `limit`.
 */

export type RailArticle = Article & {
  rail: string
  /** 1-indexed slot. The beacon needs it on the impression AND the click. */
  position: number
}

export type ArticleRail = {
  /** Stable key — also the beacon's `data-nowb-rail`. */
  key: string
  /** Bebas kicker. Information, not decoration (DESIGN-SYSTEM §2). */
  kicker: string
  title: string
  items: RailArticle[]
}

/**
 * Who is reading. Every field is optional: an anonymous first visit is the
 * common case and must get a good page, not a degraded one.
 */
export type ReaderContext = {
  /** The beacon's anonymous id, when the reader has one. */
  anonId?: string
  /** A signed-in reader (`engine.identities.id`). */
  identityId?: string
}

/** A uuid-shaped cookie value, matching `lib/stitch.ts`'s own validation —
 * a malformed `nowb_aid` cookie must not be handed to Postgres as a uuid. */
function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

/**
 * Builds a `ReaderContext` from the current request's cookies — the helper
 * `getArticleRails`/`getForYou` callers (page components) use so neither one
 * has to know the beacon's cookie name or the reader session mechanics.
 * Never throws: a page rendering for the first-ever anonymous visit must not
 * fail because there is, correctly, no session at all.
 */
export async function readerContextFromRequest(): Promise<ReaderContext> {
  const context: ReaderContext = {}
  try {
    // Dynamic, not a top-level import: `next/headers` only resolves inside
    // Next's server runtime, and this file also imports `server-only`,
    // which only resolves under Next's `react-server` condition — neither
    // is available to `scripts/verify-competitor-policy.mjs`, which
    // exercises `lib/recommendSql.ts`'s candidate-resolution SQL directly
    // with no Next process at all.
    const { cookies } = await import('next/headers')
    const jar = await cookies()
    const anonId = jar.get('nowb_aid')?.value
    if (anonId && isUuid(anonId)) context.anonId = anonId
  } catch {
    // No request-scoped cookie store available (e.g. called outside a
    // request) — an anonymous context with nothing set is the safe default.
  }
  try {
    // Dynamic for the same reason as the `next/headers` import above —
    // `@/lib/reader` itself imports `next/headers` at its own top level.
    const { currentReader } = await import('@/lib/reader')
    const reader = await currentReader()
    if (reader) context.identityId = reader.id
  } catch {
    // A database blip identifying the reader must not fail the page they
    // came to read — same stance `lib/reader.ts#currentReader` itself takes.
  }
  return context
}

// ---------------------------------------------------------------------------
// Row-to-Article resolution — the only thing this file still does that
// `lib/recommendSql.ts` cannot (it has no Payload access, by design).
// ---------------------------------------------------------------------------

async function toOrderedArticles(rows: CandidateRow[]): Promise<Article[]> {
  if (rows.length === 0) return []
  const ids = rows.map((r) => r.id)
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { _status: { equals: 'published' }, id: { in: ids } },
    limit: ids.length,
    depth: 1,
  })
  const articles = await toArticles(docs)
  const rank = new Map(ids.map((id, i) => [id, i]))
  return articles.filter((a) => rank.has(a.id)).sort((a, b) => (rank.get(a.id) ?? 0) - (rank.get(b.id) ?? 0))
}

// ---------------------------------------------------------------------------
// The public contract
// ---------------------------------------------------------------------------

const READ_NEXT_LIMIT = 6
const COMPLEMENT_LIMIT_PER_RAIL = 6
const COMPLEMENT_POOL_SIZE = 60 // one batched query across up to 3 rails' worth of types

/**
 * Every recommendation rail for one article page, in the order the page
 * should render them. May be empty; the page renders no rail rather than an
 * empty one.
 */
export async function getArticleRails(article: Article, _reader: ReaderContext = {}, limit = READ_NEXT_LIMIT): Promise<ArticleRail[]> {
  const pool = cityPool()
  let relations: TypeRelations
  try {
    relations = await loadRelations(pool)
  } catch (error) {
    // engine.type_relations is the ONE table this whole guarantee depends
    // on. Unreachable means "cannot prove the exclusion holds" — the fail-
    // closed answer is no rail at all, never a rail computed as though
    // every candidate were a safe complement.
    console.error('[recommend] getArticleRails: could not load engine.type_relations:', error instanceof Error ? error.message : error)
    return []
  }

  const sections = complementSectionsFor(article.primaryType, relations)

  const [complementRows, readNextRowsRaw] = await Promise.all([
    sections.length > 0 ? resolveComplementCandidates(pool, article.id, sections, COMPLEMENT_POOL_SIZE) : Promise.resolve([]),
    resolveReadNextCandidates(pool, article.id, article.primaryType, relations, Math.max(limit * 4, 20)),
  ])

  // Complement rails are resolved FIRST logically (picked before Read Next
  // is finalised) even though both queries ran in parallel above — no
  // article may appear in more than one rail on the page (coordinator
  // review, second pass), and a "plan around it" match is the more
  // specific recommendation of the two.
  const grouped = groupComplementCandidatesBySection(complementRows, sections, COMPLEMENT_LIMIT_PER_RAIL, new Set())
  const usedIds = new Set<number>()
  for (const rows of grouped.values()) for (const r of rows) usedIds.add(r.id)

  const readNextRows = diversify(dedupeBySeries(readNextRowsRaw), limit, usedIds)

  const rails: ArticleRail[] = []
  for (const { section, label } of sections) {
    const rows = grouped.get(section) ?? []
    if (rows.length === 0) continue
    const items = await toOrderedArticles(rows)
    if (items.length === 0) continue
    rails.push({
      key: `plan-${section}`,
      kicker: label.kicker,
      title: label.title,
      items: items.map((a, i) => ({ ...a, rail: `plan-${section}`, position: i + 1 })),
    })
  }

  const readNextArticles = await toOrderedArticles(readNextRows)
  if (readNextArticles.length > 0) {
    rails.push({
      key: 'read-next',
      kicker: 'Keep reading',
      title: 'Read Next',
      items: readNextArticles.map((a, i) => ({ ...a, rail: 'read-next', position: i + 1 })),
    })
  }
  return rails
}

// ---------------------------------------------------------------------------
// getForYou — content-based personalization from what exists (WS1 #4)
// ---------------------------------------------------------------------------

/**
 * §10's signal weights, restricted to the beacon `kind`s that carry a
 * positive taste signal — `impression`/`thumbs_down` are deliberately
 * excluded here (a negative or neutral signal is not "build a taste vector
 * from this item", it is a down-weight §10 assigns to a DIFFERENT stage of
 * ranking this file does not implement).
 */
const INTERACTION_WEIGHT: Record<string, number> = {
  click: 0.3,
  dwell: 0.6,
  scroll: 0.8,
}
const SAVED_ITEM_WEIGHT = 1.0 // §10/§17: "saved / shared — 1.0", the strongest stated signal this file can read
const TASTE_WINDOW_DAYS = 180 // §10 long_term half-life scale — see that section
const MAX_TASTE_INPUTS = 20 // bounded, same reasoning as lib/stitch.ts's STITCH_MAX_ROWS

type WeightedEmbedding = { entityId: number; weight: number; vec: number[] }

function parseVectorText(text: string): number[] {
  return text
    .slice(1, -1)
    .split(',')
    .map((v) => Number(v))
}

/**
 * Reads recent interactions + (for a signed-in reader) `saved_items`,
 * joins each to its own embedding, and returns them weighted per §10 — the
 * raw ingredients `getForYou` averages into a taste vector. `identityId`
 * takes precedence: interactions get stitched to it on sign-in
 * (`lib/stitch.ts`), so a signed-in reader's `anonId` history is already
 * reachable through `user_id` and does not need a second, OR'd lookup here.
 */
async function fetchWeightedTasteInputs(reader: ReaderContext): Promise<WeightedEmbedding[]> {
  if (!reader.identityId && !reader.anonId) return []

  const whereReader = reader.identityId ? 'user_id = $1' : 'anon_id = $1::uuid'
  const readerParam = reader.identityId ?? reader.anonId

  const interactionsSql = `
    SELECT entity_id::int AS entity_id, kind,
           COALESCE(dwell_ms, 0) AS dwell_ms, COALESCE(scroll_pct, 0) AS scroll_pct
      FROM engine.interactions
     WHERE ${whereReader}
       AND entity_type = 'article'
       AND kind IN ('click', 'dwell', 'scroll')
       AND ts >= now() - ($2 || ' days')::interval
     ORDER BY ts DESC
     LIMIT $3
  `
  let interactionRows: { entity_id: number; kind: string; dwell_ms: number; scroll_pct: number }[] = []
  try {
    const result = await cityPool().query(interactionsSql, [readerParam, String(TASTE_WINDOW_DAYS), MAX_TASTE_INPUTS])
    interactionRows = result.rows
  } catch (error) {
    console.error('[recommend] getForYou: interactions query failed:', error instanceof Error ? error.message : error)
  }

  const weighted = new Map<number, number>()
  for (const row of interactionRows) {
    let weight = INTERACTION_WEIGHT[row.kind] ?? 0
    // §10: "dwell >= 30s" / "scroll >= 70%" are the qualifying thresholds,
    // not every dwell/scroll event — an unqualified one carries no weight.
    if (row.kind === 'dwell' && row.dwell_ms < 30_000) weight = 0
    if (row.kind === 'scroll' && row.scroll_pct < 70) weight = 0
    if (weight === 0) continue
    weighted.set(row.entity_id, Math.max(weighted.get(row.entity_id) ?? 0, weight))
  }

  // `saved_items` — signed-in only, `engine.saved_items` (READER-IDENTITY.md).
  if (reader.identityId) {
    const savedSql = `
      SELECT entity_id::int AS entity_id FROM engine.saved_items
       WHERE identity_id = $1::uuid AND entity_type = 'article'
       ORDER BY created_at DESC LIMIT $2
    `
    try {
      const result = await cityPool().query<{ entity_id: number }>(savedSql, [reader.identityId, MAX_TASTE_INPUTS])
      for (const row of result.rows) weighted.set(row.entity_id, SAVED_ITEM_WEIGHT)
    } catch (error) {
      console.error('[recommend] getForYou: saved_items query failed:', error instanceof Error ? error.message : error)
    }
  }

  if (weighted.size === 0) return []

  const ids = Array.from(weighted.keys())
  const embedSql = `
    SELECT entity_id::int AS entity_id, vec::text AS vec_text
      FROM engine.embeddings
     WHERE entity_type = 'article' AND model = $1 AND entity_id = ANY($2::text[])
  `
  try {
    const result = await cityPool().query<{ entity_id: number; vec_text: string }>(embedSql, [
      EMBEDDING_MODEL,
      ids.map(String),
    ])
    return result.rows.map((r) => ({
      entityId: r.entity_id,
      weight: weighted.get(r.entity_id) ?? 0,
      vec: parseVectorText(r.vec_text),
    }))
  } catch (error) {
    console.error('[recommend] getForYou: embeddings query failed:', error instanceof Error ? error.message : error)
    return []
  }
}

function weightedCentroid(inputs: WeightedEmbedding[]): number[] | null {
  if (inputs.length === 0) return null
  const dim = inputs[0].vec.length
  const sum = new Array(dim).fill(0)
  let totalWeight = 0
  for (const input of inputs) {
    for (let i = 0; i < dim; i++) sum[i] += input.vec[i] * input.weight
    totalWeight += input.weight
  }
  if (totalWeight === 0) return null
  return sum.map((v) => v / totalWeight)
}

const FOR_YOU_SQL = `
  SELECT a.id, a.primary_type::text AS primary_type, a.series_key
    FROM public.articles a
    JOIN engine.embeddings e ON e.entity_type = 'article' AND e.entity_id = a.id::text AND e.model = $1
   WHERE a._status = 'published'
     AND a.published_at IS NOT NULL AND a.published_at <= now()
     AND NOT (a.id = ANY($2::int[]))
     AND a.id NOT IN (
       SELECT entity_id::int FROM engine.quality_scores
        WHERE entity_type = 'article' AND score < $3
     )
   ORDER BY e.vec <=> $4::vector ASC
   LIMIT $5
`

/**
 * The home page's personal rail. `null` when there is nothing personal to
 * say yet (no history, no stated preferences, no saves) — the home page
 * then renders no "For you" band at all rather than relabelling recency as
 * taste (this file's own contract, unchanged from the stub).
 *
 * No competitor exclusion here by design: unlike `getArticleRails`, there is
 * no single subject venue this feed is "on the page of" — ARCHITECTURE
 * §8.A's rule is scoped to a venue STORY's own rail, and a home-page feed
 * mixing a reader's actual interests (which may well include several
 * competing restaurants they have read about) is a different surface with
 * a different rule (§8.C: "personalization never hard-filters").
 */
export async function getForYou(reader: ReaderContext = {}, limit = 6): Promise<ArticleRail | null> {
  const inputs = await fetchWeightedTasteInputs(reader)
  if (inputs.length === 0) return null // no signal -> never invent taste

  const centroid = weightedCentroid(inputs)
  if (!centroid) return null

  const alreadyRead = inputs.map((i) => i.entityId)
  const vectorLiteral = `[${centroid.join(',')}]`

  let rows: CandidateRow[]
  try {
    const result = await cityPool().query<CandidateRow>(FOR_YOU_SQL, [
      EMBEDDING_MODEL,
      alreadyRead,
      QUALITY_FLOOR,
      vectorLiteral,
      Math.max(limit * 4, 20),
    ])
    rows = result.rows
  } catch (error) {
    console.error('[recommend] getForYou: kNN query failed:', error instanceof Error ? error.message : error)
    return null
  }
  rows = dedupeBySeries(rows)
  if (rows.length === 0) return null

  const items = await toOrderedArticles(diversify(rows, limit))
  if (items.length === 0) return null

  return {
    key: 'for-you',
    kicker: 'For you',
    // Honest label (§10/§17: never invent taste, and describe it truthfully)
    // — this file cannot yet name the ONE article that drove the strongest
    // signal without another lookup, so it names the mechanism instead of a
    // specific title; a per-item "because you read X" would need
    // per-item provenance this centroid approach does not preserve.
    title: 'Because of what you read',
    items: items.map((a, i) => ({ ...a, rail: 'for-you', position: i + 1 })),
  }
}

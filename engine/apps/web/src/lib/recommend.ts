import 'server-only'

import pg from 'pg'

import { toArticles, type Article } from '@/lib/content'
import { cityPool, payloadClient } from '@/lib/payload'
import { excludedTypesFor, type TypeRelations } from '@/lib/competitorPolicy'
import { bucketFor, railKeyWithVariant } from '@/lib/experiments'
import { alphaFor, blendTaste, labelFor } from '@/lib/taste'
import {
  complementSectionsFor,
  dedupeBySeries,
  diversify,
  fetchCovisScoresFor,
  groupComplementCandidatesBySection,
  loadRelations,
  meetsReadersAlsoReadFloor,
  resolveComplementCandidates,
  resolveCovisitedCandidates,
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
 *
 * ## Freshness guarantee for `engine.hidden_rival_flags` (third pass)
 *
 * The precomputed table this file's competitor guard reads
 * (`recommendSql.ts`'s `NOT EXISTS (SELECT 1 FROM engine.hidden_rival_flags
 * ...)`) is kept fresh by THREE mechanisms, in decreasing order of how
 * fast they react:
 *
 *   1. Per-article recompute, hooked into the SAME domain-event stream the
 *      re-embed worker already consumes (`engine/apps/worker/app/
 *      consumer.py`): `article.published`/`.republished` recompute that
 *      one article's flags, `article.unpublished` removes them. This runs
 *      within the stream's own at-least-once delivery — in practice,
 *      seconds after a save, not a scheduled interval. There is no fixed
 *      "N seconds" SLA to quote: it is bounded by domain-event delivery
 *      latency (normally sub-second) plus one recompute query (~single-
 *      digit ms, see `now_filters.hidden_rival_recompute`), not a polling
 *      period.
 *   2. **No event exists for "place_mentions changed independent of the
 *      article being republished"** — `now_place_extraction` is an
 *      offline batch CLI, not triggered by any per-article domain event.
 *      A place-extraction run that changes an article's mentions without
 *      also emitting `article.published`/`.republished` is caught by (3)
 *      only, up to a night later.
 *   3. A nightly full recompute (`app/jobs.py`'s
 *      `recompute_hidden_rival_flags_job`, 03:55 UTC) as the safety net —
 *      diffs the full table against a fresh computation and logs a
 *      non-zero added/removed count as "the event path may have missed
 *      something," rather than assuming (1)/(2) are airtight.
 *
 * Stated plainly: a newly published story naming a competing venue is
 * excluded from rails within the same publish event's delivery, not
 * "eventually" — except for a place-mentions-only change with no event of
 * its own, which is fresh within one night.
 *
 * ## Stated preferences drive "For you" from the first visit (fourth pass)
 *
 * ARCHITECTURE §10: `α = n_meaningful / (n_meaningful + 20)`,
 * `taste = α·revealed + (1−α)·stated_seed`. `n_meaningful` starts at 0 for
 * every reader, so a reader who has just finished the sign-up picker
 * (`lib/preferences.ts`) and clicked nothing yet gets `taste = stated_seed`
 * outright — "For you" is personal on the FIRST post-sign-up page view, not
 * after 20 clicks accumulate. `loadStatedSeed` builds `stated_seed` from the
 * picked terms' OWN embeddings (`engine.embeddings` entity_type='term',
 * same model/space as articles), blended with the centroid of articles
 * actually carrying those terms where `entity_terms` coverage exists for
 * that facet. Today that is `type` (75–82%) and `location` (full); `topic`/
 * `audience`/`price_band` have zero tagged articles as of this pass (a
 * parallel WS5 effort is tagging them), so a picked topic or persona still
 * contributes its own term embedding to the seed, just not an article
 * centroid yet — degrading gracefully rather than silently dropping the
 * pick. Where facet coverage exists (`type`, `location`), picked terms also
 * get a small SOFT re-rank bonus (never a hard filter — §8.C) over the kNN
 * pass, so "I picked Wellness" nudges the order without excluding a great
 * match that happens to be `stay`.
 *
 * The label is honest about which side of the blend produced the rail:
 * "Because you like {terms}" when the stated side dominates (`α < 0.5`,
 * i.e. still fewer than 20 meaningful interactions), "Because of what you
 * read" once revealed behaviour has taken over. Never both, never a guess.
 *
 * `n_meaningful` is approximated here as the COUNT of distinct articles
 * that cleared a qualifying signal in the existing 180-day window
 * (`fetchWeightedTasteInputs`) — there is no persisted `user_profiles
 * .n_meaningful` counter written anywhere yet (out of scope for this pass,
 * flagged as a follow-up); this is the same number that formula needs, just
 * computed on read rather than maintained incrementally.
 *
 * ## Session intent (fourth pass)
 *
 * §5's `taste_vec_short`: the current session's reads (`engine.interactions`
 * by `anon_id`/`user_id`, last 30 minutes) form a short-lived centroid,
 * blended with `β = 0.6` when the session has 3+ qualifying interactions,
 * else `β = 0.2` — a reader three articles deep into "things to do in
 * Ubud" gets that intent weighted heavily; one article in gets a light
 * nudge. Blended into "For you" unconditionally, and into Read Next's
 * ORDER ONLY (never its candidate pool or exclusions — those stay exactly
 * what `resolveReadNextCandidates` already returns) behind the `read-next`
 * A/B experiment below, so its effect can be measured rather than assumed.
 *
 * ## Covisitation and "Readers also read" (fourth pass)
 *
 * `engine.covisitation` is real and now genuinely populated (worker cron
 * `recompute_covisitation_job`, `now_filters.covisitation_recompute`) —
 * previously wired to be read (`now_blender.covisitation`) but never
 * written. When rows exist for a subject, Read Next's order gets a second
 * small bonus (`fetchCovisScoresFor`) alongside session intent; separately,
 * a "Readers also read" rail appears ONLY when at least `MIN_READERS_ALSO_
 * READ` (3) competitor-clean covisited items clear the score floor —
 * otherwise it is hidden, never padded to hit the count (S2 honesty rule
 * applied to a rail's very existence).
 *
 * ## A/B testing (fourth pass)
 *
 * `lib/experiments.ts`: deterministic bucketing by `anon_id` hash, variants
 * as data (`ACTIVE_EXPERIMENTS`). The one experiment wired here is
 * `read-next` (`control` vs `session-intent`), because the beacon contract
 * is frozen and the variant has to ride inside the existing `rail` value —
 * `<rail>~<variant>`, built by `railKeyWithVariant`, only while that
 * experiment is active for that reader (no `anonId` at all: no suffix, no
 * bucketing, plain `read-next`). WS4's dashboard reads exactly this
 * convention.
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
// Stated preferences (`engine.identities.stated_prefs`) and session intent
// (`engine.interactions`, last ~30 minutes) — WS1, fourth pass, items 1/3.
// Both live in the PLATFORM database (readers, not city-scoped), the same
// pool shape `lib/reader.ts`/`lib/preferences.ts` already open one of.
// ---------------------------------------------------------------------------

let platformPool: pg.Pool | null = null

function platformDbPool(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  platformPool ??= new pg.Pool({ connectionString: url, max: 4, statement_timeout: 5_000 })
  return platformPool
}

function meanVector(vectors: number[][]): number[] | null {
  if (vectors.length === 0) return null
  const dim = vectors[0].length
  const sum = new Array(dim).fill(0)
  for (const v of vectors) for (let i = 0; i < dim; i++) sum[i] += v[i]
  return sum.map((v) => v / vectors.length)
}

export type StatedSeed = {
  /** `null` when the reader has no picks, or none resolve to a known term. */
  vector: number[] | null
  /** L1 `type` slugs picked as "interests" — the soft re-rank bonus's type side. */
  pickedTypes: string[]
  /** `location` TERM IDS (not slugs) picked as "areas" — `engine.terms`
   * lives only in the PLATFORM database; `engine.entity_terms` (the CITY
   * database) has no way to join back to it and resolve a slug, so the
   * area boost below joins on `term_id` directly using ids resolved HERE,
   * against the platform's vocabulary, once. */
  pickedAreaTermIds: string[]
  /** Human labels (type + topic picks) for the honest "Because you like…" label. */
  labels: string[]
}

const EMPTY_STATED_SEED: StatedSeed = { vector: null, pickedTypes: [], pickedAreaTermIds: [], labels: [] }

/**
 * `stated_seed` (ARCHITECTURE §10): the mean of the reader's picked terms'
 * OWN embeddings, blended with the centroid of articles that actually carry
 * those terms where `entity_terms` coverage exists for that facet (today:
 * `type`, `location` — see this file's header). A picked `topic`/`persona`/
 * `budget` still contributes its term embedding even with zero article
 * coverage, rather than being dropped.
 */
async function loadStatedSeed(identityId: string | undefined): Promise<StatedSeed> {
  if (!identityId) return EMPTY_STATED_SEED

  let raw: unknown
  try {
    const { rows } = await platformDbPool().query<{ stated_prefs: unknown }>(
      `SELECT stated_prefs FROM engine.identities WHERE id = $1::uuid`,
      [identityId],
    )
    raw = rows[0]?.stated_prefs
  } catch (error) {
    console.error('[recommend] loadStatedSeed: identities lookup failed:', error instanceof Error ? error.message : error)
    return EMPTY_STATED_SEED
  }
  if (!raw || typeof raw !== 'object') return EMPTY_STATED_SEED

  const prefs = raw as { interests?: unknown; topics?: unknown; areas?: unknown }
  const interestSlugs = Array.isArray(prefs.interests) ? prefs.interests.map(String) : []
  const topicSlugs = Array.isArray(prefs.topics) ? prefs.topics.map(String) : []
  const areaSlugs = Array.isArray(prefs.areas) ? prefs.areas.map(String) : []
  if (interestSlugs.length === 0 && topicSlugs.length === 0 && areaSlugs.length === 0) return EMPTY_STATED_SEED

  let termRows: { id: string; slug: string; label: string; facet_key: string }[]
  try {
    const result = await platformDbPool().query<{ id: string; slug: string; label: string; facet_key: string }>(
      `SELECT t.id::text AS id, t.slug, t.label, f.key AS facet_key
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
        WHERE (f.key = 'type' AND t.slug = ANY($1::text[]))
           OR (f.key = 'topic' AND t.slug = ANY($2::text[]))
           OR (f.key = 'location' AND t.slug = ANY($3::text[]))`,
      [interestSlugs, topicSlugs, areaSlugs],
    )
    termRows = result.rows
  } catch (error) {
    console.error('[recommend] loadStatedSeed: term lookup failed:', error instanceof Error ? error.message : error)
    return EMPTY_STATED_SEED
  }
  if (termRows.length === 0) return EMPTY_STATED_SEED

  const termIds = termRows.map((r) => r.id)
  const labels = termRows.filter((r) => r.facet_key === 'type' || r.facet_key === 'topic').map((r) => r.label)
  const pickedTypes = termRows.filter((r) => r.facet_key === 'type').map((r) => r.slug)
  const pickedAreaTermIds = termRows.filter((r) => r.facet_key === 'location').map((r) => r.id)

  // `engine.embeddings` — including entity_type='term' — lives in the CITY
  // database, not the platform one (verified directly: `now_platform` has
  // no `engine.embeddings` table at all; `now_bali`/`now_jakarta` each hold
  // 407 term rows in the same model/space as their own articles). Only
  // `engine.terms`/`engine.facets` (the vocabulary itself) are platform-
  // scoped, because a reader's picks are platform-scoped but the
  // embedding space is per-city content.
  let termVectors: number[][] = []
  try {
    const result = await cityPool().query<{ vec_text: string }>(
      `SELECT vec::text AS vec_text FROM engine.embeddings
        WHERE entity_type = 'term' AND model = $1 AND entity_id = ANY($2::text[])`,
      [EMBEDDING_MODEL, termIds],
    )
    termVectors = result.rows.map((r) => parseVectorText(r.vec_text))
  } catch (error) {
    console.error('[recommend] loadStatedSeed: term embeddings failed:', error instanceof Error ? error.message : error)
  }
  const termMean = meanVector(termVectors)
  if (!termMean) return { vector: null, pickedTypes, pickedAreaTermIds, labels }

  // The article-centroid half of the seed — only where `entity_terms`
  // coverage exists for the picked facets (today: interests/areas). A
  // picked topic with zero tagged articles simply contributes nothing here;
  // `termMean` above already carries it.
  let seedVector = termMean
  try {
    const { rows: articleIdRows } = await cityPool().query<{ entity_id: string }>(
      `SELECT DISTINCT entity_id FROM engine.entity_terms
        WHERE entity_type = 'article' AND term_id = ANY($1::uuid[]) LIMIT 200`,
      [termIds],
    )
    if (articleIdRows.length > 0) {
      const { rows: articleEmbedRows } = await cityPool().query<{ vec_text: string }>(
        `SELECT vec::text AS vec_text FROM engine.embeddings
          WHERE entity_type = 'article' AND model = $1 AND entity_id = ANY($2::text[])`,
        [EMBEDDING_MODEL, articleIdRows.map((r) => r.entity_id)],
      )
      const articleCentroid = meanVector(articleEmbedRows.map((r) => parseVectorText(r.vec_text)))
      if (articleCentroid) {
        const blended = meanVector([termMean, articleCentroid])
        if (blended) seedVector = blended
      }
    }
  } catch (error) {
    console.error('[recommend] loadStatedSeed: article-centroid half failed:', error instanceof Error ? error.message : error)
  }

  return { vector: seedVector, pickedTypes, pickedAreaTermIds, labels }
}

const SESSION_WINDOW_MINUTES = 30
const SESSION_INTENT_HEAVY_THRESHOLD = 3 // §5: beta = 0.6 at 3+ qualifying interactions this session
const BETA_HEAVY = 0.6
const BETA_LIGHT = 0.2

type SessionIntent = { centroid: number[] | null; count: number }

/** `taste_vec_short` (§5): the SAME qualifying-signal rule
 * (`INTERACTION_WEIGHT`, defined below) restricted to the last 30 minutes —
 * "what is this reader doing RIGHT NOW", not the 180-day taste profile. */
async function fetchShortTermCentroid(reader: ReaderContext): Promise<SessionIntent> {
  if (!reader.identityId && !reader.anonId) return { centroid: null, count: 0 }
  const whereReader = reader.identityId ? 'user_id = $1' : 'anon_id = $1::uuid'
  const readerParam = reader.identityId ?? reader.anonId
  let rows: { entity_id: number; kind: string; dwell_ms: number; scroll_pct: number }[] = []
  try {
    const result = await cityPool().query(
      `SELECT entity_id::int AS entity_id, kind,
              COALESCE(dwell_ms, 0) AS dwell_ms, COALESCE(scroll_pct, 0) AS scroll_pct
         FROM engine.interactions
        WHERE ${whereReader}
          AND entity_type = 'article'
          AND kind IN ('click', 'dwell', 'scroll')
          AND ts >= now() - ($2 || ' minutes')::interval
        ORDER BY ts DESC
        LIMIT 20`,
      [readerParam, String(SESSION_WINDOW_MINUTES)],
    )
    rows = result.rows
  } catch (error) {
    console.error('[recommend] fetchShortTermCentroid: interactions query failed:', error instanceof Error ? error.message : error)
    return { centroid: null, count: 0 }
  }

  const weighted = new Map<number, number>()
  for (const row of rows) {
    let weight = INTERACTION_WEIGHT[row.kind] ?? 0
    if (row.kind === 'dwell' && row.dwell_ms < 30_000) weight = 0
    if (row.kind === 'scroll' && row.scroll_pct < 70) weight = 0
    if (weight === 0) continue
    weighted.set(row.entity_id, Math.max(weighted.get(row.entity_id) ?? 0, weight))
  }
  if (weighted.size === 0) return { centroid: null, count: 0 }

  const ids = Array.from(weighted.keys())
  try {
    const result = await cityPool().query<{ entity_id: number; vec_text: string }>(
      `SELECT entity_id::int AS entity_id, vec::text AS vec_text
         FROM engine.embeddings
        WHERE entity_type = 'article' AND model = $1 AND entity_id = ANY($2::text[])`,
      [EMBEDDING_MODEL, ids.map(String)],
    )
    const vectors = result.rows.map((r) => parseVectorText(r.vec_text))
    return { centroid: meanVector(vectors), count: weighted.size }
  } catch (error) {
    console.error('[recommend] fetchShortTermCentroid: embeddings query failed:', error instanceof Error ? error.message : error)
    return { centroid: null, count: 0 }
  }
}

/** §5's blend: heavier weight once the session has proven itself with 3+
 * qualifying reads this visit, lighter otherwise — never zero, a single
 * click already says something about right-now intent. */
function blendSessionIntent(longTerm: number[], session: SessionIntent): number[] {
  if (!session.centroid) return longTerm
  const beta = session.count >= SESSION_INTENT_HEAVY_THRESHOLD ? BETA_HEAVY : BETA_LIGHT
  return longTerm.map((v, i) => beta * session.centroid![i] + (1 - beta) * v)
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
export async function getArticleRails(article: Article, reader: ReaderContext = {}, limit = READ_NEXT_LIMIT): Promise<ArticleRail[]> {
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
  const excludedTypes = [...excludedTypesFor(relations, article.primaryType)]

  // `read-next` A/B (item 5): decided once, up front, so the SAME variant
  // governs both the re-rank below and the rail key every item on the page
  // carries — a reader can never see `session-intent`'s order under a
  // `control`-suffixed rail key or vice versa.
  const variant = bucketFor('read-next', reader.anonId)

  const [complementRows, readNextRowsRaw, session] = await Promise.all([
    sections.length > 0
      ? resolveComplementCandidates(pool, article.id, sections, COMPLEMENT_POOL_SIZE, excludedTypes)
      : Promise.resolve([]),
    // Pool size and exclusions are unchanged by the experiment — only the
    // ORDER moves, and only for readers bucketed into `session-intent`
    // (item 3: "Read Next's candidate pool and exclusions are unchanged;
    // only the order moves").
    resolveReadNextCandidates(pool, article.id, article.primaryType, relations, Math.max(limit * 4, 20)),
    variant === 'session-intent' ? fetchShortTermCentroid(reader) : Promise.resolve({ centroid: null, count: 0 }),
  ])

  // Complement rails are resolved FIRST logically (picked before Read Next
  // is finalised) even though both queries ran in parallel above — no
  // article may appear in more than one rail on the page (coordinator
  // review, second pass), and a "plan around it" match is the more
  // specific recommendation of the two.
  const grouped = groupComplementCandidatesBySection(complementRows, sections, COMPLEMENT_LIMIT_PER_RAIL, new Set())
  const usedIds = new Set<number>()
  for (const rows of grouped.values()) for (const r of rows) usedIds.add(r.id)

  let readNextPool = dedupeBySeries(readNextRowsRaw)

  // Covisitation bonus (item 4): unconditional, not gated on the A/B
  // experiment — this is a straight quality improvement when the data
  // exists, not the thing being tested. Session-intent re-rank (item 3) IS
  // the thing being tested, so it only applies for that variant.
  const candidateIds = readNextPool.map((r) => r.id)
  const covisScores = await fetchCovisScoresFor(pool, article.id, candidateIds)
  if (covisScores.size > 0 || session.centroid) {
    const withEmbeddings = session.centroid
      ? await fetchEmbeddingsFor(pool, candidateIds)
      : new Map<number, number[]>()
    const scored = readNextPool.map((row, rank) => {
      // A rank-based proxy for "how good was the subject-similarity order"
      // — the SQL already ordered by it and this file has no raw distance
      // for these rows (unlike getForYou's kNN, Read Next's SELECT never
      // needed one before). Small, monotonic, and never overturns a large
      // covis/session bonus for a candidate ranked far down the pool.
      let score = 1 - rank / Math.max(readNextPool.length, 1)
      score += (covisScores.get(row.id) ?? 0) * 0.5
      if (session.centroid) {
        const vec = withEmbeddings.get(row.id)
        if (vec) score += cosineSimilarity(vec, session.centroid) * 0.3
      }
      return { row, score }
    })
    scored.sort((a, b) => b.score - a.score)
    readNextPool = scored.map((s) => s.row)
  }

  const readNextRows = diversify(readNextPool, limit, usedIds)
  for (const r of readNextRows) usedIds.add(r.id)

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
    const railKey = railKeyWithVariant('read-next', variant)
    rails.push({
      key: railKey,
      kicker: 'Keep reading',
      title: 'Read Next',
      items: readNextArticles.map((a, i) => ({ ...a, rail: railKey, position: i + 1 })),
    })
  }

  // "Readers also read" (item 4) — hidden, not padded, below the floor.
  const covisitedRows = dedupeBySeries(
    await resolveCovisitedCandidates(pool, article.id, excludedTypes, Math.max(limit * 3, 12)),
  ).filter((r) => !usedIds.has(r.id))
  if (meetsReadersAlsoReadFloor(covisitedRows.length)) {
    const items = await toOrderedArticles(diversify(covisitedRows, limit))
    if (meetsReadersAlsoReadFloor(items.length)) {
      rails.push({
        key: 'readers-also-read',
        kicker: 'Readers also read',
        title: 'Readers Also Read',
        items: items.map((a, i) => ({ ...a, rail: 'readers-also-read', position: i + 1 })),
      })
    }
  }

  return rails
}

function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  if (normA === 0 || normB === 0) return 0
  return dot / (Math.sqrt(normA) * Math.sqrt(normB))
}

async function fetchEmbeddingsFor(pool: ReturnType<typeof cityPool>, ids: number[]): Promise<Map<number, number[]>> {
  const out = new Map<number, number[]>()
  if (ids.length === 0) return out
  try {
    const result = await pool.query<{ entity_id: number; vec_text: string }>(
      `SELECT entity_id::int AS entity_id, vec::text AS vec_text
         FROM engine.embeddings
        WHERE entity_type = 'article' AND model = $1 AND entity_id = ANY($2::text[])`,
      [EMBEDDING_MODEL, ids.map(String)],
    )
    for (const row of result.rows) out.set(row.entity_id, parseVectorText(row.vec_text))
  } catch (error) {
    console.error('[recommend] fetchEmbeddingsFor: query failed:', error instanceof Error ? error.message : error)
  }
  return out
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
  SELECT a.id, a.primary_type::text AS primary_type, a.series_key,
         (e.vec <=> $4::vector) AS distance
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

type ForYouCandidateRow = CandidateRow & { distance: number }

// Soft re-rank bonus (§8.C: "personalization never hard-filters") applied
// AFTER the kNN pass, never as a WHERE predicate — a picked facet nudges the
// order, it never removes an otherwise-great match that happens not to
// carry it. Cosine distance is in [0, 2]; these are small relative to that.
const TYPE_BOOST = 0.05
const AREA_BOOST = 0.05

// `alphaFor`/`blendTaste`/`labelFor` now live in `lib/taste.ts` (no
// `server-only`, directly unit-testable) — re-exported here so existing
// callers of `@/lib/recommend` keep working unchanged.
export { alphaFor, blendTaste, labelFor }

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
  const [inputs, statedSeed] = await Promise.all([
    fetchWeightedTasteInputs(reader),
    loadStatedSeed(reader.identityId),
  ])

  const revealedCentroid = weightedCentroid(inputs)
  // n_meaningful: see this file's header — approximated as the count of
  // distinct articles that cleared a qualifying signal in the 180-day
  // window, there being no persisted counter to read instead.
  const blended = blendTaste(revealedCentroid, statedSeed.vector, inputs.length)
  if (!blended) return null // no revealed signal AND no stated picks -> never invent taste

  const session = await fetchShortTermCentroid(reader)
  const taste = blendSessionIntent(blended.vector, session)

  const alreadyRead = inputs.map((i) => i.entityId)
  const vectorLiteral = `[${taste.join(',')}]`
  // Wider pool than the final `limit` so the soft facet boost below (§8.C:
  // never a hard filter, always a re-rank) has room to move a matching item
  // up from outside the top slice rather than only reshuffling within it.
  const poolLimit = Math.max(limit * 8, 40)

  let rows: ForYouCandidateRow[]
  try {
    const result = await cityPool().query<ForYouCandidateRow>(FOR_YOU_SQL, [
      EMBEDDING_MODEL,
      alreadyRead,
      QUALITY_FLOOR,
      vectorLiteral,
      poolLimit,
    ])
    rows = result.rows
  } catch (error) {
    console.error('[recommend] getForYou: kNN query failed:', error instanceof Error ? error.message : error)
    return null
  }
  rows = dedupeBySeries(rows) as ForYouCandidateRow[]
  if (rows.length === 0) return null

  // Soft facet boost (§8.C): only meaningful where `entity_terms` coverage
  // exists for the picked facet — today `type` (on the row already) and
  // `location` (needs a lookup against the picked area term ids). No join
  // to `engine.terms` here: that table lives only in the PLATFORM
  // database (verified directly — the city databases have no such table),
  // so `loadStatedSeed` already resolved slugs to term ids THERE;
  // `entity_terms.term_id` is compared directly against those ids.
  let areaMatchIds = new Set<number>()
  if (statedSeed.pickedAreaTermIds.length > 0) {
    try {
      const { rows: areaRows } = await cityPool().query<{ entity_id: string }>(
        `SELECT DISTINCT entity_id
           FROM engine.entity_terms
          WHERE entity_type = 'article'
            AND entity_id = ANY($1::text[])
            AND term_id = ANY($2::uuid[])`,
        [rows.map((r) => String(r.id)), statedSeed.pickedAreaTermIds],
      )
      areaMatchIds = new Set(areaRows.map((r) => Number(r.entity_id)))
    } catch (error) {
      console.error('[recommend] getForYou: area boost lookup failed:', error instanceof Error ? error.message : error)
    }
  }

  const adjusted = rows.map((row) => {
    let bonus = 0
    if (row.primary_type && statedSeed.pickedTypes.includes(row.primary_type)) bonus += TYPE_BOOST
    if (areaMatchIds.has(row.id)) bonus += AREA_BOOST
    return { ...row, distance: row.distance - bonus }
  })
  adjusted.sort((a, b) => a.distance - b.distance)

  const items = await toOrderedArticles(diversify(adjusted, limit))
  if (items.length === 0) return null

  return {
    key: 'for-you',
    kicker: 'For you',
    title: labelFor(blended.dominant, statedSeed.labels),
    items: items.map((a, i) => ({ ...a, rail: 'for-you', position: i + 1 })),
  }
}

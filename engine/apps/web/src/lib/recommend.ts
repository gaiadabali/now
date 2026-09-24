import 'server-only'

import { toArticles, type Article } from '@/lib/content'
import { cityPool, payloadClient, sectionForType } from '@/lib/payload'
import { excludedTypesFor, relationsFromRows, type TypeRelations } from '@/lib/competitorPolicy'
import { hiddenRivalPatternForSubject } from '@/lib/hiddenRival'

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
 * directly serve this file's "plan around it" contract ("stories of the
 * complement types") without an extra place->article resolution step. Given
 * that gap, this iteration computes BOTH rails directly against `engine.*`
 * in this process, rather than calling the HTTP API — a deliberate,
 * DOCUMENTED exception to `lib/payload.ts`'s "a page may never query
 * Postgres directly" rule, made specifically because:
 *
 *   1. the article page must render a real rail even when engine-api is
 *      unreachable or unconfigured (this ticket's own requirement), and
 *      this codebase has no evidence `ENGINE_API_URL` is wired up for a
 *      rails call anywhere yet (only `/search` and the beacon use it);
 *   2. the ONE thing that must not drift between the two possible
 *      computation sites is the competitor POLICY, not the ranking — so
 *      `lib/competitorPolicy.ts` + `lib/hiddenRival.ts` are written as
 *      thin, independently-tested ports of the Python engine's own
 *      `now_filters.type_relations` / `now_filters.hidden_rival`, sharing
 *      ONE conformance-vector file both suites assert against
 *      (`engine/packages/taxonomy/seed/competitor_conformance.json`).
 *
 * Ranking may legitimately differ between this path and the engine-api
 * path (different candidate pools, no MMR/blend weights, no personalised
 * re-rank) — the exclusion policy may not, and is asserted identically on
 * both sides. Wiring an `ENGINE_API_URL` call as the PREFERRED path, with
 * this implementation kept as the graceful-degradation fallback, is the
 * natural next step and is flagged in the ticket report for the owner/
 * architect rather than attempted here without a way to verify the live
 * endpoint from this environment.
 *
 * Budget: ARCHITECTURE §7 says article-page rail work should cost
 * p95 <= 150ms server time, warm. Both queries below are single
 * round trips with every selective predicate (status, type, quality,
 * hidden-rival) pushed into SQL ahead of the vector operation, mirroring
 * `now_filters`' own Sec.8.G ordering rule.
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
    // Next's server runtime. A static import would fail to even LOAD this
    // module (and every function in it, `getArticleRails` included) outside
    // that runtime. Deferring the import to here, where it is actually
    // used, keeps the rest of the module plain-Node-loadable — this file
    // also imports `server-only`, which itself only resolves under Next's
    // `react-server` condition, so `scripts/verify-competitor-policy.mjs`
    // (WS1 deliverable #5) keeps its OWN literal copy of this file's SQL
    // rather than importing this module at all — see that script's header
    // comment for why.
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
// engine.type_relations — the commercial policy, read once per rail build.
// ---------------------------------------------------------------------------

const RELATIONS_SQL = `SELECT type, exclude_same, complements, competes_with FROM engine.type_relations`

async function loadRelations(): Promise<TypeRelations> {
  const { rows } = await cityPool().query<{
    type: string
    exclude_same: boolean
    complements: string[] | null
    competes_with: string[] | null
  }>(RELATIONS_SQL)
  return relationsFromRows(rows)
}

const EMBEDDING_MODEL = 'BAAI/bge-small-en-v1.5'
// ARCHITECTURE.md §8.A "Quality floor" / now_quality.scoring.QUALITY_FLOOR —
// kept as the same literal the Python engine uses (see that module's
// docstring for the derivation); duplicated here rather than imported
// because this is a TypeScript process with no access to the Python
// package, exactly the same constraint `now_filters` itself would face in
// reverse.
const QUALITY_FLOOR = 0.35

const MAX_PER_SECTION = 2 // Sec.8.D diversity cap, "max 2 per format" analogue applied to section here

// ---------------------------------------------------------------------------
// Read Next — semantic similarity (Row 3's job), computed directly.
// ---------------------------------------------------------------------------

export type CandidateRow = {
  id: number
  primary_type: string | null
  series_key: string | null
}

const READ_NEXT_SQL = `
  WITH subj AS (
    SELECT vec FROM engine.embeddings
     WHERE entity_type = 'article' AND entity_id = $1::text AND model = $2
  )
  SELECT a.id, a.primary_type::text AS primary_type, a.series_key
    FROM public.articles a
    JOIN engine.embeddings e ON e.entity_type = 'article' AND e.entity_id = a.id::text AND e.model = $2
   CROSS JOIN subj
   WHERE a.id != $1::int
     AND a._status = 'published'
     AND a.published_at IS NOT NULL AND a.published_at <= now()
     -- Competitor exclusion (ARCHITECTURE §8.A): empty excluded-array means
     -- "this subject excludes nothing" (editorial/do/event, or none at all),
     -- in which case NO predicate is applied, including for NULL
     -- primary_type rows — matching now_filters.hard's own "if excluded:"
     -- guard exactly, not an accidental relaxation.
     AND (
       cardinality($3::text[]) = 0
       OR (a.primary_type IS NOT NULL AND a.primary_type::text != ALL($3::text[]))
     )
     AND a.id NOT IN (
       SELECT entity_id::int FROM engine.quality_scores
        WHERE entity_type = 'article' AND score < $4
     )
     AND (
       $5::text IS NULL OR NOT EXISTS (
         SELECT 1 FROM public.place_mentions pm
           JOIN public.places pl ON pl.id = pm.place_id
          WHERE pm.article_id = a.id AND pm.role = 'featured' AND pl.name ~* $5
       )
     )
   ORDER BY e.vec <=> subj.vec ASC
   LIMIT $6
`

/** Greedy diversification: walk the similarity-ordered pool and cap how
 * many of one section survive — a simplified stand-in for `now_blender
 * .mmr`'s real MMR pass (no embedding pairwise-similarity comparison
 * here), documented as such rather than silently claiming the same
 * guarantee. Series dedup happens earlier, in `dedupeBySeries` — this
 * function only ever sees already-deduped candidates. */
function diversify(pool: Article[], limit: number): Article[] {
  const picked: Article[] = []
  const perSection = new Map<string, number>()
  for (const article of pool) {
    if (picked.length >= limit) break
    const section = sectionForType(article.primaryType) ?? 'unclassified'
    const count = perSection.get(section) ?? 0
    if (count >= MAX_PER_SECTION) continue
    picked.push(article)
    perSection.set(section, count + 1)
  }
  return picked
}

/**
 * The pure-SQL half of Read Next: candidate (id, primary_type, series_key)
 * rows, competitor-policy- and hidden-rival-filtered, ordered by semantic
 * similarity — no Payload/Local API involved. Exported so a test/verify
 * harness could assert the policy directly against this function without
 * a Payload round trip. `scripts/verify-competitor-policy.mjs` (WS1
 * deliverable #5) does NOT import it, though — this file's own top-level
 * `server-only` import throws outside Next's `react-server` condition
 * (including under `payload run`, which the CMS-config import chain
 * `payloadClient()` pulls in would otherwise need), so that script keeps a
 * literal, commented copy of `READ_NEXT_SQL` instead. If this query
 * changes, that script's copy must change with it.
 */
export async function resolveReadNextCandidates(
  articleId: number,
  subjectPrimaryType: string | null,
  relations: TypeRelations,
  limit: number,
): Promise<CandidateRow[]> {
  const excluded = Array.from(excludedTypesFor(relations, subjectPrimaryType))
  const hiddenRivalPattern = hiddenRivalPatternForSubject(subjectPrimaryType, relations)
  try {
    const result = await cityPool().query<CandidateRow>(READ_NEXT_SQL, [
      articleId,
      EMBEDDING_MODEL,
      excluded,
      QUALITY_FLOOR,
      hiddenRivalPattern,
      limit,
    ])
    return result.rows
  } catch (error) {
    // The rail is a nicety; the article is not. A missing partition, an
    // embeddings backfill not yet run for this article, or the city pool
    // being cold must not 500 the page under it — same stance
    // `lib/content.ts#getMostRead` already takes for its own direct query.
    console.error('[recommend] getArticleRails: Read Next query failed:', error instanceof Error ? error.message : error)
    return []
  }
}

/** Series dedup (Sec.8.A "one per series_key") — applied HERE, at the
 * CandidateRow level, because `series_key` does not survive the Payload
 * round trip (`lib/content.ts#Article` carries no such field; it is
 * display data the view model never needed before this file existed).
 * Rows arrive already ordered by semantic similarity, so keeping the
 * FIRST occurrence per key keeps the best-ranked row in each group —
 * same outcome as `now_filters.hard`'s `DISTINCT ON` for the SQL-side
 * ladder, applied here in application code instead. */
function dedupeBySeries(rows: CandidateRow[]): CandidateRow[] {
  const seen = new Set<string>()
  const out: CandidateRow[] = []
  for (const row of rows) {
    const key = row.series_key ?? `noseries:${row.id}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(row)
  }
  return out
}

async function fetchReadNext(article: Article, relations: TypeRelations, limit: number): Promise<Article[]> {
  const pool = Math.max(limit * 4, 20) // a wider pool for `diversify` to choose from
  const rows = dedupeBySeries(await resolveReadNextCandidates(article.id, article.primaryType, relations, pool))
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
  const bySemanticRank = new Map(ids.map((id, i) => [id, i]))
  const ordered = articles
    .filter((a) => bySemanticRank.has(a.id))
    .sort((a, b) => (bySemanticRank.get(a.id) ?? 0) - (bySemanticRank.get(b.id) ?? 0))

  return diversify(ordered, limit)
}

// ---------------------------------------------------------------------------
// "Plan around it" — Row 1's job (complementary types), computed directly.
// ---------------------------------------------------------------------------

/** One rail per SECTION (not per raw L1 type) — `eat`/`drink` already share
 * the `dining` section (`lib/payload.ts#TYPE_TO_SECTION`), and now that
 * they are one competitive class (migration 0008) they should read as one
 * "where to eat and drink" rail, not two near-duplicate ones. */
const SECTION_RAIL_LABELS: Record<string, { kicker: string; title: string }> = {
  stay: { kicker: 'Plan around it', title: 'Where to Stay' },
  dining: { kicker: 'Plan around it', title: 'Where to Eat & Drink' },
  wellness: { kicker: 'Plan around it', title: 'Where to Unwind' },
  'things-to-do': { kicker: 'Plan around it', title: 'Things to Do Nearby' },
  events: { kicker: 'Plan around it', title: "What's On" },
}

/** Display order for the rails this produces — a UI decision, not a policy
 * one: WHICH sections are eligible is driven entirely by the subject's own
 * `complements` (real data), this only orders how they are presented. */
const SECTION_DISPLAY_ORDER = ['stay', 'dining', 'wellness', 'things-to-do', 'events']

const COMPLEMENT_SQL = `
  WITH subj_place AS (
    SELECT pl.area_term
      FROM public.place_mentions pm
      JOIN public.places pl ON pl.id = pm.place_id
     WHERE pm.article_id = $1::int
     ORDER BY CASE pm.role WHEN 'featured' THEN 0 WHEN 'reviewed' THEN 1 ELSE 2 END, pm.id
     LIMIT 1
  )
  SELECT a.id, a.primary_type::text AS primary_type, a.series_key,
         EXISTS (
           SELECT 1 FROM public.place_mentions pm2
             JOIN public.places pl2 ON pl2.id = pm2.place_id, subj_place sp
            WHERE pm2.article_id = a.id AND sp.area_term IS NOT NULL AND pl2.area_term = sp.area_term
         ) AS same_area
    FROM public.articles a
   WHERE a.id != $1::int
     AND a._status = 'published'
     AND a.published_at IS NOT NULL AND a.published_at <= now()
     AND a.primary_type::text = ANY($2::text[])
     AND a.id NOT IN (
       SELECT entity_id::int FROM engine.quality_scores
        WHERE entity_type = 'article' AND score < $3
     )
     AND (
       $4::text IS NULL OR NOT EXISTS (
         SELECT 1 FROM public.place_mentions pm
           JOIN public.places pl ON pl.id = pm.place_id
          WHERE pm.article_id = a.id AND pm.role = 'featured' AND pl.name ~* $4
       )
     )
   ORDER BY same_area DESC, a.published_at DESC
   LIMIT $5
`

/** The pure-SQL half of a complement rail — see `resolveReadNextCandidates`
 * above for why this is exported and Payload-free. `types` here are
 * whatever the CALLER already validated against `relations[subjectType]
 * .complements` (`fetchComplementRails` below); this function trusts them,
 * same division of responsibility as `now_filters.row1_complementary`
 * trusting its own caller's `complements` lookup. */
export async function resolveComplementCandidates(
  articleId: number,
  types: string[],
  hiddenRivalPattern: string | null,
  limit: number,
): Promise<CandidateRow[]> {
  try {
    const result = await cityPool().query<CandidateRow>(COMPLEMENT_SQL, [articleId, types, QUALITY_FLOOR, hiddenRivalPattern, limit])
    return result.rows
  } catch (error) {
    console.error('[recommend] getArticleRails: complement query failed:', error instanceof Error ? error.message : error)
    return []
  }
}

async function fetchComplementRail(
  article: Article,
  types: string[],
  hiddenRivalPattern: string | null,
  limit: number,
): Promise<Article[]> {
  const rows = await resolveComplementCandidates(article.id, types, hiddenRivalPattern, limit)
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

/**
 * Groups a venue subject's `complements` by SECTION, in
 * `SECTION_DISPLAY_ORDER`. `[]` for a non-venue subject (`relations[type]
 * .excludeSame` false, or an unclassified subject) — "plan around it" is
 * specifically a venue-story feature (docs/EDITION-2-PLAN.md §1's own
 * framing: "a hotel story gets where to eat... a restaurant story gets
 * where to stay..."). Exported (pure, no I/O) so a test could exercise the
 * exact section/type grouping `getArticleRails` uses. `scripts/verify-
 * competitor-policy.mjs` keeps its OWN copy of this logic instead — same
 * `server-only` import-chain reason as `resolveReadNextCandidates` above —
 * so this function and that script's `complementSectionsFor` must be kept
 * in step by hand if the section mapping ever changes.
 */
export function complementSectionsFor(
  subjectType: string | null,
  relations: TypeRelations,
): { section: string; types: string[]; label: { kicker: string; title: string } }[] {
  if (!subjectType) return []
  const relation = relations[subjectType]
  if (!relation || !relation.excludeSame) return []

  const bySection = new Map<string, string[]>()
  for (const complementType of relation.complements) {
    const section = sectionForType(complementType)
    if (!section) continue
    const list = bySection.get(section) ?? []
    list.push(complementType)
    bySection.set(section, list)
  }

  const out: { section: string; types: string[]; label: { kicker: string; title: string } }[] = []
  for (const section of SECTION_DISPLAY_ORDER) {
    const types = bySection.get(section)
    const label = SECTION_RAIL_LABELS[section]
    if (!types || types.length === 0 || !label) continue
    out.push({ section, types, label })
  }
  return out
}

async function fetchComplementRails(
  article: Article,
  relations: TypeRelations,
  limitPerRail: number,
): Promise<ArticleRail[]> {
  const sections = complementSectionsFor(article.primaryType, relations)
  if (sections.length === 0) return []
  const hiddenRivalPattern = hiddenRivalPatternForSubject(article.primaryType, relations)

  const rails: ArticleRail[] = []
  for (const { section, types, label } of sections) {
    const items = await fetchComplementRail(article, types, hiddenRivalPattern, limitPerRail)
    if (items.length === 0) continue
    rails.push({
      key: `plan-${section}`,
      kicker: label.kicker,
      title: label.title,
      items: items.map((a, i) => ({ ...a, rail: `plan-${section}`, position: i + 1 })),
    })
  }
  return rails
}

// ---------------------------------------------------------------------------
// The public contract
// ---------------------------------------------------------------------------

/**
 * Every recommendation rail for one article page, in the order the page
 * should render them. May be empty; the page renders no rail rather than an
 * empty one.
 */
export async function getArticleRails(article: Article, _reader: ReaderContext = {}, limit = 6): Promise<ArticleRail[]> {
  let relations: TypeRelations
  try {
    relations = await loadRelations()
  } catch (error) {
    // engine.type_relations is the ONE table this whole guarantee depends
    // on. Unreachable means "cannot prove the exclusion holds" — the fail-
    // closed answer is no rail at all, never a rail computed as though
    // every candidate were a safe complement.
    console.error('[recommend] getArticleRails: could not load engine.type_relations:', error instanceof Error ? error.message : error)
    return []
  }

  const [readNext, complementRails] = await Promise.all([
    fetchReadNext(article, relations, limit),
    fetchComplementRails(article, relations, Math.min(limit, 4)),
  ])

  const rails: ArticleRail[] = [...complementRails]
  if (readNext.length > 0) {
    rails.push({
      key: 'read-next',
      kicker: 'Keep reading',
      title: 'Read Next',
      items: readNext.map((a, i) => ({ ...a, rail: 'read-next', position: i + 1 })),
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
  const ordered = articles.filter((a) => rank.has(a.id)).sort((a, b) => (rank.get(a.id) ?? 0) - (rank.get(b.id) ?? 0))
  const items = diversify(ordered, limit)
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

import 'server-only'

import pg from 'pg'

import { cityPool } from '@/lib/payload'

/**
 * What the engine decided about an article, and how sure it was.
 *
 * The classifier's actual output is `engine.entity_terms` in the CITY
 * database — `(entity_type, entity_id, term_id, weight, source, confidence)`.
 * None of it appears on Payload's edit form, because Payload owns `public`
 * and has never been allowed to look at `engine` (ARCHITECTURE.md §1
 * principle 2). So the surface an editor reaches by clicking an article shows
 * twelve stored columns and not one of the twelve is the decision under
 * review. This module is the read side of fixing that.
 *
 * THE STRUCTURAL PROBLEM, AND WHY THERE IS NO SQL JOIN ANYWHERE BELOW.
 * `entity_terms` says term `f02c963a-…` was assigned with confidence 0.40.
 * What that term MEANS — its label, its slug, which of the eleven facets it
 * belongs to — lives in `now_platform.engine.terms` / `engine.facets`, a
 * different database on the same server. Postgres will not join across
 * databases, and neither will any amount of wishing. The join happens in
 * JavaScript, below, over two parameterised SELECTs.
 *
 * `packages/cms/src/lib/vocabulary.ts` solved the same split already and this
 * follows its shape — one read-only connection to the platform DB, SELECT
 * only, never a write — but deliberately NOT its caching. Vocabulary caches
 * the whole taxonomy once at CMS boot because Payload needs a static
 * `options` array baked into a field config before `buildConfig` runs. A
 * report has the opposite requirement: its most alarming row is "this
 * term_id resolves to nothing in the vocabulary", and under a boot-time cache
 * that row would appear for any term seeded since the last restart. An
 * integrity warning that fires on process uptime rather than on the data is
 * worse than no warning. So this queries live, per request, for the handful
 * of term ids one article actually carries.
 *
 * WHAT SURPRISED ME, MEASURED ON BALI 2026-09-16 AND WORTH KNOWING BEFORE
 * READING THE UI CODE:
 *   - `entity_terms` has no facet column. A row's facet is knowable ONLY by
 *     resolving its term in the other database. So an unresolvable term_id is
 *     not merely missing a label — it cannot be attributed to any facet at
 *     all, and the report has to show it as an orphan rather than quietly
 *     drop it. (Zero orphans in Bali today: 122 distinct term ids in use, all
 *     407 platform terms resolve. The handling exists because "today" is the
 *     only word doing work in that sentence.)
 *   - The gate does not cut across facets evenly. Every one of Bali's 3,630
 *     `type` and 3,109 `format` assignments is below 0.85; not one of its
 *     7,577 `location` or 1,488 `subtype` assignments is. So "6,739 below the
 *     gate" is not a diffuse quality problem — it is precisely the two facets
 *     §8.A's competitor exclusion depends on.
 *
 * Read-only, all of it. This app must never write (docs/ui-data-layer.md);
 * the one write this feature makes goes through Payload's own Local API and
 * lives in the page's server action, not here.
 */

/**
 * ARCHITECTURE.md §6's last pipeline step: `review: confidence < 0.85 →
 * human queue`. Strictly less-than — a proposal AT 0.85 clears. Duplicated
 * from `ClassificationReviews.ts`'s `confidenceBand` hook rather than
 * imported because that value is a Payload field hook's private business and
 * exporting it would make this module depend on the CMS package's internals
 * for a number ARCHITECTURE.md already fixes.
 */
export const CONFIDENCE_GATE = 0.85

/** Mirrors `engine.entity_terms.source`'s CHECK constraint exactly. */
export type Provenance = 'ai' | 'inferred' | 'editor'

export type Assignment = {
  termId: string
  /** `null` when the term id resolves to no row in the platform vocabulary. */
  facetKey: string | null
  facetLabel: string | null
  termLabel: string | null
  termSlug: string | null
  /** The term's parent in the taxonomy tree — "Seminyak" under "Badung". */
  parentLabel: string | null
  weight: number
  source: Provenance
  /** Nullable in the schema, and a row with no confidence is not a confident row. */
  confidence: number | null
  createdAt: string
}

export type SourceSummary = {
  source: Provenance
  count: number
  belowGate: number
  meanConfidence: number | null
}

export type ClassificationReport = {
  assignments: Assignment[]
  total: number
  belowGate: number
  meanConfidence: number | null
  bySource: SourceSummary[]
  /** Assignments whose term id is in no platform vocabulary row. */
  unresolved: number
  /** Facets the taxonomy declares `required: true` that this article has no assignment for. */
  missingRequiredFacets: Array<{ key: string; label: string }>
}

// --- the platform pool -----------------------------------------------------
//
// Module-scope, `max: 2`: a pool per request leaks connections, and this is an
// internal tool on a box already running the API, the worker and two Payload
// instances. Both spellings of the variable are accepted because both are
// really set — deploy/docker-compose.yml passes `PLATFORM_DATABASE_URI` for
// the shared Payload config and `PLATFORM_DATABASE_URL` for the commerce
// pool, and every other file in this directory reads them in this order.
let platformPool: pg.Pool | null = null

function platform(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set — the term vocabulary lives in now_platform')
  platformPool ??= new pg.Pool({ connectionString: url, max: 2, statement_timeout: 5_000 })
  return platformPool
}

type TermMeta = {
  facetKey: string
  facetLabel: string
  label: string
  slug: string
  parentLabel: string | null
}

/**
 * Resolve term ids to their meaning. One SELECT, ids passed as a uuid array.
 *
 * `= ANY($1::uuid[])` rather than an interpolated `IN (...)` list: the ids
 * come from the city database rather than from a URL, but a query builder
 * that is safe only because of where its input happened to originate is one
 * refactor away from not being safe at all.
 */
async function resolveTerms(termIds: string[]): Promise<Map<string, TermMeta>> {
  const unique = [...new Set(termIds)]
  if (unique.length === 0) return new Map()

  const { rows } = await platform().query(
    `SELECT t.id::text AS id, f.key AS facet_key, f.label AS facet_label,
            t.label, t.slug, p.label AS parent_label
       FROM engine.terms t
       JOIN engine.facets f ON f.id = t.facet_id
       LEFT JOIN engine.terms p ON p.id = t.parent_id
      WHERE t.id = ANY($1::uuid[])`,
    [unique],
  )

  return new Map(
    rows.map((r) => [
      String(r.id),
      {
        facetKey: String(r.facet_key),
        facetLabel: String(r.facet_label),
        label: String(r.label),
        slug: String(r.slug),
        parentLabel: r.parent_label === null ? null : String(r.parent_label),
      },
    ]),
  )
}

/**
 * Every seeded term for one facet, for the correction control's options.
 *
 * Deliberately not `loadVocabulary()` from the CMS package, even though it
 * answers a superset of this: that function is a boot-time snapshot, exported
 * so `buildConfig` can bake static `options` into Payload field configs before
 * the config object exists. Calling it per request would open and close a
 * connection and fetch all 407 terms to populate one dropdown of 9. The shape
 * is the same and the rationale is its — one read-only SELECT against the
 * platform DB, never a write — at the size this page needs.
 *
 * Ordered by label, matching `vocabulary.ts`'s own `ORDER BY f.key, t.label`,
 * so the same term sits in the same place in the report's control and in
 * Payload's own select on the review row.
 */
export async function facetTerms(
  facetKey: string,
): Promise<Array<{ termId: string; slug: string; label: string; parentLabel: string | null }>> {
  const { rows } = await platform().query(
    `SELECT t.id::text AS id, t.slug, t.label, p.label AS parent_label
       FROM engine.terms t
       JOIN engine.facets f ON f.id = t.facet_id
       LEFT JOIN engine.terms p ON p.id = t.parent_id
      WHERE f.key = $1
      ORDER BY t.label`,
    [facetKey],
  )
  return rows.map((r) => ({
    termId: String(r.id),
    slug: String(r.slug),
    label: String(r.label),
    parentLabel: r.parent_label === null ? null : String(r.parent_label),
  }))
}

/** The facets §4 marks `required` — type, subtype, location, format today. */
export async function requiredFacets(): Promise<Array<{ key: string; label: string }>> {
  const { rows } = await platform().query(
    `SELECT key, label FROM engine.facets WHERE required ORDER BY key`,
  )
  return rows.map((r) => ({ key: String(r.key), label: String(r.label) }))
}

/**
 * Every facet assignment the engine holds for one article, shakiest first.
 *
 * Ordering is done in SQL and it needs the NULLS FIRST: `confidence` is
 * nullable, and a row with no confidence at all is the least certain thing on
 * the page, not the most. Postgres sorts NULLs last on ASC by default, which
 * would have buried exactly the rows a reviewer most needs to see.
 *
 * Ties break on facet then label so the order is stable between renders —
 * 3,630 of Bali's `type` assignments share the identical confidence, and a
 * list that reshuffles itself on refresh is unreviewable.
 */
export async function getArticleClassification(articleId: number): Promise<ClassificationReport> {
  // The two databases in parallel: the assignments are a city read and the
  // required-facet list a platform read, and neither depends on the other.
  // Only `resolveTerms` has to wait, because its input is the first query's
  // output — that dependency is the whole reason this cannot be one query.
  const [{ rows }, required] = await Promise.all([
    cityPool().query(
      `SELECT term_id::text AS term_id, weight::float8 AS weight, source,
              confidence::float8 AS confidence, created_at
         FROM engine.entity_terms
        WHERE entity_type = 'article' AND entity_id = $1`,
      [String(articleId)],
    ),
    requiredFacets(),
  ])

  const terms = await resolveTerms(rows.map((r) => String(r.term_id)))

  const assignments: Assignment[] = rows.map((r) => {
    const meta = terms.get(String(r.term_id))
    return {
      termId: String(r.term_id),
      facetKey: meta?.facetKey ?? null,
      facetLabel: meta?.facetLabel ?? null,
      termLabel: meta?.label ?? null,
      termSlug: meta?.slug ?? null,
      parentLabel: meta?.parentLabel ?? null,
      weight: Number(r.weight),
      source: String(r.source) as Provenance,
      confidence: r.confidence === null ? null : Number(r.confidence),
      createdAt: new Date(r.created_at).toISOString(),
    }
  })

  assignments.sort((a, b) => {
    const ca = a.confidence ?? -1
    const cb = b.confidence ?? -1
    if (ca !== cb) return ca - cb
    return (
      (a.facetKey ?? '~').localeCompare(b.facetKey ?? '~') ||
      (a.termLabel ?? a.termId).localeCompare(b.termLabel ?? b.termId)
    )
  })

  const scored = assignments.filter((a) => a.confidence !== null)
  const present = new Set(assignments.map((a) => a.facetKey).filter(Boolean))

  const bySource: SourceSummary[] = (['inferred', 'ai', 'editor'] as const)
    .map((source) => {
      const forSource = assignments.filter((a) => a.source === source)
      const withScore = forSource.filter((a) => a.confidence !== null)
      return {
        source,
        count: forSource.length,
        belowGate: forSource.filter((a) => (a.confidence ?? 0) < CONFIDENCE_GATE).length,
        meanConfidence: withScore.length
          ? withScore.reduce((sum, a) => sum + (a.confidence ?? 0), 0) / withScore.length
          : null,
      }
    })
    .filter((s) => s.count > 0)

  return {
    assignments,
    total: assignments.length,
    belowGate: assignments.filter((a) => (a.confidence ?? 0) < CONFIDENCE_GATE).length,
    meanConfidence: scored.length
      ? scored.reduce((sum, a) => sum + (a.confidence ?? 0), 0) / scored.length
      : null,
    bySource,
    unresolved: assignments.filter((a) => a.facetKey === null).length,
    missingRequiredFacets: required.filter((f) => !present.has(f.key)),
  }
}

/**
 * The `classification-reviews` row ids attached to one article.
 *
 * A separate step from reading the rows themselves, which go through
 * Payload's Local API — this returns ids only. The reason is the polymorphic
 * `entity` field: `relationTo: ['articles', 'places']` is stored in a join
 * table (`classification_reviews_rels`) with one column per possible target,
 * and the Local API's filter syntax for "the polymorphic relationship points
 * at article 2516" is version-specific enough that guessing it wrong fails by
 * returning the WRONG ROWS rather than by throwing. A review decision written
 * against another article's proposal is the one bug this surface must not
 * have, so the membership question is answered by the join table directly and
 * the rows themselves are still fetched, typed, by Payload.
 *
 * `articles_id` has an ON DELETE CASCADE, so a row here always has an article.
 */
export async function reviewIdsForArticle(articleId: number): Promise<number[]> {
  const { rows } = await cityPool().query(
    `SELECT parent_id FROM public.classification_reviews_rels
      WHERE articles_id = $1
      ORDER BY parent_id`,
    [articleId],
  )
  return rows.map((r) => Number(r.parent_id))
}

export type QueueRow = {
  id: number
  title: string
  status: string
  primaryType: string | null
  format: string | null
  assignments: number
  belowGate: number
  /** The single least-confident assignment on the article — what sorts the queue. */
  weakest: number | null
  /** What that weakest assignment actually says, once resolved in the platform DB. */
  weakestFacet: string | null
  weakestTerm: string | null
  pendingReviews: number
}

/**
 * The archive ordered by how badly it needs a human, weakest article first.
 *
 * Raw SQL, and the reason is the same one `sectionFormatCounts` gives a few
 * files over: the Local API cannot aggregate. "Order 4,429 articles by the
 * minimum confidence across their assignments" is not a `payload.find` that
 * exists — and half the data being aggregated is in `engine`, which the Local
 * API cannot see at all, since Payload is bound to `public`. The rejected
 * alternative was fetching every article and every assignment and sorting in
 * Node; that is 15,804 rows over the wire to render 50.
 *
 * `search` is the first free text in this file to reach a query and is passed
 * as a parameter, never interpolated.
 */
export async function getClassificationQueue(
  options: { search?: string; limit?: number; belowGateOnly?: boolean } = {},
): Promise<QueueRow[]> {
  const { search, limit = 60, belowGateOnly = false } = options
  const params: unknown[] = [CONFIDENCE_GATE]
  let titleFilter = ''
  if (search && search.trim()) {
    params.push(`%${search.trim()}%`)
    titleFilter = `AND a.title ILIKE $${params.length}`
  }
  params.push(Math.min(Math.max(limit, 1), 200))
  const limitParam = `$${params.length}`

  // `weakest_term` is the term id AT the minimum, not merely the minimum.
  // min() answers "how bad"; the queue also has to answer "at what", and the
  // two have to come out of the same row or the label will eventually name a
  // different assignment than the number beside it does. Hence array_agg with
  // the same ordering rather than a second aggregate.
  const { rows } = await cityPool().query(
    `WITH terms AS (
       SELECT entity_id,
              count(*)::int AS assignments,
              count(*) FILTER (WHERE confidence < $1)::int AS below_gate,
              min(confidence)::float8 AS weakest,
              (array_agg(term_id::text ORDER BY confidence ASC NULLS FIRST))[1] AS weakest_term
         FROM engine.entity_terms
        WHERE entity_type = 'article'
        GROUP BY entity_id
     ), reviews AS (
       SELECT r.articles_id AS article_id, count(*)::int AS pending
         FROM public.classification_reviews_rels r
         JOIN public.classification_reviews c ON c.id = r.parent_id
        WHERE r.articles_id IS NOT NULL AND c.review_state = 'pending'
        GROUP BY r.articles_id
     )
     SELECT a.id, a.title, a._status AS status,
            a.primary_type::text AS primary_type, a.format::text AS format,
            coalesce(t.assignments, 0) AS assignments,
            coalesce(t.below_gate, 0) AS below_gate,
            t.weakest, t.weakest_term,
            coalesce(rv.pending, 0) AS pending_reviews
       FROM public.articles a
       LEFT JOIN terms t ON t.entity_id = a.id::text
       LEFT JOIN reviews rv ON rv.article_id = a.id
      WHERE TRUE ${titleFilter}
        ${belowGateOnly ? 'AND coalesce(t.below_gate, 0) > 0' : ''}
      ORDER BY t.weakest ASC NULLS LAST, coalesce(t.below_gate, 0) DESC, a.id ASC
      LIMIT ${limitParam}`,
    params,
  )

  // One vocabulary lookup for the whole page, not one per row: the 60 rows
  // on screen resolve to a handful of distinct terms (Bali's entire archive
  // uses 122 of the 407 seeded terms), and `resolveTerms` de-duplicates.
  const terms = await resolveTerms(
    rows.map((r) => r.weakest_term).filter((t): t is string => Boolean(t)),
  )

  return rows.map((r) => {
    const meta = r.weakest_term ? terms.get(String(r.weakest_term)) : undefined
    return {
      id: Number(r.id),
      title: String(r.title ?? ''),
      status: String(r.status ?? 'draft'),
      primaryType: r.primary_type === null ? null : String(r.primary_type),
      format: r.format === null ? null : String(r.format),
      assignments: Number(r.assignments),
      belowGate: Number(r.below_gate),
      weakest: r.weakest === null ? null : Number(r.weakest),
      weakestFacet: meta?.facetLabel ?? null,
      weakestTerm: meta?.label ?? null,
      pendingReviews: Number(r.pending_reviews),
    }
  })
}

export type QueueTotals = {
  articles: number
  assignments: number
  belowGate: number
  articlesBelowGate: number
  pendingReviews: number
}

/** The four numbers that say how big the backlog is. One query, one round trip. */
export async function getQueueTotals(): Promise<QueueTotals> {
  const { rows } = await cityPool().query(
    `SELECT
       (SELECT count(*)::int FROM public.articles) AS articles,
       (SELECT count(*)::int FROM engine.entity_terms WHERE entity_type = 'article') AS assignments,
       (SELECT count(*)::int FROM engine.entity_terms
         WHERE entity_type = 'article' AND confidence < $1) AS below_gate,
       (SELECT count(DISTINCT entity_id)::int FROM engine.entity_terms
         WHERE entity_type = 'article' AND confidence < $1) AS articles_below_gate,
       (SELECT count(*)::int FROM public.classification_reviews
         WHERE review_state = 'pending') AS pending_reviews`,
    [CONFIDENCE_GATE],
  )
  const r = rows[0] ?? {}
  return {
    articles: Number(r.articles ?? 0),
    assignments: Number(r.assignments ?? 0),
    belowGate: Number(r.below_gate ?? 0),
    articlesBelowGate: Number(r.articles_below_gate ?? 0),
    pendingReviews: Number(r.pending_reviews ?? 0),
  }
}

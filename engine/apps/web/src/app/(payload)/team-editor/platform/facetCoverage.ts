import 'server-only'

import pg from 'pg'

import { cityPool } from '@/lib/payload'

/**
 * Facet coverage for the console's KPI row (docs/DESIGN-SYSTEM.md §5): "Real
 * numbers: 8,052 location assignments, 3,906 format, 3,589 type, 1,690
 * subtype, and five facets at zero."
 *
 * THOSE PARTICULAR FIGURES ARE COMBINED ACROSS BOTH CITIES
 * (docs/SURFACES-PLAN.md §2.1, "measured across both databases"), and this
 * function cannot reproduce that combination honestly. A Payload instance —
 * and the web app process serving its admin — binds to exactly ONE city
 * database via `DATABASE_URI` (ARCHITECTURE.md §3.5's one deliberate
 * per-city knob); there is no second connection string here for "the other
 * city", and guessing one by string-substituting `DATABASE_URI` would be
 * exactly the kind of cross-city reach docs/SURFACES-PLAN.md S5.4 lists as
 * open, unbuilt work, not a two-line fix inside a styling ticket. So this
 * reports THIS city's live coverage — real numbers, queried on every render,
 * never the two totals added together — and says so in `scopeNote` rather
 * than mislabelling a single-city count as the combined figure. Cross-city
 * aggregation belongs to whoever builds S5.4's bridge through `now_platform`,
 * with a real answer for which city's Postgres a platform-console request is
 * allowed to open.
 *
 * THE JOIN IS IN JAVASCRIPT, for the same reason `lib/classification.ts`'s
 * is and not a fourth reimplementation of that reasoning: `entity_terms`
 * (this city's DB) has no facet column, only a `term_id`, and the term's
 * facet lives in `engine.terms`/`engine.facets` in `now_platform` — a
 * different database. Postgres cannot join across them, so the two SELECTs
 * below run against two separate connections and are reduced together here.
 */

export type FacetCoverageRow = {
  facetKey: string
  /** Rows in `entity_terms` for this facet — an "assignment", the same unit
   *  the classification queue counts. */
  assignments: number
}

export type FacetCoverageReport = {
  rows: FacetCoverageRow[]
  /** Total classified articles this city has, for the KPI row's other figure. */
  articleCount: number
  scopeNote: string
}

// A short-lived client, not a module-scope pool: this report renders once
// per visit to a screen five staff members use, not per document autosave —
// `packages/cms/src/lib/vocabulary.ts` makes the same call for the same
// "not worth holding a connection open" reason.
async function loadFacetKeys(): Promise<Map<string, string>> {
  const connectionString = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!connectionString) {
    throw new Error('PLATFORM_DATABASE_URI is not set — facet coverage needs the platform vocabulary')
  }

  const client = new pg.Client({ connectionString, connectionTimeoutMillis: 5000 })
  await client.connect()
  try {
    const { rows } = await client.query<{ term_id: string; facet_key: string }>(
      `SELECT t.id AS term_id, f.key AS facet_key
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id`,
    )
    return new Map(rows.map((r) => [r.term_id, r.facet_key]))
  } finally {
    await client.end().catch(() => {})
  }
}

async function loadFacetKeyList(): Promise<string[]> {
  const connectionString = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!connectionString) return []

  const client = new pg.Client({ connectionString, connectionTimeoutMillis: 5000 })
  await client.connect()
  try {
    const { rows } = await client.query<{ key: string }>('SELECT key FROM engine.facets ORDER BY key')
    return rows.map((r) => r.key)
  } finally {
    await client.end().catch(() => {})
  }
}

export async function getFacetCoverage(): Promise<FacetCoverageReport> {
  const citySlug = process.env.SITE_SLUG ?? 'this city'

  const [facetKeys, allFacetKeys, entityTermCounts, articleCountResult] = await Promise.all([
    loadFacetKeys(),
    loadFacetKeyList(),
    cityPool().query<{ term_id: string; n: string }>(
      `SELECT term_id, COUNT(*) AS n
         FROM engine.entity_terms
        WHERE entity_type = 'article'
        GROUP BY term_id`,
    ),
    cityPool().query<{ n: string }>(
      `SELECT COUNT(DISTINCT entity_id) AS n
         FROM engine.entity_terms
        WHERE entity_type = 'article'`,
    ),
  ])

  const byFacet = new Map<string, number>(allFacetKeys.map((key) => [key, 0]))
  for (const row of entityTermCounts.rows) {
    const facetKey = facetKeys.get(row.term_id)
    // A term id `entity_terms` carries that resolves to no row in the
    // platform vocabulary is a real integrity gap (see
    // `lib/classification.ts`'s own note on "orphans") — silently dropping
    // it from every facet's total would be exactly the kind of invented
    // tidiness S2 spent a whole phase removing. It is excluded from every
    // named facet's count and NOT added to any of them, which is honest
    // about not knowing where it belongs, rather than guessing.
    if (!facetKey) continue
    byFacet.set(facetKey, (byFacet.get(facetKey) ?? 0) + Number(row.n))
  }

  const rows: FacetCoverageRow[] = [...byFacet.entries()]
    .map(([facetKey, assignments]) => ({ facetKey, assignments }))
    .sort((a, b) => b.assignments - a.assignments)

  return {
    rows,
    articleCount: Number(articleCountResult.rows[0]?.n ?? 0),
    scopeNote: `Live from ${citySlug}'s own database — not the two-city total docs/SURFACES-PLAN.md §2.1 quotes. Combining both cities needs S5.4's cross-city bridge, which does not exist yet.`,
  }
}

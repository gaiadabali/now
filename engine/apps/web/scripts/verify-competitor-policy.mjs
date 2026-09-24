#!/usr/bin/env node
/**
 * WS1 deliverable #5 — "proof, by count rather than spot check."
 *
 * Runs the competitor/hidden-rival SQL predicates over EVERY published,
 * typed venue article (stay/eat/drink/wellness/shop) in the currently-
 * configured city (`DATABASE_URI`, from an env file passed via
 * `node --env-file=...`) and asserts that not one returned candidate,
 * across every rail, is a competitor of the subject — via
 * `lib/competitorPolicy.ts`'s `excludedTypesFor`, the SAME policy module
 * `src/lib/recommend.ts`'s SQL predicates are built from.
 *
 * The two queries below (`READ_NEXT_SQL`, `COMPLEMENT_SQL`) are a literal
 * copy of `src/lib/recommend.ts`'s own `READ_NEXT_SQL`/`COMPLEMENT_SQL` —
 * NOT a re-derivation. Kept as a separate copy, deliberately, rather than
 * importing `recommend.ts` directly, because that module imports
 * `server-only` (a guard against accidental client-bundling, correct for
 * Next.js) which throws unconditionally outside Next's `react-server`
 * module-resolution condition — including under `payload run`, which this
 * script would otherwise need for `lib/payload.ts`'s own CMS-config import
 * chain (`Articles.ts`'s directory import does not resolve under plain
 * Node ESM either — see `verify-site-config.mjs`'s header comment for the
 * identical blocker on a different file). This script needs neither
 * Payload nor Next: only `engine.type_relations` and the candidate ids +
 * types the same SQL predicates already select. If `recommend.ts`'s SQL
 * changes, this file's copy must change with it — flagged in both files'
 * comments pointing at each other.
 *
 * Run once per city:
 *
 *   node --env-file=.env.local scripts/verify-competitor-policy.mjs
 *   node --env-file=.env.jakarta.local scripts/verify-competitor-policy.mjs
 *
 * `npm run verify:competitor-policy` runs it against whatever `.env.local`
 * currently points at.
 */
import pg from 'pg'

const { excludedTypesFor, relationsFromRows } = await import('../src/lib/competitorPolicy.ts')
const { hiddenRivalPatternForSubject } = await import('../src/lib/hiddenRival.ts')

const VENUE_TYPES = ['stay', 'eat', 'drink', 'wellness', 'shop']
const RAIL_LIMIT = 6
const QUALITY_FLOOR = 0.35
const EMBEDDING_MODEL = 'BAAI/bge-small-en-v1.5'
const CONCURRENCY = 10

const TYPE_TO_SECTION = {
  eat: 'dining',
  drink: 'dining',
  stay: 'stay',
  wellness: 'wellness',
  do: 'things-to-do',
  shop: 'things-to-do',
  event: 'events',
  editorial: 'editorial',
}
const SECTION_DISPLAY_ORDER = ['stay', 'dining', 'wellness', 'things-to-do', 'events']

function connectionString() {
  const value = process.env.DATABASE_URI
  if (!value) throw new Error('DATABASE_URI is not set — pass --env-file=.env.local (or .env.jakarta.local)')
  return value
}

const pool = new pg.Pool({ connectionString: connectionString(), max: CONCURRENCY + 2, statement_timeout: 10_000 })

// Literal copy of src/lib/recommend.ts's READ_NEXT_SQL — see header comment.
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

// Literal copy of src/lib/recommend.ts's COMPLEMENT_SQL — see header comment.
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

async function loadRelations() {
  const { rows } = await pool.query(
    'SELECT type, exclude_same, complements, competes_with FROM engine.type_relations',
  )
  return relationsFromRows(rows)
}

async function loadVenueArticles() {
  // VERIFY_LIMIT is a manual escape hatch for a quick, bounded sanity run
  // (unset in normal use — every published venue article is the point of
  // this script, per the ticket's "proof, by count rather than spot
  // check").
  const limit = process.env.VERIFY_LIMIT ? Number(process.env.VERIFY_LIMIT) : null
  const { rows } = await pool.query(
    `SELECT id, primary_type::text AS primary_type
       FROM public.articles
      WHERE _status = 'published'
        AND published_at IS NOT NULL AND published_at <= now()
        AND primary_type::text = ANY($1::text[])
      ORDER BY id
      ${limit ? 'LIMIT ' + limit : ''}`,
    [VENUE_TYPES],
  )
  return rows
}

/** Mirrors `recommend.ts`'s `complementSectionsFor` — see that function. */
function complementSectionsFor(subjectType, relations) {
  if (!subjectType) return []
  const relation = relations[subjectType]
  if (!relation || !relation.excludeSame) return []
  const bySection = new Map()
  for (const complementType of relation.complements) {
    const section = TYPE_TO_SECTION[complementType]
    if (!section) continue
    const list = bySection.get(section) ?? []
    list.push(complementType)
    bySection.set(section, list)
  }
  const out = []
  for (const section of SECTION_DISPLAY_ORDER) {
    const types = bySection.get(section)
    if (types && types.length > 0) out.push({ section, types })
  }
  return out
}

async function resolveAllRails(articleId, subjectType, relations) {
  const rails = []
  const excluded = Array.from(excludedTypesFor(relations, subjectType))
  const hiddenRivalPattern = hiddenRivalPatternForSubject(subjectType, relations)

  const { rows: readNext } = await pool.query(READ_NEXT_SQL, [
    articleId,
    EMBEDDING_MODEL,
    excluded,
    QUALITY_FLOOR,
    hiddenRivalPattern,
    Math.max(RAIL_LIMIT * 4, 20),
  ])
  rails.push({ key: 'read-next', rows: readNext })

  for (const { section, types } of complementSectionsFor(subjectType, relations)) {
    const { rows } = await pool.query(COMPLEMENT_SQL, [articleId, types, QUALITY_FLOOR, hiddenRivalPattern, RAIL_LIMIT])
    rails.push({ key: `plan-${section}`, rows })
  }
  return rails
}

async function mapWithConcurrency(items, limit, fn) {
  const results = new Array(items.length)
  let next = 0
  async function worker() {
    while (next < items.length) {
      const i = next++
      results[i] = await fn(items[i], i)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker))
  return results
}

async function main() {
  const site = process.env.SITE_SLUG ?? '(unknown — SITE_SLUG not set)'
  console.log(`[verify-competitor-policy] site=${site} database=${process.env.DATABASE_URI ? '(set)' : '(NOT SET)'}`)

  const relations = await loadRelations()
  const articles = await loadVenueArticles()
  console.log(`[verify-competitor-policy] ${articles.length} published venue articles (stay/eat/drink/wellness/shop) found`)

  const t0 = Date.now()
  let checked = 0
  let emptyRails = 0
  let totalItems = 0
  let totalRails = 0
  const violations = []

  await mapWithConcurrency(articles, CONCURRENCY, async (row) => {
    const rails = await resolveAllRails(row.id, row.primary_type, relations)
    checked += 1
    const itemCount = rails.reduce((sum, r) => sum + r.rows.length, 0)
    totalItems += itemCount
    totalRails += rails.length
    if (itemCount === 0) emptyRails += 1

    const excluded = excludedTypesFor(relations, row.primary_type)
    for (const rail of rails) {
      for (const candidate of rail.rows) {
        if (excluded.has(candidate.primary_type ?? '')) {
          violations.push({
            articleId: row.id,
            subjectType: row.primary_type,
            rail: rail.key,
            candidateId: candidate.id,
            candidateType: candidate.primary_type,
          })
        }
      }
    }
  })

  const elapsedMs = Date.now() - t0
  const meanItemsPerRail = totalRails > 0 ? (totalItems / totalRails).toFixed(2) : '0'
  const meanMsPerArticle = checked > 0 ? (elapsedMs / checked).toFixed(1) : '0'

  console.log('')
  console.log(`[verify-competitor-policy] articles checked:            ${checked}`)
  console.log(`[verify-competitor-policy] articles with NO rail items: ${emptyRails}`)
  console.log(`[verify-competitor-policy] total rails produced:        ${totalRails}`)
  console.log(`[verify-competitor-policy] mean items per rail:         ${meanItemsPerRail}`)
  console.log(`[verify-competitor-policy] elapsed:                     ${elapsedMs}ms (${meanMsPerArticle}ms/article, concurrency=${CONCURRENCY})`)
  console.log(`[verify-competitor-policy] VIOLATIONS:                  ${violations.length}`)

  if (violations.length > 0) {
    console.log('')
    console.log('[verify-competitor-policy] FAIL — competitor items leaked onto a venue subject:')
    for (const v of violations.slice(0, 50)) console.log('  ' + JSON.stringify(v))
    if (violations.length > 50) console.log(`  ... and ${violations.length - 50} more`)
    process.exitCode = 1
    return
  }

  console.log('[verify-competitor-policy] PASS — zero competitor items across every checked article')
}

try {
  await main()
} finally {
  await pool.end()
}

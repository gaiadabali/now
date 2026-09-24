#!/usr/bin/env node
/**
 * WS1 deliverable #5 — "proof, by count rather than spot check."
 *
 * Runs `lib/recommendSql.ts` — the SAME module `lib/recommend.ts` calls in
 * production, not a copy of it (second-pass coordinator review: "the
 * verification script keeping its own literal copy of recommend.ts's
 * queries means the proof can drift from the product") — over EVERY
 * published, typed venue article (stay/eat/drink/wellness/shop) in the
 * currently-configured city (`DATABASE_URI`, from an env file passed via
 * `node --env-file=...`) and asserts that not one returned candidate,
 * across every rail, is a competitor of the subject.
 *
 * `lib/recommendSql.ts` has no `server-only` import and takes its
 * `pg.Pool` as a parameter rather than importing `@/lib/payload`'s
 * `cityPool()` (which pulls in the full CMS collection config —
 * `Articles.ts`'s directory import does not resolve under plain Node ESM
 * either, see `verify-site-config.mjs`'s header comment for the identical
 * blocker on a different file). This script supplies its own bare
 * `pg.Pool`; production supplies `cityPool()`. Same queries either way.
 *
 * Run once per city:
 *
 *   node --env-file=.env.local scripts/verify-competitor-policy.mjs
 *   node --env-file=.env.jakarta.local scripts/verify-competitor-policy.mjs
 *
 * `npm run verify:competitor-policy` runs it against whatever `.env.local`
 * currently points at.
 */
import { register } from 'node:module'
import pg from 'pg'

register('./lib/alias-loader.mjs', import.meta.url)

const VENUE_TYPES = ['stay', 'eat', 'drink', 'wellness', 'shop']
const RAIL_LIMIT = 6
const COMPLEMENT_POOL_SIZE = 60
const CONCURRENCY = 10

const {
  loadRelations,
  complementSectionsFor,
  resolveComplementCandidates,
  resolveReadNextCandidates,
  groupComplementCandidatesBySection,
  dedupeBySeries,
  diversify,
} = await import('../src/lib/recommendSql.ts')
const { excludedTypesFor } = await import('../src/lib/competitorPolicy.ts')

function connectionString() {
  const value = process.env.DATABASE_URI
  if (!value) throw new Error('DATABASE_URI is not set — pass --env-file=.env.local (or .env.jakarta.local)')
  return value
}

const pool = new pg.Pool({ connectionString: connectionString(), max: CONCURRENCY + 2, statement_timeout: 10_000 })

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

/** Every rail this article would get, as (rail key, candidate rows) pairs
 * — mirrors `getArticleRails`'s own assembly exactly (same resolver
 * calls, same section grouping, same cross-rail dedup), because it calls
 * the identical `lib/recommendSql.ts` functions `getArticleRails` does. */
async function resolveAllRails(articleId, subjectType, relations) {
  const sections = complementSectionsFor(subjectType, relations)

  const [complementRows, readNextRowsRaw] = await Promise.all([
    sections.length > 0 ? resolveComplementCandidates(pool, articleId, sections, COMPLEMENT_POOL_SIZE) : Promise.resolve([]),
    resolveReadNextCandidates(pool, articleId, subjectType, relations, Math.max(RAIL_LIMIT * 4, 20)),
  ])

  const grouped = groupComplementCandidatesBySection(complementRows, sections, RAIL_LIMIT, new Set())
  const usedIds = new Set()
  for (const rows of grouped.values()) for (const r of rows) usedIds.add(r.id)

  const readNextRows = diversify(dedupeBySeries(readNextRowsRaw), RAIL_LIMIT, usedIds)

  const rails = []
  for (const { section } of sections) {
    const rows = grouped.get(section) ?? []
    if (rows.length > 0) rails.push({ key: `plan-${section}`, rows })
  }
  if (readNextRows.length > 0) rails.push({ key: 'read-next', rows: readNextRows })
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

  const relations = await loadRelations(pool)
  const articles = await loadVenueArticles()
  console.log(`[verify-competitor-policy] ${articles.length} published venue articles (stay/eat/drink/wellness/shop) found`)

  const t0 = Date.now()
  let checked = 0
  let emptyRails = 0
  let totalItems = 0
  let totalRails = 0
  let railCountOverThree = 0
  const seenAcrossRailsViolations = []
  const violations = []

  await mapWithConcurrency(articles, CONCURRENCY, async (row) => {
    const rails = await resolveAllRails(row.id, row.primary_type, relations)
    checked += 1
    const itemCount = rails.reduce((sum, r) => sum + r.rows.length, 0)
    totalItems += itemCount
    totalRails += rails.length
    if (itemCount === 0) emptyRails += 1

    const planAroundRails = rails.filter((r) => r.key !== 'read-next')
    if (planAroundRails.length > 3) railCountOverThree += 1

    // Cross-rail overlap check (coordinator review #3: "No story may
    // appear in more than one rail on the same page, including Read Next").
    const seen = new Map()
    for (const rail of rails) {
      for (const candidate of rail.rows) {
        if (seen.has(candidate.id)) {
          seenAcrossRailsViolations.push({ articleId: row.id, candidateId: candidate.id, rails: [seen.get(candidate.id), rail.key] })
        } else {
          seen.set(candidate.id, rail.key)
        }
      }
    }

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
  console.log(`[verify-competitor-policy] articles with >3 plan-around rails: ${railCountOverThree}`)
  console.log(`[verify-competitor-policy] cross-rail overlap violations:      ${seenAcrossRailsViolations.length}`)
  console.log(`[verify-competitor-policy] elapsed:                     ${elapsedMs}ms (${meanMsPerArticle}ms/article, concurrency=${CONCURRENCY})`)
  console.log(`[verify-competitor-policy] COMPETITOR VIOLATIONS:       ${violations.length}`)

  let failed = false
  if (violations.length > 0) {
    failed = true
    console.log('')
    console.log('[verify-competitor-policy] FAIL — competitor items leaked onto a venue subject:')
    for (const v of violations.slice(0, 50)) console.log('  ' + JSON.stringify(v))
    if (violations.length > 50) console.log(`  ... and ${violations.length - 50} more`)
  }
  if (seenAcrossRailsViolations.length > 0) {
    failed = true
    console.log('')
    console.log('[verify-competitor-policy] FAIL — an article appeared in more than one rail:')
    for (const v of seenAcrossRailsViolations.slice(0, 20)) console.log('  ' + JSON.stringify(v))
  }
  if (railCountOverThree > 0) {
    failed = true
    console.log('')
    console.log(`[verify-competitor-policy] FAIL — ${railCountOverThree} article(s) produced more than 3 plan-around rails`)
  }

  if (failed) {
    process.exitCode = 1
    return
  }
  console.log('[verify-competitor-policy] PASS — zero competitor items, zero cross-rail overlap, rail count within bounds')
}

try {
  await main()
} finally {
  await pool.end()
}

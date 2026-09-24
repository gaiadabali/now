#!/usr/bin/env node
/**
 * WS1 deliverable, fourth pass, item 6 — proof that "For you" actually
 * reflects the sign-up picker (ARCHITECTURE §10's `stated_seed`), not just
 * that the code typechecks.
 *
 * Creates a THROWAWAY `engine.identities` row on the PLATFORM database
 * (never touches a real reader) with `stated_prefs = {interests:
 * ['wellness'], areas: ['ubud']}`, runs the SAME stated-seed + kNN logic
 * `getForYou` (`apps/web/src/lib/recommend.ts`) runs for a reader with zero
 * revealed history, reports what share of the returned items match the
 * picked type/area against the base (whole-archive) rate for the same
 * facets, then deletes the row it created.
 *
 * Cannot import `lib/recommend.ts` directly — it imports `lib/payload.ts`,
 * which pulls in the full CMS collection config and only resolves inside a
 * real Next/Payload process (same blocker `verify-competitor-policy.mjs`'s
 * header documents for the same reason). This script instead imports the
 * PURE, shared pieces that have no such import (`lib/taste.ts`,
 * `lib/recommendSql.ts`) and re-runs the stated-seed SQL inline — the exact
 * same queries `loadStatedSeed`/`getForYou` in `recommend.ts` run, kept in
 * sync by eye since there is no third shared module for cross-database
 * (platform + city) queries today (flagged, not solved, same as this
 * script's sibling's TYPE_TO_SECTION duplication note).
 *
 * Run once per city (writes to the PLATFORM db, reads the CITY db named by
 * DATABASE_URI/PLATFORM_DATABASE_URI in the given env file):
 *
 *   node --conditions react-server --experimental-strip-types \
 *     --env-file=.env.local scripts/demo-stated-prefs.mjs
 */
import { register } from 'node:module'
import pg from 'pg'

register('./lib/alias-loader.mjs', import.meta.url)

const { blendTaste, labelFor } = await import('../src/lib/taste.ts')
const { EMBEDDING_MODEL, QUALITY_FLOOR, dedupeBySeries } = await import('../src/lib/recommendSql.ts')

const PICKED_INTERESTS = ['wellness'] // a `type` slug
const PICKED_AREAS = ['ubud'] // a `location` slug
const SAMPLE_SIZE = 12
const BASE_RATE_SAMPLE = 500

function platformUrl() {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  return url
}
function cityUrl() {
  const url = process.env.DATABASE_URI
  if (!url) throw new Error('DATABASE_URI is not set')
  return url
}

function parseVectorText(text) {
  return text.slice(1, -1).split(',').map(Number)
}
function meanVector(vectors) {
  if (vectors.length === 0) return null
  const dim = vectors[0].length
  const sum = new Array(dim).fill(0)
  for (const v of vectors) for (let i = 0; i < dim; i++) sum[i] += v[i]
  return sum.map((v) => v / vectors.length)
}

const platformPool = new pg.Pool({ connectionString: platformUrl(), max: 4, statement_timeout: 10_000 })
const cityPool = new pg.Pool({ connectionString: cityUrl(), max: 4, statement_timeout: 10_000 })

async function createSyntheticReader() {
  const email = `ws1-demo-${Date.now()}@example.invalid`
  const statedPrefs = { interests: PICKED_INTERESTS, topics: [], areas: PICKED_AREAS, persona: null, budget: null }
  const { rows } = await platformPool.query(
    `INSERT INTO engine.identities (email, email_norm, stated_prefs, status)
     VALUES ($1, lower($1), $2::jsonb, 'active')
     RETURNING id::text AS id`,
    [email, JSON.stringify(statedPrefs)],
  )
  return { id: rows[0].id, email }
}

async function deleteSyntheticReader(id) {
  await platformPool.query(`DELETE FROM engine.identities WHERE id = $1::uuid`, [id])
}

/** Mirrors `recommend.ts#loadStatedSeed` — see this file's header. */
async function loadStatedSeed(identityId) {
  const { rows: termRows } = await platformPool.query(
    `SELECT t.id::text AS id, t.slug, t.label, f.key AS facet_key
       FROM engine.terms t
       JOIN engine.facets f ON f.id = t.facet_id
      WHERE (f.key = 'type' AND t.slug = ANY($1::text[]))
         OR (f.key = 'location' AND t.slug = ANY($2::text[]))`,
    [PICKED_INTERESTS, PICKED_AREAS],
  )
  if (termRows.length === 0) return { vector: null, labels: [], areaTermIds: [] }
  const termIds = termRows.map((r) => r.id)
  const labels = termRows.map((r) => r.label)
  const areaTermIds = termRows.filter((r) => r.facet_key === 'location').map((r) => r.id)

  // `engine.embeddings` (including entity_type='term') lives in the CITY
  // database, not the platform one — see recommend.ts#loadStatedSeed's own
  // note on this, found the hard way running this exact script the first
  // time (`now_platform` has no `engine.embeddings` table at all).
  const { rows: embedRows } = await cityPool.query(
    `SELECT vec::text AS vec_text FROM engine.embeddings
      WHERE entity_type = 'term' AND model = $1 AND entity_id = ANY($2::text[])`,
    [EMBEDDING_MODEL, termIds],
  )
  const termMean = meanVector(embedRows.map((r) => parseVectorText(r.vec_text)))
  if (!termMean) return { vector: null, labels }

  let seedVector = termMean
  const { rows: articleIdRows } = await cityPool.query(
    `SELECT DISTINCT entity_id FROM engine.entity_terms
      WHERE entity_type = 'article' AND term_id = ANY($1::uuid[]) LIMIT 200`,
    [termIds],
  )
  if (articleIdRows.length > 0) {
    const { rows: articleEmbedRows } = await cityPool.query(
      `SELECT vec::text AS vec_text FROM engine.embeddings
        WHERE entity_type = 'article' AND model = $1 AND entity_id = ANY($2::text[])`,
      [EMBEDDING_MODEL, articleIdRows.map((r) => r.entity_id)],
    )
    const articleCentroid = meanVector(articleEmbedRows.map((r) => parseVectorText(r.vec_text)))
    if (articleCentroid) seedVector = meanVector([termMean, articleCentroid])
  }
  return { vector: seedVector, labels, areaTermIds }
}

const FOR_YOU_SQL = `
  SELECT a.id, a.primary_type::text AS primary_type, a.series_key
    FROM public.articles a
    JOIN engine.embeddings e ON e.entity_type = 'article' AND e.entity_id = a.id::text AND e.model = $1
   WHERE a._status = 'published'
     AND a.published_at IS NOT NULL AND a.published_at <= now()
     AND a.id NOT IN (SELECT entity_id::int FROM engine.quality_scores WHERE entity_type = 'article' AND score < $2)
   ORDER BY e.vec <=> $3::vector ASC
   LIMIT $4
`

/** `areaTermIds`: resolved ONCE against the platform vocabulary
 * (`loadStatedSeed`) — `engine.terms` does not exist in the city database
 * (verified directly), so this never joins to it there; `entity_terms
 * .term_id` is compared straight against the ids already resolved. */
async function matchesPicks(ids, areaTermIds) {
  if (ids.length === 0) return 0
  const { rows: typeRows } = await cityPool.query(
    `SELECT id FROM public.articles WHERE id = ANY($1::int[]) AND primary_type::text = ANY($2::text[])`,
    [ids, PICKED_INTERESTS],
  )
  let areaRows = []
  if (areaTermIds.length > 0) {
    const result = await cityPool.query(
      `SELECT DISTINCT entity_id
         FROM engine.entity_terms
        WHERE entity_type = 'article' AND entity_id = ANY($1::text[]) AND term_id = ANY($2::uuid[])`,
      [ids.map(String), areaTermIds],
    )
    areaRows = result.rows
  }
  const matched = new Set([...typeRows.map((r) => r.id), ...areaRows.map((r) => Number(r.entity_id))])
  return matched.size
}

async function baseRate(areaTermIds) {
  const { rows } = await cityPool.query(
    `SELECT id FROM public.articles
      WHERE _status = 'published' AND published_at IS NOT NULL AND published_at <= now()
      ORDER BY random() LIMIT $1`,
    [BASE_RATE_SAMPLE],
  )
  const ids = rows.map((r) => r.id)
  const matched = await matchesPicks(ids, areaTermIds)
  return { sampleSize: ids.length, matched, rate: ids.length > 0 ? matched / ids.length : 0 }
}

async function main() {
  console.log(`[demo-stated-prefs] picks: interests=${PICKED_INTERESTS.join(',')} areas=${PICKED_AREAS.join(',')}`)
  const reader = await createSyntheticReader()
  console.log(`[demo-stated-prefs] created synthetic identity ${reader.id} (${reader.email})`)

  try {
    const seed = await loadStatedSeed(reader.id)
    if (!seed.vector) {
      console.log('[demo-stated-prefs] FAIL — no stated_seed vector resolved (picked terms not found in this city\'s vocabulary?)')
      process.exitCode = 1
      return
    }
    const blended = blendTaste(null, seed.vector, 0)
    console.log(`[demo-stated-prefs] label: "${labelFor(blended.dominant, seed.labels)}" (dominant=${blended.dominant})`)

    const vectorLiteral = `[${blended.vector.join(',')}]`
    const { rows } = await cityPool.query(FOR_YOU_SQL, [EMBEDDING_MODEL, QUALITY_FLOOR, vectorLiteral, SAMPLE_SIZE * 4])
    const deduped = dedupeBySeries(rows).slice(0, SAMPLE_SIZE)
    const ids = deduped.map((r) => r.id)

    const matched = await matchesPicks(ids, seed.areaTermIds)
    const personalizedRate = ids.length > 0 ? matched / ids.length : 0
    const base = await baseRate(seed.areaTermIds)

    console.log('')
    console.log(`[demo-stated-prefs] "For you" items:        ${ids.length}`)
    console.log(`[demo-stated-prefs] matching picked type/area: ${matched} (${(personalizedRate * 100).toFixed(1)}%)`)
    console.log(`[demo-stated-prefs] base rate (random ${base.sampleSize} published articles): ${base.matched} (${(base.rate * 100).toFixed(1)}%)`)
    console.log(
      personalizedRate > base.rate
        ? `[demo-stated-prefs] PASS — personalized rate (${(personalizedRate * 100).toFixed(1)}%) exceeds base rate (${(base.rate * 100).toFixed(1)}%)`
        : `[demo-stated-prefs] FAIL — personalized rate did not exceed base rate`,
    )
    if (personalizedRate <= base.rate) process.exitCode = 1
  } finally {
    await deleteSyntheticReader(reader.id)
    console.log(`[demo-stated-prefs] deleted synthetic identity ${reader.id}`)
  }
}

try {
  await main()
} finally {
  await platformPool.end()
  await cityPool.end()
}

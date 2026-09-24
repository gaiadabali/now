/**
 * The SQL and row-shaping `getArticleRails` runs, factored out of
 * `recommend.ts` so `scripts/verify-competitor-policy.mjs` can import the
 * EXACT same queries instead of keeping its own literal copy (coordinator
 * review, second pass: "the verification script keeping its own literal
 * copy... means the proof can drift from the product"). This module has
 * no `server-only` import and takes its `pg.Pool` as a parameter rather
 * than importing `@/lib/payload`'s `cityPool()` — `payload.ts` pulls in
 * the full CMS collection config at its own top level, which is what
 * blocked the verify script from importing `recommend.ts` directly in
 * the first pass (see that script's earlier header comment, now moot).
 * `recommend.ts` passes `cityPool()`; the verify script passes its own
 * bare `pg.Pool` — both get identical queries either way.
 *
 * ## Second-pass changes from the first version
 *
 * - **Hidden-rival guard is precomputed** (`engine.hidden_rival_flags`,
 *   migration 0009, populated by `now_filters.hidden_rival_recompute`
 *   offline) rather than a live `place_mentions`/`places` regex join.
 *   `EXPLAIN (ANALYZE, BUFFERS)` against real `now_bali` data showed the
 *   live join costing ~27ms of a ~49ms query; the precomputed lookup
 *   against a few-hundred-row table costs under 1ms. Measured before/
 *   after for the whole Read Next query: ~49ms -> ~22ms warm (single
 *   request, real data, ticket report has the full numbers).
 * - **Complement rails are ONE query**, not one per section (up to 4
 *   round trips before). Section grouping and the 3-rail cap happen in
 *   JS afterward.
 * - **A title-based hidden-rival signal** exists now too (`stay` only,
 *   measured — see `lib/hiddenRival.ts` and the ticket report), also
 *   precomputed into the same table.
 * - **Cross-rail dedup**: no article may appear in more than one rail on
 *   one page, complement rails included Read Next.
 */

import type pg from 'pg'

import { excludedTypesFor, relationsFromRows, type TypeRelations } from './competitorPolicy.ts'

/**
 * L1 `type` -> section, duplicated from `lib/payload.ts#TYPE_TO_SECTION`
 * rather than imported from it: `payload.ts` imports `@now-engine/cms
 * /payload.config` at its own top level (the whole CMS collection config),
 * which is exactly the import chain `scripts/verify-competitor-policy.mjs`
 * cannot load outside a `payload run` process (see that script's header
 * comment) — the entire point of this module existing separately is to be
 * loadable without it. This is a small, stable data map (8 entries, the §4
 * type tree), not the SQL this file exists to de-duplicate; if it drifts
 * from `payload.ts`'s copy a page's section links and this file's rail
 * grouping would disagree, which `apps/web`'s own typecheck/tests would
 * not catch today — flagged as a residual risk, not solved here.
 */
const TYPE_TO_SECTION: Record<string, string> = {
  eat: 'dining',
  drink: 'dining',
  stay: 'stay',
  wellness: 'wellness',
  do: 'things-to-do',
  shop: 'things-to-do',
  event: 'events',
  editorial: 'editorial',
}

function sectionForType(primaryType: string | null | undefined): string | null {
  if (!primaryType) return null
  return TYPE_TO_SECTION[primaryType] ?? null
}

export type CandidateRow = {
  id: number
  primary_type: string | null
  series_key: string | null
}

export const EMBEDDING_MODEL = 'BAAI/bge-small-en-v1.5'
// ARCHITECTURE.md §8.A "Quality floor" / now_quality.scoring.QUALITY_FLOOR —
// kept as the same literal the Python engine uses (see that module's
// docstring for the derivation); duplicated here because this is a
// TypeScript process with no access to the Python package.
export const QUALITY_FLOOR = 0.35

export const MAX_PER_SECTION = 2 // Sec.8.D diversity cap, "max 2 per format" analogue applied to section here
export const MAX_PLAN_AROUND_RAILS = 3 // coordinator review, second pass

type Pool = Pick<pg.Pool, 'query'>

// ---------------------------------------------------------------------------
// engine.type_relations
// ---------------------------------------------------------------------------

const RELATIONS_SQL = `SELECT type, exclude_same, complements, competes_with FROM engine.type_relations`

export async function loadRelations(pool: Pool): Promise<TypeRelations> {
  const { rows } = await pool.query<{
    type: string
    exclude_same: boolean
    complements: string[] | null
    competes_with: string[] | null
  }>(RELATIONS_SQL)
  return relationsFromRows(rows)
}

// ---------------------------------------------------------------------------
// Read Next — semantic similarity (Row 3's job)
// ---------------------------------------------------------------------------

// `eligible` is MATERIALIZED so the hard-filter predicates (status/type/
// hidden-rival/quality) are computed ONCE, as a set, before the vector
// join runs against it — Sec.8.G's own ordering rule ("push the cheap,
// selective predicates into SQL ahead of the expensive operation"),
// applied here as an explicit materialization boundary rather than left
// to the planner to discover. `el.primary_type`/`el.series_key` are
// carried through this CTE rather than re-joining `articles` a second
// time for the final SELECT.
const READ_NEXT_SQL = `
  WITH subj AS (
    SELECT vec FROM engine.embeddings
     WHERE entity_type = 'article' AND entity_id = $1::text AND model = $2
  ),
  eligible AS MATERIALIZED (
    SELECT a.id, a.primary_type::text AS primary_type, a.series_key
      FROM public.articles a
     WHERE a.id != $1::int
       AND a._status = 'published'
       AND a.published_at IS NOT NULL AND a.published_at <= now()
       -- Competitor exclusion (ARCHITECTURE §8.A): empty excluded-array
       -- means "this subject excludes nothing" (editorial/do/event, or
       -- none at all), in which case NO predicate is applied, including
       -- for NULL primary_type rows — matching now_filters.hard's own
       -- "if excluded:" guard exactly.
       AND (
         cardinality($3::text[]) = 0
         OR (a.primary_type IS NOT NULL AND a.primary_type::text != ALL($3::text[]))
       )
       -- Hidden-rival guard (precomputed — see module docstring): reuses
       -- the SAME excluded-types array, a matched_type is only ever a
       -- risk when it names a type the subject already excludes.
       AND (
         cardinality($3::text[]) = 0
         OR NOT EXISTS (
           SELECT 1 FROM engine.hidden_rival_flags hrf
            WHERE hrf.article_id = a.id::text AND hrf.matched_type = ANY($3::text[])
         )
       )
       AND a.id NOT IN (
         SELECT entity_id::int FROM engine.quality_scores
          WHERE entity_type = 'article' AND score < $4
       )
  )
  SELECT e.entity_id::int AS id, el.primary_type, el.series_key
    FROM eligible el
    JOIN engine.embeddings e ON e.entity_type = 'article' AND e.entity_id = el.id::text AND e.model = $2
   CROSS JOIN subj
   ORDER BY e.vec <=> subj.vec ASC
   LIMIT $5
`

export async function resolveReadNextCandidates(
  pool: Pool,
  articleId: number,
  subjectPrimaryType: string | null,
  relations: TypeRelations,
  limit: number,
): Promise<CandidateRow[]> {
  const excluded = Array.from(excludedTypesFor(relations, subjectPrimaryType))
  try {
    const result = await pool.query<CandidateRow>(READ_NEXT_SQL, [articleId, EMBEDDING_MODEL, excluded, QUALITY_FLOOR, limit])
    return result.rows
  } catch (error) {
    // The rail is a nicety; the article is not. A missing partition, an
    // embeddings backfill not yet run for this article, or the city pool
    // being cold must not 500 the page under it — same stance
    // `lib/content.ts#getMostRead` already takes for its own direct query.
    console.error('[recommendSql] Read Next query failed:', error instanceof Error ? error.message : error)
    return []
  }
}

/** Series dedup (Sec.8.A "one per series_key") — applied HERE, at the
 * CandidateRow level, because `series_key` does not survive the Payload
 * round trip (`lib/content.ts#Article` carries no such field). Rows
 * arrive already ordered by relevance, so keeping the FIRST occurrence
 * per key keeps the best-ranked row in each group. */
export function dedupeBySeries(rows: CandidateRow[]): CandidateRow[] {
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

/** Greedy diversification: walk the ordered pool and cap how many of one
 * section survive — a simplified stand-in for `now_blender.mmr`'s real
 * MMR pass (no embedding pairwise-similarity comparison here), documented
 * as such rather than silently claiming the same guarantee. `excludeIds`
 * is the cross-rail dedup set (coordinator review, second pass: "no
 * story may appear in more than one rail on the same page"). */
export function diversify(pool: CandidateRow[], limit: number, excludeIds: ReadonlySet<number> = new Set()): CandidateRow[] {
  const picked: CandidateRow[] = []
  const perSection = new Map<string, number>()
  for (const row of pool) {
    if (picked.length >= limit) break
    if (excludeIds.has(row.id)) continue
    const section = sectionForType(row.primary_type) ?? 'unclassified'
    const count = perSection.get(section) ?? 0
    if (count >= MAX_PER_SECTION) continue
    picked.push(row)
    perSection.set(section, count + 1)
  }
  return picked
}

// ---------------------------------------------------------------------------
// "Plan around it" — Row 1's job (complementary types), ONE batched query
// ---------------------------------------------------------------------------

const SECTION_RAIL_LABELS: Record<string, { kicker: string; title: string }> = {
  stay: { kicker: 'Plan around it', title: 'Where to Stay' },
  dining: { kicker: 'Plan around it', title: 'Where to Eat & Drink' },
  wellness: { kicker: 'Plan around it', title: 'Where to Unwind' },
  'things-to-do': { kicker: 'Plan around it', title: 'Things to Do Nearby' },
  events: { kicker: 'Plan around it', title: "What's On" },
}

/**
 * The subject's `complements`, grouped by SECTION, in the order sections
 * FIRST APPEAR walking `complements` — this IS the rail priority
 * (coordinator review: "put that priority order in data ... the
 * complements order itself, your call, documented" — see now-db migration
 * 0010, which reordered `engine.type_relations.complements` for exactly
 * this reason, same membership as before, only array position changed).
 * Capped to `MAX_PLAN_AROUND_RAILS` distinct sections. `[]` for a
 * non-venue subject (`relations[type].excludeSame` false, or
 * unclassified) — "plan around it" is a venue-story feature.
 */
export function complementSectionsFor(
  subjectType: string | null,
  relations: TypeRelations,
): { section: string; types: string[]; label: { kicker: string; title: string } }[] {
  if (!subjectType) return []
  const relation = relations[subjectType]
  if (!relation || !relation.excludeSame) return []

  const bySection = new Map<string, string[]>()
  const order: string[] = []
  for (const complementType of relation.complements) {
    const section = sectionForType(complementType)
    if (!section) continue
    if (!bySection.has(section)) order.push(section)
    const list = bySection.get(section) ?? []
    list.push(complementType)
    bySection.set(section, list)
  }

  const out: { section: string; types: string[]; label: { kicker: string; title: string } }[] = []
  for (const section of order) {
    if (out.length >= MAX_PLAN_AROUND_RAILS) break
    const label = SECTION_RAIL_LABELS[section]
    const types = bySection.get(section)
    if (!types || types.length === 0 || !label) continue
    out.push({ section, types, label })
  }
  return out
}

export type ComplementCandidateRow = CandidateRow & { same_area: boolean }

// ONE query for every complement type across every eligible section — a
// single `primary_type = ANY(:all_types)` restriction, area preference
// and per-section slicing happen in JS (`groupComplementCandidatesBySection`).
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
     AND NOT EXISTS (
       SELECT 1 FROM engine.hidden_rival_flags hrf
        WHERE hrf.article_id = a.id::text AND hrf.matched_type = ANY($2::text[])
     )
     AND a.id NOT IN (
       SELECT entity_id::int FROM engine.quality_scores
        WHERE entity_type = 'article' AND score < $3
     )
   ORDER BY same_area DESC, a.published_at DESC
   LIMIT $4
`

/** All complement candidates for every eligible section, in one round
 * trip. `poolPerSection` bounds how many rows come back per TYPE (not
 * per section) worth over-fetching — sections are sliced down to
 * `limitPerRail` afterward by `groupComplementCandidatesBySection`. */
export async function resolveComplementCandidates(
  pool: Pool,
  articleId: number,
  sections: { section: string; types: string[] }[],
  poolSize: number,
): Promise<ComplementCandidateRow[]> {
  const allTypes = Array.from(new Set(sections.flatMap((s) => s.types)))
  if (allTypes.length === 0) return []
  try {
    const result = await pool.query<ComplementCandidateRow>(COMPLEMENT_SQL, [articleId, allTypes, QUALITY_FLOOR, poolSize])
    return result.rows
  } catch (error) {
    console.error('[recommendSql] complement query failed:', error instanceof Error ? error.message : error)
    return []
  }
}

/** Slices the ONE batched complement result set into per-section groups,
 * applying series dedup, the cross-rail `excludeIds` set and
 * `limitPerRail`, in the SQL's own order (same_area desc, recency desc). */
export function groupComplementCandidatesBySection(
  rows: ComplementCandidateRow[],
  sections: { section: string; types: string[] }[],
  limitPerRail: number,
  excludeIds: ReadonlySet<number>,
): Map<string, ComplementCandidateRow[]> {
  const typeToSection = new Map<string, string>()
  for (const s of sections) for (const t of s.types) typeToSection.set(t, s.section)

  const deduped = dedupeBySeries(rows) as ComplementCandidateRow[]
  const used = new Set(excludeIds)
  const out = new Map<string, ComplementCandidateRow[]>()
  for (const s of sections) out.set(s.section, [])

  for (const row of deduped) {
    if (used.has(row.id)) continue
    const section = row.primary_type ? typeToSection.get(row.primary_type) : undefined
    if (!section) continue
    const bucket = out.get(section)
    if (!bucket || bucket.length >= limitPerRail) continue
    bucket.push(row)
    used.add(row.id) // an article can only ever be pushed into ONE section anyway (one primary_type), but guards belt-and-suspenders against a future type->section change making one type map to two sections
  }
  return out
}

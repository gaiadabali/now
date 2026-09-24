/**
 * The competitor-exclusion POLICY (ARCHITECTURE §4/§8.A), reimplemented
 * here so the article page can enforce it even when the engine API is
 * down or unconfigured (`recommend.ts`'s own contract — see that file).
 *
 * This is a direct, line-for-line port of `now_filters.type_relations`
 * (`engine/packages/filters/src/now_filters/type_relations.py`), which
 * remains the canonical implementation. Two independent copies of a
 * commercial "never violated" rule (§8.A) would drift the moment one of
 * them changed and the other didn't, which is exactly why
 * `engine/packages/taxonomy/seed/competitor_conformance.json` exists:
 * both this file's test and the Python module's test load the SAME
 * vectors, so a policy change that is not mirrored on both sides fails
 * on whichever side was forgotten, immediately, in CI.
 *
 * Ranking (which candidates are chosen, and in what order) is allowed to
 * differ between the engine-api path and this fallback — the exclusion
 * POLICY may not (docs/EDITION-2-PLAN.md WS1 deliverable #3).
 */

export type TypeRelationRow = {
  type: string
  excludeSame: boolean
  complements: string[]
  /** Migration 0008 (2026-09-24): a second exclusion axis alongside
   * `excludeSame` — types this row's type must never co-recommend even
   * though they are a DIFFERENT L1 type (the owner's "F&B is one class"
   * rule: eat/drink). See the Python module's docstring for the full
   * reasoning; this field means the identical thing here. */
  competesWith: string[]
}

export type TypeRelations = Record<string, TypeRelationRow>

/**
 * The set of L1 types that must NEVER appear alongside `subjectType` on
 * its own page (ARCHITECTURE §8.A). Mirrors `now_filters.type_relations
 * .excluded_types_for` exactly:
 *
 * - `subjectType === null` (unclassified — F68): fails CLOSED to every
 *   `excludeSame` type, every one of THEIR `competesWith` entries, plus
 *   `'unknown'`. This is deliberately the most restrictive answer, a
 *   superset of every known venue subject's own excluded set.
 * - `subjectType === ''` or a type with no relation row: excludes
 *   nothing (a relation this policy has no data for cannot be judged).
 * - A known type with `excludeSame === false` (editorial-shaped:
 *   `editorial`/`do`/`event`): excludes nothing.
 * - A known type with `excludeSame === true` (venue-shaped): excludes
 *   itself, `'unknown'`, and every entry in its own `competesWith`.
 */
export function excludedTypesFor(relations: TypeRelations, subjectType: string | null): Set<string> {
  if (subjectType === null) {
    const excluded = new Set<string>()
    for (const relation of Object.values(relations)) {
      if (relation.excludeSame) excluded.add(relation.type)
    }
    for (const relation of Object.values(relations)) {
      if (relation.excludeSame) for (const c of relation.competesWith) excluded.add(c)
    }
    excluded.add('unknown')
    return excluded
  }
  if (!subjectType) return new Set()
  const relation = relations[subjectType]
  if (!relation) return new Set()
  if (!relation.excludeSame) return new Set()
  return new Set([subjectType, 'unknown', ...relation.competesWith])
}

/**
 * True if `candidateType` must be excluded from a rail built for
 * `subjectType`. Mirrors `now_filters.type_relations.is_competitor`: a
 * falsy/missing `candidateType` fails CLOSED whenever the subject
 * excludes anything at all (F73/F74 — an unidentifiable candidate cannot
 * be vouched for as safe for a guarantee this important), and is only
 * ever `false` when the subject itself excludes nothing.
 */
export function isCompetitor(
  relations: TypeRelations,
  subjectType: string | null,
  candidateType: string | null | undefined,
): boolean {
  const excluded = excludedTypesFor(relations, subjectType)
  if (excluded.size === 0) return false
  if (!candidateType) return true
  return excluded.has(candidateType)
}

/** Builds `TypeRelations` from `engine.type_relations` row shape (as
 * returned by a `SELECT type, exclude_same, complements, competes_with`). */
export function relationsFromRows(
  rows: { type: string; exclude_same: boolean; complements: string[] | null; competes_with: string[] | null }[],
): TypeRelations {
  const relations: TypeRelations = {}
  for (const r of rows) {
    relations[r.type] = {
      type: r.type,
      excludeSame: Boolean(r.exclude_same),
      complements: r.complements ?? [],
      competesWith: r.competes_with ?? [],
    }
  }
  return relations
}

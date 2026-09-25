import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import { excludedTypesFor, isCompetitor, relationsFromRows, type TypeRelations } from '../src/lib/competitorPolicy.ts'

// ---------------------------------------------------------------------------
// The ONE conformance-vector file both suites assert against
// (docs/EDITION-2-PLAN.md WS1 deliverable #3). The Python half is
// engine/packages/filters/tests/test_competitor_conformance_vectors.py —
// see that file's docstring for why the two must never diverge.
//
// Both files load from `engine/packages/taxonomy/seed/`, the same seed
// directory `now-db`'s migration runner seeds every city database from
// (ARCHITECTURE.md §2) — not a second, web-app-local copy of the matrix.
// ---------------------------------------------------------------------------

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SEED_DIR = path.resolve(__dirname, '../../../packages/taxonomy/seed')

type SeedRelation = { type: string; exclude_same: boolean; complements: string[]; competes_with?: string[] }

function loadRelationsFromSeed(): TypeRelations {
  const doc = JSON.parse(readFileSync(path.join(SEED_DIR, 'type_relations.json'), 'utf-8')) as {
    relations: SeedRelation[]
  }
  return relationsFromRows(
    doc.relations.map((r) => ({
      type: r.type,
      exclude_same: r.exclude_same,
      complements: r.complements,
      competes_with: r.competes_with ?? [],
    })),
  )
}

type Vector = { subject_type: string | null; candidate_type: string | null; expect_excluded: boolean; note?: string }

function loadVectors(): Vector[] {
  const doc = JSON.parse(readFileSync(path.join(SEED_DIR, 'competitor_conformance.json'), 'utf-8')) as {
    vectors: Vector[]
  }
  return doc.vectors
}

test('the seed directory is reachable and both conformance files parse', () => {
  const relations = loadRelationsFromSeed()
  assert.ok(Object.keys(relations).length >= 8, 'expected the 9-row §4 matrix (8+unknown) to load')
  const vectors = loadVectors()
  assert.ok(vectors.length >= 15, 'conformance file looks empty or truncated')
})

test('every conformance vector agrees with the TS policy implementation', () => {
  const relations = loadRelationsFromSeed()
  const vectors = loadVectors()
  const failures: string[] = []
  for (const v of vectors) {
    const got = isCompetitor(relations, v.subject_type, v.candidate_type)
    if (got !== v.expect_excluded) {
      failures.push(
        `subject=${v.subject_type} candidate=${v.candidate_type}: expected excluded=${v.expect_excluded}, got ${got} (${v.note ?? ''})`,
      )
    }
  }
  assert.deepEqual(failures, [])
})

// ---------------------------------------------------------------------------
// Direct unit checks, independent of the conformance file, for the two
// axes this module adds beyond a bare port (documentation-by-test).
// ---------------------------------------------------------------------------

test('eat and drink are one competitive class (migration 0008)', () => {
  const relations = loadRelationsFromSeed()
  assert.equal(isCompetitor(relations, 'eat', 'drink'), true)
  assert.equal(isCompetitor(relations, 'drink', 'eat'), true)
  assert.equal(isCompetitor(relations, 'eat', 'stay'), false)
})

test('subjectType=null fails closed to every venue type plus unknown (F68)', () => {
  const relations = loadRelationsFromSeed()
  const excluded = excludedTypesFor(relations, null)
  assert.equal(excluded.has('stay'), true)
  assert.equal(excluded.has('eat'), true)
  assert.equal(excluded.has('drink'), true)
  assert.equal(excluded.has('wellness'), true)
  assert.equal(excluded.has('shop'), true)
  assert.equal(excluded.has('unknown'), true)
  assert.equal(excluded.has('editorial'), false)
  assert.equal(excluded.has('do'), false)
  assert.equal(excluded.has('event'), false)
})

test('an unidentifiable candidate fails closed only when the subject excludes something (F73)', () => {
  const relations = loadRelationsFromSeed()
  assert.equal(isCompetitor(relations, 'stay', null), true)
  assert.equal(isCompetitor(relations, 'stay', undefined), true)
  assert.equal(isCompetitor(relations, 'do', null), false)
  assert.equal(isCompetitor(relations, 'editorial', null), false)
})

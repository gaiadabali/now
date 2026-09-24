import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import { relationsFromRows, type TypeRelations } from '../src/lib/competitorPolicy.ts'
import {
  complementSectionsFor,
  dedupeBySeries,
  diversify,
  groupComplementCandidatesBySection,
  MAX_PLAN_AROUND_RAILS,
  meetsReadersAlsoReadFloor,
  MIN_READERS_ALSO_READ,
  type CandidateRow,
  type ComplementCandidateRow,
} from '../src/lib/recommendSql.ts'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SEED_DIR = path.resolve(__dirname, '../../../packages/taxonomy/seed')

function loadRealRelations(): TypeRelations {
  const doc = JSON.parse(readFileSync(path.join(SEED_DIR, 'type_relations.json'), 'utf-8')) as {
    relations: { type: string; exclude_same: boolean; complements: string[]; competes_with?: string[] }[]
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

// ---------------------------------------------------------------------------
// complementSectionsFor — rail priority, driven by now-db migration 0010's
// reordered `complements` (real seed data, not a synthetic fixture)
// ---------------------------------------------------------------------------

test('a stay subject prioritises dining, then things-to-do, then wellness', () => {
  const relations = loadRealRelations()
  const sections = complementSectionsFor('stay', relations)
  assert.deepEqual(
    sections.map((s) => s.section),
    ['dining', 'things-to-do', 'wellness'],
  )
})

test('an eat subject prioritises stay, then things-to-do, then events (wellness drops out of the top 3)', () => {
  const relations = loadRealRelations()
  const sections = complementSectionsFor('eat', relations)
  assert.deepEqual(
    sections.map((s) => s.section),
    ['stay', 'things-to-do', 'events'],
  )
})

test('never more than MAX_PLAN_AROUND_RAILS sections, even for a subject with many complement sections', () => {
  const relations: TypeRelations = {
    stay: { type: 'stay', excludeSame: true, complements: ['eat', 'wellness', 'do', 'event'], competesWith: [] },
    eat: { type: 'eat', excludeSame: true, complements: [], competesWith: [] },
    wellness: { type: 'wellness', excludeSame: true, complements: [], competesWith: [] },
    do: { type: 'do', excludeSame: false, complements: [], competesWith: [] },
    event: { type: 'event', excludeSame: false, complements: [], competesWith: [] },
  }
  const sections = complementSectionsFor('stay', relations)
  assert.equal(sections.length, MAX_PLAN_AROUND_RAILS)
  assert.deepEqual(
    sections.map((s) => s.section),
    ['dining', 'wellness', 'things-to-do'],
  )
})

test('a non-venue or unclassified subject gets no plan-around sections', () => {
  const relations = loadRealRelations()
  assert.deepEqual(complementSectionsFor('event', relations), [])
  assert.deepEqual(complementSectionsFor('editorial', relations), [])
  assert.deepEqual(complementSectionsFor(null, relations), [])
})

// ---------------------------------------------------------------------------
// dedupeBySeries / diversify / groupComplementCandidatesBySection
// ---------------------------------------------------------------------------

function row(id: number, primaryType: string | null, seriesKey: string | null = null): CandidateRow {
  return { id, primary_type: primaryType, series_key: seriesKey }
}

test('dedupeBySeries keeps only the first (best-ranked) row per series_key', () => {
  const rows = [row(1, 'eat', 'series-a'), row(2, 'eat', 'series-a'), row(3, 'eat', null)]
  const deduped = dedupeBySeries(rows)
  assert.deepEqual(
    deduped.map((r) => r.id),
    [1, 3],
  )
})

test('diversify respects excludeIds — the cross-rail "no story twice" rule', () => {
  const rows = [row(1, 'eat'), row(2, 'eat'), row(3, 'stay'), row(4, 'stay')]
  const picked = diversify(rows, 10, new Set([1, 3]))
  assert.deepEqual(
    picked.map((r) => r.id),
    [2, 4],
  )
})

test('diversify caps at MAX_PER_SECTION per section even with excludeIds empty', () => {
  const rows = [row(1, 'eat'), row(2, 'eat'), row(3, 'eat'), row(4, 'stay')]
  const picked = diversify(rows, 10)
  // at most 2 'dining'-section (eat) items survive
  assert.deepEqual(
    picked.map((r) => r.id),
    [1, 2, 4],
  )
})

function complementRow(id: number, primaryType: string, sameArea: boolean, seriesKey: string | null = null): ComplementCandidateRow {
  return { id, primary_type: primaryType, series_key: seriesKey, same_area: sameArea }
}

test('groupComplementCandidatesBySection buckets by section, respects limitPerRail and excludeIds', () => {
  const sections = [
    { section: 'dining', types: ['eat', 'drink'] },
    { section: 'things-to-do', types: ['do', 'shop'] },
  ]
  const rows = [
    complementRow(1, 'eat', true),
    complementRow(2, 'drink', true),
    complementRow(3, 'eat', false),
    complementRow(4, 'do', true),
    complementRow(5, 'shop', false),
  ]
  const grouped = groupComplementCandidatesBySection(rows, sections, 2, new Set([3]))
  assert.deepEqual(
    grouped.get('dining')?.map((r) => r.id),
    [1, 2], // id 3 excluded via excludeIds
  )
  assert.deepEqual(
    grouped.get('things-to-do')?.map((r) => r.id),
    [4, 5],
  )
})

test('groupComplementCandidatesBySection never puts one article in two sections', () => {
  const sections = [
    { section: 'dining', types: ['eat'] },
    { section: 'stay', types: ['stay'] },
  ]
  // Same id appears twice in the input (a defensive case — the real SQL
  // can't produce this since `a.id` is a primary key, but the function
  // must not misbehave if it ever did).
  const rows = [complementRow(1, 'eat', true), complementRow(1, 'stay', true)]
  const grouped = groupComplementCandidatesBySection(rows, sections, 6, new Set())
  const totalPlacements = Array.from(grouped.values()).reduce((sum, r) => sum + r.length, 0)
  assert.equal(totalPlacements, 1)
})

// ---------------------------------------------------------------------------
// meetsReadersAlsoReadFloor — S2 honesty rule applied to a rail's existence
// (WS1, fourth pass, item 4): fewer than MIN_READERS_ALSO_READ qualifying
// items and the rail must not render at all, never padded to a round number.
// ---------------------------------------------------------------------------

test(`meetsReadersAlsoReadFloor is false below ${MIN_READERS_ALSO_READ} qualifying items`, () => {
  assert.equal(meetsReadersAlsoReadFloor(0), false)
  assert.equal(meetsReadersAlsoReadFloor(MIN_READERS_ALSO_READ - 1), false)
})

test(`meetsReadersAlsoReadFloor is true at exactly ${MIN_READERS_ALSO_READ} and above`, () => {
  assert.equal(meetsReadersAlsoReadFloor(MIN_READERS_ALSO_READ), true)
  assert.equal(meetsReadersAlsoReadFloor(MIN_READERS_ALSO_READ + 5), true)
})

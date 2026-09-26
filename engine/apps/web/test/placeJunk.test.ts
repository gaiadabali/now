import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'

import { classifyPlaceName, normalizeFull } from '../src/lib/placeJunk.ts'

/**
 * The desk's junk badge must say exactly what `now-places triage` says.
 *
 * `junk_golden.jsonl` is written by the Python rules
 * (engine/packages/place-catalogue/scripts/build_junk_golden.py): 440 names,
 * every one of the four hand-labelled fixtures plus edge probes, each with
 * the Python tier and reason. This test fails on the first name the
 * TypeScript port classifies differently, so a change to one implementation
 * cannot ship without the other.
 */

const FIXTURES = path.resolve(import.meta.dirname, '../../../packages/place-catalogue/tests/fixtures')

const phrases = JSON.parse(readFileSync(path.join(FIXTURES, 'junk_area_phrases.json'), 'utf8')) as {
  areaPhrases: string[]
  supplementary: string[]
}
const NON_VENUE = new Set([...phrases.areaPhrases, ...phrases.supplementary])

const golden = readFileSync(path.join(FIXTURES, 'junk_golden.jsonl'), 'utf8')
  .split('\n')
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l) as { name: string; tier: 'junk' | 'suspect' | null; reason: string | null })

test('the golden file is the size the Python suite expects', () => {
  assert.ok(golden.length >= 400, `only ${golden.length} golden rows`)
})

test('every golden verdict is reproduced exactly (tier and reason)', () => {
  const mismatches: string[] = []
  for (const row of golden) {
    const v = classifyPlaceName(row.name, NON_VENUE)
    if (v.tier !== row.tier || v.reason !== row.reason) {
      mismatches.push(`${JSON.stringify(row.name)}: python=${row.tier}/${row.reason} ts=${v.tier}/${v.reason}`)
    }
  }
  assert.deepEqual(mismatches.slice(0, 15), [])
})

test('normalizeFull matches the extractor', () => {
  assert.equal(normalizeFull('New Year’s Eve'), 'new years eve')
  assert.equal(normalizeFull('  Café  del-Mar! '), 'cafe del mar')
})

test('Unicode word boundaries behave like Python', () => {
  // "é" is a word character in Python's re; JS's bare \b would split on it.
  assert.equal(classifyPlaceName('Caféfest Lounge', NON_VENUE).tier, null)
  assert.equal(classifyPlaceName('Café Fest', NON_VENUE).tier, 'junk')
})

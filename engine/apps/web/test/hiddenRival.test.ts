import assert from 'node:assert/strict'
import { test } from 'node:test'

import { relationsFromRows } from '../src/lib/competitorPolicy.ts'
import { buildNamePattern, hiddenRivalPatternForSubject, loadSubtypeLexicon } from '../src/lib/hiddenRival.ts'

test('the real type.json produces a stay lexicon containing resort and hotel', () => {
  const lexicon = loadSubtypeLexicon()
  assert.ok(lexicon.stay.includes('resort'))
  assert.ok(lexicon.stay.includes('hotel'))
  assert.ok(lexicon.stay.includes('villa'))
})

test('bare club is excluded from the drink lexicon but beach club and lounge survive', () => {
  const lexicon = loadSubtypeLexicon()
  assert.ok(!lexicon.drink.includes('club'))
  assert.ok(lexicon.drink.includes('beach club'))
  assert.ok(lexicon.drink.includes('lounge'))
})

test('westin resort name matches the stay pattern; unrelated text does not', () => {
  const pattern = buildNamePattern(['stay'])
  assert.ok(pattern)
  const re = new RegExp(pattern!.replaceAll('\\y', '\\b'), 'i')
  assert.ok(re.test('The Westin Resort Nusa Dua'))
  assert.ok(!re.test('Celebrate Wellness 2026'))
})

test('word boundary prevents club-adjacent false positives after curation', () => {
  const pattern = buildNamePattern(['drink'])
  assert.ok(pattern)
  const re = new RegExp(pattern!.replaceAll('\\y', '\\b'), 'i')
  assert.ok(!re.test('Royale Jakarta Golf Club'))
  assert.ok(re.test('Potato Head Beach Club'))
})

test('hiddenRivalPatternForSubject uses excludedTypesFor, including competes_with', () => {
  const relations = relationsFromRows([
    { type: 'stay', exclude_same: true, complements: [], competes_with: ['do'] },
    { type: 'do', exclude_same: false, complements: [], competes_with: [] },
  ])
  const pattern = hiddenRivalPatternForSubject('stay', relations)
  assert.ok(pattern)
  const re = new RegExp(pattern!.replaceAll('\\y', '\\b'), 'i')
  assert.ok(re.test('City Museum Jakarta'))
})

test('editorial-shaped subjects get no pattern', () => {
  const relations = relationsFromRows([{ type: 'event', exclude_same: false, complements: ['eat'], competes_with: [] }])
  assert.equal(hiddenRivalPatternForSubject('event', relations), null)
  assert.equal(hiddenRivalPatternForSubject(null, {}), null)
})

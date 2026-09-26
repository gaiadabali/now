import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  aliasNames,
  approvalCheck,
  buildRegionIndex,
  compareRanked,
  duplicateKey,
  evidenceScore,
  mergeEntry,
  regionVerdict,
} from '../src/lib/placeDeskRules.ts'

/**
 * The place desk's pure rules (plan P1.6). The score's worked examples are
 * the same ones `now-places` pins in
 * engine/packages/place-catalogue/tests/test_rank_triage_dedupe.py, so the
 * desk's queue and the CLI's report put places in the same order.
 */

const NOW = new Date('2026-09-26T00:00:00Z')

test('queue score matches the CLI worked examples', () => {
  assert.equal(evidenceScore(0, 0, false, null, NOW), 0)
  assert.equal(evidenceScore(2, 5, false, null, NOW), 11)
  assert.equal(evidenceScore(2, 5, true, null, NOW), 13)
  assert.equal(evidenceScore(1, 1, false, NOW, NOW), 5)
  const half = new Date(NOW.getTime() - (1825 / 2) * 86_400_000)
  assert.ok(Math.abs(evidenceScore(1, 1, false, half, NOW) - 4.5) < 1e-9)
  assert.equal(evidenceScore(0, 0, false, new Date(NOW.getTime() - 4000 * 86_400_000), NOW), 0)
})

test('ties break on featured, then stories, then the older id', () => {
  const rows = [
    { id: 3, score: 6, featured: 1, articles: 3 },
    { id: 1, score: 6, featured: 2, articles: 0 },
    { id: 2, score: 6, featured: 1, articles: 3 },
  ]
  assert.deepEqual(rows.sort(compareRanked).map((r) => r.id), [1, 2, 3])
})

test('a place cannot be approved untyped, merged or twice', () => {
  const base = { status: 'pending_review', mergedInto: null, type: 'eat', subtype: 'restaurant' }
  assert.deepEqual(approvalCheck(base), { ok: true })
  assert.equal(approvalCheck({ ...base, type: 'editorial' }).ok, false)
  assert.equal(approvalCheck({ ...base, type: 'unknown' }).ok, false)
  assert.equal(approvalCheck({ ...base, subtype: 'city-guide' }).ok, false)
  assert.equal(approvalCheck({ ...base, mergedInto: 9 }).ok, false)
  assert.equal(approvalCheck({ ...base, status: 'active' }).ok, false)
})

test('the merge audit entry has the CLI shape and carries names forward', () => {
  const entry = mergeEntry({
    loser: { id: 12, name: 'Karma Kandara Resort', aliases: [{ name: 'Karma Kandara Bali', placeId: 11, inheritedAliases: ['KK'] }] },
    mentionIds: [30, 10, 20],
    repointedPlaceIds: [11],
    by: 'desk:3 editor@example.test',
    at: NOW,
  })
  assert.deepEqual(entry, {
    name: 'Karma Kandara Resort',
    placeId: 12,
    mergedAt: '2026-09-26T00:00:00.000Z',
    by: 'desk:3 editor@example.test',
    score: null,
    mentionIds: [10, 20, 30],
    repointedPlaceIds: [11],
    inheritedAliases: ['Karma Kandara Bali', 'KK'],
  })
  assert.deepEqual(aliasNames([entry, 'Plain name']), ['Karma Kandara Resort', 'Karma Kandara Bali', 'KK', 'Plain name'])
})

test('duplicate key skips generic words and the site name', () => {
  assert.equal(duplicateKey('The Westin Resort Nusa Dua', []), 'westin')
  assert.equal(duplicateKey('Metropolis Hotel Downtown', ['metropolis']), 'downtown')
  assert.equal(duplicateKey('The Hotel', []), 'the')
  assert.equal(duplicateKey('Au', []), null)
})

test('region check: a name pointing at another region is flagged, a mixed one is not', () => {
  const index = buildRegionIndex([
    { slug: 'indonesia', label: 'Indonesia', parent: null },
    { slug: 'metro', label: 'Metro', parent: 'indonesia' },
    { slug: 'harbour-side', label: 'Harbour Side', parent: 'metro' },
    { slug: 'island', label: 'Island', parent: 'indonesia' },
    { slug: 'coral-bay', label: 'Coral Bay', parent: 'island' },
    { slug: 'international', label: 'International', parent: null },
    { slug: 'europe', label: 'Europe', parent: 'international' },
  ])
  assert.deepEqual(regionVerdict('Coral Bay Beach Club', index, 'metro'), { outOfRegion: true, region: 'island', matched: 'Coral Bay' })
  assert.equal(regionVerdict('Coral Bay Beach Club', index, 'island').outOfRegion, false)
  assert.equal(regionVerdict('Harbour Side Grill, Coral Bay', index, 'metro').outOfRegion, false)
  assert.equal(regionVerdict('Grand Europe Hotel', index, 'metro').region, 'international')
  assert.equal(regionVerdict('Indonesia Kitchen', index, 'metro').outOfRegion, false)
})

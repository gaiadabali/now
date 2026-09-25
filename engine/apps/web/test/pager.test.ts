import assert from 'node:assert/strict'
import { test } from 'node:test'

import { pageNodes, pagerSummary } from '../src/lib/pager.ts'

// ---------------------------------------------------------------------------
// pageNodes — the windowing, mirrored from @payloadcms/ui's own Pagination
// ---------------------------------------------------------------------------

test('shows every page when there are few enough of them', () => {
  assert.deepEqual(pageNodes(1, 1), [1])
  assert.deepEqual(pageNodes(1, 3), [1, 2, 3])
  assert.deepEqual(pageNodes(2, 3), [1, 2, 3])
  assert.deepEqual(pageNodes(3, 3), [1, 2, 3])
})

test('windows around the current page with no separator for a one-page gap', () => {
  // Page 2 of 4: neighbours are 1 and 3, and 4 is only one past the window —
  // no separator earns its place over just showing the page.
  assert.deepEqual(pageNodes(2, 4), [1, 2, 3, 4])
})

test('adds a separator only where it actually skips more than one page', () => {
  // Review desk's own case: page 1 of 14 clusters-pages.
  assert.deepEqual(pageNodes(1, 14), [1, 2, 'sep', 14])
  // Deep in the middle: both sides get a separator.
  assert.deepEqual(pageNodes(7, 14), [1, 'sep', 6, 7, 8, 'sep', 14])
  // Last page: only the left separator applies.
  assert.deepEqual(pageNodes(14, 14), [1, 'sep', 13, 14])
})

test('orgs list case: 32 pages, page 2', () => {
  assert.deepEqual(pageNodes(2, 32), [1, 2, 3, 'sep', 32])
})

// ---------------------------------------------------------------------------
// pagerSummary — the "Showing X–Y of Z" line
// ---------------------------------------------------------------------------

test('summarises a full page', () => {
  assert.equal(pagerSummary(1, 50, 1562), 'Showing 1–50 of 1,562')
  assert.equal(pagerSummary(2, 50, 1562), 'Showing 51–100 of 1,562')
})

test('clips the last page at the true total, not a round page size', () => {
  assert.equal(pagerSummary(32, 50, 1562), 'Showing 1,551–1,562 of 1,562')
})

test('reports zero plainly rather than "Showing 1–0 of 0"', () => {
  assert.equal(pagerSummary(1, 50, 0), 'Showing 0')
})

test('a single-page result never crosses the total', () => {
  assert.equal(pagerSummary(1, 25, 25), 'Showing 1–25 of 25')
  assert.equal(pagerSummary(1, 50, 3), 'Showing 1–3 of 3')
})

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { canManagePartners, canWritePartnershipForSite } from '../src/lib/commerceAccess.ts'
import type { CommerceRoleUser } from '../src/lib/commerceAccess.ts'

/**
 * S5.2's access-rule tests — docs/SURFACES-PLAN.md §6: "the tests are the
 * deliverable there, as they were in ADMIN-CONSOLIDATION Phase 1."
 *
 * Deliberately exercises the PURE predicates (`canWritePartnershipForSite`,
 * `canManagePartners`) rather than the Next-wrapped `requireCommerceWriter`/
 * server actions in `commerce/orgs/[id]/partnerships/actions.ts` — those call
 * `payload.auth()` and `redirect()`, which need a real Next.js request
 * context this repo's `node --test` runner does not provide (see
 * `test/html.test.ts` for the same style: plain logic, no framework). The
 * predicates are where the actual site-scoping DECISION lives; the wrapper
 * around them is a thin, mechanical "call this, and redirect if it says no"
 * that has no branch of its own left to get wrong. Same split `lib/auth.ts`
 * already uses for `canReviewClassification` vs `requireReviewerAccess`.
 *
 * The four cases the ticket asks for, each named to match:
 */

const commerceAdmin: CommerceRoleUser = { commerceRole: 'admin' }
const partnerManager: CommerceRoleUser = { commerceRole: 'partner_manager' }
const viewer: CommerceRoleUser = { commerceRole: 'viewer' }
const author: CommerceRoleUser = { commerceRole: 'none' } // editorial 'author' has no commerce role

test('an author cannot write a partnership, on any site', () => {
  assert.equal(canManagePartners(author), false)
  assert.equal(canWritePartnershipForSite(author, 'bali', 'bali'), false)
  assert.equal(canWritePartnershipForSite(author, 'bali', 'jakarta'), false)
})

test('a viewer cannot write a partnership either — reading is not writing', () => {
  assert.equal(canManagePartners(viewer), false)
  assert.equal(canWritePartnershipForSite(viewer, 'bali', 'bali'), false)
})

test('a partner_manager scoped to one site cannot write another site\'s rows', () => {
  // This process serves 'bali' (the second argument — what `SITE_SLUG` names
  // for THIS admin instance, per `commerceCurrentSiteSlug()`); the row being
  // written targets 'jakarta' (the third argument — the partnership's own
  // `site_id`, resolved to a slug). Same login, same role, wrong city.
  assert.equal(canWritePartnershipForSite(partnerManager, 'bali', 'jakarta'), false)
})

test('a partner_manager CAN write the site this process actually serves', () => {
  assert.equal(canWritePartnershipForSite(partnerManager, 'bali', 'bali'), true)
})

test('an unauthenticated caller (no session at all) cannot write', () => {
  assert.equal(canWritePartnershipForSite(null, 'bali', 'bali'), false)
  assert.equal(canWritePartnershipForSite(null, 'bali', 'jakarta'), false)
})

test('a commerce admin may write any site\'s partnerships, not just this process\'s own', () => {
  assert.equal(canWritePartnershipForSite(commerceAdmin, 'bali', 'bali'), true)
  assert.equal(canWritePartnershipForSite(commerceAdmin, 'bali', 'jakarta'), true)
})

test('a partner_manager writing with no resolvable current site is refused, not silently allowed', () => {
  // `commerceCurrentSiteSlug()` returns '' when SITE_SLUG is unset — a
  // deployment error (`lib/site.ts`'s `requireSlug()` throws on it
  // elsewhere), and the empty string must never equal a target slug by
  // coincidence. Guards against `'' === ''` reading as "same site."
  assert.equal(canWritePartnershipForSite(partnerManager, '', ''), false)
})

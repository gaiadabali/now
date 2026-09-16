import 'server-only'

import { headers as nextHeaders } from 'next/headers'
import { redirect } from 'next/navigation'

import { payloadClient } from '@/lib/payload'

/**
 * Who is signed in, and what they may see.
 *
 * Deliberately NOT a copy of the console's version. That one authenticated
 * against a Payload instance bound to `now_platform`, because the console
 * owned that database. Here Payload is bound to the **city** database and
 * identity comes from the platform through the custom strategy
 * (`packages/cms/src/auth/platformStrategy.ts`, Phase 1) — so the session is
 * resolved the same way for editorial and commerce, which is the entire point
 * of the merge.
 *
 * The roles are two independent dimensions (docs/ADMIN-CONSOLIDATION.md):
 * `role` carries editorial standing and `commerceRole` carries commercial.
 * Being an admin of Jakarta's CMS is not a reason to see partner terms.
 */

export type StaffUser = {
  id: number
  email: string
  /** Editorial dimension: admin | editor | author | none */
  role?: string
  /** Commercial dimension: admin | partner_manager | viewer | none */
  commerceRole?: string
}

export async function currentUser(): Promise<StaffUser | null> {
  const payload = await payloadClient()
  const { user } = await payload.auth({ headers: await nextHeaders() })
  return (user as StaffUser | null) ?? null
}

/**
 * For pages that require any signed-in staff member.
 *
 * Redirects to Payload's own login rather than maintaining a second one.
 */
export async function requireUser(): Promise<StaffUser> {
  const user = await currentUser()
  if (!user) redirect('/team-editor/login')
  return user
}

/** May this user see commercial data at all? */
export function canReadCommerce(user: StaffUser): boolean {
  return Boolean(user.commerceRole) && user.commerceRole !== 'none'
}

/** May this user change partnership state? Reserved for the E4.4 write surface. */
export function canManagePartners(user: StaffUser): boolean {
  return user.commerceRole === 'admin' || user.commerceRole === 'partner_manager'
}

/** May this user see editorial content at all? */
export function canReadEditorial(user: StaffUser): boolean {
  return Boolean(user.role) && user.role !== 'none'
}

/**
 * The gate every classification-report page calls first.
 *
 * The editorial mirror of `requireCommerceAccess`, and for the same reasons:
 * per route rather than in a layout, because a layout guard is a rendering
 * convenience and not an access control; and a redirect rather than a 403,
 * because a commerce-only user is legitimately signed in and simply has no
 * route here.
 *
 * Author-or-above deliberately, not editor-or-above. It matches
 * `isAuthorOrAbove` on the `classification-reviews` collection — the access
 * rule that actually decides whether the correction this page offers will be
 * accepted. Gating the page more tightly than the write it wraps would mean
 * choosing a second, looser or stricter answer to the same question, and the
 * one that counts is Payload's: every write below goes through the Local API
 * with `overrideAccess: false` and this user attached, so the collection is
 * the enforcement and this is the courtesy.
 */
export async function requireEditorialAccess(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canReadEditorial(user)) redirect('/team-editor')
  return user
}

/**
 * The same gate, but returning the user document Payload itself produced
 * rather than this file's `StaffUser` view of it.
 *
 * `StaffUser` is a hand-written shape for rendering — four fields this app
 * cares about. Payload's Local API wants the real document: it hands whatever
 * it is given to every `access` function and every hook as `req.user`, and
 * `reviewQueueHooks.autoPopulateOnDecision` reads `req.user.id` off it to
 * stamp `reviewedBy`. Passing the trimmed shape would work by coincidence
 * today and stop working the moment an access rule reads a field this type
 * never declared. So a write path asks for this and a render path asks for
 * `requireEditorialAccess` — one `payload.auth` either way.
 */
export async function requireEditorialActor() {
  const payload = await payloadClient()
  const { user } = await payload.auth({ headers: await nextHeaders() })
  if (!user) redirect('/team-editor/login')
  const role = (user as StaffUser).role
  if (!role || role === 'none') redirect('/team-editor')
  return user
}

/**
 * The gate every commerce page calls first.
 *
 * Enforced server-side, per route — not in a layout. A layout guard is a
 * rendering convenience, not an access control: Next can render a page's data
 * fetch without its parent layout in several situations, and a reader with a
 * direct URL should never be relying on layout order for whether they see
 * partner terms.
 *
 * `notFound`-style behaviour is deliberate for an editorial-only user: they
 * are legitimately signed in, and a 403 would confirm the commerce surface
 * exists. They simply have no route here.
 */
export async function requireCommerceAccess(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canReadCommerce(user)) redirect('/team-editor')
  return user
}

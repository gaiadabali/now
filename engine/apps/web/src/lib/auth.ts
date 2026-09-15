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

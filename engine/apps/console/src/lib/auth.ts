import 'server-only'
import { headers as nextHeaders } from 'next/headers'
import { redirect } from 'next/navigation'
import { getPayload } from 'payload'
import type { User } from '../../payload-types'

import config from '../../payload.config'

/**
 * The gate every console page goes through.
 *
 * Payload owns the session — `payload.auth()` validates the cookie it issued
 * at `/admin/login`, so there is no second token format, no bespoke session
 * table, and password reset and lockout come from the same place. This file
 * is the whole of the console's auth surface.
 *
 * It is a *server-side* check, not middleware. Middleware runs on the edge
 * runtime where Payload's database adapter cannot follow, and a redirect in
 * middleware would authenticate the navigation while leaving a Server
 * Component free to query the platform database anyway. Calling this at the
 * top of each page means the data fetch cannot happen before the check.
 */
export async function requireUser(): Promise<User> {
  const payload = await getPayload({ config })
  const { user } = await payload.auth({ headers: await nextHeaders() })

  if (!user) {
    // Payload's own login screen, rather than a second one to maintain.
    redirect('/admin/login')
  }
  return user as User
}

/**
 * Roles are coarse by design (see collections/Users.ts). This exists so a
 * future write surface has one place to ask, rather than scattering
 * `user.commerceRole === 'admin'` through pages.
 *
 * Reads the COMMERCE dimension only. Editorial standing is irrelevant here:
 * being an admin of Jakarta's CMS is not a reason to see partner terms, which
 * is the whole point of splitting the two (docs/ADMIN-CONSOLIDATION.md).
 */
export function canManagePartners(user: User): boolean {
  return user.commerceRole === 'admin' || user.commerceRole === 'partner_manager'
}

/** May this user see commercial data at all? */
export function canReadCommerce(user: User): boolean {
  return user.commerceRole !== 'none' && user.commerceRole !== undefined
}

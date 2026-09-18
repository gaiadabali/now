'use client'

import { useAuth } from '@payloadcms/ui'
import Link from 'next/link'

/**
 * The way into `/team-editor/staff` from the sidebar.
 *
 * **Why this needs to exist at all.** The staff surface is a Payload custom
 * view (`admin.components.views` in payload.config.ts, S3.1), not a Payload
 * collection — staff identity lives in `now_platform.public.users` and this
 * Payload instance is bound to a *city* database, so it cannot model those
 * rows (docs/ADMIN-CONSOLIDATION.md, "The one real constraint"). Payload's nav
 * lists collections, so a page that is not one gets no entry and is reachable
 * only by typing the URL. The commerce console has lived with that; for the
 * surface whose entire purpose is onboarding the people who do not yet know
 * the URL, it would defeat the point.
 *
 * Renders in `admin.components.afterNavLinks` — a slot, not a `Nav`
 * override, so Payload can keep changing the nav's internals without taking
 * this with it.
 *
 * **The role test here is cosmetic and nothing more.** It hides a link that
 * would redirect away anyway. Access is decided server-side by
 * `requireStaffAdmin()` in the view and in every action
 * (apps/web/src/lib/auth.ts); this component runs in the browser, where the
 * user chooses what it returns.
 */
export function StaffLink() {
  const { user } = useAuth() as { user?: { role?: string } | null }
  if (user?.role !== 'admin') return null

  return (
    // `next/link`: since S3.1 `/team-editor/staff` is reached through
    // Payload's own catch-all, the same as every collection link, so a
    // client-side transition resolves instead of forcing a full reload.
    <Link className="now-nav-extra" href="/team-editor/staff">
      Staff &amp; roles
    </Link>
  )
}

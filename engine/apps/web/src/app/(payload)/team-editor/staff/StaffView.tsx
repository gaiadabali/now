import { requireStaffAdmin } from '@/lib/auth'
import { listStaff } from '@/lib/staff'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { StaffConsole } from './StaffConsole'

/**
 * `/team-editor/staff` — who has an account, and what they may do.
 *
 * The surface that did not exist. Before it, `npm run staff-account -w
 * @now/auth` on a shell with `PLATFORM_DATABASE_URI` set was the only way to
 * create an account or change a role, which made onboarding anyone a task for
 * whoever has that shell.
 *
 * Reads `now_platform` over direct SQL, the same shape as the commerce
 * console, for the same unavoidable reason: this app's Payload instance is
 * bound to the *city* database and cannot see the platform's `users` table at
 * all (docs/ADMIN-CONSOLIDATION.md, "The one real constraint").
 *
 * FORMERLY `staff/page.tsx` — a literal Next route with its own
 * `staff/layout.tsx` masthead. S3.1 registers this component directly as the
 * Payload custom view at `/staff` (payload.config.ts): unlike classification
 * and commerce, staff has no sub-routes, so there is no dispatcher to write —
 * this IS the view. It still wraps itself in `AdminViewFrame`
 * (`../AdminViewFrame.tsx`) for the same reason those two do: a custom view
 * reached through Payload's route fallback gets no sidebar unless it renders
 * one itself.
 */
export async function StaffView(frame: Omit<AdminViewFrameProps, 'children' | 'contentClassName'>) {
  // Before any query. A redirect has to happen before the platform database
  // is touched, not after — and this table is the one that decides who may
  // touch it.
  const actor = await requireStaffAdmin()
  const members = await listStaff()

  return (
    // `.console__main` — the staff surface has always borrowed the commerce
    // console's page furniture (see `staff.css`, now folded into
    // styles/admin.css) rather than inventing its own. `.staff__main` layers
    // its own few rules over the same wrapper.
    <AdminViewFrame {...frame} contentClassName="console__main staff__main">
      <h1>Staff</h1>
      <p className="console__sub">
        One account signs in to every city. Roles are read from here at each
        sign-in, so a change takes effect the next time the person signs in —
        an open session keeps the role it was issued with for up to eight
        hours.
      </p>

      <StaffConsole members={members} actorEmail={actor.email} />
    </AdminViewFrame>
  )
}

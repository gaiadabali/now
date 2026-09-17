import { requireStaffAdmin } from '@/lib/auth'
import { listStaff } from '@/lib/staff'

import { StaffConsole } from './StaffConsole'

export const dynamic = 'force-dynamic'

/**
 * `/team-editor/staff` — who has an account, and what they may do.
 *
 * The surface that did not exist. Before it, `npm run staff-account -w
 * @now/auth` on a shell with `PLATFORM_DATABASE_URI` set was the only way to
 * create an account or change a role, which made onboarding anyone a task for
 * whoever has that shell.
 *
 * A plain Next page under `(payload)`, reading `now_platform` over direct SQL
 * — the same shape as `team-editor/commerce`, for the same unavoidable
 * reason: this app's Payload instance is bound to the *city* database and
 * cannot see the platform's `users` table at all
 * (docs/ADMIN-CONSOLIDATION.md, "The one real constraint").
 */
export default async function StaffPage() {
  // Before any query. A redirect has to happen before the platform database
  // is touched, not after — and this table is the one that decides who may
  // touch it.
  const actor = await requireStaffAdmin()
  const members = await listStaff()

  return (
    <>
      <h1>Staff</h1>
      <p className="console__sub">
        One account signs in to every city. Roles are read from here at each
        sign-in, so a change takes effect the next time the person signs in —
        an open session keeps the role it was issued with for up to eight
        hours.
      </p>

      <StaffConsole members={members} actorEmail={actor.email} />
    </>
  )
}

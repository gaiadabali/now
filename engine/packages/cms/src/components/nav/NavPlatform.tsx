'use client'

import { useAuth } from '@payloadcms/ui'

import { RailLink } from './RailLink'

/**
 * The way into `/team-editor/platform` from the sidebar.
 *
 * Same shape as `StaffLink`, and gated the same way, for the same reason:
 * `/team-editor/platform` is a plain Next tree under `(payload)`, not a
 * Payload collection — it edits `engine.sites` (nav, brand tokens, home
 * rails, ranking weights) across every city from the one platform database,
 * which this Payload instance cannot model any more than it can model
 * `now_platform.public.users` (docs/ADMIN-CONSOLIDATION.md, "The one real
 * constraint"). Payload's nav lists collections, so a page that is not one
 * gets no entry unless something puts it here.
 *
 * **Gated on `canManageStaff`'s rule, not a new one.** D-S1
 * (docs/SURFACES-PLAN.md §3) put the platform console under `/team-editor`
 * rather than a fourth app precisely because five staff accounts did not
 * justify a second hostname, and it accepted that trade-off on condition that
 * "the access rules become security-critical code" — the same sentence
 * ADMIN-CONSOLIDATION.md wrote about commerce. Editing `engine.sites` reaches
 * every city's masthead and rails at once, which is at least as sensitive as
 * minting a staff account, so this reuses the editorial-admin test rather
 * than inventing a fifth role dimension for one nav link.
 *
 * **The role test here is cosmetic and nothing more**, exactly as on
 * `StaffLink`: it hides a link that would redirect away anyway. Access is
 * decided server-side, inside `/team-editor/platform` itself — this
 * component only decides what the sidebar shows.
 */
export function NavPlatform() {
  const { user } = useAuth() as { user?: { role?: string } | null }
  if (user?.role !== 'admin') return null

  return (
    // `activeMatch="prefix"`: stays current on `/team-editor/platform/
    // sites/[slug]`, the only page this link's own subtree contains.
    <RailLink activeMatch="prefix" className="now-nav-extra" href="/team-editor/platform">
      Platform
    </RailLink>
  )
}

import Link from 'next/link'

import { requireCommerceAccess } from '@/lib/auth'
import { getOrg, listSites } from '@/lib/queries'

import { orgHref } from '../../../paths'
import { PartnershipForm } from './PartnershipForm'

/**
 * `/team-editor/commerce/orgs/:id/partnerships` — S5.2's create screen.
 *
 * Gated with `requireCommerceAccess()` for the READ (same as every other
 * commerce page): this renders a form, and the actual write is behind the
 * separate, stricter `requireCommerceWriter()` in `actions.ts` — a page
 * guard is not an access control for the action it renders
 * (`lib/auth.ts`'s comment on `requireStaffAdmin` makes the same point).
 *
 * **Org-level partnerships only.** ARCHITECTURE.md §11 allows a partnership
 * to name either an organisation or a single place
 * (`ck_partnerships_org_xor_place`), but there is no place browser anywhere
 * in this console yet — `OrgDetailView.tsx` prints a place-level
 * partnership's raw `place_id` as `<code>`, which is the only place a place
 * id appears at all. Building a real place picker belongs with whatever
 * ships a places index, not folded into the first write path as a
 * side-effect. This form always creates the organisation-level case; place-
 * level partnerships remain DB-writable (and the resolver already reads
 * them — see `packages/link-resolver`) but not console-writable yet. Said
 * once here rather than silently, per the report to the orchestrator.
 */
export async function NewPartnershipView({ orgId }: { orgId: string }) {
  await requireCommerceAccess()
  const [org, sites] = await Promise.all([getOrg(orgId), listSites()])

  if (!org) {
    return (
      <>
        <p className="console__sub">
          <Link href={orgHref(orgId)}>← Back</Link>
        </p>
        <h1>Not found</h1>
        <p className="console__sub">That organisation does not exist in the platform database.</p>
      </>
    )
  }

  return (
    <>
      <p className="console__sub">
        <Link href={orgHref(orgId)}>← {org.name}</Link>
      </p>
      <h1>New partnership</h1>
      <p className="console__sub">
        For {org.name}. This applies to every place that belongs to this organisation — see the
        blast radius before it saves.
      </p>
      <PartnershipForm existing={null} orgId={orgId} orgName={org.name} sites={sites} />
    </>
  )
}

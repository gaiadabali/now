import Link from 'next/link'

import { requireCommerceAccess } from '@/lib/auth'
import { getOrg, getPartnership, listPartnershipAudit, listSites } from '@/lib/queries'

import { orgHref } from '../../../../paths'
import { PartnershipForm } from '../PartnershipForm'

/**
 * `/team-editor/commerce/orgs/:id/partnerships/:partnershipId` — S5.2's edit
 * screen, with S5.2's audit trail rendered underneath it.
 *
 * Read-gated the same way `NewPartnershipView` is; see that file's comment.
 */
export async function EditPartnershipView({ orgId, partnershipId }: { orgId: string; partnershipId: string }) {
  await requireCommerceAccess()
  const [org, partnership, sites, audit] = await Promise.all([
    getOrg(orgId),
    getPartnership(partnershipId),
    listSites(),
    listPartnershipAudit(partnershipId),
  ])

  if (!org || !partnership || partnership.orgId !== orgId) {
    return (
      <>
        <p className="console__sub">
          <Link href={orgHref(orgId)}>← Back</Link>
        </p>
        <h1>Not found</h1>
        <p className="console__sub">That partnership does not exist under this organisation.</p>
      </>
    )
  }

  return (
    <>
      <p className="console__sub">
        <Link href={orgHref(orgId)}>← {org.name}</Link>
      </p>
      <h1>Edit partnership</h1>
      <p className="console__sub">
        {org.name} · <code>{partnership.siteSlug}</code> · created {partnership.createdAt.slice(0, 10)}
      </p>

      <PartnershipForm existing={partnership} orgId={orgId} orgName={org.name} sites={sites} />

      <h2 className="console__subhead">Who changed this, and when</h2>
      <p className="console__sub">Every change to this partnership is kept, alongside the person who made it.</p>
      {audit.length === 0 ? (
        <div className="console__empty">No writes recorded yet.</div>
      ) : (
        <ul className="ws4-audit">
          {audit.map((row) => (
            <li className="ws4-audit__row" key={row.id}>
              <div className="ws4-audit__meta">
                <span className="ws4-audit__actor">{row.after._audit.actorEmail}</span>
                <span className="ws4-audit__ts">{row.ts.replace('T', ' ').slice(0, 19)} UTC</span>
              </div>
              <div className="ws4-audit__diff">
                {row.before === null ? (
                  <span className="platform__pill platform__pill--governed">created</span>
                ) : (
                  <span>
                    {row.before.tier !== row.after.tier ? `tier: ${row.before.tier} → ${row.after.tier}` : null}
                    {row.before.status !== row.after.status
                      ? `${row.before.tier !== row.after.tier ? ' · ' : ''}status: ${row.before.status} → ${row.after.status}`
                      : null}
                    {row.before.tier === row.after.tier && row.before.status === row.after.status
                      ? 'edited (tier and status unchanged)'
                      : null}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

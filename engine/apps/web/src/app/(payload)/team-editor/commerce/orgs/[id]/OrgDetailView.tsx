import Link from 'next/link'
import { getOrg, listOrgVenues, listPartnerships } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'
import { consoleHref, newPartnershipHref, partnershipHref } from '../../paths'
import { VenuesPanel } from './VenuesPanel'

/**
 * FORMERLY `commerce/orgs/[id]/page.tsx` — a literal Next dynamic route, with
 * its own `commerce/not-found.tsx` for an id that does not resolve. S3.1
 * folded it into `CommerceView`'s dispatch (`../../CommerceView.tsx`), so `id`
 * now arrives as a plain string the dispatcher has already read out of
 * Payload's raw path segments, and the "not found" case is rendered inline
 * rather than thrown: `commerce/not-found.tsx` was scoped to this one route
 * and would otherwise be dead code once nothing under `commerce/` is a route
 * of its own, and its message ("that record does not exist in the platform
 * database") is specific enough to this case that Payload's generic
 * catch-all 404 would be a worse answer, not just a differently-styled one.
 */
export async function OrgDetailView({ id }: { id: string }) {
  await requireCommerceAccess()
  const org = await getOrg(id)
  if (!org) {
    return (
      <>
        <p className="console__sub"><Link href={consoleHref('/orgs')}>← Partners</Link></p>
        <h1>Not found</h1>
        <p className="console__sub">That record does not exist in the platform database.</p>
      </>
    )
  }
  const [partnerships, venues] = await Promise.all([listPartnerships(id), listOrgVenues(id)])

  return (
    <>
      <p className="console__sub"><Link href={consoleHref('/orgs')}>← Partners</Link></p>
      <h1>{org.name}</h1>
      <p className="console__sub">
        <code>{org.slug}</code>
        {org.website ? <> · <a href={org.website} rel="noreferrer nofollow" target="_blank">{org.website}</a></> : null}
      </p>

      <h2 className="console__subhead">Partnerships</h2>
      <p className="console__sub">
        A budget-exhausted or expired partnership still appears here. It simply
        stops being <em>live</em> — §11 keeps relevance and billing separate,
        and expiry is resolved at query time rather than by a nightly job.
      </p>

      {partnerships.length === 0 ? (
        <div className="console__empty">No partnerships recorded for this organisation.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Site</th><th>Tier</th><th>Status</th><th>Starts</th><th>Ends</th><th>Place</th><th></th></tr>
          </thead>
          <tbody>
            {partnerships.map((p) => (
              <tr key={p.id}>
                <td>{p.site_slug ? <code>{p.site_slug}</code> : '—'}</td>
                <td>
                  <span className={p.tier === 'paid' ? 'ws4-pill--tier-paid' : undefined}>{p.tier ?? '—'}</span>
                </td>
                <td>
                  <span className={`console__pill console__pill--${p.is_live ? 'live' : 'expired'}`}>
                    {p.is_live ? 'live' : (p.status ?? 'inactive')}
                  </span>
                </td>
                <td>{p.starts_at?.slice(0, 10) ?? '—'}</td>
                <td>{p.ends_at?.slice(0, 10) ?? 'open'}</td>
                <td>{p.place_id ? <code>{p.place_id}</code> : '—'}</td>
                <td><Link href={partnershipHref(org.id, p.id)}>Edit →</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="console__sub" style={{ marginTop: '1rem' }}>
        <Link className="platform__btn ws4-btn--primary" href={newPartnershipHref(org.id)}>
          + New partnership
        </Link>
      </p>

      <VenuesPanel initialVenues={venues} orgId={org.id} orgName={org.name} />
    </>
  )
}

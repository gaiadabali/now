import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getOrg, listPartnerships } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'

export const dynamic = 'force-dynamic'

export default async function Org({ params }: { params: Promise<{ id: string }> }) {
  await requireCommerceAccess()
  const { id } = await params
  const org = await getOrg(id)
  if (!org) notFound()
  const partnerships = await listPartnerships(id)

  return (
    <>
      <p className="sub"><Link href="/orgs">← Partners</Link></p>
      <h1>{org.name}</h1>
      <p className="sub">
        <code>{org.slug}</code>
        {org.website ? <> · <a href={org.website} rel="noreferrer nofollow" target="_blank">{org.website}</a></> : null}
      </p>

      <h1 style={{ fontSize: '1.1rem', marginTop: '1.5rem' }}>Partnerships</h1>
      <p className="sub">
        A budget-exhausted or expired partnership still appears here. It simply
        stops being <em>live</em> — §11 keeps relevance and billing separate,
        and expiry is resolved at query time rather than by a nightly job.
      </p>

      {partnerships.length === 0 ? (
        <div className="empty">No partnerships recorded for this organisation.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Site</th><th>Tier</th><th>Status</th><th>Starts</th><th>Ends</th><th>Place</th></tr>
          </thead>
          <tbody>
            {partnerships.map((p) => (
              <tr key={p.id}>
                <td>{p.site_slug ? <code>{p.site_slug}</code> : '—'}</td>
                <td>{p.tier ?? '—'}</td>
                <td>
                  <span className={`pill ${p.is_live ? 'live' : 'expired'}`}>
                    {p.is_live ? 'live' : (p.status ?? 'inactive')}
                  </span>
                </td>
                <td>{p.starts_at?.slice(0, 10) ?? '—'}</td>
                <td>{p.ends_at?.slice(0, 10) ?? 'open'}</td>
                <td>{p.place_id ? <code>{p.place_id}</code> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

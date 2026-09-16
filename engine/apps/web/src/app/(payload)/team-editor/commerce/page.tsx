import Link from 'next/link'
import { countOrgs, listCampaigns, listSites } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'
import { consoleHref } from './paths'

export const dynamic = 'force-dynamic'

export default async function Overview() {
  // Before any query: a redirect must happen before the platform database
  // is touched, not after.
  await requireCommerceAccess()
  const [sites, orgs, campaigns] = await Promise.all([listSites(), countOrgs(), listCampaigns()])
  const live = campaigns.filter((c) => c.status === 'active').length

  return (
    <>
      <h1>Overview</h1>
      <p className="console__sub">Platform database only — this console never opens a city database.</p>

      <div className="console__cards">
        <div className="console__card"><div className="console__n">{orgs.toLocaleString()}</div><div className="console__k">organisations</div></div>
        <div className="console__card"><div className="console__n">{campaigns.length}</div><div className="console__k">campaigns</div></div>
        <div className="console__card"><div className="console__n">{live}</div><div className="console__k">active campaigns</div></div>
        <div className="console__card"><div className="console__n">{sites.length}</div><div className="console__k">sites in registry</div></div>
      </div>

      <h2 className="console__subhead">Sites</h2>
      <p className="console__sub">
        The registry engine-worker and engine-api both fan out over. Adding a
        city is a row here, not a deployment.
      </p>
      {sites.length === 0 ? (
        <div className="console__empty">engine.sites is empty — nothing is deployed against this platform database yet.</div>
      ) : (
        <table>
          <thead><tr><th>Slug</th><th>Name</th><th>Hostname</th></tr></thead>
          <tbody>
            {sites.map((s) => (
              <tr key={s.id}>
                <td><code>{s.slug}</code></td>
                <td>{s.name}</td>
                <td>{s.hostname ?? <span className="console__muted">not set</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="console__sub" style={{ marginTop: '1.5rem' }}>
        <Link href={consoleHref('/orgs')}>Browse partners →</Link>
      </p>
    </>
  )
}

import { listCampaigns } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'

/**
 * FORMERLY `commerce/campaigns/page.tsx`. S3.1 folded it into
 * `CommerceView`'s dispatch — see `../CommerceView.tsx`.
 */
export async function CampaignsView() {
  await requireCommerceAccess()
  const campaigns = await listCampaigns()

  return (
    <>
      <h1>Campaigns</h1>
      <p className="console__sub">
        Budget and pacing live here; the ledger that spends against them is
        <code> engine.ad_events</code>. A campaign that has exhausted its budget
        stays eligible organically — it just stops being logged as a billable
        impression (§11).
      </p>

      {campaigns.length === 0 ? (
        <div className="console__empty">
          No campaigns yet. E4.1 loaded the org roster and the partnerships
          schema; campaign management is the rest of E4.
        </div>
      ) : (
        <table>
          <thead>
            <tr><th>Organisation</th><th>Site</th><th>Objective</th><th>Status</th><th>Pacing</th><th className="console__num">Budget</th><th className="console__num">Placements</th></tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id}>
                <td>{c.org_name ?? '—'}</td>
                <td>{c.site_slug ? <code>{c.site_slug}</code> : 'all'}</td>
                <td>{c.objective ?? '—'}</td>
                <td><span className={`console__pill${c.status === 'active' ? ' console__pill--live' : ''}`}>{c.status ?? 'draft'}</span></td>
                <td>{c.pacing ?? '—'}</td>
                <td className="console__num">{c.budget ?? '—'}</td>
                <td className="console__num">{c.placement_count || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

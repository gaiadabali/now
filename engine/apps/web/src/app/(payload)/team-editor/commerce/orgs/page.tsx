import Link from 'next/link'
import { listOrgs } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'
import { consoleHref } from '../paths'

export const dynamic = 'force-dynamic'

export default async function Orgs({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>
}) {
  await requireCommerceAccess()
  const { q } = await searchParams
  const orgs = await listOrgs(q)

  return (
    <>
      <h1>Partners</h1>
      <p className="console__sub">
        Ordered by live partnerships. &ldquo;Live&rdquo; is computed from the dates, not
        from the status column alone — that is what the renderer resolves link
        policy against (ARCHITECTURE.md §11).
      </p>

      <form className="console__search" method="get">
        <input type="search" name="q" defaultValue={q ?? ''} placeholder="Search name or slug…" aria-label="Search partners" />
      </form>

      {orgs.length === 0 ? (
        <div className="console__empty">{q ? `No partner matches “${q}”.` : 'No organisations loaded.'}</div>
      ) : (
        <table>
          <thead>
            <tr><th>Name</th><th>Type</th><th className="console__num">Live</th><th className="console__num">Total</th><th>Website</th></tr>
          </thead>
          <tbody>
            {orgs.map((o) => (
              <tr key={o.id}>
                <td><Link href={consoleHref(`/orgs/${o.id}`)}>{o.name}</Link></td>
                <td>
                  {o.type ?? (
                    <span className="console__muted" title={`Unconfirmed guess, confidence ${o.confidence ?? '?'}`}>
                      {o.type_guess ? `${o.type_guess}?` : '—'}
                    </span>
                  )}
                </td>
                <td className="console__num">{o.active_partnerships || ''}</td>
                <td className="console__num">{o.partnership_count || ''}</td>
                <td>{o.website ? <a href={o.website} rel="noreferrer nofollow" target="_blank">{new URL(o.website).host}</a> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

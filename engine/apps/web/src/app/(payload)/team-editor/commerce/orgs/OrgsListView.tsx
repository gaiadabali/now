import Link from 'next/link'
import { listOrgs } from '@/lib/queries'
import { requireCommerceAccess } from '@/lib/auth'
import { AdminPager, pagerSummary } from '../../Pager'
import { consoleHref } from '../paths'

/**
 * How many partners one screenful shows. `listOrgs()` now takes this as a
 * real SQL `LIMIT`/`OFFSET` (unlike the review desk's clusters, which are
 * few enough to fetch whole and slice in JS) — 1,562 orgs was previously cut
 * off at a flat, invisible 100 with no page beyond it and nothing on screen
 * saying so.
 */
const ORGS_PER_PAGE = 50

/**
 * FORMERLY `commerce/orgs/page.tsx`. S3.1 folded it into `CommerceView`'s
 * dispatch — see `../CommerceView.tsx`.
 */
export async function OrgsListView({ searchParams }: { searchParams: { q?: string; page?: string } }) {
  await requireCommerceAccess()
  const { q } = searchParams
  const requestedPage = Number(searchParams.page)
  const page = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const { orgs, total } = await listOrgs(q, page, ORGS_PER_PAGE)
  const totalPages = Math.max(1, Math.ceil(total / ORGS_PER_PAGE))
  const hrefForPage = (target: number) => {
    const qs = [q ? `q=${encodeURIComponent(q)}` : null, target > 1 ? `page=${target}` : null]
      .filter(Boolean)
      .join('&')
    return qs ? `${consoleHref('/orgs')}?${qs}` : consoleHref('/orgs')
  }

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
        <>
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

          <p className="admin-pager__summary">{pagerSummary(page, ORGS_PER_PAGE, total)} partners</p>
          <AdminPager hrefForPage={hrefForPage} page={page} totalPages={totalPages} />
        </>
      )}
    </>
  )
}

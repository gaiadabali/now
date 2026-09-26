import Link from 'next/link'

import { requireReviewerAccess } from '@/lib/auth'
import { deskCounts, filterQueue, loadQueue, type QueueRow } from '@/lib/placeDesk'
import { getSiteConfig } from '@/lib/site'

import { AdminPager, pagerSummary } from '../Pager'
import { BulkJunkForm } from './Decisions'
import { BULK_JUNK_BATCH, placeHref, QUEUE_FILTERS, QUEUE_PAGE_SIZE, queueHref, type QueueFilterKey } from './paths'

/**
 * The place desk's queue (plan P1.6): every place still waiting, best
 * evidence first, so the first five hundred an editor works cover most of
 * what the magazine has ever led a story with (plan §9.1).
 *
 * Five views of the same queue, as plain links: the curation order itself;
 * the rows that look like junk, for bulk confirmation; the doubtful shapes;
 * names that point at another region; and what an editor has already kept.
 */

const FILTER_LABEL: Record<QueueFilterKey, string> = {
  queue: 'To review',
  junk: 'Looks like junk',
  suspect: 'Needs a look',
  region: 'Another region',
  kept: 'Kept',
}

function Flags({ row }: { row: QueueRow }) {
  const flags: Array<{ text: string; flag?: boolean }> = []
  if (row.junk.tier === 'junk' && row.reviewedBy === null) flags.push({ text: `Looks like junk: ${row.junk.reason}`, flag: true })
  if (row.junk.tier === 'suspect') flags.push({ text: `Needs a look: ${row.junk.reason}` })
  if (row.region.outOfRegion) flags.push({ text: `Another region: ${row.region.matched}` })
  if (row.reviewedBy !== null) flags.push({ text: 'Kept' })
  if (row.partnered) flags.push({ text: 'Partner' })
  if (!flags.length) return null
  return (
    <span className="place-desk__flags">
      {flags.map((f) => (
        <span key={f.text} className={`classify__pill${f.flag ? ' classify__pill--flag' : ''}`}>
          {f.text}
        </span>
      ))}
    </span>
  )
}

export async function PlaceDeskQueueView({ searchParams }: { searchParams: { show?: string; page?: string } }) {
  const user = await requireReviewerAccess()
  const site = await getSiteConfig()
  const filter: QueueFilterKey = (QUEUE_FILTERS as readonly string[]).includes(searchParams.show ?? '')
    ? (searchParams.show as QueueFilterKey)
    : 'queue'

  const [queue, counts] = await Promise.all([loadQueue(site.slug), deskCounts(Number(user.id), site.timezone)])
  const lists = Object.fromEntries(QUEUE_FILTERS.map((f) => [f, filterQueue(queue.rows, f)])) as Record<QueueFilterKey, QueueRow[]>
  const rows = lists[filter]

  const totalPages = Math.max(1, Math.ceil(rows.length / QUEUE_PAGE_SIZE))
  const requested = Number(searchParams.page)
  const page = Number.isInteger(requested) ? Math.min(Math.max(requested, 1), totalPages) : 1
  const pageRows = rows.slice((page - 1) * QUEUE_PAGE_SIZE, page * QUEUE_PAGE_SIZE)

  return (
    <>
      <h1>Place desk</h1>
      <p className="classify__sub">
        Every place the magazine has named, strongest evidence first. Approve the real ones, mark the fragments as
        junk, merge the doubles. A place&rsquo;s page goes live on {site.name} the moment it is approved.
      </p>

      <div className="classify__cards" role="list" aria-label="Place desk counts for this city">
        <div className="classify__card" role="listitem">
          <div className="classify__n">{counts.waiting.toLocaleString()}</div>
          <div className="classify__k">Waiting</div>
        </div>
        <div className="classify__card" role="listitem">
          <div className="classify__n">{counts.approved.toLocaleString()}</div>
          <div className="classify__k">Approved and live</div>
        </div>
        <div className="classify__card" role="listitem">
          <div className="classify__n">{counts.decidedToday.toLocaleString()}</div>
          <div className="classify__k">
            Decided today · {counts.decidedTodayByMe.toLocaleString()} by you
          </div>
        </div>
        <div className="classify__card" role="listitem">
          <div className="classify__n">{counts.decidedThisWeek.toLocaleString()}</div>
          <div className="classify__k">Decided in the last 7 days</div>
        </div>
      </div>

      <nav className="classify__facets" aria-label="Which places to show">
        {QUEUE_FILTERS.map((f) => (
          <Link
            key={f}
            href={queueHref(f)}
            className={`classify__facet${f === filter ? ' classify__facet--on' : ''}`}
            aria-current={f === filter ? 'page' : undefined}
          >
            {FILTER_LABEL[f]} <span className="classify__muted">{lists[f].length.toLocaleString()}</span>
          </Link>
        ))}
      </nav>

      {!queue.partnershipRead ? (
        <p className="classify__note">
          Partnerships could not be read, so no place gets the partner boost in this order right now.
        </p>
      ) : null}

      {rows.length === 0 ? (
        <p className="classify__empty">Nothing here. Well done.</p>
      ) : filter === 'junk' ? (
        <>
          <p className="classify__note">
            These names read like fragments of a sentence, events, offers, room types or job titles rather than
            places. Check them, untick any real place, and mark the rest as junk. Junk is hidden everywhere; the
            stories that mentioned it are not touched.
          </p>
          <BulkJunkForm
            key={page}
            batch={BULK_JUNK_BATCH}
            rows={pageRows.map((r) => ({
              id: r.id,
              name: r.name,
              reason: r.junk.reason ?? '',
              featured: r.featured,
              articles: r.articles,
              href: placeHref(r.id),
            }))}
          />
        </>
      ) : (
        <table>
          <caption className="classify__caption">
            {filter === 'queue'
              ? 'In review order: 3 × times featured + stories + partner boost + how recent.'
              : `${FILTER_LABEL[filter]}, in review order.`}
          </caption>
          <thead>
            <tr>
              <th scope="col" className="classify__num">#</th>
              <th scope="col">Place</th>
              <th scope="col" className="classify__num">Featured</th>
              <th scope="col" className="classify__num">Stories</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr key={r.id}>
                <td className="classify__num">{r.rank || '—'}</td>
                <td>
                  <Link href={placeHref(r.id)} className="place-desk__name">
                    {r.name}
                  </Link>
                  <span className="place-desk__meta">
                    {r.type && r.type !== 'editorial' && r.type !== 'unknown' ? `${r.subtype ?? r.type}` : 'Kind not set'}
                    {r.area ? ` · ${r.area}` : ''}
                  </span>
                </td>
                <td className="classify__num">{r.featured}</td>
                <td className="classify__num">{r.articles}</td>
                <td>
                  <Flags row={r} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 ? (
        <div className="place-desk__pager">
          <AdminPager page={page} totalPages={totalPages} hrefForPage={(n) => queueHref(filter, n)} />
          <span className="admin-pager__summary">{pagerSummary(page, QUEUE_PAGE_SIZE, rows.length)}</span>
        </div>
      ) : null}
    </>
  )
}

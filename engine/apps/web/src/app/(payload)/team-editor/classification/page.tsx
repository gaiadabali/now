import Link from 'next/link'

import { requireEditorialAccess } from '@/lib/auth'
import { CONFIDENCE_GATE, getClassificationQueue, getQueueTotals } from '@/lib/classification'

import { classifyHref } from './paths'
import { ConfidenceMeter } from './ConfidenceMeter'

export const dynamic = 'force-dynamic'

/**
 * How many rows one screenful is. No pagination control, deliberately: there
 * are 4,253 articles with something under the gate and nobody works a queue by
 * walking to page 71 of it. The queue is ordered so that the top of page one
 * is always the work that matters most, and search narrows it when a
 * particular article is wanted. If this turns out to be wrong, the honest fix
 * is a "reviewed" filter so decided work leaves the list — not a page footer.
 */
const QUEUE_PAGE_SIZE = 60

const pct = (n: number): string => `${Math.round(n * 100)}%`

/**
 * The archive, ordered by how badly each article needs a human.
 *
 * The way in. Payload's own Articles list sorts by date and shows the twelve
 * stored columns, none of which is the classifier's confidence — there was no
 * screen anywhere that answered "which article should I review next", which
 * is the only question the §6 gate actually poses.
 *
 * Sorted by the single weakest assignment on each article rather than by a
 * mean. A mean lets nine confident `location` tags bury one 0.40 `type` guess,
 * and it is the `type` guess that §8.A's competitor exclusion will treat as
 * fact. The worst thing on the article is what decides its place in the queue.
 */
export default async function ClassificationQueue({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; all?: string }>
}) {
  await requireEditorialAccess()
  const { q, all } = await searchParams
  const belowGateOnly = all !== '1'
  const [totals, rows] = await Promise.all([
    getQueueTotals(),
    getClassificationQueue({ search: q, belowGateOnly, limit: QUEUE_PAGE_SIZE }),
  ])

  return (
    <>
      <h1>Classification queue</h1>
      <p className="classify__sub">
        Every facet the engine assigned to an article lives in{' '}
        <code>engine.entity_terms</code>, which Payload&rsquo;s edit form cannot
        see. This is that data. ARCHITECTURE.md §6 ends the pipeline with{' '}
        <em>review: confidence &lt; {CONFIDENCE_GATE} → human queue</em>, and
        §8.A spends the result: an unreviewed <code>type</code> guess is what
        competitor exclusion excludes on, for every tier including free.
      </p>

      <div className="classify__cards">
        <div className="classify__card">
          <div className="classify__n">{totals.assignments.toLocaleString()}</div>
          <div className="classify__k">facet assignments</div>
        </div>
        <div className="classify__card">
          <div className="classify__n classify__n--flag">{totals.belowGate.toLocaleString()}</div>
          <div className="classify__k">below the {CONFIDENCE_GATE} gate</div>
        </div>
        <div className="classify__card">
          <div className="classify__n">{totals.articlesBelowGate.toLocaleString()}</div>
          <div className="classify__k">
            of {totals.articles.toLocaleString()} articles affected
          </div>
        </div>
        <div className="classify__card">
          <div className="classify__n">{totals.pendingReviews.toLocaleString()}</div>
          <div className="classify__k">queued review rows</div>
        </div>
      </div>

      <form className="classify__search" method="get">
        <input type="search" name="q" defaultValue={q ?? ''} placeholder="Search titles" aria-label="Search titles" />
        {all === '1' ? <input type="hidden" name="all" value="1" /> : null}
        <button type="submit">Search</button>
        <Link
          className="classify__toggle"
          href={classifyHref(
            belowGateOnly
              ? `?all=1${q ? `&q=${encodeURIComponent(q)}` : ''}`
              : q
                ? `?q=${encodeURIComponent(q)}`
                : '',
          )}
        >
          {belowGateOnly ? 'Show every article' : 'Show only those below the gate'}
        </Link>
      </form>

      {rows.length === 0 ? (
        <div className="classify__empty">
          Nothing matches. {belowGateOnly ? 'Every article here clears the gate — or none has been classified yet.' : null}
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Article</th>
              <th>Stored type</th>
              <th className="classify__num">Facets</th>
              <th className="classify__num">Below gate</th>
              <th>Weakest assignment</th>
              <th className="classify__num">Queued</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={classifyHref(`/${row.id}`)}>{row.title || `Article ${row.id}`}</Link>
                  {row.status !== 'published' ? (
                    <> <span className="classify__pill">{row.status}</span></>
                  ) : null}
                </td>
                <td>
                  {row.primaryType ? (
                    <code>{row.primaryType}</code>
                  ) : (
                    <span className="classify__muted">not set</span>
                  )}
                </td>
                <td className="classify__num">{row.assignments}</td>
                <td className="classify__num">
                  {row.belowGate > 0 ? (
                    <span className="classify__pill classify__pill--flag">{row.belowGate}</span>
                  ) : (
                    <span className="classify__muted">0</span>
                  )}
                </td>
                <td>
                  {row.weakest === null ? (
                    <span className="classify__muted">no assignments</span>
                  ) : (
                    <>
                      <ConfidenceMeter confidence={row.weakest} label={pct(row.weakest)} />
                      <div className="classify__muted">
                        {/* No facet means the term id resolved to nothing in
                            the platform vocabulary. Saying so beats an empty
                            cell, which reads as a rendering bug. */}
                        {row.weakestFacet
                          ? `${row.weakestFacet}: ${row.weakestTerm}`
                          : 'term not in the vocabulary'}
                      </div>
                    </>
                  )}
                </td>
                <td className="classify__num">
                  {row.pendingReviews > 0 ? row.pendingReviews : <span className="classify__muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="classify__foot">
        Showing {rows.length} article{rows.length === 1 ? '' : 's'}
        {belowGateOnly ? ' with at least one assignment below the gate' : ''}, weakest first.
        {rows.length === QUEUE_PAGE_SIZE ? (
          <>
            {' '}
            That is the page limit, not the total — {totals.articlesBelowGate.toLocaleString()}{' '}
            articles have something under the gate. Search to narrow it.
          </>
        ) : null}
      </p>
    </>
  )
}

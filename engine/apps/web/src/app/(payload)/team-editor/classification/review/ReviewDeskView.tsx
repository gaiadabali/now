import Link from 'next/link'

import { requireReviewerAccess } from '@/lib/auth'
import { getQueueShape, getReviewClusters } from '@/lib/review'

import { AdminPager, pagerSummary } from '../../Pager'
import { clusterHref, REVIEW_ROOT } from '../paths'

/**
 * The review desk — the whole queue, grouped by the mistake behind it.
 *
 * Bali's queue is 6,485 pending proposals. This page shows 345 rows, because
 * that is how many distinct decisions are actually in it: the classifier's
 * prior is the WordPress category, so every article that carried the same
 * category got the same answer with the same confidence, and reviewing them
 * one at a time is reviewing the same judgement several hundred times.
 * `lib/review.ts` has the measurement and the reasoning.
 *
 * Ordered by size, not by confidence. The list view one directory up already
 * sorts by shakiest-first and that is the right order for *finding* a
 * particular article; here the question is different — "what should I spend
 * the next ten minutes on" — and the answer is the biggest unresolved
 * pattern, near enough every time. The ten largest clusters are 37% of the
 * queue.
 *
 * Facet filter rather than facet tabs: the three facets in the queue behave
 * differently enough to want separating (`subtype` writes nothing onto an
 * article at all), but a reviewer who wants all of them should not have to
 * visit three pages to get there.
 *
 * FORMERLY `classification/review/page.tsx`. S3.1 folded it into
 * `ClassificationView`'s dispatch — see `../ClassificationView.tsx`.
 */

const pct = (n: number | null): string => (n === null ? '—' : `${Math.round(n * 100)}%`)

/**
 * How many clusters one screenful shows.
 *
 * `getReviewClusters()` still fetches every pending cluster in one query —
 * there is no SQL `LIMIT` here, unlike the orgs list below, because the
 * summary numbers on this page (`shape`, the per-facet counts, "N clusters
 * covering M proposals") are computed over the WHOLE set and have to stay
 * that way whichever page is showing. What changed is only how much of
 * `clusters` gets past the `.slice()` and into the DOM: unpaginated, 345
 * clusters at roughly 65px each rendered a 22,000px page (found on staging,
 * screenshot `09b-classification-review-viewport.png`) — nothing was wrong
 * with any one row, there were just all of them, at once, every time.
 */
const CLUSTERS_PER_PAGE = 25

export async function ReviewDeskView({ searchParams }: { searchParams: { facet?: string; page?: string } }) {
  await requireReviewerAccess()
  const { facet } = searchParams
  const [shape, all] = await Promise.all([getQueueShape(), getReviewClusters()])

  const facets = [...new Set(all.map((c) => c.facetKey))].sort()
  const clusters = facet ? all.filter((c) => c.facetKey === facet) : all
  const shown = clusters.reduce((n, c) => n + c.pending, 0)

  const totalPages = Math.max(1, Math.ceil(clusters.length / CLUSTERS_PER_PAGE))
  const requestedPage = Number(searchParams.page)
  const page = Number.isInteger(requestedPage) ? Math.min(Math.max(requestedPage, 1), totalPages) : 1
  const pageClusters = clusters.slice((page - 1) * CLUSTERS_PER_PAGE, page * CLUSTERS_PER_PAGE)
  const hrefForPage = (target: number) => {
    const qs = [facet ? `facet=${encodeURIComponent(facet)}` : null, target > 1 ? `page=${target}` : null]
      .filter(Boolean)
      .join('&')
    return qs ? `${REVIEW_ROOT}?${qs}` : REVIEW_ROOT
  }

  return (
    <>
      <h1>Review desk</h1>
      <p className="classify__sub">
        The engine classified the archive best-effort and flagged everything it
        was unsure of. Those flags cluster: the prior it used is the article&rsquo;s
        old WordPress category, so articles that shared a category share an
        answer — and share its mistakes. Decide the pattern once and it applies
        to every article in it.
      </p>

      <div className="classify__cards">
        <div className="classify__card">
          <div className="classify__n classify__n--flag">{shape.pending.toLocaleString()}</div>
          <div className="classify__k">proposals awaiting a human</div>
        </div>
        <div className="classify__card">
          <div className="classify__n">{shape.clusters.toLocaleString()}</div>
          <div className="classify__k">distinct decisions behind them</div>
        </div>
        <div className="classify__card">
          <div className="classify__n">{Math.round(shape.topTenShare * 100)}%</div>
          <div className="classify__k">of the queue is in its ten biggest</div>
        </div>
        <div className="classify__card">
          <div className="classify__n">{shape.decided.toLocaleString()}</div>
          <div className="classify__k">already decided</div>
        </div>
      </div>

      <nav className="classify__facets" aria-label="Filter by facet">
        <Link
          href={REVIEW_ROOT}
          className={`classify__facet${facet ? '' : ' classify__facet--on'}`}
        >
          All facets
        </Link>
        {facets.map((f) => (
          <Link
            key={f}
            href={`${REVIEW_ROOT}?facet=${encodeURIComponent(f)}`}
            className={`classify__facet${facet === f ? ' classify__facet--on' : ''}`}
          >
            {f}
          </Link>
        ))}
      </nav>

      {clusters.length === 0 ? (
        <div className="classify__empty">
          Nothing pending{facet ? ` for ${facet}` : ''}. The queue is clear.
        </div>
      ) : (
        <ul className="classify__clusters">
          {pageClusters.map((c) => (
            <li className="classify__cluster" key={`${c.facetKey}|${c.legacyCategory}|${c.proposedValue}`}>
              <Link className="classify__cluster-link" href={clusterHref(c)}>
                <span className="classify__cluster-count">{c.pending.toLocaleString()}</span>

                <span className="classify__cluster-rule">
                  {/* The rule, in the order a person reads it: what these
                      articles were, and what the engine decided they are. */}
                  <span className="classify__cluster-from">{c.legacyCategory}</span>
                  <span className="classify__cluster-arrow" aria-hidden="true">
                    →
                  </span>
                  <code className="classify__cluster-to">
                    {c.facetKey} = {c.proposedValue}
                  </code>
                  {!c.proposalIsTerm ? (
                    <span className="classify__pill classify__pill--flag">not a term</span>
                  ) : null}
                </span>

                <span className="classify__cluster-conf">
                  {pct(c.meanConfidence)}
                  <span className="classify__muted"> confident</span>
                  {c.reasonings > 1 ? (
                    <span className="classify__muted"> · {c.reasonings} reasonings</span>
                  ) : null}
                </span>
              </Link>

              {c.sampleTitles.length > 0 ? (
                <p className="classify__cluster-eg">
                  {/* Three of the cluster's least-confident members, so the
                      examples are a test of the rule rather than a showcase
                      for it. */}
                  {c.sampleTitles.join(' · ')}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <p className="classify__foot">
        {clusters.length.toLocaleString()} cluster{clusters.length === 1 ? '' : 's'} covering{' '}
        {shown.toLocaleString()} proposal{shown === 1 ? '' : 's'} across{' '}
        {shape.articlesPending.toLocaleString()} articles.
      </p>

      {clusters.length > 0 ? (
        <>
          <p className="admin-pager__summary">{pagerSummary(page, CLUSTERS_PER_PAGE, clusters.length)} clusters</p>
          <AdminPager hrefForPage={hrefForPage} page={page} totalPages={totalPages} />
        </>
      ) : null}
    </>
  )
}

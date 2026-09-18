import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { StoryCard } from '@/components/StoryCard'
import { SectionRule } from '@/components/primitives'
import { getArchivePage } from '@/lib/content'
import { formatCount } from '@/lib/format'
import { getSiteConfig } from '@/lib/site'

/**
 * Everything, newest first.
 *
 * **Why this route exists.** The homepage linked to `/latest` twice — from
 * "The Edit" and from the "Latest" rail — and both 404'd. `/latest` is not a
 * section, so `[slug]` treated it as an article slug, found none, and called
 * `notFound()`. Nothing failed at build time because a `<Link>` to a missing
 * route is only wrong when someone clicks it.
 *
 * Deleting the two links was the cheaper fix and the wrong one. Every section
 * has a paginated index; the archive as a whole had none, so there was no
 * answer to "show me everything recent" across 4,772 and 4,429 articles.
 *
 * A static sibling of `[slug]`, so it wins the route match the way `/culture`
 * and `/places` do — deliberately, because an article could otherwise be
 * published at this address and shadow it.
 */

export const metadata: Metadata = {
  title: 'Latest',
  description: 'Everything we have published, newest first.',
}

const PER_PAGE = 24

export default async function LatestPage({
  searchParams,
}: {
  // The page number lives in the URL, not in client state — same reasoning as
  // the section indexes: a paged archive stays shareable and crawlable.
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const site = await getSiteConfig()
  const query = (await searchParams) ?? {}
  const raw = typeof query.page === 'string' ? Number.parseInt(query.page, 10) : 1
  const requested = Number.isFinite(raw) && raw > 0 ? raw : 1

  const result = await getArchivePage({ page: requested, limit: PER_PAGE })

  // A `?page=` past the end must 404 rather than render an empty archive,
  // which would read as "nothing published" on a site with 9,201 articles.
  if (result.items.length === 0 && requested > 1) notFound()

  return (
    <div className="shell band">
      <p className="kicker kicker--red">Latest</p>
      <h1 className="display display--light" style={{ fontSize: 'var(--t-headline)' }}>
        Everything, newest first
      </h1>

      <div className="facets" style={{ marginTop: 'var(--space-m)' }}>
        <span className="facets__result">
          {formatCount(result.total)} {result.total === 1 ? 'story' : 'stories'}
          {result.totalPages > 1 ? ` · page ${result.page} of ${result.totalPages}` : ''}
        </span>
      </div>

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label={site.name} note="The full archive" />
        <div className="grid grid--3 grid--ruled">
          {result.items.map((a) => (
            <StoryCard key={a.id} article={a} locale={site.locale} timeZone={site.timezone} />
          ))}
        </div>
        {result.items.length === 0 ? <p className="meta">Nothing published yet.</p> : null}
        <Pager page={result.page} totalPages={result.totalPages} />
      </section>
    </div>
  )
}

/**
 * Archive pagination.
 *
 * A deliberate near-copy of the `Pager` in `[slug]/page.tsx` rather than an
 * extraction. That one carries a section slug and a `?format=` facet through
 * every link; this one has neither, and generalising it would mean a component
 * whose props are mostly `undefined` at one of its two call sites. If a third
 * paginated index appears, that is the moment to lift it out — with 199 pages
 * here and 50 in Unclassified, only a window of numbers is ever rendered.
 */
function Pager({ page, totalPages }: { page: number; totalPages: number }) {
  if (totalPages <= 1) return null

  const href = (n: number) => (n > 1 ? `/latest?page=${n}` : '/latest')

  const span = 2
  const numbers: number[] = []
  for (let n = Math.max(1, page - span); n <= Math.min(totalPages, page + span); n++) numbers.push(n)

  return (
    <nav className="facets" style={{ marginTop: 'var(--space-l)' }} aria-label="Pagination">
      {page > 1 ? (
        <Link className="facet" href={href(page - 1)} rel="prev">
          ← Newer
        </Link>
      ) : null}

      {numbers[0] > 1 ? (
        <>
          <Link className="facet" href={href(1)}>
            1
          </Link>
          {numbers[0] > 2 ? <span className="meta">…</span> : null}
        </>
      ) : null}

      {numbers.map((n) => (
        <Link
          className="facet"
          key={n}
          href={href(n)}
          aria-current={n === page ? 'page' : undefined}
          data-active={n === page || undefined}
        >
          {n}
        </Link>
      ))}

      {numbers[numbers.length - 1] < totalPages ? (
        <>
          {numbers[numbers.length - 1] < totalPages - 1 ? <span className="meta">…</span> : null}
          <Link className="facet" href={href(totalPages)}>
            {totalPages}
          </Link>
        </>
      ) : null}

      {page < totalPages ? (
        <Link className="facet" href={href(page + 1)} rel="next">
          Older →
        </Link>
      ) : null}
    </nav>
  )
}

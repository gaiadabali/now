import Link from 'next/link'

import { pageNodes } from '@/lib/pager'
export { pagerSummary } from '@/lib/pager'

/**
 * Server-side pagination for a list this app renders in full rather than
 * handing to Payload's own list view — the review desk's 345 clusters and
 * the commerce console's 1,562 partners, both of which used to render every
 * row in one page (22,000px of DOM for the first of those) because nothing
 * here ever sliced the result.
 *
 * A plain `<Link>` grid, not Payload's own `@payloadcms/ui` `Pagination`
 * component. That component exists and does the same windowing (see its
 * `elements/Pagination/index.js` — the window algorithm below is copied from
 * it on purpose, so the numbers jump the same way Payload's own collection
 * lists do), but it is a client component built around an `onChange`
 * callback, not an `href`. Every other piece of state on these two pages —
 * search, the facet filter — is already a plain GET link or form, and a
 * paginator that was the one client-rendered island on an otherwise static
 * page would be a strange thing to hydrate for. The classnames below
 * (`admin-pager*`) are this app's own, styled in `styles/admin.css` next to
 * `classify__*`/`console__*`, not Payload's `payload-default` layer — that
 * layer is only guaranteed to be loaded on the routes that actually render
 * one of Payload's own list views, and these two do not.
 */

export function AdminPager({
  page,
  totalPages,
  hrefForPage,
}: {
  page: number
  totalPages: number
  hrefForPage: (page: number) => string
}) {
  if (totalPages <= 1) return null
  const nodes = pageNodes(page, totalPages)

  return (
    <nav aria-label="Pagination" className="admin-pager">
      <Arrow direction="left" href={page > 1 ? hrefForPage(page - 1) : null} label="Previous page" />
      {nodes.map((n, i) =>
        n === 'sep' ? (
          <span aria-hidden="true" className="admin-pager__sep" key={`sep-${i}`}>
            —
          </span>
        ) : (
          <Link
            aria-current={n === page ? 'page' : undefined}
            className={`admin-pager__page${n === page ? ' admin-pager__page--current' : ''}`}
            href={hrefForPage(n)}
            key={n}
          >
            {n}
          </Link>
        ),
      )}
      <Arrow direction="right" href={page < totalPages ? hrefForPage(page + 1) : null} label="Next page" />
    </nav>
  )
}

function Arrow({
  direction,
  href,
  label,
}: {
  direction: 'left' | 'right'
  href: string | null
  label: string
}) {
  const classes = `admin-pager__arrow admin-pager__arrow--${direction}${href ? '' : ' admin-pager__arrow--disabled'}`
  const chevron = (
    <svg aria-hidden="true" height="100%" viewBox="0 0 20 20" width="100%" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M14 8L10 12L6 8"
        fill="none"
        stroke="currentColor"
        strokeLinecap="square"
        strokeWidth="1.5"
        transform={direction === 'left' ? 'rotate(90 10 10)' : 'rotate(-90 10 10)'}
      />
    </svg>
  )
  return href ? (
    <Link aria-label={label} className={classes} href={href}>
      {chevron}
    </Link>
  ) : (
    <span aria-disabled="true" aria-label={label} className={classes}>
      {chevron}
    </span>
  )
}

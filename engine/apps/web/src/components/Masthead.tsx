import Link from 'next/link'

import type { SiteConfig } from '@/lib/site'

/**
 * The masthead — three stacked rows, in the order a magazine puts them.
 *
 * S6, and a rebuild rather than a restyle of the previous one. The old
 * masthead was a dateline bar, a centred logotype and a nav between two
 * rules. Three things were wrong with it and all three were structural.
 *
 * **It offered no way into an account.** The reader identity work — register,
 * verify, sign in, reset, preferences, the dashboard — shipped complete and
 * tested, and there was not one link to any of it anywhere on the site, in
 * the masthead or the footer. A reader could only reach it by typing the URL.
 * `Sign in` and `Subscribe` now sit in the utility row, which is the whole
 * fix.
 *
 * **It never said this was a magazine.** The edition line under the wordmark
 * is one span of Bebas in the only use of `--gold` on the site, and it is
 * doing real work: it asserts a print object with a number and a month, which
 * is what the subscription is eventually sold against. The Economist's whole
 * subscription proposition rests on the edition being a finished thing rather
 * than a feed, and this is the cheapest possible version of that claim.
 *
 * **The nav is the city's own vocabulary, and it now comes from the
 * registry.** `site.nav` is read from `engine.sites` with the baked config as
 * the floor (S1.3), so an editor renaming "Dining" to "Resto & Bars", or
 * adding Hotels, is a console edit rather than a deploy. That matters here
 * more than anywhere: the archive has 453 stay stories in Bali and 420 in
 * Jakarta, and until now there was no Hotels entry at all.
 *
 * Still a server component with no client JavaScript. The nav does not
 * collapse into a hamburger on desktop; on small screens it scrolls
 * horizontally, which keeps every section one tap away instead of two.
 */
export function Masthead({
  site,
  today,
  edition,
}: {
  site: SiteConfig
  today: string
  /** e.g. "The September Edition · No. 214". Omitted until the editions
   *  surface exists, rather than printed with an invented number. */
  edition?: string
}) {
  return (
    <header className="masthead">
      <div className="shell">
        <div className="masthead__util">
          <span className="masthead__dateline">{today}</span>
          <nav className="masthead__actions" aria-label="Utility">
            <Link href="/search">Search</Link>
            <Link href="/subscribe">Newsletter</Link>
            {/* Both of these are new, and the first one is the one that
                matters: it is the only entrance to an account system that has
                been complete and unreachable. */}
            <Link className="masthead__signin" href="/account/login">
              Sign in
            </Link>
            <Link className="masthead__subscribe" href="/subscribe">
              Subscribe
            </Link>
          </nav>
        </div>

        <div className="masthead__brand">
          <Link href="/" aria-label={site.name}>
            {/* eslint-disable-next-line @next/next/no-img-element -- local SVG, no optimisation wanted */}
            <img className="masthead__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          </Link>
          {edition ? <p className="masthead__edition">{edition}</p> : null}
        </div>
      </div>

      <div className="masthead__nav">
        <div className="shell">
          <nav aria-label="Sections">
            <ul className="masthead__nav-list">
              {site.nav.map((item) => (
                <li key={item.href}>
                  <Link className="masthead__nav-link" href={item.href}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </header>
  )
}

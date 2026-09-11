import Link from 'next/link'

import type { SiteConfig } from '@/lib/site'

/**
 * The masthead. Server component — no client JS.
 *
 * Structure is deliberately print-derived: dateline bar, centred logotype,
 * then navigation between two rules. The nav does not collapse into a
 * hamburger on desktop; on small screens it scrolls horizontally, which
 * keeps every section one tap away instead of two.
 */
export function Masthead({ site, today }: { site: SiteConfig; today: string }) {
  return (
    <header className="masthead">
      <div className="shell">
        <div className="masthead__bar">
          <span className="masthead__dateline">{today}</span>
          <nav className="masthead__utils" aria-label="Utility">
            <Link href="/subscribe">Subscribe</Link>
            <Link href="/search">Search</Link>
          </nav>
        </div>

        <div className="masthead__brand">
          <Link href="/" aria-label={site.name}>
            {/* eslint-disable-next-line @next/next/no-img-element -- local SVG, no optimisation wanted */}
            <img className="masthead__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          </Link>
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

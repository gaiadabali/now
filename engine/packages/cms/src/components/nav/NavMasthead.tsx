import Link from 'next/link'

import { loadSiteBrand } from '../../lib/siteBrand'
import { SurfaceKicker } from './SurfaceKicker'

/**
 * The city's masthead, at the top of the sidebar.
 *
 * The sidebar had no brand on it at all. The only mark in the chrome was the
 * 16px breadcrumb icon, which is a wayfinding dot, not a masthead — so the
 * admin's most persistent surface, the one an editor looks at all day, was
 * 275px of empty column with a grey group label at the top.
 *
 * S6 (docs/DESIGN-SYSTEM.md §5): the rail is `--ink` now, not a recessed
 * paper tint, so the wordmark — drawn in logo ink for the paper it ships on —
 * needs the same plate-behind-the-mark treatment `admin.css` already gives it
 * in dark theme (`html[data-theme='dark'] .now-nav-masthead__logo`). On this
 * rail that treatment is unconditional: the ink ground does not change with
 * the editor's own light/dark preference, any more than the reader site's
 * franchise band does (§1: "the same colour as the magazine's dark band,
 * doing a different job").
 *
 * Renders in `admin.components.beforeNavLinks`, so it sits inside Payload's
 * scroll container above the collection list — no template override, and it
 * keeps working when Payload changes the nav internals.
 */
export async function NavMasthead() {
  const brand = await loadSiteBrand()

  return (
    <div className="now-nav-masthead">
      <Link aria-label={brand?.logoAlt ?? 'NOW!'} className="now-nav-masthead__link" href="/team-editor">
        {brand ? (
          /* eslint-disable-next-line @next/next/no-img-element -- a local SVG
             wordmark; there is nothing for next/image to optimise. */
          <img alt={brand.logoAlt} className="now-nav-masthead__logo" src={brand.logo} />
        ) : (
          <span className="now-wordmark">
            NOW<span className="now-wordmark__bang">!</span>
          </span>
        )}
      </Link>
      <SurfaceKicker cityName={brand?.slug ?? null} />
    </div>
  )
}

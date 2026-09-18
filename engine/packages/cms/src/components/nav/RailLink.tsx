'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'

/**
 * A rail link that knows whether it is the current page.
 *
 * Payload computes `.active` / `.nav__link-indicator` (the 3px `--red` inset
 * edge, docs/DESIGN-SYSTEM.md §5) for its OWN nav — it can compare a route
 * to a collection slug because it built both. `NavConsole`, `NavReview`,
 * `NavPlatform` and `StaffLink` point at areas Payload does not know exist
 * (commerce, classification review, the platform console, staff — all plain
 * Next trees reading the platform database), so before this every one of
 * them rendered as permanently "not current", however the class list mimicked
 * Payload's own — Screenshot review during S6 caught it: `/team-editor/
 * platform` showed no active mark at all while its sibling collection links
 * did. This is that comparison, done once, shared by all four.
 *
 * `activeMatch: 'prefix'` is for a link that owns a whole subtree with no
 * sibling link sharing its prefix — `/team-editor/platform` stays current on
 * `/team-editor/platform/sites/[slug]`. The default, `'exact'`, is for links
 * that sit beside others whose own href IS their prefix — `NavConsole`'s
 * "Overview" (`/team-editor/commerce`) is a literal prefix of its own
 * sibling "Partners" (`/team-editor/commerce/orgs`), so prefix matching
 * there would light up Overview on every commerce page.
 */
export function RailLink({
  href,
  children,
  className = 'nav__link',
  activeMatch = 'exact',
}: {
  href: string
  children: ReactNode
  className?: string
  activeMatch?: 'exact' | 'prefix'
}) {
  const pathname = usePathname()
  const active = pathname === href || (activeMatch === 'prefix' && (pathname?.startsWith(`${href}/`) ?? false))

  return (
    <Link className={active ? `${className} active` : className} href={href}>
      {active ? <span className="nav__link-indicator" /> : null}
      {children}
    </Link>
  )
}

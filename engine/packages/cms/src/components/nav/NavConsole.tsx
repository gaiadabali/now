import Link from 'next/link'

/**
 * The commerce console, in the sidebar where it can be found.
 *
 * `/team-editor/commerce` has existed since the console was absorbed
 * (docs/ADMIN-CONSOLIDATION.md Phase 3) and nothing has ever linked to it.
 * The only routes in were a badge inside the console's own masthead — which
 * you can only see once you are already there — and typing the URL. A
 * surface nobody can navigate to is not a surface.
 *
 * Renders in `admin.components.afterNavLinks`, so it sits under Payload's
 * collection list as a second group rather than pretending to be a
 * collection. It is not one: these pages read `now_platform.engine.*` over
 * direct SQL, not through Payload.
 *
 * ROLE-GATED, and gated on the right dimension. Editorial standing and
 * commercial standing are independent (ADMIN-CONSOLIDATION.md): being an
 * admin of a city's CMS is not a reason to see partner terms. So this keys
 * off `commerceRole`, which the platform strategy puts on the authenticated
 * user from the signed session claims — not off `role`.
 *
 * This is presentation only. Every page behind these links calls
 * `requireCommerceAccess()` before it queries anything, because a nav that
 * hides a link is a rendering convenience and never an access control.
 */

type NavUser = { commerceRole?: string } | null | undefined

const LINKS = [
  { href: '/team-editor/commerce', label: 'Overview' },
  { href: '/team-editor/commerce/orgs', label: 'Partners' },
  { href: '/team-editor/commerce/campaigns', label: 'Campaigns' },
]

export function NavConsole({ user }: { user?: NavUser }) {
  const role = user?.commerceRole
  if (!role || role === 'none') return null

  return (
    <div className="now-nav-group">
      <p className="now-nav-group__label">Commerce</p>
      <ul className="now-nav-group__list">
        {LINKS.map((link) => (
          <li key={link.href}>
            {/* `nav__link` deliberately: these should look and behave exactly
                like the collection links above them. Borrowing Payload's
                class keeps them in step if its nav styling moves. */}
            <Link className="nav__link" href={link.href}>
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

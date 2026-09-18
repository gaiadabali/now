import { RailLink } from './RailLink'

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
 * direct SQL, not through Payload. Since S3.1 they are a Payload custom view
 * (`admin.components.views` in payload.config.ts) rather than a route that
 * shadows Payload's own catch-all, which is what lets `next/link` below
 * resolve as a client-side transition instead of a full reload.
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
 *
 * DELIBERATELY NOT `'use client'`. This component receives `user` as a
 * server prop (`@payloadcms/next/dist/elements/Nav/index.js` merges it into
 * `afterNavLinks`'s `serverProps`, not its much smaller `clientProps`), so
 * turning the whole component client-side would silently stop it receiving
 * `user` at all — the role check above would read `undefined` and the
 * entire Commerce group would vanish for every role, including admins. It
 * renders `RailLink` (`'use client'`, for `usePathname()`) as an ordinary
 * child instead, which is the normal shape for a server component that
 * needs one client-only capability: push the boundary down to the smallest
 * thing that needs it, not up to the thing that receives the data.
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
            <RailLink className="nav__link" href={link.href}>
              {link.label}
            </RailLink>
          </li>
        ))}
      </ul>
    </div>
  )
}

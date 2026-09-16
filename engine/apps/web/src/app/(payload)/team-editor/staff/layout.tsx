import Link from 'next/link'
import type { ReactNode } from 'react'

import { getSiteConfig } from '@/lib/site'

/* The house treatment for mastheads, tables, pills and empty states already
   exists, written for the commerce console next door. Importing it rather
   than restating 150 lines of the same rules means this surface cannot drift
   from that one — and the ticket asks for exactly that reuse. The file's
   location is now wrong for what it is (it is the team editor's plain-page
   stylesheet, not commerce's); moving it is a rename across two surfaces and
   belongs in its own change. */
import '../commerce/console.css'
import './staff.css'

import { EDITOR_ROOT } from './paths'

export const metadata = {
  title: 'Staff',
  description: 'Staff accounts and roles',
}

/**
 * Chrome for the staff surface. **Not a guard.**
 *
 * There is no auth check in this file, and that is deliberate rather than an
 * omission — `page.tsx` calls `requireStaffAdmin()` before it reads a row and
 * every action in `actions.ts` calls it again before it writes one. A layout
 * runs for rendering, not for access: Next can execute a page's data fetch
 * without it, and a server action never passes through it at all. See the
 * note on `requireCommerceAccess` in lib/auth.ts.
 *
 * Same shape as the commerce masthead, including the city mark. One account
 * opens both cities and this surface edits the identity *both* of them share
 * — the mark is there to say which hostname you happen to be standing on,
 * not to suggest the change is local to it.
 */
export default async function StaffLayout({ children }: { children: ReactNode }) {
  const site = await getSiteConfig()

  return (
    <>
      <header className="console__masthead staff__masthead">
        <Link href={EDITOR_ROOT} className="console__brand">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local SVG
              wordmark; there is nothing for next/image to optimise. */}
          <img className="console__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          <span className="console__brand-label">Staff</span>
        </Link>

        <Link href={EDITOR_ROOT} className="console__badge console__badge--link" title="Editorial — articles, places, events">
          editor
        </Link>
        <span className="console__badge" title="Accounts live in the platform database and are shared by every city.">
          platform-wide
        </span>
      </header>

      <main className="console__main staff__main">{children}</main>
    </>
  )
}

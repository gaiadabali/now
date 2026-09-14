import type { ReactNode } from 'react'
import Link from 'next/link'
import './globals.css'

export const metadata = {
  title: 'NOW! Console',
  description: 'Partner and campaign management',
}

/**
 * One of two root layouts; Payload's `(payload)` group has its own. There is
 * deliberately no shared `src/app/layout.tsx`, because Next only allows
 * multiple root layouts when nothing above them defines one.
 *
 * Auth is Payload's: every page under this group calls `requireUser()`
 * before it queries anything, and unauthenticated visitors are sent to
 * Payload's own login at /admin/login rather than a second login screen.
 *
 * Still read-only against commerce data. Auth was the precondition for
 * writes, not the whole of it — `engine.partnership_audit` expects an actor,
 * and the tables themselves are still Alembic-owned in `engine` because
 * `now_link_resolver` reads them on the request path. See payload.config.ts.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="masthead">
          <Link href="/" className="brand">NOW! Console</Link>
          <nav>
            <Link href="/orgs">Partners</Link>
            <Link href="/campaigns">Campaigns</Link>
          </nav>
          <Link href="/admin" className="badge" title="Payload admin — manage console users">admin</Link>
          <span className="badge" title="Commerce data is read-only until E4.4 adds an editing surface.">read-only</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  )
}

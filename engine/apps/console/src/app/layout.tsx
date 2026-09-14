import type { ReactNode } from 'react'
import Link from 'next/link'
import './globals.css'

export const metadata = {
  title: 'NOW! Console',
  description: 'Partner and campaign management',
}

/**
 * READ-ONLY, DELIBERATELY. There is no authentication in front of this app
 * yet — the compose file puts it on loopback behind a reverse proxy and
 * nothing more. Adding mutations before there is an identity to attribute
 * them to would mean anyone who reaches the port can change link policy and
 * campaign budgets, with no audit trail. `engine.partnership_audit` exists
 * and expects an actor.
 *
 * So: this ships as a viewer. Writes land when auth does.
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
          <span className="badge" title="No authentication is in front of this app yet, so it is read-only by design.">read-only</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  )
}

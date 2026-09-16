import type { ReactNode } from 'react'
import Link from 'next/link'

import { getSiteConfig } from '@/lib/site'

import { consoleHref, EDITOR_ROOT } from './paths'
import './console.css'

export const metadata = {
  title: 'Console',
  description: 'Partner and campaign management',
}

/**
 * The commerce console's chrome.
 *
 * NOT a root layout, despite what it used to claim. These pages sit under
 * `(payload)`, whose layout is Payload's own `RootLayout` — it renders the
 * <html> and <body> for this subtree. This file rendered a second
 * <html>/<body> pair inside that one, which React nests exactly as written:
 * a document inside a document.
 *
 * What it is instead: a masthead over Payload's shell, for the pages that
 * fall outside Payload's catch-all and so get none of Payload's own nav.
 * The city mark is in it for the same reason it is on the sign-in screen —
 * one account opens both cities, and partner terms are the last place to be
 * unsure which one you are looking at.
 *
 * Auth is Payload's: every page under this group calls
 * `requireCommerceAccess()` before it queries anything. That is per route
 * and not in this layout on purpose — a layout guard is a rendering
 * convenience, not an access control (see lib/auth.ts).
 *
 * Still read-only against commerce data. Auth was the precondition for
 * writes, not the whole of it — `engine.partnership_audit` expects an actor,
 * and the tables themselves are still Alembic-owned in `engine` because
 * `now_link_resolver` reads them on the request path. See payload.config.ts.
 */
export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  const site = await getSiteConfig()

  return (
    <>
      <header className="console__masthead">
        <Link href={consoleHref()} className="console__brand">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local SVG
              wordmark; there is nothing for next/image to optimise. */}
          <img className="console__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          <span className="console__brand-label">Console</span>
        </Link>

        <nav className="console__nav">
          <Link href={consoleHref('/orgs')}>Partners</Link>
          <Link href={consoleHref('/campaigns')}>Campaigns</Link>
        </nav>

        <Link href={EDITOR_ROOT} className="console__badge console__badge--link" title="Editorial — articles, places, events">
          editor
        </Link>
        <span className="console__badge" title="Commerce data is read-only until E4.4 adds an editing surface.">
          read-only
        </span>
      </header>

      <main className="console__main">{children}</main>
    </>
  )
}

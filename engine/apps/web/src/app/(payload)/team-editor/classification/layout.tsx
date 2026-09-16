import type { ReactNode } from 'react'
import Link from 'next/link'

import { getSiteConfig } from '@/lib/site'

import { classifyHref, EDITOR_ROOT } from './paths'
import './report.css'

export const metadata = {
  title: 'Classification',
  description: 'What the engine decided about an article, and how sure it was',
}

/**
 * The classification report's chrome.
 *
 * NOT a root layout. These pages sit under `(payload)`, whose layout is
 * Payload's own `RootLayout` — it renders the <html> and <body> for this
 * subtree. Same masthead-over-Payload's-shell arrangement the commerce
 * console uses, and copied from it on purpose rather than invented: these
 * pages fall outside Payload's catch-all and so get none of Payload's nav,
 * and there should be exactly one answer in this app to "what does a
 * non-Payload admin page look like".
 *
 * The city mark is here for the reason it is on the sign-in screen and on the
 * console: one account opens both cities, the screens are identical, and a
 * classification decision written into the wrong city is not a decision that
 * can be spotted afterwards.
 *
 * Auth is Payload's, and it is per route: every page under this group calls
 * `requireEditorialAccess()` before it reads anything. Not in this layout, on
 * purpose — a layout guard is a rendering convenience, not an access control
 * (see lib/auth.ts).
 */
export default async function ClassificationLayout({ children }: { children: ReactNode }) {
  const site = await getSiteConfig()

  return (
    <>
      <header className="classify__masthead">
        <Link href={classifyHref()} className="classify__brand">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local SVG
              wordmark; there is nothing for next/image to optimise. */}
          <img className="classify__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          <span className="classify__brand-label">Classification</span>
        </Link>

        <nav className="classify__nav">
          <Link href={classifyHref()}>Queue</Link>
        </nav>

        <Link
          href={EDITOR_ROOT}
          className="classify__badge classify__badge--link"
          title="Editorial — articles, places, events"
        >
          editor
        </Link>
      </header>

      <main className="classify__main">{children}</main>
    </>
  )
}

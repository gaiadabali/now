import type { Metadata } from 'next'
import { Bebas_Neue, Cormorant, Heebo } from 'next/font/google'

import { Beacon } from '@/components/Beacon'
import { Masthead } from '@/components/Masthead'
import { Footer } from '@/components/primitives'
import { RevealObserver } from '@/components/RevealObserver'
import { accountsEnabled, currentReader } from '@/lib/reader'
import { getSiteConfig } from '@/lib/site'

import '@/styles/tokens.css'
import '@/styles/base.css'
import '@/styles/magazine.css'
import '@/styles/account.css'

/* The two faces the brand already uses. Self-hosted by next/font — no
   render-blocking request to Google, and no layout shift. */
const cormorant = Cormorant({
  subsets: ['latin'],
  weight: ['300', '400', '500'],
  style: ['normal', 'italic'],
  display: 'swap',
  variable: '--font-cormorant',
})

const heebo = Heebo({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  display: 'swap',
  variable: '--font-heebo',
})

/* The third face, and not a new one: the live theme already sets every
   section label in Bebas (`bebas-font` on a `bg-red` block). The rebuild
   had simply never carried it across, so labels were being set in Heebo
   capitals and reading as UI rather than as the magazine's own device. */
const bebas = Bebas_Neue({
  subsets: ['latin'],
  weight: ['400'],
  display: 'swap',
  variable: '--font-bebas',
})

/**
 * Nothing under this layout may be prerendered.
 *
 * ARCHITECTURE.md §3.5: ONE image serves every city, differentiated only by
 * `SITE_SLUG` at runtime. Static prerendering contradicts that directly —
 * it resolves `getSiteConfig()` at *build* time and bakes one city's name,
 * masthead, nav and `metadataBase` into an artifact that is supposed to be
 * city-agnostic.
 *
 * That was not hypothetical. `.env.local` (gitignored, `SITE_SLUG=bali`)
 * made local builds succeed while silently prerendering Bali's shell into
 * the shared image; CI, which has no such file, failed on `/_not-found`
 * with "SITE_SLUG is not set" and was the only thing telling the truth.
 *
 * `today` below is the second reason: it is `new Date()` formatted in the
 * site's timezone, so a prerendered masthead would display the build date
 * to every reader, forever.
 */
export const dynamic = 'force-dynamic'

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return {
    metadataBase: new URL(`https://www.${site.hostname}`),
    title: { default: site.name, template: `%s — ${site.name}` },
    description: site.tagline,
    openGraph: { siteName: site.name, locale: site.locale, type: 'website' },
    robots: { index: true, follow: true },
    // Per-city, from the site row — ONE image serves both cities (§3.5), so a
    // static app/icon file would give Bali readers Jakarta's mark. There was
    // no favicon at all before this: /favicon.ico returned 404 and browsers
    // fell back to a blank page icon.
    icons: {
      icon: [{ url: site.brand.favicon ?? site.brand.logo }],
      shortcut: [{ url: site.brand.favicon ?? site.brand.logo }],
      apple: [{ url: site.brand.appleIcon ?? site.brand.favicon ?? site.brand.logo }],
    },
  }
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const site = await getSiteConfig()
  const today = new Intl.DateTimeFormat(site.locale, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: site.timezone,
  }).format(new Date())
  // Read once, here, and handed down — not a second `currentReader()` call
  // inside Masthead itself. One session read per request keeps it obvious
  // where the cookie is ever inspected on this layout's render path.
  const reader = await currentReader()

  return (
    <html lang={site.locale} className={`${cormorant.variable} ${heebo.variable} ${bebas.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Masthead site={site} today={today} reader={reader} accountsEnabled={accountsEnabled()} />
        <main id="main">{children}</main>
        <Footer site={site} />
        {/* Reveal-on-scroll's one client component — see RevealObserver.tsx
            for why this replaced a pure-CSS `animation-timeline: view()`
            version that held anything below the fold at opacity 0 forever
            in a full-page screenshot, a print, or any other context that
            never scrolls a real viewport. Renders nothing. */}
        <RevealObserver />
        {/* One tag for the whole site. Pages that represent an entity emit
            `<meta name="nowb:entity">` and the beacon picks it up — see
            components/Beacon.tsx. Rendered last so it never delays paint;
            it is `async` anyway. */}
        <Beacon site={site.slug} />
      </body>
    </html>
  )
}

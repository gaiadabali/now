import type { Metadata } from 'next'
import { Cormorant, Heebo } from 'next/font/google'

import { Masthead } from '@/components/Masthead'
import { Footer } from '@/components/primitives'
import { getSiteConfig } from '@/lib/site'

import '@/styles/tokens.css'
import '@/styles/base.css'
import '@/styles/magazine.css'

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

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return {
    metadataBase: new URL(`https://www.${site.hostname}`),
    title: { default: site.name, template: `%s — ${site.name}` },
    description: site.tagline,
    openGraph: { siteName: site.name, locale: site.locale, type: 'website' },
    robots: { index: true, follow: true },
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

  return (
    <html lang={site.locale} className={`${cormorant.variable} ${heebo.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Masthead site={site} today={today} />
        <main id="main">{children}</main>
        <Footer site={site} />
      </body>
    </html>
  )
}

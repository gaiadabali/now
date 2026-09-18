import type { Metadata } from 'next'
import type { ServerFunctionClient } from 'payload'

import '@payloadcms/next/css'
import { handleServerFunctions, RootLayout } from '@payloadcms/next/layouts'
import { Bebas_Neue, Cormorant, Heebo } from 'next/font/google'
import React from 'react'

import config from '@payload-config'
import { getSiteConfig } from '@/lib/site'

/* The design tokens first, then the map from Payload's variables onto them.
   Order matters only between these two: `admin.css` reads `--paper`, `--ink`
   and `--red` out of `tokens.css`. Payload's own rules are inside
   `@layer payload-default`, so they lose to both regardless of order. */
import '@/styles/tokens.css'
import '@/styles/admin.css'

import { importMap } from './team-editor/importMap.js'

/* The same two faces as the reader site, bound the same way. Self-hosted by
   next/font — an admin that pulls from fonts.googleapis.com would be the
   only part of this deployment that phones out on every page load. */
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

type Args = {
  children: React.ReactNode
}

const serverFunction: ServerFunctionClient = async function (args) {
  'use server'
  return handleServerFunctions({
    ...args,
    config,
    importMap,
  })
}

/**
 * Nothing here may be prerendered, for the same reason as the reader
 * layout: `getSiteConfig()` resolves at build time under static rendering
 * and would bake ONE city's mark into an image that serves both
 * (ARCHITECTURE.md §3.5).
 */
export const dynamic = 'force-dynamic'

/**
 * The city's own favicon on the admin tab.
 *
 * Not cosmetic. An editor working both cities has two tabs open on what is
 * otherwise the identical screen at the identical path; before this, both
 * showed a blank page icon. The tab mark is the cheapest possible answer to
 * "which city am I about to publish into" — the in-page mark
 * (`admin.components.graphics.Icon`) is the other half of it.
 *
 * This covers the routes THIS app owns under the group: the staff login and
 * the commerce console. It does NOT reach Payload's own screens — its
 * catch-all page exports its own `generateMetadata`, and a page's metadata
 * beats its layout's for the same key. Those are served by
 * `admin.meta.icons` in packages/cms/payload.config.ts, from the same file.
 */
export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  const icon = site.brand.favicon ?? site.brand.logo
  return {
    icons: {
      icon: [{ url: icon }],
      shortcut: [{ url: icon }],
      apple: [{ url: site.brand.appleIcon ?? icon }],
    },
    // An admin has no business in an index, whatever the path robots.txt
    // happens to say this week.
    robots: { index: false, follow: false },
  }
}

// One of this app's two ROOT layouts — `(site)` has the other. Next allows
// that only while nothing above them defines one, which is why there is no
// `src/app/layout.tsx`: each group renders its own <html>/<body>, and the
// admin's is Payload's rather than ours.
//
// `htmlProps` is how the font variables reach that <html>: Payload renders
// the element itself, and next/font's `.variable` classes only apply to
// whatever element carries them.
const Layout = ({ children }: Args) => (
  <RootLayout
    config={config}
    htmlProps={{ className: `${cormorant.variable} ${heebo.variable} ${bebas.variable}` }}
    importMap={importMap}
    serverFunction={serverFunction}
  >
    {children}
  </RootLayout>
)

export default Layout

'use client'

import { useAuth } from '@payloadcms/ui'

import { RailLink } from './RailLink'

/**
 * The way into `/team-editor/front-page` from the sidebar.
 *
 * Same shape as `NavPlatform`/`NavReview`, and for the same reason: this is a
 * plain Next tree under `(payload)/team-editor/**` reading `engine.sites`
 * across the platform database, not a Payload collection, so Payload's own
 * nav (which lists collections) has no entry for it unless something puts
 * one here.
 *
 * **Gated on the same test as the screen itself** (`canEditFrontPage` in
 * `apps/web/src/lib/auth.ts` — editor or admin, deliberately not the
 * commerce dimension and deliberately not `admin`-only the way
 * `NavPlatform` is: SURFACES-PLAN's editor role exists to publish and
 * curate, and arranging the front page is that job, not account
 * administration). Duplicated here rather than imported because this
 * package must never import app code (`payload.config.ts`'s own header) —
 * if the two rules ever disagree, `FrontPageView.tsx`'s own check is the one
 * that decides, this only decides what the sidebar shows.
 *
 * Hiding the link from an author is cosmetic, exactly as on `NavPlatform`:
 * an author who types the URL still reaches the screen, read-only —
 * `FrontPageView.tsx`'s own header explains why that is a render decision
 * and not a redirect.
 */
export function NavFrontPage() {
  const { user } = useAuth() as { user?: { role?: string } | null }
  const role = user?.role
  if (role !== 'admin' && role !== 'editor') return null

  return (
    <RailLink activeMatch="prefix" className="now-nav-extra" href="/team-editor/front-page">
      Front page
    </RailLink>
  )
}

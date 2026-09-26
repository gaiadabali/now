'use client'

import { useAuth } from '@payloadcms/ui'

import { RailLink } from './RailLink'

/**
 * The review desk, in the sidebar — and only for the people who work it.
 *
 * **Why it is its own group and not a collection link.** The queue's rows are
 * a Payload collection (`classification-reviews`), but working them is not
 * editing rows: the decisions that matter are made against a whole *pattern*
 * ("every article whose WordPress category was News was classified
 * `type = stay` at 41% confidence"), and Payload's list view has no way to
 * express that. These are a Payload custom view (`admin.components.views` in
 * payload.config.ts, S3.1) reading `engine.entity_terms` over SQL rather than
 * a collection, so Payload's nav would never list them on its own.
 *
 * **Why it is separate from Collections at all.** Hansel's rule: review is
 * not add-and-modify. A writer opening the sidebar should see the things they
 * write; the queue is where someone answers for what the engine believes
 * about 6,485 of them, and mixing the two into one list says they are the
 * same kind of work.
 *
 * The role test here is cosmetic, exactly as in `StaffLink` — it hides a link
 * that would redirect anyway. `requireReviewerAccess()` in every view and
 * `requireReviewerActor()` in every action are the access control, and
 * `classification-reviews`' own `access` is what finally decides the write.
 */

const LINKS: Array<{ href: string; label: string; activeMatch?: 'exact' | 'prefix' }> = [
  { href: '/team-editor/classification/review', label: 'Review desk' },
  { href: '/team-editor/classification', label: 'By article' },
  // Plan P1.6: the place catalogue's own review queue.
  { href: '/team-editor/place-desk', label: 'Place desk', activeMatch: 'prefix' },
]

export function NavReview() {
  const { user } = useAuth() as { user?: { role?: string } | null }
  const role = user?.role
  if (role !== 'admin' && role !== 'editor') return null

  return (
    <div className="now-nav-group">
      <p className="now-nav-group__label">Curation</p>
      <ul className="now-nav-group__list">
        {LINKS.map((link) => (
          <li key={link.href}>
            {/* `RailLink` wraps `next/link`, not a plain `<a>`: since S3.1
                these routes are a Payload custom view reached through the
                SAME catch-all every collection link uses, so a client-side
                transition finds a match rather than a dead end. Before S3.1
                these routes shadowed the catch-all as their own literal Next
                pages, which is exactly why a real navigation used to be the
                only option. It also carries the active-state edge every
                other rail item gets (see `RailLink`'s own comment). */}
            <RailLink className="nav__link" href={link.href} activeMatch={link.activeMatch}>
              {link.label}
            </RailLink>
          </li>
        ))}
      </ul>
    </div>
  )
}

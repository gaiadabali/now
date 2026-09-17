'use client'

import { useAuth } from '@payloadcms/ui'

/**
 * The review desk, in the sidebar — and only for the people who work it.
 *
 * **Why it is its own group and not a collection link.** The queue's rows are
 * a Payload collection (`classification-reviews`), but working them is not
 * editing rows: the decisions that matter are made against a whole *pattern*
 * ("every article whose WordPress category was News was classified
 * `type = stay` at 41% confidence"), and Payload's list view has no way to
 * express that. These pages are plain Next routes under `(payload)` reading
 * `engine.entity_terms` over SQL, so Payload's nav would never list them.
 *
 * **Why it is separate from Collections at all.** Hansel's rule: review is
 * not add-and-modify. A writer opening the sidebar should see the things they
 * write; the queue is where someone answers for what the engine believes
 * about 6,485 of them, and mixing the two into one list says they are the
 * same kind of work.
 *
 * The role test here is cosmetic, exactly as in `StaffLink` — it hides a link
 * that would redirect anyway. `requireReviewerAccess()` in every page and
 * `requireReviewerActor()` in every action are the access control, and
 * `classification-reviews`' own `access` is what finally decides the write.
 */

const LINKS = [
  { href: '/team-editor/classification/review', label: 'Review desk' },
  { href: '/team-editor/classification', label: 'By article' },
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
            {/* Plain `<a>`, not next/link: these routes fall outside Payload's
                admin catch-all, so a client-side transition would try to
                render them inside Payload's shell and find no match. A real
                navigation is the correct behaviour here, not a fallback. */}
            <a className="nav__link" href={link.href}>
              {link.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

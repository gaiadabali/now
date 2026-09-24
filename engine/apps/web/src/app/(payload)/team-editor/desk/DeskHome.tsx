import Link from 'next/link'

import { getDeskData } from './data'
import type { DeskUser } from './data'

/**
 * The desk home — `/team-editor`'s dashboard, replaced.
 *
 * Registered as `admin.components.views.dashboard.Component` in
 * `payload.config.ts`, which is the one reserved key Payload's own
 * `DashboardView` (`@payloadcms/next/dist/views/Dashboard/index.js`) reads
 * before falling back to its own `DefaultDashboard` — not a `path`-matched
 * entry in `admin.components.views`, so it cannot collide with
 * classification/commerce/staff/platform's prefix registrations (S3.1's "one
 * registration per area" hazard does not apply to this key at all).
 *
 * Needs no `AdminViewFrame`. `getRouteData`'s `segments.length === 0` branch
 * hardcodes `templateType: 'default'` for the admin root regardless of
 * whether a custom dashboard is configured, and `RootPage` wraps whatever
 * renders there in `DefaultTemplate` itself — the sidebar is already there
 * by the time this component runs. `AdminViewFrame` exists for the OTHER
 * kind of custom view (one reached through `getCustomViewByRoute`'s generic
 * fallback, which never sets a template on its own) — see its own header for
 * the full story. `front-page/FrontPageView.tsx` is that kind; this is not.
 *
 * Owner's brief (2026-09-24): "the CMS ... needs to be easy to use by
 * non-devs" and the 2026-09-16 framing that curation — reviewing what the
 * engine decided, not filling in raw fields — is the editor's actual job.
 * Payload's stock dashboard is a list of collections and a "Site" link; it
 * answers nothing a writer opens this app to ask, which is "what needs me
 * today". This does.
 */
export async function DeskHome(props: Record<string, unknown>) {
  const user = (props.user ?? null) as DeskUser | null
  if (!user) {
    // Cannot happen in practice — `RootPage` redirects to login before this
    // ever renders for an unauthenticated request — but a dashboard that
    // assumes its own precondition rather than falling back is exactly the
    // kind of bug this file's siblings keep finding the hard way.
    return null
  }

  const desk = await getDeskData(user)
  const greeting = greetingFor(new Date())

  return (
    <div className="desk">
      <header className="desk__hero">
        <h1 className="desk__greeting">
          {greeting}, {desk.greetingName}
        </h1>
      </header>

      <section className="desk__section" aria-labelledby="desk-needs-you">
        <h2 className="desk__section-title" id="desk-needs-you">
          Needs you
        </h2>
        <ul className="desk__stats">
          <NeedsYouRow
            label="My drafts"
            count={desk.myDrafts.count}
            href={desk.myDrafts.href}
            emptyNote={
              desk.myDrafts.matched
                ? 'Nothing waiting in your own drafts.'
                : "We can't yet tell which byline is yours — add articles.createdBy to link a login " +
                  'to a byline. Showing 0 rather than guessing.'
            }
          />
          <NeedsYouRow
            label="Scheduled stories"
            count={desk.scheduled.count}
            href={desk.scheduled.href}
            emptyNote="Nothing scheduled ahead."
          />
          {desk.reviewQueue ? (
            <NeedsYouRow
              label="Classification review queue"
              count={desk.reviewQueue.count}
              href={desk.reviewQueue.href}
              emptyNote="The review queue is empty."
            />
          ) : null}
        </ul>

        <h3 className="desk__subsection-title">Published, with a problem</h3>
        <ul className="desk__stats">
          <NeedsYouRow
            label="No hero image"
            count={desk.problems.noHero.count}
            href={desk.problems.noHero.href}
            emptyNote="Every published story has a hero image."
          />
          <NeedsYouRow
            label="No standfirst"
            count={desk.problems.noStandfirst.count}
            href={desk.problems.noStandfirst.href}
            emptyNote="Every published story has a standfirst."
          />
          <NeedsYouRow
            label="No type chosen"
            count={desk.problems.noType.count}
            href={desk.problems.noType.href}
            emptyNote="Every published story has a type."
          />
          {desk.problems.noArea.unavailable ? (
            <li className="desk__stat desk__stat--muted">
              <span className="desk__stat-label">No area</span>
              <span className="desk__stat-value desk__stat-value--muted">Unavailable right now</span>
            </li>
          ) : (
            <NeedsYouRow
              label="No area"
              count={desk.problems.noArea.count}
              href={desk.problems.noArea.href}
              emptyNote="Every published story has an area."
            />
          )}
        </ul>
      </section>

      <section className="desk__section" aria-labelledby="desk-recent">
        <h2 className="desk__section-title" id="desk-recent">
          Recently published
        </h2>
        {desk.recentlyPublished.length === 0 ? (
          <p className="desk__empty">
            <em>Nothing published yet.</em>
            <br />
            THE FIRST STORY YOU PUBLISH SHOWS UP HERE
          </p>
        ) : (
          <ul className="desk__recent">
            {desk.recentlyPublished.map((a) => (
              <li className="desk__recent-item" key={a.id}>
                <Link className="desk__recent-title" href={`/team-editor/collections/articles/${a.id}`}>
                  {a.title}
                </Link>
                <span className="desk__recent-date">{formatWhen(a.publishedAt)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="desk__section" aria-labelledby="desk-actions">
        <h2 className="desk__section-title" id="desk-actions">
          Quick actions
        </h2>
        <div className="desk__actions">
          <Link className="desk__action desk__action--primary" href={desk.quickActions.write}>
            Write a story
          </Link>
          <Link className="desk__action" href={desk.quickActions.upload}>
            Upload photos
          </Link>
          {desk.quickActions.review ? (
            <Link className="desk__action" href={desk.quickActions.review}>
              Review queue
            </Link>
          ) : null}
          {desk.quickActions.frontPage ? (
            <Link className="desk__action" href={desk.quickActions.frontPage}>
              Front page
            </Link>
          ) : null}
        </div>
      </section>
    </div>
  )
}

function NeedsYouRow({
  label,
  count,
  href,
  emptyNote,
}: {
  label: string
  count: number
  href: string | null
  emptyNote: string
}) {
  if (count === 0) {
    return (
      <li className="desk__stat desk__stat--zero">
        <span className="desk__stat-label">{label}</span>
        <span className="desk__stat-note">{emptyNote}</span>
      </li>
    )
  }
  const value = <span className="desk__stat-value">{count.toLocaleString()}</span>
  return (
    <li className="desk__stat">
      <span className="desk__stat-label">{label}</span>
      {href ? (
        <Link className="desk__stat-link" href={href}>
          {value}
        </Link>
      ) : (
        value
      )}
    </li>
  )
}

function greetingFor(now: Date): string {
  const hour = now.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatWhen(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

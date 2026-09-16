import Link from 'next/link'
import type { ReactNode } from 'react'

import type { SiteConfig } from '@/lib/site'
import { subscribe } from '@/lib/newsletter'

/* ---------------------------------------------------------------- rules -- */

export function SectionRule({
  label,
  note,
  moreHref,
  moreLabel = 'See all',
}: {
  label: string
  note?: string
  moreHref?: string
  moreLabel?: string
}) {
  return (
    <div className="section-rule">
      <h2 className="section-rule__label">{label}</h2>
      {note ? <span className="section-rule__note">{note}</span> : null}
      {moreHref ? (
        <Link className="section-rule__more" href={moreHref}>
          {moreLabel} →
        </Link>
      ) : null}
    </div>
  )
}

/* --------------------------------------------------------------- badges -- */

/**
 * Partner disclosure. ARCHITECTURE.md §11 requires paid placement to be
 * visible to the reader; this component is the only sanctioned way to say so,
 * so the wording can never drift between surfaces.
 */
export function PartnerBadge() {
  return <span className="badge badge--partner">Partner</span>
}

export function Badge({ children, tone = 'plain' }: { children: ReactNode; tone?: 'plain' | 'live' }) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

/* -------------------------------------------------------------- byline --- */

export function Byline({ author, date, minutes }: { author: string; date: string; minutes?: number }) {
  return (
    <div className="byline">
      <span>
        Words by <span className="byline__name">{author}</span>
      </span>
      <span className="byline__sep">·</span>
      <time>{date}</time>
      {minutes ? (
        <>
          <span className="byline__sep">·</span>
          <span>{minutes} min read</span>
        </>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------- newsletter */

export function Signup({ site }: { site: SiteConfig }) {
  return (
    <aside className="signup">
      <p className="kicker kicker--red">The Weekly</p>
      <h2 className="signup__title">
        Everything worth your
        <br />
        attention, once a week.
      </h2>
      {/*
        Posts to the real server action, same as /subscribe. It used to POST
        to `/api/subscribe`, a route that has never existed — so this
        component, which appears on nearly every page, silently discarded
        every address typed into it.
      */}
      <form className="signup__form" action={subscribe}>
        <label className="visually-hidden" htmlFor="signup-email">
          Email address
        </label>
        <input
          className="signup__input"
          id="signup-email"
          name="email"
          type="email"
          placeholder="your@email.com"
          required
        />
        <input type="hidden" name="source" value="rail" />
        <button className="signup__btn" type="submit">
          Join
        </button>
      </form>
      <p className="meta" style={{ marginTop: 'var(--space-xs)', fontSize: 'var(--t-micro)' }}>
        {site.name} · no more than one email a week.
      </p>
    </aside>
  )
}

/* ------------------------------------------------------------------ foot -- */

export function Footer({ site }: { site: SiteConfig }) {
  return (
    <footer className="footer">
      <div className="shell">
        <div className="footer__cols">
          {site.footer.map((col) => (
            <div key={col.head}>
              <h2 className="footer__head">{col.head}</h2>
              <ul className="footer__list">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href}>{l.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="footer__base">
          <span>
            © {new Date().getFullYear()} {site.name}
          </span>
          <span>{site.tagline}</span>
        </div>
      </div>
    </footer>
  )
}

import Link from 'next/link'
import type { ReactNode } from 'react'

import type { SiteConfig } from '@/lib/site'
import { subscribe } from '@/lib/newsletter'

/* ---------------------------------------------------------------- band --- */

/**
 * The unit of the page (DESIGN-SYSTEM §2).
 *
 * Every section of every reader page is a band, and a band is exactly this
 * shell: a `<section>` (so the page is a sequence of landmarks, not a wall of
 * divs — §7 requires a heading per section, which `BandHead` supplies), a
 * `.shell` to hold the content to the page measure, and a stock. `tone`
 * chooses the stock a page is allowed three of: `paper` is the default and
 * needs no class, `ivory` is spent on the one department given weight,
 * `ink` on the one band per page that goes dark. Nothing enforces "only
 * three" in code — that discipline belongs to whoever calls this — but the
 * component only offers the three the system has.
 *
 * `hair` draws the band's own top rule for a `paper` band that follows
 * another `paper` band, where the stock does not already supply the
 * separation an `ivory` or `ink` band gets for free from its background.
 */
export function Band({
  tone = 'paper',
  hair = false,
  reveal = false,
  className,
  children,
}: {
  tone?: 'paper' | 'ivory' | 'ink'
  hair?: boolean
  /**
   * Reveal-on-scroll (DESIGN-SYSTEM §... motion): a small upward fade as the
   * band enters the viewport. Pure CSS, behind `@supports (animation-timeline:
   * view())` in magazine.css — nothing is hidden when the feature or
   * JavaScript is absent, `[data-reveal]`'s un-annotated state IS the
   * finished, visible page (base.css). Opt-in per band because the lead
   * package must never move: it is what a reader sees first, and a reveal
   * animation on the very first thing painted reads as a flash of missing
   * content, not as motion.
   */
  reveal?: boolean
  className?: string
  children: ReactNode
}) {
  const cls = ['band', tone !== 'paper' ? `band--${tone}` : null, hair ? 'band--hair' : null, className]
    .filter(Boolean)
    .join(' ')
  return (
    <section className={cls} data-reveal={reveal ? '' : undefined}>
      {children}
    </section>
  )
}

/**
 * The band opener (DESIGN-SYSTEM §2) — formerly `SectionRule`, which drew a
 * single rule with a label floating on it. The new markup is heavier because
 * the job changed: the kicker is now load-bearing information (a count, a
 * promise, a frequency — "453 stories", never decoration) sitting above a
 * real `--t-display` headline, not a caption beside a line.
 *
 * `kicker` is optional on purpose. §2's instruction is explicit: "if there is
 * nothing true to put there, leave it out" — an invented count is worse than
 * no kicker, so this does not synthesise one from `title`.
 */
export function BandHead({
  kicker,
  title,
  note,
  moreHref,
  moreLabel = 'See all',
  as: Heading = 'h2',
}: {
  kicker?: string
  title: string
  /** A small annotation under the title. Not part of §2's markup — the
   *  reader-facing bands never pass it — but useful on `/design` for
   *  captioning a specimen without inventing a second kicker. */
  note?: string
  moreHref?: string
  moreLabel?: string
  /** `h1` for the one band per page whose title is the page's own — a
   *  section index's own header uses this so the page keeps exactly one h1. */
  as?: 'h1' | 'h2'
}) {
  return (
    <div className="bandhead">
      <div className="bandhead__head">
        {kicker ? <span className="bandhead__kicker">{kicker}</span> : null}
        <Heading className="bandhead__title">{title}</Heading>
        {note ? <span className="bandhead__note">{note}</span> : null}
      </div>
      {moreHref ? (
        <Link className="bandhead__more" href={moreHref}>
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
 *
 * Solid red, not a tint: the previous version leaned on a `--red-wash`
 * background that has no token in the S6 system (§1 — "the chrome is white,
 * ink and red, and that is nearly all of it"). Filling the badge with the
 * accent itself, the way `Badge tone="live"` already does, reads as
 * unmistakably as the wash did without inventing a colour that was never
 * approved.
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

/**
 * The subscribe foot (DESIGN-SYSTEM home spec) doubles as the sidebar
 * newsletter unit on an article page — same form, same server action, two
 * different bands around it. It stays its own component rather than two so
 * the one thing that used to break silently (a POST to an endpoint that
 * never existed) can only be fixed once.
 */
export function Signup({ site }: { site: SiteConfig }) {
  return (
    <div className="signup">
      <p className="bandhead__kicker">The Weekly</p>
      {/* No hard-coded <br/> — that was the actual cause of "your" landing
          alone on its own line in a narrow column: a forced break between
          "your" and "attention" survives regardless of `text-wrap: balance`
          on `.signup__title`, because `text-wrap` only ever chooses among
          natural wrap points, never removes an explicit one. Plain text
          lets the column's own width decide where the two (or more) lines
          fall, and `balance` (magazine.css) evens them out. */}
      <h2 className="signup__title">Everything worth your attention, once a week.</h2>
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
      <p className="meta meta--micro" style={{ marginTop: 'var(--space-xs)' }}>
        {site.name} · no more than one email a week.
      </p>
    </div>
  )
}

/* ---------------------------------------------------------- area index --- */

/**
 * Explore (DESIGN-SYSTEM §3) — area name in Cormorant, count in Heebo micro
 * capitals, right-aligned and tabular. Shared between the homepage's flat
 * top-areas band and anywhere else a plain area list earns its own row
 * treatment, so the two can never drift on what a count means.
 *
 * The counts are stories published about that area, never venues — §3 is
 * explicit that this must not be implied, hence the footnote rather than a
 * bare number.
 */
export function AreaIndex({ areas }: { areas: Array<{ slug: string; label: string; count: number }> }) {
  if (areas.length === 0) return null
  return (
    <div className="grid--areas">
      {areas.map((a) => (
        <Link className="area-row" key={a.slug} href={`/search?facets=location:${encodeURIComponent(a.slug)}`}>
          <span className="area-row__name">{a.label}</span>
          <span className="area-row__count">{a.count}</span>
        </Link>
      ))}
    </div>
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

import Link from 'next/link'

import { HeaderScroll } from '@/components/HeaderScroll'
import type { SignedInReader } from '@/lib/reader'
import { signOut } from '@/lib/readerActions'
import type { SiteConfig } from '@/lib/site'

/**
 * The masthead — three stacked rows, in the order a magazine puts them.
 *
 * S6, and a rebuild rather than a restyle of the previous one. The old
 * masthead was a dateline bar, a centred logotype and a nav between two
 * rules. Three things were wrong with it and all three were structural.
 *
 * **It offered no way into an account.** The reader identity work — register,
 * verify, sign in, reset, preferences, the dashboard — shipped complete and
 * tested, and there was not one link to any of it anywhere on the site, in
 * the masthead or the footer. A reader could only reach it by typing the URL.
 * `Sign in` and `Subscribe` now sit in the utility row, and a signed-in
 * reader sees their own name there instead, linking to `/account` — the two
 * are the same slot in two states, not two different features.
 *
 * **It never said this was a magazine.** The edition line under the wordmark
 * is one span of Bebas in the only use of `--gold` on the site, and it is
 * doing real work: it asserts a print object with a number and a month, which
 * is what the subscription is eventually sold against. The Economist's whole
 * subscription proposition rests on the edition being a finished thing rather
 * than a feed, and this is the cheapest possible version of that claim.
 *
 * **The nav is the city's own vocabulary, and it now comes from the
 * registry.** `site.nav` is read from `engine.sites` with the baked config as
 * the floor (S1.3), so an editor renaming "Dining" to "Resto & Bars", or
 * adding Hotels, is a console edit rather than a deploy. That matters here
 * more than anywhere: the archive has 453 stay stories in Bali and 420 in
 * Jakarta, and until now there was no Hotels entry at all.
 *
 * **Edition 2 — a real mobile menu, and (third pass) a header that does not
 * move.** The first two passes gave the WHOLE masthead `position: sticky`
 * and shrank it on scroll — smaller logo, utility row folded away — and hid
 * it on scroll-down, revealing on scroll-up. The owner's own words: it
 * "creates jitters when we try to go down and up". Both behaviours changed
 * the header's HEIGHT while scrolling, which shifts every pixel of the page
 * under a reader's thumb — that is the jitter, not a perception of one.
 *
 * The fix the big news sites use, and this one now: only `.masthead__nav`
 * (the section row) is `position: sticky`, and its height never changes,
 * ever — nothing below it can move. The utility row and the big logo above
 * it scroll away normally, like any other part of the page. A compact logo
 * lives INSIDE the sticky nav row from the very first paint, sized exactly
 * as it will always be sized, and is switched between `visibility: hidden`
 * and `visibility: visible` — never a size change — once the nav row is
 * actually pinned to the top. That "is it pinned yet" question is answered
 * by an IntersectionObserver watching `.masthead__sentinel`, a zero-height
 * marker placed immediately above the sticky row: the moment the sentinel
 * scrolls past the top of the viewport, the row it precedes must be the one
 * now sitting at `top: 0`, and not a moment before or after — a check with
 * no scroll-position arithmetic and nothing that can lag or overshoot a fast
 * flick, which is what a `scrollY` threshold can do.
 *
 * `site.nav` still renders TWICE — a plain `<nav>` row shown at `62rem` and
 * above, and a native `<details>` drawer shown below it, both inside the
 * same sticky row so the drawer's own summary button is reachable at every
 * scroll position on a phone too — and `magazine.css` shows exactly one of
 * the two with `display: none` (which also keeps the hidden copy out of the
 * accessibility tree). This was a `<details>` forced open above `62rem` in
 * an earlier pass, on the theory that one tree could serve both — it could
 * not: Chromium hides a CLOSED `<details>`'s content via the
 * `::details-content` pseudo-element (`content-visibility: hidden`), which
 * nothing short of that same new pseudo can override, and browser support
 * for it is too new to bet a desktop nav row on. Duplicating seven links is
 * cheaper than that bet.
 *
 * `<HeaderScroll>` is the one piece of client JavaScript this component
 * pulls in, and it renders nothing — it owns the IntersectionObserver above
 * and closes the mobile drawer on navigation. It no longer tracks scroll
 * DIRECTION at all; there is nothing left for a direction to drive.
 */
export function Masthead({
  site,
  today,
  edition,
  reader,
  accountsEnabled = false,
}: {
  site: SiteConfig
  today: string
  /** e.g. "The September Edition · No. 214". Omitted until the editions
   *  surface exists, rather than printed with an invented number. */
  edition?: string
  /**
   * Fetched by the layout with `currentReader()` (lib/reader.ts), not here —
   * Masthead stays a plain render of whatever it is handed, matching every
   * other prop on this component, rather than becoming the one piece of
   * chrome that also owns a database read.
   */
  reader?: SignedInReader | null
  /**
   * Whether `/account/*` will serve at all — `accountsEnabled()` in
   * lib/reader.ts, which is false whenever no mail transport is configured.
   *
   * It has to be a prop rather than a call here because the account slot is
   * the one piece of chrome that can point at a route which legitimately does
   * not exist. Accounts FAIL CLOSED without SMTP (F141: `/account/*` once
   * shipped to production with no mail and registration succeeded *wrongly*),
   * so on a deployment without a transport every `/account/**` route 404s —
   * and a masthead that links to sign-in anyway puts a broken link on every
   * page of the site. Caught by `scripts/smoke.sh`'s link crawl against the
   * production artifact, which reported "1 of 58 internal links are broken",
   * and not by any typecheck, because a `<Link>` to a missing route is only
   * wrong at click time.
   */
  accountsEnabled?: boolean
}) {
  // Rendered twice (see the doc comment above) — a `key` prefix keeps React
  // from treating the two copies' list items as the same nodes across a
  // navigation, which does not matter for correctness here (both are plain
  // links) but avoids two identically-keyed lists existing in one tree.
  const navItems = (rowKeyPrefix: string) => (
    <ul className="masthead__nav-list">
      {site.nav.map((item) => (
        <li key={`${rowKeyPrefix}-${item.href}`}>
          <Link className="masthead__nav-link" href={item.href}>
            {item.label}
          </Link>
        </li>
      ))}
    </ul>
  )

  return (
    <>
      <header className="masthead">
        <HeaderScroll />
        <div className="shell">
        <div className="masthead__util">
          <span className="masthead__dateline">{today}</span>
          <nav className="masthead__actions" aria-label="Utility">
            <Link href="/search">Search</Link>
            <Link href="/subscribe">Newsletter</Link>
            {/* The entrance to an account system that has been complete and
                unreachable. Signed in, this reads as two controls doing two
                different jobs — "Your account" (where the bare uppercase
                name used to sit, which read as a label rather than a link:
                nothing about "DEWI" said it was clickable or where it went)
                and a real "Sign out" beside it, so ending a session never
                requires a trip to the dashboard first. Signed out, "Join"
                sits beside "Sign in" — the previous row only offered the
                one, and a reader with no account yet had no header path to
                get one short of guessing `/account/register`. */}
            {accountsEnabled ? (
              reader ? (
                <>
                  <Link className="masthead__reader" href="/account">
                    <span className="masthead__greeting">Hi, {reader.name ?? 'there'} · </span>
                    Your account
                  </Link>
                  <form action={signOut} className="masthead__signout">
                    <button type="submit">Sign out</button>
                  </form>
                </>
              ) : (
                <>
                  <Link className="masthead__signin" href="/account/login">
                    Sign in
                  </Link>
                  <Link className="masthead__join" href="/account/register">
                    Join
                  </Link>
                </>
              )
            ) : null}
            <Link className="masthead__subscribe" href="/subscribe">
              Subscribe
            </Link>
          </nav>
        </div>

        <div className="masthead__brand">
          <Link href="/" aria-label={site.name}>
            {/* eslint-disable-next-line @next/next/no-img-element -- local SVG, no optimisation wanted */}
            <img className="masthead__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
          </Link>
          {edition ? <p className="masthead__edition">{edition}</p> : null}
        </div>
        </div>
      </header>

      {/* NOT inside `<header>` above — deliberately. `position: sticky`
          constrains an element to stay within its containing block's own
          box, and a short `<header>` (just the two rows above) runs out of
          "room" for a sticky descendant the moment the header itself has
          entirely scrolled past — proven with a minimal repro before
          landing this: nested inside a 150px-tall wrapper, the exact same
          sticky rule stopped clamping at `top: 0` past 100px of scroll and
          just scrolled away with its parent instead. Siblings of `<header>`
          at the page's own top level (both land as direct children of
          `<body>`, since `Masthead` itself has no wrapping element) give
          the sticky row the whole page as its effective containing block,
          which is what "stay pinned for the rest of the scroll" needs. */}
      {/* Zero-height, observed by `HeaderScroll`: while this is on screen the
          nav row below has not reached `top: 0` yet, and the moment it
          scrolls past the top of the viewport is the moment the row DOES
          reach it — the one signal the compact logo's visibility needs, with
          no scroll-position threshold to get wrong on a fast flick. */}
      <div className="masthead__sentinel" aria-hidden="true" />

      <div className="masthead__nav">
        <div className="shell masthead__nav-row">
          {/* Always in the DOM, always this size — `visibility` only
              (magazine.css), toggled by the sentinel above. A size change
              here would be exactly the jitter this whole redesign removes,
              so this logo never grows, shrinks, or is added/removed from
              layout; it is only ever shown or hidden in place. */}
          <Link className="masthead__compact-logo" href="/" aria-label={site.name}>
            {/* eslint-disable-next-line @next/next/no-img-element -- local SVG, no optimisation wanted */}
            <img className="masthead__compact-logo-img" src={site.brand.logo} alt="" />
          </Link>

          {/* Desktop row: plain, always in the DOM, hidden below 62rem with
              `display: none` — which also removes it from the a11y tree, so
              a screen-reader user below that width meets the drawer copy
              only. */}
          <nav className="navlist" aria-label="Sections">
            {navItems('row')}
          </nav>

          {/* Phone drawer: `open` is never set — closed is the correct
              default on a phone, and it is hidden entirely (not merely
              forced shut) at 62rem and above, where the row above is the
              one live copy. Living in this same sticky row is deliberate —
              the brief's "on a phone the same sticky row holds the Sections
              drawer button", so the drawer is reachable at every scroll
              position, not only at the very top of the page. */}
          <details className="navdrawer">
            <summary className="navdrawer__summary">
              <span className="navdrawer__icon" aria-hidden="true" />
              <span className="navdrawer__label">Sections</span>
            </summary>
            <nav className="navdrawer__panel" aria-label="Sections">
              {navItems('drawer')}
            </nav>
          </details>
        </div>
      </div>
    </>
  )
}

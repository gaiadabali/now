'use client'

import { useLayoutEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Reveal-on-scroll, corrected.
 *
 * The first version was pure CSS (`animation-timeline: view()`), which
 * turned out to break the exact rule it was built to honour: an element
 * that never scrolls into a real viewport — a full-page screenshot, a
 * print, a reader mode, some crawlers and renderers — sits at its `from`
 * keyframe (opacity 0) forever. Content was "visible without JS" and NOT
 * "visible without scrolling", and the brief's progressive-enhancement
 * rule covers both. See `base.css` for the fuller account; this is the
 * fix — one small client component, the IntersectionObserver allowance the
 * brief always reserved for this and that the CSS-only version never
 * ended up spending.
 *
 * What it does, once, per page:
 *
 * 1. If `prefers-reduced-motion: reduce`, do nothing at all — no class,
 *    no observer. Every `[data-reveal]` stays at its unconditional
 *    `opacity: 1` from `base.css` and this component might as well not
 *    exist for that reader.
 * 2. Otherwise, add `.reveal-ready` to `<html>` and hand every
 *    `[data-reveal]` element to ONE IntersectionObserver.
 * 3. The observer's first callback for an element decides everything, and
 *    the DEFAULT — until that callback runs — stays fully visible:
 *      - already intersecting → `.is-visible`, and stop watching. Shown
 *        immediately, no animation, exactly the brief's own words.
 *      - NOT intersecting → THIS is the only path to `.reveal-pending`
 *        (the class `base.css` actually hides), applied only once a
 *        callback has positively confirmed the element is off-screen.
 *
 * Deliberately NOT "measure with `getBoundingClientRect` before the
 * observer even exists, and pre-hide anything below the fold" — an
 * earlier version of this component did exactly that, and it re-broke the
 * bug this file exists to fix: a full-page screenshot resizes the
 * viewport to the page's whole height and captures it, and if that
 * happens before the observer's asynchronous callback has had a chance to
 * report anything, an element that was pre-hidden synchronously stays
 * hidden — visible-without-JS held, visible-without-a-real-scroll did not,
 * again. Deciding ONLY inside the observer's own callback means the
 * window where a resize-and-immediately-capture can outrun this component
 * ends with every element still at its unconditional `opacity: 1`, never
 * at the hidden one.
 *
 * Progressive enhancement, restated for this version: with no JavaScript,
 * `.reveal-ready` is never added, so `.reveal-pending` (even if some other
 * script added it, which nothing here does without the gate) has no effect
 * — `base.css`'s selector requires `html.reveal-ready` as a prefix. There
 * is no path from "no JS" to "hidden content" through this component, and
 * — per the paragraph above — no path from "JS present but a snapshot
 * beat it to the punch" either.
 *
 * Runs on every pathname change, not just mount: App Router keeps this
 * component mounted across a client-side navigation (same reasoning as
 * `HeaderScroll`'s drawer-close effect), so a new page's `[data-reveal]`
 * elements need their own pass rather than whatever the previous page left
 * behind.
 */
export function RevealObserver() {
  const pathname = usePathname()

  useLayoutEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const elements = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'))
    if (elements.length === 0) return

    document.documentElement.classList.add('reveal-ready')

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const el = entry.target as HTMLElement
          if (entry.isIntersecting) {
            el.classList.add('is-visible')
            io.unobserve(el)
          } else {
            el.classList.add('reveal-pending')
          }
        }
      },
      // A modest negative bottom margin: the element is a little way into
      // the viewport before it is considered "entered", which is what
      // keeps the reveal from firing the instant a sliver of it appears.
      { rootMargin: '0px 0px -10% 0px' },
    )
    elements.forEach((el) => io.observe(el))

    return () => io.disconnect()
  }, [pathname])

  return null
}

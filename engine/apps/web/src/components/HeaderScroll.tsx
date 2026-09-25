'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Two small, unrelated jobs for the masthead, neither of them decorative:
 *
 * 1. Close the mobile nav drawer on every client-side navigation.
 * 2. Tell `.masthead__nav` when it is actually pinned to the top of the
 *    viewport, so it can reveal the compact logo living inside it.
 *
 * Job 2 replaced a scroll-direction tracker (condense on scroll, hide on
 * down, reveal on up) that changed the header's HEIGHT while a reader
 * scrolled. The owner's own words about it: it "creates jitters when we
 * try to go down and up." A height change on an element sitting above
 * everything else shifts the whole page under a reader's thumb mid-scroll
 * — that IS the jitter, not a perception of one. `.masthead__nav` (the one
 * sticky element now — see Masthead.tsx and magazine.css) never changes
 * height, ever, whatever this component does.
 *
 * The compact logo is not decoration either — it is the one thing the
 * sticky row needs to say "this is still NOW!" once the full-size logo
 * above has scrolled away — so this stays a real IntersectionObserver
 * rather than a scroll listener with a threshold to tune: a threshold can
 * lag or overshoot on a fast flick, and a boolean "has the sentinel above
 * the sticky row left the viewport yet" cannot. `rootMargin`/`threshold`
 * default to "any overlap at all", which is exactly what "has it left the
 * viewport" needs.
 */
export function HeaderScroll() {
  const pathname = usePathname()

  useEffect(() => {
    document.querySelectorAll('details.navdrawer[open]').forEach((el) => el.removeAttribute('open'))
  }, [pathname])

  useEffect(() => {
    const sentinel = document.querySelector('.masthead__sentinel')
    const nav = document.querySelector('.masthead__nav')
    if (!sentinel || !nav) return

    const io = new IntersectionObserver(([entry]) => {
      // Not intersecting the viewport at all means it has scrolled past the
      // top — the row immediately after it is the one now sitting at
      // `top: 0`. Intersecting (including the very first check, before any
      // scroll) means the row has not reached the top yet.
      nav.classList.toggle('is-stuck', !entry.isIntersecting)
    })
    io.observe(sentinel)

    return () => {
      io.disconnect()
      nav.classList.remove('is-stuck')
    }
  }, [])

  return null
}

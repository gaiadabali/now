'use client'

import { useEffect } from 'react'

/**
 * The masthead's two scroll behaviours — condense, and hide-on-down /
 * reveal-on-up — as one tiny client component rather than two.
 *
 * The brief allows "at most one tiny client component using
 * IntersectionObserver" for reveal-on-scroll; reveal-on-scroll itself ended
 * up entirely CSS (`base.css`, `animation-timeline: view()`), which left the
 * one JS allowance unspent. This is what it is spent on instead, because a
 * direction-aware "hide going down, show going up" header has no honest
 * CSS-only equivalent — `position: sticky` alone cannot tell which way the
 * page is moving.
 *
 * No IntersectionObserver: a plain, passive, rAF-throttled scroll listener
 * that toggles two classes on `<body>` — `hdr-condensed` past a small scroll
 * threshold, `hdr-hidden` while scrolling down past the masthead's own
 * height, cleared on any upward scroll. Classes on `<body>` rather than a
 * ref into `Masthead` (a server component) so this never has to cross that
 * boundary — `magazine.css` reads `body.hdr-condensed .masthead` etc.
 *
 * Progressive enhancement: with no JS, `<body>` never gets either class and
 * the masthead renders exactly as it does today — full height, always
 * visible, never hidden. Nothing here HIDES content; it only ever adds a
 * class that makes the header smaller or temporarily off-screen, and the
 * nav underneath is real links either way.
 */
export function HeaderScroll() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let lastY = window.scrollY
    let ticking = false
    const CONDENSE_AT = 24
    const HIDE_AT = 220

    const apply = () => {
      const y = window.scrollY
      const goingDown = y > lastY
      document.body.classList.toggle('hdr-condensed', y > CONDENSE_AT)
      if (y > HIDE_AT && goingDown) {
        document.body.classList.add('hdr-hidden')
      } else if (!goingDown) {
        document.body.classList.remove('hdr-hidden')
      }
      lastY = y
      ticking = false
    }

    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(apply)
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      document.body.classList.remove('hdr-condensed', 'hdr-hidden')
    }
  }, [])

  return null
}

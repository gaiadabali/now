import { loadSiteBrand } from '../../lib/siteBrand'

/**
 * The square mark in the admin chrome — top-left of every screen, inside
 * Payload's breadcrumb "home" link (`.step-nav__home`, 16×16).
 *
 * This is the one piece of brand an editor sees on *every* page, which is
 * why it is a real component and not a CSS background: at 16px the only
 * thing distinguishing Payload's default mark from the client's is that it
 * is the client's, and a background image would carry no alt text into the
 * link that wraps it.
 *
 * Empty `alt`: the anchor around this already has a "Dashboard" title, so
 * announcing the mark again would just make the breadcrumb read twice.
 */
export async function SiteIcon() {
  const brand = await loadSiteBrand()

  if (!brand?.icon) return <FallbackMark />

  return (
    // eslint-disable-next-line @next/next/no-img-element -- local asset at a
    // fixed 16px; next/image would add a runtime optimisation pass and a
    // layout wrapper for no gain.
    <img
      alt=""
      className="graphic-icon"
      height={16}
      src={brand.icon}
      style={{ display: 'block', width: '100%', height: '100%', objectFit: 'contain' }}
      width={16}
    />
  )
}

/**
 * Shown when the city config is unreadable (see `loadSiteBrand`). A brand-red
 * disc rather than Payload's mark, so a missing config is visible to whoever
 * can fix it instead of looking like a deliberate choice.
 */
function FallbackMark() {
  return (
    <svg className="graphic-icon" height="100%" viewBox="0 0 16 16" width="100%" xmlns="http://www.w3.org/2000/svg">
      <circle cx="8" cy="8" fill="var(--now-red, #cd1719)" r="8" />
    </svg>
  )
}

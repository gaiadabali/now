import { loadSiteBrand } from '../../lib/siteBrand'

/**
 * The wide wordmark. Payload renders it on the views it owns that stand on
 * their own page — `/verify`, and its built-in login.
 *
 * The built-in login is unreachable here (the `users` collection sets
 * `disableLocalStrategy`, so the staff login at `/team-editor/login` stands
 * in its place and draws this mark itself). Registering the component anyway
 * is what keeps the two paths from drifting: whichever of them Payload
 * decides to render, the reader sees the city's own mark rather than
 * Payload's.
 */
export async function SiteLogo() {
  const brand = await loadSiteBrand()

  if (!brand) {
    return (
      <span className="graphic-logo now-wordmark" role="img" aria-label="NOW!">
        NOW<span className="now-wordmark__bang">!</span>
      </span>
    )
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- an SVG wordmark;
    // there is nothing for next/image to optimise.
    <img alt={brand.logoAlt} className="graphic-logo" src={brand.logo} style={{ maxWidth: '100%' }} />
  )
}

/**
 * Root layout — deliberately a pass-through. It renders no `<html>`.
 *
 * Two route groups sit under it and each owns a full document of its own:
 *
 *   (site)     the reader magazine  — `<html>` with the brand fonts, masthead
 *              and footer
 *   (payload)  the admin at /team-editor — Payload's own `RootLayout`, which
 *              renders `<html>`/`<body>` itself and cannot be told not to
 *
 * If this file rendered `<html>` as it used to, every admin page would ship
 * TWO of them. That is not a styling nuisance: the browser cannot hydrate a
 * nested document, so the admin returned a valid 200 and then died with
 * "Application error: a client-side exception has occurred". Server-side
 * checks could not see it — curl fetches the HTML and never runs React.
 *
 * Measured on the live site before the fix:
 *   /             <html> x1   ok
 *   /team-editor  <html> x2   broken in the browser
 *
 * So: nothing here, and each group brings its own document.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children
}

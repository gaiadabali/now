'use client'

import { usePathname } from 'next/navigation'

/**
 * The line under the logo that says which surface this is — "TEAM EDITOR ·
 * {city}" on the daily screens, "PLATFORM CONSOLE" on the one that reaches
 * every city at once (docs/DESIGN-SYSTEM.md §5: "the logo inverted at 26px
 * with the surface named under it in Bebas micro"). No city name appears in
 * this file itself (packages/cms's own `lint:site-literals` bans the word
 * anywhere in source, comments included) — `cityName` arrives already
 * resolved, from `NavMasthead`'s read of the deployed city's own config.
 *
 * A CLIENT component split out of `NavMasthead`, and the split is the whole
 * point of the file. `NavMasthead` is an async server component — it reads
 * `site.config.json` off disk once per process — and the only way to know
 * which surface is on screen is `usePathname()`, which does not exist on the
 * server side of a shared layout slot. Splitting the pathname read into its
 * own tiny client leaf keeps the disk read server-side and costs nothing per
 * render: Payload's own nav links already resolve through `next/navigation`,
 * so this is on the same client bundle regardless.
 *
 * Deliberately one boundary, not a route table. The platform console is the
 * one area whose data reaches every city from a single screen (D-S1,
 * docs/SURFACES-PLAN.md §3) — that is what makes it worth naming differently
 * from "Team editor" — so it is the one prefix this checks for. Commerce,
 * staff and classification are still work on *this* city and keep the
 * default label; splitting the kicker into five bespoke strings would be
 * signage for a distinction editors do not need to make.
 */
export function SurfaceKicker({ cityName }: { cityName: string | null }) {
  const pathname = usePathname()
  const onPlatform = pathname?.startsWith('/team-editor/platform') ?? false

  return (
    <p className="now-nav-masthead__kicker">
      {onPlatform ? 'Platform console' : cityName ? `Team editor · ${cityName}` : 'Team editor'}
    </p>
  )
}

/**
 * Comp-phase sample content. Replaced by: GUIDES → curated `guides`
 * collection, EVENTS → the `events` collection, PLACE → `places` + PostGIS.
 */
import raw from '@/fixtures/articles.json'

const ARTICLES = raw as { image: string }[]

/** Curated guides — the recirculation unit. Counts are illustrative. */
export const GUIDES = [
  { count: 24, title: 'The Dining Guide', href: '/guides/dining', image: ARTICLES[1]?.image },
  { count: 12, title: 'Where to Stay in Ubud', href: '/guides/ubud-stays', image: ARTICLES[5]?.image },
  { count: 18, title: 'Bars Worth the Detour', href: '/guides/bars', image: ARTICLES[6]?.image },
  { count: 9, title: 'A Weekend, Well Spent', href: '/guides/weekend', image: ARTICLES[9]?.image },
]

/** Events calendar stand-in — replaced by the `events` collection. */
export const EVENTS = [
  { date: '2026-09-19T19:00:00', title: 'Ubud Writers & Readers Festival', where: 'Ubud, Gianyar' },
  { date: '2026-09-24T18:30:00', title: 'Sanur Village Festival', where: 'Sanur, Denpasar' },
  { date: '2026-10-02T20:00:00', title: 'Bali Arts Alliance: Gamelan Night', where: 'Kerobokan, Badung' },
  { date: '2026-10-11T17:00:00', title: 'Nusa Dua Light Festival', where: 'Nusa Dua, Badung' },
]

/** Place profile stand-in — replaced by the `places` collection + PostGIS. */
export const PLACE = {
  slug: 'locavore-ubud',
  name: 'Locavore',
  type: 'Restaurant',
  cuisine: 'Modern Indonesian',
  area: 'Ubud',
  district: 'Gianyar',
  price: 4,
  partner: true,
  dek: 'The tasting-menu restaurant that taught an island to look at its own larder differently.',
  address: 'Jl. Dewisita No.10, Ubud, Kabupaten Gianyar, Bali 80571',
  hours: 'Tue–Sat · 18:00 — 23:00',
  phone: '+62 361 977733',
  vibe: ['Fine dining', 'Tasting menu', 'Date night'],
}

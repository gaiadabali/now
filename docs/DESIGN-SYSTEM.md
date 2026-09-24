# The Edition — design system

**Status:** S6 approved 2026-09-18; upgraded for Edition 2, 2026-09-24. This is the
build spec for both.
**Tokens:** [`engine/apps/web/src/styles/tokens.css`](../engine/apps/web/src/styles/tokens.css) — the
authority for every value. Nothing below invents a colour or a size; where a
number appears here it names a token.

Written because the design was approved as visual comps, and comps do not
survive being described from memory. Build from this file.

**What Edition 2 changed, and what it kept.** The owner's brief for this pass
was explicit: "the latest award-winning news layout... fast, with proper
animation... modern, but not too rigid and boring" — and, just as explicitly,
not a second redesign that throws away what S6 got right. So this revision
keeps every one of S6's three rules below unchanged, keeps the band system,
keeps the story card, keeps the brand's own faces and colours. What it adds:
**weight contrast** (a fourth thing under Rule 1), a **lead package** in place
of a single cover, **chrome** that condenses and collapses into a real mobile
menu, and **motion** — all as new sections, not replacements of the old ones.
If a page you remember from S6 looks unfamiliar below, it did not change; it
is filed under a section this revision added.

---

## 1. The direction, and the rules under it

The site is a magazine that is also a city guide. It reads top to bottom as
**one page of bands**, the way a contents page works — not as two products with
separate chrome, and not as a feed of identical cards.

An earlier pass split it into a light "READ" mode and a dark "GO OUT" mode.
That was rejected, and the reason is worth keeping: once half the site looks
like a listings app, the whole thing stops feeling like a magazine. The guide
is a **band**, not a second product.

Four rules carry the look. Breaking any one of them is what made the previous
attempt read flat and monotone, or — Edition 2's own findings — faint,
motionless and unusable at phone width.

**Scale.** The ratio between display type and captions is most of what reads as
expensive. `--t-cover` against `--t-micro` (10.5px, letterspaced
`--track-micro`). Do not meet in the middle. A band opener is `--t-display`; a
card headline is `--t-title`. Nothing between `--t-title` and `--t-display`.

**Weight contrast (Edition 2).** Scale alone was not enough: at card and index
sizes, Cormorant 300 read "faint and monotone" — the owner's own words, and
worst on Latest's dense row index, where the lightest weight in the system met
the smallest size in the system with no photograph beside it to carry any
weight of its own. So light (300) is now reserved for **cover and display
sizes only** — the cover/lead headline, a band opener, the greeting. A card
headline (a photograph does some of the hierarchy's work) takes **500**
(`.display--medium`). An index row with no photograph — Latest, the numbered
list — takes **600** (`.display--strong`), because the type alone is carrying
what a picture usually would. Nothing above `--t-title` ever takes the heavier
weights; the light cover voice is what makes the display sizes still read as
a magazine and not a headline generator.

**Stock.** Three grounds, and a page uses all three. `--paper` for news and
indexes; `--ivory` for one department given weight; `--ink` for **one** band per
page. A page that is white from top to bottom is the failure this replaced.

**The colour comes from the photography.** The chrome is white, ink and red,
and that is nearly all of it. `--gold` is for the edition line and nothing else.
Do not add accent colours to sections, tags or cards — if a page looks
colourless in development, that is placeholder imagery, not a missing token.

### Faces, and what each is for

| | |
|---|---|
| `--font-display` Cormorant, weight **300** at cover/display sizes, **500–600** at card/index sizes | every headline, the greeting, the numeral in a franchise band. |
| `--font-sans` Heebo | everything working — nav, meta, buttons, form fields, admin UI. |
| `--font-label` Bebas | section labels, panel titles, the edition line. Always uppercase, always `--track-label`. |

Italic Cormorant is the standfirst voice — `--t-lede`, used for deks and for
empty-state sentences. It is the one place italics appear.

Red is reserved: the mark, the **Partner** label (§11 requires it wherever a
placement appears), section labels, and the primary action. It is never
decoration.

---

## 2. The band system

Every section of every reader page is a band. A band is:

```
<section class="band [band--ivory | band--ink] [band--hair]" data-reveal>
  <div class="shell">
    <div class="bandhead">
      <span class="bandhead__kicker">453 STORIES</span>     ← Bebas, --red
      <h2 class="bandhead__title">Hotels</h2>               ← Cormorant 300, --t-display
      <a class="bandhead__more">Every stay →</a>            ← Heebo, --t-micro, right
    </div>
    …content…
  </div>
</section>
```

The kicker is **information, not decoration** — a count, a promise, a
frequency. "453 stories", "Chosen this week", "Updated monthly", "94
neighbourhoods". If there is nothing true to put there, leave it out.

`data-reveal` is optional (`<Band reveal>` in `components/primitives.tsx`) —
see §8. Never on the first band a reader sees; a reveal animation on the very
first thing painted reads as a flash of missing content, not as motion.

**The grid changes with the job.** This is what stops a long page reading as a
feed, and it is the single most important structural instruction here:

| Band | Grid |
|---|---|
| The lead package | large lead + 3–4 secondary tops, side by side; a "Just in" strip beneath both (§3) |
| The Edit | 4-up, portrait images (4:5) |
| A department (Hotels) | 1 large + up to 3 stacked side items, on `--ivory` |
| The franchise (the list) | oversized numeral + text + one portrait, on `--ink` |
| Latest | 3-column index, **no thumbnails**, hairline rules |
| Explore | 4-column area index, hairline rules |

Do not render every band as a card grid. If two adjacent bands use the same
grid, one of them is wrong.

---

## 3. Reader site

### Masthead — `components/Masthead.tsx`

Three rows: utility (dateline left; Search · Newsletter · **Sign in** ·
**Subscribe** right), centred logo with the optional edition line beneath, then
the nav between rules. `site.nav` comes from the registry, so sections are a
console edit.

The logo is `site.brand.logo` — the real SVG. Never typeset a wordmark.

**Sticky, and condensing (Edition 2).** The masthead is `position: sticky`
and shrinks as a reader scrolls: the utility row tightens, the brand row's
logo drops to 28px and the edition line disappears, giving a long article back
the vertical space the full masthead costs. Search, Sign in and Subscribe stay
— "reachable from the header" means at every scroll position, not only at the
top, so the utility row is the one row condensing never hides.

It also hides on scroll-down and reveals on scroll-up, past a small threshold,
so a reader scrolling through a long article gets the space back without
losing the header entirely — a tap upward always returns it. Both behaviours
are two classes (`hdr-condensed`, `hdr-hidden`) that `components/HeaderScroll.tsx`
toggles on `<body>`; the masthead's own markup never branches on them, and
without JavaScript the masthead simply never condenses or hides — full height,
always visible, exactly S6's masthead.

**A real mobile menu, not a sideways scroll.** Below `62rem`, `site.nav` renders
inside a native `<details class="navdrawer">` — closed by default, opened by a
`<summary>` that is a real hamburger-to-X icon. No JavaScript opens or closes
it: `Enter`/`Space` on the summary is native browser behaviour, and a screen
reader announces the disclosure state for free. Above `62rem`, `magazine.css`
forces the same markup open and lays the list out horizontally — one nav tree
serves both, and nothing here renders twice or reads `matchMedia`.

### The lead package (Edition 2 — replaces the single cover)

The first-screen complaint was specific: "the first screen is masthead plus a
single 21:9 cover — no secondary top stories, no timestamped latest." The lead
package is the fix, sized against the masthead's own measured height rather
than the viewport, so the next band's own heading is what a reader on a
1440×900 laptop sees at the edge of the first screen, not a hard cut mid-band.

- **The lead**, large, image-led, headline overlaid on a scrim at `--t-headline`
  scale (not the old `--t-cover` — a real archive headline at cover size
  overflowed a lead sized to share its row with a secondaries column; sized
  instead so an 11-word headline fits the box it is given). Kicker above in
  Bebas, meta below in Heebo capitals.
- **3–4 secondary top stories** beside it (`card--horizontal`, scoped to a
  smaller thumbnail here than the same variant's other use in a department
  band — measured against the lead's own fixed height, not the shared
  component's default).
- **A timestamped "Just in" strip** beneath both: real headlines with real
  times, in the index treatment (no thumbnails) in miniature. Not the deep
  `Latest` band further down the page — this is 3–4 items, that one is the
  full paginated archive.
- On a phone, the headline moves **below** the image rather than over it —
  "never clipped" is the brief's own phrase for what the old cover did at
  390px, and below the photograph there is no scrim contrast to get wrong.

Every story in the package — the lead, the secondaries, the strip — is
excluded from every band that follows (`lib/frontPage.ts`'s `used` set). The
previous page queried each band independently and the Hotels band re-led with
the cover story; nothing on the front page may appear twice now.

Do **not** size the lead to the viewport. It is a lead, not a hero — the
bands below it must be reachable on a laptop with a short scroll.

### Latest — an index, not a feed

Three columns, headline in Cormorant `display--strong` (600 — see Rule 1 of
§1), section in Heebo micro capitals, date right-aligned, `--hair` between
rows. **No thumbnails.** It holds roughly three times the stories per screen
that a card grid does, which is what a homepage needs after the first screen.
Twelve rows, then *Load more stories*.

### Explore

The neighbourhood index: area name in Cormorant, count in Heebo micro,
right-aligned, tabular. Four columns, `--hair` between rows. The counts are
**stories published about that area** — never implied to be venues. Footnote the
band: "Counts are stories published about each area."

This band is the site's competitive moat and should read as considered, not as
a tag cloud.

### Article page (Edition 2)

- **Headline / standfirst / byline hierarchy.** The standfirst (`.dek`) reads
  at `--body` ink on the article page specifically, not `--mute` — the shared
  colour every OTHER dek uses, correct beside a photograph but the reason the
  owner's own note called this "small grey italic" when it is the second
  thing a reader reads on the page itself. Byline carries reading time.
- **A wide hero with its caption**, 16:9, fading in on paint (opacity only —
  every image already reserves its own box, so this never costs a layout
  shift) — the 66ch measure and the drop cap, both unchanged from S6.
- **Pull quotes never cut mid-word.** `lib/html.ts`'s `sentenceBound` prefers a
  real sentence boundary within the limit and falls back to the last WORD
  boundary, never a raw character slice — the fix for the owner's own
  example, a pull quote that ended "through K…".
- **A reading progress bar**, pinned above even the condensed header:
  `animation-timeline: scroll(root)`, no scroll listener, nothing that can
  jank the frame it describes. Inert (zero width, not broken) wherever the
  browser does not support it.
- **A sticky aside** that tracks the reader down the prose column rather than
  ending where the prose happened to be shorter than the viewport: Share
  (WhatsApp, email — real links, no script) above the newsletter unit.
- **Rails from `getArticleRails()`, in order, already labelled** — never a
  rail this page builds itself, and never one that recommends by the story's
  own section (`lib/recommend.ts`'s "one rule"). More than one rail switches
  grid between them — the card grid for the first, the index treatment for
  the next — so a second rail does not read as the first one repeated.

### What must not appear

- A rail whose data does not exist. Events are all 2016–2020 and Most Read has
  no traffic yet; both are hidden, not rendered empty, and that is settled
  (S2).
- Invented counts, sample venues or placeholder headlines in shipped code.
- A "Save" affordance with no persistence behind it. `saved_items` exists and
  is empty (§4) — a button that claimed to save without writing anywhere would
  be exactly the invented content this rule already forbids. The article
  page ships Share, which is real, and leaves Save to whoever wires the write
  path (flagged in EDITION-2-PLAN, not silently skipped).

---

## 4. Reader dashboard — `/account`

It is the reader's page **inside the magazine**, so it keeps the masthead, the
nav and the edition line. The admin surfaces drop all three.

**Greeting band** on `--ivory`: "Good evening, {name}" at `--t-display` in
Cormorant 300, with "Reader since {month} · {city} edition" in Heebo micro
capitals, right-aligned on the same baseline.

**Panels**, two-column with a 320px aside. A panel is a `--edge` top rule, a
Bebas title, an optional right-aligned action in Heebo micro, then content.
Not a card — no border box, no shadow, no radius.

| Panel | State today |
|---|---|
| We think you like | **live** — chips from `stated_prefs`, with "Correct this →" |
| Continue reading | needs traffic — `interactions` |
| Saved | no data — `saved_items` exists, is empty |
| Your itineraries | not built — E5.4 |
| Aside: Membership · This month's edition · Account | membership is a proposal |

**Empty states are invitations, not blanks.** A dashed `--hair` box, one italic
Cormorant sentence at `--t-lede`, one Heebo micro line telling the reader how to
fill it:

> *Nothing kept yet.*
> THE BOOKMARK ON ANY STORY KEEPS IT HERE

Four empty panels with no invitation reads as a broken product, which is the
state a new reader arrives in.

Panels whose data does not exist yet still render, with their invitation. Do
not hide them — a reader cannot tell the difference between "not built" and
"you have none", and the invitation is what teaches the feature.

---

## 5. Admin — the desk and the console

The magazine is read; these are **operated**. The identity carries; the
treatment does not.

- Type scale comes **down**. `--t-display` is the largest thing on the page
  and appears once, as the screen title.
- `--hair` does more work; there is more rule and less whitespace than on the
  reader site.
- **State is form and colour, never a sentence.** A console is scanned, so what
  needs attention has to read before anything is read.

### The rail

`--ink`, 232px, full height. The logo at 26px, inverted, with the surface named
under it in Bebas micro ("TEAM EDITOR · BALI", "PLATFORM CONSOLE"). Groups are
Bebas at `--track-label` in `--invert` at 40% — **Editorial · Places · Engine ·
Platform · Settings**, matching `collections/groups.ts`. Items are Heebo 13px
with a right-aligned count in micro. The active item gets a 3px `--red` inset
left edge and a faint background lift.

Same colour as the magazine's dark band, doing a different job: there it is a
feature, here it holds the tool together and leaves the white for the work.

### The writing screen

The one idea worth protecting: **the headline field is set in Cormorant 300 at
`--t-display`**, on a `--hair` bottom rule with no box. A writer composes the
headline in the face and size a reader will meet it in, rather than typing into
a 14px input and hoping. Everything around it stays quiet so that lands.

- Web address below it, Heebo 13px, the domain in `--mute` and the slug in
  `--type`, with the hint: *"Filled in from the headline. Change it before
  publishing, never after."*
- Standfirst in italic Cormorant `--t-lede`, in a bordered field.
- Body: the two-pane surface that already exists — **Write** left, **How it will
  read** right on `--ivory`. Do not restyle its behaviour; it was rebuilt
  deliberately and its reasoning is in `BodyBlocksEditor.tsx`.
- Sidebar on `--ivory`: status pill + Publish, published-at, what it is about,
  what kind of writing, byline. Each with its one-line hint in `--faint`.

Tabs are **Story** and **Old site**, Heebo micro capitals, active one carrying a
2px `--red` underline.

### Status, as form

| | |
|---|---|
| Published | filled `--ok`, white type |
| Draft | filled `--hair`, `--body` type |
| Scheduled | filled `--gold`, white type |
| Governed (console) | filled `--ok` |
| From file (console) | filled `--hair`, `--mute` type |

### The console

Its job is one question per row: **is this governed here, or falling back to the
config file?** That distinction is invisible everywhere else — `psql` shows
`{}`, and a merged `getSiteConfig()` result looks identical to a real value once
the fallback has filled it in.

- KPI row: four figures, Cormorant 300 at 2.4rem over Heebo micro capitals. A
  figure that is bad turns `--red` — five of seven facets empty is a `--red`
  number, not a grey one.
- Registry table: one row per site, one chip per governed field.
- Registry-vs-file comparison: two columns, the winning side on `--ivory` with a
  3px `--ok` inset edge, the losing side in `--faint`. This is the screen where
  someone renames Dining to Resto & Bars.
- Facet coverage as bars: `--type` fill, and `--red` when the value is zero.

**The coverage figures are per city, and the screen must say so.** An earlier
draft of this section quoted a two-city total (8,052 location assignments and
"five facets at zero") as though one console screen showed it. It cannot: a
Payload process binds to exactly one city database, so the console reads
whichever city it is serving. Combining them needs the cross-city bridge
through `now_platform` in SURFACES-PLAN S5.4, which does not exist. Label the
scope on the screen rather than letting a single-city number read as the
platform-wide one — that is the same mistake as a "Most Read" rail that is
sorted by recency.

---

## 6. Copy

Words are design material. The register is a magazine's, not a product's.

- **Say what a thing does, in the reader's words.** "What it is about", not
  "primary type". "Web address", not "slug". "Old site", not "legacy".
- **A control names its own outcome.** Publish → "Published". Save → "Saved".
- **Errors explain and instruct, and do not apologise.** "Item 2 is missing a
  label or a link. Every item needs both — one incomplete item rejects the whole
  nav on read, and the site keeps whatever it had before."
- **Hints carry the consequence, not the mechanism.** "Keeps a rival hotel's
  advert off this page. Partners pay for that" beats "sets `primary_type`".
- Sentence case everywhere except Bebas labels, which are uppercase by design.

---

## 7. Accessibility floor — not optional, and not a later pass

- Visible keyboard focus on every interactive element. `--red` outline, 2px
  offset.
- Contrast: `--mute` on `--paper` and `--invert` on `--ink` both pass AA at body
  size. `--faint` is for captions only and must never carry meaning alone.
- Every band is a `<section>` with a heading; the nav is a `<nav>` with a label.
- `prefers-reduced-motion` is respected — `--dur` and `--dur-reveal` both
  collapse to 0, `--reveal-y` to 0px, and every `@supports`-gated animation is
  additionally wrapped in `@media (prefers-reduced-motion: no-preference)`, so
  a reader who asked for less motion gets none, not a smaller amount.
- The page must work at 360px with no horizontal scroll, and the reader site
  must not depend on hover for anything. The mobile nav drawer is a native
  `<details>`, keyboard-operable with no ARIA hand-written for it.

---

## 8. Motion (Edition 2)

"Fast, with proper animation" — the owner's brief — and, immediately after,
the constraint that makes it possible: **no animation library**. Everything
below is CSS, plus one small client component that owns exactly the one
behaviour CSS cannot express on its own.

**Tokens** (`tokens.css`): `--dur` (180ms) for anything that responds to a
direct interaction — hover, focus, the header condensing. `--dur-reveal`
(420ms) and `--reveal-y` (10px) for anything the reader is watching happen as
they scroll — long enough to see, short enough not to lag behind the scroll
that triggered it. Both collapse under `prefers-reduced-motion`.

**Reveal-on-scroll** — `[data-reveal]` in `base.css`. `animation-timeline:
view()`, `@supports`-gated: a band's own head and body settle a beat apart
(a small negative `animation-delay` in the scroll-driven timeline's own
percentage space) as it enters the viewport. Nothing here is a class a script
sets — the unannotated state is fully visible, which is what a browser
without the feature, or a reader without JavaScript at all, gets. Opt-in per
band (`<Band reveal>`) and never on the first band on a page.

**Image hover zoom** — `.card__img`/`.frontlead__hero-img` scale 1.02 inside a
clipped frame (`overflow: hidden` on the figure) on hover, 600ms. A clipped
frame rather than the image itself moving is what keeps the surrounding
layout from ever measuring the zoomed size.

**Link underline draw** — the masthead's own nav links only (the one place a
hover state is worth this much attention): a `background-size` strip grows
left to right rather than a `border-bottom` snapping on, because a border
cannot animate from a width of zero the way a background can.

**The header condense/hide transition** — `transform`/`box-shadow` only, on
`.masthead`, triggered by two classes `HeaderScroll.tsx` toggles on `<body>`.
The one client component this system uses, and it renders nothing: a
passive, rAF-throttled scroll listener, no IntersectionObserver needed
because reveal-on-scroll turned out to have a pure-CSS answer instead.

**Reading progress** — the article page's `.readbar`, `animation-timeline:
scroll(root)`. Same reasoning as reveal: `@supports`-gated, inert rather than
broken where unsupported.

**Image fade-in** — every content image (`.card__img`, `.article-hero__img`,
`.frontlead__hero-img`, `.lead__img`) plays a 480ms opacity animation on
paint. Opacity only, never touching layout, so this costs nothing toward CLS
— every one of these images already reserves its box via `next/image`'s
`width`/`height` or a `fill` parent with an explicit aspect-ratio.

**Everything above is additionally gated on `@media (prefers-reduced-motion:
no-preference)`** inside its own `@supports` block, so a reader who asked for
less motion gets a page that is fully rendered and fully interactive with
none of it playing — never a broken or half-hidden one.

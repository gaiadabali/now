# The Edition — design system

**Status:** approved 2026-09-18. This is the build spec for S6.
**Tokens:** [`engine/apps/web/src/styles/tokens.css`](../engine/apps/web/src/styles/tokens.css) — the
authority for every value. Nothing below invents a colour or a size; where a
number appears here it names a token.

Written because the design was approved as visual comps, and comps do not
survive being described from memory. Build from this file.

---

## 1. The direction, and the three rules under it

The site is a magazine that is also a city guide. It reads top to bottom as
**one page of bands**, the way a contents page works — not as two products with
separate chrome, and not as a feed of identical cards.

An earlier pass split it into a light "READ" mode and a dark "GO OUT" mode.
That was rejected, and the reason is worth keeping: once half the site looks
like a listings app, the whole thing stops feeling like a magazine. The guide
is a **band**, not a second product.

Three rules carry the look. Breaking any one of them is what made the previous
attempt read flat and monotone.

**Scale.** The ratio between display type and captions is most of what reads as
expensive. `--t-cover` (up to 5.6rem) against `--t-micro` (10.5px, letterspaced
`--track-micro`). Do not meet in the middle. A band opener is `--t-display`; a
card headline is `--t-title`. Nothing between `--t-title` and `--t-display`.

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
| `--font-display` Cormorant, weight **300** | every headline, the greeting, the numeral in a franchise band. Light, large, tight (`--track-display`). |
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
<section class="band [band--ivory | band--ink] [band--hair]">
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

**The grid changes with the job.** This is what stops a long page reading as a
feed, and it is the single most important structural instruction here:

| Band | Grid |
|---|---|
| Cover | full-bleed, 21:9, headline overlaid bottom-left |
| The Edit | 4-up, portrait images (4:5) |
| A department (Hotels) | 1 large + 3 stacked side items, on `--ivory` |
| The franchise (the list) | oversized numeral + text + one portrait, on `--ink` |
| Latest | 3-column index, **no thumbnails**, hairline rules |
| Explore | 4-column area index, hairline rules |

Do not render every band as a card grid. If two adjacent bands use the same
grid, one of them is wrong.

---

## 3. Reader site

### Masthead — built, see `components/Masthead.tsx`

Three rows: utility (dateline left; Search · Newsletter · **Sign in** ·
**Subscribe** right), centred logo with the optional edition line beneath, then
the nav between rules. `site.nav` comes from the registry, so sections are a
console edit.

The logo is `site.brand.logo` — the real SVG. Never typeset a wordmark.

### Cover

The lead story, full-bleed, `aspect-ratio: 21/9`, with a bottom gradient scrim
and the headline over it at `--t-cover`, `max-width: 19ch`. Kicker above in
Bebas, meta below in Heebo capitals. One italic word inside the headline is
permitted and effective; more is not.

Do **not** size it to the viewport. It is a cover, not a hero — the bands below
it must be visible on a laptop.

### Latest — an index, not a feed

Three columns, headline in Cormorant `--t-title`, section in Heebo micro
capitals, date right-aligned, `--hair` between rows. **No thumbnails.** It holds
roughly three times the stories per screen that a card grid does, which is what
a homepage needs after the first screen. Twelve rows, then *Load more stories*.

### Explore

The neighbourhood index: area name in Cormorant, count in Heebo micro,
right-aligned, tabular. Four columns, `--hair` between rows. The counts are
**stories published about that area** — never implied to be venues. Footnote the
band: "Counts are stories published about each area."

This band is the site's competitive moat and should read as considered, not as
a tag cloud.

### What must not appear

- A rail whose data does not exist. Events are all 2016–2020 and Most Read has
  no traffic yet; both are hidden, not rendered empty, and that is settled
  (S2).
- Invented counts, sample venues or placeholder headlines in shipped code.

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
- `prefers-reduced-motion` is respected — `--dur` already collapses to 0.
- The page must work at 360px with no horizontal scroll, and the reader site
  must not depend on hover for anything.

# Live-site recon — what production actually says

Companion to [ARCHITECTURE.md](ARCHITECTURE.md) and [PROGRESS.md](PROGRESS.md).
Everything here was read from the two live WordPress sites on **2026-09-08**
via their public REST API, read-only, using
[`engine/packages/wp-harvest`](engine/packages/wp-harvest/README.md).

Nothing was written to either site.

> **Both sites expose an unauthenticated WP REST API** (`/wp-json/wp/v2`).
> That is what made this possible without hPanel or a database dump, and it
> is also a small exposure worth a deliberate decision — see
> [§7](#7-things-worth-deciding-about-the-live-sites).

---

## 1. Inventory

| | NOW! Jakarta | NOW! Bali |
|---|---:|---:|
| Published posts | 4,772 | 4,429 |
| Pages | 64 | 37 |
| Media (library) | 13,817 | 25,832 |
| `upcoming-events` | 489 | 182 |
| Categories | 76 | 50 |
| Tags | 2,311 | 2,319 |
| Authors | 70 | 53 |
| Comments | 0 | 4,103 |
| Sitemap URLs | 24,984 | 29,122 |
| Theme | `nowjakarta-git` | `nowbali` |
| Article date range | — | 2013-03-01 → 2026-09-07 |

**Jakarta's live numbers match the E1.1 dump extraction exactly** — 4,772
posts, 13,817 attachments, 76 categories. Cross-checking IDs: 4,772 of 4,772
articles present in both, **zero** on either side only. The dump is complete
and still current, independently confirmed against production.

Harvested output:

- `jakarta/content/harvested/` — 13,715 media, 4,772 posts, + report
- `bali/content/harvested/` — 24,746 media, 4,429 posts, + report

Bali is now populated for the first time; `bali/` was empty before this.

---

## 2. Blockers answered

### #4 — legacy permalink structure ✅

**`/%postname%/`** — flat, at the domain root, trailing slash. No date
segment, no category prefix. Identical on both sites. Confirmed against live
`link` values and both sitemaps.

### #6 — is a GA tag hardcoded in the theme? ✅ Yes

Google Tag Manager, pasted inline in the theme, **not** plugin-managed:

| Site | Container | Notes |
|---|---|---|
| Jakarta | `GTM-5JTV355` | + Facebook Pixel (`fbq`); snippet passed through LiteSpeed's JS deferral |
| Bali | `GTM-NJF57G3` | classic hand-pasted `<!-- Google Tag Manager -->` block |

No raw `gtag.js` / `UA-` / `G-` property in the theme — everything is behind
GTM, so **whatever analytics exist are configured inside those two
containers**, which needs GTM access to enumerate. Migration consequence: a
new front end must re-emit these container IDs (or deliberately retire
them), and the beacon coexists with GTM rather than replacing it.

### #2 — `wp-content/uploads` archive or file listing ✅ Listing obtained

`media` exposes `source_url`, `media_details.file`, `filesize` and every
registered size variant. That is a complete manifest of the media library —
`attachments.jsonl` in each `harvested/` directory.

**Footprint.** Only originals need migrating; imgproxy regenerates
derivatives:

| | Jakarta | Bali |
|---|---:|---:|
| Items manifested | 13,715 | 24,746 |
| Originals (measured) | **3.7 GB** (100% report a size) | 3.0 GB (55% report a size) |
| Originals (extrapolated) | 3.7 GB | **≈5.4 GB** |
| Derivatives | 6.3 GB / 83,234 files | ≈12 GB / 199,580 files |
| Full mirror | ≈10.1 GB | ≈17 GB |

Bali's figure is an extrapolation from the 13,722 items that report a
`filesize`, at the observed 0.22 MB mean. It is an estimate, not a
measurement; Jakarta's is exact.

**So the migration payload is ~9 GB of originals, not ~27 GB of everything.**

---

## 3. Follow-ups resolved with evidence

### F11 — `guid` is not a download URL ✅ Already handled, now proven

For all 13,715 attachments present in both sources, the extract's
reconstructed `url` **equals** the live `source_url` — 13,715 of 13,715,
zero differences. E1.1's `_wp_attached_file` reconstruction was exactly
right.

`guid` differs from `source_url` for **4,428 Jakarta items** (32%) and 490
Bali items, mostly pointing at `nj.gaiada.com`. Never fetch by `guid`.

### F16 — live-URL verification ✅ Closed

F16 was inconclusive because 19 of 50 sampled URLs (38%) timed out and
rate-limiting was assumed rather than shown. Replaced with an exact
set-comparison over the whole corpus, then HTTP requests spent only where
the comparison pointed:

| | |
|---|---:|
| Stored permalinks (E1.7 map) | 4,959 |
| Present in the live sitemap | **4,772** — every published article |
| Absent from the sitemap | 187 (legacy redirect-only URLs, correctly not canonical) |
| Of those 187: redirect (301/302) | **170** ✅ |
| Of those 187: **404** | **17** ⚠️ |
| Of those 187: timeout / error | **0** |

**0 timeouts across 187 URLs at 0.5 s spacing.** The rate-limiting theory
does not reproduce; F16's timeouts were most likely request concurrency, not
a server limit. (Sporadic connection failures *do* appear under bursts with
no delay — see [§6](#6-corrections-to-my-own-measurements).)

### F17 — 6 permalink conflicts ✅ Resolved by observation, no decision needed

F17 asked Hansel to adjudicate 6 collisions. Production already adjudicates
them; the live behaviour is the specification:

| Legacy URL | Live | Winner |
|---|---|---|
| `/new-restaurants-in-jakarta-2025-latest-openings-updated/` | 200 | native article (2025 edition) |
| `/the-ambassadors-round-table-edition-7/` | 200 | native article (edition 7) |
| `/explore-vegetarian-restaurants-…-world-vegan-month/` | 301 | Redirection plugin → `/vegetarian-restaurants-in-jakarta-2024-guide-to-vegetarian-eats/` |
| `/spectacular-year-of-the-water-rabbit-…-pantjoran-pik/` | 301 | Redirection plugin → `/imlek-exploring-chinese-new-year-in-jakarta/` |
| `/contribute-to-the-readers-dispatch/` | 301 | Redirection plugin → Google Forms (external) |
| `/new-magazine-announcement/` | 301 | Redirection plugin → Payhip (external) |

The general rule, which reproduces all six:

1. **Redirection-plugin rule** — wins over everything, including a live
   article with the same slug (the plugin hooks before the main query
   resolves).
2. **Current `post_name`** — serves 200.
3. **`_wp_old_slug`** — fires only when nothing above matched.

Preserve the two external targets **with their query strings**
(`?usp=header`, `?utm_source=website&utm_medium=slider&…`).

### F29 — inline media resolution ⚠️ Re-diagnosed; the recipe was aimed at the wrong problem

F29 recorded 59.7% exact-URL resolution and attributed 3,359 unmatched refs
to WordPress's `-150x150` size and `-6` duplicate filename suffixes, with a
"match by basename with suffix stripped" recipe.

Measured against the live manifest (`match_keys` implements exactly that
recipe, plus the registered size variants):

| | Jakarta | Bali |
|---|---:|---:|
| Distinct inline `<img src>` | 16,129 | 20,753 |
| Exact `source_url` match | 5,356 (33.2%) | 14,460 (69.7%) |
| **+ `match_keys` + size variants** | **9,405 (58.3%)** | **20,077 (96.7%)** |
| Genuinely external host | 70 | 35 |
| Still unmatched | 6,654 (41.3%) | 641 (3.1%) |

**Bali: effectively solved** — 96.7%, and the 634 residual `wp-content`
misses line up with the attachments REST cannot see (below) plus a
`wp-content/uploads/photo-gallery/` plugin store outside the media library.

**Jakarta: the residual is not a matching problem at all.** Of 6,654
unmatched refs:

| Count | What |
|---:|---|
| **6,161** | `/uploads/ckeditor/pictures/<id>/content_*.jpg` — **a second, pre-WordPress media store** |
| 479 | other paths |
| **14** | genuine `wp-content/uploads` misses |

So the suffix-stripping recipe took the true `wp-content/uploads` miss count
from ~3,359 to **14**. The rest were never WordPress attachments — they live
in a legacy CKEditor upload directory that the media library has no rows
for, so no amount of basename matching could ever have found them.

**This affects 2,278 of 4,772 Jakarta articles (47.7%).**

**The files are intact:** 40 of 40 sampled return HTTP 200, mean 106 KB.
Rough size at that mean: **≈650 MB** for the 6,161 referenced files. They
are mirrorable today, and they must be mirrored — otherwise nearly half the
Jakarta archive loses its inline imagery. **Bali has none of these** (zero
`ckeditor` refs), which fits Jakarta having been migrated onto WordPress
from an older platform.

---

## 4. New findings

### N1 — REST cannot enumerate every attachment (cause proven)

| | Reported by API | Harvested | Gap |
|---|---:|---:|---:|
| Jakarta media | 13,817 | 13,715 | **102** (0.7%) |
| Bali media | 25,832 | 24,746 | **1,086** (4.2%) |
| Bali comments | 4,103 | 4,096 | 7 |

Not a harvester bug. For all 102 Jakarta items the dump supplies the answer:
**0 of 102 have a published parent post.** WordPress's
`rest_check_post_read_permission` hides attachments whose parent is not
public from anonymous callers, and the `X-WP-Total` header counts them
anyway.

Jakarta is unaffected in practice — the dump has all 13,817. **Bali's 1,086
are unaccounted for and need either authentication or a dump.**

### N2 — Jakarta's WordPress was cloned from Bali's install

Three independent signs:

1. The Jakarta dump's table prefix is **`nb15_`** — "nb" as in NOW! Bali.
2. **All 17 of the 404ing legacy URLs are Bali content in Jakarta's
   Redirection table** — Mount Agung, Nyepi, Canggu, Amed, Jemeluk,
   "Bali's best gyms". Their targets return **200 on nowbali.co.id** and
   **404 on nowjakarta.co.id**.
3. Jakarta attachment `guid`s point at `nj.gaiada.com`, a staging host.

**Consequence for the redirect deploy: those 17 rules must not ship as
Jakarta redirects.** They are not Jakarta URLs; they are leftovers from the
clone. Dropping them is the correct action, and it removes the entire 404
population from the verification above.

### N3 — Bali's taxonomy is mostly *not* Jakarta's, and it is richer in venue signal

Only **16 of Bali's 50 categories** share a slug with Jakarta's 76. **34 are
Bali-only**, and the high-volume ones map almost directly onto the engine's
type vocabulary:

| Bali category | Articles | Reads as |
|---|---:|---|
| `restaurants-bars` | 360 | eat / drink |
| `spa` | 209 | wellness |
| `hotels-resorts` | 140 | stay |
| `activities` | 119 | do |
| `explore-bali` | 117 | do |
| `bali-bar-guide` | 76 | drink |
| `restaurant-guide` | 52 | eat |
| `cultural-sites` | 71 | do |

**This changes the scope of blocker #3.** The 75→facet mapping draft was
built from Jakarta's categories alone; the review is now **110 categories
across two cities**, not 75. Worth noting that Bali's own vocabulary carries
much stronger venue-type signal than Jakarta's, which may make Bali's
typing (E2.3) easier than Jakarta's was — the opposite of the usual
second-city assumption.

### N4 — Bali content quality is high

4,429 posts, all `publish`: **0** missing titles, **0** missing content,
**100%** category coverage, 195 (4.4%) without a featured image. Mostly
classic-editor HTML — only ~5% carry Gutenberg blocks.

### N5 — Plugins visible on the live sites

`redirection` (both — holds the legacy redirect table), `litespeed-cache`
(both), `contact-form-7` (both), `wordpress-seo` (Yoast, both),
`cptui` (Jakarta — provides `upcoming-events`), `simple-history` (Jakarta),
`hostinger-tools-plugin` (Jakarta), `health-check` (Bali).

Yoast's REST head output (`yoast_head_json`) is **disabled**, so focus
keywords are not reachable over REST on either site.

---

## 5. What live access still cannot give

The REST API is a public projection. It does **not** carry:

- **Unregistered `postmeta`** — Yoast focus keywords, MapPress geo, ACF
  field values. Jakarta has these from the dump; **Bali has none of them.**
- **Non-public statuses** — drafts, private, revisions.
- **Raw `post_content`** — `context=view` output has been through
  `the_content`: shortcodes expanded and `loading="lazy"` injected (present
  in 92% of a 400-post Bali sample). Harvested rows carry
  `content_is_raw: false`. The Jakarta content cleaner's 0.000% median loss
  was measured against *raw* column data, so that figure does not transfer
  to a rendered-HTML input.
- **The 1,086 Bali attachments** of N1.
- **The files themselves** — the manifest lists URLs and sizes.

**A faithful Bali migration therefore still needs a database dump.** What is
harvested is a genuinely useful Bali dataset — enough to plan, size, map
taxonomy and build against — but it is not the equal of Jakarta's
dump-derived extract, and it should not be loaded as though it were.

---

## 6. Corrections to my own measurements

Recorded because two of these looked like site problems and were mine:

1. **`HEAD` is rejected for static files.** An initial liveness check of the
   legacy CKEditor store reported 0 of 25 reachable. `HEAD` was the cause;
   the same URLs return 200 to `GET`. `wp-harvest`'s `check_urls` already
   falls back from `HEAD` to `GET` on 405/501 — this ad-hoc script did not.
2. **CRLF in a scratch URL list** broke every request in a shell loop
   (`\r` inside the URL → curl exit before connecting), which first read as
   "the whole legacy store is gone". Python's Windows newline translation.
   Also worth knowing: the harvested JSONL is CRLF for the same reason —
   consistent with the existing `extracted/` files, which the loader already
   consumes, so it is left alone rather than "fixed" inconsistently.
3. **Sporadic connection failures do occur** under bursts with no delay
   (seen in the cross-domain spot check). At the harvester's 0.35–0.5 s
   spacing, **0 failures across ~1,200 requests**. Keep the throttle.

---

## 7. Things worth deciding about the live sites

Not acted on — each is a change to production or a cost:

1. **The REST API is open to anonymous enumeration** of every post, author
   name, media URL and comment. Normal WordPress default, and it is what
   made this recon cheap, but it also means anyone can mirror the archive.
   Worth a deliberate keep-or-close call, ideally *after* the migration
   stops depending on it.
2. **Beacon deployment (blocker #5)** — now possible with wp-admin access,
   but it is a change to a live site, so it needs an explicit go-ahead. Note
   F15: `sites.hostname` must match `nowjakarta.co.id` / `nowbali.co.id`
   before the beacon goes live, because CORS is sourced from it.
3. **Mirroring the media** — ~9 GB of originals across both sites, plus
   ~650 MB of Jakarta's legacy CKEditor store. Straightforward but not free
   in time or bandwidth, and best done once, deliberately.
4. **A Bali database dump** — the one remaining hard blocker on a faithful
   Bali migration (§5).
5. **The 17 stale Bali redirects in Jakarta's table** (N2) — worth deleting
   on the live site too, not just excluding from the new redirect map.

---

## Reproducing this

```bash
cd engine/packages/wp-harvest
uv sync

export WP_HARVEST_BASE_URL_JAKARTA=https://www.nowjakarta.co.id
export WP_HARVEST_BASE_URL_BALI=https://www.nowbali.co.id

uv run wp-harvest inventory --site jakarta
uv run wp-harvest harvest   --site bali        # then jakarta; they share a host
uv run wp-harvest sitemap   --site jakarta
uv run wp-harvest verify    --site jakarta \
    --against ../../../jakarta/content/extracted/permalink_map.jsonl \
    --field legacy_url --http-check -1
```

Cost of the full run above: **~830 requests, 0 retries, ~12 minutes** — 375 Bali,
220 Jakarta, ~30 sitemap, 187 URL checks. Ad-hoc probes for the sections above
add roughly another 130.

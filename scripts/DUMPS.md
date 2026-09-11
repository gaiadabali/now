# Local dumps of the live WordPress sites

Pulled **2026-09-09**. Files live in `<site>/db/dumps/` and are **gitignored**
— they are a full copy of production content.

To refresh, see [Refreshing](#refreshing) at the bottom. Nothing here writes
to the live sites; every route is a login plus GETs.

---

## What is on disk

| Site | File | Size | Source |
|---|---|---:|---|
| Bali | `bali-all-*-manual.xml` | 144 MB · 30,649 items | **Hansel's Tools → Export → All content**, 2026-09-09 |
| Jakarta | `jakarta-all-*.xml` | 91 MB · 18,082 items | `wp-export-wxr.py --content all` |
| Jakarta | `jakarta-attachment-*.xml` | 47 MB · 13,817 items | `wp-export-wxr.py --content attachment` |
| Jakarta | `jakarta-pages-*.xml` | 1.2 MB · 251 items | `wp-export-wxr.py --content pages` |

### ⚠️ A WordPress "All content" export does not parse as-is

Bali's export contained **six `0x03` (ETX) bytes** — paste artefacts sitting
in two posts since 2019 and 2021. XML 1.0 forbids them, so the file WordPress
handed over **fails at line 1,193,864 in any XML parser, including
WordPress's own importer.** The copy in this repo has been repaired
(`repair_illegal_chars` in `wp-export-wxr.py`); the original in `Downloads/`
is untouched and still broken.

This is not a transport problem and it is not specific to the automated
route — the manual export hit the identical six bytes at the identical
offsets, which independently confirms the defect is in the source content.
**Repair any fresh export before using it.**

### Bali: one manual export beats the three automated ones

Hansel's single "All content" export is a strict **superset** of the three
files it replaced, so those were deleted. Verified:

| | Manual export | My automated set |
|---|---:|---:|
| Published articles | **4,429** | 4,429 |
| Set difference vs REST harvest | **0 either way** | 0 |
| Drafts · private | 109 · 2 | 107 · 2 |
| Attachments | **25,832** | 25,832 — *identical set, identical metadata* |
| Pages | 42 (the real `page` count) | 164 (incl. attached media) |
| **Comments** | **9,237** | — (REST saw only 4,096 approved) |
| `nav_menu_item` | **154** | — |
| ACF field definitions | **63 fields · 7 groups** | — |
| Contact Form 7 forms | **8** | — |
| `custom_css` · `wp_global_styles` · `wp_navigation` | **1 each** | — |
| Categories · tags · authors | 50 · 2,319 · 60 | same |
| Yoast focus keywords · metadescs | 2,930 · 2,663 | 2,930 · — |

The extras matter more than they look: **9,237 comments** is more than twice
what REST exposed, the ACF field *definitions* describe the shape of every
custom field the loader will read, and the nav menus record the site's own
information architecture.

**Worth doing the same for Jakarta.** Its automated files carry no comments,
no nav menus and no ACF definitions. The E1.1 SQL dump covers Jakarta's
gaps for now, but a manual export would refresh all of it in one file — and
is the only way to get its `nav_menu_item` and ACF definitions.

---

---

## Article completeness — verified, not assumed

`python scripts/verify-articles.py` cross-checks every independent source and
exits non-zero on any gap. Result as of 2026-09-09:

```
jakarta    COMPLETE — every source agrees
bali       COMPLETE — every source agrees
```

| | Jakarta | Bali |
|---|---:|---:|
| WXR dump (raw `post_content`) | 4,772 | 4,429 |
| REST harvest | 4,772 | 4,429 |
| SQL extract (E1.1) | 4,772 | *(none)* |
| **Set differences between sources** | **0** | **0** |
| Missing from the live sitemap | **0** | **0** |
| Duplicate slugs | 0 | 0 |
| Median body | 4,773 chars | 5,093 chars |
| Total article text | 26.3 MB | 27.8 MB |

**Three bodies look odd and all three are faithful copies, not losses:**

- `108105` and `107626` (empty) are exactly the two **F17 redirect stubs** —
  posts that exist only so the Redirection plugin has something to 301 to
  Payhip and Google Forms. Verified against `permalink_conflicts.jsonl`:
  both ids appear there. There is no content to lose.
- `754` "Jakarta in a Decade" has the body `<p>xxx</p>` — an editorial
  placeholder published in 2019 and never filled in. Identical in the E1.1
  SQL extract, so it is source-side.
- Bali `38228` "Mason Jungle Buggies" is a single YouTube embed. A legitimate
  video post.

So the verifier's verdict turns on **set completeness**, and treats empty
bodies as informational unless they exceed 0.5% of the corpus — a rate, not a
handful, is what indicates a broken export.

### Articles yes; event write-ups are a separate question

"Articles" above means post type `post`. The `upcoming-events` CPT is **not
exportable** (below), so its coverage differs:

| | Jakarta | Bali |
|---|---|---|
| REST harvest | 489 rows, all with content — but **rendered**, not raw | 182 rows, 181 with content, **rendered** |
| E1.1 SQL extract | **837 rows, 828 with raw content** | **none** |

Jakarta's events are covered by the E1.1 dump. **Bali's 182 event write-ups
exist only as rendered HTML** and have no raw-content source until SSH
exists. Small, but it is the one content gap left.

---

## Why this matters — what it unlocks

The REST harvest could not reach two things. Both are now on disk:

**1. Raw `post_content`.** REST returns rendered `the_content` output —
shortcodes expanded, `loading="lazy"` injected. WXR carries the actual
column. This retires the caveat in **F37**: a Bali load no longer has to
accept rendered HTML.

**2. Every `postmeta` row.** Including the ones REST omits entirely:

| Meta key | Jakarta | Bali | Why it matters |
|---|---:|---:|---|
| `_yoast_wpseo_focuskw` | **1,143** | **2,930** | eval ground truth (E2.7). Bali had *none* before. |
| `_wp_attached_file` | 13,289 | 23,709 | authoritative media paths (F11) |
| `_wp_attachment_image_alt` | — | 11,260 | alt text for accessibility + captioning |
| `wpb_post_views_count` | 4,785 | 9,292 | popularity prior — bot-contaminated, use the head only |
| `_thumbnail_id` | 4,773 | 4,332 | featured images |

ACF, MapPress and Yoast metadesc rows are present too.

---

## What is still NOT here

Be precise about this before treating the dumps as complete:

- **`upcoming-events`** (489 Jakarta · 182 Bali). The CPT is registered
  `can_export => false`, so `export.php` **silently falls back to exporting
  posts instead** — it does not error. Events are available only from the
  REST harvest (`<site>/content/harvested/events.jsonl`) or a real
  `mysqldump`.
- **The `options` table** — site settings, and the theme's GTM container IDs.
- **Plugin tables** — notably **Redirection's**, which holds the legacy
  redirect map behind F17/F35. The E1.7 permalink map already covers Jakarta;
  Bali's has never been extracted.
- **`term_taxonomy` term meta and term order.** Categories, tags and authors
  *are* in every WXR file's channel header, but as a flat list.
- **The media files themselves.** These are manifests; the bytes are still
  only on the server (~9 GB of originals, plus Jakarta's ~650 MB legacy
  CKEditor store — see F34).

**A `mysqldump` is still the better artifact** and would supply all of the
above. It needs SSH, which on Hostinger must be enabled per-account and uses
a password **separate** from the hPanel login. `scripts/wp-dump.sh` is
written and tested for the moment that access exists.

---

## Two defects found while doing this

Recorded because both would silently corrupt a load:

**1. `post_status=all` returns nothing.** WordPress's exporter puts the value
straight into `AND post_status = %s`, so `all` is matched *literally*. The
first run produced 34 well-formed, valid, **empty** files across both sites
and reported success. The script now sends an empty status, and treats "every
export returned 0 items" as a hard error rather than a note.

**2. Control bytes make a year's export unparseable.** Six stray `0x03` (ETX)
bytes — paste artefacts sitting in Bali post bodies since 2019 and 2021 —
are exported raw by WordPress and are illegal in XML 1.0. The script now
strips only the XML-illegal C0 bytes, and prints the surrounding text for
each one so the removal is reviewable rather than silent. In UTF-8 these
bytes never appear inside a multi-byte sequence, so removing them at byte
level cannot damage neighbouring characters.

---

## Refreshing

```bash
export WP_ADMIN_USER='...'
export WP_ADMIN_PASSWORD='...'
export WP_BASE_URL_JAKARTA=https://www.nowjakarta.co.id
export WP_BASE_URL_BALI=https://www.nowbali.co.id

for s in jakarta bali; do
  python scripts/wp-export-wxr.py --site "$s" --content all
  python scripts/wp-export-wxr.py --site "$s" --content attachment
  python scripts/wp-export-wxr.py --site "$s" --content pages
done
```

Stdlib only — no venv, no install. Roughly 6 minutes for both sites.

`--chunk-years` splits posts one year at a time if a single export ever times
out; it was not needed here, and it produces a small number of duplicate
attachment rows (the same image reused as a featured image across years), so
prefer `--content all` while it keeps working.

Once SSH exists, prefer:

```bash
scripts/wp-dump.sh              # both databases, complete
scripts/wp-dump.sh --uploads    # + media, incl. the F34 legacy store
```

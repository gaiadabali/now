# NOW! Jakarta — legacy WordPress categories → facet mapping

**Status: DRAFT for human review (E1.4).** Blocks E2.1 until reviewed and corrected (PROGRESS.md, Blockers #3).

**Source:** `backup_2026-09-08-1336_NOW_Jakarta_cc5fbb88fa25-db.gz`, restored read-only into a throwaway MariaDB container and queried with SQL (`nb15_terms` × `nb15_term_taxonomy` × `nb15_term_relationships` × `nb15_posts`, plus `_yoast_wpseo_primary_category` from `nb15_postmeta`). Counts are **distinct published posts** (`post_type='post' AND post_status='publish'`), decoded from HTML entities.

**Vocabulary:** every slug below exists in `engine/packages/taxonomy/seed/` and is seeded into `now_platform.engine.terms`. Slugs marked *proposed* in the seed files are additions beyond ARCHITECTURE.md §4 and are listed for sign-off in §D.

**Machine-readable twin:** `jakarta/site/taxonomy-mapping.json` (same content; the E2.1 classifier consumes that file). This Markdown is the review surface — after review, corrections are applied to the JSON and this file is regenerated from it.

## 0. What the dump actually says

- **4,772 published posts, 75 categories with ≥1 post**, plus one empty container (`Magazine Issue`) — hence 76 rows in `nb15_term_taxonomy`. ARCHITECTURE.md §6 says 4,679 / 75: the dump is newer (93 more posts); E1.1 should re-baseline.
- **The categories are hierarchical.** Parents: `Offers` → Dining/Stay/Experience Offers · `Dining` → Dining News, Reviews, Bar Guide, Restaurant Guides · `Art & Culture` → Art, Culture, Music, Made In Indonesia, Film, Design · `Features` → Business, Community, Opinion, NOW! People, Diplomatic Relations · `Lifestyle` → Education, Shopping, Health, Sports & Activities, Kids & Family · `Travel` → Explore Indonesia, Bali Updates, World Traveller · `Discover Jakarta` → History & Heritage, City Guides, Sites & Destinations · `Explore Indonesia` → Hidden Heritage · `Magazine Issue` → 34 print-issue themes.
- Since 2023 the editors file directly under the **parent** categories (Dining 24, Discover Jakarta 24, Travel 21, Features 20, Lifestyle 13, Art & Culture 28, Offers 55) — those give a type prior but no format.
- **34 categories are print-issue groupings** (2019–2020 themes such as 'A Jakarta Smorgasbord', 'Tech Talk', 'The Plague Of Our Time'; ~205 posts). They are not subjects and must not become facets — see §B.
- 4,548 posts (95.3%) have one category, 209 have two, 15 have three. Top co-occurrences: Dining Offers + Stay Offers 33 · Offers + Experience Offers 20 · Experience Offers + Stay Offers 13 · Experience Offers + Bali Updates 10 · Offers + Bali Updates 9 · Events + Dining News 8.
- `Uncategorized` has 83 posts (1.7%) — the '98.3% coverage' figure. It includes non-articles ('Order Form - NOW! Magazines').
- Yoast primary category exists on 2,439 posts (51%); focus keyword on 1,136 (24%). ARCHITECTURE.md §6 quotes 2,455 / 1,376 from an older snapshot.
- 2,355 posts (49%) are from 2019; **2021 has 2 posts** (the site was dormant); 2023–2026 average ~480/yr.

## 1. How to read the tables

- `type/subtype`, `format`, `location` are the four **required** facets. *per article* means the legacy category does not determine that facet — the classifier decides it from content, with the listed alternates as the candidate set.
- `Conf.` is the confidence that the stated prior is right for most posts in the category: **HIGH** = apply as a strong prior; **MEDIUM** = prior, classifier may override; **LOW** = no meaningful prior. **DECISION** = a human call is needed; the question is in §C.
- Default location when nothing in the category points elsewhere is the site's own node `jakarta` (a weak prior — the classifier should refine to a district/neighbourhood whenever the text names one).
- Legacy category is a **prior, not the answer** (ARCHITECTURE.md §6). E2.1 must still classify every article; the prior shifts probability and defines the review threshold.

## A. Editorial categories (41)

| # | Legacy category | Parent | Posts | Yoast primary | type/subtype | format | location | other facets | Conf. | Notes / alternates |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **News** | — | 551 | 356 | *per article* | `news` | `jakarta` | — | HIGH | Format is certain; type is per article — the biggest single bucket (356 Yoast-primary) and the most heterogeneous. Location defaults to the site node. **Alt:** type stay/hotel dominates (Pan Pacific, Citadines, Swiss-Belhotel, Club Med); event/* when the news announces a dated happening |
| 2 | **Dining Offers** | Offers | 402 | 238 | `eat/restaurant` | `offer` | `jakarta` | — | **HIGH · DECISION** | 33 co-occur with Stay Offers = hotel F&B packages; the venue is still the restaurant/outlet, so type stays eat. 134 of 402 are from 2019 — all expired. |
| 3 | **Events** | — | 396 | 201 | `event/*` | `event` | `jakarta` | — | HIGH | Type and format certain; subtype per article. `ends_at` must be extracted (324 tribe_events rows carry dates; the rest need text extraction) or the §8.A event-expiry filter has nothing to bite on. **Alt:** subtype per article: festival \| concert \| exhibition \| performance \| screening \| sports \| community \| conference \| pop-up |
| 4 | **Dining News** | Dining | 388 | 184 | `eat/restaurant` | `news` | `jakarta` | — | HIGH | Matches the §4 worked example. **Alt:** format people for chef interviews (William Wongso); type event/festival for food festivals (Jakarta Dessert Week) |
| 5 | **Stay Offers** | Offers | 261 | 82 | `stay/hotel` | `offer` | *per article* | — | HIGH | Type/format certain. Location is per article and often OUTSIDE Jakarta (Puncak, Surabaya, Bandung, Malang) — do not default to jakarta. Same expiry problem as Dining Offers. **Alt:** subtype resort \| villa \| serviced-apartment when explicit |
| 6 | **Art** | Art & Culture | 244 | 66 | *per article* | *per article* | `jakarta` | topic: `art` | **MEDIUM · DECISION** | 244 posts, 165 from 2019. Topic art is the only certain facet; type/format split roughly between dated events and commentary. **Alt:** event/exhibition + format event (announcements: 'Mirage at ARTSPACE'); event/performance + event (theatre: 'Tadashi Suzuki's King Lear'); editorial/culture + review\|feature (commentary); editorial/people + people (artist profiles) |
| 7 | **Reviews** | Dining | 230 | 54 | `eat/restaurant` | `review` | `jakarta` | — | HIGH | 152 of 230 are from 2019 — the 18-month half-life sinks them correctly without deleting them. **Alt:** drink/rooftop-bar or drink/wine-bar when the venue is a bar ('Hakkasan Jakarta Rooftop', 'Good Wines, Good Times') |
| 8 | **Experience Offers** | Offers | 207 | 104 | `stay/hotel` | `offer` | `jakarta` | audience: `family` | **MEDIUM · DECISION** | 10 co-occur with Bali Updates (Bali hotel packages -> location bali). Audience family is frequent but not universal. **Alt:** do/attraction + offer; event/festival + event (festive programmes) |
| 9 | **Business** | Features | 186 | 32 | `editorial/business` | `feature` | `jakarta` | topic: `business` | MEDIUM | 122 of 186 from 2019. Type/subtype solid; format per article between feature/news/opinion. **Alt:** format news for appointments and expansions ('Subendi to Lead Surabaya Oakwood'); format opinion for columns ('Why Indonesian Companies Keep Failing to Change') |
| 10 | **Education** | Lifestyle | 169 | 74 | `editorial/education` | `news` | `jakarta` | topic: `education`; audience: `family` | MEDIUM | Heavily school-sponsored (BINUS, ACG open houses) — these schools are E1.5 partner-roster candidates, not just content. **Alt:** format feature for explainers; event/community + event for open houses and tryouts |
| 11 | **Explore Indonesia** | Travel | 154 | 63 | `editorial/city-guide` | `city-guide` | *per article* | topic: `travel` | HIGH | Location per article under `other/*` (Makassar, Yogyakarta, Belitung, Central Java) with `other` as the fallback when the destination has no node. **Alt:** stay/resort + offer for hotel promos filed here ('Pullman Ciawi Vimala Hills') |
| 12 | **Community** | Features | 150 | 49 | `editorial/news` | `news` | `jakarta` | topic: `community` | MEDIUM | Topic community is certain; type/format split between dated charity events and features. **Alt:** event/community + event for charity balls and fundraisers (BWA Jakarta); editorial/people + people for community profiles; format feature for initiatives ('The Living Wall') |
| 13 | **Opinion** | Features | 148 | 45 | `editorial/opinion` | `opinion` | `jakarta` | — | **HIGH · DECISION** | 148 posts, 86 from 2019. **Alt:** topic sustainability for the 'Sustainability Matters' column |
| 14 | **Bali Updates** | Travel | 111 | 92 | *per article* | *per article* | `bali` | — | HIGH | Location bali is certain and the §4 example. §4 also says format news, but the titles are as often offers ('Enchanting Year-End Escape', 'Chic Beachfront Picnic Experience') — format per article. These 111 articles are the syndication set for now_bali (§3.5). 92 have Yoast primary = Bali Updates. **Alt:** type stay/resort\|hotel dominates (Six Senses, Sofitel, InterContinental, TRIBE); wellness/retreat\|spa (COMO Shambhala, Desa Potato Head); format news OR offer — roughly half each |
| 15 | **Shopping** | Lifestyle | 108 | 29 | `shop/boutique` | `news` | `jakarta` | topic: `fashion` | MEDIUM | Mostly fashion/brand news; treat type as a prior, not a rule. **Alt:** format guide ('The Groom's Guide to Bespoke Style'); shop/mall for mall pieces; misfiled civic pieces exist ('Civic Engagement 3.0') -> classifier override |
| 16 | **Health** | Lifestyle | 99 | 28 | *per article* | *per article* | `jakarta` | topic: `health` | **MEDIUM · DECISION** | Depends on approving `editorial/lifestyle`. **Alt:** wellness/clinic\|gym\|spa + news\|review; editorial/lifestyle + feature |
| 17 | **NOW! People** | Features | 99 | 26 | `editorial/people` | `people` | `jakarta` | — | HIGH | Dormant: 64 of 99 from 2019, 3 since 2024. Evergreen format per §4. **Alt:** topic diplomacy for ambassador interviews; topic business for founders |
| 18 | **World Traveller** | Travel | 94 | 11 | `editorial/city-guide` | `city-guide` | `international` | topic: `travel` | **HIGH · DECISION** | 82 of 94 from 2019. Evergreen format. |
| 19 | **Uncategorized** | — | 83 | 12 | *per article* | *per article* | `jakarta` | — | **LOW · DECISION** | 83 posts = the 1.7% 'uncovered' in ARCHITECTURE §6 (WP assigns Uncategorized when nothing else is chosen). **Alt:** wellness/gym + news; editorial/education; editorial/opinion; editorial/culture |
| 20 | **History & Heritage** | Discover Jakarta | 74 | 41 | `editorial/heritage` | `heritage` | `jakarta` | topic: `heritage` | HIGH | Evergreen. One misfiled promo ('The Maj Senayan') -> classifier override. **Alt:** location kota-tua \| menteng \| gambir when the piece is about a place; eat/street-food + heritage for food-heritage pieces ('Betawi Satay') |
| 21 | **Culture** | Art & Culture | 67 | 17 | `editorial/culture` | `feature` | `jakarta` | topic: `culture` | **MEDIUM · DECISION** | Textiles, books, magazines, dance — coverage of culture that is neither an event nor a venue. **Alt:** do/museum + guide (Museum Tekstil); shop/boutique\|artisan + news (Batik Corner, Gramedia); format review for book pieces |
| 22 | **Sports & Activities** | Lifestyle | 61 | 11 | *per article* | *per article* | `jakarta` | topic: `sports` | **MEDIUM · DECISION** | 44 of 61 from 2019. **Alt:** event/sports + event; do/sports-activity + guide\|news; editorial/lifestyle + feature; wellness/gym for fitness venues |
| 23 | **Offers** | — | 55 | 29 | `stay/hotel` | `offer` | *per article* | — | HIGH | The parent category used directly since 2020 (55 posts); overwhelmingly hotel festive packages. Location per article (Bandung, Gading Serpong, Kuningan, PIK). Same expiry problem as Dining Offers. **Alt:** event/conference + offer for MICE pieces ('Bekasi Means Business') |
| 24 | **Music** | Art & Culture | 49 | 4 | `event/concert` | `event` | `jakarta` | topic: `music` | HIGH | 38 of 49 from 2019 — all expired events; the 14-day half-life plus ends_at expiry handles them. **Alt:** editorial/culture + feature for scene pieces ('Hollywood in Jakarta'); event/festival for We The Fest / Papandayan Jazz Fest |
| 25 | **Green Living** | — | 47 | 8 | *per article* | *per article* | `jakarta` | topic: `sustainability` | HIGH | Exactly the §4 worked example: a topic, not a type. Topic is certain; type and format per article. **Alt:** editorial/opinion + opinion (columns); editorial/lifestyle + guide ('Going Green in Jakarta: Recycling, Composting...'); event/conference + event (MVB Sustainability Forum); stay/hotel + news (Santika 'Spirit of Sustainability') |
| 26 | **Kids & Family** | Lifestyle | 46 | 8 | *per article* | *per article* | `jakarta` | audience: `family`; topic: `family` | HIGH | Exactly the §4 worked example: an audience, not a type. **Alt:** do/attraction + guide ('Jakarta for Kids', Taman Safari); stay/hotel + offer (DoubleTree family getaway); editorial/lifestyle + feature (summer ideas) |
| 27 | **Made In Indonesia** | Art & Culture | 39 | 21 | `shop/artisan` | `feature` | `indonesia` | topic: `local-brands` | MEDIUM | Local makers and brands. Type shop/artisan when a brand or product is the subject (most), else editorial/people. Nationwide -> root node `indonesia`. **Alt:** editorial/people + people ('Meet the Makers'); location per article when the maker is placed (North Sumatra coffee) |
| 28 | **Film** | Art & Culture | 35 | 6 | `event/screening` | `event` | `jakarta` | topic: `film` | **MEDIUM · DECISION** | 28 of 35 from 2019. **Alt:** editorial/culture + review for film reviews ('Daly City') |
| 29 | **Art & Culture** | — | 28 | 26 | *per article* | *per article* | `jakarta` | topic: `art`, `culture` | LOW | Parent category used directly since 2023 (28 posts, 26 Yoast-primary). Only the topic is inferable; everything else per article. **Alt:** event/performance\|exhibition + event (SIPFest, Art Jakarta Papers); editorial/culture + feature (Teater Keliling at 50); editorial/heritage + heritage (Kali Besar, Borobudur); stay/hotel + offer (Gaia Hotel weekend) |
| 30 | **Bar Guide** | Dining | 28 | 9 | `drink/bar` | `guide` | `jakarta` | — | **MEDIUM · DECISION** | Type drink is certain. **Alt:** format listing (year-stamped roundups); format news (openings: 'OZONE Bar & Karaoke is Now Open!'); format review (single-venue: 'En Par'); subtype cocktail-bar \| pub \| rooftop-bar per article; shop/boutique + news for product pieces (Manta Spiced Rum) |
| 31 | **Design** | Art & Culture | 24 | 9 | `editorial/culture` | `feature` | `jakarta` | topic: `design`, `architecture` | MEDIUM | Depends on approving `editorial/culture`; topic design is the certain part. **Alt:** event/exhibition + event (Indonesia Design Week); shop/boutique + news (Melandas launch); editorial/people + people (designer profiles); editorial/heritage + heritage (architecture history) |
| 32 | **Dining** | — | 24 | 20 | `eat/restaurant` | *per article* | `jakarta` | — | HIGH | Parent category used directly since 2023 (24 posts). Type certain; format per article. Contains recipes ('The Rice Table Recipe #5') which have no §4 format — low volume, recommend editorial/lifestyle + feature rather than a new format. **Alt:** format listing for '[Updated]' series ('New Restaurants in Jakarta 2026') + series_key; format guide for timeless roundups ('Breakfast in Jakarta'); format review (Henshin, Li Lian); format offer (St. Regis Sunday ritual) |
| 33 | **Discover Jakarta** | — | 24 | 24 | `editorial/heritage` | `heritage` | `jakarta` | topic: `heritage` | HIGH | Parent category used directly since 2023 (24 posts, all Yoast-primary). Heritage-heavy; location often resolvable to a neighbourhood. **Alt:** editorial/city-guide + city-guide for neighbourhood pieces (Kemayoran, Jatinegara); do/attraction + guide for places (Jakarta Library, Taman Doa); location per article: gambir \| kota-tua \| menteng ... |
| 34 | **Travel** | — | 21 | 20 | `editorial/city-guide` | `city-guide` | *per article* | topic: `travel` | MEDIUM | Parent category used directly since 2023 (21 posts). **Alt:** stay/resort + review\|offer (AYANA Komodo); editorial/people + people (Evan Burns); editorial/news + news (International SOS advertorial); location other/* or international per article |
| 35 | **Features** | — | 20 | 17 | `editorial/*` | `feature` | `jakarta` | — | MEDIUM | Parent category used directly since 2024 (20 posts). Format feature is certain (print-style long-form); subtype per article. **Alt:** subtype per article: culture \| heritage \| people \| opinion \| business; topic per article: architecture, heritage, culture, local-brands |
| 36 | **City Guides** | Discover Jakarta | 19 | 15 | *per article* | `guide` | `jakarta` | — | **MEDIUM · DECISION** | 14 of 19 since 2024 — this is the current SEO-listicle programme. **Alt:** shop/mall + guide; wellness/spa + listing; do/attraction + listing ('Things to do in Jakarta (2024)'); editorial/culture + feature (Library of Humor Studies) |
| 37 | **Restaurant Guides** | Dining | 17 | 15 | `eat/restaurant` | `guide` | `jakarta` | — | **MEDIUM · DECISION** | Type certain. 13 of 17 since 2024. **Alt:** format listing + series_key for '[Updated]' and seasonal roundups; format news ('BIKO Group's Next Round Begins', 2016 awards) |
| 38 | **Hidden Heritage** | Explore Indonesia | 16 | 5 | `editorial/heritage` | `heritage` | `other` | topic: `heritage`, `culture` | HIGH | All 16 from 2019-2020; child of Explore Indonesia. Exposes a tree gap: `other` has city nodes but no regional nodes (Kalimantan, Maluku, Papua, Sulawesi). Evergreen format. **Alt:** location: Kalimantan (Punan), Sulawesi (Makassar), Maluku (Banda, Seram), Belitung, Lombok — most have no node, so `other` is the honest fallback |
| 39 | **Lifestyle** | — | 13 | 10 | `editorial/lifestyle` | `feature` | `jakarta` | — | **LOW · DECISION** | Parent category used directly since 2023 (13 posts); a grab-bag. **Alt:** event/community + event (Ascott Soiree); do/workshop + people (tea lesson); wellness/retreat + news (Kemang self-care centre); editorial/culture + feature (gamelan) |
| 40 | **Sites & Destinations** | Discover Jakarta | 12 | 8 | `do/attraction` | `guide` | `jakarta` | topic: `heritage` | HIGH | 12 posts since 2024, each about ONE landmark — prime E2.3 place-extraction input (places, not just articles). **Alt:** format heritage for history-led pieces (Istiqlal, Cathedral, Immanuel Church); do/museum + guide (Museum Nasional); location per article: gambir \| kota-tua \| west-jakarta |
| 41 | **Diplomatic Relations** | Features | 11 | 5 | `editorial/people` | `people` | `jakarta` | topic: `diplomacy`; series_key: `ambassadors-round-table` | MEDIUM | 11 posts since 2024, 9 are the 'Ambassadors Round Table' series -> series_key candidate. **Alt:** editorial/news + news (KCCI cultural exchange); event/conference + event if the Round Table is treated as a dated event |

## B. Print-issue categories (34) — parent `Magazine Issue`

These are the themes of individual print issues (2019–2020, a few stragglers), each holding 2–10 posts. **Recommendation: none of them maps to a facet.** Carry the issue as `articles.series_key = issue:<slug>` so the print archive stays browsable, let the classifier assign type/subtype/location from content, and use `format: feature` as the prior (magazine long-form). Topic/occasion hints below are weak and derived from the theme name only. Almost none of these posts carry a second category (co-occurrence shows 3 overlaps in total), so there is no other prior to fall back on.

| # | Legacy category | Posts | Years | type/subtype | format | location | hints | Conf. | series_key |
|---|---|---|---|---|---|---|---|---|---|
| 42 | **A Jakarta Smorgasbord** | 10 | 2019–2019 | *per article* | `feature` | `jakarta` | indonesian food; type eat per article | LOW | `issue:a-jakarta-smorgasbord` |
| 43 | **Food The Music Of Love** | 10 | 2019–2019 | *per article* | `feature` | `jakarta` | food; type eat per article | LOW | `issue:food-the-music-of-love` |
| 44 | **Love & Romance 2020** | 10 | 2020–2020 | *per article* | `feature` | `jakarta` | occasion: `date-night` | LOW | `issue:love-and-romance-2020` |
| 45 | **Indonesia S Creative Soul** | 9 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `art`, `culture` | LOW | `issue:indonesia-s-creative-soul` |
| 46 | **Property Architecture Design** | 9 | 2020–2020 | *per article* | `feature` | `jakarta` | topic: `property`, `architecture`, `design` | LOW | `issue:property-architecture-design` |
| 47 | **Art Culture The Realm Of Contemporary Arts** | 8 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `art` | LOW | `issue:art-culture-the-realm-of-contemporary-arts` |
| 48 | **Music & Nightlife** | 8 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `music` | LOW | `issue:music-and-nightlife` |
| 49 | **Capital Of Culture** | 7 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `art`, `culture` | LOW | `issue:capital-of-culture` |
| 50 | **Its A Man's World** | 7 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `fashion` | LOW | `issue:its-a-man-s-world` |
| 51 | **Staying Successful In Times Of Challenge** | 7 | 2020–2020 | *per article* | `feature` | `jakarta` | topic: `business` | LOW | `issue:staying-successful-in-times-of-challenge` |
| 52 | **Tech Talk** | 7 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `technology` | LOW | `issue:tech-talk` |
| 53 | **The Rhythm Of Life** | 7 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `music` | LOW | `issue:the-rhythm-of-life` |
| 54 | **Architecture Property & Design** | 6 | 2019–2026 | *per article* | `feature` | `jakarta` | topic: `architecture`, `property`, `design` | LOW | `issue:architecture-property-and-design` |
| 55 | **Building Future Leader** | 6 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `education` | LOW | `issue:building-future-leader` |
| 56 | **Jakarta S Music & Nightlife** | 6 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `music` | LOW | `issue:jakarta-s-music-and-nightlife` |
| 57 | **Season Of Love** | 6 | 2019–2019 | *per article* | `feature` | `jakarta` | occasion: `date-night` | LOW | `issue:season-of-love` |
| 58 | **Staying In Style** | 6 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `fashion` | LOW | `issue:staying-in-style` |
| 59 | **The Culinary Issue** | 6 | 2019–2024 | *per article* | `feature` | `jakarta` | food; type eat per article | LOW | `issue:the-culinary-issue` |
| 60 | **Travel & Holiday** | 6 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `travel` | LOW | `issue:travel-and-holiday` |
| 61 | **Festive Issue** | 5 | 2019–2019 | *per article* | `feature` | `jakarta` | occasion: `celebration` | LOW | `issue:festive-issue` |
| 62 | **Health In An Era Of Urbanisation** | 5 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `health` | LOW | `issue:health-in-an-era-of-urbanisation` |
| 63 | **Season Of Wonders** | 5 | 2019–2019 | *per article* | `feature` | `jakarta` | occasion: `celebration` | LOW | `issue:season-of-wonders` |
| 64 | **The Festive Season** | 5 | 2019–2022 | *per article* | `feature` | `jakarta` | occasion: `celebration` | LOW | `issue:the-festive-season` |
| 65 | **Travels Far & Near** | 5 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `travel` | LOW | `issue:travels-far-and-near` |
| 66 | **Can Jakarta Really Change** | 4 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `sustainability`, `transport` | LOW | `issue:can-jakarta-really-change` |
| 67 | **In With The New** | 4 | 2020–2020 | *per article* | `feature` | `jakarta` | — | LOW | `issue:in-with-the-new` |
| 68 | **Love & Romance** | 4 | 2019–2019 | *per article* | `feature` | `jakarta` | occasion: `date-night` | LOW | `issue:love-and-romance` |
| 69 | **Money Finance** | 4 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `finance` | LOW | `issue:money-finance` |
| 70 | **The Plague Of Our Time** | 4 | 2020–2020 | *per article* | `feature` | `jakarta` | topic: `health` | LOW | `issue:the-plague-of-our-time` |
| 71 | **The Travel Issue** | 4 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `travel` | LOW | `issue:the-travel-issue` |
| 72 | **City Of The Future** | 3 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `architecture`, `transport`, `sustainability` | LOW | `issue:city-of-the-future` |
| 73 | **Embracing The New Normal** | 3 | 2020–2020 | *per article* | `feature` | `jakarta` | topic: `health`, `business` | LOW | `issue:embracing-the-new-normal` |
| 74 | **Money & Finance** | 3 | 2019–2019 | *per article* | `feature` | `jakarta` | topic: `finance` | LOW | `issue:money-and-finance` |
| 75 | **10th Anniversary Issue** | 2 | 2019–2019 | *per article* | `feature` | `jakarta` | — | LOW | `issue:10th-anniversary-issue` |

Not in the tables: `Magazine Issue` itself (term 0 posts, pure container) — nothing to map.

## C. Decisions needed (with recommendations)

1. **Dining Offers** (402 posts) — Legacy offers have no campaign row, so `campaign.ends_at` (the §8.A hard filter) is undefined. Recommend: E1.8 extracts an end date from the text where present, else marks the offer expired at publish_date + 90 days. Offers must never surface in rails once expired; they remain searchable.
2. **Art** (244 posts) — Approve the proposed `editorial/culture` subtype. Without it, exhibition reviews and artist profiles have no home except `news` or `people`.
3. **Experience Offers** (207 posts) — Is 'Experience Offers' a stay category (hotel packages) or a do category (activities)? Evidence says hotel experience packages (staycations, festive programmes, kids' activities at ARTOTEL/Novotel/HARRIS). Recommend prior stay/hotel + offer, classifier may switch to do/* or event/*.
4. **Opinion** (148 posts) — Approve the proposed `opinion` format (half-life 540 d). Fallback if rejected: format feature (evergreen) — which would keep 2019 columns permanently fresh.
5. **Health** (99 posts) — Is 'Health' a venue category or a subject? Evidence is ~50/50: venue pieces (Siloam Hospitals -> wellness/clinic, Celebrity Fitness -> wellness/gym, Sepik -> wellness/spa) vs service journalism ('Are You Really Fit for Work?'). Recommend: topic health always; type per article — wellness/* when a venue is the subject, else editorial/lifestyle (proposed) + feature.
6. **World Traveller** (94 posts) — Approve the proposed `international` location root. `location` is a required facet and 115 articles (World Traveller + part of Travel) are about Singapore, Australia, Bhutan, Hong Kong. Children can be added once E2.1 reports the destination distribution.
7. **Uncategorized** (83 posts) — No prior at all — the classifier decides every facet. Also contains non-editorial pages ('Order Form - NOW! Magazines'). Recommend: every Uncategorized post goes to the E2.8 review queue regardless of confidence, and E1.8 flags obvious non-articles for exclusion below the quality floor.
8. **Culture** (67 posts) — Depends on approving `editorial/culture`.
9. **Sports & Activities** (61 posts) — Three different things share this category: spectator/charity fixtures (Asian Tigers Golf Tournament -> event/sports + event), participatory venues and clubs (Urban Climbers -> proposed do/sports-activity), and features about sport (traditional sports, Asian Games -> editorial/culture|lifestyle + feature). Recommend approving `do/sports-activity` and letting the classifier pick among the three.
10. **Film** (35 posts) — Approve the proposed `event/screening` subtype (film festivals are the majority: 100% Manusia, Festival Sinema Prancis, Europe on Screen, Balinale). Fallback if rejected: event/festival.
11. **Bar Guide** (28 posts) — §4 maps this to format guide, but the titles are mostly year-stamped roundups ('The Best Cocktail Bars in Jakarta ... (2026)', '8 Best Beer Bars') plus bar news/reviews. Recommend the boundary: period-stamped roundup = `listing` (540 d, series_key dedup); timeless = `guide` (evergreen). Confirm this definition — it decides whether 2019 roundups stay evergreen.
12. **City Guides** (19 posts) — Naming trap: these are venue roundups ('Best Shopping Malls in Jakarta', '10 Best Spas in Jakarta', 'Things to do in Jakarta (2024)'), not destination guides. Recommend: NOT format city-guide; type = the roundup's venue type per article (shop/mall, wellness/spa, do/attraction); format guide, or listing when year-stamped. Confirm.
13. **Restaurant Guides** (17 posts) — Same guide-vs-listing boundary as Bar Guide. 'New Restaurants in Jakarta 2025 [Updated]' and the Chinese New Year roundup are period-stamped -> `listing` + series_key; 'Destination Dim Sum' is a timeless `guide`. §4's worked example says guide for the whole category.
14. **Lifestyle** (13 posts) — Depends on approving `editorial/lifestyle`.
15. **Print-issue categories (34, ~205 posts)** — confirm: no facet mapping; `series_key = issue:<slug>`; format prior `feature`; classifier decides the rest.
16. **Guide vs listing boundary (cross-cutting)** — proposed definition: a roundup tied to a period (year in title, '[Updated]', seasonal such as Chinese New Year) is `listing` (540-day half-life, `series_key` keeps only the current edition); a timeless how-to or area guide is `guide` (evergreen). Affects Bar Guide, Restaurant Guides, City Guides, Dining. Recommendation: adopt it — it lets the 2019 editions sink while the current edition stays evergreen-equivalent through dedup.
17. **Legacy offers and events with no end date** — `offer` hard-expires at `campaign.ends_at` and `event` at `event.ends_at` (§8.A), but legacy posts have neither. Recommendation: E1.8 extracts dates from text where present; otherwise offers expire at publish + 90 days and events at publish + 30 days. Expired items stay indexed for search, never in rails.
18. **Site default location** — the classifier needs 'this site's home node' for articles with no location signal. There is no `sites` column for it. Recommendation: add `sites.location_term_id` (schema owner); interim convention `sites.slug == terms.slug` (`jakarta`, `bali`) — see taxonomy README.

## D. Proposed additions to ARCHITECTURE.md §4 (seeded, marked `proposed` in the seed files)

Seeded so the classifier enum and this review see the full tree. Nothing references them yet; rejecting one is a one-line deletion in the seed file plus a `DELETE` on `engine.terms` before E2.1 runs.

- **format:** `opinion` (148 posts have no honest §4 format).
- **subtype (editorial):** `culture` (~450 arts posts across Art, Culture, Music, Film, Design, Art & Culture), `lifestyle` (Health, Lifestyle, Green Living service journalism).
- **subtype (do):** `sports-activity` (participatory sport; distinct from `event/sports`).
- **subtype (wellness):** `salon`, `retreat` (Bali).
- **subtype (event):** `performance` (theatre/dance — most of 'Art' that is not an exhibition), `screening` (film festivals), `pop-up`.
- **location root:** `international` (World Traveller 94 + Travel 21). Single leaf for now.
- **location Jakarta:** district `east-jakarta` (+ `cibubur`, `rawamangun`); neighbourhoods `kuningan` (the 5-star hotel cluster), `gunawarman`, `tebet`, `cikini` (arts district), `pasar-baru`, `kota-tua` (the heritage archive's home), `glodok`; Greater Jakarta `depok`, `bintaro`, `alam-sutera`, `gading-serpong`, `sentul`, `puncak`.
- **location Bali:** `denpasar`, `legian`, `kerobokan`, `pererenan`, `sidemen`, `nusa-penida`.
- **location elsewhere:** `surabaya`, `semarang`, `solo`, `malang`, `medan`, `lake-toba`, `makassar`, `manado`, `belitung`, `bintan`, `sumba`, `toraja`, `banyuwangi`. (Hidden Heritage also needs regional nodes — Kalimantan, Maluku, Papua, Sulawesi — not added; `other` is the fallback.)
- **term lists §4 never enumerated** (all proposals): cuisine (27), vibe (14), occasion (11), audience (6), amenities (21), topic (25), price_band slugs `budget|moderate|upscale|luxury` for `$..$$$$`.

## E. Where the evidence contradicts or strains ARCHITECTURE.md §4

1. **`stay/boutique` collides with `shop/boutique`** on the `(facet, slug)` unique key — seeded as `boutique-hotel`.
2. **District slugs are qualified** (`south-jakarta`, `south-bali`) — two `south` nodes cannot coexist in one facet; also cleaner `/{section}/{area}` URLs.
3. **'Bali Updates → format:news'** — half the posts are offers. Location `bali` is certain; format is per article.
4. **'Bar Guide' / 'Restaurant Guides' → format:guide** — most are year-stamped listicles; see the guide/listing decision.
5. **'City Guides' are venue roundups, not city guides** — mapping them to `format: city-guide` would be wrong.
6. **`type` and `subtype` are two facets** in the §4 table but one tree in the §4 diagram — modelled as two facets with a cross-facet `parent_id`, so the exclusion enum is exactly 8 rows.
7. **Editorial subtypes duplicate formats** (`news`, `people`, `heritage`, `city-guide` exist in both) — accepted: type says what the piece is about, format says its shape; they coincide for editorial pieces.
8. **Format decay has no DB home** (`terms` has no attribute column, `type_relations` is type-only) — stored as `sites.ranking_weights['decay']` per site, written once by `site:create`, editable without deploy. Proposed DDL `terms.attrs jsonb` in the taxonomy README.
9. **§6 numbers are stale**: 4,772 published posts (not 4,679); Yoast primary 2,439 (not 2,455); focus keywords 1,136 (not 1,376).
10. **Recipes** (a handful under Dining) have no format; not worth a new one — `editorial/lifestyle + feature`.

## F. Notes for E2.1 (classifier)

- Consume `taxonomy-mapping.json`: `prior.*` non-null values are the prior; `confidence` sets its weight; `alternates` is the candidate set for the *per article* facets. `Uncategorized` and every print-issue category carry no type prior.
- Enums come from the platform DB (`engine.terms` by facet), not from this file: `type` (8), `subtype` grouped by `parent_id`, `format` (11), `location` (85 nodes). Use the `aliases` in `engine/packages/taxonomy/seed/terms/*.json` in the prompt (SCBD, PIK, Kota Tua, Mega Kuningan...).
- Multi-category posts (224): when a Yoast primary category exists (2,439 posts) use it as the single prior; else combine: any `Offers`-family category ⇒ `format: offer`; `Bali Updates` + X ⇒ `location: bali` with X's type/format.
- Year-stamped roundups ⇒ `format: listing` and a `series_key` (E2.6 clusters the '[Updated]' editions).
- Location: prefer the most specific node the text supports; fall back district → city; never leave it null — `jakarta` is the floor for this site, `bali` for Bali Updates, `international` for World Traveller.
- The 200-article eval sample (≥95% type accuracy gate) should be stratified to over-sample the MEDIUM/LOW categories in table A — that is where the type errors will be.
- Extract `ends_at` for `event` and `offer` alongside classification; without it §8.A cannot expire them.
- Term embeddings (E2.4): `now_db.provisioning.TERMS_MISSING_EMBEDDINGS_SQL`; the seed leaves `embedding` NULL by design.

*Generated from the mapping spec + `categories.tsv` on 2026-09-08 by E1.4; regenerate rather than hand-edit the tables.*

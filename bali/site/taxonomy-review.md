# NOW! Bali — taxonomy review: evidence pack (resolved)

**Status: RESOLVED — Hansel's answers to all 27 decisions applied on 2026-09-10; this file and its JSON twin are E2.1's input.** Generated 2026-09-10T03:14:29+00:00 by `engine/packages/taxonomy-evidence 0.2.0`. Builds on E1.4's draft (`jakarta/site/taxonomy-mapping.md`) and the E2.0 evidence (kept in full below: every instrument reading was taken against the E2.0 proposal, which each category still shows as `e20_proposal`). The machine-readable twin `taxonomy-review.json` is rendered from the same in-memory model as this file.

## How to read this

- **§1** lists the 24 decisions that touch this city (of 27 across both cities; shared ids are identical in `jakarta/site/taxonomy-review.md`) with the evidence, the E2.0 recommendation, and **the answer** — 12 explicit (D01, D02, D06, D08, D09, D10, D14, D15, D16, D21, D22, D26), the rest the recommendation accepted as-is. Every conflict between an answer and a recommendation is stated under the decision, never reconciled silently.
- **§2** lists the categories the *data* flagged and how each flag was resolved (Hansel's answer for mixed categories: classify per article, no fixed category-wide type). **§3** is the coherence evidence, computed against the E2.0 proposal. **§4** is the vocabulary check; the reviewed change list lives in `engine/packages/taxonomy-evidence/vocabulary-delta.md`. **§5** calibrates the instruments. **§7** is the set of cross-cutting classifier rules the policy answers produce, including how `international` is encoded.
- **Appendix A** is every resolved mapping (48 categories, the 9 that changed against E2.0 first). **Appendix B** has the full evidence and the resolution for every category.
- Vectors for bali: `tfidf-proxy (embeddings no rows for this model)`. **Weaker instrument**: TF-IDF/LSA is lexical, not semantic; coherence verdicts here are indicative.
- LLM second opinion: llm second opinion: glm-5.2 via https://ollama.com/v1 (120/120 categories answered; responses cached in .cache/llm). The LLM can only add flags; it never auto-accepts anything.

### Counts

| | |
|---|---|
| Articles | 4,429 |
| Categories (with ≥1 published article) | 48 of 50 |
| Decisions touching this city (resolved / total) | 24 / 24 |
| Categories still awaiting a decision | 0 |
| Categories resolved | 48 |
| … of which changed against the E2.0 proposal | 9 |
| Categories that were flagged before resolution (decision-needed or by evidence) | 18 |
| Empty categories | 2 |

## 1. Decisions — all resolved — ordered by articles affected

| # | decision | kind | articles | answer | source |
|---|---|---|---:|---|---|
| D02 | Legacy offers and events have no end date | policy | 2,178 | Extract the real end date from the text where one is present; otherwise an offer expires at publish + 90 days and an event at publish + 30 days. Expired items stay searchable and never enter a rail. | explicit |
| D21 | Bali 'News' (1,067 -- 24% of the archive): format `news` as prior, type per article | mapping | 1,067 | Bali News (1,067): format `news` as the prior, type per article. Roughly a quarter will be relabelled event/offer by the classifier -- intended. | explicit |
| D04 | Approve `editorial/culture` (subtype) | vocabulary | 869 | Approve the `editorial/culture` subtype. | as-recommended |
| D12 | Approve the proposed event subtypes: `performance`, `screening`, `pop-up` | vocabulary | 811 | Approve the event subtypes `performance`, `screening` and `pop-up`. | as-recommended |
| D13 | Approve the proposed wellness subtypes: `salon`, `retreat` | vocabulary | 551 | Approve the wellness subtypes `salon` and `retreat`. | as-recommended |
| D20 | Bali 'Dining Offers' (487): a third read as dining news, not offers | mapping | 487 | Bali Dining Offers: format per article with `offer` as the prior (the Yoast primary decides when Restaurants and Bars is primary); roughly a third will be relabelled news. | as-recommended |
| D05 | Approve `editorial/lifestyle` (subtype) | vocabulary | 449 | Approve the `editorial/lifestyle` subtype. | as-recommended |
| D25 | Bali 'Art In Bali' (136) and Jakarta 'Art' (244): type/format per article, topic art | mapping | 380 | Jakarta Art and Bali Art In Bali: no type/format prior; topic `art`; the classifier decides among the listed alternates. | as-recommended |
| D17 | Experience Offers (both cities): hotel-experience packages, not a `do` category | mapping | 335 | Experience Offers (both cities): format `offer` fixed; type per article with `stay/hotel` as the prior; the classifier may pick eat, wellness, do or event. Not a `do` category. | as-recommended |
| D24 | Bali 'Culture' family: `culture`+`feature` vs `heritage`+`heritage` split | mapping | 333 | Bali Culture family: Bali History and Myths and Legends -> editorial/heritage + heritage; Cultural Observer, Dance and Music, Ceremonies & Festivals, Everyday Bali, Culture -> editorial/culture + feature. Stranger In Paradise keeps editorial/opinion as its prior with format per article (heritage as the alternate). | as-recommended ⚠ conflict |
| D03 | Approve the proposed `opinion` format | vocabulary | 328 | Approve the `opinion` format (540-day half-life). | as-recommended |
| D14 | Location tree: approve E1.4's proposed nodes and the corpus-found gaps | vocabulary | 327 | Add every corpus location term with >= 20 mentions (Bali 14, elsewhere in Indonesia 12, international 22, Jakarta 11 candidates -- vocabulary-delta.json lists each with its counts and the node-vs-alias call); below 20 stays out. Drop `location/rawamangun` (2 mentions). Trim the homonym-inflated aliases `Batu` (malang) and `Wijaya` (gunawarman); title-case-only matching for `solo` and `kuningan`. | explicit ⚠ conflict |
| D19 | Community (both cities): `news` or `feature` as the format prior? | mapping | 302 | Community (both cities): format prior `feature`; the classifier switches to `event` (dated fundraisers) or `news` (announcements) when the text says so; topic `community` always. | as-recommended |
| D23 | Bali 'Lifestyle' (243) is a container of Spa, Shopping and beauty -- not one thing | split | 243 | Bali Lifestyle is a container (D10): the child's prior wins; for the residue type and format per article with editorial/lifestyle as the fallback. | as-recommended |
| D01 | Guide vs listing boundary (cross-cutting) | policy | 233 | Period-stamped roundups (a year in the title, '[Updated]', a seasonal marker) are `listing`: 540-day half-life, a `series_key`, and only the current member of a series is eligible in any rail. Timeless how-to and area pieces stay evergreen `guide`. | explicit |
| D10 | Multi-category resolution order: Yoast primary > most specific child > parent container | policy | 213 | Prior resolution order for a multi-category post: the Yoast primary category, else the deepest (most specific) child category, else the parent container. | explicit |
| D09 | Uncategorized (both cities) -> review queue; non-articles excluded | policy | 154 | Migrate everything and classify best-effort: no prior from Uncategorized, the classifier decides every facet, and the standard E2.1 confidence gate applies (below the auto-apply threshold -> review queue, never written as fact). Nothing is excluded. | explicit ⚠ conflict |
| D06 | Approve the `international` location root | vocabulary | 153 | Add the `international` location root, editorial-only: searchable and eligible for Row 3 (related reading); never Row 1 (complementary places), never Row 2 (nearby), never the itinerary builder. | explicit ⚠ conflict |
| D08 | Bali's column and 'Home Life' archive categories: series_key, and are the lockdown columns migrated at all? | scope | 147 | Keep every column category and migrate all of it -- including Must Watch Movies (13) and Music to the Ears (11), which have no Bali subject. `series_key = column:<slug>` for every column. Follow-up #1: nothing is discarded and both columns stay fully searchable, but Must Watch Movies and Music to the Ears must not be recommended alongside local content -- the rails exclusion E2.0's original recommendation had is restored for exactly these two series. Every other column (Chaine Des Rottiseurs, Cook and Mix, Health & Wellness, Home Life, ...) keeps the original 'nothing excluded' answer unchanged. | explicit ⚠ conflict |
| D18 | Bali 'Explore Bali' is not a `do` category -- it is a container plus an opinion column | mapping | 117 | Explore Bali is a container (D10): no type prior of its own, children carry the priors; Explore Bali + Opinion -> editorial/opinion. | as-recommended |
| D22 | Weddings (Bali, 17) and romance content: `occasion` term or a type? | mapping | 17 | Add `occasion/wedding` (aliases weddings, honeymoon, proposal, bridal, bachelorette, hen party). The Bali Weddings category carries occasion `wedding` instead of `celebration`. | explicit |
| D27 | Bali categories with 0-3 published posts and the WP-only categories | scope | 5 | Features (3), Home Life (1) and Offers (1) are classified from content; Mapping Bali and Archives are empty containers with nothing to map. | as-recommended |
| D15 | Cuisine list: additions and removals from corpus evidence | vocabulary | 0 | Add every corpus cuisine term with >= 20 mentions. Dietary and approach terms (organic, healthy, vegetarian, vegan, gluten-free, farm-to-table) are routed to amenities, as the seed designed and the recommendation kept. No seed cuisine is removed (none has < 10 mentions). | explicit |
| D16 | Vibe, occasion, amenity, audience, topic: prune the unused, add the frequent | vocabulary | 0 | Add every vibe, occasion, amenity, audience and topic corpus term with >= 20 mentions (duplicates merged: Retiree into seniors, the two wedding topics into one, Rice terrace + Hot spring + Waterfall into do/nature). Nothing is pruned -- no seed term has zero support. Trim the homonym aliases `party` (occasion/celebration) and `business` (audience/business-traveller). | explicit |

### D02 · Legacy offers and events have no end date

*kind: policy · articles affected: 2,178 · carried from E1.4 #1/#17 · cities: bali, jakarta · status: resolved*

**Question.** `offer` hard-expires at campaign.ends_at and `event` at event.ends_at (§8.A), but legacy posts have neither. Proposed: E1.8/E2.1 extracts a date from the text where present; otherwise offers expire at publish + 90 days and events at publish + 30 days. Expired items stay searchable, never in rails.

**Affects.** bali: Dining Offers (487), jakarta: Dining Offers (402), jakarta: Events (396), jakarta: Stay Offers (261), jakarta: Experience Offers (207), bali: Stay Offers (168), bali: Experience Offers (128), jakarta: Offers (55), jakarta: Music (49), bali: Chaine Des Rottiseurs (24), bali: Offers (1)

**Evidence.**
- jakarta: 848 offer-category articles; 59% published 2023 or earlier (certainly expired); 40% carry an explicit validity phrase the extractor can read
- jakarta: 396 Events; 65% from 2023 or earlier
- bali: 781 offer-category articles; 78% published 2023 or earlier (certainly expired); 25% carry an explicit validity phrase the extractor can read

**E2.0 recommendation.** Accept the fallback windows. Almost every offer before 2024 is dead anyway; the only live question is the window for recent ones.

**Options.** accept 90/30 (recommended) · different windows · no fallback -- undated legacy offers/events are treated as expired on load

**Resolved (explicit, Hansel 2026-09-10).** Extract the real end date from the text where one is present; otherwise an offer expires at publish + 90 days and an event at publish + 30 days. Expired items stay searchable and never enter a rail.

*Option: accept 90/30.* Almost every offer before 2024 is dead anyway; the windows only matter for recent, undated ones.

**Applied.** rules.legacy_expiry

### D21 · Bali 'News' (1,067 -- 24% of the archive): format `news` as prior, type per article

*kind: mapping · articles affected: 1,067 · cities: bali · status: resolved*

**Question.** The largest category in either city. Cue instrument: news 24%, event 21%, offer 11%, unclear 31%; type is spread across stay/event/eat/editorial. Proposed: format `news` prior (21-day decay), type per article, location bali. A quarter will be relabelled event/offer by the classifier.

**Affects.** bali: News (1067)

**Evidence.**
- bali 'News' (1067): type cues event 21%, stay 21%, eat 14%, editorial 11% (coverage 79%); format cues news 37%, event 29%, offer 15%, listing 7% (coverage 69%)
- Bali News by year: 2013: 1, 2014: 9, 2015: 173, 2016: 112, 2017: 118, 2018: 101, 2019: 130, 2020: 67, 2021: 54, 2022: 61, 2023: 83, 2024: 68, 2025: 57, 2026: 33
- bali 'News' clusters (tfidf-proxy, k=3, silhouette 0.074): 41% [stay/news] e.g. W Hotels Worldwide Announces W Bali - Ubud To Open in 2020; The Garcia Island-Inspired Boutique Resort Opens in Ubud | 33% [editorial/news] e.g. The Future is Now 2017: 2nd Annual NOW! Bali PR and Marcomm ; The Bali Hope Swimrun 2019 and the Birth of 'Island Protect' | 26% [event/event] e.g. Indonesia Bertutur 2024: An Island-Wide Cultural Showcase Un; Bali Arts Festival 2024: Dates, Venue and Information

**E2.0 recommendation.** Accept -- same treatment E1.4 gave Jakarta News. Flagged only because of its size: it is the single largest lever on Bali's freshness curve.

**Options.** accept (recommended) · per-article format, no prior

**Resolved (explicit, Hansel 2026-09-10).** Bali News (1,067): format `news` as the prior, type per article. Roughly a quarter will be relabelled event/offer by the classifier -- intended.

*Option: accept.* Same treatment E1.4 gave Jakarta News; the single largest lever on Bali's freshness curve.

**Applied.** no change

### D04 · Approve `editorial/culture` (subtype)

*kind: vocabulary · articles affected: 869 · carried from E1.4 #2/#8 · cities: bali, jakarta · status: resolved*

**Question.** Arts and culture coverage that is neither a dated event nor a venue: Jakarta Art/Culture/Design/Music/Film features, and most of Bali's Culture family (Cultural Observer, Dance and Music, Ceremonies & Festivals, Everyday Bali, Myths and Legends, Art In Bali). Without the subtype they force-fit into `news` or `people`.

**Affects.** jakarta: Art (244), bali: Art In Bali (136), bali: Culture (110), bali: Cultural Observer (110), bali: Dance and Music (75), jakarta: Culture (67), bali: Ceremonies & Festivals (45), bali: Everyday Bali (30), jakarta: Art & Culture (28), jakarta: Design (24)

**Evidence.**
- 10 categories / 869 articles depend on this approval: jakarta:Art (244), bali:Art In Bali (136), bali:Culture (110), bali:Cultural Observer (110), bali:Dance and Music (75), jakarta:Culture (67), bali:Ceremonies & Festivals (45), bali:Everyday Bali (30), jakarta:Art & Culture (28), jakarta:Design (24)

**E2.0 recommendation.** Approve. Bali alone has ~600 articles that land here.

**Options.** approve (recommended) · reject -> editorial/news or editorial/people

**Resolved (as-recommended, Hansel 2026-09-10).** Approve the `editorial/culture` subtype.

*Option: approve.* ~870 articles across both cities have no honest node without it.

**Applied.** vocabulary-delta: approve subtype/culture (already seeded; already in enum_places_subtype)

### D12 · Approve the proposed event subtypes: `performance`, `screening`, `pop-up`

*kind: vocabulary · articles affected: 811 · carried from E1.4 #10 · cities: bali, jakarta · status: resolved*

**Question.** `concert` is music-only and `exhibition` is visual arts; theatre/dance (a large slice of Jakarta Art and Events), film festivals (Jakarta Film 35) and pop-up markets have no §4 node.

**Affects.** jakarta: Events (396), jakarta: Art (244), bali: Art In Bali (136), jakarta: Film (35)

**Evidence.**
- 4 categories / 811 articles depend on this approval: jakarta:Events (396), jakarta:Art (244), bali:Art In Bali (136), jakarta:Film (35)

**E2.0 recommendation.** Approve all three.

**Options.** approve all (recommended) · approve performance + screening only · reject -> festival/concert

**Resolved (as-recommended, Hansel 2026-09-10).** Approve the event subtypes `performance`, `screening` and `pop-up`.

*Option: approve all.* Theatre/dance, film festivals and pop-up markets have no Section 4 node.

**Applied.** vocabulary-delta: approve subtype/performance, screening, pop-up (already seeded; already in enum_places_subtype)

### D13 · Approve the proposed wellness subtypes: `salon`, `retreat`

*kind: vocabulary · articles affected: 551 · cities: bali, jakarta · status: resolved*

**Question.** Bali Spa and Wellness (209) and Lifestyle carry beauty venues (Toni&Guy, facials, nail bars) and multi-day retreats (COMO Shambhala, Fivelements, detox programmes) that have no §4 node; `spa` would absorb both and blur Row 1 matching.

**Affects.** bali: Lifestyle (243), bali: Spa and Wellness (209), jakarta: Health (99)

**Evidence.**
- 3 categories / 551 articles depend on this approval: bali:Lifestyle (243), bali:Spa and Wellness (209), jakarta:Health (99)
- corpus mentions -- retreat: 60 articles; salon/barbershop/nail: 64; yoga studio: 64 (lexical counts, see vocabulary section)

**E2.0 recommendation.** Approve both.

**Options.** approve both (recommended) · approve retreat only · reject -> spa

**Resolved (as-recommended, Hansel 2026-09-10).** Approve the wellness subtypes `salon` and `retreat`.

*Option: approve both.* `spa` would absorb beauty venues and multi-day retreats and blur Row 1 matching.

**Applied.** vocabulary-delta: approve subtype/salon, retreat (already seeded; already in enum_places_subtype)

### D20 · Bali 'Dining Offers' (487): a third read as dining news, not offers

*kind: mapping · articles affected: 487 · cities: bali · status: resolved*

**Question.** Jakarta Dining Offers are unambiguous promotions (cue: offer 70%). Bali's are weaker (offer 45%, news 16%, no signal 34%): many 2016-2019 pieces are new-menu or new-restaurant write-ups filed as offers, and 188 co-occur with Restaurants and Bars. Mapping all 487 to `offer` hard-expires them; mapping to `news` decays them in 21 days -- either way they leave the rails, but `offer` also excludes them from 'similar' rows once expired.

**Affects.** bali: Dining Offers (487)

**Evidence.**
- jakarta 'Dining Offers' (402): type cues eat 83%, stay 9%, drink 5%, event 2% (coverage 92%); format cues offer 80%, news 11%, listing 3%, event 3% (coverage 85%)
- bali 'Dining Offers' (487): type cues eat 82%, drink 11%, stay 5%, shop 1% (coverage 88%); format cues offer 60%, news 32%, event 2%, people 2% (coverage 70%)
- Bali Dining Offers by year: 2016: 6, 2017: 67, 2018: 76, 2019: 99, 2020: 39, 2021: 34, 2022: 48, 2023: 44, 2024: 28, 2025: 38, 2026: 8
- bali 'Dining Offers' clusters (tfidf-proxy, k=2, silhouette 0.104): 69% [eat/news] e.g. Renowned Indonesian Chef Arnold Poernomo Opens Laci Restaura; Modern Balinese Bistro, The Suku Bali, Reveals New Indonesia | 31% [eat/offer] e.g. Toast to the Season of Joy at The Oberoi Beach Resort, Bali; Art de Nöel: Sofitel Bali Nusa Dua Beach Resort’s Candle Lig

**E2.0 recommendation.** Format per article with `offer` as the prior (Yoast primary decides when it is Restaurants and Bars); accept that the classifier will relabel roughly a third as news.

**Options.** offer prior, per-article override (recommended) · offer for all 487 · news for the pre-2020 ones

**Resolved (as-recommended, Hansel 2026-09-10).** Bali Dining Offers: format per article with `offer` as the prior (the Yoast primary decides when Restaurants and Bars is primary); roughly a third will be relabelled news.

*Option: offer prior, per-article override.* Bali's offer cue is weak (45%); many 2016-2019 pieces are menu/opening write-ups filed as offers.

**Applied.** no change

### D05 · Approve `editorial/lifestyle` (subtype)

*kind: vocabulary · articles affected: 449 · carried from E1.4 #5/#14 · cities: bali, jakarta · status: resolved*

**Question.** Service journalism with no venue subject (Jakarta Health/Lifestyle/Green Living; Bali Lifestyle-only pieces and the lockdown 'Home Life' columns). Same force-fit problem as D04.

**Affects.** bali: Lifestyle (243), jakarta: Health (99), jakarta: Green Living (47), bali: Cook and Mix (16), jakarta: Lifestyle (13), bali: Must Watch Movies (13), bali: Music to the Ears (11), bali: Health & Wellness (7)

**Evidence.**
- 8 categories / 449 articles depend on this approval: bali:Lifestyle (243), jakarta:Health (99), jakarta:Green Living (47), bali:Cook and Mix (16), jakarta:Lifestyle (13), bali:Must Watch Movies (13), bali:Music to the Ears (11), bali:Health & Wellness (7)

**E2.0 recommendation.** Approve.

**Options.** approve (recommended) · reject -> editorial/news

**Resolved (as-recommended, Hansel 2026-09-10).** Approve the `editorial/lifestyle` subtype.

*Option: approve.* Service journalism with no venue subject otherwise force-fits into `news`.

**Applied.** vocabulary-delta: approve subtype/lifestyle (already seeded; already in enum_places_subtype)

### D25 · Bali 'Art In Bali' (136) and Jakarta 'Art' (244): type/format per article, topic art

*kind: mapping · articles affected: 380 · cities: bali, jakarta · status: resolved*

**Question.** Both mix dated exhibitions (event/exhibition + event), artist profiles (editorial/people + people), commentary and buying guides. Only `topic: art` is certain. Proposed: no type/format prior; classifier decides with the listed alternates; the embedding clusters below show the split.

**Affects.** jakarta: Art (244), bali: Art In Bali (136)

**Evidence.**
- jakarta 'Art' (244): type cues event 48%, do 23%, editorial 20%, stay 4% (coverage 70%); format cues event 42%, heritage 25%, listing 12%, news 11% (coverage 66%)
- jakarta 'Art' clusters (embeddings:BAAI/bge-small-en-v1.5, k=3, silhouette 0.053): 44% [event/event] e.g. Deciphering life at “The Meeting Point”, Celebration Art Pal; Artistic Connection Across Generations | 36% [event/event] e.g. Art Jakarta 2024: Presenting the Best of Indonesian & Region; Connecting Jakarta to the Global Art World | 20% [do/heritage] e.g. Exploring Our Art in Various Collections Abroad; Bartele Gallery Jakarta: Rare Antique Maps, Prints and Books
- bali 'Art In Bali' (136): type cues editorial 36%, do 30%, event 25%, stay 3% (coverage 46%); format cues heritage 37%, news 18%, event 18%, listing 10% (coverage 46%)
- bali 'Art In Bali' clusters (tfidf-proxy, k=2, silhouette 0.149): 61% [editorial/heritage] e.g. Expatriate Artist Izzy Ivy’s Delightful Visionary Paintings ; Made Valasara’s Artistic Exploration of Material Potential | 39% [do/event] e.g. Art Bali 2019 : An Exploration into Contemporary Art; Bali Art World Personalities : Meet Ruth Onduko

**E2.0 recommendation.** Accept -- do not force a type.

**Options.** accept (recommended) · event/exhibition prior

**Resolved (as-recommended, Hansel 2026-09-10).** Jakarta Art and Bali Art In Bali: no type/format prior; topic `art`; the classifier decides among the listed alternates.

*Option: accept.* Both mix dated exhibitions, artist profiles, commentary and buying guides.

**Applied.** no change

### D17 · Experience Offers (both cities): hotel-experience packages, not a `do` category

*kind: mapping · articles affected: 335 · carried from E1.4 #3 · cities: bali, jakarta · status: resolved*

**Question.** Is 'Experience Offers' a stay category (hotel packages) or a do category (activities)? Evidence in both cities: it is hotel 'experience' marketing -- F&B, wellness, festive programmes, kids' activities -- at a hotel; the venue is the hotel but the subject is often its restaurant or spa. Proposed: format `offer` fixed; type per article with `stay/hotel` as the prior; classifier may pick eat/wellness/do/event.

**Affects.** jakarta: Experience Offers (207), bali: Experience Offers (128)

**Evidence.**
- jakarta 'Experience Offers' (207): type cues stay 52%, eat 25%, wellness 14%, do 6% (coverage 86%); format cues offer 84%, news 9%, city-guide 3%, event 3% (coverage 89%)
- jakarta 'Experience Offers' clusters (embeddings:BAAI/bge-small-en-v1.5, k=3, silhouette 0.081): 40% [stay/offer] e.g. Enjoy a Blissful Ramadan with Pullman Jakarta Indonesia’s Se; The Westin Jakarta Presents Serene Stays and Culinary Deligh | 33% [stay/offer] e.g. Wellness Getaway at Tirta Ayu Spa; Save Now, Stay Later: Indulgence Awaits at The Laguna, a Lux | 28% [stay/offer] e.g. JW Marriott Hotel Jakarta Offers Festive Holiday Sparkles; Celebrate the Magical Festive Season at HARRIS Hotel & Conve
- bali 'Experience Offers' (128): type cues stay 30%, eat 30%, wellness 17%, do 9% (coverage 81%); format cues offer 76%, event 10%, news 5%, city-guide 4% (coverage 84%)
- bali 'Experience Offers' clusters (tfidf-proxy, k=3, silhouette 0.199): 52% [stay/offer] e.g. Immerse in a Serene Easter Holiday by the Sea at Jumeirah Ba; A Peek into the Experiences Offered at Japanese Hidden Gem,  | 34% [eat/offer] e.g. Cherish Joyful Festive Moments at Hilton Bali Resort; Splash Into Ayodya Resort Bali’s ‘Aqua Wonderland’ Festive P | 14% [event/event] e.g. Usher in a Wicked October at The Iron Fairies Bali; Road to 2023: White Rock Beach Club Presents an Epic 8-Day Y

**E2.0 recommendation.** Accept 'type per article, stay prior, format offer'. Do not map to `do`.

**Options.** accept (recommended) · stay/hotel for all · do/* for all

**Resolved (as-recommended, Hansel 2026-09-10).** Experience Offers (both cities): format `offer` fixed; type per article with `stay/hotel` as the prior; the classifier may pick eat, wellness, do or event. Not a `do` category.

*Option: accept.* Hotel experience marketing where the subject is often the hotel's restaurant or spa.

**Applied.** no change -- already the proposal in both cities

### D24 · Bali 'Culture' family: `culture`+`feature` vs `heritage`+`heritage` split

*kind: mapping · articles affected: 333 · cities: bali · status: resolved*

**Question.** Cultural Observer (110), Dance and Music (75), Ceremonies & Festivals (45), Myths and Legends (30), Everyday Bali (30), Bali History (22), Stranger In Paradise (21) are all evergreen explainers. Both candidate formats are evergreen so decay is unaffected; the choice decides which reader filter (Culture vs History) they surface under. Proposed: Bali History, Myths and Legends, Stranger In Paradise -> editorial/heritage + heritage; the rest -> editorial/culture + feature (needs D04).

**Affects.** bali: Cultural Observer (110), bali: Dance and Music (75), bali: Ceremonies & Festivals (45), bali: Myths and Legends (30), bali: Everyday Bali (30), bali: Bali History (22), bali: Stranger In Paradise (21)

**Evidence.**
- 7 categories / 333 articles depend on this approval: bali:Cultural Observer (110), bali:Dance and Music (75), bali:Ceremonies & Festivals (45), bali:Myths and Legends (30), bali:Everyday Bali (30), bali:Bali History (22), bali:Stranger In Paradise (21)

**E2.0 recommendation.** Accept the split as proposed.

**Options.** accept (recommended) · all heritage · all culture

**Resolved (as-recommended, Hansel 2026-09-10).** Bali Culture family: Bali History and Myths and Legends -> editorial/heritage + heritage; Cultural Observer, Dance and Music, Ceremonies & Festivals, Everyday Bali, Culture -> editorial/culture + feature. Stranger In Paradise keeps editorial/opinion as its prior with format per article (heritage as the alternate).

*Option: accept the split as proposed.* Both formats are evergreen so decay is unaffected; the split decides which reader filter the pieces surface under.

**Conflicts with the E2.0 recommendation (reported, not reconciled).**
- ⚠ E2.0's own output is inconsistent for Stranger In Paradise: the D24 question text lists it under editorial/heritage + heritage, while the proposal table has editorial/opinion + opinion (the LLM second opinion and the first-person density agree with opinion). Resolved as opinion prior, format per article with heritage as the alternate -- the clusters split 57/43 between medium and evergreen decay.

**Applied.** bali Stranger In Paradise: format per article

### D03 · Approve the proposed `opinion` format

*kind: vocabulary · articles affected: 328 · carried from E1.4 #4 · cities: bali, jakarta · status: resolved*

**Question.** 298 Opinion articles across both cities (plus Bali's Winocracy/Stranger In Paradise columns) have no honest §4 format. Proposed `opinion` with a 540-day half-life. Fallback: `feature` (evergreen), which keeps 2016 columns permanently fresh.

**Affects.** bali: Opinion (150), jakarta: Opinion (148), bali: Stranger In Paradise (21), bali: Winocracy (9)

**Evidence.**
- jakarta Opinion (148, 2019-2026): median first-person density 22.1/1000 words vs News 2.0 -- columns, not reportage; 68% are from 2020 or earlier and would stay evergreen as `feature`
- bali Opinion (150, 2013-2026): median first-person density 15.9/1000 words vs News 0.0 -- columns, not reportage; 72% are from 2020 or earlier and would stay evergreen as `feature`

**E2.0 recommendation.** Approve.

**Options.** approve (recommended) · reject -> feature

**Resolved (as-recommended, Hansel 2026-09-10).** Approve the `opinion` format (540-day half-life).

*Option: approve.* Columns date like reviews, not like guides; `feature` would keep 2016 columns permanently fresh.

**Applied.** vocabulary-delta: approve format/opinion (already seeded as proposed and already a value of enum_articles_format -- no migration)

### D14 · Location tree: approve E1.4's proposed nodes and the corpus-found gaps

*kind: vocabulary · articles affected: 327 · cities: bali, jakarta · status: resolved*

**Question.** E1.4 proposed 40+ location nodes beyond §4 (Kuningan, Kota Tua, Cikini, East Jakarta, Denpasar, Legian, Nusa Penida, Surabaya...). The corpus scan below shows how often each is actually named, and surfaces places the tree lacks entirely (Bali: Tabanan/Tanah Lot, Kintamani/Batur, Bedugul/Munduk, Nusa Lembongan, West Bali/Menjangan, Karangasem towns; Jakarta: Kebayoran Baru, Cilandak/TB Simatupang, Kemayoran, Pluit, Jatinegara/Condet).

**Affects.** jakarta: Explore Indonesia (154), jakarta: History & Heritage (74), bali: Travel (38), jakarta: Discover Jakarta (24), jakarta: Travel (21), jakarta: Hidden Heritage (16)

**Evidence.**
- E1.4-proposed nodes by corpus mentions (body / in titles): denpasar 407/19, solo 293/20, surabaya 282/42, legian 281/79, gunawarman 271/16, kuningan 259/12, kota-tua 227/13, malang 209/11, kerobokan 196/2, cikini 112/9, nusa-penida 102/19, medan 93/4, semarang 92/4, puncak 83/10, makassar 66/2, manado 63/1, sumba 59/12, bintaro 47/4, glodok 44/5, banyuwangi 41/9, gading-serpong 36/12, pererenan 35/4, alam-sutera 34/4, toraja 30/0, east-jakarta 28/1, sentul 28/5, sidemen 28/3, depok 27/2, tebet 25/0, pasar-baru 24/3, belitung 18/7, bintan 18/5, lake-toba 16/5, cibubur 13/3, rawamangun 2/0 -- homonyms inflate solo (the word), kuningan (also the Balinese holiday), malang (alias Batu), gunawarman (alias Wijaya); trust the title counts there
- proposed nodes with < 5 mentions (drop candidates): rawamangun
- places the tree lacks entirely, by mentions (body / in titles): Tabanan 162/6, Kintamani 153/5, Gianyar 150/3, Karangasem 115/8, West Bali 109/11, Bedugul 87/9, Bangli 69/4, Nusa Lembongan 58/13, Mengwi 45/1, Tanah Lot 40/1, Jatiluwih 31/1, Kedonganan 27/4, Sanur / Ketewel 25/0, Serangan 21/0, Seseh / Cemagi 16/1, Tejakula 15/1, Java (general) 859/52, Sumatra (general) 206/11, Sulawesi 179/6, Kalimantan 156/7, Nusa Tenggara 133/3, Maluku 109/6, Aceh 70/0, Riau Islands 44/5, Palembang 39/1, Padang 38/0, Lampung 37/3, Cirebon 30/0
- alias suggestions for existing nodes (surface forms the seed lacks): Ubud <- Peliatan (24), Uluwatu <- Balangan (21), Komodo & Labuan Bajo <- Komodo (74), Lombok <- Gili (39), Lake Toba <- Toba (19), BSD <- BSD (37)

**E2.0 recommendation.** Approve every proposed node with >= 10 corpus mentions; add the corpus-found gaps with >= 20 mentions; drop proposed nodes with < 5 mentions.

**Options.** approve by the mention thresholds (recommended) · approve E1.4's list as-is · §4 tree only

**Resolved (explicit, Hansel 2026-09-10).** Add every corpus location term with >= 20 mentions (Bali 14, elsewhere in Indonesia 12, international 22, Jakarta 11 candidates -- vocabulary-delta.json lists each with its counts and the node-vs-alias call); below 20 stays out. Drop `location/rawamangun` (2 mentions). Trim the homonym-inflated aliases `Batu` (malang) and `Wijaya` (gunawarman); title-case-only matching for `solo` and `kuningan`.

*Option: flat >= 20 for additions (replaces the recommendation's 10 / 20 / 5 thresholds); drop rawamangun.* Hansel: add every corpus term with >= 20 mentions, drop rawamangun, trim the homonym aliases the pack identified.

**Conflicts with the E2.0 recommendation (reported, not reconciled).**
- ⚠ The recommendation used three thresholds (approve proposed nodes >= 10, add gaps >= 20, drop proposed nodes < 5). The answer is a flat >= 20 for additions plus one named drop. Already-seeded proposed nodes with 5-19 mentions (belitung 18, bintan 18, lake-toba 16, cibubur 13) are KEPT here because only rawamangun was named -- if 'below 20 stays out' was meant to cover existing proposed nodes too, these four are a one-line removal in the seed ticket.

**Applied.** vocabulary-delta: approve the 35 remaining proposed location nodes; add 54 location terms (Bali 10 incl. a new west-bali district, elsewhere-in-Indonesia 12 region/city leaves under `other`, international 22, Jakarta 10) and 9 alias sets; drop rawamangun; trim malang/Batu, gunawarman/Wijaya + Kebayoran Baru, nusa-penida/Nusa Lembongan + Nusa Ceningan

### D19 · Community (both cities): `news` or `feature` as the format prior?

*kind: mapping · articles affected: 302 · cities: bali, jakarta · status: resolved*

**Question.** E1.4 gave Jakarta Community `editorial/news + news` (MEDIUM). Bali Community (152) reads as features and profiles of NGOs and initiatives ('Solemen Bali', 'Mission Paws'ible', 'Quantum Temple') -- evergreen, not 21-day news. A wrong prior here decays 300 articles to nothing or keeps dated charity events fresh.

**Affects.** bali: Community (152), jakarta: Community (150)

**Evidence.**
- jakarta 'Community' (150): type cues editorial 74%, event 8%, do 6%, wellness 5% (coverage 79%); format cues event 25%, listing 18%, news 17%, opinion 15% (coverage 48%)
- jakarta Community: 2019-2026, median first-person density 7.7; coherence verdict coherent
- bali 'Community' (152): type cues editorial 77%, eat 8%, do 7%, wellness 2% (coverage 80%); format cues listing 39%, event 14%, heritage 12%, news 12% (coverage 34%)
- bali Community: 2015-2026, median first-person density 3.9; coherence verdict coherent

**E2.0 recommendation.** Prior `feature` for both cities; classifier switches to `event` (dated fundraisers) or `news` (announcements) when the text says so; topic `community` always.

**Options.** feature prior for both (recommended) · keep E1.4's news prior · per article, no prior

**Resolved (as-recommended, Hansel 2026-09-10).** Community (both cities): format prior `feature`; the classifier switches to `event` (dated fundraisers) or `news` (announcements) when the text says so; topic `community` always.

*Option: feature prior for both.* NGO and initiative features are evergreen, not 21-day news.

**Applied.** no change -- E2.0 already amended Jakarta Community to feature; Bali proposal already feature

### D23 · Bali 'Lifestyle' (243) is a container of Spa, Shopping and beauty -- not one thing

*kind: split · articles affected: 243 · cities: bali · status: resolved*

**Question.** 242 of 243 also carry a child category (Shopping 114, Spa and Wellness 91, Bar Guide 26, Bali with Kids 7...); exactly one post carries Lifestyle alone. The Lifestyle-flavoured content is beauty (salons, facials, fragrance), fashion and misc. features. No single type/format prior is honest. Proposed: container (D10) -- the child's prior wins; for the residue, type per article (wellness/salon likely, needs D13), format per article, editorial/lifestyle fallback (D05).

**Affects.** bali: Lifestyle (243)

**Evidence.**
- Lifestyle (243, 2015-2020): co-filings Shopping 114, Spa and Wellness 91, Bar Guide 26; 1 carry Lifestyle alone
- bali 'Lifestyle' (243): type cues wellness 44%, shop 34%, drink 12%, do 7% (coverage 80%); format cues news 40%, offer 24%, heritage 12%, review 12% (coverage 40%)
- bali 'Lifestyle' clusters (tfidf-proxy, k=3, silhouette 0.185): 55% [shop/news] e.g. Design Your Own Flip Flops at Baia Baia; A Seminyak Shopping Spree | 35% [wellness/news] e.g. Renewing My Prana; Put Your Feet Up: 4 Great Spots for Reflexology in Bali | 9% [shop/heritage] e.g. The Diamond is June's Birthstone!; Precious Jemme

**E2.0 recommendation.** Accept; nothing to map at the parent level.

**Options.** accept (recommended) · wellness prior for all

**Resolved (as-recommended, Hansel 2026-09-10).** Bali Lifestyle is a container (D10): the child's prior wins; for the residue type and format per article with editorial/lifestyle as the fallback.

*Option: accept.* 242 of 243 also carry a child category.

**Applied.** no change

### D01 · Guide vs listing boundary (cross-cutting)

*kind: policy · articles affected: 233 · carried from E1.4 #11/#12/#13/#16 · cities: bali, jakarta · status: resolved*

**Question.** Adopt: a roundup tied to a period (year in title, '[Updated]', seasonal) is `listing` (540-day half-life, series_key dedup); a timeless how-to/area piece is `guide` (evergreen). §4 maps the Guide categories wholesale to `guide`.

**Affects.** bali: Bar Guide (76), bali: Restaurant Guide (52), jakarta: Bar Guide (28), jakarta: Dining (24), jakarta: City Guides (19), jakarta: Restaurant Guides (17), bali: Weddings (17)

**Evidence.**
- jakarta 'Bar Guide': 7% of titles carry a period stamp (year / [Updated] / season), 7% are roundups; 2019-2026
- jakarta 'Restaurant Guides': 41% of titles carry a period stamp (year / [Updated] / season), 24% are roundups; 2019-2026
- jakarta 'City Guides': 10% of titles carry a period stamp (year / [Updated] / season), 21% are roundups; 2019-2026
- jakarta 'Dining': 8% of titles carry a period stamp (year / [Updated] / season), 0% are roundups; 2023-2026
- bali 'Bar Guide': 4% of titles carry a period stamp (year / [Updated] / season), 10% are roundups; 2014-2026
- bali 'Restaurant Guide': 31% of titles carry a period stamp (year / [Updated] / season), 38% are roundups; 2016-2026
- bali 'Bali with Kids': 2% of titles carry a period stamp (year / [Updated] / season), 8% are roundups; 2017-2026
- bali 'Weddings': 0% of titles carry a period stamp (year / [Updated] / season), 12% are roundups; 2016-2026

**E2.0 recommendation.** Adopt the boundary. It is what lets the 2019 editions sink while the current '[Updated]' edition stays fresh through dedup.

**Options.** adopt (recommended) · everything in a *Guide category is `guide` (§4 literal) · everything period-stamped is `guide` but decays like listing

**Resolved (explicit, Hansel 2026-09-10).** Period-stamped roundups (a year in the title, '[Updated]', a seasonal marker) are `listing`: 540-day half-life, a `series_key`, and only the current member of a series is eligible in any rail. Timeless how-to and area pieces stay evergreen `guide`.

*Option: adopt.* Lets the 2019 editions sink while the current '[Updated]' edition stays fresh through series dedup; `guide` is reserved for pieces that do not date.

**Applied.** rules.guide_vs_listing · no category changes -- every Guide category already leaves format per article with D01 as the tie-breaker

### D10 · Multi-category resolution order: Yoast primary > most specific child > parent container

*kind: policy · articles affected: 213 · cities: bali, jakarta · status: resolved*

**Question.** Both sites file under parent containers alongside children (Bali: Dining Offers+Restaurants and Bars 188, Lifestyle+Shopping 109, Lifestyle+Spa 90, Explore Bali+Opinion 41; Jakarta: Dining Offers+Stay Offers 33). Bali has a Yoast primary on 90% of posts, Jakarta on 51%. Proposed: the prior comes from the Yoast primary when present; otherwise from the most specific (deepest) category; a parent-only category (Lifestyle, Culture, Explore Bali, Offers, Dining, Features...) is a weak prior for the articles that carry nothing else.

**Affects.** bali: Explore Bali (117), jakarta: Art & Culture (28), jakarta: Discover Jakarta (24), jakarta: Dining (24), jakarta: Features (20)

**Evidence.**
- jakarta: 224 articles (5%) carry 2+ categories; Yoast primary set on 2087 (44%); the primary is itself a parent container on 209
- jakarta container 'Offers': 55 articles, 19 carry nothing else; top co-filings: Experience Offers 20, Bali Updates 9, Explore Indonesia 5
- jakarta container 'Dining': 24 articles, 12 carry nothing else; top co-filings: Reviews 7, Features 2, Offers 1
- jakarta container 'Art & Culture': 28 articles, 23 carry nothing else; top co-filings: Events 2, Design 1, Community 1
- jakarta container 'Features': 20 articles, 9 carry nothing else; top co-filings: Made In Indonesia 2, Dining 2, Culture 1
- jakarta container 'Lifestyle': 13 articles, 8 carry nothing else; top co-filings: Shopping 2, Education 1, News 1
- jakarta container 'Travel': 21 articles, 17 carry nothing else; top co-filings: Explore Indonesia 1, Bali Updates 1, World Traveller 1
- jakarta container 'Discover Jakarta': 24 articles, 21 carry nothing else; top co-filings: History & Heritage 2, Sites & Destinations 1
- jakarta container 'Explore Indonesia': 154 articles, 140 carry nothing else; top co-filings: Offers 5, Dining News 2, Travel 1
- bali: 745 articles (17%) carry 2+ categories; Yoast primary set on 3648 (82%); the primary is itself a parent container on 400
- bali container 'Lifestyle': 243 articles, 1 carry nothing else; top co-filings: Shopping 114, Spa and Wellness 91, Bar Guide 26
- bali container 'Restaurants and Bars': 360 articles, 89 carry nothing else; top co-filings: Dining Offers 188, Reviews 63, Winocracy 9
- bali container 'Culture': 110 articles, 31 carry nothing else; top co-filings: Art In Bali 38, Dance and Music 18, Myths and Legends 13
- bali container 'Explore Bali': 117 articles, 22 carry nothing else; top co-filings: Activities 42, Opinion 41, Stranger In Paradise 8
- bali container 'Offers': 1 articles, 1 carry nothing else; top co-filings: 
- bali container 'Features': 3 articles, 3 carry nothing else; top co-filings: 
- bali container 'Home Life': 1 articles, 0 carry nothing else; top co-filings: Music to the Ears 1
- bali container 'Bar Guide': 76 articles, 38 carry nothing else; top co-filings: Lifestyle 26, News 13

**E2.0 recommendation.** Adopt. It makes the eleven container categories mostly moot.

**Options.** adopt (recommended) · always combine all categories · ignore Yoast primary

**Resolved (explicit, Hansel 2026-09-10).** Prior resolution order for a multi-category post: the Yoast primary category, else the deepest (most specific) child category, else the parent container.

*Option: adopt.* Makes the eleven container categories mostly moot; Bali has a Yoast primary on 82% of posts, Jakarta on 44%.

**Applied.** rules.prior_resolution

### D09 · Uncategorized (both cities) -> review queue; non-articles excluded

*kind: policy · articles affected: 154 · carried from E1.4 #7 · cities: bali, jakarta · status: resolved*

**Question.** Jakarta 83 + Bali 71 posts carry only Uncategorized, including non-editorial pages ('Order Form - NOW! Magazines', 'Purchasing NOW! Bali & TIMELESS Bali Magazines', 'USA NATIONAL DAY'). Proposed: no prior; every one goes to the E2.8 review queue regardless of classifier confidence; E1.8 flags obvious non-articles for exclusion below the quality floor.

**Affects.** jakarta: Uncategorized (83), bali: Uncategorized (71)

**Evidence.**
- jakarta: 83 Uncategorized (2019-2026); obvious non-articles by title: 4 -> USA NATIONAL DAY, French National Day 12 July 2019 at Raffles Jakart, SWISS NATIONAL DAY, Order Form - NOW! Magazines
- jakarta 'Uncategorized' (83): type cues editorial 31%, eat 26%, wellness 19%, stay 12% (coverage 51%); format cues opinion 34%, news 19%, event 9%, listing 9% (coverage 39%)
- bali: 71 Uncategorized (2014-2022); obvious non-articles by title: 1 -> Purchasing NOW! Bali & TIMELESS Bali Magazines
- bali 'Uncategorized' (71): type cues do 44%, eat 18%, wellness 11%, stay 9% (coverage 78%); format cues review 34%, opinion 22%, event 22%, news 9% (coverage 45%)

**E2.0 recommendation.** Confirm.

**Options.** confirm (recommended) · trust the classifier at the normal threshold

**Resolved (explicit, Hansel 2026-09-10).** Migrate everything and classify best-effort: no prior from Uncategorized, the classifier decides every facet, and the standard E2.1 confidence gate applies (below the auto-apply threshold -> review queue, never written as fact). Nothing is excluded.

*Option: migrate all; classifier at the normal threshold (neither listed option verbatim).* Hansel: migrate everything, nothing excluded -- including Uncategorized (154). The confidence gate is the standard path, not an override.

**Conflicts with the E2.0 recommendation (reported, not reconciled).**
- ⚠ The recommendation sent every Uncategorized post to the review queue regardless of confidence; the answer uses the standard gate, so high-confidence classifications auto-apply.
- ⚠ The recommendation excluded obvious non-articles below the quality floor; the answer excludes nothing. Five titles are pages rather than editorial ('Order Form - NOW! Magazines'; 'USA NATIONAL DAY'; 'French National Day 12 July 2019 at Raffles Jakarta'; 'SWISS NATIONAL DAY'; 'Purchasing NOW! Bali & TIMELESS Bali Magazines'). They will be classified best-effort and will most likely land in the review queue on low confidence, where an editor can unpublish them. Cheap to reverse -- flagged for a second look.

**Applied.** rules.migration_scope · rules.confidence_gate · jakarta + bali Uncategorized resolved: no prior, per-article everything

### D06 · Approve the `international` location root

*kind: vocabulary · articles affected: 153 · carried from E1.4 #6 · cities: bali, jakarta · status: resolved*

**Question.** `location` is required; World Traveller (94) and part of Travel are about Singapore, Dubai, Hong Kong, Switzerland... Seeded as a single leaf; children added once E2.1 reports the destination distribution.

**Affects.** jakarta: World Traveller (94), bali: Travel (38), jakarta: Travel (21)

**Evidence.**
- international destinations named in the corpus (articles): Europe 1247, Australia 508, Singapore 482, Tokyo 481, USA 377, China 361, Bangkok 293, India 290, Kuala Lumpur 228, Hong Kong 182, Africa 163, Turkey 154
- jakarta 'World Traveller' (94): 0% of titles/leads name a place outside jakarta
- jakarta 'Travel' (21): 38% of titles/leads name a place outside jakarta
- bali 'Travel' (38): 63% of titles/leads name a place outside bali

**E2.0 recommendation.** Approve.

**Options.** approve (recommended) · reject -> these articles get `indonesia` (wrong) or are excluded from location filters

**Resolved (explicit, Hansel 2026-09-10).** Add the `international` location root, editorial-only: searchable and eligible for Row 3 (related reading); never Row 1 (complementary places), never Row 2 (nearby), never the itinerary builder.

*Option: approve.* `location` is required and 115+ articles are about destinations abroad; they are worth reading next to a travel piece but can never be a nearby or complementary place, nor on an itinerary.

**Conflicts with the E2.0 recommendation (reported, not reconciled).**
- ⚠ The recommendation seeded `international` as a single leaf with children added 'once E2.1 reports the destination distribution'. The vocabulary answer (every corpus term with >= 20 mentions) adds 22 destination children now (see vocabulary-delta.json); the explicit answer wins. Children inherit the root's editorial-only attribute.

**Applied.** rules.location.international (encoding: term attribute geo_scope=abroad, enforced by the geo-anchored consumers) · vocabulary-delta: approve location/international with attrs.geo_scope=abroad; add 22 children · jakarta World Traveller keeps location international; jakarta Travel and bali Travel may pick it per article

### D08 · Bali's column and 'Home Life' archive categories: series_key, and are the lockdown columns migrated at all?

*kind: scope · articles affected: 147 · cities: bali · status: resolved*

**Question.** Bali carries column/series categories that are not subjects: Chaine Des Rottiseurs (24, 2015-18 dinner reports), Stranger In Paradise (21), Winocracy (9), NOW! Bali Podcast (27), Video (11), Behind the Bar (7), and the 2020 lockdown 'Home Life' series -- Cook and Mix (16), Must Watch Movies (13), Music to the Ears (11), Health & Wellness (7), Home Life (1). Proposed: `series_key = column:<slug>` for all; facets from content (mostly editorial/lifestyle|culture + feature). The movie/playlist columns have no Jakarta/Bali subject at all.

**Affects.** bali: NOW! Bali Podcast (27), bali: Chaine Des Rottiseurs (24), bali: Stranger In Paradise (21), bali: Cook and Mix (16), bali: Must Watch Movies (13), bali: Video (11), bali: Music to the Ears (11), bali: Winocracy (9), bali: Behind the Bar (7), bali: Health & Wellness (7), bali: Home Life (1)

**Evidence.**
- NOW! Bali Podcast (27, 2020-2025): Jero Gede Mecaling, Spreader of Death & Disease | Episo; Legends of Bali's Great Temples | Episode 4; What Will Travelling to Bali be like After Covid-19?
- Chaine Des Rottiseurs (24, 2015-2018): A Grand Induction At Sofitel Bali; Chaîne Luncheon at Locavore : Felicitations or Lamentat; Sunday Brunch À LA CHAÎNE
- Stranger In Paradise (21, 2015-2019): New Age New Bali; Looking Lovingly at Penjor; Bali Tourism at the Crossroads?
- Cook and Mix (16, 2016-2020): Cooking with Chef Mandif Warokka: Mie Cakalang; Petty Elliott's Udang Woku Blanga; Pepes Ikan: Grilled Spiced Red Snapper in Banana Leaf
- Must Watch Movies (13, 2020-2020): Add Colour to Life at Home: Wes Anderson Masterpieces Y; Co-Quarantine Cuddles: Best Tales of Love and Romance i; Tomorrowland: Post-Apocalyptic Movies That Remind Us, W
- Video (11, 2018-2023): Mason Jungle Buggies: High Speed Adventures in Bali; Hatten Wines Holds a Special Fund Raising Fair for Stel; Bali Safari & Marine Park - Experiencing the 4x4 Jeep R
- Music to the Ears (11, 2020-2020): Music & Conflict: Songs That Helped Soldiers Through Ha; One-and-done: One Hit Wonders of All-Time; Live From Your Living Room: Favourite Live & Acoustic T
- Winocracy (9, 2019-2020): Wines Banned : Indonesia's Struggle with Imported Wines; A Cup of Wine Please; The Art of Sleeping During Wine Dinners
- Behind the Bar (7, 2019-2026): Arey Barker : For Fig's Sake; Ayip Dzuhri : Samudra; Yudi Hendarsyah : Smoke & Fog
- Health & Wellness (7, 2020-2020): Home Workout by Coach Vincent; Yoga at Home with Erin Kindt of Odyssey Mvmt; Meditation for Beginners: Get Mindful with These Three 
- Home Life (1, 2020-2020): Songs to Send to Distant Lovers

**E2.0 recommendation.** Keep them all (they are cheap and searchable) but exclude the no-local-subject columns (Must Watch Movies, Music to the Ears) from the rails via the quality floor; carry series_key for every column.

**Options.** keep all, series_key, rails-excluded for the two non-local columns (recommended) · keep all, no exclusions · drop Must Watch Movies + Music to the Ears + Home Life from the migration

**Resolved (explicit, Hansel 2026-09-10).** Keep every column category and migrate all of it -- including Must Watch Movies (13) and Music to the Ears (11), which have no Bali subject. `series_key = column:<slug>` for every column. Follow-up #1: nothing is discarded and both columns stay fully searchable, but Must Watch Movies and Music to the Ears must not be recommended alongside local content -- the rails exclusion E2.0's original recommendation had is restored for exactly these two series. Every other column (Chaine Des Rottiseurs, Cook and Mix, Health & Wellness, Home Life, ...) keeps the original 'nothing excluded' answer unchanged.

*Option: keep all, migrated and searchable; rails-excluded for the two no-local-subject columns (follow-up #1, 2026-09-10, narrows the first answer's 'no exclusions').* Hansel: migrate everything, classify best-effort. Follow-up: 'migrate everything' was about not discarding content, not about making no-local-subject columns compete with local recommendations -- restoring the original recommendation's exclusion for exactly these two columns satisfies both without touching the other columns' rails eligibility.

**Conflicts with the E2.0 recommendation (reported, not reconciled).**
- ⚠ ORIGINAL (2026-09-10): the recommendation excluded the two no-local-subject columns from the rails via the quality floor. The first answer ('nothing excluded') removed that exclusion entirely and is applied as written in that round's pack.
- ⚠ SUPERSEDED same day by follow-up #1: the exclusion is restored for Must Watch Movies and Music to the Ears specifically, via a series-level hard-filter rule (not the quality floor -- see `RULES['columns']['excluded_from_rails']` for the mechanism and why). This is reported, not silently reconciled: the two rounds' packs will differ on this point if compared.
- ⚠ The four location-less columns (Must Watch Movies, Music to the Ears, Health & Wellness, Home Life) had `location: none` in the E2.0 proposal; `location` is a required facet, so the resolved prior is the site home (`bali`) -- the same fallback E1.4 uses for Jakarta (`location_when_unspecified`). This is independent of rails eligibility: the location prior still applies to all four; only Must Watch Movies and Music to the Ears lose rails eligibility.

**Applied.** rules.columns · rules.columns.excluded_from_rails (Must Watch Movies, Music to the Ears -- series-level rails exclusion, follow-up #1) · bali: Must Watch Movies, Music to the Ears, Health & Wellness, Home Life -> location prior bali · bali: Chaine Des Rottiseurs and Cook and Mix resolved under the mixed-categories answer (see the category records)

### D18 · Bali 'Explore Bali' is not a `do` category -- it is a container plus an opinion column

*kind: mapping · articles affected: 117 · cities: bali · status: resolved*

**Question.** LIVE_RECON N3 read `explore-bali` (117) as `do`. The articles disagree: 41 co-occur with Opinion ('Parking and Deliveries, The Headache Continues', 'Democracy in Action in Indonesia'), the rest are the parent of Activities/Cultural Sites/Destinations/Bali with Kids/Nature/Parks. Proposed: no type prior from 'Explore Bali' itself; children carry the priors; Explore Bali+Opinion -> editorial/opinion.

**Affects.** bali: Explore Bali (117)

**Evidence.**
- Explore Bali co-filings: Activities 42, Opinion 41, Stranger In Paradise 8; 22 carry Explore Bali alone
- bali 'Explore Bali' (117): type cues do 54%, editorial 20%, stay 9%, eat 6% (coverage 76%); format cues opinion 25%, review 22%, offer 16%, heritage 15% (coverage 58%)
- bali 'Explore Bali' clusters (tfidf-proxy, k=3, silhouette 0.144): 37% [editorial/opinion] e.g. New Years Resolutions: Getting Better All the Time?; Killing the Golden Goose: When Development Should Stop in Ba | 35% [do/review] e.g. Green Cycling Through Ubud; Saddle Up: Discovering Bali on Horseback | 28% [do/offer] e.g. Start Your Engines: Go Karting in Bali; Sea Breacher, The Ocean Trespasser

**E2.0 recommendation.** Accept -- treat as container (D10) and let Opinion win when both are present.

**Options.** accept (recommended) · do/* prior for all 117

**Resolved (as-recommended, Hansel 2026-09-10).** Explore Bali is a container (D10): no type prior of its own, children carry the priors; Explore Bali + Opinion -> editorial/opinion.

*Option: accept.* 41 of 117 co-occur with Opinion; the rest are the parent of Activities/Cultural Sites/Destinations.

**Applied.** no change

### D22 · Weddings (Bali, 17) and romance content: `occasion` term or a type?

*kind: mapping · articles affected: 17 · cities: bali · status: resolved*

**Question.** No §4 node fits weddings: venues are villas/resorts (stay), services are shops, the pieces are listings/guides. The seed has `occasion/celebration` with 'wedding' as an alias. Proposed: type per article, format listing|guide, occasion `celebration` -- or add a dedicated `occasion/wedding` (corpus: see vocabulary counts) so the itinerary/filters can target it.

**Affects.** bali: Weddings (17)

**Evidence.**
- corpus mentions -- wedding/honeymoon/proposal/bridal: 220 articles; Bali 'Weddings' category: 17

**E2.0 recommendation.** Add `occasion/wedding` (aliases honeymoon, proposal, bridal); it is a real reader intent in Bali.

**Options.** add occasion/wedding (recommended) · use celebration

**Resolved (explicit, Hansel 2026-09-10).** Add `occasion/wedding` (aliases weddings, honeymoon, proposal, bridal, bachelorette, hen party). The Bali Weddings category carries occasion `wedding` instead of `celebration`.

*Option: add occasion/wedding.* A real reader intent in Bali (220 corpus mentions); part of Hansel's >= 20 vocabulary answer.

**Applied.** vocabulary-delta: add occasion/wedding · bali Weddings: facets.occasion -> [wedding]

### D27 · Bali categories with 0-3 published posts and the WP-only categories

*kind: scope · articles affected: 5 · cities: bali · status: resolved*

**Question.** Features (3), Home Life (1), Offers (1), Mapping Bali (0 published; 41 in WP's count are non-post types), Archives (0). Proposed: no mapping needed -- Features/Home Life/Offers articles are classified from content; Mapping Bali and Archives are dropped as empty containers.

**Affects.** bali: Features (3), bali: Home Life (1), bali: Offers (1), bali: Mapping Bali (0), bali: Archives (0)

**Evidence.**
- Features: 3 published (WP count 3)
- Home Life: 1 published (WP count 1)
- Offers: 1 published (WP count 1)
- Mapping Bali: 0 published (WP count 0)
- Archives: 0 published (WP count 0)

**E2.0 recommendation.** Confirm.

**Options.** confirm (recommended)

**Resolved (as-recommended, Hansel 2026-09-10).** Features (3), Home Life (1) and Offers (1) are classified from content; Mapping Bali and Archives are empty containers with nothing to map.

*Option: confirm.* 0-3 published posts each.

**Applied.** no change

### D15 · Cuisine list: additions and removals from corpus evidence

*kind: vocabulary · articles affected: 0 · cities: jakarta, bali · status: resolved*

**Question.** The 27 seeded cuisines were invented, not extracted. The scan shows which never appear (removal candidates) and which frequent cuisines are missing (e.g. Singaporean/Malaysian, dessert/bakery/coffee as reader-facing 'cuisines', vegan/plant-based as a cuisine rather than only an amenity).

**Evidence.**
- seed cuisines with < 10 body mentions and 0 title mentions: none
- candidate cuisines with >= 40 mentions not in the seed: Coffee 941, Dessert 785, Organic 408, Fusion 333, Steak 266, Fine dining 193, Vegetarian 181, BBQ 159, Vegan 152, Burgers 115, Teppanyaki 98, Acehnese 73, Healthy 68, Bakery 68, Farm-to-table 58, Portuguese 53, Singaporean 47, Hotpot 41, Peruvian 40, Gluten-free 40

**E2.0 recommendation.** Remove seed cuisines with zero title mentions and < 10 body mentions; add candidates with >= 40 mentions; keep dietary needs in amenities as designed.

**Options.** apply thresholds (recommended) · keep the seed as-is · hand-pick

**Resolved (explicit, Hansel 2026-09-10).** Add every corpus cuisine term with >= 20 mentions. Dietary and approach terms (organic, healthy, vegetarian, vegan, gluten-free, farm-to-table) are routed to amenities, as the seed designed and the recommendation kept. No seed cuisine is removed (none has < 10 mentions).

*Option: apply thresholds (>= 20), dietary needs stay in amenities.* Hansel's flat >= 20 rule; the amenities routing is the accepted recommendation.

**Applied.** vocabulary-delta: 12 new cuisine terms, 10 cuisine alias sets, 3 dietary/approach terms routed to amenities (organic, healthy-menu, gluten-free) plus vegetarian/vegan as alias sets on the existing amenities; trim american/BBQ and chinese/hotpot (now their own cuisines)

### D16 · Vibe, occasion, amenity, audience, topic: prune the unused, add the frequent

*kind: vocabulary · articles affected: 0 · cities: jakarta, bali · status: resolved*

**Question.** Same check for the other invented lists. Some seed terms have zero corpus support; some corpus-frequent notions have no term (wedding/honeymoon as an occasion, digital-nomad as an audience, Ramadan/festive as occasions, jungle/rice-field view and private pool as amenities, Covid-19/urban issues as topics).

**Evidence.**
- vibe: unused seed terms none; rare none; frequent candidates missing: Tropical 2895, Authentic 2831, Modern 2573, Exclusive 1996, Chic 1608, Wholesome 887, Glamorous 791, Quirky 643
- occasion: unused seed terms none; rare none; frequent candidates missing: Festive 639, Business 570, Wedding 220, Ramadan 191, Nyepi / Galungan 179, Independence Day 95, Lunar New Year 91, Road trip 82
- amenities: unused seed terms none; rare none; frequent candidates missing: Buffet 629, Jungle view 357, Co-working 347, Free flow 217, Sauna / steam 203, Breakfast included 185, Late night 185, Vegetarian options 181
- audience: unused seed terms none; rare none; frequent candidates missing: Women 755, Students 588, Foodies 147, Seniors 63, Surfers 56, Divers 45
- topic: unused seed terms none; rare none; frequent candidates missing: Food & drink 3713, Weddings & romance 1384, Religion & spirituality 956, Coffee culture 899, Urban issues 821, Agriculture & food systems 736, Covid-19 438, Pets & animals 418

**E2.0 recommendation.** Prune zero-support terms unless a filter UI needs them; add candidates above the report's threshold.

**Options.** apply (recommended) · keep seed as-is

**Resolved (explicit, Hansel 2026-09-10).** Add every vibe, occasion, amenity, audience and topic corpus term with >= 20 mentions (duplicates merged: Retiree into seniors, the two wedding topics into one, Rice terrace + Hot spring + Waterfall into do/nature). Nothing is pruned -- no seed term has zero support. Trim the homonym aliases `party` (occasion/celebration) and `business` (audience/business-traveller).

*Option: apply (>= 20).* Hansel's flat >= 20 rule plus the named alias trims.

**Applied.** vocabulary-delta: vibe 12 terms + 9 alias sets, occasion 8 terms + 5 alias sets, amenities 23 terms (3 routed from cuisine) + 8 alias sets, audience 9 terms + 6 alias sets, topic 11 terms + 16 alias sets

## 2. Flagged by the evidence — and how each flag was resolved

Hansel's answer for mixed categories (`mixed-categories`): **Classify per article; no fixed category-wide type where the evidence shows a venue-type mix. Protects competitor exclusion.** The flagged facet becomes per-article. The E2.0 value stays the prior unless the cue instrument gives it <= 10% support against >= 50% for the alternate, in which case the alternate becomes the prior (Chaine Des Rottiseurs: event 0% vs review 50% -> prior review). Type flags where the instrument is fooled by vocabulary (Cook and Mix: recipes read as `eat`) still go per-article, with an explicit classifier note, because the E2.1 confidence gate catches a wrong `eat` and a false exclusion is the cheap error.

- **Travel** (38 articles; was `flagged-by-evidence`) — E2.0 proposal `editorial`/`city-guide` + *per article* (prior `city-guide`) @ *per article* (prior `other`) → resolved ***per article* (prior `editorial`)/*per article* (prior `city-guide`) + *per article* (prior `city-guide`) @ *per article* (prior `other`)**. Basis: mixed-categories, D06, D14.
  - flag: clusters split the category: k=3 split (silhouette 0.23, smallest cluster 26%) whose clusters read as different venue types (do, stay) while the proposal fixes type=editorial; 18% of members sit closer to a category of another type
  - resolution: editorial/city-guide stays the prior; the evidence split (do/stay clusters) made type per article.
- **Chaine Des Rottiseurs** (24 articles; was `decision-needed`) — E2.0 proposal `eat`/`fine-dining` + `event` @ `bali` → resolved **`eat`/`fine-dining` + *per article* (prior `review`) @ `bali`**. Basis: mixed-categories, D08, D02.
  - flag: cue instrument disagrees on format: proposal fixes `event` (short decay) but 50% of signal-bearing articles read as `review` (medium decay; only 0% as `event`)
  - resolution: Retrospective reports on society dinners (2015-2018): the cue instrument reads 50% review, 0% event, so the prior flips to review (540-day decay; all long expired either way). Type eat/fine-dining stays.
- **Stranger In Paradise** (21 articles; was `flagged-by-evidence`) — E2.0 proposal `editorial`/`opinion` + `opinion` @ `bali` → resolved **`editorial`/`opinion` + *per article* (prior `opinion`) @ `bali`**. Basis: mixed-categories, D24, D03, D08.
  - flag: clusters split the category: k=2 split (silhouette 0.13, smallest cluster 43%) whose clusters read as formats with different decay (evergreen, medium) while the proposal fixes format=opinion
  - resolution: Prior stays editorial/opinion + opinion (LLM: high-confidence opinion; first-person column). D24's text listed this column under heritage -- see D24.conflicts.
- **Cook and Mix** (16 articles; was `decision-needed`) — E2.0 proposal `editorial`/`lifestyle` + `feature` @ `bali` → resolved ***per article* (prior `editorial`)/*per article* (prior `lifestyle`) + `feature` @ `bali`**. Basis: mixed-categories, D08, D05.
  - flag: cue instrument disagrees on type: proposal fixes `editorial` but 93% of signal-bearing articles read as `eat` (only 0% as `editorial`) -- this changes competitor exclusion
  - resolution: The 93% `eat` cue is food vocabulary, not a venue subject (LLM agrees: editorial/lifestyle, high confidence). Per article under the mixed-categories answer, with the classifier note above.

## 3. Internal consistency — categories that are not one thing

Vector space: `tfidf-proxy (embeddings no rows for this model)`. A category is **incoherent** when k-means finds a split whose clusters read as different *venue* types while the proposal fixes one type (this changes competitor exclusion), or as formats with different decay classes while the proposal fixes one format — a split candidate, not a mapping problem. **mixed** is a weaker signal (clusters differ on non-venue types, or members sit closer to categories of another type). **expected-heterogeneous** means the proposal already leaves type per article (News, Events, containers, print issues), so heterogeneity is by design and the clusters are useful as classifier priors.

Verdicts were computed against the **E2.0 proposal**. Where the resolution made the flagged facet per article, the split is now by design — marked *↳ resolved* below.

| verdict | categories |
|---|---|
| incoherent | 2: Travel, Stranger In Paradise |
| mixed | 5: Destinations, Nature and Outdoors, Everyday Bali, Bali History, Parks and Attractions |
| expected-heterogeneous | 12: Weddings, News, Lifestyle, Art In Bali, Experience Offers, Explore Bali, Uncategorized, Video, Restaurants and Bars, Culture, Bali with Kids, Made in Bali |
| coherent | 24: Chaine Des Rottiseurs, Cook and Mix, Must Watch Movies, Music to the Ears, Dining Offers, Community, NOW! Bali Podcast, Dining News, Spa and Wellness, Shopping, Reviews, Stay Offers, Opinion, Hotels & Resorts, Activities, Cultural Observer, Bar Guide, Dance and Music … |
| too-small | 7: Health & Wellness, Home Life, Behind the Bar, Features, Offers, Mapping Bali, Archives |

### Split candidates

#### Travel — incoherent · 38 articles · E2.0 proposal `editorial` + *per article*

k=3 split (silhouette 0.23, smallest cluster 26%) whose clusters read as different venue types (do, stay) while the proposal fixes type=editorial; 18% of members sit closer to a category of another type. Cohesion 0.628 vs random baseline 0.428 (ratio 1.47); leakage 29% → Hotels & Resorts (3), Parks and Attractions (1), Nature and Outdoors (1), Uncategorized (1).

*↳ resolved:* *per article* (prior `editorial`)/*per article* (prior `city-guide`) + *per article* (prior `city-guide`) @ *per article* (prior `other`) (mixed-categories, D06, D14).

- **Cluster 1** — 16 articles (42%); cue type `do` 69%, cue format `city-guide` 64%; words: sumba, escape, lombok, fast, island, rediscovering
  - 2016-03-01 · Rediscovering Sumba
  - 2018-12-21 · Untouched: Discovering West Sumba
  - 2018-03-26 · Lombok: An Escape Across the Wallace Line
  - 2019-07-23 · Revisiting Lombok
- **Cluster 2** — 12 articles (32%); cue type `do` 64%, cue format `city-guide` 75%; words: island, komodo, bajo, flores, resort, labuan
  - 2026-05-21 · Exploring Labuan Bajo on Land and Sea: An Island Hopping Itinerary
  - 2024-05-28 · Exotic Adventures Around the Cape of Flowers
  - 2018-06-21 · Bijoux Bajo: Exploring Flores in Style
  - 2016-03-04 · Flourishing Flores
- **Cluster 3** — 10 articles (26%); cue type `stay` 50%, cue format `offer` 50%; words: lombok, beach, resort, gili, seaside, amber
  - 2024-07-12 · Discover Paradise at Your Doorstep at Amber Lombok Beach Resort
  - 2024-05-30 · Experience a Tranquil Seaside Escape at Amber Lombok Beach Resort
  - 2026-05-06 · Cocana Resort is Gili Trawangan's Chic Sanctuary
  - 2026-05-06 · At Innit Lombok, Contemporary Design Meets Barefoot Luxury

#### Stranger In Paradise — incoherent · 21 articles · E2.0 proposal `editorial` + `opinion`

k=2 split (silhouette 0.13, smallest cluster 43%) whose clusters read as formats with different decay (evergreen, medium) while the proposal fixes format=opinion. Cohesion 0.714 vs random baseline 0.444 (ratio 1.61); leakage 19% → Ceremonies & Festivals (1), Opinion (1), News (1), Bali History (1).

*↳ resolved:* `editorial`/`opinion` + *per article* (prior `opinion`) @ `bali` (mixed-categories, D24, D03, D08).

- **Cluster 1** — 12 articles (57%); cue type `editorial` 43%, cue format `review` 50%; words: paradise, age, pageants, beauty, toddy, palm
  - 2016-04-17 · Clouds Gathering Over The Rainbow?
  - 2015-02-04 · New Age New Bali
  - 2015-02-27 · Beauty Pageants in Paradise
  - 2015-07-31 · Of Indokrupuks and Tjokaholics
- **Cluster 2** — 9 articles (43%); cue type `editorial` 60%, cue format `heritage` 50%; words: bali's, high, quiet, kingdom, bangli, brahmans
  - 2015-12-13 · The Brahmans are Coming
  - 2016-05-17 · Tale of Two Kingdoms
  - 2019-01-15 · Bali's Power Pedanda : The Rise of Bali's High Priests
  - 2015-07-03 · Bangli – Bali’s quiet Kingdom

#### Destinations — mixed · 53 articles · E2.0 proposal `editorial` + `city-guide`

36% of members sit closer to a category of a different type (Nature and Outdoors 13, Cultural Sites 6, Bali History 2). Cohesion 0.626 vs random baseline 0.418 (ratio 1.5); leakage 47% → Nature and Outdoors (13), Cultural Sites (6), Bali History (2), Travel (2).

- **Cluster 1** — 36 articles (68%); cue type `do` 88%, cue format `city-guide` 50%; words: west, bali's, road, tabanan, local, itinerary
  - 2025-03-19 · Bali Road Trip Itinerary: Northwest Bali
  - 2015-10-02 · 11 Destinations That Will Show your 'Real Bali'
  - 2015-07-31 · Bangli Beckons
  - 2019-11-18 · West Bali : The Road Less-Travelled
- **Cluster 2** — 11 articles (21%); cue type `editorial` 71%, cue format `heritage` 100%; words: history, ancient, north, east, villages, exploring
  - 2023-03-28 · Explorations in North Bali: From Ancient History to Hot Springs
  - 2026-04-16 · In Search of Ancient Bali: Exploring Four Bali Aga Villages
  - 2024-09-19 · Denpasar: Searching for History in Bali's Capital City
  - 2021-07-04 · Klungkung and Its Craftsmen: The Influence of an Empire
- **Cluster 3** — 6 articles (11%); cue type `do` 100%, cue format `city-guide` 83%; words: nusa, island, guide, lembongan, ceningan, penida
  - 2026-06-04 · Discover Nusa Lembongan & Nusa Ceningan in Three Days: An Island Hopping Itinerary
  - 2025-01-01 · Escape to Nusa Lembongan: A NOW! Bali Guide
  - 2024-06-04 · Experiencing Island Living on Nusa Lembongan
  - 2020-01-27 · Carousing Nusa Ceningan : A NOW! Bali Guide

#### Nature and Outdoors — mixed · 33 articles · E2.0 proposal `do` + `guide`

33% of members sit closer to a category of a different type (Destinations 8, Community 3, Parks and Attractions 1). Cohesion 0.647 vs random baseline 0.432 (ratio 1.5); leakage 36% → Destinations (8), Community (3), Parks and Attractions (1).

- **Cluster 1** — 17 articles (52%); cue type `do` 86%, cue format `city-guide` 50%; words: kedonganan, beaches, hidden, best, along, spots
  - 2019-11-09 · On the Search for Bali’s Quiet Beaches
  - 2022-02-15 · Estuarine Explorations at the Kedonganan Mangroves
  - 2020-10-11 · Discovering the Best Waterfalls in Bali
  - 2016-01-07 · Guwang's Hidden Canyon
- **Cluster 2** — 10 articles (30%); cue type `do` 100%, cue format `guide` 29%; words: adventures, nature, spring, hot, healing, danau
  - 2016-10-17 · Hidden Adventures in Bedugul
  - 2021-07-01 · Lakes in Bali: Discover All 4 Stunning Bali Lakes
  - 2023-10-03 · Lakeside Bliss in Bali’s Highlands
  - 2026-08-20 · The Ultimate Adventure in Bali: Nature, Thrills and the Great Outdoors
- **Cluster 3** — 6 articles (18%); cue type `editorial` 100%, cue format `heritage` 100%; words: across, trail, island, bali's, best, fields
  - 2021-09-01 · The Astungkara Trail: A 10-Day Pilgrimage of Discovery Across Bali
  - 2023-01-24 · Back to the Roots: Learning to Farm in Bali
  - 2022-02-07 · For People and Planet: Developing Trail Tourism Across Bali
  - 2022-09-21 · Trails Through Tenganan

#### Bali History — mixed · 22 articles · E2.0 proposal `editorial` + `heritage`

k=2 split (silhouette 0.23) with clusters disagreeing on type; cross-type leakage 18%. Cohesion 0.688 vs random baseline 0.443 (ratio 1.55); leakage 36% → Cultural Sites (3), Cultural Observer (2), Art In Bali (2), Nature and Outdoors (1).

- **Cluster 1** — 13 articles (59%); cue type `do` 78%, cue format `heritage` 77%; words: history, early, brief, indies, spice, tourism
  - 2023-05-29 · Early Travels to the ‘Dutch East Indies’
  - 2025-09-17 · Indonesian Fruits Through the Eyes of Early Explorers and Botanists
  - 2025-06-26 · Bali Island in Early Photography
  - 2024-06-11 · Fallen Angels: Indonesia’s Bird of Paradise
- **Cluster 2** — 9 articles (41%); cue type `editorial` 100%, cue format `heritage` 88%; words: history, tolerance, islam, hinduism, construction, affair
  - 2019-04-30 · Early Islam in Bali: A Local Legend
  - 2026-06-18 · Senduro: The Persistent Shadow of Majapahit over Java and Bali
  - 2022-04-03 · A History of Islam in Bali: A Story of Tolerance
  - 2019-04-13 · Tracing the History of Bali: Religious Tolerance & A King's Love Affair

#### Parks and Attractions — mixed · 17 articles · E2.0 proposal `do` + *per article*

k=3 split (silhouette 0.29) with clusters disagreeing on decay class; cross-type leakage 12%. Cohesion 0.66 vs random baseline 0.454 (ratio 1.45); leakage 18% → Nature and Outdoors (1), Destinations (1), Shopping (1).

- **Cluster 1** — 8 articles (47%); cue type `do` 75%, cue format `offer` 40%; words: park, theme, bali's, biggest, funtastic, land
  - 2017-12-11 · Funtastic Land: Bali's Biggest Theme Park
  - 2023-07-04 · Trans Studio Bali: Experience Bali's Epic Indoor Theme Park
  - 2018-01-17 · A Visit to Kemenuh Butterfly Park
  - 2025-01-30 · Bali Farm House: Countryside Charm at Bali’s First Interactive Farm Sanctuary
- **Cluster 2** — 5 articles (29%); cue type `do` 100%, cue format `heritage` 100%; words: zoo, parks, bali's, attractions, best, adventure
  - 2022-01-19 · Bali Safari: Educational Adventure at This Leading Animal Conservation Park
  - 2025-08-28 · Embark On a Fun-Filled Family Excursion at Bali Zoo
  - 2017-04-03 · Bali's Best Parks and Attractions
  - 2026-05-08 · The Full Bali Zoo Experience
- **Cluster 3** — 4 articles (24%); cue type `do` 100%, cue format `news` 67%; words: adventure, indoor, park, aeroxspace, largest, adrenaline-fueled
  - 2026-07-15 · AeroXSpace: The Ultimate Indoor Playground Experience
  - 2024-09-03 · AeroXSpace: Bali’s Largest Adrenaline-Fueled Indoor Adventure Park
  - 2026-05-12 · Play, Splash, Repeat: Fun Family Days Await at Mookiland Park
  - 2026-07-28 · Sliding Into Adventure at Waterbom Bali

#### Everyday Bali — mixed · 30 articles · E2.0 proposal `editorial` + `feature`

k=2 split (silhouette 0.19) with clusters disagreeing on type; cross-type leakage 3%. Cohesion 0.777 vs random baseline 0.434 (ratio 1.79); leakage 7% → People of Bali (1), Cultural Sites (1).

- **Cluster 1** — 19 articles (63%); cue type `do` 50%, cue format `heritage` 100%; words: offering, bali's, sacred, offerings, banten, jotan
  - 2024-11-14 · Ulap-Ulap: The Protector of Balinese Buildings
  - 2020-07-03 · Tedung : Bali's Ceremonial Umbrella
  - 2024-09-23 · Pratima and Pralingga: Effigies of the Gods
  - 2024-05-22 · Kwangen: Bali’s Fragrant Offering
- **Cluster 2** — 11 articles (37%); cue type `editorial` 50%, cue format `heritage` 100%; words: traditional, philosophy, banjar, modern, complexities, world
  - 2020-08-09 · Udeng : The Traditional Headdress of Balinese Men
  - 2026-05-06 · Cili: The Symbol of Beauty and Fertility
  - 2023-10-25 · Tipat and Bantal: Symbols of the Feminine and Masculine
  - 2026-07-13 · The Hidden Philosophy of Keben

### Expected-heterogeneous categories, largest first (clusters = classifier priors)

#### News — expected-heterogeneous · 1067 articles · E2.0 proposal *per article* + `news`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.392 vs random baseline 0.397 (ratio 0.99); leakage 77% → Community (112), Hotels & Resorts (73), Bar Guide (70), Art In Bali (67).

- **Cluster 1** — 439 articles (41%); cue type `stay` 38%, cue format `news` 53%; words: opens, resort, beach, ubud, club, seminyak
  - 2019-04-15 · W Hotels Worldwide Announces W Bali - Ubud To Open in 2020
  - 2020-02-07 · The Garcia Island-Inspired Boutique Resort Opens in Ubud
  - 2018-11-18 · Trans Resort Bali : Your Family's Home Away from Home in Bali
  - 2019-05-14 · X2 Bali Breakers Resort Opens Near Balangan Beach
- **Cluster 2** — 348 articles (33%); cue type `editorial` 30%, cue format `news` 40%; words: bali's, charity, launches, hotel, school, day
  - 2017-05-10 · The Future is Now 2017: 2nd Annual NOW! Bali PR and Marcomm Gathering
  - 2019-12-09 · The Bali Hope Swimrun 2019 and the Birth of 'Island Protect'
  - 2019-07-01 · The NOW! Bali PR Gathering 2019
  - 2022-09-14 · Australian Supermodel of the Year 2023 Welcomes Indonesian Applicants
- **Cluster 3** — 280 articles (26%); cue type `event` 66%, cue format `event` 76%; words: festival, exhibition, ubud, art, food, writers
  - 2024-08-08 · Indonesia Bertutur 2024: An Island-Wide Cultural Showcase Unfolds Across Bali
  - 2024-06-07 · Bali Arts Festival 2024: Dates, Venue and Information
  - 2024-11-19 · Amarta Beach Festival 2024: Celebrating Bali’s Timeless Culture
  - 2025-08-07 · Titik Dua Honours Film Legend John Badalu with Brand-New Cinema Programme

#### Lifestyle — expected-heterogeneous · 243 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.451 vs random baseline 0.401 (ratio 1.12); leakage 98% → Shopping (94), Spa and Wellness (77), Bar Guide (23), Bali with Kids (8).

- **Cluster 1** — 134 articles (55%); cue type `shop` 53%, cue format `news` 44%; words: bali's, shopping, collection, island, opens, sensatia
  - 2018-02-22 · Design Your Own Flip Flops at Baia Baia
  - 2017-07-03 · A Seminyak Shopping Spree
  - 2016-04-16 · Bali Collection: The Perfect Shop Stop
  - 2015-08-03 · Away From Spray
- **Cluster 2** — 86 articles (35%); cue type `wellness` 98%, cue format `news` 38%; words: spa, experience, wellness, rejuvenation, seminyak, healing
  - 2016-11-10 · Renewing My Prana
  - 2018-07-19 · Put Your Feet Up: 4 Great Spots for Reflexology in Bali
  - 2015-05-27 · Taman Merah Spa
  - 2016-12-16 · Take This Wellness Program for Your Year End Resortation
- **Cluster 3** — 23 articles (9%); cue type `shop` 88%, cue format `heritage` 60%; words: birthstone, jemme, jewellery, precious, jewelery, bling
  - 2017-06-05 · The Diamond is June's Birthstone!
  - 2016-06-17 · Precious Jemme
  - 2015-09-02 · Exceptional Balinese Craftmanship
  - 2016-01-10 · Something Precious for the Precious Ones

#### Art In Bali — expected-heterogeneous · 136 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.71 vs random baseline 0.405 (ratio 1.76); leakage 14% → Bali History (5), Culture (3), Cultural Observer (3), Dance and Music (2).

- **Cluster 1** — 83 articles (61%); cue type `editorial` 56%, cue format `heritage` 53%; words: art, artist, bali's, traditional, contemporary, artistic
  - 2021-08-17 · Expatriate Artist Izzy Ivy’s Delightful Visionary Paintings Mediate Between the Worlds
  - 2021-03-26 · Made Valasara’s Artistic Exploration of Material Potential
  - 2023-11-29 · Balinese Priestess Artist Mangku Muriati’s Pandemic Observations in the Kamasan Traditional Style
  - 2022-12-12 · Wayan Kun Adnyana’s Unique Mission Within the Development of  Balinese Contemporary Art
- **Cluster 2** — 53 articles (39%); cue type `do` 38%, cue format `event` 36%; words: art, ubud, exhibition, bali's, contemporary, gallery
  - 2019-12-03 · Art Bali 2019 : An Exploration into Contemporary Art
  - 2019-04-07 · Bali Art World Personalities : Meet Ruth Onduko
  - 2021-05-31 · Cakravala: A New Cultural Platform Elevating Emerging Indonesian Artists
  - 2018-03-13 · Dipping in the Kool Aid: Bali Prison Inmates Show Artistic Talents

#### Experience Offers — expected-heterogeneous · 128 articles · E2.0 proposal *per article* + `offer`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.531 vs random baseline 0.405 (ratio 1.31); leakage 50% → Stay Offers (15), News (13), Spa and Wellness (9), Bar Guide (4).

- **Cluster 1** — 66 articles (52%); cue type `stay` 36%, cue format `offer` 69%; words: resort, easter, ubud, experience, wellness, seminyak
  - 2025-04-10 · Immerse in a Serene Easter Holiday by the Sea at Jumeirah Bali
  - 2021-11-23 · A Peek into the Experiences Offered at Japanese Hidden Gem, HOSHINOYA Bali
  - 2022-03-24 · Joyful Easter Celebrations at The Westin Resort & Spa Ubud
  - 2024-02-22 · Enjoy Luxury Experiences at The Ritz-Carlton Bali with Their Exclusive Day Pass
- **Cluster 2** — 44 articles (34%); cue type `eat` 65%, cue format `offer` 100%; words: festive, resort, season, year-end, beach, holiday
  - 2024-11-20 · Cherish Joyful Festive Moments at Hilton Bali Resort
  - 2024-11-26 · Splash Into Ayodya Resort Bali’s ‘Aqua Wonderland’ Festive Programme
  - 2024-11-28 · Welcome the Season of Joy at The Oberoi Beach Resort, Bali
  - 2023-11-15 · Merry Moments Await at Holiday Inn Resort Baruna Bali
- **Cluster 3** — 18 articles (14%); cue type `event` 47%, cue format `event` 64%; words: beach, club, presents, festival, temptation, tropical
  - 2025-10-16 · Usher in a Wicked October at The Iron Fairies Bali
  - 2022-12-13 · Road to 2023: White Rock Beach Club Presents an Epic 8-Day Year-End Festival
  - 2022-07-06 · KU DE TA Announces the Return of its Highly-Anticipated Annual White Party
  - 2024-12-26 · Savaya Bali Presents a Star-Studded Week-Long New Year’s Celebration

#### Explore Bali — expected-heterogeneous · 117 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=3 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.548 vs random baseline 0.406 (ratio 1.35); leakage 94% → Opinion (34), Activities (20), Nature and Outdoors (7), Cultural Sites (7).

- **Cluster 1** — 43 articles (37%); cue type `editorial` 52%, cue format `opinion` 55%; words: bali's, years, things, life, staying, golden
  - 2017-12-13 · New Years Resolutions: Getting Better All the Time?
  - 2017-10-12 · Killing the Golden Goose: When Development Should Stop in Bali
  - 2018-03-22 · The Bitter Lessons  Experience Teaches Us
  - 2016-02-08 · Disturbing Facts
- **Cluster 2** — 41 articles (35%); cue type `do` 52%, cue format `review` 33%; words: bali's, east, art, high, royal, real
  - 2018-10-14 · Green Cycling Through Ubud
  - 2016-05-14 · Saddle Up: Discovering Bali on Horseback
  - 2015-08-03 · Charly and his Chocolate Factory
  - 2016-04-30 · Majestic Mornings in East Bali
- **Cluster 3** — 33 articles (28%); cue type `do` 86%, cue format `offer` 53%; words: bali's, best, time, beaches, escape, diving
  - 2018-05-16 · Start Your Engines: Go Karting in Bali
  - 2016-11-22 · Sea Breacher, The Ocean Trespasser
  - 2016-11-12 · 5GX Bali: The Slingshot Returns
  - 2019-12-03 · The Best Water Sports in Bali : 11 Activities You Have to Try

#### Uncategorized — expected-heterogeneous · 71 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.537 vs random baseline 0.412 (ratio 1.3); leakage 58% → Opinion (9), Destinations (4), Weddings (4), News (4).

- **Cluster 1** — 39 articles (55%); cue type `do` 47%, cue format `review` 55%; words: bali's, welcome, well, food, kids, best
  - 2018-08-03 · Bali's Sung and Unsung Heroes
  - 2019-02-28 · What Does it Take to be a 'Bali Hero'?
  - 2019-01-02 · Happy Birthday to Us: 10 Years of NOW! Bali
  - 2017-04-03 · Is Bali Good for Kids? Yes!
- **Cluster 2** — 22 articles (31%); cue type `do` 44%, cue format `event` 60%; words: seven, festival, event, beach, bali's, great
  - 2020-01-08 · A Dying Paradise: Preserving Religion, Culture and Customs in Bali
  - 2014-12-01 · Great Escapes
  - 2020-01-16 · Bali Tourism 2020: What Does the Government Have Planned for the Island?
  - 2020-01-14 · Rural Experiences and the Rise of Bali's 'Tourist Villages'
- **Cluster 3** — 10 articles (14%); cue type `eat` 43%, cue format `news` 50%; words: love, right, shores, high, dramatic, cliffs
  - 2015-02-04 · High On Dramatic Cliffs
  - 2015-02-04 · Right  Here On Our Shores
  - 2015-02-04 · Take the Love Deeper
  - 2016-02-03 · Making the Bonds of Love

#### Restaurants and Bars — expected-heterogeneous · 360 articles · E2.0 proposal `eat` + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.503 vs random baseline 0.4 (ratio 1.26); leakage 50% → Reviews (58), Dining Offers (29), Bar Guide (19), Restaurant Guide (14).

- **Cluster 1** — 132 articles (37%); cue type `eat` 98%, cue format `review` 38%; words: restaurant, ubud, menu, flavours, dining, bites
  - 2015-02-27 · Hujan Locale its Raining Flavors in Ubud
  - 2017-08-03 · Vintaged at Balique Restaurant
  - 2016-05-07 · The Patriotic Flavours of Republik 45
  - 2019-07-11 · The Flavours of Salt, A Canggu Restaurant
- **Cluster 2** — 125 articles (35%); cue type `eat` 84%, cue format `news` 79%; words: restaurant, bar, dining, kitchen, opens, menu
  - 2018-01-29 · Meja Kitchen & Bar Goes 'Back To The Roots'
  - 2017-03-09 · Bikini Brings The Sexy Back to Seminyak
  - 2017-11-09 · Savour Peruvian-Asian Gastronomy at Seminyak's AYA Street
  - 2018-04-23 · Mr Husky Serves up Southeast Asian Cuisine with Style
- **Cluster 3** — 103 articles (29%); cue type `eat` 55%, cue format `offer` 52%; words: brunch, wine, bali's, sunday, tea, beach
  - 2016-03-02 · How Divine
  - 2017-03-03 · Bali's Breakfast Delights
  - 2019-08-19 · A Cup of Wine Please
  - 2015-02-27 · Dining Snippet

#### Culture — expected-heterogeneous · 110 articles · E2.0 proposal `editorial` + `feature`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.567 vs random baseline 0.406 (ratio 1.4); leakage 98% → Art In Bali (32), Dance and Music (16), Ceremonies & Festivals (15), Cultural Observer (13).

- **Cluster 1** — 54 articles (49%); cue type `do` 50%, cue format `heritage` 70%; words: bali's, story, ceremony, world, soul, side
  - 2020-04-18 · A Bali Myth: Knock-Knock, Who's There?
  - 2017-11-01 · Under the Rumbling Holy Mountain
  - 2023-01-01 · Ngaben: The Balinese Cremation Ceremony
  - 2015-07-02 · When The Balinese Go to The Sea
- **Cluster 2** — 37 articles (34%); cue type `do` 48%, cue format `heritage` 29%; words: art, bali's, contemporary, artistic, prize, couteau
  - 2018-01-29 · Bali's Citra Sasmita: In The Spotlight of Indonesian Contemporary Art
  - 2019-02-09 · Aswino Aji's Artistic Observations of the Ego in the Face of Balinese Culture
  - 2020-09-10 · Jean-Philippe Haure’s Quest for Beauty
  - 2018-11-13 · Empowering Bali's Women Artists: Futuwonder
- **Cluster 3** — 19 articles (17%); cue type `event` 60%, cue format `heritage` 77%; words: dance, bird, cultural, barong, gita, sandya
  - 2016-01-12 · The Bird King
  - 2020-02-17 · Sandya Gita Kotamaning Bayu
  - 2020-04-15 · Legong Jobog - Balinese Tale of Subali & Sugriwa
  - 2019-09-09 · Manik Jiwa Dance

## 4. Vocabulary — the seed against the corpus, both directions

Method: distinct articles whose title+body contain the term or one of its aliases (case-insensitive, word-boundary); lexical, so homonyms inflate a few counts (party, solo, classic, business, casual); title-only counts are the stricter signal. Scanned jakarta 4,772, bali 4,429 articles = 9,201.

**Resolved (D14/D15/D16/D22 — add every corpus term with ≥ 20 mentions):** the reviewed change list is `engine/packages/taxonomy-evidence/vocabulary-delta.md` (machine twin `engine/packages/taxonomy-evidence/vocabulary-delta.json`): 44 approvals of already-seeded proposed terms, **140 terms to add** (amenities 23, audience 9, cuisine 12, location 54, occasion 8, subtype 11, topic 11, vibe 12), 85 alias sets (232 forms), 1 drop (`location/rawamangun`), 9 alias trims, 8 merged and 3 skipped candidates; 112 of the new terms need the F20 Payload ENUM migration. Nothing below has been written to the seed.

### 4a. Seed terms that never appear (0) — removal candidates

*none*

### 4b. Seed terms with fewer than 5 mentions (2) — keep only if a filter needs the value

| facet | slug | jakarta | bali |
|---|---|---|---|
| location | `rawamangun` *(proposed)* | 2 | 0 |
| subtype | `city-guide` | 1 | 2 |

### 4c. Frequent corpus terms with no seed term (≥ 12 articles) — addition candidates (resolved: ≥ 20 added, see the delta)

**amenities** — Buffet 629 (j 405 / b 224; titles 10), Jungle view [jungle view, jungle, rainforest] 357 (j 107 / b 250; titles 30), Co-working [co-working, coworking, ballroom] 347 (j 243 / b 104; titles 13), Free flow [free flow, free-flow, bottomless] 217 (j 98 / b 119; titles 3), Sauna / steam [sauna, steam room, jacuzzi] 203 (j 78 / b 125; titles 0), Breakfast included [breakfast included, daily breakfast] 185 (j 89 / b 96; titles 0), Late night [open late, 24 hours, 24-hour] 185 (j 90 / b 95; titles 1), Vegetarian options [vegetarian] 181 (j 55 / b 126; titles 8), Rice-field view [rice field, rice paddies, paddy view] 173 (j 26 / b 147; titles 2), Private pool [private pool, plunge pool] 151 (j 31 / b 120; titles 0), Delivery [delivery, takeaway, take-away] 146 (j 89 / b 57; titles 6), Lagoon [lagoon pool, lagoon] 138 (j 58 / b 80; titles 2), River view [riverside, river view, Ayung] 133 (j 19 / b 114; titles 22), Cabana / day bed [cabana, day bed, daybed] 96 (j 22 / b 74; titles 7), Airport transfer [airport transfer, shuttle] 96 (j 51 / b 45; titles 1), Swim-up bar [swim-up bar, pool bar] 94 (j 37 / b 57; titles 3), Butler 71 (j 27 / b 44; titles 0), Dive centre [dive centre, dive center, dive shop] 61 (j 19 / b 42; titles 2), Karaoke 54 (j 42 / b 12; titles 3), Yoga shala [yoga shala, yoga studio, shala] 45 (j 8 / b 37; titles 0), Cold plunge / ice bath [ice bath, cold plunge] 44 (j 13 / b 31; titles 0), Gluten-free 40 (j 11 / b 29; titles 0), Cigar lounge [cigar] 33 (j 16 / b 17; titles 0), Wine cellar 32 (j 15 / b 17; titles 2), Sports screening [big screen, live sports] 24 (j 11 / b 13; titles 2), Shisha [shisha, hookah] 17 (j 7 / b 10; titles 0), Surf break [surf break, surf spot, reef break] 12 (j 3 / b 9; titles 0)

**audience** — Women [women, female travellers, ladies] 755 (j 371 / b 384; titles 48), Students [students, teenagers] 588 (j 430 / b 158; titles 31), Foodies [foodies, foodie] 147 (j 84 / b 63; titles 11), Seniors [seniors, elderly] 63 (j 40 / b 23; titles 0), Surfers 56 (j 12 / b 44; titles 0), Divers 45 (j 17 / b 28; titles 0), Yogis [yogis, yogi] 37 (j 10 / b 27; titles 0), Digital nomad [digital nomads, digital nomad, remote workers] 23 (j 3 / b 20; titles 1), Backpacker [backpacker, backpackers, budget travellers] 20 (j 9 / b 11; titles 0), Retiree [retirees, retirement, retire] 20 (j 9 / b 11; titles 0), LGBTQ [LGBT, LGBTQ, gay-friendly] 13 (j 8 / b 5; titles 0)

**cuisine** — Coffee [coffee, kopi, specialty coffee] 941 (j 491 / b 450; titles 57), Dessert [dessert, gelato, ice cream] 785 (j 439 / b 346; titles 25), Organic 408 (j 143 / b 265; titles 2), Fusion 333 (j 170 / b 163; titles 20), Steak 266 (j 137 / b 129; titles 8), Fine dining [degustation, Michelin] 193 (j 90 / b 103; titles 17), Vegetarian 181 (j 55 / b 126; titles 8), BBQ [barbecue, smokehouse] 159 (j 74 / b 85; titles 11), Vegan 152 (j 32 / b 120; titles 7), Burgers [burger] 115 (j 43 / b 72; titles 2), Teppanyaki 98 (j 48 / b 50; titles 9), Acehnese [Acehnese, Aceh] 73 (j 48 / b 25; titles 0), Healthy [healthy food, health food, clean eating] 68 (j 37 / b 31; titles 3), Bakery [sourdough, croissant] 68 (j 30 / b 38; titles 0), Farm-to-table [farm-to-table, farm to table] 58 (j 14 / b 44; titles 3), Portuguese 53 (j 39 / b 14; titles 2), Singaporean 47 (j 29 / b 18; titles 2), Hotpot [hot pot, shabu-shabu, shabu] 41 (j 23 / b 18; titles 8), Peruvian [Nikkei] 40 (j 22 / b 18; titles 5), Gluten-free 40 (j 11 / b 29; titles 0), Nordic [Nordic, Scandinavian] 39 (j 30 / b 9; titles 5), Moroccan 34 (j 19 / b 15; titles 3), Malaysian 33 (j 27 / b 6; titles 1), Sichuan [Szechuan] 24 (j 17 / b 7; titles 0), Tea [tea house, teahouse] 22 (j 19 / b 3; titles 0), Argentinian [Argentine, asado] 16 (j 11 / b 5; titles 1), Raw food 16 (j 2 / b 14; titles 0)

**location_bali** — Tabanan 162 (j 18 / b 144; titles 6), Kintamani [Kintamani, Mount Batur, Batur] 153 (j 16 / b 137; titles 5), Gianyar [Sukawati, Celuk, Batubulan] 150 (j 6 / b 144; titles 3), Karangasem [Amlapura, Tirta Gangga, Tenganan] 115 (j 5 / b 110; titles 8), West Bali [West Bali, Menjangan, Pemuteran] 109 (j 11 / b 98; titles 11), Bedugul [Bedugul, Bratan, Beratan] 87 (j 7 / b 80; titles 9), Bangli [Bangli, Penglipuran] 69 (j 2 / b 67; titles 4), Nusa Lembongan [Lembongan, Ceningan] 58 (j 2 / b 56; titles 13), Mengwi [Mengwi, Taman Ayun] 45 (j 1 / b 44; titles 1), Tanah Lot 40 (j 2 / b 38; titles 1), Jatiluwih 31 (j 3 / b 28; titles 1), Kedonganan 27 (j 3 / b 24; titles 4), Sanur / Ketewel [Ketewel, Saba] 25 (j 3 / b 22; titles 0), Serangan 21 (j 0 / b 21; titles 0), Seseh / Cemagi [Seseh, Cemagi, Kedungu] 16 (j 1 / b 15; titles 1), Tejakula 15 (j 0 / b 15; titles 1)

**location_elsewhere** — Java (general) [Java, Central Java, East Java] 859 (j 537 / b 322; titles 52), Sumatra (general) [Sumatra] 206 (j 127 / b 79; titles 11), Sulawesi [Sulawesi, Wakatobi, Togean] 179 (j 124 / b 55; titles 6), Kalimantan [Kalimantan, Borneo, Derawan] 156 (j 114 / b 42; titles 7), Nusa Tenggara [Nusa Tenggara, NTT, Sumbawa] 133 (j 90 / b 43; titles 3), Maluku [Maluku, Moluccas, Banda] 109 (j 78 / b 31; titles 6), Aceh [Aceh, Banda Aceh, Weh] 70 (j 46 / b 24; titles 0), Riau Islands [Batam, Riau] 44 (j 40 / b 4; titles 5), Palembang 39 (j 35 / b 4; titles 1), Padang [Bukittinggi, West Sumatra] 38 (j 24 / b 14; titles 0), Lampung [Lampung, Krakatau, Krakatoa] 37 (j 27 / b 10; titles 3), Cirebon 30 (j 28 / b 2; titles 0), Anyer / Carita [Anyer, Carita] 14 (j 13 / b 1; titles 6)

**location_international** — Europe [Europe, Paris, London] 1247 (j 825 / b 422; titles 67), Australia [Australia, Sydney, Melbourne] 508 (j 285 / b 223; titles 37), Singapore 482 (j 356 / b 126; titles 29), Tokyo [Tokyo, Japan, Kyoto] 481 (j 317 / b 164; titles 33), USA [New York, Los Angeles, San Francisco] 377 (j 248 / b 129; titles 6), China [China, Shanghai, Beijing] 361 (j 250 / b 111; titles 4), Bangkok [Bangkok, Thailand, Phuket] 293 (j 198 / b 95; titles 14), India [India, Mumbai, Delhi] 290 (j 169 / b 121; titles 8), Kuala Lumpur [Kuala Lumpur, Malaysia, Penang] 228 (j 176 / b 52; titles 6), Hong Kong 182 (j 125 / b 57; titles 12), Africa [Africa, Kenya, Tanzania] 163 (j 111 / b 52; titles 0), Turkey [Turkey, Istanbul, Cappadocia] 154 (j 103 / b 51; titles 4), Seoul [Seoul, South Korea, Korea] 145 (j 114 / b 31; titles 12), New Zealand [New Zealand, Auckland, Queenstown] 138 (j 91 / b 47; titles 12), Vietnam [Vietnam, Hanoi, Ho Chi Minh] 123 (j 88 / b 35; titles 3), Philippines [Philippines, Manila, Cebu] 105 (j 82 / b 23; titles 1), Dubai [Dubai, Abu Dhabi, UAE] 84 (j 52 / b 32; titles 3), Middle East [Qatar, Doha, Oman] 50 (j 40 / b 10; titles 7), Cambodia / Laos [Cambodia, Siem Reap, Laos] 47 (j 37 / b 10; titles 1), Taiwan [Taiwan, Taipei] 47 (j 36 / b 11; titles 3), Maldives 32 (j 22 / b 10; titles 2), Sri Lanka [Sri Lanka, Colombo] 29 (j 20 / b 9; titles 1), Nepal / Bhutan [Nepal, Bhutan, Kathmandu] 18 (j 13 / b 5; titles 2)

**location_jakarta** — Kebayoran Baru [Kebayoran] 103 (j 103 / b 0; titles 1), Cilandak [Cilandak, TB Simatupang, Simatupang] 69 (j 69 / b 0; titles 5), Kemayoran [Kemayoran, JIExpo] 67 (j 66 / b 1; titles 5), Gatot Subroto 66 (j 62 / b 4; titles 3), Tanah Abang 53 (j 52 / b 1; titles 3), Casablanca [Casablanca, Kota Kasablanka] 47 (j 41 / b 6; titles 5), Kebon Sirih [Kebon Sirih, Sabang] 41 (j 36 / b 5; titles 2), Cengkareng [Cengkareng, Soekarno-Hatta] 38 (j 37 / b 1; titles 1), Kepulauan Seribu [Thousand Islands, Kepulauan Seribu, Pulau Seribu] 32 (j 28 / b 4; titles 3), Antasari 25 (j 25 / b 0; titles 5), TMII [Taman Mini, TMII] 25 (j 25 / b 0; titles 4), Sunda Kelapa 17 (j 17 / b 0; titles 1), Karawaci [Karawaci, Lippo Village] 16 (j 16 / b 0; titles 4), Grogol 15 (j 15 / b 0; titles 1), Mampang 15 (j 15 / b 0; titles 1), Pejaten 12 (j 11 / b 1; titles 0), Senen 12 (j 12 / b 0; titles 0)

**occasion** — Festive [Christmas, New Year, New Year's Eve] 639 (j 349 / b 290; titles 211), Business [business dinner, client, meeting] 570 (j 417 / b 153; titles 15), Wedding [weddings, proposal, bridal] 220 (j 126 / b 94; titles 21), Ramadan [Ramadan, iftar, buka puasa] 191 (j 162 / b 29; titles 115), Nyepi / Galungan [Nyepi, Galungan, Saraswati] 179 (j 17 / b 162; titles 56), Independence Day [Independence Day, 17 August] 95 (j 72 / b 23; titles 23), Lunar New Year [Chinese New Year, Lunar New Year, Imlek] 91 (j 72 / b 19; titles 44), Road trip [road trip, itinerary, island hopping] 82 (j 39 / b 43; titles 10), Group [large group, group of friends, group booking] 49 (j 21 / b 28; titles 0), Halloween 30 (j 14 / b 16; titles 14)

**topic** — Food & drink [culinary, gastronomy, recipe] 3713 (j 1891 / b 1822; titles 444), Weddings & romance [romance, love] 1384 (j 722 / b 662; titles 148), Religion & spirituality [Hindu, Hinduism, Islam] 956 (j 351 / b 605; titles 35), Coffee culture [coffee, barista, roastery] 899 (j 477 / b 422; titles 60), Urban issues [flooding, flood, pollution] 821 (j 584 / b 237; titles 47), Agriculture & food systems [farmers, farming, agriculture] 736 (j 287 / b 449; titles 22), Covid-19 [Covid, Covid-19, pandemic] 438 (j 192 / b 246; titles 62), Pets & animals [dogs, dog, cats] 418 (j 160 / b 258; titles 27), Craft spirits [arak, gin, rum] 393 (j 142 / b 251; titles 41), Spa & beauty [facial, skincare] 190 (j 56 / b 134; titles 8), Weddings [weddings, bridal] 170 (j 98 / b 72; titles 15), History of tourism [tourism history, mass tourism, overtourism] 34 (j 6 / b 28; titles 1)

**venue_kind** — Temple [temples, pura] 553 (j 75 / b 478; titles 49), Coffee shop [café, roastery] 400 (j 207 / b 193; titles 42), Bookshop [bookshop, bookstore, library] 302 (j 214 / b 88; titles 11), Gelato / dessert [gelato, gelateria, ice cream] 272 (j 148 / b 124; titles 4), Palace [palace, water palace] 249 (j 136 / b 113; titles 16), Farm [farm, organic farm, plantation] 238 (j 104 / b 134; titles 18), Zoo / safari [safari, bird park, butterfly park] 178 (j 78 / b 100; titles 40), Surfing [surf] 154 (j 32 / b 122; titles 9), Church / mosque [church, cathedral, mosque] 141 (j 109 / b 32; titles 7), Theatre / concert hall [theater, concert hall, Ciputra Artpreneur] 135 (j 119 / b 16; titles 11), Volcano [Mount Batur, Mount Agung] 121 (j 6 / b 115; titles 3), Waterfall [waterfall, waterfalls] 115 (j 39 / b 76; titles 6), Convention centre [convention centre, convention center, exhibition hall] 112 (j 94 / b 18; titles 5), Stadium [stadium, arena] 81 (j 56 / b 25; titles 1), Winery [winery, vineyard] 76 (j 34 / b 42; titles 1), Rice terrace [rice terrace, rice terraces] 71 (j 8 / b 63; titles 0), Cooking class [cooking classes, culinary class] 69 (j 32 / b 37; titles 1), Trekking / hiking [trek, sunrise trek] 69 (j 24 / b 45; titles 0), Golf course [golf course, golf club, driving range] 68 (j 49 / b 19; titles 1), Billiards / bowling [billiard, pool hall, arcade] 66 (j 28 / b 38; titles 5), Yoga studio [yoga studio, yoga shala, yoga barn] 64 (j 12 / b 52; titles 2), Cycling [bike tour, bicycle] 64 (j 31 / b 33; titles 2), Karaoke [karaoke, KTV] 54 (j 42 / b 12; titles 3), Retreat centre [retreat centre, retreat center, healing centre] 54 (j 18 / b 36; titles 3), School [kindergarten, preschool] 54 (j 47 / b 7; titles 7), Snorkelling / diving [snorkeling, scuba, freediving] 53 (j 26 / b 27; titles 0), ATV / buggy [ATV, quad bike, buggy] 46 (j 13 / b 33; titles 4), Co-working [co-working, coworking] 44 (j 16 / b 28; titles 4), Distillery 39 (j 17 / b 22; titles 0), Waterpark [waterpark, water park] 37 (j 12 / b 25; titles 1)

**vibe** — Tropical [tropical, island, resort-style] 2895 (j 623 / b 2272; titles 148), Authentic [authentic, traditional] 2831 (j 1286 / b 1545; titles 109), Modern [modern, contemporary, minimalist] 2573 (j 1353 / b 1220; titles 114), Exclusive [exclusive, private, members-only] 1996 (j 1060 / b 936; titles 62), Chic [chic, stylish, elegant] 1608 (j 724 / b 884; titles 67), Wholesome [wholesome, healthy, mindful] 887 (j 421 / b 466; titles 37), Glamorous [glamorous, glam, lavish] 791 (j 343 / b 448; titles 45), Quirky [quirky, whimsical, eclectic] 643 (j 261 / b 382; titles 19), Cool [cool, edgy, underground] 522 (j 207 / b 315; titles 9), Rustic [rustic, earthy, raw] 455 (j 210 / b 245; titles 5), Nostalgic [nostalgic, retro, vintage] 242 (j 145 / b 97; titles 5), Family-friendly [family-friendly, kid-friendly] 176 (j 92 / b 84; titles 9)

Counts are lexical: `Java` also matches Java Jazz and coffee, `jungle` matches every jungle-view villa, `women` is not an audience segment until an editor says so. The title count is the stricter signal.

### 4c-bis. Alias suggestions for terms the seed already has (surface forms the seed lacks, ≥ 12 articles)

These are not missing terms — they are words the archive uses for a term that exists. Adding them as `aliases` improves the E2.1 prompt and the reader-filter matching.

**amenities** — Kids club ← kids' club, kid's club, children's club (165), Vegan options ← vegan (152), Outdoor seating ← alfresco, garden seating (70), Ocean view ← cliff-top, cliffside (61), Wi-Fi ← wifi (60), Gym ← fitness center (37), Live music ← resident DJ (16)

**audience** — Tourist ← tourists, visitors, travellers (1926), Family ← families, toddlers, teens (994), Local ← locals, Jakartans, residents (801), Expat ← expats, expatriates, international community (142), Couples ← honeymooners, lovebirds (62), Business traveller ← business travellers, business traveler, corporate travellers (41)

**cuisine** — Indonesian ← Indonesian cuisine, Indonesian food (272), Mexican ← taco, tacos (87), Balinese ← Balinese cuisine, Balinese food (84), Western ← Western food, Western cuisine (36), Middle Eastern ← Arab (31)

**location_bali** — Ubud ← Peliatan (24), Uluwatu ← Balangan (21)

**location_elsewhere** — Komodo & Labuan Bajo ← Komodo (74), Lombok ← Gili (39), Lake Toba ← Toba (19)

**location_jakarta** — BSD ← BSD (37)

**occasion** — Weekend getaway ← escape (647), Date night ← Valentine, romantic dinner (136), Night out ← after-work, after work, girls' night (43), Family day ← family outing, family getaway (26)

**topic** — Fashion ← collection (1084), Sustainability ← sustainable, eco-friendly, zero-waste (1022), Literature ← book, novel (1003), Travel ← itinerary, tourism (809), Community ← foundation, volunteer, fundraising (654), Education ← curriculum, students (568), Culture ← ritual (512), Music ← band (292), Transport ← LRT, toll road, TransJakarta (255), Sports ← tennis, rugby, badminton (213), Health ← well-being (202), Technology ← app, artificial intelligence, fintech (165), Design ← architect (138), Photography ← photographer (117), Property ← apartment, developer (105), Expat life ← living in Bali, KITAS, moving to (104), Business ← entrepreneur, start-up (80), Diplomacy ← consulate (18)

**venue_kind** — Villa ← villas (483), Mall ← shopping mall, plaza (269), Serviced apartment ← serviced apartments, residence (219), Beach club ← beach clubs (55), Pop-up ← pop up (35), Market ← night market (24)

**vibe** — Classic ← timeless, legendary, iconic (1366), Lively ← vibrant (975), Serene ← calm, sanctuary, oasis (765), Luxury ← luxurious, 5-star (689), Hidden gem ← secret, tucked away (306), Cozy ← cosy (276), Scenic ← breathtaking view, panoramic, stunning views (276), Trendy ← hipster, happening (208), Casual ← laidback (117)

### 4d. Seed coverage by facet (all seed terms, mentions per city)


**amenities** — `pool` 1199, `spa` 1087, `garden` 948, `beachfront` 628, `live-music` 408, `kids-club` 393, `gym` 365, `outdoor-seating` 357, `rooftop` 262, `wheelchair-accessible` 262, `ocean-view` 158, `private-dining` 132, `coworking-space` 116, `vegan-options` 113, `parking` 106, `wifi` 87, `halal-certified` 52, `vegetarian-friendly` 17, `pet-friendly` 16, `city-view` 12, `valet` 9

**audience** — `local` 4253, `family` 2937, `business-traveller` 1218, `tourist` 942, `couples` 361, `expat` 103

**cuisine** — `indonesian` 3266, `western` 2689, `balinese` 2205, `european` 1055, `seafood` 785, `japanese` 771, `javanese` 725, `italian` 706, `french` 647, `steakhouse` 641, `american` 627, `chinese` 539, `indian` 532, `mediterranean` 268, `spanish` 213, `thai` 182, `middle-eastern` 163, `korean` 124, `betawi` 119, `padang` 110, `latin-american` 107, `manadonese` 91, `sundanese` 83, `mexican` 81, `asian-fusion` 80, `peranakan` 50, `vietnamese` 50

**location** — `bali` 4683, `jakarta` 3723, `ubud` 1216, `seminyak` 927, `nusa-dua` 630, `kuta` 626, `uluwatu` 602, `yogyakarta` 442, `canggu` 421, `jimbaran` 410, `sanur` 410, `denpasar` 407, `south-jakarta` 400, `bandung` 399, `thamrin` 318, `solo` 293, `east-bali` 287, `surabaya` 282, `legian` 281, `gunawarman` 271, `central-bali` 262, `lombok` 262, `south-bali` 260, `kuningan` 259, `central-jakarta` 258, `sudirman` 232, `kota-tua` 227, `bogor` 221, `senayan` 219, `malang` 209, `scbd` 203, `north-bali` 198, `kerobokan` 196, `menteng` 191, `kemang` 181, `tangerang` 145, `raja-ampat` 141, `komodo` 127, `cikini` 112, `pondok-indah` 111, `nusa-penida` 102, `west-jakarta` 99, `pik` 95, `medan` 93, `semarang` 92, `senopati` 88, `puncak` 83, `gambir` 79, `bekasi` 72, `north-jakarta` 70, `makassar` 66, `manado` 63, `sumba` 59, `greater-jakarta` 57, `bsd` 56, `cipete` 49, `bintaro` 47, `glodok` 44, `amed` 42, `blok-m` 41, `banyuwangi` 41, `kelapa-gading` 40, `gading-serpong` 36, `pererenan` 35, `alam-sutera` 34, `candidasa` 32, `ancol` 31, `toraja` 30, `east-jakarta` 28, `sentul` 28, `sidemen` 28, `lovina` 28, `depok` 27, `tebet` 25, `pasar-baru` 24, `belitung` 18, `bintan` 18, `lake-toba` 16, `cibubur` 13, `puri-indah` 10, `kebon-jeruk` 9, `rawamangun` 2

**occasion** — `celebration` 1641, `brunch` 1249, `sunset` 624, `date-night` 450, `business-trip` 318, `solo` 295, `afternoon-tea` 244, `weekend-getaway` 183, `family-day` 83, `night-out` 57, `group-gathering` 43

**subtype** — `culture` 4324, `lifestyle` 3334, `people` 3129, `restaurant` 2555, `workshop` 2238, `hotel` 1999, `heritage` 1877, `community` 1846, `resort` 1734, `performance` 1682, `business` 1626, `bar` 1460, `education` 1446, `attraction` 1365, `nightclub` 1274, `spa` 1165, `salon` 1010, `market` 933, `artisan` 775, `festival` 711, `sports` 702, `exhibition` 607, `yoga` 585, `adventure` 581, `concert` 520, `tour` 508, `retreat` 489, `conference` 465, `gallery` 464, `museum` 427, `mall` 395, `villa` 388, `fine-dining` 351, `sports-activity` 305, `beach-club` 299, `boutique` 299, `watersports` 287, `cafe` 279, `clinic` 270, `gym` 257, `news` 257, `street-food` 249, `screening` 206, `cocktail-bar` 138, `opinion` 134, `pop-up` 126, `bakery` 111, `serviced-apartment` 99, `pub` 86, `rooftop-bar` 80, `boutique-hotel` 59, `glamping` 38, `food-court` 24, `wine-bar` 9, `city-guide` 3

**topic** — `culture` 3043, `travel` 2895, `business` 2103, `art` 2046, `heritage` 2018, `fashion` 1820, `sustainability` 1662, `community` 1623, `education` 1507, `film` 1446, `design` 1330, `music` 1305, `health` 1170, `sports` 1098, `technology` 839, `transport` 767, `family` 755, `architecture` 656, `property` 631, `literature` 563, `diplomacy` 454, `finance` 428, `photography` 214, `local-brands` 134, `expat-life` 60

**vibe** — `scenic` 1846, `luxury` 1266, `classic` 1231, `artsy` 1161, `serene` 818, `cozy` 721, `party` 694, `casual` 675, `lively` 648, `romantic` 382, `instagrammable` 284, `trendy` 230, `laid-back` 216, `hidden-gem` 45

### 4e. Editors' own tags with no seed coverage (post_tag vocabulary, WP counts ≥ 5)

**jakarta** — recipes 6, Sol Sessions 5

**bali** — dining 46, what's on 24, #BalineseCeremonies 24, food 20, beach 18, dinner 17, Festive Season 16, shopping 15, ocean 14, whats on 10, traditional 9, island 9, Must Watch Movies 9, natural 8, pura 8, relaxation 8, nyepi 7, soapbox 7, wellness 7, wine 7, event 7, New in Town 7, Nyepi 2020 7, sea 6, arak 6, Valentines Day 6, Covid19 6, Jean Couteau 5, Alila 5, coffee 5, ayana 5, healing 5, love 5, foundation 5, store 5, unique 5, product 5

## 5. How much to trust the instruments

The cue instrument (title-weighted keyword scores; `text.py`) measured against categories whose mapping nobody disputes. Read the shares as the instrument's ceiling: when it says 45% of a disputed category is `offer`, compare with what it says for Dining Offers below. Known blind spots: `feature` has no lexical cue (it is the residual format), interviews and travel essays read as first-person, and Balinese culture explainers trip the `do` cues (temple, village, island). Flags in §2 are therefore raised only where the disagreement would change competitor exclusion (a venue type is involved) or the decay class (short / medium / evergreen).

| city | category | n | claimed type | cue agrees | type coverage | claimed format | cue agrees | format coverage |
|---|---|---:|---|---:|---:|---|---:|---:|
| jakarta | Dining Offers | 402 | eat | 83% | 92% | offer | 80% | 85% |
| jakarta | Stay Offers | 261 | stay | 73% | 85% | offer | 70% | 79% |
| jakarta | Reviews | 230 | eat | 79% | 90% | review | 17% | 61% |
| jakarta | Dining News | 388 | eat | 86% | 93% | news | 45% | 63% |
| jakarta | Events | 396 | event | 50% | 81% | event | 60% | 73% |
| jakarta | Bar Guide | 28 | drink | 96% | 96% | - | - | 68% |
| jakarta | Music | 49 | event | 92% | 80% | event | 83% | 71% |
| jakarta | Education | 169 | editorial | 94% | 92% | - | - | 53% |
| jakarta | NOW! People | 99 | editorial | 77% | 91% | people | 57% | 69% |
| jakarta | History & Heritage | 74 | editorial | 40% | 74% | heritage | 80% | 74% |
| jakarta | Opinion | 148 | editorial | 65% | 62% | opinion | 58% | 64% |
| jakarta | World Traveller | 94 | - | - | 74% | city-guide | 25% | 72% |
| bali | Dining Offers | 487 | eat | 82% | 88% | offer | 60% | 70% |
| bali | Stay Offers | 168 | stay | 70% | 87% | offer | 92% | 94% |
| bali | Reviews | 171 | eat | 90% | 96% | review | 26% | 60% |
| bali | Spa and Wellness | 209 | wellness | 98% | 98% | - | - | 53% |
| bali | Hotels & Resorts | 140 | stay | 86% | 94% | - | - | 66% |
| bali | Restaurants and Bars | 360 | eat | 82% | 90% | - | - | 53% |
| bali | Bar Guide | 76 | drink | 82% | 86% | - | - | 33% |
| bali | Opinion | 150 | editorial | 39% | 59% | opinion | 54% | 57% |
| bali | Dining News | 265 | eat | 84% | 97% | news | 62% | 73% |
| bali | Activities | 119 | do | 75% | 88% | - | - | 56% |
| bali | People of Bali | 32 | editorial | 46% | 41% | people | 14% | 44% |
| bali | Bali History | 22 | editorial | 46% | 59% | heritage | 81% | 96% |

Coherence: Jakarta uses real embeddings; Bali uses a TF-IDF/LSA proxy because `now_bali.engine.embeddings` is empty. The proxy sees words, not meaning — two restaurant reviews that share no vocabulary look unrelated to it. Treat Bali's `mixed` verdicts as prompts to look at the titles, not as findings.

## 6. Cross-city consistency — categories both sites share (resolved priors)

A **conflict** is two fixed values that differ — a real inconsistency to resolve. **partial** means one city fixes the facet and the other leaves it per article because its articles are more mixed; that is deliberate and evidence-based, not drift.

| category | jakarta (n) | jakarta type + format | bali (n) | bali type + format | verdict |
|---|---|---|---|---|---|
| bar guide | Bar Guide (28) | drink + per-article | Bar Guide (76) | drink + per-article | same |
| community | Community (150) | editorial + per-article | Community (152) | editorial + per-article | same |
| culture | Culture (67) | editorial + feature | Culture (110) | editorial + feature | same |
| dining news | Dining News (388) | eat + news | Dining News (265) | eat + news | same |
| dining offers | Dining Offers (402) | eat + offer | Dining Offers (487) | eat + per-article | partial — format: bali leaves it per article (evidence-based), the other fixes `offer` |
| experience offers | Experience Offers (207) | per-article + offer | Experience Offers (128) | per-article + offer | same |
| features | Features (20) | per-article + feature | Features (3) | editorial + feature | partial — type: jakarta leaves it per article (evidence-based), the other fixes `editorial` |
| lifestyle | Lifestyle (13) | per-article + per-article | Lifestyle (243) | per-article + per-article | same |
| news | News (551) | per-article + news | News (1067) | per-article + news | same |
| offers | Offers (55) | stay + offer | Offers (1) | stay + offer | same |
| opinion | Opinion (148) | editorial + opinion | Opinion (150) | editorial + opinion | same |
| restaurant guide | Restaurant Guides (17) | eat + per-article | Restaurant Guide (52) | eat + per-article | same |
| reviews | Reviews (230) | per-article + review | Reviews (171) | eat + review | partial — type: jakarta leaves it per article (evidence-based), the other fixes `eat` |
| shopping | Shopping (108) | shop + news | Shopping (174) | shop + per-article | partial — format: bali leaves it per article (evidence-based), the other fixes `news` |
| stay offers | Stay Offers (261) | stay + offer | Stay Offers (168) | stay + offer | same |
| travel | Travel (21) | editorial + city-guide | Travel (38) | per-article + per-article | partial — type: bali leaves it per article (evidence-based), the other fixes `editorial`; format: bali leaves it per article (evidence-based), the other fixes `city-guide` |
| uncategorized | Uncategorized (83) | per-article + per-article | Uncategorized (71) | per-article + per-article | same |

## 7. Classification rules for E2.1 — what the policy decisions produce

Machine-readable twin: `rules` in `taxonomy-review.json` (decided by Hansel on 2026-09-10). Together with `categories[].proposal` this is the whole prior E2.1 needs.

- **Prior resolution (D10)** — order: yoast_primary → deepest_child → parent_container. The WP category is a prior, not the answer. Take the prior from the Yoast primary category when set; otherwise from the deepest (most specific) category the post carries; a parent-only container (Lifestyle, Culture, Explore Bali, Offers, Dining, Features, ...) is a weak prior for posts that carry nothing else. Explore Bali + Opinion -> Opinion wins (D18).
- **Guide vs listing (D01)** — `listing` when the title carries a period stamp (a year in the title; [Updated]; a seasonal marker (Ramadan, Christmas, Nyepi, ...)) or the piece is a roundup: 540-day half-life, `series_key` = roundup:<title slug with the period stamp removed>, rails: one member per series_key -- the current edition only (series dedup, Section 8.A). Otherwise `guide` (timeless how-to or area piece with no period stamp), evergreen. venue roundups filed under 'City Guides' are typed by the roundup's venue type per article, never format city-guide
- **Legacy expiry (D02)** — offer: the validity end date extracted from the text when a phrase like 'valid until' / 'available through' exists; otherwise published_at + 90 days. event: the event end date extracted from the text when present; otherwise published_at + 30 days. Expired: stays searchable; excluded from every rail by the Section 8.A hard filter.
- **Print issues (D07)** — facets from the category: none; `series_key` issue:<category slug>; format prior `feature`; from content.
- **Columns (D08)** — `series_key` column:<category slug>; migrated: all; rails exclusion: none for every column except the two named in excluded_from_rails (Hansel, follow-up #1, 2026-09-10); location: site home when the text names no place.
- **Migration scope (D09, D08)** — excluded categories: none; Uncategorized: no prior; classify best-effort; non-articles: not excluded by the taxonomy; the five page-like titles are listed in decisions[D09].resolution.conflicts.
- **Confidence gate** — auto-apply at ≥ 0.85; below: E2.8 review queue -- never written as fact (PROGRESS.md E2.1 spec ('< 0.85 -> review queue'); applies to every category, including Uncategorized (D09)).
- **Mixed categories (`mixed-categories`)** — Classify per article; no fixed category-wide type where the evidence shows a venue-type mix. Protects competitor exclusion. Rule: The flagged facet becomes per-article. The E2.0 value stays the prior unless the cue instrument gives it <= 10% support against >= 50% for the alternate, in which case the alternate becomes the prior (Chaine Des Rottiseurs: event 0% vs review 50% -> prior review). Type flags where the instrument is fooled by vocabulary (Cook and Mix: recipes read as `eat`) still go per-article, with an explicit classifier note, because the E2.1 confidence gate catches a wrong `eat` and a false exclusion is the cheap error.
- **Location** — required; site-home fallback {'jakarta': 'jakarta', 'bali': 'bali'}; Jakarta 'Bali Updates' (111) carry location bali -- the Section 3.5 syndication set for now_bali.

### `international` (D06) — editorial-only, and how the engine encodes it

- Term `location/international`; children: one node per destination with >= 20 corpus mentions (22 -- see vocabulary-delta.json); a child inherits the root's attribute.
- Attribute: `geo_scope` = `abroad`, inherited by descendants (default elsewhere: `home`).
- Eligible: search, row3_similar (related reading), reader location filter. Excluded: row1_complementary, row2_nearby, itinerary builder.
- Classifier rule: `international` (or a child) only when the piece is about a destination outside Indonesia; a Jakarta piece that mentions Singapore Airlines is still `jakarta`. An article about two places (Singapore vs Jakarta) carries both terms and is geo-anchored by the Indonesian one.
- Subject rule: an article whose location terms are ALL under `international` hosts no Row 1 and no Row 2: both rails are returned as not applicable (rung `subject_abroad`, empty items, no fallback ladder), Row 3 unchanged. Answered by Hansel (follow-up #4, 2026-09-10, no longer inferred): a Paris feature has no local subject place, so Row 1 (complementary places) has exactly the same problem as Row 2 (nearby) -- both are suppressed the same way.
- Candidate rule: any entity (place, event, article) whose location resolves to geo_scope=abroad is excluded from every geo-anchored pool: Row 1 and Row 2 places and itinerary slots. Row 3 and search never apply it.
- Where: a term attribute on location/international (`attrs.geo_scope = 'abroad'`), inherited by descendants -- persisted in engine.terms.attrs jsonb (the taxonomy README's proposed DDL #1; additive platform-DB migration)
- Enforced by: the geo-anchored consumers, in one place each: `now_filters.hard` gains an `abroad_terms` parameter (the set of location term ids/slugs under `international`, loaded once from the platform DB like now_rails.relations_cache loads type_relations) applied as `area_term::text != ALL(:abroad_area_slugs)` for places and `NOT EXISTS (SELECT 1 FROM engine.entity_terms et WHERE et.entity_id = a.id::text AND et.term_id = ANY(:abroad_term_ids))` for articles; Row 1, Row 2 and the itinerary callers all pass it (Row 1 added by follow-up #4 -- it was previously omitted because the answer had only been inferred, not stated). `now_rails.subject` fetches the subject article's location term ids from engine.entity_terms; all-abroad -> Row 1 and Row 2 both short-circuit to `subject_abroad`.
- Why not a facet flag: a per-article flag duplicates information derivable from location and must be kept in sync by the classifier; the attribute lives once, on the term, and every future child (Japan, Europe, ...) inherits it.
- Why not rails only code: three consumers now (Row 1 and Row 2 today, the E5 itinerary builder later) and a growing node set; a hardcoded slug list in each rail drifts. The rails still own the enforcement -- the attribute only tells them which nodes are abroad.
- Prerequisite: `public.articles` has no location column; article location lives only in engine.entity_terms (empty today). E2.1 must write the location facet there (or E2.1's ticket adds a denormalised `articles.primary_location`); without one of the two, the subject rule cannot be evaluated for either rail (PROGRESS.md F82).

## Appendix A. Resolved mappings — every category with articles, changed first

`proposal` in the JSON is the resolved prior E2.1 reads; `e20_proposal` is what the evidence was gathered against. *per article* means the classifier decides, with the prior shown in brackets where one exists.

| category | n | resolved type/subtype | format | location | other | conf. | basis | changed vs E2.0 | status |
|---|---:|---|---|---|---|---|---|---|---|
| Travel | 38 | *per article* (prior `editorial`)/*per article* (prior `city-guide`) | *per article* (prior `city-guide`) | *per article* (prior `other`) | topic: travel | medium | mixed-categories, D06, D14 | per_article: ['location', 'format'] → ['type', 'subtype', 'format', 'location'] | resolved — changed (mixed-categories, D06, D14) |
| Chaine Des Rottiseurs | 24 | `eat`/`fine-dining` | *per article* (prior `review`) | `bali` | series_key: `column:chaine-des-rotisseurs` | medium | mixed-categories, D08, D02 | format: event → review; per_article: [] → ['format'] | resolved — changed (mixed-categories, D08, D02) |
| Stranger In Paradise | 21 | `editorial`/`opinion` | *per article* (prior `opinion`) | `bali` | series_key: `column:stranger-in-paradise` | medium | mixed-categories, D24, D03, D08 | per_article: [] → ['format'] | resolved — changed (mixed-categories, D24, D03, D08) |
| Weddings | 17 | *per article*/*per article* | *per article* (prior `listing`) | `bali` | occasion: wedding | medium | D22, D01 | facets: occasion ['celebration'] → ['wedding'] | resolved — changed (D22, D01) |
| Cook and Mix | 16 | *per article* (prior `editorial`)/*per article* (prior `lifestyle`) | `feature` | `bali` | series_key: `column:cook-and-mix` | medium | mixed-categories, D08, D05 | per_article: [] → ['type', 'subtype'] | resolved — changed (mixed-categories, D08, D05) |
| Must Watch Movies | 13 | `editorial`/`lifestyle` | `feature` | `bali` | series_key: `column:must-watch-movies` | medium | D08, D05 | location: None → bali | resolved — changed (D08, D05) |
| Music to the Ears | 11 | `editorial`/`lifestyle` | `feature` | `bali` | series_key: `column:music-to-the-ears` | medium | D08, D05 | location: None → bali | resolved — changed (D08, D05) |
| Health & Wellness | 7 | `editorial`/`lifestyle` | `feature` | `bali` | topic: health; series_key: `column:health-wellness` | medium | D08, D05 | location: None → bali | resolved — changed (D08, D05) |
| Home Life | 1 | `editorial`/`lifestyle` | `feature` | `bali` | series_key: `column:home-life` | medium | D08, D27 | location: None → bali | resolved — changed (D08, D27) |
| News | 1067 | *per article*/*per article* | `news` | `bali` | - | high | D21 | - | resolved (D21) |
| Dining Offers | 487 | `eat`/`restaurant` | *per article* (prior `offer`) | `bali` | - | medium | D02, D20 | - | resolved (D02, D20) |
| Lifestyle | 243 | *per article*/*per article* | *per article* | `bali` | - | low | D23, D05, D13 | - | resolved (D23, D05, D13) |
| Community | 152 | `editorial`/`news` | *per article* (prior `feature`) | `bali` | topic: community | medium | D19 | - | resolved (D19) |
| Art In Bali | 136 | *per article*/*per article* | *per article* | `bali` | topic: art | medium | D25, D04, D12 | - | resolved (D25, D04, D12) |
| Experience Offers | 128 | *per article* (prior `stay`)/*per article* (prior `hotel`) | `offer` | `bali` | - | medium | D17, D02 | - | resolved (D17, D02) |
| Explore Bali | 117 | *per article*/*per article* | *per article* | `bali` | - | low | D18, D10 | - | resolved (D18, D10) |
| Uncategorized | 71 | *per article*/*per article* | *per article* | `bali` | - | low | D09 | - | resolved (D09) |
| NOW! Bali Podcast | 27 | `editorial`/*per article* (prior `culture`) | `feature` | `bali` | series_key: `column:podcast` | medium | D08 | - | resolved (D08) |
| Video | 11 | *per article*/*per article* | *per article* | `bali` | series_key: `column:video` | low | D08 | - | resolved (D08) |
| Restaurants and Bars | 360 | `eat`/`restaurant` | *per article* | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Dining News | 265 | `eat`/`restaurant` | `news` | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Spa and Wellness | 209 | `wellness`/`spa` | *per article* | `bali` | - | high | D13 | - | resolved (D13) |
| Shopping | 174 | `shop`/`boutique` | *per article* (prior `news`) | `bali` | - | medium | as-proposed | - | resolved (as proposed) |
| Reviews | 171 | `eat`/`restaurant` | `review` | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Stay Offers | 168 | `stay`/*per article* (prior `hotel`) | `offer` | `bali` | - | high | D02 | - | resolved (D02) |
| Opinion | 150 | `editorial`/`opinion` | `opinion` | `bali` | - | high | D03 | - | resolved (D03) |
| Hotels & Resorts | 140 | `stay`/*per article* (prior `hotel`) | *per article* | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Activities | 119 | `do`/*per article* | *per article* (prior `guide`) | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Culture | 110 | `editorial`/`culture` | `feature` | `bali` | topic: culture | medium | D04 | - | resolved (D04) |
| Cultural Observer | 110 | `editorial`/`culture` | `feature` | `bali` | topic: culture; series_key: `column:cultural-observer` | high | D04, D24 | - | resolved (D04, D24) |
| Bar Guide | 76 | `drink`/*per article* (prior `bar`) | *per article* | `bali` | - | high | D01 | - | resolved (D01) |
| Dance and Music | 75 | `editorial`/`culture` | `feature` | `bali` | topic: culture, music | high | D04, D24 | - | resolved (D04, D24) |
| Cultural Sites | 71 | `do`/`attraction` | `guide` | `bali` | topic: heritage, culture | high | as-proposed | - | resolved (as proposed) |
| Destinations | 53 | `editorial`/`city-guide` | `city-guide` | *per article* (prior `bali`) | topic: travel | high | as-proposed | - | resolved (as proposed) |
| Restaurant Guide | 52 | `eat`/`restaurant` | *per article* (prior `guide`) | `bali` | - | high | D01 | - | resolved (D01) |
| Bali with Kids | 47 | *per article* (prior `do`)/*per article* | *per article* (prior `guide`) | `bali` | audience: family; topic: family | high | as-proposed | - | resolved (as proposed) |
| Ceremonies & Festivals | 45 | `editorial`/`culture` | `feature` | `bali` | topic: culture | high | D04, D24 | - | resolved (D04, D24) |
| Nature and Outdoors | 33 | `do`/*per article* (prior `adventure`) | `guide` | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| People of Bali | 32 | `editorial`/`people` | `people` | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Myths and Legends | 30 | `editorial`/`heritage` | `heritage` | `bali` | topic: heritage, culture | high | D24 | - | resolved (D24) |
| Everyday Bali | 30 | `editorial`/`culture` | `feature` | `bali` | topic: culture | high | D04, D24 | - | resolved (D04, D24) |
| Made in Bali | 24 | *per article* (prior `shop`)/`artisan` | `feature` | `bali` | topic: local-brands | medium | as-proposed | - | resolved (as proposed) |
| Bali History | 22 | `editorial`/`heritage` | `heritage` | `bali` | topic: heritage | high | D24 | - | resolved (D24) |
| Parks and Attractions | 17 | `do`/`attraction` | *per article* (prior `guide`) | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Winocracy | 9 | `editorial`/`opinion` | `opinion` | `bali` | topic: food-drink; series_key: `column:winocracy` | high | D03, D08 | - | resolved (D03, D08) |
| Behind the Bar | 7 | `drink`/`cocktail-bar` | *per article* (prior `people`) | `bali` | series_key: `column:behind-the-bar` | high | D08 | - | resolved (D08) |
| Features | 3 | `editorial`/*per article* | `feature` | `bali` | - | medium | D27 | - | resolved (D27) |
| Offers | 1 | `stay`/*per article* (prior `hotel`) | `offer` | `bali` | - | high | D27, D02 | - | resolved (D27, D02) |

## Appendix B. Per-category evidence and resolution — changed first, then by size

### Travel — resolved — changed (mixed-categories, D06, D14)

*38 published · 2015–2026 · parent: Lifestyle · Yoast primary on 30 · slug `travel` · term 943*

> Editor's description: Discover a world of colour, culture and life through the Indonesian archipelago through our Archipelago Diaries travel stories, taking you to destinations beyond Bali, but just as exotic.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* (prior `editorial`) · subtype *per article* (prior `city-guide`) · format *per article* (prior `city-guide`) · location *per article* (prior `other`) · topic: travel · confidence **medium** · decisions D06, D14

**E2.0 proposal (before the answers).** type `editorial` · subtype `city-guide` · format *per article* (prior `city-guide`) · location *per article* (prior `other`) · topic: travel · status was `flagged-by-evidence`.

**Resolution.** basis mixed-categories, D06, D14; changed — editorial/city-guide stays the prior; the evidence split (do/stay clusters) made type per article.; addressed flags: 1.

**Reasoning.** Archipelago Diaries: Lombok, Belitung, Sumba, Flores. Location under other/* per article; hotel promos filed here need the classifier.

**Alternates for the classifier.** do/* + guide for island and destination pieces (clusters 42% + 32%); stay/resort + review\|offer for hotel pieces (cluster 26%); location `international` when the destination is abroad (D06); other/* for the archipelago (D14 adds the region nodes); stay/resort + review\|offer for hotel pieces; location international if abroad

**Flags (evidence against the E2.0 proposal).** clusters split the category: k=3 split (silhouette 0.23, smallest cluster 26%) whose clusters read as different venue types (do, stay) while the proposal fixes type=editorial; 18% of members sit closer to a category of another type

**Representative titles (spread across the date range).**
- 2015-08-03 · Taking it Easy in Gili Trawangan
- 2018-03-26 · Lombok: An Escape Across the Wallace Line
- 2018-08-17 · The Gems of Riau
- 2018-12-24 · Heritage, Culture and History in Kotagede
- 2024-05-28 · Exotic Adventures Around the Cape of Flowers
- 2024-08-07 · A Leisurely Seaside Affair Awaits at Bayside Restaurant & Bar
- 2026-05-06 · Cocana Resort is Gili Trawangan's Chic Sanctuary
- 2026-05-21 · Exploring Labuan Bajo on Land and Sea: An Island Hopping Itinerary

**Cue instrument.** type: do 59%, stay 35%, editorial 3%, eat 3% (coverage 90%); format: city-guide 56%, offer 13%, heritage 13%, news 13% (coverage 60%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** lombok 17, komodo 11, bali 10, sumba 3, belitung 1, bintan 1; 63% name only a place outside bali.

**Co-filed with.** Explore Bali 1; 37 carry this category alone.

**Coherence** (incoherent, against the E2.0 proposal). k=3 split (silhouette 0.23, smallest cluster 26%) whose clusters read as different venue types (do, stay) while the proposal fixes type=editorial; 18% of members sit closer to a category of another type. Cohesion 0.628 (baseline 0.428), leakage 29% → Hotels & Resorts (3), Parks and Attractions (1), Nature and Outdoors (1), Uncategorized (1); best split k=3 silhouette 0.23.
- cluster 1: 16 (42%) `do`/`city-guide` — Rediscovering Sumba; Untouched: Discovering West Sumba; Lombok: An Escape Across the Wallace Line
- cluster 2: 12 (32%) `do`/`city-guide` — Exploring Labuan Bajo on Land and Sea: An Island Hopping Itinerary; Exotic Adventures Around the Cape of Flowers; Bijoux Bajo: Exploring Flores in Style
- cluster 3: 10 (26%) `stay`/`offer` — Discover Paradise at Your Doorstep at Amber Lombok Beach Resort; Experience a Tranquil Seaside Escape at Amber Lombok Beach Resort; Cocana Resort is Gili Trawangan's Chic Sanctuary

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `city-guide` · format `city-guide` · location `other` · agrees: True · split: True → destination-guides, hotel-reviews, travel-practical · confidence medium. Mostly destination guides beyond Bali, but titles include hotel reviews and practical travel news, so format is mixed and a split would improve granularity.

### Chaine Des Rottiseurs — resolved — changed (mixed-categories, D08, D02)

*24 published · 2015–2018 · parent: Archives · Yoast primary on 13 · slug `chaine-des-rottiseurs` · term 42*

> Editor's description: Chaîne de Rôtisseurs: an International Association of Gastronomy now established in over 75 countries bringing together enthusiasts.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `fine-dining` · format *per article* (prior `review`) · location `bali` · series_key: `column:chaine-des-rotisseurs` · confidence **medium** · decisions D08, D02

**E2.0 proposal (before the answers).** type `eat` · subtype `fine-dining` · format `event` · location `bali` · series_key: `column:chaine-des-rotisseurs` · status was `decision-needed`.

**Resolution.** basis mixed-categories, D08, D02; changed — Retrospective reports on society dinners (2015-2018): the cue instrument reads 50% review, 0% event, so the prior flips to review (540-day decay; all long expired either way). Type eat/fine-dining stays.; addressed flags: 1.

**Reasoning.** Reports on the gastronomic society's dinners (2015-2018) -- dated, expired events at fine-dining venues.

**Alternates for the classifier.** event + event only for an announced upcoming dinner (D02 expiry applies); editorial/people + people for member profiles; format review; event/community

**Flags (evidence against the E2.0 proposal).** cue instrument disagrees on format: proposal fixes `event` (short decay) but 50% of signal-bearing articles read as `review` (medium decay; only 0% as `event`)

**Representative titles (spread across the date range).**
- 2015-02-27 · A Grand Induction At Sofitel Bali
- 2015-06-03 · Chaîne Luncheon at Locavore : Felicitations or Lamentations?
- 2015-10-02 · Sunday Brunch À LA CHAÎNE
- 2016-03-25 · An Evening on the Wild Side
- 2016-06-23 · World Chaine Day
- 2016-09-10 · Impeccable Chaîne des Rotisseurs Chapitrre at Alila Seminyak
- 2017-04-04 · Chaine Des Rotisseurs: Opia Bali's Asian Persuasions
- 2018-08-16 · A Chaine Comeback

**Cue instrument.** type: eat 87%, stay 4%, do 4%, drink 4% (coverage 96%); format: review 50%, news 25%, listing 8%, city-guide 8% (coverage 50%); period-stamped titles 8%; roundups 0%; median first-person density 2.3/1000 words.

**Places named in title/lead.** bali 17, legian 5, ubud 4, seminyak 3, sanur 1; 0% name only a place outside bali.

**Co-filed with.** Restaurants and Bars 3; 21 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.44; leakage 4% (cross-type 4%). Cohesion 0.798 (baseline 0.44), leakage 4% → Activities (1); best split k=3 silhouette 0.261.
- cluster 1: 20 (83%) `eat`/`review` — Exquisite Affair at KAYUPUTI; Impeccable Chaîne des Rotisseurs Chapitrre at Alila Seminyak; A Chaine Comeback
- cluster 2: 3 (12%) `eat`/`city-guide` — Jeunesse de La Chaine: Awakening Culinary Appreciation; Association Mondiale De La Gastronomie; Chaine des Rotisseurs : BALI OUTRÉ-MER
- cluster 3: 1 (4%) `eat`/`?` — Koko Bambu: The Mason Mansion of Chocolate

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `fine-dining` · format `event` · location `bali` · agrees: True · split: False · confidence high. All titles describe Chaîne des Rôtisseurs dining events in Bali, consistently fine-dining gatherings of a gastronomic association.

### Stranger In Paradise — resolved — changed (mixed-categories, D24, D03, D08)

*21 published · 2015–2019 · parent: Archives · Yoast primary on 10 · slug `stranger-in-paradise` · term 19*

> Editor's description: Stranger in Paradise: Discover the best time and places to visit Bali. Get information on the best things to do and the best places to stay.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `opinion` · format *per article* (prior `opinion`) · location `bali` · series_key: `column:stranger-in-paradise` · confidence **medium** · decisions D03, D08, D24

**E2.0 proposal (before the answers).** type `editorial` · subtype `opinion` · format `opinion` · location `bali` · series_key: `column:stranger-in-paradise` · status was `flagged-by-evidence`.

**Resolution.** basis mixed-categories, D24, D03, D08; changed — Prior stays editorial/opinion + opinion (LLM: high-confidence opinion; first-person column). D24's text listed this column under heritage -- see D24.conflicts.; addressed flags: 1.

**Reasoning.** Made Wijaya's satirical society column (2015-2019): opinion with a heritage flavour.

**Alternates for the classifier.** heritage (evergreen) for the historical and cultural essays -- cluster 43%; editorial/heritage + heritage; editorial/culture + feature

**Flags (evidence against the E2.0 proposal).** clusters split the category: k=2 split (silhouette 0.13, smallest cluster 43%) whose clusters read as formats with different decay (evergreen, medium) while the proposal fixes format=opinion

**Representative titles (spread across the date range).**
- 2015-02-04 · New Age New Bali
- 2015-05-15 · Looking Lovingly at Penjor
- 2015-10-10 · Bali Tourism at the Crossroads?
- 2016-01-14 · Peliatan Style
- 2016-03-03 · Ubud's First Family of Royal Indokrupuk
- 2016-06-09 · Water Palaces in the Age of Rajas
- 2016-08-31 · A Grand Farewell for a Great High Priest
- 2019-01-15 · Bali's Power Pedanda : The Rise of Bali's High Priests

**Cue instrument.** type: editorial 50%, do 17%, wellness 8%, event 8% (coverage 57%); format: review 33%, heritage 33%, opinion 25%, feature 8% (coverage 57%); period-stamped titles 0%; roundups 0%; median first-person density 18.3/1000 words.

**Places named in title/lead.** bali 13, nusa-dua 2, denpasar 2, ubud 2, kuta 1, surabaya 1; 5% name only a place outside bali.

**Co-filed with.** Explore Bali 8, Culture 2; 12 carry this category alone.

**Coherence** (incoherent, against the E2.0 proposal). k=2 split (silhouette 0.13, smallest cluster 43%) whose clusters read as formats with different decay (evergreen, medium) while the proposal fixes format=opinion. Cohesion 0.714 (baseline 0.444), leakage 19% → Ceremonies & Festivals (1), Opinion (1), News (1), Bali History (1); best split k=2 silhouette 0.135.
- cluster 1: 12 (57%) `editorial`/`review` — Clouds Gathering Over The Rainbow?; New Age New Bali; Beauty Pageants in Paradise
- cluster 2: 9 (43%) `editorial`/`heritage` — The Brahmans are Coming; Tale of Two Kingdoms; Bali's Power Pedanda : The Rise of Bali's High Priests

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `opinion` · format `opinion` · location `bali` · agrees: True · split: False · confidence high. Reflective essays on Balinese culture, history, people, and trends; clearly an opinion column with Bali-wide scope.

### Weddings — resolved — changed (D22, D01)

*17 published · 2016–2026 · parent: Lifestyle · Yoast primary on 4 · slug `weddings` · term 2578*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* (prior `listing`) · location `bali` · occasion: wedding · confidence **medium** · decisions D22, D01

**E2.0 proposal (before the answers).** type *per article* · subtype *per article* · format *per article* (prior `listing`) · location `bali` · occasion: celebration · status was `decision-needed`.

**Resolution.** basis D22, D01; changed — occasion `wedding` replaces `celebration` once the term is seeded (vocabulary-delta). Type/format per article; period-stamped roundups -> listing (D01)..

**Reasoning.** Venue and service roundups for weddings/proposals; venues are villas/resorts, services are shops.

**Alternates for the classifier.** stay/villa\|resort + listing; shop/boutique + listing; format guide

**Representative titles (spread across the date range).**
- 2016-02-01 · Beautiful Balinese Style Weddings
- 2016-02-11 · Best Bachelor Party Ideas in Bali
- 2018-02-02 · Best Wedding Chapels in Bali : Truly Exquisite Matrimonial Destinations
- 2018-06-07 · A Touch of Japan: Tirtha Bridal's Newest Wedding Experience
- 2019-03-12 · Best Bali Wedding Services : Planners, Catering, Make Up & More
- 2022-01-01 · The Ultimate Bali Proposal
- 2025-06-26 · Beachside Vows: Plan Your Dream Wedding at The Westin Resort Nusa Dua, Bali
- 2026-07-10 · Best Wedding Venues in Bali: Tying the Knot in Paradise

**Cue instrument.** type: stay 40%, do 27%, eat 27%, drink 7% (coverage 88%); format: city-guide 40%, offer 30%, news 10%, guide 10% (coverage 59%); period-stamped titles 0%; roundups 12%; median first-person density 1.0/1000 words.

**Places named in title/lead.** bali 16, uluwatu 3, nusa-dua 3, east-bali 1, ubud 1; 0% name only a place outside bali.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=3 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.689 (baseline 0.454), leakage 12% → Bar Guide (1), Travel (1); best split k=3 silhouette 0.262.
- cluster 1: 7 (41%) `stay`/`offer` — The Westin Resort Nusa Dua, Bali Unveils Heritage Beach Garden Wedding; Beachside Vows: Plan Your Dream Wedding at The Westin Resort Nusa Dua,; Under the Tree of Love: Weddings at Awarta Nusa Dua
- cluster 2: 6 (35%) `eat`/`offer` — Best Wedding Chapels in Bali : Truly Exquisite Matrimonial Destination; The Best Wedding Chapels in Bali : An Exquisite Matrimony; Tirtha Uluwatu: One of Bali's Most Stunning Wedding Venues
- cluster 3: 4 (24%) `do`/`city-guide` — The Ultimate Bali Proposal; Popping the Question: Unique Proposals in Bali; Fly Me To The Honeymoon

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: False · split: True → wedding-venues, wedding-services, proposal-honeymoon · confidence medium. Titles mix venue reviews, service guides, proposal ideas, and honeymoon features, so format and type vary per-article; location is consistently Bali.

### Cook and Mix — resolved — changed (mixed-categories, D08, D05)

*16 published · 2016–2020 · parent: Home Life · Yoast primary on 9 · slug `recipes` · term 2384*

> Editor's description: Welcome to ‘Cook & Mix’, a new column from NOW! Bali’s Home Life series. In this column we share cooking recipes to try and cocktail mixes to shake up!

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* (prior `editorial`) · subtype *per article* (prior `lifestyle`) · format `feature` · location `bali` · series_key: `column:cook-and-mix` · confidence **medium** · decisions D08, D05

**E2.0 proposal (before the answers).** type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · series_key: `column:cook-and-mix` · status was `decision-needed`.

**Resolution.** basis mixed-categories, D08, D05; changed — The 93% `eat` cue is food vocabulary, not a venue subject (LLM agrees: editorial/lifestyle, high confidence). Per article under the mixed-categories answer, with the classifier note above.; addressed flags: 1.

**Reasoning.** Recipes and cocktail mixes (2016, 2020 lockdown). No §4 format for recipes -- E1.4 chose editorial/lifestyle + feature for Jakarta's Rice Table recipes; same here.

**Alternates for the classifier.** eat/restaurant ONLY when a restaurant is the subject -- a recipe or cocktail how-to is editorial/lifestyle even when a dish, chef or venue is named

**Flags (evidence against the E2.0 proposal).** cue instrument disagrees on type: proposal fixes `editorial` but 93% of signal-bearing articles read as `eat` (only 0% as `editorial`) -- this changes competitor exclusion

**Representative titles (spread across the date range).**
- 2016-09-14 · Cooking with Chef Mandif Warokka: Mie Cakalang
- 2016-09-16 · Petty Elliott's Udang Woku Blanga
- 2020-04-03 · Pepes Ikan: Grilled Spiced Red Snapper in Banana Leaf
- 2020-04-21 · Learn to Make Sambal : Indonesia’s Favourite Chilli Relish
- 2020-05-11 · Cooking Caramelised Onion, Pear & Gorgonzola Tart with TWO Islands Wine
- 2020-06-01 · Recipe for Twice-Cooked Chicken Drumstick with Pandan and Curry Leaves
- 2020-06-15 · Soto Betawi: A Classic Dish from The Capital
- 2020-08-11 · The Quarantini : A Cocktail for Covid Times

**Cue instrument.** type: eat 93%, drink 7% (coverage 88%); format: review 40%, opinion 20%, people 20%, heritage 20% (coverage 31%); period-stamped titles 0%; roundups 0%; median first-person density 5.4/1000 words.

**Places named in title/lead.** jakarta 3, ubud 1, lake-toba 1, manado 1, bali 1; 31% name only a place outside bali.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.89 vs baseline 0.46; leakage 6% (cross-type 0%). Cohesion 0.891 (baseline 0.458), leakage 6% → Video (1); best split k=2 silhouette 0.663.
- cluster 1: 15 (94%) `eat`/`review` — Sundanese Roast Chicken with A Twist; Recipe for Ketoprak: Rice Noodles and Vegetable Salad with Peanut Sauc; Pepes Ikan: Grilled Spiced Red Snapper in Banana Leaf
- cluster 2: 1 (6%) `drink`/`?` — The Quarantini : A Cocktail for Covid Times

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Consistent recipe-and-cocktail column sharing cooking instructions; editorial lifestyle features tied to NOW! Bali with no location variation per article.

### Must Watch Movies — resolved — changed (D08, D05)

*13 published · 2020–2020 · parent: Home Life · Yoast primary on 11 · slug `movies` · term 2388*

> Editor's description: Must Watch Movies, a column from NOW! Bali’s Home Life series. Our column about movie list of the all-time best movies we consider must-watch films.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · series_key: `column:must-watch-movies` · confidence **medium** · decisions D08, D05

**E2.0 proposal (before the answers).** type `editorial` · subtype `lifestyle` · format `feature` · location *per article* · series_key: `column:must-watch-movies` · status was `decision-needed`.

**Resolution.** basis D08, D05; changed — Migrated, searchable, series_key column:must-watch-movies. Rails-excluded (follow-up #1, 2026-09-10): see rules.columns.excluded_from_rails -- series-level rule, not the quality floor. No place in the text -> site-home location fallback..

**Reasoning.** Lockdown movie lists with no Bali subject at all; location none. Rails should probably never surface these.

**Alternates for the classifier.** exclude from migration

**Representative titles (spread across the date range).**
- 2020-04-03 · Add Colour to Life at Home: Wes Anderson Masterpieces You Must Watch
- 2020-04-17 · Co-Quarantine Cuddles: Best Tales of Love and Romance in Movies
- 2020-04-27 · Tomorrowland: Post-Apocalyptic Movies That Remind Us, We’re Actually Okay
- 2020-05-11 · Seeing is Believing: Movies That Will Bend Your Mind
- 2020-06-01 · Whodunit: Greatest Murder Mysteries in Cinematic History
- 2020-06-16 · Back to the Movies: Upcoming Films to Look Forward To
- 2020-07-07 · Mood Boosters: Ultimate Feel-good Movies That Will Lift Your Spirits
- 2020-08-11 · Sing-A-Long: Best Musical Films of the 21st Century

**Cue instrument.** type: editorial 43%, event 29%, wellness 14%, eat 14% (coverage 54%); format: heritage 43%, listing 29%, news 14%, event 14% (coverage 54%); period-stamped titles 0%; roundups 0%; median first-person density 3.1/1000 words.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.94 vs baseline 0.47; leakage 0% (cross-type 0%). Cohesion 0.94 (baseline 0.469), leakage 0%; best split k=3 silhouette 0.362.
- cluster 1: 11 (85%) `editorial`/`heritage` — Seeing is Believing: Movies That Will Bend Your Mind; From the Pages to the Screen: Best Film Adaptations Based on Books; Tomorrowland: Post-Apocalyptic Movies That Remind Us, We’re Actually O
- cluster 2: 1 (8%) `?`/`news` — Best Netflix Gems to Binge-watch During Quarantine
- cluster 3: 1 (8%) `wellness`/`?` — Add Colour to Life at Home: Wes Anderson Masterpieces You Must Watch

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `lifestyle` · format `feature` · location `per-article` · agrees: True · split: False · confidence high. Curated movie recommendation lists are editorial lifestyle features with no location tie to Bali; all titles are thematic film lists, consistent and uniform.

### Music to the Ears — resolved — changed (D08, D05)

*11 published · 2020–2020 · parent: Home Life · Yoast primary on 8 · slug `music` · term 2385*

> Editor's description: Music to the Ears : Songs and sounds are often overlooked in a movie, when in fact these are key components to the concoction.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · series_key: `column:music-to-the-ears` · confidence **medium** · decisions D08, D05

**E2.0 proposal (before the answers).** type `editorial` · subtype `lifestyle` · format `feature` · location *per article* · series_key: `column:music-to-the-ears` · status was `decision-needed`.

**Resolution.** basis D08, D05; changed — Migrated, searchable, series_key column:music-to-the-ears. Rails-excluded (follow-up #1, 2026-09-10): see rules.columns.excluded_from_rails -- series-level rule, not the quality floor. No place in the text -> site-home location fallback..

**Reasoning.** Lockdown playlists with no Bali subject; location none.

**Alternates for the classifier.** exclude from migration

**Representative titles (spread across the date range).**
- 2020-04-05 · Music & Conflict: Songs That Helped Soldiers Through Hard Times
- 2020-04-16 · One-and-done: One Hit Wonders of All-Time
- 2020-05-04 · Live From Your Living Room: Favourite Live & Acoustic Tracks on Spotify
- 2020-05-11 · The Greatest Boy Bands of All Time
- 2020-06-01 · Songs to Send to Distant Lovers
- 2020-06-16 · Jazz & Equality: How America’s ‘triumphant music’ helped fuel the Civil Rights Movement
- 2020-07-21 · Reminiscing the Summer Music Festival Season (and How to Get Your Fix)
- 2020-08-12 · The Music of Movies: Soundtracks that Make the Movie

**Cue instrument.** type: event 100% (coverage 27%); format: event 50%, listing 17%, opinion 17%, news 17% (coverage 55%); period-stamped titles 0%; roundups 0%; median first-person density 10.5/1000 words.

**Co-filed with.** Home Life 1; 10 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.48; leakage 9% (cross-type 0%). Cohesion 0.797 (baseline 0.482), leakage 9% → Winocracy (1); best split k=2 silhouette 0.175.
- cluster 1: 7 (64%) `?`/`listing` — One-and-done: One Hit Wonders of All-Time; The Greatest Boy Bands of All Time; Early ‘00s Throwback Playlist
- cluster 2: 4 (36%) `event`/`event` — Live From Your Living Room: Favourite Live & Acoustic Tracks on Spotif; Jazz & Equality: How America’s ‘triumphant music’ helped fuel the Civi; How to support your favourite artists during lockdown

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `lifestyle` · format `feature` · location `per-article` · agrees: True · split: False · confidence high. Consistently music-themed editorial features covering playlists, history, and cultural commentary with no location dependency.

### Health & Wellness — resolved — changed (D08, D05)

*7 published · 2020–2020 · parent: Home Life · Yoast primary on 4 · slug `health-wellness` · term 2386*

> Editor's description: We’ve started this ‘Health & Wellness’ category as part of our ‘Home Life’ series. to help you keeping your regular exercise routine at home.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · topic: health; series_key: `column:health-wellness` · confidence **medium** · decisions D08, D05

**E2.0 proposal (before the answers).** type `editorial` · subtype `lifestyle` · format `feature` · location *per article* · topic: health; series_key: `column:health-wellness` · status was `decision-needed`.

**Resolution.** basis D08, D05; changed — Lockdown at-home wellness column; site-home location fallback. Not rails-excluded -- follow-up #1 named only Must Watch Movies and Music to the Ears..

**Reasoning.** Lockdown home-workout/yoga-at-home pieces (2020); no venue.

**Alternates for the classifier.** wellness/yoga + guide when a studio is the subject (Yoga Barn)

**Representative titles (spread across the date range).**
- 2020-04-05 · Home Workout by Coach Vincent
- 2020-04-21 · Yoga at Home with Erin Kindt of Odyssey Mvmt
- 2020-04-27 · Meditation for Beginners: Get Mindful with These Three Easy Apps
- 2020-06-01 · The Art of Breathing: 3 Pranayama Techniques to Try at Home
- 2020-06-08 · Vinyasa Yoga with Ubud's Yoga Barn
- 2020-06-16 · The Consolations of Philosophy (and Philosophers)
- 2020-07-20 · 5 Podcasts To Help You Maintain your Mental Health

**Cue instrument.** type: wellness 100% (coverage 86%); format: review 50%, guide 50% (coverage 57%); period-stamped titles 0%; roundups 0%; median first-person density 14.7/1000 words.

**Places named in title/lead.** bali 1, seminyak 1, ubud 1; 0% name only a place outside bali.

**Co-filed with.** Video 2; 5 carry this category alone.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `lifestyle` · format `feature` · location `per-article` · agrees: True · split: False · confidence high. All titles are editorial wellness-at-home features with no location dependency, fitting lifestyle editorial rather than the wellness venue/listing type.

### Home Life — resolved — changed (D08, D27)

*1 published · 2020–2020 · parent: Archives · Yoast primary on 0 · slug `home-life` · term 2383*

> Editor's description: Discover our Home Life archives a weekly Inspirations for Life at Home: Music to the ears, Must watch movies, Health & Wellness, and many more!

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `lifestyle` · format `feature` · location `bali` · series_key: `column:home-life` · confidence **medium** · decisions D08, D27

**E2.0 proposal (before the answers).** type `editorial` · subtype `lifestyle` · format `feature` · location *per article* · series_key: `column:home-life` · status was `auto-accepted (policy decisions apply)`.

**Resolution.** basis D08, D27; changed — Parent of the lockdown columns (1 post); site-home location fallback..

**Reasoning.** 1 post; parent of the lockdown columns.

**Representative titles (spread across the date range).**
- 2020-06-01 · Songs to Send to Distant Lovers

**Cue instrument.** type: no signal; format: opinion 100% (coverage 100%); period-stamped titles 0%; roundups 0%; median first-person density 77.9/1000 words.

**Co-filed with.** Music to the Ears 1; 0 carry this category alone.

**Coherence.** 1 members with vectors (< 8); read the titles instead.

### News — resolved (D21)

*1067 published · 2013–2026 · top-level · Yoast primary on 795 · slug `news` · term 3*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format `news` · location `bali` · - · confidence **high** · decisions D21

**Resolution.** basis D21; unchanged.

**Reasoning.** Catch-all. Format news is the honest prior for a category literally named News; type is spread across hotels, events, restaurants and civic pieces. Same treatment E1.4 gave Jakarta News.

**Alternates for the classifier.** stay/hotel + news (openings, appointments); event/* + event when a dated happening is announced; format offer for festive promotions filed as news

**Representative titles (spread across the date range).**
- 2013-06-09 · ETIHAD AIRWAYS DONATES PROCEEDS OF CHARITY FUN RUN IN SUPPORT OF CHILDREN WITH AUTISM
- 2015-11-01 · A Book and A Drink At The Library
- 2017-01-31 · Behold and unleash the runner within!
- 2018-08-09 · Donate to Help Those Affected by the Lombok Earthquake
- 2019-10-23 · AYANA Hotels in Bali Celebrate the Magic of Festive Season
- 2021-12-08 · Marriott International Donates AUD 5,336 to Bali Children Foundation
- 2024-02-14 · Fivelements Retreat Bali Recognised as a Leading Advocate for Holistic Wellness
- 2026-09-07 · IHG Hotels & Resorts Set to Debut First Kimpton Property in Indonesia

**Cue instrument.** type: event 21%, stay 21%, eat 14%, editorial 11% (coverage 79%); format: news 37%, event 29%, offer 15%, listing 7% (coverage 69%); period-stamped titles 20%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 779, ubud 144, seminyak 78, nusa-dua 74, kuta 51, legian 50; 2% name only a place outside bali.

**Co-filed with.** Bar Guide 13, Stay Offers 11, Spa and Wellness 5; 1019 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.392 (baseline 0.397), leakage 77% → Community (112), Hotels & Resorts (73), Bar Guide (70), Art In Bali (67); best split k=3 silhouette 0.074.
- cluster 1: 439 (41%) `stay`/`news` — W Hotels Worldwide Announces W Bali - Ubud To Open in 2020; The Garcia Island-Inspired Boutique Resort Opens in Ubud; Trans Resort Bali : Your Family's Home Away from Home in Bali
- cluster 2: 348 (33%) `editorial`/`news` — The Future is Now 2017: 2nd Annual NOW! Bali PR and Marcomm Gathering; The Bali Hope Swimrun 2019 and the Birth of 'Island Protect'; The NOW! Bali PR Gathering 2019
- cluster 3: 280 (26%) `event`/`event` — Indonesia Bertutur 2024: An Island-Wide Cultural Showcase Unfolds Acro; Bali Arts Festival 2024: Dates, Venue and Information; Amarta Beach Festival 2024: Celebrating Bali’s Timeless Culture

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `news` · location `bali` · agrees: True · split: True → hotel-and-openings, events-and-culture, offers-and-promotions · confidence high. News is a catch-all category spanning many types; format=news and location=bali are correct, but content diversity suggests splitting by dominant themes.

### Dining Offers — resolved (D02, D20)

*487 published · 2016–2026 · parent: Offers · Yoast primary on 333 · slug `dining-offers` · term 30*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `restaurant` · format *per article* (prior `offer`) · location `bali` · - · confidence **medium** · decisions D02, D20

**Resolution.** basis D02, D20; unchanged.

**Reasoning.** Type eat is certain (cue 72%). Format is weaker than Jakarta's: a third read as new-menu/new-venue news.

**Alternates for the classifier.** format news for menu launches and openings; drink/bar when the outlet is a bar (cue 10%)

**Representative titles (spread across the date range).**
- 2016-05-15 · Soul in a Bowl: Bringing the Melbourne Cafe Scene to Sanur
- 2017-12-14 · Balinese Megibung Meals launched at Paon Bali Resto
- 2018-11-22 · Above Eleven Bali Launches Nine New Island-Inspired Cocktails
- 2019-08-18 · Authentic Balinese Restaurant Mr.Wayan Opens 'By the Sea'
- 2020-10-15 · A Night with Chris Salans at Mozaic Ubud
- 2022-08-25 · The Art of Seafood Bamboo Barbecue at Karma Beach Bali
- 2024-02-08 · W Bali – Seminyak is Brimming with Romance This Valentine’s Day
- 2026-07-23 · Bali Dessert Week Brings Indonesian Flavours to the Art of Pâtisserie at Roso Restaurant

**Cue instrument.** type: eat 82%, drink 11%, stay 5%, shop 1% (coverage 88%); format: offer 60%, news 32%, event 2%, people 2% (coverage 70%); period-stamped titles 20%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 291, seminyak 71, ubud 57, nusa-dua 41, uluwatu 37, canggu 33; 0% name only a place outside bali.

**Co-filed with.** Restaurants and Bars 188, Stay Offers 3, News 2; 294 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.49 vs baseline 0.40; leakage 75% (cross-type 8%). Cohesion 0.49 (baseline 0.399), leakage 75% → Restaurants and Bars (125), Experience Offers (80), Dining News (45), Reviews (42); best split k=2 silhouette 0.104.
- cluster 1: 338 (69%) `eat`/`news` — Renowned Indonesian Chef Arnold Poernomo Opens Laci Restaurant Bali; Modern Balinese Bistro, The Suku Bali, Reveals New Indonesian Sharing ; Elevated Indonesian Cuisine at The Mill
- cluster 2: 149 (31%) `eat`/`offer` — Toast to the Season of Joy at The Oberoi Beach Resort, Bali; Art de Nöel: Sofitel Bali Nusa Dua Beach Resort’s Candle Light Christm; Light Up Your Festive Holiday at Meliá Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `restaurant` · format `per-article` · location `bali` · agrees: False · split: True → dining-offers, dining-news, dining-reviews · confidence medium. Type and location are correct, but titles span news, reviews, features, and offers, so format is per-article and a split is warranted.

### Lifestyle — resolved (D23, D05, D13)

*243 published · 2015–2020 · top-level · Yoast primary on 109 · slug `lifestyle` · term 6*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* · location `bali` · - · confidence **low** · decisions D23, D05, D13

**Resolution.** basis D23, D05, D13; unchanged.

**Reasoning.** Container: 242 of 243 also carry a child (Shopping 114, Spa and Wellness 91, Bar Guide 26, Bali with Kids 7); only one post carries Lifestyle alone. Beauty (salons, facials), fashion and misc. features dominate the parent's own flavour.

**Alternates for the classifier.** wellness/salon\|spa for beauty venues; shop/boutique for fashion; editorial/lifestyle + feature fallback

**Representative titles (spread across the date range).**
- 2015-04-01 · What Men Want
- 2015-09-02 · Zen Family Spa & Reflexology Arrives In Bali
- 2016-06-22 · Denisifique Homme
- 2017-04-10 · Nauli Yoga at Alila Seminyak
- 2017-09-22 · Lace Up in Uluwatu for the Long Summer Nights
- 2018-07-18 · Clean and Green : Sensatia Botanical's Environmentally Friendly Bath Essentials
- 2019-04-09 · Sensatia Opens Sixteenth Store at Sidewalk Jimbaran
- 2020-03-31 · An Alternative Healing Experience in Bali

**Cue instrument.** type: wellness 44%, shop 34%, drink 12%, do 7% (coverage 80%); format: news 40%, offer 24%, heritage 12%, review 12% (coverage 40%); period-stamped titles 1%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 131, seminyak 37, ubud 21, uluwatu 8, kuta 6, denpasar 5; 1% name only a place outside bali.

**Co-filed with.** Shopping 114, Spa and Wellness 91, Bar Guide 26; 1 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.451 (baseline 0.401), leakage 98% → Shopping (94), Spa and Wellness (77), Bar Guide (23), Bali with Kids (8); best split k=3 silhouette 0.185.
- cluster 1: 134 (55%) `shop`/`news` — Design Your Own Flip Flops at Baia Baia; A Seminyak Shopping Spree; Bali Collection: The Perfect Shop Stop
- cluster 2: 86 (35%) `wellness`/`news` — Renewing My Prana; Put Your Feet Up: 4 Great Spots for Reflexology in Bali; Taman Merah Spa
- cluster 3: 23 (9%) `shop`/`heritage` — The Diamond is June's Birthstone!; Precious Jemme; Exceptional Balinese Craftmanship

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: True · split: True → wellness, shop, drink, editorial · confidence high. Lifestyle is a catch-all spanning wellness, shopping, spirits, and editorial; type and format vary per article while location is consistently Bali.

### Community — resolved (D19)

*152 published · 2015–2026 · parent: Features · Yoast primary on 115 · slug `community` · term 41*

> Editor's description: NOW Bali is a weekly magazine about Bali. Here you can find the latest updates about Bali and Bali community life.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `news` · format *per article* (prior `feature`) · location `bali` · topic: community · confidence **medium** · decisions D19

**Resolution.** basis D19; unchanged — Prior feature; topic community always. The subtype prior `news` is weak (the LLM suggested a `community` editorial subtype, which does not exist); the classifier picks among people/culture/lifestyle per article..

**Reasoning.** NGO and initiative features (Solemen, Mission Paws'ible, plastic-free campaigns); evergreen features more than dated news.

**Alternates for the classifier.** event/community + event for fundraisers; editorial/people + people for founder profiles; format news for announcements

**Representative titles (spread across the date range).**
- 2015-02-27 · Making Bali Plastic Free
- 2017-02-14 · Empowering Remote Villages With Education and Life Skills
- 2018-07-12 · Meet the Elephant Man, Nigel Mason , Founder of Mason Elephant Park
- 2020-02-09 · Solemen Indonesia: Tackling Bali's Mental Health Crisis
- 2021-08-05 · Continued Community Action in Amed, A Forgotten Corner of Bali
- 2022-12-05 · BASAbali: The Journey to Digitise the Balinese Language
- 2024-10-11 · In Memoriam: Robert Epstone of SoleFamily Bali
- 2026-08-20 · Where the Next Generation of Indonesian Chefs Go to Hone Their Craft

**Cue instrument.** type: editorial 77%, eat 8%, do 7%, wellness 2% (coverage 80%); format: listing 39%, event 14%, heritage 12%, news 12% (coverage 34%); period-stamped titles 5%; roundups 1%; median first-person density 3.9/1000 words.

**Places named in title/lead.** bali 133, ubud 9, sanur 6, east-bali 5, north-bali 5, denpasar 4; 0% name only a place outside bali.

**Co-filed with.** Explore Bali 2, News 2, NOW! Bali Podcast 2; 145 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.61 vs baseline 0.40; leakage 18% (cross-type 3%). Cohesion 0.612 (baseline 0.404), leakage 18% → Opinion (4), People of Bali (4), Art In Bali (4), News (3); best split k=2 silhouette 0.246.
- cluster 1: 109 (72%) `editorial`/`listing` — Best Charities in Bali: Supporting Trusted Foundations and NGOs; Bali Children's Project Helps Reduce Poverty Through Education; A Helping Hand For The Children of Bali
- cluster 2: 43 (28%) `editorial`/`listing` — ROLE Foundation : Protecting Bali's Ecosystems; A Spotlight on Bali’s Eco Heroes; Protecting Paradise: Bali's Environmental Heroes

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `community` · format `feature` · location `bali` · agrees: False · split: False · confidence high. These are human-interest feature stories about Bali community initiatives and people, not news items; subtype should be 'community' rather than 'news'.

### Art In Bali — resolved (D25, D04, D12)

*136 published · 2015–2026 · parent: Culture · Yoast primary on 99 · slug `art-in-bali` · term 25*

> Editor's description: Exploring Art in Bali: Discover why Bali is considered the center of Indonesian art and the important parts of Balinese culture.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* · location `bali` · topic: art · confidence **medium** · decisions D25, D04, D12

**Resolution.** basis D25, D04, D12; unchanged.

**Reasoning.** Exhibitions, artist profiles, buying guides, history of Balinese painting -- topic art is the only certain facet.

**Alternates for the classifier.** event/exhibition + event; editorial/people + people; editorial/culture + feature\|heritage; do/gallery + guide

**Representative titles (spread across the date range).**
- 2015-02-04 · The Art Of  Love
- 2018-08-20 · A Guide to Buying Balinese Art at Auctions
- 2019-09-24 · Traditional Daily Life in Bali's Batuan Paintings
- 2020-10-02 · Dodit Artawan: From Photorealism to Pop Art
- 2021-11-11 · La Salaga: A Bali-Sulawesi Legend Immortalised in the Iconic Balinese Kamasan Painting Style
- 2023-07-22 · Darkness Is White: A Multimedia Exhibition of Balinese Maestro I Gusti Nyoman Lempad
- 2025-04-10 · 'Postphotography': Seasoned Balinese Photographer Gustra Explores New Fields
- 2026-08-27 · Artist Agung Pramana Questions Colonial Propaganda Narratives & Imagery

**Cue instrument.** type: editorial 36%, do 30%, event 25%, stay 3% (coverage 46%); format: heritage 37%, news 18%, event 18%, listing 10% (coverage 46%); period-stamped titles 3%; roundups 0%; median first-person density 7.3/1000 words.

**Places named in title/lead.** bali 88, ubud 29, denpasar 8, east-bali 4, kuta 3, seminyak 3; 3% name only a place outside bali.

**Co-filed with.** Culture 38, News 3, Dance and Music 1; 94 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.71 (baseline 0.405), leakage 14% → Bali History (5), Culture (3), Cultural Observer (3), Dance and Music (2); best split k=2 silhouette 0.149.
- cluster 1: 83 (61%) `editorial`/`heritage` — Expatriate Artist Izzy Ivy’s Delightful Visionary Paintings Mediate Be; Made Valasara’s Artistic Exploration of Material Potential; Balinese Priestess Artist Mangku Muriati’s Pandemic Observations in th
- cluster 2: 53 (39%) `do`/`event` — Art Bali 2019 : An Exploration into Contemporary Art; Bali Art World Personalities : Meet Ruth Onduko; Cakravala: A New Cultural Platform Elevating Emerging Indonesian Artis

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `art` · format `per-article` · location `bali` · agrees: False · split: False · confidence high. All 136 articles concern art in Bali, so type=editorial and subtype=art fit; formats vary from news and features to guides and people profiles.

### Experience Offers — resolved (D17, D02)

*128 published · 2021–2026 · parent: Offers · Yoast primary on 127 · slug `experience-offers` · term 2581*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* (prior `stay`) · subtype *per article* (prior `hotel`) · format `offer` · location `bali` · - · confidence **medium** · decisions D17, D02

**Resolution.** basis D17, D02; unchanged.

**Reasoning.** Hotel experience packages: cue type splits stay 24% / eat 24% / wellness 14% / do 7%; format offer 64%.

**Alternates for the classifier.** eat/restaurant + offer (dining experiences); wellness/spa\|retreat + offer; event/* + event (festive programmes)

**Representative titles (spread across the date range).**
- 2021-09-15 · Fun, Fitness & Fuel: W Bali – Seminyak Presents Body Reboot Weekend
- 2022-06-23 · Au Soleil: Embrace Summer at Le Méridien Bali Jimbaran
- 2022-11-29 · Paul Oakenfold, Founding Father of Dance, Set to Perform at Le Club 22
- 2023-11-15 · Conrad Bali Brings Back the Festive Arcade This Holiday Season
- 2024-10-02 · Explore Indonesia’s Heritage through Fashion, Food, and Culture at Wastra Wonderland 2nd Ed.
- 2024-11-22 · Experience Festive Grandeur at Grand Hyatt Bali
- 2025-06-05 · Raise Your Glass to World Cucumber Day 2025 With Hendrick's Gin
- 2026-09-02 · Merasa Origins: Tracing Java’s Ancient Wellness Traditions at Desa Potato Head

**Cue instrument.** type: stay 30%, eat 30%, wellness 17%, do 9% (coverage 81%); format: offer 76%, event 10%, news 5%, city-guide 4% (coverage 84%); period-stamped titles 44%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 91, ubud 18, uluwatu 17, nusa-dua 14, seminyak 11, kuta 9; 2% name only a place outside bali.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.531 (baseline 0.405), leakage 50% → Stay Offers (15), News (13), Spa and Wellness (9), Bar Guide (4); best split k=3 silhouette 0.199.
- cluster 1: 66 (52%) `stay`/`offer` — Immerse in a Serene Easter Holiday by the Sea at Jumeirah Bali; A Peek into the Experiences Offered at Japanese Hidden Gem, HOSHINOYA ; Joyful Easter Celebrations at The Westin Resort & Spa Ubud
- cluster 2: 44 (34%) `eat`/`offer` — Cherish Joyful Festive Moments at Hilton Bali Resort; Splash Into Ayodya Resort Bali’s ‘Aqua Wonderland’ Festive Programme; Welcome the Season of Joy at The Oberoi Beach Resort, Bali
- cluster 3: 18 (14%) `event`/`event` — Usher in a Wicked October at The Iron Fairies Bali; Road to 2023: White Rock Beach Club Presents an Epic 8-Day Year-End Fe; KU DE TA Announces the Return of its Highly-Anticipated Annual White P

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `offer` · location `bali` · agrees: False · split: True → Hotel & resort experiences, Beach club events, Wellness experiences · confidence medium. Titles span hotels, beach clubs, and wellness venues with varied activity types, so type and subtype cannot be fixed; format=offer and location=bali hold.

### Explore Bali — resolved (D18, D10)

*117 published · 2014–2026 · top-level · Yoast primary on 15 · slug `explore-bali` · term 4*

> Editor's description: Discover and explore Bali. Now! Bali covers all the best places to visit, things to do, and most importantly, where to stay and where to eat.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* · location `bali` · - · confidence **low** · decisions D18, D10

**Resolution.** basis D18, D10; unchanged.

**Reasoning.** Container of Activities/Cultural Sites/Destinations/Bali with Kids/Nature/Parks, plus 41 Opinion co-filings. Not a `do` category on its own.

**Alternates for the classifier.** editorial/opinion + opinion when Opinion co-occurs; children's priors when a child co-occurs; do/* + guide for the remainder

**Representative titles (spread across the date range).**
- 2014-05-20 · Awaken the Heritage
- 2015-09-02 · Indulge Your Imagination with Art
- 2016-06-13 · Before and After... Us
- 2017-04-30 · Goa Lawah: Bali's Amazing Bat Cave Temple
- 2017-12-13 · New Years Resolutions: Getting Better All the Time?
- 2018-12-04 · Is Bali still the  “Morning of The World”?
- 2019-08-03 · Learn the Magic of Balinese Silvermaking with SUNSRI House of Jewelry
- 2026-07-08 · Hunting for History: A Journey Through Bali's Megalithic and Archaeological Sites

**Cue instrument.** type: do 54%, editorial 20%, stay 9%, eat 6% (coverage 76%); format: opinion 25%, review 22%, offer 16%, heritage 15% (coverage 58%); period-stamped titles 0%; roundups 2%; median first-person density 4.6/1000 words.

**Places named in title/lead.** bali 87, ubud 11, uluwatu 5, seminyak 4, east-bali 4, jakarta 4; 2% name only a place outside bali.

**Co-filed with.** Activities 42, Opinion 41, Stranger In Paradise 8; 22 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=3 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.548 (baseline 0.406), leakage 94% → Opinion (34), Activities (20), Nature and Outdoors (7), Cultural Sites (7); best split k=3 silhouette 0.144.
- cluster 1: 43 (37%) `editorial`/`opinion` — New Years Resolutions: Getting Better All the Time?; Killing the Golden Goose: When Development Should Stop in Bali; The Bitter Lessons  Experience Teaches Us
- cluster 2: 41 (35%) `do`/`review` — Green Cycling Through Ubud; Saddle Up: Discovering Bali on Horseback; Charly and his Chocolate Factory
- cluster 3: 33 (28%) `do`/`offer` — Start Your Engines: Go Karting in Bali; Sea Breacher, The Ocean Trespasser; 5GX Bali: The Slingshot Returns

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: True · split: True → heritage-people, opinion-issues, things-to-do · confidence high. Broad catch-all category mixing editorials, opinions, events, heritage, and activities; only location is consistently Bali, so type/subtype/format must be determined per-article.

### Uncategorized — resolved (D09)

*71 published · 2014–2022 · top-level · Yoast primary on 7 · slug `uncategorized` · term 1*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* · location `bali` · - · confidence **low** · decisions D09

**Resolution.** basis D09; unchanged — No prior; every facet from content; standard confidence gate; 'Purchasing NOW! Bali & TIMELESS Bali Magazines' is migrated, not excluded..

**Reasoning.** No prior; includes non-articles ('Purchasing NOW! Bali & TIMELESS Bali Magazines'). Review queue.

**Representative titles (spread across the date range).**
- 2014-12-01 · Great Escapes
- 2015-04-01 · Welcome To Bali
- 2015-08-07 · Sanur Village Festival 2015
- 2017-01-03 · The Wild, Wild West
- 2017-10-03 · Give Yourself a Sporting Chance
- 2018-08-03 · Bali's Sung and Unsung Heroes
- 2019-02-28 · What Does it Take to be a 'Bali Hero'?
- 2022-10-30 · Purchasing NOW! Bali & TIMELESS Bali Magazines

**Cue instrument.** type: do 44%, eat 18%, wellness 11%, stay 9% (coverage 78%); format: review 34%, opinion 22%, event 22%, news 9% (coverage 45%); period-stamped titles 4%; roundups 4%; median first-person density 10.5/1000 words.

**Places named in title/lead.** bali 55, ubud 3, uluwatu 2, kuta 2, north-bali 1, nusa-dua 1; 0% name only a place outside bali.

**Co-filed with.** News 1; 70 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.537 (baseline 0.412), leakage 58% → Opinion (9), Destinations (4), Weddings (4), News (4); best split k=3 silhouette 0.196.
- cluster 1: 39 (55%) `do`/`review` — Bali's Sung and Unsung Heroes; What Does it Take to be a 'Bali Hero'?; Happy Birthday to Us: 10 Years of NOW! Bali
- cluster 2: 22 (31%) `do`/`event` — A Dying Paradise: Preserving Religion, Culture and Customs in Bali; Great Escapes; Bali Tourism 2020: What Does the Government Have Planned for the Islan
- cluster 3: 10 (14%) `eat`/`news` — High On Dramatic Cliffs; Right  Here On Our Shores; Take the Love Deeper

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: True · split: False · confidence high. Uncategorized is a catch-all with no editorial logic; titles span events, food, opinion, culture, and travel, so only the magazine-level location is determinable.

### NOW! Bali Podcast — resolved (D08)

*27 published · 2020–2025 · top-level · Yoast primary on 16 · slug `podcast` · term 2387*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype *per article* (prior `culture`) · format `feature` · location `bali` · series_key: `column:podcast` · confidence **medium** · decisions D08

**Resolution.** basis D08; unchanged.

**Reasoning.** Podcast episode pages (2020-2025). No §4 format for audio; feature + series_key keeps them browsable.

**Alternates for the classifier.** editorial/people + people for interview episodes

**Representative titles (spread across the date range).**
- 2020-04-06 · Jero Gede Mecaling, Spreader of Death & Disease \| Episode 1
- 2020-05-04 · Legends of Bali's Great Temples \| Episode 4
- 2020-05-30 · What Will Travelling to Bali be like After Covid-19?
- 2020-07-13 · Exploring Art in Bali, feat. Richard Horstman
- 2021-04-27 · Agama Tirta : Bali's Religion of Water \| Episode 17
- 2022-03-17 · Symbolism of the Barong Landung: A China-Bali Connection
- 2023-01-27 · Nature, Cosmology and Transformational Healing, Feat. Tjok Gde Kerthyasa \| Episode 26
- 2025-12-15 · The Future of Farming in Bali, Ft. Kania Maniasa \| Bali Breakfast Talks Episode 2

**Cue instrument.** type: editorial 46%, do 27%, stay 9%, wellness 9% (coverage 41%); format: heritage 57%, opinion 14%, listing 14%, city-guide 7% (coverage 52%); period-stamped titles 0%; roundups 0%; median first-person density 9.0/1000 words.

**Places named in title/lead.** bali 25, uluwatu 1, cikini 1; 0% name only a place outside bali.

**Co-filed with.** Cultural Observer 4, Community 2, Opinion 1; 20 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.78 vs baseline 0.44; leakage 11% (cross-type 0%). Cohesion 0.781 (baseline 0.437), leakage 11% → Opinion (1), Myths and Legends (1), Music to the Ears (1); best split k=3 silhouette 0.32.
- cluster 1: 17 (63%) `editorial`/`heritage` — Promoting Tourism in Bali, Is There a Right Way? \| Episode 5; A New Vision for Indonesian Tourism; How the Old Balinese 'Experience' Time \| Episode 13
- cluster 2: 7 (26%) `do`/`heritage` — 4 Rules for Life, Bali-Style; Explaining the Role and Importance of Water in Bali \| Episode 22; Puppet Masters and the Power of Myth \| Episode 15
- cluster 3: 3 (11%) `editorial`/`listing` — Training Deaf Balinese Dancers, ft. Jasmine Okubo \| Bali Breakfast Tal; The Future of Farming in Bali, Ft. Kania Maniasa \| Bali Breakfast Talk; Bali 1928: Repatriating Bali’s Musical Memories

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. All entries are podcast episodes exploring Balinese culture, religion, art, and society; editorial feature format with Bali as consistent location fits well.

### Video — resolved (D08)

*11 published · 2018–2023 · top-level · Yoast primary on 5 · slug `video` · term 294*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* · subtype *per article* · format *per article* · location `bali` · series_key: `column:video` · confidence **low** · decisions D08

**Resolution.** basis D08; unchanged.

**Reasoning.** Video posts mirroring other categories (Made in Bali, Behind the Bar, Home Workout). Classify from content.

**Representative titles (spread across the date range).**
- 2018-02-26 · Mason Jungle Buggies: High Speed Adventures in Bali
- 2018-04-18 · Hatten Wines Holds a Special Fund Raising Fair for Stella’s Child
- 2018-12-03 · Bali Safari & Marine Park - Experiencing the 4x4 Jeep Ride
- 2019-02-10 · Bali Sea Salt : Traditionally Farmed Salt Made in Bali
- 2019-11-08 · Ayip Dzuhri : Samudra
- 2019-11-08 · Yudi Hendarsyah : Smoke & Fog
- 2020-04-21 · Yoga at Home with Erin Kindt of Odyssey Mvmt
- 2023-12-25 · Arak Bali - How is it Made? \| Made in Bali Episode 2

**Cue instrument.** type: drink 50%, wellness 38%, do 12% (coverage 73%); format: review 67%, news 33% (coverage 27%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 9, jimbaran 1, seminyak 1; 0% name only a place outside bali.

**Co-filed with.** Behind the Bar 3, Restaurants and Bars 3, Made in Bali 2; 4 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.457 (baseline 0.482), leakage 46% → Activities (1), Community (1), Spa and Wellness (1), Parks and Attractions (1); best split k=2 silhouette 0.173.
- cluster 1: 7 (64%) `drink`/`news` — Arey Barker : For Fig's Sake; Yudi Hendarsyah : Smoke & Fog; Ayip Dzuhri : Samudra
- cluster 2: 4 (36%) `wellness`/`review` — Home Workout by Coach Vincent; Arak Bali - How is it Made? \| Made in Bali Episode 2; Yoga at Home with Erin Kindt of Odyssey Mvmt

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: True · split: True → activity-videos, wellness-videos, artist-profile-videos · confidence high. Video is a medium not a content type; titles span do, wellness, event, editorial, and drink, so type and format are per-article while location is consistently Bali.

### Restaurants and Bars — resolved (as proposed)

*360 published · 2014–2022 · top-level · Yoast primary on 191 · slug `restaurants-bars` · term 7*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `restaurant` · format *per article* · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Parent of Dining News/Reviews/Bar Guide/Restaurant Guide, but 360 posts carry it directly (2014-2020). Type eat with drink as the alternate (cue eat 74%, drink 13%); format per article (news/review/listing).

**Alternates for the classifier.** drink/bar\|beach-club for bar pieces; format review (first-person visits); format listing ('7 Fabulous Foodie Pleasers in Ubud')

**Representative titles (spread across the date range).**
- 2014-12-01 · Best of the East
- 2015-08-01 · The Mozaic Beachclub Sweet Finale
- 2016-10-29 · The Breezes Has Lots Cooking
- 2017-09-22 · Luigi's Hot Pizza Opens in Canggu
- 2018-02-26 · Have you been to SoulBytes in Seminyak?
- 2018-11-14 · Sambal Sommeliers : Sunset on Seminyak Introduces Chilli Gurus to Their Dining Experience
- 2019-08-12 · St.Regis Bali Unveils Authentic Balinese Restaurant, Dulang
- 2022-01-10 · Aperitif Restaurant and Bar in Ubud Takes Bali's Fine Dining to New Heights

**Cue instrument.** type: eat 82%, drink 15%, stay 1%, shop 1% (coverage 90%); format: news 43%, offer 25%, review 18%, heritage 4% (coverage 53%); period-stamped titles 2%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 171, seminyak 62, ubud 43, canggu 20, jimbaran 19, kuta 17; 0% name only a place outside bali.

**Co-filed with.** Dining Offers 188, Reviews 63, Winocracy 9; 89 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.503 (baseline 0.4), leakage 50% → Reviews (58), Dining Offers (29), Bar Guide (19), Restaurant Guide (14); best split k=3 silhouette 0.068.
- cluster 1: 132 (37%) `eat`/`review` — Hujan Locale its Raining Flavors in Ubud; Vintaged at Balique Restaurant; The Patriotic Flavours of Republik 45
- cluster 2: 125 (35%) `eat`/`news` — Meja Kitchen & Bar Goes 'Back To The Roots'; Bikini Brings The Sexy Back to Seminyak; Savour Peruvian-Asian Gastronomy at Seminyak's AYA Street
- cluster 3: 103 (29%) `eat`/`offer` — How Divine; Bali's Breakfast Delights; A Cup of Wine Please

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `restaurant` · format `per-article` · location `bali` · agrees: True · split: True → Restaurants, Bars · confidence high. Titles are overwhelmingly restaurant and dining content spanning news, reviews, and features, but the category name also includes bars, warranting a split to separate drink-focused content.

### Dining News — resolved (as proposed)

*265 published · 2021–2026 · parent: Restaurants and Bars · Yoast primary on 262 · slug `dining-news` · term 2601*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `restaurant` · format `news` · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Matches the §4 worked example and Jakarta's mapping.

**Alternates for the classifier.** drink/* for bar news; format offer for promotions filed as news

**Representative titles (spread across the date range).**
- 2021-08-19 · Das Bistro by Mama’s: A Gourmet Culinary Concept Store
- 2023-07-26 · The Newly-Opened BELLA Brings Vibrant Mediterranean Flavours to Berawa
- 2024-02-28 · Island Brewing Launches All-New Light Lager
- 2024-09-13 · Where to Celebrate the Iconic Negroni Week in Bali
- 2025-05-05 · Tanah Liat’s Reimagined Concept Focuses on Local Seafood Offerings
- 2025-10-27 · Experience the Bold New Tasting Menu at The cave by Chef Ryan Clift
- 2026-04-24 · Ginger Moon Canteen: A Seminyak Icon of Modern Asian Flavours
- 2026-09-07 · Savour Bold Indian Flavours at the Beachfront Tandoori Bar & Grill

**Cue instrument.** type: eat 84%, drink 11%, stay 3%, shop 1% (coverage 97%); format: news 62%, offer 23%, listing 4%, event 3% (coverage 73%); period-stamped titles 5%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 172, ubud 47, seminyak 37, canggu 29, uluwatu 23, nusa-dua 22; 0% name only a place outside bali.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.56 vs baseline 0.40; leakage 40% (cross-type 8%). Cohesion 0.556 (baseline 0.401), leakage 40% → Reviews (33), Dining Offers (16), Bar Guide (11), Made in Bali (9); best split k=2 silhouette 0.082.
- cluster 1: 134 (51%) `eat`/`news` — Syrco BASÈ Redefines Indonesian-Inspired Dining in the Heart of Ubud; The Shady Pig Enters a Bold New Chapter with Cocktails and Cuisine; KAJA by Numa: Mediterranean Dining in a Cave-Inspired Setting
- cluster 2: 131 (49%) `eat`/`news` — Roomah Restaurant Offers Asian and Fusion Delights in Homey Comfort; Savour Modern Asian Flavours at the Stylish MUDA by Suka; Revel in Authentic Pan-Asian Delights at Komodo Restaurant & Bar

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `news` · location `bali` · agrees: False · split: False · confidence high. Category spans both restaurants (eat) and bars/cocktail venues (drink), so type and subtype vary per article; format is consistently news and location is Bali.

### Spa and Wellness — resolved (D13)

*209 published · 2014–2026 · parent: Lifestyle · Yoast primary on 108 · slug `spa` · term 26*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `wellness` · subtype `spa` · format *per article* · location `bali` · - · confidence **high** · decisions D13

**Resolution.** basis D13; unchanged.

**Reasoning.** Cue wellness 96%. Subtype spa dominates; retreat/yoga/salon per article (needs D13 for salon/retreat). Format per article (offer 18%, news 15%, features).

**Alternates for the classifier.** wellness/retreat for multi-day programmes; wellness/yoga; wellness/salon (beauty); format offer for spa packages

**Representative titles (spread across the date range).**
- 2014-12-30 · Seven Unique Spa Treatments
- 2015-12-17 · Skin Rejuvenation At Karma Spa
- 2017-05-08 · Ever Tried a Vichy SHower & Silk Bath? Well You Can Try Now at Spa Alila
- 2018-05-09 · Rainforest Retreat: An Ubud Spa Experience Out in Nature
- 2019-05-15 · Bali's Modern Health & Beauty Treatments To Make You Look & Feel Your Best
- 2022-08-15 · World-Renowned Rossano Ferretti Hair Spa Opens at Four Seasons Jimbaran Bay
- 2025-07-03 · Finding Peace with The Ungasan Clifftop Resort’s Unique Spiritual Wellness Experience
- 2026-08-27 · Discover Ancient Rituals and Modern Healing Journeys in Bali

**Cue instrument.** type: wellness 98%, drink 1%, stay 0% (coverage 98%); format: news 35%, offer 30%, heritage 14%, review 13% (coverage 53%); period-stamped titles 3%; roundups 2%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 131, ubud 41, seminyak 23, uluwatu 14, nusa-dua 11, jimbaran 8; 0% name only a place outside bali.

**Co-filed with.** Lifestyle 91, News 5, Activities 1; 112 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.60 vs baseline 0.40; leakage 11% (cross-type 4%). Cohesion 0.604 (baseline 0.401), leakage 12% → Lifestyle (11), Explore Bali (3), Stay Offers (2), Bar Guide (2); best split k=2 silhouette 0.198.
- cluster 1: 123 (59%) `wellness`/`news` — Men's Relaxing Facial At The Spa; Midnight Massage? W Bali – Seminyak's AWAY Spa Open Round the Clock th; Taman Merah Spa
- cluster 2: 86 (41%) `wellness`/`news` — Getting Alternative: Experiencing Holistic Healing in Bali; Discover the Best Wellness Retreats in Bali: Reconnect, Restore and Re; Bali's Healing Retreats

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `wellness` · subtype `spa` · format `per-article` · location `bali` · agrees: True · split: False · confidence high. Titles consistently cover spa treatments, wellness resorts, and beauty clinics in Bali; format varies between review, feature, and listing, so per-article is correct.

### Shopping — resolved (as proposed)

*174 published · 2014–2026 · parent: Lifestyle · Yoast primary on 75 · slug `shopping` · term 28*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `shop` · subtype `boutique` · format *per article* (prior `news`) · location `bali` · - · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Mostly brand/store news and fashion features (cue shop 60%). Same prior as Jakarta Shopping.

**Alternates for the classifier.** shop/artisan for local-brand pieces; shop/mall; format feature/guide for style features and shopping guides

**Representative titles (spread across the date range).**
- 2014-12-10 · BIASA+
- 2015-12-07 · Seminyak Village: A New Lifestyle Experience
- 2016-11-14 · Surrounded by Design at Rumahan Bistro
- 2017-07-18 · Exploring Denpasar's Shops
- 2018-08-06 · Homage to Heritage: Shopping for Ethnic Fabrics
- 2019-05-19 · Bali's Best Skincare Brands You Need to Bring Home
- 2022-02-11 · Bali Nutra: Bringing Natural Coconut-based Products from Bali to the World
- 2026-09-03 · KU DE TA Boutique Brings Curated Island Fashion to Seminyak

**Cue instrument.** type: shop 82%, editorial 8%, drink 4%, wellness 3% (coverage 72%); format: news 52%, heritage 27%, offer 10%, city-guide 4% (coverage 38%); period-stamped titles 3%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 93, seminyak 18, ubud 4, nusa-dua 3, denpasar 3, canggu 3; 2% name only a place outside bali.

**Co-filed with.** Lifestyle 114, News 4, Bali with Kids 1; 56 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.52 vs baseline 0.40; leakage 19% (cross-type 9%). Cohesion 0.525 (baseline 0.403), leakage 19% → Lifestyle (6), Community (4), Made in Bali (4), Art In Bali (3); best split k=3 silhouette 0.288.
- cluster 1: 115 (66%) `shop`/`news` — A Seminyak Shopping Spree; Bali Shopping with an ‘Eco Ego’; Design Your Own Flip Flops at Baia Baia
- cluster 2: 30 (17%) `shop`/`news` — Sensatia Releases New Rejuvenating Pomegranate Cleansing Oil; Take Home Your Bali Spa Session with These Amazing Spa Products; Sensatia Botanicals Launches New Refill Pouches
- cluster 3: 29 (17%) `shop`/`heritage` — Gift Ideas for Him & Her this Valentine's Day; The Diamond is June's Birthstone!; Precious Jemme

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `shop` · subtype `per-article` · format `per-article` · location `bali` · agrees: False · split: True → fashion-boutique, beauty-wellness, lifestyle-products · confidence medium. Titles span fashion, beauty, jewelry, and eco-products with mixed formats (news, feature, guide), so subtype and format cannot be fixed; boutique is too narrow.

### Reviews — resolved (as proposed)

*171 published · 2015–2026 · parent: Restaurants and Bars · Yoast primary on 116 · slug `dining-reviews` · term 240*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `restaurant` · format `review` · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Restaurant reviews; type eat 86%. Same as Jakarta Reviews.

**Alternates for the classifier.** drink/* when the venue is a bar

**Representative titles (spread across the date range).**
- 2015-12-07 · The Flavours of Jungle Fish
- 2017-02-28 · Pizza in Paradise
- 2018-03-08 · Brunch Adventura : An Italian, Family Brunch Adventure
- 2019-04-01 · Is Bali The Food Capital of Indonesia?
- 2022-12-10 · Golden Monkey: A Taste of Authentic Chinese Cuisine in Canggu
- 2024-09-06 · Tsune Serves Japanese Cuisine with a View in Sanur
- 2026-01-06 · 12 Kitchen & Wine: Berawa's Newest Restaurant and Wine Bar
- 2026-07-07 · An Evening of Middle Eastern Flavours at Samira

**Cue instrument.** type: eat 90%, drink 9%, editorial 1%, shop 1% (coverage 96%); format: news 43%, review 26%, offer 20%, listing 4% (coverage 60%); period-stamped titles 1%; roundups 2%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 97, ubud 40, seminyak 23, canggu 16, sanur 12, uluwatu 12; 0% name only a place outside bali.

**Co-filed with.** Restaurants and Bars 63, People of Bali 1, News 1; 106 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.59 vs baseline 0.40; leakage 47% (cross-type 9%). Cohesion 0.59 (baseline 0.403), leakage 47% → Restaurants and Bars (23), Dining News (22), Restaurant Guide (10), Bar Guide (7); best split k=2 silhouette 0.095.
- cluster 1: 96 (56%) `eat`/`review` — The Patriotic Flavours of Republik 45; Dining at Queens of India : Fit for a King; Vintaged at Balique Restaurant
- cluster 2: 75 (44%) `eat`/`news` — Making Flavours with Fire at Waatu; Mama San Supper Club: Will Meyrick’s Sophisticated ‘Culinary Speakeasy; Experience Ina Ré, a New Dining Destination at Desa Kistuné

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: False · split: True → Restaurant Reviews, Bar & Drink Reviews, Food & Drink Guides · confidence high. Parent 'Restaurants and Bars' spans eat and drink; titles include reviews, guides, and features, so type, subtype, and format all vary per article.

### Stay Offers — resolved (D02)

*168 published · 2016–2026 · parent: Offers · Yoast primary on 154 · slug `stay-offers` · term 11*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `stay` · subtype *per article* (prior `hotel`) · format `offer` · location `bali` · - · confidence **high** · decisions D02

**Resolution.** basis D02; unchanged.

**Reasoning.** Cue stay 61% / offer 88%. Subtype resort\|villa per article; location is a Bali area per article.

**Alternates for the classifier.** stay/resort\|villa; wellness/retreat for spa-led packages (cue 11%)

**Representative titles (spread across the date range).**
- 2016-06-07 · Beachwalk's Summer Fashion Show
- 2019-02-14 · Experience Nyepi at Renaissance Bali Uluwatu Resort & Spa
- 2020-03-05 · Aryaduta Bali Offers the Best Weekend Rates on the Island
- 2020-10-05 · Journey to Bali: Escape to Alila Villas Uluwatu
- 2022-02-16 · Experience the Magical Sound of Silence at Sheraton Bali Kuta Resort
- 2023-03-15 · From Ubud to Canggu, Ini Vie Hospitality Presents a Selection of Nyepi Escapes
- 2024-07-16 · Exciting Summer Family Getaway at Holiday Inn Resort Baruna Bali
- 2026-07-14 · Create Meaningful Family Memories at The Westin Resort & Spa Ubud

**Cue instrument.** type: stay 70%, wellness 12%, eat 10%, do 3% (coverage 87%); format: offer 92%, news 5%, city-guide 1%, event 1% (coverage 94%); period-stamped titles 28%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 134, nusa-dua 25, ubud 21, kuta 17, uluwatu 16, legian 13; 2% name only a place outside bali.

**Co-filed with.** News 11, Dining Offers 3, Shopping 1; 152 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.57 vs baseline 0.40; leakage 31% (cross-type 12%). Cohesion 0.57 (baseline 0.403), leakage 31% → Hotels & Resorts (15), Experience Offers (9), Spa and Wellness (6), Dining Offers (5); best split k=3 silhouette 0.085.
- cluster 1: 69 (41%) `stay`/`offer` — Stay for 3 Nights, Pay for 2 Nights at Holiday Inn Resort Baruna Bali; Eid Al-Fitr Hotel Promotions in Bali 2022: Lebaran Stays and Deals; Worry-free Getaway at Melia Bali: Book Now, Stay Later
- cluster 2: 65 (39%) `stay`/`offer` — Experience the Great Escape at Fairmont Sanur Beach Bali; Escape to the Serene Sudamala Resort Sanur with Their Flash Summer Sta; Peppers Seminyak Day Pass : Access into a Luxurious Poolside and all i
- cluster 3: 34 (20%) `stay`/`offer` — Enjoy Total Relaxation with TS Suites Seminyak's Nyepi Retreat; Bask in the Magical Serenity of Nyepi at InterContinental Bali Resort; A Tranquil Nyepi Escape at Wyndham Dreamland Resort Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `stay` · subtype `hotel` · format `offer` · location `bali` · agrees: True · split: False · confidence high. Titles are overwhelmingly hotel/resort stay promotions under the Offers parent; one mall-event outlier is negligible and does not justify a split.

### Opinion — resolved (D03)

*150 published · 2013–2026 · parent: Features · Yoast primary on 87 · slug `opinion` · term 18*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `opinion` · format `opinion` · location `bali` · - · confidence **high** · decisions D03

**Resolution.** basis D03; unchanged.

**Reasoning.** Columns (Bali's Traffic Woes, Is Bali Hindu?). Depends on approving the `opinion` format.

**Alternates for the classifier.** topic per article

**Representative titles (spread across the date range).**
- 2013-03-26 · Artists and Artisans - What's the difference between an artisan and an artist?
- 2016-03-14 · Pride and Perspective: Comparing Scotland to Bali
- 2017-01-24 · News from Bordeaux Saint-Emilion
- 2018-09-26 · Kids, and Making New Discoveries in Bali
- 2019-12-30 · The Future of Bali : Challenges of Over Tourism
- 2020-12-02 · An Interview with Vice Governor Cok Ace on Bali's Tourist Recovery
- 2023-06-15 · Homogenisation, Dilution and Disorganisation
- 2026-07-20 · Festival Philosophy: How the Ubud Writers & Readers Festival Finds Its Voice Each Year

**Cue instrument.** type: editorial 39%, do 23%, eat 15%, stay 10% (coverage 59%); format: opinion 54%, review 21%, city-guide 9%, heritage 7% (coverage 57%); period-stamped titles 5%; roundups 2%; median first-person density 15.9/1000 words.

**Places named in title/lead.** bali 95, jakarta 6, ubud 5, kuta 4, central-bali 2, canggu 2; 1% name only a place outside bali.

**Co-filed with.** Explore Bali 41, NOW! Bali Podcast 1; 108 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.66 vs baseline 0.40; leakage 35% (cross-type 2%). Cohesion 0.66 (baseline 0.404), leakage 35% → Uncategorized (17), Cultural Observer (6), Community (6), Art In Bali (4); best split k=3 silhouette 0.124.
- cluster 1: 67 (45%) `do`/`opinion` — Branding the ‘Perfect Island’; New Year New Beginnings?; The 'Bali Promise': Should Visitors Pledge to Behave in Bali?
- cluster 2: 55 (37%) `editorial`/`opinion` — The Future of Bali : Challenges of Over Tourism; The Bitter Lessons  Experience Teaches Us; Bali's Recovery: Who Said It Would Be Easy?
- cluster 3: 28 (19%) `editorial`/`review` — The Strength of Belief in Bali; A Time for Reflection: Can We Find Peace This Christmas?; The Important Things In Life

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `opinion` · format `opinion` · location `bali` · agrees: True · split: False · confidence high. All titles are clearly opinion/editorial pieces focused on Bali and Indonesia, matching the proposed facet values with no need for splitting.

### Hotels & Resorts — resolved (as proposed)

*140 published · 2015–2026 · parent: Lifestyle · Yoast primary on 131 · slug `hotels-resorts` · term 2575*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `stay` · subtype *per article* (prior `hotel`) · format *per article* · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Cue stay 81%. Format per article: offers (34%), news (15%), reviews/guides.

**Alternates for the classifier.** stay/resort\|villa\|boutique-hotel; format offer\|news\|review\|listing

**Representative titles (spread across the date range).**
- 2015-10-02 · 9 Secluded Venues in Bali to Get Away From It All
- 2022-07-27 · LOST LINDENBERG: A Hidden Retreat Amidst the Lush Jungles of West Bali
- 2023-05-09 · Suara Alam Suite: A Boutique Ubud Resort Surrounded by the Sounds of Nature
- 2024-05-16 · Glamping in Bali: 7 Best Luxury Tent Getaways [2024]
- 2024-11-08 · Anantara Ubud Bali Resort Opens Deep in the Jungles of Payangan
- 2025-07-16 · Why Kids Love a Holiday at Sofitel Bali Nusa Dua Beach Resort
- 2026-02-26 · The New Paradisus by Melià Bali Redefines All-Inclusive Luxury
- 2026-09-03 · Alaya Suites Ubud Opens in the Heart of Pengosekan

**Cue instrument.** type: stay 86%, wellness 5%, do 4%, eat 2% (coverage 94%); format: offer 49%, news 29%, city-guide 14%, heritage 4% (coverage 66%); period-stamped titles 3%; roundups 6%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 93, ubud 42, seminyak 12, canggu 9, nusa-dua 9, nusa-penida 7; 6% name only a place outside bali.

**Co-filed with.** Stay Offers 1, Spa and Wellness 1; 138 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.64 vs baseline 0.40; leakage 21% (cross-type 10%). Cohesion 0.637 (baseline 0.404), leakage 21% → Travel (6), Bali with Kids (6), Stay Offers (3), Spa and Wellness (3); best split k=3 silhouette 0.122.
- cluster 1: 78 (56%) `stay`/`offer` — Amora Ubud Boutique Villas: A Secluded Valley Escape; Romance and Tranquillity Await at The Kayon Resort Ubud; Discover the New Hiliwatu, Bali Ubud, a Tribute Portfolio Resort
- cluster 2: 35 (25%) `stay`/`news` — Slow Down and Reconnect in Island Luxury at MĀUA Nusa Penida; The New Paradisus by Melià Bali Redefines All-Inclusive Luxury; Best Family-Friendly Hotels in Bali
- cluster 3: 27 (19%) `stay`/`offer` — Luxurious Summertime Escapes in Bali You'll Love; Monolocale Resort Merges Art and Luxury in Stylish Affordable Villas; Astera Villa Seminyak: An Exquisite Haven for Honeymooners

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `stay` · subtype `hotel` · format `per-article` · location `bali` · agrees: True · split: False · confidence high. All titles cover Bali hotels, resorts, and villas; format varies across news, reviews, guides, and features, so per-article is correct.

### Activities — resolved (as proposed)

*119 published · 2015–2026 · parent: Explore Bali · Yoast primary on 73 · slug `activities` · term 164*

> Editor's description: Looking for what to do in Bali? Discover the most exciting activities, day trips, experiences and more in our self-tested list of things to do!

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `do` · subtype *per article* · format *per article* (prior `guide`) · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Things to do (cue do 66%): cooking classes, canyoning, bird walks, workshops. Subtype per article; format guide with review/offer alternates.

**Alternates for the classifier.** do/workshop\|adventure\|tour\|watersports\|attraction; format review for first-person outings; format offer for operator promotions (cue 21%)

**Representative titles (spread across the date range).**
- 2015-02-04 · Romantic Rides
- 2015-11-01 · Braving The Canyon
- 2017-03-10 · Ten Pins and Pints
- 2018-07-20 · Can You Make It Through Totem Room Escape's Adventures?
- 2019-06-10 · Shake and Stir: Bali Cocktail Classes You'll Love
- 2020-08-07 · Green Camp Bali Reopens, Invites You to Enjoy the Great Outdoors!
- 2023-11-30 · Scent-based Workshops in Bali: Craft Your Own Perfume, Soap and Candle
- 2026-05-12 · The Lure of Ubud’s Birdsong: Exploring with Bali Bird Walk

**Cue instrument.** type: do 75%, wellness 9%, shop 6%, eat 5% (coverage 88%); format: offer 36%, heritage 18%, city-guide 15%, news 11% (coverage 56%); period-stamped titles 2%; roundups 3%; median first-person density 1.0/1000 words.

**Places named in title/lead.** bali 99, ubud 21, nusa-penida 5, seminyak 4, east-bali 4, canggu 4; 0% name only a place outside bali.

**Co-filed with.** Explore Bali 42, Lifestyle 2, Spa and Wellness 1; 76 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.54 vs baseline 0.41; leakage 61% (cross-type 24%). Cohesion 0.542 (baseline 0.406), leakage 61% → Nature and Outdoors (12), Parks and Attractions (9), Explore Bali (6), Bali with Kids (6); best split k=3 silhouette 0.173.
- cluster 1: 64 (54%) `do`/`city-guide` — Going Off-Road : Quad Bikes and Tubing; Dirt Biking Through Bali's Rice Fields and Jungles; Jungle Cart Bali: A Real-Life Mario Kart Adventure
- cluster 2: 43 (36%) `do`/`offer` — Bali Pottery Classes; 7 Best Art Workshops and Painting Classes in Bali; Bali's Jewelery Making Workshops
- cluster 3: 12 (10%) `do`/`offer` — Diving Around the Island: Bali Manta Rays and Mola Mola; Dive Nusa Penida; Diving in Bali's South East Coast

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `per-article` · format `per-article` · location `bali` · agrees: False · split: False · confidence high. Type and subtype are correct, but titles span guides, reviews, features, and people profiles, so format must be per-article rather than uniformly guide.

### Culture — resolved (D04)

*110 published · 2014–2024 · top-level · Yoast primary on 61 · slug `culture` · term 5*

> Editor's description: Now! Bali is the ultimate guide to Bali. Explore Bali's culture, from Bali's history, art in Bali and exhibitions found around the island.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `culture` · format `feature` · location `bali` · topic: culture · confidence **medium** · decisions D04

**Resolution.** basis D04; unchanged.

**Reasoning.** Parent of the Culture family; the ~40 Culture-only posts are rituals, artists, gallery openings -- editorial/culture + feature is the honest fallback.

**Alternates for the classifier.** event/exhibition + event for gallery shows; editorial/heritage + heritage for ritual explainers

**Representative titles (spread across the date range).**
- 2014-12-30 · Seven Balinese Rituals
- 2016-02-09 · Dancing with the Bulls
- 2017-11-30 · Stalwarts of the Sawah: The Life of the Balinese Rice Farmer
- 2018-10-17 · DenPasar2018 Art + Design: An Exhibition and Movement
- 2019-07-16 · Genevieve Couteau : The French Virtuoso That Bali Art Historians Failed to Cite
- 2019-12-24 · Prana Bhawa : A Dance for the Energy of Life
- 2020-04-18 · A Bali Myth: Knock-Knock, Who's There?
- 2024-10-24 · 3 Balinese Myths and Mysteries to Scare You on Halloween

**Cue instrument.** type: do 48%, editorial 20%, event 16%, shop 4% (coverage 40%); format: heritage 61%, opinion 9%, listing 7%, event 7% (coverage 52%); period-stamped titles 2%; roundups 0%; median first-person density 3.2/1000 words.

**Places named in title/lead.** bali 72, east-bali 7, ubud 6, denpasar 5, kuta 2, jakarta 1; 0% name only a place outside bali.

**Co-filed with.** Art In Bali 38, Dance and Music 18, Myths and Legends 13; 31 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.567 (baseline 0.406), leakage 98% → Art In Bali (32), Dance and Music (16), Ceremonies & Festivals (15), Cultural Observer (13); best split k=3 silhouette 0.261.
- cluster 1: 54 (49%) `do`/`heritage` — A Bali Myth: Knock-Knock, Who's There?; Under the Rumbling Holy Mountain; Ngaben: The Balinese Cremation Ceremony
- cluster 2: 37 (34%) `do`/`heritage` — Bali's Citra Sasmita: In The Spotlight of Indonesian Contemporary Art; Aswino Aji's Artistic Observations of the Ego in the Face of Balinese ; Jean-Philippe Haure’s Quest for Beauty
- cluster 3: 19 (17%) `event`/`heritage` — The Bird King; Sandya Gita Kotamaning Bayu; Legong Jobog - Balinese Tale of Subali & Sugriwa

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Titles consistently cover Balinese culture, rituals, art, and religion as editorial features rooted in Bali, matching the proposal exactly.

### Cultural Observer — resolved (D04, D24)

*110 published · 2015–2026 · parent: Culture · Yoast primary on 85 · slug `cultural-observer` · term 24*

> Editor's description: CULTURAL OBSERVER : The Ancestors’ Cult - The cult of the ancestors is the deepest and most indigenous element of the Balinese religion,.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `culture` · format `feature` · location `bali` · topic: culture; series_key: `column:cultural-observer` · confidence **high** · decisions D04, D24

**Resolution.** basis D04, D24; unchanged.

**Reasoning.** A long-running column on Balinese religion and society (2015-2026). Evergreen explainers.

**Alternates for the classifier.** editorial/heritage + heritage for historical pieces

**Representative titles (spread across the date range).**
- 2015-04-02 · The Purpose of Offerings and The Balinese Story Of Sangjaya Kesunu
- 2017-11-20 · Warni: Another Sad Story
- 2019-01-31 · The Magic of Finding Love in Bali
- 2019-12-30 · Holy Offerings: The Real Life Practice of 'Yadnya'
- 2021-12-16 · The Relationship Between Bali & Indonesia: How Do They See Each Other?
- 2023-07-12 · Ngiring: Accompanied by the Gods
- 2025-03-25 · Decoding the Pawukon Calendar: Cycles and Symbolism
- 2026-07-22 · Meet Bayoe Edan, the Digital Dalang of the Modern Age

**Cue instrument.** type: editorial 34%, do 34%, eat 16%, wellness 7% (coverage 50%); format: heritage 80%, review 8%, opinion 4%, news 2% (coverage 44%); period-stamped titles 2%; roundups 0%; median first-person density 4.0/1000 words.

**Places named in title/lead.** bali 75, north-bali 3, lombok 2, denpasar 2, east-bali 2, ubud 2; 1% name only a place outside bali.

**Co-filed with.** NOW! Bali Podcast 4, Culture 2; 104 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.65 vs baseline 0.41; leakage 45% (cross-type 1%). Cohesion 0.652 (baseline 0.406), leakage 46% → Everyday Bali (10), Myths and Legends (8), Ceremonies & Festivals (7), Bali History (7); best split k=3 silhouette 0.211.
- cluster 1: 65 (59%) `do`/`heritage` — Refusing to Become a Mangku Priest; The Childhood Rites of the Balinese Life Cycle; Banyan Trees and the Cult of Ancestors
- cluster 2: 37 (34%) `do`/`heritage` — A Soul in Limbo: The Curious Case of a Converted Balinese; The Temple of the Murdered Man; Warni: Another Sad Story
- cluster 3: 8 (7%) `editorial`/`heritage` — The Relationship Between Bali & Indonesia: How Do They See Each Other?; Is the Balinese ‘Cult of Ancestors’ Becoming a More Normative Hinduism; The Idea of Morality in Balinese Culture

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Consistent cultural commentary column with in-depth feature articles on Balinese religion, customs, and social issues, all Bali-focused.

### Bar Guide — resolved (D01)

*76 published · 2014–2026 · parent: Restaurants and Bars · Yoast primary on 21 · slug `bali-bar-guide` · term 27*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `drink` · subtype *per article* (prior `bar`) · format *per article* · location `bali` · - · confidence **high** · decisions D01

**Resolution.** basis D01; unchanged.

**Reasoning.** Cue drink 70%. Format per article: bar news, mixologist profiles, roundups; the guide/listing boundary (D01) decides the roundups.

**Alternates for the classifier.** drink/cocktail-bar\|beach-club\|rooftop-bar\|pub; format news\|people\|listing\|review

**Representative titles (spread across the date range).**
- 2014-07-03 · Cp Lounge Rocks the Monkey Forest
- 2015-04-02 · Music for the Soul
- 2015-07-02 · One Year Vintage Single Malt
- 2015-12-15 · Get Vintaged At The Laneway
- 2017-10-21 · Live On Big Screens: Bali's Best Sports Bars
- 2018-11-15 · Where to Party in Bali Long into the Night
- 2021-04-06 · Breman: Bali's Newest Microbrewery, Bar and Restaurant
- 2026-09-03 · Discover The Alchemist’s Spice Route at L’Atelier by Cyril Kongo

**Cue instrument.** type: drink 82%, event 8%, stay 5%, wellness 3% (coverage 86%); format: news 44%, event 16%, listing 12%, offer 8% (coverage 33%); period-stamped titles 4%; roundups 10%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 53, seminyak 18, legian 8, ubud 7, canggu 5, nusa-dua 4; 0% name only a place outside bali.

**Co-filed with.** Lifestyle 26, News 13; 38 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.52 vs baseline 0.41; leakage 39% (cross-type 16%). Cohesion 0.523 (baseline 0.411), leakage 40% → Made in Bali (8), News (4), Restaurant Guide (3), Stay Offers (2); best split k=2 silhouette 0.15.
- cluster 1: 53 (70%) `drink`/`news` — Seminyak Nightlife: Bars, Clubs and Speakeasys; Where to Party in Bali Long into the Night; Best Clubs in Bali
- cluster 2: 23 (30%) `drink`/`news` — Island Brews: Bali's Very Own Spirits; The Best Cocktail Bars in Canggu (2025): A NOW! Bali Guide; Iceland Vodka : A Spirit Made in the Rolling Hills of Tabanan, Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `drink` · subtype `bar` · format `per-article` · location `bali` · agrees: True · split: False · confidence medium. Mostly bars and nightlife venues with mixed formats (news, reviews, guides, listings); a few off-topic articles like spa and hotel manager justify per-article format.

### Dance and Music — resolved (D04, D24)

*75 published · 2013–2025 · parent: Culture · Yoast primary on 54 · slug `balinese-dance-music` · term 22*

> Editor's description: Bali is filled with culture and one of the most prominent and visible components of that are the dances of Bali , or Balinese dances. Our contributor Kartika Dewi Suardana takes us deep into the world of visual art and ceremony by exploring the many Dances of Bali that exist . In Bali, dances can be

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `culture` · format `feature` · location `bali` · topic: culture, music · confidence **high** · decisions D04, D24

**Resolution.** basis D04, D24; unchanged.

**Reasoning.** Explainers of Balinese dance forms and gamelan (Tari Topeng, Jegog, Janger) -- not events.

**Alternates for the classifier.** editorial/heritage + heritage

**Representative titles (spread across the date range).**
- 2013-03-01 · Tari Topeng (Mask Dance)
- 2015-12-09 · Pendet: A Beautiful Welcoming Dance
- 2016-11-19 · Sanghyang Deling: The Possession of Puppets
- 2017-09-08 · Discovering Bali's Traditional Musical Instruments
- 2018-05-27 · The Janger Dance: From the Rice Field to the Sea
- 2019-03-22 · Cultural Nights at the Ubud Palace
- 2019-12-24 · Prana Bhawa : A Dance for the Energy of Life
- 2025-12-10 · A Beginner’s Guide to Balinese Dance

**Cue instrument.** type: event 74%, do 18%, editorial 5%, shop 3% (coverage 51%); format: heritage 49%, event 47%, review 2%, news 2% (coverage 65%); period-stamped titles 0%; roundups 0%; median first-person density 2.4/1000 words.

**Places named in title/lead.** bali 49, ubud 9, kuningan 2, east-bali 2, north-bali 2, uluwatu 2; 3% name only a place outside bali.

**Co-filed with.** Culture 18, Art In Bali 1; 57 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.79 vs baseline 0.41; leakage 11% (cross-type 0%). Cohesion 0.791 (baseline 0.411), leakage 11% → Ceremonies & Festivals (3), Myths and Legends (1), Culture (1), Cultural Observer (1); best split k=3 silhouette 0.234.
- cluster 1: 42 (56%) `event`/`heritage` — The Panyembrama: Flowers, Smiles and Gentle Gestures; Pendet: A Beautiful Welcoming Dance; Dagger in Hand: Bali's Baris Keris Dance
- cluster 2: 27 (36%) `event`/`event` — Arja: Beauty in Complexity; The Ballet of Abimanyu; Sanghyang Deling: The Possession of Puppets
- cluster 3: 6 (8%) `do`/`heritage` — The Spiritual Sounds of the Gamelan; Discovering Bali's Traditional Musical Instruments; Jegog Bamboo

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Consistent cultural-editorial features on Balinese dance and music; category is Bali-scoped with no meaningful format or location variation warranting a split.

### Cultural Sites — resolved (as proposed)

*71 published · 2015–2026 · parent: Explore Bali · Yoast primary on 44 · slug `cultural-sites` · term 2563*

> Editor's description: The cultural sites of Bali are some of the most interesting attractions on the island. Here's a guide to the best of them.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `do` · subtype `attraction` · format `guide` · location `bali` · topic: heritage, culture · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Temples, water palaces, sacred trees -- places to visit with a heritage angle. Prime E2.3 place-extraction input.

**Alternates for the classifier.** editorial/heritage + heritage when the piece is history-led; format listing for roundups ('Chinese Temples in Bali')

**Representative titles (spread across the date range).**
- 2015-07-02 · Purifying Body & Soul
- 2017-03-19 · Bali's Beguiling Chinese Temples
- 2019-06-02 · Pura Sada Kapal : A Javanaese Mystery in Bali
- 2022-04-01 · Ubud Monkey Forest: Things to Know Before You Go
- 2023-08-04 · Taman Ujung Water Palace: The Garden at the End
- 2024-03-26 · Bunut Bolong: The Holy Hollow Tree
- 2025-01-21 · Chinese Temples in Bali
- 2026-04-22 · Kahyangan Tiga: Three Temples in Every Village in Bali

**Cue instrument.** type: do 91%, editorial 6%, event 2%, shop 2% (coverage 78%); format: heritage 95%, opinion 2%, feature 2%, city-guide 2% (coverage 82%); period-stamped titles 0%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 54, east-bali 7, central-bali 5, north-bali 5, ubud 5, denpasar 4; 0% name only a place outside bali.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.69 vs baseline 0.41; leakage 24% (cross-type 18%). Cohesion 0.692 (baseline 0.412), leakage 24% → Destinations (6), Ceremonies & Festivals (2), Myths and Legends (2), Art In Bali (2); best split k=3 silhouette 0.241.
- cluster 1: 46 (65%) `do`/`heritage` — Pura Samuan Tiga and the Evolution of Bali’s Temple Philosophy; Pura Luhur Mekori and the Battle of the Two Dragons; Pura Alas Kedaton: The Temple Without Incense
- cluster 2: 13 (18%) `do`/`heritage` — Pura Tirta Empul: The Holy Spring of Indra; Temples of Tampaksiring; Tirta Empul: Bali's Hidden Heritage
- cluster 3: 12 (17%) `do`/`heritage` — 15 Best Museums in Bali: Destinations for History, Culture and Art; Museum Gedong Arca: Clues from Prehistoric Bali; Bali's Craftsmen Villages

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `attraction` · format `per-article` · location `bali` · agrees: False · split: False · confidence high. Type, subtype, and location are correct, but format varies per article: listicles are guides, single-site profiles are features, and experiential visits read as reviews.

### Destinations — resolved (as proposed)

*53 published · 2015–2026 · parent: Explore Bali · Yoast primary on 20 · slug `destinations` · term 2577*

> Editor's description: Explore the best places to visit in Bali. Discover where to go, what to do and take a look at the best places to stay. The following article will provide you with all the information you need.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `city-guide` · format `city-guide` · location *per article* (prior `bali`) · topic: travel · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Area guides and itineraries (West Bali, Nusa Lembongan, East Bali road trip). Location is the Bali sub-area per article.

**Alternates for the classifier.** format listing for '3 days in X' itineraries

**Representative titles (spread across the date range).**
- 2015-04-02 · An Afternoon in Perancak
- 2017-11-01 · Denpasar After Dark
- 2018-08-06 · Touring Tabanan: Lakes, Rice Fields and Botanical Gardens
- 2019-06-02 · When the Night Falls in Bali : Markets, Streetfood and Local Culture
- 2020-02-28 · Back to Bedugul : Bali's Central Highlands
- 2024-06-04 · Experiencing Island Living on Nusa Lembongan
- 2025-04-01 · Bali Road Trip Itinerary: Central-North Bali
- 2026-06-04 · Discover Nusa Lembongan & Nusa Ceningan in Three Days: An Island Hopping Itinerary

**Cue instrument.** type: do 79%, editorial 16%, eat 5% (coverage 72%); format: heritage 46%, city-guide 39%, review 3%, event 3% (coverage 62%); period-stamped titles 0%; roundups 2%; median first-person density 1.8/1000 words.

**Places named in title/lead.** bali 44, east-bali 7, nusa-penida 6, ubud 5, north-bali 5, seminyak 4; 2% name only a place outside bali.

**Co-filed with.** Explore Bali 1; 52 carry this category alone.

**Coherence** (mixed, against the E2.0 proposal). 36% of members sit closer to a category of a different type (Nature and Outdoors 13, Cultural Sites 6, Bali History 2). Cohesion 0.626 (baseline 0.418), leakage 47% → Nature and Outdoors (13), Cultural Sites (6), Bali History (2), Travel (2); best split k=3 silhouette 0.179.
- cluster 1: 36 (68%) `do`/`city-guide` — Bali Road Trip Itinerary: Northwest Bali; 11 Destinations That Will Show your 'Real Bali'; Bangli Beckons
- cluster 2: 11 (21%) `editorial`/`heritage` — Explorations in North Bali: From Ancient History to Hot Springs; In Search of Ancient Bali: Exploring Four Bali Aga Villages; Denpasar: Searching for History in Bali's Capital City
- cluster 3: 6 (11%) `do`/`city-guide` — Discover Nusa Lembongan & Nusa Ceningan in Three Days: An Island Hoppi; Escape to Nusa Lembongan: A NOW! Bali Guide; Experiencing Island Living on Nusa Lembongan

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `city-guide` · format `city-guide` · location `per-article` · agrees: False · split: False · confidence high. Destination guides covering varied sub-regions of Bali; location is per-article since each title targets a specific village, regency, or area rather than Bali as a whole.

### Restaurant Guide — resolved (D01)

*52 published · 2016–2026 · parent: Restaurants and Bars · Yoast primary on 34 · slug `restaurant-guide` · term 2576*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `eat` · subtype `restaurant` · format *per article* (prior `guide`) · location `bali` · - · confidence **high** · decisions D01

**Resolution.** basis D01; unchanged.

**Reasoning.** Year-stamped and '[Updated]' roundups dominate since 2024 -> listing under D01; timeless area eats -> guide.

**Alternates for the classifier.** format listing + series_key for period-stamped roundups

**Representative titles (spread across the date range).**
- 2016-02-02 · Decadent Dinner for Two
- 2018-10-05 · Eat Streets of Bali : Savouring Sanur
- 2020-02-28 · Bali's Bean Scene : Best Coffee Spots in Bali
- 2024-07-22 · Best Mediterranean and Greek Restaurants in Bali
- 2025-05-01 · Best Chinese Restaurants in Bali (2025): Dim Sum, Hot Pot and More
- 2026-01-01 · Christmas in Bali 2026: Lunches, Dinners, Celebrations
- 2026-03-30 · Easter in Bali 2026: Brunches, Feasts and Celebrations
- 2026-08-28 · New Restaurants in Bali 2026: Latest Openings [Updated]

**Cue instrument.** type: eat 96%, drink 4% (coverage 100%); format: listing 32%, offer 25%, news 21%, city-guide 11% (coverage 54%); period-stamped titles 31%; roundups 38%; median first-person density 1.1/1000 words.

**Places named in title/lead.** bali 49, seminyak 10, canggu 8, kuta 7, legian 7, ubud 6; 0% name only a place outside bali.

**Co-filed with.** Restaurants and Bars 1; 51 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.60 vs baseline 0.42; leakage 52% (cross-type 6%). Cohesion 0.598 (baseline 0.418), leakage 52% → Restaurants and Bars (7), Reviews (4), Experience Offers (4), Dining News (4); best split k=3 silhouette 0.133.
- cluster 1: 29 (56%) `eat`/`listing` — 13 Best Restaurants in Seminyak for Dinner, Drinks and Culinary Deligh; Best Mediterranean and Greek Restaurants in Bali; Best Fine Dining in Bali: Elevated Restaurant Experiences
- cluster 2: 15 (29%) `eat`/`news` — 7 Places to Dine with Nature Abound in Bali; Plant-Powered : Plant-Based Dining You'll Love; Romance for Two: Special Dining Experiences in Bali
- cluster 3: 8 (15%) `eat`/`offer` — Christmas in Bali 2026: Lunches, Dinners, Celebrations; Chinese New Year in Bali 2026: Best Feasts and Celebrations; Easter in Bali 2026: Brunches, Feasts and Celebrations

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `restaurant` · format `guide` · location `bali` · agrees: True · split: False · confidence high. Titles are predominantly curated restaurant guides and best-of lists for Bali; category name and parent confirm eat/restaurant with guide format.

### Bali with Kids — resolved (as proposed)

*47 published · 2017–2026 · parent: Explore Bali · Yoast primary on 23 · slug `bali-with-kids` · term 29*

> Editor's description: Bali is definitely a family friendly island, so if you're coming to Bali with kids you'll find lots to do. Camping, art classes, shopping and more.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* (prior `do`) · subtype *per article* · format *per article* (prior `guide`) · location `bali` · audience: family; topic: family · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Audience family is the certain facet (the §4 Kids & Family example). Roundups of parks/activities -> do prior; listing when year-stamped (D01).

**Alternates for the classifier.** do/attraction\|workshop + guide\|listing; stay/resort + offer for family packages

**Representative titles (spread across the date range).**
- 2017-04-03 · Bali's Best Parks and Attractions
- 2017-09-22 · Taman Nusa: Around Indonesia in One Day
- 2018-09-06 · Cultural Appreciation : Teaching Kids Balinese Culture
- 2018-11-02 · Titi Batu Ubud Club : Bali's Newest Sports and Recreation Centre
- 2019-09-08 · Playtime at Parklife, Bali's Newest 'Family Hub'
- 2023-09-07 · All-Round Entertainment at the New Kupu-Kupu Kids Club
- 2025-07-08 · Best Kids Activities in Ubud: Cultural Classes and Workshops
- 2026-07-30 · 10 Best Bali Playgrounds and Parks for Kids (2026 Guide)

**Cue instrument.** type: do 79%, wellness 7%, eat 5%, shop 2% (coverage 89%); format: offer 33%, news 24%, city-guide 19%, listing 14% (coverage 45%); period-stamped titles 2%; roundups 8%; median first-person density 1.0/1000 words.

**Places named in title/lead.** bali 39, ubud 4, canggu 4, jimbaran 3, sanur 2, central-bali 2; 0% name only a place outside bali.

**Co-filed with.** Lifestyle 9, Parks and Attractions 2, Shopping 1; 37 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.661 (baseline 0.421), leakage 34% → Parks and Attractions (9), Nature and Outdoors (3), Activities (2), Destinations (1); best split k=3 silhouette 0.171.
- cluster 1: 21 (45%) `do`/`city-guide` — Playtime at Parklife, Bali's Newest 'Family Hub'; 11 Best Kids Clubs in Bali; Mai Main Canggu: An Immersive Playground Haven for Kids
- cluster 2: 19 (40%) `do`/`news` — Sports Clubs and Activities for Kids in Bali; Capoeira for Kids; Yoga for Kids : Movements & Meditations
- cluster 3: 7 (15%) `do`/`event` — Rediscovering Wildlife at Bali Safari and Marine Park; Bali's Best Parks and Attractions; Bali's Best Animal Parks Your Kids Will Love

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `per-article` · format `per-article` · location `bali` · agrees: False · split: False · confidence high. Type and location are correct, but format varies across guide, listing, review, and news articles, so format should be per-article.

### Ceremonies & Festivals — resolved (D04, D24)

*45 published · 2013–2025 · parent: Culture · Yoast primary on 20 · slug `balinese-ceremonies` · term 284*

> Editor's description: There are ceremonials and festivals happening every day in Bali. That's why we bring you an array of the latest news on Bali's biggest celebration.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `culture` · format `feature` · location `bali` · topic: culture · confidence **high** · decisions D04, D24

**Resolution.** basis D04, D24; unchanged.

**Reasoning.** Explainers of Balinese rites (Melasti, Saraswati, cremation) -- evergreen culture, not dated events.

**Alternates for the classifier.** event/festival + event for a specific dated edition; editorial/heritage + heritage

**Representative titles (spread across the date range).**
- 2013-09-27 · Sauh Munyi - A Promise to the Gods
- 2016-02-15 · The Clandestine Cockfight
- 2017-04-21 · Magical Melukat: Purifying Our Mind, Body & Soul
- 2018-10-09 · Metatah : A Balinese Teeth Filing (Done with Style)
- 2019-09-04 · Megesah : Torturing the Newly Weds
- 2022-10-21 · Understanding Hari Saraswati, Bali's Day of Knowledge
- 2023-07-31 · Penampahan Galungan: Preparations and Purifications
- 2025-11-20 · Unique Celebrations: Bali’s One-of-a-Kind Festivals

**Cue instrument.** type: event 42%, do 37%, editorial 16%, wellness 5% (coverage 42%); format: heritage 56%, event 28%, news 11%, review 6% (coverage 40%); period-stamped titles 9%; roundups 0%; median first-person density 1.0/1000 words.

**Places named in title/lead.** bali 19, ubud 3, central-bali 2, kuningan 2, denpasar 2, sanur 1; 2% name only a place outside bali.

**Co-filed with.** Culture 4, News 1; 40 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.68 vs baseline 0.42; leakage 36% (cross-type 2%). Cohesion 0.681 (baseline 0.423), leakage 36% → Cultural Observer (5), Everyday Bali (4), People of Bali (2), Stranger In Paradise (1); best split k=3 silhouette 0.201.
- cluster 1: 23 (51%) `event`/`event` — The March of the Barongs; Tajen Bali : The Island's Ritual Cockfight; O Oh Odalan – Bali’s Most Beautiful ( Temple Ceremony )
- cluster 2: 19 (42%) `do`/`heritage` — Tumpek Landep: Bali Blesses its Metals; Tumpek Kandang: The Holy Day for Animals; Tumpek Uduh: Balinese Hindu Honour Their Plants
- cluster 3: 3 (7%) `do`/`heritage` — Melukat : Purification the Balinese Way; Magical Melukat: Purifying Our Mind, Body & Soul; Coming Clean: The Melukat Cleanse

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Titles are explanatory features on Balinese ceremonies and rituals, not event listings or news, so editorial/culture/feature with Bali-wide location fits.

### Nature and Outdoors — resolved (as proposed)

*33 published · 2015–2026 · parent: Explore Bali · Yoast primary on 15 · slug `nature-and-outdoors` · term 2565*

> Editor's description: In Bali, nature and outdoor activities are a big part of life, and there are several places where you can go for a quick hike, a long walk, or a swim. Read this article to find out where to go.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `do` · subtype *per article* (prior `adventure`) · format `guide` · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Lakes, beaches, mangroves, hot springs -- outdoor places to go.

**Alternates for the classifier.** do/attraction; format listing for 'all 4 Bali lakes' roundups

**Representative titles (spread across the date range).**
- 2015-07-02 · Busy Mornings in Kedonganan
- 2016-08-02 · The Magical, Mysterious Danau Tamblingan
- 2016-10-14 · Gala Gala Underground House in Nusa Lembongan
- 2019-11-17 · Camping in Bali : Where to Pitch Up Your Tent
- 2021-07-01 · Lakes in Bali: Discover All 4 Stunning Bali Lakes
- 2022-04-01 · A Guide to Mountains in Bali: Volcanoes, Calderas and Epic Adventures
- 2023-10-03 · Lakeside Bliss in Bali’s Highlands
- 2026-08-20 · The Ultimate Adventure in Bali: Nature, Thrills and the Great Outdoors

**Cue instrument.** type: do 78%, editorial 13%, eat 4%, shop 4% (coverage 70%); format: city-guide 29%, heritage 29%, guide 18%, offer 6% (coverage 52%); period-stamped titles 0%; roundups 9%; median first-person density 1.1/1000 words.

**Places named in title/lead.** bali 29, nusa-penida 3, ubud 3, central-bali 2, north-bali 2, seminyak 1; 0% name only a place outside bali.

**Coherence** (mixed, against the E2.0 proposal). 33% of members sit closer to a category of a different type (Destinations 8, Community 3, Parks and Attractions 1). Cohesion 0.647 (baseline 0.432), leakage 36% → Destinations (8), Community (3), Parks and Attractions (1); best split k=3 silhouette 0.217.
- cluster 1: 17 (52%) `do`/`city-guide` — On the Search for Bali’s Quiet Beaches; Estuarine Explorations at the Kedonganan Mangroves; Discovering the Best Waterfalls in Bali
- cluster 2: 10 (30%) `do`/`guide` — Hidden Adventures in Bedugul; Lakes in Bali: Discover All 4 Stunning Bali Lakes; Lakeside Bliss in Bali’s Highlands
- cluster 3: 6 (18%) `editorial`/`heritage` — The Astungkara Trail: A 10-Day Pilgrimage of Discovery Across Bali; Back to the Roots: Learning to Farm in Bali; For People and Planet: Developing Trail Tourism Across Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `adventure` · format `per-article` · location `bali` · agrees: False · split: False · confidence medium. Type and location are correct, but format varies across guides, features, and listings, making it per-article rather than uniformly guide.

### People of Bali — resolved (as proposed)

*32 published · 2015–2026 · parent: Features · Yoast primary on 8 · slug `people-of-bali` · term 2562*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `people` · format `people` · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Profiles and social portraits (farmers, priests, photographers). Evergreen per §4.

**Alternates for the classifier.** editorial/culture + feature for group portraits

**Representative titles (spread across the date range).**
- 2015-12-01 · Bali Today, According to Niluh Djelantik
- 2016-04-15 · The Salt of The Earth: In Praise of Balinese Women
- 2018-06-11 · Photo Essay: Coastal Lives on the Island
- 2018-12-24 · Men of the Soil, Bali's Backbone
- 2020-03-03 · Meet Bali's Mushroom Man : I Gede Artha Sudiarsana
- 2020-07-05 · Being a Balinese Christian : A Question of Faith and Culture
- 2022-10-12 · A Reminder: Bali Bomb Survivor
- 2026-05-28 · Following The Threads with Ida Ayu Ngurah Puriani

**Cue instrument.** type: editorial 46%, do 23%, stay 8%, wellness 8% (coverage 41%); format: heritage 43%, review 21%, people 14%, city-guide 7% (coverage 44%); period-stamped titles 0%; roundups 0%; median first-person density 6.7/1000 words.

**Places named in title/lead.** bali 29, east-bali 4, uluwatu 1, ubud 1, nusa-dua 1, south-bali 1; 0% name only a place outside bali.

**Co-filed with.** Culture 2, Reviews 1; 29 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.63 vs baseline 0.43; leakage 50% (cross-type 3%). Cohesion 0.63 (baseline 0.433), leakage 50% → Opinion (3), Dance and Music (3), Explore Bali (2), Culture (2); best split k=3 silhouette 0.141.
- cluster 1: 13 (41%) `editorial`/`heritage` — On Modernity: Perspectives from Balinese; Suteja Neka : Founder of Neka Museum; An Island of Acceptance and Harmony
- cluster 2: 10 (31%) `?`/`heritage` — Bungaya: Behind The Tourist Door; Bali's Beautiful Rejang Girls; Those Wild Men of Karangasem
- cluster 3: 9 (28%) `editorial`/`people` — Meet Bali's Mushroom Man : I Gede Artha Sudiarsana; Nurturing the Next Generation of Indonesian Coffee Farmers; Closing the Distance: People of Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `people` · format `people` · location `bali` · agrees: True · split: False · confidence high. Titles consistently profile individuals and communities in Bali, fitting editorial/people/people with a stable Bali location across the full date range.

### Myths and Legends — resolved (D24)

*30 published · 2016–2026 · parent: Culture · Yoast primary on 27 · slug `myth-in-bali` · term 1706*

> Editor's description: Now! Bali Magazine is the first magazine in the world that brings together the latest news on Bali's history, myths and legends, and culture.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `heritage` · format `heritage` · location `bali` · topic: heritage, culture · confidence **high** · decisions D24

**Resolution.** basis D24; unchanged.

**Reasoning.** Folklore and origin stories -- evergreen heritage.

**Alternates for the classifier.** editorial/culture + feature

**Representative titles (spread across the date range).**
- 2016-08-28 · The Origin of Uluwatu and Why Fishermen Cannot Become Rich
- 2019-04-01 · Poo Means Luck Here in Bali
- 2019-09-11 · Pawang Hujan : Bali's Mystic Rain Stoppers
- 2020-02-13 · Madiksa: A Priest's Second Birth
- 2020-07-03 · The Bali Break-Up Curse
- 2022-10-15 · Patung Bayi : The Myth of Bali's Crying Baby Statue
- 2024-02-20 · Mt. Agung: Home of Myths and Legends
- 2026-09-03 · The Tiger & the Palm-wine Tapper - The Story of I Papaka

**Cue instrument.** type: do 70%, editorial 10%, event 10%, drink 10% (coverage 33%); format: heritage 80%, opinion 13%, review 7% (coverage 50%); period-stamped titles 0%; roundups 0%; median first-person density 1.9/1000 words.

**Places named in title/lead.** bali 23, uluwatu 2, east-bali 2, central-bali 2, south-bali 1, denpasar 1; 0% name only a place outside bali.

**Co-filed with.** Culture 13; 17 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.68 vs baseline 0.43; leakage 47% (cross-type 20%). Cohesion 0.68 (baseline 0.434), leakage 47% → Cultural Sites (6), Cultural Observer (3), Ceremonies & Festivals (2), Explore Bali (1); best split k=2 silhouette 0.18.
- cluster 1: 17 (57%) `do`/`heritage` — A Bali Myth: Knock-Knock, Who's There?; In the Name of Love: Bali's Notorious 'Love Magic'; No Baby, No Honey : Bali's Pregnancy Myth
- cluster 2: 13 (43%) `do`/`heritage` — Patung Bayi : The Myth of Bali's Crying Baby Statue; The ‘Brave’ Monkeys of Uluwatu Temple: A Bali Myth; The Law Enforcement Deities of Belega Village

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `heritage` · format `heritage` · location `bali` · agrees: True · split: False · confidence high. All titles consistently cover Balinese folklore, myths, and cultural traditions, fitting editorial heritage content rooted in Bali.

### Everyday Bali — resolved (D04, D24)

*30 published · 2017–2026 · parent: Culture · Yoast primary on 27 · slug `everyday-bali` · term 2340*

> Editor's description: Now! Bali is the most popular island magazine. This is all about the latest news about what is happening every day in Bali.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `culture` · format `feature` · location `bali` · topic: culture · confidence **high** · decisions D04, D24

**Resolution.** basis D04, D24; unchanged.

**Reasoning.** Explainers of everyday ritual objects (offerings, udeng, genta).

**Alternates for the classifier.** editorial/heritage + heritage

**Representative titles (spread across the date range).**
- 2017-09-22 · Banten Jotan: An Offering for Good and Evil
- 2020-04-14 · Meru Towers: The Principle Shrine of a Temple
- 2020-08-09 · Udeng : The Traditional Headdress of Balinese Men
- 2024-01-26 · Genta: The Balinese Priest’s Sacred Bell
- 2024-08-08 · Bija: Blessed Grains of Rice
- 2025-03-06 · Segehan: Offerings for the Bhuta Kala
- 2025-12-10 · Kober Dewata Nawa Sanga: Flags of the Nine Guardians
- 2026-07-13 · The Hidden Philosophy of Keben

**Cue instrument.** type: do 38%, editorial 25%, eat 12%, drink 12% (coverage 27%); format: heritage 100% (coverage 33%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 19; 0% name only a place outside bali.

**Coherence** (mixed, against the E2.0 proposal). k=2 split (silhouette 0.19) with clusters disagreeing on type; cross-type leakage 3%. Cohesion 0.777 (baseline 0.434), leakage 7% → People of Bali (1), Cultural Sites (1); best split k=2 silhouette 0.193.
- cluster 1: 19 (63%) `do`/`heritage` — Ulap-Ulap: The Protector of Balinese Buildings; Tedung : Bali's Ceremonial Umbrella; Pratima and Pralingga: Effigies of the Gods
- cluster 2: 11 (37%) `editorial`/`heritage` — Udeng : The Traditional Headdress of Balinese Men; Cili: The Symbol of Beauty and Fertility; Tipat and Bantal: Symbols of the Feminine and Masculine

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `bali` · agrees: True · split: False · confidence high. All titles are cultural explainers on Balinese traditions, offerings, and attire—consistent editorial features rooted in Balinese culture with no need for splitting.

### Made in Bali — resolved (as proposed)

*24 published · 2019–2025 · parent: Features · Yoast primary on 23 · slug `made-in-bali` · term 1771*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type *per article* (prior `shop`) · subtype `artisan` · format `feature` · location `bali` · topic: local-brands · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Local makers: salt, arak, craft beer, seaweed farmers. Mirrors Jakarta Made In Indonesia (shop/artisan when a brand is the subject, else editorial/people).

**Alternates for the classifier.** editorial/people + people; drink/pub\|bar for brewery/distillery pieces

**Representative titles (spread across the date range).**
- 2019-02-10 · Bali Sea Salt : Traditionally Farmed Salt Made in Bali
- 2023-05-23 · Make a Scene Bali: Leaf Weaving in New Dimensions
- 2023-10-03 · Island Brewing: A Bali Craft Beer Brewed for Good Times
- 2023-11-08 · Pande Gong: The Gamelan Makers of Tihingan Village
- 2024-05-07 · Nusa Caña: Reviving the Forgotten Story of Indonesian Rum
- 2024-09-19 · Making Beer in Bali: Inside the Brewery with Island Brewing
- 2024-10-24 · Undagi Tapel: The Mask Carvers of Bali
- 2025-09-04 · Craft Beer in Bali: The Best Local Brews and Brands

**Cue instrument.** type: drink 50%, shop 14%, editorial 14%, do 14% (coverage 58%); format: heritage 69%, listing 8%, people 8%, news 8% (coverage 54%); period-stamped titles 0%; roundups 0%; median first-person density 1.8/1000 words.

**Places named in title/lead.** bali 21, east-bali 2, south-bali 1, nusa-penida 1; 0% name only a place outside bali.

**Co-filed with.** Video 2; 22 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.551 (baseline 0.44), leakage 38% → Video (2), Shopping (1), Myths and Legends (1), Culture (1); best split k=3 silhouette 0.266.
- cluster 1: 13 (54%) `drink`/`heritage` — Marak and Ark: Bali Welcomes Two New Premium Arak Brands; Spirit of Bali: The Rise of Arak; Nusa Caña: Reviving the Forgotten Story of Indonesian Rum
- cluster 2: 8 (33%) `editorial`/`heritage` — Make a Scene Bali: Leaf Weaving in New Dimensions; Threads of Life: The Stories on the Tapestries; Empu Keris: Master Forgers of the Sacred Dagger
- cluster 3: 3 (12%) `drink`/`?` — Craft Beer in Bali: The Best Local Brews and Brands; Island Brewing: A Bali Craft Beer Brewed for Good Times; Making Beer in Bali: Inside the Brewery with Island Brewing

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `bali` · agrees: False · split: True → Crafts & Artisans, Food & Drink Production · confidence high. Category mixes artisan crafts (textiles, keris, gamelan) with food and beverage production (arak, beer, wine, coffee), so type cannot be uniformly shop.

### Bali History — resolved (D24)

*22 published · 2018–2026 · parent: Culture · Yoast primary on 16 · slug `bali-history` · term 2564*

> Editor's description: Now! Bali is packed with the latest news and special features on Bali's history, ceremonies and traditions, arts, culture and lifestyle.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `heritage` · format `heritage` · location `bali` · topic: heritage · confidence **high** · decisions D24

**Resolution.** basis D24; unchanged.

**Reasoning.** Colonial-era history, early tourism, old maps.

**Representative titles (spread across the date range).**
- 2018-11-26 · The Construction of Balinese Hinduism
- 2019-12-30 · Pan Am Monument in Bali : Commemorating a Tragedy
- 2020-09-30 · A Brief History of Sanur: The Birthplace of Bali's Tourism
- 2023-05-29 · Early Travels to the ‘Dutch East Indies’
- 2024-08-01 · The Spice Islands of Indonesia: A Brief History Told Through Old Maps
- 2025-01-16 · The Spice Route's Legacy: How Trade Shaped Traditions in Padang Bai and Tenganan
- 2025-08-28 · Bali 1952: Through the Lens of Liu Kang
- 2026-07-29 · W.O.J. Nieuwenkamp - The First European Artist in Bali

**Cue instrument.** type: do 54%, editorial 46% (coverage 59%); format: heritage 81%, news 10%, city-guide 5%, listing 5% (coverage 96%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 16, sanur 3, north-bali 2, kuta 1, seminyak 1, ubud 1; 4% name only a place outside bali.

**Coherence** (mixed, against the E2.0 proposal). k=2 split (silhouette 0.23) with clusters disagreeing on type; cross-type leakage 18%. Cohesion 0.688 (baseline 0.443), leakage 36% → Cultural Sites (3), Cultural Observer (2), Art In Bali (2), Nature and Outdoors (1); best split k=2 silhouette 0.234.
- cluster 1: 13 (59%) `do`/`heritage` — Early Travels to the ‘Dutch East Indies’; Indonesian Fruits Through the Eyes of Early Explorers and Botanists; Bali Island in Early Photography
- cluster 2: 9 (41%) `editorial`/`heritage` — Early Islam in Bali: A Local Legend; Senduro: The Persistent Shadow of Majapahit over Java and Bali; A History of Islam in Bali: A Story of Tolerance

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `heritage` · format `heritage` · location `bali` · agrees: True · split: False · confidence high. All titles are historical and cultural essays about Bali and broader Indonesian heritage, fitting editorial/heritage with Bali as the consistent geographic anchor.

### Parks and Attractions — resolved (as proposed)

*17 published · 2017–2026 · parent: Explore Bali · Yoast primary on 12 · slug `parks-and-attractions` · term 2566*

> Editor's description: Bali offers the most exciting, immersive, and memorable traveling experiences in Indonesia. Discover parks and attractions on the island and its diverse landscapes, cultural traditions, and rich history.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `do` · subtype `attraction` · format *per article* (prior `guide`) · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Zoos, waterparks, GWK, farms -- attractions.

**Alternates for the classifier.** format review for first-person visits; audience family

**Representative titles (spread across the date range).**
- 2017-04-03 · Bali's Best Parks and Attractions
- 2018-01-17 · A Visit to Kemenuh Butterfly Park
- 2022-01-19 · Bali Safari: Educational Adventure at This Leading Animal Conservation Park
- 2023-07-04 · Trans Studio Bali: Experience Bali's Epic Indoor Theme Park
- 2024-11-18 · The Story Behind Bali’s Biggest Herd
- 2025-01-30 · Bali Farm House: Countryside Charm at Bali’s First Interactive Farm Sanctuary
- 2026-05-12 · Play, Splash, Repeat: Fun Family Days Await at Mookiland Park
- 2026-07-28 · Sliding Into Adventure at Waterbom Bali

**Cue instrument.** type: do 88%, shop 6%, eat 6% (coverage 100%); format: offer 33%, heritage 33%, news 22%, city-guide 11% (coverage 53%); period-stamped titles 0%; roundups 6%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 15, kuta 3, sanur 2, denpasar 1, central-bali 1, ubud 1; 0% name only a place outside bali.

**Co-filed with.** Lifestyle 3, Bali with Kids 2, Shopping 1; 12 carry this category alone.

**Coherence** (mixed, against the E2.0 proposal). k=3 split (silhouette 0.29) with clusters disagreeing on decay class; cross-type leakage 12%. Cohesion 0.66 (baseline 0.454), leakage 18% → Nature and Outdoors (1), Destinations (1), Shopping (1); best split k=3 silhouette 0.29.
- cluster 1: 8 (47%) `do`/`offer` — Funtastic Land: Bali's Biggest Theme Park; Trans Studio Bali: Experience Bali's Epic Indoor Theme Park; A Visit to Kemenuh Butterfly Park
- cluster 2: 5 (29%) `do`/`heritage` — Bali Safari: Educational Adventure at This Leading Animal Conservation; Embark On a Fun-Filled Family Excursion at Bali Zoo; Bali's Best Parks and Attractions
- cluster 3: 4 (24%) `do`/`news` — AeroXSpace: The Ultimate Indoor Playground Experience; AeroXSpace: Bali’s Largest Adrenaline-Fueled Indoor Adventure Park; Play, Splash, Repeat: Fun Family Days Await at Mookiland Park

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `attraction` · format `per-article` · location `bali` · agrees: False · split: False · confidence high. Type and subtype correct, but format varies between guide, feature, and review across titles; one shopping-mall title is an outlier but not enough to warrant a split.

### Winocracy — resolved (D03, D08)

*9 published · 2019–2020 · parent: Archives · Yoast primary on 8 · slug `winocracy` · term 2058*

> Editor's description: Winocracy: Basically, natural wines are ruled by the maximum principle of “nothing is added, and nothing is taken away” - Restaurants and Bars

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype `opinion` · format `opinion` · location `bali` · topic: food-drink; series_key: `column:winocracy` · confidence **high** · decisions D03, D08

**Resolution.** basis D03, D08; unchanged.

**Reasoning.** A wine column (2019-2020): opinion.

**Alternates for the classifier.** drink/wine-bar when a venue is the subject

**Representative titles (spread across the date range).**
- 2019-07-15 · Wines Banned : Indonesia's Struggle with Imported Wines
- 2019-08-19 · A Cup of Wine Please
- 2019-09-06 · The Art of Sleeping During Wine Dinners
- 2019-10-19 · The Art of Drinking Alone
- 2019-12-16 · The End of Christmas
- 2020-02-23 · What I Hate About Wine
- 2020-03-17 · More is Less, Sometimes
- 2020-05-16 · Wine for Corona Times

**Cue instrument.** type: drink 86%, shop 14% (coverage 78%); format: review 75%, opinion 25% (coverage 89%); period-stamped titles 11%; roundups 0%; median first-person density 30.9/1000 words.

**Co-filed with.** Restaurants and Bars 9; 0 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.84 vs baseline 0.50; leakage 0% (cross-type 0%). Cohesion 0.84 (baseline 0.499), leakage 0%; best split k=2 silhouette 0.148.
- cluster 1: 5 (56%) `drink`/`review` — The Usual Suspects; Wine for Corona Times; The Art of Drinking Alone
- cluster 2: 4 (44%) `drink`/`review` — More is Less, Sometimes; Wines Banned : Indonesia's Struggle with Imported Wines; What I Hate About Wine

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `opinion` · format `opinion` · location `bali` · agrees: True · split: False · confidence high. Titles are personal opinion essays on wine culture and drinking habits, clearly editorial/opinion content tied to Bali publication.

### Behind the Bar — resolved (D08)

*7 published · 2019–2026 · parent: Bar Guide · Yoast primary on 7 · slug `behind-the-bar` · term 2250*

> Editor's description: This article and video series by NOW! Bali shares insight behind the scenes of Bali's most popular bars. From the island's best mixologists, sommeliers, flair bartenders and more, we explore the ways of these talented food and beverage professionals.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `drink` · subtype `cocktail-bar` · format *per article* (prior `people`) · location `bali` · series_key: `column:behind-the-bar` · confidence **high** · decisions D08

**Resolution.** basis D08; unchanged.

**Reasoning.** Mixologist profiles and craft-spirit launches; child of Bar Guide.

**Alternates for the classifier.** format news for product launches (East Indies Gin)

**Representative titles (spread across the date range).**
- 2019-11-08 · Arey Barker : For Fig's Sake
- 2019-11-08 · Ayip Dzuhri : Samudra
- 2019-11-08 · Yudi Hendarsyah : Smoke & Fog
- 2019-11-11 · Yudhistira Racik : Cristalized Angel
- 2021-11-11 · Nusantara Cold Brew: Indonesia’s First Craft Coffee Liqueur Sits on the Top Shelf
- 2021-11-24 · East Indies Gin Debuts as Indonesia’s First Authentic Distilled Craft Gin, Made in Bali
- 2026-03-16 · Bali’s Award-Winning Mixologists

**Cue instrument.** type: drink 100% (coverage 71%); format: news 100% (coverage 43%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 4, seminyak 1; 0% name only a place outside bali.

**Co-filed with.** Restaurants and Bars 3, Video 3; 4 carry this category alone.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `drink` · subtype `cocktail-bar` · format `people` · location `bali` · agrees: True · split: False · confidence high. Series profiles bar professionals and their creations; titles are person-centric with drink names, fitting people format under drink type with Bali scope.

### Features — resolved (D27)

*3 published · 2020–2026 · top-level · Yoast primary on 2 · slug `features` · term 2561*

> Editor's description: NOW! Bali Features is a simple site that is designed to provide information about people and activities in Bali, Indonesia.

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `editorial` · subtype *per article* · format `feature` · location `bali` · - · confidence **medium** · decisions D27

**Resolution.** basis D27; unchanged.

**Reasoning.** 3 posts; long-form. Subtype per article.

**Representative titles (spread across the date range).**
- 2020-05-08 · Innovation to the Rescue: Fighting Covid with Technology
- 2026-01-09 · Bali-Inspired Wellness Programmes & Experiences
- 2026-08-27 · A Moon on Water: How Two Design Teams, A Sea Apart, Shaped the Building of SAKA

**Cue instrument.** type: wellness 50%, do 50% (coverage 67%); format: heritage 100% (coverage 67%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 3; 0% name only a place outside bali.

**Coherence.** 3 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `bali` · agrees: True · split: False · confidence high. Diverse feature articles on Bali people and activities; type and format are clearly editorial/feature, subtype varies per article, location is consistently Bali.

### Offers — resolved (D27, D02)

*1 published · 2025–2025 · top-level · Yoast primary on 1 · slug `offers` · term 2580*

**Resolved prior** (evidence-pack proposal (Bali has no E1.4 draft)): type `stay` · subtype *per article* (prior `hotel`) · format `offer` · location `bali` · - · confidence **high** · decisions D27, D02

**Resolution.** basis D27, D02; unchanged.

**Reasoning.** 1 post (a festive package). Same prior as Jakarta's Offers parent (stay/hotel + offer).

**Representative titles (spread across the date range).**
- 2025-12-18 · Ring in a Clifftop Festive Season at The Ungasan

**Cue instrument.** type: stay 100% (coverage 100%); format: offer 100% (coverage 100%); period-stamped titles 100%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** uluwatu 1; 0% name only a place outside bali.

**Coherence.** 1 members with vectors (< 8); read the titles instead.

### Mapping Bali — empty

*0 published · no articles · parent: Archives · Yoast primary on 0 · slug `mapping-bali` · term 233*

> Editor's description: Mapping Bali, an intriguing perspective and angle on people, place and culture. Stay connected on our website and don’t miss any new stories.

No published articles carry this category. Nothing to map.

### Archives — empty

*0 published · no articles · top-level · Yoast primary on 0 · slug `archives` · term 2574*

> Editor's description: Discover our archives : all about Home Life, Movies, Health & Wellness, Music, Recipes, Restaurant & Bars, and many more here!

No published articles carry this category. Nothing to map.

---
*Generated from one in-memory model by `now-taxonomy-evidence build`; regenerate rather than hand-edit. Answers live in `src/now_taxonomy_evidence/resolutions.py`; cache: `engine/packages/taxonomy-evidence/.cache/`.*

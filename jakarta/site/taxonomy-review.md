# NOW! Jakarta — taxonomy review: evidence pack (resolved)

**Status: RESOLVED — Hansel's answers to all 27 decisions applied on 2026-09-10; this file and its JSON twin are E2.1's input.** Generated 2026-09-10T03:14:29+00:00 by `engine/packages/taxonomy-evidence 0.2.0`. Builds on E1.4's draft (`jakarta/site/taxonomy-mapping.md`) and the E2.0 evidence (kept in full below: every instrument reading was taken against the E2.0 proposal, which each category still shows as `e20_proposal`). The machine-readable twin `taxonomy-review.json` is rendered from the same in-memory model as this file.

## How to read this

- **§1** lists the 19 decisions that touch this city (of 27 across both cities; shared ids are identical in `bali/site/taxonomy-review.md`) with the evidence, the E2.0 recommendation, and **the answer** — 12 explicit (D01, D02, D06, D08, D09, D10, D14, D15, D16, D21, D22, D26), the rest the recommendation accepted as-is. Every conflict between an answer and a recommendation is stated under the decision, never reconciled silently.
- **§2** lists the categories the *data* flagged and how each flag was resolved (Hansel's answer for mixed categories: classify per article, no fixed category-wide type). **§3** is the coherence evidence, computed against the E2.0 proposal. **§4** is the vocabulary check; the reviewed change list lives in `engine/packages/taxonomy-evidence/vocabulary-delta.md`. **§5** calibrates the instruments. **§7** is the set of cross-cutting classifier rules the policy answers produce, including how `international` is encoded.
- **Appendix A** is every resolved mapping (75 categories, the 3 that changed against E2.0 first). **Appendix B** has the full evidence and the resolution for every category.
- Vectors for jakarta: `embeddings:BAAI/bge-small-en-v1.5`. Real `BAAI/bge-small-en-v1.5` article embeddings (filtered `WHERE model = :model`, F42).
- LLM second opinion: llm second opinion: glm-5.2 via https://ollama.com/v1 (120/120 categories answered; responses cached in .cache/llm). The LLM can only add flags; it never auto-accepts anything.

### Counts

| | |
|---|---|
| Articles | 4,772 |
| Categories (with ≥1 published article) | 75 of 76 |
| Decisions touching this city (resolved / total) | 19 / 19 |
| Categories still awaiting a decision | 0 |
| Categories resolved | 75 |
| … of which changed against the E2.0 proposal | 3 |
| Categories that were flagged before resolution (decision-needed or by evidence) | 7 |
| Empty categories | 1 |

## 1. Decisions — all resolved — ordered by articles affected

| # | decision | kind | articles | answer | source |
|---|---|---|---:|---|---|
| D02 | Legacy offers and events have no end date | policy | 2,178 | Extract the real end date from the text where one is present; otherwise an offer expires at publish + 90 days and an event at publish + 30 days. Expired items stay searchable and never enter a rail. | explicit |
| D04 | Approve `editorial/culture` (subtype) | vocabulary | 869 | Approve the `editorial/culture` subtype. | as-recommended |
| D12 | Approve the proposed event subtypes: `performance`, `screening`, `pop-up` | vocabulary | 811 | Approve the event subtypes `performance`, `screening` and `pop-up`. | as-recommended |
| D13 | Approve the proposed wellness subtypes: `salon`, `retreat` | vocabulary | 551 | Approve the wellness subtypes `salon` and `retreat`. | as-recommended |
| D05 | Approve `editorial/lifestyle` (subtype) | vocabulary | 449 | Approve the `editorial/lifestyle` subtype. | as-recommended |
| D25 | Bali 'Art In Bali' (136) and Jakarta 'Art' (244): type/format per article, topic art | mapping | 380 | Jakarta Art and Bali Art In Bali: no type/format prior; topic `art`; the classifier decides among the listed alternates. | as-recommended |
| D17 | Experience Offers (both cities): hotel-experience packages, not a `do` category | mapping | 335 | Experience Offers (both cities): format `offer` fixed; type per article with `stay/hotel` as the prior; the classifier may pick eat, wellness, do or event. Not a `do` category. | as-recommended |
| D03 | Approve the proposed `opinion` format | vocabulary | 328 | Approve the `opinion` format (540-day half-life). | as-recommended |
| D14 | Location tree: approve E1.4's proposed nodes and the corpus-found gaps | vocabulary | 327 | Add every corpus location term with >= 20 mentions (Bali 14, elsewhere in Indonesia 12, international 22, Jakarta 11 candidates -- vocabulary-delta.json lists each with its counts and the node-vs-alias call); below 20 stays out. Drop `location/rawamangun` (2 mentions). Trim the homonym-inflated aliases `Batu` (malang) and `Wijaya` (gunawarman); title-case-only matching for `solo` and `kuningan`. | explicit ⚠ conflict |
| D19 | Community (both cities): `news` or `feature` as the format prior? | mapping | 302 | Community (both cities): format prior `feature`; the classifier switches to `event` (dated fundraisers) or `news` (announcements) when the text says so; topic `community` always. | as-recommended |
| D01 | Guide vs listing boundary (cross-cutting) | policy | 233 | Period-stamped roundups (a year in the title, '[Updated]', a seasonal marker) are `listing`: 540-day half-life, a `series_key`, and only the current member of a series is eligible in any rail. Timeless how-to and area pieces stay evergreen `guide`. | explicit |
| D10 | Multi-category resolution order: Yoast primary > most specific child > parent container | policy | 213 | Prior resolution order for a multi-category post: the Yoast primary category, else the deepest (most specific) child category, else the parent container. | explicit |
| D07 | Print-issue categories carry no facets | policy | 201 | Print-issue categories carry no facets: `series_key = issue:<slug>`, format prior `feature`, everything else from content. | as-recommended |
| D26 | Jakarta 'Business' (186): a fifth are hotel corporate announcements | mapping | 186 | Jakarta Business: type per article -- no fixed category-wide type. editorial/business stays the prior; stay/hotel or eat/restaurant when a venue is the subject; format per article. | explicit |
| D09 | Uncategorized (both cities) -> review queue; non-articles excluded | policy | 154 | Migrate everything and classify best-effort: no prior from Uncategorized, the classifier decides every facet, and the standard E2.1 confidence gate applies (below the auto-apply threshold -> review queue, never written as fact). Nothing is excluded. | explicit ⚠ conflict |
| D06 | Approve the `international` location root | vocabulary | 153 | Add the `international` location root, editorial-only: searchable and eligible for Row 3 (related reading); never Row 1 (complementary places), never Row 2 (nearby), never the itinerary builder. | explicit ⚠ conflict |
| D11 | Approve `do/sports-activity` (subtype) | vocabulary | 61 | Approve `do/sports-activity`; the classifier picks among do/sports-activity, event/sports and an editorial feature per article. | as-recommended |
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

### D07 · Print-issue categories carry no facets

*kind: policy · articles affected: 201 · carried from E1.4 #15 · cities: jakarta · status: resolved*

**Question.** 34 Jakarta categories are themes of individual 2019-2020 print issues (~205 posts, 2-10 each). Proposed: no facet mapping; `series_key = issue:<slug>`; format prior `feature`; classifier assigns everything else from content.

**Affects.** jakarta: Love & Romance 2020 (10), jakarta: Food The Music Of Love (10), jakarta: A Jakarta Smorgasbord (10), jakarta: Indonesia S Creative Soul (9), jakarta: Property Architecture Design (9), jakarta: Art Culture The Realm Of Contemporary Arts (8), jakarta: Music & Nightlife (8), jakarta: Capital Of Culture (7), jakarta: Its A Man's World (7), jakarta: Tech Talk (7), jakarta: Staying Successful In Times Of Challenge (7), jakarta: The Rhythm Of Life (7), jakarta: Staying In Style (6), jakarta: Season Of Love (6) …

**Evidence.**
- 34 print-issue categories, 201 posts; by year: 2019: 159, 2020: 37, 2022: 1, 2024: 1, 2026: 3
- 197 of those posts carry no other category -- no second prior exists

**E2.0 recommendation.** Confirm. One decision retires 34 categories.

**Options.** confirm (recommended) · map each theme to a topic anyway

**Resolved (as-recommended, Hansel 2026-09-10).** Print-issue categories carry no facets: `series_key = issue:<slug>`, format prior `feature`, everything else from content.

*Option: confirm.* One decision retires 34 categories that were themes of individual 2019-2020 issues.

**Applied.** rules.print_issues · 34 Jakarta print-issue categories resolved

### D26 · Jakarta 'Business' (186): a fifth are hotel corporate announcements

*kind: mapping · articles affected: 186 · cities: jakarta · status: resolved*

**Question.** E1.4: editorial/business + feature (MEDIUM). The cue instrument reads 19% as `stay` (hotel openings, GM appointments, joint ventures filed under Business) and format splits news/feature/opinion. Proposed: keep editorial/business as the prior but let type switch to stay/eat when a venue is the subject; format per article.

**Affects.** jakarta: Business (186)

**Evidence.**
- jakarta 'Business' (186): type cues editorial 51%, stay 26%, eat 6%, shop 6% (coverage 74%); format cues news 33%, listing 13%, people 11%, offer 11% (coverage 55%)
- jakarta 'Business' clusters (embeddings:BAAI/bge-small-en-v1.5, k=2, silhouette 0.117): 59% [editorial/listing] e.g. AmCham Indonesia: Connecting Companies and Finding Solutions; An Interview with H.E. Stig Traavik, Ambassador of Norway to | 41% [stay/news] e.g. Dan Benzaquen: Hospitality at Heart; A Milestone For Ayana Resort and Spa Bali

**E2.0 recommendation.** Accept type-switchable prior; format per article.

**Options.** accept (recommended) · keep E1.4 as-is

**Resolved (explicit, Hansel 2026-09-10).** Jakarta Business: type per article -- no fixed category-wide type. editorial/business stays the prior; stay/hotel or eat/restaurant when a venue is the subject; format per article.

*Option: accept type-switchable prior; format per article -- strengthened to type per article.* Hansel: classify mixed categories per article; a fixed `editorial` type would leave hotel corporate announcements un-excluded on competitor pages.

**Applied.** jakarta Business: per_article type, subtype, format

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

### D11 · Approve `do/sports-activity` (subtype)

*kind: vocabulary · articles affected: 61 · carried from E1.4 #9 · cities: jakarta · status: resolved*

**Question.** Participatory sport venues and clubs (padel centres, climbing gyms, running clubs) versus `event/sports` (a dated fixture) versus features about sport. Jakarta Sports & Activities (61) mixes all three; Bali has the same mix inside Community/Activities.

**Affects.** jakarta: Sports & Activities (61)

**Evidence.**
- 1 categories / 61 articles depend on this approval: jakarta:Sports & Activities (61)
- corpus mentions -- golf course/club: 68; padel/tennis: 18; climbing: 15; running club: 2

**E2.0 recommendation.** Approve and let the classifier pick among the three.

**Options.** approve (recommended) · reject -> do/adventure or wellness/gym

**Resolved (as-recommended, Hansel 2026-09-10).** Approve `do/sports-activity`; the classifier picks among do/sports-activity, event/sports and an editorial feature per article.

*Option: approve.* Participatory sport venues have no other node.

**Applied.** vocabulary-delta: approve subtype/sports-activity (already seeded; already in enum_places_subtype)

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

- **Reviews** (230 articles; was `flagged-by-evidence`) — E2.0 proposal `eat`/`restaurant` + `review` @ `jakarta` → resolved ***per article* (prior `eat`)/*per article* (prior `restaurant`) + `review` @ `jakarta`**. Basis: mixed-categories.
  - flag: clusters split the category: k=2 split (silhouette 0.14, smallest cluster 23%) whose clusters read as different venue types (drink, eat) while the proposal fixes type=eat; 14% of members sit closer to a category of another type
  - resolution: Format `review` stays fixed (not flagged). Type eat/restaurant is the prior.
- **Business** (186 articles; was `decision-needed`) — E2.0 proposal `editorial`/`business` + *per article* (prior `feature`) @ `jakarta` → resolved ***per article* (prior `editorial`)/*per article* (prior `business`) + *per article* (prior `feature`) @ `jakarta`**. Basis: D26, mixed-categories.
  - flag: clusters split the category: k=2 split (silhouette 0.12, smallest cluster 41%) whose clusters read as different venue types (editorial, stay) while the proposal fixes type=editorial; 22% of members sit closer to a category of another type
  - resolution: editorial/business stays the prior; the classifier may switch to a venue type. Format per article between feature/news/opinion.
- **Features** (20 articles; was `flagged-by-evidence`) — E2.0 proposal `editorial`/*per article* + `feature` @ `jakarta` → resolved ***per article* (prior `editorial`)/*per article* + `feature` @ `jakarta`**. Basis: mixed-categories, D10.
  - flag: cue instrument disagrees on type: proposal fixes `editorial` but 50% of signal-bearing articles read as `eat` (only 25% as `editorial`) -- this changes competitor exclusion
  - resolution: Format `feature` stays fixed; the container rule (D10) applies when a child category is present.

## 3. Internal consistency — categories that are not one thing

Vector space: `embeddings:BAAI/bge-small-en-v1.5`. A category is **incoherent** when k-means finds a split whose clusters read as different *venue* types while the proposal fixes one type (this changes competitor exclusion), or as formats with different decay classes while the proposal fixes one format — a split candidate, not a mapping problem. **mixed** is a weaker signal (clusters differ on non-venue types, or members sit closer to categories of another type). **expected-heterogeneous** means the proposal already leaves type per article (News, Events, containers, print issues), so heterogeneity is by design and the clusters are useful as classifier priors.

Verdicts were computed against the **E2.0 proposal**. Where the resolution made the flagged facet per article, the split is now by design — marked *↳ resolved* below.

| verdict | categories |
|---|---|
| incoherent | 2: Reviews, Business |
| mixed | 2: World Traveller, Restaurant Guides |
| expected-heterogeneous | 25: Features, Art, Experience Offers, Uncategorized, News, Explore Indonesia, Bali Updates, Health, Sports & Activities, Offers, Green Living, Kids & Family, Art & Culture, Discover Jakarta, Dining, Travel, City Guides, Lifestyle … |
| coherent | 19: Community, Dining Offers, Events, Dining News, Stay Offers, Education, Opinion, Shopping, NOW! People, History & Heritage, Culture, Music, Made In Indonesia, Film, Bar Guide, Design, Hidden Heritage, Sites & Destinations … |
| too-small | 28: Capital Of Culture, Its A Man's World, Tech Talk, Staying Successful In Times Of Challenge, The Rhythm Of Life, Staying In Style, Season Of Love, Architecture Property & Design, Travel & Holiday, The Culinary Issue, Building Future Leader, Jakarta S Music & Nightlife, The Festive Season, Travels Far & Near, Festive Issue, Health In An Era Of Urbanisation, Season Of Wonders, In With The New … |

### Split candidates

#### Reviews — incoherent · 230 articles · E2.0 proposal `eat` + `review`

k=2 split (silhouette 0.14, smallest cluster 23%) whose clusters read as different venue types (drink, eat) while the proposal fixes type=eat; 14% of members sit closer to a category of another type. Cohesion 0.792 vs random baseline 0.754 (ratio 1.05); leakage 62% → Dining News (49), Dining (18), Bar Guide (14), Dining Offers (11).

*↳ resolved:* *per article* (prior `eat`)/*per article* (prior `restaurant`) + `review` @ `jakarta` (mixed-categories).

- **Cluster 1** — 177 articles (77%); cue type `eat` 90%, cue format `news` 39%; words: cuisine, dining, flavours, food, chef, restaurant
  - 2019-12-21 · Finest Indulgence of Local Delicacies at The Café — Hotel Mulia Senayan
  - 2022-09-12 · Celebrating Indonesian Delicacies
  - 2019-01-04 · New Deliciousness at The Dutch
  - 2019-01-04 · JW Marriott Jakarta Presents Authentic Peruvian Cuisine by Guest Chef Eduardo
- **Cluster 2** — 53 articles (23%); cue type `drink` 48%, cue format `news` 30%; words: wines, taste, starbucks, coffee, beer, wine
  - 2019-01-04 · Bellissimo Wines Hits the High Notes, in Both Flavor and Price
  - 2019-02-13 · Introducing the Diamond of The Culinary World
  - 2019-04-26 · Taste Australia: Australian Grapes Now Available in Indonesian Supermarkets
  - 2024-01-12 · Review: Wine Spectator’s Top 100 Wines of 2023

#### Business — incoherent · 186 articles · E2.0 proposal `editorial` + *per article*

k=2 split (silhouette 0.12, smallest cluster 41%) whose clusters read as different venue types (editorial, stay) while the proposal fixes type=editorial; 22% of members sit closer to a category of another type. Cohesion 0.767 vs random baseline 0.754 (ratio 1.02); leakage 61% → Stay Offers (26), NOW! People (15), News (13), Green Living (12).

*↳ resolved:* *per article* (prior `editorial`)/*per article* (prior `business`) + *per article* (prior `feature`) @ `jakarta` (D26, mixed-categories).

- **Cluster 1** — 109 articles (59%); cue type `editorial` 87%, cue format `listing` 19%; words: business, britcham, economic, ambassador, industry, sustainable
  - 2019-01-04 · AmCham Indonesia: Connecting Companies and Finding Solutions
  - 2019-02-13 · An Interview with H.E. Stig Traavik, Ambassador of Norway to Indonesia
  - 2019-01-04 · Strengthening Economic Ties Between Indonesia and Germany
  - 2019-07-12 · Canada Chamber of Commerce: Encouraging Economic Relations
- **Cluster 2** — 77 articles (41%); cue type `stay` 57%, cue format `news` 51%; words: hotel, residence, starbucks, culture, opens, group
  - 2019-10-07 · Dan Benzaquen: Hospitality at Heart
  - 2019-02-13 · A Milestone For Ayana Resort and Spa Bali
  - 2019-01-04 · The Hermitage Hotel, Jakarta Announces New General Manager
  - 2019-02-13 · Luxury Business Hotel at Its Best

#### World Traveller — mixed · 94 articles · E2.0 proposal `editorial` + `city-guide`

cohesion 0.75 is no higher than the random baseline 0.76 for a set this size. Cohesion 0.753 vs random baseline 0.756 (ratio 1.0); leakage 23% → Art (4), Dining News (3), Travel (3), Business (2).

- **Cluster 1** — 64 articles (68%); cue type `do` 45%, cue format `city-guide` 32%; words: city, around, world, destination, hong, kong
  - 2019-01-04 · The Flying Affairs
  - 2019-01-04 · Summer, Winter, Spring   and Autumn in Hong Kong
  - 2019-01-04 · Cruising Into The Heart of Bavaria
  - 2019-01-04 · The Cross Cultural Buzz of Istanbul
- **Cluster 2** — 30 articles (32%); cue type `event` 30%, cue format `heritage` 28%; words: singapore, hong, kong, korea, art, festival
  - 2019-01-04 · Sparkling Singapore
  - 2019-01-04 · Get Lost in Singapore
  - 2019-01-04 · Living Like A Local in Singapore
  - 2019-02-13 · A Sanctuary in the City of Bliss

#### Restaurant Guides — mixed · 17 articles · E2.0 proposal `eat` + *per article*

k=2 split (silhouette 0.13) with clusters disagreeing on decay class; cross-type leakage 0%. Cohesion 0.862 vs random baseline 0.771 (ratio 1.12); leakage 12% → Dining Offers (1), Dining (1).

- **Cluster 1** — 11 articles (65%); cue type `eat` 100%, cue format `offer` 62%; words: best, restaurants, weekend, indulgence, brunch, ultimate
  - 2023-07-12 · Best Brunch in Jakarta: The Ultimate Weekend Indulgence
  - 2025-10-03 · Brunches in Jakarta: A Most-Welcome Weekend Ritual
  - 2024-03-01 · Steak in Jakarta: The Best Steakhouses and Grill Restaurants
  - 2024-02-12 · Destination Dim Sum: Jakarta's Favourite Cantonese Cuisine
- **Cluster 2** — 6 articles (35%); cue type `eat` 83%, cue format `listing` 50%; words: restaurants, best, chinese, updated, openings, latest
  - 2025-11-12 · New Restaurants in Jakarta 2025: Latest Openings [Updated]
  - 2025-01-07 · New Restaurants in Jakarta 2024: Latest Openings [Updated]
  - 2024-01-12 · Best Chinese Restaurants in Jakarta (2024): Authentic and Elevated Chinese Cuisine
  - 2026-02-09 · Where to Celebrate Chinese New Year in Jakarta 2026: Dining, Hampers and Stays

### Expected-heterogeneous categories, largest first (clusters = classifier priors)

#### Art — expected-heterogeneous · 244 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.791 vs random baseline 0.754 (ratio 1.05); leakage 34% → Culture (18), Art & Culture (15), Indonesia S Creative Soul (7), Events (7).

- **Cluster 1** — 108 articles (44%); cue type `event` 57%, cue format `event` 50%; words: art, exhibition, artist, life, presents, solo
  - 2019-01-04 · Deciphering life at “The Meeting Point”, Celebration Art Palette of Eight Painters
  - 2019-12-16 · Artistic Connection Across Generations
  - 2025-08-14 · Wirantawan: Art As a Search For Oneness
  - 2019-01-04 · Legacies: Real and Imagined, The Artwork of Adam de Boer and Jumaldi Alfi
- **Cluster 2** — 87 articles (36%); cue type `event` 58%, cue format `event` 51%; words: art, artists, arts, exhibition, contemporary, world
  - 2024-09-22 · Art Jakarta 2024: Presenting the Best of Indonesian & Regional Contemporary Art
  - 2019-01-04 · Connecting Jakarta to the Global Art World
  - 2023-11-09 · ART Jakarta 2023: Southeast Asia's Premier Art Fair Returns This November
  - 2019-01-04 · Art Stage Jakarta Builds Bridge Between Indonesia and Global Art World
- **Cluster 3** — 49 articles (20%); cue type `do` 42%, cue format `heritage` 74%; words: art, gallery, history, maps, collection, antique
  - 2019-04-16 · Exploring Our Art in Various Collections Abroad
  - 2019-01-04 · Bartele Gallery Jakarta: Rare Antique Maps, Prints and Books of Indonesia
  - 2019-05-24 · Art Archives and the Exhibition-based Approach of Art History
  - 2019-01-04 · Highlighted "World Spirit", Presidential Art Collection on Display at National Gallery

#### Experience Offers — expected-heterogeneous · 207 articles · E2.0 proposal *per article* + `offer`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.807 vs random baseline 0.754 (ratio 1.07); leakage 73% → Bali Updates (35), Dining Offers (30), Stay Offers (28), Offers (24).

- **Cluster 1** — 82 articles (40%); cue type `stay` 47%, cue format `offer` 80%; words: hotel, ramadan, offers, day, special, experience
  - 2024-02-23 · Enjoy a Blissful Ramadan with Pullman Jakarta Indonesia’s Seasonal Offers
  - 2024-03-08 · The Westin Jakarta Presents Serene Stays and Culinary Delights for Blissful Ramadan Celebrations
  - 2024-02-23 · Hotel Indonesia Kempinski Jakarta's Celebratory Ramadan Experiences
  - 2023-02-09 · Experience the Flavours of Love at Pullman Jakarta Indonesia
- **Cluster 2** — 68 articles (33%); cue type `stay` 51%, cue format `offer` 78%; words: resort, wellness, hotel, spa, experience, stay
  - 2019-09-04 · Wellness Getaway at Tirta Ayu Spa
  - 2020-06-25 · Save Now, Stay Later: Indulgence Awaits at The Laguna, a Luxury Collection Resort & Spa Bali
  - 2019-03-25 · Leisure in a Special Buy One Get One Promotion at The Stones – Legian, Bali
  - 2019-02-13 · Sofitel Bali Nusa Dua Beach Resort is the Perfect Choice for Your Next Bali Holiday
- **Cluster 3** — 57 articles (28%); cue type `stay` 61%, cue format `offer` 94%; words: festive, year, hotel, season, pullman, celebrate
  - 2022-12-08 · JW Marriott Hotel Jakarta Offers Festive Holiday Sparkles
  - 2023-12-22 · Celebrate the Magical Festive Season at HARRIS Hotel & Convention Kelapa Gading Jakarta
  - 2024-12-13 · Celebrate the Festive Season in Style at Gran Meliá Jakarta
  - 2023-11-20 · Pullman Jakarta Indonesia’s Festive Feasts and Treats

#### Uncategorized — expected-heterogeneous · 83 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.726 vs random baseline 0.757 (ratio 0.96); leakage 81% → Health (9), Opinion (8), Community (5), Business (5).

- **Cluster 1** — 42 articles (51%); cue type `editorial` 46%, cue format `news` 35%; words: day, national, hotel, chef, skal, village
  - 2020-06-08 · #CookingFromHome with Chef Adrian Aditya
  - 2020-12-10 · Our New Column – Share Your Thoughts With Jakarta!
  - 2019-01-04 · Starbucks Promotes Indonesia’s Cultural Heritage
  - 2019-01-04 · French-Indonesian Organisation PER Supports Street Children
- **Cluster 2** — 41 articles (49%); cue type `wellness` 50%, cue format `opinion` 60%; words: home, time, banana, songs, music, life
  - 2020-05-23 · COVID-19: Wellbeing Management
  - 2020-05-01 · “I Learned New Life Skill during Self-Quarantine”. Have You?
  - 2020-04-16 · William Wongso’s Cooking at Home: Tips & Tricks!
  - 2020-04-23 · Quality Family Time with Lots of Fun Activities

#### News — expected-heterogeneous · 551 articles · E2.0 proposal *per article* + `news`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.763 vs random baseline 0.753 (ratio 1.01); leakage 84% → Stay Offers (61), Business (56), Events (50), Community (26).

- **Cluster 1** — 308 articles (56%); cue type `stay` 53%, cue format `news` 63%; words: hotel, opens, artotel, celebrates, ascott, hospitality
  - 2023-10-10 · The Westin Jakarta Earns Title of Indonesia’s Leading Business Hotel 2023
  - 2026-07-22 · Ascott Menteng Jakarta Unveils New Experiences Across the Property
  - 2025-10-28 · Gran Melia Jakarta Recognised for Excellence as Indonesia’s Leading Business Hotel 2025
  - 2022-11-28 · The Dharmawangsa Jakarta Celebrates 25th Anniversary
- **Cluster 2** — 243 articles (44%); cue type `editorial` 60%, cue format `news` 39%; words: business, international, world, mvb, festival, celebrates
  - 2023-10-04 · Calling all Jakarta Runners to Join ‘Road to Give’, Marriott International’s Annual Charity Fun Run
  - 2019-07-01 · Sharing in the Spirit of Ramadan
  - 2019-01-04 · Most Valued Businesses Celebrate Sustainability in Indonesia
  - 2019-01-04 · Fun Afternoon at NOW! Jakarta PR Gathering 2016

#### Explore Indonesia — expected-heterogeneous · 154 articles · E2.0 proposal `editorial` + `city-guide`

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.785 vs random baseline 0.755 (ratio 1.04); leakage 60% → Hidden Heritage (12), Stay Offers (10), Offers (9), Bali Updates (7).

- **Cluster 1** — 90 articles (58%); cue type `do` 67%, cue format `heritage` 59%; words: java, culture, east, lombok, bandung, journey
  - 2019-01-04 · Falling Under West Java's Spell
  - 2019-01-04 · History, Natural Beauty and Wildlife in East Java
  - 2019-01-04 · Javan Jaunts
  - 2019-04-10 · In the Heart of Java, Yogyakarta and Solo Offer a Wealth of Cultural Experiences
- **Cluster 2** — 64 articles (42%); cue type `stay` 33%, cue format `offer` 42%; words: resort, hotel, festival, beach, bali's, pullman
  - 2019-01-04 · Five Reasons to Visit Bali This Month
  - 2019-01-04 · Chapung Sebali Resort and Spa: Ubud's Fusion Flavours and Valley Views
  - 2019-01-04 · A Festive Time in Bali
  - 2019-02-13 · Stress-Free Stay at Sol Beach House Benoa

#### Bali Updates — expected-heterogeneous · 111 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.809 vs random baseline 0.755 (ratio 1.07); leakage 30% → Stay Offers (6), Dining News (5), Events (5), Health (4).

- **Cluster 1** — 53 articles (48%); cue type `stay` 64%, cue format `offer` 86%; words: resort, festive, nusa, dua, beach, escape
  - 2025-11-11 · Celebrate the Festive Season in Whimsical Harmony at The Westin Resort Nusa Dua, Bali
  - 2022-11-17 · Light Up Your Festive Holiday at Meliá Bali
  - 2023-12-14 · Paradise Extravaganza: Dazzling Year-End Celebrations at InterContinental Bali Resort
  - 2023-11-09 · Embark on a Sun-Kissed Festive Escape at Meliá Bali
- **Cluster 2** — 43 articles (39%); cue type `eat` 38%, cue format `news` 37%; words: ubud, wellness, como, restaurant, festival, club
  - 2020-01-17 · Embrace the Spirit of the Lunar New Year at COMO Uma Ubud
  - 2025-10-20 · Samsara Ubud Awarded ONE KEY by the Michelin Guide 2025
  - 2020-01-17 · Celebrate Lunar New Year at the Stylish COMO Uma Canggu
  - 2024-03-14 · BaliSpirit Festival Returns for its 15th Edition
- **Cluster 3** — 15 articles (14%); cue type `stay` 46%, cue format `offer` 79%; words: karma, kandara, days, year-end, programme, dance
  - 2024-11-14 · Karma Kandara's '12 Days of Karma' Promises Extravagant Year-End Festivities
  - 2022-11-15 · 12 Days of Karma: Karma Kandara’s Epic Year-End Programme
  - 2023-11-17 · 12 Days of Karma: The Ultimate Festive Season Programme at Karma Kandara
  - 2023-06-09 · Karma Kandara’s Summer Escape Packages Invite for a Sunny Bali Getaway

#### Health — expected-heterogeneous · 99 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.772 vs random baseline 0.756 (ratio 1.02); leakage 24% → Shopping (4), Sports & Activities (3), Community (3), Travel (2).

- **Cluster 1** — 64 articles (65%); cue type `wellness` 83%, cue format `news` 32%; words: spa, wellness, beauty, celebrating, skin, yoga
  - 2019-01-04 · Refresh and Revitalise at Spa Houses that Inspired by Nature & Traditional Technique
  - 2025-08-25 · 10 Best Spas in Jakarta: Top Massage & Wellness Centres
  - 2019-02-13 · Javanese Face Lift Massage Enhances Natural Beauty
  - 2019-06-17 · Jakarta’s Yoga Community Celebrates Global Wellness Day
- **Cluster 2** — 35 articles (35%); cue type `wellness` 69%, cue format `opinion` 36%; words: healthy, cancer, diabetes, breast, lifestyle, against
  - 2019-01-04 · Stunting in Indonesia: What is it and how to prevent it?
  - 2019-01-04 · Diabetes It's All About A Healthy Lifestyle
  - 2019-05-22 · Planning to Move to Indonesia? Make Sure You Have These Five Vaccines!
  - 2019-01-04 · Stand Up Against Cancer

#### Sports & Activities — expected-heterogeneous · 61 articles · E2.0 proposal *per article* + *per article*

the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.789 vs random baseline 0.759 (ratio 1.04); leakage 18% → Health (7), Community (1), Opinion (1), Education (1).

- **Cluster 1** — 36 articles (59%); cue type `event` 33%, cue format `listing` 46%; words: cup, golf, asian, football, tournament, masters
  - 2019-02-13 · Indonesia Raya: Triumph in the All Asia Cup 2016
  - 2019-01-04 · Gearing up for Indonesia Ultimate Golf Series 2016-2017
  - 2019-12-16 · A Sporting Chance for Kids
  - 2019-01-04 · World Cup Fever Infects Indonesia
- **Cluster 2** — 25 articles (41%); cue type `wellness` 47%, cue format `news` 33%; words: sports, fitness, gym, padel, opens, challenge
  - 2019-01-04 · Ready, Set, GO!
  - 2025-07-01 · From Clubs to Courts: The Rise of Social Sports in Jakarta
  - 2025-11-07 · Urban Climbers
  - 2019-08-12 · 2019 FIT Games Returns

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
| Reviews | 230 | *per article* (prior `eat`)/*per article* (prior `restaurant`) | `review` | `jakarta` | - | high | mixed-categories | per_article: [] → ['type', 'subtype'] | resolved — changed (mixed-categories) |
| Business | 186 | *per article* (prior `editorial`)/*per article* (prior `business`) | *per article* (prior `feature`) | `jakarta` | topic: business | medium | D26, mixed-categories | per_article: ['format'] → ['type', 'subtype', 'format'] | resolved — changed (D26, mixed-categories) |
| Features | 20 | *per article* (prior `editorial`)/*per article* | `feature` | `jakarta` | - | medium | mixed-categories, D10 | per_article: ['subtype'] → ['type', 'subtype'] | resolved — changed (mixed-categories, D10) |
| Art | 244 | *per article*/*per article* | *per article* | `jakarta` | topic: art | medium | D25, D04, D12 | - | resolved (D25, D04, D12) |
| Experience Offers | 207 | *per article* (prior `stay`)/*per article* (prior `hotel`) | `offer` | `jakarta` | audience: family | medium | D17, D02 | - | resolved (D17, D02) |
| Community | 150 | `editorial`/`news` | *per article* (prior `feature`) | `jakarta` | topic: community | medium | D19 | - | resolved (D19) |
| Uncategorized | 83 | *per article*/*per article* | *per article* | `jakarta` | - | low | D09 | - | resolved (D09) |
| News | 551 | *per article*/*per article* | `news` | `jakarta` | - | high | as-proposed | - | resolved (as proposed) |
| Dining Offers | 402 | `eat`/`restaurant` | `offer` | `jakarta` | - | high | D02 | - | resolved (D02) |
| Events | 396 | `event`/*per article* | `event` | `jakarta` | - | high | D02, D12 | - | resolved (D02, D12) |
| Dining News | 388 | `eat`/`restaurant` | `news` | `jakarta` | - | high | as-proposed | - | resolved (as proposed) |
| Stay Offers | 261 | `stay`/`hotel` | `offer` | *per article* | - | high | D02 | - | resolved (D02) |
| Education | 169 | `editorial`/`education` | `news` | `jakarta` | topic: education; audience: family | medium | as-proposed | - | resolved (as proposed) |
| Explore Indonesia | 154 | `editorial`/`city-guide` | `city-guide` | *per article* | topic: travel | high | D14 | - | resolved (D14) |
| Opinion | 148 | `editorial`/`opinion` | `opinion` | `jakarta` | - | high | D03 | - | resolved (D03) |
| Bali Updates | 111 | *per article*/*per article* | *per article* | `bali` | - | high | as-proposed | - | resolved (as proposed) |
| Shopping | 108 | `shop`/`boutique` | `news` | `jakarta` | topic: fashion | medium | as-proposed | - | resolved (as proposed) |
| NOW! People | 99 | `editorial`/`people` | `people` | `jakarta` | - | high | as-proposed | - | resolved (as proposed) |
| Health | 99 | *per article*/*per article* | *per article* | `jakarta` | topic: health | medium | D05, D13 | - | resolved (D05, D13) |
| World Traveller | 94 | `editorial`/`city-guide` | `city-guide` | `international` | topic: travel | high | D06 | - | resolved (D06) |
| History & Heritage | 74 | `editorial`/`heritage` | `heritage` | `jakarta` | topic: heritage | high | D14 | - | resolved (D14) |
| Culture | 67 | `editorial`/`culture` | `feature` | `jakarta` | topic: culture | medium | D04 | - | resolved (D04) |
| Sports & Activities | 61 | *per article*/*per article* | *per article* | `jakarta` | topic: sports | medium | D11 | - | resolved (D11) |
| Offers | 55 | `stay`/`hotel` | `offer` | *per article* | - | high | D02 | - | resolved (D02) |
| Music | 49 | `event`/`concert` | `event` | `jakarta` | topic: music | high | D02 | - | resolved (D02) |
| Green Living | 47 | *per article*/*per article* | *per article* | `jakarta` | topic: sustainability | high | D05 | - | resolved (D05) |
| Kids & Family | 46 | *per article*/*per article* | *per article* | `jakarta` | audience: family; topic: family | high | as-proposed | - | resolved (as proposed) |
| Made In Indonesia | 39 | `shop`/`artisan` | `feature` | `indonesia` | topic: local-brands | medium | as-proposed | - | resolved (as proposed) |
| Film | 35 | `event`/`screening` | `event` | `jakarta` | topic: film | medium | D12 | - | resolved (D12) |
| Art & Culture | 28 | *per article*/*per article* | *per article* | `jakarta` | topic: art, culture | low | D04, D10 | - | resolved (D04, D10) |
| Bar Guide | 28 | `drink`/*per article* (prior `bar`) | *per article* | `jakarta` | - | medium | D01 | - | resolved (D01) |
| Discover Jakarta | 24 | `editorial`/`heritage` | `heritage` | `jakarta` | topic: heritage | high | D10, D14 | - | resolved (D10, D14) |
| Dining | 24 | `eat`/`restaurant` | *per article* | `jakarta` | - | high | D01, D10 | - | resolved (D01, D10) |
| Design | 24 | `editorial`/`culture` | `feature` | `jakarta` | topic: design, architecture | medium | D04 | - | resolved (D04) |
| Travel | 21 | `editorial`/`city-guide` | `city-guide` | *per article* | topic: travel | medium | D06, D14 | - | resolved (D06, D14) |
| City Guides | 19 | *per article*/*per article* | `guide` | `jakarta` | - | medium | D01 | - | resolved (D01) |
| Restaurant Guides | 17 | `eat`/`restaurant` | *per article* | `jakarta` | - | medium | D01 | - | resolved (D01) |
| Hidden Heritage | 16 | `editorial`/`heritage` | `heritage` | `other` | topic: heritage, culture | high | D14 | - | resolved (D14) |
| Lifestyle | 13 | *per article* (prior `editorial`)/*per article* (prior `lifestyle`) | *per article* | `jakarta` | - | low | D05 | - | resolved (D05) |
| Sites & Destinations | 12 | `do`/`attraction` | `guide` | `jakarta` | topic: heritage | high | as-proposed | - | resolved (as proposed) |
| Diplomatic Relations | 11 | `editorial`/`people` | `people` | `jakarta` | topic: diplomacy; series_key: `ambassadors-round-table` | medium | as-proposed | - | resolved (as proposed) |
| Love & Romance 2020 | 10 | *per article*/*per article* | `feature` | `jakarta` | occasion: date-night; series_key: `issue:love-and-romance-2020` | low | D07 | - | resolved (print issue, D07) |
| Food The Music Of Love | 10 | *per article*/*per article* | `feature` | `jakarta` | series_key: `issue:food-the-music-of-love` | low | D07 | - | resolved (print issue, D07) |
| A Jakarta Smorgasbord | 10 | *per article*/*per article* | `feature` | `jakarta` | series_key: `issue:a-jakarta-smorgasbord` | low | D07 | - | resolved (print issue, D07) |
| Indonesia S Creative Soul | 9 | *per article*/*per article* | `feature` | `jakarta` | topic: art, culture; series_key: `issue:indonesia-s-creative-soul` | low | D07 | - | resolved (print issue, D07) |
| Property Architecture Design | 9 | *per article*/*per article* | `feature` | `jakarta` | topic: property, architecture, design; series_key: `issue:property-architecture-design` | low | D07 | - | resolved (print issue, D07) |
| Art Culture The Realm Of Contemporary Arts | 8 | *per article*/*per article* | `feature` | `jakarta` | topic: art; series_key: `issue:art-culture-the-realm-of-contemporary-arts` | low | D07 | - | resolved (print issue, D07) |
| Music & Nightlife | 8 | *per article*/*per article* | `feature` | `jakarta` | topic: music; series_key: `issue:music-and-nightlife` | low | D07 | - | resolved (print issue, D07) |
| Capital Of Culture | 7 | *per article*/*per article* | `feature` | `jakarta` | topic: art, culture; series_key: `issue:capital-of-culture` | low | D07 | - | resolved (print issue, D07) |
| Its A Man's World | 7 | *per article*/*per article* | `feature` | `jakarta` | topic: fashion; series_key: `issue:its-a-man-s-world` | low | D07 | - | resolved (print issue, D07) |
| Tech Talk | 7 | *per article*/*per article* | `feature` | `jakarta` | topic: technology; series_key: `issue:tech-talk` | low | D07 | - | resolved (print issue, D07) |
| Staying Successful In Times Of Challenge | 7 | *per article*/*per article* | `feature` | `jakarta` | topic: business; series_key: `issue:staying-successful-in-times-of-challenge` | low | D07 | - | resolved (print issue, D07) |
| The Rhythm Of Life | 7 | *per article*/*per article* | `feature` | `jakarta` | topic: music; series_key: `issue:the-rhythm-of-life` | low | D07 | - | resolved (print issue, D07) |
| Staying In Style | 6 | *per article*/*per article* | `feature` | `jakarta` | topic: fashion; series_key: `issue:staying-in-style` | low | D07 | - | resolved (print issue, D07) |
| Season Of Love | 6 | *per article*/*per article* | `feature` | `jakarta` | occasion: date-night; series_key: `issue:season-of-love` | low | D07 | - | resolved (print issue, D07) |
| Architecture Property & Design | 6 | *per article*/*per article* | `feature` | `jakarta` | topic: architecture, property, design; series_key: `issue:architecture-property-and-design` | low | D07 | - | resolved (print issue, D07) |
| Travel & Holiday | 6 | *per article*/*per article* | `feature` | `jakarta` | topic: travel; series_key: `issue:travel-and-holiday` | low | D07 | - | resolved (print issue, D07) |
| The Culinary Issue | 6 | *per article*/*per article* | `feature` | `jakarta` | series_key: `issue:the-culinary-issue` | low | D07 | - | resolved (print issue, D07) |
| Building Future Leader | 6 | *per article*/*per article* | `feature` | `jakarta` | topic: education; series_key: `issue:building-future-leader` | low | D07 | - | resolved (print issue, D07) |
| Jakarta S Music & Nightlife | 6 | *per article*/*per article* | `feature` | `jakarta` | topic: music; series_key: `issue:jakarta-s-music-and-nightlife` | low | D07 | - | resolved (print issue, D07) |
| The Festive Season | 5 | *per article*/*per article* | `feature` | `jakarta` | occasion: celebration; series_key: `issue:the-festive-season` | low | D07 | - | resolved (print issue, D07) |
| Travels Far & Near | 5 | *per article*/*per article* | `feature` | `jakarta` | topic: travel; series_key: `issue:travels-far-and-near` | low | D07 | - | resolved (print issue, D07) |
| Festive Issue | 5 | *per article*/*per article* | `feature` | `jakarta` | occasion: celebration; series_key: `issue:festive-issue` | low | D07 | - | resolved (print issue, D07) |
| Health In An Era Of Urbanisation | 5 | *per article*/*per article* | `feature` | `jakarta` | topic: health; series_key: `issue:health-in-an-era-of-urbanisation` | low | D07 | - | resolved (print issue, D07) |
| Season Of Wonders | 5 | *per article*/*per article* | `feature` | `jakarta` | occasion: celebration; series_key: `issue:season-of-wonders` | low | D07 | - | resolved (print issue, D07) |
| In With The New | 4 | *per article*/*per article* | `feature` | `jakarta` | series_key: `issue:in-with-the-new` | low | D07 | - | resolved (print issue, D07) |
| Money Finance | 4 | *per article*/*per article* | `feature` | `jakarta` | topic: finance; series_key: `issue:money-finance` | low | D07 | - | resolved (print issue, D07) |
| Love & Romance | 4 | *per article*/*per article* | `feature` | `jakarta` | occasion: date-night; series_key: `issue:love-and-romance` | low | D07 | - | resolved (print issue, D07) |
| The Travel Issue | 4 | *per article*/*per article* | `feature` | `jakarta` | topic: travel; series_key: `issue:the-travel-issue` | low | D07 | - | resolved (print issue, D07) |
| The Plague Of Our Time | 4 | *per article*/*per article* | `feature` | `jakarta` | topic: health; series_key: `issue:the-plague-of-our-time` | low | D07 | - | resolved (print issue, D07) |
| Can Jakarta Really Change | 4 | *per article*/*per article* | `feature` | `jakarta` | topic: sustainability, transport; series_key: `issue:can-jakarta-really-change` | low | D07 | - | resolved (print issue, D07) |
| City Of The Future | 3 | *per article*/*per article* | `feature` | `jakarta` | topic: architecture, transport, sustainability; series_key: `issue:city-of-the-future` | low | D07 | - | resolved (print issue, D07) |
| Embracing The New Normal | 3 | *per article*/*per article* | `feature` | `jakarta` | topic: health, business; series_key: `issue:embracing-the-new-normal` | low | D07 | - | resolved (print issue, D07) |
| Money & Finance | 3 | *per article*/*per article* | `feature` | `jakarta` | topic: finance; series_key: `issue:money-and-finance` | low | D07 | - | resolved (print issue, D07) |
| 10th Anniversary Issue | 2 | *per article*/*per article* | `feature` | `jakarta` | series_key: `issue:10th-anniversary-issue` | low | D07 | - | resolved (print issue, D07) |

## Appendix B. Per-category evidence and resolution — changed first, then by size

### Reviews — resolved — changed (mixed-categories)

*230 published · 2019–2026 · parent: Dining · Yoast primary on 54 · slug `dining-reviews` · term 2701*

> Editor's description: Find and read different reviews for bar, dining and restaurant by the people who know best only at NOW! Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* (prior `eat`) · subtype *per article* (prior `restaurant`) · format `review` · location `jakarta` · - · confidence **high**

**E2.0 proposal (before the answers).** type `eat` · subtype `restaurant` · format `review` · location `jakarta` · - · status was `flagged-by-evidence`.

**Resolution.** basis mixed-categories; changed — Format `review` stays fixed (not flagged). Type eat/restaurant is the prior.; addressed flags: 1.

**Reasoning.** 152 of 230 are from 2019 — the 18-month half-life sinks them correctly without deleting them.

**Alternates for the classifier.** drink/wine-bar\|bar + review for wine, beer and coffee pieces (cluster 23%); drink/rooftop-bar or drink/wine-bar when the venue is a bar ('Hakkasan Jakarta Rooftop', 'Good Wines, Good Times')

**Flags (evidence against the E2.0 proposal).** clusters split the category: k=2 split (silhouette 0.14, smallest cluster 23%) whose clusters read as different venue types (drink, eat) while the proposal fixes type=eat; 14% of members sit closer to a category of another type

**Representative titles (spread across the date range).**
- 2019-01-04 · On 25th anniversary,  Cafe Batavia Offers a New, Updated Menu
- 2019-01-04 · Discover Thailand at The Dharmawangsa Jakarta
- 2019-01-04 · Starbucks’ Frappucinos to Boost Summer Mood
- 2019-01-04 · 5 Healthy Smoothie Bowls in South Jakarta
- 2019-08-02 · Bali-based Gelato Secrets Opens its Door in Shophaus Menteng
- 2020-03-09 · These Jakarta Restaurants Offers Stunning Designs, in Addition to Their Own Signature Dishes
- 2023-09-21 · Gather at GLOU Wine & Bistro for a Vibrant and Scrumptious Meal and Drinks
- 2026-07-10 · The Legacy Continues at ORIJIN

**Cue instrument.** type: eat 79%, drink 13%, shop 3%, stay 2% (coverage 90%); format: news 38%, offer 21%, review 17%, listing 9% (coverage 61%); period-stamped titles 4%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 152, south-jakarta 14, bali 13, senayan 10, kemang 8, scbd 7; 6% name only a place outside jakarta.

**Co-filed with.** Dining 7, Art & Culture 1, Stay Offers 1; 220 carry this category alone.

**Coherence** (incoherent, against the E2.0 proposal). k=2 split (silhouette 0.14, smallest cluster 23%) whose clusters read as different venue types (drink, eat) while the proposal fixes type=eat; 14% of members sit closer to a category of another type. Cohesion 0.792 (baseline 0.754), leakage 62% → Dining News (49), Dining (18), Bar Guide (14), Dining Offers (11); best split k=2 silhouette 0.141.
- cluster 1: 177 (77%) `eat`/`news` — Finest Indulgence of Local Delicacies at The Café — Hotel Mulia Senaya; Celebrating Indonesian Delicacies; New Deliciousness at The Dutch
- cluster 2: 53 (23%) `drink`/`news` — Bellissimo Wines Hits the High Notes, in Both Flavor and Price; Introducing the Diamond of The Culinary World; Taste Australia: Australian Grapes Now Available in Indonesian Superma

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `per-article` · format `review` · location `per-article` · agrees: False · split: True → restaurant-reviews, bar-drink-reviews, dining-news-features · confidence medium. Titles span restaurants, bars, wine, cooking classes, and Bali venues, so subtype and location cannot be fixed; some titles read as news/features rather than reviews.

**E1.4 draft.** confidence high, decision_needed False

### Business — resolved — changed (D26, mixed-categories)

*186 published · 2019–2026 · parent: Features · Yoast primary on 32 · slug `business-news` · term 2770*

> Editor's description: The latest updates on the global economy and diplomatic affairs. Check out the latest updates and new articles.

**Resolved prior** (E1.4 draft, amended by the evidence pack): type *per article* (prior `editorial`) · subtype *per article* (prior `business`) · format *per article* (prior `feature`) · location `jakarta` · topic: business · confidence **medium** · decisions D26

**E2.0 proposal (before the answers).** type `editorial` · subtype `business` · format *per article* (prior `feature`) · location `jakarta` · topic: business · status was `decision-needed`.

**Resolution.** basis D26, mixed-categories; changed — editorial/business stays the prior; the classifier may switch to a venue type. Format per article between feature/news/opinion.; addressed flags: 1.

**Reasoning.** Amended: 19% read as stay (hotel corporate news). Type prior editorial/business stays but is switchable; format per article. \| E1.4: 122 of 186 from 2019. Type/subtype solid; format per article between feature/news/opinion.

**Alternates for the classifier.** stay/hotel + news when a hotel, GM appointment or opening is the subject (cluster 41%); eat/restaurant when an F&B business is the subject; format news for appointments and expansions ('Subendi to Lead Surabaya Oakwood'); format opinion for columns ('Why Indonesian Companies Keep Failing to Change')

**Flags (evidence against the E2.0 proposal).** clusters split the category: k=2 split (silhouette 0.12, smallest cluster 41%) whose clusters read as different venue types (editorial, stay) while the proposal fixes type=editorial; 22% of members sit closer to a category of another type

**Representative titles (spread across the date range).**
- 2019-01-04 · Flatpack Furniture: IKEA’s Development in Indonesia
- 2019-01-04 · Beating The Odds at Lavish Kemang Residence
- 2019-02-13 · Unlocking The Morning Jakarta at Le Meridien Jakarta
- 2019-03-18 · Asean-China Summit Commemorates 15th Anniversary of Strategic Partnership
- 2019-09-03 · Tauzia Hotels Celebrates 18th Anniversary
- 2020-02-17 · Malaysia Club Jakarta: More than Business Organisation
- 2023-11-15 · EUNIC Indonesia Forges Cultural Bridge for Indonesia and European Union
- 2026-06-08 · Why Indonesian Companies Keep Failing to Change (And What the Best Ones Do Differently)

**Cue instrument.** type: editorial 51%, stay 26%, eat 6%, shop 6% (coverage 74%); format: news 33%, listing 13%, people 11%, offer 11% (coverage 55%); period-stamped titles 5%; roundups 0%; median first-person density 3.2/1000 words.

**Places named in title/lead.** jakarta 87, bali 11, yogyakarta 5, bogor 4, scbd 3, bandung 3; 6% name only a place outside jakarta.

**Co-filed with.** NOW! People 2; 184 carry this category alone.

**Coherence** (incoherent, against the E2.0 proposal). k=2 split (silhouette 0.12, smallest cluster 41%) whose clusters read as different venue types (editorial, stay) while the proposal fixes type=editorial; 22% of members sit closer to a category of another type. Cohesion 0.767 (baseline 0.754), leakage 61% → Stay Offers (26), NOW! People (15), News (13), Green Living (12); best split k=2 silhouette 0.117.
- cluster 1: 109 (59%) `editorial`/`listing` — AmCham Indonesia: Connecting Companies and Finding Solutions; An Interview with H.E. Stig Traavik, Ambassador of Norway to Indonesia; Strengthening Economic Ties Between Indonesia and Germany
- cluster 2: 77 (41%) `stay`/`news` — Dan Benzaquen: Hospitality at Heart; A Milestone For Ayana Resort and Spa Bali; The Hermitage Hotel, Jakarta Announces New General Manager

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → hospitality-news, diplomacy-interviews, business-advice · confidence high. Titles span hotel openings, ambassador interviews, business advice, and tourism promotion with varied locations, so no single facet assignment fits.

**E1.4 draft.** confidence medium, decision_needed False

### Features — resolved — changed (mixed-categories, D10)

*20 published · 2024–2026 · top-level · Yoast primary on 17 · slug `features` · term 2766*

> Editor's description: Find insights about Community, NOW! People and Opinions. This feature is a list of the latest and greatest news stories, blogs, and opinions.

**Resolved prior** (E1.4 draft (carried)): type *per article* (prior `editorial`) · subtype *per article* · format `feature` · location `jakarta` · - · confidence **medium** · decisions D10

**E2.0 proposal (before the answers).** type `editorial` · subtype *per article* · format `feature` · location `jakarta` · - · status was `flagged-by-evidence`.

**Resolution.** basis mixed-categories, D10; changed — Format `feature` stays fixed; the container rule (D10) applies when a child category is present.; addressed flags: 1.

**Reasoning.** Parent category used directly since 2024 (20 posts). Format feature is certain (print-style long-form); subtype per article.

**Alternates for the classifier.** eat/restaurant when a restaurant is the subject (cue 50%); subtype per article: culture \| heritage \| people \| opinion \| business; topic per article: architecture, heritage, culture, local-brands

**Flags (evidence against the E2.0 proposal).** cue instrument disagrees on type: proposal fixes `editorial` but 50% of signal-bearing articles read as `eat` (only 25% as `editorial`) -- this changes competitor exclusion

**Representative titles (spread across the date range).**
- 2024-02-16 · Indonesian Democracy in Process: A Historic & Contemporary Review
- 2025-03-06 · Celebrating Ramadan & Idul Fitri Indonesian Traditions
- 2025-07-04 · Is Jakarta ‘Fit for Fitness?’
- 2025-10-10 · Meet the Makers: Drinks Edition
- 2026-04-07 · A City for Curious Learners: Inspiring Destinations For Young Minds
- 2026-05-22 · The Flavour Biodiversity of the Archipelago: Building Blocks of Nusantara Gastronomy
- 2026-06-24 · Brunch O'Clock: Weekend Indulgence across Jakarta
- 2026-08-21 · From East Indies to Indonesia: The Evolution of Architecture in the Archipelago

**Cue instrument.** type: eat 50%, editorial 25%, do 12%, wellness 12% (coverage 80%); format: heritage 56%, listing 22%, guide 11%, news 11% (coverage 45%); period-stamped titles 20%; roundups 0%; median first-person density 1.8/1000 words.

**Places named in title/lead.** jakarta 6, bali 2, yogyakarta 1, banyuwangi 1, ubud 1; 15% name only a place outside jakarta.

**Co-filed with.** Made In Indonesia 2, Dining 2, Culture 1; 9 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.799 (baseline 0.769), leakage 55% → Made In Indonesia (2), Culture (1), Explore Indonesia (1), Sports & Activities (1); best split k=2 silhouette 0.202.
- cluster 1: 17 (85%) `eat`/`heritage` — Preserving Traditional Indonesian Food; Beyond the Plate: How Social Gastronomy Can Transform Communities; The Flavour Biodiversity of the Archipelago: Building Blocks of Nusant
- cluster 2: 3 (15%) `editorial`/`listing` — Ramadan and Eid al-Fitr: Reflections on Spirituality, Community, and G; Eid al-Fitr: A Celebration of Faith, Compassion, and Community; Celebrating Ramadan & Idul Fitri Indonesian Traditions

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: True → opinion, heritage, people · confidence medium. Format and type are correct, but location is per-article since titles span Jakarta, Bali, Ubud, and national topics; split could separate opinions, heritage, and people profiles.

**E1.4 draft.** confidence medium, decision_needed False

### Art — resolved (D25, D04, D12)

*244 published · 2019–2026 · parent: Art & Culture · Yoast primary on 66 · slug `art` · term 2669*

> Editor's description: Discover art news and events in Jakarta, as well as reviews, profiles, interviews and more. Read about the latest developments in art and culture.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · topic: art · confidence **medium** · decisions D25, D04, D12

**Resolution.** basis D25, D04, D12; unchanged.

**Reasoning.** 244 posts, 165 from 2019. Topic art is the only certain facet; type/format split roughly between dated events and commentary.

**Alternates for the classifier.** event/exhibition + format event (announcements: 'Mirage at ARTSPACE'); event/performance + event (theatre: 'Tadashi Suzuki's King Lear'); editorial/culture + review\|feature (commentary); editorial/people + people (artist profiles)

**Representative titles (spread across the date range).**
- 2019-01-04 · In Cerebral Humour, A Subtle Message
- 2019-01-04 · Fabrics with History
- 2019-01-04 · ART STAGE Jakarta Announces Winners For The Inaugural Indonesia Art Award
- 2019-01-04 · Indonesia Opera Society Celebrates Tenth Anniversary with Spectacular Showcase
- 2019-03-18 · “Ontology of Ken Dedes” Forces Us to Examine the Role of Women in Javanese Folklore
- 2020-05-23 · ‘Lumbung’ is Introduced as Artistic Direction for Kassel’s Documenta 15 in 2022
- 2024-12-05 · Sing Dance Cry Breathe: Korakrit Arunanondchai Externalises Human Emotion in Museum MACAN'S Latest Exhibition
- 2026-09-04 · Terlihat / Terasa Exhibition by Rajata Hakim Asks How Much a Face Can Really Tell Us

**Cue instrument.** type: event 48%, do 23%, editorial 20%, stay 4% (coverage 70%); format: event 42%, heritage 25%, listing 12%, news 11% (coverage 66%); period-stamped titles 9%; roundups 0%; median first-person density 4.4/1000 words.

**Places named in title/lead.** jakarta 126, bali 14, yogyakarta 14, solo 13, bandung 10, south-jakarta 8; 12% name only a place outside jakarta.

**Co-filed with.** Opinion 4, Events 3, Culture 2; 234 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.791 (baseline 0.754), leakage 34% → Culture (18), Art & Culture (15), Indonesia S Creative Soul (7), Events (7); best split k=3 silhouette 0.053.
- cluster 1: 108 (44%) `event`/`event` — Deciphering life at “The Meeting Point”, Celebration Art Palette of Ei; Artistic Connection Across Generations; Wirantawan: Art As a Search For Oneness
- cluster 2: 87 (36%) `event`/`event` — Art Jakarta 2024: Presenting the Best of Indonesian & Regional Contemp; Connecting Jakarta to the Global Art World; ART Jakarta 2023: Southeast Asia's Premier Art Fair Returns This Novem
- cluster 3: 49 (20%) `do`/`heritage` — Exploring Our Art in Various Collections Abroad; Bartele Gallery Jakarta: Rare Antique Maps, Prints and Books of Indone; Art Archives and the Exhibition-based Approach of Art History

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: True · split: True → art-reviews, art-events, artist-profiles · confidence medium. Titles span reviews, event coverage, artist profiles, and news with no single dominant format; location defaults to Jakarta per magazine scope though a few articles are national.

**E1.4 draft.** confidence medium, decision_needed True — Approve the proposed `editorial/culture` subtype. Without it, exhibition reviews and artist profiles have no home except `news` or `people`.

### Experience Offers — resolved (D17, D02)

*207 published · 2019–2026 · parent: Offers · Yoast primary on 104 · slug `experience-offers` · term 2706*

> Editor's description: Experience Offers is covering the travel and tourism industry, corporate travel, hospitality, and hotel stay in Jakarta.

**Resolved prior** (E1.4 draft, amended by the evidence pack): type *per article* (prior `stay`) · subtype *per article* (prior `hotel`) · format `offer` · location `jakarta` · audience: family · confidence **medium** · decisions D17, D02

**Resolution.** basis D17, D02; unchanged.

**Reasoning.** Amended: E1.4 fixed type stay/hotel; the cue instrument splits stay 44% / eat 22% / wellness 12% / do 5% and the clusters agree -- type is per article with stay as the prior (D17). \| E1.4: 10 co-occur with Bali Updates (Bali hotel packages -> location bali). Audience family is frequent but not universal.

**Alternates for the classifier.** do/attraction + offer; event/festival + event (festive programmes)

**Representative titles (spread across the date range).**
- 2019-01-04 · New Year Feast at Pullman Jakarta
- 2019-01-04 · Need a Bit of Weekend Getaway? Bandung is Always a Choice
- 2019-09-04 · Wellness Getaway at Tirta Ayu Spa
- 2020-05-11 · HACCP-Certified Hotel Ciputra Jakarta Offers Delivery Service Menu and Virtual Promotions
- 2023-12-11 · Hotel Indonesia Kempinski Jakarta’s Exciting Year-End Festivities
- 2024-08-02 · Pullman Ciawi Vimala Hills Hosts Immersive 'Wewangian Akhir Pekan' Perfumery Class
- 2025-05-30 · Family Fun Meets Island Leisure at InterContinental Bali Resort
- 2026-09-04 · An Open Invitation to September at 25hours Hotel Jakarta The Oddbird

**Cue instrument.** type: stay 52%, eat 25%, wellness 14%, do 6% (coverage 86%); format: offer 84%, news 9%, city-guide 3%, event 3% (coverage 89%); period-stamped titles 38%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 110, bali 43, nusa-dua 11, ubud 9, legian 8, bandung 8; 28% name only a place outside jakarta.

**Co-filed with.** Offers 20, Stay Offers 13, Bali Updates 10; 157 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.807 (baseline 0.754), leakage 73% → Bali Updates (35), Dining Offers (30), Stay Offers (28), Offers (24); best split k=3 silhouette 0.081.
- cluster 1: 82 (40%) `stay`/`offer` — Enjoy a Blissful Ramadan with Pullman Jakarta Indonesia’s Seasonal Off; The Westin Jakarta Presents Serene Stays and Culinary Delights for Bli; Hotel Indonesia Kempinski Jakarta's Celebratory Ramadan Experiences
- cluster 2: 68 (33%) `stay`/`offer` — Wellness Getaway at Tirta Ayu Spa; Save Now, Stay Later: Indulgence Awaits at The Laguna, a Luxury Collec; Leisure in a Special Buy One Get One Promotion at The Stones – Legian,
- cluster 3: 57 (28%) `stay`/`offer` — JW Marriott Hotel Jakarta Offers Festive Holiday Sparkles; Celebrate the Magical Festive Season at HARRIS Hotel & Convention Kela; Celebrate the Festive Season in Style at Gran Meliá Jakarta

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `stay` · subtype `per-article` · format `offer` · location `per-article` · agrees: False · split: True → hotel-offers, wellness-retreats, travel-deals · confidence medium. Titles span hotels, wellness resorts, and airlines across multiple cities; subtype and location vary per article, contradicting the proposed hotel-only Jakarta scope.

**E1.4 draft.** confidence medium, decision_needed True — Is 'Experience Offers' a stay category (hotel packages) or a do category (activities)? Evidence says hotel experience packages (staycations, festive programmes, kids' activities at ARTOTEL/Novotel/HARRIS). Recommend prior stay/hotel + offer, classifier may switch to do/* or event/*.

### Community — resolved (D19)

*150 published · 2019–2026 · parent: Features · Yoast primary on 49 · slug `community` · term 2744*

> Editor's description: Discover NOW! Jakarta and the best way to stay connected with the community and the latest news.

**Resolved prior** (E1.4 draft, amended by the evidence pack): type `editorial` · subtype `news` · format *per article* (prior `feature`) · location `jakarta` · topic: community · confidence **medium** · decisions D19

**Resolution.** basis D19; unchanged.

**Reasoning.** Amended: prior format feature (D19); E1.4 had news. \| E1.4: Topic community is certain; type/format split between dated charity events and features.

**Alternates for the classifier.** event/community + event for charity balls and fundraisers (BWA Jakarta); editorial/people + people for community profiles; format feature for initiatives ('The Living Wall')

**Representative titles (spread across the date range).**
- 2019-01-04 · Disaster, Why And How Do We Better Respond
- 2019-01-04 · Opening Hearts and Homes at Rumah-Ku
- 2019-01-04 · NOW! Jakarta Photo Contest
- 2019-03-18 · Indonesia Indah Foundation Aims to Empower People to become Agents of Change for the Environment
- 2020-02-05 · Kartika Soekarno Foundation: A Brighter Future for Indonesian Children
- 2023-10-13 · Indonesian Heritage Society: Preserving Culture Through Community
- 2025-02-21 · United through Badminton: 75 Years of Denmark-Indonesia Diplomatic Relations
- 2026-09-02 · A New Beat for Betawi

**Cue instrument.** type: editorial 74%, event 8%, do 6%, wellness 5% (coverage 79%); format: event 25%, listing 18%, news 17%, opinion 15% (coverage 48%); period-stamped titles 11%; roundups 0%; median first-person density 7.7/1000 words.

**Places named in title/lead.** jakarta 84, bali 8, yogyakarta 4, lombok 3, central-jakarta 3, south-jakarta 3; 6% name only a place outside jakarta.

**Co-filed with.** Shopping 1, Art & Culture 1, Events 1; 146 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.77 vs baseline 0.75; leakage 66% (cross-type 13%). Cohesion 0.772 (baseline 0.755), leakage 66% → Green Living (19), Events (10), Education (8), Culture (7); best split k=3 silhouette 0.077.
- cluster 1: 64 (43%) `editorial`/`event` — Indonesia At Play-Calendar 2018 Photo Competition and Exhibition; The List of Expatriate and Intercultural Community in Jakarta for Soci; Spreading Joy to Those in Need
- cluster 2: 49 (33%) `editorial`/`listing` — Learning to Give; The Beauty of Sharing; Best Charities in Jakarta: Where to Give This Christmas Season
- cluster 3: 37 (25%) `editorial`/`listing` — Strengthen The Commitment to Support a Clean and Green Bali, Coca-Cola; Collaboration For Cleaner Environment In Bali's Big Eco Weekend 2016; Indonesia Indah Foundation Aims to Empower People to become Agents of 

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `community` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. These are community-focused feature stories, not news; locations span Jakarta, Bali, Lombok, and national, so location is per-article.

**E1.4 draft.** confidence medium, decision_needed False

### Uncategorized — resolved (D09)

*83 published · 2019–2026 · top-level · Yoast primary on 12 · slug `uncategorized` · term 1*

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · - · confidence **low** · decisions D09

**Resolution.** basis D09; unchanged — No prior; every facet from content; standard confidence gate; the four page-like titles are migrated, not excluded..

**Reasoning.** 83 posts = the 1.7% 'uncovered' in ARCHITECTURE §6 (WP assigns Uncategorized when nothing else is chosen).

**Alternates for the classifier.** wellness/gym + news; editorial/education; editorial/opinion; editorial/culture

**Representative titles (spread across the date range).**
- 2019-01-04 · Never Mind the Trees
- 2019-01-04 · EuroCham Indonesia Will Host the Eighth EU-Indonesia Business Dialogue
- 2019-01-04 · Indonesia Unfolded Seeks to Help the John Fawcett Foundation
- 2019-07-31 · French National Day 12 July 2019 at Raffles Jakarta
- 2020-04-16 · William Wongso’s Cooking at Home: Tips & Tricks!
- 2020-05-06 · Liquid Bliss from the Bees
- 2020-06-05 · Keep the Music On! A Melodic Therapy to Covid-19 Crisis
- 2026-05-04 · Wellground: The Newest Health and Fitness Hub

**Cue instrument.** type: editorial 31%, eat 26%, wellness 19%, stay 12% (coverage 51%); format: opinion 34%, news 19%, event 9%, listing 9% (coverage 39%); period-stamped titles 6%; roundups 0%; median first-person density 6.9/1000 words.

**Places named in title/lead.** jakarta 41, bali 4, kuningan 2, bandung 2, gunawarman 2, lombok 1; 6% name only a place outside jakarta.

**Co-filed with.** Events 1, Education 1; 81 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.726 (baseline 0.757), leakage 81% → Health (9), Opinion (8), Community (5), Business (5); best split k=2 silhouette 0.109.
- cluster 1: 42 (51%) `editorial`/`news` — #CookingFromHome with Chef Adrian Aditya; Our New Column – Share Your Thoughts With Jakarta!; Starbucks Promotes Indonesia’s Cultural Heritage
- cluster 2: 41 (49%) `wellness`/`opinion` — COVID-19: Wellbeing Management; “I Learned New Life Skill during Self-Quarantine”. Have You?; William Wongso’s Cooking at Home: Tips & Tricks!

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → news, food-and-recipe, event, opinion-editorial · confidence high. Uncategorized is a catch-all with no determinable facets; location should also be per-article since the category does not constrain it despite being a Jakarta magazine.

**E1.4 draft.** confidence low, decision_needed True — No prior at all — the classifier decides every facet. Also contains non-editorial pages ('Order Form - NOW! Magazines'). Recommend: every Uncategorized post goes to the E2.8 review queue regardless of confidence, and E1.8 flags obvious non-articles for exclusion below the quality floor.

### News — resolved (as proposed)

*551 published · 2019–2026 · top-level · Yoast primary on 356 · slug `news` · term 2678*

> Editor's description: Find news from the world that is trending, breaking and meaningful.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `news` · location `jakarta` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Carried: format news, type per article. The cue instrument reads 10% event / 7% listing / 7% offer -- the classifier's override rate, not a mapping problem. \| E1.4: Format is certain; type is per article — the biggest single bucket (356 Yoast-primary) and the most heterogeneous. Location defaults to the site node.

**Alternates for the classifier.** type stay/hotel dominates (Pan Pacific, Citadines, Swiss-Belhotel, Club Med); event/* when the news announces a dated happening

**Representative titles (spread across the date range).**
- 2019-01-04 · Human Rights and the UN SDGs: Identifying Key Markers in the 2030 Agenda in Indonesia
- 2019-01-04 · Empowering the Youth at TEDxJIS 2017
- 2020-01-20 · Jakarta Highland Gathering Returns in 2020!
- 2023-06-06 · Preserving Jakarta's Mangroves
- 2024-05-10 · Hotel Borobudur Jakarta Welcomes Mr. David Richard O'Hanlon as New General Manager
- 2025-03-14 · Raising Resilient Minds: Redea Institute Hosts Children’s Mental Health Workshop Series
- 2025-12-17 · Tayo Station Indonesia Launches at Lotte Mall Bintaro Ahead of Year-End Holidays
- 2026-09-04 · Skyline Prestige: The Art of Staying Above the City at Pan Pacific Jakarta

**Cue instrument.** type: stay 33%, editorial 26%, event 11%, eat 10% (coverage 75%); format: news 54%, event 14%, offer 10%, listing 10% (coverage 71%); period-stamped titles 16%; roundups 1%; median first-person density 2.0/1000 words.

**Places named in title/lead.** jakarta 278, bali 29, senayan 17, pik 17, surabaya 16, bandung 16; 10% name only a place outside jakarta.

**Co-filed with.** Stay Offers 6, Events 5, Education 3; 524 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.763 (baseline 0.753), leakage 84% → Stay Offers (61), Business (56), Events (50), Community (26); best split k=2 silhouette 0.073.
- cluster 1: 308 (56%) `stay`/`news` — The Westin Jakarta Earns Title of Indonesia’s Leading Business Hotel 2; Ascott Menteng Jakarta Unveils New Experiences Across the Property; Gran Melia Jakarta Recognised for Excellence as Indonesia’s Leading Bu
- cluster 2: 243 (44%) `editorial`/`news` — Calling all Jakarta Runners to Join ‘Road to Give’, Marriott Internati; Sharing in the Spirit of Ramadan; Most Valued Businesses Celebrate Sustainability in Indonesia

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `news` · location `per-article` · agrees: False · split: False · confidence high. Titles span multiple types and locations including Surabaya, Ubud, and national topics, so location must be per-article rather than jakarta; format is consistently news.

**E1.4 draft.** confidence high, decision_needed False

### Dining Offers — resolved (D02)

*402 published · 2019–2026 · parent: Offers · Yoast primary on 238 · slug `dining-offers` · term 2734*

> Editor's description: Jakarta is one of the most beautiful cities in the world. Getting the most out of it when you eat out is simple with our guide. The best places to eat in Jakarta, .

**Resolved prior** (E1.4 draft (carried)): type `eat` · subtype `restaurant` · format `offer` · location `jakarta` · - · confidence **high** · decisions D02

**Resolution.** basis D02; unchanged.

**Reasoning.** Carried. Cue offer 70% / eat 76% -- the cleanest offer category in either city. The only open point is the expiry policy (D02), which is not a mapping question. \| E1.4: 33 co-occur with Stay Offers = hotel F&B packages; the venue is still the restaurant/outlet, so type stays eat. 134 of 402 are from 2019 — all expired.

**Representative titles (spread across the date range).**
- 2019-01-04 · Celebrate Christmas and New Year's at Ruth’s Chris Steak House!
- 2019-01-04 · These Hotels Offer Special Promotions to Celebrate Mother's Day
- 2019-06-17 · Bodacious Brunchcation at The Apurva Kempinski Bali
- 2023-03-24 · A Journey of Impeccable Taste: Alila Villas Uluwatu & Park Hyatt Jakarta’s Collaboration Series
- 2024-05-17 · Italian Affair: Savour a Soulful Six-Hands Dinner at Alto, Four Seasons Hotel Jakarta
- 2025-03-06 · Vasa Hotel Surabaya Offers A Ramadan Feast Fit for a Maharaja
- 2026-02-10 · ARYADUTA Menteng Celebrates Ramadan with a Nusantara Dining Journey by William Wongso
- 2026-09-04 · A Taste of Home, Reimagined at Noesaka

**Cue instrument.** type: eat 83%, stay 9%, drink 5%, event 2% (coverage 92%); format: offer 80%, news 11%, listing 3%, event 3% (coverage 85%); period-stamped titles 31%; roundups 2%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 283, bali 21, bandung 16, scbd 11, yogyakarta 11, senayan 11; 11% name only a place outside jakarta.

**Co-filed with.** Stay Offers 33, Experience Offers 6, Offers 3; 355 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.82 vs baseline 0.75; leakage 44% (cross-type 12%). Cohesion 0.82 (baseline 0.754), leakage 44% → Dining News (44), Reviews (31), Offers (29), Experience Offers (24); best split k=2 silhouette 0.071.
- cluster 1: 309 (77%) `eat`/`offer` — Enjoy Special Ramadhan Promos around Jakarta; Impressive Ramadhan and Kahk, Special Egyptian Cookie at Hotel Borobud; A Series of Ramadan Celebrations at InterContinental Jakarta Pondok In
- cluster 2: 93 (23%) `eat`/`offer` — Celebrate the Festive Season with Sparkling Wonders at The Westin Jaka; A Medley of Festive Delights at DoubleTree by Hilton Jakarta – Diponeg; Feast, Stay and Celebrate at AYANA Midplaza Jakarta this Festive Seaso

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `restaurant` · format `offer` · location `per-article` · agrees: False · split: False · confidence high. Type, subtype, and format are correct, but titles reference Surabaya and Tangerang venues, so location is per-article rather than jakarta.

**E1.4 draft.** confidence high, decision_needed True — Legacy offers have no campaign row, so `campaign.ends_at` (the §8.A hard filter) is undefined. Recommend: E1.8 extracts an end date from the text where present, else marks the offer expired at publish_date + 90 days. Offers must never surface in rails once expired; they remain searchable.

### Events — resolved (D02, D12)

*396 published · 2019–2026 · top-level · Yoast primary on 201 · slug `events` · term 2689*

> Editor's description: Events are a great way to get your event noticed. This news is dedicated to all the interesting events in the world.

**Resolved prior** (E1.4 draft (carried)): type `event` · subtype *per article* · format `event` · location `jakarta` · - · confidence **high** · decisions D02, D12

**Resolution.** basis D02, D12; unchanged.

**Reasoning.** Type and format certain; subtype per article. `ends_at` must be extracted (324 tribe_events rows carry dates; the rest need text extraction) or the §8.A event-expiry filter has nothing to bite on.

**Alternates for the classifier.** subtype per article: festival \| concert \| exhibition \| performance \| screening \| sports \| community \| conference \| pop-up

**Representative titles (spread across the date range).**
- 2019-01-04 · Throwback to the 80’s At the New Year’s Eve Party at Grand Mercure Kemayoran
- 2019-01-04 · Catalan Cuisine and Spanish Cava with Michelin Star Chef Rovira Canudas
- 2019-01-04 · Korea and Indonesia Engage in a “Dialogue with the Senses”
- 2019-12-14 · Carnival of Rhythm Welcomes 2020 at Manarai Beach House
- 2023-08-31 · Selamat Datang 2023: Indonesian Heritage Society's Annual Welcome Event
- 2024-05-31 · Europe on Screen Returns to Showcase European Culture through Contemporary Films, Kicks Off on 7 June 2024
- 2025-07-23 · Enjoy Solezza, A Summer-Themed Weekend Bazaar by Market & Museum
- 2026-08-21 · Marriott Charity Classic 2026 Tees Off for Clean Water in East Nusa Tenggara

**Cue instrument.** type: event 50%, shop 14%, eat 11%, editorial 10% (coverage 81%); format: event 60%, listing 12%, news 10%, offer 8% (coverage 73%); period-stamped titles 38%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 248, bali 33, thamrin 15, yogyakarta 14, kemang 12, senayan 12; 9% name only a place outside jakarta.

**Co-filed with.** Dining News 8, News 5, Education 5; 350 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.78 vs baseline 0.75; leakage 63% (cross-type 27%). Cohesion 0.78 (baseline 0.754), leakage 63% → Music (49), Art (19), Film (19), Dining News (16); best split k=3 silhouette 0.063.
- cluster 1: 173 (44%) `eat`/`event` — I Love Food Bazaar 2023; Immerse Into the Culture at the ASEAN-India Diwali Bazaar 2023; Upcoming Community Events
- cluster 2: 156 (39%) `event`/`event` — Ascott Indonesia Marks Three Decades with the Return of ASR Festival 2; Rediscovering Joy Across the Indonesian Archipelago with Indonesian He; Art Jakarta 2023
- cluster 3: 67 (17%) `event`/`event` — The Jakarta Concert Orchestra Presents Symphony For the Nation 2025: 8; Resonansi Abadi: A Three-Night Festival Honouring World Composers and ; Jakarta Concert Orchestra Once Again Presents A Symphony of Emotions: 

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `event` · subtype `per-article` · format `event` · location `jakarta` · agrees: True · split: False · confidence high. All titles are event announcements or coverage spanning concerts, festivals, and galas; subtype varies per article and location defaults to the magazine's city.

**E1.4 draft.** confidence high, decision_needed False

### Dining News — resolved (as proposed)

*388 published · 2019–2026 · parent: Dining · Yoast primary on 184 · slug `dining-news` · term 2760*

> Editor's description: It's no secret that Jakarta's dining scene has taken a hit over the years. Here's a roundup of the latest dining news. Discover here

**Resolved prior** (E1.4 draft (carried)): type `eat` · subtype `restaurant` · format `news` · location `jakarta` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Matches the §4 worked example.

**Alternates for the classifier.** format people for chef interviews (William Wongso); type event/festival for food festivals (Jakarta Dessert Week)

**Representative titles (spread across the date range).**
- 2019-01-04 · Chavaty, The Popular Japanese Cafe, Arrives in Jakarta
- 2019-01-04 · Agneya: The Honesty of Indonesian Food
- 2019-01-04 · Introducing Teras Bromo
- 2019-05-03 · Double Chin Restaurant and Bar: An Homage to Asia
- 2023-04-26 · Plataran Bandung Opens in the 'City of Flowers'
- 2024-10-02 · Jakarta Dessert Week 2024 Brings the Sweetness of Wildlife to the City
- 2025-10-01 · Have a Taste of French Gastronomy Week: Le Goût de France – Cita Rasa Prancis
- 2026-09-04 · Jakarta Dessert Week: Your Next Dessert-Hopping Adventure

**Cue instrument.** type: eat 86%, drink 8%, shop 3%, stay 2% (coverage 93%); format: news 45%, offer 17%, review 16%, people 8% (coverage 63%); period-stamped titles 5%; roundups 1%; median first-person density 2.0/1000 words.

**Places named in title/lead.** jakarta 243, south-jakarta 18, bali 17, thamrin 16, scbd 16, senopati 13; 5% name only a place outside jakarta.

**Co-filed with.** Events 8, Dining Offers 2, Explore Indonesia 2; 374 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.75; leakage 56% (cross-type 11%). Cohesion 0.799 (baseline 0.754), leakage 56% → Reviews (59), Dining Offers (39), Dining (27), Bar Guide (20); best split k=2 silhouette 0.074.
- cluster 1: 247 (64%) `eat`/`news` — The Westin Jakarta Introduces a New ‘Royal Brunch’ Experience at Seaso; RIVA at Wyndham Jakarta Offers A Burst of Flavour; Seasonal Tastes at The Westin Jakarta
- cluster 2: 141 (36%) `eat`/`news` — Chef Nicholas Kennedy Embraces Culinary Diversity; The Road to The French Connection; Cooking: A Form of Contemporary Art

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `per-article` · format `news` · location `jakarta` · agrees: False · split: False · confidence high. Type, format, and location are correct, but subtype varies across restaurants, cafes, bars, bakeries, and events, so 'restaurant' is too narrow.

**E1.4 draft.** confidence high, decision_needed False

### Stay Offers — resolved (D02)

*261 published · 2019–2026 · parent: Offers · Yoast primary on 82 · slug `stay-offers` · term 2740*

> Editor's description: Find a wide selection of hotels, resorts and holiday apartments at great prices. Have a look at the best hotel offers in Jakarta and make a great choice.

**Resolved prior** (E1.4 draft (carried)): type `stay` · subtype `hotel` · format `offer` · location *per article* · - · confidence **high** · decisions D02

**Resolution.** basis D02; unchanged.

**Reasoning.** Type/format certain. Location is per article and often OUTSIDE Jakarta (Puncak, Surabaya, Bandung, Malang) — do not default to jakarta. Same expiry problem as Dining Offers.

**Alternates for the classifier.** subtype resort \| villa \| serviced-apartment when explicit

**Representative titles (spread across the date range).**
- 2019-01-04 · Re-discover the 1920’s at The Hermitage Jakarta
- 2019-01-04 · Experiencing The Magical Day of Silence at The Trans Resort Bali
- 2019-01-04 · Stay in Shape with Global Fitness Trends
- 2019-08-08 · Explore Semarang with ARTOTEL Gajahmada
- 2023-06-22 · Discover the Beauty of Flores with Sudamala Resort Komodo’s Summer Flash Offer
- 2024-11-22 · Introducing the Executive Business Room: A Perfect Blend of Luxury and Functionality at Hotel Borobudur Jakarta
- 2025-08-25 · Discover New Tailored Packages at Fairfield by Marriott Bekasi
- 2026-09-03 · Le Eminence Puncak Celebrates 10 Years with a Month of Events

**Cue instrument.** type: stay 73%, eat 14%, do 4%, wellness 4% (coverage 85%); format: offer 70%, news 13%, heritage 7%, city-guide 4% (coverage 79%); period-stamped titles 21%; roundups 2%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 131, bali 44, bandung 17, yogyakarta 15, kuningan 9, bogor 9; 29% name only a place outside jakarta.

**Co-filed with.** Dining Offers 33, Experience Offers 13, News 6; 201 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.75; leakage 52% (cross-type 14%). Cohesion 0.796 (baseline 0.754), leakage 52% → Experience Offers (29), Bali Updates (26), Offers (21), Explore Indonesia (11); best split k=3 silhouette 0.088.
- cluster 1: 93 (36%) `stay`/`offer` — ARTOTEL Gelora Senayan: A New Sports, Art & Lifestyle Hub; PARKROYAL Serviced Suites Jakarta Introduces New Upscale Living in the; Affordable Luxury
- cluster 2: 91 (35%) `stay`/`offer` — The Festive Season Awaits at Alila SCBD Jakarta; Enjoy the Delights of Urban Festivities at THE 101 Jakarta Sedayu Darm; Timeless Holiday Celebration at Pullman Jakarta Indonesia
- cluster 3: 77 (30%) `stay`/`offer` — Samabe Bali Suites & Villas is the Perfect Place to be Pampered; Discover the Ultimate Family Escape at InterContinental Bali Resort: W; Special Stays at the Sakala Resort Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `stay` · subtype `hotel` · format `offer` · location `per-article` · agrees: True · split: True → stay-offers, stay-reviews-features · confidence high. Titles mix promotional offers with editorial reviews, features, and opening news across Indonesia, so location is per-article and a split could improve precision.

**E1.4 draft.** confidence high, decision_needed False

### Education — resolved (as proposed)

*169 published · 2019–2026 · parent: Lifestyle · Yoast primary on 74 · slug `education` · term 2703*

> Editor's description: The world is full of educational opportunities and the best place to be is Jakarta. Here you will find the latest news about education in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `education` · format `news` · location `jakarta` · topic: education; audience: family · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Heavily school-sponsored (BINUS, ACG open houses) — these schools are E1.5 partner-roster candidates, not just content.

**Alternates for the classifier.** format feature for explainers; event/community + event for open houses and tryouts

**Representative titles (spread across the date range).**
- 2019-01-04 · CELS Runs Workshop for CV Writing and Job Interview Coaching
- 2019-01-04 · Singapore Intercultural School Bona Vista and PT Bank KEB Hana Indonesia Introduce Co-Branded Debit Card
- 2019-01-04 · The Growing Popularity of Overseas Boarding School Experiences
- 2019-09-05 · The Lie Detector: In conversation with Monica Kumala Sari, Gesture and Micro-Expression Expert
- 2023-09-01 · TigerCampus for Finding Private Online Tutors of All Ages
- 2025-03-20 · Sekolah Victory Plus: An International Baccalaureate School in Indonesia for Future Leaders
- 2025-11-07 · David Goh's Path to Success: From Sinarmas World Academy to National Academic Olympiad
- 2026-09-02 · Bandung’s Aviation Adventure

**Cue instrument.** type: editorial 94%, event 3%, do 2%, eat 1% (coverage 92%); format: news 44%, event 17%, listing 11%, opinion 11% (coverage 53%); period-stamped titles 7%; roundups 0%; median first-person density 2.6/1000 words.

**Places named in title/lead.** jakarta 101, south-jakarta 7, bandung 6, bali 4, pondok-indah 3, tangerang 3; 5% name only a place outside jakarta.

**Co-filed with.** Events 5, News 3, Kids & Family 2; 155 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.75; leakage 19% (cross-type 2%). Cohesion 0.801 (baseline 0.754), leakage 19% → Kids & Family (8), Culture (4), Art (3), Sports & Activities (3); best split k=2 silhouette 0.064.
- cluster 1: 85 (50%) `editorial`/`news` — The Future of Learning is Here: SIS South Jakarta’s Open House 2025; ACG School Jakarta: A Global Hub for Excellence and Innovation; ACG School Jakarta: Creating Tomorrow’s Leaders
- cluster 2: 84 (50%) `editorial`/`news` — Empowering Future Thinkers with International Primary Curriculum at NA; Architects of the Future: Inside the MYP Experience at Global Jaya Sch; Embracing Experiential Learning for Life Beyond School

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `education` · format `per-article` · location `per-article` · agrees: False · split: True → school-news, education-features, school-events · confidence medium. Format varies across news, features, and event listings; location includes Bandung and Melbourne, not solely Jakarta.

**E1.4 draft.** confidence medium, decision_needed False

### Explore Indonesia — resolved (D14)

*154 published · 2019–2026 · parent: Travel · Yoast primary on 63 · slug `explore-indonesia` · term 2754*

> Editor's description: Explore Indonesia is a collection of essays written by fellow travel bloggers, offering advice on how to travel in Indonesia.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `city-guide` · format `city-guide` · location *per article* · topic: travel · confidence **high** · decisions D14

**Resolution.** basis D14; unchanged.

**Reasoning.** Carried. 16% read as offers (hotel promos filed here) -- classifier override, and D14 adds the destination nodes the tree lacks. \| E1.4: Location per article under `other/*` (Makassar, Yogyakarta, Belitung, Central Java) with `other` as the fallback when the destination has no node.

**Alternates for the classifier.** stay/resort + offer for hotel promos filed here ('Pullman Ciawi Vimala Hills')

**Representative titles (spread across the date range).**
- 2019-01-04 · Holy Night in the Land of Spirits, Celebrating Christmas in Bali this Year
- 2019-01-04 · The Coral Beauty of Northern Sulawesi
- 2019-01-04 · "Samosir Lake Toba Ultra 2016" to Boost Tourism in North Sumatra
- 2019-02-13 · Indonesia's Hidden Heritage
- 2019-12-20 · A Road Trip to the West Coast of Java
- 2024-03-07 · Kebun Raya Bogor: Indonesia's Green Gift to the World
- 2025-05-16 · Liveaboard Luxury: Island-Hopping in Style
- 2026-09-02 · Bandung’s Aviation Adventure

**Cue instrument.** type: do 40%, stay 16%, eat 14%, editorial 10% (coverage 75%); format: heritage 34%, offer 22%, city-guide 12%, event 10% (coverage 70%); period-stamped titles 11%; roundups 2%; median first-person density 1.1/1000 words.

**Places named in title/lead.** bali 40, jakarta 24, yogyakarta 15, lombok 10, bandung 10, solo 8; 55% name only a place outside jakarta.

**Co-filed with.** Offers 5, Dining News 2, Travel 1; 140 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.785 (baseline 0.755), leakage 60% → Hidden Heritage (12), Stay Offers (10), Offers (9), Bali Updates (7); best split k=2 silhouette 0.093.
- cluster 1: 90 (58%) `do`/`heritage` — Falling Under West Java's Spell; History, Natural Beauty and Wildlife in East Java; Javan Jaunts
- cluster 2: 64 (42%) `stay`/`offer` — Five Reasons to Visit Bali This Month; Chapung Sebali Resort and Spa: Ubud's Fusion Flavours and Valley Views; A Festive Time in Bali

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → travel-guides, hotel-reviews, event-features · confidence high. Titles span stays, food, museums, festivals, and hotel openings across Bali, Java, Lombok, and beyond, so no single type, format, or location fits.

**E1.4 draft.** confidence high, decision_needed False

### Opinion — resolved (D03)

*148 published · 2019–2026 · parent: Features · Yoast primary on 45 · slug `opinion` · term 2685*

> Editor's description: Latest news about opinion in Jakarta. Get first-hand news in the city with NOW! Jakarta news.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `opinion` · format `opinion` · location `jakarta` · - · confidence **high** · decisions D03

**Resolution.** basis D03; unchanged.

**Reasoning.** Carried; only the vocabulary approval (D03) is open. \| E1.4: 148 posts, 86 from 2019.

**Alternates for the classifier.** topic sustainability for the 'Sustainability Matters' column

**Representative titles (spread across the date range).**
- 2019-01-04 · Ten Years of NOW! Jakarta, a New Year for Jakarta City
- 2019-01-04 · Who Are “They”?
- 2019-01-04 · Jakarta Through The Eyes Of Its Residents
- 2019-01-04 · Alistair Speirs: My Journey to Work
- 2019-10-02 · Revisiting Oktoberfest
- 2022-07-04 · Mother Earth's Balancing Act: A Frivolous Tale of Serious Proportions
- 2024-01-17 · Jakarta Then & Now: A Personal Recollection of 44 Years in the Capital
- 2026-03-19 · Sustainability Matters: Wasted Opportunities

**Cue instrument.** type: editorial 65%, eat 13%, wellness 6%, event 5% (coverage 62%); format: opinion 58%, review 18%, city-guide 5%, news 5% (coverage 64%); period-stamped titles 5%; roundups 1%; median first-person density 22.1/1000 words.

**Places named in title/lead.** jakarta 60, bali 4, surabaya 2, cikini 2, kota-tua 1, south-jakarta 1; 3% name only a place outside jakarta.

**Co-filed with.** Art 4, Explore Indonesia 1, Culture 1; 141 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.76 vs baseline 0.75; leakage 37% (cross-type 1%). Cohesion 0.763 (baseline 0.755), leakage 37% → Green Living (8), Culture (6), Love & Romance 2020 (5), Uncategorized (4); best split k=2 silhouette 0.154.
- cluster 1: 89 (60%) `editorial`/`opinion` — Enjoy Jakarta; Life in The Big Durian: A letter to The Governor of Jakarta “Bapak Aho; A Birthday Wish for DKI Jakarta
- cluster 2: 59 (40%) `editorial`/`opinion` — Idle Thoughts from a Disturbed Resident of Tangerang; I Opened The Window and In Flew Enza; Hope for the Best but Prepare for the Worst

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `opinion` · format `opinion` · location `jakarta` · agrees: True · split: False · confidence high. Titles are clearly personal essays and opinion columns about Jakarta life, culture, and current affairs, fitting editorial/opinion with a consistent Jakarta location.

**E1.4 draft.** confidence high, decision_needed True — Approve the proposed `opinion` format (half-life 540 d). Fallback if rejected: format feature (evergreen) — which would keep 2019 columns permanently fresh.

### Bali Updates — resolved (as proposed)

*111 published · 2020–2026 · parent: Travel · Yoast primary on 92 · slug `bali-updates` · term 2768*

> Editor's description: The ultimate guide to Bali - Everything you need to know about Bali - Bali Hotels, Accommodation, Attractions, Restaurants, Nightlife, Shopping, and much more.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `bali` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Carried: location bali certain, type/format per article. These 111 are the §3.5 syndication set for now_bali. \| E1.4: Location bali is certain and the §4 example. §4 also says format news, but the titles are as often offers ('Enchanting Year-End Escape', 'Chic Beachfront Picnic Experience') — format per article. These 111 articles are the syndication set for now_bali (§3.5). 92 have Yoast primary = Bali Updates.

**Alternates for the classifier.** type stay/resort\|hotel dominates (Six Senses, Sofitel, InterContinental, TRIBE); wellness/retreat\|spa (COMO Shambhala, Desa Potato Head); format news OR offer — roughly half each

**Representative titles (spread across the date range).**
- 2020-01-17 · Embrace the Spirit of the Lunar New Year at COMO Uma Ubud
- 2022-12-09 · Grand Celebrations at InterContinental Bali Resort This Festive Holiday
- 2023-05-05 · Jumeirah Bali's Sunny Sandy Summer Family Escape
- 2023-10-27 · Embrace Luxury Living at Karma Kandara’s New Apartment Units
- 2024-03-14 · BaliSpirit Festival Returns for its 15th Edition
- 2025-01-22 · Usher in Chinese New Year at Amber Lombok Beach Resort
- 2025-08-18 · Sthala Ubud Presents “Evening Melodies: A Dine with Balawan”
- 2026-09-04 · Merasa Origins: Tracing Java’s Ancient Wellness Traditions at Desa Potato Head

**Cue instrument.** type: stay 42%, eat 32%, wellness 14%, event 4% (coverage 87%); format: offer 66%, news 18%, event 9%, heritage 3% (coverage 79%); period-stamped titles 35%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** bali 72, nusa-dua 19, ubud 16, uluwatu 15, lombok 8, jimbaran 7; 93% name only a place outside jakarta.

**Co-filed with.** Experience Offers 10, Offers 9, Travel 1; 97 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.809 (baseline 0.755), leakage 30% → Stay Offers (6), Dining News (5), Events (5), Health (4); best split k=3 silhouette 0.114.
- cluster 1: 53 (48%) `stay`/`offer` — Celebrate the Festive Season in Whimsical Harmony at The Westin Resort; Light Up Your Festive Holiday at Meliá Bali; Paradise Extravaganza: Dazzling Year-End Celebrations at InterContinen
- cluster 2: 43 (39%) `eat`/`news` — Embrace the Spirit of the Lunar New Year at COMO Uma Ubud; Samsara Ubud Awarded ONE KEY by the Michelin Guide 2025; Celebrate Lunar New Year at the Stylish COMO Uma Canggu
- cluster 3: 15 (14%) `stay`/`offer` — Karma Kandara's '12 Days of Karma' Promises Extravagant Year-End Festi; 12 Days of Karma: Karma Kandara’s Epic Year-End Programme; 12 Days of Karma: The Ultimate Festive Season Programme at Karma Kanda

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `bali` · agrees: True · split: True → bali-stay, bali-eat-drink, bali-do · confidence high. Titles span hotels, dining, events, wellness, and editorial across Bali; type and format vary per article but location is consistently Bali.

**E1.4 draft.** confidence high, decision_needed False

### Shopping — resolved (as proposed)

*108 published · 2019–2026 · parent: Lifestyle · Yoast primary on 29 · slug `shopping` · term 2704*

> Editor's description: You'll know that you're likely to be able to find almost all your favorite one-stop shopping products here, and they'll all be at a price that's far.

**Resolved prior** (E1.4 draft (carried)): type `shop` · subtype `boutique` · format `news` · location `jakarta` · topic: fashion · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Mostly fashion/brand news; treat type as a prior, not a rule.

**Alternates for the classifier.** format guide ('The Groom's Guide to Bespoke Style'); shop/mall for mall pieces; misfiled civic pieces exist ('Civic Engagement 3.0') -> classifier override

**Representative titles (spread across the date range).**
- 2019-01-04 · Get in Style and Look Timeless with Daniel Wellington
- 2019-01-04 · Ramadan in Style
- 2019-01-04 · Seri Nusa, A Collaboration of The Palace Jeweler and Fashion Designer Samuel Wattimena
- 2019-01-04 · Gear Up for a Workout Look Good, Feel It
- 2019-07-05 · Flik Flak by the Swatch: Timekeeping for Young Stars
- 2022-12-08 · Central Market PIK: An Eco-Friendly One-Stop Shopping Destination
- 2024-12-05 · Exemplify Modern Luxury with Range Rover Evoque: Evolved Design and Technology
- 2026-09-08 · ISMAYA Group and Tenue de Attire Explore a New Take on City Wear

**Cue instrument.** type: shop 85%, event 5%, editorial 5%, wellness 5% (coverage 81%); format: news 48%, listing 21%, event 10%, offer 7% (coverage 63%); period-stamped titles 21%; roundups 1%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 46, thamrin 11, bali 6, senayan 4, komodo 3, south-jakarta 3; 6% name only a place outside jakarta.

**Co-filed with.** News 3, Lifestyle 2, Community 1; 102 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.78 vs baseline 0.76; leakage 30% (cross-type 8%). Cohesion 0.779 (baseline 0.756), leakage 30% → Made In Indonesia (5), Lifestyle (5), Art (3), Health (3); best split k=2 silhouette 0.12.
- cluster 1: 76 (70%) `shop`/`news` — Stylish Lebaran with Indonesian Fashion Collection; Selisik Batik Pesisir Know What You Wear; Strengthening the Cultural Identity of Young Designers at IFW 2018
- cluster 2: 32 (30%) `shop`/`news` — Daniel Wellington: Embracing Fun, Health & Style with Interactive Expe; New H&M Collection Made from Recycled Shoreline Waste; Adidas’ Hu Collection Draws on Pharrell’s Unique Inspiration

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `shop` · subtype `per-article` · format `news` · location `jakarta` · agrees: False · split: True → fashion-news, artisanal-products, brand-announcements · confidence medium. Titles are mostly fashion and brand news, not general shopping; subtype 'boutique' is too narrow and format varies between news, feature, and guide.

**E1.4 draft.** confidence medium, decision_needed False

### NOW! People — resolved (as proposed)

*99 published · 2019–2024 · parent: Features · Yoast primary on 26 · slug `now-people` · term 2692*

> Editor's description: Discover the best NOW! people in Jakarta. People who are passionate about what they do and share their values.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `people` · format `people` · location `jakarta` · - · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Dormant: 64 of 99 from 2019, 3 since 2024. Evergreen format per §4.

**Alternates for the classifier.** topic diplomacy for ambassador interviews; topic business for founders

**Representative titles (spread across the date range).**
- 2019-01-04 · In Conversation with H.E. Gary Quinlan AO​, Australian Ambassador to Indonesia
- 2019-01-04 · Christiane Doris Wasfy: For the Love of Tourism
- 2019-01-04 · An Interview with H.E. Vegard Kaale, Ambassador of Norway to Indonesia
- 2019-01-04 · Introducing the World's Best Education System to Indonesia
- 2019-05-31 · A Conversation with Madame Rachel Malik, Spouse of the British Ambassador to Indonesia
- 2020-04-09 · The Story of Doctor Debryna Dewi Lumanaw
- 2022-12-30 · Interview with Benjamin Giles: Commissioner of the Queensland State Government to Indonesia
- 2024-10-18 · AANOUKIS Swimwear Founder Alexandra Adamiak on Empowering Women Through Fashion

**Cue instrument.** type: editorial 77%, stay 9%, eat 7%, event 3% (coverage 91%); format: people 57%, review 9%, news 9%, opinion 9% (coverage 69%); period-stamped titles 0%; roundups 0%; median first-person density 25.8/1000 words.

**Places named in title/lead.** jakarta 71, bali 5, surabaya 2, yogyakarta 1, ubud 1, nusa-dua 1; 6% name only a place outside jakarta.

**Co-filed with.** Business 2; 97 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.81 vs baseline 0.76; leakage 41% (cross-type 2%). Cohesion 0.807 (baseline 0.756), leakage 41% → Business (11), Culture (4), Health (3), Education (3); best split k=3 silhouette 0.157.
- cluster 1: 51 (52%) `editorial`/`people` — An Interview with H.E. Vegard Kaale, Ambassador of Norway to Indonesia; An Interview with H.E. Peter MacArthur, Ambassador of Canada to Indone; An Interview with H.E. Johanna Brismar-Skoog, Ambassador of Sweden to 
- cluster 2: 25 (25%) `editorial`/`people` — Introducing Christophe Bernard Keramaris; An Interview with Alexander Nayoan Chairman Of The Jakarta Hotels Asso; Metta Murdaya: Championing Jamu and Indonesia's Herbal Traditions
- cluster 3: 23 (23%) `editorial`/`review` — An Interview with Maya Nelson, At the Helm of Jakarta Intercultural Sc; Ade Putri Paramadita: The Culinary Storyteller; Julia Suryakusuma: Still Fighting for What is Right

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `people` · format `people` · location `jakarta` · agrees: True · split: False · confidence high. All titles are interviews or profiles of notable individuals, consistently matching editorial type, people subtype, and people format for Jakarta.

**E1.4 draft.** confidence high, decision_needed False

### Health — resolved (D05, D13)

*99 published · 2019–2026 · parent: Lifestyle · Yoast primary on 28 · slug `health` · term 2721*

> Editor's description: How to get Healthy, Fit and Happy. Discover the latest health news from the world's most trusted health news source.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · topic: health · confidence **medium** · decisions D05, D13

**Resolution.** basis D05, D13; unchanged.

**Reasoning.** Carried as E1.4's recommendation (topic health always; wellness/* when a venue is the subject, else editorial/lifestyle) -- only the vocabulary approvals are open. \| E1.4: Depends on approving `editorial/lifestyle`.

**Alternates for the classifier.** wellness/clinic\|gym\|spa + news\|review; editorial/lifestyle + feature

**Representative titles (spread across the date range).**
- 2019-01-04 · Spa Treatments at Mandarin Oriental Jakarta Ensure Revitalisation
- 2019-01-04 · Stay Young with L'Oréal
- 2019-01-04 · What’s On at the Gym
- 2019-03-04 · Five Couples' Bonding Experiences To Try in Bali
- 2019-10-21 · Beer Spa: The Answer for Your Glowing Skin
- 2023-09-29 · The Science of Nutrigenomics: How Different Genetics Respond to Nutrition
- 2025-07-01 · From Clubs to Courts: The Rise of Social Sports in Jakarta
- 2026-08-12 · Wellness on the Itinerary at Archipelago Hotels

**Cue instrument.** type: wellness 80%, editorial 7%, do 4%, shop 4% (coverage 75%); format: news 31%, offer 22%, opinion 9%, review 9% (coverage 46%); period-stamped titles 1%; roundups 1%; median first-person density 2.0/1000 words.

**Places named in title/lead.** jakarta 45, bali 7, yogyakarta 5, south-jakarta 4, central-jakarta 3, puncak 1; 9% name only a place outside jakarta.

**Co-filed with.** Sports & Activities 3, Experience Offers 3, News 2; 88 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.772 (baseline 0.756), leakage 24% → Shopping (4), Sports & Activities (3), Community (3), Travel (2); best split k=2 silhouette 0.135.
- cluster 1: 64 (65%) `wellness`/`news` — Refresh and Revitalise at Spa Houses that Inspired by Nature & Traditi; 10 Best Spas in Jakarta: Top Massage & Wellness Centres; Javanese Face Lift Massage Enhances Natural Beauty
- cluster 2: 35 (35%) `wellness`/`opinion` — Stunting in Indonesia: What is it and how to prevent it?; Diabetes It's All About A Healthy Lifestyle; Planning to Move to Indonesia? Make Sure You Have These Five Vaccines!

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: True · split: True → wellness-spa, fitness, medical-hospital · confidence high. Titles span spa, fitness, hospitals, skincare, and general health editorial, so type and format vary per article; location defaults to Jakarta as the magazine's scope.

**E1.4 draft.** confidence medium, decision_needed True — Is 'Health' a venue category or a subject? Evidence is ~50/50: venue pieces (Siloam Hospitals -> wellness/clinic, Celebrity Fitness -> wellness/gym, Sepik -> wellness/spa) vs service journalism ('Are You Really Fit for Work?'). Recommend: topic health always; type per article — wellness/* when a venue is the subject, else editorial/lifestyle (proposed) + feature.

### World Traveller — resolved (D06)

*94 published · 2019–2025 · parent: Travel · Yoast primary on 11 · slug `world-traveller` · term 2757*

> Editor's description: World Traveller is news about travelling, the process of learning, and the experiences in the great big world.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `city-guide` · format `city-guide` · location `international` · topic: travel · confidence **high** · decisions D06

**Resolution.** basis D06; unchanged — location `international` (geo_scope abroad): searchable, Row 3 eligible, never Row 2 or the itinerary. Children of `international` are picked per article once the 22 destination nodes are seeded..

**Reasoning.** Carried; only the `international` root approval (D06) is open. \| E1.4: 82 of 94 from 2019. Evergreen format.

**Representative titles (spread across the date range).**
- 2019-01-04 · Destinations Around the World for a Quiet New Year’s Celebration
- 2019-01-04 · What’s New in Thailand This Year
- 2019-01-04 · Dubai For All
- 2019-01-04 · London Off The Beaten Path
- 2019-01-04 · Portugal Won 24 Tourism Oscars
- 2019-02-13 · Winter Highlight in France
- 2019-12-23 · Taiwan: Pioneers of Technology, Leaders in Tourism
- 2025-10-10 · Aman Sets Their Sights on Singapore for Their Latest Urban Sanctuary

**Cue instrument.** type: do 40%, eat 16%, event 14%, editorial 9% (coverage 74%); format: heritage 28%, city-guide 25%, review 16%, event 10% (coverage 72%); period-stamped titles 7%; roundups 2%; median first-person density 1.1/1000 words.

**Places named in title/lead.** jakarta 22, kota-tua 2, scbd 1, bali 1, denpasar 1; 0% name only a place outside jakarta.

**Co-filed with.** Travel 1, Stay Offers 1; 92 carry this category alone.

**Coherence** (mixed, against the E2.0 proposal). cohesion 0.75 is no higher than the random baseline 0.76 for a set this size. Cohesion 0.753 (baseline 0.756), leakage 23% → Art (4), Dining News (3), Travel (3), Business (2); best split k=2 silhouette 0.06.
- cluster 1: 64 (68%) `do`/`city-guide` — The Flying Affairs; Summer, Winter, Spring   and Autumn in Hong Kong; Cruising Into The Heart of Bavaria
- cluster 2: 30 (32%) `event`/`heritage` — Sparkling Singapore; Get Lost in Singapore; Living Like A Local in Singapore

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `guide` · location `per-article` · agrees: False · split: True → destination-guides, travel-industry-news · confidence medium. Most titles are destination guides/features covering countries not cities, so city-guide is too narrow; location varies per article and some entries are industry news rather than guides.

**E1.4 draft.** confidence high, decision_needed True — Approve the proposed `international` location root. `location` is a required facet and 115 articles (World Traveller + part of Travel) are about Singapore, Australia, Bhutan, Hong Kong. Children can be added once E2.1 reports the destination distribution.

### History & Heritage — resolved (D14)

*74 published · 2019–2026 · parent: Discover Jakarta · Yoast primary on 41 · slug `history-heritage` · term 2697*

> Editor's description: Jakarta being the capital of Indonesia, is rich in history and heritage, still awaiting to be discovered. Explore NOW! Jakarta.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `heritage` · format `heritage` · location `jakarta` · topic: heritage · confidence **high** · decisions D14

**Resolution.** basis D14; unchanged.

**Reasoning.** Evergreen. One misfiled promo ('The Maj Senayan') -> classifier override.

**Alternates for the classifier.** location kota-tua \| menteng \| gambir when the piece is about a place; eat/street-food + heritage for food-heritage pieces ('Betawi Satay')

**Representative titles (spread across the date range).**
- 2019-01-04 · Arumdalu: An Urban Farm Honours the Past and Welcomes the Future
- 2019-01-04 · Jakarta Bar Guide: B.A.T.S & Nautilus Bar
- 2019-01-04 · Kid-Friendly Adventures in and Around Jakarta
- 2019-09-13 · Jakarta’s Eco-friendly Bulk Stores
- 2023-06-16 · Sunda Kelapa and the Birth of Jakarta
- 2024-07-08 · Bubur Ase: A Special Betawi Porridge
- 2025-05-05 · Sweet Betawi Bites
- 2026-07-03 · The Distinctive Flavours of Betawi Satay

**Cue instrument.** type: editorial 40%, eat 18%, do 18%, shop 13% (coverage 74%); format: heritage 80%, offer 9%, news 7%, city-guide 2% (coverage 74%); period-stamped titles 4%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 62, kota-tua 5, bogor 4, glodok 4, tangerang 3, west-jakarta 3; 0% name only a place outside jakarta.

**Co-filed with.** Discover Jakarta 2; 72 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.79 vs baseline 0.76; leakage 64% (cross-type 20%). Cohesion 0.793 (baseline 0.758), leakage 64% → City Guides (11), Discover Jakarta (8), Stay Offers (3), Culture (3); best split k=2 silhouette 0.147.
- cluster 1: 55 (74%) `editorial`/`heritage` — Take a tour of Chinese-Indonesian Historical Sites in Jakarta; Excursion to Trendy Markets in Jakarta; Kampung Tugu: Portuguese Traces in North Jakarta
- cluster 2: 19 (26%) `editorial`/`heritage` — Betawi Culture, in a Nutshell; Sweet Betawi Bites; The Rich Flavours of a Traditional Betawi Lebaran

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `heritage` · format `heritage` · location `jakarta` · agrees: True · split: True → heritage-culture, city-discovery · confidence medium. Core heritage titles fit the proposal, but many titles are general city discovery (transport, aquarium, shops, events) that belong to other types and formats.

**E1.4 draft.** confidence high, decision_needed False

### Culture — resolved (D04)

*67 published · 2019–2026 · parent: Art & Culture · Yoast primary on 17 · slug `culture` · term 2690*

> Editor's description: Jakarta is the most populous city in Indonesia and is the country's capital as well. Jakarta's culture is always changing with new and modern trends.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `culture` · format `feature` · location `jakarta` · topic: culture · confidence **medium** · decisions D04

**Resolution.** basis D04; unchanged.

**Reasoning.** Carried; depends on D04 only. \| E1.4: Textiles, books, magazines, dance — coverage of culture that is neither an event nor a venue.

**Alternates for the classifier.** do/museum + guide (Museum Tekstil); shop/boutique\|artisan + news (Batik Corner, Gramedia); format review for book pieces

**Representative titles (spread across the date range).**
- 2019-01-04 · Inside the Recently Renovated Erasmus Huis
- 2019-01-04 · Engage and Inspire at the Goethe-Institut
- 2019-01-04 · Indonesian Textiles Between Tradition and Technology
- 2019-09-11 · World Press Photo Exhibition 2019
- 2020-01-16 · Arts and the City in the Eye of Hafiz Rancajale
- 2022-11-24 · Ancient Javanese Indigo Batik Explored in Zahir Widadi's New Book
- 2024-03-11 · History and Importance of Rice in Indonesia
- 2026-06-18 · Gramedia Keeps the Pages Turning

**Cue instrument.** type: editorial 47%, event 31%, shop 10%, do 8% (coverage 76%); format: heritage 52%, event 26%, news 11%, opinion 6% (coverage 69%); period-stamped titles 3%; roundups 0%; median first-person density 3.1/1000 words.

**Places named in title/lead.** jakarta 32, yogyakarta 5, bandung 3, surabaya 2, menteng 2, cikini 2; 9% name only a place outside jakarta.

**Co-filed with.** Art 2, Features 1, Opinion 1; 62 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.78 vs baseline 0.76; leakage 55% (cross-type 10%). Cohesion 0.782 (baseline 0.758), leakage 55% → Art (6), Features (4), Events (3), Shopping (3); best split k=2 silhouette 0.061.
- cluster 1: 37 (55%) `editorial`/`heritage` — A Historic Look into Indonesian Wedding Traditions, A Fusion of Cultur; Museum Tekstil Jakarta: Showcases Lives of Women Weavers; Ancient Javanese Indigo Batik Explored in Zahir Widadi's New Book
- cluster 2: 30 (45%) `editorial`/`heritage` — Fostering Cultural Dialogue Between the Netherlands and Indonesia; Erasmus Huis, A Home for Dutch Culture in Jakarta; Inside the Recently Renovated Erasmus Huis

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `per-article` · location `per-article` · agrees: False · split: False · confidence medium. Type and subtype fit, but titles span features, event coverage, and news across multiple locations (Jakarta, Surakarta, Borobudur), so format and location are per-article.

**E1.4 draft.** confidence medium, decision_needed True — Depends on approving `editorial/culture`.

### Sports & Activities — resolved (D11)

*61 published · 2019–2026 · parent: Lifestyle · Yoast primary on 11 · slug `sports-activities` · term 2708*

> Editor's description: Discover latest updates, events and highlights of sport and activities all over the world.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · topic: sports · confidence **medium** · decisions D11

**Resolution.** basis D11; unchanged.

**Reasoning.** Carried as E1.4's recommendation; only the subtype approval (D11) is open. \| E1.4: 44 of 61 from 2019.

**Alternates for the classifier.** event/sports + event; do/sports-activity + guide\|news; editorial/lifestyle + feature; wellness/gym for fitness venues

**Representative titles (spread across the date range).**
- 2019-01-04 · Memorable Moments from Asian Para Games 2018
- 2019-01-04 · Indonesia Races Against Time to Host Its First Triathlon in September
- 2019-01-04 · Singapore Hosts European Football Giants for International Champions Cup
- 2019-01-04 · Jakarta Komodos Junior Rugby Club Launch 2017 Season
- 2019-02-13 · Indonesia Garudas Win AFL All-Asian Cup
- 2019-12-16 · A Sporting Chance for Kids
- 2025-04-16 · Smash Padel Simatupang: An Expansive Padel Centre Opens in South Jakarta
- 2026-06-29 · Asian Tigers Golf Tournament 2026 Celebrates 12 Years of Golf for Conservation

**Cue instrument.** type: do 33%, event 21%, wellness 21%, editorial 19% (coverage 70%); format: listing 40%, event 26%, news 16%, heritage 5% (coverage 62%); period-stamped titles 20%; roundups 2%; median first-person density 3.5/1000 words.

**Places named in title/lead.** jakarta 34, bali 4, south-jakarta 3, bogor 3, senayan 2, surabaya 2; 3% name only a place outside jakarta.

**Co-filed with.** Health 3, Events 3, Education 1; 55 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.789 (baseline 0.759), leakage 18% → Health (7), Community (1), Opinion (1), Education (1); best split k=2 silhouette 0.132.
- cluster 1: 36 (59%) `event`/`listing` — Indonesia Raya: Triumph in the All Asia Cup 2016; Gearing up for Indonesia Ultimate Golf Series 2016-2017; A Sporting Chance for Kids
- cluster 2: 25 (41%) `wellness`/`news` — Ready, Set, GO!; From Clubs to Courts: The Rise of Social Sports in Jakarta; Urban Climbers

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → sports-events, sports-venues, sports-people · confidence medium. Titles span events, venue reviews, people profiles, and news with both Jakarta and international locations, so location cannot be fixed to jakarta.

**E1.4 draft.** confidence medium, decision_needed True — Three different things share this category: spectator/charity fixtures (Asian Tigers Golf Tournament -> event/sports + event), participatory venues and clubs (Urban Climbers -> proposed do/sports-activity), and features about sport (traditional sports, Asian Games -> editorial/culture\|lifestyle + feature). Recommend approving `do/sports-activity` and letting the classifier pick among the three.

### Offers — resolved (D02)

*55 published · 2020–2026 · top-level · Yoast primary on 29 · slug `offers` · term 2705*

> Editor's description: Discover dining and stay offers in the most exclusive and luxurious hotels in the world. Top-rated hotel for stay, private dining, and dining in.

**Resolved prior** (E1.4 draft (carried)): type `stay` · subtype `hotel` · format `offer` · location *per article* · - · confidence **high** · decisions D02

**Resolution.** basis D02; unchanged.

**Reasoning.** The parent category used directly since 2020 (55 posts); overwhelmingly hotel festive packages. Location per article (Bandung, Gading Serpong, Kuningan, PIK). Same expiry problem as Dining Offers.

**Alternates for the classifier.** event/conference + offer for MICE pieces ('Bekasi Means Business')

**Representative titles (spread across the date range).**
- 2020-01-17 · Embrace the Spirit of the Lunar New Year at COMO Uma Ubud
- 2020-02-13 · A Lovely Weekend at Intiwhiz Properties Across Indonesia
- 2020-05-06 · Staying Healthy and Living Well with InterContinental Jakarta Pondok Indah
- 2023-02-17 · Le Dîner d’Épicure: 6 Hands Collaboration Dinner at AMUZ Gourmet Jakarta
- 2023-11-17 · The Exclusive Chateau Margaux Dinner: A 7-Course Wine Dinner at AMUZ Gourmet
- 2025-05-30 · Live The Journey at ASR Festival 2025 with Unbeatable Offers & Deals
- 2025-12-01 · Sail into 2026 with a Pirate's Party at Royal Tulip Gunung Geulis Resort & Golf
- 2026-07-28 · Bekasi Means Business: Inside Marriott’s Integrated MICE Destination

**Cue instrument.** type: stay 43%, eat 33%, wellness 12%, event 6% (coverage 93%); format: offer 74%, news 13%, event 8%, city-guide 4% (coverage 86%); period-stamped titles 36%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 32, bali 5, ubud 3, bandung 3, canggu 2, uluwatu 2; 22% name only a place outside jakarta.

**Co-filed with.** Experience Offers 20, Bali Updates 9, Explore Indonesia 5; 19 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.812 (baseline 0.76), leakage 66% → Bali Updates (8), Dining Offers (7), Experience Offers (6), Stay Offers (4); best split k=3 silhouette 0.088.
- cluster 1: 23 (42%) `stay`/`offer` — A Journey of Impeccable Taste: Alila Villas Uluwatu & Park Hyatt Jakar; Ring in the School Holidays with Family Moments at Mandarin Oriental, ; Special Deals Offered by Holiday Inn & Suites Jakarta Gajah Mada Comme
- cluster 2: 18 (33%) `stay`/`offer` — Immerse in a Holiday Season of Feasts & Cheer at 25hours Hotel Jakarta; Celebrate the Festivities in Style at The Ritz-Carlton Jakarta, Pacifi; A Mountain Christmas and a Starlit New Year at Novus Giri
- cluster 3: 14 (25%) `wellness`/`offer` — Embrace the Spirit of the Lunar New Year at COMO Uma Ubud; Celebrate Lunar New Year at the Stylish COMO Uma Canggu; Celebrate Ramadan in Comfort at DoubleTree by Hilton Jakarta – Diponeg

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `offer` · location `per-article` · agrees: False · split: True → stay-offers, dining-offers, event-offers · confidence medium. Titles span hotel stays, dining events, and festive celebrations across multiple cities, so type and subtype cannot be fixed to stay/hotel; format is consistently offer but location varies per article.

**E1.4 draft.** confidence high, decision_needed False

### Music — resolved (D02)

*49 published · 2019–2025 · parent: Art & Culture · Yoast primary on 4 · slug `music` · term 2672*

> Editor's description: We all love listening to music. This is the update with the latest news about the music, festival, and orchestra at NOW Jakarta.

**Resolved prior** (E1.4 draft (carried)): type `event` · subtype `concert` · format `event` · location `jakarta` · topic: music · confidence **high** · decisions D02

**Resolution.** basis D02; unchanged.

**Reasoning.** 38 of 49 from 2019 — all expired events; the 14-day half-life plus ends_at expiry handles them.

**Alternates for the classifier.** editorial/culture + feature for scene pieces ('Hollywood in Jakarta'); event/festival for We The Fest / Papandayan Jazz Fest

**Representative titles (spread across the date range).**
- 2019-01-04 · Kenny G Concert in Jakarta: A Night of Nostalgia
- 2019-01-04 · “Voyage to Marege”: Music From Across The Ocean
- 2019-01-04 · May Monsters for Music Maniacs
- 2019-01-04 · August Concerts
- 2019-02-13 · Bespoke
- 2019-05-31 · Honouring Historical Relations
- 2020-03-20 · Studio Eksotika: Paradise for Audiophile
- 2025-10-08 · The Papandayan Jazz Fest 2025 Celebrates a Decade of Harmony and Cultural Resonance

**Cue instrument.** type: event 92%, editorial 3%, drink 3%, stay 3% (coverage 80%); format: event 83%, news 9%, listing 6%, heritage 3% (coverage 71%); period-stamped titles 18%; roundups 0%; median first-person density 4.3/1000 words.

**Places named in title/lead.** jakarta 30, cikini 3, bandung 2, makassar 1, bali 1, nusa-dua 1; 4% name only a place outside jakarta.

**Co-filed with.** Events 4; 45 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.78 vs baseline 0.76; leakage 14% (cross-type 2%). Cohesion 0.784 (baseline 0.76), leakage 14% → Events (2), Love & Romance 2020 (1), Music & Nightlife (1), Bali Updates (1); best split k=3 silhouette 0.103.
- cluster 1: 28 (57%) `event`/`event` — Jakarta Simfonia Orchestra Put on a Magnificent Performance of Bach’s ; The Jakarta Concert Orchestra Presents Symphony For the Nation 2025: 8; Jakarta Concert Orchestra Once Again Presents A Symphony of Emotions: 
- cluster 2: 17 (35%) `event`/`event` — Fresh and Groovy Java Jazz Festival 2020; Embrace the Diversity of Music at the 15th Java Jazz Festival; 19 Acts, Five Entertainment Zones, the Lead up to We The Fest 2019!
- cluster 3: 4 (8%) `?`/`news` — Good Music: Bare Necessities of Our Lives; Bespoke; DeWolff: Music That Blows Your Mind

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → Concerts & Performances, Music Festivals, Music Features & Reviews · confidence medium. Mix of event listings, festival coverage, artist profiles, and editorial features; subtype and format vary per article, though location is consistently Jakarta.

**E1.4 draft.** confidence high, decision_needed False

### Green Living — resolved (D05)

*47 published · 2019–2025 · top-level · Yoast primary on 8 · slug `green-living` · term 2752*

> Editor's description: Environmentally conscious individuals are getting inspired by the green living in Indonesia and they are taking it as a model to save their oceans.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · topic: sustainability · confidence **high** · decisions D05

**Resolution.** basis D05; unchanged.

**Reasoning.** Exactly the §4 worked example: a topic, not a type. Topic is certain; type and format per article.

**Alternates for the classifier.** editorial/opinion + opinion (columns); editorial/lifestyle + guide ('Going Green in Jakarta: Recycling, Composting...'); event/conference + event (MVB Sustainability Forum); stay/hotel + news (Santika 'Spirit of Sustainability')

**Representative titles (spread across the date range).**
- 2019-03-18 · Guide to Sustainable Living by Susan Poku
- 2019-07-12 · Sorting Waste: A Simple Way to a Healthier Life
- 2019-08-19 · What Does it Take to Make Indonesia a Sustainable Tourism Destination?
- 2019-12-19 · A Less Waste Year-End Celebration
- 2020-02-21 · Starbucks to Gradually Replace Its Plastic Straw with Paper
- 2020-04-13 · BritCham’s First Environmental Series Aimed to Spread the Awareness
- 2022-08-03 · Do You Actually Know The Benefits of Solar Energy?
- 2025-10-15 · Lead the Way to a Greener Hospitality Industry at TRANSFORMATION - MVB Sustainability Forum 2025

**Cue instrument.** type: editorial 82%, eat 8%, event 3%, do 3% (coverage 81%); format: listing 27%, news 27%, guide 12%, city-guide 12% (coverage 55%); period-stamped titles 8%; roundups 0%; median first-person density 6.0/1000 words.

**Places named in title/lead.** jakarta 21, bandung 3, bali 2, central-jakarta 1, thamrin 1, komodo 1; 13% name only a place outside jakarta.

**Co-filed with.** Events 1; 46 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.811 (baseline 0.76), leakage 17% → Property Architecture Design (3), City Guides (1), Made In Indonesia (1), Uncategorized (1); best split k=3 silhouette 0.144.
- cluster 1: 23 (49%) `editorial`/`listing` — Learn How to Manage Your Waste with Waste4Change; Going Green in Jakarta: Recycling, Composting and Responsible Waste Ma; Indonesia Clean-from-Waste 2025: What the Business Sector Can Do
- cluster 2: 17 (36%) `editorial`/`news` — What Does it Take to Make Indonesia a Sustainable Tourism Destination?; MVB on Sustainability for Key Economic Sectors; Lead the Way to a Greener Hospitality Industry at TRANSFORMATION - MVB
- cluster 3: 7 (15%) `editorial`/`listing` — Starting at Home, It’s Time to Measure Our Personal Carbon Footprint; Environmental Relief in the Midst of Pandemic; Making a Sustainable Home: Designing an Eco-Friendly House

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → sustainability-guides, green-business-events, environmental-news · confidence medium. Titles span guides, news, events, and features with locations ranging from Jakarta to Bandung to Indonesia-wide, so location is per-article not fixed to Jakarta.

**E1.4 draft.** confidence high, decision_needed False

### Kids & Family — resolved (as proposed)

*46 published · 2019–2026 · parent: Lifestyle · Yoast primary on 8 · slug `kids-family-life` · term 2751*

> Editor's description: NOW! Jakarta is a website for kids and family. It provides a friendly platform for parents, guardians and kids to connect with each other.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · audience: family; topic: family · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Exactly the §4 worked example: an audience, not a type.

**Alternates for the classifier.** do/attraction + guide ('Jakarta for Kids', Taman Safari); stay/hotel + offer (DoubleTree family getaway); editorial/lifestyle + feature (summer ideas)

**Representative titles (spread across the date range).**
- 2019-01-04 · Aqua Camp Offers Family an Undersea Getaway
- 2019-01-04 · Beautiful Essentials
- 2019-01-04 · Digital Parenting
- 2019-05-03 · Options and Demand Increasing for International Schools in SE Asia
- 2019-06-17 · Nature Learning at Royal Safari Garden
- 2020-03-11 · Thermos for Every Need
- 2024-03-05 · New Wildlife Discoveries at Taman Mini Indonesia Indah
- 2026-04-07 · A City for Curious Learners: Inspiring Destinations For Young Minds

**Cue instrument.** type: do 46%, editorial 40%, eat 6%, shop 6% (coverage 76%); format: offer 36%, opinion 20%, news 16%, guide 8% (coverage 54%); period-stamped titles 2%; roundups 4%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 28, bogor 2, bandung 1, scbd 1, bali 1, central-bali 1; 4% name only a place outside jakarta.

**Co-filed with.** Education 2, Experience Offers 1, City Guides 1; 42 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.758 (baseline 0.76), leakage 70% → Education (8), City Guides (4), Explore Indonesia (3), Design (2); best split k=2 silhouette 0.19.
- cluster 1: 34 (74%) `do`/`offer` — A City for Curious Learners: Inspiring Destinations For Young Minds; Jakarta for Kids: The Best Spots in the City for Weekends and Holidays; Staying Stimulated: Jakarta’s Summer Activities for Kids
- cluster 2: 12 (26%) `eat`/`offer` — It's Fun Outside; Designed For Everyone; Playful Touches

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → kids-activities, education, family-lifestyle · confidence high. Titles span activities, schools, shopping, spa, and Bali trips, so type, format, and location all vary per article; location is not always Jakarta.

**E1.4 draft.** confidence high, decision_needed False

### Made In Indonesia — resolved (as proposed)

*39 published · 2019–2025 · parent: Art & Culture · Yoast primary on 21 · slug `made-in-indonesia` · term 2709*

> Editor's description: Get the latest and updated information on what is made in Indonesia only at NOW Jakarta on this site.

**Resolved prior** (E1.4 draft (carried)): type `shop` · subtype `artisan` · format `feature` · location `indonesia` · topic: local-brands · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** Local makers and brands. Type shop/artisan when a brand or product is the subject (most), else editorial/people. Nationwide -> root node `indonesia`.

**Alternates for the classifier.** editorial/people + people ('Meet the Makers'); location per article when the maker is placed (North Sumatra coffee)

**Representative titles (spread across the date range).**
- 2019-01-04 · Kandura: Shaping the Modern Kenduri
- 2019-01-04 · Topiku: Converting Discarded Items into Unique Hats
- 2019-12-13 · Kemala Home Living: A Green Alternative in Home Decorating
- 2022-12-07 · Savis Tea: A Showcase of Indonesia's Rich Tea Bounty
- 2024-01-08 · Mazaraat Cheese: A Story of an Indonesian Artisanal Cheese Producer
- 2024-07-15 · Waste Not, Want Not: Crafting Furniture and Fashion from Agroforestry Waste with MYCL
- 2025-05-06 · Biomaterials, Brewed Better: Bell Living Lab's Innovative Use of Coffee Byproducts
- 2025-11-05 · Design That Wakes Us Up: Dit Réveille’s Journey from Plastic Scraps to Modern Furniture

**Cue instrument.** type: shop 56%, eat 16%, editorial 8%, wellness 8% (coverage 64%); format: news 33%, heritage 27%, offer 13%, people 13% (coverage 38%); period-stamped titles 0%; roundups 0%; median first-person density 3.0/1000 words.

**Places named in title/lead.** jakarta 4, bandung 2, kemang 1, raja-ampat 1; 8% name only a place outside jakarta.

**Co-filed with.** Features 2, The Culinary Issue 1; 36 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.76; leakage 23% (cross-type 10%). Cohesion 0.799 (baseline 0.761), leakage 23% → A Jakarta Smorgasbord (3), Design (2), Shopping (2), Community (1); best split k=2 silhouette 0.118.
- cluster 1: 25 (64%) `shop`/`heritage` — Ayumu Gendouts: A Funky Twist on Indonesian Woven Crafts; Exploring the Rich Tapestry of Indonesian Textiles; Torajamelo, Preserving Indonesia's Ancient Artisanal Weaving
- cluster 2: 14 (36%) `eat`/`news` — Meet the Makers: Food Edition; Indonesia’s Finest Tea; Savis Tea: A Showcase of Indonesia's Rich Tea Bounty

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `shop` · subtype `artisan` · format `feature` · location `indonesia` · agrees: True · split: True → artisan-crafts, artisan-food-drink · confidence high. Consistently feature profiles of Indonesian makers and producers, but roughly half are food/drink artisans better served by eat/drink types rather than shop.

**E1.4 draft.** confidence medium, decision_needed False

### Film — resolved (D12)

*35 published · 2019–2026 · parent: Art & Culture · Yoast primary on 6 · slug `film` · term 2716*

> Editor's description: NOW! Jakarta magazine is one of the best film magazines from Indonesia. Here is the latest news of NOW! Jakarta's film archives.

**Resolved prior** (E1.4 draft (carried)): type `event` · subtype `screening` · format `event` · location `jakarta` · topic: film · confidence **medium** · decisions D12

**Resolution.** basis D12; unchanged.

**Reasoning.** Carried as E1.4's recommendation (event/screening); only D12 is open. \| E1.4: 28 of 35 from 2019.

**Alternates for the classifier.** editorial/culture + review for film reviews ('Daly City')

**Representative titles (spread across the date range).**
- 2019-01-04 · Promoting Tolerance through Film: A Conversation with Monique Rijkers
- 2019-01-04 · The Golden Globes 2018: Women Power on Screen
- 2019-01-04 · German Filmmakers Explore Indonesia’s Remote Islands
- 2019-01-04 · Entree For Entries
- 2019-01-04 · Festival Puts Spotlight on Australian Cinema
- 2019-02-13 · A Man in a Man's World
- 2025-04-21 · Experience the Italian Film Festival 2025: Venice In Jakarta
- 2026-07-30 · 100% Manusia Film Festival Marks 10 Years with 'A Decade of Love Language'

**Cue instrument.** type: event 89%, do 7%, editorial 4% (coverage 77%); format: event 82%, news 14%, listing 4% (coverage 63%); period-stamped titles 31%; roundups 0%; median first-person density 2.6/1000 words.

**Places named in title/lead.** jakarta 15, bali 5, yogyakarta 4, thamrin 3, medan 3, ubud 2; 9% name only a place outside jakarta.

**Co-filed with.** Events 4; 31 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.79 vs baseline 0.76; leakage 9% (cross-type 3%). Cohesion 0.793 (baseline 0.761), leakage 9% → Kids & Family (1), World Traveller (1), Art (1); best split k=2 silhouette 0.265.
- cluster 1: 26 (74%) `event`/`event` — Showcasing the Quality of European Films; Enjoy Bold, Inclusive Cinema as Europe on Screen Turns 25; Bali International Indigenous Film Festival Returns with  a Packed Lin
- cluster 2: 9 (26%) `event`/`news` — Entree For Entries; Oscars 2018 Committed to Promise an Inclusion for Future Films; A Tech Savvy Year Ahead

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `event` · subtype `screening` · format `per-article` · location `per-article` · agrees: False · split: True → Film Festivals & Screenings, Film News & Awards · confidence medium. Most titles cover Jakarta film festivals and screenings, but some are news about international awards (Oscars, Golden Globes) and one references Bali, so format and location vary per article.

**E1.4 draft.** confidence medium, decision_needed True — Approve the proposed `event/screening` subtype (film festivals are the majority: 100% Manusia, Festival Sinema Prancis, Europe on Screen, Balinale). Fallback if rejected: event/festival.

### Art & Culture — resolved (D04, D10)

*28 published · 2023–2026 · top-level · Yoast primary on 26 · slug `art-and-culture` · term 2671*

> Editor's description: Art & Exhibition Explore news about art and culture in NOW! Jakarta. Supporting art in various form including film, music, design and local hidden heritage.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format *per article* · location `jakarta` · topic: art, culture · confidence **low** · decisions D04, D10

**Resolution.** basis D04, D10; unchanged.

**Reasoning.** Parent container used directly since 2023; topic art/culture only, everything else per article. D10 makes it moot when a child is present. \| E1.4: Parent category used directly since 2023 (28 posts, 26 Yoast-primary). Only the topic is inferable; everything else per article.

**Alternates for the classifier.** event/performance\|exhibition + event (SIPFest, Art Jakarta Papers); editorial/culture + feature (Teater Keliling at 50); editorial/heritage + heritage (Kali Besar, Borobudur); stay/hotel + offer (Gaia Hotel weekend)

**Representative titles (spread across the date range).**
- 2023-02-07 · Art Jakarta Gardens Returns to Capture Young Art Enthusiasts
- 2023-10-31 · Celebrating 50 Years of the Jakarta Theatre Festival
- 2025-01-07 · Jakarta’s Cultural Communities: Seeking the Artistic Connection
- 2025-05-19 · Goethe-Institut's 'Living at the Urban Seafront' Exhibition Puts Coastal Communities in Frame
- 2025-07-29 · Bali Island in Early Photography
- 2026-01-27 · Art Jakarta Papers 2026: A New Fair Dedicated to the Power of Paper
- 2026-06-24 · ARTJOG 2026 Celebrates Art Across Generations
- 2026-08-18 · A Weekend in Tune at The Gaia Hotel Bandung

**Cue instrument.** type: event 41%, editorial 29%, shop 12%, eat 12% (coverage 61%); format: heritage 38%, event 29%, news 14%, listing 14% (coverage 75%); period-stamped titles 14%; roundups 0%; median first-person density 1.7/1000 words.

**Places named in title/lead.** jakarta 12, yogyakarta 5, bali 2, bandung 2, kota-tua 1, denpasar 1; 29% name only a place outside jakarta.

**Co-filed with.** Events 2, Design 1, Community 1; 23 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.782 (baseline 0.764), leakage 54% → Art (6), Discover Jakarta (2), Made In Indonesia (1), Events (1); best split k=2 silhouette 0.098.
- cluster 1: 21 (75%) `event`/`event` — Jakarta’s Cultural Communities: Seeking the Artistic Connection; Unravelling Yogyakarta’s Street Art Scene with Begok Oner; ‘Offerings’, ArtMoments Jakarta 2026 Reimagines the Art Fair Experienc
- cluster 2: 7 (25%) `editorial`/`heritage` — Bali Island in Early Photography; Early Travels to the ‘Dutch East Indies’; Kali Besar: The Waterway of Jakarta’s Historical Past

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → Art & Exhibitions, Heritage & History, Performing Arts · confidence high. Titles span art exhibitions, theatre, heritage sites, fashion, and books across multiple cities (Yogyakarta, Bandung, Borobudur, Paris), so location is per-article, not fixed to Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Bar Guide — resolved (D01)

*28 published · 2019–2026 · parent: Dining · Yoast primary on 9 · slug `bar-guide` · term 2731*

> Editor's description: A guide to the best bars and clubs in the city and advice on the best way to get there, allow you to organize a night out in JAKARTA.

**Resolved prior** (E1.4 draft, amended by the evidence pack): type `drink` · subtype *per article* (prior `bar`) · format *per article* · location `jakarta` · - · confidence **medium** · decisions D01

**Resolution.** basis D01; unchanged.

**Reasoning.** Amended: E1.4 fixed format guide; the cue instrument reads 53% of the signal-bearing pieces as news (openings, product launches) and the titles agree -- type drink stays, format is per article with the roundups decided by D01. \| E1.4: Type drink is certain.

**Alternates for the classifier.** format listing (year-stamped roundups); format news (openings: 'OZONE Bar & Karaoke is Now Open!'); format review (single-venue: 'En Par'); subtype cocktail-bar \| pub \| rooftop-bar per article; shop/boutique + news for product pieces (Manta Spiced Rum)

**Representative titles (spread across the date range).**
- 2019-01-04 · The Singleton “Unlearn Session” Invites One to Push One’s Limits
- 2019-03-18 · A Bar Named Gina
- 2019-05-08 · Art Bar Academy: Learning from the Masters
- 2019-08-16 · Bartending Beauties at Barong Bar
- 2019-12-12 · Get Personal at Soirée
- 2023-05-26 · Inside ARTOZ Bar, Jakarta’s New Whisky Wonderland
- 2024-01-27 · The Distillers Library: A Haven for Single Malt Whisky Connoisseurs
- 2026-08-07 · The Best Cocktail Bars in Jakarta: From Speakeasies to Social Hotspots (2026)

**Cue instrument.** type: drink 96%, shop 4% (coverage 96%); format: news 53%, offer 16%, listing 16%, city-guide 10% (coverage 68%); period-stamped titles 7%; roundups 7%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 23, senopati 2, scbd 2, thamrin 1, kuningan 1, west-jakarta 1; 0% name only a place outside jakarta.

**Co-filed with.** Dining 1, Restaurant Guides 1; 27 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.82 vs baseline 0.76; leakage 14% (cross-type 7%). Cohesion 0.818 (baseline 0.764), leakage 14% → News (1), Lifestyle (1), Stay Offers (1), Dining (1); best split k=2 silhouette 0.093.
- cluster 1: 16 (57%) `drink`/`news` — Five Bar Lounges in Jakarta to Visit on the Weekend; The Best Cocktail Bars in Jakarta: From Speakeasies to Social Hotspots; Four Places to Enjoy Cocktails in Jakarta This Weekend
- cluster 2: 12 (43%) `drink`/`news` — Inside ARTOZ Bar, Jakarta’s New Whisky Wonderland; Celebrate Negroni with Style at Barong Bar; Classic Cocktails at Writers Bar, Raffles Jakarta

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `drink` · subtype `bar` · format `per-article` · location `jakarta` · agrees: True · split: False · confidence high. All titles concern bars and nightlife in Jakarta, but formats range from guides to news to reviews, so format is correctly per-article.

**E1.4 draft.** confidence medium, decision_needed True — §4 maps this to format guide, but the titles are mostly year-stamped roundups ('The Best Cocktail Bars in Jakarta ... (2026)', '8 Best Beer Bars') plus bar news/reviews. Recommend the boundary: period-stamped roundup = `listing` (540 d, series_key dedup); timeless = `guide` (evergreen). Confirm this definition — it decides whether 2019 roundups stay evergreen.

### Discover Jakarta — resolved (D10, D14)

*24 published · 2023–2026 · top-level · Yoast primary on 24 · slug `discover-jakarta` · term 2696*

> Editor's description: Discover Jakarta by following its history and heritage. NOW! Jakarta is great if you want to know more about the city's history and heritage.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `heritage` · format `heritage` · location `jakarta` · topic: heritage · confidence **high** · decisions D10, D14

**Resolution.** basis D10, D14; unchanged.

**Reasoning.** Parent category used directly since 2023 (24 posts, all Yoast-primary). Heritage-heavy; location often resolvable to a neighbourhood.

**Alternates for the classifier.** editorial/city-guide + city-guide for neighbourhood pieces (Kemayoran, Jatinegara); do/attraction + guide for places (Jakarta Library, Taman Doa); location per article: gambir \| kota-tua \| menteng ...

**Representative titles (spread across the date range).**
- 2023-02-08 · The Aesthetic Jakarta Library
- 2023-06-08 · All Saints Anglican Church: The Oldest English-Speaking Institution in Indonesia
- 2024-03-12 · An Ocean of Discovery at the Jakarta Aquarium and Safari
- 2025-08-29 · Oma Huis: A Return to Grandma’s House
- 2025-11-06 · Cikini 82: Exploring the House Where the Republic Was Born
- 2026-01-15 · Societeit de Harmonie: Before Car Parks, There Was Champagne
- 2026-05-15 · At Jatinegara, Traces of the 'True State' Remain
- 2026-09-07 · Medan Merdeka: Jakarta’s Symbolic Square of Freedom

**Cue instrument.** type: editorial 68%, event 10%, wellness 5%, eat 5% (coverage 79%); format: heritage 84%, news 16% (coverage 79%); period-stamped titles 0%; roundups 0%; median first-person density 1.1/1000 words.

**Places named in title/lead.** jakarta 20, cikini 3, west-jakarta 2, central-jakarta 2, medan 2, bogor 1; 0% name only a place outside jakarta.

**Co-filed with.** History & Heritage 2, Sites & Destinations 1; 21 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.807 (baseline 0.766), leakage 42% → City Guides (4), Sites & Destinations (3), History & Heritage (1), Hidden Heritage (1); best split k=3 silhouette 0.135.
- cluster 1: 19 (79%) `editorial`/`heritage` — Uncovering the History of Jakarta’s Northern Coastline; Tracing Indonesia’s Banking Journey in Kota Tua Jakarta; From Wilhelmina Park to Istiqlal Mosque: The History of Jakarta’s Most
- cluster 2: 3 (12%) `eat`/`news` — Urban Forest Cipete: A Haven of Green in the City; Bird Watching in Jakarta; An Ocean of Discovery at the Jakarta Aquarium and Safari
- cluster 3: 2 (8%) `event`/`news` — Buku Betawi: Palang Pintu, A Unique Betawi Proposal Tradition; Lenong Betawi: Jakarta's Vibrant Art Performance

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `heritage` · format `heritage` · location `jakarta` · agrees: True · split: False · confidence high. Titles overwhelmingly cover Jakarta's history, heritage sites, and cultural traditions, matching editorial/heritage; a few outliers like bird watching don't justify a split.

**E1.4 draft.** confidence high, decision_needed False

### Dining — resolved (D01, D10)

*24 published · 2023–2026 · top-level · Yoast primary on 20 · slug `dining` · term 2700*

> Editor's description: Through this guide, you'll get the the best places to eat and the best deals. We will be discussing the top dining places located in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type `eat` · subtype `restaurant` · format *per article* · location `jakarta` · - · confidence **high** · decisions D01, D10

**Resolution.** basis D01, D10; unchanged.

**Reasoning.** Parent category used directly since 2023 (24 posts). Type certain; format per article. Contains recipes ('The Rice Table Recipe #5') which have no §4 format — low volume, recommend editorial/lifestyle + feature rather than a new format.

**Alternates for the classifier.** format listing for '[Updated]' series ('New Restaurants in Jakarta 2026') + series_key; format guide for timeless roundups ('Breakfast in Jakarta'); format review (Henshin, Li Lian); format offer (St. Regis Sunday ritual)

**Representative titles (spread across the date range).**
- 2023-03-17 · Lokaholik, Flying the National Booze Flag!
- 2023-03-17 · A Tale of Two at Lobo & Juno
- 2024-10-01 · The Rice Table Recipe #2: Salmon Lodeh
- 2024-10-01 · The Rice Table Recipe #5: Balinese Pork Bowl
- 2025-02-03 · Continuum, A Wine Legacy Perpetuated
- 2025-11-12 · Li Lian at Park Hyatt Jakarta: A Contemporary Take on Cantonese Dining
- 2026-06-08 · Hotel Tentrem Jakarta Introduced Its Latest Dining Line-Up in Alam Sutera
- 2026-08-26 · New Restaurants in Jakarta 2026: Latest Openings [Updated]

**Cue instrument.** type: eat 88%, drink 12% (coverage 100%); format: news 38%, offer 19%, review 12%, people 12% (coverage 67%); period-stamped titles 8%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 16, kuningan 2, blok-m 1, makassar 1, sentul 1, bali 1; 4% name only a place outside jakarta.

**Co-filed with.** Reviews 7, Features 2, Offers 1; 12 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.822 (baseline 0.766), leakage 38% → Bar Guide (2), Dining Offers (2), Dining News (2), Restaurant Guides (2); best split k=2 silhouette 0.129.
- cluster 1: 15 (62%) `eat`/`news` — Brunch O'Clock: Weekend Indulgence across Jakarta; Jardino: A Contemporary Restaurant Offering Delicious Comfort Food; New Restaurants in Jakarta 2026: Latest Openings [Updated]
- cluster 2: 9 (38%) `eat`/`people` — The Rice Table: Indonesian Recipes from Jakarta’s Top Chefs; The Rice Table Recipe #5: Balinese Pork Bowl; The Rice Table Recipe #4: Bebek Goreng Renyah with Nasi Kecombrang

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → restaurant-reviews, recipes, bar-and-drink, dining-guides · confidence high. Titles span restaurants, bars, recipes, events, and guides, so subtype=restaurant is too narrow; format and subtype are genuinely per-article.

**E1.4 draft.** confidence high, decision_needed False

### Design — resolved (D04)

*24 published · 2019–2026 · parent: Art & Culture · Yoast primary on 9 · slug `design` · term 2756*

> Editor's description: NOW! Jakarta is dedicated to exhibiting and promoting Indonesian design in all its manifestations. Introducing Indonesian design to a global stage.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `culture` · format `feature` · location `jakarta` · topic: design, architecture · confidence **medium** · decisions D04

**Resolution.** basis D04; unchanged.

**Reasoning.** Depends on approving `editorial/culture`; topic design is the certain part.

**Alternates for the classifier.** event/exhibition + event (Indonesia Design Week); shop/boutique + news (Melandas launch); editorial/people + people (designer profiles); editorial/heritage + heritage (architecture history)

**Representative titles (spread across the date range).**
- 2019-01-04 · Modern Scandinavian: Hay and Montana’s Designs Showcased at Danish Ambassador’s Residence
- 2019-01-04 · Boss Design’s Exceptional Task Chairs
- 2019-05-28 · Veteran Indonesian Artist Joins Converse
- 2020-02-26 · Melandas to Launch ‘Home Harmony’ in 2020
- 2023-05-15 · Soya C(o)u(l)ture: A Fashion Material from Tofu Wastewater
- 2025-09-16 · Indonesia Design Week (IDW) 2025 Celebrates Creativity, Innovation & Collaboration
- 2026-07-15 · What Makes A Design ‘Indonesian’ Today?
- 2026-09-03 · Inside Indonesia Design Week 2026’s Biggest Edition Yet

**Cue instrument.** type: shop 47%, editorial 29%, event 12%, eat 12% (coverage 71%); format: news 44%, people 12%, listing 12%, event 12% (coverage 67%); period-stamped titles 21%; roundups 0%; median first-person density 3.1/1000 words.

**Places named in title/lead.** jakarta 9, senayan 1, bintaro 1, cikini 1, yogyakarta 1, pik 1; 4% name only a place outside jakarta.

**Co-filed with.** Architecture Property & Design 2, Art & Culture 1, Events 1; 18 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.80 vs baseline 0.77; leakage 25% (cross-type 17%). Cohesion 0.804 (baseline 0.766), leakage 25% → Shopping (3), Art Culture The Realm Of Contemporary Arts (1), Made In Indonesia (1), Property Architecture Design (1); best split k=2 silhouette 0.107.
- cluster 1: 14 (58%) `shop`/`news` — What Makes A Design ‘Indonesian’ Today?; Indonesia Design Week (IDW) 2025 Celebrates Creativity, Innovation & C; Introducing Indonesian Design to A Global Stage
- cluster 2: 10 (42%) `shop`/`news` — HAY Furniture: When Architecture Meets Fashion; Modern Scandinavian: Hay and Montana’s Designs Showcased at Danish Amb; Combining Comfort and Style at Your Home with IKEA

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `culture` · format `feature` · location `jakarta` · agrees: True · split: False · confidence medium. Predominantly design-focused feature articles; a few titles lean news or event coverage but not enough to warrant a split.

**E1.4 draft.** confidence medium, decision_needed False

### Travel — resolved (D06, D14)

*21 published · 2023–2026 · top-level · Yoast primary on 20 · slug `travel` · term 2739*

> Editor's description: Travel archives are a collection of travel guides and articles I've written over the years. Visit NOW! Jakarta for the more adventurous

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `city-guide` · format `city-guide` · location *per article* · topic: travel · confidence **medium** · decisions D06, D14

**Resolution.** basis D06, D14; unchanged.

**Reasoning.** Parent category used directly since 2023 (21 posts).

**Alternates for the classifier.** stay/resort + review\|offer (AYANA Komodo); editorial/people + people (Evan Burns); editorial/news + news (International SOS advertorial); location other/* or international per article

**Representative titles (spread across the date range).**
- 2023-02-08 · Indonesia’s ‘Monuments of Love’
- 2023-05-19 · The New Hong Kong Bucket List
- 2023-07-20 · Evan Burns: A Trailblazing Leader at the Helm of Cross Hotels & Resorts Indonesia
- 2023-12-13 · Craft Villages of Lombok
- 2024-09-20 · Inside the New Mövenpick Hotel Jakarta City Centre, Now Officially Opened
- 2025-05-22 · AYANA Komodo: A Family Adventure in the Cape of Flowers
- 2025-10-10 · 33 Indonesian Hotels & Resorts Receive Inaugural ‘MICHELIN Keys'
- 2026-06-12 · Finding Pure Escapism on Two Indonesian ‘Castaway’ Islands

**Cue instrument.** type: stay 44%, do 25%, wellness 19%, eat 6% (coverage 76%); format: city-guide 46%, news 23%, offer 15%, event 8% (coverage 62%); period-stamped titles 0%; roundups 10%; median first-person density 1.0/1000 words.

**Places named in title/lead.** jakarta 5, komodo 2, kuta 1, solo 1, belitung 1, bandung 1; 38% name only a place outside jakarta.

**Co-filed with.** Explore Indonesia 1, Bali Updates 1, World Traveller 1; 17 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.787 (baseline 0.768), leakage 48% → Explore Indonesia (3), World Traveller (3), Green Living (1), Business (1); best split k=3 silhouette 0.122.
- cluster 1: 12 (57%) `do`/`city-guide` — Finding Pure Escapism on Two Indonesian ‘Castaway’ Islands; In Search of Restful Escapes: Weekend Getaways from Jakarta; Meruorah Komodo Labuan Bajo: A Luxury in the Wild Beauty of Flores
- cluster 2: 7 (33%) `stay`/`news` — 33 Indonesian Hotels & Resorts Receive Inaugural ‘MICHELIN Keys'; Inside the New Mövenpick Hotel Jakarta City Centre, Now Officially Ope; Experience Where Hospitality Meets Innovation with New Smart Rooms by 
- cluster 3: 2 (10%) `stay`/`city-guide` — Begin Every Trip with Peace of Mind with International SOS; Hotels in the Sky: Reviewing the Best Airlines in the World (By Cabin 

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → stay-reviews-openings, destination-guides, hotel-news-people · confidence high. Category mixes hotel reviews, resort openings, destination guides, airline reviews, and people profiles across multiple locations; no single facet assignment is valid.

**E1.4 draft.** confidence medium, decision_needed False

### City Guides — resolved (D01)

*19 published · 2019–2026 · parent: Discover Jakarta · Yoast primary on 15 · slug `city-guides` · term 2767*

> Editor's description: NOW! Jakarta City Guides are now updated with new and exciting places to visit, new and interesting things to do, and new and cool places.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `guide` · location `jakarta` · - · confidence **medium** · decisions D01

**Resolution.** basis D01; unchanged.

**Reasoning.** Carried as E1.4's recommendation: NOT format city-guide -- venue roundups typed per article; guide or listing under D01. \| E1.4: 14 of 19 since 2024 — this is the current SEO-listicle programme.

**Alternates for the classifier.** shop/mall + guide; wellness/spa + listing; do/attraction + listing ('Things to do in Jakarta (2024)'); editorial/culture + feature (Library of Humor Studies)

**Representative titles (spread across the date range).**
- 2019-07-11 · Child-Friendly Parks in Jakarta
- 2022-10-18 · Jakarta's Library of Humor Studies: A Serious Place to Research Humour
- 2024-01-22 · Things to do in Jakarta (2024): Experiences & Activities
- 2024-11-07 · Exploring Jakarta’s Own "Rumah Batik"
- 2025-03-13 · Monumental Places of Worship: Religious Diversity in Jakarta
- 2025-03-17 · 6 Best Theatres in Jakarta: Beautiful Concert Halls and Performance Venues
- 2025-05-05 · Jakarta Skylines: An Open-Top Tour of Jakarta
- 2026-04-07 · A City for Curious Learners: Inspiring Destinations For Young Minds

**Cue instrument.** type: do 41%, wellness 18%, editorial 12%, event 12% (coverage 90%); format: heritage 42%, listing 17%, event 17%, opinion 8% (coverage 63%); period-stamped titles 10%; roundups 21%; median first-person density 1.0/1000 words.

**Places named in title/lead.** jakarta 19, south-jakarta 2, kota-tua 1, yogyakarta 1, solo 1, gambir 1; 0% name only a place outside jakarta.

**Co-filed with.** Health 1, Features 1, Kids & Family 1; 17 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.83 (baseline 0.769), leakage 21% → Kids & Family (1), History & Heritage (1), Sites & Destinations (1), Health (1); best split k=2 silhouette 0.096.
- cluster 1: 11 (58%) `do`/`heritage` — 11 Best Museums in Jakarta: Discover History & Heritage of the City; Things to do in Jakarta (2024): Experiences & Activities; A Visitor's Guide to Kota Tua Jakarta, The 'Old Town' of the Capital
- cluster 2: 8 (42%) `wellness`/`listing` — Best Shopping Malls in Jakarta: The Top Shopping, Dining and Entertain; 10 Best Spas in Jakarta: Top Massage & Wellness Centres; Child-Friendly Parks in Jakarta

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `guide` · location `jakarta` · agrees: True · split: False · confidence high. Titles span stay, do, wellness, shop, and editorial types but are uniformly guide-format articles about Jakarta, so type and subtype are per-article while format and location are fixed.

**E1.4 draft.** confidence medium, decision_needed True — Naming trap: these are venue roundups ('Best Shopping Malls in Jakarta', '10 Best Spas in Jakarta', 'Things to do in Jakarta (2024)'), not destination guides. Recommend: NOT format city-guide; type = the roundup's venue type per article (shop/mall, wellness/spa, do/attraction); format guide, or listing when year-stamped. Confirm.

### Restaurant Guides — resolved (D01)

*17 published · 2019–2026 · parent: Dining · Yoast primary on 15 · slug `restaurant-guides` · term 2769*

**Resolved prior** (E1.4 draft, amended by the evidence pack): type `eat` · subtype `restaurant` · format *per article* · location `jakarta` · - · confidence **medium** · decisions D01

**Resolution.** basis D01; unchanged.

**Reasoning.** Amended: E1.4 fixed format guide; 13 of 17 are 2024+ period-stamped roundups ('[Updated]', year in title) plus two news items -- type eat stays, format is per article with D01 deciding the roundups. Mirrors Bali Restaurant Guide. \| E1.4: Type certain. 13 of 17 since 2024.

**Alternates for the classifier.** format listing + series_key for '[Updated]' and seasonal roundups; format news ('BIKO Group's Next Round Begins', 2016 awards)

**Representative titles (spread across the date range).**
- 2019-01-04 · NOW! Jakarta's Best Restaurant, Bar and Cafe Awards 2016
- 2023-07-18 · Jakarta’s Delightful Delis
- 2024-01-12 · Best Chinese Restaurants in Jakarta (2024): Authentic and Elevated Chinese Cuisine
- 2024-02-09 · Valentines Day in Jakarta 2024: Romantic Dinners and Experiences
- 2024-03-01 · Steak in Jakarta: The Best Steakhouses and Grill Restaurants
- 2024-09-23 · 5 Best Omakase in Jakarta: Japanese Tasting Menus at Their Finest
- 2025-11-12 · New Restaurants in Jakarta 2025: Latest Openings [Updated]
- 2026-05-29 · BIKO Group’s Next Round Begins

**Cue instrument.** type: eat 94%, drink 6% (coverage 94%); format: offer 43%, listing 29%, news 14%, heritage 7% (coverage 82%); period-stamped titles 41%; roundups 24%; median first-person density 1.0/1000 words.

**Places named in title/lead.** jakarta 17; 0% name only a place outside jakarta.

**Co-filed with.** Bar Guide 1, Dining 1; 16 carry this category alone.

**Coherence** (mixed, against the E2.0 proposal). k=2 split (silhouette 0.13) with clusters disagreeing on decay class; cross-type leakage 0%. Cohesion 0.862 (baseline 0.771), leakage 12% → Dining Offers (1), Dining (1); best split k=2 silhouette 0.128.
- cluster 1: 11 (65%) `eat`/`offer` — Best Brunch in Jakarta: The Ultimate Weekend Indulgence; Brunches in Jakarta: A Most-Welcome Weekend Ritual; Steak in Jakarta: The Best Steakhouses and Grill Restaurants
- cluster 2: 6 (35%) `eat`/`listing` — New Restaurants in Jakarta 2025: Latest Openings [Updated]; New Restaurants in Jakarta 2024: Latest Openings [Updated]; Best Chinese Restaurants in Jakarta (2024): Authentic and Elevated Chi

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `restaurant` · format `per-article` · location `jakarta` · agrees: True · split: True → guides, new-openings, awards · confidence high. All articles concern Jakarta restaurants, but formats range from curated guides and best-of lists to news on new openings and awards, justifying per-article format and a possible split.

**E1.4 draft.** confidence medium, decision_needed True — Same guide-vs-listing boundary as Bar Guide. 'New Restaurants in Jakarta 2025 [Updated]' and the Chinese New Year roundup are period-stamped -> `listing` + series_key; 'Destination Dim Sum' is a timeless `guide`. §4's worked example says guide for the whole category.

### Hidden Heritage — resolved (D14)

*16 published · 2019–2020 · parent: Explore Indonesia · Yoast primary on 5 · slug `hidden-heritage` · term 2748*

> Editor's description: Discover the hidden heritage of Indonesia by reading our latest articles about the various places and their unique stories.

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `heritage` · format `heritage` · location `other` · topic: heritage, culture · confidence **high** · decisions D14

**Resolution.** basis D14; unchanged.

**Reasoning.** All 16 from 2019-2020; child of Explore Indonesia. Exposes a tree gap: `other` has city nodes but no regional nodes (Kalimantan, Maluku, Papua, Sulawesi). Evergreen format.

**Alternates for the classifier.** location: Kalimantan (Punan), Sulawesi (Makassar), Maluku (Banda, Seram), Belitung, Lombok — most have no node, so `other` is the honest fallback

**Representative titles (spread across the date range).**
- 2019-01-04 · Celebrating Indigenous Dance and Rituals at Gawai Festival
- 2019-01-04 · Reflecting on Indonesia’s Hidden Heritage 2017
- 2019-01-04 · A Journey Into the Heart of Ma'Anyan Country
- 2019-01-04 · Culture, Colour And A Global Gathering At Gawai Festival
- 2019-01-04 · Venturing Into the Wild at Sebangau National Park
- 2019-08-22 · Seram Island – Meeting the Nuaulu Tribe
- 2019-12-20 · Reflections 2019: From Lombok Peresean Stick Fighters to the Dark Tales from Banda Islands
- 2020-03-06 · Into The Heart of The Ancestral Lands of The Punan

**Cue instrument.** type: do 46%, editorial 27%, event 18%, wellness 9% (coverage 69%); format: heritage 27%, event 18%, opinion 18%, feature 9% (coverage 69%); period-stamped titles 12%; roundups 0%; median first-person density 33.1/1000 words.

**Places named in title/lead.** bali 5, jakarta 3, east-bali 1, belitung 1, lombok 1, makassar 1; 31% name only a place outside jakarta.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.84 vs baseline 0.77; leakage 12% (cross-type 0%). Cohesion 0.837 (baseline 0.772), leakage 12% → Culture (1), Bali Updates (1); best split k=3 silhouette 0.121.
- cluster 1: 9 (56%) `do`/`feature` — Into the Wilds – West Kalimantan; Into The Heart of The Ancestral Lands of The Punan; Seram Island – Meeting the Nuaulu Tribe
- cluster 2: 5 (31%) `editorial`/`heritage` — Reflecting on Indonesia’s Hidden Heritage 2017; Bringing Back the Culture of the Traditional School; Hidden Heritage: The Sweet Melodies of Rote
- cluster 3: 2 (12%) `event`/`event` — Celebrating Indigenous Dance and Rituals at Gawai Festival; Culture, Colour And A Global Gathering At Gawai Festival

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `heritage` · format `heritage` · location `per-article` · agrees: False · split: True → heritage-culture, nature-travel · confidence medium. Mostly heritage/culture editorial but locations span all of Indonesia so per-article is correct; a few titles like spa and national park lean nature/travel rather than heritage.

**E1.4 draft.** confidence high, decision_needed False

### Lifestyle — resolved (D05)

*13 published · 2023–2026 · top-level · Yoast primary on 10 · slug `lifestyle` · term 2675*

> Editor's description: Find all latest news, update and information about lifestyle nowdays. Latest news in all areas of lifestyle, like sports, entertainment, health, health and beauty, and finance.

**Resolved prior** (E1.4 draft, amended by the evidence pack): type *per article* (prior `editorial`) · subtype *per article* (prior `lifestyle`) · format *per article* · location `jakarta` · - · confidence **low** · decisions D05

**Resolution.** basis D05; unchanged.

**Reasoning.** Amended: 13 posts since 2023, a grab-bag (duty-free shop, pottery workshop, serviced residences, mahjong); no honest type or format prior -- editorial/lifestyle is only the fallback (D05). \| E1.4: Parent category used directly since 2023 (13 posts); a grab-bag.

**Alternates for the classifier.** event/community + event (Ascott Soiree); do/workshop + people (tea lesson); wellness/retreat + news (Kemang self-care centre); editorial/culture + feature (gamelan)

**Representative titles (spread across the date range).**
- 2023-03-17 · Sarinah Duty Free: A Curation of Indonesian Products
- 2023-05-15 · H&M Indonesia x Mugler Collaboration: Iconic Shapes and Silhouettes Collection
- 2023-10-10 · Creating ‘Harmony’ in the Home
- 2024-05-13 · Clay Therapy: Immersive Pottery Workshops with Tanakita Ceramics
- 2025-05-27 · A Kemang Revival:  The Self Care Community Centre by Space Available
- 2026-07-07 · The Gongs of the Gamelan Still Reverberate in the City
- 2026-07-17 · A Lesson in the Art of Tea, with Eliawati Erly
- 2026-09-04 · Mahjong Mania: The Hottest Social Game in Town

**Cue instrument.** type: shop 40%, editorial 40%, do 10%, stay 10% (coverage 77%); format: news 83%, offer 17% (coverage 46%); period-stamped titles 0%; roundups 0%; median first-person density 3.0/1000 words.

**Places named in title/lead.** jakarta 6, blok-m 1, thamrin 1, west-jakarta 1, south-jakarta 1, pondok-indah 1; 0% name only a place outside jakarta.

**Co-filed with.** Shopping 2, Education 1, News 1; 8 carry this category alone.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.792 (baseline 0.775), leakage 15% → Shopping (1), Made In Indonesia (1); best split k=2 silhouette 0.093.
- cluster 1: 9 (69%) `editorial`/`news` — A Kemang Revival:  The Self Care Community Centre by Space Available; The Gongs of the Gamelan Still Reverberate in the City; An Evening of Art, Culture and Connection at Ascott Soirée
- cluster 2: 4 (31%) `shop`/`news` — Local Scents, Global Ambitions: Inside Indonesia’s Expanding Fragrance; Sarinah Duty Free: A Curation of Indonesian Products; Ranch Market’s 25th Anniversary: An Amazing Journey of Providing Fresh

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `lifestyle` · format `per-article` · location `jakarta` · agrees: True · split: True → shop, wellness, culture · confidence high. Catch-all lifestyle bucket spanning shop, wellness, culture, and stay; type and subtype as editorial/lifestyle fit, format varies per article, split recommended for better facet granularity.

**E1.4 draft.** confidence low, decision_needed True — Depends on approving `editorial/lifestyle`.

### Sites & Destinations — resolved (as proposed)

*12 published · 2024–2025 · parent: Discover Jakarta · Yoast primary on 8 · slug `sites-destinations` · term 2796*

**Resolved prior** (E1.4 draft (carried)): type `do` · subtype `attraction` · format `guide` · location `jakarta` · topic: heritage · confidence **high**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** 12 posts since 2024, each about ONE landmark — prime E2.3 place-extraction input (places, not just articles).

**Alternates for the classifier.** format heritage for history-led pieces (Istiqlal, Cathedral, Immanuel Church); do/museum + guide (Museum Nasional); location per article: gambir \| kota-tua \| west-jakarta

**Representative titles (spread across the date range).**
- 2024-01-08 · Rode Winkel: The Transformation of Toko Merah
- 2025-02-20 · Celebrating Love, Intellectualism, and Democracy at Wisma Habibie and Ainun
- 2025-03-13 · Guide to Monas: Indonesia's National Monument in Jakarta
- 2025-03-13 · Guide to Istana Merdeka: Indonesia's Presidential Palace in Jakarta
- 2025-03-13 · Guide to Museum Nasional Indonesia: Jakarta's Institution of Culture & History
- 2025-03-13 · Immanuel Church Jakarta: One of Indonesia's Oldest Churches
- 2025-03-13 · Jakarta Cathedral: A Neo-Gothic Masterpiece in Indonesia
- 2025-11-05 · A New Green Sanctuary in West Jakarta: Taman Doa Kasih Mulia Sejati

**Cue instrument.** type: editorial 75%, do 25% (coverage 67%); format: heritage 70%, news 30% (coverage 83%); period-stamped titles 0%; roundups 0%; median first-person density 0.0/1000 words.

**Places named in title/lead.** jakarta 11, gambir 4, south-jakarta 1, kemang 1, medan 1, kota-tua 1; 0% name only a place outside jakarta.

**Co-filed with.** Discover Jakarta 1; 11 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.84 vs baseline 0.78; leakage 17% (cross-type 17%). Cohesion 0.837 (baseline 0.777), leakage 17% → History & Heritage (1), Discover Jakarta (1); best split k=2 silhouette 0.108.
- cluster 1: 9 (75%) `editorial`/`heritage` — Guide to Monas: Indonesia's National Monument in Jakarta; Guide to Museum Nasional Indonesia: Jakarta's Institution of Culture &; Guide to Istana Merdeka: Indonesia's Presidential Palace in Jakarta
- cluster 2: 3 (25%) `editorial`/`heritage` — Guide to Kota Tua & Fatahillah Square: Jakarta's Historic Centre; Rode Winkel: The Transformation of Toko Merah; Barnyard Jakarta: An Urban Nature Reserve in the Heart of Kemang

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `do` · subtype `attraction` · format `guide` · location `jakarta` · agrees: True · split: False · confidence high. Titles are predominantly guides to Jakarta attractions and landmarks; a couple lean news but not enough to split.

**E1.4 draft.** confidence high, decision_needed False

### Diplomatic Relations — resolved (as proposed)

*11 published · 2024–2026 · parent: Features · Yoast primary on 5 · slug `diplomatic-relations` · term 2797*

**Resolved prior** (E1.4 draft (carried)): type `editorial` · subtype `people` · format `people` · location `jakarta` · topic: diplomacy; series_key: `ambassadors-round-table` · confidence **medium**

**Resolution.** basis as-proposed; unchanged.

**Reasoning.** 11 posts since 2024, 9 are the 'Ambassadors Round Table' series -> series_key candidate.

**Alternates for the classifier.** editorial/news + news (KCCI cultural exchange); event/conference + event if the Round Table is treated as a dated event

**Representative titles (spread across the date range).**
- 2024-03-08 · The Ambassadors Round Table: Edition 1
- 2024-06-05 · 75 Years of UK-Indonesia Relations, with H.E. Dominic Jermey, British Ambassador to Indonesia
- 2024-11-28 · The Ambassadors Round Table: Edition 4
- 2025-01-21 · The Ambassadors Round Table: Edition 5
- 2025-06-27 · The Ambassadors Round Table: Edition 6
- 2025-11-18 · The Ambassadors Round Table: Edition 7
- 2026-07-03 · Beyond K-Pop: KCCI Expands Cultural Exchange
- 2026-07-03 · The 13th Ambassadors Round Table: Bulgaria

**Cue instrument.** type: editorial 100% (coverage 91%); format: listing 38%, people 25%, news 25%, city-guide 12% (coverage 73%); period-stamped titles 0%; roundups 0%; median first-person density 11.9/1000 words.

**Places named in title/lead.** jakarta 10; 0% name only a place outside jakarta.

**Co-filed with.** Explore Indonesia 1; 10 carry this category alone.

**Coherence** (coherent, against the E2.0 proposal). cohesion 0.89 vs baseline 0.78; leakage 9% (cross-type 0%). Cohesion 0.891 (baseline 0.78), leakage 9% → Culture (1); best split k=2 silhouette 0.359.
- cluster 1: 8 (73%) `editorial`/`listing` — The Ambassadors Round Table: Edition 1; The Ambassadors Round Table: Edition 5; The Ambassadors Round Table: Edition 7
- cluster 2: 3 (27%) `editorial`/`people` — 75 Years of UK-Indonesia Relations, with H.E. Dominic Jermey, British ; Ambassadors' Travel Tales of the Archipelago: UK, Ireland, & Denmark; Beyond K-Pop: KCCI Expands Cultural Exchange

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `people` · format `people` · location `jakarta` · agrees: True · split: False · confidence high. Consistent series of ambassador profiles and diplomatic interviews centered in Jakarta; all titles are people-focused editorial content.

**E1.4 draft.** confidence medium, decision_needed False

### Love & Romance 2020 — resolved (print issue, D07)

*10 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 0 · slug `love-and-romance-2020` · term 2724*

> Editor's description: Love & Romance is your source for all the latest news about celebrities, movies, relationships and dating.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: date-night; series_key: `issue:love-and-romance-2020` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-01-30 · The Science of Love
- 2020-01-30 · All Kinds of Love: Swiping for Love
- 2020-02-05 · All Kinds of Love: Objects of Passion
- 2020-02-06 · Urban Temples of Love: Top Wedding Venues in Jakarta
- 2020-02-10 · All Kinds of Love: Intercultural Love
- 2020-02-11 · All Kinds of Love: Humans and Pets
- 2020-02-12 · Jakarta Love Stories
- 2020-02-13 · All-time Finest Movies about Love and Romance

**Cue instrument.** type: do 40%, stay 40%, editorial 20% (coverage 50%); format: opinion 60%, people 20%, offer 20% (coverage 50%); period-stamped titles 0%; roundups 0%; median first-person density 11.3/1000 words.

**Places named in title/lead.** jakarta 3, pondok-indah 1, bali 1, raja-ampat 1; 0% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.798 (baseline 0.783), leakage 20% → City Guides (1), Travel (1); best split k=2 silhouette 0.165.
- cluster 1: 5 (50%) `stay`/`offer` — Jakarta Love Stories; All Kinds of Love: Intercultural Love; Urban Temples of Love: Top Wedding Venues in Jakarta
- cluster 2: 5 (50%) `do`/`opinion` — The Science of Love; All Kinds of Love: Objects of Passion; All Kinds of Love: Self-love

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. Themed issue collection with diverse love-related topics spanning editorial, listings, and reviews; type varies per article but format is consistently feature and location is Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Food The Music Of Love — resolved (print issue, D07)

*10 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `food-the-music-of-love` · term 2737*

> Editor's description: The food is the music of love. Food is the most important thing in the world. Without food the world would be a very boring place.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · series_key: `issue:food-the-music-of-love` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Alternates for the classifier.** food; type eat per article

**Representative titles (spread across the date range).**
- 2019-01-04 · A Tuscan Feast at Rafles Jakarta
- 2019-01-04 · Meat Time Delights at Bradley's Kitchen
- 2019-01-04 · Food (Ordering) Made Easy
- 2019-01-04 · The Perfect Remedy of Sweet Sunday Brunch
- 2019-01-04 · Crave A Meatless Menu for Veggie Lovers at Hard Rock Cafe Jakarta
- 2019-01-04 · Indonesia's Wine Scene
- 2019-01-04 · The Expert View on Jakarta's Culinary Scene
- 2019-01-04 · Celebrating Indonesian Cuisine

**Cue instrument.** type: eat 90%, drink 10% (coverage 100%); format: offer 43%, news 29%, heritage 14%, opinion 14% (coverage 70%); period-stamped titles 0%; roundups 0%; median first-person density 2.0/1000 words.

**Places named in title/lead.** jakarta 5, south-jakarta 1, gunawarman 1, bali 1; 0% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.83 (baseline 0.783), leakage 10% → Restaurant Guides (1); best split k=2 silhouette 0.153.
- cluster 1: 8 (80%) `eat`/`offer` — Celebrating Indonesian Cuisine; The Expert View on Jakarta's Culinary Scene; Indonesian Cuisine Shines at Samsara
- cluster 2: 2 (20%) `eat`/`offer` — The Perfect Remedy of Sweet Sunday Brunch; Meat Time Delights at Bradley's Kitchen

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `eat` · subtype `per-article` · format `feature` · location `jakarta` · agrees: False · split: False · confidence high. All titles are food/dining features; type is clearly 'eat', not per-article, while subtype varies across reviews, guides, and news.

**E1.4 draft.** confidence low, decision_needed False

### A Jakarta Smorgasbord — resolved (print issue, D07)

*10 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `a-jakarta-smorgasbord` · term 2745*

> Editor's description: A Jakarta smorgasbord is a tradition that has been performed by the people of Jakarta, Indonesia for centuries.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · series_key: `issue:a-jakarta-smorgasbord` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Alternates for the classifier.** indonesian food; type eat per article

**Representative titles (spread across the date range).**
- 2019-01-04 · Sambal, an Integral Part of the Indonesian Palate
- 2019-01-04 · Amed Sea Salt Honours Local Farmers
- 2019-01-04 · Revo’s Culinary Journey is Ready for Take off
- 2019-01-04 · Das Beste: October Heralds a Celebration of the Riches of German and Swiss Cuisine
- 2019-01-04 · Tortured Brew : The Truth Behind Luwak Coffee
- 2019-01-04 · The Fascinating History and Mystery of Coffee in Java
- 2019-01-04 · A Slice of Conservation at Panda House by WWF Indonesia
- 2019-01-04 · Selatan Encourages Green Living

**Cue instrument.** type: eat 75%, editorial 25% (coverage 80%); format: heritage 67%, people 17%, review 17% (coverage 60%); period-stamped titles 0%; roundups 0%; median first-person density 6.5/1000 words.

**Places named in title/lead.** jakarta 6, amed 1; 0% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.811 (baseline 0.783), leakage 20% → Dining News (1), Reviews (1); best split k=2 silhouette 0.103.
- cluster 1: 6 (60%) `editorial`/`heritage` — A Slice of Conservation at Panda House by WWF Indonesia; Selatan Encourages Green Living; The Fascinating History and Mystery of Coffee in Java
- cluster 2: 4 (40%) `eat`/`people` — Sambal, an Integral Part of the Indonesian Palate; Revo’s Culinary Journey is Ready for Take off; Amed Sea Salt Honours Local Farmers

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: True → food-and-culinary, sustainability-and-conservation · confidence medium. Titles span food/culinary features and sustainability/conservation topics, so type varies per article; format is consistently feature and the magazine context anchors location to Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Indonesia S Creative Soul — resolved (print issue, D07)

*9 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `indonesia-s-creative-soul` · term 2711*

> Editor's description: Indonesia S Creative Soul is a home for Indonesian and international design and art lovers. Experience the best of Indonesian design and art!

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: art, culture; series_key: `issue:indonesia-s-creative-soul` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · The Charm and Beauty of Ballet
- 2019-01-04 · The Remarkable World of Harry Darsono
- 2019-01-04 · Meeting A Young Hazara Artist In Jakarta
- 2019-01-04 · From Bollywood to Jakarta for Love and Art
- 2019-01-04 · La Pavana Comes to Bandung
- 2019-01-04 · An Extraordinary Ballet Gala
- 2019-01-04 · Presenting Art and Design in Digital Form
- 2019-01-04 · Meet Indonesia's Creative Souls

**Cue instrument.** type: event 67%, do 17%, shop 17% (coverage 67%); format: people 40%, heritage 20%, review 20%, event 20% (coverage 56%); period-stamped titles 0%; roundups 0%; median first-person density 19.1/1000 words.

**Places named in title/lead.** jakarta 4, south-jakarta 2, bandung 2, kemang 1; 22% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design. Cohesion 0.805 (baseline 0.787), leakage 22% → Music (1), Design (1); best split k=2 silhouette 0.153.
- cluster 1: 7 (78%) `event`/`heritage` — From Bollywood to Jakarta for Love and Art; Presenting Art and Design in Digital Form; Meeting A Young Hazara Artist In Jakarta
- cluster 2: 2 (22%) `event`/`people` — La Pavana Comes to Bandung; Interview with Robert Nordling, Music Director of The Bandung Philharm

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. Arts and culture features spanning multiple locations (Jakarta, Bandung) and creative disciplines, so location should be per-article rather than fixed to jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Property Architecture Design — resolved (print issue, D07)

*9 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 2 · slug `property-architecture-design` · term 2758*

> Editor's description: A complete guide to property and architecture design news. Find the best property news and design ideas at NOW! Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: property, architecture, design; series_key: `issue:property-architecture-design` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-03-02 · The Never-Ending Pursuit of Aesthetics
- 2020-03-02 · Sustainable and Circular Construction: Why the Way We Build Has to Change
- 2020-03-03 · A Dream of A Green Home: Get to Know Green Building Council Indonesia
- 2020-03-05 · Architecture and Sustainability
- 2020-03-09 · The Home of Future Design
- 2020-03-09 · Pre-Fab Home. Are They Fab for You?
- 2020-03-09 · High-End Vertical Living: A List of Top Apartments in Jakarta
- 2020-03-11 · Jakarta’s Amazingly Designed Hotels

**Cue instrument.** type: editorial 71%, wellness 14%, stay 14% (coverage 78%); format: opinion 67%, heritage 33% (coverage 33%); period-stamped titles 0%; roundups 0%; median first-person density 8.7/1000 words.

**Places named in title/lead.** jakarta 4, kuningan 1; 0% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.809 (baseline 0.787), leakage 22% → City Guides (1), Stay Offers (1); best split k=2 silhouette 0.216.
- cluster 1: 7 (78%) `editorial`/`opinion` — Architecture and Sustainability; A More Ethical Architecture; The Home of Future Design
- cluster 2: 2 (22%) `wellness`/`heritage` — High-End Vertical Living: A List of Top Apartments in Jakarta; Jakarta’s Amazingly Designed Hotels

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. Titles mix Jakarta-specific and general architecture/design features, so location is per-article; type varies across stay, editorial, and shop, but format is consistently feature.

**E1.4 draft.** confidence low, decision_needed False

### Art Culture The Realm Of Contemporary Arts — resolved (print issue, D07)

*8 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `art-culture-the-realm-of-contemporary-arts` · term 2688*

> Editor's description: The Art Culture The Realm Of Contemporary Arts Archives is a digital collection that gives access to the museum's permanent collection of contemporary art

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: art; series_key: `issue:art-culture-the-realm-of-contemporary-arts` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-08-01 · First Asian Art Collective to Curate World Renowned documenta
- 2019-08-01 · The Rise of Contemporary Art
- 2019-08-02 · I La Galigo: Charming Buginese Epic
- 2019-08-08 · Embrace Your Inner Artist with Jakarta Art Community
- 2019-08-09 · Artistic Elevation in Top Jakarta Properties
- 2019-08-12 · Examining Sukarno Collection
- 2019-08-15 · At the Studio with Eko Nugroho
- 2019-08-19 · Betawi Cultural Village: History, Identity and Representation

**Cue instrument.** type: event 33%, do 17%, stay 17%, shop 17% (coverage 75%); format: news 50%, heritage 50% (coverage 25%); period-stamped titles 0%; roundups 0%; median first-person density 10.2/1000 words.

**Places named in title/lead.** jakarta 5, yogyakarta 1; 12% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.825 (baseline 0.791), leakage 25% → Art (1), History & Heritage (1); best split k=2 silhouette 0.174.
- cluster 1: 6 (75%) `event`/`news` — Embrace Your Inner Artist with Jakarta Art Community; The Rise of Contemporary Art; Artistic Elevation in Top Jakarta Properties
- cluster 2: 2 (25%) `event`/`heritage` — Betawi Cultural Village: History, Identity and Representation; I La Galigo: Charming Buginese Epic

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: True → art-features, cultural-heritage, artist-profiles · confidence medium. Articles span artist profiles, cultural heritage, and art-world news with varying locations, so type and location are per-article; format is consistently feature.

**E1.4 draft.** confidence low, decision_needed False

### Music & Nightlife — resolved (print issue, D07)

*8 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `music-and-nightlife` · term 2694*

> Editor's description: The latest report of music and nightlife shows the top tracks and live events in Jakarta. Subscribe NOW! Jakarta to stay updated.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: music; series_key: `issue:music-and-nightlife` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · The Story of the Hip-Hop Artist NAYAKA
- 2019-01-04 · Batutara Percussion in Promoting Environmental Sustainability Through Music
- 2019-01-04 · Shelly Gautama on Playing the Bagpipes in Asia
- 2019-01-04 · Stars and Rabbit, an Indie Duo Who Make Whispers Overseas
- 2019-01-04 · Programme Notes: Bandung Philharmonic Orchestra and Young Steinway Artist Gala Concert
- 2019-01-04 · Irish Bagpipes Find a Following in Indonesia
- 2019-01-04 · Guide to the Galaxy, Jakarta's Music and Nightlife Scene
- 2019-01-04 · Symphony for the Nation Concert Pays Homage to Indonesian Luminaries

**Cue instrument.** type: editorial 67%, event 33% (coverage 75%); format: event 60%, feature 20%, opinion 20% (coverage 62%); period-stamped titles 0%; roundups 0%; median first-person density 14.2/1000 words.

**Places named in title/lead.** jakarta 4, yogyakarta 1, bandung 1; 25% name only a place outside jakarta.

**Coherence** (expected-heterogeneous, against the E2.0 proposal). the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design; k=2 clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem. Cohesion 0.8 (baseline 0.791), leakage 25% → City Guides (1), Music (1); best split k=2 silhouette 0.113.
- cluster 1: 6 (75%) `editorial`/`feature` — Shelly Gautama on Playing the Bagpipes in Asia; Irish Bagpipes Find a Following in Indonesia; Batutara Percussion in Promoting Environmental Sustainability Through 
- cluster 2: 2 (25%) `event`/`event` — Symphony for the Nation Concert Pays Homage to Indonesian Luminaries; Programme Notes: Bandung Philharmonic Orchestra and Young Steinway Art

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → artist-profiles, event-reviews, scene-guides · confidence medium. Most titles are artist/people profiles rather than nightlife features; format varies between feature, people, and guide, so per-article is more accurate.

**E1.4 draft.** confidence low, decision_needed False

### Capital Of Culture — resolved (print issue, D07)

*7 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `capital-of-culture` · term 2702*

> Editor's description: NOW Jakarta is an independent cultural magazine that is dedicated to the creative industries in Indonesia. NOW Jakarta seeks to promote Indonesian arts, culture and artists.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: art, culture; series_key: `issue:capital-of-culture` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Jakarta’s Most Visited Places for Arts & Culture Perfomances
- 2019-01-04 · A Young Curator, Gesyada Annisa Namora Siregar
- 2019-01-04 · Museum of Modern and Contemporary Art in Nusantara: A Dose of Culture
- 2019-01-04 · The National Gallery of Indonesia: A Repository of Indonesian Art
- 2019-01-04 · Welcoming Indonesia’s Latest Landmark, The statue of Garuda Wisnu Kencana
- 2019-01-04 · Talking Art with President Director of Indonesian Luxury Deborah Iskandar
- 2019-01-04 · Indonesian Art Scene Boosted by the Games, Not the Other Way Round

**Cue instrument.** type: event 50%, do 50% (coverage 57%); format: heritage 50%, opinion 50% (coverage 29%); period-stamped titles 0%; roundups 0%; median first-person density 20.0/1000 words.

**Places named in title/lead.** jakarta 5, central-jakarta 1, cikini 1, bali 1, uluwatu 1; 0% name only a place outside jakarta.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. Articles cover pan-Indonesian arts and culture, not Jakarta-specific, so location should be per-article; format=feature and type=per-article are correct.

**E1.4 draft.** confidence low, decision_needed False

### Its A Man's World — resolved (print issue, D07)

*7 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `its-a-man-s-world` · term 2722*

> Editor's description: A blog about the world of men's style, lifestyle, and culture. Discover here at NOW! Jakarta and find the latest updated.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: fashion; series_key: `issue:its-a-man-s-world` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Scotland and Indonesia, United Through Football Since 1972
- 2019-02-13 · A Story of Passion
- 2019-02-13 · Up Close and Personal with Patrick Beck
- 2019-02-13 · Fat & Fabulous
- 2019-02-13 · Man's Guide to A Great Mane
- 2019-02-13 · Merpati Putih Bringing The Superman In You
- 2019-02-13 · The Batik Every Dapper Man Needs

**Cue instrument.** type: shop 40%, stay 20%, wellness 20%, editorial 20% (coverage 71%); format: review 33%, heritage 33%, offer 33% (coverage 43%); period-stamped titles 0%; roundups 0%; median first-person density 6.4/1000 words.

**Places named in title/lead.** jakarta 2, kemang 1, blok-m 1, senayan 1, yogyakarta 1, lombok 1; 29% name only a place outside jakarta.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: True → people-profiles, style-grooming, sports-culture · confidence medium. Diverse men's lifestyle topics span profiles, fashion, sports, and culture, so type/subtype are per-article; format is consistently feature-like editorial content.

**E1.4 draft.** confidence low, decision_needed False

### Tech Talk — resolved (print issue, D07)

*7 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `tech-talk` · term 2733*

> Editor's description: Technology news is a catch-all term for stories about any aspect of the computer, telecommunications, and digital media industries. Learn the latest tech news, tips, and trends.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: technology; series_key: `issue:tech-talk` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Why Older is Sometimes Better PART I : Communication & Literacy
- 2019-01-04 · A New Approach to Solving the World’s Biggest Problems
- 2019-01-04 · To IPO or ICO? That is the Question!
- 2019-01-04 · How to Tackle Digital Violence Against Women
- 2019-01-04 · Indonesia’s Online Encyclopedia
- 2019-01-04 · The Impact of Open Data
- 2019-01-04 · Technology  of the Future

**Cue instrument.** type: editorial 67%, do 33% (coverage 43%); format: news 40%, opinion 20%, offer 20%, listing 20% (coverage 71%); period-stamped titles 0%; roundups 0%; median first-person density 11.3/1000 words.

**Places named in title/lead.** jakarta 4; 0% name only a place outside jakarta.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: False · confidence medium. Tech commentary spans opinion, news, and feature formats with no consistent Jakarta-specific angle, so type=editorial with other facets per-article fits better.

**E1.4 draft.** confidence low, decision_needed False

### Staying Successful In Times Of Challenge — resolved (print issue, D07)

*7 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 0 · slug `staying-successful-in-times-of-challenge` · term 2749*

> Editor's description: This special report shows you how to stay successful in times of challenge and difficulty. You'll learn how to make the most of even the most difficult circumstances.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: business; series_key: `issue:staying-successful-in-times-of-challenge` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-04-01 · Why We Crave Success
- 2020-04-01 · The Legacy Lives On: In Conversation with Rina Ciputra
- 2020-04-02 · Happy Hearts Indonesia: Building Schools for the Poor
- 2020-04-03 · The Journey Towards Success
- 2020-04-06 · The Young and Inspiring Angkie Yudistia
- 2020-04-07 · Ismaya's Frans Widjaja: Success Through Self Understanding
- 2020-04-09 · Andrew You: Wielding the Right Attitude Towards JD.ID Success

**Cue instrument.** type: editorial 71%, shop 14%, eat 14% (coverage 100%); format: opinion 40%, people 20%, listing 20%, review 20% (coverage 71%); period-stamped titles 0%; roundups 0%; median first-person density 41.4/1000 words.

**Places named in title/lead.** jakarta 1, yogyakarta 1; 0% name only a place outside jakarta.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. Special report with profiles, interviews, and inspirational success stories; no single lifestyle type applies, but all are feature-format editorial content tied to Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### The Rhythm Of Life — resolved (print issue, D07)

*7 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `the-rhythm-of-life` · term 2762*

> Editor's description: The Rhythm Of Life is the world's largest and most comprehensive resource on rhythm of life. The site is filled with comprehensive articles, videos, and resources covering the science and psychology of rhythm, with a focus on the rhythms of our daily activities.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: music; series_key: `issue:the-rhythm-of-life` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Voices  from Kupang
- 2019-01-04 · Keeping Jakarta’s Vibrant Music Beat Alive
- 2019-01-04 · Jakarta’s Best Music Schools
- 2019-01-04 · Why Jakartans is really into karaoke for Fun
- 2019-01-04 · Kampung Tugu: The Identity of Keroncong
- 2019-01-04 · Enjoying The Place with Live Music and Performance in Jakarta
- 2019-01-04 · Here Are The Stories of Two Night Creatures in Jakarta

**Cue instrument.** type: editorial 50%, event 25%, drink 25% (coverage 57%); format: event 40%, opinion 20%, heritage 20%, review 20% (coverage 71%); period-stamped titles 0%; roundups 0%; median first-person density 12.4/1000 words.

**Places named in title/lead.** jakarta 5, south-jakarta 1, senopati 1; 0% name only a place outside jakarta.

**Coherence.** 7 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. All titles are feature articles about Jakarta's music and nightlife culture, but their specific types (do, heritage, editorial) vary per article.

**E1.4 draft.** confidence low, decision_needed False

### Staying In Style — resolved (print issue, D07)

*6 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `staying-in-style` · term 2691*

> Editor's description: Everything from fashion news to new runway shows, celebrity style and lifestyle trends, and discover more from NOW! Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: fashion; series_key: `issue:staying-in-style` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Beauty Tricks from the Kitchen Pantry
- 2019-01-04 · A Chat With Make-Up Artist Arsya Nafisa
- 2019-01-04 · Designer Denny Wirawan Introduces Kelana Spring Summer 2017 Collection
- 2019-01-04 · Fashion Photography with Sally Ann and Emily May
- 2019-01-04 · Storytelling from Tulisan
- 2019-01-04 · Back to Nature with Slow Fashion

**Cue instrument.** type: shop 80%, wellness 20% (coverage 83%); format: review 50%, people 25%, news 25% (coverage 67%); period-stamped titles 17%; roundups 0%; median first-person density 26.4/1000 words.

**Places named in title/lead.** jakarta 2, south-jakarta 1, gunawarman 1; 0% name only a place outside jakarta.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. Titles span fashion, beauty, and lifestyle features with no single type; all are feature-format profiles or trend pieces tied to Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Season Of Love — resolved (print issue, D07)

*6 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `season-of-love` · term 2693*

> Editor's description: Season Of Love is a fun, a stunning and romantic venue, interactive, and stylish way to find your dream date in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: date-night; series_key: `issue:season-of-love` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · The Beauty of Poetry
- 2019-01-04 · The Soundtrack of my (Love) Life
- 2019-01-04 · The Story of Happy Ending Long Distance Relationship
- 2019-01-04 · Spreading the Love on Valentine’s Day
- 2019-01-04 · Legendary Love Stories
- 2019-01-04 · Finding Romance in Jakarta

**Cue instrument.** type: do 100% (coverage 17%); format: opinion 50%, event 25%, heritage 25% (coverage 67%); period-stamped titles 17%; roundups 0%; median first-person density 22.1/1000 words.

**Places named in title/lead.** jakarta 5; 0% name only a place outside jakarta.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. All articles are editorial features on love/romance themes, but topics range from poetry to Jakarta-specific dating, so type and format are determinable while location is not.

**E1.4 draft.** confidence low, decision_needed False

### Architecture Property & Design — resolved (print issue, D07)

*6 published · 2019–2026 · parent: Magazine Issue · Yoast primary on 2 · slug `architecture-property-and-design` · term 2710*

> Editor's description: NOW Jakarta is a free community-based website dedicated to delivering information on the latest developments in architecture, property and design.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: architecture, property, design; series_key: `issue:architecture-property-and-design` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-03-04 · Jakarta's Co-working Spaces Gain Popularity
- 2019-03-18 · Architect Cosmas Gozali Offers His Thoughts on Design
- 2019-03-18 · Esti McMillan Helps Expatriates in Jakarta Find the Perfect Space
- 2026-07-10 · A Closer Look into Indonesia's Architecture Evolution
- 2026-07-15 · What Makes A Design ‘Indonesian’ Today?
- 2026-07-20 · How Restaurant Design Shapes Jakarta's Dining Experience

**Cue instrument.** type: editorial 75%, eat 25% (coverage 67%); format: feature 50%, heritage 50% (coverage 33%); period-stamped titles 0%; roundups 0%; median first-person density 7.2/1000 words.

**Places named in title/lead.** jakarta 4; 0% name only a place outside jakarta.

**Co-filed with.** Design 2; 4 carry this category alone.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: True → architecture-features, property-features, design-features · confidence medium. Titles span multiple types (stay, eat, people, editorial) but share feature format and Jakarta focus; splitting by subtopic would improve facet precision.

**E1.4 draft.** confidence low, decision_needed False

### Travel & Holiday — resolved (print issue, D07)

*6 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 1 · slug `travel-and-holiday` · term 2729*

> Editor's description: Travel & Holiday Archives. Latest news about travel and holiday destinations, places to visit, travel news, and more.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: travel; series_key: `issue:travel-and-holiday` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Enjoying One-Stop Reservations at Asia’s Theme Parks
- 2019-01-04 · Potsdam: A City Fit for Emperors and Kings
- 2019-01-04 · At Torajan Funerals, Grieving is Impolite
- 2019-01-04 · Culture, Food and City Hopping: Nigel Mason's Travels
- 2019-01-04 · Mapping The Future of the Indonesian Traveller
- 2019-01-04 · The Synergy of Hotel Indonesia Group

**Cue instrument.** type: do 50%, shop 25%, stay 25% (coverage 67%); format: city-guide 33%, offer 17%, heritage 17%, guide 17% (coverage 100%); period-stamped titles 0%; roundups 0%; median first-person density 13.4/1000 words.

**Places named in title/lead.** jakarta 2, toraja 1; 17% name only a place outside jakarta.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: True → travel-destinations, travel-industry · confidence medium. Articles cover diverse global destinations and travel-industry topics, so location is per-article not jakarta; format is mostly feature but industry pieces lean news.

**E1.4 draft.** confidence low, decision_needed False

### The Culinary Issue — resolved (print issue, D07)

*6 published · 2019–2024 · parent: Magazine Issue · Yoast primary on 1 · slug `the-culinary-issue` · term 2732*

> Editor's description: The Culinary Issue is a collection of articles written by our expert contributors, covering food fraud and food safety issues.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · series_key: `issue:the-culinary-issue` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Alternates for the classifier.** food; type eat per article

**Representative titles (spread across the date range).**
- 2019-10-03 · Your Taste Buds and You
- 2019-10-04 · Savouring Sweet Treats During Jakarta Dessert Week
- 2019-10-10 · Ambrosia Private Club Signs Mandif Warokka
- 2019-10-15 · Saturday Chinese Brunch at Raffles Jakarta
- 2019-10-16 · Plataran Catering Services: Spice up Your Events with First-class Cuisine
- 2024-09-09 · Time, The Forgotten Ingredient

**Cue instrument.** type: eat 100% (coverage 100%); format: offer 50%, review 25%, news 25% (coverage 67%); period-stamped titles 0%; roundups 0%; median first-person density 2.9/1000 words.

**Places named in title/lead.** jakarta 2, bali 1; 17% name only a place outside jakarta.

**Co-filed with.** Made In Indonesia 1; 5 carry this category alone.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → food features, restaurant news, event listings · confidence medium. Titles span features, news, and listings across eat/event/editorial types; only location is consistently Jakarta, so format and type are per-article.

**E1.4 draft.** confidence low, decision_needed False

### Building Future Leader — resolved (print issue, D07)

*6 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `building-future-leader` · term 2738*

> Editor's description: NOW Jakarta News is a leading Indonesian media company. We provide you with the latest breaking news, business and financial information, and lifestyle information.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: education; series_key: `issue:building-future-leader` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Womenesia Works with Women for Empowerment
- 2019-01-04 · Exercising Control
- 2019-01-04 · Indonesian Family Develops International Standard Education for the Country
- 2019-01-04 · Beyond the Mall
- 2019-01-04 · Taman Bacaan Pelangi: Developing a Reading Culture in Eastern Indonesia
- 2019-01-04 · Jaspal Sidhu: Because Quality Education Should Be Accessible to Every Child

**Cue instrument.** type: editorial 80%, do 20% (coverage 83%); format: opinion 50%, listing 25%, offer 25% (coverage 67%); period-stamped titles 0%; roundups 0%; median first-person density 4.5/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. Articles are magazine features on education and social leadership topics spanning national scope, not Jakarta-specific; type is editorial rather than per-article.

**E1.4 draft.** confidence low, decision_needed False

### Jakarta S Music & Nightlife — resolved (print issue, D07)

*6 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `jakarta-s-music-and-nightlife` · term 2759*

> Editor's description: Jakarta has a lot to offer visitors and residents alike. Whether you are looking to hit the town and dance the night away, or looking to relax and unwind, there's always something to do in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: music; series_key: `issue:jakarta-s-music-and-nightlife` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-09-02 · Sips, Savouries, Sounds: Our Favourite Nightlife Venues in Jakarta
- 2019-09-11 · When Rocks and Gamelan Collide
- 2019-09-11 · The Sounds of Indonesian Contemporary Classic
- 2019-09-13 · Northern Soul Dances into Jakarta's Music Scene
- 2019-09-16 · Music in Education
- 2019-09-16 · Endah Laras: Queen of Keroncong

**Cue instrument.** type: event 40%, editorial 40%, drink 20% (coverage 83%); format: news 40%, opinion 40%, event 20% (coverage 83%); period-stamped titles 0%; roundups 0%; median first-person density 5.3/1000 words.

**Places named in title/lead.** jakarta 4; 0% name only a place outside jakarta.

**Coherence.** 6 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence medium. Titles mix nightlife venue coverage with music artist profiles and cultural commentary, so type varies per article; all are Jakarta-focused features.

**E1.4 draft.** confidence low, decision_needed False

### The Festive Season — resolved (print issue, D07)

*5 published · 2019–2022 · parent: Magazine Issue · Yoast primary on 0 · slug `the-festive-season` · term 2680*

> Editor's description: From Thanksgiving to Christmas, the weather changes and the days get shorter. To celebrate, we're bringing you a selection of seasonal recipes, crafts, and gift ideas.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: celebration; series_key: `issue:the-festive-season` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-02-13 · Cakes For Charity
- 2019-02-13 · Memories of Christmas
- 2019-02-13 · Tech Gifts for the Holidays
- 2019-02-13 · Christmas Services at All Saints Anglican Church Jakarta
- 2022-12-05 · "The Greatest Borobudur Show” Christmas Celebration

**Cue instrument.** type: editorial 33%, eat 33%, stay 33% (coverage 60%); format: listing 50%, offer 50% (coverage 40%); period-stamped titles 60%; roundups 0%; median first-person density 8.5/1000 words.

**Places named in title/lead.** jakarta 3, menteng 1, yogyakarta 1; 0% name only a place outside jakarta.

**Co-filed with.** Offers 1, Stay Offers 1; 4 carry this category alone.

**Coherence.** 5 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → festive-events, gift-guides, seasonal-editorial · confidence medium. Titles span events, gift guides, and reflective features across multiple locations, so format and location are not fixed; only the festive-season theme unifies them.

**E1.4 draft.** confidence low, decision_needed False

### Travels Far & Near — resolved (print issue, D07)

*5 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `travels-far-and-near` · term 2686*

> Editor's description: Travels Far & Near is a collection of free travel guides, with more than 100 posts. The travel guides have been written and updated by travel writers and bloggers, for travelers and backpackers.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: travel; series_key: `issue:travels-far-and-near` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Kazakhstan Enters World Stage with Astana Expo 2017
- 2019-01-04 · Astana, A Modern Metropolis Amidst Nomadic Steppe
- 2019-01-04 · New Zealand’s Natural Beauty
- 2019-01-04 · Nicholas Saputra, A Traveler With A Cause
- 2019-01-04 · Top Travel Destinations Off The Beaten Path

**Cue instrument.** type: do 40%, event 20%, shop 20%, stay 20% (coverage 100%); format: listing 33%, review 33%, city-guide 33% (coverage 60%); period-stamped titles 20%; roundups 20%; median first-person density 5.0/1000 words.

**Places named in title/lead.** jakarta 1, sumba 1; 20% name only a place outside jakarta.

**Coherence.** 5 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `per-article` · agrees: False · split: True → travel-guides, travel-features, travel-people · confidence medium. Titles span global destinations and formats (guides, features, people profiles), so location is per-article not jakarta and format varies; splitting by article purpose is warranted.

**E1.4 draft.** confidence low, decision_needed False

### Festive Issue — resolved (print issue, D07)

*5 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `festive-issue` · term 2707*

> Editor's description: The most complete and balanced guide to Jakarta for the food, party and travel enthusiast. The issue also includes an exclusive guide to street food in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: celebration; series_key: `issue:festive-issue` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · NOW! JAKARTA’S ‘Cakes For Charity’ Programme Sends a Joy to Communities
- 2019-01-04 · Light Craft: Unconventional Rattan Christmas Trees & Christmas Ball Lights
- 2019-01-04 · The Magic of the Festive Season at Four Seasons Hotel Jakarta
- 2019-01-04 · Joyful Christmas Feast at Hotel Borobudur Jakarta
- 2019-01-04 · Christmas Tradition in South America

**Cue instrument.** type: eat 50%, editorial 25%, shop 25% (coverage 80%); format: offer 67%, listing 33% (coverage 60%); period-stamped titles 80%; roundups 0%; median first-person density 3.5/1000 words.

**Places named in title/lead.** jakarta 4, yogyakarta 1; 0% name only a place outside jakarta.

**Coherence.** 5 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: False · confidence medium. A magazine-issue category bundles heterogeneous content; type and format vary per article, though location is consistently Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Health In An Era Of Urbanisation — resolved (print issue, D07)

*5 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `health-in-an-era-of-urbanisation` · term 2719*

> Editor's description: This is an ongoing effort to preserve the city's heritage by publishing photos of the old architecture, as well as its health & history.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: health; series_key: `issue:health-in-an-era-of-urbanisation` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Octane Airdyne X: Powerful and Reliable Workout for Today’s Exercisers
- 2019-01-04 · Special Olympics Indonesia: Can Sports Unite Communities?
- 2019-01-04 · Redefining Notions of Beauty in Today's Society
- 2019-01-04 · Trends in Fitness: From Strength to High Intensity Interval Training
- 2019-01-04 · In Good Health: Exercise is Key but Nutrition Plays a Vital Role

**Cue instrument.** type: wellness 100% (coverage 60%); format: listing 50%, opinion 50% (coverage 40%); period-stamped titles 0%; roundups 0%; median first-person density 7.0/1000 words.

**Places named in title/lead.** jakarta 2; 0% name only a place outside jakarta.

**Coherence.** 5 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence medium. Titles span wellness, sports, and societal commentary so type is per-article; all are feature-length editorial pieces tied to Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### Season Of Wonders — resolved (print issue, D07)

*5 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `season-of-wonders` · term 2735*

> Editor's description: The Season of Wonders is discovering Christmas, Christmas gives, New Year and traditions in Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: celebration; series_key: `issue:season-of-wonders` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Welcoming the New Year
- 2019-01-04 · Discovering Christmas Traditions
- 2019-01-04 · The Season of Giving
- 2019-01-04 · Celebrating Green Christmas
- 2019-01-04 · The True Meaning of Christmas

**Cue instrument.** type: eat 25%, event 25%, editorial 25%, shop 25% (coverage 80%); format: listing 50%, offer 25%, event 25% (coverage 80%); period-stamped titles 80%; roundups 0%; median first-person density 4.2/1000 words.

**Places named in title/lead.** jakarta 4, gunawarman 1; 0% name only a place outside jakarta.

**Coherence.** 5 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. Seasonal holiday-themed feature articles spanning multiple types (editorial, do, shop) with no single type binding them; format and location are consistent.

**E1.4 draft.** confidence low, decision_needed False

### In With The New — resolved (print issue, D07)

*4 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 0 · slug `in-with-the-new` · term 2684*

> Editor's description: In With The New Archives is a monthly digital magazine featuring the best of NOW! Jakarta's digital content.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · series_key: `issue:in-with-the-new` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-01-06 · Into 2020 with Intent
- 2020-01-08 · 20 Wishes from NOW! Jakarta Colleagues for 2020
- 2020-01-13 · For Better Sidewalks
- 2020-01-14 · Voice of the People on Wider Sidewalks in Jakarta

**Cue instrument.** type: editorial 75%, wellness 25% (coverage 100%); format: listing 50%, opinion 50% (coverage 50%); period-stamped titles 50%; roundups 0%; median first-person density 27.1/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: False · confidence medium. Titles mix features, opinion, and editorial pieces about Jakarta urban life; format varies per article, so per-article is more accurate than a fixed feature.

**E1.4 draft.** confidence low, decision_needed False

### Money Finance — resolved (print issue, D07)

*4 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `money-finance` · term 2715*

> Editor's description: Learn why you have to have the right financial advice. Find out the basic rules of investing, and the secrets of financial freedom.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: finance; series_key: `issue:money-finance` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-04-04 · A Critique of Criticising Capitalism
- 2019-04-05 · Insurance in Indonesia
- 2019-04-10 · Brikcoin: A Manual Cryptocurrency for the Value of the Absence of Plastic
- 2019-04-11 · From Zero to Unicorn

**Cue instrument.** type: editorial 100% (coverage 50%); format: listing 100% (coverage 25%); period-stamped titles 0%; roundups 0%; median first-person density 2.0/1000 words.

**Places named in title/lead.** jakarta 1; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `jakarta` · agrees: False · split: False · confidence medium. All titles are finance-themed magazine features; type is consistently editorial, not per-article, while subtopics vary too widely to assign a single subtype.

**E1.4 draft.** confidence low, decision_needed False

### Love & Romance — resolved (print issue, D07)

*4 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `love-and-romance` · term 2717*

> Editor's description: All about Love and Romance News. Active lifestyle, healthy living and relationships. Discover NOW! Jakarta

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · occasion: date-night; series_key: `issue:love-and-romance` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-02-13 · An Unorthodox​ Honeymoon
- 2019-02-13 · Wedding Fairs this Year
- 2019-02-13 · Zola Yoana, Founder and CEO of Heart Inc Helps Match Single Professionals
- 2019-02-13 · SweetEscape: Snap To Service!

**Cue instrument.** type: event 67%, do 33% (coverage 75%); format: event 50%, people 50% (coverage 50%); period-stamped titles 0%; roundups 0%; median first-person density 4.1/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → wedding-events, people-profiles, lifestyle-features · confidence medium. Titles span events, people profiles, and lifestyle features with no consistent type or format; only location is reliably Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### The Travel Issue — resolved (print issue, D07)

*4 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `the-travel-issue` · term 2761*

> Editor's description: The Travel Issue. Here you'll find guides to the world's finest locations and a trove of travel tips.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: travel; series_key: `issue:the-travel-issue` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-11-01 · Being A Responsible Traveller
- 2019-11-04 · Cathay Pacific Embarks on a Journey of Moving People Forward in Life
- 2019-11-04 · Qatar Airways: Constant Aviation Innovation and Expansion
- 2019-11-07 · Up-Close and Personal with Motoharu Taki, Regional Manager of Japan Airlines

**Cue instrument.** type: shop 100% (coverage 25%); format: city-guide 50%, news 50% (coverage 100%); period-stamped titles 0%; roundups 0%; median first-person density 20.0/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: False · confidence medium. Magazine-issue category with travel-themed features spanning airlines, destinations, and people; location varies per article and is not Jakarta-specific.

**E1.4 draft.** confidence low, decision_needed False

### The Plague Of Our Time — resolved (print issue, D07)

*4 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 1 · slug `the-plague-of-our-time` · term 2764*

> Editor's description: The Plague Of Our Time is a satirical current events blog. We cover politics, world news, business and technology.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: health; series_key: `issue:the-plague-of-our-time` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-05-04 · Surviving the Plague with the Right Protective Gear
- 2020-05-04 · Designs for Care
- 2020-05-06 · The Jakarta Hotels Association on Covid-19
- 2020-05-07 · Hope Amidst a Global Pandemic

**Cue instrument.** type: shop 33%, stay 33%, wellness 33% (coverage 75%); format: offer 50%, opinion 50% (coverage 50%); period-stamped titles 0%; roundups 0%; median first-person density 24.6/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `per-article` · agrees: False · split: True → covid-19 coverage, satirical commentary · confidence medium. Blog spans politics, world news, business and technology with global pandemic themes, so location is per-article not fixed to Jakarta; type varies by article.

**E1.4 draft.** confidence low, decision_needed False

### Can Jakarta Really Change — resolved (print issue, D07)

*4 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `can-jakarta-really-change` · term 2765*

> Editor's description: Can Jakarta Really Change? Jakarta has been transformed by the process of urban reform over the last three decades. Discover more at NOW! Jakarta.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: sustainability, transport; series_key: `issue:can-jakarta-really-change` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-05-31 · What is a Sustainable City?
- 2019-05-31 · Oswar Mungkasa: Jakarta’s Sustainability Initiatives in Place
- 2019-06-10 · Taking Initiative in Reducing Jakarta’s Waste
- 2019-06-11 · Sustainability in Jakarta’s Satellite Cities

**Cue instrument.** type: editorial 75%, eat 25% (coverage 100%); format: opinion 100% (coverage 25%); period-stamped titles 0%; roundups 0%; median first-person density 7.1/1000 words.

**Places named in title/lead.** jakarta 4, bekasi 1; 0% name only a place outside jakarta.

**Coherence.** 4 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `feature` · location `jakarta` · agrees: True · split: False · confidence high. Magazine-issue theme covering Jakarta sustainability topics; type varies per article but format is consistently feature and location is Jakarta.

**E1.4 draft.** confidence low, decision_needed False

### City Of The Future — resolved (print issue, D07)

*3 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `city-of-the-future` · term 2728*

> Editor's description: NOW Jakarta is the only magazine in Indonesia that covers the city of Jakarta in an innovative and thought-provoking way.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: architecture, transport, sustainability; series_key: `issue:city-of-the-future` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Perspectives A Concise History Of Jakarta
- 2019-01-04 · Making Jakarta a More Favourable Tourist Destination
- 2019-01-04 · Towards a New Jakarta

**Cue instrument.** type: editorial 100% (coverage 100%); format: heritage 50%, city-guide 50% (coverage 67%); period-stamped titles 0%; roundups 0%; median first-person density 10.4/1000 words.

**Places named in title/lead.** jakarta 3; 0% name only a place outside jakarta.

**Coherence.** 3 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `editorial` · subtype `per-article` · format `feature` · location `jakarta` · agrees: False · split: False · confidence medium. All titles are editorial reflections on Jakarta's identity and future; type is better as editorial than per-article, though subtype varies across history, tourism, and urban planning.

**E1.4 draft.** confidence low, decision_needed False

### Embracing The New Normal — resolved (print issue, D07)

*3 published · 2020–2020 · parent: Magazine Issue · Yoast primary on 0 · slug `embracing-the-new-normal` · term 2743*

> Editor's description: The Embracing The New Normal blog at NOW! Jakarta will feature personal stories, research, natural treatments, and helpful resources.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: health, business; series_key: `issue:embracing-the-new-normal` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2020-06-19 · Here There Be Monsters
- 2020-06-23 · Embracing the “New Normal”: Are you?
- 2020-06-23 · Covid-19 and The Indonesian Economy

**Cue instrument.** type: editorial 100% (coverage 33%); format: opinion 100% (coverage 100%); period-stamped titles 0%; roundups 0%; median first-person density 37.2/1000 words.

**Places named in title/lead.** jakarta 1; 0% name only a place outside jakarta.

**Coherence.** 3 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: True → personal-reflection, economic-analysis · confidence medium. Titles span personal essays, reflective features, and economic news, so format varies per article; type and subtype are undetermined by the category.

**E1.4 draft.** confidence low, decision_needed False

### Money & Finance — resolved (print issue, D07)

*3 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `money-and-finance` · term 2755*

> Editor's description: Finance is a complicated subject, and there is so much information out there that it's easy to get lost. Here are some posts that help make the world of finance a little easier to understand.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · topic: finance; series_key: `issue:money-and-finance` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Cigna Insurance Offers Peace of Mind
- 2019-01-04 · Moneyed Millennials
- 2019-01-04 · From Bitcoin to Borderless Money, the Fintech Revolution is Here

**Cue instrument.** type: wellness 100% (coverage 33%); format: offer 100% (coverage 33%); period-stamped titles 0%; roundups 0%; median first-person density 5.5/1000 words.

**Places named in title/lead.** jakarta 1; 0% name only a place outside jakarta.

**Coherence.** 3 members with vectors (< 8); read the titles instead.

**LLM second opinion** (glm-5.2, against the E2.0 proposal): type `per-article` · subtype `per-article` · format `per-article` · location `jakarta` · agrees: False · split: False · confidence medium. Titles span offers, profiles, and trend features, so format varies per article; type and subtype also undetermined by the category.

**E1.4 draft.** confidence low, decision_needed False

### 10th Anniversary Issue — resolved (print issue, D07)

*2 published · 2019–2019 · parent: Magazine Issue · Yoast primary on 0 · slug `10th-anniversary-issue` · term 2712*

> Editor's description: 10th Anniversary Issue- The decade that was is almost upon us and we want to look back at the decade that was.

**Resolved prior** (E1.4 draft (carried)): type *per article* · subtype *per article* · format `feature` · location `jakarta` · series_key: `issue:10th-anniversary-issue` · confidence **low** · decisions D07

**Resolution.** basis D07; unchanged.

**Reasoning.** Print-issue grouping (parent 'Magazine Issue'), not a subject. Keep as series_key for the print archive; facets come from the classifier. Format feature = magazine long-form prior.

**Representative titles (spread across the date range).**
- 2019-01-04 · Former Editors Share Memories of their time at the Magazine
- 2019-01-14 · A Look Back at the Decade That was

**Cue instrument.** type: editorial 100% (coverage 50%); format: listing 100% (coverage 50%); period-stamped titles 0%; roundups 0%; median first-person density 30.6/1000 words.

**Places named in title/lead.** jakarta 2; 0% name only a place outside jakarta.

**Coherence.** 2 members with vectors (< 8); read the titles instead.

**E1.4 draft.** confidence low, decision_needed False

### Magazine Issue — empty

*0 published · no articles · top-level · Yoast primary on 0 · slug `magazine-issue` · term 2679*

> Editor's description: Magazine issues are important because they provide clues to the future. They can tell us what to expect in the coming months, and they can help us prepare. This post looks at what happened in the last year to some of the most important issues.

No published articles carry this category. Nothing to map.

---
*Generated from one in-memory model by `now-taxonomy-evidence build`; regenerate rather than hand-edit. Answers live in `src/now_taxonomy_evidence/resolutions.py`; cache: `engine/packages/taxonomy-evidence/.cache/`.*

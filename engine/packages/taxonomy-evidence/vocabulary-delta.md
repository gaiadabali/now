# Vocabulary delta — the seed change the taxonomy review produced

**Generated 2026-09-10T03:14:29+00:00 from the same scan as the review packs; decided by Hansel on 2026-09-10.** Machine twin: `vocabulary-delta.json` (same model). This file is *input to the seed ticket* (F20): nothing here has been written to `engine/packages/taxonomy/seed/`.

Rule: add every corpus term with ≥ 20 mentions (distinct articles, title+body, both cities); below that stays out. 194 candidates qualified, 23 did not. Decisions: D03, D04, D05, D06, D11, D12, D13, D14, D15, D16, D22.

| action | count |
|---|---:|
| approve | 44 |
| add_term | 140 |
| add_alias_sets | 85 |
| add_alias_forms | 232 |
| merged | 8 |
| skipped | 3 |
| drop_term | 1 |
| trim_alias | 9 |
| match_hints | 8 |
| add_term requiring a Payload ENUM migration (F20) | 112 |

New terms by facet: amenities 23, audience 9, cuisine 12, location 54, occasion 8, subtype 11, topic 11, vibe 12.

## 1. Approve (already seeded as `proposed`; documentation change only)

| facet | slug | label | parent | decision | mentions (j / b / titles) | note |
|---|---|---|---|---|---|---|
| format | `opinion` | Opinion | - | D03 | - |  |
| location | `denpasar` | Denpasar | south-bali | D14 | 407 (49 / 358 / 19) |  |
| location | `solo` | Solo | other | D14 | 293 (187 / 106 / 20) |  |
| location | `surabaya` | Surabaya | other | D14 | 282 (235 / 47 / 42) |  |
| location | `legian` | Legian | south-bali | D14 | 281 (42 / 239 / 79) |  |
| location | `gunawarman` | Gunawarman / Dharmawangsa | south-jakarta | D14 | 271 (190 / 81 / 16) |  |
| location | `kuningan` | Kuningan | south-jakarta | D14 | 259 (235 / 24 / 12) |  |
| location | `kota-tua` | Kota Tua | west-jakarta | D14 | 227 (206 / 21 / 13) |  |
| location | `malang` | Malang | other | D14 | 209 (94 / 115 / 11) |  |
| location | `kerobokan` | Kerobokan | south-bali | D14 | 196 (12 / 184 / 2) |  |
| location | `cikini` | Cikini | central-jakarta | D14 | 112 (97 / 15 / 9) |  |
| location | `nusa-penida` | Nusa Penida | east-bali | D14 | 102 (5 / 97 / 19) |  |
| location | `medan` | Medan | other | D14 | 93 (81 / 12 / 4) |  |
| location | `semarang` | Semarang | other | D14 | 92 (77 / 15 / 4) |  |
| location | `puncak` | Puncak | greater-jakarta | D14 | 83 (76 / 7 / 10) |  |
| location | `makassar` | Makassar | other | D14 | 66 (58 / 8 / 2) |  |
| location | `manado` | Manado | other | D14 | 63 (41 / 22 / 1) |  |
| location | `sumba` | Sumba | other | D14 | 59 (33 / 26 / 12) |  |
| location | `bintaro` | Bintaro | greater-jakarta | D14 | 47 (47 / 0 / 4) |  |
| location | `glodok` | Glodok | west-jakarta | D14 | 44 (42 / 2 / 5) |  |
| location | `banyuwangi` | Banyuwangi | other | D14 | 41 (19 / 22 / 9) |  |
| location | `gading-serpong` | Gading Serpong | greater-jakarta | D14 | 36 (36 / 0 / 12) |  |
| location | `pererenan` | Pererenan | south-bali | D14 | 35 (2 / 33 / 4) |  |
| location | `alam-sutera` | Alam Sutera | greater-jakarta | D14 | 34 (33 / 1 / 4) |  |
| location | `toraja` | Toraja | other | D14 | 30 (21 / 9 / 0) |  |
| location | `east-jakarta` | East Jakarta | jakarta | D14 | 28 (28 / 0 / 1) |  |
| location | `sentul` | Sentul | greater-jakarta | D14 | 28 (27 / 1 / 5) |  |
| location | `sidemen` | Sidemen | east-bali | D14 | 28 (1 / 27 / 3) |  |
| location | `depok` | Depok | greater-jakarta | D14 | 27 (27 / 0 / 2) |  |
| location | `tebet` | Tebet | south-jakarta | D14 | 25 (25 / 0 / 0) |  |
| location | `pasar-baru` | Pasar Baru | central-jakarta | D14 | 24 (24 / 0 / 3) |  |
| location | `belitung` | Belitung | other | D14 | 18 (17 / 1 / 7) | already seeded as `proposed`; already a value of the Payload enum where one exists -- approval changes documentation only (kept although below 20 mentions: only rawamangun was named for dropping -- see D14 conflicts) |
| location | `bintan` | Bintan | other | D14 | 18 (14 / 4 / 5) | already seeded as `proposed`; already a value of the Payload enum where one exists -- approval changes documentation only (kept although below 20 mentions: only rawamangun was named for dropping -- see D14 conflicts) |
| location | `lake-toba` | Lake Toba | other | D14 | 16 (13 / 3 / 5) | already seeded as `proposed`; already a value of the Payload enum where one exists -- approval changes documentation only (kept although below 20 mentions: only rawamangun was named for dropping -- see D14 conflicts) |
| location | `cibubur` | Cibubur | east-jakarta | D14 | 13 (13 / 0 / 3) | already seeded as `proposed`; already a value of the Payload enum where one exists -- approval changes documentation only (kept although below 20 mentions: only rawamangun was named for dropping -- see D14 conflicts) |
| location | `international` | International | - | D06 | - | attrs {'geo_scope': 'abroad', 'inherited_by_descendants': True};  |
| subtype | `culture` | Culture | editorial | D04 | 4324 (2306 / 2018 / 306) |  |
| subtype | `lifestyle` | Lifestyle | editorial | D05 | 3334 (1798 / 1536 / 173) |  |
| subtype | `performance` | Performance | event | D12 | 1682 (887 / 795 / 99) |  |
| subtype | `salon` | Salon | wellness | D13 | 1010 (444 / 566 / 63) |  |
| subtype | `retreat` | Retreat | wellness | D13 | 489 (170 / 319 / 53) |  |
| subtype | `sports-activity` | Sports & activities | do | D11 | 305 (203 / 102 / 39) |  |
| subtype | `screening` | Screening | event | D12 | 206 (130 / 76 / 36) |  |
| subtype | `pop-up` | Pop-up | event | D12 | 126 (77 / 49 / 14) |  |

## 2. Add terms

| facet | slug | label | parent | aliases | mentions (j / b / titles) | merged from | migration | note |
|---|---|---|---|---|---|---|---|---|
| amenities | `buffet` | Buffet | - | buffet breakfast, brunch buffet | 629 (405 / 224 / 10) | - | enum_places_amenities |  |
| amenities | `organic` | Organic & farm-to-table | - | organic menu, farm-to-table, farm to table | 408 (143 / 265 / 2) | cuisine/Farm-to-table 58 | enum_places_amenities | approach term -> amenities (D15); merges Farm-to-table (58) |
| amenities | `jungle-view` | Jungle view | - | rainforest view | 357 (107 / 250 / 30) | - | enum_places_amenities | bare 'jungle' / 'rainforest' inflate the count (every jungle-view villa); aliases kept to the view sense |
| amenities | `free-flow` | Free flow | - | free-flow, bottomless | 217 (98 / 119 / 3) | - | enum_places_amenities |  |
| amenities | `sauna` | Sauna & steam | - | steam room, jacuzzi, hot tub, onsen | 203 (78 / 125 / 0) | - | enum_places_amenities |  |
| amenities | `breakfast-included` | Breakfast included | - | daily breakfast | 185 (89 / 96 / 0) | - | enum_places_amenities |  |
| amenities | `late-night` | Open late | - | open late, 24 hours, 24-hour | 185 (90 / 95 / 1) | - | enum_places_amenities | the opening-hours sense; 'late night' is trimmed from vibe/party |
| amenities | `rice-field-view` | Rice-field view | - | rice field view, paddy view, rice paddies | 173 (26 / 147 / 2) | - | enum_places_amenities |  |
| amenities | `private-pool` | Private pool | - | plunge pool | 151 (31 / 120 / 0) | - | enum_places_amenities |  |
| amenities | `delivery` | Delivery & takeaway | - | takeaway, take-away, GoFood, GrabFood | 146 (89 / 57 / 6) | - | enum_places_amenities |  |
| amenities | `lagoon-pool` | Lagoon pool | - | lagoon | 138 (58 / 80 / 2) | - | enum_places_amenities |  |
| amenities | `river-view` | River view | - | riverside, Ayung river | 133 (19 / 114 / 22) | - | enum_places_amenities |  |
| amenities | `cabanas` | Cabanas & day beds | - | cabana, day bed, daybed, sunbed, sun lounger | 96 (22 / 74 / 7) | - | enum_places_amenities |  |
| amenities | `airport-transfer` | Airport transfer | - | shuttle | 96 (51 / 45 / 1) | - | enum_places_amenities |  |
| amenities | `swim-up-bar` | Swim-up bar | - | pool bar | 94 (37 / 57 / 3) | - | enum_places_amenities |  |
| amenities | `butler` | Butler service | - | butler | 71 (27 / 44 / 0) | - | enum_places_amenities |  |
| amenities | `healthy-menu` | Healthy menu | - | healthy food, health food, clean eating, superfood | 68 (37 / 31 / 3) | - | enum_places_amenities | approach term -> amenities (D15) |
| amenities | `dive-centre` | Dive centre | - | dive center, dive shop, PADI | 61 (19 / 42 / 2) | - | enum_places_amenities |  |
| amenities | `cold-plunge` | Cold plunge / ice bath | - | ice bath | 44 (13 / 31 / 0) | - | enum_places_amenities |  |
| amenities | `gluten-free` | Gluten-free options | - | gluten free | 40 (11 / 29 / 0) | cuisine/Gluten-free 40 | enum_places_amenities | dietary -> amenities (D15); merges the cuisine/Gluten-free candidate |
| amenities | `cigar-lounge` | Cigar lounge | - | cigar | 33 (16 / 17 / 0) | - | enum_places_amenities |  |
| amenities | `wine-cellar` | Wine cellar | - | - | 32 (15 / 17 / 2) | - | enum_places_amenities |  |
| amenities | `sports-screening` | Sports screening | - | big screen, live sports | 24 (11 / 13 / 2) | - | enum_places_amenities |  |
| audience | `women` | Women | - | female travellers, ladies | 755 (371 / 384 / 48) | - | platform only | lexical count inflated by generic 'women'; 48 title hits support a segment |
| audience | `students` | Students | - | teenagers, university students | 588 (430 / 158 / 31) | - | platform only |  |
| audience | `foodies` | Foodies | - | foodie | 147 (84 / 63 / 11) | - | platform only |  |
| audience | `seniors` | Seniors | - | elderly, retirees, retirement | 63 (40 / 23 / 0) | audience/Retiree 20 | platform only | merges the Retiree candidate (20) |
| audience | `surfers` | Surfers | - | - | 56 (12 / 44 / 0) | - | platform only |  |
| audience | `divers` | Divers | - | - | 45 (17 / 28 / 0) | - | platform only |  |
| audience | `yogis` | Yogis | - | yogi | 37 (10 / 27 / 0) | - | platform only |  |
| audience | `digital-nomads` | Digital nomads | - | digital nomad, remote workers | 23 (3 / 20 / 1) | - | platform only |  |
| audience | `backpackers` | Backpackers | - | backpacker, budget travellers | 20 (9 / 11 / 0) | - | platform only |  |
| cuisine | `coffee` | Coffee | - | kopi, specialty coffee, espresso | 941 (491 / 450 / 57) | - | enum_places_cuisine |  |
| cuisine | `dessert` | Dessert | - | gelato, ice cream, pastry, patisserie | 785 (439 / 346 / 25) | - | enum_places_cuisine |  |
| cuisine | `fusion` | Fusion | - | fusion cuisine | 333 (170 / 163 / 20) | - | enum_places_cuisine |  |
| cuisine | `bbq` | BBQ & grill | - | barbecue, smokehouse, BBQ | 159 (74 / 85 / 11) | - | enum_places_cuisine | 'BBQ' trimmed from cuisine/american |
| cuisine | `acehnese` | Acehnese | - | Aceh cuisine, mie Aceh | 73 (48 / 25 / 0) | - | enum_places_cuisine | bare 'Aceh' is the location; not an alias here |
| cuisine | `portuguese` | Portuguese | - | - | 53 (39 / 14 / 2) | - | enum_places_cuisine |  |
| cuisine | `singaporean` | Singaporean | - | - | 47 (29 / 18 / 2) | - | enum_places_cuisine |  |
| cuisine | `hotpot` | Hotpot | - | hot pot, shabu-shabu, steamboat | 41 (23 / 18 / 8) | - | enum_places_cuisine | 'hotpot' trimmed from cuisine/chinese |
| cuisine | `nordic` | Nordic | - | Scandinavian | 39 (30 / 9 / 5) | - | enum_places_cuisine |  |
| cuisine | `moroccan` | Moroccan | - | - | 34 (19 / 15 / 3) | - | enum_places_cuisine |  |
| cuisine | `malaysian` | Malaysian | - | - | 33 (27 / 6 / 1) | - | enum_places_cuisine |  |
| cuisine | `tea` | Tea | - | tea house, teahouse, artisan tea | 22 (19 / 3 / 0) | - | enum_places_cuisine | the venue_kind Tea house candidate (24) goes to eat/cafe's alias set |
| location | `europe` | Europe | international | Paris, London, Amsterdam, Rome, Italy, France, Switzerland, Germany, Spain, Portugal, Vienna, Prague | 1247 (825 / 422 / 67) | - | enum_places_area_term | region node; a country splits out once it reaches >= 20 on its own |
| location | `java` | Java | other | Central Java, East Java, West Java | 859 (537 / 322 / 52) | - | enum_places_area_term | region node; re-parenting other/* cities under this and the other region nodes below is APPROVED (Hansel, follow-up #4, 2026-09-10; parent_id only) -- see resolutions.RULES['location']['reparenting']. Applied by the seed ticket, not by this delta. |
| location | `australia` | Australia | international | Sydney, Melbourne, Perth, Brisbane | 508 (285 / 223 / 37) | - | enum_places_area_term |  |
| location | `singapore` | Singapore | international | - | 482 (356 / 126 / 29) | - | enum_places_area_term |  |
| location | `japan` | Japan | international | Tokyo, Kyoto, Osaka, Hokkaido | 481 (317 / 164 / 33) | - | enum_places_area_term | lexicon label 'Tokyo' relabelled to the country |
| location | `usa` | United States | international | New York, Los Angeles, San Francisco, Las Vegas, Hawaii, USA | 377 (248 / 129 / 6) | - | enum_places_area_term |  |
| location | `china` | China | international | Shanghai, Beijing, Macau | 361 (250 / 111 / 4) | - | enum_places_area_term |  |
| location | `thailand` | Thailand | international | Bangkok, Phuket, Chiang Mai, Koh Samui | 293 (198 / 95 / 14) | - | enum_places_area_term | lexicon label 'Bangkok' relabelled to the country |
| location | `india` | India | international | Mumbai, Delhi, Kerala, Rajasthan | 290 (169 / 121 / 8) | - | enum_places_area_term |  |
| location | `malaysia` | Malaysia | international | Kuala Lumpur, Penang, Langkawi | 228 (176 / 52 / 6) | - | enum_places_area_term | lexicon label 'Kuala Lumpur' relabelled to the country |
| location | `sumatra` | Sumatra | other | - | 206 (127 / 79 / 11) | - | enum_places_area_term | region node |
| location | `hong-kong` | Hong Kong | international | - | 182 (125 / 57 / 12) | - | enum_places_area_term |  |
| location | `sulawesi` | Sulawesi | other | Wakatobi, Togean | 179 (124 / 55 / 6) | - | enum_places_area_term | region node |
| location | `africa` | Africa | international | Kenya, Tanzania, Cape Town, Morocco, Marrakech, Egypt | 163 (111 / 52 / 0) | - | enum_places_area_term | region node |
| location | `tabanan` | Tabanan | west-bali | - | 162 (18 / 144 / 6) | - | enum_places_area_term |  |
| location | `kalimantan` | Kalimantan | other | Borneo, Derawan, Tanjung Puting | 156 (114 / 42 / 7) | - | enum_places_area_term | region node |
| location | `turkey` | Turkey | international | Istanbul, Cappadocia | 154 (103 / 51 / 4) | - | enum_places_area_term |  |
| location | `kintamani` | Kintamani & Mount Batur | north-bali | Mount Batur, Batur, Lake Batur | 153 (16 / 137 / 5) | - | enum_places_area_term | Bangli-regency highlands, grouped with the north for readers |
| location | `gianyar` | Gianyar | central-bali | Sukawati, Celuk, Batubulan, Keliki, Tampaksiring | 150 (6 / 144 / 3) | - | enum_places_area_term | the regency's towns outside Ubud; central-bali keeps 'Gianyar' as its own alias |
| location | `south-korea` | South Korea | international | Seoul, Korea, Jeju | 145 (114 / 31 / 12) | - | enum_places_area_term | lexicon label 'Seoul' relabelled to the country |
| location | `new-zealand` | New Zealand | international | Auckland, Queenstown | 138 (91 / 47 / 12) | - | enum_places_area_term |  |
| location | `nusa-tenggara` | Nusa Tenggara | other | NTT, Sumbawa, Alor, Kupang, Ende, Kelimutu | 133 (90 / 43 / 3) | - | enum_places_area_term | region node; lombok, komodo and sumba stay their own leaves |
| location | `vietnam` | Vietnam | international | Hanoi, Ho Chi Minh, Da Nang, Hoi An | 123 (88 / 35 / 3) | - | enum_places_area_term |  |
| location | `west-bali` | West Bali | bali | Menjangan, Pemuteran, Jembrana, Negara, Gilimanuk, Perancak | 109 (11 / 98 / 11) | - | enum_places_area_term | new district -- Section 4 has no West Bali node; parent of tabanan, tanah-lot, jatiluwih |
| location | `maluku` | Maluku | other | Moluccas, Banda, Ambon, Ternate, Seram | 109 (78 / 31 / 6) | - | enum_places_area_term | region node |
| location | `philippines` | Philippines | international | Manila, Cebu, Palawan | 105 (82 / 23 / 1) | - | enum_places_area_term |  |
| location | `kebayoran-baru` | Kebayoran Baru | south-jakarta | Kebayoran | 103 (103 / 0 / 1) | - | enum_places_area_term | 'Kebayoran Baru' trimmed from gunawarman (a strip inside the district) |
| location | `bedugul` | Bedugul & Lake Bratan | north-bali | Bratan, Beratan, Lake Bratan | 87 (7 / 80 / 9) | - | enum_places_area_term | highlands next to Munduk (a north-bali alias) |
| location | `uae` | United Arab Emirates | international | Dubai, Abu Dhabi, UAE | 84 (52 / 32 / 3) | - | enum_places_area_term | lexicon label 'Dubai' relabelled to the country |
| location | `aceh` | Aceh | other | Banda Aceh, Weh, Pulau Weh | 70 (46 / 24 / 0) | - | enum_places_area_term |  |
| location | `bangli` | Bangli & Penglipuran | central-bali | Penglipuran | 69 (2 / 67 / 4) | - | enum_places_area_term |  |
| location | `cilandak` | Cilandak | south-jakarta | TB Simatupang, Simatupang | 69 (69 / 0 / 5) | - | enum_places_area_term |  |
| location | `kemayoran` | Kemayoran | central-jakarta | JIExpo | 67 (66 / 1 / 5) | - | enum_places_area_term |  |
| location | `gatot-subroto` | Gatot Subroto | south-jakarta | Jalan Gatot Subroto, Semanggi | 66 (62 / 4 / 3) | - | enum_places_area_term |  |
| location | `nusa-lembongan` | Nusa Lembongan | east-bali | Lembongan, Ceningan, Nusa Ceningan | 58 (2 / 56 / 13) | - | enum_places_area_term | sibling of nusa-penida; 'Nusa Lembongan' / 'Nusa Ceningan' trimmed from nusa-penida |
| location | `tanah-abang` | Tanah Abang | central-jakarta | - | 53 (52 / 1 / 3) | - | enum_places_area_term |  |
| location | `middle-east` | Middle East | international | Qatar, Doha, Oman, Jordan | 50 (40 / 10 / 7) | - | enum_places_area_term | region node for the Gulf and Levant outside the UAE and Turkey |
| location | `cambodia` | Cambodia | international | Siem Reap, Angkor, Laos, Luang Prabang | 47 (37 / 10 / 1) | - | enum_places_area_term | Laos rides along as an alias until it reaches >= 20 on its own (joint count 47) |
| location | `taiwan` | Taiwan | international | Taipei | 47 (36 / 11 / 3) | - | enum_places_area_term |  |
| location | `casablanca` | Casablanca | south-jakarta | Kota Kasablanka, Casablanca Raya | 47 (41 / 6 / 5) | - | enum_places_area_term |  |
| location | `mengwi` | Mengwi | south-bali | Taman Ayun | 45 (1 / 44 / 1) | - | enum_places_area_term |  |
| location | `riau-islands` | Riau Islands | other | Batam, Riau | 44 (40 / 4 / 5) | - | enum_places_area_term | bintan stays its own leaf |
| location | `kebon-sirih` | Kebon Sirih & Sabang | central-jakarta | Sabang, Jalan Sabang | 41 (36 / 5 / 2) | - | enum_places_area_term |  |
| location | `tanah-lot` | Tanah Lot | west-bali | - | 40 (2 / 38 / 1) | - | enum_places_area_term |  |
| location | `palembang` | Palembang | other | - | 39 (35 / 4 / 1) | - | enum_places_area_term |  |
| location | `padang` | Padang | other | Bukittinggi, West Sumatra | 38 (24 / 14 / 0) | - | enum_places_area_term | homonym with cuisine/padang -- see match hint |
| location | `cengkareng` | Cengkareng | west-jakarta | Soekarno-Hatta, CGK | 38 (37 / 1 / 1) | - | enum_places_area_term |  |
| location | `lampung` | Lampung | other | Krakatau, Krakatoa, Way Kambas | 37 (27 / 10 / 3) | - | enum_places_area_term |  |
| location | `maldives` | Maldives | international | - | 32 (22 / 10 / 2) | - | enum_places_area_term |  |
| location | `kepulauan-seribu` | Kepulauan Seribu | north-jakarta | Thousand Islands, Pulau Seribu | 32 (28 / 4 / 3) | - | enum_places_area_term | its own regency administratively; filed under north-jakarta for readers |
| location | `jatiluwih` | Jatiluwih | west-bali | - | 31 (3 / 28 / 1) | - | enum_places_area_term |  |
| location | `cirebon` | Cirebon | other | - | 30 (28 / 2 / 0) | - | enum_places_area_term |  |
| location | `sri-lanka` | Sri Lanka | international | Colombo | 29 (20 / 9 / 1) | - | enum_places_area_term |  |
| location | `tmii` | TMII / Taman Mini | east-jakarta | Taman Mini, Taman Mini Indonesia Indah | 25 (25 / 0 / 4) | - | enum_places_area_term |  |
| occasion | `festive` | Festive season | - | Christmas, New Year, New Year's Eve, festive season, year-end, Thanksgiving | 639 (349 / 290 / 211) | - | platform only |  |
| occasion | `wedding` | Wedding | - | weddings, honeymoon, proposal, bridal, bachelorette, hen party | 220 (126 / 94 / 21) | - | platform only | D22 |
| occasion | `ramadan` | Ramadan & Eid | - | iftar, buka puasa, Lebaran, Eid | 191 (162 / 29 / 115) | - | platform only |  |
| occasion | `balinese-holy-days` | Balinese holy days | - | Nyepi, Galungan, Kuningan, Saraswati, Pagerwesi | 179 (17 / 162 / 56) | - | platform only | 'Kuningan' here is the holy day -- the location/kuningan hint points Bali text at this term |
| occasion | `independence-day` | Independence Day | - | 17 August, Hari Merdeka | 95 (72 / 23 / 23) | - | platform only |  |
| occasion | `lunar-new-year` | Lunar New Year | - | Chinese New Year, Imlek | 91 (72 / 19 / 44) | - | platform only |  |
| occasion | `road-trip` | Road trip | - | island hopping | 82 (39 / 43 / 10) | - | platform only | 'itinerary' inflates; not an alias |
| occasion | `halloween` | Halloween | - | - | 30 (14 / 16 / 14) | - | platform only |  |
| subtype | `temple` | Temple | do | temples, pura, klenteng, Chinese temple | 553 (75 / 478 / 49) | - | enum_places_subtype | Bali's most-mentioned venue kind (553); a place to visit, hence `do` |
| subtype | `bookshop` | Bookshop | shop | bookstore, book shop, library | 302 (214 / 88 / 11) | - | enum_places_subtype | libraries ride along: not a shop, but the only node close to one |
| subtype | `dessert-shop` | Dessert shop | eat | gelato, gelateria, ice cream parlour, dessert bar, patisserie | 272 (148 / 124 / 4) | - | enum_places_subtype |  |
| subtype | `farm` | Farm & plantation | do | organic farm, plantation, coffee plantation, agritourism | 238 (104 / 134 / 18) | - | enum_places_subtype |  |
| subtype | `zoo` | Zoo & safari park | do | safari, bird park, butterfly park, elephant park, aquarium | 178 (78 / 100 / 40) | - | enum_places_subtype |  |
| subtype | `place-of-worship` | Church & mosque | do | church, cathedral, mosque, masjid | 141 (109 / 32 / 7) | - | enum_places_subtype | temples have their own node |
| subtype | `theatre` | Theatre & concert hall | do | theater, concert hall, performing arts centre, Ciputra Artpreneur, Salihara, Aula Simfonia | 135 (119 / 16 / 11) | - | enum_places_subtype | the venue; event/performance is the dated show |
| subtype | `nature` | Nature spot | do | waterfall, waterfalls, lake, hot spring, hot springs, mangrove, national park, rice terrace, rice terraces, viewpoint | 115 (39 / 76 / 6) | venue_kind/Rice terrace 71; venue_kind/Hot spring 28 | enum_places_subtype | merges Rice terrace (71) and Hot spring (28): the missing 'outdoor place to go' node Bali's Nature and Outdoors category needed |
| subtype | `winery-distillery` | Winery & distillery | drink | winery, vineyard, distillery, brewery, taproom, cellar door | 76 (34 / 42 / 1) | venue_kind/Distillery 39 | enum_places_subtype | merges Distillery (39); Brewery / taproom (12) is below threshold and rides along as an alias |
| subtype | `karaoke` | Karaoke | drink | KTV, karaoke bar | 54 (42 / 12 / 3) | - | enum_places_subtype |  |
| subtype | `cinema` | Cinema | do | movie theatre, movie theater, XXI, CGV | 26 (19 / 7 / 2) | - | enum_places_subtype | the venue; event/screening is the dated showing |
| topic | `food-drink` | Food & drink | - | culinary, gastronomy, recipe, recipes, cooking | 3713 (1891 / 1822 / 444) | - | platform only | 'chef', 'wine', 'coffee', 'cocktail' inflate; not aliases |
| topic | `weddings` | Weddings & romance | - | wedding, weddings, bridal, honeymoon, romance | 1384 (722 / 662 / 148) | topic/Weddings 170 | platform only | merges the Weddings topic candidate (170); 'love' inflates and is not an alias |
| topic | `religion-spirituality` | Religion & spirituality | - | Hindu, Hinduism, Islam, Buddhism, spirituality, spiritual | 956 (351 / 605 / 35) | - | platform only | 'church' / 'mosque' belong to do/place-of-worship |
| topic | `coffee-culture` | Coffee culture | - | barista, roastery, specialty coffee | 899 (477 / 422 / 60) | - | platform only |  |
| topic | `urban-issues` | Urban issues | - | flooding, pollution, air quality, city planning, congestion | 821 (584 / 237 / 47) | - | platform only | governor names dropped from the aliases |
| topic | `agriculture` | Agriculture & food systems | - | farmers, farming, fishermen, seaweed farming, permaculture | 736 (287 / 449 / 22) | - | platform only |  |
| topic | `covid-19` | Covid-19 | - | Covid, pandemic, lockdown, PSBB, PPKM, new normal | 438 (192 / 246 / 62) | - | platform only |  |
| topic | `pets-animals` | Pets & animals | - | dogs, cats, animal welfare, wildlife, sea turtles | 418 (160 / 258 / 27) | - | platform only |  |
| topic | `craft-spirits` | Craft spirits & brewing | - | arak, gin, rum, craft beer, distillery | 393 (142 / 251 / 41) | - | platform only | 'winery' / 'vineyard' belong to drink/winery-distillery |
| topic | `spa-beauty` | Spa & beauty | - | facial, skincare, beauty | 190 (56 / 134 / 8) | - | platform only |  |
| topic | `tourism` | Tourism | - | mass tourism, overtourism, tourism history | 34 (6 / 28 / 1) | - | platform only |  |
| vibe | `tropical` | Tropical | - | island-style, resort-style | 2895 (623 / 2272 / 148) | - | enum_places_vibe | bare 'island' inflates; not an alias |
| vibe | `authentic` | Authentic | - | traditional | 2831 (1286 / 1545 / 109) | - | enum_places_vibe |  |
| vibe | `modern` | Modern | - | contemporary, minimalist, industrial, sleek | 2573 (1353 / 1220 / 114) | - | enum_places_vibe | 'contemporary' also matches contemporary art -- 114 title hits still support it |
| vibe | `exclusive` | Exclusive | - | members-only, VIP | 1996 (1060 / 936 / 62) | - | enum_places_vibe | 'private' inflates; not an alias |
| vibe | `chic` | Chic | - | stylish, elegant, sophisticated, refined | 1608 (724 / 884 / 67) | - | enum_places_vibe |  |
| vibe | `wholesome` | Wholesome | - | mindful, conscious | 887 (421 / 466 / 37) | - | enum_places_vibe | 'healthy' belongs to amenities/healthy-menu |
| vibe | `glamorous` | Glamorous | - | glam, lavish, decadent, indulgent | 791 (343 / 448 / 45) | - | enum_places_vibe |  |
| vibe | `quirky` | Quirky | - | whimsical, eclectic, playful | 643 (261 / 382 / 19) | - | enum_places_vibe |  |
| vibe | `edgy` | Edgy | - | underground, alternative, cool | 522 (207 / 315 / 9) | - | enum_places_vibe | relabelled from 'Cool' -- the bare word is a homonym; kept as an alias for the prompt |
| vibe | `rustic` | Rustic | - | earthy | 455 (210 / 245 / 5) | - | enum_places_vibe | 'raw' inflates; not an alias |
| vibe | `nostalgic` | Nostalgic | - | retro, vintage, colonial charm | 242 (145 / 97 / 5) | - | enum_places_vibe |  |
| vibe | `family-friendly` | Family-friendly | - | kid-friendly | 176 (92 / 84 / 9) | - | enum_places_vibe | overlaps audience/family and amenities/kids-club by design: a vibe of the place, not who it is for |

## 3. Add aliases to existing terms (no migration — aliases are not persisted)

| facet | slug | aliases added | evidence (candidate: mentions) | note |
|---|---|---|---|---|
| amenities | `coworking-space` | co-working, coworking | amenities/Co-working 347 | 'ballroom' and 'MICE' were lumped into this candidate by the lexicon and carry no separate count -- not added |
| amenities | `gym` | fitness center | amenities/Gym 37 |  |
| amenities | `kids-club` | kids' club, kid's club, children's club | amenities/Kids club 165 |  |
| amenities | `ocean-view` | cliff-top, cliffside | amenities/Ocean view 61 |  |
| amenities | `outdoor-seating` | alfresco, garden seating | amenities/Outdoor seating 70 |  |
| amenities | `vegan-options` | vegan | cuisine/Vegan 152; amenities/Vegan options 152 | dietary -> amenities (D15) |
| amenities | `vegetarian-friendly` | vegetarian, vegetarian options | amenities/Vegetarian options 181; cuisine/Vegetarian 181 | dietary -> amenities (D15); merges the cuisine/Vegetarian candidate |
| amenities | `wifi` | wifi | amenities/Wi-Fi 60 |  |
| audience | `business-traveller` | business travellers, business traveler, corporate travellers | audience/Business traveller 41 |  |
| audience | `couples` | honeymooners, lovebirds | audience/Couples 62 |  |
| audience | `expat` | expats, expatriates, international community | audience/Expat 142 |  |
| audience | `family` | families, toddlers | audience/Family 994 |  |
| audience | `local` | locals, Jakartans, residents | audience/Local 801 |  |
| audience | `tourist` | tourists, visitors, travellers, traveler, travelers | audience/Tourist 1926 |  |
| cuisine | `american` | burger | cuisine/Burgers 115 |  |
| cuisine | `balinese` | Balinese cuisine, Balinese food | cuisine/Balinese 84 |  |
| cuisine | `chinese` | Szechuan | cuisine/Sichuan 24 |  |
| cuisine | `indonesian` | Indonesian cuisine, Indonesian food | cuisine/Indonesian 272 |  |
| cuisine | `japanese` | teppanyaki | cuisine/Teppanyaki 98 |  |
| cuisine | `latin-american` | Nikkei | cuisine/Peruvian 40 |  |
| cuisine | `mexican` | taco, tacos | cuisine/Mexican 87 |  |
| cuisine | `middle-eastern` | Arab | cuisine/Middle Eastern 31 |  |
| cuisine | `steakhouse` | steak | cuisine/Steak 266 |  |
| cuisine | `western` | Western food, Western cuisine | cuisine/Western 36 |  |
| location | `cipete` | Antasari, Pangeran Antasari | location_jakarta/Antasari 25 | parallel to Fatmawati, already a cipete alias |
| location | `east-bali` | Amlapura, Tirta Gangga, Tenganan, Besakih, Padang Bai, Padangbai | location_bali/Karangasem 115 | 'Karangasem' is already east-bali's alias -- the regency IS East Bali; its towns become aliases rather than a redundant node |
| location | `gianyar` | Ketewel, Saba | location_bali/Sanur / Ketewel 25 | Gianyar coast, not Sanur (the lexicon label was wrong) |
| location | `jimbaran` | Kedonganan | location_bali/Kedonganan 27 | adjacent beach on the same bay |
| location | `komodo` | Komodo | location_elsewhere/Komodo & Labuan Bajo 74 |  |
| location | `lombok` | Gili | location_elsewhere/Lombok 39 |  |
| location | `sanur` | Serangan | location_bali/Serangan 21 | island off Sanur |
| location | `ubud` | Peliatan | location_bali/Ubud 24 |  |
| location | `uluwatu` | Balangan | location_bali/Uluwatu 21 |  |
| occasion | `business-trip` | business dinner, team building, team-building, MICE | occasion/Business 570 | the label duplicates business-trip, so an alias set, not a term; 'client' and 'meeting' inflate and are not added |
| occasion | `date-night` | Valentine, romantic dinner | occasion/Date night 136 |  |
| occasion | `family-day` | family outing, family getaway | occasion/Family day 26 |  |
| occasion | `group-gathering` | large group, group booking, group of friends | occasion/Group 49 |  |
| occasion | `night-out` | after-work, after work, girls' night, boys' night | occasion/Night out 43 |  |
| subtype | `adventure` | volcano, Mount Batur, Mount Agung, sunrise trek, trek, trekking, hiking, ATV, quad bike, buggy, horse riding, horseback riding, helicopter tour, hot air balloon, rafting, white water rafting | venue_kind/Volcano 121; venue_kind/Trekking / hiking 69; venue_kind/ATV / buggy 46; venue_kind/Horse riding 32; venue_kind/Helicopter / balloon 31; venue_kind/Rafting 25 |  |
| subtype | `attraction` | palace, water palace, puri, waterpark, water park | venue_kind/Palace 249; venue_kind/Waterpark 37 |  |
| subtype | `bakery` | sourdough, croissant | cuisine/Bakery 68 |  |
| subtype | `beach-club` | beach clubs | venue_kind/Beach club 55 |  |
| subtype | `cafe` | café, coffee shop, roastery, kopi, tea house, teahouse, tea room | venue_kind/Coffee shop 400; venue_kind/Tea house 24 |  |
| subtype | `conference` | convention centre, convention center, exhibition hall, JCC, ICE BSD, JIExpo | venue_kind/Convention centre 112 |  |
| subtype | `education` | school, kindergarten, preschool, international school | venue_kind/School 54 |  |
| subtype | `fine-dining` | degustation, Michelin, tasting menu | cuisine/Fine dining 193 |  |
| subtype | `mall` | shopping mall, plaza | venue_kind/Mall 269 |  |
| subtype | `market` | night market | venue_kind/Market 24 |  |
| subtype | `pop-up` | pop up | venue_kind/Pop-up 35 |  |
| subtype | `retreat` | retreat centre, retreat center, healing centre, wellness centre, wellness center | venue_kind/Retreat centre 54 |  |
| subtype | `salon` | barber, nail salon, manicure | venue_kind/Barbershop 35; venue_kind/Nail bar 29 |  |
| subtype | `serviced-apartment` | serviced apartments, residence | venue_kind/Serviced apartment 219 |  |
| subtype | `sports` | stadium, arena | venue_kind/Stadium 81 |  |
| subtype | `sports-activity` | golf course, golf club, driving range, billiards, pool hall, arcade, trampoline park, escape room | venue_kind/Golf course 68; venue_kind/Billiards / bowling 66 |  |
| subtype | `street-food` | warung, warungs | venue_kind/Warung 31 |  |
| subtype | `tour` | bike tour, cycling tour, bicycle tour, sunset cruise, dinner cruise, liveaboard, phinisi | venue_kind/Cycling 64; venue_kind/Cruise 31 |  |
| subtype | `villa` | villas | venue_kind/Villa 483 |  |
| subtype | `watersports` | surf, surfing, surf school, surf camp, snorkelling, snorkeling, scuba, diving, freediving, kitesurfing, kitesurf, sailing, catamaran, yacht | venue_kind/Surfing 154; venue_kind/Snorkelling / diving 53; venue_kind/Kitesurfing / sailing 37 |  |
| subtype | `workshop` | cooking class, cooking classes, culinary class | venue_kind/Cooking class 69 |  |
| subtype | `yoga` | yoga studio, yoga shala, shala, yoga barn | venue_kind/Yoga studio 64 |  |
| topic | `business` | entrepreneur, start-up | topic/Business 80 |  |
| topic | `community` | foundation, volunteer, fundraising | topic/Community 654 |  |
| topic | `culture` | ritual | topic/Culture 512 |  |
| topic | `design` | architect | topic/Design 138 |  |
| topic | `education` | curriculum | topic/Education 568 |  |
| topic | `expat-life` | living in Bali, KITAS, moving to | topic/Expat life 104 |  |
| topic | `health` | well-being | topic/Health 202 |  |
| topic | `literature` | novel | topic/Literature 1003 |  |
| topic | `music` | band | topic/Music 292 |  |
| topic | `photography` | photographer | topic/Photography 117 |  |
| topic | `property` | apartment | topic/Property 105 |  |
| topic | `sports` | tennis, rugby, badminton, basketball, MotoGP, Formula | topic/Sports 213 |  |
| topic | `sustainability` | sustainable, eco-friendly, zero-waste, plastic, recycling | topic/Sustainability 1022 |  |
| topic | `technology` | artificial intelligence, fintech, e-commerce | topic/Technology 165 |  |
| topic | `transport` | LRT, toll road, TransJakarta, flight, airline | topic/Transport 255 |  |
| topic | `travel` | itinerary, tourism | topic/Travel 809 |  |
| vibe | `casual` | laidback | vibe/Casual 117 |  |
| vibe | `classic` | timeless, legendary, iconic | vibe/Classic 1366 |  |
| vibe | `cozy` | cosy | vibe/Cozy 276 |  |
| vibe | `hidden-gem` | secret, tucked away | vibe/Hidden gem 306 |  |
| vibe | `lively` | vibrant | vibe/Lively 975 |  |
| vibe | `luxury` | luxurious, 5-star | vibe/Luxury 689 |  |
| vibe | `scenic` | breathtaking view, panoramic, stunning views, sweeping views | vibe/Scenic 276 |  |
| vibe | `serene` | calm, sanctuary, oasis | vibe/Serene 765 |  |
| vibe | `trendy` | hipster, happening | vibe/Trendy 208 |  |

Alias-suggestion forms deliberately not added: `amenities/kids-club` ← family-friendly (now vibe/family-friendly); `audience/family` ← teens (audience/students carries 'teenagers'); `location/bsd` ← BSD (already the term's label); `occasion/weekend-getaway` ← escape (inflates ('escape the city', 647 mentions)); `topic/fashion` ← collection (inflates (art collection, hotel collection)); `topic/literature` ← book (inflates ('book now', 'book a table')); `topic/education` ← students (audience/students); `topic/technology` ← app (inflates); `topic/property` ← developer (ambiguous (software developer)).

## 4. Drop terms

- **location/`rawamangun`** — 2 mentions. 2 corpus mentions, 0 in titles -- below every threshold; named by Hansel (D14). Migration: Postgres cannot remove a value from enum_places_area_term in place: leave the orphaned value (harmless, nothing references it) or recreate the type. Delete the engine.terms row after confirming no entity_terms row references it (cross-DB, check every city).

## 5. Trim aliases (homonym-inflated)

| facet | slug | remove | keep | reason |
|---|---|---|---|---|
| cuisine | `javanese` | Solo | Javanese, Jawa, Jogja | the city homonym; Solo-style food is Javanese without naming the city (Hansel: `solo`). |
| occasion | `celebration` | party | Celebration, birthday, wedding | 'third party', 'party of four'; vibe/party owns the nightlife sense (Hansel: `party`). |
| audience | `business-traveller` | business | Business traveller, corporate visitor | the bare noun is a topic (topic/business), not an audience (Hansel: `business`-as-audience). |
| location | `malang` | Batu | Malang, Bromo | Indonesian for 'stone': Batu Bolong, Batubulan, Mount Batur (Hansel: `Batu`). |
| location | `gunawarman` | Wijaya, Kebayoran Baru | Gunawarman / Dharmawangsa, Dharmawangsa, Wolter Monginsidi | 'Wijaya' is a common surname (Made Wijaya, the Stranger In Paradise author) and only one street of the strip (Hansel: `Wijaya`); Kebayoran Baru is now its own node. |
| vibe | `party` | late night | Party, nightlife | an opening-hours amenity, now amenities/late-night. |
| cuisine | `american` | BBQ | American, burgers, diner | now cuisine/bbq. |
| cuisine | `chinese` | hotpot | Chinese, Cantonese, Sichuan, dim sum | now cuisine/hotpot. |
| location | `nusa-penida` | Nusa Lembongan, Nusa Ceningan | Nusa Penida, Nusa Islands | now location/nusa-lembongan. |

## 6. Match hints for the E2.1 prompt (labels that are homonyms)

- `location/solo` — Match only title-case 'Solo' in a Central Java / Surakarta context; never 'solo traveller', 'solo exhibition', 'solo show'. Prefer 'Surakarta'.
- `occasion/solo` — The label is a homonym; 'solo traveller' / 'me time' are the evidence, never the bare word.
- `location/kuningan` — In Bali text 'Kuningan' is the holy day (occasion/balinese-holy-days), never the Jakarta district.
- `location/padang` — Bare 'Padang' is usually the cuisine (cuisine/padang); the city only in a travel context or via Bukittinggi / West Sumatra.
- `location/java` — Also matches Java Jazz and Java coffee; a region only when the piece travels there.
- `vibe/party` — The nightlife sense only ('party crowd', 'party scene'); not 'third party' or 'party of four'.
- `vibe/edgy` — 'cool' is kept as an alias for the prompt but the bare word is a homonym ('cool down', 'cool drinks').
- `location/international` — geo_scope=abroad: eligible for search and Row 3, never Row 2 or the itinerary; every child inherits. Only when the piece is about a destination outside Indonesia.

## 7. Merged and skipped candidates (≥ threshold, not added as their own term)

- audience/Retiree (20) → merged into audience/Seniors
- cuisine/Vegetarian (181) → merged into amenities/Vegetarian options — dietary -> amenities (D15)
- cuisine/Farm-to-table (58) → merged into cuisine/Organic
- cuisine/Gluten-free (40) → merged into amenities/Gluten-free
- topic/Weddings (170) → merged into topic/Weddings & romance
- venue_kind/Rice terrace (71) → merged into venue_kind/Waterfall
- venue_kind/Distillery (39) → merged into venue_kind/Winery
- venue_kind/Hot spring (28) → merged into venue_kind/Waterfall
- amenities/Karaoke (54) → skipped: covered by the new venue subtype drink/karaoke (identical surface forms); a karaoke room as a hotel amenity is not evidenced separately
- amenities/Yoga shala (45) → skipped: covered by the alias set added to wellness/yoga (yoga studio, yoga shala, shala); not evidenced as a separate resort amenity
- venue_kind/Co-working (44) → skipped: a co-working space has no venue-type node; covered by the alias set added to amenities/coworking-space

## 8. Below the threshold (23) — for the record, not added

location_international/Nepal / Bhutan 18, venue_kind/Tattoo studio 18, venue_kind/Padel / tennis 18, venue_kind/Embassy 18, amenities/Shisha 17, location_jakarta/Sunda Kelapa 17, cuisine/Argentinian 16, cuisine/Raw food 16, location_bali/Seseh / Cemagi 16, location_jakarta/Karawaci 16, venue_kind/Food hall / court 16, location_bali/Tejakula 15, location_jakarta/Grogol 15, location_jakarta/Mampang 15, venue_kind/Climbing gym 15, venue_kind/Eco lodge 15, location_elsewhere/Anyer / Carita 14, audience/LGBTQ 13, amenities/Surf break 12, location_jakarta/Pejaten 12, location_jakarta/Senen 12, venue_kind/Brewery / taproom 12, venue_kind/Dive centre 12

## 9. Migration (F20)

Adding a TERM to a facet that is a Payload ENUM needs `migrate:create` + `migrate` on every city DB and a restart of every cms-<city>. Aliases, attrs, match hints and approvals of already-seeded proposed terms need no migration (aliases are not persisted; proposed terms are already enum values).

New enum values by facet: **amenities** (enum_places_amenities): buffet, organic, jungle-view, free-flow, sauna, breakfast-included, late-night, rice-field-view, private-pool, delivery, lagoon-pool, river-view, cabanas, airport-transfer, swim-up-bar, butler, healthy-menu, dive-centre, cold-plunge, gluten-free, cigar-lounge, wine-cellar, sports-screening; **cuisine** (enum_places_cuisine): coffee, dessert, fusion, bbq, acehnese, portuguese, singaporean, hotpot, nordic, moroccan, malaysian, tea; **location** (enum_places_area_term): europe, java, australia, singapore, japan, usa, china, thailand, india, malaysia, sumatra, hong-kong, sulawesi, africa, tabanan, kalimantan, turkey, kintamani, gianyar, south-korea, new-zealand, nusa-tenggara, vietnam, west-bali, maluku, philippines, kebayoran-baru, bedugul, uae, aceh, bangli, cilandak, kemayoran, gatot-subroto, nusa-lembongan, tanah-abang, middle-east, cambodia, taiwan, casablanca, mengwi, riau-islands, kebon-sirih, tanah-lot, palembang, padang, cengkareng, lampung, maldives, kepulauan-seribu, jatiluwih, cirebon, sri-lanka, tmii; **subtype** (enum_places_subtype): temple, bookshop, dessert-shop, farm, zoo, place-of-worship, theatre, nature, winery-distillery, karaoke, cinema; **vibe** (enum_places_vibe): tropical, authentic, modern, exclusive, chic, wholesome, glamorous, quirky, edgy, rustic, nostalgic, family-friendly.

Platform-only facets (no Payload enum, `engine.terms` upsert only): occasion, audience, topic.

`attrs` (geo_scope on location/international) has no column yet: engine.terms.attrs jsonb is the taxonomy README's proposed DDL #1 -- an additive platform-DB migration; until it lands the attribute lives in the seed file as documentation and the rails read the international subtree by parent.

- 1. edit engine/packages/taxonomy/seed/terms/*.json per this file (approve = drop the `proposed` flag; add_term/add_alias/trim as listed; delete rawamangun)
- 2. `now-db migrate --all` -- upserts platform engine.terms (type_relations untouched: no L1 change; format_decay untouched: opinion already listed)
- 3. Payload `migrate:create` + `migrate` on every city DB for the facets in new_enum_values
- 4. restart every cms-<city>
- 5. E2.1 reads its enums from the platform DB -- run it after step 2, or accept a second pass for the new terms

---
*Generated by `now-taxonomy-evidence build`; regenerate rather than hand-edit. Source of truth: `vocabulary_delta.py`.*

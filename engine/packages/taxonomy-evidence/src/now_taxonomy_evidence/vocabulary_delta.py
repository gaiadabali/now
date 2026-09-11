"""The reviewed vocabulary delta (D03-D06, D11-D16, D22): what the seed ticket applies.

Hansel's rule: add every corpus term with >= 20 mentions; below 20 stays out;
drop `location/rawamangun`; trim the homonym-inflated aliases (`solo`,
`party`, `business`-as-audience, `Batu`, `Wijaya`).

This module turns that rule into an exact, reviewable list. It never writes
to `engine/packages/taxonomy/seed/` -- the seed change and its Payload ENUM
migration (F20) are a separate ticket that applies this file.

How the list is built (`build_delta`):

* every vocabulary candidate at or above the threshold MUST have an entry in
  `CANDIDATE_ACTIONS` (add a term, add an alias set to an existing term,
  merge into another candidate, or skip with a reason) -- the build fails
  loudly on an unmapped candidate, so the delta cannot silently miss one;
* counts are taken from the corpus scan (`vocabulary.analyse_vocabulary`),
  never typed here;
* alias suggestions (surface forms for terms the seed already has) at or
  above the threshold become alias additions, minus a short list of
  homonym-inflating forms with the reason next to each;
* every seed term marked `proposed` is approved (D03/D04/D05/D06/D11/D12/
  D13/D14) except the named drop.

Curation calls (the judgement that is not mechanical):

* `venue_kind` candidates are L2 venue kinds. When an existing subtype
  already means the same thing the candidate becomes an alias set for it
  (Coffee shop -> eat/cafe); when no node exists a new subtype is added with
  an explicit L1 parent (Temple -> do/temple). Exclusion works at L1 only, so
  new L2 nodes never change competitor exclusion.
* dietary and approach terms (organic, healthy, vegetarian, vegan,
  gluten-free, farm-to-table) go to amenities, as the seed designed (D15).
* international destinations are named at country/region level with the
  cities as aliases (the lexicon probed by city: Tokyo -> japan).
* duplicates are merged (Retiree into seniors; the two wedding topics;
  Waterfall + Rice terrace + Hot spring into do/nature).
"""
from __future__ import annotations

from .resolutions import DECIDED_BY, DECIDED_ON

THRESHOLD = 20

# Facets that are Payload ENUMs (engine/packages/cms migration 20260908_131927):
# adding a TERM here needs `migrate:create` + `migrate` on every city DB and a
# restart of every cms-<city> (F20). Aliases and attrs are not persisted
# anywhere Payload reads; approving an already-seeded proposed term changes
# nothing in the enum (its value is already there).
PAYLOAD_ENUMS: dict[str, str] = {
    "type": "enum_places_type / enum_articles_primary_type",
    "subtype": "enum_places_subtype",
    "format": "enum_articles_format",
    "location": "enum_places_area_term",
    "cuisine": "enum_places_cuisine",
    "amenities": "enum_places_amenities",
    "vibe": "enum_places_vibe",
    "price_band": "enum_places_price_band",
}
PLATFORM_ONLY_FACETS: tuple[str, ...] = ("occasion", "audience", "topic")

FACET_FAMILY = {"location_jakarta": "location", "location_bali": "location", "location_elsewhere": "location", "location_international": "location", "venue_kind": "subtype"}

# Which decision approves a proposed seed term.
APPROVAL_DECISION: dict[tuple[str, str], str] = {
    ("format", "opinion"): "D03",
    ("subtype", "culture"): "D04",
    ("subtype", "lifestyle"): "D05",
    ("location", "international"): "D06",
    ("subtype", "sports-activity"): "D11",
    ("subtype", "performance"): "D12",
    ("subtype", "screening"): "D12",
    ("subtype", "pop-up"): "D12",
    ("subtype", "salon"): "D13",
    ("subtype", "retreat"): "D13",
}
APPROVAL_DEFAULT_BY_FACET = {"location": "D14", "cuisine": "D15"}

# Attributes that ride on approved/added terms (documentation today; persisted once engine.terms.attrs exists).
TERM_ATTRS: dict[tuple[str, str], dict] = {
    ("location", "international"): {"geo_scope": "abroad", "inherited_by_descendants": True},
}

DROPS: list[dict] = [
    {"facet": "location", "slug": "rawamangun", "reason": "2 corpus mentions, 0 in titles -- below every threshold; named by Hansel (D14).",
     "migration_note": "Postgres cannot remove a value from enum_places_area_term in place: leave the orphaned value (harmless, nothing references it) or recreate the type. Delete the engine.terms row after confirming no entity_terms row references it (cross-DB, check every city)."},
]

TRIMS: list[dict] = [
    {"facet": "cuisine", "slug": "javanese", "remove": ["Solo"], "reason": "the city homonym; Solo-style food is Javanese without naming the city (Hansel: `solo`)."},
    {"facet": "occasion", "slug": "celebration", "remove": ["party"], "reason": "'third party', 'party of four'; vibe/party owns the nightlife sense (Hansel: `party`)."},
    {"facet": "audience", "slug": "business-traveller", "remove": ["business"], "reason": "the bare noun is a topic (topic/business), not an audience (Hansel: `business`-as-audience)."},
    {"facet": "location", "slug": "malang", "remove": ["Batu"], "reason": "Indonesian for 'stone': Batu Bolong, Batubulan, Mount Batur (Hansel: `Batu`)."},
    {"facet": "location", "slug": "gunawarman", "remove": ["Wijaya", "Kebayoran Baru"], "reason": "'Wijaya' is a common surname (Made Wijaya, the Stranger In Paradise author) and only one street of the strip (Hansel: `Wijaya`); Kebayoran Baru is now its own node."},
    {"facet": "vibe", "slug": "party", "remove": ["late night"], "reason": "an opening-hours amenity, now amenities/late-night."},
    {"facet": "cuisine", "slug": "american", "remove": ["BBQ"], "reason": "now cuisine/bbq."},
    {"facet": "cuisine", "slug": "chinese", "remove": ["hotpot"], "reason": "now cuisine/hotpot."},
    {"facet": "location", "slug": "nusa-penida", "remove": ["Nusa Lembongan", "Nusa Ceningan"], "reason": "now location/nusa-lembongan."},
]

MATCH_HINTS: list[dict] = [
    {"facet": "location", "slug": "solo", "hint": "Match only title-case 'Solo' in a Central Java / Surakarta context; never 'solo traveller', 'solo exhibition', 'solo show'. Prefer 'Surakarta'."},
    {"facet": "occasion", "slug": "solo", "hint": "The label is a homonym; 'solo traveller' / 'me time' are the evidence, never the bare word."},
    {"facet": "location", "slug": "kuningan", "hint": "In Bali text 'Kuningan' is the holy day (occasion/balinese-holy-days), never the Jakarta district."},
    {"facet": "location", "slug": "padang", "hint": "Bare 'Padang' is usually the cuisine (cuisine/padang); the city only in a travel context or via Bukittinggi / West Sumatra."},
    {"facet": "location", "slug": "java", "hint": "Also matches Java Jazz and Java coffee; a region only when the piece travels there."},
    {"facet": "vibe", "slug": "party", "hint": "The nightlife sense only ('party crowd', 'party scene'); not 'third party' or 'party of four'."},
    {"facet": "vibe", "slug": "edgy", "hint": "'cool' is kept as an alias for the prompt but the bare word is a homonym ('cool down', 'cool drinks')."},
    {"facet": "location", "slug": "international", "hint": "geo_scope=abroad: eligible for search and Row 3, never Row 2 or the itinerary; every child inherits. Only when the piece is about a destination outside Indonesia."},
]

# Forms from the alias-suggestion list that are NOT added, with the reason.
ALIAS_FORM_SKIPS: dict[tuple[str, str], dict[str, str]] = {
    ("amenities", "Kids club"): {"family-friendly": "now vibe/family-friendly"},
    ("topic", "Fashion"): {"collection": "inflates (art collection, hotel collection)"},
    ("occasion", "Weekend getaway"): {"escape": "inflates ('escape the city', 647 mentions)"},
    ("topic", "Literature"): {"book": "inflates ('book now', 'book a table')"},
    ("topic", "Education"): {"students": "audience/students"},
    ("topic", "Technology"): {"app": "inflates"},
    ("topic", "Property"): {"developer": "ambiguous (software developer)"},
    ("audience", "Family"): {"teens": "audience/students carries 'teenagers'"},
    ("location_jakarta", "BSD"): {"BSD": "already the term's label"},
}


def _geo(lat: float, lng: float) -> dict:
    return {"lat": lat, "lng": lng}


def T(facet: str, slug: str, label: str, aliases: list[str] | tuple[str, ...] = (), parent: str | None = None, geo: dict | None = None, note: str = "") -> dict:
    return {"action": "add_term", "facet": facet, "slug": slug, "label": label, "aliases": list(aliases), "parent": parent, "geo": geo, "note": note}


def A(facet: str, slug: str, aliases: list[str] | tuple[str, ...], note: str = "") -> dict:
    return {"action": "add_alias", "facet": facet, "slug": slug, "aliases": list(aliases), "note": note}


def MERGE(target: str, note: str = "") -> dict:
    return {"action": "merge", "into": target, "note": note}


def SKIP(reason: str) -> dict:
    return {"action": "skip", "reason": reason}


# Keys are `<candidate facet>/<label>` exactly as the vocabulary scan emits them.
CANDIDATE_ACTIONS: dict[str, dict] = {
    # ---- amenities ------------------------------------------------------------
    "amenities/Buffet": T("amenities", "buffet", "Buffet", ["buffet breakfast", "brunch buffet"]),
    "amenities/Jungle view": T("amenities", "jungle-view", "Jungle view", ["rainforest view"], note="bare 'jungle' / 'rainforest' inflate the count (every jungle-view villa); aliases kept to the view sense"),
    "amenities/Co-working": A("amenities", "coworking-space", ["co-working", "coworking"], note="'ballroom' and 'MICE' were lumped into this candidate by the lexicon and carry no separate count -- not added"),
    "amenities/Free flow": T("amenities", "free-flow", "Free flow", ["free-flow", "bottomless"]),
    "amenities/Sauna / steam": T("amenities", "sauna", "Sauna & steam", ["steam room", "jacuzzi", "hot tub", "onsen"]),
    "amenities/Breakfast included": T("amenities", "breakfast-included", "Breakfast included", ["daily breakfast"]),
    "amenities/Late night": T("amenities", "late-night", "Open late", ["open late", "24 hours", "24-hour"], note="the opening-hours sense; 'late night' is trimmed from vibe/party"),
    "amenities/Vegetarian options": A("amenities", "vegetarian-friendly", ["vegetarian", "vegetarian options"], note="dietary -> amenities (D15); merges the cuisine/Vegetarian candidate"),
    "amenities/Rice-field view": T("amenities", "rice-field-view", "Rice-field view", ["rice field view", "paddy view", "rice paddies"]),
    "amenities/Private pool": T("amenities", "private-pool", "Private pool", ["plunge pool"]),
    "amenities/Delivery": T("amenities", "delivery", "Delivery & takeaway", ["takeaway", "take-away", "GoFood", "GrabFood"]),
    "amenities/Lagoon": T("amenities", "lagoon-pool", "Lagoon pool", ["lagoon"]),
    "amenities/River view": T("amenities", "river-view", "River view", ["riverside", "Ayung river"]),
    "amenities/Cabana / day bed": T("amenities", "cabanas", "Cabanas & day beds", ["cabana", "day bed", "daybed", "sunbed", "sun lounger"]),
    "amenities/Airport transfer": T("amenities", "airport-transfer", "Airport transfer", ["shuttle"]),
    "amenities/Swim-up bar": T("amenities", "swim-up-bar", "Swim-up bar", ["pool bar"]),
    "amenities/Butler": T("amenities", "butler", "Butler service", ["butler"]),
    "amenities/Dive centre": T("amenities", "dive-centre", "Dive centre", ["dive center", "dive shop", "PADI"]),
    "amenities/Karaoke": SKIP("covered by the new venue subtype drink/karaoke (identical surface forms); a karaoke room as a hotel amenity is not evidenced separately"),
    "amenities/Yoga shala": SKIP("covered by the alias set added to wellness/yoga (yoga studio, yoga shala, shala); not evidenced as a separate resort amenity"),
    "amenities/Cold plunge / ice bath": T("amenities", "cold-plunge", "Cold plunge / ice bath", ["ice bath"]),
    "amenities/Gluten-free": T("amenities", "gluten-free", "Gluten-free options", ["gluten free"], note="dietary -> amenities (D15); merges the cuisine/Gluten-free candidate"),
    "amenities/Cigar lounge": T("amenities", "cigar-lounge", "Cigar lounge", ["cigar"]),
    "amenities/Wine cellar": T("amenities", "wine-cellar", "Wine cellar"),
    "amenities/Sports screening": T("amenities", "sports-screening", "Sports screening", ["big screen", "live sports"]),
    # ---- audience -------------------------------------------------------------
    "audience/Women": T("audience", "women", "Women", ["female travellers", "ladies"], note="lexical count inflated by generic 'women'; 48 title hits support a segment"),
    "audience/Students": T("audience", "students", "Students", ["teenagers", "university students"]),
    "audience/Foodies": T("audience", "foodies", "Foodies", ["foodie"]),
    "audience/Seniors": T("audience", "seniors", "Seniors", ["elderly", "retirees", "retirement"], note="merges the Retiree candidate (20)"),
    "audience/Surfers": T("audience", "surfers", "Surfers"),
    "audience/Divers": T("audience", "divers", "Divers"),
    "audience/Yogis": T("audience", "yogis", "Yogis", ["yogi"]),
    "audience/Digital nomad": T("audience", "digital-nomads", "Digital nomads", ["digital nomad", "remote workers"]),
    "audience/Backpacker": T("audience", "backpackers", "Backpackers", ["backpacker", "budget travellers"]),
    "audience/Retiree": MERGE("audience/Seniors"),
    # ---- cuisine --------------------------------------------------------------
    "cuisine/Coffee": T("cuisine", "coffee", "Coffee", ["kopi", "specialty coffee", "espresso"]),
    "cuisine/Dessert": T("cuisine", "dessert", "Dessert", ["gelato", "ice cream", "pastry", "patisserie"]),
    "cuisine/Organic": T("amenities", "organic", "Organic & farm-to-table", ["organic menu", "farm-to-table", "farm to table"], note="approach term -> amenities (D15); merges Farm-to-table (58)"),
    "cuisine/Fusion": T("cuisine", "fusion", "Fusion", ["fusion cuisine"]),
    "cuisine/Steak": A("cuisine", "steakhouse", ["steak"]),
    "cuisine/Fine dining": A("subtype", "fine-dining", ["degustation", "Michelin", "tasting menu"]),
    "cuisine/Vegetarian": MERGE("amenities/Vegetarian options", note="dietary -> amenities (D15)"),
    "cuisine/BBQ": T("cuisine", "bbq", "BBQ & grill", ["barbecue", "smokehouse", "BBQ"], note="'BBQ' trimmed from cuisine/american"),
    "cuisine/Vegan": A("amenities", "vegan-options", ["vegan"], note="dietary -> amenities (D15)"),
    "cuisine/Burgers": A("cuisine", "american", ["burger"]),
    "cuisine/Teppanyaki": A("cuisine", "japanese", ["teppanyaki"]),
    "cuisine/Acehnese": T("cuisine", "acehnese", "Acehnese", ["Aceh cuisine", "mie Aceh"], note="bare 'Aceh' is the location; not an alias here"),
    "cuisine/Healthy": T("amenities", "healthy-menu", "Healthy menu", ["healthy food", "health food", "clean eating", "superfood"], note="approach term -> amenities (D15)"),
    "cuisine/Bakery": A("subtype", "bakery", ["sourdough", "croissant"]),
    "cuisine/Farm-to-table": MERGE("cuisine/Organic"),
    "cuisine/Portuguese": T("cuisine", "portuguese", "Portuguese"),
    "cuisine/Singaporean": T("cuisine", "singaporean", "Singaporean"),
    "cuisine/Hotpot": T("cuisine", "hotpot", "Hotpot", ["hot pot", "shabu-shabu", "steamboat"], note="'hotpot' trimmed from cuisine/chinese"),
    "cuisine/Peruvian": A("cuisine", "latin-american", ["Nikkei"]),
    "cuisine/Gluten-free": MERGE("amenities/Gluten-free"),
    "cuisine/Nordic": T("cuisine", "nordic", "Nordic", ["Scandinavian"]),
    "cuisine/Moroccan": T("cuisine", "moroccan", "Moroccan"),
    "cuisine/Malaysian": T("cuisine", "malaysian", "Malaysian"),
    "cuisine/Sichuan": A("cuisine", "chinese", ["Szechuan"]),
    "cuisine/Tea": T("cuisine", "tea", "Tea", ["tea house", "teahouse", "artisan tea"], note="the venue_kind Tea house candidate (24) goes to eat/cafe's alias set"),
    # ---- location: Bali -------------------------------------------------------
    "location_bali/Tabanan": T("location", "tabanan", "Tabanan", [], parent="west-bali", geo=_geo(-8.5411, 115.1256)),
    "location_bali/Kintamani": T("location", "kintamani", "Kintamani & Mount Batur", ["Mount Batur", "Batur", "Lake Batur"], parent="north-bali", geo=_geo(-8.2500, 115.3500), note="Bangli-regency highlands, grouped with the north for readers"),
    "location_bali/Gianyar": T("location", "gianyar", "Gianyar", ["Sukawati", "Celuk", "Batubulan", "Keliki", "Tampaksiring"], parent="central-bali", geo=_geo(-8.5446, 115.3263), note="the regency's towns outside Ubud; central-bali keeps 'Gianyar' as its own alias"),
    "location_bali/Karangasem": A("location", "east-bali", ["Amlapura", "Tirta Gangga", "Tenganan", "Besakih", "Padang Bai", "Padangbai"], note="'Karangasem' is already east-bali's alias -- the regency IS East Bali; its towns become aliases rather than a redundant node"),
    "location_bali/West Bali": T("location", "west-bali", "West Bali", ["Menjangan", "Pemuteran", "Jembrana", "Negara", "Gilimanuk", "Perancak"], parent="bali", geo=_geo(-8.3600, 114.6300), note="new district -- Section 4 has no West Bali node; parent of tabanan, tanah-lot, jatiluwih"),
    "location_bali/Bedugul": T("location", "bedugul", "Bedugul & Lake Bratan", ["Bratan", "Beratan", "Lake Bratan"], parent="north-bali", geo=_geo(-8.2750, 115.1650), note="highlands next to Munduk (a north-bali alias)"),
    "location_bali/Bangli": T("location", "bangli", "Bangli & Penglipuran", ["Penglipuran"], parent="central-bali", geo=_geo(-8.4540, 115.3540)),
    "location_bali/Nusa Lembongan": T("location", "nusa-lembongan", "Nusa Lembongan", ["Lembongan", "Ceningan", "Nusa Ceningan"], parent="east-bali", geo=_geo(-8.6800, 115.4500), note="sibling of nusa-penida; 'Nusa Lembongan' / 'Nusa Ceningan' trimmed from nusa-penida"),
    "location_bali/Mengwi": T("location", "mengwi", "Mengwi", ["Taman Ayun"], parent="south-bali", geo=_geo(-8.5430, 115.1700)),
    "location_bali/Tanah Lot": T("location", "tanah-lot", "Tanah Lot", [], parent="west-bali", geo=_geo(-8.6212, 115.0868)),
    "location_bali/Jatiluwih": T("location", "jatiluwih", "Jatiluwih", [], parent="west-bali", geo=_geo(-8.3700, 115.1300)),
    "location_bali/Kedonganan": A("location", "jimbaran", ["Kedonganan"], note="adjacent beach on the same bay"),
    "location_bali/Sanur / Ketewel": A("location", "gianyar", ["Ketewel", "Saba"], note="Gianyar coast, not Sanur (the lexicon label was wrong)"),
    "location_bali/Serangan": A("location", "sanur", ["Serangan"], note="island off Sanur"),
    # ---- location: elsewhere in Indonesia (flat leaves under `other`) ----------
    "location_elsewhere/Java (general)": T("location", "java", "Java", ["Central Java", "East Java", "West Java"], parent="other", geo=_geo(-7.5000, 110.0000), note="region node; re-parenting other/* cities under this and the other region nodes below is APPROVED (Hansel, follow-up #4, 2026-09-10; parent_id only) -- see resolutions.RULES['location']['reparenting']. Applied by the seed ticket, not by this delta."),
    "location_elsewhere/Sumatra (general)": T("location", "sumatra", "Sumatra", [], parent="other", geo=_geo(-0.5000, 101.5000), note="region node"),
    "location_elsewhere/Sulawesi": T("location", "sulawesi", "Sulawesi", ["Wakatobi", "Togean"], parent="other", geo=_geo(-2.0000, 121.0000), note="region node"),
    "location_elsewhere/Kalimantan": T("location", "kalimantan", "Kalimantan", ["Borneo", "Derawan", "Tanjung Puting"], parent="other", geo=_geo(0.0000, 114.0000), note="region node"),
    "location_elsewhere/Nusa Tenggara": T("location", "nusa-tenggara", "Nusa Tenggara", ["NTT", "Sumbawa", "Alor", "Kupang", "Ende", "Kelimutu"], parent="other", geo=_geo(-8.7000, 120.0000), note="region node; lombok, komodo and sumba stay their own leaves"),
    "location_elsewhere/Maluku": T("location", "maluku", "Maluku", ["Moluccas", "Banda", "Ambon", "Ternate", "Seram"], parent="other", geo=_geo(-3.2000, 128.5000), note="region node"),
    "location_elsewhere/Aceh": T("location", "aceh", "Aceh", ["Banda Aceh", "Weh", "Pulau Weh"], parent="other", geo=_geo(5.5483, 95.3238)),
    "location_elsewhere/Riau Islands": T("location", "riau-islands", "Riau Islands", ["Batam", "Riau"], parent="other", geo=_geo(1.1000, 104.0000), note="bintan stays its own leaf"),
    "location_elsewhere/Palembang": T("location", "palembang", "Palembang", [], parent="other", geo=_geo(-2.9909, 104.7566)),
    "location_elsewhere/Padang": T("location", "padang", "Padang", ["Bukittinggi", "West Sumatra"], parent="other", geo=_geo(-0.9471, 100.4172), note="homonym with cuisine/padang -- see match hint"),
    "location_elsewhere/Lampung": T("location", "lampung", "Lampung", ["Krakatau", "Krakatoa", "Way Kambas"], parent="other", geo=_geo(-5.4292, 105.2610)),
    "location_elsewhere/Cirebon": T("location", "cirebon", "Cirebon", [], parent="other", geo=_geo(-6.7320, 108.5523)),
    # ---- location: international (children of `international`; inherit geo_scope=abroad) ----
    "location_international/Europe": T("location", "europe", "Europe", ["Paris", "London", "Amsterdam", "Rome", "Italy", "France", "Switzerland", "Germany", "Spain", "Portugal", "Vienna", "Prague"], parent="international", geo=_geo(48.8566, 2.3522), note="region node; a country splits out once it reaches >= 20 on its own"),
    "location_international/Australia": T("location", "australia", "Australia", ["Sydney", "Melbourne", "Perth", "Brisbane"], parent="international", geo=_geo(-33.8688, 151.2093)),
    "location_international/Singapore": T("location", "singapore", "Singapore", [], parent="international", geo=_geo(1.3521, 103.8198)),
    "location_international/Tokyo": T("location", "japan", "Japan", ["Tokyo", "Kyoto", "Osaka", "Hokkaido"], parent="international", geo=_geo(35.6762, 139.6503), note="lexicon label 'Tokyo' relabelled to the country"),
    "location_international/USA": T("location", "usa", "United States", ["New York", "Los Angeles", "San Francisco", "Las Vegas", "Hawaii", "USA"], parent="international", geo=_geo(40.7128, -74.0060)),
    "location_international/China": T("location", "china", "China", ["Shanghai", "Beijing", "Macau"], parent="international", geo=_geo(31.2304, 121.4737)),
    "location_international/Bangkok": T("location", "thailand", "Thailand", ["Bangkok", "Phuket", "Chiang Mai", "Koh Samui"], parent="international", geo=_geo(13.7563, 100.5018), note="lexicon label 'Bangkok' relabelled to the country"),
    "location_international/India": T("location", "india", "India", ["Mumbai", "Delhi", "Kerala", "Rajasthan"], parent="international", geo=_geo(19.0760, 72.8777)),
    "location_international/Kuala Lumpur": T("location", "malaysia", "Malaysia", ["Kuala Lumpur", "Penang", "Langkawi"], parent="international", geo=_geo(3.1390, 101.6869), note="lexicon label 'Kuala Lumpur' relabelled to the country"),
    "location_international/Hong Kong": T("location", "hong-kong", "Hong Kong", [], parent="international", geo=_geo(22.3193, 114.1694)),
    "location_international/Africa": T("location", "africa", "Africa", ["Kenya", "Tanzania", "Cape Town", "Morocco", "Marrakech", "Egypt"], parent="international", geo=_geo(-1.2921, 36.8219), note="region node"),
    "location_international/Turkey": T("location", "turkey", "Turkey", ["Istanbul", "Cappadocia"], parent="international", geo=_geo(41.0082, 28.9784)),
    "location_international/Seoul": T("location", "south-korea", "South Korea", ["Seoul", "Korea", "Jeju"], parent="international", geo=_geo(37.5665, 126.9780), note="lexicon label 'Seoul' relabelled to the country"),
    "location_international/New Zealand": T("location", "new-zealand", "New Zealand", ["Auckland", "Queenstown"], parent="international", geo=_geo(-36.8485, 174.7633)),
    "location_international/Vietnam": T("location", "vietnam", "Vietnam", ["Hanoi", "Ho Chi Minh", "Da Nang", "Hoi An"], parent="international", geo=_geo(21.0285, 105.8542)),
    "location_international/Philippines": T("location", "philippines", "Philippines", ["Manila", "Cebu", "Palawan"], parent="international", geo=_geo(14.5995, 120.9842)),
    "location_international/Dubai": T("location", "uae", "United Arab Emirates", ["Dubai", "Abu Dhabi", "UAE"], parent="international", geo=_geo(25.2048, 55.2708), note="lexicon label 'Dubai' relabelled to the country"),
    "location_international/Middle East": T("location", "middle-east", "Middle East", ["Qatar", "Doha", "Oman", "Jordan"], parent="international", geo=_geo(25.2854, 51.5310), note="region node for the Gulf and Levant outside the UAE and Turkey"),
    "location_international/Cambodia / Laos": T("location", "cambodia", "Cambodia", ["Siem Reap", "Angkor", "Laos", "Luang Prabang"], parent="international", geo=_geo(13.3671, 103.8448), note="Laos rides along as an alias until it reaches >= 20 on its own (joint count 47)"),
    "location_international/Taiwan": T("location", "taiwan", "Taiwan", ["Taipei"], parent="international", geo=_geo(25.0330, 121.5654)),
    "location_international/Maldives": T("location", "maldives", "Maldives", [], parent="international", geo=_geo(4.1755, 73.5093)),
    "location_international/Sri Lanka": T("location", "sri-lanka", "Sri Lanka", ["Colombo"], parent="international", geo=_geo(6.9271, 79.8612)),
    # ---- location: Jakarta ----------------------------------------------------
    "location_jakarta/Kebayoran Baru": T("location", "kebayoran-baru", "Kebayoran Baru", ["Kebayoran"], parent="south-jakarta", geo=_geo(-6.2437, 106.7995), note="'Kebayoran Baru' trimmed from gunawarman (a strip inside the district)"),
    "location_jakarta/Cilandak": T("location", "cilandak", "Cilandak", ["TB Simatupang", "Simatupang"], parent="south-jakarta", geo=_geo(-6.2914, 106.8006)),
    "location_jakarta/Kemayoran": T("location", "kemayoran", "Kemayoran", ["JIExpo"], parent="central-jakarta", geo=_geo(-6.1626, 106.8500)),
    "location_jakarta/Gatot Subroto": T("location", "gatot-subroto", "Gatot Subroto", ["Jalan Gatot Subroto", "Semanggi"], parent="south-jakarta", geo=_geo(-6.2297, 106.8175)),
    "location_jakarta/Tanah Abang": T("location", "tanah-abang", "Tanah Abang", [], parent="central-jakarta", geo=_geo(-6.1868, 106.8118)),
    "location_jakarta/Casablanca": T("location", "casablanca", "Casablanca", ["Kota Kasablanka", "Casablanca Raya"], parent="south-jakarta", geo=_geo(-6.2238, 106.8433)),
    "location_jakarta/Kebon Sirih": T("location", "kebon-sirih", "Kebon Sirih & Sabang", ["Sabang", "Jalan Sabang"], parent="central-jakarta", geo=_geo(-6.1836, 106.8280)),
    "location_jakarta/Cengkareng": T("location", "cengkareng", "Cengkareng", ["Soekarno-Hatta", "CGK"], parent="west-jakarta", geo=_geo(-6.1479, 106.7383)),
    "location_jakarta/Kepulauan Seribu": T("location", "kepulauan-seribu", "Kepulauan Seribu", ["Thousand Islands", "Pulau Seribu"], parent="north-jakarta", geo=_geo(-5.7500, 106.5500), note="its own regency administratively; filed under north-jakarta for readers"),
    "location_jakarta/Antasari": A("location", "cipete", ["Antasari", "Pangeran Antasari"], note="parallel to Fatmawati, already a cipete alias"),
    "location_jakarta/TMII": T("location", "tmii", "TMII / Taman Mini", ["Taman Mini", "Taman Mini Indonesia Indah"], parent="east-jakarta", geo=_geo(-6.3024, 106.8952)),
    # ---- occasion -------------------------------------------------------------
    "occasion/Festive": T("occasion", "festive", "Festive season", ["Christmas", "New Year", "New Year's Eve", "festive season", "year-end", "Thanksgiving"]),
    "occasion/Business": A("occasion", "business-trip", ["business dinner", "team building", "team-building", "MICE"], note="the label duplicates business-trip, so an alias set, not a term; 'client' and 'meeting' inflate and are not added"),
    "occasion/Wedding": T("occasion", "wedding", "Wedding", ["weddings", "honeymoon", "proposal", "bridal", "bachelorette", "hen party"], note="D22"),
    "occasion/Ramadan": T("occasion", "ramadan", "Ramadan & Eid", ["iftar", "buka puasa", "Lebaran", "Eid"]),
    "occasion/Nyepi / Galungan": T("occasion", "balinese-holy-days", "Balinese holy days", ["Nyepi", "Galungan", "Kuningan", "Saraswati", "Pagerwesi"], note="'Kuningan' here is the holy day -- the location/kuningan hint points Bali text at this term"),
    "occasion/Independence Day": T("occasion", "independence-day", "Independence Day", ["17 August", "Hari Merdeka"]),
    "occasion/Lunar New Year": T("occasion", "lunar-new-year", "Lunar New Year", ["Chinese New Year", "Imlek"]),
    "occasion/Road trip": T("occasion", "road-trip", "Road trip", ["island hopping"], note="'itinerary' inflates; not an alias"),
    "occasion/Group": A("occasion", "group-gathering", ["large group", "group booking", "group of friends"]),
    "occasion/Halloween": T("occasion", "halloween", "Halloween"),
    # ---- topic ----------------------------------------------------------------
    "topic/Food & drink": T("topic", "food-drink", "Food & drink", ["culinary", "gastronomy", "recipe", "recipes", "cooking"], note="'chef', 'wine', 'coffee', 'cocktail' inflate; not aliases"),
    "topic/Weddings & romance": T("topic", "weddings", "Weddings & romance", ["wedding", "weddings", "bridal", "honeymoon", "romance"], note="merges the Weddings topic candidate (170); 'love' inflates and is not an alias"),
    "topic/Religion & spirituality": T("topic", "religion-spirituality", "Religion & spirituality", ["Hindu", "Hinduism", "Islam", "Buddhism", "spirituality", "spiritual"], note="'church' / 'mosque' belong to do/place-of-worship"),
    "topic/Coffee culture": T("topic", "coffee-culture", "Coffee culture", ["barista", "roastery", "specialty coffee"]),
    "topic/Urban issues": T("topic", "urban-issues", "Urban issues", ["flooding", "pollution", "air quality", "city planning", "congestion"], note="governor names dropped from the aliases"),
    "topic/Agriculture & food systems": T("topic", "agriculture", "Agriculture & food systems", ["farmers", "farming", "fishermen", "seaweed farming", "permaculture"]),
    "topic/Covid-19": T("topic", "covid-19", "Covid-19", ["Covid", "pandemic", "lockdown", "PSBB", "PPKM", "new normal"]),
    "topic/Pets & animals": T("topic", "pets-animals", "Pets & animals", ["dogs", "cats", "animal welfare", "wildlife", "sea turtles"]),
    "topic/Craft spirits": T("topic", "craft-spirits", "Craft spirits & brewing", ["arak", "gin", "rum", "craft beer", "distillery"], note="'winery' / 'vineyard' belong to drink/winery-distillery"),
    "topic/Spa & beauty": T("topic", "spa-beauty", "Spa & beauty", ["facial", "skincare", "beauty"]),
    "topic/Weddings": MERGE("topic/Weddings & romance"),
    "topic/History of tourism": T("topic", "tourism", "Tourism", ["mass tourism", "overtourism", "tourism history"]),
    # ---- venue_kind -> subtype -------------------------------------------------
    "venue_kind/Temple": T("subtype", "temple", "Temple", ["temples", "pura", "klenteng", "Chinese temple"], parent="do", note="Bali's most-mentioned venue kind (553); a place to visit, hence `do`"),
    "venue_kind/Coffee shop": A("subtype", "cafe", ["café", "coffee shop", "roastery", "kopi"]),
    "venue_kind/Bookshop": T("subtype", "bookshop", "Bookshop", ["bookstore", "book shop", "library"], parent="shop", note="libraries ride along: not a shop, but the only node close to one"),
    "venue_kind/Gelato / dessert": T("subtype", "dessert-shop", "Dessert shop", ["gelato", "gelateria", "ice cream parlour", "dessert bar", "patisserie"], parent="eat"),
    "venue_kind/Palace": A("subtype", "attraction", ["palace", "water palace", "puri"]),
    "venue_kind/Farm": T("subtype", "farm", "Farm & plantation", ["organic farm", "plantation", "coffee plantation", "agritourism"], parent="do"),
    "venue_kind/Zoo / safari": T("subtype", "zoo", "Zoo & safari park", ["safari", "bird park", "butterfly park", "elephant park", "aquarium"], parent="do"),
    "venue_kind/Surfing": A("subtype", "watersports", ["surf", "surfing", "surf school", "surf camp"]),
    "venue_kind/Church / mosque": T("subtype", "place-of-worship", "Church & mosque", ["church", "cathedral", "mosque", "masjid"], parent="do", note="temples have their own node"),
    "venue_kind/Theatre / concert hall": T("subtype", "theatre", "Theatre & concert hall", ["theater", "concert hall", "performing arts centre", "Ciputra Artpreneur", "Salihara", "Aula Simfonia"], parent="do", note="the venue; event/performance is the dated show"),
    "venue_kind/Volcano": A("subtype", "adventure", ["volcano", "Mount Batur", "Mount Agung", "sunrise trek"]),
    "venue_kind/Waterfall": T("subtype", "nature", "Nature spot", ["waterfall", "waterfalls", "lake", "hot spring", "hot springs", "mangrove", "national park", "rice terrace", "rice terraces", "viewpoint"], parent="do", note="merges Rice terrace (71) and Hot spring (28): the missing 'outdoor place to go' node Bali's Nature and Outdoors category needed"),
    "venue_kind/Convention centre": A("subtype", "conference", ["convention centre", "convention center", "exhibition hall", "JCC", "ICE BSD", "JIExpo"]),
    "venue_kind/Stadium": A("subtype", "sports", ["stadium", "arena"]),
    "venue_kind/Winery": T("subtype", "winery-distillery", "Winery & distillery", ["winery", "vineyard", "distillery", "brewery", "taproom", "cellar door"], parent="drink", note="merges Distillery (39); Brewery / taproom (12) is below threshold and rides along as an alias"),
    "venue_kind/Rice terrace": MERGE("venue_kind/Waterfall"),
    "venue_kind/Cooking class": A("subtype", "workshop", ["cooking class", "cooking classes", "culinary class"]),
    "venue_kind/Trekking / hiking": A("subtype", "adventure", ["trek", "trekking", "hiking"]),
    "venue_kind/Golf course": A("subtype", "sports-activity", ["golf course", "golf club", "driving range"]),
    "venue_kind/Billiards / bowling": A("subtype", "sports-activity", ["billiards", "pool hall", "arcade", "trampoline park", "escape room"]),
    "venue_kind/Yoga studio": A("subtype", "yoga", ["yoga studio", "yoga shala", "shala", "yoga barn"]),
    "venue_kind/Cycling": A("subtype", "tour", ["bike tour", "cycling tour", "bicycle tour"]),
    "venue_kind/Karaoke": T("subtype", "karaoke", "Karaoke", ["KTV", "karaoke bar"], parent="drink"),
    "venue_kind/Retreat centre": A("subtype", "retreat", ["retreat centre", "retreat center", "healing centre", "wellness centre", "wellness center"]),
    "venue_kind/School": A("subtype", "education", ["school", "kindergarten", "preschool", "international school"]),
    "venue_kind/Snorkelling / diving": A("subtype", "watersports", ["snorkelling", "snorkeling", "scuba", "diving", "freediving"]),
    "venue_kind/ATV / buggy": A("subtype", "adventure", ["ATV", "quad bike", "buggy"]),
    "venue_kind/Co-working": SKIP("a co-working space has no venue-type node; covered by the alias set added to amenities/coworking-space"),
    "venue_kind/Distillery": MERGE("venue_kind/Winery"),
    "venue_kind/Waterpark": A("subtype", "attraction", ["waterpark", "water park"]),
    "venue_kind/Kitesurfing / sailing": A("subtype", "watersports", ["kitesurfing", "kitesurf", "sailing", "catamaran", "yacht"]),
    "venue_kind/Barbershop": A("subtype", "salon", ["barber"]),
    "venue_kind/Horse riding": A("subtype", "adventure", ["horse riding", "horseback riding"]),
    "venue_kind/Warung": A("subtype", "street-food", ["warung", "warungs"]),
    "venue_kind/Cruise": A("subtype", "tour", ["sunset cruise", "dinner cruise", "liveaboard", "phinisi"]),
    "venue_kind/Helicopter / balloon": A("subtype", "adventure", ["helicopter tour", "hot air balloon"]),
    "venue_kind/Nail bar": A("subtype", "salon", ["nail salon", "manicure"]),
    "venue_kind/Hot spring": MERGE("venue_kind/Waterfall"),
    "venue_kind/Cinema": T("subtype", "cinema", "Cinema", ["movie theatre", "movie theater", "XXI", "CGV"], parent="do", note="the venue; event/screening is the dated showing"),
    "venue_kind/Rafting": A("subtype", "adventure", ["rafting", "white water rafting"]),
    "venue_kind/Tea house": A("subtype", "cafe", ["tea house", "teahouse", "tea room"]),
    # ---- vibe -----------------------------------------------------------------
    "vibe/Tropical": T("vibe", "tropical", "Tropical", ["island-style", "resort-style"], note="bare 'island' inflates; not an alias"),
    "vibe/Authentic": T("vibe", "authentic", "Authentic", ["traditional"]),
    "vibe/Modern": T("vibe", "modern", "Modern", ["contemporary", "minimalist", "industrial", "sleek"], note="'contemporary' also matches contemporary art -- 114 title hits still support it"),
    "vibe/Exclusive": T("vibe", "exclusive", "Exclusive", ["members-only", "VIP"], note="'private' inflates; not an alias"),
    "vibe/Chic": T("vibe", "chic", "Chic", ["stylish", "elegant", "sophisticated", "refined"]),
    "vibe/Wholesome": T("vibe", "wholesome", "Wholesome", ["mindful", "conscious"], note="'healthy' belongs to amenities/healthy-menu"),
    "vibe/Glamorous": T("vibe", "glamorous", "Glamorous", ["glam", "lavish", "decadent", "indulgent"]),
    "vibe/Quirky": T("vibe", "quirky", "Quirky", ["whimsical", "eclectic", "playful"]),
    "vibe/Cool": T("vibe", "edgy", "Edgy", ["underground", "alternative", "cool"], note="relabelled from 'Cool' -- the bare word is a homonym; kept as an alias for the prompt"),
    "vibe/Rustic": T("vibe", "rustic", "Rustic", ["earthy"], note="'raw' inflates; not an alias"),
    "vibe/Nostalgic": T("vibe", "nostalgic", "Nostalgic", ["retro", "vintage", "colonial charm"]),
    "vibe/Family-friendly": T("vibe", "family-friendly", "Family-friendly", ["kid-friendly"], note="overlaps audience/family and amenities/kids-club by design: a vibe of the place, not who it is for"),
}


class DeltaError(ValueError):
    """The curated table and the corpus scan disagree -- fix the table, never the scan."""


def _mentions(row: dict) -> dict:
    return {"total": row["total"], "jakarta": row["hits"].get("jakarta", 0), "bali": row["hits"].get("bali", 0), "titles": sum(row["title_hits"].values())}


def _requires_migration(facet: str) -> bool:
    return facet in PAYLOAD_ENUMS


def build_delta(vocab: dict, seed: dict) -> dict:
    """Assemble the delta from the corpus scan + the seed. Raises DeltaError on
    an unmapped candidate, a stale key, a slug collision or a dangling alias
    target, so a change in the lexicon or the seed cannot silently produce an
    incomplete delta."""
    cands = {r["key"]: r for r in vocab["candidates"]}
    all_cands = {r["key"]: r for r in vocab.get("_all_candidates", [])} or cands
    seed_rows = {r["key"]: r for r in vocab["seed_terms"]}
    seed_slugs: dict[str, set[str]] = {}
    seed_labels: dict[str, dict[str, str]] = {}
    for facet, terms in seed["terms"].items():
        seed_slugs[facet] = {t["slug"] for t in terms}
        seed_labels[facet] = {t["label"].lower(): t["slug"] for t in terms}
        seed_labels[facet].update({t["slug"].lower(): t["slug"] for t in terms})

    above = {k: r for k, r in cands.items() if r["total"] >= THRESHOLD}
    unmapped = sorted(set(above) - set(CANDIDATE_ACTIONS))
    stale = sorted(set(CANDIDATE_ACTIONS) - set(all_cands))
    if unmapped:
        raise DeltaError(f"candidates at or above {THRESHOLD} mentions with no curated action: {unmapped}")
    if stale:
        raise DeltaError(f"curated actions whose candidate no longer exists in the scan: {stale}")

    add_terms: dict[tuple[str, str], dict] = {}
    add_aliases: dict[tuple[str, str], dict] = {}
    merged: list[dict] = []
    skipped: list[dict] = []
    below = [{"candidate": k, "facet": r["facet"], "label": r["label"], "mentions": _mentions(r)} for k, r in sorted(cands.items(), key=lambda kv: -kv[1]["total"]) if r["total"] < THRESHOLD]

    def merge_target_key(key: str) -> str:
        seen = []
        while CANDIDATE_ACTIONS[key]["action"] == "merge":
            seen.append(key)
            key = CANDIDATE_ACTIONS[key]["into"]
            if key in seen:
                raise DeltaError(f"merge cycle at {key}")
            if key not in CANDIDATE_ACTIONS:
                raise DeltaError(f"merge target {key!r} has no action")
        return key

    # first pass: terms and aliases
    for key, act in CANDIDATE_ACTIONS.items():
        row = all_cands[key]
        if row["total"] < THRESHOLD and act["action"] != "skip":
            # a curated entry below threshold is allowed only as documentation; it never adds anything
            skipped.append({"candidate": key, "mentions": _mentions(row), "reason": f"below the {THRESHOLD}-mention threshold (curated entry kept for the record)"})
            continue
        if act["action"] == "add_term":
            facet, slug = act["facet"], act["slug"]
            if slug in seed_slugs.get(facet, set()):
                raise DeltaError(f"{key}: add_term {facet}/{slug} collides with an existing seed slug")
            if (facet, slug) in add_terms:
                raise DeltaError(f"{key}: add_term {facet}/{slug} duplicated within the delta")
            entry = {
                "facet": facet, "slug": slug, "label": act["label"], "parent": act["parent"], "aliases": list(act["aliases"]), "geo": act["geo"],
                "from_candidate": key, "mentions": _mentions(row), "merged_from": [],
                "requires_migration": _requires_migration(facet), "payload_enum": PAYLOAD_ENUMS.get(facet),
                "attrs": ({"inherits_from": act["parent"], **TERM_ATTRS[("location", "international")]} if act["parent"] == "international" else None),
                "note": act["note"],
            }
            add_terms[(facet, slug)] = entry
        elif act["action"] == "add_alias":
            facet, slug = act["facet"], act["slug"]
            tgt = add_aliases.setdefault((facet, slug), {"facet": facet, "slug": slug, "aliases": [], "from_candidates": [], "mentions": [], "requires_migration": False, "note": ""})
            for a in act["aliases"]:
                if a not in tgt["aliases"]:
                    tgt["aliases"].append(a)
            tgt["from_candidates"].append(key)
            tgt["mentions"].append({"candidate": key, **_mentions(row)})
            if act["note"]:
                tgt["note"] = (tgt["note"] + " | " + act["note"]).strip(" |")
        elif act["action"] == "skip":
            skipped.append({"candidate": key, "mentions": _mentions(row), "reason": act["reason"]})

    # second pass: merges (need the targets to exist)
    for key, act in CANDIDATE_ACTIONS.items():
        if act["action"] != "merge":
            continue
        row = all_cands[key]
        if row["total"] < THRESHOLD:
            continue
        target = merge_target_key(key)
        tact = CANDIDATE_ACTIONS[target]
        if tact["action"] == "add_term":
            add_terms[(tact["facet"], tact["slug"])]["merged_from"].append({"candidate": key, **_mentions(row)})
        elif tact["action"] == "add_alias":
            add_aliases[(tact["facet"], tact["slug"])]["mentions"].append({"candidate": key, **_mentions(row), "merged": True})
        else:
            raise DeltaError(f"{key}: merge target {target} is a {tact['action']}, not a term or alias")
        merged.append({"candidate": key, "into": target, "mentions": _mentions(row), "note": act.get("note", "")})

    # alias suggestions (surface forms for terms the seed already has)
    alias_sugg_applied: list[dict] = []
    alias_sugg_skipped_forms: list[dict] = []
    for r in vocab.get("alias_suggestions", []):
        if r["total"] < THRESHOLD:
            continue
        fam = FACET_FAMILY.get(r["facet"], r["facet"])
        slug = seed_labels.get(fam, {}).get(r["label"].lower())
        if slug is None:
            raise DeltaError(f"alias suggestion {r['key']} names no seed term in facet {fam}")
        skips = ALIAS_FORM_SKIPS.get((r["facet"], r["label"]), {})
        keep = [f for f in r["forms"] if f not in skips]
        for f, why in skips.items():
            if f in r["forms"]:
                alias_sugg_skipped_forms.append({"facet": fam, "slug": slug, "form": f, "reason": why})
        if not keep:
            continue
        tgt = add_aliases.setdefault((fam, slug), {"facet": fam, "slug": slug, "aliases": [], "from_candidates": [], "mentions": [], "requires_migration": False, "note": ""})
        added = []
        for a in keep:
            if a not in tgt["aliases"]:
                tgt["aliases"].append(a)
                added.append(a)
        tgt["from_candidates"].append(r["key"] + " (alias suggestion)")
        tgt["mentions"].append({"candidate": r["key"], **_mentions(r), "alias_suggestion": True})
        alias_sugg_applied.append({"facet": fam, "slug": slug, "aliases": added, "mentions": _mentions(r)})

    # alias targets must exist (seed or this delta)
    for (facet, slug) in add_aliases:
        if slug not in seed_slugs.get(facet, set()) and (facet, slug) not in add_terms:
            raise DeltaError(f"add_alias target {facet}/{slug} is neither a seed term nor added by this delta")
    # new terms must not re-use a surface form that is another new term's slug-label in the same facet
    for (facet, slug), t in add_terms.items():
        if t["parent"] and facet == "location" and t["parent"] not in seed_slugs["location"] and (facet, t["parent"]) not in add_terms:
            raise DeltaError(f"{facet}/{slug}: parent {t['parent']} does not exist")
        if facet == "subtype" and t["parent"] not in seed_slugs.get("type", set()):
            raise DeltaError(f"subtype/{slug}: parent type {t['parent']} does not exist")

    # approvals: every proposed seed term except the drops
    drop_keys = {(d["facet"], d["slug"]) for d in DROPS}
    approvals = []
    for facet, terms in seed["terms"].items():
        for t in terms:
            if not t.get("proposed") or (facet, t["slug"]) in drop_keys:
                continue
            row = seed_rows.get(f"{facet}/{t['slug']}")
            approvals.append({
                "facet": facet, "slug": t["slug"], "label": t["label"], "parent": t.get("parent"),
                "decision": APPROVAL_DECISION.get((facet, t["slug"]), APPROVAL_DEFAULT_BY_FACET.get(facet, "D16")),
                "mentions": _mentions(row) if row else None,
                "attrs": TERM_ATTRS.get((facet, t["slug"])),
                "requires_migration": False,
                "note": "already seeded as `proposed`; already a value of the Payload enum where one exists -- approval changes documentation only" + (" (kept although below 20 mentions: only rawamangun was named for dropping -- see D14 conflicts)" if row and row["total"] < THRESHOLD else ""),
            })
    approvals.sort(key=lambda a: (a["facet"], -(a["mentions"]["total"] if a["mentions"] else 0)))

    drops = []
    for d in DROPS:
        row = seed_rows.get(f"{d['facet']}/{d['slug']}")
        drops.append({**d, "mentions": _mentions(row) if row else None, "requires_migration": _requires_migration(d["facet"]), "payload_enum": PAYLOAD_ENUMS.get(d["facet"])})

    trims = []
    for t in TRIMS:
        row = seed_rows.get(f"{t['facet']}/{t['slug']}")
        current = list(row["forms"]) if row else []
        trims.append({**t, "current_forms": current, "keep": [f for f in current if f not in t["remove"]], "mentions_before": _mentions(row) if row else None, "requires_migration": False})

    terms_out = sorted(add_terms.values(), key=lambda t: (t["facet"], -t["mentions"]["total"]))
    aliases_out = sorted(add_aliases.values(), key=lambda a: (a["facet"], a["slug"]))
    new_enum_values: dict[str, list[str]] = {}
    for t in terms_out:
        if t["requires_migration"]:
            new_enum_values.setdefault(t["facet"], []).append(t["slug"])

    counts = {
        "approve": len(approvals), "add_term": len(terms_out), "add_alias_sets": len(aliases_out),
        "add_alias_forms": sum(len(a["aliases"]) for a in aliases_out), "merged": len(merged), "skipped": len(skipped),
        "drop_term": len(drops), "trim_alias": len(trims), "match_hints": len(MATCH_HINTS),
        "candidates_at_or_above_threshold": len(above), "candidates_below_threshold": len(below),
        "add_term_by_facet": {f: sum(1 for t in terms_out if t["facet"] == f) for f in sorted({t["facet"] for t in terms_out})},
        "add_term_requiring_migration": sum(1 for t in terms_out if t["requires_migration"]),
    }
    return {
        "version": 1,
        "generated": None,  # filled by the caller (same timestamp as the packs)
        "decided_by": DECIDED_BY, "decided_on": DECIDED_ON,
        "decisions": ["D03", "D04", "D05", "D06", "D11", "D12", "D13", "D14", "D15", "D16", "D22"],
        "rule": {
            "add_threshold_mentions": THRESHOLD,
            "method": vocab.get("method"),
            "articles_scanned": vocab.get("articles_scanned"),
            "below_threshold": "stays out",
            "curation": "venue kinds become aliases of an existing subtype when one means the same thing, else a new subtype with an explicit L1 parent (exclusion is L1-only, so no competitor-exclusion change); dietary/approach terms go to amenities (D15); international destinations are named at country/region level with cities as aliases; duplicates merged",
            "source_of_truth": "engine/packages/taxonomy-evidence/src/now_taxonomy_evidence/vocabulary_delta.py (CANDIDATE_ACTIONS); counts from vocabulary.analyse_vocabulary",
            "seed_untouched": "engine/packages/taxonomy/seed/ is NOT modified by this package; the seed ticket applies this file",
        },
        "counts": counts,
        "approve": approvals,
        "add_term": terms_out,
        "add_alias": aliases_out,
        "alias_forms_not_added": alias_sugg_skipped_forms,
        "merged": merged,
        "skipped": skipped,
        "drop_term": drops,
        "trim_alias": trims,
        "match_hints": MATCH_HINTS,
        "below_threshold": below,
        "migration": {
            "f20": "Adding a TERM to a facet that is a Payload ENUM needs `migrate:create` + `migrate` on every city DB and a restart of every cms-<city>. Aliases, attrs, match hints and approvals of already-seeded proposed terms need no migration (aliases are not persisted; proposed terms are already enum values).",
            "payload_enums": PAYLOAD_ENUMS,
            "platform_only_facets": list(PLATFORM_ONLY_FACETS),
            "new_enum_values": new_enum_values,
            "drop_note": drops[0]["migration_note"] if drops else None,
            "attrs_note": "`attrs` (geo_scope on location/international) has no column yet: engine.terms.attrs jsonb is the taxonomy README's proposed DDL #1 -- an additive platform-DB migration; until it lands the attribute lives in the seed file as documentation and the rails read the international subtree by parent.",
            "sequence": [
                "1. edit engine/packages/taxonomy/seed/terms/*.json per this file (approve = drop the `proposed` flag; add_term/add_alias/trim as listed; delete rawamangun)",
                "2. `now-db migrate --all` -- upserts platform engine.terms (type_relations untouched: no L1 change; format_decay untouched: opinion already listed)",
                "3. Payload `migrate:create` + `migrate` on every city DB for the facets in new_enum_values",
                "4. restart every cms-<city>",
                "5. E2.1 reads its enums from the platform DB -- run it after step 2, or accept a second pass for the new terms",
            ],
        },
    }


def render_delta_markdown(delta: dict) -> str:
    L: list[str] = []
    w = L.append
    c = delta["counts"]
    w("# Vocabulary delta — the seed change the taxonomy review produced")
    w("")
    w(f"**Generated {delta['generated']} from the same scan as the review packs; decided by {delta['decided_by']} on {delta['decided_on']}.** Machine twin: `vocabulary-delta.json` (same model). "
      "This file is *input to the seed ticket* (F20): nothing here has been written to `engine/packages/taxonomy/seed/`.")
    w("")
    w(f"Rule: add every corpus term with ≥ {delta['rule']['add_threshold_mentions']} mentions (distinct articles, title+body, both cities); below that stays out. "
      f"{c['candidates_at_or_above_threshold']} candidates qualified, {c['candidates_below_threshold']} did not. Decisions: {', '.join(delta['decisions'])}.")
    w("")
    w("| action | count |\n|---|---:|")
    for k in ("approve", "add_term", "add_alias_sets", "add_alias_forms", "merged", "skipped", "drop_term", "trim_alias", "match_hints"):
        w(f"| {k} | {c[k]} |")
    w(f"| add_term requiring a Payload ENUM migration (F20) | {c['add_term_requiring_migration']} |")
    w("")
    w("New terms by facet: " + ", ".join(f"{f} {n}" for f, n in c["add_term_by_facet"].items()) + ".")
    w("")
    w("## 1. Approve (already seeded as `proposed`; documentation change only)")
    w("")
    w("| facet | slug | label | parent | decision | mentions (j / b / titles) | note |\n|---|---|---|---|---|---|---|")
    for a in delta["approve"]:
        m = a["mentions"]
        ms = f"{m['total']} ({m['jakarta']} / {m['bali']} / {m['titles']})" if m else "-"
        w(f"| {a['facet']} | `{a['slug']}` | {a['label']} | {a['parent'] or '-'} | {a['decision']} | {ms} | {(a.get('attrs') and ('attrs ' + str(a['attrs']) + '; ') or '')}{a['note'] if 'kept although' in a['note'] else ''} |")
    w("")
    w("## 2. Add terms")
    w("")
    w("| facet | slug | label | parent | aliases | mentions (j / b / titles) | merged from | migration | note |\n|---|---|---|---|---|---|---|---|---|")
    for t in delta["add_term"]:
        m = t["mentions"]
        mf = "; ".join(f"{x['candidate']} {x['total']}" for x in t["merged_from"]) or "-"
        w(f"| {t['facet']} | `{t['slug']}` | {t['label']} | {t['parent'] or '-'} | {', '.join(t['aliases']) or '-'} | {m['total']} ({m['jakarta']} / {m['bali']} / {m['titles']}) | {mf} | {t['payload_enum'] if t['requires_migration'] else 'platform only'} | {t['note'].replace('|', '/')} |")
    w("")
    w("## 3. Add aliases to existing terms (no migration — aliases are not persisted)")
    w("")
    w("| facet | slug | aliases added | evidence (candidate: mentions) | note |\n|---|---|---|---|---|")
    for a in delta["add_alias"]:
        ev = "; ".join(f"{x['candidate']} {x['total']}" for x in a["mentions"])
        w(f"| {a['facet']} | `{a['slug']}` | {', '.join(a['aliases'])} | {ev} | {a['note'].replace('|', '/')} |")
    w("")
    if delta["alias_forms_not_added"]:
        w("Alias-suggestion forms deliberately not added: " + "; ".join(f"`{x['facet']}/{x['slug']}` ← {x['form']} ({x['reason']})" for x in delta["alias_forms_not_added"]) + ".")
        w("")
    w("## 4. Drop terms")
    w("")
    for d in delta["drop_term"]:
        m = d["mentions"]
        w(f"- **{d['facet']}/`{d['slug']}`** — {m['total'] if m else '?'} mentions. {d['reason']} Migration: {d['migration_note']}")
    w("")
    w("## 5. Trim aliases (homonym-inflated)")
    w("")
    w("| facet | slug | remove | keep | reason |\n|---|---|---|---|---|")
    for t in delta["trim_alias"]:
        w(f"| {t['facet']} | `{t['slug']}` | {', '.join(t['remove'])} | {', '.join(t['keep']) or '(label only)'} | {t['reason']} |")
    w("")
    w("## 6. Match hints for the E2.1 prompt (labels that are homonyms)")
    w("")
    for h in delta["match_hints"]:
        w(f"- `{h['facet']}/{h['slug']}` — {h['hint']}")
    w("")
    w("## 7. Merged and skipped candidates (≥ threshold, not added as their own term)")
    w("")
    for m in delta["merged"]:
        w(f"- {m['candidate']} ({m['mentions']['total']}) → merged into {m['into']}{(' — ' + m['note']) if m['note'] else ''}")
    for s in delta["skipped"]:
        w(f"- {s['candidate']} ({s['mentions']['total']}) → skipped: {s['reason']}")
    w("")
    w(f"## 8. Below the threshold ({len(delta['below_threshold'])}) — for the record, not added")
    w("")
    w(", ".join(f"{b['candidate']} {b['mentions']['total']}" for b in delta["below_threshold"]))
    w("")
    w("## 9. Migration (F20)")
    w("")
    mg = delta["migration"]
    w(mg["f20"])
    w("")
    w("New enum values by facet: " + "; ".join(f"**{f}** ({PAYLOAD_ENUMS[f]}): {', '.join(v)}" for f, v in mg["new_enum_values"].items()) + ".")
    w("")
    w("Platform-only facets (no Payload enum, `engine.terms` upsert only): " + ", ".join(mg["platform_only_facets"]) + ".")
    w("")
    w(mg["attrs_note"])
    w("")
    for s in mg["sequence"]:
        w(f"- {s}")
    w("")
    w("---")
    w("*Generated by `now-taxonomy-evidence build`; regenerate rather than hand-edit. Source of truth: `vocabulary_delta.py`.*")
    return "\n".join(L) + "\n"

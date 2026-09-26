"""P1.1 -- junk detection over `public.places.name`.

ITINERARY-AND-READER-PRODUCTS-PLAN.md Sec.9.3 step 1: "fragments by rule
(possessives, generic-lead words, 'at <venue>' event phrases, award/franchise
titles, single dictionary words), plus the extractor's own noise list."

How the rules were built, and how they are measured -- stated plainly
because the two are easy to confuse:

  * `tests/fixtures/junk_hand_labeled_100.jsonl` (Bali, 100 rows) and
    `tests/fixtures/junk_heldout_jakarta_100.jsonl` (Jakarta, 100 rows)
    are the TUNING sets. The first version of this file was written
    against the Bali set alone and scored 25% recall (13/51) on the
    Jakarta set the first time it was run -- it had learned Bali's
    examples, not the shapes. Every rule below is therefore written as a
    SHAPE (a job title followed by "of", a year inside a name, "X and the
    Y", a word cut off mid-way) rather than a literal from either sample.
  * `tests/fixtures/junk_blind_bali_100.jsonl` is the HOLD-OUT: 100 Bali
    rows labelled by hand only after this file stopped changing, measured
    once, and never tuned against. Its number is the honest one; the
    report prints all three.

Precision over recall is the plan's bias ("a doubtful row stays pending"):
a rule that would flag a real venue in either tuning set was narrowed or
dropped, and the remaining misses are listed in the tests rather than
chased with rules specific to one row.

Nothing here writes. `classify()` proposes; `now-places triage --apply` is
the one place `status = junk` is written, and only after a dry run.

Each rule returns EARLY with its own reason, not a combined score -- an
editor reading the triage report (or the desk's badge) should read "why"
in six words. Rules run roughly narrowest-first.

The desk (engine/apps/web) runs a TypeScript port of this module so it can
badge rows without a database column for proposals.
`tests/fixtures/junk_golden.jsonl` pins every fixture verdict and both
test suites assert against it, so the two cannot drift silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from now_place_extraction.extract import is_non_venue_phrase

# ---------------------------------------------------------------- lexicons

# First tokens that mark a description, call to action, date or sentence
# fragment rather than a proper venue name.
_LEADING_FLAG_WORDS = {
    "best", "their", "its", "his", "her", "our", "your", "off", "join",
    "held", "available", "with", "at", "special", "top",
    "shopping", "christmas", "resolution", "located", "in", "inside",
    "near", "nearest", "during", "featuring", "including", "from", "for",
    "via", "when", "where", "while", "since", "visit",
    "enjoy", "discover", "celebrate", "book", "meet", "opening", "opened",
    "launched", "hosted", "presented", "organised", "organized", "curated",
    "designed", "owned", "managed", "powered", "inspired", "introducing",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}
# Real brands that open with a flag word.
_LEADING_FLAG_EXCEPTIONS = ("best western", "new york steakhouse", "top of the")

_MONTH = (
    r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|"
    r"aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)"
)
_MONTH_AT_RE = re.compile(rf"\b{_MONTH}\b.*\bat\b", re.IGNORECASE)

# Event/offer vocabulary strong enough ANYWHERE in the name.
_EVENT_WORD_RE = re.compile(
    r"\b(celebrations?|festivals?|fest|raves?|series|buffets?|brunch(es)?|"
    r"part(y|ies)|gala|workshops?|masterclass(es)?|promos?|promotions?|"
    r"packages?|packag|edition|exhibitions?|concerts?|launch(es)?|"
    r"anniversary|countdown|ramadan|iftar|easter|valentine'?s?|halloween|"
    r"new\s+year'?s?|weekend|holiday|clean\s*up|sound\s+healing|"
    r"tree\s+lighting|fiesta|takeover|pop-?up)\b",
    re.IGNORECASE,
)
# Real names that contain an event word.
_EVENT_WORD_EXCEPTIONS = ("holiday inn", "festival walk", "festival city")

# Substrings that mark an event/description when the name ALSO has an
# " at " phrase -- "Four Seasons Resort Bali at Sayan" is a real hotel and
# must not be flagged on " at " alone.
_EVENT_AT_SUBSTRINGS = (
    "dinner", "lunch", "cocktail", "ceremony", "market", "week", "reserved",
    "seats", "moment", "training", "chef", "sous", "executive", "held",
    "christmas", "drinks", "welcome", "final ", "event ", "indulge",
    "evening", "night out", "session",
    # activities and offers held AT a venue
    "painting", "cooking", "tasting", "making", "carving", "weaving",
    "dancing", "yoga", "class", "workshop", "tour ", "stay ", "treatment",
    "massage", "facial", "feast", "breakfast", "afternoon tea", "pairing",
)

# Competitions, gatherings and public events.
_GATHERING_RE = re.compile(
    r"\b(competitions?|championships?|tournaments?|cook[- ]?off|contests?|"
    r"auctions?|fundraisers?|conferences?|summit|forum|expo|bazaars?|"
    r"screenings?|open\s+house|charity\s+(run|dinner|gala))\b",
    re.IGNORECASE,
)
# "Global Wellness Day", "Earth Day": a name ending in "Day" is a date.
_ENDS_WITH_DAY_RE = re.compile(r"\S\s+day$", re.IGNORECASE)
# Prices and durations belong to offers: "Resort Credit of IDR 600,000",
# "Three Days Bike Retreat", "One Night Stay at X".
_PRICE_RE = re.compile(r"\b(idr|rp|usd|us\$|sgd|aud)\s*[\d.,]+|\$\s*\d", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"\b(one|two|three|four|five|six|seven|\d+)[- ](day|days|night|nights|hour|hours)\b(?!-)",
    re.IGNORECASE,
)
# A clock time: "10pm at the Rooftop", "8am at X".
_TIME_RE = re.compile(r"\b\d{1,2}([.:]\d\d)?\s*(am|pm)\b", re.IGNORECASE)
# Floor/level locators: "Dahana Restaurant Level 2", "Ground Floor".
_LEVEL_RE = re.compile(r"\b(level|lantai|lt\.?|floor)\s*\d+\s*$|\bground\s+floor\b", re.IGNORECASE)
# A job title opening the name: "Bar Manager Herry Kurniawan".
_TITLE_LEAD_RE = re.compile(
    r"^(the\s+)?(bar|general|restaurant|spa|hotel|area|sales|marketing|executive|"
    r"assistant|resident|operations|f&b|food\s+and\s+beverage)\s+"
    r"(manager|director|chef|head|supervisor)\b",
    re.IGNORECASE,
)
# Superlatives right after a possessive: "Bali's Leading Lifestyle Hotel".
_POSSESSIVE_SUPERLATIVE_RE = re.compile(
    r"[’'`]s\s+(leading|best|finest|first|largest|biggest|newest|oldest|only|"
    r"favou?rite|top|most|latest|famous|iconic|premier|number|no\.?)\b",
    re.IGNORECASE,
)

_WEEKDAY_EVENT_RE = re.compile(
    r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b.*\b(market|brunch|session|night|sessions)\b",
    re.IGNORECASE,
)

# A person, not a place: "General Manager of X", "Executive Chef of X",
# "Chef X at Y".
_PERSON_TITLE_RE = re.compile(
    r"\b(general\s+manager|residence\s+manager|hotel\s+manager|manager|director|"
    r"executive\s+chef|head\s+chef|pastry\s+chef|sous\s+chef|chef|founder|"
    r"co-?founder|owner|ceo|sommelier|bartender|mixologist|curator)\s+(of|at)\b",
    re.IGNORECASE,
)
_PERSON_TITLE_LEAD_RE = re.compile(
    r"^(executive\s+)?(sous\s+|head\s+|pastry\s+)?chef\b", re.IGNORECASE
)

_AWARD_RE = re.compile(r"\b(runner.?up|awards?|of the year|top\s*\d+|winners?)\b", re.IGNORECASE)
_ORDINAL_RE = re.compile(r"\b\d+(st|nd|rd|th)\b", re.IGNORECASE)
# A 21st-century year inside a name is an edition/event date ("Wellness
# Weekend 2019 Celebration", "Health Restaurant of 2016"); heritage years
# ("1945 Restaurant", "Hotel 1928") are real names and not matched.
_MODERN_YEAR_RE = re.compile(r"\b20[0-3]\d\b")
# "2013 Serpentine Gallery Pavilion", "1971 at Pike Place Market" -- but
# not "1945 Restaurant at Fairmont", a real restaurant.
_YEAR_LEAD_RE = re.compile(r"^(20\d\d\s+\S+\s+\S+|(18|19|20)\d\d\s+(at|by|and)\b)", re.IGNORECASE)

# Street/complex fragments swallowed with the name.
_ADDRESS_TOKEN_RE = re.compile(r"\b(jalan|jl|jln|kawasan)\b\.?", re.IGNORECASE)
_ADDRESS_TRAILING_RE = re.compile(r"\b(no|lot|rd|road|st|street|blok|kav)\.?$", re.IGNORECASE)

# Possessives.
_TRAILING_QUOTE_RE = re.compile(r"[’'`]\s*$")
_TRAILING_POSSESSIVE_RE = re.compile(r"[’'`]s\s*$")
_POSSESSIVE_SPLIT_RE = re.compile(r"[’'`]s\b")

# Hotel inventory.
_ROOM_NOUNS = {"suite", "suites", "room", "rooms", "villa", "villas", "floor", "floors", "bedroom", "bedrooms"}
_ROOM_DESCRIPTORS = {
    "the", "deluxe", "premier", "premium", "superior", "executive", "club",
    "grand", "junior", "royal", "presidential", "honeymoon", "studio",
    "family", "ocean", "sea", "view", "pool", "garden", "lagoon", "sky",
    "king", "queen", "twin", "double", "single", "one", "two", "three",
    "one-bedroom", "two-bedroom", "three-bedroom", "bedroom", "private",
    "cliff", "beachfront", "terrace", "penthouse", "signature", "classic",
    "luxury", "villa", "suite", "strand", "a", "for", "river", "jungle",
    "forest", "rice", "paddy", "valley", "hill", "treehouse", "bamboo",
    "mountain", "lake", "spa", "wellness", "romantic",
}
_ROOM_LEAD_WORDS = {"one-bedroom", "two-bedroom", "three-bedroom", "bedroom", "deluxe", "honeymoon"}
_ROOM_SUITE_FOR_RE = re.compile(r"\bsuite\b.*\bfor\s*\d+\s*$", re.IGNORECASE)
_TRAILING_INVENTORY = {"floor", "floors"}

# Trailing words that describe a product, a picture or a concept, not a
# venue's own name.
_TRAILING_NON_NAME_WORDS = {
    "escape", "getaway", "journey", "journeys", "package", "packages",
    "exterior", "interior", "facade", "signage", "concept", "experts",
    "specialists", "menu", "menus", "offer", "offers", "deal", "deals",
    "treatment", "treatments", "ritual", "rituals", "facilities",
    "amenities", "services", "programme", "programmes", "program",
    "programs", "activities", "classes", "sessions", "community",
}

# "<plural noun> of <place>" reads as an article about the place's culture.
_CONCEPT_LEAD_WORDS = {"dances", "masters", "evolution", "secrets", "stories", "history", "taste", "flavours", "flavors"}

# Words with no identifying power on their own. A name made ONLY of these
# (plus "the"/"and"/"&") names a kind of place, not a place.
_GENERIC_WORDS = {
    # venue nouns (the extractor's own VENUE_KEYWORDS, single words)
    "hotel", "resort", "villa", "villas", "suite", "suites", "residence",
    "restaurant", "resto", "cafe", "café", "bar", "lounge", "bistro", "club",
    "rooftop", "spa", "retreat", "wellness", "museum", "gallery", "temple",
    "park", "beach", "golf", "school", "market", "mall", "warung", "kedai",
    "nightclub", "pub", "brewery", "winery", "distillery", "theatre",
    "cinema", "gym", "studio", "kitchen", "eatery", "diner", "grill",
    "steakhouse", "bakery", "deli", "delicatessen", "taproom", "patisserie",
    "pizzeria", "teahouse", "foundation", "center", "centre", "clinic",
    "farm", "sanctuary", "shrine", "aquarium", "zoo", "stadium", "pool",
    "terrace", "garden", "gardens", "hall", "room", "shop", "store",
    "boutique", "salon", "library", "office", "apartment", "apartments",
    "hotels", "resorts", "restaurants", "bars", "spas", "lounges", "cafes",
    "kitchens", "clubs", "residences", "galleries", "museums", "shops",
    # descriptors that only qualify a venue noun
    "kids", "water", "medical", "emergency", "whisky", "whiskey", "wine",
    "cocktail", "coffee", "tea", "24-hour", "all-day", "open-air", "lobby",
    "main", "day", "dining", "sky", "outdoor", "indoor", "private", "public",
    "modern", "single", "experts", "local", "traditional", "luxury",
    "boutique", "sports", "fitness", "health", "beauty", "art", "craft",
    "night", "floating", "infinity", "sunset", "seafood", "vegan",
    # cuisine/nationality adjectives
    "balinese", "indonesian", "javanese", "chinese", "japanese", "korean",
    "thai", "italian", "french", "indian", "mexican", "spanish", "greek",
    "western", "asian", "european", "american", "mediterranean",
    "australian", "vietnamese",
}
_GLUE_WORDS = {"the", "and", "&", "a", "of"}

# Literal phrases seen live that carry no distinguishing proper noun but
# contain one word that is not generic in the abstract.
_GENERIC_PHRASE_BLOCKLIST = {"outreach centre", "ubud centre"}

# Two unrelated international hotel brands in one name is a concatenation
# of two captions, not a co-branded property.
_HOTEL_BRANDS = {
    "conrad", "hilton", "sofitel", "marriott", "hyatt", "sheraton", "westin",
    "kempinski", "mulia", "shangri-la", "shangri la", "four seasons",
    "intercontinental", "ritz-carlton", "ritz carlton", "fairmont", "raffles",
    "alila", "bvlgari", "ayana", "como", "pullman", "novotel", "ascott",
    "citadines", "mandarin oriental", "st regis", "st. regis", "w hotel",
}
# Pairs that genuinely co-brand one property.
_BRAND_PAIR_EXCEPTIONS = ({"ritz-carlton", "ritz carlton"}, {"shangri-la", "shangri la"}, {"st regis", "st. regis"})

# Venue head nouns: the same head appearing twice with different
# modifiers is two venues run together ("Central Park Tribeca Park").
_HEAD_NOUNS = {"hotel", "resort", "restaurant", "mall", "park", "museum", "cafe", "café", "gallery", "university", "school", "temple"}

# A venue noun on the LEFT of " and " means the left side was already a
# complete venue; what follows is a second one.
_VENUE_NOUNS_FOR_AND = _HEAD_NOUNS | {
    "centre", "center", "club", "spa", "bar", "lounge", "plaza", "tower",
    "kitchen", "bistro", "grill", "institute", "hall", "market", "beach",
}
# Right-hand sides of " and " / " & " that complete a compound venue type
# ("Bar and Brasserie", "Resort & Villas") rather than start a second
# venue.
_COMPOUND_TAIL_WORDS = _GENERIC_WORDS | {
    "brasserie", "grill", "terrace", "villas", "suites", "residences",
    "convention", "conventions", "lounge", "wine", "dine", "dining",
    "gallery", "shop", "co", "company", "sons", "friends", "more",
    "cooking", "lodge", "food", "dive", "surf", "yoga", "sports", "bowling",
}

# Short tokens that are complete words.
_SHORT_WORD_ALLOWLIST = {
    "bar", "spa", "pub", "inn", "zoo", "gym", "art", "jl", "bbq", "deli",
    "grill", "tea", "co", "one", "two", "six", "ten", "sun", "sea", "sky",
    "bay", "day", "all", "and", "the", "ku", "ta", "de", "la", "le",
}
# Stems the extractor cuts off mid-word. A last token that is a strict
# prefix of one of these (and not itself a word) is a truncation.
_TRUNCATION_STEMS = (
    "cafe", "restaurant", "package", "centre", "center", "kitchen",
    "gallery", "resort", "lounge", "bakery", "bistro", "market", "garden",
    "gourmet", "coffee", "boutique", "apartment", "residence", "villas",
    "suites", "hotel", "brasserie", "patisserie", "delicatessen",
)

_URL_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+){2,}$")
_URLISH_RE = re.compile(r"(https?://|www\.|\.(com|co\.id|id|net|org)\b)", re.IGNORECASE)

_MAX_TOKENS = 14


@dataclass(frozen=True)
class JunkVerdict:
    """`is_junk` is the high-precision tier -- the only rows
    `triage --apply` writes. `suspect` is the structural tier: names whose
    SHAPE is doubtful (two names joined, "something at a venue", a number,
    a sentence opener) but where a real venue is common enough that an
    editor must look. Both tiers are listed in the report and badged in the
    desk; only `is_junk` rows are ever written without a human."""

    is_junk: bool
    reason: str | None = None
    suspect: bool = False

    @property
    def flagged(self) -> bool:
        return self.is_junk or self.suspect

    @property
    def tier(self) -> str | None:
        return "junk" if self.is_junk else ("suspect" if self.suspect else None)


def _clean_token(t: str) -> str:
    return t.lower().strip(".,;:!?()\"“”")


def _words(name: str) -> list[str]:
    return [w for w in (_clean_token(t) for t in name.split()) if w]


# An event word directly followed by one of these names a place built for
# events ("Bali Festival Park", "Festival Walk"), not an event.
_EVENT_VENUE_FOLLOWERS = {"park", "walk", "city", "hall", "centre", "center", "ground", "grounds", "plaza", "club", "inn", "house"}


def _event_word_hit(raw: str, lowered: str) -> bool:
    if any(e in lowered for e in _EVENT_WORD_EXCEPTIONS):
        return False
    for m in _EVENT_WORD_RE.finditer(raw):
        following = _words(raw[m.end():])
        if following and following[0] in _EVENT_VENUE_FOLLOWERS:
            continue
        return True
    return False


def _gathering_hit(raw: str) -> bool:
    for m in _GATHERING_RE.finditer(raw):
        following = _words(raw[m.end():])
        if following and following[0] in _EVENT_VENUE_FOLLOWERS:
            continue  # "Conference Center", "Expo Hall"
        return True
    return False


def _is_truncation(token: str) -> bool:
    t = token.lower()
    if len(t) < 3 or t in _SHORT_WORD_ALLOWLIST or t in _GENERIC_WORDS:
        return False
    return any(stem.startswith(t) and stem != t for stem in _TRUNCATION_STEMS)


def _and_splits(raw: str) -> list[tuple[str, str, bool]]:
    """Every " and " / " & " split point, keeping the original casing.
    Returns (left, right, is_ampersand) per point, left to right."""
    lowered = raw.lower()
    out: list[tuple[str, str, bool]] = []
    for m in re.finditer(r" (and|&) ", lowered):
        out.append((raw[: m.start()].strip(), raw[m.end():].strip(), m.group(1) == "&"))
    return out


def _concatenation_reason(raw: str, lowered: str, words: list[str]) -> str | None:
    if " and at " in lowered:
        return "two phrases run together ('and at')"
    if re.search(r"\band\b.*\bat\b", lowered) and not lowered.startswith("the "):
        # "Indulge and Imbibe at X" -- a compound phrase happening at a venue.
        left = lowered.split(" at ", 1)[0]
        if not any(w in _VENUE_NOUNS_FOR_AND for w in _words(left)):
            return "event/description phrase ('... and ... at ...')"
    for left, right_raw, ampersand in _and_splits(raw):
        reason = _split_reason(left, right_raw, ampersand)
        if reason:
            return reason
    return None


def _split_reason(left: str, right_raw: str, ampersand: bool) -> str | None:
    # Only the words up to the next connector belong to the right side.
    right_raw = re.split(r" (?:and|&) ", right_raw, maxsplit=1, flags=re.IGNORECASE)[0]
    left_words, right_words = _words(left), _words(right_raw)
    if not left_words or not right_words:
        return None
    # "X and I", "X and Vis" -- cut off after the connector.
    if len(right_words) == 1 and len(right_words[0]) <= 3 and right_words[0] not in _SHORT_WORD_ALLOWLIST:
        return "truncated after 'and'"
    # "X and The Y" / "X and the Pool Side": a second noun phrase with its
    # own article.
    if right_words[0] == "the" and len(right_words) >= 2:
        return "two venues run together ('X and the Y')"
    # Left side already a complete venue, right side not just a compound
    # venue type ("Bar and Brasserie", "Resort & Villas").
    if any(w in _VENUE_NOUNS_FOR_AND for w in left_words) and right_words[0] not in _COMPOUND_TAIL_WORDS:
        if not all(w in _COMPOUND_TAIL_WORDS or w in _GLUE_WORDS for w in right_words):
            # Right side must look like a name: a capitalised token, a
            # number, or its own venue noun.
            # "&" joins parts of ONE name far more often than "and" does
            # ("Moet & Chandon", "Bar & Dim Sum"), so after "&" the right
            # side must carry its own venue noun.
            right_is_venue = any(w in _VENUE_NOUNS_FOR_AND for w in right_words)
            if right_is_venue or (not ampersand and re.search(r"(^|\s)([A-Z0-9])", right_raw)):
                return "two venues run together ('X and Y')"
    return None


def _possessive_reason(raw: str) -> str | None:
    if _TRAILING_POSSESSIVE_RE.search(raw):
        return "possessive fragment ('s with nothing after)"
    if _TRAILING_QUOTE_RE.search(raw):
        return "trailing quote fragment"
    if _POSSESSIVE_SUPERLATIVE_RE.search(raw):
        return "possessive + superlative (a description)"
    if len(_POSSESSIVE_SPLIT_RE.findall(raw)) >= 2:
        return "possessive fragment (two possessives)"
    m = _POSSESSIVE_SPLIT_RE.search(raw)
    if not m:
        return None
    possessor = raw[: m.start()]
    owner_words = [w for w in _words(possessor) if w not in {"the"}]
    lowered_owner = possessor.lower()
    # "Mil's Kitchen", "Bali's Bat Cave Temple": one proper-noun owner is
    # the venue's own name. An owner that is itself a venue ("The Spa's",
    # "Lagoon Cafe's", "The Sofitel's") or a long phrase is a fragment of
    # a sentence about that venue.
    if (
        len(owner_words) >= 2
        or any(w in _GENERIC_WORDS for w in owner_words)
        or any(b in lowered_owner for b in _HOTEL_BRANDS)
    ):
        return "possessive fragment (a venue's 'X's Y')"
    return None


def _room_reason(words: list[str]) -> str | None:
    joined = " ".join(words)
    if _ROOM_SUITE_FOR_RE.search(joined):
        return "hotel room/rate-plan row"
    if words[-1] in _TRAILING_INVENTORY:
        return "hotel room/floor inventory"
    if words[-1] in _ROOM_NOUNS and len(words) <= 5 and all(w in _ROOM_DESCRIPTORS or w in _ROOM_NOUNS for w in words):
        return "hotel room/rate-plan row"
    # "Aksari Suite", "The Anvaya Suite": a resort's name plus a SINGULAR
    # "suite" is a room category there ("The Haven Suites", plural, is a
    # hotel).
    if words[-1] == "suite" and len([w for w in words if w != "the"]) <= 2:
        return "hotel room category (<resort> Suite)"
    if words[0] in _ROOM_LEAD_WORDS and any(w in _ROOM_NOUNS for w in words):
        return "hotel room/rate-plan row"
    if words[0] == "one" and len(words) > 1 and words[1] in {"bedroom", "bedrooms"}:
        return "hotel room/rate-plan row"
    return None


def classify(name: str) -> JunkVerdict:
    """The single entry point. Returns the first matching rule's verdict.

    `name` is used close to raw (only stripped): several rules key on
    casing or punctuation (a trailing curly quote, a capitalised right-hand
    side) that a normalised form would destroy.
    """
    raw = " ".join((name or "").split())
    if not raw:
        return JunkVerdict(True, "empty name")
    lowered = raw.lower()
    words = _words(raw)
    if not words:
        return JunkVerdict(True, "empty name")

    if _URL_SLUG_RE.match(raw) or _URLISH_RE.search(raw):
        return JunkVerdict(True, "URL or slug as name")

    # The extractor's own noise list (Sec.9.3 names it): a whole name that
    # is an area or region ("Nusa Dua", "South Jakarta") is geography, not
    # a venue. (Its other gate, `plausible_new_place`, is NOT reused: it
    # needs a 3-letter word and so rejects real names like "TS Suites".)
    if is_non_venue_phrase(raw):
        return JunkVerdict(True, "an area or region name, not a venue")

    if len(words) > _MAX_TOKENS:
        return JunkVerdict(True, f"run-on text ({len(words)} words)")

    reason = _possessive_reason(raw)
    if reason:
        return JunkVerdict(True, reason)

    if lowered in _GENERIC_PHRASE_BLOCKLIST:
        return JunkVerdict(True, "generic phrase, no proper noun")

    if words[0] in _LEADING_FLAG_WORDS and not lowered.startswith(_LEADING_FLAG_EXCEPTIONS):
        return JunkVerdict(True, f"leading descriptive/CTA word ({words[0]!r})")
    # "New Thai Restaurant" is a description; "New Kuta Golf Course" is a
    # name -- "new" only counts when a generic word follows it.
    if words[0] == "new" and len(words) > 1 and words[1] in _GENERIC_WORDS:
        return JunkVerdict(True, "leading descriptive word ('new')")
    if words[0] == "the" and len(words) > 1 and words[1] in {"best", "new", "top"} and not lowered.startswith(_LEADING_FLAG_EXCEPTIONS):
        return JunkVerdict(True, f"leading descriptive word ({words[1]!r})")

    if _PERSON_TITLE_RE.search(raw) or _PERSON_TITLE_LEAD_RE.search(raw) or _TITLE_LEAD_RE.search(raw):
        return JunkVerdict(True, "a person's job title, not a venue")

    if _ADDRESS_TOKEN_RE.search(raw) or _ADDRESS_TRAILING_RE.search(raw):
        return JunkVerdict(True, "address/street fragment")

    if _AWARD_RE.search(raw) or _ORDINAL_RE.search(raw):
        return JunkVerdict(True, "award/ranking fragment")

    if _YEAR_LEAD_RE.search(raw):
        return JunkVerdict(True, "year-led title (an edition or vintage)")
    if _MODERN_YEAR_RE.search(raw):
        return JunkVerdict(True, "dated edition/event")

    if _event_word_hit(raw, lowered):
        return JunkVerdict(True, "event/offer, not a venue")
    if _WEEKDAY_EVENT_RE.search(raw):
        return JunkVerdict(True, "recurring event, not a venue")
    if _gathering_hit(raw):
        return JunkVerdict(True, "competition/gathering, not a venue")
    if _ENDS_WITH_DAY_RE.search(raw) and len(words) > 1 and words[-2] not in {"all", "every", "the"}:
        return JunkVerdict(True, "a date or observance ('... Day')")
    if _PRICE_RE.search(raw) or _DURATION_RE.search(raw):
        return JunkVerdict(True, "an offer (price or duration)")
    if _TIME_RE.search(raw):
        return JunkVerdict(True, "a clock time, not a venue")
    if _LEVEL_RE.search(raw):
        return JunkVerdict(True, "a floor/level locator")

    if " at " in f" {lowered} ":
        if _MONTH_AT_RE.search(raw):
            return JunkVerdict(True, "date + event-at phrase")
        if any(s in lowered for s in _EVENT_AT_SUBSTRINGS):
            return JunkVerdict(True, "event/description phrase ('... at ...')")

    reason = _room_reason(words)
    if reason:
        return JunkVerdict(True, reason)

    if words[-1] in _TRAILING_NON_NAME_WORDS:
        return JunkVerdict(True, f"product/caption word at the end ({words[-1]!r})")

    if " of " in f" {lowered} " and any(w in _CONCEPT_LEAD_WORDS for w in words[:2]):
        return JunkVerdict(True, "concept/trend title, not a venue")

    brands = {b for b in _HOTEL_BRANDS if re.search(rf"(?<![a-z]){re.escape(b)}(?![a-z])", lowered)}
    if len(brands) >= 2 and not any(brands <= pair for pair in _BRAND_PAIR_EXCEPTIONS):
        return JunkVerdict(True, "two hotel brands run together")

    heads = [w for w in words if w in _HEAD_NOUNS]
    if len(heads) != len(set(heads)):
        return JunkVerdict(True, "the same venue noun twice (two venues run together)")

    reason = _concatenation_reason(raw, lowered, words)
    if reason:
        return JunkVerdict(True, reason)

    if _is_truncation(words[-1]):
        return JunkVerdict(True, f"word cut off ({words[-1]!r})")

    content = [w for w in re.split(r"[\s]+", lowered) if w and w not in _GLUE_WORDS]
    content = [_clean_token(w) for w in content]
    if content and all(w in _GENERIC_WORDS for w in content):
        return JunkVerdict(True, "generic phrase, no proper noun")

    reason = _suspect_reason(raw, lowered, words)
    if reason:
        return JunkVerdict(False, reason, suspect=True)

    return JunkVerdict(False, None)


# ------------------------------------------------------------ suspect tier
#
# Shapes, not literals. Each of these matches real venues too ("Li Lian at
# Park Hyatt", "Museum of Toys", "25hours Hotel"), which is exactly why
# they are a review tier and never written by --apply.

_SENTENCE_OPENERS = {"as", "to", "if", "so", "or", "but", "on", "an", "this", "that", "these", "those", "some", "every", "each"}
_SUSPECT_MAX_TOKENS = 7
# Nouns that head an outlet's own name; two of them with a proper name
# between ("Copa Restaurant La Floriane Bistro") is two outlets.
_OUTLET_NOUNS = {"restaurant", "bistro", "bar", "lounge", "cafe", "café", "grill", "kitchen", "museum", "mall", "gallery", "resort", "hotel"}


def _suspect_reason(raw: str, lowered: str, words: list[str]) -> str | None:
    if words[0] in _SENTENCE_OPENERS:
        return f"opens like a sentence ({words[0]!r})"
    for left, right_raw, _amp in _and_splits(raw):
        right_first = _words(re.split(r" (?:and|&) ", right_raw, maxsplit=1, flags=re.IGNORECASE)[0])
        if right_first and right_first[0] not in _COMPOUND_TAIL_WORDS:
            return "two names joined by 'and'/'&'"
    if " at " in f" {lowered} ":
        return "something 'at' a venue (event, outlet or person?)"
    if " of " in f" {lowered} ":
        return "'X of Y' (part of a place, a person or a title?)"
    if re.search(r"\d", raw):
        return "contains a number"
    nouns = [i for i, w in enumerate(words) if w in _OUTLET_NOUNS]
    if len({words[i] for i in nouns}) >= 2:
        between = words[nouns[0] + 1: nouns[-1]]
        if sum(1 for w in between if w not in _GENERIC_WORDS and w not in _GLUE_WORDS and w != "by") >= 2:
            return "two venue names run together"
    if len(words) > _SUSPECT_MAX_TOKENS:
        return f"long for a name ({len(words)} words)"
    return None


def is_junk(name: str) -> bool:
    return classify(name).is_junk

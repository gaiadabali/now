"""Candidate venue-name phrase extraction from plain text.

Deterministic, not statistical NER (ARCHITECTURE.md Sec.1: "deterministic
engine decides"). A candidate is a run of Title-Case / all-caps / digit
tokens, allowing a small set of connector words to appear MID-phrase
(never at the edges) because real venue names use them constantly: "The
Ritz-Carlton Jakarta Mega Kuningan", "W Bali Seminyak", "T Galleria by
DFS, Bali", "Bella Cucina at InterContinental Bali Resort".

This over-generates (plenty of candidates are not venues at all -- person
names, event names, brand names) by design: precision is enforced
downstream by (a) gazetteer matching against known places for the exact
same city, and (b) a venue-keyword heuristic for anything not already
known, not by trying to make the regex itself smart. A candidate nobody
can corroborate (no gazetteer hit, no venue keyword, appears once) is
simply dropped rather than promoted to a place -- see pipeline.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Connector words allowed strictly BETWEEN two capitalized tokens.
_CONNECTORS = {"the", "of", "at", "by", "and", "&", "de", "la", "el"}

# A single token: capitalized word (allows internal hyphen/apostrophe),
# an ALL-CAPS acronym-ish word, or a short digit-led token ("40", "W2").
# Deliberately NO "." in the character class: an earlier version allowed
# it (for abbreviations like "St.") and it silently swallowed the next
# SENTENCE's trailing period too ("...in Jakarta." matched as one token
# "Jakarta."), polluting exact-match against the gazetteer (`normalize_full`
# strips punctuation anyway, so "St Regis" without the dot still matches
# fine; the false-positive sentence-boundary capture was the worse cost).
_TOKEN_RE = r"(?:[A-Z][A-Za-z'’\-]*|[0-9]+[A-Za-z']*)"
_CONNECTOR_RE = r"(?:[Tt]he|[Oo]f|[Aa]t|[Bb]y|[Aa]nd|&)"

_CANDIDATE_RE = re.compile(
    rf"""
    (?<![A-Za-z0-9\-]){_TOKEN_RE}
    (?:[ ,\-](?:{_TOKEN_RE}|{_CONNECTOR_RE}))*
    (?![A-Za-z0-9])
    """,
    re.VERBOSE,
)

# Venue-type keywords used to score a NEW (not-yet-known) candidate as
# "venue-shaped" -- ARCHITECTURE.md's own type tree gives most of these.
VENUE_KEYWORDS = {
    "hotel", "resort", "villa", "villas", "suite", "suites", "residence",
    "restaurant", "resto", "cafe", "café", "bar", "lounge", "bistro",
    "club", "beach club", "rooftop", "spa", "retreat", "wellness",
    "museum", "gallery", "temple", "park", "beach", "golf", "school",
    "market", "mall", "warung", "kedai", "nightclub", "pub", "brewery",
    "winery", "distillery", "theatre", "cinema", "gym", "studio",
    "kitchen", "eatery", "diner", "grill", "steakhouse", "bakery", "deli",
    "delicatessen", "taproom", "patisserie", "pizzeria", "teahouse",
    "foundation", "center", "centre", "clinic", "farm",
    "sanctuary", "shrine", "monastery", "aquarium", "zoo", "stadium",
    # NOT "academy" -- found live: matched "Academy Awards" (the Oscars),
    # not a venue. Real academies/schools still match via "school".
}


@dataclass(frozen=True)
class Candidate:
    surface_text: str
    start: int
    end: int


def _trim_connectors(text: str) -> tuple[str, int, int]:
    """Strip TRAILING connector-word tokens only ("...Bar and" ->
    "...Bar"). The match can never legitimately START on a connector --
    `_CANDIDATE_RE`'s anchor token is `_TOKEN_RE`, which requires an
    initial capital/digit, so a leading "the"/"of"/"at" is structurally
    impossible to match in the first place. That asymmetry matters: many
    real venue names in this exact corpus legitimately START with "The"
    ("The Ritz-Carlton Jakarta Mega Kuningan", "The St. Regis Bali
    Resort", "The Trans Resort Bali" -- all real `public.places` rows),
    so an earlier version of this function that also trimmed leading
    connectors was silently stripping "The" off every such name and
    breaking exact-match against the gazetteer. Returns the trimmed text
    plus the end_delta to apply to the original span."""
    tokens = text.split(" ")
    end_delta = 0
    while tokens and tokens[-1].strip(",-").lower() in _CONNECTORS:
        end_delta += len(tokens[-1]) + 1
        tokens.pop()
    return " ".join(tokens), 0, end_delta


_MIN_LEN = 3  # drop single-letter/very short noise tokens like stray "A"


def extract_candidates(text: str) -> list[Candidate]:
    if not text:
        return []
    out: list[Candidate] = []
    for m in _CANDIDATE_RE.finditer(text):
        raw = m.group(0)
        trimmed, start_delta, end_delta = _trim_connectors(raw)
        trimmed = trimmed.strip(" ,-")
        if len(trimmed) < _MIN_LEN:
            continue
        # Require at least one alphabetic character and at least one
        # actual capitalized/acronym token (reject pure connector debris
        # and bare numbers like a stray "40" with nothing else).
        if not re.search(r"[A-Za-z]{2,}", trimmed):
            continue
        start = m.start() + start_delta
        end = m.end() - end_delta
        out.append(Candidate(surface_text=trimmed, start=start, end=end))
    return out


_WORD_RE = re.compile(r"[a-z]+")


def looks_venue_shaped(name: str) -> bool:
    """Whole-WORD match only, deliberately not `keyword in lowered`: a
    naive substring check matched "bar" inside "LeBARan" (Eid) and would
    equally match "spa" inside "Spanish" or "gym" inside a random string
    -- found live (see report), not hypothetical."""
    words = set(_WORD_RE.findall(name.lower()))
    single_word_keywords = {kw for kw in VENUE_KEYWORDS if " " not in kw}
    if words & single_word_keywords:
        return True
    multi_word_keywords = VENUE_KEYWORDS - single_word_keywords
    lowered = name.lower()
    return any(kw in lowered for kw in multi_word_keywords)


# Function words, deictics, calendar words, nationalities, and magazine
# boilerplate that capitalize for reasons that have nothing to do with
# being a venue name (sentence-initial capitalization, headline case,
# "Read NOW / SUBSCRIBE" mastheads, a "<Month> <Year>" issue credit line).
# Found by running the real extractor against 100 live Jakarta articles
# and inspecting the highest-recurrence surviving candidates by hand
# (see this ticket's report) -- NOT guessed in the abstract. A candidate
# is only rejected if EVERY token it contains (after removing connector
# words) is in this set; "Holland Bakery" survives ("holland" is a
# nationality-adjacent word but "bakery" is not in this set), "Ramadan"
# alone does not.
NOISE_WORDS = {
    "this", "that", "these", "those", "there", "here", "it", "its",
    "what", "when", "where", "who", "why", "how", "with", "for", "and",
    "but", "or", "so", "now", "you", "your", "we", "our", "they", "their",
    "he", "she", "his", "her", "i", "available", "read", "subscribe",
    "more", "also", "just", "according", "meanwhile", "however",
    "moreover", "despite", "whether", "unlike", "since", "while",
    "although", "because", "every", "each", "some", "many", "most",
    "all", "both", "either", "neither", "several", "few", "one", "two",
    "three", "four", "five", "kids", "family", "guests", "instagram",
    "facebook", "whatsapp", "twitter", "tiktok", "dutch", "chinese",
    "japanese", "javanese", "malaysian", "asian", "indonesian",
    "australian", "indonesia", "jakarta", "bali", "magazine", "photo",
    "photos", "image", "images", "from", "through", "during", "after",
    "then", "jokowi", "covid",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "southeast", "middle", "eastern", "western", "northern", "southern",
    "asia", "asian", "america", "european", "europe",
    # Temporal common nouns -- generic venue-type keywords appended to
    # one of these ("Wellness Day", "New Year's Eve") describe an EVENT,
    # not a venue, and previously survived because the keyword ("wellness")
    # was stripped as generic but the temporal word wasn't, leaving
    # something that looked "meaningful" by accident. Found live.
    "day", "days", "night", "nights", "week", "weeks", "weekend",
    "weekends", "eve", "morning", "afternoon", "evening", "season",
    # Awards/booklet copy -- found live ("Best Restaurant Bar and Cafe
    # Winners E-Booklet").
    "winners", "winner", "awards", "award", "booklet",
}

# The full, real `enum_places_area_term` vocabulary (verified live against
# both cities' Postgres before hardcoding this -- ARCHITECTURE.md Sec.4
# "Location tree" is exactly this list). A candidate whose FULL normalized
# name matches one of these entries is a geographic AREA ("South
# Jakarta", "Kebayoran Baru", "Hong Kong"), not a venue -- ARCHITECTURE's
# own data model puts geography in `places.area_term` / the platform
# `terms` location tree, never as its own `places` row for content this
# pipeline creates. (The pre-existing 177 rows already violate this --
# "Bali", "Ubud", "Nusa Dua" are places there too -- but that set is this
# ticket's Finding #1, not a pattern to extend.) Hyphens are rendered as
# spaces to compare against `normalize_full`, which already folds
# punctuation to spaces.
_AREA_TERM_ENUM = {
    "aceh", "africa", "alam-sutera", "amed", "ancol", "australia", "bali",
    "bandung", "bangli", "banyuwangi", "bedugul", "bekasi", "belitung",
    "bintan", "bintaro", "blok-m", "bogor", "bsd", "cambodia", "candidasa",
    "canggu", "casablanca", "cengkareng", "central-bali", "central-jakarta",
    "china", "cibubur", "cikini", "cilandak", "cipete", "cirebon",
    "denpasar", "depok", "east-bali", "east-jakarta", "other", "europe",
    "gading-serpong", "gambir", "gatot-subroto", "gianyar", "glodok",
    "greater-jakarta", "gunawarman", "hong-kong", "india", "indonesia",
    "international", "jakarta", "japan", "jatiluwih", "java", "jimbaran",
    "kalimantan", "kebayoran-baru", "kebon-jeruk", "kebon-sirih",
    "kelapa-gading", "kemang", "kemayoran", "kepulauan-seribu", "kerobokan",
    "kintamani", "komodo", "kota-tua", "kuningan", "kuta", "lake-toba",
    "lampung", "legian", "lombok", "lovina", "makassar", "malang",
    "malaysia", "maldives", "maluku", "manado", "medan", "mengwi",
    "menteng", "middle-east", "new-zealand", "north-bali", "north-jakarta",
    "nusa-dua", "nusa-lembongan", "nusa-penida", "nusa-tenggara", "padang",
    "palembang", "pasar-baru", "pererenan", "philippines", "pik",
    "pondok-indah", "puncak", "puri-indah", "raja-ampat", "rawamangun",
    "riau-islands", "sanur", "scbd", "semarang", "seminyak", "senayan",
    "senopati", "sentul", "sidemen", "singapore", "solo", "south-bali",
    "south-jakarta", "south-korea", "sri-lanka", "sudirman", "sulawesi",
    "sumatra", "sumba", "surabaya", "tabanan", "taiwan", "tanah-abang",
    "tanah-lot", "tangerang", "tebet", "thailand", "thamrin", "tmii",
    "toraja", "turkey", "uae", "ubud", "uluwatu", "usa", "vietnam",
    "west-bali", "west-jakarta", "yogyakarta",
}
_AREA_TERM_PHRASES = {t.replace("-", " ") for t in _AREA_TERM_ENUM}

# Supplementary geo/date/CTA phrases that are NOT venues but are NOT in
# the area_term enum either (Java's own provinces, generic CTAs, holidays)
# -- found the same way as NOISE_WORDS, by hand-inspecting live extractor
# output against the real corpus (report).
_SUPPLEMENTARY_NON_VENUE_PHRASES = {
    "west java", "east java", "central java", "united states",
    "new year", "new years eve", "chinese new year", "book now",
    "read now", "christmas", "valentines day", "halloween", "world cup",
    "united kingdom", "north america", "south america", "new york",
    "los angeles", "london", "paris", "dubai", "seoul", "bangkok",
    "kuala lumpur", "beijing", "shanghai", "tokyo",
}
_NON_VENUE_PHRASES = _AREA_TERM_PHRASES | _SUPPLEMENTARY_NON_VENUE_PHRASES


def is_non_venue_phrase(name: str) -> bool:
    from now_place_extraction.normalize import normalize_full

    return normalize_full(name) in _NON_VENUE_PHRASES


# A candidate STARTING with any of these is, in this corpus, always an
# image credit line ("Photo by Raditya Fadilla", "Courtesy of the hotel")
# rather than a venue -- found the same way as NOISE_WORDS, by hand-
# inspecting live extractor output (report). Checked on the first token
# only (not "does the phrase contain 'Photo' anywhere") since a real venue
# CAN legitimately contain "Gallery"/"Studio" etc. elsewhere in its name.
_CREDIT_LINE_PREFIXES = {"photo", "photos", "image", "images", "courtesy"}


_SINGLE_WORD_VENUE_KEYWORDS = {kw for kw in VENUE_KEYWORDS if " " not in kw}


def _meaningful_tokens(name: str) -> list[str]:
    from now_place_extraction.normalize import _GENERIC_WORDS  # bare venue-type nouns too

    out = []
    for t in name.split(" "):
        stripped = t.strip(",.-")
        if not stripped or stripped.isdigit():
            continue  # bare years/numbers carry no venue-identifying signal alone
        low = stripped.lower()
        if low in NOISE_WORDS or low in _GENERIC_WORDS or low in _SINGLE_WORD_VENUE_KEYWORDS:
            # A candidate that is ENTIRELY generic venue-type nouns ("Restaurant",
            # "The Hotel", "Wellness") has no actual NAME in it -- found live: bare
            # "Restaurant"/"Wellness" cleared the old check because
            # `looks_venue_shaped` matches the keyword against itself with
            # nothing else in the phrase to actually identify a specific venue.
            continue
        out.append(stripped)
    return out


def plausible_new_place(surface_text: str) -> bool:
    """Gate for a candidate that had NO gazetteer hit: is there anything
    left once known noise words (and bare numbers, and credit-line
    prefixes) are stripped? Pure-noise candidates ("Jakarta Magazine May
    2019", "It's", "SUBSCRIBE", "Photo by Raditya Fadilla") return False
    regardless of how often they recur -- recurrence alone was proven
    live to be a bad precision signal (boilerplate recurs constantly by
    construction; see report). Recurrence is still applied on TOP of this
    gate by the caller (pipeline.py), not instead of it."""
    first = surface_text.split(" ", 1)[0].strip(",.-").lower()
    if first in _CREDIT_LINE_PREFIXES:
        return False
    if is_non_venue_phrase(surface_text):
        return False
    remaining = _meaningful_tokens(surface_text)
    return len(remaining) > 0 and any(len(t) >= 3 for t in remaining)

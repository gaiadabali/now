/**
 * The place desk's copy of `now_places.junk` (engine/packages/place-catalogue).
 *
 * The desk badges each place with the same verdict `now-places triage` puts
 * in its report: "junk" (the high-precision tier, which the desk offers for
 * bulk confirmation), "suspect" (a doubtful shape an editor should look at),
 * or nothing. There is no database column for a proposal, and there should
 * not need to be one, so the rules run here too.
 *
 * TWO IMPLEMENTATIONS OF ONE RULE SET ARE A DRIFT RISK, so they are pinned
 * together: `place-catalogue/tests/fixtures/junk_golden.jsonl` holds the
 * Python verdict (tier and exact reason) for 440 names, and
 * `test/placeJunk.test.ts` asserts this file reproduces every one of them.
 * Change junk.py, regenerate the golden file, then change this until the
 * test passes again.
 *
 * Python's `re` is Unicode-aware (`\b`, `\d` treat "é" and Arabic-Indic
 * digits as word characters); JavaScript's `\b` is ASCII-only even under the
 * `u` flag. `rx()` rewrites both so a name like "Café Fest" gets the same
 * answer in both places.
 *
 * Pure and Next-free so `node --test` can import it.
 */

export type JunkTier = 'junk' | 'suspect' | null

export type JunkVerdict = { tier: JunkTier; reason: string | null }

const WORD = String.raw`[\p{L}\p{N}_]`
const UB = String.raw`(?:(?<=${WORD})(?!${WORD})|(?<!${WORD})(?=${WORD}))`

/** Compile a Python-flavoured pattern with Unicode `\b` and `\d`. */
function rx(pattern: string, flags = 'i'): RegExp {
  const src = pattern.replace(/\\b/g, UB).replace(/\\d/g, String.raw`\p{Nd}`)
  return new RegExp(src, flags.includes('u') ? flags : `${flags}u`)
}

// ---------------------------------------------------------------- lexicons

const LEADING_FLAG_WORDS = new Set([
  'best', 'their', 'its', 'his', 'her', 'our', 'your', 'off', 'join',
  'held', 'available', 'with', 'at', 'special', 'top',
  'shopping', 'christmas', 'resolution', 'located', 'in', 'inside',
  'near', 'nearest', 'during', 'featuring', 'including', 'from', 'for',
  'via', 'when', 'where', 'while', 'since', 'visit',
  'enjoy', 'discover', 'celebrate', 'book', 'meet', 'opening', 'opened',
  'launched', 'hosted', 'presented', 'organised', 'organized', 'curated',
  'designed', 'owned', 'managed', 'powered', 'inspired', 'introducing',
  'january', 'february', 'march', 'april', 'may', 'june', 'july',
  'august', 'september', 'october', 'november', 'december',
])
const LEADING_FLAG_EXCEPTIONS = ['best western', 'new york steakhouse', 'top of the']

const MONTH =
  String.raw`(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|` +
  String.raw`aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)`
const MONTH_AT_RE = rx(String.raw`\b${MONTH}\b.*\bat\b`)

const EVENT_WORD_SRC =
  String.raw`\b(celebrations?|festivals?|fest|raves?|series|buffets?|brunch(es)?|` +
  String.raw`part(y|ies)|gala|workshops?|masterclass(es)?|promos?|promotions?|` +
  String.raw`packages?|packag|edition|exhibitions?|concerts?|launch(es)?|` +
  String.raw`anniversary|countdown|ramadan|iftar|easter|valentine'?s?|halloween|` +
  String.raw`new\s+year'?s?|weekend|holiday|clean\s*up|sound\s+healing|` +
  String.raw`tree\s+lighting|fiesta|takeover|pop-?up)\b`
const EVENT_WORD_RE_G = rx(EVENT_WORD_SRC, 'gi')
const EVENT_WORD_EXCEPTIONS = ['holiday inn', 'festival walk', 'festival city']

const EVENT_AT_SUBSTRINGS = [
  'dinner', 'lunch', 'cocktail', 'ceremony', 'market', 'week', 'reserved',
  'seats', 'moment', 'training', 'chef', 'sous', 'executive', 'held',
  'christmas', 'drinks', 'welcome', 'final ', 'event ', 'indulge',
  'evening', 'night out', 'session',
  'painting', 'cooking', 'tasting', 'making', 'carving', 'weaving',
  'dancing', 'yoga', 'class', 'workshop', 'tour ', 'stay ', 'treatment',
  'massage', 'facial', 'feast', 'breakfast', 'afternoon tea', 'pairing',
]

const GATHERING_SRC =
  String.raw`\b(competitions?|championships?|tournaments?|cook[- ]?off|contests?|` +
  String.raw`auctions?|fundraisers?|conferences?|summit|forum|expo|bazaars?|` +
  String.raw`screenings?|open\s+house|charity\s+(run|dinner|gala))\b`
const GATHERING_RE_G = rx(GATHERING_SRC, 'gi')
const ENDS_WITH_DAY_RE = rx(String.raw`\S\s+day$`)
const PRICE_RE = rx(String.raw`\b(idr|rp|usd|us\$|sgd|aud)\s*[\d.,]+|\$\s*\d`)
const DURATION_RE = rx(String.raw`\b(one|two|three|four|five|six|seven|\d+)[- ](day|days|night|nights|hour|hours)\b(?!-)`)
const TIME_RE = rx(String.raw`\b\d{1,2}([.:]\d\d)?\s*(am|pm)\b`)
const LEVEL_RE = rx(String.raw`\b(level|lantai|lt\.?|floor)\s*\d+\s*$|\bground\s+floor\b`)
const TITLE_LEAD_RE = rx(
  String.raw`^(the\s+)?(bar|general|restaurant|spa|hotel|area|sales|marketing|executive|` +
    String.raw`assistant|resident|operations|f&b|food\s+and\s+beverage)\s+` +
    String.raw`(manager|director|chef|head|supervisor)\b`,
)
const POSSESSIVE_SUPERLATIVE_RE = rx(
  String.raw`[’'\x60]s\s+(leading|best|finest|first|largest|biggest|newest|oldest|only|` +
    String.raw`favou?rite|top|most|latest|famous|iconic|premier|number|no\.?)\b`,
)
const WEEKDAY_EVENT_RE = rx(String.raw`\b(mon|tues|wednes|thurs|fri|satur|sun)day\b.*\b(market|brunch|session|night|sessions)\b`)
const PERSON_TITLE_RE = rx(
  String.raw`\b(general\s+manager|residence\s+manager|hotel\s+manager|manager|director|` +
    String.raw`executive\s+chef|head\s+chef|pastry\s+chef|sous\s+chef|chef|founder|` +
    String.raw`co-?founder|owner|ceo|sommelier|bartender|mixologist|curator)\s+(of|at)\b`,
)
const PERSON_TITLE_LEAD_RE = rx(String.raw`^(executive\s+)?(sous\s+|head\s+|pastry\s+)?chef\b`)
const AWARD_RE = rx(String.raw`\b(runner.?up|awards?|of the year|top\s*\d+|winners?)\b`)
const ORDINAL_RE = rx(String.raw`\b\d+(st|nd|rd|th)\b`)
const MODERN_YEAR_RE = rx(String.raw`\b20[0-3]\d\b`, '')
const YEAR_LEAD_RE = rx(String.raw`^(20\d\d\s+\S+\s+\S+|(18|19|20)\d\d\s+(at|by|and)\b)`)
const ADDRESS_TOKEN_RE = rx(String.raw`\b(jalan|jl|jln|kawasan)\b\.?`)
const ADDRESS_TRAILING_RE = rx(String.raw`\b(no|lot|rd|road|st|street|blok|kav)\.?$`)
const TRAILING_QUOTE_RE = rx(String.raw`[’'\x60]\s*$`, '')
const TRAILING_POSSESSIVE_RE = rx(String.raw`[’'\x60]s\s*$`, '')
const POSSESSIVE_SPLIT_RE_G = rx(String.raw`[’'\x60]s\b`, 'g')
const AND_THEN_AT_RE = rx(String.raw`\band\b.*\bat\b`, '')

const ROOM_NOUNS = new Set(['suite', 'suites', 'room', 'rooms', 'villa', 'villas', 'floor', 'floors', 'bedroom', 'bedrooms'])
const ROOM_DESCRIPTORS = new Set([
  'the', 'deluxe', 'premier', 'premium', 'superior', 'executive', 'club',
  'grand', 'junior', 'royal', 'presidential', 'honeymoon', 'studio',
  'family', 'ocean', 'sea', 'view', 'pool', 'garden', 'lagoon', 'sky',
  'king', 'queen', 'twin', 'double', 'single', 'one', 'two', 'three',
  'one-bedroom', 'two-bedroom', 'three-bedroom', 'bedroom', 'private',
  'cliff', 'beachfront', 'terrace', 'penthouse', 'signature', 'classic',
  'luxury', 'villa', 'suite', 'strand', 'a', 'for', 'river', 'jungle',
  'forest', 'rice', 'paddy', 'valley', 'hill', 'treehouse', 'bamboo',
  'mountain', 'lake', 'spa', 'wellness', 'romantic',
])
const ROOM_LEAD_WORDS = new Set(['one-bedroom', 'two-bedroom', 'three-bedroom', 'bedroom', 'deluxe', 'honeymoon'])
const ROOM_SUITE_FOR_RE = rx(String.raw`\bsuite\b.*\bfor\s*\d+\s*$`)
const TRAILING_INVENTORY = new Set(['floor', 'floors'])

const TRAILING_NON_NAME_WORDS = new Set([
  'escape', 'getaway', 'journey', 'journeys', 'package', 'packages',
  'exterior', 'interior', 'facade', 'signage', 'concept', 'experts',
  'specialists', 'menu', 'menus', 'offer', 'offers', 'deal', 'deals',
  'treatment', 'treatments', 'ritual', 'rituals', 'facilities',
  'amenities', 'services', 'programme', 'programmes', 'program',
  'programs', 'activities', 'classes', 'sessions', 'community',
])
const CONCEPT_LEAD_WORDS = new Set(['dances', 'masters', 'evolution', 'secrets', 'stories', 'history', 'taste', 'flavours', 'flavors'])

const GENERIC_WORDS = new Set([
  'hotel', 'resort', 'villa', 'villas', 'suite', 'suites', 'residence',
  'restaurant', 'resto', 'cafe', 'café', 'bar', 'lounge', 'bistro', 'club',
  'rooftop', 'spa', 'retreat', 'wellness', 'museum', 'gallery', 'temple',
  'park', 'beach', 'golf', 'school', 'market', 'mall', 'warung', 'kedai',
  'nightclub', 'pub', 'brewery', 'winery', 'distillery', 'theatre',
  'cinema', 'gym', 'studio', 'kitchen', 'eatery', 'diner', 'grill',
  'steakhouse', 'bakery', 'deli', 'delicatessen', 'taproom', 'patisserie',
  'pizzeria', 'teahouse', 'foundation', 'center', 'centre', 'clinic',
  'farm', 'sanctuary', 'shrine', 'aquarium', 'zoo', 'stadium', 'pool',
  'terrace', 'garden', 'gardens', 'hall', 'room', 'shop', 'store',
  'boutique', 'salon', 'library', 'office', 'apartment', 'apartments',
  'hotels', 'resorts', 'restaurants', 'bars', 'spas', 'lounges', 'cafes',
  'kitchens', 'clubs', 'residences', 'galleries', 'museums', 'shops',
  'kids', 'water', 'medical', 'emergency', 'whisky', 'whiskey', 'wine',
  'cocktail', 'coffee', 'tea', '24-hour', 'all-day', 'open-air', 'lobby',
  'main', 'day', 'dining', 'sky', 'outdoor', 'indoor', 'private', 'public',
  'modern', 'single', 'experts', 'local', 'traditional', 'luxury',
  'sports', 'fitness', 'health', 'beauty', 'art', 'craft',
  'night', 'floating', 'infinity', 'sunset', 'seafood', 'vegan',
  'balinese', 'indonesian', 'javanese', 'chinese', 'japanese', 'korean',
  'thai', 'italian', 'french', 'indian', 'mexican', 'spanish', 'greek',
  'western', 'asian', 'european', 'american', 'mediterranean',
  'australian', 'vietnamese',
])
const GLUE_WORDS = new Set(['the', 'and', '&', 'a', 'of'])
const GENERIC_PHRASE_BLOCKLIST = new Set(['outreach centre', 'ubud centre'])

const HOTEL_BRANDS = [
  'conrad', 'hilton', 'sofitel', 'marriott', 'hyatt', 'sheraton', 'westin',
  'kempinski', 'mulia', 'shangri-la', 'shangri la', 'four seasons',
  'intercontinental', 'ritz-carlton', 'ritz carlton', 'fairmont', 'raffles',
  'alila', 'bvlgari', 'ayana', 'como', 'pullman', 'novotel', 'ascott',
  'citadines', 'mandarin oriental', 'st regis', 'st. regis', 'w hotel',
]
const BRAND_PAIR_EXCEPTIONS = [
  new Set(['ritz-carlton', 'ritz carlton']),
  new Set(['shangri-la', 'shangri la']),
  new Set(['st regis', 'st. regis']),
]
const BRAND_RES = HOTEL_BRANDS.map(
  (b) => [b, new RegExp(`(?<![a-z])${b.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![a-z])`)] as const,
)

const HEAD_NOUNS = new Set(['hotel', 'resort', 'restaurant', 'mall', 'park', 'museum', 'cafe', 'café', 'gallery', 'university', 'school', 'temple'])
const VENUE_NOUNS_FOR_AND = new Set([
  ...HEAD_NOUNS,
  'centre', 'center', 'club', 'spa', 'bar', 'lounge', 'plaza', 'tower',
  'kitchen', 'bistro', 'grill', 'institute', 'hall', 'market', 'beach',
])
const COMPOUND_TAIL_WORDS = new Set([
  ...GENERIC_WORDS,
  'brasserie', 'grill', 'terrace', 'villas', 'suites', 'residences',
  'convention', 'conventions', 'lounge', 'wine', 'dine', 'dining',
  'gallery', 'shop', 'co', 'company', 'sons', 'friends', 'more',
  'cooking', 'lodge', 'food', 'dive', 'surf', 'yoga', 'sports', 'bowling',
])
const SHORT_WORD_ALLOWLIST = new Set([
  'bar', 'spa', 'pub', 'inn', 'zoo', 'gym', 'art', 'jl', 'bbq', 'deli',
  'grill', 'tea', 'co', 'one', 'two', 'six', 'ten', 'sun', 'sea', 'sky',
  'bay', 'day', 'all', 'and', 'the', 'ku', 'ta', 'de', 'la', 'le',
])
const TRUNCATION_STEMS = [
  'cafe', 'restaurant', 'package', 'centre', 'center', 'kitchen',
  'gallery', 'resort', 'lounge', 'bakery', 'bistro', 'market', 'garden',
  'gourmet', 'coffee', 'boutique', 'apartment', 'residence', 'villas',
  'suites', 'hotel', 'brasserie', 'patisserie', 'delicatessen',
]
const EVENT_VENUE_FOLLOWERS = new Set(['park', 'walk', 'city', 'hall', 'centre', 'center', 'ground', 'grounds', 'plaza', 'club', 'inn', 'house'])

const URL_SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+){2,}$/
const URLISH_RE = rx(String.raw`(https?://|www\.|\.(com|co\.id|id|net|org)\b)`)

const MAX_TOKENS = 14

const SENTENCE_OPENERS = new Set(['as', 'to', 'if', 'so', 'or', 'but', 'on', 'an', 'this', 'that', 'these', 'those', 'some', 'every', 'each'])
const SUSPECT_MAX_TOKENS = 7
const OUTLET_NOUNS = new Set(['restaurant', 'bistro', 'bar', 'lounge', 'cafe', 'café', 'grill', 'kitchen', 'museum', 'mall', 'gallery', 'resort', 'hotel'])

/**
 * The extractor's supplementary non-venue phrases
 * (`now_place_extraction.extract._SUPPLEMENTARY_NON_VENUE_PHRASES`). The
 * AREA phrases are not copied here: they are the city database's own
 * `enum_places_area_term`, read at runtime (`placeDesk.ts`) and passed in.
 */
export const SUPPLEMENTARY_NON_VENUE_PHRASES: readonly string[] = [
  'bangkok', 'beijing', 'book now', 'chinese new year', 'christmas', 'dubai',
  'east java', 'halloween', 'kuala lumpur', 'london', 'los angeles',
  'new year', 'new years eve', 'new york', 'north america', 'paris',
  'read now', 'seoul', 'shanghai', 'south america', 'tokyo',
  'united kingdom', 'united states', 'valentines day', 'west java',
  'central java', 'world cup',
]

// ------------------------------------------------------------- helpers

const STRIP_CHARS = new Set(['.', ',', ';', ':', '!', '?', '(', ')', '"', '“', '”'])

function cleanToken(t: string): string {
  let s = t.toLowerCase()
  let a = 0
  let b = s.length
  while (a < b && STRIP_CHARS.has(s[a]!)) a++
  while (b > a && STRIP_CHARS.has(s[b - 1]!)) b--
  s = s.slice(a, b)
  return s
}

function splitWs(s: string): string[] {
  return s.split(/\s+/u).filter(Boolean)
}

function words(name: string): string[] {
  return splitWs(name).map(cleanToken).filter(Boolean)
}

/** Python's `repr()` of a plain string, for reason texts like `('best')`. */
function pyRepr(s: string): string {
  if (s.includes("'") && !s.includes('"')) return `"${s.replace(/\\/g, '\\\\')}"`
  return `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

/** `now_place_extraction.normalize.normalize_full`. */
export function normalizeFull(name: string): string {
  let folded = (name ?? '').normalize('NFKD').replace(/\p{Mn}/gu, '')
  folded = folded.toLowerCase()
  folded = folded.replace(/[’‘'\x60]/g, '')
  folded = folded.replace(/[^a-z0-9\s]/g, ' ')
  return folded.replace(/\s+/g, ' ').trim()
}

function eventWordHit(raw: string, lowered: string): boolean {
  if (EVENT_WORD_EXCEPTIONS.some((e) => lowered.includes(e))) return false
  for (const m of raw.matchAll(EVENT_WORD_RE_G)) {
    const following = words(raw.slice((m.index ?? 0) + m[0].length))
    if (following.length && EVENT_VENUE_FOLLOWERS.has(following[0]!)) continue
    return true
  }
  return false
}

function gatheringHit(raw: string): boolean {
  for (const m of raw.matchAll(GATHERING_RE_G)) {
    const following = words(raw.slice((m.index ?? 0) + m[0].length))
    if (following.length && EVENT_VENUE_FOLLOWERS.has(following[0]!)) continue
    return true
  }
  return false
}

function isTruncation(token: string): boolean {
  const t = token.toLowerCase()
  if (t.length < 3 || SHORT_WORD_ALLOWLIST.has(t) || GENERIC_WORDS.has(t)) return false
  return TRUNCATION_STEMS.some((stem) => stem.startsWith(t) && stem !== t)
}

function andSplits(raw: string): Array<[string, string, boolean]> {
  const lowered = raw.toLowerCase()
  const out: Array<[string, string, boolean]> = []
  for (const m of lowered.matchAll(/ (and|&) /g)) {
    const start = m.index ?? 0
    out.push([raw.slice(0, start).trim(), raw.slice(start + m[0].length).trim(), m[1] === '&'])
  }
  return out
}

function firstSegment(right: string): string {
  const m = / (?:and|&) /i.exec(right)
  return m ? right.slice(0, m.index) : right
}

function splitReason(left: string, rightRawFull: string, ampersand: boolean): string | null {
  const rightRaw = firstSegment(rightRawFull)
  const leftWords = words(left)
  const rightWords = words(rightRaw)
  if (!leftWords.length || !rightWords.length) return null
  if (rightWords.length === 1 && rightWords[0]!.length <= 3 && !SHORT_WORD_ALLOWLIST.has(rightWords[0]!)) {
    return "truncated after 'and'"
  }
  if (rightWords[0] === 'the' && rightWords.length >= 2) return "two venues run together ('X and the Y')"
  if (leftWords.some((w) => VENUE_NOUNS_FOR_AND.has(w)) && !COMPOUND_TAIL_WORDS.has(rightWords[0]!)) {
    if (!rightWords.every((w) => COMPOUND_TAIL_WORDS.has(w) || GLUE_WORDS.has(w))) {
      const rightIsVenue = rightWords.some((w) => VENUE_NOUNS_FOR_AND.has(w))
      if (rightIsVenue || (!ampersand && /(^|\s)([A-Z0-9])/u.test(rightRaw))) {
        return "two venues run together ('X and Y')"
      }
    }
  }
  return null
}

function concatenationReason(raw: string, lowered: string): string | null {
  if (lowered.includes(' and at ')) return "two phrases run together ('and at')"
  if (AND_THEN_AT_RE.test(lowered) && !lowered.startsWith('the ')) {
    const left = lowered.split(' at ')[0] ?? lowered
    if (!words(left).some((w) => VENUE_NOUNS_FOR_AND.has(w))) {
      return "event/description phrase ('... and ... at ...')"
    }
  }
  for (const [left, right, amp] of andSplits(raw)) {
    const reason = splitReason(left, right, amp)
    if (reason) return reason
  }
  return null
}

function possessiveReason(raw: string): string | null {
  if (TRAILING_POSSESSIVE_RE.test(raw)) return "possessive fragment ('s with nothing after)"
  if (TRAILING_QUOTE_RE.test(raw)) return 'trailing quote fragment'
  if (POSSESSIVE_SUPERLATIVE_RE.test(raw)) return 'possessive + superlative (a description)'
  const all = [...raw.matchAll(POSSESSIVE_SPLIT_RE_G)]
  if (all.length >= 2) return 'possessive fragment (two possessives)'
  const m = all[0]
  if (!m) return null
  const possessor = raw.slice(0, m.index)
  const ownerWords = words(possessor).filter((w) => w !== 'the')
  const loweredOwner = possessor.toLowerCase()
  if (
    ownerWords.length >= 2 ||
    ownerWords.some((w) => GENERIC_WORDS.has(w)) ||
    HOTEL_BRANDS.some((b) => loweredOwner.includes(b))
  ) {
    return "possessive fragment (a venue's 'X's Y')"
  }
  return null
}

function roomReason(ws: string[]): string | null {
  const joined = ws.join(' ')
  const last = ws[ws.length - 1]!
  if (ROOM_SUITE_FOR_RE.test(joined)) return 'hotel room/rate-plan row'
  if (TRAILING_INVENTORY.has(last)) return 'hotel room/floor inventory'
  if (ROOM_NOUNS.has(last) && ws.length <= 5 && ws.every((w) => ROOM_DESCRIPTORS.has(w) || ROOM_NOUNS.has(w))) {
    return 'hotel room/rate-plan row'
  }
  if (last === 'suite' && ws.filter((w) => w !== 'the').length <= 2) return 'hotel room category (<resort> Suite)'
  if (ROOM_LEAD_WORDS.has(ws[0]!) && ws.some((w) => ROOM_NOUNS.has(w))) return 'hotel room/rate-plan row'
  if (ws[0] === 'one' && ws.length > 1 && (ws[1] === 'bedroom' || ws[1] === 'bedrooms')) return 'hotel room/rate-plan row'
  return null
}

function suspectReason(raw: string, lowered: string, ws: string[]): string | null {
  if (SENTENCE_OPENERS.has(ws[0]!)) return `opens like a sentence (${pyRepr(ws[0]!)})`
  for (const [, right] of andSplits(raw)) {
    const rightFirst = words(firstSegment(right))
    if (rightFirst.length && !COMPOUND_TAIL_WORDS.has(rightFirst[0]!)) return "two names joined by 'and'/'&'"
  }
  if (` ${lowered} `.includes(' at ')) return "something 'at' a venue (event, outlet or person?)"
  if (` ${lowered} `.includes(' of ')) return "'X of Y' (part of a place, a person or a title?)"
  if (/\p{Nd}/u.test(raw)) return 'contains a number'
  const nouns = ws.map((w, i) => (OUTLET_NOUNS.has(w) ? i : -1)).filter((i) => i >= 0)
  if (new Set(nouns.map((i) => ws[i])).size >= 2) {
    const between = ws.slice(nouns[0]! + 1, nouns[nouns.length - 1]!)
    if (between.filter((w) => !GENERIC_WORDS.has(w) && !GLUE_WORDS.has(w) && w !== 'by').length >= 2) {
      return 'two venue names run together'
    }
  }
  if (ws.length > SUSPECT_MAX_TOKENS) return `long for a name (${ws.length} words)`
  return null
}

const junk = (reason: string): JunkVerdict => ({ tier: 'junk', reason })

/**
 * `now_places.junk.classify`. `nonVenuePhrases` is the extractor's noise
 * list: the city's area enum (spaces for hyphens) plus
 * `SUPPLEMENTARY_NON_VENUE_PHRASES`.
 */
export function classifyPlaceName(name: string, nonVenuePhrases: ReadonlySet<string>): JunkVerdict {
  const raw = splitWs(name ?? '').join(' ')
  if (!raw) return junk('empty name')
  const lowered = raw.toLowerCase()
  const ws = words(raw)
  if (!ws.length) return junk('empty name')
  const first = ws[0]!
  const last = ws[ws.length - 1]!

  if (URL_SLUG_RE.test(raw) || URLISH_RE.test(raw)) return junk('URL or slug as name')
  if (nonVenuePhrases.has(normalizeFull(raw))) return junk('an area or region name, not a venue')
  if (ws.length > MAX_TOKENS) return junk(`run-on text (${ws.length} words)`)

  const possessive = possessiveReason(raw)
  if (possessive) return junk(possessive)

  if (GENERIC_PHRASE_BLOCKLIST.has(lowered)) return junk('generic phrase, no proper noun')

  const flagException = LEADING_FLAG_EXCEPTIONS.some((e) => lowered.startsWith(e))
  if (LEADING_FLAG_WORDS.has(first) && !flagException) return junk(`leading descriptive/CTA word (${pyRepr(first)})`)
  if (first === 'new' && ws.length > 1 && GENERIC_WORDS.has(ws[1]!)) return junk("leading descriptive word ('new')")
  if (first === 'the' && ws.length > 1 && ['best', 'new', 'top'].includes(ws[1]!) && !flagException) {
    return junk(`leading descriptive word (${pyRepr(ws[1]!)})`)
  }

  if (PERSON_TITLE_RE.test(raw) || PERSON_TITLE_LEAD_RE.test(raw) || TITLE_LEAD_RE.test(raw)) {
    return junk("a person's job title, not a venue")
  }
  if (ADDRESS_TOKEN_RE.test(raw) || ADDRESS_TRAILING_RE.test(raw)) return junk('address/street fragment')
  if (AWARD_RE.test(raw) || ORDINAL_RE.test(raw)) return junk('award/ranking fragment')
  if (YEAR_LEAD_RE.test(raw)) return junk('year-led title (an edition or vintage)')
  if (MODERN_YEAR_RE.test(raw)) return junk('dated edition/event')
  if (eventWordHit(raw, lowered)) return junk('event/offer, not a venue')
  if (WEEKDAY_EVENT_RE.test(raw)) return junk('recurring event, not a venue')
  if (gatheringHit(raw)) return junk('competition/gathering, not a venue')
  if (ENDS_WITH_DAY_RE.test(raw) && ws.length > 1 && !['all', 'every', 'the'].includes(ws[ws.length - 2]!)) {
    return junk("a date or observance ('... Day')")
  }
  if (PRICE_RE.test(raw) || DURATION_RE.test(raw)) return junk('an offer (price or duration)')
  if (TIME_RE.test(raw)) return junk('a clock time, not a venue')
  if (LEVEL_RE.test(raw)) return junk('a floor/level locator')

  if (` ${lowered} `.includes(' at ')) {
    if (MONTH_AT_RE.test(raw)) return junk('date + event-at phrase')
    if (EVENT_AT_SUBSTRINGS.some((s) => lowered.includes(s))) return junk("event/description phrase ('... at ...')")
  }

  const room = roomReason(ws)
  if (room) return junk(room)

  if (TRAILING_NON_NAME_WORDS.has(last)) return junk(`product/caption word at the end (${pyRepr(last)})`)

  if (` ${lowered} `.includes(' of ') && ws.slice(0, 2).some((w) => CONCEPT_LEAD_WORDS.has(w))) {
    return junk('concept/trend title, not a venue')
  }

  const brands = new Set(BRAND_RES.filter(([, re]) => re.test(lowered)).map(([b]) => b))
  if (brands.size >= 2 && !BRAND_PAIR_EXCEPTIONS.some((pair) => [...brands].every((b) => pair.has(b)))) {
    return junk('two hotel brands run together')
  }

  const heads = ws.filter((w) => HEAD_NOUNS.has(w))
  if (heads.length !== new Set(heads).size) return junk('the same venue noun twice (two venues run together)')

  const concat = concatenationReason(raw, lowered)
  if (concat) return junk(concat)

  if (isTruncation(last)) return junk(`word cut off (${pyRepr(last)})`)

  const content = lowered
    .split(/\s+/u)
    .filter((w) => w && !GLUE_WORDS.has(w))
    .map(cleanToken)
  if (content.length && content.every((w) => GENERIC_WORDS.has(w))) return junk('generic phrase, no proper noun')

  const suspect = suspectReason(raw, lowered, ws)
  if (suspect) return { tier: 'suspect', reason: suspect }

  return { tier: null, reason: null }
}

/** The noise-list set from the area enum values (hyphens read as spaces). */
export function nonVenuePhraseSet(areaEnumValues: readonly string[]): Set<string> {
  return new Set([...areaEnumValues.map((v) => v.replace(/-/g, ' ')), ...SUPPLEMENTARY_NON_VENUE_PHRASES])
}

"""Text cleaning and the keyword-cue instrument.

The cue scorer is deliberately crude and deliberately transparent: a
weighted count of regex cues per facet value, title-weighted, with an
abstain when nothing fires or two values tie. It is *evidence*, not a
classifier -- every number it produces is reported next to the categories
whose mapping nobody disputes (Dining Offers -> offer, Reviews -> review,
Events -> event ...) so the reader can see how much to trust it before
reading it on the ambiguous ones. E2.1 replaces it with an LLM.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_TAG_RE = re.compile(r"<[^>]+>")
_SHORTCODE_RE = re.compile(r"\[/?[a-zA-Z_][^\]]{0,200}\]")
_WS_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def clean_html(raw: str) -> str:
    if not raw:
        return ""
    s = _SCRIPT_RE.sub(" ", raw)
    s = _TAG_RE.sub(" ", s)
    s = _SHORTCODE_RE.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ").replace(" ", " ").replace("﻿", "")
    return _WS_RE.sub(" ", s).strip()


TYPES = ("stay", "eat", "drink", "do", "wellness", "shop", "event", "editorial")
FORMATS = ("news", "event", "offer", "review", "listing", "guide", "feature", "heritage", "people", "city-guide", "opinion")

# --- type cues -------------------------------------------------------------
# (regex, weight). Word boundaries everywhere; all matching is case-insensitive.
TYPE_CUES: dict[str, list[tuple[str, float]]] = {
    "stay": [
        (r"\bhotels?\b", 1.0), (r"\bresorts?\b", 1.0), (r"\bvillas?\b", 1.0), (r"\bsuites?\b", 0.8),
        (r"\bstaycations?\b", 1.2), (r"\baccommodations?\b", 0.8), (r"\brooms? (rate|night)|\broom nights?\b", 1.0),
        (r"\bserviced apartments?\b|\baparthotel\b|\bresidences\b", 1.0), (r"\bglamping\b|\beco-?lodge\b|\bhostel\b", 1.0),
        (r"\bcheck-?in\b|\bnights? stay\b|\bper night\b", 0.8), (r"\bguests?\b", 0.3),
    ],
    "eat": [
        (r"\brestaurants?\b", 1.0), (r"\bmenus?\b", 0.8), (r"\bchefs?\b", 0.8), (r"\bdining\b|\bdine\b|\bdiners\b", 0.8),
        (r"\bcuisines?\b", 0.8), (r"\bdish(es)?\b", 0.7), (r"\bbrunch\b|\bbreakfast\b|\blunch\b|\bdinner\b", 0.6),
        (r"\bcaf[eé]s?\b|\bcoffee shop\b|\bbakery\b|\bpatisserie\b|\bdesserts?\b", 0.9), (r"\bculinary\b|\bgastronom", 0.7),
        (r"\bfood\b|\beater(y|ies)\b|\bbistro\b|\bwarung\b|\bfoodies?\b", 0.6), (r"\btasting menu\b|\bomakase\b|\bdegustation\b", 1.0),
        (r"\bpizza\b|\bpasta\b|\bsushi\b|\bramen\b|\bsteak\b|\bseafood\b|\bnoodles?\b|\bburgers?\b", 0.6),
    ],
    "drink": [
        (r"\bbars?\b", 1.0), (r"\bcocktails?\b|\bmixolog", 1.0), (r"\bwines?\b|\bsommelier\b", 0.8), (r"\bbeers?\b|\bbrewer(y|ies)\b|\bcraft beer\b", 0.8),
        (r"\bwhisk(e)?y\b|\bgin\b|\brum\b|\bvodka\b|\bsake\b|\barak\b|\bspirits\b", 0.6), (r"\bnightclub\b|\bnightlife\b|\bclubbing\b", 0.9),
        (r"\bpubs?\b|\blounges?\b|\bspeakeasy\b|\btaproom\b", 0.8), (r"\bbeach ?clubs?\b|\brooftop\b", 0.8), (r"\bhappy hour\b|\bsundowners?\b", 0.9),
    ],
    "wellness": [
        (r"\bspas?\b", 1.0), (r"\bmassages?\b", 1.0), (r"\bwellness\b", 0.9), (r"\byoga\b|\bpilates\b|\bmeditation\b", 1.0),
        (r"\bgyms?\b|\bfitness\b|\bworkouts?\b|\bcrossfit\b", 0.9), (r"\bretreats?\b|\bdetox\b|\bhealing\b", 0.8),
        (r"\bclinics?\b|\bhospitals?\b|\bdoctors?\b|\bmedical\b|\bdental\b|\baesthetic\b", 0.9), (r"\btreatments?\b|\btherap(y|ies|ist)\b", 0.7),
        (r"\bsalons?\b|\bbarbershop\b|\bnail bar\b|\bbeauty\b", 0.7),
    ],
    "shop": [
        (r"\bmalls?\b|\bshopping cent(re|er)s?\b|\bdepartment stores?\b", 1.0), (r"\bboutiques?\b", 0.9), (r"\bshopping\b|\bshoppers?\b", 0.8),
        (r"\bstores?\b|\bretail(er)?s?\b|\boutlets?\b", 0.7), (r"\bbrands?\b|\bcollections?\b|\bfashion\b|\bdesigners?\b", 0.5),
        (r"\bjewell?ery\b|\bhandbags?\b|\bsneakers?\b|\bapparel\b|\bhomewares?\b|\bfurniture\b", 0.6), (r"\bmarkets?\b|\bpasar\b|\bbazaar\b", 0.6),
        (r"\bartisans?\b|\bhandmade\b|\bcrafts?\b|\bbatik\b", 0.5),
    ],
    "do": [
        (r"\bmuseums?\b", 1.0), (r"\bgaller(y|ies)\b", 0.6), (r"\battractions?\b|\btheme parks?\b|\bzoo\b|\bsafari\b|\baquarium\b", 1.0),
        (r"\btours?\b|\bday trips?\b|\bexcursions?\b|\bcruises?\b", 0.8), (r"\btrekking\b|\bhik(e|ing)\b|\bclimb(ing)?\b|\bvolcano\b|\bwaterfalls?\b", 1.0),
        (r"\bdiving\b|\bsnorkell?ing\b|\bsurf(ing)?\b|\brafting\b|\bkayak|\bpaddle\b|\bsailing\b", 1.0), (r"\btemples?\b|\bpura\b", 0.6),
        (r"\bworkshops?\b|\bclass(es)?\b|\bcourses?\b|\blessons?\b", 0.6), (r"\bthings to do\b|\bactivit(y|ies)\b|\badventures?\b", 0.8),
        (r"\bgolf\b|\bcycling\b|\bpadel\b|\bbowling\b|\bkarting\b|\bplaygrounds?\b", 0.7), (r"\bparks?\b|\bgardens?\b|\bbeach(es)?\b|\bislands?\b", 0.4),
    ],
    "event": [
        (r"\bfestivals?\b", 1.0), (r"\bconcerts?\b|\bgigs?\b|\blive music\b|\bDJ\b|\bline-?up\b", 0.9), (r"\bexhibitions?\b|\bart fair\b|\bbiennale\b", 0.9),
        (r"\bperformances?\b|\btheat(re|er)\b|\bballet\b|\bopera\b|\bdance show\b|\bstand-?up\b|\bcomedy\b", 0.8),
        (r"\bconferences?\b|\bsummits?\b|\bforums?\b|\bexpos?\b|\bseminars?\b|\bsymposium\b", 0.9), (r"\bscreenings?\b|\bpremieres?\b|\bfilm festival\b", 0.9),
        (r"\btournaments?\b|\bmarathons?\b|\bfun run\b|\brace\b|\bchampionships?\b|\bmatch(es)?\b", 0.8), (r"\bcharity (gala|ball|night|dinner)\b|\bfundrais", 0.8),
        (r"\btickets?\b|\bRSVP\b|\bregister (now|here)\b|\bregistration\b", 0.8), (r"\bwill (be held|take place)\b|\btakes place\b|\bis held\b", 1.0),
        (r"\bpop-?ups?\b|\btrunk show\b|\bopen house\b", 0.7),
    ],
    "editorial": [
        (r"\bopinion\b|\bcolumn(ist)?\b|\beditor'?s? (note|letter)\b", 1.0), (r"\binterview\b|\bin conversation\b|\bQ&A\b|\bprofile\b", 0.8),
        (r"\bhistory\b|\bheritage\b|\bcolonial\b|\bcentury\b|\bancient\b|\bhistorical\b", 0.7), (r"\beconomy\b|\bgovernment\b|\bpolicy\b|\bpolitic", 0.8),
        (r"\bschools?\b|\buniversit(y|ies)\b|\bstudents?\b|\bcurriculum\b|\beducation\b", 0.8), (r"\bcommunity\b|\bcharity\b|\bfoundation\b|\bNGO\b|\bvolunteers?\b", 0.6),
        (r"\bexpats?\b|\bexpatriates?\b|\bdiplomat(ic|s)?\b|\bambassadors?\b|\bembassy\b", 0.8), (r"\bsustainab|\bplastic\b|\brecycl|\bclimate\b|\benvironment", 0.6),
        (r"\btraffic\b|\bMRT\b|\bflood(s|ing)?\b|\bcity administration\b|\bgovernor\b", 0.8), (r"\bwe should\b|\bI think\b|\bin my view\b|\bwhy (we|you|it)\b", 0.6),
    ],
}

# --- format cues -----------------------------------------------------------
FORMAT_CUES: dict[str, list[tuple[str, float]]] = {
    "offer": [
        (r"\bpromo(tion)?s?\b", 1.0), (r"\bpackages?\b", 1.0), (r"\boffers?\b", 0.8), (r"\bdeals?\b", 0.9), (r"\bdiscounts?\b|\d+\s?% off\b|\bsave (up to )?\d+", 1.0),
        (r"\bIDR\s?[\d.,]+|\bRp\.?\s?[\d.,]+|\bvouchers?\b", 1.0), (r"\bper (person|pax|couple|night|room)\b|\bnett\b|\+\+", 0.9),
        (r"\bvalid (until|through|from|for)\b|\bavailable (until|from|through)\b|\bbook (now|your)\b|\bbookings?\b|\breservations?\b", 0.8),
        (r"\bstarting (from|at)\b|\bpriced? at\b|\bfor only\b|\binclusive of\b|\binclud(es|ing)\b", 0.6), (r"\bbuy \d+ get \d+\b|\ball-?you-?can-?eat\b|\bfree flow\b", 0.9),
        (r"\bfestive (package|programme|program|season|menu|offer)|\bstaycation\b|\bgetaway\b|\bescape\b", 0.7), (r"\bmembers?\b|\bloyalty\b|\bprivileges?\b|\bexclusive\b", 0.4),
        (r"\bhigh tea\b|\bafternoon tea\b|\bsunday brunch\b|\bbuffet\b|\bset menu\b|\bspecial menu\b", 0.5),
    ],
    "event": [
        (r"\b(\d{1,2}(st|nd|rd|th)?\s+(of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)|(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(st|nd|rd|th)?)\b", 0.8),
        (r"\bwill (be held|take place|run|perform|present|feature|host)\b|\btakes place\b|\bis (being )?held\b|\bruns? (until|through|from)\b", 1.0),
        (r"\bfestivals?\b|\bconcerts?\b|\bexhibitions?\b|\bperformances?\b|\bscreenings?\b|\bconferences?\b|\btournaments?\b|\bmarathons?\b", 0.8),
        (r"\btickets?\b|\bRSVP\b|\bline-?up\b|\bperformers?\b|\bheadlin(er|ing)\b|\bregister\b", 0.9), (r"\bthis (weekend|saturday|sunday|friday|month)\b|\bupcoming\b|\bsave the date\b", 0.8),
        (r"\bopening (night|ceremony)\b|\bgala\b|\bcharity (ball|night)\b|\bfun run\b", 0.8),
    ],
    "news": [
        (r"\bopens?\b|\bopening\b|\bnow open\b|\breopens?\b|\bsoft-?launch", 1.0), (r"\blaunch(es|ed|ing)?\b", 0.9), (r"\bappoint(s|ed|ment)\b|\bnamed\b|\bjoins\b|\bpromoted\b", 1.0),
        (r"\bannounc(es|ed|ement)\b|\bintroduc(es|ed|ing)\b|\bunveil(s|ed)\b|\bwelcomes\b|\bdebuts?\b", 0.9), (r"\bcelebrates?\b|\banniversary\b|\binaugurat", 0.6),
        (r"\bpartners? with\b|\bpartnership\b|\bcollaborat|\bsigns?\b|\bMoU\b|\bagreement\b", 0.7), (r"\bwins?\b|\bawarded\b|\breceives?\b|\brecogni[sz]ed\b|\bawards?\b", 0.7),
        (r"\bnewly\b|\bbrand-?new\b|\blatest\b|\bnew (menu|chef|look|outlet|branch|store|flagship|concept|restaurant|bar|hotel|resort|spa)\b", 0.6), (r"\bexpands?\b|\bexpansion\b|\brebrand", 0.7),
        (r"\bpresents\b|\bbrings\b|\breturns\b|\bis back\b|\barrives\b|\bcomes to\b|\blands in\b|\bmakes its debut\b|\bnow serving\b|\bopened its doors\b|\bhas opened\b|\bhas (just )?launched\b", 0.8),
        (r"\bappointed\b|\btakes (the )?helm\b|\bnew general manager\b", 0.9),
    ],
    "review": [
        (r"\breview(ed|s)?\b", 1.2), (r"\bwe (tried|ordered|sampled|tasted|visited|started|opted|loved|went|sat|were|had|chose|shared|finished|began)\b|\bI (tried|ordered|had|loved|went|visited|opted|found|was|chose|could|must|would)\b", 0.9),
        (r"\bmy (visit|meal|stay|favourite|favorite|verdict|palate|companion|plate|dining|first|second)\b|\bour (visit|meal|stay|table|verdict|server|waiter|waitress|dining|first|second|plates?|dishes|order)\b", 0.9),
        (r"\bverdict\b|\bhighlights? of the (meal|menu|night)\b|\bstandout\b|\bhits? and misses\b|\bmust-?try\b|\bworth (the|a|every)\b", 0.8),
        (r"\bdelicious\b|\bflavou?rs?\b|\btextures?\b|\bportions?\b|\bplating\b|\bcrispy\b|\btender\b|\bcreamy\b|\bsucculent\b|\bjuicy\b|\bmoist\b", 0.35),
        (r"\bthe service was\b|\bthe ambiance\b|\bthe ambience\b|\bthe atmosphere\b|\bcame with\b|\bserved with\b|\bpaired with\b|\barrived\b", 0.5),
    ],
    "listing": [
        (r"\b(19|20)\d\d\b", 0.8), (r"\[updated\]|\bupdated\b", 1.0), (r"\b(\d+|ten|five|seven|eight|nine|six|twelve|fifteen|twenty) (best|of the best|great|fabulous|top|must|new|places|spots|restaurants|bars|caf[eé]s|hotels|villas|spas|things|ways|reasons)\b", 1.2),
        (r"\b(best|top) (\d+ )?(restaurants|bars|caf[eé]s|hotels|villas|spas|places|spots|brunch|breakfast|rooftops?|beach clubs|malls|things to do|day trips)\b", 1.0), (r"\bround-?up\b|\bour picks\b|\bwhere to (eat|drink|stay|shop|go|celebrate)\b", 0.9),
        (r"\bthis (month|week|weekend|season|ramadan|christmas|easter|valentine)\b|\bchinese new year\b|\bramadan\b|\biftar\b|\bchristmas\b|\bnew year'?s? eve\b", 0.5),
    ],
    "guide": [
        (r"\bguide\b", 1.0), (r"\bhow to\b|\bwhat to (do|eat|see|know|expect)\b|\bwhere to\b", 0.9), (r"\beverything you need to know\b|\bultimate\b|\bbeginner'?s\b|\b101\b", 0.9),
        (r"\btips\b|\bdos and don'?ts\b|\bchecklist\b|\bexplained\b", 0.8), (r"\bthings to do\b|\bplaces to (visit|see|go)\b", 0.7),
    ],
    "feature": [
        (r"\bthe (story|history|rise|art|life|world|future|making|meaning|secret|secrets) of\b", 0.7), (r"\binside\b|\bbehind the scenes\b|\bin depth\b|\ba (look|closer look|journey|day) (at|into|through|in the life)\b", 0.7),
        (r"\bexplor(es|ing)\b|\buncover|\bdiscover(ing)?\b|\brediscover", 0.4),
    ],
    "heritage": [
        (r"\bhistory\b|\bhistoric(al)?\b", 1.0), (r"\bheritage\b", 1.0), (r"\bcolonial\b|\bBatavia\b|\bDutch East Indies\b|\bVOC\b|\bDutch\b", 1.0), (r"\b(1[5-9]\d\d|18th|19th|17th|16th) century\b|\bcentur(y|ies)\b", 0.8),
        (r"\bancient\b|\bkingdom\b|\bdynasty\b|\bempire\b|\bmajapahit\b|\bsultan", 0.9), (r"\blegends?\b|\bmyths?\b|\bfolklore\b|\bancestors?\b|\bsacred\b|\britual", 0.7),
        (r"\bbuilt in\b|\bfounded in\b|\bdates back\b|\brestor(ed|ation)\b|\bconservation\b", 0.8), (r"\bold town\b|\bkota tua\b|\bmuseums?\b|\bmonuments?\b", 0.6),
    ],
    "people": [
        (r"\binterview\b|\bQ&A\b|\bin conversation with\b|\btalks? (to|with)\b|\bsits? down with\b|\bchats? with\b|\bcatch(es)? up with\b", 1.2), (r"\bmeet\b|\bprofile\b|\bfive minutes with\b|\bminutes with\b|\bget to know\b", 0.9),
        (r"\bfounder\b|\bCEO\b|\bgeneral manager\b|\bdirector\b|\bartist\b|\bdesigner\b|\bauthor\b|\bchef\b|\bambassador\b|\bentrepreneur\b", 0.4), (r"\bhe (says|explains|tells|recalls|adds)\b|\bshe (says|explains|tells|recalls|adds)\b|\bsays\b|\bexplains\b|\brecalls\b", 0.5),
        (r"\bborn in\b|\bgrew up\b|\bher journey\b|\bhis journey\b|\bcareer\b|\bpassion\b", 0.5),
    ],
    "city-guide": [
        (r"\btravel(ling|ing|ler|lers)?\b", 0.7), (r"\btrips?\b|\bgetaways?\b|\bescape to\b|\bweekend in\b|\bdays? in\b|\bitinerar(y|ies)\b|\bjourney to\b|\broad trip\b", 0.9),
        (r"\bdestinations?\b|\bexplor(e|ing) (the|indonesia|bali|java|sumatra|lombok|flores|singapore|japan|australia)\b|\bisland hopping\b", 0.9), (r"\bwhere to (stay|eat|go)\b|\bwhat to (see|do)\b|\bhighlights\b", 0.5),
        (r"\bflights?\b|\bairport\b|\bferr(y|ies)\b|\bvisa\b|\bdomestic\b|\boverseas\b|\babroad\b", 0.5),
    ],
    "opinion": [
        (r"\bopinion\b|\bcolumn\b|\beditorial\b|\bop-?ed\b", 1.2), (r"\bwe (should|must|need to|ought to)\b|\bI (think|believe|argue|wonder|would argue)\b|\bin my (view|opinion|experience)\b", 1.0),
        (r"\bwhy (we|you|it|the|is|do|does|are|jakarta|bali|indonesia)\b|\bshould\b|\bought\b|\bdebate\b|\bargu(e|ment)\b", 0.5), (r"\?\s*$", 0.6),
        (r"\bthe problem (with|is)\b|\bthe trouble with\b|\bthe case for\b|\bthe case against\b|\bhonestly\b|\blet'?s be honest\b", 0.9),
    ],
}


def _compile(cues: dict[str, list[tuple[str, float]]]) -> dict[str, list[tuple[re.Pattern[str], float]]]:
    return {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in cues.items()}


_TYPE = _compile(TYPE_CUES)
_FORMAT = _compile(FORMAT_CUES)

# F111/F113: measured against Hansel's 253 adjudicated type/format verdicts,
# this instrument's auto-apply bands (0.66/0.45) were WORSE than its review
# bands (0.61), and the concrete failure mode was spot-checked, not guessed --
# "Italy -- The Land of Wines" (an editorial history of Italian wine) scored
# `drink`; a whisky market-entry business story scored `drink`; a skincare
# founder profile scored `wellness`. In every case a type word saturating
# BODY text was read as "the article is about a venue of that type" when it
# was really "the article's topic happens to share this vocabulary."
#
# TITLE_W/LEAD_W/BODY_W are kept at their ORIGINAL values -- an earlier draft
# of this fix raised them (to lean harder on title position, the way
# location's own `title_match` mechanism does at 0.97), but that uniformly
# inflates every raw score, and `_decide`'s "confident" bit is an ABSOLUTE
# margin threshold (`margin >= 2 * min_margin`), not a relative one. Measured
# effect: previously-abstaining items started crossing that absolute
# threshold on marginally stronger title matches, most of them wrong (9 of 13
# newly-decisive former-abstains in this measurement landed in the
# auto-applied CUE_CONFIDENT band, only 3 correct) -- i.e. rescaling the head
# zones alone made the instrument MORE willing to auto-apply, the opposite of
# what F111/F113 need. Left unchanged here; `min_score`/`min_margin` would
# need to move in lockstep with any future zone-weight change to avoid this.
#
# The body window shrinks from 2,600 to 1,200 characters (matching the
# "title + dek + body[:1600]" budget already used for article embeddings,
# F94) -- less body text scanned means less room for unrelated topic
# vocabulary to accumulate. The larger change is `_combine_head_body` below:
# body evidence can no longer manufacture a decision by itself, only
# corroborate one the title/lead already support.
TITLE_W, LEAD_W, BODY_W = 3.0, 1.5, 1.0
CAP_PER_CUE = 3  # occurrences counted per cue per zone


@dataclass
class CueResult:
    value: str | None                   # argmax or None (abstain)
    scores: dict[str, float] = field(default_factory=dict)
    margin: float = 0.0
    confident: bool = False


def _score(zones: list[tuple[str, float]], cues: dict[str, list[tuple[re.Pattern[str], float]]]) -> dict[str, float]:
    out = {k: 0.0 for k in cues}
    for text, zw in zones:
        if not text:
            continue
        for k, pats in cues.items():
            s = 0.0
            for pat, w in pats:
                n = 0
                for _ in pat.finditer(text):
                    n += 1
                    if n >= CAP_PER_CUE:
                        break
                s += n * w
            out[k] += s * zw
    return out


# **A candidate with ZERO title-zone support can never decide anything by
# itself.** This is the direct, load-bearing implementation of "a type word
# in the title is far stronger evidence than one in the body" (location's own
# `title_match` mechanism measured 0.97 on the same human-labelled set,
# against `lead_only_match`'s 0.55 -- deliberately kept below the auto-apply
# gate). Without title support, lead+body combined are capped at
# NO_TITLE_CEILING (2.0), which sits below min_score (2.5) in both
# score_type/score_format_full -- so no amount of lead- or body-zone density,
# however broad or repetitive, can single-handedly cross the decision
# threshold. This is a hard gate, not a soft weighting: an earlier draft only
# down-weighted the body zone and left an uncapped lead zone, which still let
# a lead paragraph dense with off-topic vocabulary decide outright (found on
# an adversarial case built to mirror F111's own examples -- a generic,
# venue-less title whose lead alone was saturated with `drink` words still
# won). Once a candidate DOES have title support, lead and body may each
# corroborate it (up to a multiple of what the more-trusted zone already
# found, plus a small flat allowance) but still cannot run away on their own.
#
# Trade-off, stated plainly: a minority of genuinely correct venue-type
# articles whose title has no cue word at all (e.g. a piece titled only by
# its own brand name, with the venue-type evidence appearing solely in the
# lead or body) will now abstain instead of classify, where the old
# instrument would have gotten them right. This trades away some recall on
# that slice. Accepted because F111/F113 measured this instrument's problem
# as precision, not recall -- CUE_CONFIDENT (0.93) and CUE_FIRED (0.72) were
# already *worse* than the abstain/category-prior bands, i.e. the instrument
# was already over-firing, not under-firing, so a change that trades firing
# rate for correctness-when-firing is the right direction even though it is
# not free.
NO_TITLE_CEILING = 2.0
LEAD_CAP_MULT, LEAD_CAP_BASE = 2.0, 1.5
BODY_CAP_MULT, BODY_CAP_BASE = 1.5, 1.5


def _score_head_body(
    title: str, text: str, cues: dict[str, list[tuple[re.Pattern[str], float]]]
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Returns (title, lead, body): each zone's raw score, already
    zone-weighted, kept separate (rather than one flat sum) so the decision
    step can treat lead and body as corroborating a more-trusted zone rather
    than sufficient on their own -- see `_combine_head_body`."""
    title_scores = _score([(title, TITLE_W)], cues)
    lead_scores = _score([(text[:400], LEAD_W)], cues)
    body_scores = _score([(text[400:1600], BODY_W)], cues)
    return title_scores, lead_scores, body_scores


def _combine_head_body(title_scores: dict[str, float], lead_scores: dict[str, float], body_scores: dict[str, float]) -> dict[str, float]:
    out = {}
    for k in title_scores:
        t = title_scores.get(k, 0.0)
        if t <= 0:
            # No title anchor at all: lead+body together cannot manufacture
            # a decision on their own (see NO_TITLE_CEILING above).
            out[k] = min(lead_scores.get(k, 0.0) + body_scores.get(k, 0.0), NO_TITLE_CEILING)
            continue
        lead_capped = min(lead_scores.get(k, 0.0), LEAD_CAP_MULT * t + LEAD_CAP_BASE)
        head = t + lead_capped
        body_capped = min(body_scores.get(k, 0.0), BODY_CAP_MULT * head + BODY_CAP_BASE)
        out[k] = head + body_capped
    return out


def _decide(scores: dict[str, float], min_score: float, min_margin: float) -> CueResult:
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top, second = ranked[0], ranked[1] if len(ranked) > 1 else (None, 0.0)
    margin = top[1] - second[1]
    if top[1] < min_score or margin < min_margin:
        return CueResult(None, scores, margin, False)
    return CueResult(top[0], scores, margin, margin >= 2 * min_margin)


def score_type(title: str, text: str) -> CueResult:
    t, l, b = _score_head_body(title, text, _TYPE)
    return _decide(_combine_head_body(t, l, b), min_score=2.5, min_margin=1.0)


def score_format(title: str, text: str) -> CueResult:
    t, l, b = _score_head_body(title, text, _FORMAT)
    scores = _combine_head_body(t, l, b)
    # a title-level period stamp makes 'listing' beat 'guide' by construction
    return _decide(scores, min_score=2.5, min_margin=1.0)


# --- location gazetteer ----------------------------------------------------
# Built from the seed location tree at runtime (labels + aliases) plus a few
# spelling variants the seed does not carry. Matching is title+lead only:
# body mentions of "Bali" in a Jakarta hotel piece are noise, title mentions
# are signal.
#
# F95: a location word embedded in an Indonesian dish name ("nasi bali",
# "siomay bandung", "soto Padang", "Sate Khas Senayan") is not a place
# mention -- it is a menu item, and this naming convention (food noun +
# region name) is routine in this corpus, not an edge case. Three fixes were
# considered:
#   1. A full dish-name stoplist ("nasi bali", "sate senayan", ...) -- exact
#      and simple, but it is a phrase-per-(dish, place) pairing that needs a
#      new entry for every new dish/place combination the corpus invents.
#   2. Require a preceding preposition ("in Bali", "at Ubud") -- generalises
#      better, but this corpus's own house style drops the preposition
#      constantly in headlines and possessives ("NOW! Bali Guide", "Ubud's
#      Newest Cafe", "Best Restaurants Canggu (2026)"); requiring one would
#      suppress real title-zone location signal, trading a false-positive
#      bug for a false-negative one.
#   3. A general food-context detector -- most powerful, but opaque and the
#      likeliest to fail quietly, which cuts against this module's stated
#      design (a crude, transparent, inspectable cue instrument).
# Chosen: option 1's structural generalisation -- a curated, closed list of
# Indonesian food/dish nouns (_DISH_NOUNS) that, when a location match is
# immediately preceded by one of them (optionally through a style modifier
# like "khas"/"ala"/"gaya"), suppresses *that occurrence* of the match. It
# is maintenance-light (one list, not one entry per dish x place), fires
# only on the narrow noun-adjacency pattern that actually causes the bug,
# and leaves every other path -- "cuisine of Sulawesi", "Best Restaurants in
# Canggu", "A Weekend in Bali", generic "food"/"cuisine"/"street" -- alone,
# because those are not in the dish-noun set and are usually genuine
# location signal, not a menu item. What this gives up: on the rare article
# whose *only* textual anchor for a place is a branded dish name that
# happens to also be true editorial content about that place, the mention
# is dropped -- accepted, because precision matters more than recall here
# (F95 spec) and other facets (place-extraction, editor review) can still
# recover it.
_DISH_NOUNS = {
    "nasi", "sate", "satay", "soto", "bakso", "ayam", "es", "gudeg", "rendang", "bebek",
    "pempek", "empek", "empek-empek", "mie", "mi", "sop", "gado-gado", "gado", "martabak",
    "kerak", "batagor", "siomay", "lontong", "ketoprak", "pecel", "tahu", "tempe",
    "krupuk", "kerupuk", "sambal", "gulai", "opor", "semur", "urap", "pepes",
    "otak-otak", "klepon", "dodol", "wedang", "jamu", "kue", "bubur", "rawon", "empal",
    "krecek", "tongseng", "iga", "coto", "konro", "pallubasa", "rujak", "asinan",
    "kupat", "ketupat", "laksa", "kwetiau", "bihun", "capcay",
}
# style modifiers / generic F&B-brand connectors that can sit between the
# dish noun and the region name ("sate khas Senayan", "nasi ala Padang",
# "Sate House Senayan"); at most one is skipped.
_DISH_MODIFIERS = {"khas", "ala", "gaya", "house"}
_WORD_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _is_dish_context(zone: str, match_start: int) -> bool:
    """True if the word immediately before `match_start` (skipping at most
    one style modifier) is an Indonesian food/dish noun -- i.e. the location
    word is functioning as part of a dish name, not as a place mention."""
    toks = _WORD_TOKEN_RE.findall(zone[:match_start])[-2:]
    if not toks:
        return False
    idx = len(toks) - 1
    if toks[idx].lower() in _DISH_MODIFIERS:
        idx -= 1
    return idx >= 0 and toks[idx].lower() in _DISH_NOUNS


def build_location_matcher(seed_terms: list[dict]) -> list[tuple[re.Pattern[str], str]]:
    pats: list[tuple[re.Pattern[str], str]] = []
    skip = {"indonesia", "other", "international"}  # roots: never inferred from a mention
    for t in seed_terms:
        if t["slug"] in skip:
            continue
        names = [t["label"]] + list(t.get("aliases") or [])
        for n in names:
            n = re.sub(r"\s*\(.*?\)", "", n).strip()
            if len(n) < 3:
                continue
            pats.append((re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", re.I), t["slug"]))
    return pats


def match_locations(title: str, lead: str, matcher: list[tuple[re.Pattern[str], str]]) -> list[str]:
    hits: list[str] = []
    zone = f"{title} || {lead}"
    for pat, slug in matcher:
        if slug in hits:
            continue
        for m in pat.finditer(zone):
            if _is_dish_context(zone, m.start()):
                continue
            hits.append(slug)
            break
    return hits


# --- period stamp (listing vs guide boundary, E1.4 decision 16) -------------
_YEAR_IN_TITLE = re.compile(r"\b(20[12]\d)\b")
_UPDATED = re.compile(r"\[\s*updated\s*\]|\bupdated\b", re.I)
_SEASONAL = re.compile(r"\b(ramadan|iftar|christmas|new year|valentine|easter|chinese new year|lunar new year|festive|eid|lebaran|halloween|nyepi|galungan)\b", re.I)


def period_stamp(title: str) -> str | None:
    if _YEAR_IN_TITLE.search(title):
        return "year"
    if _UPDATED.search(title):
        return "updated"
    if _SEASONAL.search(title):
        return "seasonal"
    return None


_ROUNDUP = re.compile(r"\b(\d+|ten|five|seven|eight|nine|six|twelve|fifteen|twenty|best|top)\b.*\b(best|places|spots|restaurants|bars|caf[eé]s|hotels|villas|spas|things|ways|reasons|picks|ideas|destinations|beaches|brunches)\b", re.I)


def is_roundup(title: str) -> bool:
    return bool(_ROUNDUP.search(title))


WORD_RE = re.compile(r"[a-z][a-z'\-]+")
STOP = set("""a an and are as at be but by for from has have he her his i if in into is it its of on or our she that the their
there these they this to was we were what when where which who will with you your about after all also am any been being
can could did do does doing down during each few he'd he'll he's here how just me more most my no nor not now off once only
other out over own same so some such than then through too under until up very while why would yet said says one two new
jakarta bali indonesia indonesian balinese now""".split())


def tokens(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(text.lower()) if w not in STOP and len(w) > 2]


_FP_RE = re.compile(r"\b(I|I'm|I've|we|we're|we've|my|our|me|us)\b")
_WORDS_RE = re.compile(r"\b\w+\b")


def first_person_density(text: str) -> float:
    """First-person pronouns per 1,000 words over the body -- the single
    most reliable lexical marker of a review or a column versus a press
    release rewrite."""
    words = len(_WORDS_RE.findall(text))
    if words < 40:
        return 0.0
    return 1000.0 * len(_FP_RE.findall(text)) / words


def score_format_full(title: str, text: str) -> CueResult:
    f_t, f_l, f_b = _score_head_body(title, text, _FORMAT)
    scores = _combine_head_body(f_t, f_l, f_b)
    fp = first_person_density(text)
    # First person means "review" only when a venue is the subject; in an
    # interview, a column or a travel essay it means people/opinion/feature.
    t_t, t_l, t_b = _score_head_body(title, text, _TYPE)
    tscores = _combine_head_body(t_t, t_l, t_b)
    venue_like = max(tscores[k] for k in ("stay", "eat", "drink", "wellness", "shop")) >= 3.0 and tscores["editorial"] < 3.0
    interview_like = scores["people"] >= 3.0
    if fp >= 8:
        if venue_like and not interview_like:
            scores["review"] += 2.0
        else:
            scores["opinion"] += 0.8
            scores["feature"] += 0.8
    if fp >= 15:
        if venue_like and not interview_like:
            scores["review"] += 1.5
        else:
            scores["opinion"] += 1.0
            scores["feature"] += 0.5
    if fp >= 25 and not interview_like:
        scores["opinion"] += 1.5
    return _decide(scores, min_score=2.5, min_margin=1.0)


FEATURE_VERSION = 7  # F111/F113: title-anchored, lead/body-capped type/format cue scoring.
# NOTE: bumped to 7, not 6 -- a `.cache/features-*-v6.json` pair already existed with a
# very recent mtime when this change landed (a parallel F101 location-promotion agent
# was editing this same package concurrently per the task brief), and its content
# (uncapped type_scores in the double digits) shows it was generated from the PRE-fix
# scoring, not this one. Reusing 6 would have made a stale, wrong-code cache look valid
# for this change. Left that file alone (not mine to delete mid-flight); picked the next
# number instead so this change always forces a fresh cache regardless of what 6 means
# elsewhere.

VENUE_TYPES = ("stay", "eat", "drink", "wellness", "shop")  # exclude_same = true in type_relations.json
DECAY_CLASS = {"news": "short", "event": "short", "offer": "short", "review": "medium", "listing": "medium", "opinion": "medium",
               "guide": "evergreen", "feature": "evergreen", "heritage": "evergreen", "people": "evergreen", "city-guide": "evergreen"}


def article_features(title: str, text: str, loc_matcher: list[tuple[re.Pattern[str], str]] | None = None) -> dict:
    t = score_type(title, text)
    f = score_format_full(title, text)
    return {
        "type": t.value, "type_scores": {k: round(v, 2) for k, v in t.scores.items() if v}, "type_margin": round(t.margin, 2),
        "format": f.value, "format_scores": {k: round(v, 2) for k, v in f.scores.items() if v}, "format_margin": round(f.margin, 2),
        "fp_density": round(first_person_density(text), 1),
        "period_stamp": period_stamp(title), "roundup": is_roundup(title),
        "locations": match_locations(title, text[:400], loc_matcher) if loc_matcher else [],
    }

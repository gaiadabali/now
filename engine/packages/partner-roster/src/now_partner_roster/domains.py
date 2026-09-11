"""Domain normalization, exclusion classification and org-name/type
heuristics. Pure functions, no I/O — kept separate from `pipeline.py` so
each rule is independently unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# href repair
# ---------------------------------------------------------------------------

# Observed in the real corpus (e.g. wp_id 456, 6029, 6583...): a stray
# "http://" was prepended in front of an already-absolute "https://..." URL
# by a copy/paste through an old editor plugin, producing
# "http://https://www.ismaya.com/...". `urlsplit` parses that as netloc
# "https:" with no host, which would otherwise show up as a bogus domain.
# Unwrap the outer scheme and keep the inner absolute URL.
_DOUBLE_SCHEME_RE = re.compile(r"^https?://(https?://.+)$", re.IGNORECASE)


def repair_href(href: str) -> str:
    href = href.strip()
    m = _DOUBLE_SCHEME_RE.match(href)
    if m:
        return m.group(1)
    return href


def extract_netloc(href: str) -> str | None:
    """Return the lowercased netloc (host[:port]) for an absolute http(s)
    URL, or None for anything else (relative paths, mailto:, tel:,
    javascript:, empty/malformed hrefs)."""
    href = repair_href(href)
    parts = urlsplit(href)
    if parts.scheme.lower() not in ("http", "https"):
        return None
    netloc = parts.netloc.lower()
    if not netloc:
        return None
    # strip a userinfo@ prefix if present (not seen in this corpus, but cheap
    # to be defensive) and a port suffix — org identity doesn't care about it.
    netloc = netloc.rsplit("@", 1)[-1]
    netloc = netloc.split(":", 1)[0]
    return netloc


def strip_www(netloc: str) -> str:
    return netloc[4:] if netloc.startswith("www.") else netloc


# ---------------------------------------------------------------------------
# our own site's domains — outbound "links" to these are internal, not partners
# ---------------------------------------------------------------------------

OWN_SITE_SUFFIXES = ("nowjakarta.co.id", "nowbali.co.id")


def is_own_site(netloc: str) -> bool:
    bare = strip_www(netloc)
    return any(bare == suf or bare.endswith("." + suf) for suf in OWN_SITE_SUFFIXES)


# ---------------------------------------------------------------------------
# exclusion categories: social / stock / shortener / utility
# (+ "internal" for our own domains, handled separately above but grouped in
# the same exclusion report for a single reviewable list)
# ---------------------------------------------------------------------------

SOCIAL_DOMAINS = {
    "instagram.com", "facebook.com", "twitter.com", "x.com", "threads.net",
    "tiktok.com", "linkedin.com", "pinterest.com", "youtube.com", "youtu.be",
    "open.spotify.com", "linktr.ee", "line.me",
}

STOCK_DOMAINS = {
    "unsplash.com", "pexels.com", "pixabay.com", "shutterstock.com",
    "istockphoto.com", "gettyimages.com", "freepik.com", "flickr.com",
}

SHORTENER_DOMAINS = {
    "bit.ly", "goo.gl", "maps.app.goo.gl", "tinyurl.com", "ow.ly", "buff.ly",
    "t.co", "rebrand.ly", "cutt.ly", "chope.app.link", "app.link",
    "getcraft.go2cloud.org", "lnk.bio", "s.id",
}
# app.link / onelink.me are Branch.io deep-link redirectors: one string per
# advertiser but the resolvable destination isn't recoverable offline, so
# they're excluded as a category rather than assigned to an org.
SHORTENER_SUFFIXES = ("onelink.me", "go2cloud.org")

UTILITY_DOMAINS = {
    "wa.me", "api.whatsapp.com", "google.com", "www.google.com",
    "maps.google.com", "docs.google.com", "drive.google.com", "forms.gle",
    "play.google.com", "apps.apple.com", "schema.org", "gravatar.com",
    "wordpress.com", "wp.com", "w.org", "en.wikipedia.org", "wikipedia.org",
    "mailchimp.com", "eepurl.com", "zoom.us", "calendly.com",
}


@dataclass(frozen=True)
class Classification:
    excluded: bool
    reason: str | None  # "social" | "stock" | "shortener" | "utility" | "internal" | None


def classify(netloc: str) -> Classification:
    bare = strip_www(netloc)
    if is_own_site(netloc):
        return Classification(True, "internal")
    if bare in SOCIAL_DOMAINS or any(bare.endswith("." + d) for d in SOCIAL_DOMAINS):
        return Classification(True, "social")
    if bare in STOCK_DOMAINS or any(bare.endswith("." + d) for d in STOCK_DOMAINS):
        return Classification(True, "stock")
    if (
        bare in SHORTENER_DOMAINS
        or any(bare.endswith("." + d) for d in SHORTENER_DOMAINS)
        or any(bare == suf or bare.endswith("." + suf) for suf in SHORTENER_SUFFIXES)
    ):
        return Classification(True, "shortener")
    if bare in UTILITY_DOMAINS or any(bare.endswith("." + d) for d in UTILITY_DOMAINS):
        return Classification(True, "utility")
    return Classification(False, None)


# ---------------------------------------------------------------------------
# root-domain extraction (poor-man's public-suffix-list — no new dependency,
# scoped to the multi-label suffixes actually observed or plausible in this
# corpus, per CLAUDE.md/ticket "no new dependencies without spec saying so")
# ---------------------------------------------------------------------------

_MULTI_LABEL_SUFFIXES = {
    "co.id", "com.id", "or.id", "net.id", "ac.id", "go.id", "sch.id", "web.id",
    "my.id", "biz.id",
    "co.uk", "com.au", "co.jp", "com.sg",
}

# subdomain labels that are generic marketing/booking portals rather than a
# distinct property — a hit here means "this is the group itself", not a
# sub-property.
_GENERIC_SUBDOMAIN_LABELS = {
    "www", "all", "book", "booking", "reservations", "shop", "blog", "news",
    "careers", "help", "support", "m", "en", "id", "app", "my", "travel",
    "www2", "api",
}


@dataclass(frozen=True)
class RootDomain:
    root: str  # the registrable-domain label, e.g. "marriott", "intercontinental"
    suffix: str  # e.g. "com", "co.id"
    subdomain: str | None  # e.g. "bali", "jakartapondokindah" — None if apex/generic


def parse_root_domain(netloc: str) -> RootDomain:
    labels = netloc.split(".")
    suffix = None
    for n in (2, 1):
        if len(labels) > n:
            candidate = ".".join(labels[-n:])
            if candidate in _MULTI_LABEL_SUFFIXES:
                suffix = candidate
                break
    if suffix is None:
        suffix = labels[-1]
        root_and_sub = labels[:-1]
    else:
        root_and_sub = labels[: -len(suffix.split("."))]

    if not root_and_sub:
        # bare TLD-only netloc, shouldn't happen for real hrefs
        return RootDomain(root=netloc, suffix=suffix, subdomain=None)

    root = root_and_sub[-1]
    sub_labels = root_and_sub[:-1]
    if not sub_labels:
        subdomain = None
    else:
        first = sub_labels[0]
        if first in _GENERIC_SUBDOMAIN_LABELS and len(sub_labels) == 1:
            subdomain = None
        else:
            # keep the innermost, most specific label (closest to the root)
            subdomain = sub_labels[-1]
            if subdomain in _GENERIC_SUBDOMAIN_LABELS:
                subdomain = None
    return RootDomain(root=root, suffix=suffix, subdomain=subdomain)


# ---------------------------------------------------------------------------
# curated aliases — same organisation, different registrable root, caught by
# knowledge rather than string matching (kept small and reviewable; anything
# not in here falls back to the substring-keyword heuristic below, flagged
# ambiguous, or stays its own unmerged org).
# ---------------------------------------------------------------------------

ROOT_ALIASES: dict[str, str] = {
    "accorhotels": "accor",
}

# canonical display names for well-known roots (else Title-Case fallback)
CANONICAL_NAMES: dict[str, str] = {
    "marriott": "Marriott International",
    "accor": "Accor",
    "ihg": "IHG Hotels & Resorts",
    "intercontinental": "InterContinental Hotels Group",
    "hyatt": "Hyatt Hotels Corporation",
    "kempinski": "Kempinski Hotels",
    "fourseasons": "Four Seasons Hotels and Resorts",
    "comohotels": "COMO Hotels and Resorts",
    "ayana": "AYANA Hospitality",
    "alilahotels": "Alila Hotels & Resorts",
    "raffles": "Raffles Hotels & Resorts",
    "tuguhotels": "Tugu Hotels",
    "langhamhotels": "Langham Hospitality Group",
    "mandarinoriental": "Mandarin Oriental Hotel Group",
    "fairmont": "Fairmont Hotels & Resorts",
    "ismaya": "Ismaya Group",
    "karmagroup": "Karma Group",
    "hotelborobudur": "Hotel Borobudur Jakarta",
    "discoverasr": "ASR Group (Discover ASR)",
    "chope": "Chope",
    "artotelgroup": "ARTOTEL Group",
    "pullman": "Pullman Hotels & Resorts",
}

# brand keyword -> parent org slug, applied when the keyword appears as a
# substring of an unrelated-looking registrable root (not caught by the
# subdomain relationship above) — e.g. "jwmarriottsurabaya.com" contains
# "marriott" but is not a subdomain of marriott.com. Confidence for these is
# deliberately lower than a real subdomain relationship; see cluster.py.
GROUP_KEYWORDS: dict[str, str] = {
    "marriott": "marriott",
    "accor": "accor",
    "pullman": "pullman",
    "novotel": "accor",
    "mercure": "accor",
    "sofitel": "accor",
    "ibis": "accor",
    "artotel": "artotelgroup",
    "intercontinental": "intercontinental",
    "ihg": "ihg",
    "kempinski": "kempinski",
    "hyatt": "hyatt",
    "ayana": "ayana",
    "alila": "alilahotels",
    "raffles": "raffles",
    "tugu": "tuguhotels",
    "fairmont": "fairmont",
}


def canonical_name(root: str) -> str:
    if root in CANONICAL_NAMES:
        return CANONICAL_NAMES[root]
    # Title-case fallback, e.g. "hotelborobudur" -> "Hotelborobudur" (still
    # low-confidence-worthy; a human names it properly on review).
    return root.replace("-", " ").title()


# ---------------------------------------------------------------------------
# type_guess — a low-confidence hint for E2.3, never a decision
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("hotel", "stay"), ("resort", "stay"), ("residence", "stay"),
    ("marriott", "stay"), ("accor", "stay"), ("hyatt", "stay"),
    ("intercontinental", "stay"), ("ihg", "stay"), ("kempinski", "stay"),
    ("fourseasons", "stay"), ("four-seasons", "stay"), ("ayana", "stay"),
    ("alila", "stay"), ("raffles", "stay"), ("tugu", "stay"), ("fairmont", "stay"),
    ("mandarinoriental", "stay"), ("langham", "stay"), ("comohotels", "stay"),
    ("pullman", "stay"), ("novotel", "stay"), ("ibis", "stay"), ("sofitel", "stay"),
    ("artotel", "stay"), ("dharmawangsa", "stay"), ("sultanjakarta", "stay"),
    ("restaurant", "eat"), ("cafe", "eat"), ("dining", "eat"), ("chope", "eat"),
    ("gourmet", "eat"),
    ("bar", "drink"), ("brew", "drink"),
    ("gallery", "do"), ("museum", "do"), ("festival", "do"), ("concerthall", "do"),
    ("wikipedia", None),
]


def type_guess(root: str) -> tuple[str | None, float]:
    """Returns (type_guess, confidence-contribution). Domain-only signal is
    inherently weak — E2.3 does the real classification from article
    context; this just seeds a prior."""
    low = root.lower()
    for kw, guess in _TYPE_KEYWORDS:
        if kw in low:
            return guess, 0.4 if guess else 0.0
    return None, 0.0

"""Small, dependency-free text normalization used for dedup keys, area-term
text matching, and slug generation. Deliberately ASCII-only heuristics —
the corpus is Indonesian/English venue names, not a general i18n problem."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_name(text: str | None) -> str:
    """Lowercase, accent-stripped, punctuation-stripped, whitespace-collapsed.
    Used as the dedup/match key — deliberately lossy, never shown to a human."""

    if not text:
        return ""
    text = strip_accents(text).lower()
    text = _NON_ALNUM.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def slugify(text: str, *, max_len: int = 80) -> str:
    text = strip_accents(text or "").lower()
    text = _SLUG_NON_ALNUM.sub("-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_len].strip("-") or "place"


def candidate_key(name: str, address: str | None) -> str:
    """Stable dedup/resume key for a merged candidate. Address is included
    when present so two different real places that happen to share a
    generic name ("Bali") don't collide; when address is absent the name
    alone is the key, matching how the free-seed merge in dedupe.py groups
    rows (see its docstring for why that's safe at this corpus's scale)."""

    basis = normalize_name(name) + "|" + normalize_name(address)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

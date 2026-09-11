"""Name normalization for venue dedup.

Two representations are produced for every name, deliberately kept
separate rather than collapsed into one "the normalized form":

  - `normalize_full(name)`  -- lowercase, diacritics folded, punctuation
    stripped, whitespace collapsed. Used for EXACT-match comparison
    (catches pure casing/punctuation drift: "METIS Lounge" vs "Metis
    Lounge").

  - `core_tokens(name)` -- `normalize_full` further stripped of generic
    venue/geo words ("the", "hotel", "resort", "jakarta", "&", "and", ...)
    that make two DIFFERENT venues look similar for the wrong reason
    (two unrelated hotels both containing "Resort Bali") while also being
    exactly the words that legitimately vary across mentions of the SAME
    venue ("The Ritz-Carlton Jakarta Mega Kuningan" / "Ritz Carlton Mega
    Kuningan"). Used for fuzzy/blocking comparison, never for auto-merge
    on its own -- see match.py.

Kept deliberately dependency-free (no rapidfuzz/spacy): ARCHITECTURE.md
Sec.1 wants the deterministic core auditable by inspection.
"""

from __future__ import annotations

import re
import unicodedata

# Words that are near-universal in venue names and carry ~zero
# discriminating signal once a name is being compared to another --
# generic venue-type nouns, plus the two whole-city/country names so broad
# that nearly every venue in a city's corpus carries them ("Jakarta",
# "Bali", "Indonesia").
#
# Deliberately EXCLUDED: sub-city area names (ubud, canggu, kuta, legian,
# seminyak, sanur, nusa dua, jimbaran, kemang, menteng, senopati, kuningan,
# scbd, ...). These are the opposite of noise for dedup -- they are often
# the ONLY thing distinguishing two real, distinct venues that share a
# brand ("Padma Resort Ubud" vs "Padma Resort Legian" -- two different
# hotels, not a name-drift pair). Stripping them would have made
# core_tokens() collapse both to {"padma"} and auto-merged two different
# properties -- exactly the over-merge failure mode this ticket calls out
# as worse than under-merging. See tests/test_match.py.
_GENERIC_WORDS = {
    "the", "a", "an", "and", "at", "of", "by", "in", "on",
    "hotel", "hotels", "resort", "resorts", "restaurant", "restaurants",
    "cafe", "café", "bar", "bars", "lounge", "club", "spa", "villa", "villas",
    "beach", "rooftop", "residence", "residences", "suites", "suite",
    "boutique", "gallery", "museum",
    "jakarta", "bali", "indonesia",
}

_APOSTROPHE_RE = re.compile(r"[’‘'`]")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def _fold_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_full(name: str) -> str:
    """Lowercase, diacritic-folded, punctuation-stripped, whitespace-collapsed.

    Apostrophes are removed OUTRIGHT (joined, not turned into a space) --
    "Year's" -> "years", not "year s". Every other punctuation character
    becomes a space (a word separator). Getting this backwards was found
    live: "New Year’s Eve" normalized to "new year s eve" (four
    tokens) instead of "new years eve" (three), which silently broke an
    exact-phrase exclusion list lookup elsewhere in this package."""
    folded = _fold_diacritics(name or "")
    folded = folded.lower()
    folded = _APOSTROPHE_RE.sub("", folded)
    folded = _PUNCT_RE.sub(" ", folded)
    folded = _WS_RE.sub(" ", folded).strip()
    return folded


def tokens(name: str) -> list[str]:
    return normalize_full(name).split(" ") if name else []


def core_tokens(name: str) -> list[str]:
    """`tokens()` minus generic venue/geo words. If stripping generic
    words would remove EVERYTHING (e.g. the venue's whole name is "The
    Beach Club"), fall back to the full token list -- an empty core key
    is worse than a slightly-too-generic one, and would collapse every
    such venue into a single (wrong) block."""
    toks = tokens(name)
    core = [t for t in toks if t not in _GENERIC_WORDS]
    return core if core else toks


def blocking_key(name: str) -> str:
    """First core token -- the classic dedup "blocking" key, keeping
    pairwise comparison to within same-first-distinctive-word groups
    rather than the full O(n^2) corpus. Two venues that share no core
    token at all are never compared."""
    core = core_tokens(name)
    return core[0] if core else ""

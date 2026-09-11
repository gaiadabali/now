"""Per-article cue features, cached on disk so a re-render is seconds, not minutes.

Cache lives in `<package>/.cache/` (gitignored). Keyed by city and by
`text.FEATURE_VERSION` -- bump that constant whenever a lexicon changes and
the cache rebuilds itself.
"""
from __future__ import annotations

import json
from pathlib import Path

from .sources import Article, load_seed
from .text import FEATURE_VERSION, article_features, build_location_matcher

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"


def _cache_path(city: str) -> Path:
    return CACHE_DIR / f"features-{city}-v{FEATURE_VERSION}.json"


def compute_features(city: str, articles: list[Article], seed: dict | None = None, use_cache: bool = True) -> dict[int, dict]:
    path = _cache_path(city)
    if use_cache and path.is_file():
        with open(path, encoding="utf-8") as fh:
            cached = {int(k): v for k, v in json.load(fh).items()}
        if set(cached) == {a.wp_id for a in articles}:
            return cached
    seed = seed or load_seed()
    matcher = build_location_matcher(seed["terms"]["location"])
    out: dict[int, dict] = {}
    for a in articles:
        out[a.wp_id] = article_features(a.title, a.text, matcher)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
    return out

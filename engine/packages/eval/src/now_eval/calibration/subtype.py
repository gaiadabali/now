"""Subtype-facet calibration -- F115: `subtype` is the single largest slice
of the review backlog (6,023 of 18,192 rows, 33%) and, unlike `type`,
`format` and `location`, it had **no calibration coverage at all** before
this ticket. It is also the least-evidenced instrument by construction:
E2.1's own report says subtype had no prior mechanism, so it added "a
simple keyword matcher, kept deliberately conservative"
(`now_classifier.subtype.infer_subtype`) rather than reusing an existing
one. Nobody has measured whether that matcher is any good.

**Why this is its own module rather than a merge into `sample.py`/
`label.py` (the type/format pipeline), following the same precedent
`location.py` set:** subtype needs its own module for exactly one reason
type/format does not have to deal with -- **no convenience column.**
`public.articles` carries `primary_type` and `format` columns the
classifier writes an accepted value into directly; there is no
`primary_subtype`. So the accepted value has to be read back off
`engine.entity_terms.term_id` via the platform vocabulary, the same way
`location.py` already does it (`db_frame.fetch_subtype_outcomes`, a close
sibling of `fetch_location_outcomes`).

**Everything else about subtype is structurally identical to type/format
-- single-valued, forced-choice, no overloaded confidence number -- so
this module deliberately does NOT duplicate the sampling/merge/queue-
building logic a second time.** It reuses:
- `strata.FrameRecord` + `strata.stratified_sample` for the stratified
  draw (their `(city, facet, confidence)` grouping and per-value round-
  robin already do exactly what a 66-term vocabulary needs -- see
  `strata.py`'s `TARGET_N_BY_CONFIDENCE`, extended by this ticket with
  subtype's own two confidence values, 0.70 and 0.35, which cannot affect
  type/format's sampling since no type/format row is ever exactly 0.70 or
  0.35).
- `sample.write_sample` / `sample.summarize` unchanged (both are already
  facet-agnostic).
- `adjudication.merge` / `adjudication.build_queue` / `adjudication.write_queue`
  unchanged -- `merge` looks up `label.get(row["facet"])`, i.e.
  `label.get("subtype")` for these rows, entirely generically. This is
  exactly why this module's blind LLM label uses the literal string
  `"unresolved"` (not `"none"` or any other synonym) for "no specific
  subtype fits" -- `now_classifier`'s own no-match fallback proposes that
  exact literal, and matching it means `agree = llm_value == proposed_value`
  works without any normalisation step, and Hansel sees the same word on
  both sides in the adjudication tool when they agree nothing fits.
- `render_html.write_html` unchanged -- it already renders any non-
  `location` facet with the generic three-way (classifier / LLM / neither)
  forced-choice UI. The one field name to note: this module's blind label
  writes its reasoning into a JSON key called `format_reasoning`, which
  `adjudication.merge`/`_to_item` picks up generically and the HTML tool
  displays for any facet that isn't literally `"type"` -- an intentional
  reuse of that slot (the same trick `location.py` plays with
  `llm_type_reasoning`), not a real "format" value.
- `analyze.build_cell_estimates` / `analyze.preliminary_agreement_rate` /
  `mapping.recommend` / `mapping.simulate_coverage` unchanged -- see
  `finalize.py`'s subtype section for how they're wired in.

Only two things are genuinely new: reading the DB (`db_frame.py`, already
added) and the blind classification prompt (below) -- forced single-choice
over the full 66-slug vocabulary, grouped by parent type for the model's
own readability only (it is not scored on which group it picks).
"""
from __future__ import annotations

import json
from pathlib import Path

from .strata import FrameRecord, stratified_sample

# slug -> parent type, transcribed from `engine.terms` (66 rows, facet
# 'subtype', joined to their parent's slug) at the time this ticket ran a
# read-only recon query. Hardcoded rather than queried live for the same
# reason `llm_client.TYPE_DESCRIPTIONS`/`FORMAT_DESCRIPTIONS` are: the blind
# prompt must be a pure, unit-testable function of its arguments, not a
# function of live DB state that could silently drift the prompt's meaning
# between calibration runs.
SUBTYPE_VOCABULARY: dict[str, str] = {
    "adventure": "do", "artisan": "shop", "attraction": "do", "bakery": "eat",
    "bar": "drink", "beach-club": "drink", "bookshop": "shop", "boutique": "shop",
    "boutique-hotel": "stay", "business": "editorial", "cafe": "eat", "cinema": "do",
    "city-guide": "editorial", "clinic": "wellness", "cocktail-bar": "drink",
    "community": "event", "concert": "event", "conference": "event",
    "culture": "editorial", "dessert-shop": "eat", "education": "editorial",
    "exhibition": "event", "farm": "do", "festival": "event", "fine-dining": "eat",
    "food-court": "eat", "gallery": "do", "glamping": "stay", "gym": "wellness",
    "heritage": "editorial", "hotel": "stay", "karaoke": "drink",
    "lifestyle": "editorial", "mall": "shop", "market": "shop", "museum": "do",
    "nature": "do", "news": "editorial", "nightclub": "drink", "opinion": "editorial",
    "people": "editorial", "performance": "event", "place-of-worship": "do",
    "pop-up": "event", "pub": "drink", "resort": "stay", "restaurant": "eat",
    "retreat": "wellness", "rooftop-bar": "drink", "salon": "wellness",
    "screening": "event", "serviced-apartment": "stay", "spa": "wellness",
    "sports": "event", "sports-activity": "do", "street-food": "eat",
    "temple": "do", "theatre": "do", "tour": "do", "villa": "stay",
    "watersports": "do", "wine-bar": "drink", "winery-distillery": "drink",
    "workshop": "do", "yoga": "wellness", "zoo": "do",
}


# ---------------------------------------------------------------------------
# Step 1: sampling frame + stratified draw. Thin wrapper around the shared
# `strata` module -- see the module docstring for why no new sampling
# algorithm is written here.
# ---------------------------------------------------------------------------

def build_subtype_frame(city: str, root: Path, term_slug_map: dict) -> list[dict]:
    from .db_frame import fetch_subtype_outcomes, load_article_content

    outcomes = fetch_subtype_outcomes(city, term_slug_map)
    content = load_article_content(city, root)
    frame = []
    for o in outcomes:
        c = content.get(o.wp_id)
        if c is None:
            continue
        frame.append(
            {
                "key": f"{city}:{o.wp_id}:subtype",
                "city": city,
                "wp_id": o.wp_id,
                "article_id": o.article_id,
                "facet": "subtype",
                "proposed_value": o.proposed_value,
                "confidence": o.confidence,
                "source": o.source,
                "outcome": o.outcome,
                "title": c.title,
                "excerpt": c.excerpt,
                "text_excerpt": c.text_excerpt,
                "categories": list(c.categories),
            }
        )
    return frame


def build_and_sample(root: Path, seed: str = "now-eval-calibration-subtype-v1") -> list[dict]:
    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import load_term_slug_map

    term_slug_map = load_term_slug_map(create_engine(platform_database_url()))

    frame_by_key: dict[str, dict] = {}
    all_records: list[FrameRecord] = []
    for city in ("jakarta", "bali"):
        frame = build_subtype_frame(city, root, term_slug_map)
        for row in frame:
            frame_by_key[row["key"]] = row
            all_records.append(
                FrameRecord(
                    key=row["key"], city=row["city"], facet=row["facet"],
                    proposed_value=row["proposed_value"], confidence=row["confidence"],
                )
            )

    selected = stratified_sample(all_records, seed=seed)
    return [frame_by_key[r.key] for r in selected]


# ---------------------------------------------------------------------------
# Step 2: blind LLM proxy label -- forced single choice over the full
# vocabulary, blind to the WP category, the classifier's own resolved
# `type`, and its proposed subtype. `"unresolved"` is the deliberate literal
# fallback (matches `now_classifier`'s own no-match value -- see module
# docstring).
# ---------------------------------------------------------------------------

def _vocabulary_lines() -> str:
    from collections import defaultdict

    by_parent: dict[str, list[str]] = defaultdict(list)
    for slug, parent in SUBTYPE_VOCABULARY.items():
        by_parent[parent].append(slug)
    return "\n".join(f"{parent}: " + ", ".join(sorted(slugs)) for parent, slugs in sorted(by_parent.items()))


def build_prompt(title: str, excerpt: str, text_excerpt: str) -> list[dict]:
    system = (
        "You are labelling articles from a Jakarta/Bali lifestyle magazine for an independent "
        "evaluation dataset. You will be given ONLY an article's title and a body excerpt -- no "
        "category metadata of any kind, because the whole point of this labelling pass is to be "
        "an independent check, blind to any prior categorization. Read the text and decide, from "
        "its content alone, the single SUBTYPE that best describes what this article is mainly "
        "about -- a more specific label than a general type. The full vocabulary, grouped by its "
        "parent type for readability only (you are not scored on the group, only the exact "
        "subtype slug):\n\n"
        f"{_vocabulary_lines()}\n\n"
        'If the article is general editorial content that does not fit any specific subtype above '
        '(a broad trend piece, a listicle spanning many venues, or anything with no single clear '
        'subject), answer exactly "unresolved" -- do not guess the closest-sounding slug.\n\n'
        "Respond with ONLY a JSON object, no other text: "
        '{"subtype": "<one slug from the list above, or "unresolved">", "reasoning": "<one short sentence>"}'
    )
    body = f"TITLE: {title}\n\nEXCERPT: {excerpt}\n\nBODY: {text_excerpt}".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": body},
    ]


def label_sample(sample_path: Path, out_path: Path, *, sleep_between: float = 0.2,
                  progress_every: int = 10, model: str | None = None) -> dict:
    """One call per unique article (subtype is single-valued, so a sample
    row is already one article -- no de-duplication across facets needed
    the way type/format's `label.py` needs it). Resumable: skips any
    (city, wp_id) already present in `out_path`."""
    import sys
    import time

    from .llm_client import load_ollama_env

    rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    unique: dict[tuple[str, int], dict] = {}
    for r in rows:
        unique.setdefault((r["city"], r["wp_id"]), r)

    done: set[tuple[str, int]] = set()
    if out_path.is_file():
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                done.add((row["city"], row["wp_id"]))
    todo = [v for k, v in unique.items() if k not in done]

    env = load_ollama_env()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_ok, n_err = 0, 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for i, r in enumerate(todo, 1):
            label = classify_subtype(r["wp_id"], r["city"], r["title"], r["excerpt"], r["text_excerpt"], env, model=model)
            record = {
                "city": label["city"], "wp_id": label["wp_id"], "subtype": label["subtype"],
                "reasoning": label["reasoning"],
                # Reused generically by `adjudication.merge`/`render_html` for any
                # facet that isn't literally "type" -- see module docstring.
                "format_reasoning": label["reasoning"],
                "raw": label["raw"], "error": label["error"],
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            if label["error"]:
                n_err += 1
            else:
                n_ok += 1
            if i % progress_every == 0 or i == len(todo):
                print(f"[subtype-label] {i}/{len(todo)} done (ok={n_ok} err={n_err}, {len(done)} already cached)",
                      file=sys.stderr)
            time.sleep(sleep_between)
    return {"total_unique": len(unique), "already_done": len(done), "processed_this_run": len(todo),
            "ok": n_ok, "errors": n_err}


def classify_subtype(
    wp_id: int, city: str, title: str, excerpt: str, text_excerpt: str,
    env: dict[str, str], model: str | None = None, timeout: float = 60.0, max_retries: int = 3,
) -> dict:
    import time

    import requests

    from .llm_client import _parse_response, _redact

    base_url = env["OLLAMA_CLOUD_BASE_URL"].rstrip("/")
    api_key = env["OLLAMA_CLOUD_API_KEY"]
    # GENERAL tier, not FAST: a 66-way forced choice is closer to type/
    # format's open classification than to location's yes/no validation, so
    # this reuses type/format's reasoning-quality-over-latency rationale
    # (see `llm_client.py`), including its generous max_tokens for the same
    # documented reason (glm-5.2 spends tokens on a hidden reasoning field).
    model = model or env.get("OLLAMA_CLOUD_MODEL_GENERAL", "glm-5.2")
    messages = build_prompt(title, excerpt, text_excerpt)

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.0, "max_tokens": 800},
                timeout=timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = _parse_response(content)
            return {
                "wp_id": wp_id, "city": city, "subtype": parsed.get("subtype"),
                "reasoning": str(parsed.get("reasoning", ""))[:300], "raw": content, "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            last_err = _redact(str(exc), api_key)
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return {"wp_id": wp_id, "city": city, "subtype": None, "reasoning": "", "raw": "", "error": last_err}

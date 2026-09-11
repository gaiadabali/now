"""Location-facet calibration -- added mid-ticket after a parallel F101 audit
found that Jakarta's `location` review queue holds 1,124 rows (683 in Bali)
at confidence 0.75, and that every one of them is a *category-fixed* value
-- i.e. `taxonomy-review.json`'s own recorded human decision
(`resolution.decided_by`), not a classifier guess -- sitting just below the
gate under the same invented "medium" number F96 already flags. That single
band is probably the highest-leverage question in this whole calibration:
if it is genuinely >=0.85 accurate, ~1,807 rows leave the queue for free.

Kept as its own module (parallel to the type/format pipeline in `sample.py`
/ `label.py`, not merged into it) for three reasons the type/format design
does not have to deal with:

1. **`location` is multi-valued.** The same article can carry several
   simultaneously-true locations (a Bali Updates piece about a specific
   Lombok resort correctly carries both `bali` and `lombok`). A forced
   single-choice "which one is right" question (the type/format design)
   would systematically mismeasure this facet -- so the LLM task here is
   *validation* ("is this specific proposed location correct?", yes/no) per
   candidate, not "produce your own single value and compare."
2. **The confidence number 0.90 is overloaded** across two unrelated
   mechanisms (`site_home_fallback` vs `title_match`, disambiguated only by
   `source` -- see `provenance.py`). Strata here are keyed by
   `(source, confidence)`, not confidence alone.
3. **The flagged 0.75 band needs more precision than the other bands**,
   because it alone gates ~1,807 rows -- so it gets a bigger sample (n=35)
   than the type/format design spent on any single cell.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .provenance import provenance_label

# (source, confidence) -> target sample size. 0.75/inferred (category-fixed,
# below the gate) gets the largest n in this entire calibration: it is the
# band the parallel audit identified as the highest-leverage single number.
LOCATION_TARGET_N: dict[tuple[str, float], int] = {
    ("inferred", 0.95): 25,   # category_fixed_high (currently auto-applied) -- baseline to compare 0.75 against
    ("inferred", 0.75): 35,   # category_fixed_medium -- THE flagged band
    ("inferred", 0.45): 15,   # category_fixed_low
    ("inferred", 0.90): 15,   # site_home_fallback (small population: 130 in Jakarta, 0 in Bali)
    ("ai", 0.90): 20,         # title_match
    ("ai", 0.55): 20,         # lead_only_match
}
DEFAULT_TARGET_N = 15


def _stable(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def target_n(source: str, confidence: float, population: int) -> int:
    n = LOCATION_TARGET_N.get((source, round(confidence, 2)), DEFAULT_TARGET_N)
    return min(n, population)


def build_location_frame(city: str, root: Path, term_slug_map: dict) -> list[dict]:
    from .db_frame import fetch_location_outcomes, load_article_content

    outcomes = fetch_location_outcomes(city, term_slug_map)
    content = load_article_content(city, root)
    frame = []
    for o in outcomes:
        c = content.get(o.wp_id)
        if c is None:
            continue
        frame.append(
            {
                "key": f"{city}:{o.wp_id}:location:{o.proposed_value}:{o.confidence}:{o.source}",
                "city": city,
                "wp_id": o.wp_id,
                "article_id": o.article_id,
                "facet": "location",
                "proposed_value": o.proposed_value,
                "confidence": o.confidence,
                "source": o.source,
                "outcome": o.outcome,
                "provenance": provenance_label("location", o.confidence, o.source),
                "title": c.title,
                "excerpt": c.excerpt,
                "text_excerpt": c.text_excerpt,
                "categories": list(c.categories),
            }
        )
    return frame


def stratified_sample(records: list[dict], *, seed: str = "now-eval-calibration-location-v1") -> list[dict]:
    """Same round-robin-across-values design as `strata.stratified_sample`,
    but grouped by `(city, source, confidence)` -- not just confidence --
    because `location`'s 0.90 is shared by two different mechanisms."""
    by_cell: dict[tuple, dict[str, list[dict]]] = {}
    for r in records:
        cell = (r["city"], r["source"], round(r["confidence"], 2))
        by_cell.setdefault(cell, {}).setdefault(r["proposed_value"], []).append(r)

    selected: list[dict] = []
    for cell, by_value in by_cell.items():
        population = sum(len(v) for v in by_value.values())
        n = target_n(cell[1], cell[2], population)
        ranked = {v: sorted(items, key=lambda r: _stable(seed, r["key"])) for v, items in by_value.items()}
        cursors = {v: 0 for v in ranked}
        value_order = sorted(ranked.keys(), key=lambda v: _stable(seed, f"cell-order:{cell}:{v}"))
        picked = 0
        while picked < n:
            progressed = False
            for v in value_order:
                if picked >= n:
                    break
                idx = cursors[v]
                if idx < len(ranked[v]):
                    selected.append(ranked[v][idx])
                    cursors[v] = idx + 1
                    picked += 1
                    progressed = True
            if not progressed:
                break
    return selected


def build_and_sample(root: Path, seed: str = "now-eval-calibration-location-v1") -> list[dict]:
    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import load_term_slug_map

    term_slug_map = load_term_slug_map(create_engine(platform_database_url()))
    all_records: list[dict] = []
    for city in ("jakarta", "bali"):
        all_records.extend(build_location_frame(city, root, term_slug_map))
    return stratified_sample(all_records, seed=seed)


def write_sample(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict]) -> dict:
    from collections import Counter

    by_cell = Counter((r["city"], r["provenance"]) for r in rows)
    unique_articles = {(r["city"], r["wp_id"]) for r in rows}
    return {
        "total_rows": len(rows),
        "unique_articles": len(unique_articles),
        "cells": {f"{c}:{p}": n for (c, p), n in sorted(by_cell.items())},
    }


# ---------------------------------------------------------------------------
# Blind validation prompt: batches every candidate location for one article
# into a single call ("is each of these proposed locations correct, based on
# the text alone?") rather than one call per candidate.
# ---------------------------------------------------------------------------

VALIDATION_SYSTEM_PROMPT = (
    "You are checking proposed location tags on articles from a Jakarta/Bali lifestyle magazine, "
    "for an independent evaluation dataset. You are given ONLY an article's title and a body excerpt "
    "-- no category metadata -- plus a list of proposed location slugs. For EACH proposed location, "
    "decide from the text alone whether that location genuinely applies to this article (a specific "
    "place mentioned or clearly the article's setting, or the whole city/region the piece is about). "
    "More than one proposed location can be correct at once -- a piece can genuinely be about a "
    "specific area within a city AND the city itself. Do not assume only one answer is right.\n\n"
    "Respond with ONLY a JSON object, no other text: "
    '{"verdicts": [{"slug": "<slug>", "correct": true|false, "reasoning": "<one short sentence>"}, ...]}, '
    "one entry per proposed location, in the order given."
)


def build_validation_prompt(title: str, excerpt: str, text_excerpt: str, candidate_slugs: list[str]) -> list[dict]:
    body = (
        f"TITLE: {title}\n\nEXCERPT: {excerpt}\n\nBODY: {text_excerpt}\n\n"
        f"PROPOSED LOCATIONS TO CHECK: {json.dumps(candidate_slugs)}"
    ).strip()
    return [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {"role": "user", "content": body},
    ]


@dataclass(frozen=True)
class LocationVerdict:
    wp_id: int
    city: str
    verdicts: dict[str, dict]   # slug -> {"correct": bool, "reasoning": str}
    raw: str
    error: str | None = None


def validate_locations(
    wp_id: int, city: str, title: str, excerpt: str, text_excerpt: str, candidate_slugs: list[str],
    env: dict[str, str], model: str | None = None, timeout: float = 60.0, max_retries: int = 3,
) -> LocationVerdict:
    import time

    import requests

    from .llm_client import _parse_response, _redact

    base_url = env["OLLAMA_CLOUD_BASE_URL"].rstrip("/")
    api_key = env["OLLAMA_CLOUD_API_KEY"]
    model = model or env.get("OLLAMA_CLOUD_MODEL_FAST", "deepseek-v4-flash")
    messages = build_validation_prompt(title, excerpt, text_excerpt, candidate_slugs)

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
            by_slug = {v["slug"]: {"correct": bool(v.get("correct")), "reasoning": str(v.get("reasoning", ""))[:300]}
                       for v in parsed.get("verdicts", []) if "slug" in v}
            return LocationVerdict(wp_id=wp_id, city=city, verdicts=by_slug, raw=content)
        except Exception as exc:  # noqa: BLE001
            last_err = _redact(str(exc), api_key)
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return LocationVerdict(wp_id=wp_id, city=city, verdicts={}, raw="", error=last_err)


def _already_labelled(out_path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if out_path.is_file():
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                done.add((row["city"], row["wp_id"]))
    return done


def label_sample(sample_path: Path, out_path: Path, *, sleep_between: float = 0.2,
                  progress_every: int = 10, model: str | None = None) -> dict:
    """One call per unique article, batching every sampled location
    candidate for that article into the same validation request (an
    article can appear once per distinct proposed location value)."""
    import sys
    import time
    from dataclasses import asdict

    from .llm_client import load_ollama_env

    rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    by_article: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        by_article.setdefault((r["city"], r["wp_id"]), []).append(r)

    done = _already_labelled(out_path)
    todo = [(k, v) for k, v in by_article.items() if k not in done]

    env = load_ollama_env()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_ok, n_err = 0, 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for i, ((city, wp_id), article_rows) in enumerate(todo, 1):
            candidates = sorted({r["proposed_value"] for r in article_rows})
            first = article_rows[0]
            verdict = validate_locations(wp_id, city, first["title"], first["excerpt"], first["text_excerpt"],
                                          candidates, env, model=model)
            fh.write(json.dumps(asdict(verdict), ensure_ascii=False) + "\n")
            fh.flush()
            if verdict.error:
                n_err += 1
            else:
                n_ok += 1
            if i % progress_every == 0 or i == len(todo):
                print(f"[location-label] {i}/{len(todo)} done (ok={n_ok} err={n_err}, {len(done)} already cached)",
                      file=sys.stderr)
            time.sleep(sleep_between)
    return {"total_unique": len(by_article), "already_done": len(done), "processed_this_run": len(todo),
            "ok": n_ok, "errors": n_err}


# ---------------------------------------------------------------------------
# Adjudication: same "adjudicate every disagreement + a control slice of
# agreements" design as the type/format pipeline (see adjudication.py's
# docstring), reusing `stats.estimate_cell_accuracy` unchanged -- only the
# *meaning* of "agree" differs: here it's "the blind LLM validated this
# specific proposed location as correct" rather than "produced the same
# value independently."
# ---------------------------------------------------------------------------

def merge(sample_rows: list[dict], llm_verdicts: list[dict]) -> list[dict]:
    by_article: dict[tuple[str, int], dict] = {(v["city"], v["wp_id"]): v for v in llm_verdicts}
    merged = []
    for row in sample_rows:
        v = by_article.get((row["city"], row["wp_id"]))
        if v is None or v.get("error"):
            continue
        verdict = (v.get("verdicts") or {}).get(row["proposed_value"])
        if verdict is None:
            continue  # model dropped this candidate from its response -- don't silently guess
        merged.append({**row, "llm_correct": bool(verdict["correct"]), "llm_reasoning": verdict.get("reasoning", ""),
                       "agree": bool(verdict["correct"])})
    return merged


def build_queue(merged_rows: list[dict], *, total_budget: int = 150,
                 seed: str = "now-eval-calibration-location-adjudication-v1") -> list[dict]:
    from .adjudication import _stable

    disagreements = [r for r in merged_rows if not r["agree"]]
    agreements = [r for r in merged_rows if r["agree"]]

    items = [_to_item(r, "disagreement") for r in disagreements]

    control_budget = max(0, total_budget - len(disagreements))
    by_cell: dict[str, list[dict]] = {}
    for r in agreements:
        by_cell.setdefault(r["provenance"] + ":" + r["city"], []).append(r)
    total_agreements = len(agreements) or 1
    for cell, rows in by_cell.items():
        share = round(control_budget * len(rows) / total_agreements)
        n = min(len(rows), max(2, share) if control_budget > 0 else 0)
        ranked = sorted(rows, key=lambda r: _stable(seed, r["key"]))
        for r in ranked[:n]:
            items.append(_to_item(r, "control"))
    return items


def _to_item(row: dict, kind: str) -> dict:
    return {
        "item_id": row["key"] + f":{kind}",
        "city": row["city"], "wp_id": row["wp_id"], "facet": "location",
        "cell": row["provenance"] + ":" + row["city"],
        "confidence": row["confidence"], "outcome": row["outcome"],
        "classifier_value": row["proposed_value"], "llm_value": row["proposed_value"] if row["llm_correct"] else None,
        "kind": kind, "title": row["title"], "excerpt": row["excerpt"], "text_excerpt": row["text_excerpt"],
        "llm_type_reasoning": row.get("llm_reasoning", ""), "llm_format_reasoning": "",
        "provenance": row["provenance"], "llm_correct": row["llm_correct"],
    }

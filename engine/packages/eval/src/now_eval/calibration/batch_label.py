"""Wave 18, senior-be ticket 2: offline LLM batch labelling for the full
9,201-article corpus (both cities), progressively replacing the weakest
type/format values while the parallel routing agent ships best-of-band
coverage immediately (F120/Wave 18 changelog). This module does NOT re-run
or replace that work -- it is a slower, higher-quality instrument that
lands on disk now and gets *applied* later, by a separate, human-gated step
(see `docs/llm-batch-apply-design.md`).

**Reuses `llm_client.build_prompt` / `llm_client.label_article` completely
unchanged** -- the brief is explicit that changing the prompt invalidates
F118's 211/211 blind-adjudication evidence, and nothing here has a reason
to change it. This module only adds: (1) a full-corpus, priority-ordered
queue instead of the 253-item calibration sample, (2) a per-city,
append-only, fsync'd ledger so a multi-day run survives being killed, and
(3) live pacing against the shared key's own `/api/usage` endpoint.

**Read-only against both city DBs, always.** The only DB access in this
module (`fetch_priority_map`) is a SELECT-shaped read via
`db_frame.fetch_facet_outcomes`, reused as-is -- this module contains no
INSERT/UPDATE/DELETE anywhere, against any database. Content (title/
excerpt/body) is read from the version-controlled evidence files via
`db_frame.load_article_content`, which touches no database at all.

**ARCHITECTURE.md §1** ("deterministic engine decides, LLM narrates"):
like `label.py`, this is a human-initiated, offline batch script. No
runtime path (`now_classifier`, `engine-api`) imports this module.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .llm_client import label_article, load_ollama_env

CITIES = ("jakarta", "bali")

# Worst-measured-accuracy-first (F113/F120): a call spent here replaces a
# weaker existing value than the same call spent on a 0.95 article.
#   0.72 -> 0.283 accuracy (worst)   0.93 -> 0.450   0.40 -> 0.312 (abstain)
#   0.45 -> 0.417 (abstain, thin)    0.75 -> 0.610   0.95 -> 0.660 (best, still short of 0.85)
PRIORITY_ORDER: tuple[float, ...] = (0.72, 0.93, 0.40, 0.45, 0.75, 0.95)

DEFAULT_OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "llm_batch"
USAGE_URL = "https://ollama.com/api/usage"


# --------------------------------------------------------------------------
# Pure logic (no DB, no network) -- unit-tested directly.
# --------------------------------------------------------------------------

def tier_index(confidence_values: set[float]) -> int:
    """Lowest (= highest priority) index in PRIORITY_ORDER touched by any
    confidence value this article's type/format outcomes carry. Values not
    in PRIORITY_ORDER (shouldn't happen against real data, but defensive)
    sort after everything named."""
    best = len(PRIORITY_ORDER)
    for v in confidence_values:
        rounded = round(v, 2)
        if rounded in PRIORITY_ORDER:
            best = min(best, PRIORITY_ORDER.index(rounded))
    return best


def build_priority_queue(articles: list[dict], bands_by_key: dict[tuple[str, int], set[float]]) -> list[dict]:
    """Sorts articles (each a dict with at least `city`/`wp_id`) so the
    weakest-measured band goes first, tie-broken by (city, wp_id) for a
    deterministic, reproducible order across restarts -- resumability
    depends on re-runs re-deriving the *same* queue, not just skipping
    already-done keys, so a change in DB state mid-run (e.g. the routing
    agent's concurrent re-classification) can only ever re-tier articles
    not yet processed, never reorder ones already written."""
    def sort_key(a: dict) -> tuple[int, str, int]:
        bands = bands_by_key.get((a["city"], a["wp_id"]), set())
        return (tier_index(bands), a["city"], a["wp_id"])

    return sorted(articles, key=sort_key)


def already_labelled(*out_paths: Path) -> set[tuple[str, int]]:
    """Every (city, wp_id) with a terminal record in any of the given
    ledger files -- matches `label.py`'s `_already_labelled` semantics
    exactly (any line, ok or error, counts as done; a batch script that
    wants to retry errors re-runs against a filtered copy, same as
    `label.py` always has -- this module doesn't change that contract)."""
    done: set[tuple[str, int]] = set()
    for out_path in out_paths:
        if not out_path.is_file():
            continue
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                done.add((row["city"], row["wp_id"]))
    return done


@dataclass(frozen=True)
class RateBudget:
    """Pacing policy against the shared, weekly-rate-limited key. `usage`
    is `limits.weekly.usage` from `/api/usage` -- a fraction of the shared
    cap, not ours alone. Degrades in two stages rather than one cliff:
    slow down well before the point of no return, only ever hard-stop with
    plenty of headroom left for whoever else is on this key."""
    soft_ceiling: float = 0.55   # above this: multiply sleep_between (slow down, don't stop)
    hard_ceiling: float = 0.75   # above this: stop cleanly, resumable, no partial writes lost
    slowdown_factor: float = 4.0

    def sleep_multiplier(self, current_usage: float) -> float:
        if current_usage >= self.hard_ceiling:
            raise RateBudgetExceeded(current_usage, self.hard_ceiling)
        if current_usage >= self.soft_ceiling:
            return self.slowdown_factor
        return 1.0


class RateBudgetExceeded(RuntimeError):
    def __init__(self, current_usage: float, hard_ceiling: float) -> None:
        super().__init__(f"weekly usage {current_usage:.3f} >= hard ceiling {hard_ceiling:.3f} -- stopping cleanly")
        self.current_usage = current_usage
        self.hard_ceiling = hard_ceiling


# --------------------------------------------------------------------------
# I/O: DB (read-only), evidence files (read-only), network (Ollama), disk (append-only ledger).
# --------------------------------------------------------------------------

def fetch_priority_map(cities: Iterable[str] = CITIES) -> dict[tuple[str, int], set[float]]:
    """Every (city, wp_id) -> set of confidence values its type/format
    outcomes carry today. Read-only: two SELECT-shaped calls per city via
    `db_frame`, nothing else. Imported lazily so this module stays
    importable (for the pure functions above / their tests) without the
    `calibration` extra installed."""
    from sqlalchemy import create_engine

    from now_platform_db.settings import platform_database_url

    from .db_frame import fetch_facet_outcomes, _load_term_map

    term_map = _load_term_map(create_engine(platform_database_url()))
    out: dict[tuple[str, int], set[float]] = {}
    for city in cities:
        for fo in fetch_facet_outcomes(city, term_map):
            out.setdefault((city, fo.wp_id), set()).add(round(fo.confidence, 2))
    return out


def fetch_usage(env: dict[str, str]) -> dict:
    """Live read of the shared key's own usage endpoint -- never logs or
    returns the key itself. Used both to re-measure the rate budget before
    scheduling and to pace/backoff during a long run."""
    import requests

    resp = requests.get(USAGE_URL, headers={"Authorization": f"Bearer {env['OLLAMA_CLOUD_API_KEY']}"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def weekly_usage_fraction(usage_doc: dict) -> float:
    return float(usage_doc.get("limits", {}).get("weekly", {}).get("usage", 0.0))


def out_path_for(city: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    return out_dir / f"{city}_llm_labels.full.jsonl"


def status_path(out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    return out_dir / "STATUS.json"


def _write_status(out_dir: Path, **fields) -> None:
    path = status_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {}
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            doc = {}
    doc.update(fields)
    doc["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")


def run_batch(
    root: Path,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    cities: tuple[str, ...] = CITIES,
    limit: int | None = None,
    sleep_between: float = 1.0,
    usage_check_every: int = 50,
    rate_budget: RateBudget = RateBudget(),
    model: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Main driver. Resumable by construction (skips any (city, wp_id)
    already terminal in its city's ledger); append-only + fsync'd per
    write (same durability guarantee as `media_mirror.ledger.Ledger` --
    a crash mid-run loses only the one in-flight call). Writes labels to
    `out_dir` only -- never to `now_jakarta` / `now_bali`.
    """
    from .db_frame import load_article_content

    articles: list[dict] = []
    for city in cities:
        for wp_id, content in load_article_content(city, root).items():
            articles.append({
                "city": city, "wp_id": wp_id, "title": content.title,
                "excerpt": content.excerpt, "text_excerpt": content.text_excerpt,
            })

    bands_by_key = fetch_priority_map(cities)
    queue = build_priority_queue(articles, bands_by_key)

    out_paths = {city: out_path_for(city, out_dir) for city in cities}
    done = already_labelled(*out_paths.values())
    todo = [a for a in queue if (a["city"], a["wp_id"]) not in done]
    if limit is not None:
        todo = todo[:limit]

    tier_counts: dict[int, int] = {}
    for a in queue:
        if (a["city"], a["wp_id"]) not in done:
            t = tier_index(bands_by_key.get((a["city"], a["wp_id"]), set()))
            tier_counts[t] = tier_counts.get(t, 0) + 1

    summary = {
        "total_corpus": len(articles), "already_done": len(done),
        "remaining_before_limit": len(queue) - len(done),
        "processed_this_run": 0, "ok": 0, "errors": 0,
        "remaining_by_tier": {PRIORITY_ORDER[t] if t < len(PRIORITY_ORDER) else "other": n
                              for t, n in sorted(tier_counts.items())},
    }
    if dry_run:
        return summary

    env = load_ollama_env()
    start_usage_doc = fetch_usage(env)
    start_usage = weekly_usage_fraction(start_usage_doc)
    _write_status(out_dir, phase="running", start_usage=start_usage, **{k: v for k, v in summary.items() if k != "remaining_by_tier"})

    n_ok, n_err = 0, 0
    current_multiplier = 1.0
    for i, a in enumerate(todo, 1):
        label = label_article(a["wp_id"], a["city"], a["title"], a["excerpt"], a["text_excerpt"], env, model=model)
        record = dict(label.__dict__)
        record["tier_confidence"] = sorted(bands_by_key.get((a["city"], a["wp_id"]), set()))
        record["labelled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = out_paths[a["city"]]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        if label.error:
            n_err += 1
        else:
            n_ok += 1

        if i % usage_check_every == 0 or i == len(todo):
            try:
                usage_doc = fetch_usage(env)
                usage = weekly_usage_fraction(usage_doc)
                current_multiplier = rate_budget.sleep_multiplier(usage)
                _write_status(out_dir, phase="running", processed_this_run=i, ok=n_ok, errors=n_err,
                              last_usage=usage, start_usage=start_usage, sleep_multiplier=current_multiplier)
                print(f"[batch_label] {i}/{len(todo)} (ok={n_ok} err={n_err}) weekly_usage={usage:.3f} "
                      f"(started {start_usage:.3f}) multiplier={current_multiplier}", file=sys.stderr)
            except RateBudgetExceeded as exc:
                _write_status(out_dir, phase="paused_hard_ceiling", processed_this_run=i, ok=n_ok, errors=n_err,
                              last_usage=exc.current_usage)
                print(f"[batch_label] STOPPING: {exc}", file=sys.stderr)
                break
            except Exception as exc:  # noqa: BLE001 - a failed usage check should not kill the run
                print(f"[batch_label] usage check failed, continuing at current pace: {exc}", file=sys.stderr)

        time.sleep(sleep_between * current_multiplier)

    summary["processed_this_run"] = n_ok + n_err
    summary["ok"] = n_ok
    summary["errors"] = n_err
    _write_status(out_dir, phase="idle", **{k: v for k, v in summary.items() if k != "remaining_by_tier"})
    return summary

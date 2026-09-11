"""Step 2: run the blind LLM proxy labeller over every unique article in the
calibration sample (one call per article, not per sample row -- an article
selected for both its `type` cell and its `format` cell still gets exactly
one call, since one call already returns both facets).

Resumable by construction: `label_sample` skips any (city, wp_id) already
present in `out_path`, so a run that is interrupted (rate limit, network,
Ctrl-C) can just be re-invoked and picks up where it left off rather than
re-spending budget on articles already labelled.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .llm_client import ProxyLabel, label_article, load_ollama_env


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
    rows = [json.loads(l) for l in open(sample_path, encoding="utf-8") if l.strip()]
    unique: dict[tuple[str, int], dict] = {}
    for r in rows:
        unique.setdefault((r["city"], r["wp_id"]), r)

    done = _already_labelled(out_path)
    todo = [v for k, v in unique.items() if k not in done]

    env = load_ollama_env()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_ok, n_err = 0, 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for i, r in enumerate(todo, 1):
            label = label_article(r["wp_id"], r["city"], r["title"], r["excerpt"], r["text_excerpt"], env, model=model)
            fh.write(json.dumps(label.__dict__, ensure_ascii=False) + "\n")
            fh.flush()
            if label.error:
                n_err += 1
            else:
                n_ok += 1
            if i % progress_every == 0 or i == len(todo):
                print(f"[label] {i}/{len(todo)} done (ok={n_ok} err={n_err}, {len(done)} already cached)", file=sys.stderr)
            time.sleep(sleep_between)
    return {"total_unique": len(unique), "already_done": len(done), "processed_this_run": len(todo),
            "ok": n_ok, "errors": n_err}

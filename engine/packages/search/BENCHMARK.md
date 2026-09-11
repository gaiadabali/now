# F60 — root cause found and fixed: onnxruntime version drift

**Date:** 2026-09-09 · **Machine:** same box as F53 · **DB:** `now_jakarta` · **Method:** standalone `query_embedder.embed_query()` loop (no DB, no other code — same technique F53 used for its "isolating the embedding step further" section) plus `now-search bench` end-to-end.

## The hypothesis, tested directly

F53 named "onnxruntime version drift" as its leading unconfirmed hypothesis for a ~30-40ms floor that survived even the quietest host-load windows it measured (installed `onnxruntime==1.29.0`; the doc-time version was never recorded). This session tested that hypothesis directly by installing a range of `onnxruntime` releases into this package's own `.venv` (`uv pip install --no-deps onnxruntime==<version>`) and re-running the identical standalone benchmark against each, with nothing else changed (same `fastembed==0.8.0`, same `threads=4`, same model, same machine):

| onnxruntime | p50 | p95 | host load at measurement |
|---|---|---|---|
| 1.19.2 | 27.0ms | 31.5ms | 1–12% |
| 1.20.1 | 22.9ms | 27.7ms | 20% |
| 1.21.1 | 22.7ms | 26.1ms | 12% |
| 1.22.1 | 12.5ms | 14.9ms | 34% |
| 1.23.2 | 6.1ms | 7.3ms | 12% |
| 1.24.2 | 5.8ms | 7.5ms | 4–39% |
| 1.25.1 | 5.5ms | 7.1ms | 90% (!) |
| **1.29.0 (what F53 measured, and what was installed before this fix)** | **99–112ms** | **117–126ms** | 4–46% |

Every version from 1.19.2 through 1.25.1 measured **single- to low-double-digit milliseconds**, including a run at 1.25.1 taken during an observed **90% host-load spike** — still 5.5ms p50. 1.29.0 measured **~100ms p50 at 4-46% load** — worse than every other version's number *at any load this session observed, including that 90% spike*. This is not a contention story: it is a real, reproducible, large regression specific to something that changed in `onnxruntime`'s CPU kernels between the ~1.25 and 1.29 release lines, for this exact model/op mix. (Correctness was checked, not assumed, at both ends: embeddings from 1.23.2 and 1.29.0 are both 384-dim, L2-normalized, and rank a semantically-similar sentence pair above a dissimilar one — the fast versions are not fast because they're returning garbage.)

This also **retires F53's "onnxruntime version drift... not confirmed" framing** — it's confirmed now, with numbers, not a guess. It additionally explains why `query_embedder.py`'s own documented benchmark (p50 46.5ms/p95 52.4ms) was itself *unreachable* by F53 on 1.29.0: that benchmark was almost certainly recorded against an older `onnxruntime` release than 1.29.0 (never recorded which one — see `query_embedder.py`'s original docstring), and even that documented number turns out to be conservative — every pre-regression version tested here beat it, several by 5-10x.

## The fix

`onnxruntime` had **no version pin anywhere in this repo** — it is a transitive dependency of `fastembed` (itself only ever pulled in transitively through `now-embeddings`, despite `query_embedder.py` importing it directly), so `uv lock`/`uv sync` silently resolves to the newest release satisfying `fastembed`'s own constraint at whatever moment someone re-locks. That is exactly how this regressed with zero code change in this package.

Fixed in `engine/packages/search/pyproject.toml`:
- `fastembed>=0.4,<1` declared as a **direct** dependency (matches what `query_embedder.py` actually imports, instead of relying on it arriving transitively via `now-embeddings`).
- `onnxruntime>=1.21.0,<1.25,!=1.24.0,!=1.24.1` declared as a **direct** dependency, pinning to the confirmed-fast range (`!=1.24.0,!=1.24.1` mirrors `fastembed`'s own exclusion of those two patch releases). `uv lock` resolved this to **`onnxruntime==1.24.4`**.

Each package in this repo has its **own independent `uv.lock`/`.venv`** (verified: `engine/packages/embeddings` has no `uv.lock` of its own; every other package's lock is self-contained) — so this pin and re-lock is fully isolated to `now-search`'s own environment and touches no other package's dependency resolution.

## Verified after the fix

Full test suite: `43 passed` (`uv run pytest`, unchanged pass count plus the two new F67 tests — see that section of this repo's report). End-to-end `now-search bench --db now_jakarta`, repeated at varying host load:

| n | host load | p50 | p95 | p99 | max | min |
|---|---|---|---|---|---|---|
| 100 | 5% | 37.53ms | 47.28ms | 54.79ms | 63.72ms | 29.56ms |
| 100 | 2% | 34.98ms | 42.53ms | 48.43ms | 49.61ms | 26.94ms |
| 100 | 28% | 35.45ms | 45.98ms | 47.76ms | 54.50ms | 28.71ms |
| 100 | 55% | 36.72ms | 45.06ms | 51.12ms | 52.03ms | 29.03ms |
| 200 | 2% | 37.04ms | 46.44ms | 50.32ms | 51.82ms | 29.90ms |

**p95 < 80ms is now met, comfortably, on every run measured, including at 55% host load** — versus F53's best-ever p95 of 109.55ms and worst of 196.45ms on the same box with the same query mix. The gate that F53 and F60 both called "not met, and unlikely to be met on any request-time-embedding path" is met by fixing the dependency version, no architecture change required.

## Re-baselining `query_embedder.py`'s own documented number

`query_embedder.py`'s module docstring benchmark (p50=46.5ms/p95=52.4ms, "fastembed 0.8.0", `onnxruntime` version unrecorded) is **superseded, not reproduced**: with `onnxruntime==1.24.4` pinned, the same standalone single-query benchmark now measures **p50 ~5.5-6ms/p95 ~7-10ms** — roughly 8x faster than the old documented number, not merely "back to it." The old number was not wrong for whatever version it was measured against, but citing it going forward would understate what this package now does; `query_embedder.py`'s docstring has been updated in this same change to record the *range* actually measured (1.19.2-1.25.1) and to point here for the full method, rather than quote a single stale pair of numbers next to an unrecorded dependency version — exactly the trap that caused this investigation.

## Recommendation for whoever next touches this package's dependencies

Re-run `now-search bench` (or the standalone `query_embedder.embed_query()` loop above) before raising the `onnxruntime<1.25` ceiling in `pyproject.toml`. If a future `onnxruntime` release is needed (security fix, new provider, Python version support), benchmark it against this table first — the gap between "compatible" and "fast" for this exact op mix is 4-20x, not noise.

## Reproduction

```bash
cd engine/packages/search
uv run python -m now_search.cli bench --db now_jakarta -n 200   # end-to-end

# standalone embedder-only loop (no DB in the loop), N=200:
uv run python -c "
import time
from now_search import query_embedder
query_embedder.warm_up()
times = []
for i in range(200):
    t0 = time.perf_counter()
    query_embedder.embed_query(f'rooftop bar senopati query variant {i}')
    times.append((time.perf_counter() - t0) * 1000)
times.sort()
print('p50', times[len(times)//2], 'p95', times[int(len(times)*0.95)])
"
```

---

# F53 — settling the p95 question

**Date:** 2026-09-09 · **Machine:** 16 logical CPUs (host) · **DB:** `now_jakarta` (real, 4,772 articles) · **Method:** `now-search bench` (`python -m now_search.cli bench --db now_jakarta -n 100`) plus a read-only, out-of-tree per-stage script (see "Method note" below). No source in `engine/packages/search/` was modified for this report.

## Machine load during measurement

The box was **not consistently quiet** — three other agents were active in the same repo throughout this session. Host CPU load (`Get-CimInstance Win32_Processor | Select LoadPercentage`) was sampled repeatedly across the measurement window and swung **between 28% and 96%**, with no run taken at a verified idle baseline. This is noted per-run below, and is itself part of the answer: F41's premise ("four agents plus other projects' containers") still holds today, just less severely on average.

## End-to-end `now-search bench` — 6 runs, n=100 each

| Run | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | min (ms) | host load nearby |
|---|---|---|---|---|---|---|
| 1 | 90.41 | 115.11 | 154.99 | 245.38 | 75.68 | not sampled |
| 2 | 150.97 | 196.45 | 214.87 | 291.15 | 93.68 | ~96% (spike observed) |
| 3 | 90.01 | 109.55 | 115.21 | 118.31 | 75.34 | ~28% |
| 4 | 100.58 | 123.27 | 148.62 | 152.09 | 79.46 | not sampled |
| 5 | 101.93 | 135.21 | 203.73 | 250.36 | 87.22 | not sampled |
| 6 | 101.22 | 124.05 | 145.06 | 150.20 | 83.50 | 69–77% |

**Spread:** p50 90–151 ms, p95 110–196 ms across the six runs. Excluding run 2 (the one run coinciding with an observed 96% host-load spike), the other five cluster tightly: p50 90–102 ms, p95 110–135 ms.

**Compared to prior figures:**
- F41 (previous measurement): p50 130–135 ms / p95 153–157 ms.
- E3.1 (earlier still, before the lexical materialisation and F49/F51/F52 landed): p50 55.1 ms / p95 65.4 ms.
- Today: p50 ~90–102 ms / p95 ~110–135 ms on 5 of 6 runs, worse on the 6th run coinciding with the heaviest observed contention.

**Verdict on the acceptance criterion:** p95 < 80 ms is **not met** on any of the 6 runs, including the two lowest (109.55 ms and 115.11 ms). Contention has genuinely improved things versus F41 (median run is ~20–30 ms faster on both p50 and p95), but the gate is still missed by 30–55 ms even on the best runs, and the machine was demonstrably not idle for any of them.

## Per-stage breakdown

`SearchEngine.search()`'s own `SearchTiming` bundles query embedding and the semantic pgvector query into one `semantic_ms` bucket, which is not fine-grained enough for this ticket's ask. To isolate embedding cost specifically, a read-only script (kept only in the local scratchpad, not committed to `search/`) calls `now_search.lexical.search_lexical`, `now_search.query_embedder.embed_query`, and `now_search.semantic.search_semantic` directly with independent timers — the exact same calls `engine.py`'s `search()` makes, in the same order, just measured separately. No `now_search` source file was edited.

Two runs against real `now_jakarta` data (n=100, n=150):

| Stage | n=100 p50 | n=100 p95 | n=150 p50 | n=150 p95 |
|---|---|---|---|---|
| lexical (`search_lexical`) | 2.43 ms | 26.25 ms | 2.57 ms | 31.05 ms |
| **embedding** (`embed_query`) | **86.28 ms** | **96.87 ms** | **82.33 ms** | **99.98 ms** |
| semantic SQL (`search_semantic`, vector already computed) | 4.23 ms | 6.00 ms | 4.34 ms | 5.71 ms |
| fusion (`reciprocal_rank_fusion`) | 0.13 ms | 0.28 ms | 0.13 ms | 0.28 ms |
| **sum of the above** | 97.54 ms | 121.66 ms | 94.83 ms | 127.23 ms |

**The embedding step is, again, essentially the entire p95 budget** — lexical, semantic SQL and fusion together contribute under 40 ms even at p95 in both runs (lexical's own p95 of ~26–31 ms is noise from the same host contention — its own dedicated suite measures p95 5.95 ms on `engine.article_search`, per F41/PROGRESS.md — not a change in the lexical query itself).

## Isolating the embedding step further — no DB, no other code in the loop

To rule out any interaction with the DB connection or the lexical/semantic queries, `query_embedder.embed_query()` was benchmarked completely standalone (model warmed up once, then called in a tight loop, no SQLAlchemy connection open at all):

| Run | n | p50 | p95 | p99 | min | max | host load nearby |
|---|---|---|---|---|---|---|---|
| A | 200 | 76.63 ms | 94.20 ms | 109.74 ms | 60.84 ms | 120.45 ms | not sampled |
| B | 120 | 86.7 ms | 125.1 ms | — | 63.0 ms | — | ~96% |
| C | 120 | 75.9 ms | 90.6 ms | — | 60.7 ms | — | ~28–47% |
| D | 120 | 93.9 ms | 169.0 ms | — | 71.9 ms | — | ~96% |

`query_embedder.py`'s own documented benchmark (fastembed 0.8.0, `threads=4`, the exact config this code path uses): **p50 = 46.5 ms / p95 = 52.4 ms.**

Every run above — including run C, taken during one of the lowest observed host-load windows (28–47%) — has a **p50 nearly double** the documented figure, and **not one of the 660 embedding calls sampled across these 4 runs ever got as low as the documented p50 of 46.5 ms** (the single lowest value observed, across all runs, was 60.7 ms).

## Verdict: contention, or regression?

**Both, but not in the proportion F41 assumed.**

- **Contention is real and measurable.** Host CPU load swung 28%–96% during this session (three other agents active in the same repo), and the one end-to-end run that landed during an observed 96% spike (run 2: p95 196.45 ms) is visibly worse than the other five (p95 109–135 ms). This matches F41's account.
- **But contention does not explain the gap to `query_embedder.py`'s own documented number.** That benchmark's precise job is to justify `threads=4` over `threads=16` — it's a same-machine, same-library-version (`fastembed 0.8.0`) comparison already accounting for typical dev-box load, not a pristine/idle-only number. Here, even the *single fastest embedding call observed across 660 samples and 4 independent runs* (60.7 ms) is 14 ms above that benchmark's documented **p95** (52.4 ms), and every run's p50 sits 65–100% above the documented p50 (46.5 ms) — including run C at the lowest observed load of the whole session. If contention alone explained F41's numbers, at least one low-load sample should have approached 46–52 ms; none did.
- **Working hypothesis for the residual gap** (not confirmed — this package's source was intentionally not touched, per scope): the installed `onnxruntime` is `1.29.0`; the docstring benchmark does not record which `onnxruntime` version it was measured against, and ONNX Runtime's CPU kernel performance is version-sensitive. This is a plausible, testable explanation for a ~30–40 ms floor shift and is a legitimate follow-up for whoever owns `search/`, separate from this report.

**Bottom line:** the box is quieter than when F41 measured it (median end-to-end p95 improved from ~155 ms to ~120 ms), so contention was a real contributor and F41's instinct was not wrong — but treating this purely as "CPU contention, resolves itself on a quiet machine" is not supported by today's data. There appears to be a genuine, reproducible ~30–40 ms floor in the embedding step versus its own documented baseline that survives even the quietest windows observed in this session. **p95 < 80 ms end-to-end is not met today, on any run, at any observed load level**, and closing it will need either a quieter box than any this session saw, or a fix/re-validation in `query_embedder.py`'s benchmark assumptions (out of this ticket's scope: `search/` source is explicitly not to be modified here).

## Reproduction

```bash
cd engine/packages/search
uv run python -m now_search.cli bench --db now_jakarta -n 100    # end-to-end, repeat several times
```

The per-stage and standalone-embedding scripts used for the breakdown above are ad hoc (scratchpad-only, not committed) and call only `now_search`'s existing public functions (`lexical.search_lexical`, `query_embedder.embed_query`, `semantic.search_semantic`, `rrf.reciprocal_rank_fusion`) with independent `time.perf_counter()` timers around each — no modification to any file in this package.

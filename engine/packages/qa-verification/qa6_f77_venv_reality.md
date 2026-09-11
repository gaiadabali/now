# QA.6 — F77 venv-reality check (2026-09-10)

Claim: "F60's pin reached only `search`; now all six packages (search, embeddings,
blender, inspector, rails, apps/api) resolve 1.24.4, verified installed."

## Lockfile spec (all 6, `uv.lock`) — matches claim
```
apps/api/uv.lock      -> onnxruntime 1.24.4
packages/blender      -> onnxruntime 1.24.4
packages/embeddings   -> onnxruntime 1.24.4
packages/inspector    -> onnxruntime 1.24.4
packages/rails        -> onnxruntime 1.24.4
packages/search       -> onnxruntime 1.24.4
```

## Installed reality (`.venv/Scripts/python.exe -c "import onnxruntime; print(onnxruntime.__version__)"`)
```
blender    -> 1.29.0   <-- SLOW VERSION, still installed
inspector  -> 1.29.0   <-- SLOW VERSION, still installed
embeddings -> 1.24.4
rails      -> 1.24.4
search     -> 1.24.4
apps/api   -> 1.24.4
```

mtimes prove why: blender/inspector's `uv.lock` was rewritten 2026-09-10 09:55
(the F77 fix), but their `onnxruntime` dist-info under `.venv` is still dated
2026-09-09 — i.e. `uv sync` was never re-run in those two package venvs after
the pyproject/lock fix landed. `embeddings`, `rails`, `search` DO show a
dist-info mtime matching (or after) their lock rewrite — they were synced.

Both blender and inspector actively import fastembed/onnxruntime at runtime
(similarity.py, reranker.py, blender.py; filters_adapter.py, generators.py) —
this is not a dormant transitive dependency, it is exercised code.

## Verdict
FAIL as stated ("all six packages resolve 1.24.4, verified installed") for
blender and inspector specifically — true only at the lockfile-spec level,
false in the actually-running interpreter. This is exactly the spec/lock/
reality gap the ticket brief warned to check for, and is exactly how the
original F60->F77 gap was missed (a pin can be "fixed" in every file that
matters and still not be running anywhere).

Fix: run `uv sync` (or equivalent) inside blender/.venv and inspector/.venv,
then re-verify by import, not by grepping pyproject/uv.lock.

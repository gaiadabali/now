"""Search domain -- `GET /v1/{site}/search`.

Hybrid BM25 + pgvector retrieval, RRF-fused (E3.1, `now_search`), over a
candidate pool resolved by §8's hard filters first. `service.py` holds
the orchestration and `schemas.py` the wire shape.
"""

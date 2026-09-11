"""Article vectors: real embeddings where they exist, a text proxy where they do not.

* Jakarta: `now_jakarta.engine.embeddings` (model `BAAI/bge-small-en-v1.5`,
  384-dim, 4,772 article rows) joined to `public.articles.legacy_wp_id`.
  Always `WHERE model = :model` (PROGRESS.md F42 -- the HNSW index does not
  discriminate by model).
* Bali: no embeddings exist yet (verified: `now_bali.engine.embeddings` is
  empty). The proxy is TF-IDF over title+lead+body reduced with truncated
  SVD (LSA, 128 dims). It is a **weaker** instrument -- lexical, not
  semantic -- and every number derived from it is labelled as such.
* If the database is unreachable, Jakarta silently gets the same proxy and
  the run records `vector_source = "tfidf-proxy (db unavailable)"`.

Both paths return L2-normalised float32 matrices aligned to a list of wp_ids.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from .sources import Article
from .text import tokens

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass
class VectorSpace:
    city: str
    source: str                 # "embeddings:<model>" | "tfidf-proxy" | "tfidf-proxy (db unavailable: ...)"
    wp_ids: list[int]
    matrix: np.ndarray          # (n, d) float32, rows L2-normalised
    is_proxy: bool

    def index(self) -> dict[int, int]:
        return {w: i for i, w in enumerate(self.wp_ids)}


def _normalise(m: np.ndarray) -> np.ndarray:
    m = m.astype(np.float32, copy=False)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _parse_vec(text: str) -> np.ndarray:
    return np.asarray([float(x) for x in text.strip("[]").split(",")], dtype=np.float32)


def load_embeddings(city: str, db_name: str | None = None, model: str = EMBEDDING_MODEL) -> VectorSpace | None:
    """Fetch real article embeddings for a city DB; None if the DB or the
    rows are unavailable (caller falls back to the proxy)."""
    db_name = db_name or f"now_{city}"
    try:
        from sqlalchemy import create_engine, text as sql
        from now_db.settings import city_database_url
        engine = create_engine(city_database_url(db_name), pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                sql(
                    "SELECT a.legacy_wp_id::bigint AS wp_id, e.vec::text AS vec "
                    "FROM engine.embeddings e JOIN public.articles a ON a.id::text = e.entity_id "
                    "WHERE e.entity_type = 'article' AND e.model = :model AND a.legacy_wp_id IS NOT NULL"
                ),
                {"model": model},
            ).fetchall()
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 -- any failure means "no embeddings", reported upstream
        return VectorSpace(city, f"unavailable: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}", [], np.zeros((0, 0), np.float32), True)
    if not rows:
        return None
    wp_ids = [int(r[0]) for r in rows]
    mat = np.vstack([_parse_vec(r[1]) for r in rows])
    return VectorSpace(city, f"embeddings:{model}", wp_ids, _normalise(mat), False)


def _doc_text(a: Article) -> str:
    # title weighted by repetition so it dominates the lexical signature the
    # way it dominates a reader's perception of "what this piece is"
    return f"{a.title} {a.title} {a.title} {a.excerpt} {a.text[:3000]}"


def tfidf_proxy(city: str, articles: list[Article], n_components: int = 128, max_features: int = 20000) -> VectorSpace:
    docs = [_doc_text(a) for a in articles]
    wp_ids = [a.wp_id for a in articles]
    try:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(tokenizer=tokens, preprocessor=None, lowercase=False, token_pattern=None,
                              min_df=3, max_df=0.5, max_features=max_features, sublinear_tf=True)
        X = vec.fit_transform(docs)
        k = min(n_components, X.shape[1] - 1, X.shape[0] - 1)
        Z = TruncatedSVD(n_components=k, random_state=0).fit_transform(X)
        return VectorSpace(city, "tfidf-proxy", wp_ids, _normalise(Z), True)
    except ImportError:
        return VectorSpace(city, "tfidf-proxy (numpy fallback)", wp_ids, _normalise(_numpy_tfidf(docs, max_features=6000)), True)


def _numpy_tfidf(docs: list[str], max_features: int) -> np.ndarray:
    """Dependency-free TF-IDF (dense, top-N vocabulary) for the case where
    scikit-learn cannot load. Coarser than the sklearn path; still lexical."""
    from collections import Counter
    df: Counter[str] = Counter()
    toks = [tokens(d) for d in docs]
    for t in toks:
        df.update(set(t))
    n = len(docs)
    vocab = [w for w, c in df.most_common() if 3 <= c <= 0.5 * n][:max_features]
    idx = {w: i for i, w in enumerate(vocab)}
    idf = np.array([math.log((1 + n) / (1 + df[w])) + 1.0 for w in vocab], dtype=np.float32)
    m = np.zeros((n, len(vocab)), dtype=np.float32)
    for r, t in enumerate(toks):
        c = Counter(w for w in t if w in idx)
        for w, k in c.items():
            m[r, idx[w]] = (1 + math.log(k)) * idf[idx[w]]
    return m


def vectors_for(city: str, articles: list[Article], use_db: bool = True) -> VectorSpace:
    if use_db:
        emb = load_embeddings(city)
        if emb is not None and emb.matrix.size:
            # align: keep only articles we have vectors for (should be all)
            have = set(emb.wp_ids)
            missing = [a.wp_id for a in articles if a.wp_id not in have]
            if missing:
                emb.source += f" ({len(missing)} articles without a vector)"
            return emb
        reason = emb.source if emb is not None else "no rows for this model"
        proxy = tfidf_proxy(city, articles)
        proxy.source = f"tfidf-proxy (embeddings {reason})"
        return proxy
    return tfidf_proxy(city, articles)


def cosine_centroid(mat: np.ndarray) -> np.ndarray:
    c = mat.mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n else c


_ws = re.compile(r"\s+")

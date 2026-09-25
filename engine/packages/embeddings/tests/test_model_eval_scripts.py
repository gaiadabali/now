"""Pure pieces of the WS6 measurement scripts (`scripts/measure_corpus_
language.py`, `scripts/compare_embedding_models.py`): the numbers in
docs/EDITION-2-PLAN.md come from these functions, so their arithmetic is
pinned here. No DB, no model, no langdetect (a stub detector stands in)."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lang = _load("measure_corpus_language")
cmp_ = _load("compare_embedding_models")

EN = "The restaurant serves grilled fish on the beach every evening at sunset."
ID = "Restoran ini menyajikan ikan bakar yang lezat di pantai dan juga untuk keluarga."


def _stub_detect(seg: str) -> str:
    return "id" if " yang " in f" {seg} " else "en"


def test_language_profile_splits_by_segment_and_weights_by_letters():
    prof = lang.language_profile(f"{EN}\n\n{ID}", _stub_detect)
    en_letters = sum(c.isalpha() for c in EN)
    id_letters = sum(c.isalpha() for c in ID)
    assert prof["letters"] == en_letters + id_letters
    assert prof["id_share_langdetect"] == pytest.approx(id_letters / (en_letters + id_letters))
    # the lexical instrument agrees on this text: the Indonesian sentence is
    # dense in function words (ini, yang, di, dan, juga, untuk), the English none
    assert prof["id_share_lexical"] == pytest.approx(prof["id_share_langdetect"])


def test_short_segments_are_not_classified():
    # "type: eat" / "format: news" lines that textbuild adds are below the
    # letter floor and must not dilute or inflate either share
    prof = lang.language_profile(f"type: eat\n\nformat: news\n\n{EN}", _stub_detect)
    assert prof["letters"] == sum(c.isalpha() for c in EN)
    assert prof["id_share_langdetect"] == 0.0


def test_english_that_names_a_warung_is_english():
    txt = "We had nasi goreng and babi guling at a warung on Jalan Raya Ubud before the ceremony."
    assert lang.language_profile(txt, _stub_detect)["id_share_lexical"] == 0.0


def test_buckets():
    assert lang.bucket(0.0) == "english"
    assert lang.bucket(lang.MIXED_AT) == "mixed"
    assert lang.bucket(lang.INDONESIAN_AT) == "indonesian"


def test_topk_is_exact_and_excludes_the_seed():
    rng = np.random.default_rng(0)
    m = rng.normal(size=(50, 8)).astype(np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    got = cmp_.topk(m, m[3], 5, exclude=3)
    brute = [i for i in np.argsort(-(m @ m[3])) if i != 3][:5]
    assert got == brute


def test_metrics_known_item():
    rel = {"a": 3.0}
    r = cmp_._metrics(["x", "a", "y"], rel)
    assert r["hit@10"] == 1.0 and r["recall@10"] == 1.0
    assert r["mrr@10"] == 0.5
    assert r["ndcg@10"] == pytest.approx(1 / math.log2(3))
    miss = cmp_._metrics(["x", "y"], rel)
    assert miss == {"ndcg@10": 0.0, "recall@10": 0.0, "hit@10": 0.0, "mrr@10": 0.0}


def test_recall_caps_at_k_relevant():
    rel = {str(i): 1.0 for i in range(20)}
    r = cmp_._metrics([str(i) for i in range(10)], rel)
    assert r["recall@10"] == 1.0


def test_paired_bootstrap_brackets_the_mean_difference():
    a = [0.0, 0.5, 1.0, 0.25] * 25
    b = [x + 0.1 for x in a]
    s = cmp_._paired_bootstrap(a, b)
    assert s["diff"] == pytest.approx(0.1)
    assert s["lo"] == pytest.approx(0.1) and s["hi"] == pytest.approx(0.1)
    same = cmp_._paired_bootstrap(a, a)
    assert same == {"diff": 0.0, "lo": 0.0, "hi": 0.0}


def test_cache_labels():
    assert cmp_.model_of("BAAI/bge-small-en-v1.5@fresh") == "BAAI/bge-small-en-v1.5"
    assert cmp_.model_of("BAAI/bge-m3") == "BAAI/bge-m3"

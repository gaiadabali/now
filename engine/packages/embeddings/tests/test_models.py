"""The embedding-model config point (`now_embeddings.models`): the default,
the env override, refusal of unregistered names, and the cross-language pin
that keeps the web tier's fallback equal to the Python default.

Pure-Python -- no model download, no DB."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from now_embeddings import models

REPO_ENGINE = Path(__file__).resolve().parents[3]  # engine/
WEB_CONFIG = REPO_ENGINE / "apps" / "web" / "src" / "lib" / "embeddingModel.ts"


def test_default_is_registered_and_storable():
    spec = models.get_spec(models.DEFAULT_MODEL)
    assert spec.storable, "the default model must fit engine.embeddings.vec -- every reader queries it"
    assert spec.dim == models.STORED_DIM


def test_active_model_defaults_without_env(monkeypatch):
    monkeypatch.delenv(models.ENV_VAR, raising=False)
    assert models.active_model_name() == models.DEFAULT_MODEL


def test_blank_env_means_default(monkeypatch):
    monkeypatch.setenv(models.ENV_VAR, "   ")
    assert models.active_model_name() == models.DEFAULT_MODEL


def test_env_selects_a_registered_model(monkeypatch):
    other = next(n for n in models.REGISTRY if n != models.DEFAULT_MODEL)
    monkeypatch.setenv(models.ENV_VAR, other)
    assert models.active_model_name() == other
    assert models.active_spec().name == other


def test_unregistered_env_value_fails_loudly(monkeypatch):
    # A typo must not silently point every reader at a model with no rows
    # (every semantic rail would come back empty, and nothing would error).
    monkeypatch.setenv(models.ENV_VAR, "BAAI/bge-smol-en-v1.5")
    with pytest.raises(models.UnknownEmbeddingModel):
        models.active_model_name()


def test_storable_tracks_the_column_width():
    widths = {n: s.dim for n, s in models.REGISTRY.items()}
    for name, spec in models.REGISTRY.items():
        assert spec.storable == (widths[name] == models.STORED_DIM)


def test_asymmetric_prefixes_only_where_the_model_was_trained_with_them():
    # bge v1.5 passages are embedded bare and the pipeline has never used
    # its optional query instruction -- adding either would change every
    # stored bge-small vector's neighbourhood.
    live = models.get_spec(models.DEFAULT_MODEL)
    assert live.query_prefix == "" and live.passage_prefix == ""
    e5 = models.get_spec("intfloat/multilingual-e5-small")
    assert (e5.query_prefix, e5.passage_prefix) == ("query: ", "passage: ")


def test_local_provider_constants_follow_the_config(monkeypatch):
    monkeypatch.delenv(models.ENV_VAR, raising=False)
    import now_embeddings.providers.local as local

    local = importlib.reload(local)
    assert local.MODEL_NAME == models.DEFAULT_MODEL
    assert local.DIM == models.get_spec(models.DEFAULT_MODEL).dim


def test_web_fallback_literal_matches_python_default():
    """The web tier cannot import this module, so it carries one fallback
    literal of its own. This is the check that keeps the two equal."""
    src = WEB_CONFIG.read_text(encoding="utf-8")
    m = re.search(r"NOW_EMBEDDING_MODEL\?\.trim\(\)\s*\|\|\s*'([^']+)'", src)
    assert m, f"could not find the fallback literal in {WEB_CONFIG}"
    assert m.group(1) == models.DEFAULT_MODEL
    assert models.ENV_VAR in src


def test_web_read_next_uses_the_config_point():
    sql_module = (WEB_CONFIG.parent / "recommendSql.ts").read_text(encoding="utf-8")
    assert "from './embeddingModel.ts'" in sql_module
    assert models.DEFAULT_MODEL not in sql_module, "recommendSql.ts must not carry its own model literal"


# Readers deliberately NOT on the switch: they score article vectors against
# artifacts that were BUILT in one model's space (the classifier's F120
# centroids, `engine/packages/classifier/data/embed_routing_centroids.json`,
# and the F118/F120 calibration measurements). Following NOW_EMBEDDING_MODEL
# would compare new-space vectors with old-space centroids -- both 384-d for
# e5-small, so nothing would error; the answers would just be wrong. They
# keep a pinned literal, and this keeps the pin equal to the default until a
# rollout rebuilds those artifacts (scripts/rollout_embedding_model.py).
CENTROID_SPACE_PINS = (
    REPO_ENGINE / "packages" / "taxonomy-evidence" / "src" / "now_taxonomy_evidence" / "vectors.py",
    REPO_ENGINE / "packages" / "eval" / "src" / "now_eval" / "calibration" / "embed_data.py",
)


@pytest.mark.parametrize("path", CENTROID_SPACE_PINS, ids=lambda p: p.parent.name + "/" + p.name)
def test_centroid_space_pins_match_the_default(path):
    src = path.read_text(encoding="utf-8")
    assert f'"{models.DEFAULT_MODEL}"' in src, f"{path} no longer pins the model its artifacts were built with"


def test_search_query_embedder_follows_the_config_point():
    src = (REPO_ENGINE / "packages" / "search" / "src" / "now_search" / "query_embedder.py").read_text(encoding="utf-8")
    assert "from now_embeddings.providers.local import" in src and "MODEL_NAME" in src
    code = src.split('"""', 2)[-1]  # past the module docstring, which may name the model in prose
    assert models.DEFAULT_MODEL not in code, "query_embedder must not carry its own model literal"

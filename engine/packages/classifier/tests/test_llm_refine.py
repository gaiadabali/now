from __future__ import annotations

import json

import pytest

from now_classifier.facet_tagging import llm_refine


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for var in ("ANTHROPIC_API_KEY", "OLLAMA_CLOUD_API_KEY", "OLLAMA_CLOUD_BASE_URL", "NOW_LLM_ENV_FILE"):
        monkeypatch.delenv(var, raising=False)
    # Point at an empty env file so a real developer's secrets file never
    # leaks into this test's "no key" assertions.
    monkeypatch.setenv("NOW_LLM_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    monkeypatch.setattr(llm_refine, "CACHE_DIR", tmp_path / "cache")


def test_fails_closed_with_no_key_anywhere() -> None:
    assert llm_refine.load_llm_config() is None


def test_anthropic_key_takes_priority(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = llm_refine.load_llm_config()
    assert cfg is not None
    assert cfg.provider == "anthropic"
    assert "sk-ant-test" not in cfg.safe_repr  # never printed unredacted


def test_ollama_key_used_when_no_anthropic_key(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "ollama-test-key")
    cfg = llm_refine.load_llm_config()
    assert cfg is not None
    assert cfg.provider == "ollama"
    assert cfg.base_url == "https://ollama.com/v1"
    assert cfg.model == "deepseek-v4-flash"


def test_ollama_key_read_from_env_file(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / "ollama-cloud.env"
    env_file.write_text("OLLAMA_CLOUD_API_KEY=from-file-key\nOLLAMA_CLOUD_MODEL_FAST=deepseek-v4-flash\n", encoding="utf-8")
    monkeypatch.setenv("NOW_LLM_ENV_FILE", str(env_file))
    cfg = llm_refine.load_llm_config()
    assert cfg is not None
    assert cfg.api_key == "from-file-key"


def test_parse_applies_true() -> None:
    assert llm_refine._parse_applies('{"applies": true}') is True


def test_parse_applies_false() -> None:
    assert llm_refine._parse_applies('{"applies": false}') is False


def test_parse_applies_strips_markdown_fences() -> None:
    assert llm_refine._parse_applies('```json\n{"applies": true}\n```') is True


def test_parse_applies_unparseable_is_none() -> None:
    assert llm_refine._parse_applies("not json at all") is None
    assert llm_refine._parse_applies("") is None
    assert llm_refine._parse_applies(None) is None


def test_judge_one_returns_none_on_unparseable_response(monkeypatch) -> None:
    cfg = llm_refine.LLMConfig(provider="ollama", base_url="https://example.invalid", api_key="k", model="m")
    monkeypatch.setattr(llm_refine, "_chat_ollama", lambda *a, **kw: "garbage, not json")
    result = llm_refine.judge_one(cfg, "vibe", "Romantic", "A Title", "some lead text")
    assert result is None


def test_judge_one_caches_to_disk(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(llm_refine, "CACHE_DIR", cache_dir)
    cfg = llm_refine.LLMConfig(provider="ollama", base_url="https://example.invalid", api_key="k", model="m")
    calls = {"n": 0}

    def fake_chat(*_a, **_kw):
        calls["n"] += 1
        return '{"applies": true}'

    monkeypatch.setattr(llm_refine, "_chat_ollama", fake_chat)
    first = llm_refine.judge_one(cfg, "vibe", "Romantic", "A Title", "some lead text")
    second = llm_refine.judge_one(cfg, "vibe", "Romantic", "A Title", "some lead text")
    assert first is True
    assert second is True
    assert calls["n"] == 1  # second call served from cache, not the network


def test_judge_one_fails_closed_on_auth_error(monkeypatch) -> None:
    """A 401/403 must abstain (None), never raise, never retry forever."""
    class FakeResponse:
        status_code = 401

        def json(self):  # pragma: no cover - not reached
            return {}

    monkeypatch.setattr(llm_refine.time, "sleep", lambda *_: None)

    def fake_post(*_a, **_kw):
        return FakeResponse()

    fake_requests = type("M", (), {"post": staticmethod(fake_post)})
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)
    cfg = llm_refine.LLMConfig(provider="ollama", base_url="https://example.invalid", api_key="bad-key", model="m")
    result = llm_refine.judge_one(cfg, "vibe", "Romantic", "A Title", "some lead text")
    assert result is None

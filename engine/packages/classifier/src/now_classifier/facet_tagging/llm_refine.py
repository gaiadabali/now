"""Optional LLM refinement, OFF by default.

Deliverable #4 of the WS5 ticket: an LLM pass over ONLY the borderline
band per facet (the band `calibration.py` measured just under the 0.80
ship bar -- `lead`, for every one of the five alias-based facets;
`price_band` has no borderline band, both its bands already ship). Never
invoked by `tag-facets` itself -- a separate command
(`now-classifier refine-facets`), so a normal re-run of the base job never
depends on network access or a paid/rate-limited provider.

**No valid key exists at the time this was written** (the shared Ollama
Cloud key returns Unauthorized; there is no Anthropic key in this
environment -- see the ticket brief). This module is therefore
UNTESTED against a real provider response; its unit tests
(`tests/test_llm_refine.py`) mock the HTTP layer. `load_llm_config()`
returning `None` (no key found anywhere) is the expected, normal path
today, and every caller must treat it as "skip cleanly", never an error.

Provider-agnostic by design: checks `ANTHROPIC_API_KEY` first (if a key
ever appears there, Anthropic's Messages API), then the Ollama Cloud
OpenAI-compatible endpoint (env vars per the user's own global notes:
`OLLAMA_CLOUD_API_KEY`/`OLLAMA_CLOUD_BASE_URL` from
`~/.claude/secrets/ollama-cloud.env`, base `https://ollama.com/v1`, model
`deepseek-v4-flash` -- the "fast" tier, appropriate for a high-volume
yes/no relevance judgment, not the heavier `qwen3.5:397b`). Both paths
speak the same minimal `chat(system, user) -> str | None` shape so the
rest of this module (`refine_batch`) never branches on which provider
answered.

Writes `source='ai'` (never `'inferred'`, so a base-job re-run's stale-
retraction pass -- scoped to `source='inferred'` only, see `db.py` -- can
never delete an LLM-refined row, and vice versa: this module never
retracts an `inferred` row either, it only adds `ai` ones). Confidence is
a fixed, disclosed, conservative constant (`LLM_CONFIDENCE`), not a
per-item probability the provider does not actually return -- stamping an
invented per-item number would repeat exactly the mistake
`now_classifier.confidence`'s own docstring warns against.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "llm-facet-refine"
DEFAULT_OLLAMA_ENV_FILE = Path.home() / ".claude" / "secrets" / "ollama-cloud.env"

# A single LLM pass, never independently measured against a held-out
# labelled sample the way MEASURED_PRECISION's numbers were -- so this
# sits below every measured band this job ships (0.80-0.95), not at or
# above them. Still comfortably an "inferred, worth surfacing" tag, not a
# guess: the whole point of this path is that a real model read the
# actual article text for this one decision.
LLM_CONFIDENCE = 0.75

SYSTEM_PROMPT = (
    "You are checking whether a proposed tag genuinely applies to a magazine article, for a lifestyle "
    "magazine's reader-preference system (NOW! Jakarta / NOW! Bali). You will be given the article's title "
    "and opening text, a facet name, and a candidate term. Answer ONLY with compact JSON: "
    '{"applies": true|false}. No prose, no markdown fences. Be strict: only true if a reader who picked '
    "this term as an interest would genuinely expect this article to satisfy it."
)


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # "anthropic" | "ollama"
    base_url: str
    api_key: str
    model: str

    @property
    def safe_repr(self) -> str:
        return f"{self.provider} {self.base_url} model={self.model} key=<redacted:{len(self.api_key)} chars>"


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].split("\t#", 1)[0]
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_llm_config() -> LLMConfig | None:
    """Fails closed: returns `None` (never raises) when no usable key is
    found anywhere -- the expected result today. Never prints or logs the
    key itself, only `LLMConfig.safe_repr` (redacted) is ever suitable to
    log."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        return LLMConfig(
            provider="anthropic",
            base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
            api_key=anthropic_key,
            model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        )
    env_path = Path(os.environ.get("NOW_LLM_ENV_FILE", str(DEFAULT_OLLAMA_ENV_FILE)))
    file_env = _read_env_file(env_path) or {}
    key = os.environ.get("OLLAMA_CLOUD_API_KEY") or file_env.get("OLLAMA_CLOUD_API_KEY")
    if not key:
        return None
    base = os.environ.get("OLLAMA_CLOUD_BASE_URL") or file_env.get("OLLAMA_CLOUD_BASE_URL") or "https://ollama.com/v1"
    model = os.environ.get("OLLAMA_CLOUD_MODEL_FAST") or file_env.get("OLLAMA_CLOUD_MODEL_FAST") or "deepseek-v4-flash"
    return LLMConfig(provider="ollama", base_url=base.rstrip("/"), api_key=key, model=model)


def _cache_key(cfg: LLMConfig, user_prompt: str) -> Path:
    h = hashlib.sha256(f"{cfg.provider}:{cfg.model}:{user_prompt}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _chat_ollama(cfg: LLMConfig, user_prompt: str, timeout: int | None = None) -> str | None:
    import requests
    payload = {
        "model": cfg.model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        "max_tokens": 100,
        "temperature": 0,
    }
    # A local reasoning model (gemma4 on a laptop's Ollama, the only provider
    # that worked on 2026-09-25) spends a 100-token budget "thinking" and
    # returns empty content. `NOW_LLM_REASONING_EFFORT=none` turns that off
    # on OpenAI-compatible servers that honour it; unset, the request is
    # unchanged. The first local call also loads the model (~60 s), hence
    # the overridable timeout.
    effort = os.environ.get("NOW_LLM_REASONING_EFFORT")
    if effort:
        payload["reasoning_effort"] = effort
    timeout = timeout or int(os.environ.get("NOW_LLM_TIMEOUT_S", "60"))
    for attempt in range(3):
        try:
            r = requests.post(
                f"{cfg.base_url}/chat/completions", json=payload, timeout=timeout,
                headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
            )
            if r.status_code in (401, 403):
                return None  # bad/expired key -- fail closed, no retry (retrying won't fix auth)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            body = r.json()
            return (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        except Exception:  # noqa: BLE001 -- network/provider error: retry then give up, never crash the caller
            time.sleep(2 * (attempt + 1))
    return None


def _chat_anthropic(cfg: LLMConfig, user_prompt: str, timeout: int = 60) -> str | None:
    import requests
    payload = {
        "model": cfg.model,
        "max_tokens": 100,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    for attempt in range(3):
        try:
            r = requests.post(
                f"{cfg.base_url}/v1/messages", json=payload, timeout=timeout,
                headers={"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            )
            if r.status_code in (401, 403):
                return None
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            body = r.json()
            parts = body.get("content") or []
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def _parse_applies(raw: str | None) -> bool | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except ValueError:
        return None
    val = parsed.get("applies")
    return bool(val) if isinstance(val, bool) else None


def judge_one(cfg: LLMConfig, facet: str, term_label: str, title: str, lead: str) -> bool | None:
    """Returns True/False (the LLM's verdict) or None (no usable answer --
    caller must treat as abstain, i.e. do not write). Cached on disk keyed
    by the exact prompt, so a re-run of `refine-facets` costs zero calls
    for a candidate it already judged."""
    user_prompt = (
        f"Facet: {facet}\nCandidate term: {term_label}\n"
        f"Article title: {title}\nArticle opening text: {lead[:600]}\n\n"
        # An f-string, not `.format()`: Python binds `.format()` to the WHOLE
        # implicitly concatenated literal above, already-substituted title and
        # lead included, so an article whose text held a "}" crashed the run
        # (Jakarta, 2026-09-25). The rendered prompt is byte-identical for every
        # other article, so the on-disk verdict cache stays valid.
        f'Does "{term_label}" genuinely apply to this article? Answer as JSON: {{"applies": true|false}}'
    )
    cache = _cache_key(cfg, user_prompt)
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))["applies"]
    raw = _chat_anthropic(cfg, user_prompt) if cfg.provider == "anthropic" else _chat_ollama(cfg, user_prompt)
    verdict = _parse_applies(raw)
    if verdict is not None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"applies": verdict}), encoding="utf-8")
    return verdict

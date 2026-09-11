"""Optional second opinion from the shared OpenAI-compatible provider.

Contract with the rest of the pack: the LLM can only *add doubt*. A category
is never auto-accepted because the model agreed; it can lose auto-acceptance
because the model disagreed with the evidence-based proposal on `type` or
`format`. So the pack degrades cleanly -- without the provider, the verdicts
are the heuristic ones and the report says so.

Credentials: read from the env file named by `NOW_LLM_ENV_FILE` (default
`~/.claude/secrets/ollama-cloud.env`) or from the process environment
(`OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_BASE_URL`, `OLLAMA_CLOUD_MODEL_GENERAL`).
The key is never logged, never written to the cache, never in the output.
Responses are cached in `<package>/.cache/llm/<sha256 of prompt>.json` so a
re-render costs zero calls against the shared weekly cap.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm"
DEFAULT_ENV_FILE = Path.home() / ".claude" / "secrets" / "ollama-cloud.env"

SYSTEM = (
    "You are auditing how legacy WordPress categories of two city lifestyle magazines (NOW! Jakarta, NOW! Bali) "
    "decompose into a facet model. Facets: type (one of stay, eat, drink, do, wellness, shop, event, editorial), "
    "subtype (free text, one of the type's children or null), format (one of news, event, offer, review, listing, guide, "
    "feature, heritage, people, city-guide, opinion), location (a slug or 'per-article'). "
    "A facet value is 'per-article' when the category does not determine it. Judge from the titles given. "
    "Answer ONLY with compact JSON, no prose, no markdown fences."
)


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def safe_repr(self) -> str:
        return f"{self.base_url} model={self.model} key=<redacted:{len(self.api_key)} chars>"


def load_config() -> LLMConfig | None:
    env: dict[str, str] = {}
    path = Path(os.environ.get("NOW_LLM_ENV_FILE", str(DEFAULT_ENV_FILE)))
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].split("\t#", 1)[0]  # inline comments ("MODEL=glm-5.2   # general")
            env[k.strip()] = v.strip().strip('"').strip("'")
    key = os.environ.get("OLLAMA_CLOUD_API_KEY") or env.get("OLLAMA_CLOUD_API_KEY")
    base = os.environ.get("OLLAMA_CLOUD_BASE_URL") or env.get("OLLAMA_CLOUD_BASE_URL") or "https://ollama.com/v1"
    model = os.environ.get("NOW_LLM_MODEL") or os.environ.get("OLLAMA_CLOUD_MODEL_GENERAL") or env.get("OLLAMA_CLOUD_MODEL_GENERAL") or "glm-5.2"
    if not key:
        return None
    return LLMConfig(base.rstrip("/"), key, model)


def _cache_key(payload: dict) -> Path:
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _chat(cfg: LLMConfig, messages: list[dict], max_tokens: int = 1800, timeout: int = 120) -> dict | None:
    import requests
    payload = {"model": cfg.model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
    cache = _cache_key(payload)
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            r = requests.post(f"{cfg.base_url}/chat/completions", json=payload, timeout=timeout,
                              headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"})
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            body = r.json()
            content = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            content = content.strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content[content.find("{"):]
            parsed = json.loads(content[content.find("{"): content.rfind("}") + 1])
            out = {"model": body.get("model", cfg.model), "usage": body.get("usage"), "result": parsed}
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            return out
        except (ValueError, KeyError):
            return None  # unparseable -> treat as no opinion
        except Exception:  # noqa: BLE001 -- network/provider errors: retry then give up
            time.sleep(2 * (attempt + 1))
    return None


def category_prompt(city: str, name: str, description: str, n: int, years: str, titles: list[str], proposal: dict, parent: str | None) -> list[dict]:
    lines = "\n".join(f"- {t}" for t in titles)
    user = (
        f"City: {city}. Legacy category: \"{name}\" (parent: {parent or 'none'}; {n} published articles, {years}).\n"
        f"Editor's category description: {description or '(none)'}\n"
        f"Evidence-based proposal under review: type={proposal.get('type') or 'per-article'}, subtype={proposal.get('subtype') or 'per-article'}, "
        f"format={proposal.get('format') or 'per-article'}, location={proposal.get('location') or 'per-article'}.\n"
        f"Representative titles across the category's date range:\n{lines}\n\n"
        "Return JSON: {\"type\": <value or \"per-article\">, \"subtype\": <value or \"per-article\">, \"format\": <value or \"per-article\">, "
        "\"location\": <slug or \"per-article\">, \"agree_with_proposal\": true|false, \"split_recommended\": true|false, "
        "\"split_into\": [<2-3 short labels, or empty>], \"confidence\": \"high\"|\"medium\"|\"low\", \"rationale\": <one sentence, max 40 words>}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def second_opinions(cfg: LLMConfig, jobs: dict[str, list[dict]], workers: int = 4) -> dict[str, dict | None]:
    """jobs: key -> messages. Returns key -> parsed result (or None)."""
    out: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {k: ex.submit(_chat, cfg, m) for k, m in jobs.items()}
        for k, f in futs.items():
            try:
                out[k] = f.result()
            except Exception:  # noqa: BLE001
                out[k] = None
    return out

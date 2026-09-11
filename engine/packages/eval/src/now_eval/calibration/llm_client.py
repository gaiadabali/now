"""Blind proxy labelling via the shared Ollama Cloud provider
(`C:\\Users\\Hansel\\.claude\\secrets\\ollama-cloud.env`).

**Blindness is load-bearing, not a nicety.** The prompt sent to the model
carries only the article's title + a body excerpt -- never the WP category,
never `now_classifier`'s proposed type/format, never its confidence. If the
model saw any of those it would just be agreeing with the same prior the
classifier already leans on, reproducing F96's circularity in a more
expensive form. `build_prompt` below is the single place that constructs the
message; it is unit-tested (`tests/calibration/test_llm_client.py`) to assert
none of the forbidden fields ever appear in the rendered text.

**ARCHITECTURE.md §1** ("deterministic engine decides, LLM narrates"): this
client is invoked exactly once, offline, by a human-initiated calibration
script. Nothing in `now_classifier` or any runtime request path imports this
module or could reach it.

The API key is read from the environment (or the secrets `.env` file) and is
never logged, printed, or included in any exception message this module
raises -- `_redact` scrubs it defensively even from unexpected requests
exceptions.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SECRETS_PATH = Path.home() / ".claude" / "secrets" / "ollama-cloud.env"

TYPE_DESCRIPTIONS = {
    "stay": "Hotels, resorts, villas, serviced apartments, glamping and other accommodation.",
    "eat": "Restaurants, cafes, bakeries, street food, food courts and other places to eat.",
    "drink": "Bars, rooftop bars, cocktail bars, breweries/wineries, nightclubs, pubs and other places to drink.",
    "do": "Attractions, museums, galleries, tours, adventure/watersports, workshops, temples, nature spots and other things to do or see.",
    "wellness": "Spas, gyms, yoga studios, clinics, salons and wellness retreats.",
    "shop": "Malls, boutiques, markets, artisan shops and bookshops.",
    "event": "A DATED happening -- festival, concert, exhibition, conference, sports fixture, community event or performance. Use this when the article is announcing or previewing something happening on a specific date, not a venue review.",
    "editorial": "General editorial content that is not about one specific venue and not a dated happening -- news, opinion, profiles, business, education, heritage, city guides, culture, lifestyle.",
    "unknown": "Use only if the article genuinely cannot be classified into any type above from its content alone.",
}

FORMAT_DESCRIPTIONS = {
    "news": "Time-bound announcement: openings, appointments, launches, updates.",
    "event": "Announcement or preview of a dated happening.",
    "offer": "Promotion or deal.",
    "review": "First-person evaluation of a venue, show, product or trip.",
    "listing": "Roundup or listicle tied to a period ('New restaurants in Jakarta 2024', 'Best brunches this month').",
    "guide": "Timeless how-to, thematic or area guide ('Where to eat in Senopati').",
    "feature": "Long-form editorial not tied to a date.",
    "heritage": "History and heritage long-form.",
    "people": "Profile or interview.",
    "city-guide": "Destination guide covering a place, region or country.",
    "opinion": "Column or op-ed.",
}

FORBIDDEN_SUBSTRINGS_HINT = (
    # Sanity-checked by tests: none of these words describe a classifier
    # proposal or WP category and must never appear in the rendered prompt.
    "wp category", "wordpress category", "classifier proposed", "confidence",
    "primary_type", "primary category",
)


def build_prompt(title: str, excerpt: str, text_excerpt: str) -> list[dict]:
    type_lines = "\n".join(f"- {slug}: {desc}" for slug, desc in TYPE_DESCRIPTIONS.items())
    format_lines = "\n".join(f"- {slug}: {desc}" for slug, desc in FORMAT_DESCRIPTIONS.items())
    system = (
        "You are labelling articles from a Jakarta/Bali lifestyle magazine for an independent "
        "evaluation dataset. You will be given ONLY an article's title and a body excerpt -- no "
        "category metadata of any kind, because the whole point of this labelling pass is to be "
        "an independent check, blind to any prior categorization. Read the text and decide, from "
        "its content alone:\n\n"
        f"TYPE (what kind of subject this is):\n{type_lines}\n\n"
        f"FORMAT (what shape of piece this is):\n{format_lines}\n\n"
        "Respond with ONLY a JSON object, no other text: "
        '{"type": "<one type slug>", "format": "<one format slug>", '
        '"type_reasoning": "<one short sentence>", "format_reasoning": "<one short sentence>"}'
    )
    body = f"TITLE: {title}\n\nEXCERPT: {excerpt}\n\nBODY: {text_excerpt}".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": body},
    ]


@dataclass(frozen=True)
class ProxyLabel:
    wp_id: int
    city: str
    type: str | None
    format: str | None
    type_reasoning: str
    format_reasoning: str
    raw: str
    error: str | None = None


def _redact(text: str, api_key: str | None) -> str:
    if api_key:
        text = text.replace(api_key, "<redacted>")
    return text


def load_ollama_env(secrets_path: Path = DEFAULT_SECRETS_PATH) -> dict[str, str]:
    """Reads the shared secrets file into a dict without ever printing it.
    Environment variables already set take precedence (lets CI or a caller
    override without touching the file)."""
    values: dict[str, str] = {}
    if secrets_path.is_file():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split("#", 1)[0]  # strip a trailing inline comment (e.g. "glm-5.2   # general reasoning / chat brain")
            values[k.strip()] = v.strip()
    for k in ("OLLAMA_CLOUD_BASE_URL", "OLLAMA_CLOUD_API_KEY", "OLLAMA_CLOUD_MODEL_GENERAL",
              "OLLAMA_CLOUD_MODEL_FAST", "OLLAMA_CLOUD_MODEL_CODE", "OLLAMA_CLOUD_MODEL_BIG"):
        if os.environ.get(k):
            values[k] = os.environ[k]
    return values


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = _JSON_RE.search(content)
        if m:
            return json.loads(m.group(0))
        raise


def label_article(
    wp_id: int,
    city: str,
    title: str,
    excerpt: str,
    text_excerpt: str,
    env: dict[str, str],
    model: str | None = None,
    timeout: float = 60.0,
    max_retries: int = 3,
) -> ProxyLabel:
    import requests

    base_url = env["OLLAMA_CLOUD_BASE_URL"].rstrip("/")
    api_key = env["OLLAMA_CLOUD_API_KEY"]
    model = model or env.get("OLLAMA_CLOUD_MODEL_GENERAL", "glm-5.2")
    messages = build_prompt(title, excerpt, text_excerpt)

    last_err: str | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                # max_tokens is generous: glm-5.2 is a reasoning model that spends tokens on a
                # hidden "reasoning" field before it emits the requested JSON in "content" -- a
                # tight budget here truncates before any content is produced at all (observed
                # live: max_tokens=300 -> content="", finish_reason="length").
                json={"model": model, "messages": messages, "temperature": 0.0, "max_tokens": 800},
                timeout=timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = _parse_response(content)
            return ProxyLabel(
                wp_id=wp_id, city=city,
                type=parsed.get("type"), format=parsed.get("format"),
                type_reasoning=str(parsed.get("type_reasoning", ""))[:300],
                format_reasoning=str(parsed.get("format_reasoning", ""))[:300],
                raw=content,
            )
        except Exception as exc:  # noqa: BLE001 - retried below, redacted on final failure
            last_err = _redact(str(exc), api_key)
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return ProxyLabel(wp_id=wp_id, city=city, type=None, format=None,
                       type_reasoning="", format_reasoning="", raw="", error=last_err)

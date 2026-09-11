"""Optional LLM adjudication for genuinely ambiguous merge pairs, via the
shared Ollama Cloud provider (`C:\\Users\\Hansel\\.claude\\secrets\\
ollama-cloud.env`). OFF by default (`pipeline.py` only wires this in when
`--use-llm` is passed) -- the deterministic clustering in dedup.py is the
primary mechanism per ARCHITECTURE.md Sec.1 ("deterministic engine
decides, LLM narrates"); this is reserved for the pairs deterministic
scoring itself could not confidently place on either side of the gate.

Hard call budget, enforced here, not just documented: `Adjudicator` raises
once `max_calls` is exhausted rather than silently degrading to "always
undecided", so a caller cannot accidentally blow through the shared
weekly-rate-limited key without finding out.

The API key is read from the env file at call time and never logged,
printed, or included in any exception message.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_KEY_FILE = Path(r"C:\Users\Hansel\.claude\secrets\ollama-cloud.env")
DEFAULT_MODEL = "glm-5.2"  # general-purpose tier; this is a yes/no judgement call, not code
BASE_URL = "https://ollama.com/v1"


def _read_key(key_file: Path = DEFAULT_KEY_FILE) -> str:
    if not key_file.exists():
        raise RuntimeError(f"Ollama Cloud key file not found at {key_file} -- cannot use --use-llm.")
    for line in key_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip().upper() in ("OLLAMA_API_KEY", "OLLAMA_KEY", "API_KEY"):
            return value.strip().strip('"').strip("'")
    raise RuntimeError(f"No API key found in {key_file}.")


class BudgetExceeded(RuntimeError):
    pass


class Adjudicator:
    """Ask "are these the same real-world venue?" for one ambiguous
    (name_a, name_b) pair. Returns True/False/None (None = model declined
    to commit -- treated as "review", never as a merge)."""

    def __init__(self, *, max_calls: int = 150, model: str = DEFAULT_MODEL, key_file: Path = DEFAULT_KEY_FILE):
        self.max_calls = max_calls
        self.calls_made = 0
        self._model = model
        self._api_key = _read_key(key_file)

    def __call__(self, name_a: str, name_b: str) -> bool | None:
        if self.calls_made >= self.max_calls:
            raise BudgetExceeded(
                f"LLM adjudication budget ({self.max_calls} calls) exhausted -- remaining ambiguous "
                "pairs are routed to the review queue instead of being decided. See pipeline report."
            )
        self.calls_made += 1

        import httpx  # optional dependency (`now-place-extraction[llm]`)

        prompt = (
            "You compare two short strings that are candidate names for the SAME real-world "
            "venue (hotel, restaurant, bar, shop, etc.), extracted from unrelated mentions in a "
            "city magazine's articles.\n"
            f'Name A: "{name_a}"\nName B: "{name_b}"\n\n'
            "Are these almost certainly the SAME specific venue (allowing for abbreviation, "
            "punctuation, or a dropped/added brand suffix), as opposed to two DIFFERENT venues "
            "(even if related, e.g. two branches of the same chain in different areas, or a "
            "generic word overlap)? Answer with exactly one word: YES, NO, or UNSURE."
        )
        resp = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 5,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
        if answer.startswith("YES"):
            return True
        if answer.startswith("NO"):
            return False
        return None

"""F66 QA.5 adversarial validator battery.

POSTs a battery of hostile/edge-case entity_id values to the REAL running
engine-api /v1/jakarta/events endpoint and records the exact HTTP status
and body for each. No mocking -- this hits the live uvicorn process
started for this QA pass on http://127.0.0.1:8123.

Run: .venv/Scripts/python.exe adversarial_battery.py   (from engine/apps/api,
     with the venv that has httpx, or use the stdlib fallback below)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
import uuid

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8123/v1/jakarta/events"


def post(entity_id_value):
    session_id = str(uuid.uuid4())
    anon_id = str(uuid.uuid4())
    ts = int(time.time() * 1000)
    payload = {
        "interactions": [],
        "impressions": [
            {
                "session_id": session_id,
                "anon_id": anon_id,
                "surface": "article",
                "rail": "complementary",
                "entity_id": entity_id_value,
                "position": 1,
                "ts": ts,
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), body.decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), body.decode()
    except Exception as e:  # noqa: BLE001
        return "EXC", repr(e), body.decode()


CASES = [
    ("valid_numeric_13", "13"),
    ("negative", "-1"),
    ("zero_padded_007", "007"),
    ("zero_padded_0013", "0013"),
    ("huge_50_digits", "1" * 50),
    ("unicode_arabic_indic_digits", "١٢٣"),  # ١٢٣
    ("unicode_fullwidth_digits", "１２３"),  # 123 fullwidth
    ("leading_trailing_whitespace", "  13  "),
    ("leading_whitespace_only", " 13"),
    ("sql_drop_table", "1; DROP TABLE interactions;--"),
    ("sql_or_true", "1' OR '1'='1"),
    ("xss_script", "<script>alert(1)</script>"),
    ("leftover_uuid", "0a1c2d3e-4f50-4617-9283-a4b5c6d7e8f9"),
    ("empty_string", ""),
    ("decimal", "1.0"),
    ("scientific_notation", "1e2"),
    ("plus_prefixed", "+13"),
    ("valid_zero", "0"),
    ("null_literal_none", None),  # will be sent as JSON null
]

if __name__ == "__main__":
    results = []
    for name, val in CASES:
        status, resp_body, req_body = post(val)
        results.append(
            {
                "case": name,
                "entity_id_sent": val,
                "request_body": req_body,
                "status": status,
                "response_body": resp_body,
            }
        )
        print(f"=== {name} ===")
        print(f"request entity_id: {val!r}")
        print(f"request body: {req_body}")
        print(f"HTTP {status}")
        print(f"response body: {resp_body}")
        print()

    with open("adversarial_results.json", "w") as f:
        json.dump(results, f, indent=2)

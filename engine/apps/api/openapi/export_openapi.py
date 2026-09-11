"""Exports engine-api's OpenAPI schema to a JSON file, without booting a
server or touching any database.

Building the FastAPI `app` object is safe with zero real infrastructure
present: engine construction (`create_async_engine`) is lazy in SQLAlchemy's
asyncio dialect -- no connection is attempted until something executes a
query, and this script never runs the lifespan (no queries execute).

Usage:
    python openapi/export_openapi.py [output_path]

Defaults to writing `openapi/openapi.json` next to this script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402  (path must be set up first)


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("openapi.json")
    schema = app.openapi()
    out_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()

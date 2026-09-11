"""E1.8 — JSONL (E1.1 extraction contract) -> city DB `public` loader.

Public entry point is the `now-loader` CLI (`now_loader.cli`). See the
package README for the full design writeup (idempotency keys, the
places.type/subtype sentinel, the events content-loss gap, the events
ledger, and how E1.3's future media URL rewrite should hook in).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"

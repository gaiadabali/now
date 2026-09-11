"""One-shot WordPress (UpdraftPlus/MariaDB) -> JSONL extraction for NOW! Jakarta (E1.1).

WordPress is a migration source only. This package never runs against a live
WP instance and never writes back to it — it reads a restored MariaDB dump
and emits newline-delimited JSON under jakarta/content/extracted/.
"""

__version__ = "0.1.0"

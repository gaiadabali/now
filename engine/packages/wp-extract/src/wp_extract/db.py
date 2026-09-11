from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
import pymysql.cursors

from wp_extract.config import Config


@contextmanager
def connect(cfg: Config) -> Iterator[pymysql.connections.Connection]:
    conn = pymysql.connect(
        host=cfg.db_host,
        port=cfg.db_port,
        user=cfg.db_user,
        password=cfg.db_password,
        database=cfg.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSDictCursor,  # server-side, streams rows
        read_timeout=300,
        write_timeout=300,
    )
    try:
        yield conn
    finally:
        conn.close()


def query(conn: pymysql.connections.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Buffered fetch — fine for anything up to a few hundred thousand rows
    of this dump's row sizes (verified against restored DB, see restore.sh).
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def scalar(conn: pymysql.connections.Connection, sql: str, params: tuple = ()) -> Any:
    with conn.cursor(pymysql.cursors.Cursor) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None

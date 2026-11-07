"""
SQLite token pool repository for pre-captured nkparam search tokens.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from typing import Optional


class NkparamDB:
    """Manages active and consumed nkparam tokens in an SQLite pool."""

    def __init__(self, db_path: str = "nkparams.db") -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nkparams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nkparam TEXT UNIQUE,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def add_nkparam(self, nkparam: str) -> bool:
        if not nkparam or not nkparam.strip():
            return False
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO nkparams (nkparam, is_active) VALUES (?, 1)",
                (nkparam.strip(),),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_nkparam(self) -> Optional[str]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nkparam
                FROM nkparams
                WHERE is_active = 1
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                nk_id, nkparam = row
                cur.execute("UPDATE nkparams SET is_active = 0 WHERE id = ?", (nk_id,))
                conn.commit()
                return nkparam
            return None
        finally:
            conn.close()

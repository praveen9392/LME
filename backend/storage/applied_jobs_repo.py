"""
Repository for storing and deduplicating applied jobs in SQLite and CSV.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)

_CSV_FIELDS = ["hash", "job_id", "title", "company", "location", "ai_score", "applied_at"]


class AppliedJobsDB:
    """
    Thread-safe storage for applied jobs using SQLite and mirrored CSV.
    Deduplication key: 16-character hex prefix of SHA-256("{job_id}|{company.lower()}").
    """

    def __init__(self, db_path: str = "applied_jobs.db", csv_path: str = "applied_jobs.csv") -> None:
        self.db_path = str(db_path)
        self.csv_path = str(csv_path)
        self._init_db()
        self._init_csv()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_csv(self) -> None:
        if not os.path.exists(self.csv_path):
            try:
                Path(self.csv_path).parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=_CSV_FIELDS).writeheader()
            except Exception as exc:
                logger.warning("Could not initialize CSV applied jobs log: %s", exc)

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    hash        TEXT PRIMARY KEY,
                    job_id      TEXT NOT NULL,
                    title       TEXT,
                    company     TEXT,
                    location    TEXT,
                    ai_score    INTEGER,
                    applied_at  TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_id ON applied_jobs(job_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_applied_at ON applied_jobs(applied_at)")
            conn.commit()
        finally:
            conn.close()

    # ── Deduplication Key Hashing ────────────────────────────────────────────

    @staticmethod
    def _hash(job_id: str, company: str) -> str:
        """16-char hex prefix of SHA-256("{job_id}|{company_lower}")."""
        key = f"{str(job_id).strip()}|{(company or '').lower().strip()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    # ── Dedup Check ──────────────────────────────────────────────────────────

    def has_applied(self, job_id: str, company: str) -> bool:
        """
        Returns True if the job has been previously applied to.
        Checks both the compound hash and the raw job_id for legacy records.
        """
        h = self._hash(job_id, company)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM applied_jobs WHERE hash = ? OR job_id = ? LIMIT 1",
                (h, str(job_id)),
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    # ── Write Application ───────────────────────────────────────────────────

    def mark_applied(self, job: Any, ai_score: Optional[int] = None) -> str:
        """
        Records an application in both SQLite and CSV. Returns the generated hash.
        """
        job_id = getattr(job, "job_id", str(job))
        company = getattr(job, "company", "")
        title = getattr(job, "title", "")
        location = getattr(job, "location", "")

        h = self._hash(job_id, company)
        applied_at = datetime.now(timezone.utc).isoformat()

        self._insert_raw(h, job_id, title, company, location, ai_score, applied_at)
        self._append_csv(h, job_id, title, company, location, ai_score, applied_at)
        logger.info("Recorded application: %s @ %s [hash: %s, score: %s]", title, company, h, ai_score)
        return h

    def _append_csv(
        self,
        hash_id: str,
        job_id: str,
        title: str,
        company: str,
        location: str,
        ai_score: Optional[int],
        applied_at: str,
    ) -> None:
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=_CSV_FIELDS).writerow({
                    "hash": hash_id,
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "ai_score": ai_score if ai_score is not None else "",
                    "applied_at": applied_at,
                })
        except Exception as exc:
            logger.warning("Failed to append to CSV: %s", exc)

    def _insert_raw(
        self,
        hash_id: str,
        job_id: str,
        title: str,
        company: str,
        location: str,
        ai_score: Optional[int],
        applied_at: str,
    ) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT OR IGNORE INTO applied_jobs
                   (hash, job_id, title, company, location, ai_score, applied_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hash_id, str(job_id), title, company, location, ai_score, applied_at),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Read Applications ───────────────────────────────────────────────────

    def list_applied(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT hash, job_id, title, company, location, ai_score, applied_at
                   FROM applied_jobs
                   ORDER BY applied_at DESC
                   LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def total(self) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM applied_jobs")
            row = cur.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    # ── Delete Application (Re-apply feature) ────────────────────────────────

    def remove(self, hash_or_job_id: str) -> bool:
        """
        Removes an application record by hash or job_id.
        Allows the agent to re-apply to the job on subsequent runs.
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM applied_jobs WHERE hash = ? OR job_id = ?",
                (hash_or_job_id, hash_or_job_id),
            )
            conn.commit()
            deleted = cur.rowcount > 0
            if deleted:
                logger.info("Removed applied job record: %s", hash_or_job_id)
            return deleted
        finally:
            conn.close()

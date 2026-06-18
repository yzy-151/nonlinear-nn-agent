"""Minimal SQLite runtime control plane (v2.0.0).

Provides request deduplication, job leases with expiry, and monotonic
event sequencing — all backed by a single-file SQLite database.

Tables:
  requests — (session_id, request_id) UNIQUE, payload, status
  jobs     — job_id PK, session_id, request_id, lease_owner, lease_expires_at,
             max_attempts=3, attempts, status
  events   — event_id AUTOINCREMENT, session_id, sequence, event_type, payload

Key properties:
  - WAL mode for concurrent readers
  - busy_timeout=5000ms to reduce SQLITE_BUSY under contention
  - Atomic claim via UPDATE WHERE (no SELECT-then-UPDATE races)
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class RuntimeControlPlane:
    """SQLite-backed control plane for the Agent Harness Runtime."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
                session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                completed_at REAL,
                PRIMARY KEY (session_id, request_id)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                lease_owner TEXT,
                lease_expires_at REAL,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                completed_at REAL
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_session_seq
                ON events(session_id, sequence);
        """)
        self._conn.commit()

    # ── Request dedup ──────────────────────────────────────────
    def register_request(
        self, session_id: str, request_id: str, payload: str = "{}"
    ) -> bool:
        """Register a request. Returns True if new, False if duplicate."""
        now = time.time()
        try:
            self._conn.execute(
                "INSERT INTO requests(session_id, request_id, payload, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (session_id, request_id, payload, now),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # ── Job lease with atomic claim ────────────────────────────
    def enqueue_job(
        self, session_id: str, request_id: str, max_attempts: int = 3
    ) -> str:
        """Enqueue a job and return its job_id."""
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        self._conn.execute(
            "INSERT INTO jobs(job_id, session_id, request_id, status, "
            "max_attempts, created_at) VALUES (?, ?, ?, 'queued', ?, ?)",
            (job_id, session_id, request_id, max_attempts, now),
        )
        self._conn.commit()
        return job_id

    def claim_job(
        self, job_id: str, owner: str, lease_seconds: float = 60.0
    ) -> bool:
        """Atomically claim a queued job whose lease is expired or absent.

        Returns True if the claim succeeded (this caller owns the job).
        """
        now = time.time()
        cursor = self._conn.execute(
            """UPDATE jobs SET
                lease_owner = ?,
                lease_expires_at = ?,
                attempts = attempts + 1
            WHERE job_id = ?
            AND status = 'queued'
            AND (lease_expires_at IS NULL OR lease_expires_at < ?)
            AND attempts < max_attempts""",
            (owner, now + lease_seconds, job_id, now),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def complete_job(self, job_id: str) -> None:
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET status = 'completed', completed_at = ? WHERE job_id = ?",
            (now, job_id),
        )
        self._conn.commit()

    def fail_job(self, job_id: str) -> None:
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET status = 'failed', completed_at = ? WHERE job_id = ?",
            (now, job_id),
        )
        self._conn.commit()

    def fail_job_if_max_attempts(self, job_id: str) -> bool:
        """If attempts >= max_attempts, mark job as 'failed'. Returns True if failed."""
        cursor = self._conn.execute(
            "SELECT attempts, max_attempts FROM jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row and row[0] >= row[1]:
            self.fail_job(job_id)
            return True
        return False

    # ── Event sequencing ───────────────────────────────────────
    def record_event(
        self, session_id: str, event_type: str, payload: str = "{}"
    ) -> int:
        """Append an event and return its monotonic sequence number."""
        now = time.time()
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(sequence), -1) + 1 FROM events WHERE session_id = ?",
            (session_id,),
        )
        seq = cursor.fetchone()[0]
        self._conn.execute(
            "INSERT INTO events(session_id, sequence, event_type, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, seq, event_type, payload, now),
        )
        self._conn.commit()
        return seq

    def get_events_since(
        self, session_id: str, last_event_id: int = -1
    ) -> list[dict[str, Any]]:
        """Return events with sequence > last_event_id for SSE replay."""
        cursor = self._conn.execute(
            "SELECT sequence, event_type, payload FROM events "
            "WHERE session_id = ? AND sequence > ? ORDER BY sequence",
            (session_id, last_event_id),
        )
        return [
            {"id": seq, "event": etype, "data": json.loads(payload)}
            for seq, etype, payload in cursor.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()

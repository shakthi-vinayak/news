"""
worker/storage/db.py
SQLite schema, connection helpers, and CRUD operations.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Default DB path — override via DB_PATH env var or pass explicitly.
DEFAULT_DB_PATH = Path(__file__).parent.parent / "db" / "app.db"


# ── Schema ─────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS news (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    source          TEXT NOT NULL,
    published_at    TEXT,
    summary         TEXT,
    tags            TEXT DEFAULT '[]',   -- JSON array
    relevance_score REAL DEFAULT 0.0,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    url             TEXT NOT NULL,
    source          TEXT NOT NULL,
    location        TEXT,
    posted_at       TEXT,
    category        TEXT,
    relevance_score REAL DEFAULT 0.0,
    salary_range    TEXT,
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    news_collected  INTEGER DEFAULT 0,
    jobs_collected  INTEGER DEFAULT 0,
    errors          TEXT DEFAULT '[]'   -- JSON array of error strings
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_source    ON news(source);
CREATE INDEX IF NOT EXISTS idx_jobs_posted    ON jobs(posted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_source    ON jobs(source);
"""


# ── Connection ──────────────────────────────────────────────────────────────
def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    log.info("DB initialised at %s", db_path)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Helpers ─────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tags_to_json(tags: list[str] | None) -> str:
    return json.dumps(tags or [])


def _json_to_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


# ── News CRUD ───────────────────────────────────────────────────────────────
def upsert_news(conn: sqlite3.Connection, item: dict[str, Any]) -> bool:
    """Insert or update a news item. Returns True if newly inserted."""
    now = _now()
    existing = conn.execute(
        "SELECT id FROM news WHERE id = ?", (item["id"],)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE news
               SET last_seen_at    = ?,
                   summary         = COALESCE(?, summary),
                   tags            = COALESCE(?, tags),
                   relevance_score = CASE WHEN ? > 0 THEN ? ELSE relevance_score END
               WHERE id = ?""",
            (
                now,
                item.get("summary"),
                _tags_to_json(item.get("tags")) if item.get("tags") else None,
                item.get("relevance_score", 0),
                item.get("relevance_score", 0),
                item["id"],
            ),
        )
        return False
    else:
        conn.execute(
            """INSERT INTO news
               (id, title, url, source, published_at, summary, tags,
                relevance_score, first_seen_at, last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                item["id"],
                item["title"],
                item["url"],
                item["source"],
                item.get("published_at"),
                item.get("summary"),
                _tags_to_json(item.get("tags")),
                item.get("relevance_score", 0.0),
                now,
                now,
            ),
        )
        return True


def get_news(
    conn: sqlite3.Connection, *, days: int = 30, limit: int = 500
) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM news
           WHERE first_seen_at >= datetime('now', ?)
           ORDER BY published_at DESC
           LIMIT ?""",
        (f"-{days} days", limit),
    ).fetchall()
    return [_row_to_news_dict(r) for r in rows]


def _row_to_news_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = _json_to_tags(d.get("tags"))
    return d


# ── Jobs CRUD ───────────────────────────────────────────────────────────────
def upsert_job(conn: sqlite3.Connection, item: dict[str, Any]) -> bool:
    """Insert or update a job item. Returns True if newly inserted."""
    now = _now()
    existing = conn.execute(
        "SELECT id FROM jobs WHERE id = ?", (item["id"],)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE jobs
               SET last_seen_at    = ?,
                   relevance_score = CASE WHEN ? > 0 THEN ? ELSE relevance_score END,
                   category        = COALESCE(?, category),
                   salary_range    = COALESCE(?, salary_range)
               WHERE id = ?""",
            (
                now,
                item.get("relevance_score", 0),
                item.get("relevance_score", 0),
                item.get("category"),
                item.get("salary_range"),
                item["id"],
            ),
        )
        return False
    else:
        conn.execute(
            """INSERT INTO jobs
               (id, title, company, url, source, location, posted_at,
                category, relevance_score, salary_range, first_seen_at, last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item["id"],
                item["title"],
                item.get("company", ""),
                item["url"],
                item["source"],
                item.get("location"),
                item.get("posted_at"),
                item.get("category"),
                item.get("relevance_score", 0.0),
                item.get("salary_range"),
                now,
                now,
            ),
        )
        return True


def get_jobs(
    conn: sqlite3.Connection, *, days: int = 30, limit: int = 500
) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM jobs
           WHERE first_seen_at >= datetime('now', ?)
           ORDER BY posted_at DESC
           LIMIT ?""",
        (f"-{days} days", limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Run log ─────────────────────────────────────────────────────────────────
def start_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute(
        "INSERT INTO run_log (run_id, started_at, errors) VALUES (?,?,?)",
        (run_id, _now(), "[]"),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    news_collected: int = 0,
    jobs_collected: int = 0,
    errors: list[str] | None = None,
) -> None:
    conn.execute(
        """UPDATE run_log
           SET finished_at    = ?,
               news_collected = ?,
               jobs_collected = ?,
               errors         = ?
           WHERE run_id = ?""",
        (
            _now(),
            news_collected,
            jobs_collected,
            json.dumps(errors or []),
            run_id,
        ),
    )
    conn.commit()

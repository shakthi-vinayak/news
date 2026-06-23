"""
worker/storage/export_json.py
Reads from SQLite and writes docs/data/news.json, jobs.json, meta.json.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.db import get_jobs, get_news

log = logging.getLogger(__name__)

DOCS_DATA_PATH = Path(__file__).parent.parent.parent / "docs" / "data"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    log.info("Wrote %s (%d bytes)", path.name, path.stat().st_size)


def export_all(
    conn: sqlite3.Connection,
    *,
    output_dir: Path | None = None,
    retention_days: int = 30,
    source_health: dict[str, str] | None = None,
) -> dict[str, int]:
    """
    Export news + jobs to static JSON files.

    Returns a dict with counts: {"news": N, "jobs": M}.
    """
    out = output_dir or DOCS_DATA_PATH
    out.mkdir(parents=True, exist_ok=True)

    generated_at = _now_iso()

    # ── News ──────────────────────────────────────────────────────────
    news_items = get_news(conn, days=retention_days)
    # Ensure tags is always a list (just in case)
    for item in news_items:
        if not isinstance(item.get("tags"), list):
            item["tags"] = []
        # Remove internal DB fields that shouldn't appear in JSON
        item.pop("first_seen_at", None)
        item.pop("last_seen_at", None)

    news_payload = {
        "generated_at": generated_at,
        "items": news_items,
    }
    _write_json(out / "news.json", news_payload)

    # ── Jobs ──────────────────────────────────────────────────────────
    job_items = get_jobs(conn, days=retention_days)
    for item in job_items:
        item.pop("first_seen_at", None)
        item.pop("last_seen_at", None)

    jobs_payload = {
        "generated_at": generated_at,
        "items": job_items,
    }
    _write_json(out / "jobs.json", jobs_payload)

    # ── Meta ──────────────────────────────────────────────────────────
    meta_payload = {
        "generated_at": generated_at,
        "news_count": len(news_items),
        "jobs_count": len(job_items),
        "source_health": source_health or {},
    }
    _write_json(out / "meta.json", meta_payload)

    log.info(
        "Export complete: %d news, %d jobs -> %s",
        len(news_items),
        len(job_items),
        out,
    )
    return {"news": len(news_items), "jobs": len(job_items)}
